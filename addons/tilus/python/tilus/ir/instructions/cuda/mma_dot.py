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

from tvm_ffi import dtype, std
from tvm_ffi.dataclasses import field, py_class

from ...inst import Instruction, make_output_var
from ...layout import Layout


@py_class("tilus.DotInst", structural_eq="tree")
class DotInst(Instruction, mnemonic="tilus.Dot"):
    lhs: std.Expr = field(lang_kind="arg")
    rhs: std.Expr = field(lang_kind="arg")
    output: std.Var = field(
        kw_only=True,
        lang_kind="out",
        structural_eq="def-recursive",
    )

    def __init__(
        self,
        lhs: std.Expr,
        rhs: std.Expr,
        *,
        output: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        output = make_output_var(output, ty)
        self.__ffi_init__(lhs, rhs, output=output)

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


@py_class("tilus.AtomicMmaConfig", structural_eq="tree")
class AtomicMmaConfig(std.Attrs, mnemonic="tilus.AtomicMmaConfig"):
    name: str = field(lang_kind="attr")
    m: int = field(lang_kind="attr")
    n: int = field(lang_kind="attr")
    k: int = field(lang_kind="attr")
    vec_k: int = field(lang_kind="attr")
    la: Layout = field(lang_kind="attr")
    lb: Layout = field(lang_kind="attr")
    lc: Layout = field(lang_kind="attr")
    operand_type: dtype = field(lang_kind="attr")
    acc_type: dtype = field(lang_kind="attr")


__all__ = [  # noqa: RUF022
    "DotInst",
    "AtomicMmaConfig",
]
