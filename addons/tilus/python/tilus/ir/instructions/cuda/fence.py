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

from ...inst import Instruction, validate_string_attr

FENCE_PROXY_ASYNC_SPACES = ("shared::cta", "shared::cluster", "global")


@py_class("tilus.FenceProxyAsync", structural_eq="tree")
class FenceProxyAsync(Instruction, mnemonic="tilus.FenceProxyAsync"):
    space: str = field(lang_kind="attr")

    def __post_init__(self) -> None:
        validate_string_attr(self.space, "space", FENCE_PROXY_ASYNC_SPACES)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.FenceProxyAsyncRelease", structural_eq="tree")
class FenceProxyAsyncRelease(Instruction, mnemonic="tilus.FenceProxyAsyncRelease"):
    def outputs(self) -> tuple[std.Var, ...]:
        return ()


__all__ = [
    "FenceProxyAsync",
    "FenceProxyAsyncRelease",
]
