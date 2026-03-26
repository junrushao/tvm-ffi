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

from tvm_ffi.dataclasses import field, py_class

from ...inst import Instruction


@py_class("tilus.SimtDotInst", structural_eq="tree")
class SimtDotInst(Instruction, mnemonic="tilus.SimtDot"):
    EXPECTED_INPUTS: ClassVar[int] = 2
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("warp_spatial", "warp_repeat"),
        ("thread_spatial", "thread_repeat"),
        ("warp_spatial", "thread_spatial"),
    )

    warp_spatial: list[int] = field(lang_kind="attr")
    warp_repeat: list[int] = field(lang_kind="attr")
    thread_spatial: list[int] = field(lang_kind="attr")
    thread_repeat: list[int] = field(lang_kind="attr")


__all__ = [
    "SimtDotInst",
]
