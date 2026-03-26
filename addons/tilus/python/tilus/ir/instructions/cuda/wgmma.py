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


@py_class("tilus.WgmmaFenceInst", structural_eq="tree")
class WgmmaFenceInst(Instruction, mnemonic="tilus.WgmmaFence"):
    EXPECTED_INPUTS: ClassVar[int] = 0


@py_class("tilus.WgmmaCommitGroupInst", structural_eq="tree")
class WgmmaCommitGroupInst(Instruction, mnemonic="tilus.WgmmaCommitGroup"):
    EXPECTED_INPUTS: ClassVar[int] = 0


@py_class("tilus.WgmmaWaitGroupInst", structural_eq="tree")
class WgmmaWaitGroupInst(Instruction, mnemonic="tilus.WgmmaWaitGroup"):
    EXPECTED_INPUTS: ClassVar[int] = 0
    NONNEGATIVE_INT_ATTRS: ClassVar[tuple[str, ...]] = ("n",)

    n: std.Expr = field(lang_kind="attr")


@py_class("tilus.WgmmaMmaSSInst", structural_eq="tree")
class WgmmaMmaSSInst(Instruction, mnemonic="tilus.WgmmaMmaSS"):
    EXPECTED_INPUTS: ClassVar[int] = 2


@py_class("tilus.WgmmaMmaRSInst", structural_eq="tree")
class WgmmaMmaRSInst(Instruction, mnemonic="tilus.WgmmaMmaRS"):
    EXPECTED_INPUTS: ClassVar[int] = 2


__all__ = [  # noqa: RUF022
    "WgmmaFenceInst",
    "WgmmaCommitGroupInst",
    "WgmmaWaitGroupInst",
    "WgmmaMmaSSInst",
    "WgmmaMmaRSInst",
]
