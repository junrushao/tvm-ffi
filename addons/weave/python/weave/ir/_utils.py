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

from collections.abc import Iterable, Sequence
from typing import Any, ClassVar

from tvm_ffi import Array, List, std
from tvm_ffi import dataclasses as dc
from tvm_ffi.structural import structural_equal


def normalize_dtype(value: Any, *, field_name: str) -> std.Ty | None:
    """Normalize dtype-bearing fields while rejecting ambiguous raw strings."""
    if value is None:
        return None
    if isinstance(value, str):
        raise TypeError(f"{field_name} must be a Weave/std type, not raw string")
    try:
        return std.normalize_ty(value)
    except TypeError as err:
        raise TypeError(f"{field_name}: {err}") from None


def validate_cta_group(value: Any, *, field_name: str = "cta_group") -> int:
    """Validate CTA group ids without accepting bool-as-int values."""
    if type(value) is not int or value not in (1, 2):
        raise ValueError(f"{field_name} must be 1 or 2")
    return value


def normalize_expr(value: Any, *, field_name: str = "expr") -> std.Expr:
    """Normalize literals to ``std.Expr`` and reject raw strings."""
    if isinstance(value, std.StringImm):
        raise TypeError(f"{field_name} expects std.Expr, not raw string")
    if isinstance(value, std.Expr):
        return value
    if isinstance(value, str):
        raise TypeError(f"{field_name} expects std.Expr, not raw string {value!r}")
    if isinstance(value, (bool, int, float)):
        return std.Expr.literal(value)
    raise TypeError(f"{field_name} expects std.Expr, got {type(value).__name__}")


def normalize_optional_expr(value: Any, *, field_name: str) -> std.Expr | None:
    """Normalize an optional expression field."""
    if value is None:
        return None
    return normalize_expr(value, field_name=field_name)


def normalize_expr_sequence(value: Any, *, field_name: str) -> list[std.Expr]:
    """Normalize a sequence of expression-like values."""
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{field_name} expects a sequence of std.Expr, not {value!r}")
    if not isinstance(value, Iterable):
        raise TypeError(f"{field_name} expects a sequence, got {type(value).__name__}")
    return [normalize_expr(item, field_name=f"{field_name}[]") for item in value]


def normalize_expr_fields(obj: Any, field_names: Iterable[str]) -> None:
    """Normalize named expression fields on a py_class object in-place."""
    for name in field_names:
        value = getattr(obj, name)
        if value is None:
            continue
        if isinstance(value, (list, tuple, List, Array)):
            normalized = normalize_expr_sequence(value, field_name=name)
            if isinstance(value, tuple):
                normalized_value: Any = tuple(normalized)
            elif isinstance(value, (List, Array)):
                normalized_value = type(value)(normalized)
            else:
                normalized_value = normalized
        else:
            normalized_value = normalize_expr(value, field_name=name)
        if normalized_value is not value:
            object.__setattr__(obj, name, normalized_value)


def normalize_domain(value: Any, valid: Sequence[str], *, field_name: str) -> str:
    """Normalize a string-like domain value and validate it."""
    if hasattr(value, "value") and isinstance(value.value, str):
        value = value.value
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value).__name__}")
    if value not in valid:
        choices = ", ".join(repr(item) for item in valid)
        raise ValueError(f"{field_name} must be one of {choices}, got {value!r}")
    return value


def collect_fields_with_var_def_ty(obj: Any) -> std.FieldCollectionResult:
    """Collect dialect fields and print the single defined variable type as ``ty=``."""
    fields = std.collect_dialect_fields(obj)
    var_def = list(fields.var_def)
    ty = var_def[0].ty if len(var_def) == 1 else None
    return std.FieldCollectionResult(
        args=list(fields.args),
        attrs=fields.attrs,
        var_def=var_def,
        body=list(fields.body),
        ty=ty,
    )


def var_with_ty_hint(var: std.Var | None, ty: Any, *, field_name: str) -> std.Var:
    """Return a constructor-owned variable, optionally created from ``ty``."""
    if var is None:
        if ty is None:
            raise TypeError(f"{field_name} requires std.Var or ty")
        return std.Var(std.normalize_ty(ty), "")
    if not isinstance(var, std.Var):
        raise TypeError(f"{field_name} must be std.Var")
    if ty is None:
        if isinstance(var.ty, std.AnyTy):
            raise TypeError(f"{field_name} requires a concrete type")
        return var
    normalized_ty = std.normalize_ty(ty)
    if not isinstance(var.ty, std.AnyTy) and not structural_equal(var.ty, normalized_ty):
        raise TypeError(f"{field_name} type does not match ty")
    return std.Var(normalized_ty, var.name)


def _collect_op_fields(obj: Any) -> std.FieldCollectionResult:
    fields = std.collect_dialect_fields(obj)
    var_def = list(fields.var_def)
    ty = (
        var_def[0].ty
        if len(var_def) == 1 and not type(obj).OUTPUT_TY_INFERABLE_FROM_INPUTS
        else None
    )
    return std.FieldCollectionResult(
        args=list(fields.args),
        attrs=fields.attrs,
        var_def=var_def,
        body=list(fields.body),
        ty=ty,
    )


@dc.py_class("weave.Op", structural_eq="tree", init=False)
class Op(std.BaseVarDef, mnemonic="weave.Op"):
    """Base class for executable Weave operations."""

    __ffi_dialect_field_collector__ = staticmethod(_collect_op_fields)

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset()
    OUTPUT_TY_INFERABLE_FROM_INPUTS: ClassVar[bool] = False
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {}

    def __post_init__(self) -> None:
        normalize_expr_fields(self, self.EXPR_FIELDS)
        for field_name, valid_values in self.VALID_DOMAINS.items():
            value = getattr(self, field_name, None)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    normalize_domain(value, valid_values, field_name=field_name),
                )


@dc.py_class("weave.MarkerTy", structural_eq="tree", init=False)
class MarkerTy(std.Ty, mnemonic="weave.MarkerTy"):
    """Base class for no-field Weave marker types."""


@dc.py_class("weave.MarkerNode", structural_eq="tree", init=False)
class MarkerNode(std.Node, mnemonic="weave.MarkerNode"):
    """Base class for no-field Weave marker nodes."""


__all__ = [
    "MarkerNode",
    "MarkerTy",
    "Op",
    "collect_fields_with_var_def_ty",
    "normalize_domain",
    "normalize_dtype",
    "normalize_expr",
    "normalize_expr_fields",
    "normalize_expr_sequence",
    "normalize_optional_expr",
    "validate_cta_group",
    "var_with_ty_hint",
]
