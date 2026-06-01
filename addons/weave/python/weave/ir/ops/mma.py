# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""MMA and tensor-memory operation nodes."""

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

TCGEN05_CP_SHAPES = (
    "4x256b",
    "32x128b.warpx4",
    "64x128b.warpx2::02_13",
    "64x128b.warpx2::01_23",
    "128x128b",
    "128x256b",
)
PACKED_F32X2_OPS = ("add", "sub", "mul", "fma", "max")
FRAGMENT_OPS = (
    "add",
    "fma",
    "mul",
    "sub",
    "neg",
    "abs",
    "max",
    "min",
    "exp2",
    "rsqrt",
    "rcp",
    "cvt_bf16",
    "cvt_f32",
    "mask",
    "bitmask",
)
MMA_TILE_MODES = ("ss", "sr", "rs", "rr")


@dc.py_class("weave.Tcgen05Cp", structural_eq="tree")
class Tcgen05Cp(Op, mnemonic="weave.Tcgen05Cp"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    shape: str = dc.field(default="32x128b.warpx4", lang_kind="attr")
    cta_group: int = dc.field(default=1, lang_kind="attr")
    sbo: int = dc.field(default=128, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")

    def __init__(
        self,
        src: std.Expr,
        dst: std.Expr,
        shape: str = "32x128b.warpx4",
        cta_group: int = 1,
        sbo: int = 128,
        elected: bool = False,
    ) -> None:
        shape = validate_candidate_value(shape, TCGEN05_CP_SHAPES, field_name="shape")
        cta_group = validate_cta_group(cta_group)
        if sbo <= 0 or sbo % 16:
            raise ValueError("sbo must be a positive multiple of 16")
        self.__ffi_init__(src, dst, shape, cta_group, sbo, elected)


@dc.py_class("weave.PackedF32x2", structural_eq="tree")
class PackedF32x2(Op, mnemonic="weave.PackedF32x2"):
    op: str = dc.field(kw_only=True, lang_kind="attr")
    inputs: list[std.Expr] = dc.field(default_factory=list, lang_kind="arg")
    output: std.Expr | None = dc.field(default=None, lang_kind="arg")

    def __post_init__(self) -> None:
        self.op = validate_candidate_value(self.op, PACKED_F32X2_OPS, field_name="op")


@dc.py_class("weave.FragmentOp", structural_eq="tree")
class FragmentOp(Op, mnemonic="weave.FragmentOp"):
    op: str = dc.field(kw_only=True, lang_kind="attr")
    dst: std.Expr = dc.field(lang_kind="arg")
    srcs: list[std.Expr] = dc.field(default_factory=list, lang_kind="arg")
    size: int = dc.field(default=0, lang_kind="attr")
    dtype: tvm_dtype | None = dc.field(default=None, lang_kind="attr")

    def __init__(
        self,
        dst: std.Expr,
        srcs: list[std.Expr] | None = None,
        *,
        op: str,
        size: int = 0,
        dtype: std.TyLike | None = None,
    ) -> None:
        op = validate_candidate_value(op, FRAGMENT_OPS, field_name="op")
        if dtype is not None:
            dtype = normalize_dtype(dtype, field_name="dtype")
        if size < 0:
            raise ValueError("size must be non-negative")
        self.__ffi_init__(
            op=op,
            dst=dst,
            srcs=srcs or [],
            size=size,
            dtype=dtype,
        )


@dc.py_class("weave.MmaTile", structural_eq="tree")
class MmaTile(Op, mnemonic="weave.MmaTile"):
    """High-level MMA tile op retained from the reference catalog."""

    a_desc: std.Expr = dc.field(lang_kind="arg")
    b_desc: std.Expr = dc.field(lang_kind="arg")
    d_tmem: std.Expr = dc.field(lang_kind="arg")
    k_idx: std.Expr = dc.field(lang_kind="arg")
    mode: str = dc.field(default="ss", lang_kind="attr")
    cta_group: int = dc.field(default=1, lang_kind="attr")
    a_dtype: tvm_dtype | None = dc.field(default=None, lang_kind="attr")
    b_dtype: tvm_dtype | None = dc.field(default=None, lang_kind="attr")
    acc_dtype: tvm_dtype | None = dc.field(default=None, lang_kind="attr")

    def __init__(
        self,
        a_desc: std.Expr,
        b_desc: std.Expr,
        d_tmem: std.Expr,
        k_idx: std.Expr,
        mode: str = "ss",
        cta_group: int = 1,
        a_dtype: std.TyLike | None = None,
        b_dtype: std.TyLike | None = None,
        acc_dtype: std.TyLike | None = None,
    ) -> None:
        mode = validate_candidate_value(mode, MMA_TILE_MODES, field_name="mode")
        cta_group = validate_cta_group(cta_group)
        if a_dtype is not None:
            a_dtype = normalize_dtype(a_dtype, field_name="a_dtype")
        if b_dtype is not None:
            b_dtype = normalize_dtype(b_dtype, field_name="b_dtype")
        if acc_dtype is not None:
            acc_dtype = normalize_dtype(acc_dtype, field_name="acc_dtype")
        self.__ffi_init__(
            a_desc,
            b_desc,
            d_tmem,
            k_idx,
            mode,
            cta_group,
            a_dtype,
            b_dtype,
            acc_dtype,
        )


__all__ = [  # noqa: RUF022
    "Tcgen05Cp",
    "PackedF32x2",
    "FragmentOp",
    "MmaTile",
]
