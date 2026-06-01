# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Top-level Weave configuration nodes."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from ._utils import validate_candidate_value, validate_cta_group
from .handles import TmemRegion

PIPELINE_STYLES = ("sequential", "sw_pipelined", "warp_specialized", "none")
EPILOGUE_STYLES = ("inline", "overlapped")
TMEM_BUFFERING = ("single", "double")


@dc.py_class("weave.WarpRole", structural_eq="tree")
class WarpRole(std.Attrs, mnemonic="weave.WarpRole"):
    """Named warp role with assigned warp ids."""

    name: str = dc.field(lang_kind="attr")
    warp_ids: tuple[int, ...] = dc.field(lang_kind="attr")
    register_budget: int | None = dc.field(default=None, lang_kind="attr")
    auto_warp_vars: bool = dc.field(default=False, lang_kind="attr")
    tmem_var_regions: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    warp_group_size: int = dc.field(default=0, lang_kind="attr")
    instances: int = dc.field(default=1, lang_kind="attr")

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("WarpRole.name must be non-empty")
        if self.instances <= 0:
            raise ValueError("instances must be positive")


@dc.py_class("weave.Pipeline", structural_eq="tree")
class PipelineSpec(std.Attrs, mnemonic="weave.Pipeline"):
    """Named pipeline configuration."""

    name: str = dc.field(lang_kind="attr")
    num_stages: int = dc.field(lang_kind="attr")
    style: str = dc.field(default="sequential", lang_kind="attr")
    smem_buffers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    cta_group: int = dc.field(default=1, lang_kind="attr")
    producer_barriers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    consumer_barriers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    release_barriers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    smem_region: str = dc.field(default="", lang_kind="attr")
    kparam_name: str = dc.field(default="", lang_kind="attr")

    def __init__(
        self,
        name: str,
        num_stages: int,
        style: str = "sequential",
        smem_buffers: tuple[str, ...] = (),
        cta_group: int = 1,
        producer_barriers: tuple[str, ...] = (),
        consumer_barriers: tuple[str, ...] = (),
        release_barriers: tuple[str, ...] = (),
        smem_region: str = "",
        kparam_name: str = "",
    ) -> None:
        style = validate_candidate_value(style, PIPELINE_STYLES, field_name="style")
        if num_stages <= 0:
            raise ValueError("num_stages must be positive")
        cta_group = validate_cta_group(cta_group)
        self.__ffi_init__(
            name,
            num_stages,
            style,
            smem_buffers,
            cta_group,
            producer_barriers,
            consumer_barriers,
            release_barriers,
            smem_region,
            kparam_name,
        )


@dc.py_class("weave.PipelineConfig", structural_eq="tree")
class PipelineConfig(std.Attrs, mnemonic="weave.PipelineConfig"):
    """Legacy or multi-pipeline configuration."""

    style: str = dc.field(default="sequential", lang_kind="attr")
    num_stages: int = dc.field(default=1, lang_kind="attr")
    pipelines: tuple[PipelineSpec, ...] = dc.field(default_factory=tuple, lang_kind="attr")

    def __post_init__(self) -> None:
        self.style = validate_candidate_value(self.style, PIPELINE_STYLES, field_name="style")
        if self.num_stages <= 0:
            raise ValueError("num_stages must be positive")


@dc.py_class("weave.WarpConfig", structural_eq="tree")
class WarpConfig(std.Attrs, mnemonic="weave.WarpConfig"):
    """Warp topology configuration."""

    num_warps: int = dc.field(lang_kind="attr")
    roles: tuple[WarpRole, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    tma_warp: int | None = dc.field(default=None, lang_kind="attr")
    mma_warp: int | None = dc.field(default=None, lang_kind="attr")
    epilogue_warps: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")

    def __post_init__(self) -> None:
        if self.num_warps <= 0:
            raise ValueError("num_warps must be positive")


@dc.py_class("weave.GridConfig", structural_eq="tree")
class GridConfig(std.Attrs, mnemonic="weave.GridConfig"):
    """Grid and cluster topology."""

    cluster_dims: tuple[int, int, int] = dc.field(default=(1, 1, 1), lang_kind="attr")
    cta_group: int = dc.field(default=1, lang_kind="attr")

    def __init__(
        self,
        cluster_dims: tuple[int, int, int] = (1, 1, 1),
        cta_group: int = 1,
    ) -> None:
        if len(cluster_dims) != 3:
            raise ValueError("cluster_dims must have 3 entries")
        self.__ffi_init__(cluster_dims, validate_cta_group(cta_group))


@dc.py_class("weave.TmemConfig", structural_eq="tree")
class TmemConfig(std.Attrs, mnemonic="weave.TmemConfig"):
    """Tensor-memory allocation configuration."""

    buffering: str = dc.field(default="single", lang_kind="attr")
    regions: tuple[TmemRegion, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    total_cols: int = dc.field(default=512, lang_kind="attr")
    allocator_warp: int | None = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        self.buffering = validate_candidate_value(
            self.buffering, TMEM_BUFFERING, field_name="buffering"
        )
        if self.total_cols <= 0:
            raise ValueError("total_cols must be positive")


@dc.py_class("weave.EpilogueConfig", structural_eq="tree")
class EpilogueConfig(std.Attrs, mnemonic="weave.EpilogueConfig"):
    """Epilogue execution configuration."""

    style: str = dc.field(default="inline", lang_kind="attr")
    vectorized: bool = dc.field(default=False, lang_kind="attr")
    num_epilogue_warps: int = dc.field(default=0, lang_kind="attr")

    def __post_init__(self) -> None:
        self.style = validate_candidate_value(self.style, EPILOGUE_STYLES, field_name="style")
        if self.num_epilogue_warps < 0:
            raise ValueError("num_epilogue_warps must be non-negative")


@dc.py_class("weave.PipelineProtocol", structural_eq="tree")
class PipelineProtocol(std.Attrs, mnemonic="weave.PipelineProtocol"):
    """Pipeline fill/steady/drain protocol."""

    pipeline: str = dc.field(lang_kind="attr")
    load_tasks: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    compute_tasks: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    empty_barrier: str = dc.field(default="", lang_kind="attr")
    full_barrier: str = dc.field(default="", lang_kind="attr")


@dc.py_class("weave.TaskTiming", structural_eq="tree")
class TaskTiming(std.Attrs, mnemonic="weave.TaskTiming"):
    """Estimated task timing metadata."""

    task: str = dc.field(default="", lang_kind="attr")
    cycles: int = dc.field(default=0, lang_kind="attr")


@dc.py_class("weave.BarrierEdge", structural_eq="tree")
class BarrierEdge(std.Attrs, mnemonic="weave.BarrierEdge"):
    """Barrier dependency edge metadata."""

    producer: str = dc.field(default="", lang_kind="attr")
    consumer: str = dc.field(default="", lang_kind="attr")
    barrier: str = dc.field(default="", lang_kind="attr")


@dc.py_class("weave.SmemAllocation", structural_eq="tree")
class SmemAllocation(std.Attrs, mnemonic="weave.SmemAllocation"):
    """Shared-memory allocation metadata."""

    name: str = dc.field(default="", lang_kind="attr")
    offset: int = dc.field(default=0, lang_kind="attr")
    size: int = dc.field(default=0, lang_kind="attr")


@dc.py_class("weave.TmemAllocation", structural_eq="tree")
class TmemAllocation(std.Attrs, mnemonic="weave.TmemAllocation"):
    """Tensor-memory allocation metadata."""

    name: str = dc.field(default="", lang_kind="attr")
    start_col: int = dc.field(default=0, lang_kind="attr")
    ncols: int = dc.field(default=0, lang_kind="attr")


__all__ = [
    "BarrierEdge",
    "EpilogueConfig",
    "GridConfig",
    "PipelineConfig",
    "PipelineProtocol",
    "PipelineSpec",
    "SmemAllocation",
    "TaskTiming",
    "TmemAllocation",
    "TmemConfig",
    "WarpConfig",
    "WarpRole",
]
