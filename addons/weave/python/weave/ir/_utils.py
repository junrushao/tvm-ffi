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
"""Shared helpers for Weave IR nodes."""

from __future__ import annotations

from collections.abc import Sequence

from tvm_ffi import dataclasses as dc
from tvm_ffi import dtype as tvm_dtype
from tvm_ffi import std


def normalize_dtype(value: std.TyLike | tvm_dtype, *, field_name: str) -> tvm_dtype:
    """Normalize scalar dtype attributes while rejecting ambiguous raw strings."""
    if isinstance(value, tvm_dtype):
        return value
    if isinstance(value, str):
        return tvm_dtype(value)
    try:
        ty = std.normalize_ty(value)
    except TypeError as err:
        raise TypeError(f"{field_name}: {err}") from None
    if not isinstance(ty, std.PrimTy):
        raise TypeError(f"{field_name} must be a scalar dtype, got {type(ty).__name__}")
    return ty.dtype


def validate_cta_group(value: int, *, field_name: str = "cta_group") -> int:
    """Validate CTA group ids without accepting bool-as-int values."""
    if type(value) is not int or value not in (1, 2):
        raise ValueError(f"{field_name} must be 1 or 2")
    return value


def validate_candidate_value(value: str, valid: Sequence[str], *, field_name: str) -> str:
    """Validate that a string field is one of the supported candidates."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value).__name__}")
    if value not in valid:
        choices = ", ".join(repr(item) for item in valid)
        raise ValueError(f"{field_name} must be one of {choices}, got {value!r}")
    return value


def collect_fields_with_out_ty(obj: std.Node) -> std.FieldCollectionResult:
    """Collect dialect fields and print the single defined variable type as ``ty=``."""
    fields = std.collect_dialect_fields(obj)
    outs = list(fields.outs)
    ty = outs[0].ty if len(outs) == 1 else None
    return std.FieldCollectionResult(
        args=list(fields.args),
        attrs=fields.attrs,
        outs=outs,
        body=list(fields.body),
        ty=ty,
    )


def var_with_ty_hint(var: std.Var | None, ty: std.TyLike | None, *, field_name: str) -> std.Var:
    """Return a constructor-owned variable, optionally created from ``ty``."""
    if var is None:
        if ty is None:
            raise TypeError(f"{field_name} requires std.Var or ty")
        return std.Var(std.normalize_ty(ty), "")
    if not isinstance(var, std.Var):
        raise TypeError(f"{field_name} must be std.Var")
    if ty is not None:
        raise TypeError(f"{field_name} and ty cannot both be supplied")
    if isinstance(var.ty, std.AnyTy):
        raise TypeError(f"{field_name} requires a concrete type")
    return var


@dc.py_class("weave.Effect", structural_eq="tree", init=False)
class Effect(std.Stmt, mnemonic="weave.Effect"):
    """Base class for executable Weave statements without defined outputs."""


@dc.py_class("weave.Op", structural_eq="tree", init=False)
class Op(Effect, mnemonic="weave.Op"):
    """Base class for executable Weave operations."""


@dc.py_class("weave.OutputOp", structural_eq="tree", init=False)
class OutputOp(std.BaseVarDef, mnemonic="weave.OutputOp"):
    """Base class for executable Weave operations that define output variables."""

    __ffi_dialect_field_collector__ = staticmethod(collect_fields_with_out_ty)


@dc.py_class("weave.MarkerTy", structural_eq="tree", init=False)
class MarkerTy(std.Ty, mnemonic="weave.MarkerTy"):
    """Base class for no-field Weave marker types."""


__all__ = [
    "Effect",
    "MarkerTy",
    "Op",
    "OutputOp",
    "collect_fields_with_out_ty",
    "normalize_dtype",
    "validate_candidate_value",
    "validate_cta_group",
    "var_with_ty_hint",
]
