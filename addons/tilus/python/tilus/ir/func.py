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
"""Tilus function and metadata nodes."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import std


@dc.py_class("tilus.Analysis", structural_eq="tree")
class Analysis(std.Attrs, mnemonic="tilus.Analysis"):
    """Compiler analysis facts attached to Tilus metadata."""

    divisibility: dict[str, int] = dc.field(default_factory=dict, lang_kind="attr")
    lower_bound: dict[str, int] = dc.field(default_factory=dict, lang_kind="attr")
    upper_bound: dict[str, int] = dc.field(default_factory=dict, lang_kind="attr")


@dc.py_class("tilus.Metadata", structural_eq="tree")
class Metadata(std.Attrs, mnemonic="tilus.Metadata"):
    """Tilus kernel launch and analysis metadata."""

    grid_blocks: list[int] = dc.field(default_factory=list, lang_kind="attr")
    cluster_blocks: list[int] = dc.field(default_factory=list, lang_kind="attr")
    block_indices: list[str] = dc.field(default_factory=list, lang_kind="attr")
    num_warps: int | None = dc.field(default=None, lang_kind="attr")
    param2divisibility: dict[str, int] = dc.field(default_factory=dict, lang_kind="attr")
    analysis: Analysis | None = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        for name, values in (
            ("grid_blocks", self.grid_blocks),
            ("cluster_blocks", self.cluster_blocks),
            ("block_indices", self.block_indices),
        ):
            if values and len(values) != 3:
                raise ValueError(f"{name} must be empty or have 3 entries")
        for name, values in (
            ("grid_blocks", self.grid_blocks),
            ("cluster_blocks", self.cluster_blocks),
        ):
            for value in values:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise TypeError(f"{name} entries must be integers, got {value!r}")


@dc.py_class("tilus.Function", structural_eq="tree")
class Function(std.BaseFunc, mnemonic="tilus.Function"):
    """A Tilus kernel function."""

    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")
    metadata: Metadata | None = dc.field(default=None, lang_kind="attr")


__all__ = ["Analysis", "Function", "Metadata"]
