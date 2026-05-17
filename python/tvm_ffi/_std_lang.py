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

from tvm_ffi.core import MISSING

from . import std
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

    def __call__(self, value: TypingAny) -> std.Cast:
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
        vars_in_order = [(bind, var) for bind in self.binds for var in _binding_vars(bind)]
        if len(names) != len(vars_in_order):
            raise TypeError(f"expected {len(vars_in_order)} binding target(s), got {len(names)}")

        rebuilt: list[std.Stmt] = []
        offset = 0
        for bind in self.binds:
            bind_vars = _binding_vars(bind)
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
        return [var for bind in self.binds for var in _binding_vars(bind)]

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
        **attrs: TypingAny,
    ) -> None:
        """Create a loop frame with a placeholder induction variable."""
        self.start = start
        self.stop = stop
        self.step = step
        range_values = tuple(MISSING if value is None else value for value in (start, stop, step))
        loop_ty = (
            std.PrimTy("int64")
            if all(MISSING.is_(value) for value in range_values)
            else _find_common_ty(*range_values)
        )
        self.attrs = dict(attrs)
        self.vars: list[std.Var] = [std.Var(loop_ty, "")]
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


def _make_binary_generic(op_cls: type) -> Callable[..., std.Expr]:
    """Create a binary expression generic that infers its result type."""

    def generic(lhs: TypingAny, rhs: TypingAny) -> std.Expr:
        ty = _find_common_ty(lhs, rhs)
        return op_cls(lhs, rhs, ty=ty)

    return generic


def _bool_like_ty(ty: std.Ty) -> std.Ty:
    """Return the boolean result type matching a value type's shape/lanes."""
    if isinstance(ty, std.AnyTy):
        return ty
    if isinstance(ty, std.PrimTy):
        return std.PrimTy(std.PrimTy("bool").dtype.with_lanes(ty.dtype.lanes))
    if isinstance(ty, std.TensorTy):
        return std.TensorTy(list(ty.shape), std.PrimTy("bool").dtype.with_lanes(ty.dtype.lanes))
    return std.AnyTy()


def _make_bool_binary_generic(op_cls: type) -> Callable[..., std.Expr]:
    """Create a binary generic whose result is bool-shaped."""

    def generic(lhs: TypingAny, rhs: TypingAny) -> std.Expr:
        value_ty = _find_common_ty(lhs, rhs)
        return op_cls(lhs, rhs, ty=_bool_like_ty(value_ty))

    return generic


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

    @staticmethod
    def func(**attrs: TypingAny) -> FuncFactory:
        """Create the parser frame used by ``@std.func`` syntax."""
        return FuncFactory(**attrs)

    @staticmethod
    def module(**attrs: TypingAny) -> ModuleFactory:
        """Create the parser frame used by ``@std.module`` syntax."""
        return ModuleFactory(**attrs)

    @staticmethod
    def while_(cond: TypingAny, **attrs: TypingAny) -> WhileFactory:
        """Create the parser frame used by ``with std.while_(...)`` syntax."""
        return WhileFactory(cond, **attrs)

    @staticmethod
    def min(lhs: TypingAny, rhs: TypingAny) -> std.Min:
        """Create the parser-visible ``min`` expression."""
        return std.Min(lhs, rhs, ty=_find_common_ty(lhs, rhs))

    @staticmethod
    def max(lhs: TypingAny, rhs: TypingAny) -> std.Max:
        """Create the parser-visible ``max`` expression."""
        return std.Max(lhs, rhs, ty=_find_common_ty(lhs, rhs))

    @staticmethod
    def abs(value: TypingAny) -> std.Abs:
        """Create the parser-visible ``abs`` expression."""
        return std.Abs(value, ty=_parse_value_ty(value))

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
            frame = ForFactory(range_.start, range_.stop, range_.step, **kwargs)
        else:
            frame = ForFactory(None, range_, None, **kwargs)
        return frame


def _same_ty(lhs: std.Ty, rhs: std.Ty) -> bool:
    """Compare two dialect types structurally for parser type inference."""
    from tvm_ffi.structural import structural_equal  # noqa: PLC0415

    return structural_equal(lhs, rhs)


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


def _parse_value_ty(value: std.ExprLike) -> std.Ty:
    """Infer a standard dialect type for parsed values and native literals."""
    if isinstance(value, std.Expr):
        return value.ty
    if isinstance(value, bool):
        return std.PrimTy("bool")
    if isinstance(value, int):
        return std.PrimTy("int64")
    if isinstance(value, float):
        return std.PrimTy("float32")
    return std.AnyTy()


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
        if not isinstance(bind_ty, std.AnyTy) and not isinstance(expr_ty, std.AnyTy):
            if not _same_ty(bind_ty, expr_ty):
                raise TypeError(
                    f"type mismatch: {bind_ty.text()} vs {expr_ty.text()}; "
                    "use an explicit cast on the rhs"
                )

    vars = [std.Var(bind_ty, name) for name in names]
    return std.BindExpr(expr, *vars, **(attrs or {}))


def _bind_var_def_from_names(names: Sequence[str], tys: Sequence[TypingAny]) -> std.VarDef:
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


def _binding_vars(bind: std.Stmt) -> Sequence[std.Var]:
    """Return variables carried by supported binding statements."""
    if isinstance(bind, (std.BindExpr, std.VarDef)):
        return bind.vars
    raise TypeError(f"unsupported bind type: {type(bind).__name__}")


def _element_ty(base_ty: std.Ty, indices: Sequence[TypingAny]) -> std.Ty:
    """Infer the result type of a load from a base type and index count."""
    num_indices = len(indices)
    if num_indices == 0:
        return base_ty
    result = base_ty
    if isinstance(base_ty, std.AnyTy):
        result = std.AnyTy()
    elif isinstance(base_ty, std.TensorTy):
        rank = len(base_ty.shape)
        if num_indices >= rank:
            result = std.PrimTy(base_ty.dtype)
        else:
            result = std.TensorTy(list(base_ty.shape)[num_indices:], base_ty.dtype)
    elif isinstance(base_ty, std.TupleTy):
        index = indices[0]
        if isinstance(index, int):
            fields = list(base_ty.fields)
            try:
                field_ty = fields[index]
            except IndexError:
                result = std.AnyTy()
            else:
                result = _element_ty(field_ty, indices[1:])
        else:
            result = std.AnyTy()
    return result


def _make_load(args: Sequence[TypingAny]) -> std.Load:
    """Build a load from generic index syntax."""
    if len(args) < 1:
        raise TypeError("std.Load expects at least an expression")
    lhs = args[0]
    indices = args[1:]
    if not isinstance(lhs, std.Expr):
        raise TypeError(f"std.Load base must be an expression, got {type(lhs).__name__}")
    ty = _element_ty(lhs.ty, indices)
    return std.Load(lhs, *indices, ty=ty)


def _find_common_ty(*args: TypingAny) -> std.Ty:
    """Choose a result type for binary-like expressions from parser values.

    Used by arithmetic, comparisons, logical ops, and range type inference.
    ``MISSING`` values are skipped, matching types are kept, native literals may
    adopt a non-literal primitive type, ``std.Any`` dominates typed operands, and
    remaining mismatches are reported as parse errors.
    """
    ty: std.Ty | None = None
    ty_value: TypingAny = MISSING
    for value in args:
        if MISSING.is_(value):
            continue

        next_ty = _parse_value_ty(value)
        if ty is None:
            ty = next_ty
            ty_value = value
            continue
        if _same_ty(ty, next_ty):
            continue
        ty_value_is_literal = isinstance(ty_value, (bool, int, float, str))
        value_is_literal = isinstance(value, (bool, int, float, str))
        if ty_value_is_literal and not value_is_literal and isinstance(next_ty, std.PrimTy):
            can_adopt = (
                isinstance(ty_value, int)
                and (next_ty.dtype.is_bool or next_ty.dtype.is_integer or next_ty.dtype.is_float)
            ) or (isinstance(ty_value, float) and next_ty.dtype.is_float)
            if can_adopt:
                ty = next_ty
                ty_value = value
                continue
        if value_is_literal and not ty_value_is_literal and isinstance(ty, std.PrimTy):
            can_adopt = (
                isinstance(value, int)
                and (ty.dtype.is_bool or ty.dtype.is_integer or ty.dtype.is_float)
            ) or (isinstance(value, float) and ty.dtype.is_float)
            if can_adopt:
                continue
        if isinstance(ty, std.AnyTy):
            continue
        if isinstance(next_ty, std.AnyTy):
            ty = next_ty
            ty_value = value
            continue
        hint = (
            f"; cast literal {ty_value!r} with {next_ty.text()}({ty_value!r})"
            if ty_value_is_literal and not value_is_literal
            else f"; cast literal {value!r} with {ty.text()}({value!r})"
            if value_is_literal and not ty_value_is_literal
            else f"; cast literals explicitly, for example {next_ty.text()}({ty_value!r})"
            if ty_value_is_literal and not _same_ty(next_ty, ty)
            else f"; cast literals explicitly, for example {ty.text()}({value!r})"
            if value_is_literal and not _same_ty(ty, next_ty)
            else "; explicit casts are required, for example std.i64(0)"
        )
        raise TypeError(f"type mismatch: {ty.text()} vs {next_ty.text()}{hint}")

    if ty is None:
        raise TypeError("cannot infer type from missing values")
    return ty


def _make_floordiv(lhs: TypingAny, rhs: TypingAny) -> std.FloorDiv:
    """Build integer floor division from the parser ``//`` generic."""
    ty = _find_common_ty(lhs, rhs)
    dtype = ty.dtype if isinstance(ty, (std.PrimTy, std.TensorTy)) else None
    if dtype is None or not dtype.is_integer:
        raise TypeError(f"__floordiv__ only supports integer types, got {ty.text()}")
    return std.FloorDiv(lhs, rhs, ty=ty)


def _make_mod(lhs: TypingAny, rhs: TypingAny) -> std.FloorMod | std.CMod:
    """Build modulo from the parser ``%`` generic based on the resolved type."""
    ty = _find_common_ty(lhs, rhs)
    dtype = ty.dtype if isinstance(ty, (std.PrimTy, std.TensorTy)) else None
    if dtype is not None and dtype.is_float:
        return std.CMod(lhs, rhs, ty=ty)
    if dtype is None or not dtype.is_integer:
        raise TypeError(f"__mod__ only supports integer types, got {ty.text()}")
    return std.FloorMod(lhs, rhs, ty=ty)


Std.__ffi_globals__ = {
    "range": Std.range,
    "min": Std.min,
    "max": Std.max,
    "abs": Std.abs,
}

Std.__ffi_generics__ = {
    "__add__": _make_binary_generic(std.Add),
    "__sub__": _make_binary_generic(std.Sub),
    "__mul__": _make_binary_generic(std.Mul),
    "__truediv__": _make_binary_generic(std.CDiv),
    "__floordiv__": _make_floordiv,
    "__mod__": _make_mod,
    "__pow__": _make_binary_generic(std.Pow),
    "__lshift__": _make_binary_generic(std.LShift),
    "__rshift__": _make_binary_generic(std.RShift),
    "__and__": _make_binary_generic(std.BitwiseAnd),
    "__or__": _make_binary_generic(std.BitwiseOr),
    "__xor__": _make_binary_generic(std.BitwiseXor),
    "min": _make_binary_generic(std.Min),
    "max": _make_binary_generic(std.Max),
    "__eq__": _make_bool_binary_generic(std.Eq),
    "__ne__": _make_bool_binary_generic(std.Ne),
    "__le__": _make_bool_binary_generic(std.Le),
    "__ge__": _make_bool_binary_generic(std.Ge),
    "__gt__": _make_bool_binary_generic(std.Gt),
    "__lt__": _make_bool_binary_generic(std.Lt),
    "__logical_and__": _make_bool_binary_generic(std.And),
    "__logical_or__": _make_bool_binary_generic(std.Or),
    "__invert__": lambda value: std.BitwiseNot(value, ty=_parse_value_ty(value)),
    "__not__": lambda value: std.Not(value, ty=_bool_like_ty(_parse_value_ty(value))),
    "__neg__": lambda value: (
        -value if isinstance(value, (int, float)) else std.Sub(0, value, ty=_parse_value_ty(value))
    ),
    "__pos__": lambda value: value,
    "__if_then_else__": lambda cond, then_expr, else_expr: std.IfExpr(
        cond, then_expr, else_expr, ty=_find_common_ty(then_expr, else_expr)
    ),
    "__load__": lambda base, *indices: _make_load((base, *indices)),
    "__slice__": std.Range,
    "__cast__": lambda ty, value: std.Cast(normalize_ty(ty), value),
    "__call__": lambda callee, *args: std.Call(callee, *args, ty=std.AnyTy()),
    "__store__": lambda lhs, rhs, *indices: std.Store(lhs, *indices, rhs=rhs),
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
    "__bind_var_def__": lambda names, *tys: _bind_var_def_from_names(names, tys),
}
register_dialect("std", Std)
