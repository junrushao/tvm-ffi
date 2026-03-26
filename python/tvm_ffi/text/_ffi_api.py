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
"""FFI API for namespace `ffi.text`."""

# tvm-ffi-stubgen(begin): import-section
# fmt: off
# isort: off
from __future__ import annotations
from ..registry import init_ffi_api as _FFI_INIT_FUNC
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tvm_ffi import Object
    from tvm_ffi.text import PrinterConfig
    from tvm_ffi.text.ast import Node
    from typing import Any
# isort: on
# fmt: on
# tvm-ffi-stubgen(end)

# tvm-ffi-stubgen(begin): global/ffi.text@..registry
# fmt: off
_FFI_INIT_FUNC("ffi.text", __name__)
if TYPE_CHECKING:
    def DocToPythonScript(_0: Node, _1: PrinterConfig, /) -> str: ...
    def IRPrintDispatch(_0: Any, _1: Any, _2: Any, /) -> Node: ...
    def ToPython(_0: Object, _1: PrinterConfig, /) -> str: ...
# fmt: on
# tvm-ffi-stubgen(end)

__all__ = [
    # tvm-ffi-stubgen(begin): __all__
    "DocToPythonScript",
    "IRPrintDispatch",
    "ToPython",
    # tvm-ffi-stubgen(end)
]
