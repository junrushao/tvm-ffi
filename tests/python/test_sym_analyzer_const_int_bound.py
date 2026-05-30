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

import dataclasses

import pytest
from tvm_ffi import std
from tvm_ffi import std as S
from tvm_ffi.std import (
    ConstIntBound,
    const_int_bound,
    const_int_bound_update,
    enter_constraint,
)
from tvm_ffi.std import truncdiv as tdiv
from tvm_ffi.std import truncmod as tmod

POS_INF = 2**63 - 1
NEG_INF = -POS_INF


def var(name: str, dtype: str = S.DefaultIntegerType) -> S.Var:
    return S.Var(S.PrimTy(dtype), name)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "param" in metafunc.fixturenames:
        if test_cases := getattr(metafunc.cls, "param", None):
            metafunc.parametrize("param", test_cases)


@dataclasses.dataclass
class Param:
    expr: S.Expr
    expected: tuple[int | None, int | None]
    bounds: dict[std.Var, tuple[int, int]] = dataclasses.field(default_factory=dict)
    constraint: S.Expr | None = None

    @property
    def __name__(self) -> str:
        return str(self.expr).replace("\n", "; ")


class _Test:
    def test_body(self, param: Param) -> None:
        analyzer = S.Analyzer()
        for var, bounds in param.bounds.items():
            const_int_bound_update(analyzer, var, ConstIntBound(*bounds))
        with enter_constraint(analyzer, param.constraint):
            actual = const_int_bound(analyzer, param.expr)
        expected_min_value, expected_max_value = param.expected
        if expected_min_value is not None:
            assert actual.min_value == expected_min_value
        if expected_max_value is not None:
            assert actual.max_value == expected_max_value


class TestDataType(_Test):
    param = (
        Param(var("x", dtype="int64"), (NEG_INF, POS_INF)),
        Param(var("x", dtype="int8"), (-128, 127)),
        Param(var("x", dtype="uint8"), (0, 255)),
    )


class TestCastBound(_Test):
    x = var("x", dtype="int8")

    param = (
        Param(tmod(x, 3).astype("uint32"), (0, 2)),
        Param(tmod(x, 3).astype("float32").astype("int32"), (-2, 2)),
    )


class TestAddSubBound(_Test):
    x = var("x", "int64")
    y = var("y", "int64")

    param = (
        Param(x + y, (NEG_INF, POS_INF)),
        Param(x + y, (1, 14), bounds={x: (0, 4), y: (1, 10)}),
        Param(x - y, (-10, 3), bounds={x: (0, 4), y: (1, 10)}),
        Param(x - y, (-10, POS_INF), bounds={x: (0, POS_INF), y: (1, 10)}),
        Param(1 - x, (NEG_INF, 1), bounds={x: (0, POS_INF), y: (1, 10)}),
    )


class TestMulBound(_Test):
    x = var("x", "int64")
    y = var("y", "int64")

    param = (
        Param(x * y + 20, (0, 60), {x: (-2, 4), y: (4, 10)}),
        Param(x * y, (-32, 24), {x: (-3, 4), y: (-8, 2)}),
        Param(x * y, (NEG_INF, POS_INF), {x: (NEG_INF, 4), y: (-8, 2)}),
    )


class TestTruncDivBound(_Test):
    x = var("x")
    y = var("y")

    param = (
        Param(tdiv(x, y), (-2, None), {x: (-9, 4), y: (4, 10)}),
        Param(tdiv(x, y), (-4, 9), {x: (-9, 4), y: (-2, 0)}),
        Param(tdiv(x, y), (NEG_INF, POS_INF), {x: (NEG_INF, 4), y: (-2, 1)}),
        Param(tdiv(x, y), (-9, 9), {x: (-9, 4), y: (-4, 12)}),
    )


class TestTruncModBound(_Test):
    x = var("x")
    y = var("y")

    param = (
        Param(tmod(x, y), (-9, 4), {x: (-9, 4), y: (4, 10)}),
        Param(tmod(x, y), (-9, 9), {x: (NEG_INF, POS_INF), y: (4, 10)}),
        Param(tmod(x, y), (0, 9), {x: (1, POS_INF), y: (4, 10)}),
    )


class TestFloorDivBound(_Test):
    x = var("x", dtype="int32")
    y = var("y", dtype="int32")
    ux = var("x", dtype="uint32")
    uy = var("y", dtype="uint32")

    param = (
        Param(x // y, (-9 // 4, None), {x: (-9, 4), y: (4, 10)}),
        Param(x // y, (-4, 9), {x: (-9, 4), y: (-2, 0)}),
        Param(x // y, (NEG_INF, POS_INF), {x: (NEG_INF, 4), y: (-2, 1)}),
        Param(x // y, (-9, 9), {x: (-9, 4), y: (-4, 12)}),
        Param(ux // uy, (0, 4), {ux: (1, 4), uy: (0, 12)}),
    )


class TestFloorModBound(_Test):
    x = var("x")
    y = var("y")

    param = (
        Param(x % y, (0, 9), {x: (-9, 4), y: (4, 10)}),
        Param(x % y, (0, 9), {x: (NEG_INF, POS_INF), y: (4, 10)}),
        Param(x % y, (0, 9), {x: (1, POS_INF), y: (4, 10)}),
    )


class TestMinMaxBound(_Test):
    x = var("x")
    y = var("y")

    param = (
        Param(S.min(x, y), (-9, 10), {x: (-9, 11), y: (4, 10)}),
        Param(S.min(x, y), (NEG_INF, 10), {x: (NEG_INF, POS_INF), y: (4, 10)}),
        Param(S.max(x, y), (4, POS_INF), {x: (NEG_INF, POS_INF), y: (4, 10)}),
        Param(S.max(x, y), (4, POS_INF), {x: (1, POS_INF), y: (4, 10)}),
    )


class TestSelectBound(_Test):
    x = var("x")
    y = var("y")

    param = (
        Param(
            S.select(x > 1, (y < 0).astype("int32"), y + 1),
            (0, 11),
            {x: (-9, 11), y: (4, 10)},
        ),
    )


class TestShiftAndBound(_Test):
    x = var("x")
    y = var("y")

    param = (
        Param(x >> y, (-3, 2), {x: (-9, 11), y: (2, 10)}),
        Param(x & y, (0, 10), {x: (-9, 11), y: (2, 10)}),
        Param(x & y, (0, 10), {x: (10, 11), y: (2, 10)}),
    )


class TestMixIndexBound(_Test):
    x = var("x")
    y = var("y")

    param = (
        Param(tmod(x, 8) + tdiv(x, 8) * 8, (0, 24 - 1), {x: (0, 24 - 1), y: (0, 3 - 1)}),
        Param(y + x * 3, (0, 24 * 3 - 1), {x: (0, 24 - 1), y: (0, 3 - 1)}),
        Param(tmod(x, 7) + tdiv(x, 7) * 7, (0, (23 // 7) * 7 + 6), {x: (0, 24 - 1), y: (0, 3 - 1)}),
    )


class TestFloorModNegativeDivisor(_Test):
    a = var("a")
    b = var("b")

    param = (Param(a % b, (-4, 6), {a: (0, 6), b: (-5, 7)}),)


class TestDivModAssumeNoZeroDivisor(_Test):
    a = var("a")
    b = var("b")

    param = (
        Param(a // b, (0, 6), {a: (0, 6), b: (0, POS_INF)}),
        Param(a % b, (0, 6), {a: (0, 6), b: (0, POS_INF)}),
    )


class TestMultipleCondition(_Test):
    a = var("a")

    param = (
        Param(
            a % 58 - 1,
            (0, None),
            bounds={a: (0, 128)},
            constraint=S.logical_and(1 <= a % 58, a % 58 < 57),
        ),
    )
