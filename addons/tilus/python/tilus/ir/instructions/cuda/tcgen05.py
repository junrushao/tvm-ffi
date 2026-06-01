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

from __future__ import annotations

from tvm_ffi import std
from tvm_ffi.dataclasses import field, py_class

from ...inst import (
    Instruction,
    make_output_var,
    validate_int_attr,
    validate_matching_lengths,
)


@py_class("tilus.Tcgen05AllocInst", structural_eq="tree")
class Tcgen05AllocInst(Instruction, mnemonic="tilus.Tcgen05Alloc"):
    cta_group: int = field(lang_kind="attr")

    def __init__(self, cta_group: int) -> None:
        self.__ffi_init__(cta_group=validate_int_attr(cta_group, "cta_group", (1, 2)))

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.Tcgen05DeallocInst", structural_eq="tree")
class Tcgen05DeallocInst(Instruction, mnemonic="tilus.Tcgen05Dealloc"):
    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.Tcgen05RelinquishAllocPermitInst", structural_eq="tree")
class Tcgen05RelinquishAllocPermitInst(Instruction, mnemonic="tilus.Tcgen05RelinquishAllocPermit"):
    cta_group: int = field(default=1, lang_kind="attr")

    def __init__(self, cta_group: int = 1) -> None:
        self.__ffi_init__(cta_group=validate_int_attr(cta_group, "cta_group", (1, 2)))

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.Tcgen05SliceInst", structural_eq="tree")
class Tcgen05SliceInst(Instruction, mnemonic="tilus.Tcgen05Slice"):
    src: std.Expr = field(lang_kind="arg")
    offsets: list[std.Expr] = field(lang_kind="arg")
    slice_dims: list[int] = field(lang_kind="attr")
    output: std.Var = field(
        kw_only=True,
        lang_kind="out",
        structural_eq="def-recursive",
    )

    def __init__(
        self,
        src: std.Expr,
        offsets: list[std.Expr],
        slice_dims: list[int],
        *,
        output: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        output = make_output_var(output, ty)
        self.__ffi_init__(src, offsets=offsets, slice_dims=slice_dims, output=output)
        validate_matching_lengths(self, "offsets", "slice_dims")

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


@py_class("tilus.Tcgen05ViewInst", structural_eq="tree")
class Tcgen05ViewInst(Instruction, mnemonic="tilus.Tcgen05View"):
    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.Tcgen05LoadInst", structural_eq="tree")
class Tcgen05LoadInst(Instruction, mnemonic="tilus.Tcgen05Load"):
    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.Tcgen05StoreInst", structural_eq="tree")
class Tcgen05StoreInst(Instruction, mnemonic="tilus.Tcgen05Store"):
    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.Tcgen05WaitInst", structural_eq="tree")
class Tcgen05WaitInst(Instruction, mnemonic="tilus.Tcgen05Wait"):
    wait_load: bool = field(lang_kind="attr")
    wait_store: bool = field(lang_kind="attr")

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.Tcgen05CopyInst", structural_eq="tree")
class Tcgen05CopyInst(Instruction, mnemonic="tilus.Tcgen05Copy"):
    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.Tcgen05CommitInst", structural_eq="tree")
class Tcgen05CommitInst(Instruction, mnemonic="tilus.Tcgen05Commit"):
    mbarrier: std.Expr = field(lang_kind="arg")
    cta_group: int = field(lang_kind="attr")
    multicast_mask: int | None = field(default=None, lang_kind="attr")

    def __init__(
        self,
        mbarrier: std.Expr,
        cta_group: int,
        multicast_mask: int | None = None,
    ) -> None:
        self.__ffi_init__(
            mbarrier=mbarrier,
            cta_group=validate_int_attr(cta_group, "cta_group", (1, 2)),
            multicast_mask=multicast_mask,
        )

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.Tcgen05MmaSSInst", structural_eq="tree")
class Tcgen05MmaSSInst(Instruction, mnemonic="tilus.Tcgen05MmaSS"):
    lhs: std.Expr = field(lang_kind="arg")
    rhs: std.Expr = field(lang_kind="arg")
    enable_input_d: std.Expr = field(lang_kind="arg")
    cta_group: int = field(lang_kind="attr")
    output: std.Var = field(
        kw_only=True,
        lang_kind="out",
        structural_eq="def-recursive",
    )

    def __init__(
        self,
        lhs: std.Expr,
        rhs: std.Expr,
        enable_input_d: std.Expr,
        cta_group: int,
        *,
        output: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        output = make_output_var(output, ty)
        self.__ffi_init__(
            lhs,
            rhs,
            enable_input_d=enable_input_d,
            cta_group=validate_int_attr(cta_group, "cta_group", (1, 2)),
            output=output,
        )

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


@py_class("tilus.Tcgen05MmaTSInst", structural_eq="tree")
class Tcgen05MmaTSInst(Instruction, mnemonic="tilus.Tcgen05MmaTS"):
    lhs: std.Expr = field(lang_kind="arg")
    rhs: std.Expr = field(lang_kind="arg")
    enable_input_d: std.Expr = field(lang_kind="arg")
    cta_group: int = field(lang_kind="attr")
    output: std.Var = field(
        kw_only=True,
        lang_kind="out",
        structural_eq="def-recursive",
    )

    def __init__(
        self,
        lhs: std.Expr,
        rhs: std.Expr,
        enable_input_d: std.Expr,
        cta_group: int,
        *,
        output: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        output = make_output_var(output, ty)
        self.__ffi_init__(
            lhs,
            rhs,
            enable_input_d=enable_input_d,
            cta_group=validate_int_attr(cta_group, "cta_group", (1, 2)),
            output=output,
        )

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


__all__ = [  # noqa: RUF022
    "Tcgen05AllocInst",
    "Tcgen05DeallocInst",
    "Tcgen05RelinquishAllocPermitInst",
    "Tcgen05SliceInst",
    "Tcgen05ViewInst",
    "Tcgen05LoadInst",
    "Tcgen05StoreInst",
    "Tcgen05WaitInst",
    "Tcgen05CopyInst",
    "Tcgen05CommitInst",
    "Tcgen05MmaSSInst",
    "Tcgen05MmaTSInst",
]
