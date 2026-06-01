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

CACHE_EVICTS = ("evict_normal", "evict_first", "evict_last", "evict_unchanged", "no_allocate")


@py_class("tilus.CopyAsyncInst", structural_eq="tree")
class CopyAsyncInst(Instruction, mnemonic="tilus.CopyAsync"):
    src: std.Expr = field(lang_kind="arg")
    dst: std.Expr = field(lang_kind="arg")
    offsets: list[std.Expr] = field(lang_kind="arg")
    dims: list[int] | None = field(default=None, lang_kind="attr")
    evict: str | None = field(default=None, lang_kind="attr")
    check_bounds: bool = field(default=True, lang_kind="attr")

    def __post_init__(self) -> None:
        validate_matching_lengths(self, "offsets", "dims")
        validate_string_attr(self.evict, "evict", CACHE_EVICTS)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncGenericInst", structural_eq="tree")
class CopyAsyncGenericInst(Instruction, mnemonic="tilus.CopyAsyncGeneric"):
    offset: std.Expr = field(lang_kind="arg")
    ptr: str = field(kw_only=True, lang_kind="attr")
    axes: list[str] = field(kw_only=True, lang_kind="attr")
    mask: std.Expr | None = field(default=None, lang_kind="arg")
    evict: str | None = field(default=None, lang_kind="attr")

    def __init__(
        self,
        offset: std.Expr,
        mask: std.Expr | None = None,
        *,
        ptr: str,
        axes: list[str],
        evict: str | None = None,
    ) -> None:
        validate_string_attr(evict, "evict", CACHE_EVICTS)
        self.__ffi_init__(offset=offset, mask=mask, ptr=ptr, axes=axes, evict=evict)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncCommitGroupInst", structural_eq="tree")
class CopyAsyncCommitGroupInst(Instruction, mnemonic="tilus.CopyAsyncCommitGroup"):
    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncWaitGroupInst", structural_eq="tree")
class CopyAsyncWaitGroupInst(Instruction, mnemonic="tilus.CopyAsyncWaitGroup"):
    n: int = field(lang_kind="attr")

    def __init__(self, n: int) -> None:
        self.__ffi_init__(n=validate_nonnegative_int_attr(n, "n"))

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncWaitAllInst", structural_eq="tree")
class CopyAsyncWaitAllInst(Instruction, mnemonic="tilus.CopyAsyncWaitAll"):
    def outputs(self) -> tuple[std.Var, ...]:
        return ()


__all__ = [  # noqa: RUF022
    "CopyAsyncInst",
    "CopyAsyncGenericInst",
    "CopyAsyncCommitGroupInst",
    "CopyAsyncWaitGroupInst",
    "CopyAsyncWaitAllInst",
]
