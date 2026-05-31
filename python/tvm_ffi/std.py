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

import contextlib
from collections.abc import (
    Generator,
    ItemsView,
    Iterator,
    KeysView,
    Mapping,
    MutableMapping,
    MutableSequence,
    Sequence,
)
from enum import IntEnum, IntFlag
from typing import Any, ClassVar, Literal, overload
from typing import cast as _typing_cast

from typing_extensions import Never, Protocol, TypeAlias

from tvm_ffi import dtype
from tvm_ffi.core import MISSING, Function, Object, _lookup_type_attr
from tvm_ffi.dataclasses import c_class, field
from tvm_ffi.pyast import PrinterConfig

from . import _std_api


class _FactoryLike(Protocol):
    def to_dialect(self) -> Ty: ...


TyLike: TypeAlias = "Ty | str | _FactoryLike"
AttrsLike: TypeAlias = "Attrs | Mapping[str, Any] | None"
ExprLike: TypeAlias = "Expr | bool | int | float | str"
RangeLike: TypeAlias = "Range | ExprLike"
DefaultIntegerType: str = "int64"
DefaultFloatType: str = "float32"


def collect_dialect_fields(obj: Any) -> FieldCollectionResult:
    """Run the default std dialect field collector."""
    type_info = getattr(Node, "__tvm_ffi_type_info__")
    collector = _lookup_type_attr(
        type_info.type_index,
        "__ffi_dialect_field_collector__",
    )
    if collector is None:
        raise RuntimeError("ffi.std.Node field collector is not registered")
    return _typing_cast(FieldCollectionResult, collector(obj))


def normalize_ty(value: Any, default: Any = MISSING) -> Ty:
    """Normalize parser-side type factories and dtype strings to ``std.Ty``."""
    if value is None:
        if default is MISSING:
            raise TypeError("expected std type, got NoneType")
        return normalize_ty(default)
    if isinstance(value, Ty):
        return value
    if hasattr(value, "to_dialect"):
        ty = value.to_dialect()  # ty: ignore[call-non-callable]
        if isinstance(ty, Ty):
            return ty
        raise TypeError(f"expected std type from to_dialect(), got {type(ty).__name__}")
    if isinstance(value, str):
        return PrimTy(value)
    raise TypeError(f"expected std type, got {type(value).__name__}")


def _normalize_expr(value: ExprLike, like: Expr | None = None) -> Expr:
    """Normalize Python literals to standard dialect immediate expressions."""
    if isinstance(value, Expr):
        return value
    if like is not None:
        ty = like.ty
        if isinstance(ty, PrimTy):
            return const(ty.dtype, _typing_cast(Any, value))
    return Expr.literal(value)


def _normalize_attrs(value: AttrsLike) -> Attrs | None:
    """Normalize mapping attributes to ``std.Attrs``."""
    if value is None or isinstance(value, Attrs):
        return value
    if isinstance(value, Mapping):
        return DictAttrs(**dict(value))
    raise TypeError(f"expected std attrs, got {type(value).__name__}")


@c_class("ffi.std.Node", init=False)
class Node(Object):
    """Base class for the standard dialect.

    Subclasses declare their printed dialect and mnemonic with
    ``mnemonic="dialect.Name"`` in the class definition.
    """

    __ffi_dialect_mnemonic__: ClassVar[tuple[str, str]] = ("std", "Node")

    # tvm-ffi-stubgen(begin): object/ffi.std.Node
    # fmt: off
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __init__(self, _no_direct_init: Never) -> None: ...

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

        @staticmethod
        def __ffi_dialect_field_collector__(obj: Any) -> FieldCollectionResult: ...

    def __init_subclass__(cls, *, mnemonic: str, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        dialect, name = mnemonic.rsplit(".", 1)
        cls.__ffi_dialect_mnemonic__ = (dialect, name)
        cls.__annotations__ = {
            **cls.__dict__.get("__annotations__", {}),
            "__ffi_dialect_mnemonic__": ClassVar,
        }

    def text(self, config: PrinterConfig | None = None) -> str:
        """Render this standard dialect node with the FFI text printer."""
        from tvm_ffi import pyast  # noqa: PLC0415

        return pyast.to_python(self, config)

    def text_render(
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
    # fmt: on
    # tvm-ffi-stubgen(end)


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
        self.__ffi_init__(name, ty=normalize_ty(ty))


@c_class("ffi.std.BaseScope")
class BaseScope(Stmt, mnemonic="std.BaseScope"):
    """Base class for scoped statement blocks."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BaseScope
    # fmt: off
    if TYPE_CHECKING:
        def __init__(self) -> None: ...
        def __ffi_init__(self) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self) -> None:
        self.__ffi_init__()


@c_class("ffi.std.BaseFunc")
class BaseFunc(Stmt, mnemonic="std.BaseFunc"):
    """Base class for standard dialect functions."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BaseFunc
    # fmt: off
    symbol: str
    args: MutableSequence[Var]
    ret_type: Ty | None
    if TYPE_CHECKING:
        def __init__(self, symbol: str, args: MutableSequence[Var], ret_type: Ty | None) -> None: ...
        def __ffi_init__(self, symbol: str, args: MutableSequence[Var], ret_type: Ty | None) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        symbol: str,
        args: Sequence[Var],
        ret_type: TyLike | None,
    ) -> None:
        self.__ffi_init__(
            symbol,
            list(args),
            normalize_ty(ret_type) if ret_type is not None else None,
        )


@c_class("ffi.std.Func")
class Func(BaseFunc, mnemonic="std.Func"):
    """A standard dialect function."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Func
    # fmt: off
    body: MutableSequence[Stmt]
    attrs: Attrs | None
    if TYPE_CHECKING:
        def __init__(self, symbol: str, args: MutableSequence[Var], ret_type: Ty | None, body: MutableSequence[Stmt], attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, _0: str, _1: MutableSequence[Var], _2: Ty | None, _3: MutableSequence[Stmt], _4: Attrs | None, /) -> None: ...  # ty: ignore[invalid-method-override]
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
            attrs: AttrsLike = None,
        ) -> None: ...

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        symbol: str,
        args: Sequence[Var],
        ret_type: TyLike | None,
        body: Sequence[Stmt],
        *,
        attrs: AttrsLike = None,
    ) -> None:
        self.__ffi_init__(
            symbol,
            list(args),
            normalize_ty(ret_type) if ret_type is not None else None,
            list(body),
            _normalize_attrs(attrs),
        )


@c_class("ffi.std.Module")
class Module(Node, mnemonic="std.Module"):
    """A module containing functions."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Module
    # fmt: off
    funcs: MutableSequence[BaseFunc]
    if TYPE_CHECKING:
        def __init__(self, funcs: MutableSequence[BaseFunc]) -> None: ...
        def __ffi_init__(self, funcs: MutableSequence[BaseFunc]) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.Range")
class Range(Aggregate, mnemonic="std.Range"):
    """A start/extent range or slice."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Range
    # fmt: off
    start: Expr | None
    extent: Expr
    step: Expr | None
    if TYPE_CHECKING:
        def __init__(self, extent: Expr, start: Expr | None = ..., *, step: Expr | None = ...) -> None: ...
        def __ffi_init__(self, _0: Expr | None, _1: Expr, _2: Expr | None, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    start = field(default=None)
    extent = field()
    step = field(default=None)

    if TYPE_CHECKING:

        @overload
        def __init__(self, extent: ExprLike, *, step: ExprLike | None = ...) -> None: ...

        @overload
        def __init__(
            self, start: ExprLike | None, extent: ExprLike, *, step: ExprLike | None = ...
        ) -> None: ...

    def __init__(
        self,
        *args: ExprLike | None,
        step: ExprLike | None = None,
    ) -> None:
        if len(args) > 2:
            raise TypeError(f"Range expects at most 2 positional arguments, but got {len(args)}")
        if len(args) == 0:
            raise TypeError("Range missing required extent")
        elif len(args) == 1:
            if args[0] is None:
                raise TypeError("Range missing required extent")
            start_value = None
            extent_value = args[0]
        elif len(args) == 2:
            if args[1] is None:
                raise TypeError("Range missing required extent")
            start_value, extent_value = args
        self.__ffi_init__(start_value, extent_value, step)  # type: ignore[call-arg]


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
        self.__ffi_init__(value, ty=normalize_ty(ty))

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
        self.__ffi_init__(value, ty=normalize_ty(ty))

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
        self.__ffi_init__(value, ty=normalize_ty(ty))

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
        self.__ffi_init__(value, ty=normalize_ty(ty))

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
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Sub")
class Sub(Expr, mnemonic="std.Sub"):
    """Subtraction."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Sub
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Mul")
class Mul(Expr, mnemonic="std.Mul"):
    """Multiplication."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Mul
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


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
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


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
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


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
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


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
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Pow")
class Pow(Expr, mnemonic="std.Pow"):
    """Exponentiation."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Pow
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.LShift")
class LShift(Expr, mnemonic="std.LShift"):
    """Left shift."""

    # tvm-ffi-stubgen(begin): object/ffi.std.LShift
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.RShift")
class RShift(Expr, mnemonic="std.RShift"):
    """Right shift."""

    # tvm-ffi-stubgen(begin): object/ffi.std.RShift
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.BitwiseAnd")
class BitwiseAnd(Expr, mnemonic="std.BitwiseAnd"):
    """Bitwise and."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BitwiseAnd
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.BitwiseOr")
class BitwiseOr(Expr, mnemonic="std.BitwiseOr"):
    """Bitwise or."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BitwiseOr
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.BitwiseXor")
class BitwiseXor(Expr, mnemonic="std.BitwiseXor"):
    """Bitwise exclusive or."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BitwiseXor
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Min")
class Min(Expr, mnemonic="std.Min"):
    """Minimum."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Min
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Max")
class Max(Expr, mnemonic="std.Max"):
    """Maximum."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Max
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Eq")
class Eq(Expr, mnemonic="std.Eq"):
    """Equality comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Eq
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Ne")
class Ne(Expr, mnemonic="std.Ne"):
    """Inequality comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Ne
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Le")
class Le(Expr, mnemonic="std.Le"):
    """Less-than-or-equal comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Le
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Ge")
class Ge(Expr, mnemonic="std.Ge"):
    """Greater-than-or-equal comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Ge
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Gt")
class Gt(Expr, mnemonic="std.Gt"):
    """Greater-than comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Gt
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Lt")
class Lt(Expr, mnemonic="std.Lt"):
    """Less-than comparison."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Lt
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.And")
class And(Expr, mnemonic="std.And"):
    """Logical and."""

    # tvm-ffi-stubgen(begin): object/ffi.std.And
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Or")
class Or(Expr, mnemonic="std.Or"):
    """Logical or."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Or
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Any, _2: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(a, b, normalize_ty(ty))


@c_class("ffi.std.Not")
class Not(Expr, mnemonic="std.Not"):
    """Logical not."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Not
    # fmt: off
    operand: Expr
    if TYPE_CHECKING:
        def __init__(self, operand: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, operand: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(operand, normalize_ty(ty))


@c_class("ffi.std.BitwiseNot")
class BitwiseNot(Expr, mnemonic="std.BitwiseNot"):
    """Bitwise not."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BitwiseNot
    # fmt: off
    operand: Expr
    if TYPE_CHECKING:
        def __init__(self, operand: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, operand: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(operand, normalize_ty(ty))


@c_class("ffi.std.Abs")
class Abs(Expr, mnemonic="std.Abs"):
    """Absolute value."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Abs
    # fmt: off
    operand: Expr
    if TYPE_CHECKING:
        def __init__(self, operand: ExprLike, *, ty: TyLike) -> None: ...
        def __ffi_init__(self, _0: Any, _1: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, operand: ExprLike, *, ty: TyLike) -> None:
        self.__ffi_init__(operand, normalize_ty(ty))


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
        def __ffi_init__(self, _0: Any, _1: Any, _2: Any, _3: Ty, /) -> None: ...  # ty: ignore[invalid-method-override]
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
        self.__ffi_init__(cond, then_expr, else_expr, normalize_ty(ty))


@c_class("ffi.std.Load")
class Load(Expr, mnemonic="std.Load"):
    """Indexed load."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Load
    # fmt: off
    lhs: Expr
    indices: MutableSequence[Range]
    if TYPE_CHECKING:
        def __init__(self, lhs: Expr, indices: MutableSequence[Range], *, ty: Ty) -> None: ...
        def __ffi_init__(self, _0: Any, _1: MutableSequence[Range], _2: Ty | None, /) -> None: ...  # ty: ignore[invalid-method-override]
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
        self.__ffi_init__(lhs, indices, normalize_ty(ty) if ty is not None else None)


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
        self.__ffi_init__(value, ty=normalize_ty(ty))


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
        elif not isinstance(callee, (str, Expr, BaseFunc)):
            raise TypeError(
                "std.Call callee must be a name, expression, or function, "
                f"got {type(callee).__name__}"
            )
        self.__ffi_init__(callee, args, kwargs or None, ty=normalize_ty(ty))


@c_class("ffi.std.IfStmt")
class IfStmt(Stmt, mnemonic="std.IfStmt"):
    """If/else statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.IfStmt
    # fmt: off
    cond: Expr
    then_body: MutableSequence[Stmt]
    else_body: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, cond: Expr, then_body: MutableSequence[Stmt], else_body: MutableSequence[Stmt]) -> None: ...
        def __ffi_init__(self, _0: Expr, _1: MutableSequence[Stmt], _2: MutableSequence[Stmt], /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        cond: ExprLike,
        then_body: Sequence[Stmt],
        else_body: Sequence[Stmt],
    ) -> None:
        self.__ffi_init__(
            cond,
            list(then_body),
            list(else_body),
        )


@c_class("ffi.std.Scope")
class Scope(BaseScope, mnemonic="std.Scope"):
    """A scoped statement block with lexical bindings."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Scope
    # fmt: off
    binds: MutableSequence[Stmt]
    body: MutableSequence[Stmt]
    attrs: Attrs | None
    if TYPE_CHECKING:
        def __init__(self, binds: MutableSequence[Stmt], body: MutableSequence[Stmt], attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, _0: MutableSequence[Stmt], _1: MutableSequence[Stmt], _2: Attrs | None, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        binds: Sequence[Stmt],
        body: Sequence[Stmt],
        *,
        attrs: AttrsLike = None,
    ) -> None:
        self.__ffi_init__(list(binds), list(body), _normalize_attrs(attrs))


@c_class("ffi.std.BaseFor")
class BaseFor(Stmt, mnemonic="std.BaseFor"):
    """Base class for standard dialect for loops."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BaseFor
    # fmt: off
    extent: Expr
    var: Var
    if TYPE_CHECKING:
        def __init__(self, extent: Expr, var: Var) -> None: ...
        def __ffi_init__(self, extent: Expr, var: Var) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        extent: ExprLike,
        var: Var,
    ) -> None:
        self.__ffi_init__(extent, var)


@c_class("ffi.std.For")
class For(BaseFor, mnemonic="std.For"):
    """For loop."""

    # tvm-ffi-stubgen(begin): object/ffi.std.For
    # fmt: off
    start: Expr | None
    step: Expr | None
    body: MutableSequence[Stmt]
    attrs: Attrs | None
    if TYPE_CHECKING:
        def __init__(self, extent: Expr, var: Var, body: MutableSequence[Stmt], start: Expr | None = ..., attrs: Attrs | None = ..., *, step: Expr | None = ...) -> None: ...
        def __ffi_init__(self, _0: Expr | None, _1: Expr, _2: Expr | None, _3: Var, _4: MutableSequence[Stmt], _5: Attrs | None, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __init__(
            self,
            start: ExprLike | None,
            extent: ExprLike,
            var: Var,
            body: MutableSequence[Stmt],
            *,
            step: ExprLike | None = ...,
            attrs: AttrsLike = ...,
        ) -> None: ...

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        start: ExprLike | None,
        extent: ExprLike,
        *args: Any,
        step: ExprLike | None = None,
        var: Var | None = None,
        body: Sequence[Stmt] | None = None,
        attrs: AttrsLike = None,
    ) -> None:
        if len(args) > 2:
            raise TypeError(f"For expects at most 4 positional arguments, but got {len(args) + 2}")
        if args:
            if var is not None:
                raise TypeError("For got loop variable both positionally and by keyword")
            if not isinstance(args[0], Var):
                raise TypeError(f"For expected a loop variable, got {type(args[0]).__name__}")
            var = args[0]
        if len(args) == 2:
            if body is not None:
                raise TypeError("For got body both positionally and by keyword")
            body = args[1]
        if body is None:
            raise TypeError("For missing required body")
        if var is None:
            raise TypeError("For missing required var")
        self.__ffi_init__(start, extent, step, var, list(body), _normalize_attrs(attrs))


@c_class("ffi.std.BaseWhile")
class BaseWhile(Stmt, mnemonic="std.BaseWhile"):
    """Base class for standard dialect while loops."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BaseWhile
    # fmt: off
    cond: Expr
    if TYPE_CHECKING:
        def __init__(self, cond: Expr) -> None: ...
        def __ffi_init__(self, cond: Expr) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, cond: ExprLike) -> None:
        self.__ffi_init__(cond)


@c_class("ffi.std.While")
class While(BaseWhile, mnemonic="std.While"):
    """While loop."""

    # tvm-ffi-stubgen(begin): object/ffi.std.While
    # fmt: off
    body: MutableSequence[Stmt]
    attrs: Attrs | None
    if TYPE_CHECKING:
        def __init__(self, cond: Expr, body: MutableSequence[Stmt], attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, _0: Expr, _1: MutableSequence[Stmt], _2: Attrs | None, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __init__(
            self,
            cond: ExprLike,
            body: MutableSequence[Stmt],
            *,
            attrs: AttrsLike = None,
        ) -> None: ...

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        cond: ExprLike,
        body: MutableSequence[Stmt],
        *,
        attrs: AttrsLike = None,
    ) -> None:
        self.__ffi_init__(cond, list(body), _normalize_attrs(attrs))


@c_class("ffi.std.BaseBindExpr")
class BaseBindExpr(Stmt, mnemonic="std.BaseBindExpr"):
    """Base class for expression bindings."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BaseBindExpr
    # fmt: off
    expr: Expr
    if TYPE_CHECKING:
        def __init__(self, expr: Expr) -> None: ...
        def __ffi_init__(self, expr: Expr) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, expr: ExprLike) -> None:
        self.__ffi_init__(_normalize_expr(expr))


@c_class("ffi.std.BindExpr")
class BindExpr(BaseBindExpr, mnemonic="std.BindExpr"):
    """Binding that defines variables from an expression."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BindExpr
    # fmt: off
    vars: MutableSequence[Var]
    if TYPE_CHECKING:
        def __init__(self, expr: Expr, vars: MutableSequence[Var]) -> None: ...
        def __ffi_init__(self, _0: MutableSequence[Var], _1: Expr, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, expr: ExprLike, *args: Var) -> None:
        self.__ffi_init__(list(args), _normalize_expr(expr))

    def __ffi_update_var_name__(self, *name: str) -> tuple[Var, ...]:
        if len(name) != len(self.vars):
            raise TypeError(f"expected {len(self.vars)} binding target(s), got {len(name)}")
        for var, new_name in zip(self.vars, name):
            var.name = new_name
        return tuple(self.vars)


@c_class("ffi.std.BaseVarDef")
class BaseVarDef(Stmt, mnemonic="std.BaseVarDef"):
    """Base class for variable definitions."""

    # tvm-ffi-stubgen(begin): object/ffi.std.BaseVarDef
    # fmt: off
    if TYPE_CHECKING:
        def __init__(self) -> None: ...
        def __ffi_init__(self) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self) -> None:
        self.__ffi_init__()


@c_class("ffi.std.VarDef")
class VarDef(BaseVarDef, mnemonic="std.VarDef"):
    """Binding that defines variables without a source expression."""

    # tvm-ffi-stubgen(begin): object/ffi.std.VarDef
    # fmt: off
    vars: MutableSequence[Var]
    if TYPE_CHECKING:
        def __init__(self, vars: MutableSequence[Var]) -> None: ...
        def __ffi_init__(self, vars: MutableSequence[Var]) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, *args: Var | TyLike) -> None:
        vars = [arg if isinstance(arg, Var) else Var(normalize_ty(arg), "") for arg in args]
        self.__ffi_init__(vars)

    def __ffi_update_var_name__(self, *name: str) -> tuple[Var, ...]:
        if len(name) != len(self.vars):
            raise TypeError(f"expected {len(self.vars)} binding target(s), got {len(name)}")
        for var, new_name in zip(self.vars, name):
            var.name = new_name
        return tuple(self.vars)


@c_class("ffi.std.Store")
class Store(Stmt, mnemonic="std.Store"):
    """Indexed store."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Store
    # fmt: off
    lhs: Expr
    indices: MutableSequence[Range]
    rhs: Expr
    if TYPE_CHECKING:
        def __init__(self, lhs: Expr, indices: MutableSequence[Range], rhs: Expr) -> None: ...
        def __ffi_init__(self, _0: Expr, _1: MutableSequence[Range], _2: Expr, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, lhs: ExprLike, rhs: ExprLike, *indices: RangeLike) -> None:
        self.__ffi_init__(lhs, indices, rhs)


@c_class("ffi.std.Assert")
class Assert(Stmt, mnemonic="std.Assert"):
    """Assertion statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Assert
    # fmt: off
    cond: Expr
    if TYPE_CHECKING:
        def __init__(self, cond: Expr) -> None: ...
        def __ffi_init__(self, _0: Expr, /) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, cond: ExprLike) -> None:
        self.__ffi_init__(cond)


@c_class("ffi.std.Return")
class Return(Stmt, mnemonic="std.Return"):
    """Return statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Return
    # fmt: off
    vars: MutableSequence[Var]
    if TYPE_CHECKING:
        def __init__(self, vars: MutableSequence[Var]) -> None: ...
        def __ffi_init__(self, vars: MutableSequence[Var]) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, *vars: Var) -> None:
        self.__ffi_init__(list(vars))


@c_class("ffi.std.Yield")
class Yield(Stmt, mnemonic="std.Yield"):
    """Yield statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Yield
    # fmt: off
    vars: MutableSequence[Var]
    if TYPE_CHECKING:
        def __init__(self, vars: MutableSequence[Var]) -> None: ...
        def __ffi_init__(self, vars: MutableSequence[Var]) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, *vars: Var) -> None:
        self.__ffi_init__(list(vars))


@c_class("ffi.std.Break")
class Break(Stmt, mnemonic="std.Break"):
    """Break statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Break
    # fmt: off
    if TYPE_CHECKING:
        def __init__(self) -> None: ...
        def __ffi_init__(self) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self) -> None:
        self.__ffi_init__()


@c_class("ffi.std.Continue")
class Continue(Stmt, mnemonic="std.Continue"):
    """Continue statement."""

    # tvm-ffi-stubgen(begin): object/ffi.std.Continue
    # fmt: off
    if TYPE_CHECKING:
        def __init__(self) -> None: ...
        def __ffi_init__(self) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self) -> None:
        self.__ffi_init__()


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


@c_class("ffi.std.FieldCollectionResult")
class FieldCollectionResult(Node, mnemonic="std.FieldCollectionResult"):
    """Collected language fields for std-derived dialect text printing."""

    # tvm-ffi-stubgen(begin): object/ffi.std.FieldCollectionResult
    # fmt: off
    args: MutableSequence[Any]
    attrs: DictAttrs
    outs: MutableSequence[Var]
    body: MutableSequence[Node]
    ty: Ty | None
    if TYPE_CHECKING:
        def __init__(self, args: MutableSequence[Any], attrs: DictAttrs, outs: MutableSequence[Var], body: MutableSequence[Node], ty: Ty | None) -> None: ...
        def __ffi_init__(self, args: MutableSequence[Any], attrs: DictAttrs, outs: MutableSequence[Var], body: MutableSequence[Node], ty: Ty | None) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        args: Sequence[Any] | None = None,
        attrs: DictAttrs | Mapping[str, Any] | None = None,
        outs: Sequence[Var] | None = None,
        body: Sequence[Node] | None = None,
        ty: Ty | None = None,
    ) -> None:
        if attrs is None:
            attrs = DictAttrs()
        elif isinstance(attrs, Mapping):
            attrs = DictAttrs(**attrs)
        self.__ffi_init__(list(args or []), attrs, list(outs or []), list(body or []), ty)


class ProofStrength(IntEnum):
    """Strength level used by :meth:`Analyzer.can_prove`."""

    DEFAULT = 0
    SYMBOLIC_BOUND = 1


class RewriteExtension(IntFlag):
    """Optional rewrite simplifier extensions."""

    NONE = 0
    TRANSITIVELY_PROVE_INEQUALITIES = 1 << 0
    CONVERT_BOOLEAN_TO_AND_OF_ORS = 1 << 1
    APPLY_CONSTRAINTS_TO_BOOLEAN_BRANCHES = 1 << 2
    COMPARISON_OF_PRODUCT_AND_SUM = 1 << 3


@c_class("ffi.std.ConstIntBound")
class ConstIntBound(Object):
    """Closed integer interval inferred by constant integer bound analysis."""

    min_value: int
    max_value: int


@c_class("ffi.std.ModularSet")
class ModularSet(Object):
    """Set of integers representable as ``coeff * x + base``."""

    coeff: int
    base: int


@c_class("ffi.std.IntervalSet", init=False)
class IntervalSet(Object):
    """Symbolic interval set."""

    min_value: Expr
    max_value: Expr

    if TYPE_CHECKING:

        def __ffi_init__(self, min_value: Expr, max_value: Expr) -> None: ...

    def __init__(self, min_value: ExprLike, max_value: ExprLike) -> None:
        if isinstance(min_value, int) and isinstance(max_value, int):
            lhs = const("int32", min_value)
            rhs = const("int32", max_value)
            self.__ffi_init__(lhs, rhs)
            return
        like = max_value if isinstance(max_value, Expr) else None
        lhs = _normalize_expr(min_value, like)
        rhs = _normalize_expr(max_value, lhs)
        self.__ffi_init__(lhs, rhs)


@c_class("ffi.std.Analyzer")
class Analyzer(Object):
    """Symbolic analyzer for scalar :class:`tvm_ffi.std.Expr` values."""

    if TYPE_CHECKING:

        def mark_global_non_neg_value(self, value: Expr) -> None:
            """Mark an expression as globally non-negative."""
            ...

        def bind_expr(
            self,
            var: Var,
            expr: Expr,
            allow_override: bool = False,
        ) -> None:
            """Bind a variable to an expression."""
            ...

        def bind_range(
            self,
            var: Var,
            range: Range,
            allow_override: bool = False,
        ) -> None:
            """Bind a variable to a range."""
            ...

        def can_prove_greater_equal(self, expr: Expr, lower_bound: int) -> bool:
            """Return whether ``expr >= lower_bound`` can be proven."""
            ...

        def can_prove_less(self, expr: Expr, upper_bound: int) -> bool:
            """Return whether ``expr < upper_bound`` can be proven."""
            ...

        def can_prove_less_equal_than_symbolic_shape_value(
            self,
            lhs: Expr,
            shape: Expr,
        ) -> bool:
            """Return whether ``lhs <= shape`` can be proven for shape values."""
            ...

    def bind(
        self,
        var: Var,
        bound: Range | ExprLike,
        allow_override: bool = False,
    ) -> None:
        """Bind ``var`` to an expression or range."""
        if isinstance(bound, Range):
            self.bind_range(var, bound, allow_override)
        else:
            self.bind_expr(var, _normalize_expr(bound, var), allow_override)

    def can_prove(
        self,
        cond: Expr,
        *,
        strength: Literal["default", "symbolic_bound"] | ProofStrength = ProofStrength.DEFAULT,
    ) -> bool:
        """Return whether a boolean expression can be proven."""
        if isinstance(strength, str):
            strength = {
                "default": ProofStrength.DEFAULT,
                "symbolic_bound": ProofStrength.SYMBOLIC_BOUND,
            }[strength]
        return bool(_std_api._AnalyzerCanProve(self, cond, int(strength)))

    def can_prove_equal(self, lhs: Expr, rhs: ExprLike) -> bool:
        """Return whether two expressions can be proven equal."""
        return bool(_std_api._AnalyzerCanProveEqual(self, lhs, _normalize_expr(rhs, lhs)))

    def simplify(self, expr: Expr, *, steps: int = 2) -> Expr:
        """Simplify an expression."""
        return _typing_cast(Expr, _std_api._AnalyzerSimplify(self, expr, steps))


def const(dtype: dtype | str, value: bool | int | float) -> Expr:
    """Create a scalar constant with the requested dtype."""
    ty = PrimTy(dtype)
    if ty.dtype.is_bool:
        return BoolImm(ty, bool(value))
    if ty.dtype.is_float:
        return FloatImm(ty, float(value))
    return IntImm(ty, int(value))


def min_value(dtype: dtype | str) -> Expr:
    """Return the minimum integer value representable by ``dtype``."""
    ty = PrimTy(dtype)
    if not ty.dtype.is_integer:
        raise TypeError("min_value only supports integer dtypes")
    if str(ty.dtype).startswith("uint"):
        return IntImm(ty, 0)
    bits = ty.dtype.bits
    return IntImm(ty, -(1 << (bits - 1)))


def max_value(dtype: dtype | str) -> Expr:
    """Return the maximum integer value representable by ``dtype``."""
    ty = PrimTy(dtype)
    if not ty.dtype.is_integer:
        raise TypeError("max_value only supports integer dtypes")
    bits = ty.dtype.bits
    if str(ty.dtype).startswith("uint"):
        return IntImm(ty, (1 << bits) - 1)
    return IntImm(ty, (1 << (bits - 1)) - 1)


def const_int_bound(analyzer: Analyzer, expr: Expr) -> ConstIntBound:
    """Run constant integer bound analysis."""
    return _typing_cast(ConstIntBound, _std_api._AnalyzerConstIntBound(analyzer, expr))


def modular_set(analyzer: Analyzer, expr: Expr) -> ModularSet:
    """Run modular set analysis."""
    return _typing_cast(ModularSet, _std_api._AnalyzerModularSet(analyzer, expr))


def rewrite_simplify(analyzer: Analyzer, expr: Expr) -> Expr:
    """Run the rewrite simplifier only."""
    return _typing_cast(Expr, _std_api._AnalyzerRewriteSimplify(analyzer, expr))


def canonical_simplify(analyzer: Analyzer, expr: Expr) -> Expr:
    """Run the canonical simplifier only."""
    return _typing_cast(Expr, _std_api._AnalyzerCanonicalSimplify(analyzer, expr))


def interval_set(
    analyzer: Analyzer,
    expr: Expr,
    dom_map: Mapping[Var, IntervalSet],
) -> IntervalSet:
    """Evaluate the interval set of ``expr`` under ``dom_map``."""
    return _typing_cast(IntervalSet, _std_api._AnalyzerIntervalSet(analyzer, expr, dict(dom_map)))


def const_int_bound_update(
    analyzer: Analyzer,
    var: Var,
    info: ConstIntBound,
    allow_override: bool = False,
) -> None:
    """Update the analyzer's constant integer bound state."""
    _std_api._AnalyzerConstIntBoundUpdate(analyzer, var, info, allow_override)


def get_enabled_extensions(analyzer: Analyzer) -> RewriteExtension:
    """Return enabled rewrite extensions."""
    return RewriteExtension(_std_api._AnalyzerGetEnabledExtensions(analyzer))


def set_enabled_extensions(analyzer: Analyzer, flags: RewriteExtension | int) -> None:
    """Set enabled rewrite extensions."""
    _std_api._AnalyzerSetEnabledExtensions(analyzer, int(flags))


@contextlib.contextmanager
def enter_constraint(analyzer: Analyzer, constraint: Expr | None) -> Generator[None, None, None]:
    """Temporarily add a boolean constraint to analyzer state."""
    if constraint is None:
        yield
        return
    exit_constraint = _typing_cast(
        Function, _std_api._AnalyzerEnterConstraint(analyzer, constraint)
    )
    try:
        yield
    finally:
        exit_constraint()


def cast(ty: TyLike, value: ExprLike) -> Expr:
    """Cast an expression to a standard dialect type."""
    return _typing_cast(Expr, _std_api.cast(normalize_ty(ty), value))


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
    "Analyzer",
    "And",
    "AnyTy",
    "Assert",
    "Attrs",
    "BaseBindExpr",
    "BaseFor",
    "BaseFunc",
    "BaseScope",
    "BaseVarDef",
    "BaseWhile",
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
    "ConstIntBound",
    "Continue",
    "DictAttrs",
    "Eq",
    "Expr",
    "FieldCollectionResult",
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
    "IntervalSet",
    "LShift",
    "Le",
    "Load",
    "Lt",
    "Max",
    "Min",
    "ModularSet",
    "Module",
    "Mul",
    "Ne",
    "Node",
    "Not",
    "Or",
    "Pow",
    "PrimTy",
    "ProofStrength",
    "RShift",
    "Range",
    "Return",
    "RewriteExtension",
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
    "canonical_simplify",
    "cast",
    "cdiv",
    "cmod",
    "collect_dialect_fields",
    "const",
    "const_int_bound",
    "const_int_bound_update",
    "enter_constraint",
    "eq",
    "equal",
    "floordiv",
    "floormod",
    "ge",
    "get_enabled_extensions",
    "greater",
    "greater_equal",
    "gt",
    "if_then_else",
    "interval_set",
    "le",
    "left_shift",
    "less",
    "less_equal",
    "logical_and",
    "logical_not",
    "logical_or",
    "lt",
    "max",
    "max_value",
    "min",
    "min_value",
    "modular_set",
    "mul",
    "ne",
    "neg",
    "normalize_ty",
    "not_equal",
    "pow",
    "rewrite_simplify",
    "right_shift",
    "select",
    "set_enabled_extensions",
    "sub",
    "truncdiv",
    "truncmod",
]
