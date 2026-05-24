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


class InstructionError(Exception):
    """Raised when an instruction has invalid operands."""


def _format_valid_values(values: tuple[str, ...]) -> str:
    return ", ".join(repr(value) for value in values)


@dc.py_class("tilus.Instruction", structural_eq="tree")
class Instruction(std.Stmt, mnemonic="tilus.Instruction"):
    """Base class for Tilus instructions."""

    EXPECTED_INPUTS: ClassVar[int | tuple[int, ...] | None] = None
    MATCHING_ATTR_LENGTHS: ClassVar[tuple[tuple[str, str], ...]] = ()
    NONNEGATIVE_INT_ATTRS: ClassVar[tuple[str, ...]] = ()
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

    inputs: list[Any] = dc.field(default_factory=list, lang_kind="arg")
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


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, std.IntImm):
        return int(value.value)
    return None


__all__ = ["Instruction", "InstructionError"]
