# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Weave handle and metadata nodes."""

from __future__ import annotations

from typing import Any

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from ._utils import normalize_domain, normalize_dtype, validate_cta_group
from .dtypes import StringLike, Swizzle

ShapeDim = int | StringLike | std.Expr
ExprOrInt = int | std.Expr
SwizzleSpec = StringLike | Swizzle | None

SIGNALING_MODES = ("elected", "hw_commit", "all_warps", "tma_expect_tx")
MEMORY_SPACES = ("gmem", "smem", "tmem", "regs", "local", "param", "symm")


@dc.py_class("weave.TmemRegion", structural_eq="tree")
class TmemRegion(std.Node, mnemonic="weave.TmemRegion"):
    """Named tensor-memory column region."""

    name: str = dc.field(lang_kind="arg")
    start_col: int = dc.field(lang_kind="arg")
    ncols: int = dc.field(lang_kind="arg")
    num_buffers: int = dc.field(default=1, lang_kind="attr")
    kparam_name: str = dc.field(default="", lang_kind="attr")
    var_name: str = dc.field(default="", lang_kind="attr")
    dtype: Any = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))
        if self.start_col < 0 or self.ncols <= 0 or self.num_buffers <= 0:
            raise ValueError("invalid TMEM region extent")


@dc.py_class("weave.Mbarrier", structural_eq="tree")
class MbarrierSpec(std.Node, mnemonic="weave.Mbarrier"):
    """Mbarrier group specification."""

    role: str = dc.field(lang_kind="arg")
    count: int = dc.field(lang_kind="arg")
    init_count: int = dc.field(default=0, lang_kind="attr")
    producers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    consumers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    signaling_mode: str | None = dc.field(default=None, lang_kind="attr")
    producer_warps: int = dc.field(default=0, lang_kind="attr")
    stage_var: str = dc.field(default="", lang_kind="attr")
    pipeline: str = dc.field(default="", lang_kind="attr")
    init_phase: int = dc.field(default=0, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "producers", tuple(self.producers))
        object.__setattr__(self, "consumers", tuple(self.consumers))
        if self.count <= 0:
            raise ValueError("count must be positive")
        if self.init_phase not in (0, 1):
            raise ValueError("init_phase must be 0 or 1")
        if self.signaling_mode is not None:
            object.__setattr__(
                self,
                "signaling_mode",
                normalize_domain(self.signaling_mode, SIGNALING_MODES, field_name="signaling_mode"),
            )

    def derived_init_count(self) -> int:
        """Return explicit or signaling-derived arrival count."""
        if self.init_count > 0:
            return self.init_count
        if self.signaling_mode == "all_warps":
            return max(self.producer_warps, 1)
        return 1


@dc.py_class("weave.TmaDescriptor", structural_eq="tree")
class TmaDescriptor(std.Node, mnemonic="weave.TmaDescriptor"):
    """TMA tensor map descriptor."""

    ndim: int = dc.field(lang_kind="arg")
    box_shape: tuple[ShapeDim, ...] = dc.field(lang_kind="attr")
    swizzle: SwizzleSpec = dc.field(default="128B", lang_kind="attr")
    global_shape: tuple[StringLike, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    global_strides: tuple[StringLike, ...] = dc.field(default_factory=tuple, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "box_shape", tuple(self.box_shape))
        object.__setattr__(self, "global_shape", tuple(self.global_shape))
        object.__setattr__(self, "global_strides", tuple(self.global_strides))
        if self.ndim <= 0:
            raise ValueError("ndim must be positive")
        if len(self.box_shape) != self.ndim:
            raise ValueError("box_shape length must match ndim")


@dc.py_class("weave.Buffer", structural_eq="tree")
class BufferRef(std.Node, mnemonic="weave.Buffer"):
    """Typed memory buffer reference."""

    name: str = dc.field(lang_kind="arg")
    dtype: Any = dc.field(lang_kind="arg")
    shape: tuple[ShapeDim, ...] = dc.field(lang_kind="attr")
    space: str = dc.field(default="gmem", lang_kind="attr")
    tmem_col: int | None = dc.field(default=None, lang_kind="attr")
    smem_offset: int | None = dc.field(default=None, lang_kind="attr")
    swizzle: SwizzleSpec = dc.field(default=None, lang_kind="attr")
    stage: int | None = dc.field(default=None, lang_kind="attr")
    tma: TmaDescriptor | None = dc.field(default=None, lang_kind="attr")
    source_gmem: str = dc.field(default="", lang_kind="attr")
    scale_buffer: str = dc.field(default="", lang_kind="attr")
    align: int = dc.field(default=1, lang_kind="attr")
    volatile: bool = dc.field(default=False, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))
        object.__setattr__(self, "shape", tuple(self.shape))
        object.__setattr__(
            self, "space", normalize_domain(self.space, MEMORY_SPACES, field_name="space")
        )
        if self.align <= 0:
            raise ValueError("align must be positive")


@dc.py_class("weave.Param", structural_eq="tree")
class ScalarParam(std.Node, mnemonic="weave.Param"):
    """Scalar kernel parameter."""

    name: str = dc.field(lang_kind="arg")
    ctype: str = dc.field(lang_kind="arg")


@dc.py_class("weave.SmemPool", structural_eq="tree")
class SmemPool(std.Node, mnemonic="weave.SmemPool"):
    """Named shared-memory pool."""

    name: str = dc.field(lang_kind="arg")
    size: int = dc.field(lang_kind="arg")

    def __post_init__(self) -> None:
        if self.size < 0:
            raise ValueError("size must be non-negative")


@dc.py_class("weave.SmemView", structural_eq="tree")
class SmemView(std.Node, mnemonic="weave.SmemView"):
    """View into a shared-memory pool."""

    name: str = dc.field(lang_kind="arg")
    pool: SmemPool | StringLike = dc.field(lang_kind="arg")
    offset: ExprOrInt = dc.field(lang_kind="arg")
    shape: tuple[ShapeDim, ...] = dc.field(lang_kind="attr")
    dtype: Any = dc.field(lang_kind="attr")
    stage: int | None = dc.field(default=None, lang_kind="attr")
    stride: ExprOrInt | None = dc.field(default=None, lang_kind="attr")
    swizzle: SwizzleSpec = dc.field(default=None, lang_kind="attr")
    layout: str = dc.field(default="", lang_kind="attr")
    alias_of: str = dc.field(default="", lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "shape", tuple(self.shape))
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))


@dc.py_class("weave.PhaseVar", structural_eq="tree")
class PhaseVar(std.Node, mnemonic="weave.PhaseVar"):
    """Rotating phase variable metadata."""

    name: str = dc.field(lang_kind="arg")
    dtype: Any = dc.field(default_factory=lambda: std.PrimTy("int32"), lang_kind="attr")
    init_value: ExprOrInt = dc.field(default=0, lang_kind="attr")
    rotation_rule: str = dc.field(default="", lang_kind="attr")
    rotation_trigger: str = dc.field(default="", lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))


@dc.py_class("weave.PhaseDomain", structural_eq="tree")
class PhaseDomain(std.Node, mnemonic="weave.PhaseDomain"):
    """Pipeline phase domain."""

    pipeline: str = dc.field(lang_kind="arg")
    stage_var: str = dc.field(lang_kind="arg")
    num_stages: int = dc.field(lang_kind="arg")
    phase_vars: tuple[PhaseVar, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    owner_role: str = dc.field(default="", lang_kind="attr")
    stage_ctype: str = dc.field(default="int", lang_kind="attr")
    stage_init: int = dc.field(default=0, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "phase_vars", tuple(self.phase_vars))
        if self.num_stages <= 0:
            raise ValueError("num_stages must be positive")


@dc.py_class("weave.MmaParams", structural_eq="tree")
class MmaParams(std.Aggregate, mnemonic="weave.MmaParams"):
    """MMA loop parameter bundle."""

    k_steps_per_group: int = dc.field(lang_kind="arg")
    k_groups: int = dc.field(lang_kind="arg")
    group_lo_offset: int = dc.field(lang_kind="arg")
    cta_group: Any = dc.field(default=1, lang_kind="attr")
    tile_m: int = dc.field(default=0, lang_kind="attr")
    tile_n: int = dc.field(default=0, lang_kind="attr")
    dtype: Any = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))
        if self.k_steps_per_group <= 0 or self.k_groups <= 0:
            raise ValueError("MMA step and group counts must be positive")
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))


@dc.py_class("weave.SoftmaxParams", structural_eq="tree")
class SoftmaxParams(std.Node, mnemonic="weave.SoftmaxParams"):
    """Softmax schedule parameters."""

    tile_n: int = dc.field(lang_kind="arg")
    num_load_chunks: int = dc.field(default=0, lang_kind="attr")
    num_store_chunks: int = dc.field(default=0, lang_kind="attr")


@dc.py_class("weave.EpilogueParams", structural_eq="tree")
class EpilogueParams(std.Node, mnemonic="weave.EpilogueParams"):
    """Epilogue schedule parameters."""

    head_dim: int = dc.field(lang_kind="arg")
    num_chunks_16: int = dc.field(lang_kind="arg")
    use_tma_store: bool = dc.field(default=False, lang_kind="attr")


@dc.py_class("weave.TmaLoadParams", structural_eq="tree")
class TmaLoadParams(std.Node, mnemonic="weave.TmaLoadParams"):
    """TMA load schedule parameters."""

    pipeline_name: str = dc.field(lang_kind="arg")
    num_stages: int = dc.field(default=1, lang_kind="attr")
    src_buffers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    dst_buffers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    full_barrier: str = dc.field(default="", lang_kind="attr")
    empty_barrier: str = dc.field(default="", lang_kind="attr")
    stage_var: str = dc.field(default="", lang_kind="attr")
    phase_vars: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "src_buffers", tuple(self.src_buffers))
        object.__setattr__(self, "dst_buffers", tuple(self.dst_buffers))
        object.__setattr__(self, "phase_vars", tuple(self.phase_vars))


@dc.py_class("weave.NamedBarrierSpec", structural_eq="tree")
class NamedBarrierSpec(std.Node, mnemonic="weave.NamedBarrierSpec"):
    """Reusable named CTA barrier specification."""

    name: str = dc.field(lang_kind="arg")
    bar_id: int = dc.field(lang_kind="arg")
    thread_count: int = dc.field(lang_kind="arg")


@dc.py_class("weave.ProcessGroup", structural_eq="tree")
class ProcessGroup(std.Node, mnemonic="weave.ProcessGroup"):
    """Distributed process group handle intent."""

    name: str = dc.field(lang_kind="arg")
    world_size: int = dc.field(lang_kind="arg")


@dc.py_class("weave.SymmetricMemory", structural_eq="tree")
class SymmetricMemory(std.Node, mnemonic="weave.SymmetricMemory"):
    """Symmetric-memory declaration intent."""

    name: str = dc.field(lang_kind="arg")
    dtype: Any = dc.field(lang_kind="arg")
    shape: tuple[ShapeDim, ...] = dc.field(lang_kind="attr")
    group: ProcessGroup | StringLike = dc.field(lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))
        object.__setattr__(self, "shape", tuple(self.shape))


__all__ = [
    "BufferRef",
    "EpilogueParams",
    "MbarrierSpec",
    "MmaParams",
    "NamedBarrierSpec",
    "PhaseDomain",
    "PhaseVar",
    "ProcessGroup",
    "ScalarParam",
    "SmemPool",
    "SmemView",
    "SoftmaxParams",
    "SymmetricMemory",
    "TmaDescriptor",
    "TmaLoadParams",
    "TmemRegion",
]
