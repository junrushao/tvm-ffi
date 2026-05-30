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
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

import pytest
import tvm_ffi
from tvm_ffi import std
from tvm_ffi import std as S


def var(name: str, dtype: str = S.DefaultIntegerType) -> S.Var:
    return S.Var(S.PrimTy(dtype), name)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "param" in metafunc.fixturenames:
        if test_cases := getattr(metafunc.cls, "param", None):
            metafunc.parametrize("param", test_cases)


@pytest.fixture
def analyzer() -> S.Analyzer:
    return S.Analyzer()


def test_index_flatten(analyzer: S.Analyzer) -> None:
    i0 = var("i0", "int64")
    i1 = var("i1", "int64")
    analyzer.bind(i0, S.Range(S.const("int64", 0), S.const("int64", 8)))
    analyzer.bind(i1, S.Range(S.const("int64", 0), S.const("int64", 3)))

    i_flattened = i0 * 3 + i1
    before = (i_flattened) // 12 * 12 + (i_flattened) % 12 // 4 * 4 + (i_flattened) % 4
    expected_after = i_flattened
    after = analyzer.simplify(before)
    assert tvm_ffi.structural_equal(expected_after, after)


@pytest.mark.parametrize(
    "dtype",
    (
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "int8",
        "int16",
        "int32",
        "int64",
        "float16",
        "float32",
        "float64",
    ),
)
def test_can_prove_self_identity(analyzer: S.Analyzer, dtype: str) -> None:
    n = var("n", dtype)
    assert analyzer.can_prove(S.equal(n, n))
    assert analyzer.can_prove_equal(n, n)


class TestSymbolicCompare:
    @dataclasses.dataclass
    class Param:
        """Input case for symbolic comparison checks."""

        expr: S.Expr
        expected: bool = True
        strength: Literal["default", "symbolic_bound"] = "symbolic_bound"
        bounds: Mapping[std.Var, std.Range] = dataclasses.field(default_factory=dict)

    i0 = var("i0", "int64")
    i1 = var("i1", "int64")
    n = var("n", "int64")
    m = var("m", "int64")
    bounds = MappingProxyType(
        {
            i0: S.Range(S.const("int64", 0), (n + 31) // 32),
            i1: S.Range(S.const("int64", 0), S.const("int64", 32)),
        }
    )

    param = (
        Param(
            i0 * 32 + i1 < (n + 31) // 32 * 32,
            strength="default",
            expected=False,
            bounds=bounds,
        ),
        Param(i0 * 32 + i1 < (n + 31) // 32 * 32, bounds=bounds),
        Param(i0 * 32 + i1 < (n + 31) // 32 * 32 + m, bounds=bounds),
        Param(i0 * 32 + i1 + 1 <= (n + 31) // 32 * 32, bounds=bounds),
        Param((n + 31) // 32 * 32 >= i0 * 32 + i1 + 1, bounds=bounds),
        Param((n + 31) // 32 * 32 >= i0 * 32 + i1, bounds=bounds),
    )

    @staticmethod
    def test_body(analyzer: S.Analyzer, param: Param) -> None:
        analyzer.mark_global_non_neg_value(TestSymbolicCompare.n)
        analyzer.mark_global_non_neg_value(TestSymbolicCompare.m)
        if param.bounds:
            for var, bound in param.bounds.items():
                analyzer.bind(var, bound)
        assert analyzer.can_prove(param.expr, strength=param.strength) == param.expected
