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
"""Tilus addon for TVM-FFI."""

from __future__ import annotations

from . import _tilus_lang as _tilus_lang
from . import ir, transforms
from .ir import *

__all__: list[str] = ["ir", "transforms"]
__all__.extend(ir.__all__)

_PUBLIC_TENSOR_CONSTRUCTORS = [
    "RegTensor",
    "RegisterTensor",
    "SharedTensor",
    "GlobalTensor",
    "TMemoryTensor",
]
_PUBLIC_LAYOUT_CONSTRUCTORS = [
    "Swizzle",
    "RegisterLayout",
    "SharedLayout",
    "GlobalLayout",
    "TMemoryLayout",
]
_PUBLIC_STMT_ALIASES = [
    "Eval",
    "Inst",
]
_PUBLIC_INSTRUCTION_CONSTRUCTORS = [
    getattr(ir.instructions, name).__ffi_dialect_mnemonic__[1] for name in ir.instructions.__all__
]


def _export_lang_name(name: str) -> None:
    globals()[name] = getattr(_tilus_lang.TilusLang, name)
    if name not in __all__:
        __all__.append(name)


for _name in (
    *_PUBLIC_LAYOUT_CONSTRUCTORS,
    *_PUBLIC_TENSOR_CONSTRUCTORS,
    *_PUBLIC_STMT_ALIASES,
    *_PUBLIC_INSTRUCTION_CONSTRUCTORS,
):
    _export_lang_name(_name)

del (
    _PUBLIC_INSTRUCTION_CONSTRUCTORS,
    _PUBLIC_LAYOUT_CONSTRUCTORS,
    _PUBLIC_STMT_ALIASES,
    _PUBLIC_TENSOR_CONSTRUCTORS,
    _export_lang_name,
    _name,
)
