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
"""Tilus instruction base nodes."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import std


class InstructionError(Exception):
    """Raised when an instruction has invalid operands."""


def _format_valid_values(values: tuple[str, ...]) -> str:
    return ", ".join(repr(value) for value in values)


def make_output_var(
    output: std.Var | None,
    ty: std.TyLike | None,
) -> std.Var:
    """Return an existing output var or allocate one from ``ty``."""
    if output is not None:
        if ty is not None:
            raise TypeError("exactly one of `ty` and `output` must be supplied")
        return output
    if ty is None:
        raise TypeError("exactly one of `ty` and `output` must be supplied")
    return std.Var(std.normalize_ty(ty), "")


def _collect_instruction_fields(obj: Instruction) -> std.FieldCollectionResult:
    fields = std.collect_dialect_fields(obj)
    ty: std.Ty | None = None
    outputs = obj.outputs()
    if len(outputs) == 1:
        output = outputs[0]
        ty = output.ty
    return std.FieldCollectionResult(
        args=list(fields.args),
        attrs=fields.attrs,
        outs=list(fields.outs),
        body=list(fields.body),
        ty=ty,
    )


@dc.py_class("tilus.Instruction", structural_eq="tree")
class Instruction(std.BaseVarDef, mnemonic="tilus.Instruction"):
    """Base class for Tilus instructions."""

    __ffi_dialect_field_collector__ = staticmethod(_collect_instruction_fields)

    def outputs(self) -> tuple[std.Var, ...]:
        """Return the variables defined by this instruction."""
        raise NotImplementedError(f"{type(self).__name__}.outputs() is not implemented")

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        outputs = self.outputs()
        if len(outputs) != 1 or not hasattr(self, "output"):
            raise TypeError(f"{type(self).__name__} does not define assignable output")
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        current_output = outputs[0]
        current_output.name = name[0]
        return (current_output,)


def validate_matching_lengths(instruction: Instruction, lhs_name: str, rhs_name: str) -> None:
    """Validate that two sequence fields have the same length when present."""
    lhs = getattr(instruction, lhs_name)
    rhs = getattr(instruction, rhs_name)
    if lhs is None or rhs is None:
        return
    if len(lhs) != len(rhs):
        raise ValueError(
            f"{type(instruction).__name__}.{lhs_name} and {rhs_name} must have "
            f"the same length, got {len(lhs)} and {len(rhs)}"
        )


def validate_string_attr(value: str | None, attr_name: str, valid_values: tuple[str, ...]) -> None:
    """Validate a string-valued instruction attribute."""
    if value is None:
        return
    if value not in valid_values:
        raise ValueError(
            f"{attr_name} must be one of {_format_valid_values(valid_values)}, got {value!r}"
        )


def validate_int_attr(value: int, attr_name: str, valid_values: tuple[int, ...]) -> int:
    """Validate and return an integer-valued instruction attribute."""
    int_value = _int_value(value)
    if int_value is None or int_value not in valid_values:
        raise ValueError(f"{attr_name} must be one of {valid_values}, got {value!r}")
    return int_value


def validate_nonnegative_int_attr(value: int, attr_name: str) -> int:
    """Validate and return a non-negative integer instruction attribute."""
    int_value = _int_value(value)
    if int_value is None or int_value < 0:
        raise ValueError(f"{attr_name} must be a non-negative integer constant")
    return int_value


def _int_value(value: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


__all__ = [
    "Instruction",
    "InstructionError",
    "make_output_var",
    "validate_int_attr",
    "validate_matching_lengths",
    "validate_nonnegative_int_attr",
    "validate_string_attr",
]
