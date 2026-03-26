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
"""Operation-level Weave text round-trip tests."""

from __future__ import annotations

from typing import Any

import pytest
import weave  # noqa: F401  # Registers the Weave dialect.
import weave.ir as wi
from _roundtrip import assert_node_roundtrip
from tvm_ffi import std


def _v(name: str, ty: std.Ty | None = None) -> std.Var:
    return std.Var(ty or wi.i32, name)


def _region() -> wi.TmemRegion:
    return wi.TmemRegion("acc", 0, 128, num_buffers=2, dtype=wi.f32)


def _barrier() -> wi.MbarrierSpec:
    return wi.MbarrierSpec(
        "full",
        2,
        producers=("load",),
        consumers=("compute",),
        signaling_mode="all_warps",
    )


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(wi.BuiltinVar("warp_in_role", dst=1), id="builtin-var"),
        pytest.param(
            wi.TmemRegionLoad(
                _region(),
                dst=1,
                col_offset=2,
                num=32,
                dst_offset=4,
                wait=False,
                row_base=8,
            ),
            id="tmem-region-load-full",
        ),
        pytest.param(
            wi.TmemRegionStore(_region(), src=1, col_offset=2, num=16, dtype=wi.f32, row_base=8),
            id="tmem-region-store-full",
        ),
        pytest.param(
            wi.SmemDesc("tile", k_idx=0, mode="mn", dst=1, step=2, offset=3),
            id="smem-desc-full",
        ),
        pytest.param(
            wi.GmemLoad(1, 2, count=8, dtype=wi.bf16, dst_dtype=wi.f32, dst_offset=3, index=4),
            id="gmem-load-full",
        ),
        pytest.param(
            wi.GmemStore(
                1,
                2,
                count=8,
                dtype=wi.bf16,
                src_dtype=wi.f32,
                src_offset=3,
                index=4,
                scale=5,
                cache_hint="evict_last",
            ),
            id="gmem-store-full",
        ),
        pytest.param(wi.SmemStore(1, 2, predicate=True, index=0), id="smem-store-full"),
        pytest.param(wi.SmemLoad(1, 2), id="smem-load"),
        pytest.param(wi.SmemRead(1, dst=2, index=0), id="smem-read-full"),
        pytest.param(wi.SmemLoadRegs("regs", 1, count=4, dtype=wi.f32), id="smem-load-regs"),
        pytest.param(wi.SmemWrite(1, 2, index=0), id="smem-write-full"),
        pytest.param(wi.SmemLoadVec(1, 2, count=4, dst_offset=8), id="smem-load-vec-full"),
        pytest.param(wi.SmemStoreVec(1, 2), id="smem-store-vec"),
        pytest.param(wi.TmaStore(1, 2), id="tma-store"),
        pytest.param(wi.TmaReduceOp(1, 2, op="max"), id="tma-reduce-op"),
        pytest.param(
            wi.TmaGatherLoad(1, 2, 3, tokens_per_page=128, mbar_expr=4, token_offset=5),
            id="tma-gather-load-full",
        ),
        pytest.param(
            wi.ScaleFactorCopy(1, 2, cta_group=2, sbo=128, elected=True),
            id="scale-factor-copy-full",
        ),
        pytest.param(wi.MetadataCopy(1, 2, cta_group=2), id="metadata-copy-full"),
    ],
)
def test_memory_ops_text_round_trip(node: Any) -> None:
    assert_node_roundtrip(node)


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(wi.Elementwise(op="fma", inputs=[1, 2, 3], output=4), id="elementwise"),
        pytest.param(
            wi.PredicatedStore(1, 2, bound_m=3, bound_n=4, tile_offset_m=5, tile_offset_n=6),
            id="predicated-store",
        ),
        pytest.param(wi.ThreshMask(1, 32, width=16), id="thresh-mask"),
        pytest.param(
            wi.BitmaskFill(1, 2, fill_value=3, offset=4, count=16),
            id="bitmask-fill-full",
        ),
        pytest.param(wi.MaskFill(1, 0, size=8, lo=2, hi=6), id="mask-fill-full"),
        pytest.param(
            wi.RegArrayCast(1, 2, src_dtype=wi.i8, dst_dtype=wi.bf16, count=4, offset=8),
            id="reg-array-cast-full",
        ),
    ],
)
def test_elementwise_and_mask_ops_text_round_trip(node: Any) -> None:
    assert_node_roundtrip(node)


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(wi.BarrierSync(barrier_id=1), id="barrier-sync"),
        pytest.param(
            wi.BarrierTryWait(_barrier(), 0, 1, _v("tok"), stage_is_deterministic=False),
            id="barrier-try-wait-var-def",
        ),
        pytest.param(
            wi.BarrierWait(_barrier(), 0, 1, token=2, stage_is_deterministic=False),
            id="barrier-wait-full",
        ),
        pytest.param(
            wi.BarrierSignal(
                _barrier(),
                "arrive_expect_tx",
                0,
                tx_bytes=128,
                arrive_count=2,
                cta_group=2,
                cluster=True,
                elected=True,
                transaction_group="tma",
            ),
            id="barrier-signal-full",
        ),
        pytest.param(wi.MBarrierArrive(1), id="mbarrier-arrive"),
        pytest.param(
            wi.PeerArriveCommit(_barrier(), 0, cta_group=2, elected=True), id="peer-arrive"
        ),
        pytest.param(
            wi.MulticastCommit(_barrier(), 0, 3, cta_group=2, elected=True),
            id="multicast-commit",
        ),
        pytest.param(wi.DualCommit(_barrier(), _barrier(), 0, 1, cta_group=2), id="dual-commit"),
        pytest.param(wi.Fence(kind="before_thread_sync"), id="fence"),
        pytest.param(wi.ThreadFence(scope="system"), id="thread-fence"),
        pytest.param(wi.ClusterSync(), id="cluster-sync"),
        pytest.param(wi.GridSync(), id="grid-sync"),
        pytest.param(wi.GridDepSync(), id="grid-dep-sync"),
        pytest.param(wi.GridDepLaunch(), id="grid-dep-launch"),
        pytest.param(wi.ClusterMapa(1, 2, _v("remote", wi.u32)), id="cluster-mapa-var-def"),
        pytest.param(
            wi.ClusterBarrierArrive(1, tx_count=16, peer_rank=0), id="cluster-barrier-arrive"
        ),
        pytest.param(
            wi.CpAsyncBulkSmem2SmemCluster(1, 2, 16, barrier=_barrier(), mbar_addr=3),
            id="cp-async-bulk-smem-to-smem-cluster",
        ),
        pytest.param(wi.WarpReduce(1, op="max", dst=_v("warp_max", wi.f32)), id="warp-reduce"),
        pytest.param(wi.BlockReduce(1, 2, op="min"), id="block-reduce"),
        pytest.param(
            wi.CrossWarpReduce(1, 2, _v("cw", wi.f32), op="max", finalize="rsqrt"),
            id="cross-warp-reduce",
        ),
        pytest.param(
            wi.WarpGroupReduce(1, 2, _v("wg", wi.f32), op="min", num_warp_groups=4),
            id="warp-group-reduce",
        ),
        pytest.param(
            wi.StAsync(1, srcs=[2, 3, 4, 5], bytes=16, barrier=6, src_is_int=True),
            id="st-async-full",
        ),
    ],
)
def test_barrier_sync_and_reduction_ops_text_round_trip(node: Any) -> None:
    assert_node_roundtrip(node)


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(
            wi.Tcgen05Cp(1, 2, shape="128x256b", cta_group=2, sbo=256, elected=True),
            id="tcgen05-cp-full",
        ),
        pytest.param(wi.PackedF32x2("fma", inputs=[1, 2, 3], output=4), id="packed-f32x2"),
        pytest.param(
            wi.FragmentOp("cvt_f32", 1, srcs=[2, 3], size=16, dtype=wi.f32), id="fragment-op"
        ),
        pytest.param(
            wi.MmaTile(
                1,
                2,
                3,
                k_idx=0,
                mode="ss",
                cta_group=2,
                a_dtype=wi.bf16,
                b_dtype=wi.bf16,
                acc_dtype=wi.f32,
            ),
            id="mma-tile",
        ),
        pytest.param(wi.AtomicOp("add", 1, 2, space="gmem", index=0, dtype=wi.f32), id="atomic-op"),
        pytest.param(wi.AtomicFetchAdd(1, 2, 3, index=4, dtype=wi.u32), id="atomic-fetch-add"),
        pytest.param(wi.RelaxedFmax(1, 2, space="smem"), id="relaxed-fmax"),
        pytest.param(wi.AtomicMaxF32Positive(1, 2, index=0, dst=3), id="atomic-max-f32-positive"),
        pytest.param(wi.SysVolatileLoad128(1, 2), id="sys-volatile-load-128"),
        pytest.param(wi.SysVolatileStore128(1, 2), id="sys-volatile-store-128"),
        pytest.param(wi.MultimemLdReduce(1, 2, payload="bf16x8"), id="multimem-ld-reduce"),
        pytest.param(wi.MultimemStore(1, 2, payload="f32x4"), id="multimem-store"),
        pytest.param(
            wi.MultimemRedAddI32(1, 2, sem="relaxed", scope="gpu"), id="multimem-red-add-i32"
        ),
        pytest.param(wi.AtomicMaxFloatEncode(1, 2), id="atomic-max-float-encode"),
        pytest.param(wi.AtomicMaxFloatDecode(1, 2), id="atomic-max-float-decode"),
        pytest.param(wi.ClcTryCancel(1, 2, multicast=True), id="clc-try-cancel"),
        pytest.param(wi.ClcQueryCancel(1, 2), id="clc-query-cancel"),
        pytest.param(wi.ClcQueryCancelGetCtaId(1, 2, dim="y"), id="clc-query-cancel-get-cta-id"),
        pytest.param(wi.ClcFenceRelease(), id="clc-fence-release"),
    ],
)
def test_mma_atomic_multimem_and_clc_ops_text_round_trip(node: Any) -> None:
    assert_node_roundtrip(node)


@pytest.mark.parametrize("mode", ["ss", "sr", "rs", "rr"])
def test_mma_tile_valid_modes_text_round_trip(mode: str) -> None:
    assert_node_roundtrip(
        wi.MmaTile(
            1,
            2,
            3,
            k_idx=0,
            mode=mode,
            a_dtype=wi.bf16,
            b_dtype=wi.bf16,
            acc_dtype=wi.f32,
        )
    )
