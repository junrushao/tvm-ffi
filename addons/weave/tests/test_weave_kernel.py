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
"""Kernel helper property and invariant tests."""

from __future__ import annotations

import pytest
import weave  # noqa: F401
from weave.ir import (
    BarrierEdge,
    BufferRef,
    Kernel,
    MbarrierSpec,
    PhaseDomain,
    PipelineProtocol,
    SmemAllocation,
    SmemPool,
    SmemView,
    TaskTiming,
    TmemAllocation,
    TmemConfig,
    TmemRegion,
    WarpConfig,
    f32,
)


def test_kernel_threads_uses_override_before_warp_config() -> None:
    assert Kernel("k", [], None, [], warps=WarpConfig(4)).threads == 128
    assert Kernel("k", [], None, [], warps=WarpConfig(4), threads_override=64).threads == 64
    assert Kernel("k", [], None, []).threads == 0


def test_kernel_aggregate_properties() -> None:
    kernel = Kernel(
        "k",
        [],
        None,
        [],
        mbarriers=[MbarrierSpec("full", 2), MbarrierSpec("empty", 3)],
        tmem=TmemConfig(
            regions=[
                TmemRegion("acc", 0, 128),
                TmemRegion("tmp", 128, 64),
            ]
        ),
    )

    assert kernel.total_mbarriers == 5
    assert kernel.tmem_max_col == 192


def test_kernel_sequence_attrs_accept_lists_without_leaking_python_lists() -> None:
    buffer = BufferRef("A", f32, (1,))
    mbarrier = MbarrierSpec("full", 1)
    smem_pool = SmemPool("pool", 1024)
    smem_view = SmemView(0, name="tile", pool="pool", shape=(1,), dtype=f32)
    protocol = PipelineProtocol("main")
    phase_domain = PhaseDomain("main", "stage", 1)
    task_timing = TaskTiming(task="load", cycles=1)
    barrier_edge = BarrierEdge(producer="load", consumer="mma", barrier="full")
    smem_allocation = SmemAllocation(name="tile", offset=0, size=64)
    tmem_allocation = TmemAllocation(name="acc", start_col=0, ncols=16)
    kernel = Kernel(
        "k",
        [],
        None,
        [],
        buffers=[buffer],
        mbarriers=[mbarrier],
        smem_pools=[smem_pool],
        smem_views=[smem_view],
        protocols=[protocol],
        phase_domains=[phase_domain],
        constexpr_no_default=["BLOCK_M"],
        body_local_constexprs=["stage"],
        task_times=[task_timing],
        barriers=[barrier_edge],
        smem_alloc=[smem_allocation],
        tmem_alloc=[tmem_allocation],
    )

    expected_values = {
        "buffers": (buffer,),
        "mbarriers": (mbarrier,),
        "smem_pools": (smem_pool,),
        "smem_views": (smem_view,),
        "protocols": (protocol,),
        "phase_domains": (phase_domain,),
        "constexpr_no_default": ("BLOCK_M",),
        "body_local_constexprs": ("stage",),
        "task_times": (task_timing,),
        "barriers": (barrier_edge,),
        "smem_alloc": (smem_allocation,),
        "tmem_alloc": (tmem_allocation,),
    }
    for name, expected in expected_values.items():
        value = getattr(kernel, name)
        assert not isinstance(value, list), name
        assert tuple(value) == expected, name


def test_kernel_rejects_non_statement_body_entries() -> None:
    with pytest.raises(TypeError, match=r"(Kernel body expects std\.Stmt|expected ffi\.std\.Stmt)"):
        Kernel("k", [], None, [object()])
