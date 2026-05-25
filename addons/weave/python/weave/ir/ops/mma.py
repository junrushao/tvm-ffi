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

from typing import Any, ClassVar

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from .._utils import Op, normalize_dtype, normalize_expr_sequence, validate_cta_group

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
    cta_group: Any = dc.field(default=1, lang_kind="attr")
    sbo: int = dc.field(default=128, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst"))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"shape": TCGEN05_CP_SHAPES}

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))
        if self.sbo <= 0 or self.sbo % 16:
            raise ValueError("sbo must be a positive multiple of 16")


@dc.py_class("weave.PackedF32x2", structural_eq="tree")
class PackedF32x2(Op, mnemonic="weave.PackedF32x2"):
    op: str = dc.field(lang_kind="arg")
    inputs: list[std.Expr] = dc.field(default_factory=list, lang_kind="attr")
    output: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("output",))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"op": PACKED_F32X2_OPS}

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "inputs", normalize_expr_sequence(self.inputs, field_name="inputs")
        )
        super().__post_init__()


@dc.py_class("weave.FragmentOp", structural_eq="tree")
class FragmentOp(Op, mnemonic="weave.FragmentOp"):
    op: str = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    srcs: list[std.Expr] = dc.field(default_factory=list, lang_kind="attr")
    size: int = dc.field(default=0, lang_kind="attr")
    dtype: Any = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("dst",))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"op": FRAGMENT_OPS}

    def __post_init__(self) -> None:
        object.__setattr__(self, "srcs", normalize_expr_sequence(self.srcs, field_name="srcs"))
        super().__post_init__()
        object.__setattr__(self, "dtype", normalize_dtype(self.dtype, field_name="dtype"))
        if self.size < 0:
            raise ValueError("size must be non-negative")


@dc.py_class("weave.MmaTile", structural_eq="tree")
class MmaTile(Op, mnemonic="weave.MmaTile"):
    """High-level MMA tile op retained from the reference catalog."""

    a_desc: std.Expr = dc.field(lang_kind="arg")
    b_desc: std.Expr = dc.field(lang_kind="arg")
    d_tmem: std.Expr = dc.field(lang_kind="arg")
    k_idx: std.Expr = dc.field(lang_kind="attr")
    mode: str = dc.field(default="ss", lang_kind="attr")
    cta_group: Any = dc.field(default=1, lang_kind="attr")
    a_dtype: Any = dc.field(default=None, lang_kind="attr")
    b_dtype: Any = dc.field(default=None, lang_kind="attr")
    acc_dtype: Any = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("a_desc", "b_desc", "d_tmem", "k_idx"))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"mode": MMA_TILE_MODES}

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))
        for name in ("a_dtype", "b_dtype", "acc_dtype"):
            object.__setattr__(
                self,
                name,
                normalize_dtype(getattr(self, name), field_name=name),
            )


__all__ = [  # noqa: RUF022
    "Tcgen05Cp",
    "PackedF32x2",
    "FragmentOp",
    "MmaTile",
]
