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


@py_class("tilus.DotInst", structural_eq="tree")
class DotInst(Instruction, mnemonic="tilus.Dot"):
    EXPECTED_INPUTS: ClassVar[int] = 2


@py_class("tilus.AtomicMmaConfig", structural_eq="tree")
class AtomicMmaConfig(std.Node, mnemonic="tilus.AtomicMmaConfig"):
    name: str = field(lang_kind="attr")
    m: int = field(lang_kind="attr")
    n: int = field(lang_kind="attr")
    k: int = field(lang_kind="attr")
    vec_k: int = field(lang_kind="attr")
    la: std.Node = field(lang_kind="attr")
    lb: std.Node = field(lang_kind="attr")
    lc: std.Node = field(lang_kind="attr")
    operand_type: std.Ty = field(lang_kind="attr")
    acc_type: std.Ty = field(lang_kind="attr")


__all__ = [  # noqa: RUF022
    "DotInst",
    "AtomicMmaConfig",
]
