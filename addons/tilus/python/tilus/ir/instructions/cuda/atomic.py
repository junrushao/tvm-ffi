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

from tvm_ffi import std
from tvm_ffi.dataclasses import field, py_class

from ...inst import Instruction, validate_string_attr

ATOMIC_OPS = (
    "add",
    "sub",
    "min",
    "max",
    "and",
    "or",
    "xor",
    "exch",
    "exchange",
    "cas",
    "inc",
    "dec",
)
ATOMIC_SEMS = ("relaxed", "acquire", "release", "acq_rel")
ATOMIC_SCOPES = ("cta", "cluster", "gpu", "sys")


@py_class("tilus.AtomicSharedInst", structural_eq="tree")
class AtomicSharedInst(Instruction, mnemonic="tilus.AtomicShared"):
    ptr: std.Expr = field(lang_kind="arg")
    value: std.Expr = field(lang_kind="arg")
    op: str = field(lang_kind="attr")
    sem: str = field(default="relaxed", lang_kind="attr")
    scope: str = field(default="cta", lang_kind="attr")

    def __post_init__(self) -> None:
        validate_string_attr(self.op, "op", ATOMIC_OPS)
        validate_string_attr(self.sem, "sem", ATOMIC_SEMS)
        validate_string_attr(self.scope, "scope", ATOMIC_SCOPES)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.AtomicGlobalInst", structural_eq="tree")
class AtomicGlobalInst(Instruction, mnemonic="tilus.AtomicGlobal"):
    ptr: std.Expr = field(lang_kind="arg")
    value: std.Expr = field(lang_kind="arg")
    op: str = field(lang_kind="attr")
    sem: str = field(default="relaxed", lang_kind="attr")
    scope: str = field(default="gpu", lang_kind="attr")

    def __post_init__(self) -> None:
        validate_string_attr(self.op, "op", ATOMIC_OPS)
        validate_string_attr(self.sem, "sem", ATOMIC_SEMS)
        validate_string_attr(self.scope, "scope", ATOMIC_SCOPES)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.AtomicScatterSharedInst", structural_eq="tree")
class AtomicScatterSharedInst(Instruction, mnemonic="tilus.AtomicScatterShared"):
    ptr: std.Expr = field(lang_kind="arg")
    value: std.Expr = field(lang_kind="arg")
    op: str = field(lang_kind="attr")
    dim: int = field(lang_kind="attr")
    sem: str = field(default="relaxed", lang_kind="attr")
    scope: str = field(default="cta", lang_kind="attr")

    def __post_init__(self) -> None:
        validate_string_attr(self.op, "op", ("add", "sub", "min", "max"))
        validate_string_attr(self.sem, "sem", ATOMIC_SEMS)
        validate_string_attr(self.scope, "scope", ATOMIC_SCOPES)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.AtomicScatterGlobalInst", structural_eq="tree")
class AtomicScatterGlobalInst(Instruction, mnemonic="tilus.AtomicScatterGlobal"):
    ptr: std.Expr = field(lang_kind="arg")
    value: std.Expr = field(lang_kind="arg")
    op: str = field(lang_kind="attr")
    dim: int = field(lang_kind="attr")
    sem: str = field(default="relaxed", lang_kind="attr")
    scope: str = field(default="gpu", lang_kind="attr")

    def __post_init__(self) -> None:
        validate_string_attr(self.op, "op", ("add", "sub", "min", "max"))
        validate_string_attr(self.sem, "sem", ATOMIC_SEMS)
        validate_string_attr(self.scope, "scope", ATOMIC_SCOPES)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


__all__ = [  # noqa: RUF022
    "AtomicSharedInst",
    "AtomicGlobalInst",
    "AtomicScatterSharedInst",
    "AtomicScatterGlobalInst",
]
