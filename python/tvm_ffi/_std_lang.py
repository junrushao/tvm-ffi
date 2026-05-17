# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Language modules used by the Python-shaped IR parser."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any as TypingAny
from typing import Callable, ClassVar, cast

from tvm_ffi.structural import structural_equal

from . import dtype, std
from ._pyast_parser import (
    Factory,
    Frame,
    TyFactory,
    normalize_ty,
    register_dialect,
)


class PrimTyFactory(TyFactory):
    """Factory for a named primitive type alias."""

    def __init__(self, dtype: str) -> None:
        """Create a primitive type alias exposed as ``std.i32`` and similar names."""
        self.ty = std.PrimTy(dtype)

    def to_dialect(self) -> std.PrimTy:
        """Return the primitive dialect type for annotation and constructor syntax."""
        return self.ty

    def __call__(self, value: TypingAny) -> std.Expr:
        """Treat primitive type calls over literals as typed immediates."""
        literal = self.ty.coerce_literal(value)
        if literal is not None:
            return literal
        return self._make_cast(value)

    def __getitem__(self, indices: Sequence[TypingAny]) -> std.Ty:
        """Treat indexing a scalar type as tensor type syntax, like ``std.f32[16]``."""
        if len(indices) == 1 and isinstance(indices[0], tuple):
            indices = indices[0]
        ty = self.to_dialect()
        return std.TensorTy(shape=indices, dtype=ty.dtype)


class AnyTyFactory(TyFactory):
    """Factory for the parser fallback ``std.Any`` type."""

    def __init__(self) -> None:
        """Create the singleton parser-side ``std.Any`` factory."""
        self.ty = std.AnyTy()

    def to_dialect(self) -> std.AnyTy:
        """Return the dialect ``std.AnyTy`` node."""
        return self.ty

    def __call__(self, value: TypingAny) -> std.Expr:
        """Treat ``std.Any(x)`` as an explicit cast to the fallback type."""
        return self._make_cast(value)

    def __getitem__(self, indices: Sequence[TypingAny]) -> std.Ty:
        """Reject ``std.Any[...]`` because tensor syntax needs a concrete dtype."""
        del indices
        raise TypeError(
            "std.Any cannot be indexed as a tensor type; use std.f32[...] or another concrete dtype"
        )


class TupleTyFactory(TyFactory):
    """Factory for tuple type syntax."""

    def __call__(self, *fields: TypingAny) -> std.TupleTy:
        """Build ``std.TupleTy`` from call syntax such as ``std.Tuple(std.i32)``."""
        return std.TupleTy([normalize_ty(field) for field in fields])

    def __getitem__(self, indices: Sequence[TypingAny]) -> std.TupleTy:
        """Build tuple types from printed syntax such as ``std.Tuple[std.i32]``."""
        if len(indices) == 1 and isinstance(indices[0], tuple):
            indices = indices[0]
        return self(*indices)

    def to_dialect(self) -> std.Ty:
        """Reject bare ``std.Tuple`` because field types are required."""
        raise TypeError("std.Tuple requires field types")


class PrimFactory(Factory):
    """Explicit primitive type constructor for ``std.Prim(...)`` syntax."""

    def __call__(self, dtype: TypingAny) -> std.PrimTy:
        """Build a primitive type from a dtype string or dtype alias."""
        return std.PrimTy(dtype)


class TensorFactory(Factory):
    """Explicit tensor type constructor for ``std.Tensor(...)`` syntax."""

    def __call__(self, shape: Sequence[TypingAny], dtype: TypingAny) -> std.TensorTy:
        """Build a tensor type from an explicit shape and dtype."""
        return std.TensorTy(shape=list(shape), dtype=dtype)


class FuncFactory(Frame):
    """Parser frame for ``@std.func`` function definitions."""

    def __init__(self, **attrs: TypingAny) -> None:
        """Create an empty function frame with optional function attributes."""
        self.attrs = dict(attrs)
        self.symbol = ""
        self.args: list[std.Var] = []
        self.ret_type: std.Ty | None = None
        self.body: list[TypingAny] = []

    def make_arg(self, name: str, ty: std.Ty) -> std.Var:
        """Create a function argument variable from a parameter annotation."""
        return std.Var(normalize_ty(ty), name)

    def to_dialect(self) -> std.Func:
        """Build the final ``std.Func`` after the parser has filled the frame body."""
        return std.Func(
            symbol=self.symbol,
            args=self.args,
            ret_type=self.ret_type,
            body=self.body,
            attrs=self.attrs or None,
        )


class ModuleFactory(Frame):
    """Parser frame for ``@std.module`` class definitions."""

    def __init__(self, **attrs: TypingAny) -> None:
        """Create an empty module frame and reject unsupported module attributes."""
        if attrs:
            raise TypeError("std.Module does not accept attributes")
        self.body: list[TypingAny] = []

    def to_dialect(self) -> std.Module:
        """Build a ``std.Module`` from class-body functions.

        Used by the module printer form where modules are represented as a
        decorated class containing ``@std.func`` methods.
        """
        funcs = [stmt for stmt in self.body if isinstance(stmt, std.Func)]
        if len(funcs) != len(self.body):
            bad = next(stmt for stmt in self.body if not isinstance(stmt, std.Func))
            raise TypeError(
                f"std.Module body can only contain std.Func definitions, got {type(bad).__name__}"
            )
        return std.Module(funcs)


class RegionFactory(Frame):
    """Base frame for body-bearing region statements with optional bindings."""

    node_cls: TypingAny = std.Scope

    def __init__(self, binds: Sequence[std.Stmt] | None = None, **attrs: TypingAny) -> None:
        """Create a region frame from placeholder binds and attributes."""
        self.attrs = dict(attrs)
        self.binds: list[std.Stmt] = list(binds or [])
        self.body: list[TypingAny] = []

    def bind_names(self, names: Sequence[str]) -> None:
        """Rename placeholder bind variables to match ``for`` or ``with as`` targets."""
        num_bind_vars = sum(len(cast(TypingAny, bind).vars) for bind in self.binds)
        if len(names) != num_bind_vars:
            raise TypeError(f"expected {num_bind_vars} binding target(s), got {len(names)}")

        rebuilt: list[std.Stmt] = []
        offset = 0
        for bind in self.binds:
            bind_vars = cast(TypingAny, bind).vars
            count = len(bind_vars)
            new_vars = [std.Var(bind_vars[i].ty, names[offset + i]) for i in range(count)]
            offset += count
            if isinstance(bind, std.BindExpr):
                attrs = cast(TypingAny, bind.attrs)
                rebuilt.append(std.BindExpr(bind.expr, *new_vars, **(attrs or {})))
            elif isinstance(bind, std.VarDef):
                attrs = cast(TypingAny, bind.attrs)
                rebuilt.append(std.VarDef(*new_vars, **(attrs or {})))
            else:
                raise TypeError(f"unsupported bind type: {type(bind).__name__}")
        self.binds = rebuilt

    def bound_vars(self) -> list[std.Var]:
        """Return variables introduced by the region header."""
        return [var for bind in self.binds for var in cast(TypingAny, bind).vars]

    def to_dialect(self) -> std.Stmt:
        """Build the concrete region statement after its body has been parsed."""
        return self.node_cls(
            binds=self.binds,
            body=self.body,
            attrs=self.attrs or None,
        )


class ScopeFactory(RegionFactory):
    """Parser frame for ``std.scope`` and ``with std.scope(...)`` syntax."""

    node_cls = std.Scope


class ForFactory(Frame):
    """Parser frame for ``for`` loops and explicit ``std.For`` construction."""

    def __init__(
        self,
        start: TypingAny | None,
        stop: TypingAny | None,
        step: TypingAny | None,
        *,
        ty: std.TyLike | None = None,
        **attrs: TypingAny,
    ) -> None:
        """Create a loop frame with a placeholder induction variable."""
        self.start = start
        self.stop = stop
        self.step = step
        for value in (start, stop, step):
            if value is None or isinstance(value, int):
                continue
            if not isinstance(value, std.Expr):
                raise TypeError(
                    f"range expects Python integers or integer expressions, got {type(value).__name__}"
                )
            if isinstance(value.ty, (std.AnyTy, std.PrimTy)):
                ty = value.ty
            elif isinstance(value, str) and dtype.is_dtype(value):
                ty = std.PrimTy(value)
            else:
                raise TypeError(
                    f"Range expression must have a Python integer or an std.Expr with integer type, got {value.ty.text()}"
                )
        if ty is None:
            ty = std.PrimTy("int64")
        self.attrs = dict(attrs)
        self.vars: list[std.Var] = [std.Var(ty, "")]
        self.body: list[TypingAny] = []

    def bind_names(self, names: Sequence[str]) -> None:
        """Rename placeholder loop variables to match the ``for`` target."""
        if len(names) != len(self.vars):
            raise TypeError(f"expected {len(self.vars)} binding target(s), got {len(names)}")
        self.vars = [std.Var(var.ty, name) for var, name in zip(self.vars, names)]

    def bound_vars(self) -> list[std.Var]:
        """Return variables introduced by the loop header."""
        return list(self.vars)

    def to_dialect(self) -> std.For:
        """Build a ``std.For`` after the target name and body are known."""
        return std.For(
            start=self.start,
            stop=self.stop,
            step=self.step,
            vars=self.vars,
            body=self.body,
            attrs=self.attrs or None,
        )


class WhileFactory(Frame):
    """Parser frame for Python ``while`` and explicit ``std.while_`` regions."""

    def __init__(
        self,
        cond: TypingAny,
        **attrs: TypingAny,
    ) -> None:
        """Create a while frame with a condition and optional attributes."""
        self.attrs = dict(attrs)
        self.cond = cond
        self.body: list[TypingAny] = []

    def to_dialect(self) -> std.While:
        """Build a ``std.While`` after its body has been parsed."""
        return std.While(
            cond=self.cond,
            body=self.body,
            attrs=self.attrs or None,
        )


class Std:
    """Parser language module for the standard dialect."""

    __ffi_globals__: ClassVar[dict[str, TypingAny]]
    __ffi_generics__: ClassVar[dict[TypingAny, Callable[..., TypingAny]]]

    Any = AnyTyFactory()
    Tuple = TupleTyFactory()
    Prim = PrimFactory()
    Tensor = TensorFactory()

    Node = std.Node
    Ty = std.Ty
    Stmt = std.Stmt
    Attrs = std.Attrs
    Aggregate = std.Aggregate
    Expr = std.Expr
    BindExpr = std.BindExpr
    VarDef = std.VarDef

    bool = PrimTyFactory("bool")
    i8 = PrimTyFactory("int8")
    i16 = PrimTyFactory("int16")
    i32 = PrimTyFactory("int32")
    i64 = PrimTyFactory("int64")
    u8 = PrimTyFactory("uint8")
    u16 = PrimTyFactory("uint16")
    u32 = PrimTyFactory("uint32")
    u64 = PrimTyFactory("uint64")
    f16 = PrimTyFactory("float16")
    f32 = PrimTyFactory("float32")
    f64 = PrimTyFactory("float64")
    bf16 = PrimTyFactory("bfloat16")
    f8_e3m4 = PrimTyFactory("float8_e3m4")
    f8_e4m3 = PrimTyFactory("float8_e4m3")
    f8_e4m3b11fnuz = PrimTyFactory("float8_e4m3b11fnuz")
    f8_e4m3fn = PrimTyFactory("float8_e4m3fn")
    f8_e4m3fnuz = PrimTyFactory("float8_e4m3fnuz")
    f8_e5m2 = PrimTyFactory("float8_e5m2")
    f8_e5m2fnuz = PrimTyFactory("float8_e5m2fnuz")
    f8_e8m0fnu = PrimTyFactory("float8_e8m0fnu")
    f6_e2m3fn = PrimTyFactory("float6_e2m3fn")
    f6_e3m2fn = PrimTyFactory("float6_e3m2fn")
    f4_e2m1fn = PrimTyFactory("float4_e2m1fn")
    f4_e2m1fnx2 = PrimTyFactory("float4_e2m1fnx2")

    DictAttrs = std.DictAttrs
    Func = std.Func
    Module = std.Module
    Range = std.Range
    AnyTy = std.AnyTy
    PrimTy = std.PrimTy
    TupleTy = std.TupleTy
    TensorTy = std.TensorTy
    IntImm = std.IntImm
    FloatImm = std.FloatImm
    StringImm = std.StringImm
    BoolImm = std.BoolImm
    Var = std.Var

    Add = std.Add
    Sub = std.Sub
    Mul = std.Mul
    CDiv = std.CDiv
    FloorDiv = std.FloorDiv
    FloorMod = std.FloorMod
    CMod = std.CMod
    Pow = std.Pow
    LShift = std.LShift
    RShift = std.RShift
    BitwiseAnd = std.BitwiseAnd
    BitwiseOr = std.BitwiseOr
    BitwiseXor = std.BitwiseXor
    Min = std.Min
    Max = std.Max
    Eq = std.Eq
    Ne = std.Ne
    Le = std.Le
    Ge = std.Ge
    Gt = std.Gt
    Lt = std.Lt
    And = std.And
    Or = std.Or

    Not = std.Not
    BitwiseNot = std.BitwiseNot
    Abs = std.Abs
    IfExpr = std.IfExpr
    Load = std.Load
    Cast = std.Cast
    Call = std.Call
    IfStmt = std.IfStmt
    Scope = std.Scope
    For = std.For
    While = std.While
    Store = std.Store
    Assert = std.Assert
    Return = std.Return
    Yield = std.Yield
    Break = std.Break
    Continue = std.Continue

    func = FuncFactory
    module = ModuleFactory
    while_ = WhileFactory
    min = std.min
    max = std.max
    abs = std.abs

    @staticmethod
    def range(*args: TypingAny, **attrs: TypingAny) -> ForFactory:
        """Create a loop frame for parser-visible Python range loops."""
        if len(args) == 1:
            start, stop, step = None, args[0], None
        elif len(args) == 2:
            start, stop, step = args[0], args[1], None
        elif len(args) == 3:
            start, stop, step = args
        else:
            raise TypeError("range expects 1 to 3 positional arguments")
        return ForFactory(start, stop, step, **attrs)

    @staticmethod
    def scope(*binds: TypingAny, **kwargs: TypingAny) -> ScopeFactory:
        """Create the parser frame used by ``with std.scope(...)`` syntax."""
        return ScopeFactory(_normalize_binds(binds), **kwargs)

    @staticmethod
    def for_(range_: TypingAny = None, **kwargs: TypingAny) -> ForFactory:
        """Create the parser frame used by explicit ``std.for_(...)`` loop headers."""
        if isinstance(range_, std.Range):
            return ForFactory(range_.start, range_.stop, range_.step, **kwargs)
        return ForFactory(None, range_, None, **kwargs)


def _normalize_binds(values: Sequence[TypingAny]) -> list[std.Stmt]:
    """Convert explicit region bind initializers into binding statements.

    Used by ``std.scope(...)``, ``std.while_(...)``, and ``std.for_(...)`` factory
    syntax.  Existing binds are preserved, types become variable definitions,
    and expressions or literals become expression binds with placeholder names.
    """
    binds: list[std.Stmt] = []
    for value in values:
        if isinstance(value, (std.BindExpr, std.VarDef)):
            binds.append(value)
        elif isinstance(value, std.Ty) or hasattr(value, "to_dialect"):
            ty = normalize_ty(value)
            binds.append(std.VarDef(std.Var(ty, "")))
        elif isinstance(value, std.Expr) or isinstance(value, (bool, int, float, str)):
            literal = std.Expr.literal(value)
            binds.append(std.BindExpr(literal, std.Var(literal.ty, "")))
        else:
            raise TypeError(f"expected bind initializer, got {type(value).__name__}")
    return binds


def _bind_expr_from_names(
    names: Sequence[str],
    ty: std.TyLike | None,
    expr: std.ExprLike | std.BindExpr,
) -> std.BindExpr:
    """Build assignment bindings once the left-hand names are known."""

    def _materialize_literal(value: std.ExprLike, ty: std.TyLike) -> std.Expr:
        """Convert native literals to typed or default dialect immediates."""
        if not isinstance(value, (bool, int, float, str)):
            return value
        ty = normalize_ty(ty)
        if isinstance(ty, std.PrimTy):
            literal = ty.coerce_literal(value)
            if literal is not None:
                return literal
        return std.Expr.literal(value)

    attrs = None
    if isinstance(expr, std.BindExpr):
        if expr.vars:
            raise TypeError("std.BindExpr RHS must not already define vars")
        attrs = cast(TypingAny, expr.attrs)
        expr = expr.expr

    if ty is None:
        expr = std.Expr.literal(expr)
        bind_ty = expr.ty
    else:
        bind_ty = normalize_ty(ty)
        expr = _materialize_literal(expr, bind_ty)
        expr_ty = expr.ty
        if (
            not isinstance(bind_ty, std.AnyTy)
            and not isinstance(expr_ty, std.AnyTy)
            and not structural_equal(bind_ty, expr_ty)
        ):
            raise TypeError(
                f"type mismatch: {bind_ty.text()} vs {expr_ty.text()}; "
                "use an explicit cast on the rhs"
            )

    vars = [std.Var(bind_ty, name) for name in names]
    return std.BindExpr(expr, *vars, **(attrs or {}))


def _bind_var_def_from_names(names: Sequence[str], *tys: TypingAny) -> std.VarDef:
    """Build annotated variable definitions from left-hand names and types."""
    if len(tys) == 1 and isinstance(tys[0], std.VarDef):
        bind = tys[0]
        if len(bind.vars) != len(names):
            raise TypeError(f"expected {len(bind.vars)} binding target(s), got {len(names)}")
        vars = [std.Var(var.ty, name) for var, name in zip(bind.vars, names)]
        attrs = cast(TypingAny, bind.attrs)
        return std.VarDef(*vars, **(attrs or {}))
    if len(names) != len(tys):
        raise TypeError(f"expected {len(tys)} binding target(s), got {len(names)}")
    vars = [std.Var(normalize_ty(ty), name) for name, ty in zip(names, tys)]
    return std.VarDef(*vars)


def _make_call(callee: TypingAny, *args: TypingAny) -> std.Call:
    """Build a call from generic call syntax."""
    return std.Call(callee, *args, ty=std.AnyTy())


def _make_floordiv(lhs: TypingAny, rhs: TypingAny) -> std.Expr:
    """Build integer floor division from the parser ``//`` generic."""
    result = std.floordiv(lhs, rhs)
    ty = result.ty
    dtype = ty.dtype if isinstance(ty, (std.PrimTy, std.TensorTy)) else None
    if dtype is None or not dtype.is_integer:
        raise TypeError(f"__floordiv__ only supports integer types, got {ty.text()}")
    return result


def _make_mod(lhs: TypingAny, rhs: TypingAny) -> std.Expr:
    """Build modulo from the parser ``%`` generic based on the resolved type."""
    ty = std.add(lhs, rhs).ty
    dtype = ty.dtype if isinstance(ty, (std.PrimTy, std.TensorTy)) else None
    if dtype is not None and dtype.is_float:
        return std.cmod(lhs, rhs)
    if dtype is None or not dtype.is_integer:
        raise TypeError(f"__mod__ only supports integer types, got {ty.text()}")
    return std.floormod(lhs, rhs)


Std.__ffi_globals__ = {
    "range": Std.range,
    "min": Std.min,
    "max": Std.max,
    "abs": Std.abs,
}

Std.__ffi_generics__ = {
    "__add__": std.add,
    "__sub__": std.sub,
    "__mul__": std.mul,
    "__truediv__": std.cdiv,
    "__floordiv__": _make_floordiv,
    "__mod__": _make_mod,
    "__pow__": std.pow,
    "__lshift__": std.left_shift,
    "__rshift__": std.right_shift,
    "__and__": std.bitwise_and,
    "__or__": std.bitwise_or,
    "__xor__": std.bitwise_xor,
    "min": std.min,
    "max": std.max,
    "__eq__": std.eq,
    "__ne__": std.ne,
    "__le__": std.le,
    "__ge__": std.ge,
    "__gt__": std.gt,
    "__lt__": std.lt,
    "__logical_and__": std.logical_and,
    "__logical_or__": std.logical_or,
    "__invert__": std.bitwise_not,
    "__not__": std.logical_not,
    "__neg__": std.neg,
    "__pos__": lambda x: x,
    "__if_then_else__": std.if_then_else,
    "__load__": std.Load,
    "__slice__": std.Range,
    "__cast__": std.cast,
    "__call__": _make_call,
    "__store__": std.Store,
    "__if__": std.IfStmt,
    "__while__": WhileFactory,
    "__assert__": std.Assert,
    "__return__": std.Return,
    "__yield__": std.Yield,
    "__break__": std.Break,
    "__continue__": std.Continue,
    # Literal materialization generics use std.Expr.literal defaults:
    # bool -> BoolImm[bool], int -> IntImm[int64], float -> FloatImm[float32],
    # str -> StringImm[AnyTy].
    "__literal_bool__": std.BoolImm.from_py,
    "__literal_int__": std.IntImm.from_py,
    "__literal_float__": std.FloatImm.from_py,
    "__literal_str__": std.StringImm.from_py,
    # Binding generics:
    # - "__bind_expr__": (names: Names, ty: TypeLike | None, expr: ExprLike | std.BindExpr)
    #   -> std.BindExpr.
    # - "__bind_var_def__": (names: Names, *tys: TypeLike) -> std.VarDef.
    # - "__bind_var_def__": (names: Names, bind: std.VarDef) -> std.VarDef.
    "__bind_expr__": _bind_expr_from_names,
    "__bind_var_def__": _bind_var_def_from_names,
}
register_dialect("std", Std)
