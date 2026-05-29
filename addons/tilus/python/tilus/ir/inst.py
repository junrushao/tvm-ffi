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

from typing import Any, ClassVar

from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi.structural import structural_equal

_PENDING_INSTRUCTION_TY: dict[int, std.Ty] = {}


class InstructionError(Exception):
    """Raised when an instruction has invalid operands."""


def _format_valid_values(values: tuple[str, ...]) -> str:
    return ", ".join(repr(value) for value in values)


def _collect_instruction_fields(obj: Any) -> std.FieldCollectionResult:
    fields = std.collect_dialect_fields(obj)
    ty: std.Ty | None = None
    output = getattr(obj, "output", None)
    if isinstance(output, std.Var):
        inferred_ty = (
            infer_instruction_output_ty(obj) if type(obj).OUTPUT_TY_INFERABLE_FROM_INPUTS else None
        )
        if inferred_ty is None or not structural_equal(output.ty, inferred_ty):
            ty = output.ty
    return std.FieldCollectionResult(
        args=list(fields.args),
        attrs=fields.attrs,
        var_def=list(fields.var_def),
        body=list(fields.body),
        ty=ty,
    )


@dc.py_class("tilus.Instruction", structural_eq="tree")
class Instruction(std.BaseVarDef, mnemonic="tilus.Instruction"):
    """Base class for Tilus instructions."""

    __ffi_dialect_field_collector__ = staticmethod(_collect_instruction_fields)

    EXPECTED_INPUTS: ClassVar[int | tuple[int, ...] | None] = None
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = ()
    NONNEGATIVE_INT_ATTRS: ClassVar[tuple[str, ...]] = ()
    OUTPUT_TY_INFERABLE_FROM_INPUTS: ClassVar[bool] = False
    TY_INPUT_INDICES: ClassVar[tuple[int, ...]] = ()
    _VALID_ATTR_CONSTANTS: ClassVar[dict[str, str]] = {
        "VALID_EVICTS": "evict",
        "VALID_L2_EVICTS": "l2_evict",
        "VALID_OPS": "op",
        "VALID_SCOPES": "scope",
        "VALID_SEMS": "sem",
        "VALID_SPACES": "space",
    }
    _VALID_INT_ATTR_CONSTANTS: ClassVar[dict[str, str]] = {
        "VALID_CTA_GROUPS": "cta_group",
    }

    inputs: list[std.Expr] = dc.field(default_factory=list, lang_kind="arg")
    output: std.Var | None = dc.field(
        default=None,
        lang_kind="var_def",
        structural_eq="def-recursive",
    )

    def __post_init__(self) -> None:
        self._validate_input_arity()
        self._validate_attr_lengths()
        self._validate_string_domains()
        self._validate_int_domains()
        self._validate_nonnegative_int_attrs()

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        if self.output is not None:
            output = std.Var(self.output.ty, name[0])
            object.__setattr__(self, "output", output)
            self.__post_init__()
            return (output,)
        explicit_ty = pop_instruction_ty_hint(self)
        ty = explicit_ty or infer_instruction_output_ty(self)
        if ty is None:
            raise TypeError("instruction assignment requires an inferable output type")
        output = std.Var(ty, name[0])
        object.__setattr__(self, "output", output)
        self.__post_init__()
        if explicit_ty is not None:
            validate_instruction_output_ty(self, explicit_ty)
        return (output,)

    def _validate_input_arity(self) -> None:
        expected = self.EXPECTED_INPUTS
        if expected is None:
            return

        actual = len(self.inputs)
        valid_counts = (expected,) if isinstance(expected, int) else expected
        if actual not in valid_counts:
            expected_text = (
                str(valid_counts[0])
                if len(valid_counts) == 1
                else "one of " + ", ".join(str(count) for count in valid_counts)
            )
            raise InstructionError(
                f"{type(self).__name__} expects {expected_text} input(s), got {actual}"
            )

    def _validate_attr_lengths(self) -> None:
        for lhs_name, rhs_name in self.MATCHING_ATTR_LENGTHS:
            lhs = getattr(self, lhs_name)
            rhs = getattr(self, rhs_name)
            if lhs is None or rhs is None:
                continue
            if len(lhs) != len(rhs):
                raise ValueError(
                    f"{type(self).__name__}.{lhs_name} and {rhs_name} must have "
                    f"the same length, got {len(lhs)} and {len(rhs)}"
                )

    def _validate_string_domains(self) -> None:
        cls = type(self)
        for constant_name, attr_name in self._VALID_ATTR_CONSTANTS.items():
            valid_values = getattr(cls, constant_name, None)
            if valid_values is None or not hasattr(self, attr_name):
                continue
            value = getattr(self, attr_name)
            if value is None:
                continue
            if value not in valid_values:
                raise ValueError(
                    f"{cls.__name__}.{attr_name} must be one of "
                    f"{_format_valid_values(valid_values)}, got {value!r}"
                )

    def _validate_int_domains(self) -> None:
        cls = type(self)
        for constant_name, attr_name in self._VALID_INT_ATTR_CONSTANTS.items():
            valid_values = getattr(cls, constant_name, None)
            if valid_values is None or not hasattr(self, attr_name):
                continue
            value = _int_value(getattr(self, attr_name))
            if value is None or value not in valid_values:
                raise ValueError(
                    f"{cls.__name__}.{attr_name} must be one of {valid_values}, "
                    f"got {getattr(self, attr_name)!r}"
                )

    def _validate_nonnegative_int_attrs(self) -> None:
        cls = type(self)
        for attr_name in self.NONNEGATIVE_INT_ATTRS:
            if not hasattr(self, attr_name):
                continue
            value = _int_value(getattr(self, attr_name))
            if value is None or value < 0:
                raise ValueError(
                    f"{cls.__name__}.{attr_name} must be a non-negative integer constant"
                )


def validate_instruction_ty_hint(instruction: Instruction, ty: Any) -> None:
    """Validate and record an explicit constructor output ``ty=`` hint."""
    ty = std.normalize_ty(ty)
    output_ty = infer_instruction_output_ty_from_ty_hint(type(instruction), ty)
    _validate_instruction_input_ty(instruction, ty)
    if instruction.output is None:
        _PENDING_INSTRUCTION_TY[id(instruction)] = output_ty
    else:
        validate_instruction_output_ty(instruction, ty)


def pop_instruction_ty_hint(instruction: Instruction) -> std.Ty | None:
    """Return and clear the pending ``ty=`` hint for an instruction RHS."""
    return _PENDING_INSTRUCTION_TY.pop(id(instruction), None)


def infer_instruction_output_ty(instruction: Instruction) -> std.Ty | None:
    """Infer an output type for unannotated instruction assignment."""
    for operand in instruction.inputs:
        if isinstance(operand, std.Expr):
            return operand.ty
    return None


def infer_instruction_input_ty(
    cls: type[Instruction],
    output_ty: Any,
) -> std.Ty:
    """Infer the typed input operand from an output ``ty=`` hint."""
    output_ty = std.normalize_ty(output_ty)
    converter = getattr(cls, "input_ty_from_output_ty", None)
    if converter is None:
        return output_ty
    return std.normalize_ty(converter(output_ty))


def infer_instruction_output_ty_from_ty_hint(
    cls: type[Instruction],
    ty: Any,
) -> std.Ty:
    """Infer the instruction output type from a constructor ``ty=`` hint."""
    ty = std.normalize_ty(ty)
    converter = getattr(cls, "output_ty_from_ty_hint", None)
    if converter is None:
        return ty
    return std.normalize_ty(converter(ty))


def validate_instruction_output_ty(instruction: Instruction, ty: Any) -> None:
    """Validate that an explicit output type hint matches ``output.ty``."""
    from .tensor import Tensor

    if instruction.output is None:
        return
    ty_hint = std.normalize_ty(ty)
    ty = infer_instruction_output_ty_from_ty_hint(type(instruction), ty)
    output_ty = instruction.output.ty
    if not structural_equal(ty, output_ty):
        if (
            isinstance(ty_hint, Tensor)
            and isinstance(output_ty, Tensor)
            and structural_equal(ty_hint.dtype, output_ty.dtype)
            and tuple(ty_hint.shape) == tuple(output_ty.shape)
        ):
            return
        raise TypeError(
            f"{type(instruction).__name__} `ty` keyword must match output dtype and shape"
        )


def _validate_instruction_input_ty(instruction: Instruction, ty: std.Ty) -> None:
    input_indices = type(instruction).TY_INPUT_INDICES
    if not input_indices:
        return
    from .tensor import Tensor

    input_ty = infer_instruction_input_ty(type(instruction), ty)
    input_index = input_indices[0]
    if input_index >= len(instruction.inputs):
        return
    operand = instruction.inputs[input_index]
    if not isinstance(operand, std.Var):
        raise TypeError(
            f"{type(instruction).__name__} `ty` keyword requires operand {input_index} to be std.Var"
        )
    if isinstance(operand.ty, Tensor) and isinstance(input_ty, Tensor):
        compatible = type(operand.ty) is type(input_ty) and structural_equal(
            operand.ty.dtype, input_ty.dtype
        )
    else:
        compatible = structural_equal(operand.ty, input_ty)
    if not compatible:
        raise TypeError(
            f"{type(instruction).__name__} `ty` keyword must match operand {input_index} type"
        )


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, std.IntImm):
        return int(value.value)
    return None


__all__ = ["Instruction", "InstructionError"]
