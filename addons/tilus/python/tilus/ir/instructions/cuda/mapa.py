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

from ...inst import Instruction, make_output_var


@py_class("tilus.MapSharedAddrInst", structural_eq="tree")
class MapSharedAddrInst(Instruction, mnemonic="tilus.MapSharedAddr"):
    src: std.Expr = field(lang_kind="arg")
    target_rank: std.Expr = field(lang_kind="arg")
    output: std.Var = field(
        kw_only=True,
        lang_kind="out",
        structural_eq="def-recursive",
    )

    def __init__(
        self,
        src: std.Expr,
        target_rank: std.Expr,
        *,
        output: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        output = make_output_var(output, ty)
        self.__ffi_init__(src, target_rank=target_rank, output=output)
        self.__post_init__()

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


__all__ = [
    "MapSharedAddrInst",
]
