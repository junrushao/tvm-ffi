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
"""Common utility functions in stub generation."""

from __future__ import annotations

from io import StringIO
from typing import Callable

from tvm_ffi.core import TypeSchema
from tvm_ffi.registry import list_global_func_names


def _compute_global_func_tab() -> dict[str, list[str]]:
    # Build global function table only if we are going to process blocks.
    global_func_tab: dict[str, list[str]] = {}
    for name in list_global_func_names():
        prefix, suffix = name.rsplit(".", 1)
        global_func_tab.setdefault(prefix, []).append(suffix)
    # Ensure stable ordering for deterministic output.
    for k in list(global_func_tab.keys()):
        global_func_tab[k].sort()
    return global_func_tab


def _as_func_signature(
    schema: TypeSchema,
    func_name: str,
    ty_map: Callable[[str], str],
) -> str:
    buf = StringIO()
    buf.write(f"def {func_name}(")
    if schema.origin != "Callable":
        raise ValueError(f"Expected Callable type schema, but got: {schema}")
    if not schema.args:
        buf.write("*args: Any) -> Any:")
        return buf.getvalue()
    arg_ret = schema.args[0]
    arg_args = schema.args[1:]
    for i, arg in enumerate(arg_args):
        buf.write(f"_{i}: ")
        buf.write(arg.repr(ty_map))
        buf.write(", ")
    if arg_args:
        buf.write("/")
    buf.write(") -> ")
    buf.write(arg_ret.repr(ty_map))
    buf.write(":")
    return buf.getvalue()
