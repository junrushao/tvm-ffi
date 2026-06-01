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

from ...inst import (
    Instruction,
    make_output_var,
    validate_matching_lengths,
)


@py_class("tilus.SimtDotInst", structural_eq="tree")
class SimtDotInst(Instruction, mnemonic="tilus.SimtDot"):
    lhs: std.Expr = field(lang_kind="arg")
    rhs: std.Expr = field(lang_kind="arg")
    warp_spatial: list[int] = field(lang_kind="attr")
    warp_repeat: list[int] = field(lang_kind="attr")
    thread_spatial: list[int] = field(lang_kind="attr")
    thread_repeat: list[int] = field(lang_kind="attr")
    output: std.Var = field(
        kw_only=True,
        lang_kind="out",
        structural_eq="def-recursive",
    )

    def __init__(
        self,
        lhs: std.Expr,
        rhs: std.Expr,
        warp_spatial: list[int],
        warp_repeat: list[int],
        thread_spatial: list[int],
        thread_repeat: list[int],
        *,
        output: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        output = make_output_var(output, ty)
        self.__ffi_init__(
            lhs,
            rhs,
            warp_spatial=warp_spatial,
            warp_repeat=warp_repeat,
            thread_spatial=thread_spatial,
            thread_repeat=thread_repeat,
            output=output,
        )
        validate_matching_lengths(self, "warp_spatial", "warp_repeat")
        validate_matching_lengths(self, "thread_spatial", "thread_repeat")
        validate_matching_lengths(self, "warp_spatial", "thread_spatial")

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


__all__ = [
    "SimtDotInst",
]
