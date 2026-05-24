# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Representative per-node text round-trip tests for Weave IR."""

# ruff: noqa: F405

from __future__ import annotations

from typing import Any

import tvm_ffi
import weave  # noqa: F401  # Registers the dialect.
from tvm_ffi import std
from tvm_ffi._pyast_parser import parse
from weave.ir import *


def _rt(node: Any) -> None:
    parsed = parse(node.text())
    assert tvm_ffi.structural_equal(parsed, node), node.text()
    assert tvm_ffi.structural_equal(node, parsed), node.text()


def _v(name: str, ty: std.Ty | None = None) -> std.Var:
    return std.Var(ty or i32, name)


def _barrier() -> MbarrierSpec:
    return MbarrierSpec("full", 2)


def _region() -> TmemRegion:
    return TmemRegion("acc", 0, 128)


def _nodes() -> list[Any]:
    pool = SmemPool("pool", 4096)
    desc = TmaDescriptor(2, (16, 64))
    buf = BufferRef("A", f32, (128, 64), tma=desc)
    view = SmemView("tile", pool, 0, (16, 64), f32)
    phase = PhaseVar("phase")
    domain = PhaseDomain("main", "stage", 2, phase_vars=(phase,))
    role = WarpRole("mma", (0, 1, 2, 3))
    pipe = PipelineSpec("main", 2)
    barrier = _barrier()
    assign = Assign(Const("x", i32), 1)
    task_node = TaskSpec("load", "producer", "tma", body=[assign])
    return [
        RawTy(),
        Ue4m3Ty(),
        ConstexprTy(),
        TmaGatherTy(),
        TmaReduceTy(),
        GridCounterTy(),
        TmaTy(2),
        UniformTy(i32),
        PtrTy(f32, const=True, space="global"),
        Swizzle(4, 3, 3),
        Const("BLOCK_M", i32),
        Field(Const("frag"), "x", f32),
        AddrOf(Const("ptr", i32), PtrTy(i32)),
        Deref(Const("ptr", PtrTy(f32)), f32),
        ReinterpretCast(Const("ptr", PtrTy(u8)), PtrTy(f32, const=True)),
        SmemSwizzleOffset(1, Swizzle(4, 3, 3)),
        SmemSwizzleAddress(1, swizzle=Swizzle(4, 3, 3), row_stride_bytes=256),
        TmemRef("acc", offset=1),
        SmemRef("tile", offset=2),
        SmemDescRef("tile", 0),
        BarrierRef("full", stage=0),
        BuiltinRef("warp_in_role", i32),
        role,
        pipe,
        PipelineProtocol("main", load_tasks=("load",), compute_tasks=("mma",)),
        barrier,
        desc,
        buf,
        ScalarParam("n", "int"),
        WarpConfig(4, roles=(role,)),
        PipelineConfig(pipelines=(pipe,)),
        GridConfig(cluster_dims=(2, 1, 1), cta_group=2),
        TmemConfig(regions=(_region(),), buffering="double"),
        EpilogueConfig("overlapped", vectorized=True, num_epilogue_warps=1),
        pool,
        view,
        phase,
        domain,
        MmaParams(2, 4, 0, dtype=f32),
        SoftmaxParams(128, num_load_chunks=4),
        EpilogueParams(128, 8, use_tma_store=True),
        TmaLoadParams("main", src_buffers=("A",), dst_buffers=("tile",)),
        NamedBarrierSpec("bar", 1, 128),
        ProcessGroup("pg", 8),
        SymmetricMemory("sym", f32, (128,), "pg"),
        TaskTiming(task="load", cycles=10),
        BarrierEdge("load", "mma", "full"),
        SmemAllocation("tile", 0, 1024),
        TmemAllocation("acc", 0, 128),
        task_node,
        ForLoop(extent=4, var=_v("i"), body=[std.Break()], start=0, step=1),
        Block([assign]),
        LeaderCtaBlock([assign]),
        ElectedThreadBlock([assign]),
        ConditionalIteration(Const("i", i32), last_expr=True, body=[assign]),
        VarDecl(_v("stage"), "int", init=0),
        assign,
        Kernel(
            "kernel",
            [],
            None,
            [task_node],
            pipeline=PipelineConfig(pipelines=(pipe,)),
            warps=WarpConfig(4, roles=(role,)),
            grid=GridConfig(),
            tmem=TmemConfig(regions=(_region(),)),
            epilogue=EpilogueConfig(),
            buffers=(buf,),
            mbarriers=(barrier,),
            smem_pools=(pool,),
            smem_views=(view,),
            phase_domains=(domain,),
        ),
        BuiltinVar("warp_in_role", dst=1),
        TmemRegionLoad(_region(), dst=1, col_offset=0, num=16),
        TmemRegionStore(_region(), src=1, dtype=f32),
        SmemDesc("tile", k_idx=0, mode="k", dst=1),
        GmemLoad(1, 2, count=8, dtype=bf16, dst_dtype=f32),
        GmemStore(1, 2, count=8, dtype=bf16, src_dtype=f32),
        SmemStore(1, 2, predicate=True, index=0),
        SmemLoad(1, 2),
        SmemRead(1, dst=2, index=0),
        SmemLoadRegs("regs", 1, count=4, dtype=f32),
        SmemWrite(1, 2, index=0),
        SmemLoadVec(1, 2),
        SmemStoreVec(1, 2),
        TmaStore(1, 2),
        TmaReduceOp(1, 2, op="max"),
        TmaGatherLoad(1, 2, 3, token_offset=4),
        ScaleFactorCopy(1, 2, cta_group=2, sbo=128),
        MetadataCopy(1, 2),
        Elementwise(op="fma", inputs=[1, 2, 3], output=4),
        PredicatedStore(1, 2, bound_m=3, bound_n=4, tile_offset_m=5, tile_offset_n=6),
        ThreshMask(1, 32, width=16),
        BitmaskFill(1, 2, fill_value=0, count=16),
        MaskFill(1, 0, size=8),
        RegArrayCast(1, 2, src_dtype=i8, dst_dtype=bf16, count=4),
        BarrierSync(),
        BarrierTryWait(barrier, 0, 1, _v("tok")),
        BarrierWait(barrier, 0, 1, token=1),
        BarrierSignal(barrier, "arrive_expect_tx", 0, tx_bytes=128),
        MBarrierArrive(1),
        PeerArriveCommit(barrier, 0),
        MulticastCommit(barrier, 0, 3),
        DualCommit(barrier, barrier, 0, 1),
        Fence(kind="before_thread_sync"),
        ThreadFence(scope="system"),
        ClusterSync(),
        GridSync(),
        GridDepSync(),
        GridDepLaunch(),
        ClusterMapa(1, 2, _v("remote", u32)),
        ClusterBarrierArrive(1, tx_count=16, peer_rank=0),
        CpAsyncBulkSmem2SmemCluster(1, 2, 16, mbar_addr=3),
        WarpReduce(1, op="add"),
        BlockReduce(1, 2, op="max"),
        CrossWarpReduce(1, 2, _v("cw", f32), finalize="rsqrt"),
        WarpGroupReduce(1, 2, _v("wg", f32), num_warp_groups=2),
        StAsync(1, srcs=[2, 3, 4, 5], bytes=16),
        Tcgen05Cp(1, 2, shape="4x256b"),
        PackedF32x2("fma", inputs=[1, 2, 3], output=4),
        FragmentOp("add", 1, srcs=[2, 3], size=16, dtype=f32),
        MmaTile(1, 2, 3, k_idx=0, a_dtype=bf16, b_dtype=bf16, acc_dtype=f32),
        AtomicOp("add", 1, 2, space="gmem", dtype=f32),
        AtomicFetchAdd(1, 2, 3, dtype=u32),
        RelaxedFmax(1, 2, space="smem"),
        AtomicMaxF32Positive(1, 2, index=0, dst=3),
        SysVolatileLoad128(1, 2),
        SysVolatileStore128(1, 2),
        MultimemLdReduce(1, 2, payload="bf16x8"),
        MultimemStore(1, 2),
        MultimemRedAddI32(1, 2, sem="relaxed", scope="gpu"),
        AtomicMaxFloatEncode(1, 2),
        AtomicMaxFloatDecode(1, 2),
        ClcTryCancel(1, 2, multicast=True),
        ClcQueryCancel(1, 2),
        ClcQueryCancelGetCtaId(1, 2, dim="y"),
        ClcFenceRelease(),
    ]


def test_representative_weave_nodes_text_round_trip() -> None:
    for node in _nodes():
        _rt(node)
