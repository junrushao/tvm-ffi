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
"""Tests for Python-defined TVM-FFI type registration."""

from __future__ import annotations

import itertools
from typing import Any

import pytest
from tvm_ffi.core import (
    MISSING,
    TypeInfo,
    TypeSchema,
    _lookup_or_register_type_info_from_type_key,
    get_type_attr,
    py_class_append_field,
    py_class_make_type,
    register_type_attr,
)
from tvm_ffi.dataclasses import Field

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_counter = itertools.count(1)
_PARENT_SIZE = 24  # ffi.Object header: ref_count(8) + type_index(4) + pad(4) + deleter(8)


def _unique_type_key(prefix: str = "testing.PyObj") -> str:
    """Generate a unique type key to avoid conflicts between tests."""
    return f"{prefix}{next(_counter)}"


def _ffi_object_type_index() -> int:
    """Return the type index for ffi.Object."""
    return _lookup_or_register_type_info_from_type_key("ffi.Object").type_index


def _register_single_field(origin: str, **field_kwargs: Any) -> TypeInfo:
    """Register a type with one field and return the TypeInfo."""
    tkey = _unique_type_key()
    tindex = py_class_make_type(tkey, _ffi_object_type_index())
    f = Field("x", TypeSchema(origin), **field_kwargs)
    py_class_append_field(tindex, f)
    return _lookup_or_register_type_info_from_type_key(tkey)


# ---------------------------------------------------------------------------
# 1. Field class
# ---------------------------------------------------------------------------


def test_field_basic() -> None:
    """Field defaults: no default, all flags True, no doc."""
    f = Field("x", TypeSchema("int"))
    assert f.name == "x"
    assert f.ty.origin == "int"
    assert f.default is MISSING
    assert f.default_factory is MISSING
    assert f.init is True
    assert f.repr is True
    assert f.hash is True
    assert f.compare is True
    assert f.kw_only is False
    assert f.doc is None


def test_field_with_default() -> None:
    """Field accepts a default value."""
    f = Field("y", TypeSchema("int"), default=42)
    assert f.default == 42
    assert f.default_factory is MISSING


def test_field_with_default_factory() -> None:
    """Field accepts a default factory callable."""
    factory = list
    f = Field("z", TypeSchema("str"), default_factory=factory)
    assert f.default is MISSING
    assert f.default_factory is factory


def test_field_cannot_have_both_default_and_factory() -> None:
    """Raise ValueError when both default and default_factory are given."""
    with pytest.raises(ValueError, match="cannot specify both"):
        Field("bad", TypeSchema("int"), default=0, default_factory=list)


def test_field_with_flags() -> None:
    """Field stores custom flag values."""
    f = Field(
        "w",
        TypeSchema("float"),
        init=False,
        repr=False,
        hash=False,
        compare=False,
        kw_only=True,
        doc="A floating point field.",
    )
    assert f.init is False
    assert f.repr is False
    assert f.hash is False
    assert f.compare is False
    assert f.kw_only is True
    assert f.doc == "A floating point field."


# ---------------------------------------------------------------------------
# 2. py_class_make_type
# ---------------------------------------------------------------------------


def test_make_type_returns_positive_index() -> None:
    """Allocated type index is a positive integer."""
    tindex = py_class_make_type(_unique_type_key(), _ffi_object_type_index())
    assert isinstance(tindex, int)
    assert tindex > 0


def test_make_type_unique_indices() -> None:
    """Each new type gets a distinct type index."""
    idx1 = py_class_make_type(_unique_type_key(), _ffi_object_type_index())
    idx2 = py_class_make_type(_unique_type_key(), _ffi_object_type_index())
    assert idx1 != idx2


def test_make_type_lookup_by_key() -> None:
    """Allocated type can be looked up by type key."""
    tkey = _unique_type_key()
    tindex = py_class_make_type(tkey, _ffi_object_type_index())
    info = _lookup_or_register_type_info_from_type_key(tkey)
    assert info.type_index == tindex
    assert info.type_key == tkey


# ---------------------------------------------------------------------------
# 3. py_class_append_field — single field of each type
# ---------------------------------------------------------------------------

# (origin, expected_size) — all start at parent_size=24 which is 8-aligned
_SINGLE_FIELD_CASES = [
    ("int", 8),
    ("float", 8),
    ("bool", 8),
    ("str", 8),  # Object*
    ("Object", 8),  # Object*
    ("Tensor", 8),  # Object*
    ("dtype", 4),  # DLDataType
    ("Device", 8),  # DLDevice
    ("Any", 16),  # TVMFFIAny
]


@pytest.mark.parametrize(
    "origin, expected_size", _SINGLE_FIELD_CASES, ids=[c[0] for c in _SINGLE_FIELD_CASES]
)
def test_single_field_size(origin: str, expected_size: int) -> None:
    """Each field type produces the correct size and offset from parent."""
    info = _register_single_field(origin)
    assert len(info.fields) == 1
    assert info.fields[0].name == "x"
    assert info.fields[0].offset == _PARENT_SIZE
    assert info.fields[0].size == expected_size


@pytest.mark.parametrize(
    "origin, expected_size", _SINGLE_FIELD_CASES, ids=[c[0] for c in _SINGLE_FIELD_CASES]
)
def test_single_field_getter_setter(origin: str, expected_size: int) -> None:
    """Every registered field has non-None getter and setter."""
    info = _register_single_field(origin)
    assert info.fields[0].getter is not None
    assert info.fields[0].setter is not None


# ---------------------------------------------------------------------------
# 4. Multiple fields and offset computation (auto-offset)
# ---------------------------------------------------------------------------


def test_two_int_fields() -> None:
    """Two int fields are laid out contiguously via py_class_append_field."""
    tkey = _unique_type_key()
    tindex = py_class_make_type(tkey, _ffi_object_type_index())
    py_class_append_field(tindex, Field("x", TypeSchema("int")))
    py_class_append_field(tindex, Field("y", TypeSchema("int")))

    info = _lookup_or_register_type_info_from_type_key(tkey)
    assert len(info.fields) == 2
    assert info.fields[0].offset == 24
    assert info.fields[1].offset == 32


def test_int_dtype_int_layout() -> None:
    """Verify padding between int64 and DLDataType fields.

    Layout (parent = 24):
      offset 24: int64_t   (8 bytes, align 8)
      offset 32: DLDataType (4 bytes, align 2)
      offset 36: padding   (4 bytes for next 8-byte alignment)
      offset 40: int64_t   (8 bytes, align 8)
    """
    tkey = _unique_type_key()
    tindex = py_class_make_type(tkey, _ffi_object_type_index())
    py_class_append_field(tindex, Field("a", TypeSchema("int")))
    py_class_append_field(tindex, Field("dt", TypeSchema("dtype")))
    py_class_append_field(tindex, Field("b", TypeSchema("int")))

    info = _lookup_or_register_type_info_from_type_key(tkey)
    assert [f.offset for f in info.fields] == [24, 32, 40]


def test_mixed_field_types() -> None:
    """Register various field types and verify all names round-trip."""
    tkey = _unique_type_key()
    tindex = py_class_make_type(tkey, _ffi_object_type_index())
    origins = ["int", "float", "bool", "str"]
    for o in origins:
        py_class_append_field(tindex, Field(f"v_{o}", TypeSchema(o)))

    info = _lookup_or_register_type_info_from_type_key(tkey)
    assert [f.name for f in info.fields] == [f"v_{o}" for o in origins]


# ---------------------------------------------------------------------------
# 5. Field flags
# ---------------------------------------------------------------------------

_FLAG_CASES = [
    # (field_kwargs, attribute, expected)
    ({}, "frozen", False),  # writable by default
    ({"default": 99}, "c_has_default", True),
    ({}, "c_has_default", False),
    ({"default": 0, "init": False}, "c_init", False),
    ({"kw_only": True}, "c_kw_only", True),
]


@pytest.mark.parametrize(
    "field_kwargs, attr, expected",
    _FLAG_CASES,
    ids=["writable", "has_default", "no_default", "init_off", "kw_only"],
)
def test_field_flags(field_kwargs: dict[str, Any], attr: str, expected: object) -> None:
    """Flag bits round-trip through registration."""
    info = _register_single_field("int", **field_kwargs)
    assert getattr(info.fields[0], attr) is expected


# ---------------------------------------------------------------------------
# 6. Field metadata (type_schema JSON)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "origin, args, expected_origin",
    [
        ("int", (), "int"),
        ("float", (), "float"),
        ("bool", (), "bool"),
        ("str", (), "str"),
        ("Array", (TypeSchema("int"),), "Array"),
    ],
    ids=["int", "float", "bool", "str", "Array[int]"],
)
def test_field_metadata_type_schema(origin: str, args: tuple[()], expected_origin: str) -> None:
    """type_schema metadata round-trips through registration."""
    tkey = _unique_type_key()
    tindex = py_class_make_type(tkey, _ffi_object_type_index())
    py_class_append_field(tindex, Field("x", TypeSchema(origin, args)))

    info = _lookup_or_register_type_info_from_type_key(tkey)
    ts = TypeSchema.from_json_obj(info.fields[0].metadata["type_schema"])
    assert ts.origin == expected_origin
    if args:
        assert len(ts.args) == len(args)


def test_doc_string() -> None:
    """Field doc string round-trips through registration."""
    info = _register_single_field("int", doc="An integer field.")
    assert info.fields[0].doc == "An integer field."


# ---------------------------------------------------------------------------
# 7. register_type_attr / get_type_attr
# ---------------------------------------------------------------------------


def test_register_and_get_type_attr() -> None:
    """Arbitrary type attrs round-trip via register_type_attr/get_type_attr."""
    tkey = _unique_type_key()
    tindex = py_class_make_type(tkey, _ffi_object_type_index())
    register_type_attr(tindex, "my_custom_attr", 42)
    assert get_type_attr(tindex, "my_custom_attr") == 42


def test_register_ffi_total_size() -> None:
    """__ffi_total_size__ is stored as type attr and updates metadata."""
    tkey = _unique_type_key()
    tindex = py_class_make_type(tkey, _ffi_object_type_index())
    py_class_append_field(tindex, Field("x", TypeSchema("int")))
    py_class_append_field(tindex, Field("y", TypeSchema("float")))
    register_type_attr(tindex, "__ffi_total_size__", 40)
    assert get_type_attr(tindex, "__ffi_total_size__") == 40


def test_register_ffi_doc() -> None:
    """__ffi_doc__ is stored as type attr and updates metadata."""
    tkey = _unique_type_key()
    tindex = py_class_make_type(tkey, _ffi_object_type_index())
    register_type_attr(tindex, "__ffi_doc__", "A test type.")
    assert get_type_attr(tindex, "__ffi_doc__") == "A test type."


def test_get_type_attr_missing() -> None:
    """get_type_attr returns None for unregistered attributes."""
    tkey = _unique_type_key()
    tindex = py_class_make_type(tkey, _ffi_object_type_index())
    assert get_type_attr(tindex, "nonexistent") is None


# ---------------------------------------------------------------------------
# 8. Default values
# ---------------------------------------------------------------------------

_DEFAULT_CASES = [
    ("int", 42),
    ("str", "hello"),
    ("Object", None),
]


@pytest.mark.parametrize("origin, default", _DEFAULT_CASES, ids=[c[0] for c in _DEFAULT_CASES])
def test_default_value(origin: str, default: object) -> None:
    """Default values are stored and flagged for various types."""
    info = _register_single_field(origin, default=default)
    assert info.fields[0].c_has_default is True


# ---------------------------------------------------------------------------
# 9. Type hierarchy
# ---------------------------------------------------------------------------


def test_parent_type_info() -> None:
    """Python-defined type inheriting from ffi.Object has correct parent."""
    tkey = _unique_type_key()
    py_class_make_type(tkey, _ffi_object_type_index())
    info = _lookup_or_register_type_info_from_type_key(tkey)
    assert info.parent_type_info is not None
    assert info.parent_type_info.type_key == "ffi.Object"


def test_chained_inheritance() -> None:
    """Child type inheriting from a Python-defined parent has correct ancestry."""
    parent_key = _unique_type_key("testing.Parent")
    parent_idx = py_class_make_type(parent_key, _ffi_object_type_index())
    py_class_append_field(parent_idx, Field("p", TypeSchema("int")))
    register_type_attr(parent_idx, "__ffi_total_size__", 32)

    child_key = _unique_type_key("testing.Child")
    py_class_make_type(child_key, parent_idx)
    info = _lookup_or_register_type_info_from_type_key(child_key)
    assert info.parent_type_info is not None
    assert info.parent_type_info.type_key == parent_key
