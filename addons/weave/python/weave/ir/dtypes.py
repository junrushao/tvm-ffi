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
"""Weave type and expression helpers built on ``tvm_ffi.std``."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from ._utils import MarkerTy

HandleRef = str | std.Attrs

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


@dc.py_class("weave.Swizzle", structural_eq="tree")
class Swizzle(std.Attrs, mnemonic="weave.Swizzle"):
    """Shared-memory swizzle descriptor."""

    base: int = dc.field(lang_kind="attr")
    bits: int = dc.field(lang_kind="attr")
    shift: int = dc.field(lang_kind="attr")

    def __post_init__(self) -> None:
        if self.base < 0 or self.bits < 0 or self.shift < 0:
            raise ValueError("swizzle fields must be non-negative")

    @property
    def num_bytes(self) -> int:
        return 1 << self.base if self.base else 0


SWIZZLE_NONE = Swizzle(0, 0, 0)
SWIZZLE_32B = Swizzle(5, 4, 3)
SWIZZLE_64B = Swizzle(6, 5, 3)
SWIZZLE_128B = Swizzle(7, 6, 3)


class _LmNamespace:
    """Parser and Python namespace that mirrors Loom's ``lm`` types."""

    i8 = i8
    i16 = i16
    i32 = i32
    i64 = i64
    u8 = u8
    u16 = u16
    u32 = u32
    u64 = u64
    f16 = f16
    bf16 = bf16
    f32 = f32
    f64 = f64
    f8_e4m3 = f8_e4m3
    f8_e5m2 = f8_e5m2
    f8_e8m0fnu = f8_e8m0fnu
    f4_e2m1fn = f4_e2m1fn
    f32x2 = f32x2
    bf16x2 = bf16x2
    raw = RawTy()
    ue4m3 = Ue4m3Ty()
    constexpr = ConstexprTy()
    tma2d = TmaTy(2)
    tma3d = TmaTy(3)
    tma4d = TmaTy(4)
    tma5d = TmaTy(5)
    tma_gather = TmaGatherTy()
    tma_reduce = TmaReduceTy()
    grid_counter = GridCounterTy()

    @staticmethod
    def ptr(
        elem_ty: std.TyLike | None = None,
        *,
        const: bool = False,
        volatile: bool = False,
        space: str | None = None,
    ) -> PtrTy:
        return PtrTy(elem_ty, const=const, volatile=volatile, space=space)

    @staticmethod
    def uniform(base: std.TyLike) -> UniformTy:
        return UniformTy(base)


lm = _LmNamespace()


@dc.py_class("weave.Const", structural_eq="tree")
class Const(std.Expr, mnemonic="weave.Const"):
    """Named compile-time constant expression."""

    name: str = dc.field(lang_kind="attr")
    result_ty: std.Ty = dc.field(default_factory=std.AnyTy, lang_kind="attr")

    def __init__(self, name: str, result_ty: std.TyLike | None = None) -> None:
        result_ty = std.normalize_ty(result_ty, default=std.AnyTy())
        self.__ffi_init__(name, result_ty, ty=result_ty)


@dc.py_class("weave.Field", structural_eq="tree")
class Field(std.Expr, mnemonic="weave.Field"):
    """Field access expression."""

    base: std.Expr = dc.field(lang_kind="arg")
    field: str = dc.field(lang_kind="attr")
    result_ty: std.Ty = dc.field(default_factory=std.AnyTy, lang_kind="attr")

    def __init__(self, base: std.Expr, field: str, result_ty: std.TyLike | None = None) -> None:
        result_ty = std.normalize_ty(result_ty, default=std.AnyTy())
        self.__ffi_init__(base, field, result_ty, ty=result_ty)


@dc.py_class("weave.AddrOf", structural_eq="tree")
class AddrOf(std.Expr, mnemonic="weave.AddrOf"):
    """Address-of expression."""

    expr: std.Expr = dc.field(lang_kind="arg")
    result_ty: PtrTy = dc.field(default_factory=PtrTy, lang_kind="attr")

    def __init__(self, expr: std.Expr, result_ty: std.TyLike | None = None) -> None:
        result_ty = result_ty if isinstance(result_ty, PtrTy) else PtrTy(result_ty)
        self.__ffi_init__(expr, result_ty, ty=result_ty)


@dc.py_class("weave.Deref", structural_eq="tree")
class Deref(std.Expr, mnemonic="weave.Deref"):
    """Pointer dereference expression."""

    expr: std.Expr = dc.field(lang_kind="arg")
    result_ty: std.Ty = dc.field(default_factory=std.AnyTy, lang_kind="attr")

    def __init__(self, expr: std.Expr, result_ty: std.TyLike | None = None) -> None:
        result_ty = std.normalize_ty(result_ty, default=std.AnyTy())
        self.__ffi_init__(expr, result_ty, ty=result_ty)


@dc.py_class("weave.ReinterpretCast", structural_eq="tree")
class ReinterpretCast(std.Expr, mnemonic="weave.ReinterpretCast"):
    """Reinterpret-cast expression."""

    expr: std.Expr = dc.field(lang_kind="arg")
    target_type: std.Ty = dc.field(lang_kind="attr")

    def __init__(self, expr: std.Expr, target_type: std.TyLike) -> None:
        target_type = std.normalize_ty(target_type)
        self.__ffi_init__(expr, target_type, ty=target_type)


@dc.py_class("weave.SmemSwizzleOffset", structural_eq="tree")
class SmemSwizzleOffset(std.Expr, mnemonic="weave.SmemSwizzleOffset"):
    """SMEM swizzle offset expression."""

    expr: std.Expr = dc.field(lang_kind="arg")
    swizzle: Swizzle | None = dc.field(default=None, lang_kind="attr")
    result_ty: std.Ty = dc.field(default_factory=lambda: i32, lang_kind="attr")

    def __init__(
        self,
        expr: std.Expr | bool | int | float,
        swizzle: Swizzle | None = None,
        result_ty: std.TyLike | None = None,
    ) -> None:
        result_ty = std.normalize_ty(result_ty, default=i32)
        self.__ffi_init__(expr, swizzle, result_ty, ty=result_ty)


@dc.py_class("weave.SmemSwizzleAddress", structural_eq="tree")
class SmemSwizzleAddress(std.Expr, mnemonic="weave.SmemSwizzleAddress"):
    """SMEM swizzled address expression."""

    expr: std.Expr = dc.field(lang_kind="arg")
    row_stride_bytes: std.Expr | None = dc.field(default=None, lang_kind="arg")
    coord_row: std.Expr | None = dc.field(default=None, lang_kind="arg")
    coord_col: std.Expr | None = dc.field(default=None, lang_kind="arg")
    swizzle: Swizzle | None = dc.field(default=None, lang_kind="attr")
    view: HandleRef | None = dc.field(default=None, lang_kind="attr")
    layout: str | None = dc.field(default=None, lang_kind="attr")
    coord_col_unit: str | None = dc.field(default=None, lang_kind="attr")
    tcgen05_tile_height: int | None = dc.field(default=None, lang_kind="attr")
    tcgen05_k_elements: int | None = dc.field(default=None, lang_kind="attr")
    addr_space: str | None = dc.field(default=None, lang_kind="attr")
    result_ty: std.Ty = dc.field(default_factory=lambda: u32, lang_kind="attr")

    def __init__(
        self,
        expr: std.Expr | bool | int | float,
        row_stride_bytes: std.Expr | bool | int | float | None = None,
        coord_row: std.Expr | bool | int | float | None = None,
        coord_col: std.Expr | bool | int | float | None = None,
        *,
        swizzle: Swizzle | None = None,
        view: HandleRef | None = None,
        layout: str | None = None,
        coord_col_unit: str | None = None,
        tcgen05_tile_height: int | None = None,
        tcgen05_k_elements: int | None = None,
        addr_space: str | None = None,
        result_ty: std.TyLike | None = None,
    ) -> None:
        result_ty = std.normalize_ty(result_ty, default=u32)
        self.__ffi_init__(
            expr,
            row_stride_bytes,
            coord_row,
            coord_col,
            swizzle,
            view,
            layout,
            coord_col_unit,
            tcgen05_tile_height,
            tcgen05_k_elements,
            addr_space,
            result_ty,
            ty=result_ty,
        )


@dc.py_class("weave.TmemRef", structural_eq="tree")
class TmemRef(std.Expr, mnemonic="weave.TmemRef"):
    """Reference to a tensor-memory region."""

    region: HandleRef = dc.field(kw_only=True, lang_kind="attr")
    offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    result_ty: std.Ty = dc.field(default_factory=lambda: u32, lang_kind="attr")

    def __init__(
        self,
        offset: std.Expr | bool | int | float | None = None,
        *,
        region: HandleRef,
        result_ty: std.TyLike | None = None,
    ) -> None:
        result_ty = std.normalize_ty(result_ty, default=u32)
        self.__ffi_init__(
            region=region,
            offset=offset,
            result_ty=result_ty,
            ty=result_ty,
        )


@dc.py_class("weave.SmemRef", structural_eq="tree")
class SmemRef(std.Expr, mnemonic="weave.SmemRef"):
    """Reference to shared memory."""

    buffer: HandleRef = dc.field(kw_only=True, lang_kind="attr")
    offset: std.Expr | None = dc.field(default=None, lang_kind="arg")
    result_ty: std.Ty = dc.field(default_factory=lambda: u32, lang_kind="attr")

    def __init__(
        self,
        offset: std.Expr | bool | int | float | None = None,
        *,
        buffer: HandleRef,
        result_ty: std.TyLike | None = None,
    ) -> None:
        result_ty = std.normalize_ty(result_ty, default=u32)
        self.__ffi_init__(
            buffer=buffer,
            offset=offset,
            result_ty=result_ty,
            ty=result_ty,
        )


@dc.py_class("weave.SmemDescRef", structural_eq="tree")
class SmemDescRef(std.Expr, mnemonic="weave.SmemDescRef"):
    """Reference to a generated SMEM descriptor."""

    buffer: HandleRef = dc.field(kw_only=True, lang_kind="attr")
    k_idx: std.Expr = dc.field(lang_kind="arg")
    mode: str = dc.field(default="k", lang_kind="attr")
    result_ty: std.Ty = dc.field(default_factory=lambda: u64, lang_kind="attr")

    def __init__(
        self,
        k_idx: std.Expr | bool | int | float,
        *,
        buffer: HandleRef,
        mode: str = "k",
        result_ty: std.TyLike | None = None,
    ) -> None:
        result_ty = std.normalize_ty(result_ty, default=u64)
        self.__ffi_init__(
            buffer=buffer,
            k_idx=k_idx,
            mode=mode,
            result_ty=result_ty,
            ty=result_ty,
        )


@dc.py_class("weave.BarrierRef", structural_eq="tree")
class BarrierRef(std.Expr, mnemonic="weave.BarrierRef"):
    """Reference to an mbarrier address."""

    barrier: HandleRef = dc.field(kw_only=True, lang_kind="attr")
    stage: std.Expr | None = dc.field(default=None, lang_kind="arg")
    result_ty: std.Ty = dc.field(default_factory=lambda: u64, lang_kind="attr")

    def __init__(
        self,
        stage: std.Expr | bool | int | float | None = None,
        *,
        barrier: HandleRef,
        result_ty: std.TyLike | None = None,
    ) -> None:
        result_ty = std.normalize_ty(result_ty, default=u64)
        self.__ffi_init__(
            barrier=barrier,
            stage=stage,
            result_ty=result_ty,
            ty=result_ty,
        )


@dc.py_class("weave.BuiltinRef", structural_eq="tree")
class BuiltinRef(std.Expr, mnemonic="weave.BuiltinRef"):
    """Reference to a lowering-provided builtin value."""

    name: str = dc.field(lang_kind="attr")
    result_ty: std.Ty = dc.field(default_factory=std.AnyTy, lang_kind="attr")

    def __init__(self, name: str, result_ty: std.TyLike | None = None) -> None:
        result_ty = std.normalize_ty(result_ty, default=std.AnyTy())
        self.__ffi_init__(name, result_ty, ty=result_ty)


__all__ = [
    "SWIZZLE_32B",
    "SWIZZLE_64B",
    "SWIZZLE_128B",
    "SWIZZLE_NONE",
    "AddrOf",
    "BarrierRef",
    "BuiltinRef",
    "Const",
    "ConstexprTy",
    "Deref",
    "Field",
    "GridCounterTy",
    "PtrTy",
    "RawTy",
    "ReinterpretCast",
    "SmemDescRef",
    "SmemRef",
    "SmemSwizzleAddress",
    "SmemSwizzleOffset",
    "Swizzle",
    "TmaGatherTy",
    "TmaReduceTy",
    "TmaTy",
    "TmemRef",
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
    "lm",
    "u8",
    "u16",
    "u32",
    "u64",
]
