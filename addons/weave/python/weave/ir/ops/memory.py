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

from typing import Any, ClassVar

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from .._utils import Op, normalize_dtype, validate_cta_group
from ..dtypes import StringLike
from ..handles import BufferRef, SmemView, TmemRegion

SMEM_DESC_MODES = ("k", "mn")
GMEM_CACHE_HINTS = ("none", "no_allocate", "evict_first", "evict_last")
TMA_REDUCE_OPS = ("add", "min", "max", "inc", "dec", "and", "or", "xor")
TmemRegionRef = StringLike | TmemRegion
SmemBufferRef = StringLike | BufferRef | SmemView


@dc.py_class("weave.BuiltinVar", structural_eq="tree")
class BuiltinVar(Op, mnemonic="weave.BuiltinVar"):
    name: str = dc.field(lang_kind="arg")
    dst: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("dst",))


@dc.py_class("weave.TmemRegionLoad", structural_eq="tree")
class TmemRegionLoad(Op, mnemonic="weave.TmemRegionLoad"):
    region: TmemRegionRef = dc.field(lang_kind="arg")
    dst: std.Expr | None = dc.field(default=None, lang_kind="attr")
    col_offset: std.Expr | None = dc.field(default=None, lang_kind="attr")
    num: int = dc.field(default=16, lang_kind="attr")
    dst_offset: int = dc.field(default=0, lang_kind="attr")
    wait: bool = dc.field(default=True, lang_kind="attr")
    row_base: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("dst", "col_offset", "row_base"))

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.num not in (8, 16, 32):
            raise ValueError("num must be one of 8, 16, 32")


@dc.py_class("weave.TmemRegionStore", structural_eq="tree")
class TmemRegionStore(Op, mnemonic="weave.TmemRegionStore"):
    region: TmemRegionRef = dc.field(lang_kind="arg")
    src: std.Expr | None = dc.field(default=None, lang_kind="attr")
    col_offset: std.Expr | None = dc.field(default=None, lang_kind="attr")
    num: int = dc.field(default=8, lang_kind="attr")
    dtype: Any = dc.field(default=None, lang_kind="attr")
    row_base: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "col_offset", "row_base"))

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.num not in (8, 16):
            raise ValueError("num must be 8 or 16")
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))


@dc.py_class("weave.SmemDesc", structural_eq="tree")
class SmemDesc(Op, mnemonic="weave.SmemDesc"):
    buffer: SmemBufferRef = dc.field(lang_kind="arg")
    k_idx: std.Expr | None = dc.field(default=None, lang_kind="attr")
    mode: str = dc.field(default="k", lang_kind="attr")
    dst: std.Expr | None = dc.field(default=None, lang_kind="attr")
    step: std.Expr | None = dc.field(default=None, lang_kind="attr")
    offset: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("k_idx", "dst", "step", "offset"))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"mode": SMEM_DESC_MODES}


@dc.py_class("weave.GmemLoad", structural_eq="tree")
class GmemLoad(Op, mnemonic="weave.GmemLoad"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    count: int = dc.field(lang_kind="attr")
    dtype: Any = dc.field(lang_kind="attr")
    dst_dtype: Any = dc.field(lang_kind="attr")
    dst_offset: std.Expr | None = dc.field(default=None, lang_kind="attr")
    index: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst", "dst_offset", "index"))

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))
        object.__setattr__(
            self, "dst_dtype", normalize_dtype(self.dst_dtype, field_name="dst_dtype")
        )


@dc.py_class("weave.GmemStore", structural_eq="tree")
class GmemStore(Op, mnemonic="weave.GmemStore"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    count: int = dc.field(lang_kind="attr")
    dtype: Any = dc.field(lang_kind="attr")
    src_dtype: Any = dc.field(lang_kind="attr")
    src_offset: std.Expr | None = dc.field(default=None, lang_kind="attr")
    index: std.Expr | None = dc.field(default=None, lang_kind="attr")
    scale: std.Expr | None = dc.field(default=None, lang_kind="attr")
    cache_hint: str = dc.field(default="none", lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(
        ("src", "dst", "src_offset", "index", "scale")
    )
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"cache_hint": GMEM_CACHE_HINTS}

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))
        object.__setattr__(
            self, "src_dtype", normalize_dtype(self.src_dtype, field_name="src_dtype")
        )


@dc.py_class("weave.SmemStore", structural_eq="tree")
class SmemStore(Op, mnemonic="weave.SmemStore"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    predicate: std.Expr | None = dc.field(default=None, lang_kind="attr")
    index: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst", "predicate", "index"))


@dc.py_class("weave.SmemLoad", structural_eq="tree")
class SmemLoad(Op, mnemonic="weave.SmemLoad"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst"))


@dc.py_class("weave.SmemRead", structural_eq="tree")
class SmemRead(Op, mnemonic="weave.SmemRead"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr | None = dc.field(default=None, lang_kind="attr")
    index: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst", "index"))


@dc.py_class("weave.SmemLoadRegs", structural_eq="tree")
class SmemLoadRegs(Op, mnemonic="weave.SmemLoadRegs"):
    name: str = dc.field(lang_kind="arg")
    src_expr: std.Expr = dc.field(lang_kind="arg")
    count: int = dc.field(default=0, lang_kind="attr")
    dtype: Any = dc.field(default_factory=lambda: std.PrimTy("float32"), lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src_expr",))

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))
        if self.count < 0:
            raise ValueError("count must be non-negative")


@dc.py_class("weave.SmemWrite", structural_eq="tree")
class SmemWrite(Op, mnemonic="weave.SmemWrite"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    index: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst", "index"))


@dc.py_class("weave.SmemLoadVec", structural_eq="tree")
class SmemLoadVec(Op, mnemonic="weave.SmemLoadVec"):
    dst: std.Expr = dc.field(lang_kind="arg")
    src_addr: std.Expr = dc.field(lang_kind="arg")
    count: int = dc.field(default=1, lang_kind="attr")
    dst_offset: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("dst", "src_addr", "dst_offset"))

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.count not in (1, 4):
            raise ValueError("count must be 1 or 4")


@dc.py_class("weave.SmemStoreVec", structural_eq="tree")
class SmemStoreVec(Op, mnemonic="weave.SmemStoreVec"):
    dst_addr: std.Expr = dc.field(lang_kind="arg")
    src: std.Expr = dc.field(lang_kind="arg")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("dst_addr", "src"))


@dc.py_class("weave.TmaStore", structural_eq="tree")
class TmaStore(Op, mnemonic="weave.TmaStore"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst"))


@dc.py_class("weave.TmaReduceOp", structural_eq="tree")
class TmaReduceOp(Op, mnemonic="weave.TmaReduceOp"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    op: str = dc.field(default="add", lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst"))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"op": TMA_REDUCE_OPS}


@dc.py_class("weave.TmaGatherLoad", structural_eq="tree")
class TmaGatherLoad(Op, mnemonic="weave.TmaGatherLoad"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    page_table: std.Expr = dc.field(lang_kind="arg")
    tokens_per_page: int = dc.field(default=64, lang_kind="attr")
    mbar_expr: std.Expr | None = dc.field(default=None, lang_kind="attr")
    token_offset: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(
        ("src", "dst", "page_table", "mbar_expr", "token_offset")
    )


@dc.py_class("weave.ScaleFactorCopy", structural_eq="tree")
class ScaleFactorCopy(Op, mnemonic="weave.ScaleFactorCopy"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    cta_group: Any = dc.field(default=1, lang_kind="attr")
    sbo: int = dc.field(default=256, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst"))

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))
        if self.sbo <= 0 or self.sbo % 16:
            raise ValueError("sbo must be a positive multiple of 16")


@dc.py_class("weave.MetadataCopy", structural_eq="tree")
class MetadataCopy(Op, mnemonic="weave.MetadataCopy"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    cta_group: Any = dc.field(default=1, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst"))

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))


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
