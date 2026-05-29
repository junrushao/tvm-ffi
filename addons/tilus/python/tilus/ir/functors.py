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
"""Generic Tilus IR visitors and rewriters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Hashable

from tvm_ffi import std
from tvm_ffi.container import Array, Dict, List, Map
from tvm_ffi.core import Object, _lookup_type_attr
from tvm_ffi.dataclasses import fields, is_dataclass, replace

_CONSTANT_TYPES = (str, int, float, bool, type(None), bytes)
_SEQUENCE_TYPES = (list, tuple, List, Array)
_MAPPING_TYPES = (dict, Dict, Map)
_IN_PROGRESS = object()
_STMT_SEQUENCE_FIELD_NAMES = frozenset(("body", "then_body", "else_body"))


class _DeleteStmt:
    """Marker returned by rewriters to remove one statement from a body."""


DELETE_STMT = _DeleteStmt()


class StmtSplice:
    """Marker returned by rewriters to replace one statement with many."""

    def __init__(self, statements: Iterable[std.Stmt]) -> None:
        self.statements = tuple(statements)
        for stmt in self.statements:
            if not isinstance(stmt, std.Stmt):
                raise TypeError(f"StmtSplice expects std.Stmt, got {type(stmt).__name__}")


def _memo_key(node: Any) -> Hashable:
    if type(node) in _CONSTANT_TYPES:
        return (type(node), node)
    if isinstance(node, Object):
        return (type(node), node.__chandle__())
    return id(node)


def _is_same_value(lhs: Any, rhs: Any) -> bool:
    if isinstance(lhs, Object) and isinstance(rhs, Object):
        return type(lhs) is type(rhs) and lhs.__chandle__() == rhs.__chandle__()
    return lhs is rhs


def _dialect_field_collector(node: std.Node) -> Any:
    type_info = getattr(type(node), "__tvm_ffi_type_info__", None)
    if type_info is None:
        return None
    collector = _lookup_type_attr(type_info.type_index, "__ffi_dialect_field_collector__")
    if collector is not None:
        return collector
    if type_info.type_key.startswith("ffi.std."):
        return None
    return _lookup_type_attr(
        type_info.type_index,
        "__ffi_dialect_field_collector__",
        ancestor=True,
    )


class IRFunctor:
    """Base class for memoized Tilus IR traversal.

    Subclasses may define ``visit_<ClassName>`` methods for specific nodes.  If
    no exact handler exists, ``visit_default`` is used.
    """

    def __init__(self) -> None:
        self.memo: dict[Hashable, Any] = {}

    def __call__(self, node: Any) -> Any:
        """Visit a node."""
        return self.visit(node)

    def visit(self, node: Any) -> Any:
        """Dispatch to an exact ``visit_<ClassName>`` method when present."""
        key = _memo_key(node)
        if key in self.memo:
            ret = self.memo[key]
            if ret is _IN_PROGRESS:
                raise ValueError("cyclic Tilus IR is not supported")
            return ret

        method = getattr(self, f"visit_{type(node).__name__}", None)
        if method is None:
            method = self.visit_default
        self.memo[key] = _IN_PROGRESS
        try:
            ret = method(node)
            self.memo[key] = ret
            return ret
        except Exception:
            self.memo.pop(key, None)
            raise

    def visit_default(self, node: Any) -> Any:
        """Handle nodes without an exact visitor method."""
        raise NotImplementedError(type(node).__name__)


class IRRewriter(IRFunctor):
    """Rewrite Tilus IR, preserving object identity when children are unchanged."""

    def visit_default(self, node: Any) -> Any:
        """Rewrite a node with the generic traversal."""
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
        """Rewrite sequence elements."""
        updated = []
        changed = False
        for item in node:
            rewritten = self.visit(item)
            if rewritten is DELETE_STMT or isinstance(rewritten, StmtSplice):
                raise ValueError("statement deletion/splicing is only valid in statement bodies")
            updated.append(rewritten)
            changed = changed or not _is_same_value(rewritten, item)
        if not changed:
            return node
        if isinstance(node, tuple):
            return tuple(updated)
        if isinstance(node, (List, Array)):
            return type(node)(updated)
        return updated

    def visit_stmt_sequence(self, node: Sequence[std.Stmt]) -> Sequence[std.Stmt]:
        """Rewrite a statement body, allowing statement deletion and splicing."""
        updated = []
        changed = False
        for item in node:
            if not isinstance(item, std.Stmt):
                raise TypeError(f"statement body expects std.Stmt, got {type(item).__name__}")
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
            changed = changed or not _is_same_value(rewritten, item)
        if not changed:
            return node
        if isinstance(node, tuple):
            return tuple(updated)
        if isinstance(node, (List, Array)):
            return type(node)(updated)
        return updated

    def visit_mapping(self, node: Mapping[Any, Any]) -> Mapping[Any, Any]:
        """Rewrite mapping keys and values."""
        updated = {}
        changed = False
        for key, value in node.items():
            rewritten_key = self.visit(key)
            rewritten_value = self.visit(value)
            updated[rewritten_key] = rewritten_value
            changed = (
                changed
                or not _is_same_value(rewritten_key, key)
                or not _is_same_value(rewritten_value, value)
            )
        if not changed:
            return node
        if isinstance(node, (Dict, Map)):
            return type(node)(updated)
        return type(node)(updated)

    def visit_dataclass(self, node: Any) -> Any:
        """Rewrite dataclass fields."""
        collector = _dialect_field_collector(node)
        if collector is not None:
            # Exercise the dialect reflection hook so malformed lang_kind schemas
            # fail during traversal, while replacement below remains field-based.
            collector(node)

        changes: dict[str, Any] = {}
        for field in fields(node):
            if not field.init:
                continue
            field_name = field.name
            if field_name is None:
                continue
            value = getattr(node, field_name)
            if self._is_stmt_sequence_field(field, value):
                updated = self.visit_stmt_sequence(value)
            else:
                updated = self.visit(value)
            if not _is_same_value(updated, value):
                changes[field_name] = updated
        if not changes:
            return node
        return replace(node, **changes)

    def _is_stmt_sequence_field(self, field: Any, value: Any) -> bool:
        """Return whether a dataclass field is a statement sequence body."""
        if not isinstance(value, _SEQUENCE_TYPES):
            return False
        if getattr(field, "lang_kind", None) == "body":
            return True
        return field.name in _STMT_SEQUENCE_FIELD_NAMES and all(
            isinstance(item, std.Stmt) for item in value
        )


class IRVisitor(IRFunctor):
    """Read-only Tilus IR traversal."""

    def visit_default(self, node: Any) -> None:
        """Visit a node with the generic traversal."""
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
            self.visit_dataclass(node)
            return None
        return None

    def visit_dataclass(self, node: std.Node) -> None:
        """Visit dataclass fields."""
        collector = _dialect_field_collector(node)
        if collector is not None:
            collector(node)
        for field in fields(node):
            field_name = field.name
            if field_name is not None:
                self.visit(getattr(node, field_name))


__all__ = ["DELETE_STMT", "IRFunctor", "IRRewriter", "IRVisitor", "StmtSplice"]
