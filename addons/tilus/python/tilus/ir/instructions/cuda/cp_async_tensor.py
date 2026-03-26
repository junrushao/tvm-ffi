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


@py_class("tilus.CopyAsyncTensorGlobalToSharedInst", structural_eq="tree")
class CopyAsyncTensorGlobalToSharedInst(
    Instruction, mnemonic="tilus.CopyAsyncTensorGlobalToShared"
):
    EXPECTED_INPUTS: ClassVar[int] = 2
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = (("offsets", "dims"),)
    VALID_CTA_GROUPS: ClassVar[tuple[int, ...]] = (1, 2)

    offsets: list[std.Expr] = field(lang_kind="attr")
    dims: list[int] = field(lang_kind="attr")
    mbarrier: std.Expr = field(lang_kind="attr")
    cta_group: std.Expr = field(lang_kind="attr")
    multicast_mask: std.Expr | None = field(default=None, lang_kind="attr")
    cache_policy: std.Expr | None = field(default=None, lang_kind="attr")


@py_class("tilus.CopyAsyncTensorSharedToGlobalInst", structural_eq="tree")
class CopyAsyncTensorSharedToGlobalInst(
    Instruction, mnemonic="tilus.CopyAsyncTensorSharedToGlobal"
):
    EXPECTED_INPUTS: ClassVar[int] = 2
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = (("offsets", "dims"),)

    offsets: list[std.Expr] = field(lang_kind="attr")
    dims: list[int] = field(lang_kind="attr")
    cache_policy: std.Expr | None = field(default=None, lang_kind="attr")


@py_class("tilus.CopyAsyncTensorCommitGroupInst", structural_eq="tree")
class CopyAsyncTensorCommitGroupInst(Instruction, mnemonic="tilus.CopyAsyncTensorCommitGroup"):
    EXPECTED_INPUTS: ClassVar[int] = 0


@py_class("tilus.CopyAsyncTensorWaitGroupInst", structural_eq="tree")
class CopyAsyncTensorWaitGroupInst(Instruction, mnemonic="tilus.CopyAsyncTensorWaitGroup"):
    EXPECTED_INPUTS: ClassVar[int] = 0
    NONNEGATIVE_INT_ATTRS: ClassVar[tuple[str, ...]] = ("n",)

    n: int = field(lang_kind="attr")
    read: bool = field(default=False, lang_kind="attr")


__all__ = [  # noqa: RUF022
    "CopyAsyncTensorGlobalToSharedInst",
    "CopyAsyncTensorSharedToGlobalInst",
    "CopyAsyncTensorCommitGroupInst",
    "CopyAsyncTensorWaitGroupInst",
]
