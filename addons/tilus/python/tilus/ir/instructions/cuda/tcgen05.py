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

from typing import ClassVar

from tvm_ffi import std
from tvm_ffi.dataclasses import field, py_class

from ...inst import Instruction


@py_class("tilus.Tcgen05AllocInst", structural_eq="tree")
class Tcgen05AllocInst(Instruction, mnemonic="tilus.Tcgen05Alloc"):
    EXPECTED_INPUTS: ClassVar[int] = 0
    VALID_CTA_GROUPS: ClassVar[tuple[int, ...]] = (1, 2)

    cta_group: std.Expr = field(lang_kind="attr")


@py_class("tilus.Tcgen05DeallocInst", structural_eq="tree")
class Tcgen05DeallocInst(Instruction, mnemonic="tilus.Tcgen05Dealloc"):
    EXPECTED_INPUTS: ClassVar[int] = 0


@py_class("tilus.Tcgen05RelinquishAllocPermitInst", structural_eq="tree")
class Tcgen05RelinquishAllocPermitInst(Instruction, mnemonic="tilus.Tcgen05RelinquishAllocPermit"):
    EXPECTED_INPUTS: ClassVar[int] = 0
    VALID_CTA_GROUPS: ClassVar[tuple[int, ...]] = (1, 2)

    cta_group: std.Expr = field(default_factory=lambda: std.IntImm.from_py(1), lang_kind="attr")


@py_class("tilus.Tcgen05SliceInst", structural_eq="tree")
class Tcgen05SliceInst(Instruction, mnemonic="tilus.Tcgen05Slice"):
    EXPECTED_INPUTS: ClassVar[int] = 1
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = (("offsets", "slice_dims"),)

    offsets: list[std.Expr] = field(lang_kind="attr")
    slice_dims: list[int] = field(lang_kind="attr")


@py_class("tilus.Tcgen05ViewInst", structural_eq="tree")
class Tcgen05ViewInst(Instruction, mnemonic="tilus.Tcgen05View"):
    EXPECTED_INPUTS: ClassVar[int] = 0


@py_class("tilus.Tcgen05LoadInst", structural_eq="tree")
class Tcgen05LoadInst(Instruction, mnemonic="tilus.Tcgen05Load"):
    EXPECTED_INPUTS: ClassVar[int] = 0


@py_class("tilus.Tcgen05StoreInst", structural_eq="tree")
class Tcgen05StoreInst(Instruction, mnemonic="tilus.Tcgen05Store"):
    EXPECTED_INPUTS: ClassVar[int] = 0


@py_class("tilus.Tcgen05WaitInst", structural_eq="tree")
class Tcgen05WaitInst(Instruction, mnemonic="tilus.Tcgen05Wait"):
    EXPECTED_INPUTS: ClassVar[int] = 0

    wait_load: bool = field(lang_kind="attr")
    wait_store: bool = field(lang_kind="attr")


@py_class("tilus.Tcgen05CopyInst", structural_eq="tree")
class Tcgen05CopyInst(Instruction, mnemonic="tilus.Tcgen05Copy"):
    EXPECTED_INPUTS: ClassVar[int] = 0


@py_class("tilus.Tcgen05CommitInst", structural_eq="tree")
class Tcgen05CommitInst(Instruction, mnemonic="tilus.Tcgen05Commit"):
    EXPECTED_INPUTS: ClassVar[int] = 0
    VALID_CTA_GROUPS: ClassVar[tuple[int, ...]] = (1, 2)

    mbarrier: std.Expr = field(lang_kind="attr")
    cta_group: std.Expr = field(lang_kind="attr")
    multicast_mask: int | None = field(default=None, lang_kind="attr")


@py_class("tilus.Tcgen05MmaSSInst", structural_eq="tree")
class Tcgen05MmaSSInst(Instruction, mnemonic="tilus.Tcgen05MmaSS"):
    EXPECTED_INPUTS: ClassVar[int] = 2
    VALID_CTA_GROUPS: ClassVar[tuple[int, ...]] = (1, 2)

    enable_input_d: std.Expr = field(lang_kind="attr")
    cta_group: std.Expr = field(lang_kind="attr")


@py_class("tilus.Tcgen05MmaTSInst", structural_eq="tree")
class Tcgen05MmaTSInst(Instruction, mnemonic="tilus.Tcgen05MmaTS"):
    EXPECTED_INPUTS: ClassVar[int] = 2
    VALID_CTA_GROUPS: ClassVar[tuple[int, ...]] = (1, 2)

    enable_input_d: std.Expr = field(lang_kind="attr")
    cta_group: std.Expr = field(lang_kind="attr")


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
