# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Focused validation tests for Weave IR constructors."""

# ruff: noqa: F405

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import tvm_ffi
import weave  # noqa: F401
from tvm_ffi import std
from weave.ir import *


def _var(name: str = "v", ty: std.Ty | None = None) -> std.Var:
    return std.Var(ty or i32, name)


def _string_imm(value: str) -> std.StringImm:
    return std.StringImm.from_py(value)


def test_expr_fields_reject_raw_strings() -> None:
    with pytest.raises(TypeError):
        SmemStore("src", 1)
    with pytest.raises(TypeError):
        Elementwise(op="add", inputs=["a", 1])


def test_domain_fields_are_validated() -> None:
    with pytest.raises(ValueError):
        BarrierSignal(MbarrierSpec("full", 1), "bad", 0)
    with pytest.raises(ValueError):
        AtomicOp("bad", 1, 2, space="gmem", dtype=i32)
    with pytest.raises(ValueError):
        Tcgen05Cp(1, 2, shape="bad")


def test_dtype_fields_reject_raw_strings() -> None:
    with pytest.raises(TypeError):
        GmemLoad(1, 2, count=1, dtype="f32", dst_dtype=i32)


@pytest.mark.parametrize(
    "ctor",
    [
        pytest.param(lambda: TmemRegion("acc", 0, 16, dtype="f32"), id="tmem-region"),
        pytest.param(lambda: BufferRef("A", "f32", (16,)), id="buffer-ref"),
        pytest.param(lambda: SmemView("tile", "pool", 0, (16,), "f32"), id="smem-view"),
        pytest.param(lambda: PhaseVar("phase", dtype="int32"), id="phase-var"),
        pytest.param(lambda: MmaParams(1, 1, 0, dtype="f32"), id="mma-params"),
        pytest.param(lambda: SymmetricMemory("sym", "f32", (16,), "pg"), id="symmetric-memory"),
        pytest.param(lambda: AtomicOp("add", 1, 2, space="gmem", dtype="f32"), id="atomic-op"),
        pytest.param(lambda: AtomicFetchAdd(1, 2, 3, dtype="f32"), id="atomic-fetch-add"),
        pytest.param(
            lambda: GmemStore(1, 2, count=1, dtype="f32", src_dtype=i32),
            id="gmem-store-dtype",
        ),
        pytest.param(
            lambda: GmemStore(1, 2, count=1, dtype=i32, src_dtype="f32"),
            id="gmem-store-src-dtype",
        ),
        pytest.param(
            lambda: TmemRegionStore(TmemRegion("acc", 0, 16), dtype="f32"),
            id="tmem-store",
        ),
        pytest.param(lambda: SmemLoadRegs("regs", 1, dtype="f32"), id="smem-load-regs"),
        pytest.param(lambda: RegArrayCast(1, 2, src_dtype="f32", dst_dtype=i32), id="reg-cast-src"),
        pytest.param(lambda: RegArrayCast(1, 2, src_dtype=i32, dst_dtype="f32"), id="reg-cast-dst"),
        pytest.param(lambda: FragmentOp("add", 1, dtype="f32"), id="fragment-op"),
        pytest.param(lambda: MmaTile(1, 2, 3, k_idx=4, a_dtype="f32"), id="mma-tile"),
    ],
)
def test_dtype_fields_reject_raw_strings_across_weave(ctor: Callable[[], Any]) -> None:
    with pytest.raises(TypeError):
        ctor()


def test_op_dtype_fields_normalize_factory_values() -> None:
    class DTypeProxy:
        def to_dialect(self) -> std.Ty:
            return i32

    load = GmemLoad(1, 2, count=1, dtype=DTypeProxy(), dst_dtype=DTypeProxy())
    store = GmemStore(1, 2, count=1, dtype=DTypeProxy(), src_dtype=DTypeProxy())
    atom = AtomicOp("add", 1, 2, space="gmem", dtype=DTypeProxy())
    cast = RegArrayCast(1, 2, src_dtype=DTypeProxy(), dst_dtype=DTypeProxy())

    for value in (load.dtype, load.dst_dtype, store.dtype, store.src_dtype, atom.dtype):
        assert tvm_ffi.structural_equal(value, i32)
    assert tvm_ffi.structural_equal(cast.src_dtype, i32)
    assert tvm_ffi.structural_equal(cast.dst_dtype, i32)


def test_handle_dtype_fields_normalize_factory_values() -> None:
    class DTypeProxy:
        def to_dialect(self) -> std.Ty:
            return i32

    values = [
        TmemRegion("acc", 0, 16, dtype=DTypeProxy()).dtype,
        BufferRef("A", DTypeProxy(), (16,)).dtype,
        SmemView("tile", "pool", 0, (16,), DTypeProxy()).dtype,
        PhaseVar("phase", dtype=DTypeProxy()).dtype,
        MmaParams(1, 1, 0, dtype=DTypeProxy()).dtype,
        SymmetricMemory("sym", DTypeProxy(), (16,), "pg").dtype,
        TmemRegionStore(TmemRegion("acc", 0, 16), dtype=DTypeProxy()).dtype,
    ]

    for value in values:
        assert tvm_ffi.structural_equal(value, i32)


def test_string_like_narrowed_fields_accept_string_imm_values() -> None:
    swizzle = _string_imm("128B")
    pool = _string_imm("pool")
    role = _string_imm("role")

    TmaDescriptor(2, (16, 16), swizzle=swizzle)
    BufferRef("A", i32, (16,), swizzle=swizzle)
    SmemView("tile", pool, 0, (16,), i32, swizzle=swizzle)
    TaskSpec("task", "producer", role, outputs=(_string_imm("out"),))
    TmemRegionLoad(_string_imm("acc"))
    SmemDesc(_string_imm("tile"))


def test_structured_barrier_refs_reject_raw_strings() -> None:
    with pytest.raises(TypeError):
        BarrierSignal("full", "arrive", Const("stage", i32))
    with pytest.raises(TypeError):
        BarrierSignal(std.StringImm.from_py("full"), "arrive", Const("stage", i32))
    with pytest.raises(TypeError):
        BarrierWait("full", Const("stage", i32), Const("phase", i32))
    with pytest.raises(TypeError):
        BarrierTryWait("full", Const("stage", i32), Const("phase", i32), _var("tok"))
    with pytest.raises(TypeError):
        PeerArriveCommit(std.StringImm.from_py("full"), 0)
    with pytest.raises(TypeError):
        CpAsyncBulkSmem2SmemCluster(1, 2, 16, barrier=std.StringImm.from_py("full"))
    with pytest.raises(TypeError):
        PeerArriveCommit("full", 0)
    with pytest.raises(TypeError):
        MulticastCommit("full", 0, 1)
    with pytest.raises(TypeError):
        DualCommit("full", MbarrierSpec("full", 1), 0, 1)
    with pytest.raises(TypeError):
        DualCommit(MbarrierSpec("full", 1), "full", 0, 1)
    with pytest.raises(TypeError):
        CpAsyncBulkSmem2SmemCluster(1, 2, 16, barrier="full")


@pytest.mark.parametrize(
    "ctor",
    [
        pytest.param(lambda: PipelineSpec("p", 1, style="bad"), id="pipeline-style"),
        pytest.param(lambda: PipelineSpec("p", 0), id="pipeline-stages"),
        pytest.param(lambda: PipelineSpec("p", 1, cta_group=3), id="pipeline-cta-group"),
        pytest.param(lambda: PipelineSpec("p", 1, cta_group=True), id="pipeline-cta-group-bool"),
        pytest.param(lambda: PipelineConfig(style="bad"), id="pipeline-config-style"),
        pytest.param(lambda: PipelineConfig(num_stages=0), id="pipeline-config-stages"),
        pytest.param(lambda: GridConfig(cta_group=3), id="grid-cta-group"),
        pytest.param(lambda: GridConfig(cta_group=True), id="grid-cta-group-bool"),
        pytest.param(lambda: TmemConfig(buffering="triple"), id="tmem-buffering"),
        pytest.param(lambda: EpilogueConfig("bad"), id="epilogue-style"),
        pytest.param(lambda: MbarrierSpec("full", 1, signaling_mode="bad"), id="mbarrier-mode"),
        pytest.param(lambda: BufferRef("A", i32, (1,), space="bad"), id="buffer-space"),
        pytest.param(lambda: SmemDesc("tile", mode="bad"), id="smem-desc-mode"),
        pytest.param(
            lambda: GmemStore(1, 2, count=1, dtype=i32, src_dtype=i32, cache_hint="bad"),
            id="gmem-cache-hint",
        ),
        pytest.param(lambda: TmaReduceOp(1, 2, op="bad"), id="tma-reduce-op"),
        pytest.param(lambda: Fence(kind="bad"), id="fence-kind"),
        pytest.param(lambda: ThreadFence(scope="bad"), id="thread-fence-scope"),
        pytest.param(lambda: WarpReduce(1, op="bad"), id="warp-reduce-op"),
        pytest.param(lambda: BlockReduce(1, 2, op="bad"), id="block-reduce-op"),
        pytest.param(
            lambda: CrossWarpReduce(1, 2, _var("cw", f32), finalize="bad"),
            id="cross-finalize",
        ),
        pytest.param(
            lambda: WarpGroupReduce(1, 2, _var("wg", f32), op="bad"),
            id="warpg-reduce-op",
        ),
        pytest.param(lambda: PackedF32x2("bad"), id="packed-f32x2-op"),
        pytest.param(lambda: FragmentOp("bad", 1), id="fragment-op-domain"),
        pytest.param(lambda: AtomicOp("bad", 1, 2, space="gmem", dtype=i32), id="atomic-op-domain"),
        pytest.param(lambda: AtomicOp("add", 1, 2, space="bad", dtype=i32), id="atomic-space"),
        pytest.param(lambda: RelaxedFmax(1, 2, space="bad"), id="relaxed-fmax-space"),
        pytest.param(lambda: MultimemLdReduce(1, 2, payload="bad"), id="multimem-load-payload"),
        pytest.param(lambda: MultimemStore(1, 2, payload="bf16x8"), id="multimem-store-payload"),
        pytest.param(lambda: MultimemRedAddI32(1, 2, sem="bad"), id="multimem-sem"),
        pytest.param(lambda: MultimemRedAddI32(1, 2, scope="bad"), id="multimem-scope"),
        pytest.param(lambda: ClcQueryCancelGetCtaId(1, 2, dim="bad"), id="clc-dim"),
        pytest.param(lambda: BarrierSignal(MbarrierSpec("full", 1), "bad", 0), id="barrier-action"),
        pytest.param(lambda: Tcgen05Cp(1, 2, shape="bad"), id="tcgen-shape"),
        pytest.param(lambda: MmaTile(1, 2, 3, k_idx=4, mode="bad"), id="mma-tile-mode"),
    ],
)
def test_domain_validators_reject_unknown_values(ctor: Callable[[], Any]) -> None:
    with pytest.raises((TypeError, ValueError)):
        ctor()


@pytest.mark.parametrize(
    "ctor",
    [
        pytest.param(lambda: TmaTy(0), id="tma-ty-ndim"),
        pytest.param(lambda: Swizzle(-1, 0, 0), id="swizzle-base"),
        pytest.param(lambda: UniformTy(123), id="uniform-ty"),
        pytest.param(lambda: WarpRole("", (0,)), id="warp-role-name"),
        pytest.param(lambda: WarpRole("load", (0,), instances=0), id="warp-role-instances"),
        pytest.param(lambda: WarpConfig(0), id="warp-config-warps"),
        pytest.param(lambda: GridConfig(cluster_dims=(1, 1)), id="grid-cluster-dims"),
        pytest.param(lambda: TmemConfig(total_cols=0), id="tmem-total-cols"),
        pytest.param(lambda: EpilogueConfig(num_epilogue_warps=-1), id="epilogue-warps"),
        pytest.param(lambda: TmemRegion("acc", -1, 16), id="tmem-start"),
        pytest.param(lambda: TmemRegion("acc", 0, 0), id="tmem-ncols"),
        pytest.param(lambda: TmemRegion("acc", 0, 16, num_buffers=0), id="tmem-buffers"),
        pytest.param(lambda: MbarrierSpec("full", 0), id="mbarrier-count"),
        pytest.param(lambda: MbarrierSpec("full", 1, init_phase=2), id="mbarrier-phase"),
        pytest.param(lambda: TmaDescriptor(0, ()), id="tma-desc-ndim"),
        pytest.param(lambda: TmaDescriptor(3, (8, 8)), id="tma-desc-rank"),
        pytest.param(lambda: BufferRef("A", i32, (1,), align=0), id="buffer-align"),
        pytest.param(lambda: SmemPool("pool", -1), id="smem-pool-size"),
        pytest.param(lambda: PhaseDomain("main", "stage", 0), id="phase-domain-stages"),
        pytest.param(lambda: MmaParams(0, 1, 0), id="mma-k-steps"),
        pytest.param(lambda: MmaParams(1, 0, 0), id="mma-groups"),
        pytest.param(lambda: MmaParams(1, 1, 0, cta_group=3), id="mma-cta-group"),
        pytest.param(lambda: MmaParams(1, 1, 0, cta_group=True), id="mma-cta-group-bool"),
        pytest.param(lambda: TmemRegionLoad(TmemRegion("acc", 0, 16), num=7), id="tmem-load-num"),
        pytest.param(
            lambda: TmemRegionStore(TmemRegion("acc", 0, 16), num=32), id="tmem-store-num"
        ),
        pytest.param(lambda: SmemLoadRegs("regs", 1, count=-1), id="smem-load-regs-count"),
        pytest.param(lambda: SmemLoadVec(1, 2, count=2), id="smem-load-vec-count"),
        pytest.param(lambda: ScaleFactorCopy(1, 2, cta_group=3), id="scale-cta-group"),
        pytest.param(lambda: ScaleFactorCopy(1, 2, cta_group=True), id="scale-cta-group-bool"),
        pytest.param(lambda: ScaleFactorCopy(1, 2, sbo=24), id="scale-sbo"),
        pytest.param(lambda: MetadataCopy(1, 2, cta_group=3), id="metadata-cta-group"),
        pytest.param(lambda: MetadataCopy(1, 2, cta_group=True), id="metadata-cta-group-bool"),
        pytest.param(
            lambda: BarrierSignal(MbarrierSpec("full", 1), "arrive", 0, cta_group=3),
            id="signal-cta",
        ),
        pytest.param(
            lambda: BarrierSignal(MbarrierSpec("full", 1), "arrive", 0, cta_group=True),
            id="signal-cta-bool",
        ),
        pytest.param(
            lambda: PeerArriveCommit(MbarrierSpec("full", 1), 0, cta_group=3),
            id="peer-arrive-cta",
        ),
        pytest.param(
            lambda: MulticastCommit(MbarrierSpec("full", 1), 0, 1, cta_group=3),
            id="multicast-cta",
        ),
        pytest.param(
            lambda: DualCommit(
                MbarrierSpec("empty", 1), MbarrierSpec("full", 1), 0, 1, cta_group=3
            ),
            id="dual-commit-cta",
        ),
        pytest.param(lambda: StAsync(1, bytes=12), id="st-async-bytes"),
        pytest.param(lambda: ThreshMask(1, 2, width=0), id="thresh-width-low"),
        pytest.param(lambda: ThreshMask(1, 2, width=33), id="thresh-width-high"),
        pytest.param(lambda: BitmaskFill(1, 2, count=0), id="bitmask-count-low"),
        pytest.param(lambda: BitmaskFill(1, 2, count=33), id="bitmask-count-high"),
        pytest.param(lambda: MaskFill(1, 2, size=-1), id="mask-size"),
        pytest.param(lambda: Tcgen05Cp(1, 2, cta_group=3), id="tcgen-cta"),
        pytest.param(lambda: Tcgen05Cp(1, 2, cta_group=True), id="tcgen-cta-bool"),
        pytest.param(lambda: Tcgen05Cp(1, 2, sbo=24), id="tcgen-sbo"),
        pytest.param(lambda: MmaTile(1, 2, 3, k_idx=4, cta_group=3), id="mma-tile-cta"),
        pytest.param(lambda: MmaTile(1, 2, 3, k_idx=4, cta_group=True), id="mma-tile-cta-bool"),
        pytest.param(lambda: FragmentOp("add", 1, size=-1), id="fragment-size"),
    ],
)
def test_numeric_and_cross_field_invariants(ctor: Callable[[], Any]) -> None:
    with pytest.raises((TypeError, ValueError)):
        ctor()


@pytest.mark.parametrize(
    "ctor",
    [
        pytest.param(lambda: Elementwise(op="add", inputs=b"abc"), id="elementwise-bytes"),
        pytest.param(lambda: Elementwise(op="add", inputs=42), id="elementwise-non-iterable"),
        pytest.param(lambda: PackedF32x2("add", inputs=["src"]), id="packed-string-input"),
        pytest.param(lambda: StAsync(1, srcs=["src"]), id="st-async-string-src"),
    ],
)
def test_expr_sequences_reject_invalid_inputs(ctor: Callable[[], Any]) -> None:
    with pytest.raises(TypeError):
        ctor()


def test_dtype_proxy_cannot_return_raw_string() -> None:
    class BadTyFactory:
        def to_dialect(self) -> str:
            return "float32"

    with pytest.raises(TypeError, match="dtype"):
        BufferRef("A", BadTyFactory(), (1,))


@pytest.mark.parametrize(
    "ctor",
    [
        pytest.param(lambda: PipelineSpec("p", 1, style="sequential"), id="pipeline-sequential"),
        pytest.param(lambda: PipelineSpec("p", 1, style="sw_pipelined"), id="pipeline-sw"),
        pytest.param(lambda: PipelineSpec("p", 1, style="warp_specialized"), id="pipeline-ws"),
        pytest.param(lambda: PipelineSpec("p", 1, style="none"), id="pipeline-none"),
        pytest.param(lambda: MbarrierSpec("full", 1, signaling_mode="elected"), id="mbar-elected"),
        pytest.param(lambda: MbarrierSpec("full", 1, signaling_mode="hw_commit"), id="mbar-hw"),
        pytest.param(lambda: MbarrierSpec("full", 1, signaling_mode="all_warps"), id="mbar-all"),
        pytest.param(
            lambda: MbarrierSpec("full", 1, signaling_mode="tma_expect_tx"), id="mbar-tma"
        ),
        pytest.param(
            lambda: GmemStore(1, 2, count=1, dtype=i32, src_dtype=i32, cache_hint="none"),
            id="cache-none",
        ),
        pytest.param(
            lambda: GmemStore(1, 2, count=1, dtype=i32, src_dtype=i32, cache_hint="no_allocate"),
            id="cache-no-allocate",
        ),
        pytest.param(
            lambda: GmemStore(1, 2, count=1, dtype=i32, src_dtype=i32, cache_hint="evict_first"),
            id="cache-evict-first",
        ),
        pytest.param(
            lambda: GmemStore(1, 2, count=1, dtype=i32, src_dtype=i32, cache_hint="evict_last"),
            id="cache-evict-last",
        ),
        pytest.param(lambda: Fence(kind="after_thread_sync"), id="fence-after"),
        pytest.param(lambda: Fence(kind="before_thread_sync"), id="fence-before"),
        pytest.param(lambda: ThreadFence(scope="block"), id="thread-block"),
        pytest.param(lambda: ThreadFence(scope="device"), id="thread-device"),
        pytest.param(lambda: ThreadFence(scope="system"), id="thread-system"),
        pytest.param(lambda: WarpReduce(1, op="add"), id="reduce-add"),
        pytest.param(lambda: WarpReduce(1, op="max"), id="reduce-max"),
        pytest.param(lambda: WarpReduce(1, op="min"), id="reduce-min"),
        pytest.param(lambda: ClcQueryCancelGetCtaId(1, 2, dim="x"), id="clc-x"),
        pytest.param(lambda: ClcQueryCancelGetCtaId(1, 2, dim="y"), id="clc-y"),
        pytest.param(lambda: ClcQueryCancelGetCtaId(1, 2, dim="z"), id="clc-z"),
        pytest.param(lambda: Tcgen05Cp(1, 2, shape="4x256b"), id="tcgen-4x256"),
        pytest.param(lambda: Tcgen05Cp(1, 2, shape="128x256b"), id="tcgen-128x256"),
        pytest.param(
            lambda: Tcgen05Cp(1, 2, shape="64x128b.warpx2::02_13"),
            id="tcgen-warpx2",
        ),
    ],
)
def test_valid_domain_values_are_accepted(ctor: Callable[[], Any]) -> None:
    ctor()


def test_mbarrier_derived_init_count() -> None:
    assert MbarrierSpec("full", 4, init_count=3).derived_init_count() == 3
    assert (
        MbarrierSpec("full", 4, signaling_mode="all_warps", producer_warps=7).derived_init_count()
        == 7
    )
    assert MbarrierSpec("full", 4, signaling_mode="all_warps").derived_init_count() == 1


def test_kernel_body_rejects_non_statements() -> None:
    with pytest.raises(TypeError):
        Kernel("bad", [], None, ["not a stmt"])


def test_task_scope_body_rejects_non_statements() -> None:
    with pytest.raises(TypeError):
        TaskSpec("bad", "producer", "tma", body=[Const("not_stmt", i32)])
    with pytest.raises(TypeError):
        Block([Const("not_stmt", i32)])


def test_task_and_assignment_invariants() -> None:
    with pytest.raises(ValueError):
        TaskSpec("", "producer", "tma")
    with pytest.raises(ValueError):
        ForLoop(extent=4, var=_var("i"), body=[], step=0)
    with pytest.raises(ValueError):
        ForLoop(extent=4, var=_var("i"), body=[], unroll=-1)
    with pytest.raises(TypeError):
        ForLoop(extent=4, var=_var("i"), body=[], start="stage")
    with pytest.raises(TypeError):
        VarDecl("not_a_var", "int")
    with pytest.raises(ValueError):
        Assign(Const("x", i32), 1, op="??")


def test_smem_swizzle_address_rejects_unknown_keywords() -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        SmemSwizzleAddress(1, unknown=True)
