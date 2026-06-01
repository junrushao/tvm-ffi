# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Weave memory operation nodes."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import dtype as tvm_dtype
from tvm_ffi import std

from .._utils import (
    Op,
    normalize_dtype,
    validate_candidate_value,
    validate_cta_group,
)
from ..handles import BufferRef, SmemView, TmemRegion

SMEM_DESC_MODES = ("k", "mn")
GMEM_CACHE_HINTS = ("none", "no_allocate", "evict_first", "evict_last")
TMA_REDUCE_OPS = ("add", "min", "max", "inc", "dec", "and", "or", "xor")
TmemRegionRef = str | TmemRegion
SmemBufferRef = str | BufferRef | SmemView


def _check_named_ref(value: str | std.Attrs, *, field_name: str) -> None:
    if isinstance(value, std.StringImm):
        raise TypeError(f"{field_name} expects a structured handle or plain string, not StringImm")


@dc.py_class("weave.BuiltinVar", structural_eq="tree")
class BuiltinVar(Op, mnemonic="weave.BuiltinVar"):
    dst: std.Expr | None = dc.field(default=None, lang_kind="arg")
    name: str = dc.field(kw_only=True, lang_kind="attr")

    def __init__(self, dst: std.Expr | None = None, *, name: str) -> None:
        self.__ffi_init__(dst=dst, name=name)


@dc.py_class("weave.TmemRegionLoad", structural_eq="tree")
class TmemRegionLoad(Op, mnemonic="weave.TmemRegionLoad"):
    dst: std.Expr | None = dc.field(default=None, lang_kind="arg")
    col_offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    row_base: std.Expr | None = dc.field(default=None, lang_kind="arg")
    region: TmemRegionRef = dc.field(kw_only=True, lang_kind="attr")
    num: int = dc.field(default=16, lang_kind="attr")
    dst_offset: int = dc.field(default=0, lang_kind="attr")
    wait: bool = dc.field(default=True, lang_kind="attr")

    def __init__(
        self,
        dst: std.Expr | None = None,
        col_offset: std.Expr | None = None,
        row_base: std.Expr | None = None,
        *,
        region: TmemRegionRef,
        num: int = 16,
        dst_offset: int = 0,
        wait: bool = True,
    ) -> None:
        _check_named_ref(region, field_name="region")
        if num not in (8, 16, 32):
            raise ValueError("num must be one of 8, 16, 32")
        self.__ffi_init__(
            dst=dst,
            col_offset=col_offset,
            row_base=row_base,
            region=region,
            num=num,
            dst_offset=dst_offset,
            wait=wait,
        )


@dc.py_class("weave.TmemRegionStore", structural_eq="tree")
class TmemRegionStore(Op, mnemonic="weave.TmemRegionStore"):
    src: std.Expr | None = dc.field(default=None, lang_kind="arg")
    col_offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    row_base: std.Expr | None = dc.field(default=None, lang_kind="arg")
    region: TmemRegionRef = dc.field(kw_only=True, lang_kind="attr")
    num: int = dc.field(default=8, lang_kind="attr")
    dtype: tvm_dtype | None = dc.field(default=None, lang_kind="attr")

    def __init__(
        self,
        src: std.Expr | None = None,
        col_offset: std.Expr | None = None,
        row_base: std.Expr | None = None,
        *,
        region: TmemRegionRef,
        num: int = 8,
        dtype: std.TyLike | None = None,
    ) -> None:
        _check_named_ref(region, field_name="region")
        if num not in (8, 16):
            raise ValueError("num must be 8 or 16")
        if dtype is not None:
            dtype = normalize_dtype(dtype, field_name="dtype")
        self.__ffi_init__(
            src=src,
            col_offset=col_offset,
            row_base=row_base,
            region=region,
            num=num,
            dtype=dtype,
        )


@dc.py_class("weave.SmemDesc", structural_eq="tree")
class SmemDesc(Op, mnemonic="weave.SmemDesc"):
    k_idx: std.Expr | None = dc.field(default=None, lang_kind="arg")
    dst: std.Expr | None = dc.field(default=None, lang_kind="arg")
    step: std.Expr | None = dc.field(default=None, lang_kind="arg")
    offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    buffer: SmemBufferRef = dc.field(kw_only=True, lang_kind="attr")
    mode: str = dc.field(default="k", lang_kind="attr")

    def __init__(
        self,
        k_idx: std.Expr | None = None,
        dst: std.Expr | None = None,
        step: std.Expr | None = None,
        offset: std.Expr | None = None,
        *,
        buffer: SmemBufferRef,
        mode: str = "k",
    ) -> None:
        _check_named_ref(buffer, field_name="buffer")
        mode = validate_candidate_value(mode, SMEM_DESC_MODES, field_name="mode")
        self.__ffi_init__(
            k_idx=k_idx,
            dst=dst,
            step=step,
            offset=offset,
            buffer=buffer,
            mode=mode,
        )


@dc.py_class("weave.GmemLoad", structural_eq="tree")
class GmemLoad(Op, mnemonic="weave.GmemLoad"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    dst_offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    index: std.Expr | None = dc.field(default=None, lang_kind="arg")
    count: int = dc.field(kw_only=True, lang_kind="attr")
    dtype: tvm_dtype = dc.field(kw_only=True, lang_kind="attr")
    dst_dtype: tvm_dtype = dc.field(kw_only=True, lang_kind="attr")

    def __init__(
        self,
        src: std.Expr,
        dst: std.Expr,
        dst_offset: std.Expr | None = None,
        index: std.Expr | None = None,
        *,
        count: int,
        dtype: std.TyLike,
        dst_dtype: std.TyLike,
    ) -> None:
        if dtype is None:
            raise TypeError("dtype is required")
        if dst_dtype is None:
            raise TypeError("dst_dtype is required")
        dtype = normalize_dtype(dtype, field_name="dtype")
        dst_dtype = normalize_dtype(dst_dtype, field_name="dst_dtype")
        self.__ffi_init__(
            src=src,
            dst=dst,
            dst_offset=dst_offset,
            index=index,
            count=count,
            dtype=dtype,
            dst_dtype=dst_dtype,
        )


@dc.py_class("weave.GmemStore", structural_eq="tree")
class GmemStore(Op, mnemonic="weave.GmemStore"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    src_offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    index: std.Expr | None = dc.field(default=None, lang_kind="arg")
    scale: std.Expr | None = dc.field(default=None, lang_kind="arg")
    count: int = dc.field(kw_only=True, lang_kind="attr")
    dtype: tvm_dtype = dc.field(kw_only=True, lang_kind="attr")
    src_dtype: tvm_dtype = dc.field(kw_only=True, lang_kind="attr")
    cache_hint: str = dc.field(default="none", lang_kind="attr")

    def __init__(
        self,
        src: std.Expr,
        dst: std.Expr,
        src_offset: std.Expr | None = None,
        index: std.Expr | None = None,
        scale: std.Expr | None = None,
        *,
        count: int,
        dtype: std.TyLike,
        src_dtype: std.TyLike,
        cache_hint: str = "none",
    ) -> None:
        if dtype is None:
            raise TypeError("dtype is required")
        if src_dtype is None:
            raise TypeError("src_dtype is required")
        dtype = normalize_dtype(dtype, field_name="dtype")
        src_dtype = normalize_dtype(src_dtype, field_name="src_dtype")
        cache_hint = validate_candidate_value(cache_hint, GMEM_CACHE_HINTS, field_name="cache_hint")
        self.__ffi_init__(
            src=src,
            dst=dst,
            src_offset=src_offset,
            index=index,
            scale=scale,
            count=count,
            dtype=dtype,
            src_dtype=src_dtype,
            cache_hint=cache_hint,
        )


@dc.py_class("weave.SmemStore", structural_eq="tree")
class SmemStore(Op, mnemonic="weave.SmemStore"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    predicate: std.Expr | None = dc.field(default=None, lang_kind="arg")
    index: std.Expr | None = dc.field(default=None, lang_kind="arg")


@dc.py_class("weave.SmemLoad", structural_eq="tree")
class SmemLoad(Op, mnemonic="weave.SmemLoad"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")


@dc.py_class("weave.SmemRead", structural_eq="tree")
class SmemRead(Op, mnemonic="weave.SmemRead"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr | None = dc.field(default=None, lang_kind="arg")
    index: std.Expr | None = dc.field(default=None, lang_kind="arg")


@dc.py_class("weave.SmemLoadRegs", structural_eq="tree")
class SmemLoadRegs(Op, mnemonic="weave.SmemLoadRegs"):
    src_expr: std.Expr = dc.field(lang_kind="arg")
    name: str = dc.field(kw_only=True, lang_kind="attr")
    count: int = dc.field(default=0, lang_kind="attr")
    dtype: tvm_dtype = dc.field(default_factory=lambda: tvm_dtype("float32"), lang_kind="attr")

    def __init__(
        self,
        src_expr: std.Expr,
        *,
        name: str,
        count: int = 0,
        dtype: std.TyLike = std.PrimTy("float32"),
    ) -> None:
        if dtype is None:
            raise TypeError("dtype is required")
        dtype = normalize_dtype(dtype, field_name="dtype")
        if count < 0:
            raise ValueError("count must be non-negative")
        self.__ffi_init__(src_expr=src_expr, name=name, count=count, dtype=dtype)


@dc.py_class("weave.SmemWrite", structural_eq="tree")
class SmemWrite(Op, mnemonic="weave.SmemWrite"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    index: std.Expr | None = dc.field(default=None, lang_kind="arg")


@dc.py_class("weave.SmemLoadVec", structural_eq="tree")
class SmemLoadVec(Op, mnemonic="weave.SmemLoadVec"):
    dst: std.Expr = dc.field(lang_kind="arg")
    src_addr: std.Expr = dc.field(lang_kind="arg")
    dst_offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    count: int = dc.field(default=1, lang_kind="attr")

    def __post_init__(self) -> None:
        if self.count not in (1, 4):
            raise ValueError("count must be 1 or 4")


@dc.py_class("weave.SmemStoreVec", structural_eq="tree")
class SmemStoreVec(Op, mnemonic="weave.SmemStoreVec"):
    dst_addr: std.Expr = dc.field(lang_kind="arg")
    src: std.Expr = dc.field(lang_kind="arg")


@dc.py_class("weave.TmaStore", structural_eq="tree")
class TmaStore(Op, mnemonic="weave.TmaStore"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")


@dc.py_class("weave.TmaReduceOp", structural_eq="tree")
class TmaReduceOp(Op, mnemonic="weave.TmaReduceOp"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    op: str = dc.field(default="add", lang_kind="attr")

    def __post_init__(self) -> None:
        self.op = validate_candidate_value(self.op, TMA_REDUCE_OPS, field_name="op")


@dc.py_class("weave.TmaGatherLoad", structural_eq="tree")
class TmaGatherLoad(Op, mnemonic="weave.TmaGatherLoad"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    page_table: std.Expr = dc.field(lang_kind="arg")
    mbar_expr: std.Expr | None = dc.field(default=None, lang_kind="arg")
    token_offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    tokens_per_page: int = dc.field(default=64, lang_kind="attr")


@dc.py_class("weave.ScaleFactorCopy", structural_eq="tree")
class ScaleFactorCopy(Op, mnemonic="weave.ScaleFactorCopy"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    cta_group: int = dc.field(default=1, lang_kind="attr")
    sbo: int = dc.field(default=256, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")

    def __init__(
        self,
        src: std.Expr,
        dst: std.Expr,
        cta_group: int = 1,
        sbo: int = 256,
        elected: bool = False,
    ) -> None:
        cta_group = validate_cta_group(cta_group)
        if sbo <= 0 or sbo % 16:
            raise ValueError("sbo must be a positive multiple of 16")
        self.__ffi_init__(src, dst, cta_group, sbo, elected)


@dc.py_class("weave.MetadataCopy", structural_eq="tree")
class MetadataCopy(Op, mnemonic="weave.MetadataCopy"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    cta_group: int = dc.field(default=1, lang_kind="attr")

    def __init__(self, src: std.Expr, dst: std.Expr, cta_group: int = 1) -> None:
        self.__ffi_init__(src, dst, validate_cta_group(cta_group))


__all__ = [  # noqa: RUF022
    "BuiltinVar",
    "TmemRegionLoad",
    "TmemRegionStore",
    "SmemDesc",
    "GmemLoad",
    "GmemStore",
    "SmemStore",
    "SmemLoad",
    "SmemRead",
    "SmemLoadRegs",
    "SmemWrite",
    "SmemLoadVec",
    "SmemStoreVec",
    "TmaStore",
    "TmaReduceOp",
    "TmaGatherLoad",
    "ScaleFactorCopy",
    "MetadataCopy",
]
