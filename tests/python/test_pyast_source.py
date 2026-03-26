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

import sys

import pytest
from tvm_ffi import pyast
from tvm_ffi._pyast_parser import Parser
from tvm_ffi._pyast_source import DiagnosticLevel, Source


def test_format_error_renders_colored_source_context() -> None:
    source = Source("x + 1\n", feature_version=sys.version_info[:2])
    assert isinstance(source.ast_root, pyast.StmtBlock)
    stmt = source.ast_root.stmts[0]

    assert source.format_error(stmt, "bad addition", DiagnosticLevel.ERROR, color=True) == (
        "\033[1m\033[31merror: \033[39mbad addition\n"
        "\033[34m --> \033[39m\033[0m<str>:1:1\n"
        "   |  \n"
        " 1 |  x + 1\n"
        "   |  ^^^^^\n"
    )


def test_format_error_renders_missing_span_with_single_caret() -> None:
    source = Source("x\n", feature_version=sys.version_info[:2])
    node = pyast.Id("x")

    assert source.format_error(node, "missing span", DiagnosticLevel.WARNING, color=True) == (
        "\033[1m\033[33mwarning: \033[39mmissing span\n"
        "\033[34m --> \033[39m\033[0m<str>:1:1\n"
        "   |  \n"
        " 1 |  x\n"
        "   |  ^\n"
    )


def test_parser_run_attaches_diagnostic_without_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = Source("x = y\n", feature_version=sys.version_info[:2])
    parser = Parser(source, extra_vars={})

    with pytest.raises(NameError) as exc_info:
        parser.run()

    assert (
        str(exc_info.value)
        == (
            "error: name 'y' is not defined\n --> <str>:1:5\n   |  \n 1 |  x = y\n   |      ^\n"
        ).rstrip()
    )
    assert capsys.readouterr().err == ""
