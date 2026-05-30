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

import contextlib
import dataclasses

import pytest
from tvm_ffi import std
from tvm_ffi import std as S
from tvm_ffi.std import (
    ConstIntBound,
    const_int_bound_update,
    enter_constraint,
    modular_set,
)
from tvm_ffi.std import truncdiv as tdiv
from tvm_ffi.std import truncmod as tmod


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
    known_bounds: dict[std.Var, tuple[int, int] | S.Expr] = dataclasses.field(default_factory=dict)
    constraints: list[S.Expr | bool] = dataclasses.field(default_factory=list)

    @property
    def __name__(self) -> str:
        return str(self.expr).replace("\n", "; ")


class _Test:
    def test_body(self, param: Param) -> None:
        analyzer = S.Analyzer()
        for var, bounds in param.known_bounds.items():
            if isinstance(bounds, S.Expr):
                analyzer.bind(var, bounds)
            else:
                const_int_bound_update(analyzer, var, ConstIntBound(*bounds))
        with contextlib.ExitStack() as exit_stack:
            for constraint in param.constraints:
                assert isinstance(constraint, S.Expr)
                exit_stack.enter_context(enter_constraint(analyzer, constraint))
            actual = modular_set(analyzer, param.expr)
        expected_coeff, expected_base = param.expected
        if expected_coeff is not None:
            assert actual.coeff == expected_coeff
        if expected_base is not None:
            assert actual.base == expected_base


class TestCast(_Test):
    x = var("x", dtype="int8")

    param = (
        Param((x * 3).astype("uint32"), (3, 0)),
        Param((x * 3 + 1).astype("float32").astype("int32"), (3, 1)),
    )


class TestAddSub(_Test):
    x = var("x", "int64")
    y = var("y", "int64")

    param = (
        Param(x * 6 + y * 4, (2, 0)),
        Param(1 - y, (4, 0), known_bounds={y: x * 4 + 1}),
    )


class TestMul(_Test):
    x = var("x")
    y = var("y")

    param = (Param((x * 4 + 2) * (y * 6 + 1), (4, 2)),)


class TestFloorMod(_Test):
    x = var("x")
    y = var("y")

    param = (Param((x * 128 + y * 4) % 256, (4, 0)),)


class TestDivShift(_Test):
    x = var("x")

    param = (
        Param(tdiv(x * 4 + 2, 2), (1, 0)),
        # right shift always round down so it is fine
        Param((x * 4 + 2) >> 1, (2, 1)),
        Param((x * 4 + 2) // 2, (2, 1)),
        # x is non-negative
        Param(tdiv(x * 4 + 2, 2), (2, 1), known_bounds={x: (0, 100)}),
    )


class TestMod(_Test):
    x = var("x")

    param = (
        # not sure if x is non-negative
        Param(tmod(x * 4 + 1, 4), (1, 0)),
        # no need to be positive if base == 0
        Param(tmod(x * 4, 4), (4, 0)),
        # floor mod tests
        Param((x * 4 + 3) % 2, (2, 1)),
        Param((x * 4 + 3) % 8, (4, 3)),
        # x is non-negative
        Param(tmod(x * 4 + 3, 2), (2, 1), known_bounds={x: (0, 100)}),
    )


class TestMinMaxSelect(_Test):
    x = var("x")
    y = var("y")

    param = (
        Param(S.min(x * 3, y * 9), (3, 0)),
        Param(S.max(x * 3 + 1, y * 9 + 4), (3, 1)),
        Param(S.select(x > 0, x * 3 + 1, y * 9 + 2), (1, 0)),
    )


class TestMixIndex(_Test):
    x = var("x")
    y = var("y")

    param = (
        Param(x * 4 + y * 6 + 7, (2, 1)),
        Param((x * 4 + 1) * (y * 8 + 3), (4, 3)),
        Param(tdiv(x * 4 + 1, y * 8 + 3), (1, 0)),
        Param((x * 4 + 1) * tdiv(y * 8, 4), (2, 0)),
        Param(x * 12 + S.min(y * 3 * 7, 2), (1, 0)),
    )


class TestBitwiseAnd(_Test):
    x = var("x")
    y = var("y")

    param = (
        Param((x * 16 + y * 4) & 31, (4, 0)),
        Param((x * 16 + y * 4) & 17, (1, 0)),
    )


class TestConstraintScope(_Test):
    a = var("a")
    b = var("b")

    param = (
        Param(
            b + a * 2,
            (4, 0),
            constraints=[
                tmod(b, 4) == 2,
                tmod(a, 2) == 1,
            ],
        ),
        Param(
            b + a * 2,
            (2, 0),
            constraints=[
                tmod(b, 4) == 2,
            ],
        ),
        Param(b + 1, (1, 0)),
    )


class TestIntersect(_Test):
    a = var("x")
    b = var("y")

    param = (
        Param(
            a,
            (12, 1),
            constraints=[
                tmod(a, 4) == 1,
                tmod(a, 3) == 1,
            ],
        ),
        Param(
            a,
            (105, 23),
            constraints=[
                tmod(a, 3) == 2,
                tmod(a, 5) == 3,
                tmod(a, 7) == 2,
            ],
        ),
    )
