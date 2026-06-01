# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Weave type nodes and dtype namespace helpers."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from ._utils import MarkerTy

i8 = std.PrimTy("int8")
i16 = std.PrimTy("int16")
i32 = std.PrimTy("int32")
i64 = std.PrimTy("int64")
u8 = std.PrimTy("uint8")
u16 = std.PrimTy("uint16")
u32 = std.PrimTy("uint32")
u64 = std.PrimTy("uint64")
f16 = std.PrimTy("float16")
bf16 = std.PrimTy("bfloat16")
f32 = std.PrimTy("float32")
f64 = std.PrimTy("float64")
f8_e4m3 = std.PrimTy("float8_e4m3")
f8_e5m2 = std.PrimTy("float8_e5m2")
f8_e8m0fnu = std.PrimTy("float8_e8m0fnu")
f4_e2m1fn = std.PrimTy("float4_e2m1fn")
f32x2 = std.PrimTy("float32x2")
bf16x2 = std.PrimTy("bfloat16x2")


@dc.py_class("weave.RawTy", structural_eq="tree")
class RawTy(MarkerTy, mnemonic="weave.RawTy"):
    """Opaque raw payload type."""


@dc.py_class("weave.Ue4m3Ty", structural_eq="tree")
class Ue4m3Ty(MarkerTy, mnemonic="weave.Ue4m3Ty"):
    """Unsigned e4m3 scale-factor payload type."""


@dc.py_class("weave.ConstexprTy", structural_eq="tree")
class ConstexprTy(MarkerTy, mnemonic="weave.ConstexprTy"):
    """Compile-time constexpr marker type."""


@dc.py_class("weave.TmaGatherTy", structural_eq="tree")
class TmaGatherTy(MarkerTy, mnemonic="weave.TmaGatherTy"):
    """TMA gather descriptor marker type."""


@dc.py_class("weave.TmaReduceTy", structural_eq="tree")
class TmaReduceTy(MarkerTy, mnemonic="weave.TmaReduceTy"):
    """TMA reduce descriptor marker type."""


@dc.py_class("weave.GridCounterTy", structural_eq="tree")
class GridCounterTy(MarkerTy, mnemonic="weave.GridCounterTy"):
    """Grid dependency counter marker type."""


@dc.py_class("weave.TmaTy", structural_eq="tree")
class TmaTy(std.Ty, mnemonic="weave.TmaTy"):
    """TMA descriptor type with fixed rank."""

    ndim: int = dc.field(lang_kind="attr")

    def __post_init__(self) -> None:
        if self.ndim <= 0:
            raise ValueError("ndim must be positive")


@dc.py_class("weave.UniformTy", structural_eq="tree")
class UniformTy(std.Ty, mnemonic="weave.UniformTy"):
    """Warp-uniform scalar type wrapper."""

    base: std.Ty = dc.field(lang_kind="attr")

    def __post_init__(self) -> None:
        self.base = std.normalize_ty(self.base)


@dc.py_class("weave.PtrTy", structural_eq="tree")
class PtrTy(std.Ty, mnemonic="weave.PtrTy"):
    """Pointer type with optional address space and qualifiers."""

    elem_ty: std.Ty | None = dc.field(default=None, lang_kind="attr")
    const: bool = dc.field(default=False, lang_kind="attr")
    volatile: bool = dc.field(default=False, lang_kind="attr")
    space: str | None = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        if self.elem_ty is not None:
            self.elem_ty = std.normalize_ty(self.elem_ty)


__all__ = [
    "ConstexprTy",
    "GridCounterTy",
    "PtrTy",
    "RawTy",
    "TmaGatherTy",
    "TmaReduceTy",
    "TmaTy",
    "Ue4m3Ty",
    "UniformTy",
    "bf16",
    "bf16x2",
    "f4_e2m1fn",
    "f8_e4m3",
    "f8_e5m2",
    "f8_e8m0fnu",
    "f16",
    "f32",
    "f32x2",
    "f64",
    "i8",
    "i16",
    "i32",
    "i64",
    "u8",
    "u16",
    "u32",
    "u64",
]
