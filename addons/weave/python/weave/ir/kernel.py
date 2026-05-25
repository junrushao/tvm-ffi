# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Top-level Weave kernel node."""

from __future__ import annotations

from typing import Any

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from .config import (
    BarrierEdge,
    EpilogueConfig,
    GridConfig,
    PipelineConfig,
    PipelineProtocol,
    SmemAllocation,
    TaskTiming,
    TmemAllocation,
    TmemConfig,
    WarpConfig,
)
from .handles import (
    BufferRef,
    MbarrierSpec,
    PhaseDomain,
    ScalarParam,
    SmemPool,
    SmemView,
    TmemRegion,
)


@dc.py_class("weave.Kernel", structural_eq="tree")
class Kernel(std.BaseFunc, mnemonic="weave.Kernel"):
    """A Weave kernel function."""

    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")
    pipeline: PipelineConfig | None = dc.field(default=None, lang_kind="attr")
    warps: WarpConfig | None = dc.field(default=None, lang_kind="attr")
    grid: GridConfig | None = dc.field(default=None, lang_kind="attr")
    tmem: TmemConfig | None = dc.field(default=None, lang_kind="attr")
    epilogue: EpilogueConfig | None = dc.field(default=None, lang_kind="attr")
    buffers: tuple[BufferRef, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    mbarriers: tuple[MbarrierSpec, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    smem_pools: tuple[SmemPool, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    smem_views: tuple[SmemView, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    protocols: tuple[PipelineProtocol, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    phase_domains: tuple[PhaseDomain, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    params: tuple[ScalarParam, ...] | None = dc.field(default=None, lang_kind="attr")
    constants: Any = dc.field(default=None, lang_kind="attr")
    constexpr_no_default: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    tile_params: std.Node | None = dc.field(default=None, lang_kind="attr")
    body_local_constexprs: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    threads_override: int | None = dc.field(default=None, lang_kind="attr")
    min_blocks: int | None = dc.field(default=None, lang_kind="attr")
    ii: int | None = dc.field(default=None, lang_kind="attr")
    pipeline_depth: int | None = dc.field(default=None, lang_kind="attr")
    task_times: tuple[TaskTiming, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    barriers: tuple[BarrierEdge, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    smem_alloc: tuple[SmemAllocation, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    tmem_alloc: tuple[TmemAllocation, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    reg_budgets: Any = dc.field(default=None, lang_kind="attr")
    tma_param_ndims: Any = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        for name in (
            "buffers",
            "mbarriers",
            "smem_pools",
            "smem_views",
            "protocols",
            "phase_domains",
            "constexpr_no_default",
            "body_local_constexprs",
            "task_times",
            "barriers",
            "smem_alloc",
            "tmem_alloc",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.params is not None:
            object.__setattr__(self, "params", tuple(self.params))
        for stmt in self.body:
            if not isinstance(stmt, std.Stmt):
                raise TypeError(f"Kernel body expects std.Stmt, got {type(stmt).__name__}")

    @property
    def threads(self) -> int:
        if self.threads_override is not None:
            return self.threads_override
        return 32 * self.warps.num_warps if self.warps is not None else 0

    @property
    def total_mbarriers(self) -> int:
        return sum(bar.count for bar in self.mbarriers)

    @property
    def tmem_max_col(self) -> int:
        regions: list[TmemRegion] = []
        if self.tmem is not None:
            regions.extend(getattr(self.tmem, "regions", ()))
        return max((region.start_col + region.ncols for region in regions), default=0)


__all__ = ["Kernel"]
