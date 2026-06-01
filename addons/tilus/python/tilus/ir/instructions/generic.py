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

from typing import cast

from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi.core import MISSING
from tvm_ffi.structural import structural_equal

from .. import tensor as tensor_mod
from ..inst import (
    Instruction,
    make_output_var,
    validate_matching_lengths,
    validate_string_attr,
)


@dc.py_class("tilus.LoadGlobalInst", structural_eq="tree")
class LoadGlobalInst(Instruction, mnemonic="tilus.LoadGlobal"):
    """Load from a global tensor into a register tensor."""

    src: std.Expr = dc.field(lang_kind="arg")
    output: std.Var = dc.field(
        kw_only=True,
        lang_kind="out",
        structural_eq="def-recursive",
    )
    offsets: list[std.Expr] = dc.field(default_factory=list, lang_kind="arg")
    dims: list[int] = dc.field(default_factory=list, lang_kind="attr")

    def __init__(
        self,
        src: std.Expr,
        offsets: list[std.ExprLike] | object = MISSING,
        dims: list[int] | object = MISSING,
        *,
        output: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        if MISSING.is_(offsets):
            offsets = []
        if MISSING.is_(dims):
            dims = []
        if ty is not None and output is None:
            ty = std.normalize_ty(ty)
            if not isinstance(src, std.Var):
                raise TypeError("LoadGlobalInst `ty` keyword requires src to be std.Var")
            if not isinstance(ty, (tensor_mod.RegisterTensor, tensor_mod.GlobalTensor)):
                raise TypeError(
                    f"LoadGlobalInst `ty` must be a register or global tensor, got {type(ty).__name__}"
                )
            if not isinstance(src.ty, tensor_mod.GlobalTensor) or not structural_equal(
                src.ty.dtype, ty.dtype
            ):
                raise TypeError(
                    "LoadGlobalInst `ty` keyword must match src dtype and storage scope"
                )
            ty = (
                tensor_mod.RegisterTensor(ty.dtype, shape=tuple(ty.shape))
                if isinstance(ty, tensor_mod.GlobalTensor)
                else ty
            )
        output = make_output_var(output, ty)
        self.__ffi_init__(
            src,
            offsets=cast(list[std.ExprLike], offsets),
            dims=cast(list[int], dims),
            output=output,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        validate_matching_lengths(self, "offsets", "dims")

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


@dc.py_class("tilus.StoreGlobalInst", structural_eq="tree")
class StoreGlobalInst(Instruction, mnemonic="tilus.StoreGlobal"):
    """Store a register tensor into a global tensor."""

    dst: std.Expr = dc.field(lang_kind="arg")
    value: std.Expr = dc.field(lang_kind="arg")
    offsets: list[std.Expr] = dc.field(default_factory=list, lang_kind="arg")
    dims: list[int] = dc.field(default_factory=list, lang_kind="attr")

    def __post_init__(self) -> None:
        validate_matching_lengths(self, "offsets", "dims")

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@dc.py_class("tilus.LoadSharedInst", structural_eq="tree")
class LoadSharedInst(Instruction, mnemonic="tilus.LoadShared"):
    """Load from shared memory."""

    src: std.Expr = dc.field(lang_kind="arg")
    output: std.Var = dc.field(
        kw_only=True,
        lang_kind="out",
        structural_eq="def-recursive",
    )

    def __init__(
        self,
        src: std.Expr,
        *,
        output: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        if ty is not None and output is None:
            ty = std.normalize_ty(ty)
            if not isinstance(src, std.Var):
                raise TypeError("LoadSharedInst `ty` keyword requires src to be std.Var")
            if not isinstance(ty, (tensor_mod.RegisterTensor, tensor_mod.SharedTensor)):
                raise TypeError(
                    f"LoadSharedInst `ty` must be a register or shared tensor, got {type(ty).__name__}"
                )
            if not isinstance(src.ty, tensor_mod.SharedTensor) or not structural_equal(
                src.ty.dtype, ty.dtype
            ):
                raise TypeError(
                    "LoadSharedInst `ty` keyword must match src dtype and storage scope"
                )
            ty = (
                tensor_mod.RegisterTensor(ty.dtype, shape=tuple(ty.shape))
                if isinstance(ty, tensor_mod.SharedTensor)
                else ty
            )
        output = make_output_var(output, ty)
        self.__ffi_init__(src, output=output)
        self.__post_init__()

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


@dc.py_class("tilus.StoreSharedInst", structural_eq="tree")
class StoreSharedInst(Instruction, mnemonic="tilus.StoreShared"):
    """Store to shared memory."""

    dst: std.Expr = dc.field(lang_kind="arg")
    value: std.Expr = dc.field(lang_kind="arg")

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@dc.py_class("tilus.CastInst", structural_eq="tree")
class CastInst(Instruction, mnemonic="tilus.Cast"):
    """Cast a tensor."""

    src: std.Expr = dc.field(lang_kind="arg")
    output: std.Var = dc.field(
        kw_only=True,
        lang_kind="out",
        structural_eq="def-recursive",
    )

    def __init__(
        self,
        src: std.Expr,
        *,
        output: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        output = make_output_var(output, ty)
        self.__ffi_init__(src, output=output)
        self.__post_init__()

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


@dc.py_class("tilus.AddInst", structural_eq="tree")
class AddInst(Instruction, mnemonic="tilus.Add"):
    """Elementwise addition."""

    lhs: std.Expr = dc.field(lang_kind="arg")
    rhs: std.Expr = dc.field(lang_kind="arg")
    output: std.Var = dc.field(
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
        self.__post_init__()

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


@dc.py_class("tilus.SubInst", structural_eq="tree")
class SubInst(Instruction, mnemonic="tilus.Sub"):
    """Elementwise subtraction."""

    lhs: std.Expr = dc.field(lang_kind="arg")
    rhs: std.Expr = dc.field(lang_kind="arg")
    output: std.Var = dc.field(
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
        self.__post_init__()

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


@dc.py_class("tilus.MulInst", structural_eq="tree")
class MulInst(Instruction, mnemonic="tilus.Mul"):
    """Elementwise multiplication."""

    lhs: std.Expr = dc.field(lang_kind="arg")
    rhs: std.Expr = dc.field(lang_kind="arg")
    output: std.Var = dc.field(
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
        self.__post_init__()

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


@dc.py_class("tilus.DivInst", structural_eq="tree")
class DivInst(Instruction, mnemonic="tilus.Div"):
    """Elementwise division."""

    lhs: std.Expr = dc.field(lang_kind="arg")
    rhs: std.Expr = dc.field(lang_kind="arg")
    output: std.Var = dc.field(
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
        self.__post_init__()

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)


@dc.py_class("tilus.ReduceInst", structural_eq="tree")
class ReduceInst(Instruction, mnemonic="tilus.Reduce"):
    """Tensor reduction."""

    src: std.Expr = dc.field(lang_kind="arg")
    output: std.Var = dc.field(
        kw_only=True,
        lang_kind="out",
        structural_eq="def-recursive",
    )
    dim: int = dc.field(default=0, lang_kind="attr")
    op: str = dc.field(default="sum", lang_kind="attr")
    keepdim: bool = dc.field(default=False, lang_kind="attr")

    def __init__(
        self,
        src: std.Expr,
        dim: int = 0,
        op: str = "sum",
        keepdim: bool = False,
        *,
        output: std.Var | None = None,
        ty: std.TyLike | None = None,
    ) -> None:
        output = make_output_var(output, ty)
        self.__ffi_init__(src, dim=dim, op=op, keepdim=keepdim, output=output)
        self.__post_init__()

    def outputs(self) -> tuple[std.Var, ...]:
        return (self.output,)

    def __post_init__(self) -> None:
        validate_string_attr(self.op, "op", ("sum", "max", "min"))


@dc.py_class("tilus.SyncThreadsInst", structural_eq="tree")
class SyncThreadsInst(Instruction, mnemonic="tilus.SyncThreads"):
    """Synchronize all threads."""

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


@dc.py_class("tilus.NopInst", structural_eq="tree")
class NopInst(Instruction, mnemonic="tilus.Nop"):
    """No-op instruction."""

    def outputs(self) -> tuple[std.Var, ...]:
        return ()


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
