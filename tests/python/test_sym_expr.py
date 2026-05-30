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

from __future__ import annotations

import operator
from collections.abc import Callable

import pytest
from tvm_ffi import std
from tvm_ffi import std as S


def var(name: str, dtype: str = S.DefaultIntegerType) -> S.Var:
    return S.Var(S.PrimTy(dtype), name)


def _dtype(expr: S.Expr) -> str:
    assert isinstance(expr.ty, std.PrimTy)
    return str(expr.ty.dtype)


def test_var() -> None:
    x = var("x", "int64")
    assert isinstance(x, S.Expr)
    assert x.name == "x"
    assert _dtype(x) == "int64"


def test_immediates() -> None:
    i = S.const("int64", -1)
    b = S.const("bool", True)
    f = S.const("float32", 1.0)

    assert isinstance(i, S.IntImm)
    assert i.value == -1
    assert _dtype(i) == "int64"
    assert isinstance(b, S.BoolImm)
    assert b.value is True
    assert _dtype(b) == "bool"
    assert isinstance(f, S.FloatImm)
    assert f.value == 1.0
    assert _dtype(f) == "float32"


@pytest.mark.parametrize(
    "op, cls",
    [
        (operator.add, S.Add),
        (operator.sub, S.Sub),
        (operator.mul, S.Mul),
        (S.truncdiv, S.CDiv),
        (S.truncmod, S.CMod),
        (operator.floordiv, S.FloorDiv),
        (operator.mod, S.FloorMod),
        (S.min, S.Min),
        (S.max, S.Max),
    ],
)
def test_arith_binary(
    op: Callable[[std.Expr, std.Expr], std.Expr],
    cls: type[std.Expr],
) -> None:
    x = var("x", "int64")
    y = var("y", "int64")
    assert isinstance(op(x, y), cls)


@pytest.mark.parametrize(
    "op, cls",
    [
        (S.equal, S.Eq),
        (S.not_equal, S.Ne),
        (S.greater_equal, S.Ge),
        (S.less_equal, S.Le),
        (S.greater, S.Gt),
        (S.less, S.Lt),
    ],
)
def test_cmp(
    op: Callable[[std.Expr, std.Expr], std.Expr],
    cls: type[std.Expr],
) -> None:
    x = var("x", "int64")
    y = var("y", "int64")
    z = op(x, y)
    assert isinstance(z, cls)
    assert _dtype(z) == "bool"


def test_logical() -> None:
    x = var("x", "bool")
    y = var("y", "bool")
    assert isinstance(S.logical_and(x, y), S.And)
    assert isinstance(S.logical_or(x, y), S.Or)
    assert isinstance(S.logical_not(x), S.Not)


def test_select() -> None:
    cond = var("cond", "bool")
    true_value = var("true_value", "int64")
    false_value = var("false_value", "int64")
    z = S.select(cond, true_value, false_value)
    assert isinstance(z, S.IfExpr)
    assert _dtype(z) == "int64"


def test_range() -> None:
    extent = var("extent", "int64")
    r = S.Range(S.const("int64", 0), extent)
    assert r.start is not None
    assert _dtype(r.start) == "int64"
    assert r.extent.same_as(extent)
