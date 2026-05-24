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

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, ClassVar

from tvm_ffi import Array, List, std
from tvm_ffi import dataclasses as dc
from tvm_ffi.dataclasses import fields


def collect_dialect_fields(obj: Any) -> std.FieldCollectionResult:
    """Collect ``lang_kind`` fields for Weave nodes, including empty marker nodes."""

    args: list[Any] = []
    attrs: dict[str, Any] = {}
    var_def: list[std.Var] = []
    body: list[Any] = []

    def extend_values(target: list[Any], value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (Array, List)):
            target.extend(value)
        else:
            target.append(value)

    def extend_var_def(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, std.Var):
            var_def.append(value)
        elif isinstance(value, (Array, List)):
            for item in value:
                extend_var_def(item)
        else:
            collector = getattr(type(value), "__ffi_dialect_field_collector__", None)
            if collector is None:
                raise TypeError(f"expected std.Var or var-def node, got {type(value).__name__}")
            var_def.extend(collector(value).var_def)

    for f in fields(obj):
        lang_kind = f.lang_kind
        if lang_kind is None:
            continue
        name = f.name
        if name is None:
            continue
        value = getattr(obj, name)
        if lang_kind == "arg":
            extend_values(args, value)
        elif lang_kind == "attr":
            if value is None:
                continue
            if name == "attrs" and isinstance(value, Mapping):
                attrs.update(value)
            else:
                attrs[name] = value
        elif lang_kind == "var_def":
            extend_var_def(value)
        elif lang_kind == "body":
            extend_values(body, value)
        else:
            raise ValueError(f"Invalid {lang_kind = } on {type(obj).__name__}.{name}")
    return std.FieldCollectionResult(args=args, attrs=attrs, var_def=var_def, body=body)


def normalize_ty(value: Any, default: std.Ty | None = None) -> std.Ty:
    """Normalize parser type factories, strings, and ``None`` to ``std.Ty``."""
    if value is None:
        if default is not None:
            return default
        return std.AnyTy()
    if isinstance(value, std.Ty):
        return value
    if hasattr(value, "to_dialect"):
        return value.to_dialect()
    if isinstance(value, str):
        return std.PrimTy(value)
    raise TypeError(f"expected std type, got {type(value).__name__}")


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


@dc.py_class("weave.Op", structural_eq="tree", init=False)
class Op(std.Stmt, mnemonic="weave.Op"):
    """Base class for executable Weave operations."""

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset()
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {}

    __ffi_dialect_field_collector__ = staticmethod(collect_dialect_fields)

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

    __ffi_dialect_field_collector__ = staticmethod(collect_dialect_fields)


@dc.py_class("weave.MarkerNode", structural_eq="tree", init=False)
class MarkerNode(std.Node, mnemonic="weave.MarkerNode"):
    """Base class for no-field Weave marker nodes."""

    __ffi_dialect_field_collector__ = staticmethod(collect_dialect_fields)


__all__ = [
    "MarkerNode",
    "MarkerTy",
    "Op",
    "collect_dialect_fields",
    "normalize_domain",
    "normalize_expr",
    "normalize_expr_fields",
    "normalize_expr_sequence",
    "normalize_optional_expr",
    "normalize_ty",
]
