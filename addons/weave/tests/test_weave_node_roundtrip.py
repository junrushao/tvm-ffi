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
"""Per-node Weave text round-trip tests."""

from __future__ import annotations

from typing import Any

import pytest
import weave  # noqa: F401  # Registers the Weave dialect.
import weave.ir as wi
from _roundtrip import assert_node_roundtrip
from tvm_ffi import std


def _v(name: str, ty: std.Ty | None = None) -> std.Var:
    return std.Var(ty or wi.i32, name)


def _pool() -> wi.SmemPool:
    return wi.SmemPool("pool", 8192)


def _swizzle() -> wi.Swizzle:
    return wi.Swizzle(7, 6, 3)


def _tma() -> wi.TmaDescriptor:
    return wi.TmaDescriptor(
        2,
        box_shape=(16, 64),
        swizzle="128B",
        global_shape=("m", "n"),
        global_strides=("n", "1"),
    )


def _buffer() -> wi.BufferRef:
    return wi.BufferRef(
        "A",
        wi.f32,
        (128, 64),
        space="gmem",
        tma=_tma(),
        source_gmem="A_global",
        scale_buffer="A_scale",
        align=16,
        volatile=True,
    )


def _barrier() -> wi.MbarrierSpec:
    return wi.MbarrierSpec(
        "full",
        2,
        init_count=1,
        producers=("load",),
        consumers=("compute",),
        signaling_mode="all_warps",
        producer_warps=4,
        stage_var="stage",
        pipeline="main",
        init_phase=1,
    )


def _role() -> wi.WarpRole:
    return wi.WarpRole(
        "load",
        (0, 1),
        register_budget=32,
        auto_warp_vars=True,
        tmem_var_regions=("acc",),
        warp_group_size=2,
        instances=1,
    )


def _pipeline() -> wi.PipelineSpec:
    return wi.PipelineSpec(
        "main",
        3,
        style="sw_pipelined",
        smem_buffers=("tile",),
        cta_group=2,
        producer_barriers=("empty",),
        consumer_barriers=("full",),
        release_barriers=("done",),
        smem_region="main",
        kparam_name="k",
    )


def _phase() -> wi.PhaseVar:
    return wi.PhaseVar(
        name="phase",
        dtype=wi.i32,
        init_value=1,
        rotation_rule="xor",
        rotation_trigger="advance",
    )


def _task_body() -> list[std.Stmt]:
    return [wi.Assign(wi.Const("stage", wi.i32), 0)]


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(wi.RawTy(), id="raw-ty-marker"),
        pytest.param(wi.Ue4m3Ty(), id="ue4m3-ty-marker"),
        pytest.param(wi.ConstexprTy(), id="constexpr-ty-marker"),
        pytest.param(wi.TmaGatherTy(), id="tma-gather-ty-marker"),
        pytest.param(wi.TmaReduceTy(), id="tma-reduce-ty-marker"),
        pytest.param(wi.GridCounterTy(), id="grid-counter-ty-marker"),
        pytest.param(wi.TmaTy(5), id="tma-ty-rank"),
        pytest.param(wi.UniformTy(wi.i32), id="uniform-ty"),
        pytest.param(wi.PtrTy(wi.f32, const=True, volatile=True, space="global"), id="ptr-ty"),
        pytest.param(_swizzle(), id="swizzle"),
        pytest.param(wi.Const("BLOCK_M", wi.i32), id="const-expr"),
        pytest.param(wi.Field(wi.Const("frag"), "x", wi.f32), id="field-expr"),
        pytest.param(wi.AddrOf(wi.Const("ptr", wi.i32), wi.PtrTy(wi.i32)), id="addr-of-expr"),
        pytest.param(wi.Deref(wi.Const("ptr", wi.PtrTy(wi.f32)), wi.f32), id="deref-expr"),
        pytest.param(
            wi.ReinterpretCast(wi.Const("ptr", wi.PtrTy(wi.u8)), wi.PtrTy(wi.f32, const=True)),
            id="reinterpret-cast-expr",
        ),
        pytest.param(wi.SmemSwizzleOffset(1, _swizzle()), id="smem-swizzle-offset"),
        pytest.param(
            wi.SmemSwizzleAddress(
                1,
                swizzle=_swizzle(),
                row_stride_bytes=256,
                layout="tcgen05",
                coord_row=2,
                coord_col=3,
                coord_col_unit="element",
                tcgen05_tile_height=64,
                tcgen05_k_elements=32,
                addr_space="shared",
            ),
            id="smem-swizzle-address-full",
        ),
        pytest.param(wi.TmemRef(1, region="acc"), id="tmem-ref"),
        pytest.param(wi.SmemRef(2, buffer="tile"), id="smem-ref"),
        pytest.param(wi.SmemDescRef(0, buffer="tile", mode="mn"), id="smem-desc-ref"),
        pytest.param(wi.BarrierRef(0, barrier="full"), id="barrier-ref"),
        pytest.param(wi.BuiltinRef("warp_in_role", wi.i32), id="builtin-ref"),
    ],
)
def test_type_and_expression_nodes_text_round_trip(node: Any) -> None:
    assert_node_roundtrip(node)


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(_role(), id="warp-role"),
        pytest.param(_pipeline(), id="pipeline-spec"),
        pytest.param(
            wi.PipelineConfig(style="warp_specialized", num_stages=3, pipelines=(_pipeline(),)),
            id="pipeline-config",
        ),
        pytest.param(
            wi.PipelineProtocol(
                "main",
                load_tasks=("load",),
                compute_tasks=("mma",),
                empty_barrier="empty",
                full_barrier="full",
            ),
            id="pipeline-protocol",
        ),
        pytest.param(
            wi.WarpConfig(
                8,
                roles=(_role(),),
                tma_warp=0,
                mma_warp=4,
                epilogue_warps=(6, 7),
            ),
            id="warp-config",
        ),
        pytest.param(wi.GridConfig(cluster_dims=(2, 1, 1), cta_group=2), id="grid-config"),
        pytest.param(
            wi.TmemConfig(
                buffering="double",
                regions=(wi.TmemRegion("acc", 0, 128, num_buffers=2, dtype=wi.f32),),
                total_cols=256,
                allocator_warp=7,
            ),
            id="tmem-config",
        ),
        pytest.param(
            wi.EpilogueConfig("overlapped", vectorized=True, num_epilogue_warps=1),
            id="epilogue-config",
        ),
        pytest.param(wi.TaskTiming(task="load", cycles=42), id="task-timing"),
        pytest.param(
            wi.BarrierEdge(producer="load", consumer="mma", barrier="full"),
            id="barrier-edge",
        ),
        pytest.param(
            wi.SmemAllocation(name="tile", offset=64, size=4096),
            id="smem-allocation",
        ),
        pytest.param(
            wi.TmemAllocation(name="acc", start_col=128, ncols=64),
            id="tmem-allocation",
        ),
        pytest.param(wi.TmemRegion("acc", 0, 128, num_buffers=2, dtype=wi.f32), id="tmem-region"),
        pytest.param(_barrier(), id="mbarrier-spec"),
        pytest.param(_tma(), id="tma-descriptor"),
        pytest.param(_buffer(), id="buffer-ref"),
        pytest.param(wi.ScalarParam("m", "int"), id="scalar-param"),
        pytest.param(_pool(), id="smem-pool"),
        pytest.param(
            wi.SmemView(
                0,
                name="tile",
                pool=_pool(),
                shape=(16, 64),
                dtype=wi.bf16,
                stage=1,
                stride=64,
                swizzle=_swizzle(),
                layout="row",
                alias_of="tile_base",
            ),
            id="smem-view",
        ),
        pytest.param(_phase(), id="phase-var"),
        pytest.param(
            wi.PhaseDomain(
                "main",
                "stage",
                3,
                phase_vars=(_phase(),),
                owner_role="load",
                stage_ctype="int",
                stage_init=1,
            ),
            id="phase-domain",
        ),
        pytest.param(
            wi.MmaParams(2, 4, 0, cta_group=2, tile_m=128, tile_n=64, dtype=wi.bf16),
            id="mma-params",
        ),
        pytest.param(
            wi.SoftmaxParams(128, num_load_chunks=4, num_store_chunks=2),
            id="softmax-params",
        ),
        pytest.param(
            wi.EpilogueParams(128, 8, use_tma_store=True),
            id="epilogue-params",
        ),
        pytest.param(
            wi.TmaLoadParams(
                "main",
                num_stages=3,
                src_buffers=("A",),
                dst_buffers=("tile",),
                full_barrier="full",
                empty_barrier="empty",
                stage_var="stage",
                phase_vars=("phase",),
            ),
            id="tma-load-params",
        ),
        pytest.param(wi.NamedBarrierSpec("cta", 1, 128), id="named-barrier-spec"),
        pytest.param(wi.ProcessGroup("pg", 8), id="process-group"),
        pytest.param(
            wi.SymmetricMemory("sym", wi.f32, (128,), wi.ProcessGroup("pg", 8)),
            id="symmetric-memory",
        ),
    ],
)
def test_config_and_handle_nodes_text_round_trip(node: Any) -> None:
    assert_node_roundtrip(node)


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(
            wi.TaskSpec(
                "load",
                "producer",
                "tma",
                pipeline="main",
                inputs=("A",),
                outputs=("tile",),
                depends_on=("init",),
                sync_before=("empty",),
                sync_after=("full",),
                body=_task_body(),
            ),
            id="task-spec-full",
        ),
        pytest.param(
            wi.ForLoop(
                extent=4,
                var=_v("k"),
                body=_task_body(),
                start=0,
                step=1,
                step_expr=1,
                constexpr=True,
                unroll=2,
                ctype="int",
            ),
            id="for-loop-full",
        ),
        pytest.param(wi.Block(_task_body()), id="block-scope"),
        pytest.param(wi.LeaderCtaBlock(_task_body()), id="leader-cta-block"),
        pytest.param(wi.ElectedThreadBlock(_task_body()), id="elected-thread-block"),
        pytest.param(
            wi.ConditionalIteration(wi.Const("k", wi.i32), last_expr=True, body=_task_body()),
            id="conditional-iteration",
        ),
        pytest.param(
            wi.VarDecl(
                0,
                array_size=4,
                ctype="int",
                uniform=True,
                zero_init=True,
                var=_v("stage"),
            ),
            id="var-decl",
        ),
        pytest.param(wi.Assign(wi.Const("stage", wi.i32), 1, op="+="), id="assign"),
        pytest.param(
            wi.Kernel(
                "kernel",
                [_v("m")],
                wi.i32,
                [
                    wi.TaskSpec(
                        "load",
                        "producer",
                        "tma",
                        pipeline="main",
                        body=_task_body(),
                    )
                ],
                pipeline=wi.PipelineConfig(
                    style="warp_specialized",
                    num_stages=3,
                    pipelines=(_pipeline(),),
                ),
                warps=wi.WarpConfig(8, roles=(_role(),)),
                grid=wi.GridConfig(cluster_dims=(2, 1, 1), cta_group=2),
                tmem=wi.TmemConfig(
                    buffering="double",
                    regions=(wi.TmemRegion("acc", 0, 128),),
                    total_cols=256,
                ),
                epilogue=wi.EpilogueConfig("overlapped", vectorized=True),
                buffers=(_buffer(),),
                mbarriers=(_barrier(),),
                smem_pools=(_pool(),),
                smem_views=(
                    wi.SmemView(0, name="tile", pool="pool", shape=(16, 64), dtype=wi.bf16),
                ),
                protocols=(wi.PipelineProtocol("main", load_tasks=("load",)),),
                phase_domains=(wi.PhaseDomain("main", "stage", 3, phase_vars=(_phase(),)),),
                params=(wi.ScalarParam("m", "int"),),
                constants={"BLOCK_M": 64},
                constexpr_no_default=("kStages",),
                tile_params=wi.MmaParams(2, 4, 0, dtype=wi.bf16),
                body_local_constexprs=("kTile",),
                threads_override=256,
                min_blocks=2,
                ii=1,
                pipeline_depth=3,
                task_times=(wi.TaskTiming(task="load", cycles=42),),
                barriers=(wi.BarrierEdge(producer="load", consumer="mma", barrier="full"),),
                smem_alloc=(wi.SmemAllocation(name="tile", offset=0, size=4096),),
                tmem_alloc=(wi.TmemAllocation(name="acc", start_col=0, ncols=128),),
                reg_budgets={"mma": 128},
                tma_param_ndims={"A": 2},
            ),
            id="kernel-full",
        ),
    ],
)
def test_task_scope_and_kernel_nodes_text_round_trip(node: Any) -> None:
    assert_node_roundtrip(node)


def test_kernel_derived_properties() -> None:
    kernel = wi.Kernel(
        "kernel",
        [],
        None,
        [],
        warps=wi.WarpConfig(4),
        tmem=wi.TmemConfig(regions=(wi.TmemRegion("acc", 32, 96),)),
        mbarriers=(wi.MbarrierSpec("empty", 2), wi.MbarrierSpec("full", 3)),
    )

    assert kernel.threads == 128
    assert kernel.total_mbarriers == 5
    assert kernel.tmem_max_col == 128
