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
"""Tests for Tilus transform passes."""

from __future__ import annotations

import tilus  # noqa: F401  # Registers the Tilus dialect.
from tilus.ir.func import Function
from tilus.ir.functors import DELETE_STMT, IRRewriter, StmtSplice
from tilus.ir.inst import Instruction
from tilus.ir.instructions.generic import AddInst, MulInst, NopInst, StoreGlobalInst
from tilus.ir.stmt import ThreadGroup
from tilus.ir.tensor import register_tensor
from tilus.transforms import dead_code_elimination
from tvm_ffi import std


def _reg_var(name: str) -> std.Var:
    return std.Var(register_tensor("float32", (2, 2)), name)


def _stmt_names(body: list[std.Stmt]) -> list[str]:
    names = []
    for stmt in body:
        if isinstance(stmt, Instruction) and (output := getattr(stmt, "output", None)) is not None:
            names.append(output.name)
        else:
            names.append(type(stmt).__name__)
    return names


def test_dead_code_elimination_removes_unused_pure_instruction_chain() -> None:
    """DCE removes dead pure instructions and keeps used or effectful ones."""
    x = _reg_var("x")
    dead_a = _reg_var("dead_a")
    dead_b = _reg_var("dead_b")
    live_a = _reg_var("live_a")
    live_b = _reg_var("live_b")

    dead_add = AddInst(x, x, output=dead_a)
    dead_mul = MulInst(dead_a, x, output=dead_b)
    live_add = AddInst(x, x, output=live_a)
    live_mul = MulInst(live_a, x, output=live_b)
    store = StoreGlobalInst(live_b, x)
    ret = std.Return(live_b)
    func = Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[dead_add, dead_mul, live_add, live_mul, store, ret],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert rewritten is not func
    assert _stmt_names(list(rewritten.body)) == [
        "live_a",
        "live_b",
        "StoreGlobalInst",
        "Return",
    ]
    assert isinstance(rewritten.body[2], StoreGlobalInst)


def test_dead_code_elimination_preserves_unchanged_function_identity() -> None:
    """DCE preserves object identity when no instruction is removed."""
    x = _reg_var("x")
    store = StoreGlobalInst(x, x)
    func = Function(symbol="kernel", args=[x], ret_type=None, body=[store], metadata=None)

    assert dead_code_elimination(func) is func


def test_dead_code_elimination_rewrites_nested_statement_bodies() -> None:
    """DCE also removes dead pure instructions from nested statement bodies."""
    x = _reg_var("x")
    dead = AddInst(x, x, output=_reg_var("dead"))
    live = AddInst(x, x, output=_reg_var("live"))
    group = ThreadGroup(0, 32, [dead, live, std.Return(live.output)])
    func = Function(symbol="kernel", args=[x], ret_type=None, body=[group], metadata=None)

    rewritten = dead_code_elimination(func)

    assert isinstance(rewritten.body[0], ThreadGroup)
    assert _stmt_names(list(rewritten.body[0].body)) == ["live", "Return"]


def test_ir_rewriter_supports_delete_and_splice_in_statement_bodies() -> None:
    """IRRewriter allows delete and splice markers in statement body fields."""
    x = _reg_var("x")
    drop = AddInst(x, x, output=_reg_var("drop"))
    keep = AddInst(x, x, output=_reg_var("keep"))

    class BodyRewrite(IRRewriter):
        def visit_AddInst(self, node: AddInst) -> AddInst | object:
            if node.output is not None and node.output.name == "drop":
                return DELETE_STMT
            return StmtSplice([node, NopInst()])

    func = Function(symbol="kernel", args=[x], ret_type=None, body=[drop, keep], metadata=None)

    rewritten = BodyRewrite()(func)

    assert _stmt_names(list(rewritten.body)) == ["keep", "NopInst"]


def test_ir_rewriter_preserves_identity_for_noop_function() -> None:
    """Generic no-op rewriting does not rebuild unchanged FFI nodes."""
    x = _reg_var("x")
    func = Function(symbol="kernel", args=[x], ret_type=None, body=[std.Return(x)], metadata=None)

    assert IRRewriter()(func) is func


def test_ir_rewriter_rejects_delete_in_scope_binds() -> None:
    """Delete markers are not valid for scope binding lists."""
    x = _reg_var("x")

    class DropBindings(IRRewriter):
        def visit_TensorItemValue(self, node: object) -> object:
            return DELETE_STMT

    from tilus.ir.stmt import TensorItemValue

    scope = std.Scope([TensorItemValue(x)], [std.Return(x)])

    try:
        DropBindings()(scope)
    except ValueError:
        pass
    else:
        raise AssertionError("expected delete in scope binds to fail")
