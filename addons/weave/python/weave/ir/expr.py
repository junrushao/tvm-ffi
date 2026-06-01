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
"""Weave expression nodes built on ``tvm_ffi.std``."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from .swizzle import Swizzle
from .types import PtrTy, i32, u32, u64

HandleRef = str | std.Attrs


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
    "AddrOf",
    "BarrierRef",
    "BuiltinRef",
    "Const",
    "Deref",
    "Field",
    "ReinterpretCast",
    "SmemDescRef",
    "SmemRef",
    "SmemSwizzleAddress",
    "SmemSwizzleOffset",
    "TmemRef",
]
