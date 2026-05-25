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
"""Function/module-level Weave text-format round-trip tests."""

from __future__ import annotations

import pytest
import weave  # noqa: F401  # Registers the dialect.
from _roundtrip import assert_source_roundtrip


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @weave.Kernel
            def empty_kernel():
                pass
            """,
            id="empty-kernel",
        ),
        pytest.param(
            """
            @weave.kernel
            def typed_alias_kernel(
                m: std.i32,
                ptr: weave.PtrTy(std.bf16, const=True, space="global"),
            ) -> std.i32:
                return m
            """,
            id="lowercase-kernel-alias-and-typed-signature",
        ),
        pytest.param(
            """
            # Comments and blank lines are not semantically significant.
            @weave.Kernel
            def first():
                pass

            @weave.Kernel
            def second():
                pass
            """,
            id="multiple-top-level-kernels-with-comments",
        ),
    ],
)
def test_weave_kernel_source_round_trip(source: str) -> None:
    assert_source_roundtrip(source)


def test_weave_kernel_alias_prints_canonical_decorator() -> None:
    printed = assert_source_roundtrip(
        """
        @weave.kernel
        def alias_surface(x: weave.lm.f32) -> weave.lm.f32:
            return x
        """
    )

    assert printed.startswith("@weave.Kernel")
    assert "@weave.kernel" not in printed
    assert "weave.lm" not in printed
    assert printed.count("std.f32") == 2


def test_weave_kernels_inside_std_module_round_trip() -> None:
    printed = assert_source_roundtrip(
        """
        @std.module
        class KernelPair:
            @weave.Kernel
            def load_tile():
                with weave.TaskSpec("load", "producer", "tma"):
                    pass

            @weave.kernel
            def compute_tile():
                with weave.task("compute", "consumer", "mma"):
                    pass
        """
    )

    assert printed.startswith("@std.module")
    assert printed.count("@weave.Kernel") == 2
    assert "@weave.kernel" not in printed
    assert printed.count("with weave.TaskSpec") == 2
    assert "with weave.task" not in printed


def test_fully_decorated_kernel_source_round_trip() -> None:
    printed = assert_source_roundtrip(
        """
        @weave.Kernel(
            pipeline=weave.PipelineConfig(
                num_stages=2,
                style="warp_specialized",
                pipelines=[
                    weave.Pipeline(
                        "main",
                        2,
                        style="warp_specialized",
                        smem_buffers=["tile"],
                        cta_group=2,
                    )
                ],
            ),
            warps=weave.WarpConfig(
                4,
                roles=[
                    weave.WarpRole("load", [0], instances=1),
                    weave.WarpRole("mma", [1, 2, 3]),
                ],
            ),
            grid=weave.GridConfig(cluster_dims=[2, 1, 1], cta_group=2),
            tmem=weave.TmemConfig(
                buffering="double",
                regions=[weave.TmemRegion("acc", 0, 128, dtype=std.f32)],
            ),
            epilogue=weave.EpilogueConfig(
                "overlapped",
                vectorized=True,
                num_epilogue_warps=1,
            ),
            buffers=[
                weave.Buffer(
                    "A",
                    std.bf16,
                    shape=[128, 64],
                    tma=weave.TmaDescriptor(2, box_shape=[16, 64]),
                )
            ],
            mbarriers=[
                weave.Mbarrier(
                    "full",
                    2,
                    producers=["load"],
                    consumers=["mma"],
                    signaling_mode="all_warps",
                    producer_warps=4,
                )
            ],
            smem_pools=[weave.SmemPool("pool", 4096)],
            smem_views=[
                weave.SmemView(
                    "tile",
                    "pool",
                    0,
                    shape=[16, 64],
                    dtype=std.bf16,
                    swizzle=weave.Swizzle(7, 6, 3),
                )
            ],
            protocols=[
                weave.PipelineProtocol(
                    "main",
                    load_tasks=["load"],
                    compute_tasks=["mma"],
                )
            ],
            phase_domains=[
                weave.PhaseDomain(
                    "main",
                    "stage",
                    2,
                    phase_vars=[weave.PhaseVar("phase", dtype=std.i32)],
                )
            ],
            params=[weave.Param("m", "int")],
            constants={"BLOCK_M": 64},
            task_times=[weave.TaskTiming(task="load", cycles=12)],
            barriers=[weave.BarrierEdge(producer="load", consumer="mma", barrier="full")],
            smem_alloc=[weave.SmemAllocation(name="tile", offset=0, size=1024)],
            tmem_alloc=[weave.TmemAllocation(name="acc", start_col=0, ncols=128)],
            tile_params=weave.MmaParams(2, 4, 0, dtype=std.bf16),
            reg_budgets={"mma": 128},
            tma_param_ndims={"A": 2},
        )
        def full_kernel(
            m: std.i32,
            ptr: weave.PtrTy(std.bf16, const=True, space="global"),
        ) -> std.i32:
            with weave.TaskSpec("load", "producer", "tma", pipeline="main", outputs=["tile"]):
                weave.GmemLoad(
                    weave.Const("src", result_ty=std.u64),
                    weave.Const("dst", result_ty=std.u32),
                    count=8,
                    dtype=std.bf16,
                    dst_dtype=std.f32,
                )
                tok = weave.BarrierTryWait(weave.Mbarrier("full", 2), 0, 1, ty=std.i32)
            return m
        """
    )

    assert "pipeline=weave.PipelineConfig" in printed
    assert "buffers=[weave.Buffer" in printed
    assert 'constants={"BLOCK_M": 64}' in printed
    assert 'params=[weave.Param("m", "int")]' in printed
    assert "tile_params=weave.MmaParams" in printed
    assert 'reg_budgets={"mma": 128}' in printed
    assert 'tma_param_ndims={"A": 2}' in printed
    assert "tok = weave.BarrierTryWait" in printed
    assert "ty=std.i32" in printed


def test_task_scope_and_loop_source_round_trip() -> None:
    printed = assert_source_roundtrip(
        """
        @weave.Kernel
        def body_kernel():
            with weave.task("compute", "consumer", "mma", depends_on=["load"]):
                stage = weave.VarDecl("int", init=0, ty=std.i32)
                for k in weave.ForLoop(4, start=0, step=1, ty=std.i32):
                    with weave.Block():
                        weave.Assign(weave.Const("stage", result_ty=std.i32), k, op="+=")
                    with weave.LeaderCtaBlock():
                        weave.BarrierSignal(weave.Mbarrier("full", 2), "arrive", stage)
                    with weave.ElectedThreadBlock():
                        weave.ClusterSync()
                    with weave.ConditionalIteration(k, last_expr=k + 1):
                        break
        """
    )

    assert "with weave.TaskSpec" in printed
    assert "for k in weave.ForLoop" in printed
    assert "with weave.LeaderCtaBlock" in printed
    assert "with weave.ElectedThreadBlock" in printed
    assert "with weave.ConditionalIteration" in printed


def test_operation_source_round_trip() -> None:
    printed = assert_source_roundtrip(
        """
        @weave.Kernel
        def ops_kernel():
            with weave.TaskSpec("compute", "consumer", "mma"):
                weave.SmemDesc("tile", k_idx=0, mode="mn", dst=1, step=2, offset=3)
                weave.Elementwise(op="fma", inputs=[1, 2, 3], output=4)
                weave.PredicatedStore(
                    1,
                    2,
                    bound_m=3,
                    bound_n=4,
                    tile_offset_m=5,
                    tile_offset_n=6,
                )
                weave.Tcgen05Cp(
                    1,
                    2,
                    shape="64x128b.warpx2::02_13",
                    cta_group=2,
                    sbo=256,
                )
                weave.MmaTile(
                    1,
                    2,
                    3,
                    k_idx=0,
                    a_dtype=std.bf16,
                    b_dtype=std.bf16,
                    acc_dtype=std.f32,
                )
                weave.AtomicOp("max", 1, 2, space="smem", index=3, dtype=std.f32)
                weave.MultimemLdReduce(1, 2, payload="bf16x8")
                weave.ClcQueryCancelGetCtaId(1, 2, dim="z")
        """
    )

    assert "weave.SmemDesc" in printed
    assert "weave.Elementwise" in printed
    assert "weave.PredicatedStore" in printed
    assert "weave.Tcgen05Cp" in printed
    assert "weave.MmaTile" in printed
    assert "weave.AtomicOp" in printed
    assert 'payload="bf16x8"' in printed
    assert 'dim="z"' in printed


def test_memory_barrier_and_reduction_source_round_trip() -> None:
    printed = assert_source_roundtrip(
        """
        @weave.Kernel
        def ops_catalog():
            with weave.TaskSpec("ops", "consumer", "mma"):
                weave.TmemRegionLoad(
                    weave.TmemRegion("acc", 0, 128, dtype=std.f32),
                    dst=1,
                    col_offset=2,
                    num=16,
                    row_base=3,
                )
                weave.TmemRegionStore(
                    weave.TmemRegion("acc", 0, 128, dtype=std.f32),
                    src=4,
                    col_offset=5,
                    num=8,
                    dtype=std.f32,
                    row_base=6,
                )
                weave.TmaGatherLoad(
                    1,
                    2,
                    3,
                    tokens_per_page=128,
                    mbar_expr=4,
                    token_offset=5,
                )
                weave.BarrierWait(weave.Mbarrier("full", 2), 0, 1, token=2)
                weave.PeerArriveCommit(weave.Mbarrier("full", 2), 0, cta_group=2)
                weave.MulticastCommit(weave.Mbarrier("full", 2), 0, 3, cta_group=2)
                weave.DualCommit(
                    weave.Mbarrier("full", 2),
                    weave.Mbarrier("empty", 2),
                    0,
                    1,
                    cta_group=2,
                )
                weave.GridSync()
                weave.GridDepSync()
                weave.GridDepLaunch()
                reduced = weave.WarpReduce(1, op="max", ty=std.i32)
                weave.BlockReduce(1, 2, op="min")
                weave.CrossWarpReduce(
                    1,
                    2,
                    std.Var(std.f32, "cw"),
                    op="max",
                    finalize="rsqrt",
                )
                weave.WarpGroupReduce(
                    1,
                    2,
                    std.Var(std.f32, "wg"),
                    op="min",
                    num_warp_groups=4,
                )
                weave.StAsync(1, srcs=[2, 3, 4, 5], bytes=16, barrier=reduced, src_is_int=True)
        """
    )

    for expected in (
        "weave.TmemRegionLoad",
        "weave.TmemRegionStore",
        "weave.TmaGatherLoad",
        "weave.BarrierWait",
        "weave.PeerArriveCommit",
        "weave.MulticastCommit",
        "weave.DualCommit",
        "weave.GridSync",
        "weave.GridDepSync",
        "weave.GridDepLaunch",
        "reduced = weave.WarpReduce",
        "weave.BlockReduce",
        "weave.CrossWarpReduce",
        "weave.WarpGroupReduce",
        "weave.StAsync",
    ):
        assert expected in printed
