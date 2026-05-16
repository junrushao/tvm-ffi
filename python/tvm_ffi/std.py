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
from typing import Any, ClassVar, cast

from typing_extensions import Never, Protocol, TypeAlias

from tvm_ffi import dtype
from tvm_ffi.core import MISSING, Object
from tvm_ffi.dataclasses import c_class, field
from tvm_ffi.pyast import PrinterConfig


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
        return cast(Any, value).to_dialect()
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
    """Base class for the standard dialect."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Node")

    # tvm-ffi-stubgen(begin): object/ffi.std.Node
    # fmt: off
    # fmt: on
    # tvm-ffi-stubgen(end)

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

    # tvm-ffi-stubgen(begin): object/ffi.std.Ty
    # fmt: off
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.Attrs", init=False)
class Attrs(Node):
    """Base class for standard dialect attributes."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Attrs")

    # tvm-ffi-stubgen(begin): object/ffi.std.Attrs
    # fmt: off
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.Stmt", init=False)
class Stmt(Node):
    """Base class for standard dialect statements."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Stmt")

    # tvm-ffi-stubgen(begin): object/ffi.std.Stmt
    # fmt: off
    attrs: Attrs | None
    # fmt: on
    # tvm-ffi-stubgen(end)

    attrs = field(default=None, kw_only=True)


@c_class("ffi.std.Aggregate", init=False)
class Aggregate(Node):
    """Base class for standard dialect aggregate helper nodes."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Aggregate")

    # tvm-ffi-stubgen(begin): object/ffi.std.Aggregate
    # fmt: off
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.Expr", init=False)
class Expr(Node):
    """Base class for standard dialect expressions."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Expr")

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


@c_class("ffi.std.Var")
class Var(Expr):
    """A named SSA-style variable."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Var")

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
class Func(Stmt):
    """A standard dialect function."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Func")

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
class Module(Node):
    """A module containing functions."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Module")

    # tvm-ffi-stubgen(begin): object/ffi.std.Module
    # fmt: off
    funcs: MutableSequence[Func]
    if TYPE_CHECKING:
        def __init__(self, funcs: MutableSequence[Func]) -> None: ...
        def __ffi_init__(self, funcs: MutableSequence[Func]) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.Range")
class Range(Aggregate):
    """A half-open range or slice."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Range")

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
class AnyTy(Ty):
    """The unconstrained type."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Any")

    # tvm-ffi-stubgen(begin): object/ffi.std.AnyTy
    # fmt: off
    if TYPE_CHECKING:
        def __init__(self) -> None: ...
        def __ffi_init__(self) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.PrimTy")
class PrimTy(Ty):
    """A primitive scalar type."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Prim")

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
class TupleTy(Ty):
    """A tuple type."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Tuple")

    # tvm-ffi-stubgen(begin): object/ffi.std.TupleTy
    # fmt: off
    fields: MutableSequence[Ty]
    if TYPE_CHECKING:
        def __init__(self, fields: MutableSequence[Ty]) -> None: ...
        def __ffi_init__(self, fields: MutableSequence[Ty]) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.std.TensorTy")
class TensorTy(Ty):
    """A tensor type."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Tensor")

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
class BoolImm(Expr):
    """A boolean immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "BoolImm")

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
class IntImm(Expr):
    """An integer immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "IntImm")

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
class FloatImm(Expr):
    """A floating-point immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "FloatImm")

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
class StringImm(Expr):
    """A string immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "StringImm")

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
class Add(Expr):
    """Addition."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Add")

    # tvm-ffi-stubgen(begin): object/ffi.std.Add
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Sub")
class Sub(Expr):
    """Subtraction."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Sub")

    # tvm-ffi-stubgen(begin): object/ffi.std.Sub
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Mul")
class Mul(Expr):
    """Multiplication."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Mul")

    # tvm-ffi-stubgen(begin): object/ffi.std.Mul
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.CDiv")
class CDiv(Expr):
    """C-style division.

    For integer operands, ``CDiv`` means ``truncdiv``: the quotient is
    truncated toward zero.  For floating-point operands, ``CDiv`` means
    C-style division.  Use ``FloorDiv`` only for integer floor division.
    """

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "CDiv")

    # tvm-ffi-stubgen(begin): object/ffi.std.CDiv
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.FloorDiv")
class FloorDiv(Expr):
    """Integer floor division.

    ``FloorDiv`` only works for integer operands.  It always computes
    ``floor(a / b)``, unlike ``CDiv`` which means ``truncdiv`` for integer
    operands and C-style division for floating-point operands.
    """

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "FloorDiv")

    # tvm-ffi-stubgen(begin): object/ffi.std.FloorDiv
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.FloorMod")
class FloorMod(Expr):
    """Integer floor modulo.

    ``FloorMod`` only works for integer operands.  It is paired with
    ``FloorDiv`` and always uses ``floor(a / b)``.  Use ``CMod`` for
    integer ``truncmod`` behavior or floating-point C-style modulo.
    """

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "FloorMod")

    # tvm-ffi-stubgen(begin): object/ffi.std.FloorMod
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.CMod")
class CMod(Expr):
    """C-style modulo.

    For integer operands, ``CMod`` means ``truncmod`` and is paired with
    ``CDiv``.  For floating-point operands, ``CMod`` means C-style modulo.
    Use ``FloorMod`` only for integer floor modulo.
    """

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "CMod")

    # tvm-ffi-stubgen(begin): object/ffi.std.CMod
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Pow")
class Pow(Expr):
    """Exponentiation."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Pow")

    # tvm-ffi-stubgen(begin): object/ffi.std.Pow
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.LShift")
class LShift(Expr):
    """Left shift."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "LShift")

    # tvm-ffi-stubgen(begin): object/ffi.std.LShift
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.RShift")
class RShift(Expr):
    """Right shift."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "RShift")

    # tvm-ffi-stubgen(begin): object/ffi.std.RShift
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Xor")
class Xor(Expr):
    """Bitwise exclusive OR."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Xor")

    # tvm-ffi-stubgen(begin): object/ffi.std.Xor
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Min")
class Min(Expr):
    """Minimum."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Min")

    # tvm-ffi-stubgen(begin): object/ffi.std.Min
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Max")
class Max(Expr):
    """Maximum."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Max")

    # tvm-ffi-stubgen(begin): object/ffi.std.Max
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Eq")
class Eq(Expr):
    """Equality comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Eq")

    # tvm-ffi-stubgen(begin): object/ffi.std.Eq
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Ne")
class Ne(Expr):
    """Inequality comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Ne")

    # tvm-ffi-stubgen(begin): object/ffi.std.Ne
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Le")
class Le(Expr):
    """Less-than-or-equal comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Le")

    # tvm-ffi-stubgen(begin): object/ffi.std.Le
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Ge")
class Ge(Expr):
    """Greater-than-or-equal comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Ge")

    # tvm-ffi-stubgen(begin): object/ffi.std.Ge
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Gt")
class Gt(Expr):
    """Greater-than comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Gt")

    # tvm-ffi-stubgen(begin): object/ffi.std.Gt
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Lt")
class Lt(Expr):
    """Less-than comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Lt")

    # tvm-ffi-stubgen(begin): object/ffi.std.Lt
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.And")
class And(Expr):
    """Logical and."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "And")

    # tvm-ffi-stubgen(begin): object/ffi.std.And
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Or")
class Or(Expr):
    """Logical or."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Or")

    # tvm-ffi-stubgen(begin): object/ffi.std.Or
    # fmt: off
    a: Expr
    b: Expr
    if TYPE_CHECKING:
        def __init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, a: Expr, b: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, a: ExprLike, b: ExprLike, *, ty: TyLike) -> None:
        _binary_expr_ffi_init(self, a, b, ty=ty)


@c_class("ffi.std.Not")
class Not(Expr):
    """Logical not."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Not")

    # tvm-ffi-stubgen(begin): object/ffi.std.Not
    # fmt: off
    operand: Expr
    if TYPE_CHECKING:
        def __init__(self, operand: Expr, *, ty: Ty) -> None: ...
        def __ffi_init__(self, operand: Expr, *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, operand: ExprLike, *, ty: TyLike) -> None:
        _unary_expr_ffi_init(self, operand, ty=ty)


@c_class("ffi.std.Load")
class Load(Expr):
    """Indexed load."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Load")

    # tvm-ffi-stubgen(begin): object/ffi.std.Load
    # fmt: off
    lhs: Expr
    indices: MutableSequence[Range]
    if TYPE_CHECKING:
        def __init__(self, lhs: Expr, indices: MutableSequence[Range], *, ty: Ty) -> None: ...
        def __ffi_init__(self, lhs: Expr, indices: MutableSequence[Range], *, ty: Ty) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(
        self,
        lhs: ExprLike,
        *indices: RangeLike,
        ty: TyLike,
    ) -> None:
        self.__ffi_init__(lhs, indices, ty=_normalize_ty(ty))


@c_class("ffi.std.Cast")
class Cast(Expr):
    """Type cast."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Cast")

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
class Call(Expr):
    """Function call expression."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Call")

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
class IfStmt(Stmt):
    """If/else statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "IfStmt")

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
            attrs=kwargs or None,
        )


@c_class("ffi.std.Scope")
class Scope(Stmt):
    """A scoped statement block."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Scope")

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
class For(Stmt):
    """For loop."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "For")

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


@c_class("ffi.std.While")
class While(Stmt):
    """While loop."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "While")

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


@c_class("ffi.std.BindExpr")
class BindExpr(Stmt):
    """Binding that defines variables from an expression."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "BindExpr")

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
class VarDef(Stmt):
    """Binding that defines variables without a source expression."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "VarDef")

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
class Store(Stmt):
    """Indexed store."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Store")

    # tvm-ffi-stubgen(begin): object/ffi.std.Store
    # fmt: off
    lhs: Expr
    indices: MutableSequence[Range]
    rhs: Expr
    if TYPE_CHECKING:
        def __init__(self, lhs: Expr, indices: MutableSequence[Range], rhs: Expr, *, attrs: Attrs | None = ...) -> None: ...
        def __ffi_init__(self, lhs: Expr, indices: MutableSequence[Range], rhs: Expr, *, attrs: Attrs | None = ...) -> None: ...  # ty: ignore[invalid-method-override]
    # fmt: on
    # tvm-ffi-stubgen(end)

    if TYPE_CHECKING:

        def __ffi_init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, lhs: ExprLike, *indices: RangeLike, rhs: ExprLike, **kwargs: Any) -> None:
        self.__ffi_init__(lhs, indices, rhs, attrs=kwargs or None)


@c_class("ffi.std.Assert")
class Assert(Stmt):
    """Assertion statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Assert")

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
        self.__ffi_init__(cond, attrs=kwargs or None)


@c_class("ffi.std.Return")
class Return(Stmt):
    """Return statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Return")

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
class Yield(Stmt):
    """Yield statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Yield")

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
class Break(Stmt):
    """Break statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Break")

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
class Continue(Stmt):
    """Continue statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Continue")

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
class DictAttrs(Attrs):
    """Dictionary-backed attributes."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "DictAttrs")

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


__all__ = [
    "Add",
    "Aggregate",
    "And",
    "AnyTy",
    "Assert",
    "Attrs",
    "BindExpr",
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
    "TupleTy",
    "Ty",
    "Var",
    "VarDef",
    "While",
    "Xor",
    "Yield",
]
