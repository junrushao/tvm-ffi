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

# tvm-ffi-stubgen(begin): import-section
# fmt: off
# isort: off
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from collections.abc import MutableMapping, MutableSequence
    from tvm_ffi import dtype
    from typing import Any
# isort: on
# fmt: on
# tvm-ffi-stubgen(end)

from collections.abc import (
    ItemsView,
    Iterator,
    KeysView,
    Mapping,
    MutableMapping,
    MutableSequence,
    Sequence,
)
from typing import Any, ClassVar
from typing import cast as _typing_cast

from typing_extensions import Never, Protocol, TypeAlias

from tvm_ffi import dtype
from tvm_ffi.core import MISSING, Object
from tvm_ffi.dataclasses import c_class, field
from tvm_ffi.pyast import PrinterConfig

from . import _std_api


class _FactoryLike(Protocol):
    def to_dialect(self) -> Ty: ...


DialectMnemonic: TypeAlias = "tuple[str, str]"
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
        return value.to_dialect()  # ty: ignore[call-non-callable]
    if isinstance(value, str):
        return PrimTy(value)
    raise TypeError(f"expected std type, got {type(value).__name__}")


def _normalize_expr(value: ExprLike) -> Expr:
    """Normalize Python literals to standard dialect immediate expressions."""
    if isinstance(value, Expr):
        return value
    return Expr.literal(value)


def _binary_expr_ffi_init(self: Any, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
    self.__ffi_init__(a, b, _normalize_ty(ty))


def _unary_expr_ffi_init(self: Any, operand: ExprLike, *, ty: TyLike) -> None:
    self.__ffi_init__(operand, _normalize_ty(ty))


@c_class("ffi.std.Node", init=False)
class Node(Object):
    """Base class for the standard dialect.

    Subclasses declare their printed dialect and mnemonic with
    ``mnemonic="dialect.Name"`` in the class definition.
    """

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Node")

    # tvm-ffi-stubgen(begin): object/ffi.std.Node
    # fmt: off
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __init__(self, _no_direct_init: Never) -> None: ...

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init_subclass__(cls, *, mnemonic: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if mnemonic is None:
            raise TypeError(
                f"{cls.__name__}: subclasses of std.Node must define "
                "mnemonic as a class definition keyword"
            )
        dialect, name = mnemonic.rsplit(".", 1)
        cls.__ffi_dialect_mnemonic__ = (dialect, name)
        cls.__annotations__["__ffi_dialect_mnemonic__"] = ClassVar[DialectMnemonic]

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
class Ty(Node, mnemonic="std.Ty"):
    """Base class for standard dialect types."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Ty
    # fmt: off
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.Attrs", init=False)
class Attrs(Node, mnemonic="std.Attrs"):
    """Base class for standard dialect attributes."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Attrs
    # fmt: off
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.Stmt", init=False)
class Stmt(Node, mnemonic="std.Stmt"):
    """Base class for standard dialect statements."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Stmt
    # fmt: off
    attrs: Attrs | None
    # fmt: on
    # tvm-ffi-stubgen(end)

    attrs = field(default=None, kw_only=True)


@c_class("ffi.std.Aggregate", init=False)
class Aggregate(Node, mnemonic="std.Aggregate"):
    """Base class for standard dialect aggregate helper nodes."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Aggregate
    # fmt: off
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.Expr", init=False)
class Expr(Node, mnemonic="std.Expr"):
    """Base class for standard dialect expressions."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Expr
    # fmt: off
    ty: Ty
    # fmt: on
    # tvm-ffi-stubgen(end)

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

    def __add__(self, other: ExprLike) -> Expr:
        return add(self, other)

    def __radd__(self, other: ExprLike) -> Expr:
        return add(other, self)

    def __sub__(self, other: ExprLike) -> Expr:
        return sub(self, other)

    def __rsub__(self, other: ExprLike) -> Expr:
        return sub(other, self)

    def __mul__(self, other: ExprLike) -> Expr:
        return mul(self, other)

    def __rmul__(self, other: ExprLike) -> Expr:
        return mul(other, self)

    def __truediv__(self, other: ExprLike) -> Expr:
        return cdiv(self, other)

    def __rtruediv__(self, other: ExprLike) -> Expr:
        return cdiv(other, self)

    def __floordiv__(self, other: ExprLike) -> Expr:
        return floordiv(self, other)

    def __rfloordiv__(self, other: ExprLike) -> Expr:
        return floordiv(other, self)

    def __mod__(self, other: ExprLike) -> Expr:
        return floormod(self, other)

    def __rmod__(self, other: ExprLike) -> Expr:
        return floormod(other, self)

    def __pow__(self, other: ExprLike) -> Expr:
        return pow(self, other)

    def __rpow__(self, other: ExprLike) -> Expr:
        return pow(other, self)

    def __neg__(self) -> Expr:
        return neg(self)

    def __pos__(self) -> Expr:
        return self

    def __abs__(self) -> Expr:
        return abs(self)

    def __lshift__(self, other: ExprLike) -> Expr:
        return left_shift(self, other)

    def __rlshift__(self, other: ExprLike) -> Expr:
        return left_shift(other, self)

    def __rshift__(self, other: ExprLike) -> Expr:
        return right_shift(self, other)

    def __rrshift__(self, other: ExprLike) -> Expr:
        return right_shift(other, self)

    def __and__(self, other: ExprLike) -> Expr:
        return bitwise_and(self, other)

    def __rand__(self, other: ExprLike) -> Expr:
        return bitwise_and(other, self)

    def __or__(self, other: ExprLike) -> Expr:
        return bitwise_or(self, other)

    def __ror__(self, other: ExprLike) -> Expr:
        return bitwise_or(other, self)

    def __xor__(self, other: ExprLike) -> Expr:
        return bitwise_xor(self, other)

    def __rxor__(self, other: ExprLike) -> Expr:
        return bitwise_xor(other, self)

    def __invert__(self) -> Expr:
        return bitwise_not(self)

    def __lt__(self, other: ExprLike) -> Expr:
        return lt(self, other)

    def __le__(self, other: ExprLike) -> Expr:
        return le(self, other)

    def __gt__(self, other: ExprLike) -> Expr:
        return gt(self, other)

    def __ge__(self, other: ExprLike) -> Expr:
        return ge(self, other)

    def __eq__(self, other: object) -> Expr | bool:  # ty: ignore[invalid-method-override]
        if isinstance(other, Expr):
            return Object.__eq__(self, other)
        if isinstance(other, (bool, int, float, str)):
            return eq(self, other)
        return Object.__eq__(self, other)

    def __ne__(self, other: object) -> Expr | bool:  # ty: ignore[invalid-method-override]
        if isinstance(other, Expr):
            return Object.__ne__(self, other)
        if isinstance(other, (bool, int, float, str)):
            return ne(self, other)
        return not Object.__eq__(self, other)

    def __bool__(self) -> bool:
        raise TypeError(
            "Cannot use std.Expr as a Python bool; use logical_and(), "
            "logical_or(), or logical_not()"
        )

    def __nonzero__(self) -> bool:
        return self.__bool__()

    __hash__ = Object.__hash__

    def equal(self, other: ExprLike) -> Expr:
        """Create a standard dialect equality expression."""
        return eq(self, other)

    def not_equal(self, other: ExprLike) -> Expr:
        """Create a standard dialect inequality expression."""
        return ne(self, other)

    def logical_and(self, other: ExprLike) -> Expr:
        """Create a standard dialect logical-and expression."""
        return logical_and(self, other)

    def logical_or(self, other: ExprLike) -> Expr:
        """Create a standard dialect logical-or expression."""
        return logical_or(self, other)

    def logical_not(self) -> Expr:
        """Create a standard dialect logical-not expression."""
        return logical_not(self)

    def if_then_else(self, then_expr: ExprLike, else_expr: ExprLike) -> Expr:
        """Create a standard dialect ternary expression."""
        return if_then_else(self, then_expr, else_expr)

    def cast(self, ty: TyLike) -> Expr:
        """Cast this expression to a standard dialect type."""
        return cast(ty, self)

    def astype(self, ty: TyLike) -> Expr:
        """Alias for ``cast``."""
        return self.cast(ty)


@c_class("ffi.std.Var")
class Var(Expr, mnemonic="std.Var"):
    """A named SSA-style variable."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Var
    # fmt: off
    name: str
    if TYPE_CHECKING:
        def __init__(self, name: str, *, ty: Ty) -> None: ...
        def __ffi_init__(self, name: str, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, ty: TyLike, name: str) -> None:
        self.__ffi_init__(name, ty=_normalize_ty(ty))


@c_class("ffi.std.Func")
class Func(Stmt, mnemonic="std.Func"):
    """A standard dialect function."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Func
    # fmt: off
    symbol: str
    args: MutableSequence[Var]
    ret_type: Ty | None
    body: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, symbol: str, args: MutableSequence[Var], ret_type: Ty | None, body: MutableSequence[Stmt], *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, symbol: str, args: MutableSequence[Var], ret_type: Ty | None, body: MutableSequence[Stmt], *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

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
class Module(Node, mnemonic="std.Module"):
    """A module containing functions."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Module
    # fmt: off
    funcs: MutableSequence[Func]
    if TYPE_CHECKING:
        def __init__(self, funcs: MutableSequence[Func]) -> None: ...
        def __ffi_init__(self, funcs: MutableSequence[Func]) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.Range")
class Range(Aggregate, mnemonic="std.Range"):
    """A half-open range or slice."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Range
    # fmt: off
    start: Expr | None
    stop: Expr | None
    step: Expr | None
    if TYPE_CHECKING:
        def __init__(self, start: Expr | None = ..., stop: Expr | None = ..., step: Expr | None = ...) -> None: ...
        def __ffi_init__(self, start: Expr | None = ..., stop: Expr | None = ..., step: Expr | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    start = field(default=None)
    stop = field(default=None)
    step = field(default=None)

    if TYPE_CHECKING:

        def __init__(
            self,
            start: ExprLike | None = ...,
            stop: ExprLike | None = ...,
            step: ExprLike | None = ...,
        ) -> None: ...

    def __init__(
        self,
        *args: ExprLike | None,
        start: ExprLike | None | object = MISSING,
        stop: ExprLike | None | object = MISSING,
        step: ExprLike | None | object = MISSING,
    ) -> None:
        has_keywords = not MISSING.is_(start) or not MISSING.is_(stop) or not MISSING.is_(step)
        if args and has_keywords:
            raise TypeError("Range cannot mix positional arguments with start/stop/step keywords")
        if len(args) > 3:
            raise TypeError(f"Range expects at most 3 positional arguments, but got {len(args)}")
        if len(args) == 0:
            start_value = None if MISSING.is_(start) else start
            stop_value = None if MISSING.is_(stop) else stop
            step_value = None if MISSING.is_(step) else step
        elif len(args) == 1:
            start_value = None
            stop_value = args[0]
            step_value = None
        elif len(args) == 2:
            start_value, stop_value = args
            step_value = None
        else:
            start_value, stop_value, step_value = args
        self.__ffi_init__(start_value, stop_value, step_value)  # type: ignore[call-arg]


@c_class("ffi.std.AnyTy")
class AnyTy(Ty, mnemonic="std.Any"):
    """The unconstrained type."""

    # tvm-ffi-stubgen(begin): object/ffi.std.AnyTy
    # fmt: off
    if TYPE_CHECKING:
        def __init__(self) -> None: ...
        def __ffi_init__(self) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.PrimTy")
class PrimTy(Ty, mnemonic="std.Prim"):
    """A primitive scalar type."""

    # tvm-ffi-stubgen(begin): object/ffi.std.PrimTy
    # fmt: off
    dtype: dtype
    if TYPE_CHECKING:
        def __init__(self, dtype: dtype) -> None: ...
        def __ffi_init__(self, dtype: dtype) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)
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


@c_class("ffi.std.TupleTy")
class TupleTy(Ty, mnemonic="std.Tuple"):
    """A tuple type."""

    # tvm-ffi-stubgen(begin): object/ffi.std.TupleTy
    # fmt: off
    fields: MutableSequence[Ty]
    if TYPE_CHECKING:
        def __init__(self, fields: MutableSequence[Ty]) -> None: ...
        def __ffi_init__(self, fields: MutableSequence[Ty]) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.TensorTy")
class TensorTy(Ty, mnemonic="std.Tensor"):
    """A tensor type."""

    # tvm-ffi-stubgen(begin): object/ffi.std.TensorTy
    # fmt: off
    shape: MutableSequence[Expr]
    dtype: dtype
    if TYPE_CHECKING:
        def __init__(self, shape: MutableSequence[Expr], dtype: dtype) -> None: ...
        def __ffi_init__(self, shape: MutableSequence[Expr], dtype: dtype) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __init__(self, shape: Sequence[ExprLike], dtype: dtype | str) -> None: ...


@c_class("ffi.std.BoolImm")
class BoolImm(Expr, mnemonic="std.BoolImm"):
    """A boolean immediate."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BoolImm
    # fmt: off
    value: bool
    if TYPE_CHECKING:
        def __init__(self, value: bool, *, ty: Ty) -> None: ...
        def __ffi_init__(self, value: bool, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, ty: TyLike, value: bool) -> None:
        self.__ffi_init__(value, ty=_normalize_ty(ty))

    @staticmethod
    def from_py(value: bool) -> BoolImm:
        """Create a boolean immediate from a Python bool literal."""
        return BoolImm(PrimTy("bool"), value)


@c_class("ffi.std.IntImm")
class IntImm(Expr, mnemonic="std.IntImm"):
    """An integer immediate."""

    # tvm-ffi-stubgen(begin): object/ffi.std.IntImm
    # fmt: off
    value: int
    if TYPE_CHECKING:
        def __init__(self, value: int, *, ty: Ty) -> None: ...
        def __ffi_init__(self, value: int, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, ty: TyLike, value: int) -> None:
        self.__ffi_init__(value, ty=_normalize_ty(ty))

    @staticmethod
    def from_py(value: int) -> IntImm:
        """Create an integer immediate from a Python integer literal."""
        return IntImm(PrimTy(DefaultIntegerType), value)


@c_class("ffi.std.FloatImm")
class FloatImm(Expr, mnemonic="std.FloatImm"):
    """A floating-point immediate."""

    # tvm-ffi-stubgen(begin): object/ffi.std.FloatImm
    # fmt: off
    value: float
    if TYPE_CHECKING:
        def __init__(self, value: float, *, ty: Ty) -> None: ...
        def __ffi_init__(self, value: float, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, ty: TyLike, value: float) -> None:
        self.__ffi_init__(value, ty=_normalize_ty(ty))

    @staticmethod
    def from_py(value: float) -> FloatImm:
        """Create a floating-point immediate from a Python float literal."""
        return FloatImm(PrimTy(DefaultFloatType), value)


@c_class("ffi.std.StringImm")
class StringImm(Expr, mnemonic="std.StringImm"):
    """A string immediate."""

    # tvm-ffi-stubgen(begin): object/ffi.std.StringImm
    # fmt: off
    value: str
    if TYPE_CHECKING:
        def __init__(self, value: str, *, ty: Ty) -> None: ...
        def __ffi_init__(self, value: str, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, ty: TyLike, value: str) -> None:
        self.__ffi_init__(value, ty=_normalize_ty(ty))

    @staticmethod
    def from_py(value: str) -> StringImm:
        """Create a string immediate from a Python string literal."""
        return StringImm(AnyTy(), value)


@c_class("ffi.std.Add")
class Add(Expr, mnemonic="std.Add"):
    """Addition."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Add
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Sub")
class Sub(Expr, mnemonic="std.Sub"):
    """Subtraction."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Sub
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Mul")
class Mul(Expr, mnemonic="std.Mul"):
    """Multiplication."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Mul
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.CDiv")
class CDiv(Expr, mnemonic="std.CDiv"):
    """C-style division.

    For integer operands, ``CDiv`` means ``truncdiv``: the quotient is
    truncated toward zero.  For floating-point operands, ``CDiv`` means
    C-style division.  Use ``FloorDiv`` only for integer floor division.
    """

    # tvm-ffi-stubgen(begin): object/ffi.std.CDiv
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.FloorDiv")
class FloorDiv(Expr, mnemonic="std.FloorDiv"):
    """Integer floor division.

    ``FloorDiv`` only works for integer operands.  It always computes
    ``floor(a / b)``, unlike ``CDiv`` which means ``truncdiv`` for integer
    operands and C-style division for floating-point operands.
    """

    # tvm-ffi-stubgen(begin): object/ffi.std.FloorDiv
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.FloorMod")
class FloorMod(Expr, mnemonic="std.FloorMod"):
    """Integer floor modulo.

    ``FloorMod`` only works for integer operands.  It is paired with
    ``FloorDiv`` and always uses ``floor(a / b)``.  Use ``CMod`` for
    integer ``truncmod`` behavior or floating-point C-style modulo.
    """

    # tvm-ffi-stubgen(begin): object/ffi.std.FloorMod
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.CMod")
class CMod(Expr, mnemonic="std.CMod"):
    """C-style modulo.

    For integer operands, ``CMod`` means ``truncmod`` and is paired with
    ``CDiv``.  For floating-point operands, ``CMod`` means C-style modulo.
    Use ``FloorMod`` only for integer floor modulo.
    """

    # tvm-ffi-stubgen(begin): object/ffi.std.CMod
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Pow")
class Pow(Expr, mnemonic="std.Pow"):
    """Exponentiation."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Pow
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.LShift")
class LShift(Expr, mnemonic="std.LShift"):
    """Left shift."""

    # tvm-ffi-stubgen(begin): object/ffi.std.LShift
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.RShift")
class RShift(Expr, mnemonic="std.RShift"):
    """Right shift."""

    # tvm-ffi-stubgen(begin): object/ffi.std.RShift
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.BitwiseAnd")
class BitwiseAnd(Expr, mnemonic="std.BitwiseAnd"):
    """Bitwise and."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BitwiseAnd
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.BitwiseOr")
class BitwiseOr(Expr, mnemonic="std.BitwiseOr"):
    """Bitwise or."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BitwiseOr
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.BitwiseXor")
class BitwiseXor(Expr, mnemonic="std.BitwiseXor"):
    """Bitwise exclusive or."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BitwiseXor
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Min")
class Min(Expr, mnemonic="std.Min"):
    """Minimum."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Min
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Max")
class Max(Expr, mnemonic="std.Max"):
    """Maximum."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Max
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Eq")
class Eq(Expr, mnemonic="std.Eq"):
    """Equality comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Eq
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Ne")
class Ne(Expr, mnemonic="std.Ne"):
    """Inequality comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Ne
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Le")
class Le(Expr, mnemonic="std.Le"):
    """Less-than-or-equal comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Le
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Ge")
class Ge(Expr, mnemonic="std.Ge"):
    """Greater-than-or-equal comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Ge
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Gt")
class Gt(Expr, mnemonic="std.Gt"):
    """Greater-than comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Gt
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Lt")
class Lt(Expr, mnemonic="std.Lt"):
    """Less-than comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Lt
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.And")
class And(Expr, mnemonic="std.And"):
    """Logical and."""

    # tvm-ffi-stubgen(begin): object/ffi.std.And
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Or")
class Or(Expr, mnemonic="std.Or"):
    """Logical or."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Or
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _binary_expr_ffi_init


@c_class("ffi.std.Not")
class Not(Expr, mnemonic="std.Not"):
    """Logical not."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Not
    # fmt: off
    operand: Expr
    if TYPE_CHECKING:
        def __init__(self, operand: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, operand: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _unary_expr_ffi_init


@c_class("ffi.std.BitwiseNot")
class BitwiseNot(Expr, mnemonic="std.BitwiseNot"):
    """Bitwise not."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BitwiseNot
    # fmt: off
    operand: Expr
    if TYPE_CHECKING:
        def __init__(self, operand: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, operand: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _unary_expr_ffi_init


@c_class("ffi.std.Abs")
class Abs(Expr, mnemonic="std.Abs"):
    """Absolute value."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Abs
    # fmt: off
    operand: Expr
    if TYPE_CHECKING:
        def __init__(self, operand: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, operand: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if not TYPE_CHECKING:
        __init__ = _unary_expr_ffi_init


@c_class("ffi.std.IfExpr")
class IfExpr(Expr, mnemonic="std.IfExpr"):
    """Ternary expression."""

    # tvm-ffi-stubgen(begin): object/ffi.std.IfExpr
    # fmt: off
    cond: Expr
    then_expr: Expr
    else_expr: Expr
    if TYPE_CHECKING:
        def __init__(self, cond: ExprLike, then_expr: ExprLike, else_expr: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, cond: Expr, then_expr: Expr, else_expr: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self: Any,
        cond: ExprLike,
        then_expr: ExprLike,
        else_expr: ExprLike,
        *,
        ty: TyLike,
    ) -> None:
        self.__ffi_init__(cond, then_expr, else_expr, _normalize_ty(ty))


@c_class("ffi.std.Load")
class Load(Expr, mnemonic="std.Load"):
    """Indexed load."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Load
    # fmt: off
    lhs: Expr
    indices: MutableSequence[Range]
    if TYPE_CHECKING:
        def __init__(self, lhs: ExprLike, *indices: RangeLike, ty: TyLike | None = ...) -> None: ...
        def __ffi_init__(self, lhs: Expr, indices: MutableSequence[Range], ty: Ty | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        lhs: ExprLike,
        *indices: RangeLike,
        ty: TyLike | None = None,
    ) -> None:
        self.__ffi_init__(lhs, indices, _normalize_ty(ty) if ty is not None else None)


@c_class("ffi.std.Cast")
class Cast(Expr, mnemonic="std.Cast"):
    """Type cast."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Cast
    # fmt: off
    value: Expr
    if TYPE_CHECKING:
        def __init__(self, value: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, value: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, ty: TyLike, value: ExprLike) -> None:
        self.__ffi_init__(value, ty=_normalize_ty(ty))


@c_class("ffi.std.Call")
class Call(Expr, mnemonic="std.Call"):
    """Function call expression."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Call
    # fmt: off
    callee: Any
    args: MutableSequence[Expr]
    attr: Attrs | None
    if TYPE_CHECKING:
        def __init__(self, callee: Any, args: MutableSequence[Expr], attr: Attrs | None = ..., *, ty: Ty) -> None: ...
        def __ffi_init__(self, callee: Any, args: MutableSequence[Expr], attr: Attrs | None = ..., *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    attr = field(default=None)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        callee: Any,
        *args: ExprLike,
        ty: TyLike,
        **kwargs: Any,
    ) -> None:
        if isinstance(callee, Var):
            callee = callee.name
        elif not isinstance(callee, (str, Expr, Func)):
            raise TypeError(
                "std.Call callee must be a name, expression, or function, "
                f"got {type(callee).__name__}"
            )
        self.__ffi_init__(callee, args, kwargs or None, ty=_normalize_ty(ty))


@c_class("ffi.std.IfStmt")
class IfStmt(Stmt, mnemonic="std.IfStmt"):
    """If/else statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.IfStmt
    # fmt: off
    cond: Expr
    then_body: MutableSequence[Stmt]
    else_body: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, cond: Expr, then_body: MutableSequence[Stmt], else_body: MutableSequence[Stmt], *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, cond: Expr, then_body: MutableSequence[Stmt], else_body: MutableSequence[Stmt], *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

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
            kwargs or None,
        )


@c_class("ffi.std.Scope")
class Scope(Stmt, mnemonic="std.Scope"):
    """A scoped statement block."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Scope
    # fmt: off
    binds: MutableSequence[Stmt]
    body: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, binds: MutableSequence[Stmt], body: MutableSequence[Stmt], *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, binds: MutableSequence[Stmt], body: MutableSequence[Stmt], *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __init__(
            self,
            binds: MutableSequence[Stmt],
            body: MutableSequence[Stmt],
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.For")
class For(Stmt, mnemonic="std.For"):
    """For loop."""

    # tvm-ffi-stubgen(begin): object/ffi.std.For
    # fmt: off
    start: Expr | None
    stop: Expr | None
    step: Expr | None
    vars: MutableSequence[Var]
    body: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, start: Expr | None, stop: Expr | None, step: Expr | None, vars: MutableSequence[Var], body: MutableSequence[Stmt], *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, start: Expr | None, stop: Expr | None, step: Expr | None, vars: MutableSequence[Var], body: MutableSequence[Stmt], *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __init__(
            self,
            start: ExprLike | None,
            stop: ExprLike | None,
            step: ExprLike | None,
            vars: MutableSequence[Var],
            body: MutableSequence[Stmt],
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        start: ExprLike | None,
        stop: ExprLike | None,
        step: ExprLike | None,
        *,
        vars: MutableSequence[Var],
        body: MutableSequence[Stmt],
        attrs: AttrsLike = None,
    ) -> None:
        self.__ffi_init__(start, stop, step, list(vars), list(body), attrs)


@c_class("ffi.std.While")
class While(Stmt, mnemonic="std.While"):
    """While loop."""

    # tvm-ffi-stubgen(begin): object/ffi.std.While
    # fmt: off
    cond: Expr
    body: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, cond: Expr, body: MutableSequence[Stmt], *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, cond: Expr, body: MutableSequence[Stmt], *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __init__(
            self,
            cond: ExprLike,
            body: MutableSequence[Stmt],
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        cond: ExprLike,
        body: MutableSequence[Stmt],
        *,
        attrs: AttrsLike = None,
    ) -> None:
        self.__ffi_init__(cond, list(body), attrs)


@c_class("ffi.std.BindExpr")
class BindExpr(Stmt, mnemonic="std.BindExpr"):
    """Binding that defines variables from an expression."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BindExpr
    # fmt: off
    vars: MutableSequence[Var]
    expr: Expr
    if TYPE_CHECKING:
        def __init__(self, vars: MutableSequence[Var], expr: Expr, *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, vars: MutableSequence[Var], expr: Expr, *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, expr: ExprLike, *args: Var, **kwargs: Any) -> None:
        self.__ffi_init__(list(args), _normalize_expr(expr), attrs=kwargs or None)


@c_class("ffi.std.VarDef")
class VarDef(Stmt, mnemonic="std.VarDef"):
    """Binding that defines variables without a source expression."""

    # tvm-ffi-stubgen(begin): object/ffi.std.VarDef
    # fmt: off
    vars: MutableSequence[Var]
    if TYPE_CHECKING:
        def __init__(self, vars: MutableSequence[Var], *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, vars: MutableSequence[Var], *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, *args: Var | TyLike, **kwargs: Any) -> None:
        vars = [arg if isinstance(arg, Var) else Var(_normalize_ty(arg), "") for arg in args]
        self.__ffi_init__(vars, attrs=kwargs or None)


@c_class("ffi.std.Store")
class Store(Stmt, mnemonic="std.Store"):
    """Indexed store."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Store
    # fmt: off
    lhs: Expr
    indices: MutableSequence[Range]
    rhs: Expr
    if TYPE_CHECKING:
        def __init__(self, lhs: ExprLike, rhs: ExprLike, *indices: RangeLike, **kwargs: Any) -> None: ...
        def __ffi_init__(self, lhs: Expr, indices: MutableSequence[Range], rhs: Expr, *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, lhs: ExprLike, rhs: ExprLike, *indices: RangeLike, **kwargs: Any) -> None:
        self.__ffi_init__(lhs, indices, rhs, kwargs or None)


@c_class("ffi.std.Assert")
class Assert(Stmt, mnemonic="std.Assert"):
    """Assertion statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Assert
    # fmt: off
    cond: Expr
    if TYPE_CHECKING:
        def __init__(self, cond: Expr, *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, cond: Expr, *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, cond: ExprLike, **kwargs: Any) -> None:
        self.__ffi_init__(cond, kwargs or None)


@c_class("ffi.std.Return")
class Return(Stmt, mnemonic="std.Return"):
    """Return statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Return
    # fmt: off
    exprs: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, exprs: MutableSequence[Expr], *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, exprs: MutableSequence[Expr], *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, *exprs: ExprLike, **kwargs: Any) -> None:
        self.__ffi_init__(list(exprs), attrs=kwargs or None)


@c_class("ffi.std.Yield")
class Yield(Stmt, mnemonic="std.Yield"):
    """Yield statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Yield
    # fmt: off
    exprs: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, exprs: MutableSequence[Expr], *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, exprs: MutableSequence[Expr], *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, *exprs: ExprLike, **kwargs: Any) -> None:
        self.__ffi_init__(list(exprs), attrs=kwargs or None)


@c_class("ffi.std.Break")
class Break(Stmt, mnemonic="std.Break"):
    """Break statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Break
    # fmt: off
    if TYPE_CHECKING:
        def __init__(self, *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, **kwargs: Any) -> None:
        self.__ffi_init__(attrs=kwargs or None)


@c_class("ffi.std.Continue")
class Continue(Stmt, mnemonic="std.Continue"):
    """Continue statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Continue
    # fmt: off
    if TYPE_CHECKING:
        def __init__(self, *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, **kwargs: Any) -> None:
        self.__ffi_init__(attrs=kwargs or None)


@c_class("ffi.std.DictAttrs")
class DictAttrs(Attrs, mnemonic="std.DictAttrs"):
    """Dictionary-backed attributes."""

    # tvm-ffi-stubgen(begin): object/ffi.std.DictAttrs
    # fmt: off
    values: MutableMapping[str, Any]
    if TYPE_CHECKING:
        def __init__(self, values: MutableMapping[str, Any]) -> None: ...
        def __ffi_init__(self, values: MutableMapping[str, Any]) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

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


def cast(ty: TyLike, value: ExprLike) -> Expr:
    """Cast an expression to a standard dialect type."""
    return _typing_cast(Expr, _std_api.cast(_normalize_ty(ty), value))


def add(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect addition expression."""
    return _typing_cast(Expr, _std_api.add(lhs, rhs))


def sub(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect subtraction expression."""
    return _typing_cast(Expr, _std_api.sub(lhs, rhs))


def mul(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect multiplication expression."""
    return _typing_cast(Expr, _std_api.mul(lhs, rhs))


def cdiv(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect C-style division expression."""
    return _typing_cast(Expr, _std_api.cdiv(lhs, rhs))


def cmod(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect C-style modulo expression."""
    return _typing_cast(Expr, _std_api.cmod(lhs, rhs))


def truncdiv(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Alias for C-style division."""
    return _typing_cast(Expr, _std_api.truncdiv(lhs, rhs))


def truncmod(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Alias for C-style modulo."""
    return _typing_cast(Expr, _std_api.truncmod(lhs, rhs))


def floordiv(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect floor division expression."""
    return _typing_cast(Expr, _std_api.floordiv(lhs, rhs))


def floormod(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect floor modulo expression."""
    return _typing_cast(Expr, _std_api.floormod(lhs, rhs))


def pow(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect power expression."""
    return _typing_cast(Expr, _std_api.pow(lhs, rhs))


def min(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect minimum expression."""
    return _typing_cast(Expr, _std_api.min(lhs, rhs))


def max(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect maximum expression."""
    return _typing_cast(Expr, _std_api.max(lhs, rhs))


def eq(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect equality expression."""
    return _typing_cast(Expr, _std_api.eq(lhs, rhs))


def ne(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect inequality expression."""
    return _typing_cast(Expr, _std_api.ne(lhs, rhs))


def le(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect less-than-or-equal expression."""
    return _typing_cast(Expr, _std_api.le(lhs, rhs))


def ge(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect greater-than-or-equal expression."""
    return _typing_cast(Expr, _std_api.ge(lhs, rhs))


def gt(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect greater-than expression."""
    return _typing_cast(Expr, _std_api.gt(lhs, rhs))


def lt(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect less-than expression."""
    return _typing_cast(Expr, _std_api.lt(lhs, rhs))


def equal(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Alias for equality."""
    return _typing_cast(Expr, _std_api.equal(lhs, rhs))


def not_equal(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Alias for inequality."""
    return _typing_cast(Expr, _std_api.not_equal(lhs, rhs))


def less_equal(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Alias for less-than-or-equal."""
    return _typing_cast(Expr, _std_api.less_equal(lhs, rhs))


def greater_equal(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Alias for greater-than-or-equal."""
    return _typing_cast(Expr, _std_api.greater_equal(lhs, rhs))


def less(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Alias for less-than."""
    return _typing_cast(Expr, _std_api.less(lhs, rhs))


def greater(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Alias for greater-than."""
    return _typing_cast(Expr, _std_api.greater(lhs, rhs))


def logical_and(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect logical-and expression."""
    return _typing_cast(Expr, _std_api.logical_and(lhs, rhs))


def logical_or(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect logical-or expression."""
    return _typing_cast(Expr, _std_api.logical_or(lhs, rhs))


def logical_not(operand: ExprLike) -> Expr:
    """Create a standard dialect logical-not expression."""
    return _typing_cast(Expr, _std_api.logical_not(operand))


def left_shift(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect left-shift expression."""
    return _typing_cast(Expr, _std_api.left_shift(lhs, rhs))


def right_shift(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect right-shift expression."""
    return _typing_cast(Expr, _std_api.right_shift(lhs, rhs))


def bitwise_and(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect bitwise-and expression."""
    return _typing_cast(Expr, _std_api.bitwise_and(lhs, rhs))


def bitwise_or(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect bitwise-or expression."""
    return _typing_cast(Expr, _std_api.bitwise_or(lhs, rhs))


def bitwise_xor(lhs: ExprLike, rhs: ExprLike) -> Expr:
    """Create a standard dialect bitwise-xor expression."""
    return _typing_cast(Expr, _std_api.bitwise_xor(lhs, rhs))


def bitwise_not(operand: ExprLike) -> Expr:
    """Create a standard dialect bitwise-not expression."""
    return _typing_cast(Expr, _std_api.bitwise_not(operand))


def bitwise_neg(operand: ExprLike) -> Expr:
    """Alias for bitwise-not."""
    return _typing_cast(Expr, _std_api.bitwise_neg(operand))


def neg(operand: ExprLike) -> Expr:
    """Create unary negation as ``0 - operand``."""
    return _typing_cast(Expr, _std_api.neg(operand))


def abs(operand: ExprLike) -> Expr:
    """Create a standard dialect absolute-value expression."""
    return _typing_cast(Expr, _std_api.abs(operand))


def if_then_else(cond: ExprLike, then_expr: ExprLike, else_expr: ExprLike) -> Expr:
    """Create a standard dialect ternary expression."""
    return _typing_cast(Expr, _std_api.if_then_else(cond, then_expr, else_expr))


def select(cond: ExprLike, then_expr: ExprLike, else_expr: ExprLike) -> Expr:
    """Alias for a ternary expression."""
    return _typing_cast(Expr, _std_api.select(cond, then_expr, else_expr))


__all__ = [
    "Abs",
    "Add",
    "Aggregate",
    "And",
    "AnyTy",
    "Assert",
    "Attrs",
    "BindExpr",
    "BitwiseAnd",
    "BitwiseNot",
    "BitwiseOr",
    "BitwiseXor",
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
    "IfExpr",
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
    "TupleTy",
    "Ty",
    "Var",
    "VarDef",
    "While",
    "Yield",
    "abs",
    "add",
    "bitwise_and",
    "bitwise_neg",
    "bitwise_not",
    "bitwise_or",
    "bitwise_xor",
    "cast",
    "cdiv",
    "cmod",
    "eq",
    "equal",
    "floordiv",
    "floormod",
    "ge",
    "greater",
    "greater_equal",
    "gt",
    "if_then_else",
    "le",
    "left_shift",
    "less",
    "less_equal",
    "logical_and",
    "logical_not",
    "logical_or",
    "lt",
    "max",
    "min",
    "mul",
    "ne",
    "neg",
    "not_equal",
    "pow",
    "right_shift",
    "select",
    "sub",
    "truncdiv",
    "truncmod",
]
