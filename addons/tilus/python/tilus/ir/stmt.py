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
from tvm_ffi import std

from .tensor import GlobalTensor, SharedTensor, Tensor, TMemoryTensor


def _collect_tensor_item_ptr_fields(obj: TensorItemPtr) -> std.FieldCollectionResult:
    return std.FieldCollectionResult(
        outs=[obj.var],
        ty=obj.var.ty,
    )


def _collect_tensor_item_value_fields(obj: TensorItemValue) -> std.FieldCollectionResult:
    return std.FieldCollectionResult(outs=[obj.var], ty=obj.var.ty)


@dc.py_class("tilus.ThreadGroup", structural_eq="tree")
class ThreadGroup(std.BaseScope, mnemonic="tilus.ThreadGroup"):
    """Restrict a body to a contiguous group of threads."""

    thread_begin: int = dc.field(lang_kind="attr")
    num_threads: int = dc.field(lang_kind="attr")
    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")

    def __post_init__(self) -> None:
        if self.num_threads <= 0:
            raise ValueError("num_threads must be positive")


@dc.py_class("tilus.Evaluate", structural_eq="tree")
class Evaluate(std.Stmt, mnemonic="tilus.Eval"):
    """Evaluate an expression for side effects, optionally predicated."""

    expr: std.Expr = dc.field(lang_kind="arg")
    pred: std.Expr | None = dc.field(default=None, lang_kind="arg")


@dc.py_class("tilus.TensorItemPtr", structural_eq="tree")
class TensorItemPtr(std.BaseVarDef, mnemonic="tilus.TensorItemPtr"):
    """Bind a pointer to a tensor item."""

    __ffi_dialect_field_collector__ = staticmethod(_collect_tensor_item_ptr_fields)

    var: std.Var = dc.field(lang_kind="out", structural_eq="def-recursive")

    def __init__(self, var: std.Var) -> None:
        _check_tensor_ptr_var(var)
        self.__ffi_init__(var=var)

    @property
    def tensor(self) -> Tensor:
        return _check_tensor_ptr_var(self.var)

    @property
    def space(self) -> str:
        return _derive_tensor_ptr_space(self.tensor)

    def __post_init__(self) -> None:
        _check_tensor_ptr_var(self.var)

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        self.var.name = name[0]
        self.__post_init__()
        return (self.var,)


@dc.py_class("tilus.TensorItemValue", structural_eq="tree")
class TensorItemValue(std.BaseVarDef, mnemonic="tilus.TensorItemValue"):
    """Bind the scalar value of a tensor item."""

    __ffi_dialect_field_collector__ = staticmethod(_collect_tensor_item_value_fields)

    var: std.Var = dc.field(lang_kind="out", structural_eq="def-recursive")

    def __init__(self, var: std.Var) -> None:
        _check_tensor_var(var)
        self.__ffi_init__(var=var)

    @property
    def tensor(self) -> Tensor:
        return _check_tensor_var(self.var)

    def __post_init__(self) -> None:
        _check_tensor_var(self.var)

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        self.var.name = name[0]
        self.__post_init__()
        return (self.var,)


def thread_group(
    thread_begin: int,
    num_threads: int,
    body: Sequence[std.Stmt] | None = None,
) -> ThreadGroup:
    """Create a thread-group statement."""
    return ThreadGroup(thread_begin, num_threads, list(body or ()))


def _check_tensor_var(var: std.Var) -> Tensor:
    if not isinstance(var.ty, Tensor):
        raise TypeError("`var` must be a std.Var whose ty is a Tilus Tensor")
    return var.ty


def _derive_tensor_ptr_space(tensor: Tensor) -> str:
    if isinstance(tensor, SharedTensor):
        return "shared"
    if isinstance(tensor, GlobalTensor):
        return "global"
    if isinstance(tensor, TMemoryTensor):
        return "tmem"
    raise TypeError("TensorItemPtr requires a SharedTensor, GlobalTensor, or TMemoryTensor")


def _check_tensor_ptr_var(var: std.Var) -> Tensor:
    tensor = _check_tensor_var(var)
    _derive_tensor_ptr_space(tensor)
    return tensor


__all__ = [
    "Evaluate",
    "TensorItemPtr",
    "TensorItemValue",
    "ThreadGroup",
    "thread_group",
]
