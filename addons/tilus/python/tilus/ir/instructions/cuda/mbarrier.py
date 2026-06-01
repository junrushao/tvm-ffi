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

MBARRIER_ARRIVE_SEMS = ("release", "relaxed")
MBARRIER_WAIT_SEMS = ("acquire", "relaxed")
MBARRIER_SCOPES = ("cta", "cluster")


@py_class("tilus.AllocBarrierInst", structural_eq="tree")
class AllocBarrierInst(Instruction, mnemonic="tilus.AllocBarrier"):
    counts: list[std.Expr] = field(lang_kind="arg")

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.ArriveBarrierInst", structural_eq="tree")
class ArriveBarrierInst(Instruction, mnemonic="tilus.ArriveBarrier"):
    barrier: std.Expr = field(lang_kind="arg")
    count: std.Expr = field(lang_kind="arg")
    sem: str = field(default="release", lang_kind="attr")
    scope: str = field(default="cta", lang_kind="attr")

    def __post_init__(self) -> None:
        validate_string_attr(self.sem, "sem", MBARRIER_ARRIVE_SEMS)
        validate_string_attr(self.scope, "scope", MBARRIER_SCOPES)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.ArriveExpectTxBarrierInst", structural_eq="tree")
class ArriveExpectTxBarrierInst(Instruction, mnemonic="tilus.ArriveExpectTxBarrier"):
    barrier: std.Expr = field(lang_kind="arg")
    transaction_bytes: std.Expr = field(lang_kind="arg")
    sem: str = field(default="release", lang_kind="attr")
    scope: str = field(default="cta", lang_kind="attr")

    def __post_init__(self) -> None:
        validate_string_attr(self.sem, "sem", MBARRIER_ARRIVE_SEMS)
        validate_string_attr(self.scope, "scope", MBARRIER_SCOPES)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.WaitBarrierInst", structural_eq="tree")
class WaitBarrierInst(Instruction, mnemonic="tilus.WaitBarrier"):
    barrier: std.Expr = field(lang_kind="arg")
    phase: std.Expr = field(lang_kind="arg")
    sem: str = field(default="acquire", lang_kind="attr")
    scope: str = field(default="cta", lang_kind="attr")

    def __post_init__(self) -> None:
        validate_string_attr(self.sem, "sem", MBARRIER_WAIT_SEMS)
        validate_string_attr(self.scope, "scope", MBARRIER_SCOPES)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.ArriveExpectTxMulticastBarrierInst", structural_eq="tree")
class ArriveExpectTxMulticastBarrierInst(
    Instruction, mnemonic="tilus.ArriveExpectTxMulticastBarrier"
):
    barrier: std.Expr = field(lang_kind="arg")
    transaction_bytes: std.Expr = field(lang_kind="arg")
    multicast_mask: std.Expr = field(lang_kind="arg")
    sem: str = field(default="release", lang_kind="attr")
    scope: str = field(default="cta", lang_kind="attr")

    def __post_init__(self) -> None:
        validate_string_attr(self.sem, "sem", MBARRIER_ARRIVE_SEMS)
        validate_string_attr(self.scope, "scope", MBARRIER_SCOPES)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@py_class("tilus.ArriveExpectTxRemoteBarrierInst", structural_eq="tree")
class ArriveExpectTxRemoteBarrierInst(Instruction, mnemonic="tilus.ArriveExpectTxRemoteBarrier"):
    barrier: std.Expr = field(lang_kind="arg")
    transaction_bytes: std.Expr = field(lang_kind="arg")
    target_rank: std.Expr = field(lang_kind="arg")
    sem: str = field(default="release", lang_kind="attr")
    scope: str = field(default="cta", lang_kind="attr")

    def __post_init__(self) -> None:
        validate_string_attr(self.sem, "sem", MBARRIER_ARRIVE_SEMS)
        validate_string_attr(self.scope, "scope", MBARRIER_SCOPES)

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


__all__ = [  # noqa: RUF022
    "AllocBarrierInst",
    "ArriveBarrierInst",
    "ArriveExpectTxBarrierInst",
    "WaitBarrierInst",
    "ArriveExpectTxMulticastBarrierInst",
    "ArriveExpectTxRemoteBarrierInst",
]
