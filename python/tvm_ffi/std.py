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

from typing import TYPE_CHECKING, Any, ClassVar

from tvm_ffi import dtype
from tvm_ffi.core import Object
from tvm_ffi.dataclasses import c_class, field

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping, MutableSequence, Sequence

    from typing_extensions import Never, TypeAlias

    from tvm_ffi.pyast import PrinterConfig

    DialectMnemonic: TypeAlias = "tuple[str, str] | tuple[str, str, str]"
else:
    DialectMnemonic = tuple


if TYPE_CHECKING:
    AttrsLike: TypeAlias = "Attrs | Mapping[str, Any] | None"
    ExprLike: TypeAlias = "Expr | int | float | str"
    RangeLike: TypeAlias = "Range | ExprLike"


@c_class("ffi.std.Node", init=False)
class Node(Object):
    """Base class for the standard dialect."""

    if TYPE_CHECKING:

        def __init__(self, _no_direct_init: Never) -> None: ...

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


@c_class("ffi.std.Attrs", init=False)
class Attrs(Node):
    """Base class for standard dialect attributes."""


@c_class("ffi.std.Stmt", init=False)
class Stmt(Node):
    """Base class for standard dialect statements."""

    attrs: Attrs | None = field(default=None, kw_only=True)


@c_class("ffi.std.Structure", init=False)
class Structure(Node):
    """Base class for standard dialect structural helper nodes."""


@c_class("ffi.std.Expr", init=False)
class Expr(Node):
    """Base class for standard dialect expressions."""

    ty: Ty


@c_class("ffi.std.Var")
class Var(Expr):
    """A named SSA-style variable."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Var")

    name: str


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
class Range(Structure):
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


@c_class("ffi.std.IntImm")
class IntImm(Expr):
    """An integer immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "IntImm")

    value: int


@c_class("ffi.std.FloatImm")
class FloatImm(Expr):
    """A floating-point immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "FloatImm")

    value: float


@c_class("ffi.std.StringImm")
class StringImm(Expr):
    """A string immediate."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "StringImm")

    value: str


@c_class("ffi.std.Add")
class Add(Expr):
    """Addition."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Add", "__add__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Sub")
class Sub(Expr):
    """Subtraction."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Sub", "__sub__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Mul")
class Mul(Expr):
    """Multiplication."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Mul", "__mul__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.FloorDiv")
class FloorDiv(Expr):
    """Floor division."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "FloorDiv", "__floordiv__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.FloorMod")
class FloorMod(Expr):
    """Floor modulo."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "FloorMod", "__mod__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Min")
class Min(Expr):
    """Minimum."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Min", "min")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Max")
class Max(Expr):
    """Maximum."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Max", "max")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Eq")
class Eq(Expr):
    """Equality comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Eq", "__eq__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Ne")
class Ne(Expr):
    """Inequality comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Ne", "__ne__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Le")
class Le(Expr):
    """Less-than-or-equal comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Le", "__le__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Ge")
class Ge(Expr):
    """Greater-than-or-equal comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Ge", "__ge__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Gt")
class Gt(Expr):
    """Greater-than comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Gt", "__gt__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Lt")
class Lt(Expr):
    """Less-than comparison."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Lt", "__lt__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.And")
class And(Expr):
    """Logical and."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "And", "__and__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Or")
class Or(Expr):
    """Logical or."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Or", "__or__")

    a: Expr
    b: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, a: ExprLike, b: ExprLike) -> None: ...


@c_class("ffi.std.Not")
class Not(Expr):
    """Logical not."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Not", "__invert__")

    operand: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, operand: ExprLike) -> None: ...


@c_class("ffi.std.Load")
class Load(Expr):
    """Indexed load."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Load", "__load__")

    var: Var
    indices: MutableSequence[Range]
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, var: Var, indices: Sequence[RangeLike]) -> None: ...


@c_class("ffi.std.Cast")
class Cast(Expr):
    """Type cast."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Cast", "__cast__")

    value: Expr
    if TYPE_CHECKING:

        def __init__(self, ty: Ty, value: ExprLike) -> None: ...


@c_class("ffi.std.Call")
class Call(Expr):
    """Function call expression."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Call")

    callee: Any
    args: MutableSequence[Expr]
    attr: Attrs | None = field(default=None)
    if TYPE_CHECKING:

        def __init__(
            self,
            ty: Ty,
            callee: Any,
            args: Sequence[ExprLike],
            attr: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.IfStmt")
class IfStmt(Stmt):
    """If/else statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "IfStmt", "__if__")

    cond: Expr
    then_body: MutableSequence[Stmt]
    else_body: MutableSequence[Stmt]
    if TYPE_CHECKING:

        def __init__(
            self,
            cond: ExprLike,
            then_body: MutableSequence[Stmt],
            else_body: MutableSequence[Stmt],
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.Scope")
class Scope(Stmt):
    """A scoped statement block."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Scope")

    vars: MutableSequence[Bind]
    body: MutableSequence[Stmt]
    if TYPE_CHECKING:

        def __init__(
            self,
            vars: MutableSequence[Bind],
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
            vars: MutableSequence[Bind],
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
            vars: MutableSequence[Bind],
            body: MutableSequence[Stmt],
            cond: ExprLike,
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.Bind", init=False)
class Bind(Stmt):
    """Base variable binding statement."""

    vars: MutableSequence[Var]
    if TYPE_CHECKING:

        def __init__(self, _no_direct_init: Never) -> None: ...


@c_class("ffi.std.BindExpr")
class BindExpr(Bind):
    """Binding that defines variables from an expression."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "BindExpr", "__bind_expr__")

    expr: Expr
    if TYPE_CHECKING:

        def __init__(
            self,
            vars: MutableSequence[Var],
            expr: ExprLike,
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.BindVarDef")
class BindVarDef(Bind):
    """Binding that defines variables without a source expression."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = (
        "std",
        "BindVarDef",
        "__bind_var_def__",
    )

    if TYPE_CHECKING:

        def __init__(
            self,
            vars: MutableSequence[Var],
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.Store")
class Store(Stmt):
    """Indexed store."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Store", "__store__")

    var: Var
    indices: MutableSequence[Range]
    rhs: Expr
    if TYPE_CHECKING:

        def __init__(
            self,
            var: Var,
            indices: Sequence[RangeLike],
            rhs: ExprLike,
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.Assert")
class Assert(Stmt):
    """Assertion statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Assert", "__assert__")

    cond: Expr
    if TYPE_CHECKING:

        def __init__(
            self,
            cond: ExprLike,
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.Return")
class Return(Stmt):
    """Return statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Return", "__return__")

    vars: MutableSequence[Var]
    if TYPE_CHECKING:

        def __init__(
            self,
            vars: MutableSequence[Var],
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.Yield")
class Yield(Stmt):
    """Yield statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Yield", "__yield__")

    vars: MutableSequence[Var]
    if TYPE_CHECKING:

        def __init__(
            self,
            vars: MutableSequence[Var],
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.Break")
class Break(Stmt):
    """Break statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Break", "__break__")
    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.Continue")
class Continue(Stmt):
    """Continue statement."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "Continue", "__continue__")
    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            attrs: AttrsLike = ...,
        ) -> None: ...


@c_class("ffi.std.DictAttrs")
class DictAttrs(Attrs):
    """Dictionary-backed attributes."""

    __ffi_dialect_mnemonic__: ClassVar[DialectMnemonic] = ("std", "DictAttrs")

    values: MutableMapping[str, Any]


__all__ = [
    "Add",
    "And",
    "AnyTy",
    "Assert",
    "Attrs",
    "Bind",
    "BindExpr",
    "BindVarDef",
    "Break",
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
    "PrimTy",
    "Range",
    "Return",
    "Scope",
    "Stmt",
    "Store",
    "StringImm",
    "Structure",
    "Sub",
    "TensorTy",
    "TupleType",
    "Ty",
    "Var",
    "While",
    "Yield",
]
