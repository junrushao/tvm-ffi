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
"""Shared Weave parser/printer round-trip helpers."""

from __future__ import annotations

from textwrap import dedent
from typing import Any

import tvm_ffi
from tvm_ffi._pyast_parser import parse


def text(ir: Any) -> str:
    """Render a parser result that may contain multiple top-level objects."""
    if isinstance(ir, list):
        return "\n\n".join(text(item) for item in ir)
    return ir.text()


def assert_node_roundtrip(node: Any) -> str:
    """Round-trip an already constructed node through its printed text."""
    printed = node.text()
    reparsed = parse(printed)
    reprinted = text(reparsed)

    assert tvm_ffi.structural_equal(reparsed, node), printed
    assert tvm_ffi.structural_equal(node, reparsed), printed
    assert reprinted == printed
    return printed


def assert_source_roundtrip(source: str) -> str:
    """Parse user-facing source, print it, then verify print/parse idempotence."""
    parsed = parse(dedent(source).strip())
    printed = text(parsed)
    reparsed = parse(printed)
    reprinted = text(reparsed)

    assert tvm_ffi.structural_equal(parsed, reparsed), printed
    assert tvm_ffi.structural_equal(reparsed, parsed), printed
    assert reprinted == printed
    return printed
