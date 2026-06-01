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

from tvm_ffi import dataclasses as dc
from tvm_ffi import dtype as tvm_dtype
from tvm_ffi import std

from ._utils import normalize_dtype, validate_candidate_value, validate_cta_group
from .swizzle import Swizzle

ShapeDim = int | str
SwizzleSpec = str | Swizzle | None

SIGNALING_MODES = ("elected", "hw_commit", "all_warps", "tma_expect_tx")
MEMORY_SPACES = ("gmem", "smem", "tmem", "regs", "local", "param", "symm")


@dc.py_class("weave.TmemRegion", structural_eq="tree")
class TmemRegion(std.Attrs, mnemonic="weave.TmemRegion"):
    """Named tensor-memory column region."""

    name: str = dc.field(lang_kind="attr")
    start_col: int = dc.field(lang_kind="attr")
    ncols: int = dc.field(lang_kind="attr")
    num_buffers: int = dc.field(default=1, lang_kind="attr")
    kparam_name: str = dc.field(default="", lang_kind="attr")
    var_name: str = dc.field(default="", lang_kind="attr")
    dtype: tvm_dtype | None = dc.field(default=None, lang_kind="attr")

    def __init__(
        self,
        name: str,
        start_col: int,
        ncols: int,
        num_buffers: int = 1,
        kparam_name: str = "",
        var_name: str = "",
        dtype: std.TyLike | None = None,
    ) -> None:
        if dtype is not None:
            dtype = normalize_dtype(dtype, field_name="dtype")
        if start_col < 0 or ncols <= 0 or num_buffers <= 0:
            raise ValueError("invalid TMEM region extent")
        self.__ffi_init__(
            name,
            start_col,
            ncols,
            num_buffers,
            kparam_name,
            var_name,
            dtype,
        )


@dc.py_class("weave.Mbarrier", structural_eq="tree")
class MbarrierSpec(std.Attrs, mnemonic="weave.Mbarrier"):
    """Mbarrier group specification."""

    role: str = dc.field(lang_kind="attr")
    count: int = dc.field(lang_kind="attr")
    init_count: int = dc.field(default=0, lang_kind="attr")
    producers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    consumers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    signaling_mode: str | None = dc.field(default=None, lang_kind="attr")
    producer_warps: int = dc.field(default=0, lang_kind="attr")
    stage_var: str = dc.field(default="", lang_kind="attr")
    pipeline: str = dc.field(default="", lang_kind="attr")
    init_phase: int = dc.field(default=0, lang_kind="attr")

    def __post_init__(self) -> None:
        if self.count <= 0:
            raise ValueError("count must be positive")
        if self.init_phase not in (0, 1):
            raise ValueError("init_phase must be 0 or 1")
        if self.signaling_mode is not None:
            self.signaling_mode = validate_candidate_value(
                self.signaling_mode, SIGNALING_MODES, field_name="signaling_mode"
            )

    def derived_init_count(self) -> int:
        """Return explicit or signaling-derived arrival count."""
        if self.init_count > 0:
            return self.init_count
        if self.signaling_mode == "all_warps":
            return max(self.producer_warps, 1)
        return 1


@dc.py_class("weave.TmaDescriptor", structural_eq="tree")
class TmaDescriptor(std.Attrs, mnemonic="weave.TmaDescriptor"):
    """TMA tensor map descriptor."""

    ndim: int = dc.field(lang_kind="attr")
    box_shape: tuple[ShapeDim, ...] = dc.field(lang_kind="attr")
    swizzle: SwizzleSpec = dc.field(default="128B", lang_kind="attr")
    global_shape: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    global_strides: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")

    def __post_init__(self) -> None:
        if self.ndim <= 0:
            raise ValueError("ndim must be positive")
        if len(self.box_shape) != self.ndim:
            raise ValueError("box_shape length must match ndim")


@dc.py_class("weave.Buffer", structural_eq="tree")
class BufferRef(std.Attrs, mnemonic="weave.Buffer"):
    """Typed memory buffer reference."""

    name: str = dc.field(lang_kind="attr")
    dtype: tvm_dtype = dc.field(lang_kind="attr")
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

    def __init__(
        self,
        name: str,
        dtype: std.TyLike,
        shape: tuple[ShapeDim, ...],
        space: str = "gmem",
        tmem_col: int | None = None,
        smem_offset: int | None = None,
        swizzle: SwizzleSpec = None,
        stage: int | None = None,
        tma: TmaDescriptor | None = None,
        source_gmem: str = "",
        scale_buffer: str = "",
        align: int = 1,
        volatile: bool = False,
    ) -> None:
        if dtype is None:
            raise TypeError("dtype is required")
        dtype = normalize_dtype(dtype, field_name="dtype")
        space = validate_candidate_value(space, MEMORY_SPACES, field_name="space")
        if align <= 0:
            raise ValueError("align must be positive")
        self.__ffi_init__(
            name,
            dtype,
            shape,
            space,
            tmem_col,
            smem_offset,
            swizzle,
            stage,
            tma,
            source_gmem,
            scale_buffer,
            align,
            volatile,
        )


@dc.py_class("weave.Param", structural_eq="tree")
class ScalarParam(std.Attrs, mnemonic="weave.Param"):
    """Scalar kernel parameter."""

    name: str = dc.field(lang_kind="attr")
    ctype: str = dc.field(lang_kind="attr")


@dc.py_class("weave.SmemPool", structural_eq="tree")
class SmemPool(std.Attrs, mnemonic="weave.SmemPool"):
    """Named shared-memory pool."""

    name: str = dc.field(lang_kind="attr")
    size: int = dc.field(lang_kind="attr")

    def __post_init__(self) -> None:
        if self.size < 0:
            raise ValueError("size must be non-negative")


@dc.py_class("weave.SmemView", structural_eq="tree")
class SmemView(std.Attrs, mnemonic="weave.SmemView"):
    """View into a shared-memory pool."""

    name: str = dc.field(kw_only=True, lang_kind="attr")
    pool: SmemPool | str = dc.field(kw_only=True, lang_kind="attr")
    offset: std.Expr = dc.field(lang_kind="arg")
    shape: tuple[ShapeDim, ...] = dc.field(lang_kind="attr")
    stride: int | None = dc.field(default=None, lang_kind="attr")
    dtype: tvm_dtype = dc.field(kw_only=True, lang_kind="attr")
    stage: int | None = dc.field(default=None, lang_kind="attr")
    swizzle: SwizzleSpec = dc.field(default=None, lang_kind="attr")
    layout: str = dc.field(default="", lang_kind="attr")
    alias_of: str = dc.field(default="", lang_kind="attr")

    def __init__(
        self,
        offset: std.Expr | bool | int | float,
        *,
        name: str,
        pool: SmemPool | str,
        shape: tuple[ShapeDim, ...],
        dtype: std.TyLike | tvm_dtype,
        stage: int | None = None,
        stride: int | None = None,
        swizzle: SwizzleSpec = None,
        layout: str = "",
        alias_of: str = "",
    ) -> None:
        if dtype is None:
            raise TypeError("dtype is required")
        dtype = normalize_dtype(dtype, field_name="dtype")
        self.__ffi_init__(
            name=name,
            pool=pool,
            offset=offset,
            shape=shape,
            stride=stride,
            dtype=dtype,
            stage=stage,
            swizzle=swizzle,
            layout=layout,
            alias_of=alias_of,
        )


@dc.py_class("weave.PhaseVar", structural_eq="tree")
class PhaseVar(std.Attrs, mnemonic="weave.PhaseVar"):
    """Rotating phase variable metadata."""

    name: str = dc.field(kw_only=True, lang_kind="attr")
    init_value: std.Expr = dc.field(default=0, lang_kind="arg")
    dtype: tvm_dtype = dc.field(default_factory=lambda: tvm_dtype("int32"), lang_kind="attr")
    rotation_rule: str = dc.field(default="", lang_kind="attr")
    rotation_trigger: str = dc.field(default="", lang_kind="attr")

    def __init__(
        self,
        init_value: std.Expr | bool | int | float = 0,
        *,
        name: str,
        dtype: std.TyLike | tvm_dtype = std.PrimTy("int32"),
        rotation_rule: str = "",
        rotation_trigger: str = "",
    ) -> None:
        if dtype is None:
            raise TypeError("dtype is required")
        dtype = normalize_dtype(dtype, field_name="dtype")
        self.__ffi_init__(
            name=name,
            init_value=init_value,
            dtype=dtype,
            rotation_rule=rotation_rule,
            rotation_trigger=rotation_trigger,
        )


@dc.py_class("weave.PhaseDomain", structural_eq="tree")
class PhaseDomain(std.Attrs, mnemonic="weave.PhaseDomain"):
    """Pipeline phase domain."""

    pipeline: str = dc.field(lang_kind="attr")
    stage_var: str = dc.field(lang_kind="attr")
    num_stages: int = dc.field(lang_kind="attr")
    phase_vars: tuple[PhaseVar, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    owner_role: str = dc.field(default="", lang_kind="attr")
    stage_ctype: str = dc.field(default="int", lang_kind="attr")
    stage_init: int = dc.field(default=0, lang_kind="attr")

    def __post_init__(self) -> None:
        if self.num_stages <= 0:
            raise ValueError("num_stages must be positive")


@dc.py_class("weave.MmaParams", structural_eq="tree")
class MmaParams(std.Attrs, mnemonic="weave.MmaParams"):
    """MMA loop parameter bundle."""

    k_steps_per_group: int = dc.field(lang_kind="attr")
    k_groups: int = dc.field(lang_kind="attr")
    group_lo_offset: int = dc.field(lang_kind="attr")
    cta_group: int = dc.field(default=1, lang_kind="attr")
    tile_m: int = dc.field(default=0, lang_kind="attr")
    tile_n: int = dc.field(default=0, lang_kind="attr")
    dtype: tvm_dtype | None = dc.field(default=None, lang_kind="attr")

    def __init__(
        self,
        k_steps_per_group: int,
        k_groups: int,
        group_lo_offset: int,
        cta_group: int = 1,
        tile_m: int = 0,
        tile_n: int = 0,
        dtype: std.TyLike | None = None,
    ) -> None:
        cta_group = validate_cta_group(cta_group)
        if dtype is not None:
            dtype = normalize_dtype(dtype, field_name="dtype")
        if k_steps_per_group <= 0 or k_groups <= 0:
            raise ValueError("MMA step and group counts must be positive")
        self.__ffi_init__(
            k_steps_per_group,
            k_groups,
            group_lo_offset,
            cta_group,
            tile_m,
            tile_n,
            dtype,
        )


@dc.py_class("weave.SoftmaxParams", structural_eq="tree")
class SoftmaxParams(std.Attrs, mnemonic="weave.SoftmaxParams"):
    """Softmax schedule parameters."""

    tile_n: int = dc.field(lang_kind="attr")
    num_load_chunks: int = dc.field(default=0, lang_kind="attr")
    num_store_chunks: int = dc.field(default=0, lang_kind="attr")


@dc.py_class("weave.EpilogueParams", structural_eq="tree")
class EpilogueParams(std.Attrs, mnemonic="weave.EpilogueParams"):
    """Epilogue schedule parameters."""

    head_dim: int = dc.field(lang_kind="attr")
    num_chunks_16: int = dc.field(lang_kind="attr")
    use_tma_store: bool = dc.field(default=False, lang_kind="attr")


@dc.py_class("weave.TmaLoadParams", structural_eq="tree")
class TmaLoadParams(std.Attrs, mnemonic="weave.TmaLoadParams"):
    """TMA load schedule parameters."""

    pipeline_name: str = dc.field(lang_kind="attr")
    num_stages: int = dc.field(default=1, lang_kind="attr")
    src_buffers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    dst_buffers: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    full_barrier: str = dc.field(default="", lang_kind="attr")
    empty_barrier: str = dc.field(default="", lang_kind="attr")
    stage_var: str = dc.field(default="", lang_kind="attr")
    phase_vars: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")


@dc.py_class("weave.NamedBarrierSpec", structural_eq="tree")
class NamedBarrierSpec(std.Attrs, mnemonic="weave.NamedBarrierSpec"):
    """Reusable named CTA barrier specification."""

    name: str = dc.field(lang_kind="attr")
    bar_id: int = dc.field(lang_kind="attr")
    thread_count: int = dc.field(lang_kind="attr")


@dc.py_class("weave.ProcessGroup", structural_eq="tree")
class ProcessGroup(std.Attrs, mnemonic="weave.ProcessGroup"):
    """Distributed process group handle intent."""

    name: str = dc.field(lang_kind="attr")
    world_size: int = dc.field(lang_kind="attr")


@dc.py_class("weave.SymmetricMemory", structural_eq="tree")
class SymmetricMemory(std.Attrs, mnemonic="weave.SymmetricMemory"):
    """Symmetric-memory declaration intent."""

    name: str = dc.field(lang_kind="attr")
    dtype: tvm_dtype = dc.field(lang_kind="attr")
    shape: tuple[ShapeDim, ...] = dc.field(lang_kind="attr")
    group: ProcessGroup | str = dc.field(lang_kind="attr")

    def __init__(
        self,
        name: str,
        dtype: std.TyLike,
        shape: tuple[ShapeDim, ...],
        group: ProcessGroup | str,
    ) -> None:
        if dtype is None:
            raise TypeError("dtype is required")
        dtype = normalize_dtype(dtype, field_name="dtype")
        self.__ffi_init__(name, dtype, shape, group)


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
