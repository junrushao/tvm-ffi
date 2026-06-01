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
import weave  # noqa: F401
from tvm_ffi import std
from weave.ir import *


def _var(name: str = "v", ty: std.Ty | None = None) -> std.Var:
    return std.Var(ty or i32, name)


def _string_imm(value: str) -> std.StringImm:
    return std.StringImm.from_py(value)


def test_expr_fields_reject_unconvertible_values() -> None:
    with pytest.raises(TypeError):
        SmemStore(object(), 1)
    with pytest.raises(TypeError):
        Elementwise(op="add", inputs=[object(), 1])


def test_domain_fields_are_validated() -> None:
    with pytest.raises(ValueError):
        BarrierSignal(0, action="bad", barrier=MbarrierSpec("full", 1))
    with pytest.raises(ValueError):
        AtomicOp(1, 2, op="bad", space="gmem", dtype=i32)
    with pytest.raises(ValueError):
        Tcgen05Cp(1, 2, shape="bad")


def test_dtype_fields_normalize_raw_strings() -> None:
    load = GmemLoad(1, 2, count=1, dtype="int32", dst_dtype=i32)
    assert load.dtype == i32.dtype
    assert load.dst_dtype == i32.dtype


@pytest.mark.parametrize(
    "ctor",
    [
        pytest.param(lambda: TmemRegion("acc", 0, 16, dtype="f32"), id="tmem-region"),
        pytest.param(lambda: BufferRef("A", "f32", (16,)), id="buffer-ref"),
        pytest.param(
            lambda: SmemView(0, name="tile", pool="pool", shape=(16,), dtype="f32"),
            id="smem-view",
        ),
        pytest.param(lambda: PhaseVar(name="phase", dtype="int32"), id="phase-var"),
        pytest.param(lambda: MmaParams(1, 1, 0, dtype="f32"), id="mma-params"),
        pytest.param(lambda: SymmetricMemory("sym", "f32", (16,), "pg"), id="symmetric-memory"),
        pytest.param(lambda: AtomicOp(1, 2, op="add", space="gmem", dtype="f32"), id="atomic-op"),
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
            lambda: TmemRegionStore(region=TmemRegion("acc", 0, 16), dtype="f32"),
            id="tmem-store",
        ),
        pytest.param(lambda: SmemLoadRegs(1, name="regs", dtype="f32"), id="smem-load-regs"),
        pytest.param(lambda: RegArrayCast(1, 2, src_dtype="f32", dst_dtype=i32), id="reg-cast-src"),
        pytest.param(lambda: RegArrayCast(1, 2, src_dtype=i32, dst_dtype="f32"), id="reg-cast-dst"),
        pytest.param(lambda: FragmentOp(1, op="add", dtype="f32"), id="fragment-op"),
        pytest.param(lambda: MmaTile(1, 2, 3, k_idx=4, a_dtype="f32"), id="mma-tile"),
    ],
)
def test_dtype_fields_normalize_raw_strings_across_weave(ctor: Callable[[], Any]) -> None:
    ctor()


def test_op_dtype_fields_normalize_factory_values() -> None:
    class DTypeProxy:
        def to_dialect(self) -> std.Ty:
            return i32

    load = GmemLoad(1, 2, count=1, dtype=DTypeProxy(), dst_dtype=DTypeProxy())
    store = GmemStore(1, 2, count=1, dtype=DTypeProxy(), src_dtype=DTypeProxy())
    atom = AtomicOp(1, 2, op="add", space="gmem", dtype=DTypeProxy())
    cast = RegArrayCast(1, 2, src_dtype=DTypeProxy(), dst_dtype=DTypeProxy())

    for value in (load.dtype, load.dst_dtype, store.dtype, store.src_dtype, atom.dtype):
        assert value == i32.dtype
    assert cast.src_dtype == i32.dtype
    assert cast.dst_dtype == i32.dtype


def test_handle_dtype_fields_normalize_factory_values() -> None:
    class DTypeProxy:
        def to_dialect(self) -> std.Ty:
            return i32

    values = [
        TmemRegion("acc", 0, 16, dtype=DTypeProxy()).dtype,
        BufferRef("A", DTypeProxy(), (16,)).dtype,
        SmemView(0, name="tile", pool="pool", shape=(16,), dtype=DTypeProxy()).dtype,
        PhaseVar(name="phase", dtype=DTypeProxy()).dtype,
        MmaParams(1, 1, 0, dtype=DTypeProxy()).dtype,
        SymmetricMemory("sym", DTypeProxy(), (16,), "pg").dtype,
        TmemRegionStore(region=TmemRegion("acc", 0, 16), dtype=DTypeProxy()).dtype,
    ]

    for value in values:
        assert value == i32.dtype


def test_attr_string_fields_reject_string_imm_values() -> None:
    swizzle = _string_imm("128B")
    pool = _string_imm("pool")
    role = _string_imm("role")

    for ctor in (
        lambda: TmaDescriptor(2, (16, 16), swizzle=swizzle),
        lambda: BufferRef("A", i32, (16,), swizzle=swizzle),
        lambda: SmemView(0, name="tile", pool=pool, shape=(16,), dtype=i32),
        lambda: SmemView(0, name="tile", pool="pool", shape=(16,), dtype=i32, swizzle=swizzle),
        lambda: TaskSpec("task", "producer", role, outputs=("out",)),
        lambda: TaskSpec("task", "producer", "role", outputs=(_string_imm("out"),)),
        lambda: TmemRegionLoad(region=_string_imm("acc")),
        lambda: SmemDesc(buffer=_string_imm("tile")),
    ):
        with pytest.raises(TypeError):
            ctor()


def test_structured_barrier_refs_reject_raw_strings() -> None:
    with pytest.raises(TypeError):
        BarrierSignal(Const("stage", i32), action="arrive", barrier="full")
    with pytest.raises(TypeError):
        BarrierSignal(Const("stage", i32), action="arrive", barrier=std.StringImm.from_py("full"))
    with pytest.raises(TypeError):
        BarrierWait(Const("stage", i32), Const("phase", i32), barrier="full")
    with pytest.raises(TypeError):
        BarrierTryWait(Const("stage", i32), Const("phase", i32), _var("tok"), barrier="full")
    with pytest.raises(TypeError):
        PeerArriveCommit(0, barrier=std.StringImm.from_py("full"))
    with pytest.raises(TypeError):
        CpAsyncBulkSmem2SmemCluster(1, 2, 16, barrier=std.StringImm.from_py("full"))
    with pytest.raises(TypeError):
        PeerArriveCommit(0, barrier="full")
    with pytest.raises(TypeError):
        MulticastCommit(0, 1, barrier="full")
    with pytest.raises(TypeError):
        DualCommit(0, 1, barrier_0="full", barrier_1=MbarrierSpec("full", 1))
    with pytest.raises(TypeError):
        DualCommit(0, 1, barrier_0=MbarrierSpec("full", 1), barrier_1="full")
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
        pytest.param(lambda: SmemDesc(buffer="tile", mode="bad"), id="smem-desc-mode"),
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
        pytest.param(lambda: PackedF32x2(op="bad"), id="packed-f32x2-op"),
        pytest.param(lambda: FragmentOp(1, op="bad"), id="fragment-op-domain"),
        pytest.param(
            lambda: AtomicOp(1, 2, op="bad", space="gmem", dtype=i32), id="atomic-op-domain"
        ),
        pytest.param(lambda: AtomicOp(1, 2, op="add", space="bad", dtype=i32), id="atomic-space"),
        pytest.param(lambda: RelaxedFmax(1, 2, space="bad"), id="relaxed-fmax-space"),
        pytest.param(lambda: MultimemLdReduce(1, 2, payload="bad"), id="multimem-load-payload"),
        pytest.param(lambda: MultimemStore(1, 2, payload="bf16x8"), id="multimem-store-payload"),
        pytest.param(lambda: MultimemRedAddI32(1, 2, sem="bad"), id="multimem-sem"),
        pytest.param(lambda: MultimemRedAddI32(1, 2, scope="bad"), id="multimem-scope"),
        pytest.param(lambda: ClcQueryCancelGetCtaId(1, 2, dim="bad"), id="clc-dim"),
        pytest.param(
            lambda: BarrierSignal(0, action="bad", barrier=MbarrierSpec("full", 1)),
            id="barrier-action",
        ),
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
        pytest.param(
            lambda: TmemRegionLoad(region=TmemRegion("acc", 0, 16), num=7), id="tmem-load-num"
        ),
        pytest.param(
            lambda: TmemRegionStore(region=TmemRegion("acc", 0, 16), num=32), id="tmem-store-num"
        ),
        pytest.param(lambda: SmemLoadRegs(1, name="regs", count=-1), id="smem-load-regs-count"),
        pytest.param(lambda: SmemLoadVec(1, 2, count=2), id="smem-load-vec-count"),
        pytest.param(lambda: ScaleFactorCopy(1, 2, cta_group=3), id="scale-cta-group"),
        pytest.param(lambda: ScaleFactorCopy(1, 2, cta_group=True), id="scale-cta-group-bool"),
        pytest.param(lambda: ScaleFactorCopy(1, 2, sbo=24), id="scale-sbo"),
        pytest.param(lambda: MetadataCopy(1, 2, cta_group=3), id="metadata-cta-group"),
        pytest.param(lambda: MetadataCopy(1, 2, cta_group=True), id="metadata-cta-group-bool"),
        pytest.param(
            lambda: BarrierSignal(0, action="arrive", barrier=MbarrierSpec("full", 1), cta_group=3),
            id="signal-cta",
        ),
        pytest.param(
            lambda: BarrierSignal(
                0, action="arrive", barrier=MbarrierSpec("full", 1), cta_group=True
            ),
            id="signal-cta-bool",
        ),
        pytest.param(
            lambda: PeerArriveCommit(0, barrier=MbarrierSpec("full", 1), cta_group=3),
            id="peer-arrive-cta",
        ),
        pytest.param(
            lambda: MulticastCommit(0, 1, barrier=MbarrierSpec("full", 1), cta_group=3),
            id="multicast-cta",
        ),
        pytest.param(
            lambda: DualCommit(
                0,
                1,
                barrier_0=MbarrierSpec("empty", 1),
                barrier_1=MbarrierSpec("full", 1),
                cta_group=3,
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
        pytest.param(lambda: FragmentOp(1, op="add", size=-1), id="fragment-size"),
        pytest.param(
            lambda: Kernel("k", [], None, [], reg_budgets={"mma": std.Var(i32, "n")}),
            id="kernel-reg-budget-expr",
        ),
        pytest.param(
            lambda: Kernel("k", [], None, [], reg_budgets={"mma": True}),
            id="kernel-reg-budget-bool",
        ),
        pytest.param(
            lambda: Kernel("k", [], None, [], reg_budgets={"mma": 1.5}),
            id="kernel-reg-budget-float",
        ),
        pytest.param(
            lambda: Kernel("k", [], None, [], tma_param_ndims={1: 2}),
            id="kernel-tma-param-key",
        ),
        pytest.param(
            lambda: Kernel("k", [], None, [], tma_param_ndims={"A": True}),
            id="kernel-tma-param-bool",
        ),
        pytest.param(
            lambda: Kernel("k", [], None, [], tma_param_ndims={"A": 1.5}),
            id="kernel-tma-param-float",
        ),
        pytest.param(
            lambda: Kernel("k", [], None, [], tma_param_ndims=std.IntImm.from_py(1)),
            id="kernel-tma-param-map",
        ),
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
        pytest.param(lambda: PackedF32x2(inputs=[object()], op="add"), id="packed-object-input"),
        pytest.param(lambda: StAsync(1, srcs=[object()]), id="st-async-object-src"),
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


def test_kernel_constants_preserve_primitive_python_values() -> None:
    kernel = Kernel(
        "k",
        [],
        None,
        [],
        constants={"i": 64, "f": 1.5, "s": "tile", "b": True},
    )

    constants = dict(kernel.constants.items())
    assert constants == {"i": 64, "f": 1.5, "s": "tile", "b": True}
    assert {key: type(value) for key, value in constants.items()} == {
        "i": int,
        "f": float,
        "s": str,
        "b": bool,
    }


@pytest.mark.parametrize("field_name", ["reg_budgets", "tma_param_ndims"])
@pytest.mark.parametrize("bad_value", [True, 1.5])
def test_kernel_int_maps_reject_invalid_values_after_field_conversion(
    field_name: str, bad_value: object
) -> None:
    kernel = Kernel("k", [], None, [])
    setattr(kernel, field_name, {"x": bad_value})

    with pytest.raises(TypeError, match=rf"{field_name}\['x'\] must be an integer constant"):
        kernel.__post_init__()


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
        pytest.param(lambda: WarpReduce(1, op="add", ty=i32), id="reduce-add"),
        pytest.param(lambda: WarpReduce(1, op="max", ty=i32), id="reduce-max"),
        pytest.param(lambda: WarpReduce(1, op="min", ty=i32), id="reduce-min"),
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
        ForLoop(extent=4, var=_var("i"), body=[], start=object())
    with pytest.raises(TypeError):
        VarDecl(ctype="int", var="not_a_var")
    with pytest.raises(ValueError):
        Assign(Const("x", i32), 1, op="??")
