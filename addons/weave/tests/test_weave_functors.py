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
"""Visitor and rewriter tests for Weave IR."""

from __future__ import annotations

import pytest
import tvm_ffi
import weave  # noqa: F401
from tvm_ffi import std
from weave.ir import Assign, Const, Kernel, i32
from weave.ir.functors import DELETE_STMT, IRFunctor, IRRewriter, IRVisitor, StmtSplice


def _kernel() -> Kernel:
    return Kernel(
        "kernel",
        [std.Var(i32, "arg")],
        None,
        [
            Assign(Const("drop", i32), 1),
            Assign(Const("keep", i32), 2),
        ],
    )


def test_ir_visitor_traverses_weave_dataclass_fields() -> None:
    class CollectConsts(IRVisitor):
        def __init__(self) -> None:
            super().__init__()
            self.names: list[str] = []

        def visit_Const(self, node: Const) -> None:
            self.names.append(node.name)
            return self.visit_default(node)

    visitor = CollectConsts()
    visitor(_kernel())

    assert visitor.names == ["drop", "keep"]


def test_ir_functor_dispatches_and_memoizes_objects() -> None:
    class CountConsts(IRFunctor):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def visit_Const(self, node: Const) -> str:
            self.calls += 1
            return node.name

    node = Const("memoized", i32)
    functor = CountConsts()

    assert functor(node) == "memoized"
    assert functor(node) == "memoized"
    assert functor.calls == 1


def test_ir_rewriter_preserves_identity_for_noop_kernel() -> None:
    kernel = _kernel()

    assert IRRewriter()(kernel) is kernel


def test_ir_rewriter_supports_delete_and_splice_in_statement_bodies() -> None:
    class BodyRewrite(IRRewriter):
        def visit_Assign(self, node: Assign) -> Assign | StmtSplice | object:
            assert isinstance(node.target, Const)
            if node.target.name == "drop":
                return DELETE_STMT
            return StmtSplice([node, Assign(Const("after", i32), 3)])

    rewritten = BodyRewrite()(_kernel())

    assert [stmt.target.name for stmt in rewritten.body] == ["keep", "after"]


def test_ir_rewriter_can_delete_only_statement_and_empty_splice() -> None:
    class DropOrEmptySplice(IRRewriter):
        def visit_Assign(self, node: Assign) -> StmtSplice | object:
            assert isinstance(node.target, Const)
            if node.target.name == "drop":
                return DELETE_STMT
            return StmtSplice([])

    kernel = Kernel(
        "kernel",
        [],
        None,
        [
            Assign(Const("drop", i32), 1),
            Assign(Const("keep", i32), 2),
        ],
    )
    rewritten = DropOrEmptySplice()(kernel)

    assert rewritten.body == []


def test_ir_rewriter_rewrites_mapping_keys_and_values() -> None:
    class RewriteMapping(IRRewriter):
        def visit_str(self, node: str) -> str:
            return "new" if node == "old" else node

        def visit_Const(self, node: Const) -> Const:
            if node.name == "value":
                return Const("changed", i32)
            return node

    rewritten = RewriteMapping()({"old": Const("value", i32)})
    items = list(rewritten.items())

    assert len(items) == 1
    assert items[0][0] == "new"
    assert tvm_ffi.structural_equal(items[0][1], Const("changed", i32))


def test_ir_rewriter_rejects_cyclic_containers() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)

    with pytest.raises(ValueError, match="cyclic Weave IR is not supported"):
        IRRewriter()(cyclic)


def test_ir_rewriter_rejects_delete_or_splice_outside_statement_bodies() -> None:
    class DropArgs(IRRewriter):
        def visit_Var(self, node: std.Var) -> object:
            if node.name == "arg":
                return DELETE_STMT
            return node

    with pytest.raises(ValueError, match="only valid in statement bodies"):
        DropArgs()(_kernel())


def test_ir_rewriter_rejects_non_statement_body_rewrite() -> None:
    class ReturnExprFromStatement(IRRewriter):
        def visit_Assign(self, node: Assign) -> Const:
            return Const("not_stmt", i32)

    with pytest.raises(TypeError, match="statement rewriter returned Const"):
        ReturnExprFromStatement()(_kernel())


def test_stmt_splice_rejects_non_statement_values() -> None:
    with pytest.raises(TypeError, match=r"StmtSplice expects std\.Stmt"):
        StmtSplice([Const("not_stmt", i32)])
