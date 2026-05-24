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
"""Public Tilus IR exports."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

_PUBLIC_MODULES = (
    "tensor",
    "layout",
    "stmt",
    "inst",
    "instructions",
    "func",
    "functors",
)

__all__: list[str] = []


def _export_module(module: ModuleType) -> None:
    names = getattr(module, "__all__", ())
    for name in names:
        globals()[name] = getattr(module, name)
        __all__.append(name)


for _module_name in _PUBLIC_MODULES:
    try:
        _export_module(import_module(f"{__name__}.{_module_name}"))
    except ModuleNotFoundError as err:
        if err.name != f"{__name__}.{_module_name}":
            raise

del import_module, _export_module, _module_name
