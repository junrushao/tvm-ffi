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
"""Shared-memory swizzle metadata nodes."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import std


@dc.py_class("weave.Swizzle", structural_eq="tree")
class Swizzle(std.Attrs, mnemonic="weave.Swizzle"):
    """Shared-memory swizzle descriptor."""

    base: int = dc.field(lang_kind="attr")
    bits: int = dc.field(lang_kind="attr")
    shift: int = dc.field(lang_kind="attr")

    def __post_init__(self) -> None:
        if self.base < 0 or self.bits < 0 or self.shift < 0:
            raise ValueError("swizzle fields must be non-negative")

    @property
    def num_bytes(self) -> int:
        return 1 << self.base if self.base else 0


SWIZZLE_NONE = Swizzle(0, 0, 0)
SWIZZLE_32B = Swizzle(5, 4, 3)
SWIZZLE_64B = Swizzle(6, 5, 3)
SWIZZLE_128B = Swizzle(7, 6, 3)


__all__ = [
    "SWIZZLE_32B",
    "SWIZZLE_64B",
    "SWIZZLE_128B",
    "SWIZZLE_NONE",
    "Swizzle",
]
