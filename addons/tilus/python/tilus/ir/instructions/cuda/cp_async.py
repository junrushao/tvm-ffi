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

CACHE_EVICTS = ("evict_normal", "evict_first", "evict_last", "evict_unchanged", "no_allocate")


@py_class("tilus.CopyAsyncInst", structural_eq="tree")
class CopyAsyncInst(Instruction, mnemonic="tilus.CopyAsync"):
    EXPECTED_INPUTS: ClassVar[int] = 2
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = (("offsets", "dims"),)
    VALID_EVICTS: ClassVar[tuple[str, ...]] = CACHE_EVICTS

    offsets: list[std.Expr] = field(lang_kind="attr")
    dims: list[int] | None = field(default=None, lang_kind="attr")
    evict: str | None = field(default=None, lang_kind="attr")
    check_bounds: bool = field(default=True, lang_kind="attr")


@py_class("tilus.CopyAsyncGenericInst", structural_eq="tree")
class CopyAsyncGenericInst(Instruction, mnemonic="tilus.CopyAsyncGeneric"):
    EXPECTED_INPUTS: ClassVar[int] = 0
    VALID_EVICTS: ClassVar[tuple[str, ...]] = CACHE_EVICTS

    ptr: str = field(lang_kind="attr")
    axes: list[str] = field(lang_kind="attr")
    offset: std.Expr = field(lang_kind="attr")
    mask: std.Expr | None = field(default=None, lang_kind="attr")
    evict: str | None = field(default=None, lang_kind="attr")


@py_class("tilus.CopyAsyncCommitGroupInst", structural_eq="tree")
class CopyAsyncCommitGroupInst(Instruction, mnemonic="tilus.CopyAsyncCommitGroup"):
    EXPECTED_INPUTS: ClassVar[int] = 0


@py_class("tilus.CopyAsyncWaitGroupInst", structural_eq="tree")
class CopyAsyncWaitGroupInst(Instruction, mnemonic="tilus.CopyAsyncWaitGroup"):
    EXPECTED_INPUTS: ClassVar[int] = 0
    NONNEGATIVE_INT_ATTRS: ClassVar[tuple[str, ...]] = ("n",)

    n: std.Expr = field(lang_kind="attr")


@py_class("tilus.CopyAsyncWaitAllInst", structural_eq="tree")
class CopyAsyncWaitAllInst(Instruction, mnemonic="tilus.CopyAsyncWaitAll"):
    EXPECTED_INPUTS: ClassVar[int] = 0


__all__ = [  # noqa: RUF022
    "CopyAsyncInst",
    "CopyAsyncGenericInst",
    "CopyAsyncCommitGroupInst",
    "CopyAsyncWaitGroupInst",
    "CopyAsyncWaitAllInst",
]
