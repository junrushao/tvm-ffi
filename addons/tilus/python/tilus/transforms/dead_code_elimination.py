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
"""Dead-code elimination for Tilus function bodies."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Hashable

from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi.core import Object

from tilus.ir.func import Function
from tilus.ir.functors import IRRewriter, IRVisitor, _dialect_field_collector
from tilus.ir.inst import Instruction
from tilus.ir.instructions.generic import (
    AddInst,
    CastInst,
    DivInst,
    LoadGlobalInst,
    LoadSharedInst,
    MulInst,
    NopInst,
    ReduceInst,
    SubInst,
)
from tilus.ir.stmt import InstStmt

from .base import FunctionPass

_PURE_INSTRUCTION_TYPES = (
    AddInst,
    CastInst,
    DivInst,
    LoadGlobalInst,
    LoadSharedInst,
    MulInst,
    NopInst,
    ReduceInst,
    SubInst,
)


def _node_key(node: Object) -> Hashable:
    return (type(node), node.__chandle__())


def is_pure_instruction(inst: Instruction) -> bool:
    """Return whether an instruction can be dropped when its output is unused."""
    return isinstance(inst, _PURE_INSTRUCTION_TYPES)


def _instruction_from_stmt(stmt: std.Stmt) -> Instruction | None:
    if isinstance(stmt, Instruction):
        return stmt
    if isinstance(stmt, InstStmt):
        return stmt.inst
    return None


def _output_key(inst: Instruction) -> Hashable | None:
    if inst.output is None:
        return None
    return _node_key(inst.output)


def _is_same_value(lhs: Any, rhs: Any) -> bool:
    if isinstance(lhs, Object) and isinstance(rhs, Object):
        return type(lhs) is type(rhs) and lhs.__chandle__() == rhs.__chandle__()
    return lhs is rhs


class _UseCollector(IRVisitor):
    def __init__(self, include_bodies: bool = True) -> None:
        super().__init__()
        self.include_bodies = include_bodies
        self.vars: set[Hashable] = set()

    def visit_Var(self, node: std.Var) -> None:
        self.vars.add(_node_key(node))

    def visit_BindExpr(self, node: std.BindExpr) -> None:
        self.visit(node.expr)
        self.visit(getattr(node, "attrs", None))

    def visit_base_bind_expr(self, node: std.BaseBindExpr) -> None:
        self.visit(node.expr)
        self.visit(getattr(node, "attrs", None))
        self.visit_collected_fields(node)

    def visit_Scope(self, node: std.Scope) -> None:
        self.visit(getattr(node, "attrs", None))
        self.visit(node.binds)
        if self.include_bodies:
            self.visit(node.body)

    def visit_For(self, node: std.For) -> None:
        self.visit(getattr(node, "attrs", None))
        self.visit(node.start)
        self.visit(node.extent)
        self.visit(node.step)
        if self.include_bodies:
            self.visit(node.body)

    def visit_base_for(self, node: std.BaseFor) -> None:
        self.visit(getattr(node, "attrs", None))
        self.visit(node.extent)
        self.visit_collected_fields(node)

    def visit_While(self, node: std.While) -> None:
        self.visit(getattr(node, "attrs", None))
        self.visit(node.cond)
        if self.include_bodies:
            self.visit(node.body)

    def visit_base_while(self, node: std.BaseWhile) -> None:
        self.visit(getattr(node, "attrs", None))
        self.visit(node.cond)
        self.visit_collected_fields(node)

    def visit_IfStmt(self, node: std.IfStmt) -> None:
        self.visit(getattr(node, "attrs", None))
        self.visit(node.cond)
        if self.include_bodies:
            self.visit(node.then_body)
            self.visit(node.else_body)

    def visit_default(self, node: Any) -> None:
        if isinstance(node, Instruction):
            self.visit_instruction_uses(node)
            return None
        if isinstance(node, std.BaseBindExpr):
            self.visit_base_bind_expr(node)
            return None
        if isinstance(node, std.BaseFor):
            self.visit_base_for(node)
            return None
        if isinstance(node, std.BaseWhile):
            self.visit_base_while(node)
            return None
        return super().visit_default(node)

    def visit_instruction_uses(self, inst: Instruction) -> None:
        self.visit_dataclass(inst)

    def visit_collected_fields(self, node: std.Node) -> None:
        collector = _dialect_field_collector(node)
        if collector is None:
            return
        collected = collector(node)
        for value in collected.args:
            self.visit(value)
        self.visit(collected.attrs)
        if self.include_bodies:
            for stmt in collected.body:
                self.visit(stmt)

    def visit_dataclass(self, node: std.Node) -> None:
        collector = _dialect_field_collector(node)
        if collector is not None:
            self.visit_collected_fields(node)
            return None
        return super().visit_dataclass(node)


def _collect_uses(node: Any, *, include_bodies: bool = True) -> set[Hashable]:
    collector = _UseCollector(include_bodies)
    collector(node)
    return collector.vars


def _collect_defs(node: Any) -> set[Hashable]:
    if isinstance(node, Instruction):
        output = _output_key(node)
        return set() if output is None else {output}
    if isinstance(node, InstStmt):
        output = _output_key(node.inst)
        return set() if output is None else {output}
    if isinstance(node, std.BindExpr):
        return {_node_key(var) for var in node.vars}
    if isinstance(node, std.VarDef):
        return {_node_key(var) for var in node.vars}
    if isinstance(node, std.Scope):
        defs: set[Hashable] = set()
        for bind in node.binds:
            defs.update(_collect_defs(bind))
        return defs
    if isinstance(node, std.For):
        return {_node_key(node.var)}
    if isinstance(node, std.BaseFor):
        return {_node_key(node.var)}

    collector = _dialect_field_collector(node)
    if collector is None:
        return set()
    return {_node_key(var) for var in collector(node).var_def}


class _DeadCodeEliminator(IRRewriter):
    def visit_Function(self, func: Function) -> Function:
        body, _ = self._rewrite_body(func.body)
        if _is_same_value(body, func.body):
            return func
        return dc.replace(func, body=body)

    def visit_dataclass(self, node: Any) -> Any:
        changes: dict[str, Any] = {}
        for field in dc.fields(node):
            if not field.init:
                continue
            field_name = field.name
            if field_name is None:
                continue
            value = getattr(node, field_name)
            if self._is_stmt_sequence_field(field, value):
                updated, _ = self._rewrite_body(value)
            else:
                updated = self.visit(value)
            if not _is_same_value(updated, value):
                changes[field_name] = updated
        if not changes:
            return node
        return dc.replace(node, **changes)

    def _rewrite_body(
        self,
        body: Sequence[std.Stmt],
        live_out: set[Hashable] | None = None,
    ) -> tuple[Sequence[std.Stmt], set[Hashable]]:
        live: set[Hashable] = set(live_out or ())
        rewritten_reversed: list[std.Stmt] = []
        changed = False

        for stmt in reversed(body):
            rewritten_stmt, stmt_live_in, stmt_changed = self._rewrite_stmt(stmt, live)
            changed = changed or stmt_changed
            if rewritten_stmt is None:
                continue
            live = stmt_live_in
            rewritten_reversed.append(rewritten_stmt)

        if not changed:
            return body, live
        rewritten_reversed.reverse()
        return rewritten_reversed, live

    def _rewrite_stmt(
        self,
        stmt: std.Stmt,
        live_out: set[Hashable],
    ) -> tuple[std.Stmt | None, set[Hashable], bool]:
        rewritten_stmt, nested_live = self._rewrite_stmt_fields(stmt, live_out)
        changed = not _is_same_value(rewritten_stmt, stmt)
        inst = _instruction_from_stmt(rewritten_stmt)
        if inst is not None and self._can_drop(inst, live_out):
            return None, live_out, True

        defs = _collect_defs(rewritten_stmt)
        uses = _collect_uses(rewritten_stmt, include_bodies=False)
        live_in = (set(live_out) - defs) | uses | nested_live
        return rewritten_stmt, live_in, changed

    def _rewrite_stmt_fields(
        self,
        stmt: std.Stmt,
        live_out: set[Hashable],
    ) -> tuple[std.Stmt, set[Hashable]]:
        changes: dict[str, Any] = {}
        nested_live: set[Hashable] = set()
        for field in dc.fields(stmt):
            if not field.init:
                continue
            field_name = field.name
            if field_name is None:
                continue
            value = getattr(stmt, field_name)
            if self._is_stmt_sequence_field(field, value):
                if isinstance(stmt, std.BaseWhile) and field_name == "body":
                    updated, body_live = self._rewrite_while_body(stmt, value, live_out)
                else:
                    updated, body_live = self._rewrite_body(value, live_out)
                nested_live.update(body_live)
            else:
                updated = self.visit(value)
            if not _is_same_value(updated, value):
                changes[field_name] = updated

        rewritten_stmt = stmt if not changes else dc.replace(stmt, **changes)
        # Stmt-sequence live-ins are uses of the enclosing statement, except
        # variables bound by the enclosing statement itself.
        defs = _collect_defs(rewritten_stmt)
        return rewritten_stmt, nested_live - defs

    def _rewrite_while_body(
        self,
        stmt: std.BaseWhile,
        body: Sequence[std.Stmt],
        live_out: set[Hashable],
    ) -> tuple[Sequence[std.Stmt], set[Hashable]]:
        base_live_out = set(live_out) | _collect_uses(stmt.cond, include_bodies=False)
        field_live_out = set(base_live_out)
        while True:
            updated, body_live = self._rewrite_body(body, field_live_out)
            next_live_out = base_live_out | body_live
            if next_live_out == field_live_out:
                return updated, body_live
            field_live_out = next_live_out

    def _can_drop(self, inst: Instruction, live: set[Hashable]) -> bool:
        if not is_pure_instruction(inst):
            return False
        output = _output_key(inst)
        return output is None or output not in live


class DeadCodeElimination(FunctionPass):
    """Remove unused pure instructions from a Tilus function body."""

    name = "dead_code_elimination"

    def transform_function(self, func: Function) -> Function:
        return _DeadCodeEliminator()(func)


def dead_code_elimination(func: Function) -> Function:
    """Remove unused pure instructions from a Tilus function body."""
    return DeadCodeElimination()(func)


__all__ = ["DeadCodeElimination", "dead_code_elimination", "is_pure_instruction"]
