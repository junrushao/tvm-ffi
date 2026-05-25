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

from typing import Any, ClassVar

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from .._utils import Op, normalize_dtype, normalize_expr_sequence

ELEMENTWISE_OPS = ("fma", "mul", "add", "sub", "fmax", "exp", "bitmask")


@dc.py_class("weave.Elementwise", structural_eq="tree")
class Elementwise(Op, mnemonic="weave.Elementwise"):
    op: str = dc.field(lang_kind="attr")
    inputs: list[std.Expr] = dc.field(default_factory=list, lang_kind="attr")
    output: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("output",))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"op": ELEMENTWISE_OPS}

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "inputs", normalize_expr_sequence(self.inputs, field_name="inputs")
        )
        super().__post_init__()


@dc.py_class("weave.PredicatedStore", structural_eq="tree")
class PredicatedStore(Op, mnemonic="weave.PredicatedStore"):
    dst: std.Expr = dc.field(lang_kind="arg")
    src: std.Expr = dc.field(lang_kind="arg")
    bound_m: std.Expr = dc.field(lang_kind="attr")
    bound_n: std.Expr = dc.field(lang_kind="attr")
    tile_offset_m: std.Expr = dc.field(lang_kind="attr")
    tile_offset_n: std.Expr = dc.field(lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(
        ("dst", "src", "bound_m", "bound_n", "tile_offset_m", "tile_offset_n")
    )


@dc.py_class("weave.ThreshMask", structural_eq="tree")
class ThreshMask(Op, mnemonic="weave.ThreshMask"):
    dst: std.Expr = dc.field(lang_kind="arg")
    limit: std.Expr = dc.field(lang_kind="arg")
    width: int = dc.field(default=32, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("dst", "limit"))

    def __post_init__(self) -> None:
        super().__post_init__()
        if not 1 <= self.width <= 32:
            raise ValueError("width must be in [1, 32]")


@dc.py_class("weave.BitmaskFill", structural_eq="tree")
class BitmaskFill(Op, mnemonic="weave.BitmaskFill"):
    array: std.Expr = dc.field(lang_kind="arg")
    mask: std.Expr = dc.field(lang_kind="arg")
    fill_value: std.Expr | None = dc.field(default=None, lang_kind="attr")
    offset: std.Expr | None = dc.field(default=None, lang_kind="attr")
    count: int = dc.field(default=32, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("array", "mask", "fill_value", "offset"))

    def __post_init__(self) -> None:
        super().__post_init__()
        if not 1 <= self.count <= 32:
            raise ValueError("count must be in [1, 32]")


@dc.py_class("weave.MaskFill", structural_eq="tree")
class MaskFill(Op, mnemonic="weave.MaskFill"):
    array: std.Expr = dc.field(lang_kind="arg")
    fill: std.Expr = dc.field(lang_kind="arg")
    size: int = dc.field(default=0, lang_kind="attr")
    lo: std.Expr | None = dc.field(default=None, lang_kind="attr")
    hi: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("array", "fill", "lo", "hi"))

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.size < 0:
            raise ValueError("size must be non-negative")


@dc.py_class("weave.RegArrayCast", structural_eq="tree")
class RegArrayCast(Op, mnemonic="weave.RegArrayCast"):
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    src_dtype: Any = dc.field(lang_kind="attr")
    dst_dtype: Any = dc.field(lang_kind="attr")
    count: int = dc.field(default=0, lang_kind="attr")
    offset: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "dst", "offset"))

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(
            self, "src_dtype", normalize_dtype(self.src_dtype, field_name="src_dtype")
        )
        object.__setattr__(
            self, "dst_dtype", normalize_dtype(self.dst_dtype, field_name="dst_dtype")
        )


__all__ = [  # noqa: RUF022
    "Elementwise",
    "PredicatedStore",
    "ThreshMask",
    "BitmaskFill",
    "MaskFill",
    "RegArrayCast",
]
