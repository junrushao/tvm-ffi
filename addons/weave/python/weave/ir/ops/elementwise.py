# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Weave elementwise and mask operation nodes."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import dtype as tvm_dtype
from tvm_ffi import std

from .._utils import Op, normalize_domain, normalize_required_dtype

ELEMENTWISE_OPS = ("fma", "mul", "add", "sub", "fmax", "exp", "bitmask")


@dc.py_class("weave.Elementwise", structural_eq="tree")
class Elementwise(Op, mnemonic="weave.Elementwise"):
    inputs: list[std.Expr] = dc.field(default_factory=list, lang_kind="arg")
    output: std.Expr | None = dc.field(default=None, lang_kind="arg")
    op: str = dc.field(kw_only=True, lang_kind="attr")

    def __init__(
        self,
        inputs: list[std.Expr] | None = None,
        output: std.Expr | None = None,
        *,
        op: str,
    ) -> None:
        self.__ffi_init__(inputs=inputs or [], output=output, op=op)
        self.__post_init__()

    def __post_init__(self) -> None:
        self.op = normalize_domain(self.op, ELEMENTWISE_OPS, field_name="op")


@dc.py_class("weave.PredicatedStore", structural_eq="tree")
class PredicatedStore(Op, mnemonic="weave.PredicatedStore"):
    dst: std.Expr = dc.field(lang_kind="arg")
    src: std.Expr = dc.field(lang_kind="arg")
    bound_m: std.Expr = dc.field(lang_kind="arg")
    bound_n: std.Expr = dc.field(lang_kind="arg")
    tile_offset_m: std.Expr = dc.field(lang_kind="arg")
    tile_offset_n: std.Expr = dc.field(lang_kind="arg")


@dc.py_class("weave.ThreshMask", structural_eq="tree")
class ThreshMask(Op, mnemonic="weave.ThreshMask"):
    dst: std.Expr = dc.field(lang_kind="arg")
    limit: std.Expr = dc.field(lang_kind="arg")
    width: int = dc.field(default=32, lang_kind="attr")

    def __post_init__(self) -> None:
        if not 1 <= self.width <= 32:
            raise ValueError("width must be in [1, 32]")


@dc.py_class("weave.BitmaskFill", structural_eq="tree")
class BitmaskFill(Op, mnemonic="weave.BitmaskFill"):
    array: std.Expr = dc.field(lang_kind="arg")
    mask: std.Expr = dc.field(lang_kind="arg")
    fill_value: std.Expr | None = dc.field(default=None, lang_kind="arg")
    offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    count: int = dc.field(default=32, lang_kind="attr")

    def __post_init__(self) -> None:
        if not 1 <= self.count <= 32:
            raise ValueError("count must be in [1, 32]")


@dc.py_class("weave.MaskFill", structural_eq="tree")
class MaskFill(Op, mnemonic="weave.MaskFill"):
    array: std.Expr = dc.field(lang_kind="arg")
    fill: std.Expr = dc.field(lang_kind="arg")
    lo: std.Expr | None = dc.field(default=None, lang_kind="arg")
    hi: std.Expr | None = dc.field(default=None, lang_kind="arg")
    size: int = dc.field(default=0, lang_kind="attr")

    def __post_init__(self) -> None:
        if self.size < 0:
            raise ValueError("size must be non-negative")


@dc.py_class("weave.RegArrayCast", structural_eq="tree")
class RegArrayCast(Op, mnemonic="weave.RegArrayCast"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    src_dtype: tvm_dtype = dc.field(kw_only=True, lang_kind="attr")
    dst_dtype: tvm_dtype = dc.field(kw_only=True, lang_kind="attr")
    count: int = dc.field(default=0, lang_kind="attr")

    def __init__(
        self,
        src: std.Expr,
        dst: std.Expr,
        offset: std.Expr | None = None,
        *,
        src_dtype: std.TyLike,
        dst_dtype: std.TyLike,
        count: int = 0,
    ) -> None:
        src_dtype = normalize_required_dtype(src_dtype, field_name="src_dtype")
        dst_dtype = normalize_required_dtype(dst_dtype, field_name="dst_dtype")
        self.__ffi_init__(
            src=src,
            dst=dst,
            offset=offset,
            src_dtype=src_dtype,
            dst_dtype=dst_dtype,
            count=count,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        self.src_dtype = normalize_required_dtype(self.src_dtype, field_name="src_dtype")
        self.dst_dtype = normalize_required_dtype(self.dst_dtype, field_name="dst_dtype")


__all__ = [  # noqa: RUF022
    "Elementwise",
    "PredicatedStore",
    "ThreshMask",
    "BitmaskFill",
    "MaskFill",
    "RegArrayCast",
]
