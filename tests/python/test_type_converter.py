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
"""Tests for TypeSchema type conversion to CAny."""

from __future__ import annotations

import collections.abc
import ctypes
import sys
import typing
from typing import Callable, Iterator, Optional, Union

import pytest
import tvm_ffi
from tvm_ffi.core import (
    TypeSchema,
)

# Python 3.9+ supports list[int], dict[str, int], tuple[int, ...] at runtime.
# On 3.8, these raise TypeError("'type' object is not subscriptable").
_PY39 = sys.version_info >= (3, 9)
requires_py39 = pytest.mark.skipif(
    not _PY39, reason="builtin generic subscripts require Python 3.9+"
)
from tvm_ffi.testing import (
    TestObjectBase,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def S(origin: str, *args: TypeSchema) -> TypeSchema:
    """Shorthand constructor for TypeSchema (string-based)."""
    return TypeSchema(origin, tuple(args))


# Annotation-based constructor — the main subject under test.
A = TypeSchema.from_annotation


# ---------------------------------------------------------------------------
# Category 1: POD type exact match (check_value)
# ---------------------------------------------------------------------------
class TestPODExactMatch:
    def test_int(self) -> None:
        """Test int."""
        A(int).check_value(42)

    def test_float(self) -> None:
        """Test float."""
        A(float).check_value(3.14)

    def test_bool_true(self) -> None:
        """Test bool true."""
        A(bool).check_value(True)

    def test_bool_false(self) -> None:
        """Test bool false."""
        A(bool).check_value(False)

    def test_str(self) -> None:
        """Test str."""
        A(str).check_value("hello")

    def test_bytes(self) -> None:
        """Test bytes."""
        A(bytes).check_value(b"data")

    def test_none(self) -> None:
        """Test none."""
        A(type(None)).check_value(None)


# ---------------------------------------------------------------------------
# Category 2: Implicit conversions (mirrors TryCastFromAnyView)
# ---------------------------------------------------------------------------
class TestImplicitConversions:
    def test_bool_to_int(self) -> None:
        """Bool -> int is OK (C++: int accepts bool)."""
        A(int).check_value(True)

    def test_int_to_float(self) -> None:
        """Int -> float is OK (C++: float accepts int)."""
        A(float).check_value(42)

    def test_bool_to_float(self) -> None:
        """Bool -> float is OK (C++: float accepts bool)."""
        A(float).check_value(True)

    def test_int_to_bool(self) -> None:
        """Int -> bool is OK (C++: bool accepts int)."""
        A(bool).check_value(1)


# ---------------------------------------------------------------------------
# Category 3: Rejection cases
# ---------------------------------------------------------------------------
class TestRejections:
    def test_str_not_int(self) -> None:
        """Test str not int."""
        with pytest.raises(TypeError, match="expected int"):
            A(int).check_value("hello")

    def test_float_not_int(self) -> None:
        """Test float not int."""
        with pytest.raises(TypeError):
            A(int).check_value(3.14)

    def test_none_not_int(self) -> None:
        """Test none not int."""
        with pytest.raises(TypeError):
            A(int).check_value(None)

    def test_int_not_str(self) -> None:
        """Test int not str."""
        with pytest.raises(TypeError):
            A(str).check_value(42)

    def test_str_not_bool(self) -> None:
        """Test str not bool."""
        with pytest.raises(TypeError):
            A(bool).check_value("hello")

    def test_none_not_str(self) -> None:
        """Test none not str."""
        with pytest.raises(TypeError):
            A(str).check_value(None)

    def test_int_not_bytes(self) -> None:
        """Test int not bytes."""
        with pytest.raises(TypeError):
            A(bytes).check_value(42)

    def test_int_not_none(self) -> None:
        """Test int not none."""
        with pytest.raises(TypeError):
            A(type(None)).check_value(42)


# ---------------------------------------------------------------------------
# Category 4: Special types
# ---------------------------------------------------------------------------
class TestSpecialTypes:
    def test_device_pass(self) -> None:
        """Test device pass."""
        dev = tvm_ffi.Device("cpu", 0)
        A(tvm_ffi.Device).check_value(dev)

    def test_device_fail(self) -> None:
        """Test device fail."""
        with pytest.raises(TypeError):
            A(tvm_ffi.Device).check_value(42)

    def test_dtype_pass(self) -> None:
        """Test dtype pass."""
        dt = tvm_ffi.core.DataType("float32")
        A(tvm_ffi.core.DataType).check_value(dt)

    def test_dtype_str_pass(self) -> None:
        """Str accepted as dtype (will be parsed)."""
        A(tvm_ffi.core.DataType).check_value("float32")

    def test_dtype_fail(self) -> None:
        """Test dtype fail."""
        with pytest.raises(TypeError):
            A(tvm_ffi.core.DataType).check_value(42)

    def test_opaque_ptr_pass(self) -> None:
        """Test opaque ptr pass."""
        A(ctypes.c_void_p).check_value(ctypes.c_void_p(0))

    def test_opaque_ptr_none_pass(self) -> None:
        """Test opaque ptr none pass."""
        A(ctypes.c_void_p).check_value(None)

    def test_opaque_ptr_fail(self) -> None:
        """Test opaque ptr fail."""
        with pytest.raises(TypeError):
            A(ctypes.c_void_p).check_value(42)

    def test_callable_pass_function(self) -> None:
        """Test callable pass function."""
        A(Callable).check_value(lambda x: x)

    def test_callable_pass_builtin(self) -> None:
        """Test callable pass builtin."""
        A(Callable).check_value(len)

    def test_callable_fail(self) -> None:
        """Test callable fail."""
        with pytest.raises(TypeError):
            A(Callable).check_value(42)

    def test_collections_abc_callable_pass_function(self) -> None:
        """collections.abc.Callable accepts Python functions."""
        A(collections.abc.Callable).check_value(lambda x: x)

    def test_collections_abc_callable_pass_builtin(self) -> None:
        """collections.abc.Callable accepts builtins."""
        A(collections.abc.Callable).check_value(len)

    def test_collections_abc_callable_fail(self) -> None:
        """collections.abc.Callable rejects non-callables."""
        with pytest.raises(TypeError, match="expected Callable"):
            A(collections.abc.Callable).check_value(42)

    def test_callable_cobject_wraps_to_function(self) -> None:
        """Callable CObjects are wrapped instead of asserting."""

        class CallableObj(TestObjectBase):
            def __call__(self, x: int) -> int:
                return x + 1

        obj = CallableObj(v_i64=1, v_f64=2.0, v_str="s")
        with pytest.raises(TypeError, match=r"expected Callable, got .*TestObjectBase"):
            A(Callable).check_value(obj)


# ---------------------------------------------------------------------------
# Category 5: Object types
# ---------------------------------------------------------------------------
class TestObjectTypes:
    def test_object_pass(self) -> None:
        """Any CObject passes TypeSchema('Object')."""
        f = tvm_ffi.get_global_func("testing.echo")
        A(tvm_ffi.core.Object).check_value(f)

    def test_object_fail(self) -> None:
        """Test object fail."""
        with pytest.raises(TypeError):
            A(tvm_ffi.core.Object).check_value(42)

    def test_specific_object_pass(self) -> None:
        """A Function object should pass its own type schema."""
        f = tvm_ffi.get_global_func("testing.echo")
        A(Callable).check_value(f)

    def test_function_from_extern_c_exists(self) -> None:
        """ffi.FunctionFromExternC should be registered."""
        fn = tvm_ffi.get_global_func("ffi.FunctionFromExternC", allow_missing=True)
        assert fn is not None, "ffi.FunctionFromExternC not registered"


# ---------------------------------------------------------------------------
# Category 6: Optional
# ---------------------------------------------------------------------------
class TestOptional:
    def test_none_passes(self) -> None:
        """Test none passes."""
        A(Optional[int]).check_value(None)

    def test_inner_type_passes(self) -> None:
        """Test inner type passes."""
        A(Optional[int]).check_value(42)

    def test_wrong_type_fails(self) -> None:
        """Test wrong type fails."""
        with pytest.raises(TypeError, match="expected int"):
            A(Optional[int]).check_value("hello")

    def test_nested_optional(self) -> None:
        """Test nested optional."""
        schema = A(Optional[Optional[int]])
        schema.check_value(None)
        schema.check_value(42)


# ---------------------------------------------------------------------------
# Category 7: Union / Variant
# ---------------------------------------------------------------------------
class TestUnion:
    def test_first_alt_passes(self) -> None:
        """Test first alt passes."""
        A(Union[int, str]).check_value(42)

    def test_second_alt_passes(self) -> None:
        """Test second alt passes."""
        A(Union[int, str]).check_value("hello")

    def test_no_alt_matches(self) -> None:
        """Test no alt matches."""
        with pytest.raises(TypeError, match="got float"):
            A(Union[int, str]).check_value(3.14)

    def test_bool_matches_int_alt(self) -> None:
        """Bool is accepted by the int alternative."""
        A(Union[int, str]).check_value(True)


# ---------------------------------------------------------------------------
# Category 8: Containers
# ---------------------------------------------------------------------------
class TestContainers:
    @requires_py39
    def test_array_list_pass(self) -> None:
        """Test array list pass."""
        A(tuple[int, ...]).check_value([1, 2, 3])

    @requires_py39
    def test_array_tuple_pass(self) -> None:
        """Test array tuple pass."""
        A(tuple[int, ...]).check_value((1, 2, 3))

    @requires_py39
    def test_array_wrong_element(self) -> None:
        """Test array wrong element."""
        with pytest.raises(TypeError, match=r"element \[1\].*expected int"):
            A(tuple[int, ...]).check_value([1, "x"])

    @requires_py39
    def test_array_empty_pass(self) -> None:
        """Test array empty pass."""
        A(tuple[int, ...]).check_value([])

    @requires_py39
    def test_array_any_pass(self) -> None:
        """Test array any pass."""
        A(tuple[typing.Any, ...]).check_value([1, "x", None])

    @requires_py39
    def test_array_wrong_container_type(self) -> None:
        """Test array wrong container type."""
        with pytest.raises(TypeError, match="expected Array"):
            A(tuple[int, ...]).check_value(42)

    @requires_py39
    def test_array_rejects_generator(self) -> None:
        """Generators are not accepted by Array schemas."""

        def gen() -> Iterator[int]:
            yield 1
            yield 2

        with pytest.raises(TypeError, match="expected Array"):
            A(tuple[int, ...]).check_value(gen())

    @requires_py39
    def test_array_rejects_string(self) -> None:
        """Strings are not accepted by Array schemas."""
        with pytest.raises(TypeError, match="expected Array"):
            A(tuple[int, ...]).check_value("hello")

    @requires_py39
    def test_list_pass(self) -> None:
        """Test list pass."""
        A(list[str]).check_value(["a", "b"])

    @requires_py39
    def test_map_pass(self) -> None:
        """Test map pass."""
        A(tvm_ffi.Map[str, int]).check_value({"a": 1, "b": 2})

    @requires_py39
    def test_map_wrong_key(self) -> None:
        """Test map wrong key."""
        with pytest.raises(TypeError, match="expected str"):
            A(tvm_ffi.Map[str, int]).check_value({1: 2})

    @requires_py39
    def test_map_wrong_value(self) -> None:
        """Test map wrong value."""
        with pytest.raises(TypeError, match="expected int"):
            A(tvm_ffi.Map[str, int]).check_value({"a": "b"})

    @requires_py39
    def test_map_empty_pass(self) -> None:
        """Test map empty pass."""
        A(tvm_ffi.Map[str, int]).check_value({})

    @requires_py39
    def test_dict_pass(self) -> None:
        """Test dict pass."""
        A(dict[str, int]).check_value({"a": 1})

    @requires_py39
    def test_map_wrong_container(self) -> None:
        """Test map wrong container."""
        with pytest.raises(TypeError, match="expected Map"):
            A(tvm_ffi.Map[str, int]).check_value([1, 2])

    @requires_py39
    def test_map_rejects_non_mapping_pairs(self) -> None:
        """Lists of pairs are not accepted by Map schemas."""
        with pytest.raises(TypeError, match="expected Map"):
            A(tvm_ffi.Map[str, int]).check_value([("a", 1)])


# ---------------------------------------------------------------------------
# Category 9: Nested types
# ---------------------------------------------------------------------------
class TestNestedTypes:
    @requires_py39
    def test_array_optional_int(self) -> None:
        """Test array optional int."""
        A(tuple[Optional[int], ...]).check_value([1, None, 2])

    @requires_py39
    def test_map_str_array_int(self) -> None:
        """Test map str array int."""
        A(tvm_ffi.Map[str, tuple[int, ...]]).check_value({"a": [1, 2]})

    @requires_py39
    def test_map_str_array_int_nested_fail(self) -> None:
        """Test map str array int nested fail."""
        with pytest.raises(TypeError, match="expected int"):
            A(tvm_ffi.Map[str, tuple[int, ...]]).check_value({"a": [1, "x"]})

    @requires_py39
    def test_union_with_containers(self) -> None:
        """Test union with containers."""
        schema = A(Union[int, tuple[str, ...]])
        schema.check_value(42)
        schema.check_value(["a", "b"])
        with pytest.raises(TypeError):
            schema.check_value(3.14)


# ---------------------------------------------------------------------------
# Category 10: Any
# ---------------------------------------------------------------------------
class TestAny:
    def test_int(self) -> None:
        """Test int."""
        A(typing.Any).check_value(42)

    def test_none(self) -> None:
        """Test none."""
        A(typing.Any).check_value(None)

    def test_str(self) -> None:
        """Test str."""
        A(typing.Any).check_value("hello")

    def test_list(self) -> None:
        """Test list."""
        A(typing.Any).check_value([1, 2, 3])

    def test_object(self) -> None:
        """Test object."""
        A(typing.Any).check_value(object())
