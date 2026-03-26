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

from typing import Any

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from ._utils import normalize_domain, validate_cta_group
from .handles import TmemRegion

PIPELINE_STYLES = ("sequential", "sw_pipelined", "warp_specialized", "none")
EPILOGUE_STYLES = ("inline", "overlapped")
TMEM_BUFFERING = ("single", "double")


@dc.py_class("weave.WarpRole", structural_eq="tree")
class WarpRole(std.Node, mnemonic="weave.WarpRole"):
    """Named warp role with assigned warp ids."""

    name: str = dc.field(lang_kind="arg")
    warp_ids: tuple[int, ...] = dc.field(lang_kind="attr")
    register_budget: int | None = dc.field(default=None, lang_kind="attr")
    auto_warp_vars: bool = dc.field(default=False, lang_kind="attr")
    tmem_var_regions: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    warp_group_size: int = dc.field(default=0, lang_kind="attr")
    instances: int = dc.field(default=1, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "warp_ids", tuple(self.warp_ids))
        object.__setattr__(self, "tmem_var_regions", tuple(self.tmem_var_regions))
        if not self.name:
            raise ValueError("WarpRole.name must be non-empty")
        if self.instances <= 0:
            raise ValueError("instances must be positive")


@dc.py_class("weave.Pipeline", structural_eq="tree")
class PipelineSpec(std.Node, mnemonic="weave.Pipeline"):
    """Named pipeline configuration."""

    name: str = dc.field(lang_kind="arg")
    num_stages: int = dc.field(lang_kind="arg")
    style: str = dc.field(default="sequential", lang_kind="attr")
    smem_buffers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    cta_group: Any = dc.field(default=1, lang_kind="attr")
    producer_barriers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    consumer_barriers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    release_barriers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    smem_region: str = dc.field(default="", lang_kind="attr")
    kparam_name: str = dc.field(default="", lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "style", normalize_domain(self.style, PIPELINE_STYLES, field_name="style")
        )
        for name in ("smem_buffers", "producer_barriers", "consumer_barriers", "release_barriers"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.num_stages <= 0:
            raise ValueError("num_stages must be positive")
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))


@dc.py_class("weave.PipelineConfig", structural_eq="tree")
class PipelineConfig(std.Node, mnemonic="weave.PipelineConfig"):
    """Legacy or multi-pipeline configuration."""

    style: str = dc.field(default="sequential", lang_kind="attr")
    num_stages: int = dc.field(default=1, lang_kind="attr")
    pipelines: tuple[PipelineSpec, ...] = dc.field(default_factory=tuple, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "style", normalize_domain(self.style, PIPELINE_STYLES, field_name="style")
        )
        object.__setattr__(self, "pipelines", tuple(self.pipelines))
        if self.num_stages <= 0:
            raise ValueError("num_stages must be positive")


@dc.py_class("weave.WarpConfig", structural_eq="tree")
class WarpConfig(std.Node, mnemonic="weave.WarpConfig"):
    """Warp topology configuration."""

    num_warps: int = dc.field(lang_kind="arg")
    roles: tuple[WarpRole, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    tma_warp: int | None = dc.field(default=None, lang_kind="attr")
    mma_warp: int | None = dc.field(default=None, lang_kind="attr")
    epilogue_warps: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", tuple(self.roles))
        object.__setattr__(self, "epilogue_warps", tuple(self.epilogue_warps))
        if self.num_warps <= 0:
            raise ValueError("num_warps must be positive")


@dc.py_class("weave.GridConfig", structural_eq="tree")
class GridConfig(std.Node, mnemonic="weave.GridConfig"):
    """Grid and cluster topology."""

    cluster_dims: tuple[int, int, int] = dc.field(default=(1, 1, 1), lang_kind="attr")
    cta_group: Any = dc.field(default=1, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "cluster_dims", tuple(self.cluster_dims))
        if len(self.cluster_dims) != 3:
            raise ValueError("cluster_dims must have 3 entries")
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))


@dc.py_class("weave.TmemConfig", structural_eq="tree")
class TmemConfig(std.Node, mnemonic="weave.TmemConfig"):
    """Tensor-memory allocation configuration."""

    buffering: str = dc.field(default="single", lang_kind="attr")
    regions: tuple[TmemRegion, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    total_cols: int = dc.field(default=512, lang_kind="attr")
    allocator_warp: int | None = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "buffering",
            normalize_domain(self.buffering, TMEM_BUFFERING, field_name="buffering"),
        )
        object.__setattr__(self, "regions", tuple(self.regions))
        if self.total_cols <= 0:
            raise ValueError("total_cols must be positive")


@dc.py_class("weave.EpilogueConfig", structural_eq="tree")
class EpilogueConfig(std.Node, mnemonic="weave.EpilogueConfig"):
    """Epilogue execution configuration."""

    style: str = dc.field(default="inline", lang_kind="arg")
    vectorized: bool = dc.field(default=False, lang_kind="attr")
    num_epilogue_warps: int = dc.field(default=0, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "style", normalize_domain(self.style, EPILOGUE_STYLES, field_name="style")
        )
        if self.num_epilogue_warps < 0:
            raise ValueError("num_epilogue_warps must be non-negative")


@dc.py_class("weave.PipelineProtocol", structural_eq="tree")
class PipelineProtocol(std.Node, mnemonic="weave.PipelineProtocol"):
    """Pipeline fill/steady/drain protocol."""

    pipeline: str = dc.field(lang_kind="arg")
    load_tasks: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    compute_tasks: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    empty_barrier: str = dc.field(default="", lang_kind="attr")
    full_barrier: str = dc.field(default="", lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "load_tasks", tuple(self.load_tasks))
        object.__setattr__(self, "compute_tasks", tuple(self.compute_tasks))


@dc.py_class("weave.TaskTiming", structural_eq="tree")
class TaskTiming(std.Node, mnemonic="weave.TaskTiming"):
    """Estimated task timing metadata."""

    task: str = dc.field(default="", lang_kind="attr")
    cycles: int = dc.field(default=0, lang_kind="attr")


@dc.py_class("weave.BarrierEdge", structural_eq="tree")
class BarrierEdge(std.Node, mnemonic="weave.BarrierEdge"):
    """Barrier dependency edge metadata."""

    producer: str = dc.field(default="", lang_kind="attr")
    consumer: str = dc.field(default="", lang_kind="attr")
    barrier: str = dc.field(default="", lang_kind="attr")


@dc.py_class("weave.SmemAllocation", structural_eq="tree")
class SmemAllocation(std.Node, mnemonic="weave.SmemAllocation"):
    """Shared-memory allocation metadata."""

    name: str = dc.field(default="", lang_kind="attr")
    offset: int = dc.field(default=0, lang_kind="attr")
    size: int = dc.field(default=0, lang_kind="attr")


@dc.py_class("weave.TmemAllocation", structural_eq="tree")
class TmemAllocation(std.Node, mnemonic="weave.TmemAllocation"):
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
