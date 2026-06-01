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

from collections.abc import Iterable

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from ._utils import (
    Effect,
    collect_fields_with_out_ty,
    var_with_ty_hint,
)

ASSIGN_OPS = ("=", "+=", "-=", "*=", "/=", "%=", "//=", "^=", "&=", "|=", "<<=", ">>=")


def _check_body(body: Iterable[std.Stmt]) -> None:
    for stmt in body:
        if not isinstance(stmt, std.Stmt):
            raise TypeError(f"body expects std.Stmt, got {type(stmt).__name__}")


@dc.py_class("weave.TaskSpec", structural_eq="tree")
class TaskSpec(std.BaseScope, mnemonic="weave.TaskSpec"):
    """Task body assigned to a role and optional pipeline."""

    name: str = dc.field(lang_kind="attr")
    kind: str = dc.field(lang_kind="attr")
    assigned_role: str = dc.field(lang_kind="attr")
    sync_before: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    sync_after: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    pipeline: str = dc.field(default="", lang_kind="attr")
    inputs: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    outputs: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    depends_on: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TaskSpec.name must be non-empty")
        _check_body(self.body)


@dc.py_class("weave.ForLoop", structural_eq="tree")
class ForLoop(std.BaseFor, mnemonic="weave.ForLoop"):
    """Weave loop with schedule metadata."""

    start: std.Expr | None = dc.field(default=None, lang_kind="arg")
    step_expr: std.Expr | None = dc.field(default=None, lang_kind="arg")
    step: int | None = dc.field(default=None, lang_kind="attr")
    constexpr: bool | None = dc.field(default=None, lang_kind="attr")
    unroll: int | None = dc.field(default=None, lang_kind="attr")
    ctype: str | None = dc.field(default=None, lang_kind="attr")
    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    def __post_init__(self) -> None:
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
    last_expr: std.Expr | None = dc.field(default=None, lang_kind="arg")
    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    def __post_init__(self) -> None:
        _check_body(self.body)


@dc.py_class("weave.VarDecl", structural_eq="tree")
class VarDecl(std.BaseVarDef, mnemonic="weave.VarDecl"):
    """Variable declaration with C type spelling metadata."""

    __ffi_dialect_field_collector__ = staticmethod(collect_fields_with_out_ty)

    var: std.Var = dc.field(lang_kind="out", structural_eq="def-recursive")
    ctype: str = dc.field(kw_only=True, lang_kind="attr")
    init: std.Expr | None = dc.field(default=None, lang_kind="arg")
    array_size: std.Expr | None = dc.field(default=None, lang_kind="arg")
    uniform: bool = dc.field(default=False, lang_kind="attr")
    zero_init: bool = dc.field(default=False, lang_kind="attr")

    def __init__(
        self,
        init: std.Expr | bool | int | float | None = None,
        array_size: std.Expr | bool | int | float | None = None,
        *,
        ctype: str,
        uniform: bool = False,
        zero_init: bool = False,
        var: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        self.__ffi_init__(
            var=var_with_ty_hint(var, ty, field_name="var"),
            ctype=ctype,
            init=init,
            array_size=array_size,
            uniform=uniform,
            zero_init=zero_init,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        if not isinstance(self.var, std.Var):
            raise TypeError("var must be std.Var")

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        self.var.name = name[0]
        self.__post_init__()
        return (self.var,)


@dc.py_class("weave.Assign", structural_eq="tree")
class Assign(Effect, mnemonic="weave.Assign"):
    """Mutation assignment."""

    target: std.Expr = dc.field(lang_kind="arg")
    expr: std.Expr = dc.field(lang_kind="arg")
    op: str = dc.field(default="=", lang_kind="attr")

    def __post_init__(self) -> None:
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
