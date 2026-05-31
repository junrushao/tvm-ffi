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
    validate_matching_lengths,
    validate_nonnegative_int_attr,
    validate_string_attr,
)
from .cp_async import CACHE_EVICTS


@py_class("tilus.CopyAsyncBulkGlobalToSharedInst", structural_eq="tree")
class CopyAsyncBulkGlobalToSharedInst(Instruction, mnemonic="tilus.CopyAsyncBulkGlobalToShared"):
    src: std.Expr = field(lang_kind="arg")
    dst: std.Expr = field(lang_kind="arg")
    offsets: list[std.Expr] = field(lang_kind="arg")
    mbarrier: std.Expr = field(lang_kind="arg")
    dims: list[int] = field(lang_kind="attr")
    evict: str | None = field(default=None, lang_kind="attr")
    check_bounds: bool = field(default=True, lang_kind="attr")

    def __post_init__(self) -> None:
        validate_matching_lengths(self, "offsets", "dims")
        validate_string_attr(self.evict, "evict", CACHE_EVICTS)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncBulkGlobalToClusterSharedInst", structural_eq="tree")
class CopyAsyncBulkGlobalToClusterSharedInst(
    Instruction, mnemonic="tilus.CopyAsyncBulkGlobalToClusterShared"
):
    src: std.Expr = field(lang_kind="arg")
    dst: std.Expr = field(lang_kind="arg")
    offsets: list[std.Expr] = field(lang_kind="arg")
    mbarrier: std.Expr = field(lang_kind="arg")
    dims: list[int] = field(lang_kind="attr")
    cta_mask: int = field(lang_kind="attr")
    evict: str | None = field(default=None, lang_kind="attr")
    check_bounds: bool = field(default=True, lang_kind="attr")

    def __post_init__(self) -> None:
        validate_matching_lengths(self, "offsets", "dims")
        validate_string_attr(self.evict, "evict", CACHE_EVICTS)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncBulkSharedToGlobalInst", structural_eq="tree")
class CopyAsyncBulkSharedToGlobalInst(Instruction, mnemonic="tilus.CopyAsyncBulkSharedToGlobal"):
    src: std.Expr = field(lang_kind="arg")
    dst: std.Expr = field(lang_kind="arg")
    offsets: list[std.Expr] = field(lang_kind="arg")
    dims: list[int] = field(lang_kind="attr")
    check_bounds: bool = field(default=True, lang_kind="attr")
    l2_evict: str | None = field(default="evict_first", lang_kind="attr")

    def __post_init__(self) -> None:
        validate_matching_lengths(self, "offsets", "dims")
        validate_string_attr(self.l2_evict, "l2_evict", CACHE_EVICTS)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncBulkSharedToClusterSharedInst", structural_eq="tree")
class CopyAsyncBulkSharedToClusterSharedInst(
    Instruction, mnemonic="tilus.CopyAsyncBulkSharedToClusterShared"
):
    src: std.Expr = field(lang_kind="arg")
    dst: std.Expr = field(lang_kind="arg")
    mbarrier: std.Expr = field(lang_kind="arg")
    remote_rank: int = field(lang_kind="attr")

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncBulkCommitGroupInst", structural_eq="tree")
class CopyAsyncBulkCommitGroupInst(Instruction, mnemonic="tilus.CopyAsyncBulkCommitGroup"):
    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncBulkWaitGroupInst", structural_eq="tree")
class CopyAsyncBulkWaitGroupInst(Instruction, mnemonic="tilus.CopyAsyncBulkWaitGroup"):
    n: int = field(lang_kind="attr")

    def __init__(self, n: int) -> None:
        self.__ffi_init__(n=validate_nonnegative_int_attr(n, "n"))
        self.__post_init__()

    def __post_init__(self) -> None:
        self.n = validate_nonnegative_int_attr(self.n, "n")

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


__all__ = [  # noqa: RUF022
    "CopyAsyncBulkGlobalToSharedInst",
    "CopyAsyncBulkGlobalToClusterSharedInst",
    "CopyAsyncBulkSharedToGlobalInst",
    "CopyAsyncBulkSharedToClusterSharedInst",
    "CopyAsyncBulkCommitGroupInst",
    "CopyAsyncBulkWaitGroupInst",
]
