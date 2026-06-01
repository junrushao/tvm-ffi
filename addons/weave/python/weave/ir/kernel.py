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

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

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
    EpilogueParams,
    MbarrierSpec,
    MmaParams,
    PhaseDomain,
    ScalarParam,
    SmemPool,
    SmemView,
    SoftmaxParams,
    TmaLoadParams,
    TmemRegion,
)

TileParams = MmaParams | SoftmaxParams | EpilogueParams | TmaLoadParams
PrimitiveConstant = bool | int | float | str


def _normalize_constants(
    value: Mapping[str, PrimitiveConstant] | None,
) -> dict[str, PrimitiveConstant]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("constants must be a mapping from str to primitive constants")
    result: dict[str, PrimitiveConstant] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"constants keys must be strings, got {key!r}")
        if type(item) not in (bool, int, float, str):
            raise TypeError(f"constants[{key!r}] must be a primitive constant")
        result[key] = item
    return result


def _normalize_int_map(value: Mapping[str, int] | None, *, field_name: str) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping from str to int")
    result: dict[str, int] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"{field_name} keys must be strings, got {key!r}")
        if isinstance(item, bool) or not isinstance(item, int):
            raise TypeError(f"{field_name}[{key!r}] must be an integer constant")
        result[key] = item
    return result


@dc.py_class("weave.Kernel", structural_eq="tree", kw_only=True)
class Kernel(std.BaseFunc, mnemonic="weave.Kernel"):
    """A Weave kernel function."""

    body: list[std.Stmt] = dc.field(default_factory=list, kw_only=False, lang_kind="body")
    if TYPE_CHECKING:
        constants: dict[str, PrimitiveConstant]
    else:
        constants: dict = dc.field(default_factory=dict, kw_only=True, lang_kind="attr")
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
    params: tuple[ScalarParam, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    constexpr_no_default: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    tile_params: TileParams | None = dc.field(default=None, lang_kind="attr")
    body_local_constexprs: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    threads_override: int | None = dc.field(default=None, lang_kind="attr")
    min_blocks: int | None = dc.field(default=None, lang_kind="attr")
    ii: int | None = dc.field(default=None, lang_kind="attr")
    pipeline_depth: int | None = dc.field(default=None, lang_kind="attr")
    task_times: tuple[TaskTiming, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    barriers: tuple[BarrierEdge, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    smem_alloc: tuple[SmemAllocation, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    tmem_alloc: tuple[TmemAllocation, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    if TYPE_CHECKING:
        reg_budgets: dict[str, int]
        tma_param_ndims: dict[str, int]
    else:
        reg_budgets: dict = dc.field(default_factory=dict, lang_kind="attr")
        tma_param_ndims: dict = dc.field(default_factory=dict, lang_kind="attr")

    def __init__(
        self,
        symbol: str = "",
        args: Sequence[std.Var] | None = None,
        ret_type: std.TyLike | None = None,
        body: Sequence[std.Stmt] | None = None,
        *,
        constants: Mapping[str, PrimitiveConstant] | None = None,
        pipeline: PipelineConfig | None = None,
        warps: WarpConfig | None = None,
        grid: GridConfig | None = None,
        tmem: TmemConfig | None = None,
        epilogue: EpilogueConfig | None = None,
        buffers: Sequence[BufferRef] = (),
        mbarriers: Sequence[MbarrierSpec] = (),
        smem_pools: Sequence[SmemPool] = (),
        smem_views: Sequence[SmemView] = (),
        protocols: Sequence[PipelineProtocol] = (),
        phase_domains: Sequence[PhaseDomain] = (),
        params: Sequence[ScalarParam] = (),
        constexpr_no_default: Sequence[str] = (),
        tile_params: TileParams | None = None,
        body_local_constexprs: Sequence[str] = (),
        threads_override: int | None = None,
        min_blocks: int | None = None,
        ii: int | None = None,
        pipeline_depth: int | None = None,
        task_times: Sequence[TaskTiming] = (),
        barriers: Sequence[BarrierEdge] = (),
        smem_alloc: Sequence[SmemAllocation] = (),
        tmem_alloc: Sequence[TmemAllocation] = (),
        reg_budgets: Mapping[str, int] | None = None,
        tma_param_ndims: Mapping[str, int] | None = None,
    ) -> None:
        self.__ffi_init__(
            symbol,
            list(args or ()),
            std.normalize_ty(ret_type) if ret_type is not None else None,
            list(body or ()),
            constants=_normalize_constants(constants),
            pipeline=pipeline,
            warps=warps,
            grid=grid,
            tmem=tmem,
            epilogue=epilogue,
            buffers=tuple(buffers),
            mbarriers=tuple(mbarriers),
            smem_pools=tuple(smem_pools),
            smem_views=tuple(smem_views),
            protocols=tuple(protocols),
            phase_domains=tuple(phase_domains),
            params=tuple(params),
            constexpr_no_default=tuple(constexpr_no_default),
            tile_params=tile_params,
            body_local_constexprs=tuple(body_local_constexprs),
            threads_override=threads_override,
            min_blocks=min_blocks,
            ii=ii,
            pipeline_depth=pipeline_depth,
            task_times=tuple(task_times),
            barriers=tuple(barriers),
            smem_alloc=tuple(smem_alloc),
            tmem_alloc=tuple(tmem_alloc),
            reg_budgets=_normalize_int_map(reg_budgets, field_name="reg_budgets"),
            tma_param_ndims=_normalize_int_map(tma_param_ndims, field_name="tma_param_ndims"),
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        self.constants = _normalize_constants(self.constants)
        self.reg_budgets = _normalize_int_map(self.reg_budgets, field_name="reg_budgets")
        self.tma_param_ndims = _normalize_int_map(
            self.tma_param_ndims, field_name="tma_param_ndims"
        )
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
