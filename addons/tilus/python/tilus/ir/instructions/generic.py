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
"""Generic Tilus instructions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi.core import MISSING

from .. import tensor as tensor_mod
from ..inst import Instruction, validate_instruction_ty_hint


@dc.py_class("tilus.LoadGlobalInst", structural_eq="tree")
class LoadGlobalInst(Instruction, mnemonic="tilus.LoadGlobal"):
    """Load from a global tensor into a register tensor."""

    EXPECTED_INPUTS: ClassVar[int] = 1
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = (("offsets", "dims"),)
    TY_INPUT_INDICES: ClassVar[tuple[int, ...]] = (0,)

    offsets: list[std.Expr] = dc.field(default_factory=list, lang_kind="attr")
    dims: list[int] = dc.field(default_factory=list, lang_kind="attr")

    @staticmethod
    def input_ty_from_output_ty(output_ty: std.Ty) -> std.Ty:
        if isinstance(output_ty, tensor_mod.GlobalTensor):
            return output_ty
        if not isinstance(output_ty, tensor_mod.Tensor):
            raise TypeError(
                f"LoadGlobalInst `ty` must be a Tilus tensor, got {type(output_ty).__name__}"
            )
        return tensor_mod.GlobalTensor(output_ty.dtype, shape=tuple(output_ty.shape))

    @staticmethod
    def output_ty_from_ty_hint(ty: std.Ty) -> std.Ty:
        if isinstance(ty, tensor_mod.GlobalTensor):
            return tensor_mod.RegisterTensor(ty.dtype, shape=tuple(ty.shape))
        return ty

    def __init__(
        self,
        inputs: Sequence[std.Expr] | None = None,
        output: std.Var | None = None,
        offsets: Sequence[std.Expr] | None = None,
        dims: Sequence[int] | None = None,
        *,
        ty: Any = MISSING,
    ) -> None:
        self.__ffi_init__(
            list(inputs) if inputs is not None else [],
            output,
            list(offsets) if offsets is not None else [],
            list(dims) if dims is not None else [],
        )
        self.__post_init__()
        if not MISSING.is_(ty):
            validate_instruction_ty_hint(self, ty)


@dc.py_class("tilus.StoreGlobalInst", structural_eq="tree")
class StoreGlobalInst(Instruction, mnemonic="tilus.StoreGlobal"):
    """Store a register tensor into a global tensor."""

    EXPECTED_INPUTS: ClassVar[int] = 2
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = (("offsets", "dims"),)

    offsets: list[std.Expr] = dc.field(default_factory=list, lang_kind="attr")
    dims: list[int] = dc.field(default_factory=list, lang_kind="attr")


@dc.py_class("tilus.LoadSharedInst", structural_eq="tree")
class LoadSharedInst(Instruction, mnemonic="tilus.LoadShared"):
    """Load from shared memory."""

    EXPECTED_INPUTS: ClassVar[int] = 1
    TY_INPUT_INDICES: ClassVar[tuple[int, ...]] = (0,)

    @staticmethod
    def input_ty_from_output_ty(output_ty: std.Ty) -> std.Ty:
        if isinstance(output_ty, tensor_mod.SharedTensor):
            return output_ty
        if not isinstance(output_ty, tensor_mod.Tensor):
            raise TypeError(
                f"LoadSharedInst `ty` must be a Tilus tensor, got {type(output_ty).__name__}"
            )
        return tensor_mod.SharedTensor(output_ty.dtype, shape=tuple(output_ty.shape))

    @staticmethod
    def output_ty_from_ty_hint(ty: std.Ty) -> std.Ty:
        if isinstance(ty, tensor_mod.SharedTensor):
            return tensor_mod.RegisterTensor(ty.dtype, shape=tuple(ty.shape))
        return ty

    def __init__(
        self,
        inputs: Sequence[std.Expr] | None = None,
        output: std.Var | None = None,
        *,
        ty: Any = MISSING,
    ) -> None:
        self.__ffi_init__(list(inputs) if inputs is not None else [], output)
        self.__post_init__()
        if not MISSING.is_(ty):
            validate_instruction_ty_hint(self, ty)


@dc.py_class("tilus.StoreSharedInst", structural_eq="tree")
class StoreSharedInst(Instruction, mnemonic="tilus.StoreShared"):
    """Store to shared memory."""

    EXPECTED_INPUTS: ClassVar[int] = 2


@dc.py_class("tilus.CastInst", structural_eq="tree")
class CastInst(Instruction, mnemonic="tilus.Cast"):
    """Cast a tensor."""

    EXPECTED_INPUTS: ClassVar[int] = 1


@dc.py_class("tilus.AddInst", structural_eq="tree")
class AddInst(Instruction, mnemonic="tilus.Add"):
    """Elementwise addition."""

    EXPECTED_INPUTS: ClassVar[int] = 2
    OUTPUT_TY_INFERABLE_FROM_INPUTS: ClassVar[bool] = True


@dc.py_class("tilus.SubInst", structural_eq="tree")
class SubInst(Instruction, mnemonic="tilus.Sub"):
    """Elementwise subtraction."""

    EXPECTED_INPUTS: ClassVar[int] = 2
    OUTPUT_TY_INFERABLE_FROM_INPUTS: ClassVar[bool] = True


@dc.py_class("tilus.MulInst", structural_eq="tree")
class MulInst(Instruction, mnemonic="tilus.Mul"):
    """Elementwise multiplication."""

    EXPECTED_INPUTS: ClassVar[int] = 2
    OUTPUT_TY_INFERABLE_FROM_INPUTS: ClassVar[bool] = True


@dc.py_class("tilus.DivInst", structural_eq="tree")
class DivInst(Instruction, mnemonic="tilus.Div"):
    """Elementwise division."""

    EXPECTED_INPUTS: ClassVar[int] = 2
    OUTPUT_TY_INFERABLE_FROM_INPUTS: ClassVar[bool] = True


@dc.py_class("tilus.ReduceInst", structural_eq="tree")
class ReduceInst(Instruction, mnemonic="tilus.Reduce"):
    """Tensor reduction."""

    EXPECTED_INPUTS: ClassVar[int] = 1
    VALID_OPS: ClassVar[tuple[str, ...]] = ("sum", "max", "min")

    dim: int = dc.field(default=0, lang_kind="attr")
    op: str = dc.field(default="sum", lang_kind="attr")
    keepdim: bool = dc.field(default=False, lang_kind="attr")


@dc.py_class("tilus.SyncThreadsInst", structural_eq="tree")
class SyncThreadsInst(Instruction, mnemonic="tilus.SyncThreads"):
    """Synchronize all threads."""

    EXPECTED_INPUTS: ClassVar[int] = 0


@dc.py_class("tilus.NopInst", structural_eq="tree")
class NopInst(Instruction, mnemonic="tilus.Nop"):
    """No-op instruction."""

    EXPECTED_INPUTS: ClassVar[int] = 0


__all__ = [
    "AddInst",
    "CastInst",
    "DivInst",
    "LoadGlobalInst",
    "LoadSharedInst",
    "MulInst",
    "NopInst",
    "ReduceInst",
    "StoreGlobalInst",
    "StoreSharedInst",
    "SubInst",
    "SyncThreadsInst",
]
