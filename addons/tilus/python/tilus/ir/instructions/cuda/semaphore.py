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

from ...inst import Instruction


@py_class("tilus.LockSemaphoreInst", structural_eq="tree")
class LockSemaphoreInst(Instruction, mnemonic="tilus.LockSemaphore"):
    semaphore: std.Expr = field(lang_kind="arg")
    value: std.Expr = field(lang_kind="arg")

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.ReleaseSemaphoreInst", structural_eq="tree")
class ReleaseSemaphoreInst(Instruction, mnemonic="tilus.ReleaseSemaphore"):
    semaphore: std.Expr = field(lang_kind="arg")
    value: std.Expr = field(lang_kind="arg")

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


__all__ = [
    "LockSemaphoreInst",
    "ReleaseSemaphoreInst",
]
