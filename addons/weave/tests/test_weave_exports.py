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
"""Public export and parser namespace tests for Weave."""

from __future__ import annotations

from typing import get_origin

import pytest
import tvm_ffi
import weave
import weave.ir as wi
from tvm_ffi import std
from tvm_ffi._pyast_parser import parse
from tvm_ffi.dataclasses import fields
from weave.ir import config, dtypes, functors, handles, kernel, ops, task
from weave.ir.ops import atomic, barriers, clc, elementwise, memory, mma

OP_EXPORTS = {
    memory: {
        "BuiltinVar",
        "GmemLoad",
        "GmemStore",
        "MetadataCopy",
        "ScaleFactorCopy",
        "SmemDesc",
        "SmemLoad",
        "SmemLoadRegs",
        "SmemLoadVec",
        "SmemRead",
        "SmemStore",
        "SmemStoreVec",
        "SmemWrite",
        "TmaGatherLoad",
        "TmaReduceOp",
        "TmaStore",
        "TmemRegionLoad",
        "TmemRegionStore",
    },
    elementwise: {
        "BitmaskFill",
        "Elementwise",
        "MaskFill",
        "PredicatedStore",
        "RegArrayCast",
        "ThreshMask",
    },
    barriers: {
        "BarrierSignal",
        "BarrierSync",
        "BarrierTryWait",
        "BarrierWait",
        "BlockReduce",
        "ClusterBarrierArrive",
        "ClusterMapa",
        "ClusterSync",
        "CpAsyncBulkSmem2SmemCluster",
        "CrossWarpReduce",
        "DualCommit",
        "Fence",
        "GridDepLaunch",
        "GridDepSync",
        "GridSync",
        "MBarrierArrive",
        "MulticastCommit",
        "PeerArriveCommit",
        "StAsync",
        "ThreadFence",
        "WarpGroupReduce",
        "WarpReduce",
    },
    mma: {"FragmentOp", "MmaTile", "PackedF32x2", "Tcgen05Cp"},
    atomic: {
        "AtomicFetchAdd",
        "AtomicMaxF32Positive",
        "AtomicMaxFloatDecode",
        "AtomicMaxFloatEncode",
        "AtomicOp",
        "MultimemLdReduce",
        "MultimemRedAddI32",
        "MultimemStore",
        "RelaxedFmax",
        "SysVolatileLoad128",
        "SysVolatileStore128",
    },
    clc: {"ClcFenceRelease", "ClcQueryCancel", "ClcQueryCancelGetCtaId", "ClcTryCancel"},
}

IR_MODULES = (config, dtypes, functors, handles, kernel, ops, task)


@pytest.mark.parametrize("module, expected", OP_EXPORTS.items())
def test_op_module_exports_are_intentional(module: object, expected: set[str]) -> None:
    assert set(module.__all__) == expected
    assert not any(name.startswith("_") for name in module.__all__)


def test_weave_ir_does_not_export_imported_typing_or_helper_names() -> None:
    for leaked_name in ("Any", "ClassVar", "Op", "std", "dc", "normalize_expr"):
        assert leaked_name not in wi.__all__, leaked_name
        assert leaked_name not in weave.__all__, leaked_name
    assert not any(name.startswith("_") for name in wi.__all__)
    assert set(weave.__all__) == set(wi.__all__)


def test_weave_ir_public_exports_match_declared_module_surfaces() -> None:
    expected = [name for module in IR_MODULES for name in module.__all__]

    assert wi.__all__ == expected
    assert len(wi.__all__) == len(set(wi.__all__))
    for module in IR_MODULES:
        for name in module.__all__:
            assert getattr(wi, name) is getattr(module, name), name


def test_weave_top_level_reexports_public_ir_names() -> None:
    for name in wi.__all__:
        assert getattr(weave, name) is getattr(wi, name)


def test_public_op_exports_are_reachable_from_weave_ir() -> None:
    for module, names in OP_EXPORTS.items():
        for name in names:
            assert getattr(wi, name) is getattr(module, name), name
            assert getattr(weave, name) is getattr(module, name), name


@pytest.mark.parametrize(
    "source, expected",
    [
        pytest.param(
            'weave.Pipeline("main", 2, style="sw_pipelined")',
            wi.PipelineSpec("main", 2, style="sw_pipelined"),
            id="pipeline-mnemonic",
        ),
        pytest.param(
            'weave.Mbarrier("full", 2, signaling_mode="hw_commit")',
            wi.MbarrierSpec("full", 2, signaling_mode="hw_commit"),
            id="mbarrier-mnemonic",
        ),
        pytest.param(
            'weave.Buffer("A", std.f32, shape=[16, 16], space="gmem")',
            wi.BufferRef("A", wi.f32, (16, 16), space="gmem"),
            id="buffer-mnemonic",
        ),
        pytest.param(
            'weave.Param("m", "int")',
            wi.ScalarParam("m", "int"),
            id="param-mnemonic",
        ),
        pytest.param(
            'weave.lm.ptr(weave.lm.f32, const=True, space="global")',
            wi.PtrTy(wi.f32, const=True, space="global"),
            id="lm-pointer-helper",
        ),
        pytest.param(
            "weave.lm.uniform(std.i32)",
            wi.UniformTy(wi.i32),
            id="lm-uniform-helper",
        ),
        pytest.param("weave.lm.raw", wi.RawTy(), id="lm-raw"),
        pytest.param("weave.lm.ue4m3", wi.Ue4m3Ty(), id="lm-ue4m3"),
        pytest.param("weave.lm.constexpr", wi.ConstexprTy(), id="lm-constexpr"),
        pytest.param("weave.lm.tma2d", wi.TmaTy(2), id="lm-tma2d"),
        pytest.param("weave.lm.tma3d", wi.TmaTy(3), id="lm-tma3d"),
        pytest.param("weave.lm.tma4d", wi.TmaTy(4), id="lm-tma4d"),
        pytest.param("weave.lm.tma5d", wi.TmaTy(5), id="lm-tma5d"),
        pytest.param("weave.lm.tma_gather", wi.TmaGatherTy(), id="lm-tma-gather"),
        pytest.param("weave.lm.tma_reduce", wi.TmaReduceTy(), id="lm-tma-reduce"),
        pytest.param("weave.lm.grid_counter", wi.GridCounterTy(), id="lm-grid-counter"),
        pytest.param("weave.lm.f8_e4m3", wi.f8_e4m3, id="lm-f8-e4m3"),
        pytest.param("weave.lm.f8_e5m2", wi.f8_e5m2, id="lm-f8-e5m2"),
        pytest.param("weave.lm.f8_e8m0fnu", wi.f8_e8m0fnu, id="lm-f8-e8m0"),
        pytest.param("weave.lm.f4_e2m1fn", wi.f4_e2m1fn, id="lm-f4-e2m1"),
        pytest.param("weave.lm.f32x2", wi.f32x2, id="lm-f32x2"),
        pytest.param("weave.lm.bf16x2", wi.bf16x2, id="lm-bf16x2"),
    ],
)
def test_parser_namespace_aliases_roundtrip(source: str, expected: object) -> None:
    parsed = parse(source)

    assert tvm_ffi.structural_equal(parsed, expected)


def _is_expr_annotation(annotation: object) -> bool:
    if get_origin(annotation) is list:
        return False
    if annotation is std.Expr:
        return True
    return std.Expr in getattr(annotation, "__args__", ())


def test_expr_typed_op_fields_are_declared_for_normalization() -> None:
    for module in OP_EXPORTS:
        for name in module.__all__:
            cls = getattr(module, name)
            expr_fields = {
                field.name
                for field in fields(cls)
                if _is_expr_annotation(getattr(field, "type", None))
            }
            assert expr_fields <= cls.EXPR_FIELDS, f"{name}: {expr_fields - cls.EXPR_FIELDS}"
