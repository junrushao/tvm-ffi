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
"""Tilus statement nodes."""

from __future__ import annotations

from collections.abc import Sequence

from tvm_ffi import dataclasses as dc
from tvm_ffi import std, structural_equal

from .inst import Instruction
from .tensor import Tensor


def _check_tensor_var(var: std.Var, field_name: str) -> None:
    if not isinstance(var.ty, Tensor):
        raise TypeError(f"{field_name} must be a std.Var whose ty is a Tilus Tensor")


def _check_tensor_binding(tensor: Tensor, var: std.Var) -> None:
    _check_tensor_var(var, "var")
    if not structural_equal(var.ty, tensor):
        raise TypeError("var.ty must match tensor")


@dc.py_class("tilus.ThreadGroup", structural_eq="tree")
class ThreadGroup(std.BaseScope, mnemonic="tilus.ThreadGroup"):
    """Restrict a body to a contiguous group of threads."""

    thread_begin: int = dc.field(lang_kind="arg")
    num_threads: int = dc.field(lang_kind="arg")
    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    def __post_init__(self) -> None:
        if self.num_threads <= 0:
            raise ValueError("num_threads must be positive")


@dc.py_class("tilus.Evaluate", structural_eq="tree")
class Evaluate(std.Stmt, mnemonic="tilus.Eval"):
    """Evaluate an expression for side effects, optionally predicated."""

    expr: std.Expr = dc.field(lang_kind="arg")
    pred: std.Expr | None = dc.field(default=None, lang_kind="attr")


@dc.py_class("tilus.TensorItemPtr", structural_eq="tree")
class TensorItemPtr(std.BaseVarDef, mnemonic="tilus.TensorItemPtr"):
    """Bind a pointer to a tensor item."""

    tensor: Tensor = dc.field(lang_kind="arg")
    var: std.Var = dc.field(lang_kind="var_def", structural_eq="def-recursive")
    space: str | None = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        _check_tensor_binding(self.tensor, self.var)

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        var = std.Var(self.var.ty, name[0])
        object.__setattr__(self, "var", var)
        self.__post_init__()
        return (var,)


@dc.py_class("tilus.TensorItemValue", structural_eq="tree")
class TensorItemValue(std.BaseVarDef, mnemonic="tilus.TensorItemValue"):
    """Bind the scalar value of a tensor item."""

    tensor: Tensor = dc.field(lang_kind="arg")
    var: std.Var = dc.field(lang_kind="var_def", structural_eq="def-recursive")

    def __post_init__(self) -> None:
        _check_tensor_binding(self.tensor, self.var)

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        var = std.Var(self.var.ty, name[0])
        object.__setattr__(self, "var", var)
        self.__post_init__()
        return (var,)


@dc.py_class("tilus.Inst", structural_eq="tree")
class InstStmt(std.Stmt, mnemonic="tilus.Inst"):
    """Execute a Tilus instruction."""

    inst: Instruction = dc.field(lang_kind="arg")

    def __post_init__(self) -> None:
        if not isinstance(self.inst, Instruction):
            raise TypeError("inst must be a Tilus Instruction")


def thread_group(
    thread_begin: int,
    num_threads: int,
    body: Sequence[std.Stmt] | None = None,
) -> ThreadGroup:
    """Create a thread-group statement."""
    return ThreadGroup(thread_begin, num_threads, list(body or ()))


__all__ = [
    "Evaluate",
    "InstStmt",
    "TensorItemPtr",
    "TensorItemValue",
    "ThreadGroup",
    "thread_group",
]
