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
"""Standard core dialect bindings."""

from __future__ import annotations

from collections.abc import (
    ItemsView,
    Iterator,
    KeysView,
    Mapping,
    MutableMapping,
    MutableSequence,
    Sequence,
)
from typing import TYPE_CHECKING, Any, ClassVar, cast

from typing_extensions import Never, Protocol, TypeAlias

from tvm_ffi import dtype
from tvm_ffi.core import Object
from tvm_ffi.dataclasses import c_class, field
from tvm_ffi.pyast import PrinterConfig


class _FactoryLike(Protocol):
    def to_dialect(self) -> Ty: ...


DialectMnemonic: TypeAlias = "tuple[str, str] | tuple[str, str, str]"
TyLike: TypeAlias = "Ty | str | _FactoryLike"
AttrsLike: TypeAlias = "Attrs | Mapping[str, Any] | None"
ExprLike: TypeAlias = "Expr | bool | int | float | str"
RangeLike: TypeAlias = "Range | ExprLike"
DefaultIntegerType: str = "int64"
DefaultFloatType: str = "float32"


def _normalize_ty(value: TyLike) -> Ty:
    """Normalize parser-side type factories and dtype strings to ``std.Ty``."""
    if isinstance(value, Ty):
        return value
    if hasattr(value, "to_dialect"):
        return cast(Any, value).to_dialect()
    if isinstance(value, str):
        return PrimTy(value)
    raise TypeError(f"expected std type, got {type(value).__name__}")


def _normalize_expr(value: ExprLike) -> Expr:
    """Normalize Python literals to standard dialect immediate expressions."""
    if isinstance(value, Expr):
        return value
    return Expr.literal(value)


@c_class("ffi.std.Node", init=False)
class Node(Object):
    """Base class for the standard dialect."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Node")

    if TYPE_CHECKING:

        def __init__(self, _no_direct_init: Never) -> None: ...

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "__ffi_dialect_mnemonic__" not in cls.__dict__:
            raise TypeError(
                f"{cls.__name__}: subclasses of std.Node must define "
                "__ffi_dialect_mnemonic__ directly on the class"
            )

    def text(self, config: PrinterConfig | None = None) -> str:
        """Render this standard dialect node with the FFI text printer."""
        from tvm_ffi import pyast  # noqa: PLC0415

        return pyast.to_python(self, config)

    def render_text(
        self,
        config: PrinterConfig | None = None,
        style: str | None = None,
    ) -> None:
        """Print this standard dialect node with optional syntax highlighting."""
        from tvm_ffi._pyast_colored_print import cprint  # noqa: PLC0415

        cprint(self.text(config), style=style)


@c_class("ffi.std.Ty", init=False)
class Ty(Node):
    """Base class for standard dialect types."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Ty")


@c_class("ffi.std.Attrs", init=False)
class Attrs(Node):
    """Base class for standard dialect attributes."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Attrs")


@c_class("ffi.std.Stmt", init=False)
class Stmt(Node):
    """Base class for standard dialect statements."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Stmt")

    attrs: Attrs | None = field(default=None, kw_only=True)


@c_class("ffi.std.Aggregate", init=False)
class Aggregate(Node):
    """Base class for standard dialect aggregate helper nodes."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Aggregate")


@c_class("ffi.std.Expr", init=False)
class Expr(Node):
    """Base class for standard dialect expressions."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Expr")

    ty: Ty

    @staticmethod
    def literal(value: ExprLike) -> Expr:
        """Convert a Python literal to a standard dialect expression."""
        if isinstance(value, Expr):
            return value
        if isinstance(value, bool):
            return BoolImm.from_py(value)
        if isinstance(value, int):
            return IntImm.from_py(value)
        if isinstance(value, float):
            return FloatImm.from_py(value)
        if isinstance(value, str):
            return StringImm.from_py(value)
        raise TypeError(f"Unsupported type: {type(value).__name__}")


@c_class("ffi.std.Var")
class Var(Expr):
    """A named SSA-style variable."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Var")

    name: str

    def __init__(self, ty: TyLike, name: str) -> None:
        self.__ffi_init__(_normalize_ty(ty), name)


@c_class("ffi.std.Func")
class Func(Stmt):
    """A standard dialect function."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Func")

    symbol: str
    args: MutableSequence[Var]
    ret_type: Ty | None
    body: MutableSequence[Stmt]
    if TYPE_CHECKING:

        def __init__(
            self,
            symbol: str,
            args: MutableSequence[Var],
            ret_type: Ty | None,
            body: MutableSequence[Stmt],
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.Module")
class Module(Node):
    """A module containing functions."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Module")

    funcs: MutableSequence[Func]


@c_class("ffi.std.Range")
class Range(Aggregate):
    """A half-open range or slice."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Range")

    start: Expr | None = field(default=None)
    stop: Expr | None = field(default=None)
    step: Expr | None = field(default=None)
    if TYPE_CHECKING:

        def __init__(
            self,
            start: ExprLike | None = ...,
            stop: ExprLike | None = ...,
            step: ExprLike | None = ...,
        ) -> None: ...


@c_class("ffi.std.AnyTy")
class AnyTy(Ty):
    """The unconstrained type."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Any")


@c_class("ffi.std.PrimTy")
class PrimTy(Ty):
    """A primitive scalar type."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Prim")

    dtype: dtype
    if TYPE_CHECKING:

        def __init__(self, dtype: dtype | str) -> None: ...

    def coerce_literal(self, value: ExprLike) -> Expr | None:
        """Coerce a Python literal to this primitive type."""
        if not isinstance(value, (bool, int, float)):
            return None
        dtype = self.dtype
        if dtype.is_bool:
            return BoolImm(self, bool(value))
        if dtype.is_integer:
            return IntImm(self, int(value))
        if dtype.is_float:
            return FloatImm(self, float(value))
        return None


@c_class("ffi.std.TupleType")
class TupleType(Ty):
    """A tuple type."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Tuple")

    fields: MutableSequence[Ty]


@c_class("ffi.std.TensorTy")
class TensorTy(Ty):
    """A tensor type."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Tensor")

    shape: MutableSequence[Expr]
    dtype: dtype
    if TYPE_CHECKING:

        def __init__(self, shape: Sequence[ExprLike], dtype: dtype | str) -> None: ...


@c_class("ffi.std.BoolImm")
class BoolImm(Expr):
    """A boolean immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "BoolImm")

    value: bool

    def __init__(self, ty: TyLike, value: bool) -> None:
        self.__ffi_init__(_normalize_ty(ty), value)

    @staticmethod
    def from_py(value: bool) -> BoolImm:
        """Create a boolean immediate from a Python bool literal."""
        return BoolImm(PrimTy("bool"), value)


@c_class("ffi.std.IntImm")
class IntImm(Expr):
    """An integer immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "IntImm")

    value: int

    def __init__(self, ty: TyLike, value: int) -> None:
        self.__ffi_init__(_normalize_ty(ty), value)

    @staticmethod
    def from_py(value: int) -> IntImm:
        """Create an integer immediate from a Python integer literal."""
        return IntImm(PrimTy(DefaultIntegerType), value)


@c_class("ffi.std.FloatImm")
class FloatImm(Expr):
    """A floating-point immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "FloatImm")

    value: float

    def __init__(self, ty: TyLike, value: float) -> None:
        self.__ffi_init__(_normalize_ty(ty), value)

    @staticmethod
    def from_py(value: float) -> FloatImm:
        """Create a floating-point immediate from a Python float literal."""
        return FloatImm(PrimTy(DefaultFloatType), value)


@c_class("ffi.std.StringImm")
class StringImm(Expr):
    """A string immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "StringImm")

    value: str

    def __init__(self, ty: TyLike, value: str) -> None:
        self.__ffi_init__(_normalize_ty(ty), value)

    @staticmethod
    def from_py(value: str) -> StringImm:
        """Create a string immediate from a Python string literal."""
        return StringImm(AnyTy(), value)


@c_class("ffi.std.Add")
class Add(Expr):
    """Addition."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Add", "__add__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Sub")
class Sub(Expr):
    """Subtraction."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Sub", "__sub__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Mul")
class Mul(Expr):
    """Multiplication."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Mul", "__mul__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.CDiv")
class CDiv(Expr):
    """C-style division.

    For integer operands, ``CDiv`` means ``truncdiv``: the quotient is
    truncated toward zero.  For floating-point operands, ``CDiv`` means
    C-style division.  Use ``FloorDiv`` only for integer floor division.
    """

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "CDiv", "__truediv__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.FloorDiv")
class FloorDiv(Expr):
    """Integer floor division.

    ``FloorDiv`` only works for integer operands.  It always computes
    ``floor(a / b)``, unlike ``CDiv`` which means ``truncdiv`` for integer
    operands and C-style division for floating-point operands.
    """

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "FloorDiv", "__floordiv__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.FloorMod")
class FloorMod(Expr):
    """Integer floor modulo.

    ``FloorMod`` only works for integer operands.  It is paired with
    ``FloorDiv`` and always uses ``floor(a / b)``.  Use ``CMod`` for
    integer ``truncmod`` behavior or floating-point C-style modulo.
    """

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "FloorMod", "__mod__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.CMod")
class CMod(Expr):
    """C-style modulo.

    For integer operands, ``CMod`` means ``truncmod`` and is paired with
    ``CDiv``.  For floating-point operands, ``CMod`` means C-style modulo.
    Use ``FloorMod`` only for integer floor modulo.
    """

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "CMod")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Pow")
class Pow(Expr):
    """Exponentiation."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Pow", "__pow__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.LShift")
class LShift(Expr):
    """Left shift."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "LShift", "__lshift__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.RShift")
class RShift(Expr):
    """Right shift."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "RShift", "__rshift__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Xor")
class Xor(Expr):
    """Bitwise exclusive OR."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Xor", "__xor__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Min")
class Min(Expr):
    """Minimum."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Min", "min")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Max")
class Max(Expr):
    """Maximum."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Max", "max")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Eq")
class Eq(Expr):
    """Equality comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Eq", "__eq__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Ne")
class Ne(Expr):
    """Inequality comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Ne", "__ne__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Le")
class Le(Expr):
    """Less-than-or-equal comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Le", "__le__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Ge")
class Ge(Expr):
    """Greater-than-or-equal comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Ge", "__ge__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Gt")
class Gt(Expr):
    """Greater-than comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Gt", "__gt__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Lt")
class Lt(Expr):
    """Less-than comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Lt", "__lt__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.And")
class And(Expr):
    """Logical and."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "And", "__and__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Or")
class Or(Expr):
    """Logical or."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Or", "__or__")

    a: Expr
    b: Expr

    def __init__(self, ty: TyLike, a: ExprLike, b: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), a, b)


@c_class("ffi.std.Not")
class Not(Expr):
    """Logical not."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Not", "__invert__")

    operand: Expr

    def __init__(self, ty: TyLike, operand: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), operand)


@c_class("ffi.std.Load")
class Load(Expr):
    """Indexed load."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Load", "__load__")

    lhs: Expr
    indices: MutableSequence[Range]

    def __init__(
        self,
        ty: TyLike,
        lhs: ExprLike,
        *indices: RangeLike,
    ) -> None:
        self.__ffi_init__(_normalize_ty(ty), lhs, list(indices))


@c_class("ffi.std.Cast")
class Cast(Expr):
    """Type cast."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Cast", "__cast__")

    value: Expr

    def __init__(self, ty: TyLike, value: ExprLike) -> None:
        self.__ffi_init__(_normalize_ty(ty), value)


@c_class("ffi.std.Call")
class Call(Expr):
    """Function call expression."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Call")

    callee: Any
    args: MutableSequence[Expr]
    attr: Attrs | None = field(default=None)

    def __init__(
        self,
        ty: TyLike,
        callee: Any,
        *args: ExprLike,
        **kwargs: Any,
    ) -> None:
        if isinstance(callee, Var):
            callee = callee.name
        elif not isinstance(callee, (str, Expr, Func)):
            raise TypeError(
                f"std.Call callee must be a name, expression, or function, got {type(callee).__name__}"
            )
        self.__ffi_init__(_normalize_ty(ty), callee, list(args), kwargs or None)


@c_class("ffi.std.IfStmt")
class IfStmt(Stmt):
    """If/else statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "IfStmt", "__if__")

    cond: Expr
    then_body: MutableSequence[Stmt]
    else_body: MutableSequence[Stmt]

    def __init__(
        self,
        cond: ExprLike,
        then_body: Sequence[Stmt],
        else_body: Sequence[Stmt],
        **kwargs: Any,
    ) -> None:
        self.__ffi_init__(
            cond,
            list(then_body),
            list(else_body),
            attrs=kwargs or None,
        )


@c_class("ffi.std.Scope")
class Scope(Stmt):
    """A scoped statement block."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Scope")

    binds: MutableSequence[Bind]
    body: MutableSequence[Stmt]
    if TYPE_CHECKING:

        def __init__(
            self,
            binds: MutableSequence[Bind],
            body: MutableSequence[Stmt],
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.For")
class For(Scope):
    """For loop."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "For", "__for__")

    range_: Range
    if TYPE_CHECKING:

        def __init__(
            self,
            binds: MutableSequence[Bind],
            body: MutableSequence[Stmt],
            range_: RangeLike,
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.While")
class While(Scope):
    """While loop."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "While", "__while__")

    cond: Expr
    if TYPE_CHECKING:

        def __init__(
            self,
            binds: MutableSequence[Bind],
            body: MutableSequence[Stmt],
            cond: ExprLike,
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.Bind", init=False)
class Bind(Stmt):
    """Base variable binding statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Bind")

    vars: MutableSequence[Var]
    if TYPE_CHECKING:

        def __init__(self, _no_direct_init: Never) -> None: ...


@c_class("ffi.std.BindExpr")
class BindExpr(Bind):
    """Binding that defines variables from an expression."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "BindExpr", "__bind_expr__")

    expr: Expr

    def __init__(self, expr: ExprLike, *args: Var, **kwargs: Any) -> None:
        self.__ffi_init__(list(args), _normalize_expr(expr), attrs=kwargs or None)


@c_class("ffi.std.BindVarDef")
class BindVarDef(Bind):
    """Binding that defines variables without a source expression."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = (
        "std",
        "BindVarDef",
        "__bind_var_def__",
    )

    def __init__(self, *args: Var | TyLike, **kwargs: Any) -> None:
        vars = [arg if isinstance(arg, Var) else Var(_normalize_ty(arg), "") for arg in args]
        self.__ffi_init__(vars, attrs=kwargs or None)


@c_class("ffi.std.Store")
class Store(Stmt):
    """Indexed store."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Store", "__store__")

    lhs: Expr
    indices: MutableSequence[Range]
    rhs: Expr

    def __init__(self, lhs: ExprLike, *indices: RangeLike, rhs: ExprLike, **kwargs: Any) -> None:
        self.__ffi_init__(lhs, list(indices), rhs, attrs=kwargs or None)


@c_class("ffi.std.Assert")
class Assert(Stmt):
    """Assertion statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Assert", "__assert__")

    cond: Expr

    def __init__(self, cond: ExprLike, **kwargs: Any) -> None:
        self.__ffi_init__(cond, attrs=kwargs or None)


@c_class("ffi.std.Return")
class Return(Stmt):
    """Return statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Return", "__return__")

    exprs: MutableSequence[Expr]

    def __init__(self, *exprs: ExprLike, **kwargs: Any) -> None:
        self.__ffi_init__(list(exprs), attrs=kwargs or None)


@c_class("ffi.std.Yield")
class Yield(Stmt):
    """Yield statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Yield", "__yield__")

    exprs: MutableSequence[Expr]

    def __init__(self, *exprs: ExprLike, **kwargs: Any) -> None:
        self.__ffi_init__(list(exprs), attrs=kwargs or None)


@c_class("ffi.std.Break")
class Break(Stmt):
    """Break statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Break", "__break__")

    def __init__(self, **kwargs: Any) -> None:
        self.__ffi_init__(attrs=kwargs or None)


@c_class("ffi.std.Continue")
class Continue(Stmt):
    """Continue statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Continue", "__continue__")

    def __init__(self, **kwargs: Any) -> None:
        self.__ffi_init__(attrs=kwargs or None)


@c_class("ffi.std.DictAttrs")
class DictAttrs(Attrs):
    """Dictionary-backed attributes."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "DictAttrs")

    values: MutableMapping[str, Any]

    def __init__(self, **kwargs: Any) -> None:
        self.__ffi_init__(kwargs)

    def __len__(self) -> int:
        return len(self.values)

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __contains__(self, key: object) -> bool:
        return key in self.values

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Return ``key`` if present, otherwise ``default``."""
        return self.values.get(key, default)

    def keys(self) -> KeysView[str]:
        """Return a dynamic view over attribute keys."""
        return self.values.keys()

    def items(self) -> ItemsView[str, Any]:
        """Return a dynamic view over attribute items."""
        return self.values.items()


__all__ = [
    "Add",
    "Aggregate",
    "And",
    "AnyTy",
    "Assert",
    "Attrs",
    "Bind",
    "BindExpr",
    "BindVarDef",
    "BoolImm",
    "Break",
    "CDiv",
    "CMod",
    "Call",
    "Cast",
    "Continue",
    "DictAttrs",
    "Eq",
    "Expr",
    "FloatImm",
    "FloorDiv",
    "FloorMod",
    "For",
    "Func",
    "Ge",
    "Gt",
    "IfStmt",
    "IntImm",
    "LShift",
    "Le",
    "Load",
    "Lt",
    "Max",
    "Min",
    "Module",
    "Mul",
    "Ne",
    "Node",
    "Not",
    "Or",
    "Pow",
    "PrimTy",
    "RShift",
    "Range",
    "Return",
    "Scope",
    "Stmt",
    "Store",
    "StringImm",
    "Sub",
    "TensorTy",
    "TupleType",
    "Ty",
    "Var",
    "While",
    "Xor",
    "Yield",
]
