# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Generic Weave IR visitors and rewriters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tvm_ffi import std
from tvm_ffi.container import Array, Dict, List, Map
from tvm_ffi.core import Object
from tvm_ffi.dataclasses import fields, is_dataclass, replace

_CONSTANT_TYPES = (str, int, float, bool, type(None), bytes)
_SEQUENCE_TYPES = (list, tuple, List, Array)
_MAPPING_TYPES = (dict, Dict, Map)
_IN_PROGRESS = object()


class _DeleteStmt:
    """Marker returned by rewriters to remove one statement from a body."""


DELETE_STMT = _DeleteStmt()


class StmtSplice:
    """Marker returned by rewriters to replace one statement with many."""

    def __init__(self, statements: Sequence[std.Stmt]) -> None:
        self.statements = tuple(statements)
        for stmt in self.statements:
            if not isinstance(stmt, std.Stmt):
                raise TypeError(f"StmtSplice expects std.Stmt, got {type(stmt).__name__}")


def _memo_key(node: Any) -> Any:
    if type(node) in _CONSTANT_TYPES:
        return (type(node), node)
    if isinstance(node, Object):
        return (type(node), node.__chandle__())
    return id(node)


def _same(lhs: Any, rhs: Any) -> bool:
    if isinstance(lhs, Object) and isinstance(rhs, Object):
        return type(lhs) is type(rhs) and lhs.__chandle__() == rhs.__chandle__()
    return lhs is rhs


class IRFunctor:
    """Base class for memoized Weave IR traversal."""

    def __init__(self) -> None:
        self.memo: dict[Any, Any] = {}

    def __call__(self, node: Any) -> Any:
        return self.visit(node)

    def visit(self, node: Any) -> Any:
        key = _memo_key(node)
        if key in self.memo:
            ret = self.memo[key]
            if ret is _IN_PROGRESS:
                raise ValueError("cyclic Weave IR is not supported")
            return ret
        method = getattr(self, f"visit_{type(node).__name__}", self.visit_default)
        self.memo[key] = _IN_PROGRESS
        try:
            ret = method(node)
            self.memo[key] = ret
            return ret
        except Exception:
            self.memo.pop(key, None)
            raise

    def visit_default(self, node: Any) -> Any:
        raise NotImplementedError(type(node).__name__)


class IRRewriter(IRFunctor):
    """Rewrite Weave IR, preserving object identity when children do not change."""

    def visit_default(self, node: Any) -> Any:
        if isinstance(node, _CONSTANT_TYPES):
            return node
        if isinstance(node, _SEQUENCE_TYPES):
            return self.visit_sequence(node)
        if isinstance(node, _MAPPING_TYPES):
            return self.visit_mapping(node)
        if is_dataclass(node):
            return self.visit_dataclass(node)
        return node

    def visit_sequence(self, node: Sequence[Any]) -> Sequence[Any]:
        updated = []
        changed = False
        for item in node:
            rewritten = self.visit(item)
            if rewritten is DELETE_STMT or isinstance(rewritten, StmtSplice):
                raise ValueError("statement deletion/splicing is only valid in statement bodies")
            updated.append(rewritten)
            changed = changed or not _same(rewritten, item)
        if not changed:
            return node
        if isinstance(node, tuple):
            return tuple(updated)
        if isinstance(node, (List, Array)):
            return type(node)(updated)
        return updated

    def visit_stmt_sequence(self, node: Sequence[std.Stmt]) -> Sequence[std.Stmt]:
        updated = []
        changed = False
        for item in node:
            rewritten = self.visit(item)
            if rewritten is DELETE_STMT:
                changed = True
                continue
            if isinstance(rewritten, StmtSplice):
                updated.extend(rewritten.statements)
                changed = True
                continue
            if not isinstance(rewritten, std.Stmt):
                raise TypeError(f"statement rewriter returned {type(rewritten).__name__}")
            updated.append(rewritten)
            changed = changed or not _same(rewritten, item)
        if not changed:
            return node
        if isinstance(node, tuple):
            return tuple(updated)
        if isinstance(node, (List, Array)):
            return type(node)(updated)
        return updated

    def visit_mapping(self, node: Mapping[Any, Any]) -> Mapping[Any, Any]:
        updated = {}
        changed = False
        for key, value in node.items():
            new_key = self.visit(key)
            new_value = self.visit(value)
            updated[new_key] = new_value
            changed = changed or not _same(new_key, key) or not _same(new_value, value)
        if not changed:
            return node
        if isinstance(node, (Dict, Map)):
            return type(node)(updated)
        return type(node)(updated)

    def visit_dataclass(self, node: Any) -> Any:
        changes: dict[str, Any] = {}
        for field in fields(node):
            if not field.init:
                continue
            field_name = field.name
            if field_name is None:
                continue
            value = getattr(node, field_name)
            if field.lang_kind == "body" and isinstance(value, _SEQUENCE_TYPES):
                rewritten = self.visit_stmt_sequence(value)
            else:
                rewritten = self.visit(value)
            if not _same(rewritten, value):
                changes[field_name] = rewritten
        if not changes:
            return node
        return replace(node, **changes)


class IRVisitor(IRFunctor):
    """Read-only Weave IR traversal."""

    def visit_default(self, node: Any) -> None:
        if isinstance(node, _CONSTANT_TYPES):
            return None
        if isinstance(node, _SEQUENCE_TYPES):
            for item in node:
                self.visit(item)
            return None
        if isinstance(node, _MAPPING_TYPES):
            for key, value in node.items():
                self.visit(key)
                self.visit(value)
            return None
        if is_dataclass(node):
            for field in fields(node):
                field_name = field.name
                if field_name is not None:
                    self.visit(getattr(node, field_name))
        return None


__all__ = ["DELETE_STMT", "IRFunctor", "IRRewriter", "IRVisitor", "StmtSplice"]
