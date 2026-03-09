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
"""Tests for registering TVM-FFI types from Python Field descriptors."""

# ruff: noqa: D102
from __future__ import annotations

import copy
import gc
import itertools
import math

import pytest
import tvm_ffi
from tvm_ffi import core
from tvm_ffi._ffi_api import DeepCopy, RecursiveEq, RecursiveHash, ReprPrint
from tvm_ffi.core import MISSING, TypeSchema
from tvm_ffi.dataclasses.field import Field
from tvm_ffi.registry import _add_class_attrs, _install_dataclass_dunders
from tvm_ffi.testing import TestObjectBase as _TestObjectBase

# ---------------------------------------------------------------------------
# Unique type key generator
# ---------------------------------------------------------------------------
_counter = itertools.count()


def _unique_key(base: str) -> str:
    """Return a globally unique type key for testing."""
    return f"testing.py_class.{base}_{next(_counter)}"


# ---------------------------------------------------------------------------
# Helper: create and register a type from Field descriptors
# ---------------------------------------------------------------------------
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
    type_key = _unique_key(name)
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
#  1. Registration
# ###########################################################################
class TestRegisterPyClass:
    """_register_py_class: type allocation, ancestors, pending fields."""

    def test_basic_registration(self) -> None:
        type_key = _unique_key("RegBasic")
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        cls = type("RegBasic", (core.Object,), {"__slots__": ()})
        info = core._register_py_class(parent_info, type_key, cls)
        assert info is not None
        assert info.type_key == type_key

    def test_type_index_allocated(self) -> None:
        type_key = _unique_key("RegIndex")
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        cls = type("RegIndex", (core.Object,), {"__slots__": ()})
        info = core._register_py_class(parent_info, type_key, cls)
        assert isinstance(info.type_index, int)
        assert info.type_index > 0

    def test_ancestors_include_parent(self) -> None:
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        type_key = _unique_key("RegAncestors")
        cls = type("RegAncestors", (core.Object,), {"__slots__": ()})
        info = core._register_py_class(parent_info, type_key, cls)
        assert parent_info.type_index in info.type_ancestors

    def test_parent_type_info_set(self) -> None:
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        type_key = _unique_key("RegParent")
        cls = type("RegParent", (core.Object,), {"__slots__": ()})
        info = core._register_py_class(parent_info, type_key, cls)
        assert info.parent_type_info is parent_info

    def test_initial_fields_none_and_methods_empty(self) -> None:
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        type_key = _unique_key("RegEmpty")
        cls = type("RegEmpty", (core.Object,), {"__slots__": ()})
        info = core._register_py_class(parent_info, type_key, cls)
        assert info.fields is None
        assert len(info.methods) == 0

    def test_two_registrations_different_indices(self) -> None:
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        cls1 = type("RegDiff1", (core.Object,), {"__slots__": ()})
        cls2 = type("RegDiff2", (core.Object,), {"__slots__": ()})
        info1 = core._register_py_class(parent_info, _unique_key("RegDiff1"), cls1)
        info2 = core._register_py_class(parent_info, _unique_key("RegDiff2"), cls2)
        assert info1.type_index != info2.type_index

    def test_fields_none_before_registration(self) -> None:
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        cls = type("Pending", (core.Object,), {"__slots__": ()})
        info = core._register_py_class(parent_info, _unique_key("Pending"), cls)
        assert info.fields is None

    def test_register_fields_is_instance_method(self) -> None:
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        cls = type("PendingM", (core.Object,), {"__slots__": ()})
        info = core._register_py_class(parent_info, _unique_key("PendingM"), cls)
        assert hasattr(info, "_register_fields")

    def test_duplicate_type_key_raises(self) -> None:
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        type_key = _unique_key("Dup")
        cls1 = type("Dup1", (core.Object,), {"__slots__": ()})
        core._register_py_class(parent_info, type_key, cls1)
        cls2 = type("Dup2", (core.Object,), {"__slots__": ()})
        with pytest.raises((RuntimeError, ValueError)):
            core._register_py_class(parent_info, type_key, cls2)

    def test_duplicate_type_key_preserves_original(self) -> None:
        """After rejected duplicate, original entry is intact."""
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        type_key = _unique_key("DupPreserve")
        cls1 = type("DupPreserve1", (core.Object,), {"__slots__": ()})
        info1 = core._register_py_class(parent_info, type_key, cls1)
        info1._register_fields([Field(name="x", ty=TypeSchema("int"))])
        setattr(cls1, "__tvm_ffi_type_info__", info1)
        _add_class_attrs(cls1, info1)

        cls2 = type("DupPreserve2", (core.Object,), {"__slots__": ()})
        with pytest.raises((RuntimeError, ValueError)):
            core._register_py_class(parent_info, type_key, cls2)

        reloaded = core._lookup_or_register_type_info_from_type_key(type_key)
        assert reloaded.type_cls is cls1
        assert [f.name for f in reloaded.fields] == ["x"]


# ###########################################################################
#  2. Field Registration
# ###########################################################################
class TestFieldRegistration:
    """_register_fields: field types, metadata, offsets."""

    def test_int_field_registered(self) -> None:
        cls = _make_type(
            "FldInt",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        info = getattr(cls, "__tvm_ffi_type_info__")
        assert len(info.fields) == 1
        assert info.fields[0].name == "x"

    def test_float_field_registered(self) -> None:
        cls = _make_type(
            "FldFloat",
            [Field(name="val", ty=TypeSchema("float"), default=0.0, default_factory=MISSING)],
        )
        info = getattr(cls, "__tvm_ffi_type_info__")
        assert info.fields[0].name == "val"

    def test_str_field_registered(self) -> None:
        cls = _make_type(
            "FldStr",
            [Field(name="s", ty=TypeSchema("str"), default="hello", default_factory=MISSING)],
        )
        info = getattr(cls, "__tvm_ffi_type_info__")
        assert info.fields[0].name == "s"

    def test_bool_field_registered(self) -> None:
        cls = _make_type(
            "FldBool",
            [Field(name="flag", ty=TypeSchema("bool"), default=False, default_factory=MISSING)],
        )
        info = getattr(cls, "__tvm_ffi_type_info__")
        assert info.fields[0].name == "flag"

    def test_multiple_fields_count(self) -> None:
        cls = _make_type(
            "FldMulti",
            [
                Field(name="a", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="b", ty=TypeSchema("float"), default=0.0, default_factory=MISSING),
                Field(name="c", ty=TypeSchema("str"), default="x", default_factory=MISSING),
            ],
        )
        info = getattr(cls, "__tvm_ffi_type_info__")
        assert len(info.fields) == 3
        assert [f.name for f in info.fields] == ["a", "b", "c"]

    def test_field_offsets_increasing(self) -> None:
        cls = _make_type(
            "FldOff",
            [
                Field(name="a", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="b", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING),
                Field(name="c", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING),
            ],
        )
        info = getattr(cls, "__tvm_ffi_type_info__")
        offsets = [f.offset for f in info.fields]
        for i in range(1, len(offsets)):
            assert offsets[i] > offsets[i - 1], f"Field offsets not increasing: {offsets}"

    def test_ffi_init_method_registered(self) -> None:
        cls = _make_type(
            "FldInit",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        info = getattr(cls, "__tvm_ffi_type_info__")
        assert "__ffi_init__" in [m.name for m in info.methods]

    def test_field_metadata_repr_flag(self) -> None:
        cls = _make_type(
            "FldReprMeta",
            [
                Field(
                    name="visible",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    repr=True,
                ),
                Field(
                    name="hidden",
                    ty=TypeSchema("int"),
                    default=0,
                    default_factory=MISSING,
                    repr=False,
                ),
            ],
        )
        info = getattr(cls, "__tvm_ffi_type_info__")
        assert len(info.fields) == 2


# ###########################################################################
#  3. Field Descriptor
# ###########################################################################
class TestFieldDescriptor:
    """Field class: validation, compare default, default_factory checks."""

    def test_compare_default_is_false(self) -> None:
        f = Field(name="x", ty=TypeSchema("int"))
        assert f.compare is False

    def test_default_and_factory_mutually_exclusive(self) -> None:
        with pytest.raises(ValueError):
            Field(name="x", ty=TypeSchema("int"), default=0, default_factory=lambda: 0)

    def test_factory_must_be_callable(self) -> None:
        with pytest.raises(TypeError, match="callable"):
            Field(name="x", ty=TypeSchema("int"), default_factory=0)

    def test_non_callable_factory_rejected(self) -> None:
        with pytest.raises(TypeError, match="callable"):
            Field(name="x", ty=TypeSchema("int"), default_factory="not_callable")


# ###########################################################################
#  4. Construction
# ###########################################################################
class TestConstruction:
    """__init__: positional/keyword args, defaults, factory defaults, errors."""

    def test_keyword_args(self) -> None:
        Cls = _make_type(
            "ConKw",
            [
                Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="y", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING),
            ],
        )
        obj = Cls(x=42, y=3.14)
        assert obj.x == 42
        assert obj.y == pytest.approx(3.14)

    def test_positional_args(self) -> None:
        Cls = _make_type(
            "ConPos",
            [
                Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="y", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING),
            ],
        )
        obj = Cls(10, 2.5)
        assert obj.x == 10
        assert obj.y == pytest.approx(2.5)

    def test_mixed_positional_and_keyword(self) -> None:
        Cls = _make_type(
            "ConMixed",
            [
                Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="y", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING),
            ],
        )
        obj = Cls(7, y=1.5)
        assert obj.x == 7
        assert obj.y == pytest.approx(1.5)

    def test_default_value_int(self) -> None:
        Cls = _make_type(
            "ConDefInt",
            [Field(name="x", ty=TypeSchema("int"), default=99, default_factory=MISSING)],
        )
        assert Cls().x == 99

    def test_default_value_float(self) -> None:
        Cls = _make_type(
            "ConDefFloat",
            [Field(name="x", ty=TypeSchema("float"), default=1.5, default_factory=MISSING)],
        )
        assert Cls().x == pytest.approx(1.5)

    def test_default_value_str(self) -> None:
        Cls = _make_type(
            "ConDefStr",
            [Field(name="s", ty=TypeSchema("str"), default="hello", default_factory=MISSING)],
        )
        assert Cls().s == "hello"

    def test_override_default(self) -> None:
        Cls = _make_type(
            "ConOverride",
            [Field(name="x", ty=TypeSchema("int"), default=0, default_factory=MISSING)],
        )
        assert Cls(x=42).x == 42

    def test_required_and_optional_together(self) -> None:
        Cls = _make_type(
            "ConReqOpt",
            [
                Field(
                    name="required", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING
                ),
                Field(
                    name="optional", ty=TypeSchema("float"), default=0.0, default_factory=MISSING
                ),
            ],
        )
        obj = Cls(required=5)
        assert obj.required == 5
        assert obj.optional == pytest.approx(0.0)

    def test_missing_required_raises(self) -> None:
        Cls = _make_type(
            "ConMissing",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        with pytest.raises(TypeError):
            Cls()

    def test_extra_kwarg_raises(self) -> None:
        Cls = _make_type(
            "ConExtra",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        with pytest.raises(TypeError):
            Cls(x=1, bogus=2)

    def test_str_field_construction(self) -> None:
        Cls = _make_type(
            "ConStr",
            [Field(name="name", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        assert Cls(name="world").name == "world"

    def test_bool_field_construction(self) -> None:
        Cls = _make_type(
            "ConBool",
            [Field(name="flag", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING)],
        )
        assert Cls(flag=True).flag is True
        assert Cls(flag=False).flag is False

    def test_kw_only_field(self) -> None:
        Cls = _make_type(
            "ConKwOnly",
            [
                Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(
                    name="y",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    kw_only=True,
                ),
            ],
        )
        obj = Cls(1, y=2)
        assert obj.x == 1
        assert obj.y == 2

    def test_kw_only_rejects_positional(self) -> None:
        Cls = _make_type(
            "ConKwOnlyReject",
            [
                Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(
                    name="y",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    kw_only=True,
                ),
            ],
        )
        with pytest.raises(TypeError):
            Cls(1, 2)

    def test_isinstance_check(self) -> None:
        Cls = _make_type(
            "ConIsInstance",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(x=1)
        assert isinstance(obj, Cls)
        assert isinstance(obj, core.Object)


# ###########################################################################
#  5. Getter / Setter
# ###########################################################################
class TestGetterSetter:
    """Field access: get/set POD, str, bool, mutation isolation."""

    def test_get_int(self) -> None:
        Cls = _make_type(
            "GSInt",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        assert Cls(x=42).x == 42

    def test_set_int(self) -> None:
        Cls = _make_type(
            "GSSetInt",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(x=1)
        obj.x = 100
        assert obj.x == 100

    def test_get_float(self) -> None:
        Cls = _make_type(
            "GSFloat",
            [Field(name="val", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING)],
        )
        assert Cls(val=3.14).val == pytest.approx(3.14)

    def test_set_float(self) -> None:
        Cls = _make_type(
            "GSSetFloat",
            [Field(name="val", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(val=1.0)
        obj.val = 2.718
        assert obj.val == pytest.approx(2.718)

    def test_get_str(self) -> None:
        Cls = _make_type(
            "GSStr",
            [Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        assert Cls(s="hello").s == "hello"

    def test_set_str(self) -> None:
        Cls = _make_type(
            "GSSetStr",
            [Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(s="hello")
        obj.s = "world"
        assert obj.s == "world"

    def test_get_bool(self) -> None:
        Cls = _make_type(
            "GSBool",
            [Field(name="flag", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING)],
        )
        assert Cls(flag=True).flag is True

    def test_set_bool(self) -> None:
        Cls = _make_type(
            "GSSetBool",
            [Field(name="flag", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(flag=True)
        obj.flag = False
        assert obj.flag is False

    def test_mutation_isolated(self) -> None:
        Cls = _make_type(
            "GSIsolate",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        a = Cls(x=1)
        b = Cls(x=1)
        a.x = 99
        assert a.x == 99
        assert b.x == 1

    def test_multiple_fields_mutation(self) -> None:
        Cls = _make_type(
            "GSMultiMut",
            [
                Field(name="a", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="b", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING),
                Field(name="c", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING),
            ],
        )
        obj = Cls(a=1, b=2.0, c="x")
        obj.a = 10
        obj.b = 20.0
        obj.c = "y"
        assert obj.a == 10
        assert obj.b == pytest.approx(20.0)
        assert obj.c == "y"

    def test_set_array_field(self) -> None:
        Cls = _make_type(
            "GSSetArr",
            [
                Field(
                    name="arr",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(arr=[1])
        obj.arr = tvm_ffi.Array([4, 5, 6])
        assert len(obj.arr) == 3
        assert obj.arr[0] == 4


# ###########################################################################
#  6. ObjectRef Fields
# ###########################################################################
class TestObjectRefFields:
    """Fields holding ObjectRef types: Array, custom objects."""

    def test_array_field(self) -> None:
        Cls = _make_type(
            "ObjArr",
            [
                Field(
                    name="arr",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(arr=tvm_ffi.Array([1, 2, 3]))
        assert len(obj.arr) == 3
        assert obj.arr[0] == 1
        assert obj.arr[2] == 3

    def test_array_field_from_list(self) -> None:
        Cls = _make_type(
            "ObjArrList",
            [
                Field(
                    name="arr",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(arr=[10, 20, 30])
        assert len(obj.arr) == 3
        assert obj.arr[1] == 20

    def test_nested_object_field(self) -> None:
        Inner = _make_type(
            "ObjInner",
            [Field(name="val", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        inner_info = getattr(Inner, "__tvm_ffi_type_info__")
        inner_schema = TypeSchema(inner_info.type_key, origin_type_index=inner_info.type_index)
        Outer = _make_type(
            "ObjOuter",
            [Field(name="child", ty=inner_schema, default=MISSING, default_factory=MISSING)],
        )
        assert Outer(child=Inner(val=42)).child.val == 42


# ###########################################################################
#  7. Optional Fields
# ###########################################################################
class TestOptionalFields:
    """Optional/Union fields: None and non-None values."""

    def test_optional_int_with_value(self) -> None:
        Cls = _make_type(
            "OptIntV",
            [
                Field(
                    name="x",
                    ty=TypeSchema("Optional", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        assert Cls(x=42).x == 42

    def test_optional_int_with_none(self) -> None:
        Cls = _make_type(
            "OptIntN",
            [
                Field(
                    name="x",
                    ty=TypeSchema("Optional", (TypeSchema("int"),)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        assert Cls().x is None

    def test_optional_str_with_value(self) -> None:
        Cls = _make_type(
            "OptStrV",
            [
                Field(
                    name="s",
                    ty=TypeSchema("Optional", (TypeSchema("str"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        assert Cls(s="hello").s == "hello"

    def test_optional_str_with_none(self) -> None:
        Cls = _make_type(
            "OptStrN",
            [
                Field(
                    name="s",
                    ty=TypeSchema("Optional", (TypeSchema("str"),)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        assert Cls().s is None

    def test_optional_set_to_none(self) -> None:
        Cls = _make_type(
            "OptSet",
            [
                Field(
                    name="x",
                    ty=TypeSchema("Optional", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(x=42)
        obj.x = None
        assert obj.x is None

    def test_optional_set_back_to_value(self) -> None:
        Cls = _make_type(
            "OptBack",
            [
                Field(
                    name="x",
                    ty=TypeSchema("Optional", (TypeSchema("int"),)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls()
        obj.x = 99
        assert obj.x == 99

    def test_all_optional_fields_default_none(self) -> None:
        Cls = _make_type(
            "AllOpt",
            [
                Field(
                    name="a",
                    ty=TypeSchema("Optional", (TypeSchema("int"),)),
                    default=None,
                    default_factory=MISSING,
                ),
                Field(
                    name="b",
                    ty=TypeSchema("Optional", (TypeSchema("str"),)),
                    default=None,
                    default_factory=MISSING,
                ),
                Field(
                    name="c",
                    ty=TypeSchema("Optional", (TypeSchema("float"),)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls()
        assert obj.a is None
        assert obj.b is None
        assert obj.c is None
        obj.a = 42
        assert obj.a == 42
        obj.b = "hello"
        assert obj.b == "hello"

    def test_optional_object_none_and_back(self) -> None:
        Cls = _make_type(
            "OptObjRound",
            [
                Field(
                    name="ref",
                    ty=TypeSchema("Optional", (TypeSchema("Object"),)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls()
        assert obj.ref is None
        obj.ref = tvm_ffi.Array([1])
        assert len(obj.ref) == 1
        obj.ref = None
        assert obj.ref is None

    def test_union_int_str(self) -> None:
        """Union[int, str] field should accept both types."""
        Cls = _make_type(
            "UnionIntStr",
            [
                Field(
                    name="val",
                    ty=TypeSchema("Union", (TypeSchema("int"), TypeSchema("str"))),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(val=42)
        assert obj.val == 42
        obj.val = "hello"
        assert obj.val == "hello"

    def test_union_int_str_rejects_float(self) -> None:
        """Union[int, str] should reject float (not in union)."""
        Cls = _make_type(
            "UnionReject",
            [
                Field(
                    name="val",
                    ty=TypeSchema("Union", (TypeSchema("int"), TypeSchema("str"))),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(val=1)
        with pytest.raises((TypeError, RuntimeError)):
            obj.val = 3.14

    def test_optional_union(self) -> None:
        """Optional[Union[int, str]] should accept None, int, and str."""
        Cls = _make_type(
            "OptUnion",
            [
                Field(
                    name="val",
                    ty=TypeSchema(
                        "Optional",
                        (TypeSchema("Union", (TypeSchema("int"), TypeSchema("str"))),),
                    ),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls()
        assert obj.val is None
        obj.val = 42
        assert obj.val == 42
        obj.val = "hi"
        assert obj.val == "hi"
        obj.val = None
        assert obj.val is None


# ###########################################################################
#  8. Any Fields
# ###########################################################################
class TestAnyField:
    """Fields with TypeSchema('Any'): hold any value type."""

    def test_any_holds_int(self) -> None:
        Cls = _make_type(
            "AnyI",
            [Field(name="val", ty=TypeSchema("Any"), default=None, default_factory=MISSING)],
        )
        assert Cls(val=42).val == 42

    def test_any_holds_str(self) -> None:
        Cls = _make_type(
            "AnyS",
            [Field(name="val", ty=TypeSchema("Any"), default=None, default_factory=MISSING)],
        )
        assert Cls(val="hello").val == "hello"

    def test_any_holds_none(self) -> None:
        Cls = _make_type(
            "AnyN",
            [Field(name="val", ty=TypeSchema("Any"), default=None, default_factory=MISSING)],
        )
        assert Cls().val is None

    def test_any_holds_object(self) -> None:
        Cls = _make_type(
            "AnyObj",
            [Field(name="val", ty=TypeSchema("Any"), default=None, default_factory=MISSING)],
        )
        arr = tvm_ffi.Array([1, 2])
        assert len(Cls(val=arr).val) == 2

    def test_any_type_change(self) -> None:
        Cls = _make_type(
            "AnyChg",
            [Field(name="val", ty=TypeSchema("Any"), default=None, default_factory=MISSING)],
        )
        obj = Cls()
        obj.val = 42
        assert obj.val == 42
        obj.val = "hello"
        assert obj.val == "hello"
        obj.val = None
        assert obj.val is None
        obj.val = tvm_ffi.Array([1])
        assert len(obj.val) == 1


# ###########################################################################
#  9. Default Factory
# ###########################################################################
class TestDefaultFactory:
    """default_factory support: fresh instances, override, various types."""

    def test_factory_produces_fresh_instances(self) -> None:
        Cls = _make_type(
            "DFFresh",
            [
                Field(
                    name="data",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default_factory=lambda: tvm_ffi.Array([]),
                ),
            ],
        )
        a = Cls()
        b = Cls()
        assert not a.data.same_as(b.data)

    def test_factory_with_content(self) -> None:
        Cls = _make_type(
            "DFContent",
            [
                Field(
                    name="items",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default_factory=lambda: tvm_ffi.Array([1, 2, 3]),
                ),
            ],
        )
        obj = Cls()
        assert len(obj.items) == 3
        assert obj.items[0] == 1

    def test_factory_override(self) -> None:
        Cls = _make_type(
            "DFOverride",
            [Field(name="x", ty=TypeSchema("int"), default_factory=lambda: 42)],
        )
        assert Cls(x=99).x == 99

    def test_factory_str(self) -> None:
        Cls = _make_type(
            "DFStr",
            [Field(name="s", ty=TypeSchema("str"), default_factory=lambda: "generated")],
        )
        assert Cls().s == "generated"


# ###########################################################################
#  10. Repr
# ###########################################################################
class TestRepr:
    """Repr: includes field values, repr=False exclusion, various types."""

    def test_repr_includes_fields(self) -> None:
        Cls = _make_type(
            "ReprBasic",
            [
                Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="y", ty=TypeSchema("float"), default=0.0, default_factory=MISSING),
            ],
        )
        r = ReprPrint(Cls(x=42, y=3.14))
        assert "x=42" in r
        assert "y=3.14" in r

    def test_repr_str_field(self) -> None:
        Cls = _make_type(
            "ReprStr",
            [Field(name="name", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        assert '"hello"' in ReprPrint(Cls(name="hello"))

    def test_repr_bool_field(self) -> None:
        Cls = _make_type(
            "ReprBool",
            [Field(name="flag", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING)],
        )
        assert "flag=True" in ReprPrint(Cls(flag=True))

    def test_repr_false_excluded(self) -> None:
        Cls = _make_type(
            "ReprExcl",
            [
                Field(
                    name="visible", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING
                ),
                Field(
                    name="hidden",
                    ty=TypeSchema("int"),
                    default=0,
                    default_factory=MISSING,
                    repr=False,
                ),
            ],
        )
        r = ReprPrint(Cls(visible=42))
        assert "visible=42" in r
        assert "hidden" not in r

    def test_python_repr_delegates(self) -> None:
        Cls = _make_type(
            "ReprDeleg",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        assert "x=7" in repr(Cls(x=7))

    def test_repr_contains_type_key(self) -> None:
        Cls = _make_type(
            "ReprKey",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        info = getattr(Cls, "__tvm_ffi_type_info__")
        assert info.type_key in ReprPrint(Cls(x=1))

    def test_repr_optional_none(self) -> None:
        Cls = _make_type(
            "ReprOptNone",
            [
                Field(
                    name="x",
                    ty=TypeSchema("Optional", (TypeSchema("int"),)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        r = ReprPrint(Cls())
        assert isinstance(r, str)

    def test_repr_array_field(self) -> None:
        Cls = _make_type(
            "ReprArr",
            [
                Field(
                    name="items",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        r = ReprPrint(Cls(items=[1, 2, 3]))
        assert isinstance(r, str)


# ###########################################################################
#  11. Hash
# ###########################################################################
class TestHash:
    """Hash: equal objects same hash, hash=False ignored."""

    def test_equal_objects_same_hash(self) -> None:
        Cls = _make_type(
            "HashEq",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
                Field(
                    name="y",
                    ty=TypeSchema("float"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
            unsafe_hash=True,
        )
        assert RecursiveHash(Cls(x=1, y=2.0)) == RecursiveHash(Cls(x=1, y=2.0))

    def test_different_objects_different_hash(self) -> None:
        Cls = _make_type(
            "HashDiff",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
            unsafe_hash=True,
        )
        assert RecursiveHash(Cls(x=1)) != RecursiveHash(Cls(x=2))

    def test_hash_false_field_ignored(self) -> None:
        Cls = _make_type(
            "HashIgn",
            [
                Field(
                    name="key",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
                Field(
                    name="ignored",
                    ty=TypeSchema("int"),
                    default=0,
                    default_factory=MISSING,
                    hash=False,
                ),
            ],
            eq=True,
            unsafe_hash=True,
        )
        assert RecursiveHash(Cls(key=42, ignored=100)) == RecursiveHash(Cls(key=42, ignored=999))

    def test_hash_dunder_installed(self) -> None:
        Cls = _make_type(
            "HashDunder",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            eq=True,
            unsafe_hash=True,
        )
        assert isinstance(hash(Cls(x=42)), int)

    def test_usable_as_dict_key(self) -> None:
        Cls = _make_type(
            "HashDict",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
            unsafe_hash=True,
        )
        assert {Cls(x=1): "value"}[Cls(x=1)] == "value"

    def test_usable_in_set(self) -> None:
        Cls = _make_type(
            "HashSet",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
            unsafe_hash=True,
        )
        assert len({Cls(x=1), Cls(x=1), Cls(x=2)}) == 2


# ###########################################################################
#  12. Equality
# ###########################################################################
class TestEquality:
    """Equality: structural compare, compare=False exclusion."""

    def test_equal_objects(self) -> None:
        Cls = _make_type(
            "EqEqual",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
                Field(
                    name="y",
                    ty=TypeSchema("float"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
        )
        assert Cls(x=1, y=2.0) == Cls(x=1, y=2.0)

    def test_different_objects(self) -> None:
        Cls = _make_type(
            "EqDiff",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
        )
        assert Cls(x=1) != Cls(x=2)

    def test_compare_false_field_ignored(self) -> None:
        Cls = _make_type(
            "EqIgn",
            [
                Field(
                    name="key",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
                Field(
                    name="ignored",
                    ty=TypeSchema("int"),
                    default=0,
                    default_factory=MISSING,
                    compare=False,
                ),
            ],
            eq=True,
        )
        assert RecursiveEq(Cls(key=42, ignored=100), Cls(key=42, ignored=999))

    def test_compare_off_excludes_from_eq(self) -> None:
        """Fields with compare=False (default) are ignored by RecursiveEq."""
        Cls = _make_type(
            "CmpOff",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            eq=True,
        )
        assert RecursiveEq(Cls(x=1), Cls(x=2))

    def test_compare_true_includes_in_eq(self) -> None:
        Cls = _make_type(
            "CmpOn",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
        )
        assert not RecursiveEq(Cls(x=1), Cls(x=2))

    def test_eq_reflexive(self) -> None:
        Cls = _make_type(
            "EqRefl",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
        )
        a = Cls(x=42)
        assert a == a  # noqa: PLR0124

    def test_eq_symmetric(self) -> None:
        Cls = _make_type(
            "EqSym",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
        )
        a, b = Cls(x=1), Cls(x=1)
        assert a == b
        assert b == a

    def test_eq_with_str_field(self) -> None:
        Cls = _make_type(
            "EqStr",
            [
                Field(
                    name="s",
                    ty=TypeSchema("str"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
        )
        assert RecursiveEq(Cls(s="hello"), Cls(s="hello"))
        assert not RecursiveEq(Cls(s="hello"), Cls(s="world"))

    def test_eq_hash_consistency(self) -> None:
        Cls = _make_type(
            "EqHashCon",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
                Field(
                    name="y",
                    ty=TypeSchema("float"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
            unsafe_hash=True,
        )
        a, b = Cls(x=1, y=2.0), Cls(x=1, y=2.0)
        assert RecursiveEq(a, b)
        assert RecursiveHash(a) == RecursiveHash(b)


# ###########################################################################
#  13. Edge Cases
# ###########################################################################
class TestEdgeCases:
    """Empty class, zero/negative/large values, init=False, mixed types."""

    def test_empty_class_no_fields(self) -> None:
        Cls = _make_type("EdgeEmpty", [])
        obj = Cls()
        assert isinstance(obj, core.Object)
        assert isinstance(obj, Cls)

    def test_empty_class_repr(self) -> None:
        Cls = _make_type("EdgeEmptyRepr", [])
        info = getattr(Cls, "__tvm_ffi_type_info__")
        assert info.type_key in ReprPrint(Cls())

    def test_bool_true_and_false(self) -> None:
        Cls = _make_type(
            "EdgeBool",
            [Field(name="flag", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING)],
        )
        assert Cls(flag=True).flag is True
        assert Cls(flag=False).flag is False

    def test_bool_default_false(self) -> None:
        Cls = _make_type(
            "EdgeBoolDef",
            [Field(name="flag", ty=TypeSchema("bool"), default=False, default_factory=MISSING)],
        )
        assert Cls().flag is False

    def test_multiple_types_together(self) -> None:
        Cls = _make_type(
            "EdgeMulti",
            [
                Field(
                    name="i",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
                Field(name="f", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING),
                Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING),
                Field(name="b", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING),
            ],
        )
        obj = Cls(i=42, f=3.14, s="test", b=True)
        assert obj.i == 42
        assert obj.f == pytest.approx(3.14)
        assert obj.s == "test"
        assert obj.b is True

    def test_pod_and_objectref_mixed(self) -> None:
        Cls = _make_type(
            "EdgeMixed",
            [
                Field(name="count", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(
                    name="items",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
                Field(name="label", ty=TypeSchema("str"), default="", default_factory=MISSING),
            ],
        )
        obj = Cls(count=3, items=[1, 2, 3])
        assert obj.count == 3
        assert len(obj.items) == 3
        assert obj.label == ""

    def test_multiple_types_with_defaults(self) -> None:
        Cls = _make_type(
            "EdgeMultiDef",
            [
                Field(name="i", ty=TypeSchema("int"), default=0, default_factory=MISSING),
                Field(name="f", ty=TypeSchema("float"), default=1.0, default_factory=MISSING),
                Field(name="s", ty=TypeSchema("str"), default="default", default_factory=MISSING),
                Field(name="b", ty=TypeSchema("bool"), default=True, default_factory=MISSING),
            ],
        )
        obj = Cls()
        assert obj.i == 0
        assert obj.f == pytest.approx(1.0)
        assert obj.s == "default"
        assert obj.b is True

    def test_zero_values(self) -> None:
        Cls = _make_type(
            "EdgeZero",
            [
                Field(name="i", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="f", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING),
            ],
        )
        obj = Cls(i=0, f=0.0)
        assert obj.i == 0
        assert obj.f == 0.0

    def test_negative_values(self) -> None:
        Cls = _make_type(
            "EdgeNeg",
            [
                Field(name="i", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="f", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING),
            ],
        )
        obj = Cls(i=-42, f=-3.14)
        assert obj.i == -42
        assert obj.f == pytest.approx(-3.14)

    def test_large_int(self) -> None:
        Cls = _make_type(
            "EdgeLargeInt",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        large = 2**62
        assert Cls(x=large).x == large

    def test_empty_string_field(self) -> None:
        Cls = _make_type(
            "EdgeEmptyStr",
            [Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        assert Cls(s="").s == ""

    def test_long_string_field(self) -> None:
        Cls = _make_type(
            "EdgeLongStr",
            [Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        long_str = "a" * 1000
        assert Cls(s=long_str).s == long_str

    def test_equality_empty_class(self) -> None:
        Cls = _make_type("EdgeEmptyEq", [], eq=True, unsafe_hash=True)
        assert RecursiveEq(Cls(), Cls())
        assert RecursiveHash(Cls()) == RecursiveHash(Cls())

    def test_init_false_field_excluded_from_init(self) -> None:
        Cls = _make_type(
            "EdgeInitFalse",
            [
                Field(
                    name="visible", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING
                ),
                Field(
                    name="internal",
                    ty=TypeSchema("int"),
                    default=0,
                    default_factory=MISSING,
                    init=False,
                ),
            ],
        )
        obj = Cls(visible=42)
        assert obj.visible == 42
        assert obj.internal == 0

    def test_init_false_field_rejected_as_kwarg(self) -> None:
        Cls = _make_type(
            "EdgeInitFalseReject",
            [
                Field(
                    name="visible", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING
                ),
                Field(
                    name="internal",
                    ty=TypeSchema("int"),
                    default=0,
                    default_factory=MISSING,
                    init=False,
                ),
            ],
        )
        with pytest.raises(TypeError):
            Cls(visible=1, internal=2)

    def test_init_false_field_writable(self) -> None:
        Cls = _make_type(
            "EdgeInitFalseWrite",
            [
                Field(
                    name="visible", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING
                ),
                Field(
                    name="internal",
                    ty=TypeSchema("int"),
                    default=0,
                    default_factory=MISSING,
                    init=False,
                ),
            ],
        )
        obj = Cls(visible=1)
        obj.internal = 99
        assert obj.internal == 99


# ###########################################################################
#  14. Inheritance (Python-defined parent)
# ###########################################################################
class TestInheritance:
    """Python-defined parent → child: field offsets, aliasing."""

    def test_child_fields_after_parent(self) -> None:
        Parent = _make_type(
            "InhParent",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        Child = _make_type(
            "InhChild",
            [Field(name="y", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=Parent,
        )
        obj = Child(1, 2)
        assert obj.x == 1
        assert obj.y == 2

    def test_child_field_offsets_non_overlapping(self) -> None:
        Parent = _make_type(
            "InhParentOff",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        Child = _make_type(
            "InhChildOff",
            [Field(name="y", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=Parent,
        )
        p_info = getattr(Parent, "__tvm_ffi_type_info__")
        c_info = getattr(Child, "__tvm_ffi_type_info__")
        parent_end = p_info.fields[0].offset + p_info.fields[0].size
        assert c_info.fields[0].offset >= parent_end

    def test_mutation_no_aliasing(self) -> None:
        Parent = _make_type(
            "InhParentAlias",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        Child = _make_type(
            "InhChildAlias",
            [Field(name="y", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=Parent,
        )
        obj = Child(1, 2)
        obj.y = 9
        assert obj.x == 1
        assert obj.y == 9

    def test_three_level_inheritance(self) -> None:
        """Object → A → B → C: all fields accessible and non-overlapping."""
        A = _make_type(
            "InhA",
            [Field(name="a", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        B = _make_type(
            "InhB",
            [Field(name="b", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
            parent=A,
        )
        C = _make_type(
            "InhC",
            [Field(name="c", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING)],
            parent=B,
        )
        obj = C(a=1, b="two", c=3.0)
        assert obj.a == 1
        assert obj.b == "two"
        assert obj.c == pytest.approx(3.0)

    def test_three_level_offsets_non_overlapping(self) -> None:
        A = _make_type(
            "InhAOff",
            [Field(name="a", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        B = _make_type(
            "InhBOff",
            [Field(name="b", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=A,
        )
        C = _make_type(
            "InhCOff",
            [Field(name="c", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=B,
        )
        a_info = getattr(A, "__tvm_ffi_type_info__")
        b_info = getattr(B, "__tvm_ffi_type_info__")
        c_info = getattr(C, "__tvm_ffi_type_info__")
        a_end = a_info.fields[0].offset + a_info.fields[0].size
        b_end = b_info.fields[0].offset + b_info.fields[0].size
        assert b_info.fields[0].offset >= a_end
        assert c_info.fields[0].offset >= b_end

    def test_three_level_mutation_no_aliasing(self) -> None:
        A = _make_type(
            "InhAMut",
            [Field(name="a", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        B = _make_type(
            "InhBMut",
            [Field(name="b", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=A,
        )
        C = _make_type(
            "InhCMut",
            [Field(name="c", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=B,
        )
        obj = C(a=1, b=2, c=3)
        obj.c = 99
        assert obj.a == 1
        assert obj.b == 2
        assert obj.c == 99
        obj.a = 77
        assert obj.a == 77
        assert obj.b == 2
        assert obj.c == 99

    def test_three_level_isinstance(self) -> None:
        A = _make_type(
            "InhAIs",
            [Field(name="a", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        B = _make_type(
            "InhBIs",
            [Field(name="b", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=A,
        )
        C = _make_type(
            "InhCIs",
            [Field(name="c", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=B,
        )
        obj = C(a=1, b=2, c=3)
        assert isinstance(obj, C)
        assert isinstance(obj, B)
        assert isinstance(obj, A)
        assert isinstance(obj, core.Object)

    def test_three_level_deep_copy(self) -> None:
        A = _make_type(
            "InhACopy",
            [Field(name="a", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        B = _make_type(
            "InhBCopy",
            [Field(name="b", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=A,
        )
        C = _make_type(
            "InhCCopy",
            [Field(name="c", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=B,
        )
        obj = C(a=1, b=2, c=3)
        obj_copy = DeepCopy(obj)
        assert not obj.same_as(obj_copy)
        assert obj_copy.a == 1
        assert obj_copy.b == 2
        assert obj_copy.c == 3
        obj_copy.c = 99
        assert obj.c == 3


# ###########################################################################
#  15. Mutual / Self References
# ###########################################################################
class TestMutualReferences:
    """Mutual and self-referential type fields via two-phase registration."""

    def _register_bare(self, name: str) -> tuple[type, core.TypeInfo]:
        """Register a type with no fields (phase 1 of two-phase)."""
        parent_info = core._type_cls_to_type_info(core.Object)
        assert parent_info is not None
        cls = type(name, (core.Object,), {"__slots__": ()})
        info = core._register_py_class(parent_info, _unique_key(name), cls)
        return cls, info

    def _finalize(self, cls: type, info: core.TypeInfo, fields: list[Field]) -> None:
        """Register fields and install class attrs (phase 2 of two-phase)."""
        info._register_fields(fields)
        setattr(cls, "__tvm_ffi_type_info__", info)
        _add_class_attrs(cls, info)
        _install_dataclass_dunders(
            cls,
            init=True,
            repr=True,
            eq=False,
            order=False,
            unsafe_hash=False,
        )

    def test_mutual_references(self) -> None:
        """Foo has Optional[Bar], Bar has Optional[Foo]."""
        Foo, foo_info = self._register_bare("MutFoo")
        Bar, bar_info = self._register_bare("MutBar")
        foo_schema = TypeSchema(foo_info.type_key, origin_type_index=foo_info.type_index)
        bar_schema = TypeSchema(bar_info.type_key, origin_type_index=bar_info.type_index)
        self._finalize(
            Foo,
            foo_info,
            [
                Field(name="a", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING),
                Field(
                    name="bar",
                    ty=TypeSchema("Optional", (bar_schema,)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        self._finalize(
            Bar,
            bar_info,
            [
                Field(
                    name="foo",
                    ty=TypeSchema("Optional", (foo_schema,)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        foo = Foo(a="hello")
        bar = Bar()
        bar.foo = foo
        foo.bar = bar
        assert foo.bar.foo.a == "hello"

    def test_self_referential_field(self) -> None:
        """Bar has Optional[Bar] (self-reference)."""
        Bar, bar_info = self._register_bare("SelfRef")
        bar_schema = TypeSchema(bar_info.type_key, origin_type_index=bar_info.type_index)
        self._finalize(
            Bar,
            bar_info,
            [
                Field(name="val", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(
                    name="next",
                    ty=TypeSchema("Optional", (bar_schema,)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        a = Bar(val=1)
        b = Bar(val=2, next=a)
        assert b.next.val == 1
        assert a.next is None
        # Circular: a → b → a
        a.next = b
        assert a.next.next.val == 1

    def test_typed_mutual_ref_rejects_wrong_type(self) -> None:
        """Optional[Foo] field should reject Bar objects."""
        Foo, foo_info = self._register_bare("TypedFoo")
        Bar, bar_info = self._register_bare("TypedBar")
        foo_schema = TypeSchema(foo_info.type_key, origin_type_index=foo_info.type_index)
        self._finalize(
            Foo,
            foo_info,
            [
                Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
            ],
        )
        self._finalize(
            Bar,
            bar_info,
            [
                Field(
                    name="foo",
                    ty=TypeSchema("Optional", (foo_schema,)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        bar = Bar()
        bar.foo = Foo(x=1)  # OK
        assert bar.foo.x == 1
        with pytest.raises((TypeError, RuntimeError)):
            bar.foo = bar  # Bar is not Foo


# ###########################################################################
#  16. Inheritance (native C++ parent)
# ###########################################################################
class TestNativeParentInheritance:
    """Python-defined child of C++ TestObjectBase: offsets, fields, methods, copy."""

    def test_non_overlapping_offsets(self) -> None:
        parent_info = core._type_cls_to_type_info(_TestObjectBase)
        assert parent_info is not None
        Child = _make_type(
            "InhNativeChild",
            [Field(name="extra", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=_TestObjectBase,
        )
        child_info = getattr(Child, "__tvm_ffi_type_info__")
        parent_end = max(f.offset + f.size for f in parent_info.fields)
        assert child_info.fields[0].offset >= parent_end

    def test_preserves_parent_fields(self) -> None:
        Child = _make_type(
            "InhNativePreserve",
            [Field(name="extra", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=_TestObjectBase,
        )
        obj = Child(extra=7, v_i64=1, v_f64=2.0, v_str="x")
        assert obj.extra == 7
        assert obj.v_i64 == 1
        assert obj.v_f64 == 2.0
        assert obj.v_str == "x"

    def test_mutation_no_aliasing(self) -> None:
        Child = _make_type(
            "InhNativeMut",
            [Field(name="extra", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=_TestObjectBase,
        )
        obj = Child(extra=7, v_i64=1, v_f64=2.0, v_str="x")
        obj.extra = 33
        assert obj.extra == 33
        assert obj.v_i64 == 1
        assert obj.v_f64 == 2.0
        assert obj.v_str == "x"

    def test_parent_method_uses_parent_state(self) -> None:
        Child = _make_type(
            "InhNativeMethod",
            [Field(name="extra", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=_TestObjectBase,
        )
        obj = Child(extra=7, v_i64=1, v_f64=2.0, v_str="x")
        assert obj.add_i64(5) == 6

    def test_copy_preserves_all_fields(self) -> None:
        Child = _make_type(
            "InhNativeCopy",
            [Field(name="extra", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=_TestObjectBase,
        )
        obj = Child(extra=7, v_i64=1, v_f64=2.0, v_str="x")
        obj_copy = copy.copy(obj)
        assert obj_copy.extra == 7
        assert obj_copy.v_i64 == 1
        assert obj_copy.v_f64 == 2.0
        assert obj_copy.v_str == "x"

    def test_deepcopy_preserves_all_fields(self) -> None:
        Child = _make_type(
            "InhNativeDeepCopy",
            [Field(name="extra", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
            parent=_TestObjectBase,
        )
        obj = Child(extra=7, v_i64=1, v_f64=2.0, v_str="x")
        obj_copy = copy.deepcopy(obj)
        assert obj_copy.extra == 7
        assert obj_copy.v_i64 == 1
        assert obj_copy.v_f64 == 2.0
        assert obj_copy.v_str == "x"


# ###########################################################################
#  16. Deep Copy
# ###########################################################################
class TestDeepCopy:
    """DeepCopy: basic, nested ObjectRef, mutation independence, Python dunder."""

    def test_deep_copy_basic(self) -> None:
        Cls = _make_type(
            "DCBasic",
            [
                Field(
                    name="x",
                    ty=TypeSchema("int"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
                Field(
                    name="s",
                    ty=TypeSchema("str"),
                    default=MISSING,
                    default_factory=MISSING,
                    compare=True,
                ),
            ],
            eq=True,
        )
        obj = Cls(x=42, s="hello")
        obj_copy = DeepCopy(obj)
        assert not obj.same_as(obj_copy)
        assert RecursiveEq(obj, obj_copy)

    def test_deep_copy_nested_objectref(self) -> None:
        Cls = _make_type(
            "DCNested",
            [
                Field(
                    name="items",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(items=tvm_ffi.Array([1, 2, 3]))
        obj_copy = DeepCopy(obj)
        assert not obj.items.same_as(obj_copy.items)
        assert len(obj_copy.items) == 3

    def test_deep_copy_mutate_independent(self) -> None:
        Cls = _make_type(
            "DCMut",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(x=1)
        obj_copy = DeepCopy(obj)
        obj_copy.x = 99
        assert obj.x == 1

    def test_python_deepcopy_dunder(self) -> None:
        Cls = _make_type(
            "DCPython",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(x=42)
        obj_copy = copy.deepcopy(obj)
        assert obj_copy.x == 42
        assert not obj.same_as(obj_copy)


# ###########################################################################
#  17. Memory / Lifetime
# ###########################################################################
class TestMemoryLifetime:
    """Verify ObjectRef/Any fields are properly ref-counted."""

    def test_objectref_field_kept_alive(self) -> None:
        Cls = _make_type(
            "MemAlive",
            [
                Field(
                    name="arr",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        arr = tvm_ffi.Array([1, 2, 3])
        obj = Cls(arr=arr)
        del arr
        gc.collect()
        assert len(obj.arr) == 3

    def test_multiple_objects_independent_lifetime(self) -> None:
        Cls = _make_type(
            "MemIndep",
            [
                Field(
                    name="arr",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        shared = tvm_ffi.Array([10, 20])
        a = Cls(arr=shared)
        b = Cls(arr=shared)
        del a
        gc.collect()
        assert len(b.arr) == 2
        assert b.arr[0] == 10

    def test_str_field_any_storage(self) -> None:
        Cls = _make_type(
            "MemStr",
            [Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        assert Cls(s="hi").s == "hi"
        long_str = "a" * 500
        assert Cls(s=long_str).s == long_str


# ###########################################################################
#  18. Bool Alignment
# ###########################################################################
class TestBoolAlignment:
    """Bool fields (1 byte): packing, padding, alternating layouts."""

    def test_bool_then_int_alignment(self) -> None:
        Cls = _make_type(
            "BoolAlign",
            [
                Field(name="flag", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING),
                Field(name="val", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
            ],
        )
        info = getattr(Cls, "__tvm_ffi_type_info__")
        assert info.fields[0].offset == 24
        assert info.fields[1].offset % 8 == 0
        assert info.fields[1].offset >= info.fields[0].offset + 1

    def test_bool_then_int_values(self) -> None:
        Cls = _make_type(
            "BoolAlignVal",
            [
                Field(name="flag", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING),
                Field(name="val", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
            ],
        )
        obj = Cls(flag=True, val=42)
        assert obj.flag is True
        assert obj.val == 42
        obj.flag = False
        assert obj.flag is False
        assert obj.val == 42

    def test_multiple_bools_packed(self) -> None:
        Cls = _make_type(
            "MultiBool",
            [
                Field(name="a", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING),
                Field(name="b", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING),
                Field(name="c", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING),
            ],
        )
        info = getattr(Cls, "__tvm_ffi_type_info__")
        assert [f.offset for f in info.fields] == [24, 25, 26]
        obj = Cls(a=True, b=False, c=True)
        assert obj.a is True
        assert obj.b is False
        assert obj.c is True

    def test_bool_int_bool_int_alternating(self) -> None:
        Cls = _make_type(
            "BoolIntBoolInt",
            [
                Field(name="b1", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING),
                Field(name="i1", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="b2", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING),
                Field(name="i2", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
            ],
        )
        obj = Cls(b1=True, i1=100, b2=False, i2=200)
        assert obj.b1 is True
        assert obj.i1 == 100
        assert obj.b2 is False
        assert obj.i2 == 200


# ###########################################################################
#  19. Type Conversion Errors
# ###########################################################################
class TestTypeConversionErrors:
    """Type conversion errors: wrong-type setter/construction raises."""

    def test_set_int_field_to_str_raises(self) -> None:
        Cls = _make_type(
            "ErrIntStr",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(x=1)
        with pytest.raises((TypeError, RuntimeError)):
            obj.x = "not_an_int"

    def test_set_str_field_to_int_raises(self) -> None:
        Cls = _make_type(
            "ErrStrInt",
            [Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(s="hello")
        with pytest.raises((TypeError, RuntimeError)):
            obj.s = 42

    def test_construct_with_wrong_type_raises(self) -> None:
        Cls = _make_type(
            "ErrInit",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        with pytest.raises((TypeError, RuntimeError)):
            Cls(x="bad")

    def test_set_wrong_type_preserves_old_value(self) -> None:
        """Failed type-checked mutation preserves old value."""
        Cls = _make_type(
            "ErrPreserve",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(x=42)
        with pytest.raises((TypeError, RuntimeError)):
            obj.x = "bad_value"
        assert obj.x == 42

    def test_type_schema_convert_raises_directly(self) -> None:
        """TypeSchema.convert raises TypeError for incompatible values."""
        ts = TypeSchema("int")
        assert ts.convert(42).to_py() == 42
        with pytest.raises(TypeError):
            ts.convert("not_an_int")

    def test_set_non_optional_object_field_to_none_raises(self) -> None:
        """A non-Optional Object field must reject None."""
        Cls = _make_type(
            "ErrObjNone",
            [
                Field(
                    name="child",
                    ty=TypeSchema("Object"),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(child=tvm_ffi.Array([1]))
        with pytest.raises((TypeError, RuntimeError)):
            obj.child = None

    def test_construct_non_optional_object_field_with_none_raises(self) -> None:
        """Constructing with None for a non-Optional Object field must fail."""
        Cls = _make_type(
            "ErrObjNoneInit",
            [
                Field(
                    name="child",
                    ty=TypeSchema("Object"),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        with pytest.raises((TypeError, RuntimeError)):
            Cls(child=None)

    def test_optional_object_field_accepts_none(self) -> None:
        """An Optional[Object] field should accept None."""
        Cls = _make_type(
            "OptObjNone",
            [
                Field(
                    name="child",
                    ty=TypeSchema("Optional", (TypeSchema("Object"),)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls()
        assert obj.child is None
        obj.child = tvm_ffi.Array([1, 2])
        assert len(obj.child) == 2
        obj.child = None
        assert obj.child is None

    def test_set_bool_field_to_str_raises(self) -> None:
        Cls = _make_type(
            "ErrBoolStr",
            [Field(name="b", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(b=True)
        with pytest.raises((TypeError, RuntimeError)):
            obj.b = "not_a_bool"

    def test_set_array_field_to_int_raises(self) -> None:
        Cls = _make_type(
            "ErrArrInt",
            [
                Field(
                    name="arr",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(arr=[1])
        with pytest.raises((TypeError, RuntimeError)):
            obj.arr = 42

    def test_construct_multiple_wrong_types_first_caught(self) -> None:
        """When the first field has a wrong type, the error is caught."""
        Cls = _make_type(
            "ErrMulti",
            [
                Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="y", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING),
            ],
        )
        with pytest.raises((TypeError, RuntimeError)):
            Cls(x="bad", y="ok")

    def test_set_optional_to_wrong_inner_type_raises(self) -> None:
        Cls = _make_type(
            "ErrOptWrong",
            [
                Field(
                    name="x",
                    ty=TypeSchema("Optional", (TypeSchema("int"),)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls()
        with pytest.raises((TypeError, RuntimeError)):
            obj.x = "not_an_int"


# ###########################################################################
#  20. Setter / Getter Corner Cases
# ###########################################################################
class TestSetterGetterCornerCases:
    """Extensive setter/getter coverage: conversions, nesting, edge values."""

    # --- Bool / int coercion ---

    def test_bool_field_accepts_true_false(self) -> None:
        Cls = _make_type(
            "SGBool",
            [Field(name="b", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(b=True)
        assert obj.b is True
        obj.b = False
        assert obj.b is False

    def test_int_field_accepts_bool(self) -> None:
        """Python bool is a subclass of int — FFI should accept it."""
        Cls = _make_type(
            "SGIntBool",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(x=True)
        assert obj.x == 1
        obj.x = False
        assert obj.x == 0

    # --- Float edge values ---

    def test_float_field_inf_nan(self) -> None:
        Cls = _make_type(
            "SGFloatEdge",
            [Field(name="f", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(f=float("inf"))
        assert math.isinf(obj.f)
        obj.f = float("-inf")
        assert math.isinf(obj.f) and obj.f < 0
        obj.f = float("nan")
        assert math.isnan(obj.f)

    def test_float_field_accepts_int(self) -> None:
        Cls = _make_type(
            "SGFloatInt",
            [Field(name="f", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(f=42)
        assert obj.f == pytest.approx(42.0)

    # --- String edge values ---

    def test_str_field_unicode(self) -> None:
        Cls = _make_type(
            "SGStrUni",
            [Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(s="日本語テスト 🎉")
        assert obj.s == "日本語テスト 🎉"

    def test_str_field_null_bytes(self) -> None:
        Cls = _make_type(
            "SGStrNull",
            [Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        s = "hello\x00world"
        obj = Cls(s=s)
        assert obj.s == s

    # --- Multiple mutations ---

    def test_repeated_mutation_same_field(self) -> None:
        Cls = _make_type(
            "SGRepeat",
            [Field(name="x", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(x=0)
        for i in range(100):
            obj.x = i
        assert obj.x == 99

    def test_repeated_str_mutation(self) -> None:
        """Stress: repeated str assignment should not leak."""
        Cls = _make_type(
            "SGRepeatStr",
            [Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING)],
        )
        obj = Cls(s="init")
        for i in range(100):
            obj.s = f"value_{i}"
        assert obj.s == "value_99"

    def test_repeated_objectref_mutation(self) -> None:
        """Stress: repeated ObjectRef assignment should properly DecRef old values."""
        Cls = _make_type(
            "SGRepeatArr",
            [
                Field(
                    name="arr",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(arr=[0])
        for i in range(50):
            obj.arr = tvm_ffi.Array([i])
        assert obj.arr[0] == 49

    # --- Nested object fields ---

    def test_nested_two_levels(self) -> None:
        Inner = _make_type(
            "SGInner",
            [Field(name="val", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING)],
        )
        inner_info = getattr(Inner, "__tvm_ffi_type_info__")
        inner_schema = TypeSchema(inner_info.type_key, origin_type_index=inner_info.type_index)
        Outer = _make_type(
            "SGOuter",
            [Field(name="child", ty=inner_schema, default=MISSING, default_factory=MISSING)],
        )
        obj = Outer(child=Inner(val=42))
        assert obj.child.val == 42
        # Mutate inner through outer
        new_inner = Inner(val=99)
        obj.child = new_inner
        assert obj.child.val == 99

    def test_self_referential_optional_field(self) -> None:
        """A type with an Optional[Self] field (stored as Any)."""
        Cls = _make_type(
            "SGSelfRef",
            [
                Field(name="val", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(
                    name="next",
                    ty=TypeSchema("Optional", (TypeSchema("Object"),)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        a = Cls(val=1)
        b = Cls(val=2, next=a)
        assert b.val == 2
        assert b.next.val == 1
        assert a.next is None

    # --- Default factory edge cases ---

    def test_default_factory_called_each_time(self) -> None:
        call_count = [0]

        def factory() -> int:
            call_count[0] += 1
            return call_count[0]

        Cls = _make_type(
            "SGFactoryCount",
            [Field(name="x", ty=TypeSchema("int"), default_factory=factory)],
        )
        a = Cls()
        b = Cls()
        c = Cls()
        assert a.x == 1
        assert b.x == 2
        assert c.x == 3

    # --- Mixed types in one class ---

    def test_all_pod_plus_objectref_plus_optional(self) -> None:
        Cls = _make_type(
            "SGKitchenSink",
            [
                Field(name="i", ty=TypeSchema("int"), default=MISSING, default_factory=MISSING),
                Field(name="f", ty=TypeSchema("float"), default=MISSING, default_factory=MISSING),
                Field(name="b", ty=TypeSchema("bool"), default=MISSING, default_factory=MISSING),
                Field(name="s", ty=TypeSchema("str"), default=MISSING, default_factory=MISSING),
                Field(
                    name="arr",
                    ty=TypeSchema("Array", (TypeSchema("int"),)),
                    default=MISSING,
                    default_factory=MISSING,
                ),
                Field(
                    name="opt",
                    ty=TypeSchema("Optional", (TypeSchema("int"),)),
                    default=None,
                    default_factory=MISSING,
                ),
            ],
        )
        obj = Cls(i=1, f=2.0, b=True, s="hi", arr=[10, 20])
        assert obj.i == 1
        assert obj.f == pytest.approx(2.0)
        assert obj.b is True
        assert obj.s == "hi"
        assert len(obj.arr) == 2
        assert obj.opt is None
        # Mutate all fields
        obj.i = -1
        obj.f = -2.0
        obj.b = False
        obj.s = "bye"
        obj.arr = tvm_ffi.Array([30])
        obj.opt = 42
        assert obj.i == -1
        assert obj.f == pytest.approx(-2.0)
        assert obj.b is False
        assert obj.s == "bye"
        assert len(obj.arr) == 1
        assert obj.opt == 42


# ###########################################################################
#  21. FFI Global Function Existence
# ###########################################################################
class TestFFIGlobalFunctions:
    """Verify required FFI global functions are registered."""

    def test_make_ffi_new_exists(self) -> None:
        assert tvm_ffi.get_global_func("ffi.MakeFFINew", allow_missing=True) is not None

    def test_register_auto_init_exists(self) -> None:
        assert tvm_ffi.get_global_func("ffi.RegisterAutoInit", allow_missing=True) is not None

    def test_get_field_getter_exists(self) -> None:
        assert tvm_ffi.get_global_func("ffi.GetFieldGetter", allow_missing=True) is not None

    def test_make_field_setter_exists(self) -> None:
        assert tvm_ffi.get_global_func("ffi.MakeFieldSetter", allow_missing=True) is not None

    def test_make_new_removed(self) -> None:
        assert tvm_ffi.get_global_func("ffi.MakeNew", allow_missing=True) is None
