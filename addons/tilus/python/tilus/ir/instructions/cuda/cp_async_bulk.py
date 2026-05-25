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
from .cp_async import CACHE_EVICTS


@py_class("tilus.CopyAsyncBulkGlobalToSharedInst", structural_eq="tree")
class CopyAsyncBulkGlobalToSharedInst(Instruction, mnemonic="tilus.CopyAsyncBulkGlobalToShared"):
    EXPECTED_INPUTS: ClassVar[int] = 2
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = (("offsets", "dims"),)
    VALID_EVICTS: ClassVar[tuple[str, ...]] = CACHE_EVICTS

    offsets: list[std.Expr] = field(lang_kind="attr")
    dims: list[int] = field(lang_kind="attr")
    mbarrier: std.Expr = field(lang_kind="attr")
    evict: str | None = field(default=None, lang_kind="attr")
    check_bounds: bool = field(default=True, lang_kind="attr")


@py_class("tilus.CopyAsyncBulkGlobalToClusterSharedInst", structural_eq="tree")
class CopyAsyncBulkGlobalToClusterSharedInst(
    Instruction, mnemonic="tilus.CopyAsyncBulkGlobalToClusterShared"
):
    EXPECTED_INPUTS: ClassVar[int] = 2
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = (("offsets", "dims"),)
    VALID_EVICTS: ClassVar[tuple[str, ...]] = CACHE_EVICTS

    offsets: list[std.Expr] = field(lang_kind="attr")
    dims: list[int] = field(lang_kind="attr")
    mbarrier: std.Expr = field(lang_kind="attr")
    cta_mask: int = field(lang_kind="attr")
    evict: str | None = field(default=None, lang_kind="attr")
    check_bounds: bool = field(default=True, lang_kind="attr")


@py_class("tilus.CopyAsyncBulkSharedToGlobalInst", structural_eq="tree")
class CopyAsyncBulkSharedToGlobalInst(Instruction, mnemonic="tilus.CopyAsyncBulkSharedToGlobal"):
    EXPECTED_INPUTS: ClassVar[int] = 2
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = (("offsets", "dims"),)
    VALID_L2_EVICTS: ClassVar[tuple[str, ...]] = CACHE_EVICTS

    offsets: list[std.Expr] = field(lang_kind="attr")
    dims: list[int] = field(lang_kind="attr")
    check_bounds: bool = field(default=True, lang_kind="attr")
    l2_evict: str | None = field(default="evict_first", lang_kind="attr")


@py_class("tilus.CopyAsyncBulkSharedToClusterSharedInst", structural_eq="tree")
class CopyAsyncBulkSharedToClusterSharedInst(
    Instruction, mnemonic="tilus.CopyAsyncBulkSharedToClusterShared"
):
    EXPECTED_INPUTS: ClassVar[int] = 2

    mbarrier: std.Expr = field(lang_kind="attr")
    remote_rank: int = field(lang_kind="attr")


@py_class("tilus.CopyAsyncBulkCommitGroupInst", structural_eq="tree")
class CopyAsyncBulkCommitGroupInst(Instruction, mnemonic="tilus.CopyAsyncBulkCommitGroup"):
    EXPECTED_INPUTS: ClassVar[int] = 0


@py_class("tilus.CopyAsyncBulkWaitGroupInst", structural_eq="tree")
class CopyAsyncBulkWaitGroupInst(Instruction, mnemonic="tilus.CopyAsyncBulkWaitGroup"):
    EXPECTED_INPUTS: ClassVar[int] = 0
    NONNEGATIVE_INT_ATTRS: ClassVar[tuple[str, ...]] = ("n",)

    n: int = field(lang_kind="attr")


__all__ = [  # noqa: RUF022
    "CopyAsyncBulkGlobalToSharedInst",
    "CopyAsyncBulkGlobalToClusterSharedInst",
    "CopyAsyncBulkSharedToGlobalInst",
    "CopyAsyncBulkSharedToClusterSharedInst",
    "CopyAsyncBulkCommitGroupInst",
    "CopyAsyncBulkWaitGroupInst",
]
