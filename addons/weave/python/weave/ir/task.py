# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Weave task and control-flow nodes."""

from __future__ import annotations

from typing import Any, ClassVar

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from ._utils import (
    collect_fields_with_var_def_ty,
    normalize_expr,
    normalize_optional_expr,
    var_with_ty_hint,
)
from .dtypes import StringLike

ASSIGN_OPS = ("=", "+=", "-=", "*=", "/=", "%=", "//=", "^=", "&=", "|=", "<<=", ">>=")


def _check_body(body: list[Any]) -> None:
    for stmt in body:
        if not isinstance(stmt, std.Stmt):
            raise TypeError(f"body expects std.Stmt, got {type(stmt).__name__}")


@dc.py_class("weave.TaskSpec", structural_eq="tree")
class TaskSpec(std.BaseScope, mnemonic="weave.TaskSpec"):
    """Task body assigned to a role and optional pipeline."""

    name: str = dc.field(lang_kind="arg")
    kind: str = dc.field(lang_kind="arg")
    assigned_role: StringLike = dc.field(lang_kind="arg")
    pipeline: str = dc.field(default="", lang_kind="attr")
    inputs: tuple[StringLike, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    outputs: tuple[StringLike, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    depends_on: tuple[StringLike, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    sync_before: tuple[StringLike | std.Expr, ...] = dc.field(
        default_factory=tuple, lang_kind="attr"
    )
    sync_after: tuple[StringLike | std.Expr, ...] = dc.field(
        default_factory=tuple, lang_kind="attr"
    )
    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    def __post_init__(self) -> None:
        for name in ("inputs", "outputs", "depends_on", "sync_before", "sync_after"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not self.name:
            raise ValueError("TaskSpec.name must be non-empty")
        _check_body(self.body)


@dc.py_class("weave.ForLoop", structural_eq="tree")
class ForLoop(std.BaseFor, mnemonic="weave.ForLoop"):
    """Weave loop with schedule metadata."""

    start: std.Expr | None = dc.field(default=None, lang_kind="attr")
    step: int | None = dc.field(default=None, lang_kind="attr")
    step_expr: std.Expr | None = dc.field(default=None, lang_kind="attr")
    constexpr: bool | None = dc.field(default=None, lang_kind="attr")
    unroll: int | None = dc.field(default=None, lang_kind="attr")
    ctype: str | None = dc.field(default=None, lang_kind="attr")
    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("start", "step_expr"))

    def __post_init__(self) -> None:
        if self.start is not None:
            object.__setattr__(self, "start", normalize_expr(self.start, field_name="start"))
        if self.step_expr is not None:
            object.__setattr__(
                self, "step_expr", normalize_expr(self.step_expr, field_name="step_expr")
            )
        if self.step == 0:
            raise ValueError("step must be non-zero")
        if self.unroll is not None and self.unroll < 0:
            raise ValueError("unroll must be non-negative")
        _check_body(self.body)


@dc.py_class("weave.Block", structural_eq="tree")
class Block(std.BaseScope, mnemonic="weave.Block"):
    """Lexical block."""

    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    def __post_init__(self) -> None:
        _check_body(self.body)


@dc.py_class("weave.LeaderCtaBlock", structural_eq="tree")
class LeaderCtaBlock(std.BaseScope, mnemonic="weave.LeaderCtaBlock"):
    """Block executed by the leader CTA."""

    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    def __post_init__(self) -> None:
        _check_body(self.body)


@dc.py_class("weave.ElectedThreadBlock", structural_eq="tree")
class ElectedThreadBlock(std.BaseScope, mnemonic="weave.ElectedThreadBlock"):
    """Block executed by an elected thread."""

    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    def __post_init__(self) -> None:
        _check_body(self.body)


@dc.py_class("weave.ConditionalIteration", structural_eq="tree")
class ConditionalIteration(std.BaseScope, mnemonic="weave.ConditionalIteration"):
    """Canonicalized conditional-iteration scope."""

    iter_var: std.Expr = dc.field(lang_kind="arg")
    last_expr: std.Expr | None = dc.field(default=None, lang_kind="attr")
    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    def __post_init__(self) -> None:
        object.__setattr__(self, "iter_var", normalize_expr(self.iter_var, field_name="iter_var"))
        object.__setattr__(
            self,
            "last_expr",
            normalize_optional_expr(self.last_expr, field_name="last_expr"),
        )
        _check_body(self.body)


@dc.py_class("weave.VarDecl", structural_eq="tree")
class VarDecl(std.BaseVarDef, mnemonic="weave.VarDecl"):
    """Variable declaration with C type spelling metadata."""

    __ffi_dialect_field_collector__ = staticmethod(collect_fields_with_var_def_ty)

    var: std.Var = dc.field(lang_kind="var_def", structural_eq="def-recursive")
    ctype: str = dc.field(lang_kind="arg")
    init: std.Expr | None = dc.field(default=None, lang_kind="attr")
    array_size: std.Expr | None = dc.field(default=None, lang_kind="attr")
    uniform: bool = dc.field(default=False, lang_kind="attr")
    zero_init: bool = dc.field(default=False, lang_kind="attr")

    def __init__(
        self,
        ctype: str,
        init: std.Expr | None = None,
        array_size: std.Expr | None = None,
        uniform: bool = False,
        zero_init: bool = False,
        var: std.Var | None = None,
        *,
        ty: Any = None,
    ) -> None:
        self.__ffi_init__(
            var_with_ty_hint(var, ty, field_name="var"),
            ctype,
            init,
            array_size,
            uniform,
            zero_init,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        if not isinstance(self.var, std.Var):
            raise TypeError("var must be std.Var")
        if self.init is not None:
            object.__setattr__(self, "init", normalize_expr(self.init, field_name="init"))
        if self.array_size is not None:
            object.__setattr__(
                self,
                "array_size",
                normalize_expr(self.array_size, field_name="array_size"),
            )

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        var = std.Var(self.var.ty, name[0])
        object.__setattr__(self, "var", var)
        self.__post_init__()
        return (var,)


@dc.py_class("weave.Assign", structural_eq="tree")
class Assign(std.Stmt, mnemonic="weave.Assign"):
    """Mutation assignment."""

    target: std.Expr = dc.field(lang_kind="arg")
    expr: std.Expr = dc.field(lang_kind="arg")
    op: str = dc.field(default="=", lang_kind="attr")

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", normalize_expr(self.target, field_name="target"))
        object.__setattr__(self, "expr", normalize_expr(self.expr, field_name="expr"))
        if self.op not in ASSIGN_OPS:
            raise ValueError(f"unknown assignment operator: {self.op}")


__all__ = [
    "Assign",
    "Block",
    "ConditionalIteration",
    "ElectedThreadBlock",
    "ForLoop",
    "LeaderCtaBlock",
    "TaskSpec",
    "VarDecl",
]
