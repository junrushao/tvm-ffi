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
"""Tests for Python-defined TVM-FFI types: ``@py_class`` decorator and low-level Field API."""

# ruff: noqa: D102
from __future__ import annotations

import itertools
import sys

import pytest
from tvm_ffi import core
from tvm_ffi.core import Object, TypeInfo
from tvm_ffi.dataclasses import Field, field, py_class
from tvm_ffi.registry import _add_class_attrs, _install_dataclass_dunders

_needs_310 = pytest.mark.skipif(sys.version_info < (3, 10), reason="X | Y syntax requires 3.10+")

# ---------------------------------------------------------------------------
# Unique type key generator (avoids collisions across tests)
# ---------------------------------------------------------------------------
_counter = itertools.count()


def _unique_key(base: str) -> str:
    return f"testing.py_class_dec.{base}_{next(_counter)}"


def _get_type_info(cls: type) -> TypeInfo:
    ret = cls.__tvm_ffi_type_info__  # ty: ignore[unresolved-attribute]
    assert isinstance(ret, TypeInfo), f"Expected TypeInfo, got {type(ret)}"
    return ret


# ---------------------------------------------------------------------------
# Low-level helpers for _make_type-based tests
# ---------------------------------------------------------------------------
_counter_ff = itertools.count()


def _unique_key_ff(base: str) -> str:
    """Return a globally unique type key for low-level field tests."""
    return f"testing.py_class.{base}_{next(_counter_ff)}"


def _make_type(
    name: str,
    fields: list[Field],
    *,
    parent: type = core.Object,
    eq: bool = False,
    unsafe_hash: bool = False,
    repr: bool = True,
) -> type:
    """Create, register, and fully set up a Python-defined TVM-FFI type.

    Returns the ready-to-use Python class.
    """
    type_key = _unique_key_ff(name)
    parent_info = core._type_cls_to_type_info(parent)
    assert parent_info is not None
    cls = type(name, (parent,), {"__slots__": ()})
    info = core._register_py_class(parent_info, type_key, cls)
    info._register_fields(fields)
    setattr(cls, "__tvm_ffi_type_info__", info)
    _add_class_attrs(cls, info)
    _install_dataclass_dunders(
        cls,
        init=True,
        repr=repr,
        eq=eq,
        order=False,
        unsafe_hash=unsafe_hash,
    )
    return cls


# ###########################################################################
#  1. Basic registration
# ###########################################################################
class TestBasicRegistration:
    """@py_class decorator with different calling conventions."""

    def test_bare_decorator(self) -> None:
        @py_class(_unique_key("Bare"))
        class Bare(Object):
            x: int

        info = _get_type_info(Bare)
        assert info is not None
        assert len(info.fields) == 1
        assert info.fields[0].name == "x"

    def test_decorator_with_options(self) -> None:
        @py_class(_unique_key("Opts"), eq=True)
        class Opts(Object):
            x: int

        assert hasattr(Opts, "__eq__")
        assert Opts(x=1) == Opts(x=1)

    def test_auto_type_key(self) -> None:
        @py_class(_unique_key("AutoKey"))
        class AutoKey(Object):
            x: int

        info = _get_type_info(AutoKey)
        assert info.type_key.startswith("testing.")

    def test_explicit_type_key(self) -> None:
        key = _unique_key("ExplicitKey")

        @py_class(key)
        class ExplicitKey(Object):
            x: int

        assert _get_type_info(ExplicitKey).type_key == key

    def test_empty_class(self) -> None:
        @py_class(_unique_key("Empty"))
        class Empty(Object):
            pass

        obj = Empty()
        assert obj is not None

    def test_isinstance_check(self) -> None:
        @py_class(_unique_key("InstCheck"))
        class InstCheck(Object):
            x: int

        obj = InstCheck(x=42)
        assert isinstance(obj, InstCheck)
        assert isinstance(obj, Object)


# ###########################################################################
#  2. Field parsing
# ###########################################################################
class TestFieldParsing:
    """Annotation-to-Field conversion."""

    def test_int_field(self) -> None:
        @py_class(_unique_key("IntFld"))
        class IntFld(Object):
            x: int

        obj = IntFld(x=42)
        assert obj.x == 42

    def test_float_field(self) -> None:
        @py_class(_unique_key("FltFld"))
        class FltFld(Object):
            x: float

        obj = FltFld(x=3.14)
        assert abs(obj.x - 3.14) < 1e-10

    def test_str_field(self) -> None:
        @py_class(_unique_key("StrFld"))
        class StrFld(Object):
            x: str

        obj = StrFld(x="hello")
        assert obj.x == "hello"

    def test_bool_field(self) -> None:
        @py_class(_unique_key("BoolFld"))
        class BoolFld(Object):
            x: bool

        obj = BoolFld(x=True)
        assert obj.x is True

    @_needs_310
    def test_optional_field(self) -> None:
        @py_class(_unique_key("OptFld"))
        class OptFld(Object):
            x: int | None

        obj = OptFld(x=42)
        assert obj.x == 42
        obj2 = OptFld(x=None)
        assert obj2.x is None

    def test_multiple_fields(self) -> None:
        @py_class(_unique_key("Multi"))
        class Multi(Object):
            a: int
            b: float
            c: str

        obj = Multi(a=1, b=2.0, c="three")
        assert obj.a == 1
        assert obj.b == 2.0
        assert obj.c == "three"


# ###########################################################################
#  3. Defaults
# ###########################################################################
class TestDefaults:
    """Default values and default_factory."""

    def test_bare_default(self) -> None:
        @py_class(_unique_key("BareDef"))
        class BareDef(Object):
            x: int
            y: int = 10

        obj = BareDef(x=1)
        assert obj.y == 10

    def test_field_default(self) -> None:
        @py_class(_unique_key("FldDef"))
        class FldDef(Object):
            x: int = field(default=42)

        obj = FldDef()
        assert obj.x == 42

    def test_field_default_factory(self) -> None:
        call_count = 0

        def make_default() -> int:
            nonlocal call_count
            call_count += 1
            return 99

        @py_class(_unique_key("FldFact"))
        class FldFact(Object):
            x: int = field(default_factory=make_default)

        obj1 = FldFact()
        assert obj1.x == 99
        obj2 = FldFact()
        assert obj2.x == 99
        assert call_count == 2

    def test_default_and_factory_mutually_exclusive(self) -> None:
        with pytest.raises(ValueError, match="cannot specify both"):
            field(default=1, default_factory=int)

    def test_non_callable_factory_rejected(self) -> None:
        with pytest.raises(TypeError, match="default_factory must be a callable"):
            field(default_factory=42)  # ty: ignore[invalid-argument-type]

    def test_required_before_optional(self) -> None:
        @py_class(_unique_key("ReqOpt"))
        class ReqOpt(Object):
            a: int
            b: int = 10

        obj = ReqOpt(1)
        assert obj.a == 1
        assert obj.b == 10


# ###########################################################################
