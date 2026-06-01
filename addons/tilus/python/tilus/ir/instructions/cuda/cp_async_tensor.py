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
    validate_int_attr,
    validate_matching_lengths,
    validate_nonnegative_int_attr,
)


@py_class("tilus.CopyAsyncTensorGlobalToSharedInst", structural_eq="tree")
class CopyAsyncTensorGlobalToSharedInst(
    Instruction, mnemonic="tilus.CopyAsyncTensorGlobalToShared"
):
    src: std.Expr = field(lang_kind="arg")
    dst: std.Expr = field(lang_kind="arg")
    offsets: list[std.Expr] = field(lang_kind="arg")
    mbarrier: std.Expr = field(lang_kind="arg")
    dims: list[int] = field(kw_only=True, lang_kind="attr")
    cta_group: int = field(kw_only=True, lang_kind="attr")
    multicast_mask: std.Expr | None = field(default=None, lang_kind="arg")
    cache_policy: std.Expr | None = field(default=None, lang_kind="arg")

    def __init__(
        self,
        src: std.Expr,
        dst: std.Expr,
        offsets: list[std.Expr],
        mbarrier: std.Expr,
        multicast_mask: std.Expr | None = None,
        cache_policy: std.Expr | None = None,
        *,
        dims: list[int],
        cta_group: int,
    ) -> None:
        self.__ffi_init__(
            src=src,
            dst=dst,
            offsets=offsets,
            mbarrier=mbarrier,
            multicast_mask=multicast_mask,
            cache_policy=cache_policy,
            dims=dims,
            cta_group=validate_int_attr(cta_group, "cta_group", (1, 2)),
        )
        validate_matching_lengths(self, "offsets", "dims")

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncTensorSharedToGlobalInst", structural_eq="tree")
class CopyAsyncTensorSharedToGlobalInst(
    Instruction, mnemonic="tilus.CopyAsyncTensorSharedToGlobal"
):
    src: std.Expr = field(lang_kind="arg")
    dst: std.Expr = field(lang_kind="arg")
    offsets: list[std.Expr] = field(lang_kind="arg")
    dims: list[int] = field(kw_only=True, lang_kind="attr")
    cache_policy: std.Expr | None = field(default=None, lang_kind="arg")

    def __init__(
        self,
        src: std.Expr,
        dst: std.Expr,
        offsets: list[std.Expr],
        cache_policy: std.Expr | None = None,
        *,
        dims: list[int],
    ) -> None:
        self.__ffi_init__(
            src=src,
            dst=dst,
            offsets=offsets,
            cache_policy=cache_policy,
            dims=dims,
        )
        validate_matching_lengths(self, "offsets", "dims")

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncTensorCommitGroupInst", structural_eq="tree")
class CopyAsyncTensorCommitGroupInst(Instruction, mnemonic="tilus.CopyAsyncTensorCommitGroup"):
    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.CopyAsyncTensorWaitGroupInst", structural_eq="tree")
class CopyAsyncTensorWaitGroupInst(Instruction, mnemonic="tilus.CopyAsyncTensorWaitGroup"):
    n: int = field(lang_kind="attr")
    read: bool = field(default=False, lang_kind="attr")

    def __init__(self, n: int, read: bool = False) -> None:
        self.__ffi_init__(n=validate_nonnegative_int_attr(n, "n"), read=read)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


__all__ = [  # noqa: RUF022
    "CopyAsyncTensorGlobalToSharedInst",
    "CopyAsyncTensorSharedToGlobalInst",
    "CopyAsyncTensorCommitGroupInst",
    "CopyAsyncTensorWaitGroupInst",
]
