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
# ruff: noqa: D100, D101

from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any, TypeVar

import tvm_ffi as ffi
from tvm_ffi import dataclasses as dc

############## Basic components ##############


@dc.py_class("ffi.std.Node")
class Node(dc.Object):
    def text(self) -> str:
        """Get the text representation of this IR node."""
        from .pyast import to_python  # noqa: PLC0415

        return to_python(self)


@dc.py_class("ffi.std.Ty")
class Ty(Node):
    pass


@dc.py_class("ffi.std.Stmt")
class Stmt(Node):
    pass


@dc.py_class("ffi.std.Attrs")
class Attrs(Node):
    @staticmethod
    def __ffi_convert__(src: Any) -> Attrs:
        if src is None:
            return DictAttrs(values={})
        if isinstance(src, Mapping):
            return DictAttrs(values=src)
        raise TypeError(f"Unsupported type for conversion to Attrs: {type(src)}")


@dc.py_class("ffi.std.Expr")
class Expr(Node):
    ty: Ty

    @staticmethod
    def __ffi_convert__(src: Any) -> Expr:
        if isinstance(src, int):
            return IntImm(value=src, ty=AnyTy())
        if isinstance(src, float):
            return FloatImm(value=src, ty=AnyTy())
        raise TypeError(f"Unsupported type for conversion to Expr: {type(src)}")

    @staticmethod
    def _make(value: Number, ty: Ty | None = None) -> Expr:
        if ty is None:
            ty = AnyTy()
        if isinstance(value, int):
            return IntImm(value=value, ty=ty)
        if isinstance(value, float):
            return FloatImm(value=value, ty=ty)
        raise TypeError(f"Unsupported type for conversion to Expr: {type(value)}")


@dc.py_class("ffi.std.Value")
class Value(Expr):
    name: str


@dc.py_class("ffi.std.Func")
class Func(Stmt):
    symbol: str
    attrs: Attrs | None
    args: list[Value] = dc.field(structural_eq="def")
    body: list[Stmt]
    ret_type: Ty | None


@dc.py_class("ffi.std.Module")
class Module(Node):
    funcs: list[Func]


@dc.py_class("ffi.std.Range")
class Range(Node):
    start: Expr
    stop: Expr | None  # None means single point [start, start]
    step: Expr | None  # None means 1

    def __ffi_convert__(src: Any) -> Range:
        if isinstance(src, Number):
            return Range(Expr.__ffi_convert__(src), None, None)
        if isinstance(src, Expr):
            return Range(src, None, None)
        raise TypeError(f"Unsupported type for conversion to Range: {type(src)}")


############## Types ##############


@dc.py_class("ffi.std.AnyTy")
class AnyTy(Ty):
    pass


@dc.py_class("ffi.std.PrimTy")
class PrimTy(Ty):
    dtype: ffi.dtype


@dc.py_class("ffi.std.TupleType")
class TupleType(Ty):
    fields: list[Ty]


@dc.py_class("ffi.std.TensorTy")
class TensorTy(Ty):
    shape: list[Expr]
    dtype: ffi.dtype


############## Expressions ##############


@dc.py_class("ffi.std.IntImm")
class IntImm(Expr):
    value: int


@dc.py_class("ffi.std.FloatImm")
class FloatImm(Expr):
    value: float


@dc.py_class("ffi.std.StringImm")
class StringImm(Expr):
    value: str


@dc.py_class("ffi.std.Add")
class Add(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Add:  # ty: ignore[invalid-method-override]
        return _normalize_binary_arith(Add, a, b)


@dc.py_class("ffi.std.Sub")
class Sub(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Sub:  # ty: ignore[invalid-method-override]
        return _normalize_binary_arith(Sub, a, b)


@dc.py_class("ffi.std.Mul")
class Mul(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Mul:  # ty: ignore[invalid-method-override]
        return _normalize_binary_arith(Mul, a, b)


@dc.py_class("ffi.std.FloorDiv")
class FloorDiv(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> FloorDiv:  # ty: ignore[invalid-method-override]
        return _normalize_binary_arith(FloorDiv, a, b)


@dc.py_class("ffi.std.FloorMod")
class FloorMod(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> FloorMod:  # ty: ignore[invalid-method-override]
        return _normalize_binary_arith(FloorMod, a, b)


@dc.py_class("ffi.std.Min")
class Min(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Min:  # ty: ignore[invalid-method-override]
        return _normalize_binary_arith(Min, a, b)


@dc.py_class("ffi.std.Max")
class Max(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Max:  # ty: ignore[invalid-method-override]
        return _normalize_binary_arith(Max, a, b)


@dc.py_class("ffi.std.Eq")
class Eq(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Eq:  # ty: ignore[invalid-method-override]
        return _normalize_binary_cmp(Eq, a, b)


@dc.py_class("ffi.std.Ne")
class Ne(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Ne:  # ty: ignore[invalid-method-override]
        return _normalize_binary_cmp(Ne, a, b)


@dc.py_class("ffi.std.Le")
class Le(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Le:  # ty: ignore[invalid-method-override]
        return _normalize_binary_cmp(Le, a, b)


@dc.py_class("ffi.std.Ge")
class Ge(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Ge:  # ty: ignore[invalid-method-override]
        return _normalize_binary_cmp(Ge, a, b)


@dc.py_class("ffi.std.Gt")
class Gt(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Gt:  # ty: ignore[invalid-method-override]
        return _normalize_binary_cmp(Gt, a, b)


@dc.py_class("ffi.std.Lt")
class Lt(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Lt:  # ty: ignore[invalid-method-override]
        return _normalize_binary_cmp(Lt, a, b)


@dc.py_class("ffi.std.And")
class And(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> And:  # ty: ignore[invalid-method-override]
        return _normalize_binary_arith(And, a, b)


@dc.py_class("ffi.std.Or")
class Or(Expr):
    a: Expr
    b: Expr

    @staticmethod
    def _make(a: Expr | Number, b: Expr | Number) -> Or:  # ty: ignore[invalid-method-override]
        return _normalize_binary_arith(Or, a, b)


@dc.py_class("ffi.std.Not")
class Not(Expr):
    operand: Expr

    @staticmethod
    def _make(operand: Expr | Number) -> Not:  # ty: ignore[invalid-method-override]
        if isinstance(operand, Number):
            operand = Expr.__ffi_convert__(operand)
        return Not(ty=PrimTy(dtype=ffi.dtype("bool")), operand=operand)


@dc.py_class("ffi.std.Load")
class Load(Expr):
    value: Value
    indices: list[Range]


@dc.py_class("ffi.std.Cast")
class Cast(Expr):
    value: Expr

    @staticmethod
    def _make(dtype: str, value: Expr) -> Cast:  # ty: ignore[invalid-method-override]
        return Cast(
            ty=PrimTy(dtype=ffi.dtype(dtype)),
            value=value,
        )


@dc.py_class("ffi.std.CallExpr")
class CallExpr(Expr):
    callee: Any  # TODO: be more specific on its typing
    args: list[Expr]


############## Region-bearing Statements ##############


@dc.py_class("ffi.std.IfStmt")
class IfStmt(Stmt):
    cond: Expr
    then_body: list[Stmt]
    else_body: list[Stmt]


@dc.py_class("ffi.std.For")
class For(Stmt):
    range_: Range
    attrs: Attrs | None
    carry_inits: list[Expr]
    values: list[Value] | None  # def sites of the loop-carried variables
    body: list[Stmt]


@dc.py_class("ffi.std.While")
class While(Stmt):
    cond: Expr
    attrs: Attrs | None
    carry_inits: list[Expr]
    values: list[Value] | None  # def sites of the loop-carried variables
    body: list[Stmt]


class Scope(Stmt):
    carry_inits: list[Expr]
    values: list[Value] | None  # def sites of the variables defined in the
    body: list[Stmt]


############## Sequential Statements ##############


@dc.py_class("ffi.std.Binding")
class Binding(Stmt):
    expr: Expr | None = None
    attrs: Attrs | None = None


@dc.py_class("ffi.std.NullBinding")
class NullBinding(Binding):
    pass


@dc.py_class("ffi.std.SingleBinding")
class SingleBinding(Binding):
    value: Value  # def sites of the assigned variables


@dc.py_class("ffi.std.TupleBinding")
class TupleBinding(Binding):
    values: list[Value]  # def sites of the assigned variables


@dc.py_class("ffi.std.Store")
class Store(Stmt):
    value: Value
    indices: list[Range]
    rhs: Expr


############## Jumping Statements ##############


@dc.py_class("ffi.std.Return")
class Return(Stmt):
    values: list[Value]


@dc.py_class("ffi.std.Yield")
class Yield(Stmt):
    values: list[Value]


@dc.py_class("ffi.std.Break")
class Break(Stmt):
    pass


@dc.py_class("ffi.std.Continue")
class Continue(Stmt):
    pass


########### Attributes ###########


@dc.py_class("ffi.std.DictAttrs")
class DictAttrs(Attrs):
    values: dict[str, Any]


_ExprT = TypeVar("_ExprT", bound=Expr)


def _normalize_binary_arith(op: type[_ExprT], a: Expr | Number, b: Expr | Number) -> _ExprT:
    if isinstance(a, Number):
        a = Expr.__ffi_convert__(a)
    if isinstance(b, Number):
        b = Expr.__ffi_convert__(b)
    ty = a.ty if isinstance(b.ty, AnyTy) else b.ty
    return op(ty=ty, a=a, b=b)  # ty: ignore[unknown-argument]


def _normalize_binary_cmp(op: type[_ExprT], a: Expr | Number, b: Expr | Number) -> _ExprT:
    if isinstance(a, Number):
        a = Expr.__ffi_convert__(a)
    if isinstance(b, Number):
        b = Expr.__ffi_convert__(b)
    ty = PrimTy(dtype=ffi.dtype("bool"))
    return op(ty=ty, a=a, b=b)  # ty: ignore[unknown-argument]
