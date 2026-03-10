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
    ObjectConvertible,
    TypeSchema,
)

# Python 3.9+ supports list[int], dict[str, int], tuple[int, ...] at runtime.
# On 3.8, these raise TypeError("'type' object is not subscriptable").
_PY39 = sys.version_info >= (3, 9)
requires_py39 = pytest.mark.skipif(
    not _PY39, reason="builtin generic subscripts require Python 3.9+"
)
from tvm_ffi.testing import (
    TestIntPair,
    TestObjectBase,
    TestObjectDerived,
    _TestCxxClassBase,
    _TestCxxClassDerived,
    _TestCxxClassDerivedDerived,
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

    def test_object_convertible_convert(self) -> None:
        """Any eagerly unwraps ObjectConvertible via asobject()."""
        inner = TestIntPair(1, 2)

        class Convertible(ObjectConvertible):
            def asobject(self) -> tvm_ffi.core.Object:
                return inner

        result = A(typing.Any).convert(Convertible()).to_py()
        assert result.same_as(inner)

    def test_object_convertible_error(self) -> None:
        """Any surfaces asobject() failures during eager normalization."""

        class BadConvertible(ObjectConvertible):
            def asobject(self) -> tvm_ffi.core.Object:
                raise RuntimeError("broken")

        with pytest.raises(TypeError, match=r"asobject\(\) failed"):
            A(typing.Any).check_value(BadConvertible())

    def test_object_protocol_convert(self) -> None:
        """Any eagerly unwraps __tvm_ffi_object__ before dispatch."""
        inner = TestIntPair(1, 2)

        class ObjProto:
            def __tvm_ffi_object__(self) -> object:
                return inner

        result = A(typing.Any).convert(ObjProto()).to_py()
        assert result.same_as(inner)

    def test_object_protocol_error(self) -> None:
        """Any surfaces __tvm_ffi_object__ failures during eager normalization."""

        class BadProto:
            def __tvm_ffi_object__(self) -> object:
                raise RuntimeError("broken")

        with pytest.raises(TypeError, match=r"__tvm_ffi_object__\(\) failed"):
            A(typing.Any).check_value(BadProto())


# ---------------------------------------------------------------------------
# Category 11: Error message quality
# ---------------------------------------------------------------------------
class TestErrorMessages:
    def test_basic_type_mismatch(self) -> None:
        """Test basic type mismatch."""
        with pytest.raises(TypeError, match=r"expected int, got str"):
            A(int).check_value("hello")

    @requires_py39
    def test_nested_array_error(self) -> None:
        """Test nested array error."""
        with pytest.raises(TypeError, match=r"element \[2\].*expected int, got str"):
            A(tuple[int, ...]).check_value([1, 2, "x"])

    @requires_py39
    def test_nested_map_error(self) -> None:
        """Test nested map error."""
        with pytest.raises(TypeError, match=r"value for key 'b'.*expected int, got str"):
            A(tvm_ffi.Map[str, int]).check_value({"a": 1, "b": "x"})

    def test_union_error_lists_alternatives(self) -> None:
        """Test union error lists alternatives."""
        with pytest.raises(TypeError, match="got float") as exc_info:
            A(Union[int, str]).check_value(3.14)
        err = str(exc_info.value)
        assert "int" in err
        assert "str" in err

    def test_schema_in_error_message(self) -> None:
        """check_value includes the schema repr in the TypeError."""
        with pytest.raises(TypeError, match=r"type check failed for"):
            A(int).check_value("hello")

    def test_convert_error_message(self) -> None:
        """Convert includes the schema repr in the TypeError."""
        with pytest.raises(TypeError, match=r"type conversion failed for"):
            A(int).convert("hello")


# ---------------------------------------------------------------------------
# Category 12: from_type_index factory
# ---------------------------------------------------------------------------
class TestFromTypeIndex:
    def test_int(self) -> None:
        """Test int."""
        schema = TypeSchema.from_type_index(1)  # kTVMFFIInt
        assert schema.origin == "int"
        assert schema.origin_type_index == 1

    def test_float(self) -> None:
        """Test float."""
        schema = TypeSchema.from_type_index(3)  # kTVMFFIFloat
        assert schema.origin == "float"

    def test_bool(self) -> None:
        """Test bool."""
        schema = TypeSchema.from_type_index(2)  # kTVMFFIBool
        assert schema.origin == "bool"

    def test_array_with_args(self) -> None:
        """Test array with args."""
        schema = TypeSchema.from_type_index(71, (A(int),))  # kTVMFFIArray
        assert schema.origin == "Array"
        assert len(schema.args) == 1
        assert schema.args[0].origin == "int"

    def test_roundtrip_check(self) -> None:
        """from_type_index then check_value works correctly."""
        schema = TypeSchema.from_type_index(1)  # int
        schema.check_value(42)
        with pytest.raises(TypeError):
            schema.check_value("hello")

    def test_none(self) -> None:
        """Test none."""
        schema = TypeSchema.from_type_index(0)  # kTVMFFINone
        assert schema.origin == "None"
        schema.check_value(None)

    def test_any(self) -> None:
        """Test any."""
        schema = TypeSchema.from_type_index(-1)  # kTVMFFIAny
        assert schema.origin == "Any"
        schema.check_value("anything")

    def test_str(self) -> None:
        """Test str."""
        schema = TypeSchema.from_type_index(65)  # kTVMFFIStr
        assert schema.origin == "str"
        schema.check_value("hello")

    def test_map_with_args(self) -> None:
        """Test map with args."""
        schema = TypeSchema.from_type_index(72, (A(str), A(int)))  # kTVMFFIMap
        assert schema.origin == "Map"
        schema.check_value({"a": 1})


# ---------------------------------------------------------------------------
# Category 13: Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_bytearray_passes_bytes(self) -> None:
        """Test bytearray passes bytes."""
        A(bytes).check_value(bytearray(b"data"))

    @requires_py39
    def test_tuple_passes_array(self) -> None:
        """Tuple is accepted as a sequence type for Array."""
        A(tuple[int, ...]).check_value((1, 2, 3))

    def test_empty_union_is_rejected(self) -> None:
        """Union requires at least 2 args."""
        with pytest.raises(ValueError, match="at least two"):
            TypeSchema("Union", ())

    def test_origin_type_index_auto_computed(self) -> None:
        """origin_type_index is automatically computed from origin string."""
        schema = A(int)
        assert schema.origin_type_index == 1  # kTVMFFIInt
        schema = A(float)
        assert schema.origin_type_index == 3  # kTVMFFIFloat
        schema = A(Optional[int])
        assert schema.origin_type_index == -2  # structural

    def test_check_value_succeeds_on_valid(self) -> None:
        """Test check value succeeds on valid input."""
        A(int).check_value(42)

    def test_check_value_raises_on_failure(self) -> None:
        """Test check value raises TypeError on failure."""
        with pytest.raises(TypeError, match="expected int"):
            A(int).check_value("hello")

    @requires_py39
    def test_tuple_type_schema(self) -> None:
        """Test tuple type schema."""
        schema = A(tuple[int, str])
        schema.check_value((1, "a"))
        with pytest.raises(TypeError):
            schema.check_value((1, 2))
        with pytest.raises(TypeError):
            schema.check_value((1,))

    def test_numpy_int_passes_int(self) -> None:
        """Numpy integer types should pass int check via Integral."""
        np = pytest.importorskip("numpy")
        A(int).check_value(np.int64(42))
        A(float).check_value(np.float64(3.14))


# ===========================================================================
# Type Converter Tests (convert)
# ===========================================================================


# ---------------------------------------------------------------------------
# Category 14: POD conversion results
# ---------------------------------------------------------------------------
class TestConvertPOD:
    def test_int_passthrough(self) -> None:
        """Int -> int returns the same value."""
        result = A(int).convert(42).to_py()
        assert result == 42
        assert type(result) is int

    def test_bool_to_int(self) -> None:
        """Bool -> int actually converts to int."""
        result = A(int).convert(True).to_py()
        assert result == 1
        assert type(result) is int

    def test_bool_false_to_int(self) -> None:
        """Test bool false to int."""
        result = A(int).convert(False).to_py()
        assert result == 0
        assert type(result) is int

    def test_float_passthrough(self) -> None:
        """Test float passthrough."""
        result = A(float).convert(3.14).to_py()
        assert result == 3.14
        assert type(result) is float

    def test_int_to_float(self) -> None:
        """Int -> float actually converts."""
        result = A(float).convert(42).to_py()
        assert result == 42.0
        assert type(result) is float

    def test_bool_to_float(self) -> None:
        """Bool -> float actually converts."""
        result = A(float).convert(True).to_py()
        assert result == 1.0
        assert type(result) is float

    def test_bool_passthrough(self) -> None:
        """Test bool passthrough."""
        result = A(bool).convert(True).to_py()
        assert result is True
        assert type(result) is bool

    def test_int_to_bool(self) -> None:
        """Int -> bool actually converts."""
        result = A(bool).convert(1).to_py()
        assert result is True
        assert type(result) is bool

    def test_int_zero_to_bool(self) -> None:
        """Test int zero to bool."""
        result = A(bool).convert(0).to_py()
        assert result is False
        assert type(result) is bool

    def test_str_passthrough(self) -> None:
        """Test str passthrough — returns tvm_ffi.String (subclass of str)."""
        result = A(str).convert("hello").to_py()
        assert result == "hello"
        assert isinstance(result, str)
        assert isinstance(result, tvm_ffi.core.String)

    def test_bytes_passthrough(self) -> None:
        """Test bytes passthrough — returns tvm_ffi.Bytes (subclass of bytes)."""
        result = A(bytes).convert(b"data").to_py()
        assert result == b"data"
        assert isinstance(result, bytes)
        assert isinstance(result, tvm_ffi.core.Bytes)

    def test_bytearray_to_bytes(self) -> None:
        """Bytearray -> bytes converts to tvm_ffi.Bytes."""
        result = A(bytes).convert(bytearray(b"data")).to_py()
        assert result == b"data"
        assert isinstance(result, bytes)
        assert isinstance(result, tvm_ffi.core.Bytes)


# ---------------------------------------------------------------------------
# Category 15: None disambiguation (critical design point)
# ---------------------------------------------------------------------------
class TestNoneDisambiguation:
    def test_none_converts_successfully_for_none_schema(self) -> None:
        """TypeSchema('None').convert(None) returns None as a valid result."""
        result = A(type(None)).convert(None).to_py()
        assert result is None

    def test_none_converts_successfully_for_optional(self) -> None:
        """Optional[int].convert(None) returns None as a valid result."""
        result = A(Optional[int]).convert(None).to_py()
        assert result is None

    def test_none_fails_for_int(self) -> None:
        """TypeSchema('int').convert(None) raises TypeError."""
        with pytest.raises(TypeError, match="expected int, got None"):
            A(int).convert(None)

    def test_convert_none_success(self) -> None:
        """Convert returns None for Optional[int] with None input."""
        result = A(Optional[int]).convert(None).to_py()
        assert result is None

    def test_convert_none_failure(self) -> None:
        """Convert raises TypeError for failed conversion."""
        with pytest.raises(TypeError, match="expected int"):
            A(int).convert(None)

    def test_convert_success_with_value(self) -> None:
        """Convert returns converted value on success."""
        result = A(int).convert(True).to_py()
        assert result == 1
        assert type(result) is int

    def test_opaque_ptr_none_converts(self) -> None:
        """ctypes.c_void_p accepts None and converts it to a null opaque pointer."""
        result = A(ctypes.c_void_p).convert(None).to_py()
        assert isinstance(result, ctypes.c_void_p)
        assert result.value is None

    def test_convert_opaque_ptr_none(self) -> None:
        """Test convert opaque ptr none."""
        result = A(ctypes.c_void_p).convert(None).to_py()
        assert isinstance(result, ctypes.c_void_p)
        assert result.value is None


# ---------------------------------------------------------------------------
# Category 16: Special type conversions
# ---------------------------------------------------------------------------
class TestConvertSpecialTypes:
    def test_dtype_str_converts(self) -> None:
        """Str -> dtype actually creates a DataType object."""
        result = A(tvm_ffi.core.DataType).convert("float32").to_py()
        assert isinstance(result, tvm_ffi.core.DataType)
        assert str(result) == "float32"

    def test_dtype_passthrough(self) -> None:
        """Test dtype passthrough."""
        dt = tvm_ffi.core.DataType("int32")
        result = A(tvm_ffi.core.DataType).convert(dt).to_py()
        assert str(result) == str(dt)

    def test_device_passthrough(self) -> None:
        """Test device passthrough."""
        dev = tvm_ffi.Device("cpu", 0)
        result = A(tvm_ffi.Device).convert(dev).to_py()
        assert str(result) == str(dev)

    def test_callable_passthrough(self) -> None:
        """Test callable passthrough."""
        fn = lambda x: x
        result = A(Callable).convert(fn).to_py()
        assert callable(result)

    def test_opaque_ptr_passthrough(self) -> None:
        """Test opaque ptr passthrough."""
        ptr = ctypes.c_void_p(42)
        result = A(ctypes.c_void_p).convert(ptr).to_py()
        assert result is not None


# ---------------------------------------------------------------------------
# Category 17: Container conversion results
# ---------------------------------------------------------------------------
class TestConvertContainers:
    @requires_py39
    def test_array_converts_bool_elements_to_int(self) -> None:
        """Array[int] with bool elements converts them to int."""
        result = A(tuple[int, ...]).convert([True, False, 1]).to_py()
        assert list(result) == [1, 0, 1]
        assert all(type(x) is int for x in result)

    @requires_py39
    def test_array_int_passthrough(self) -> None:
        """Array[int] with int elements returns ffi.Array."""
        result = A(tuple[int, ...]).convert([1, 2, 3]).to_py()
        assert list(result) == [1, 2, 3]

    @requires_py39
    def test_array_any_passthrough(self) -> None:
        """Array[Any] wraps into ffi.Array."""
        original = [1, "x", None]
        result = A(tuple[typing.Any, ...]).convert(original).to_py()
        assert isinstance(result, tvm_ffi.Array)

    @requires_py39
    def test_map_converts_values(self) -> None:
        """Map[str, float] converts int values to float."""
        result = A(tvm_ffi.Map[str, float]).convert({"a": 1, "b": 2}).to_py()
        assert isinstance(result, tvm_ffi.Map)
        assert type(result["a"]) is float
        assert type(result["b"]) is float
        assert result["a"] == 1.0
        assert result["b"] == 2.0

    @requires_py39
    def test_map_any_float_converts_values(self) -> None:
        """Map[Any, float] still converts values when keys are Any."""
        result = A(tvm_ffi.Map[typing.Any, float]).convert({"a": 1, "b": 2}).to_py()
        assert isinstance(result, tvm_ffi.Map)
        assert type(result["a"]) is float

    @requires_py39
    def test_map_any_any_passthrough(self) -> None:
        """Map[Any, Any] wraps into ffi.Map."""
        original = {"a": 1}
        result = A(tvm_ffi.Map[typing.Any, typing.Any]).convert(original).to_py()
        assert isinstance(result, tvm_ffi.Map)

    @requires_py39
    def test_map_empty_dict_convert(self) -> None:
        """Empty dict converts to Map[str, int]."""
        result = A(tvm_ffi.Map[str, int]).convert({}).to_py()
        assert len(result) == 0

    @requires_py39
    def test_dict_empty_dict_convert(self) -> None:
        """Empty dict converts to Dict[str, int]."""
        result = A(dict[str, int]).convert({}).to_py()
        assert len(result) == 0

    @requires_py39
    def test_tuple_converts_elements(self) -> None:
        """tuple[int, float] converts elements positionally."""
        result = A(tuple[int, float]).convert((True, 42)).to_py()
        assert list(result) == [1, 42.0]
        assert type(result[0]) is int
        assert type(result[1]) is float

    @requires_py39
    def test_nested_array_in_map(self) -> None:
        """Map[str, Array[int]] recursively converts elements."""
        result = A(tvm_ffi.Map[str, tuple[int, ...]]).convert({"a": [True, False]}).to_py()
        assert isinstance(result, tvm_ffi.Map)
        assert list(result["a"]) == [1, 0]
        assert all(type(x) is int for x in result["a"])

    @requires_py39
    def test_array_optional_int_all_none(self) -> None:
        """Array[Optional[int]] accepts an all-None payload."""
        result = A(tuple[Optional[int], ...]).convert([None, None, None]).to_py()
        assert list(result) == [None, None, None]


# ---------------------------------------------------------------------------
# Category 18: Optional/Union conversion results
# ---------------------------------------------------------------------------
class TestConvertComposite:
    def test_optional_converts_inner(self) -> None:
        """Optional[float].convert(42) converts int -> float."""
        result = A(Optional[float]).convert(42).to_py()
        assert result == 42.0
        assert type(result) is float

    def test_optional_none(self) -> None:
        """Test optional none."""
        result = A(Optional[float]).convert(None).to_py()
        assert result is None

    def test_union_picks_first_match(self) -> None:
        """Union[int, str] converts bool via int alternative."""
        result = A(Union[int, str]).convert(True).to_py()
        assert result == 1
        assert type(result) is int

    def test_union_second_match(self) -> None:
        """Test union second match."""
        result = A(Union[int, str]).convert("hello").to_py()
        assert result == "hello"

    def test_any_passthrough(self) -> None:
        """Any returns value as-is."""
        result = A(typing.Any).convert(42).to_py()
        assert result == 42
        result = A(typing.Any).convert(None).to_py()
        assert result is None


# ---------------------------------------------------------------------------
# Category 19: Convert rejection cases
# ---------------------------------------------------------------------------
class TestConvertRejections:
    def test_int_rejects_str(self) -> None:
        """Test int rejects str."""
        with pytest.raises(TypeError, match="expected int, got str"):
            A(int).convert("hello")

    def test_int_rejects_float(self) -> None:
        """Test int rejects float."""
        with pytest.raises(TypeError, match="expected int, got float"):
            A(int).convert(3.14)

    def test_str_rejects_int(self) -> None:
        """Test str rejects int."""
        with pytest.raises(TypeError, match="expected str, got int"):
            A(str).convert(42)

    @requires_py39
    def test_array_rejects_wrong_element(self) -> None:
        """Test array rejects wrong element."""
        with pytest.raises(TypeError, match=r"element \[1\].*expected int, got str"):
            A(tuple[int, ...]).convert([1, "x"])

    @requires_py39
    def test_map_rejects_wrong_value(self) -> None:
        """Test map rejects wrong value."""
        with pytest.raises(TypeError, match=r"value for key 'a'.*expected int, got str"):
            A(tvm_ffi.Map[str, int]).convert({"a": "x"})

    @requires_py39
    def test_tuple_rejects_wrong_length(self) -> None:
        """Test tuple rejects wrong length."""
        with pytest.raises(TypeError, match=r"expected tuple of length 2"):
            A(tuple[int, str]).convert((1,))

    def test_convert_failure_raises(self) -> None:
        """Test convert failure raises TypeError."""
        with pytest.raises(TypeError, match="expected int"):
            A(int).convert("hello")


# ---------------------------------------------------------------------------
# Category 20: Numpy conversion
# ---------------------------------------------------------------------------
class TestConvertNumpy:
    def test_numpy_int_to_int(self) -> None:
        """Test numpy int to int."""
        np = pytest.importorskip("numpy")
        result = A(int).convert(np.int64(42)).to_py()
        assert result == 42
        assert type(result) is int

    def test_numpy_float_to_float(self) -> None:
        """Test numpy float to float."""
        np = pytest.importorskip("numpy")
        result = A(float).convert(np.float64(3.14)).to_py()
        assert result == pytest.approx(3.14)
        # np.float64 is a subclass of float, so isinstance check passes
        # and the value is returned as-is (no forced conversion to plain float)
        assert isinstance(result, float)


# ===========================================================================
# Nested Conversion Tests (with inner-level conversions)
# ===========================================================================


# ---------------------------------------------------------------------------
# Category 21: Array nested with Optional/Union (inner conversion)
# ---------------------------------------------------------------------------
class TestNestedArrayComposite:
    @requires_py39
    def test_array_optional_float_with_bool(self) -> None:
        """Array[Optional[float]] converts bool elements to float."""
        result = A(tuple[Optional[float], ...]).convert([True, None, 3]).to_py()
        assert list(result) == [1.0, None, 3.0]
        assert type(result[0]) is float
        assert result[1] is None
        assert type(result[2]) is float

    @requires_py39
    def test_array_optional_int_with_bool(self) -> None:
        """Array[Optional[int]] converts bool elements to int."""
        result = A(tuple[Optional[int], ...]).convert([True, None, 2]).to_py()
        assert list(result) == [1, None, 2]
        assert type(result[0]) is int
        assert result[1] is None

    @requires_py39
    def test_array_union_int_str_with_bool(self) -> None:
        """Array[Union[int, str]] converts bool via int alternative."""
        result = A(tuple[Union[int, str], ...]).convert([True, "hello", False]).to_py()
        assert list(result) == [1, "hello", 0]
        assert type(result[0]) is int
        assert type(result[1]) is str
        assert type(result[2]) is int

    @requires_py39
    def test_array_union_float_str_with_int(self) -> None:
        """Array[Union[float, str]] converts int via float alternative."""
        result = A(tuple[Union[float, str], ...]).convert([42, "hi", True]).to_py()
        assert list(result) == [42.0, "hi", 1.0]
        assert type(result[0]) is float
        assert type(result[2]) is float

    @requires_py39
    def test_array_optional_float_all_none(self) -> None:
        """Array[Optional[float]] with all None elements."""
        result = A(tuple[Optional[float], ...]).convert([None, None]).to_py()
        assert list(result) == [None, None]

    @requires_py39
    def test_array_optional_float_empty(self) -> None:
        """Array[Optional[float]] with empty list."""
        result = A(tuple[Optional[float], ...]).convert([]).to_py()
        assert list(result) == []

    @requires_py39
    def test_array_union_failure_in_element(self) -> None:
        """Array[Union[int, str]] fails when element matches no alternative."""
        with pytest.raises(TypeError, match=r"element \[1\].*got float"):
            A(tuple[Union[int, str], ...]).check_value([1, 3.14])


# ---------------------------------------------------------------------------
# Category 22: Map/Dict nested with Optional/Union (inner conversion)
# ---------------------------------------------------------------------------
class TestNestedMapComposite:
    @requires_py39
    def test_map_str_optional_float_with_int(self) -> None:
        """Map[str, Optional[float]] converts int values to float."""
        result = A(tvm_ffi.Map[str, Optional[float]]).convert({"a": 1, "b": None}).to_py()
        assert type(result["a"]) is float
        assert result["a"] == 1.0
        assert result["b"] is None

    @requires_py39
    def test_map_str_union_int_str(self) -> None:
        """Map[str, Union[int, str]] converts bool values via int."""
        result = A(tvm_ffi.Map[str, Union[int, str]]).convert({"x": True, "y": "hello"}).to_py()
        assert result["x"] == 1
        assert result["y"] == "hello"
        assert type(result["x"]) is int

    @requires_py39
    def test_dict_str_optional_int(self) -> None:
        """Dict[str, Optional[int]] with bool conversion."""
        result = A(dict[str, Optional[int]]).convert({"a": True, "b": None, "c": 42}).to_py()
        assert result["a"] == 1
        assert result["b"] is None
        assert result["c"] == 42
        assert type(result["a"]) is int

    @requires_py39
    def test_map_str_optional_float_failure(self) -> None:
        """Map[str, Optional[float]] fails for non-float non-None value."""
        with pytest.raises(TypeError, match="expected float"):
            A(tvm_ffi.Map[str, Optional[float]]).check_value({"a": "bad"})


# ---------------------------------------------------------------------------
# Category 23: Nested containers (container inside container)
# ---------------------------------------------------------------------------
class TestNestedContainerInContainer:
    @requires_py39
    def test_array_of_array_int(self) -> None:
        """Array[Array[int]] with inner bool->int conversion."""
        result = A(tuple[tuple[int, ...], ...]).convert([[True, False], [1, 2]]).to_py()
        assert [list(row) for row in result] == [[1, 0], [1, 2]]
        assert all(type(x) is int for row in result for x in row)

    @requires_py39
    def test_array_of_array_float(self) -> None:
        """Array[Array[float]] with inner int->float conversion."""
        result = A(tuple[tuple[float, ...], ...]).convert([[1, 2], [True, 3]]).to_py()
        assert [list(row) for row in result] == [[1.0, 2.0], [1.0, 3.0]]
        assert all(type(x) is float for row in result for x in row)

    @requires_py39
    def test_map_str_array_float(self) -> None:
        """Map[str, Array[float]] with int->float conversion in arrays."""
        result = (
            A(tvm_ffi.Map[str, tuple[float, ...]]).convert({"a": [1, 2], "b": [True, 3]}).to_py()
        )
        assert list(result["a"]) == [1.0, 2.0]
        assert list(result["b"]) == [1.0, 3.0]
        assert all(type(x) is float for x in result["a"])
        assert all(type(x) is float for x in result["b"])

    @requires_py39
    def test_dict_str_array_int(self) -> None:
        """Dict[str, Array[int]] with bool->int conversion."""
        result = A(dict[str, tuple[int, ...]]).convert({"a": [True, False]}).to_py()
        assert list(result["a"]) == [1, 0]
        assert all(type(x) is int for x in result["a"])

    @requires_py39
    def test_array_of_map_str_int(self) -> None:
        """Array[Map[str, int]] with bool->int value conversion."""
        result = A(tuple[tvm_ffi.Map[str, int], ...]).convert([{"x": True}, {"y": 2}]).to_py()
        assert result[0]["x"] == 1
        assert result[1]["y"] == 2
        assert type(result[0]["x"]) is int

    @requires_py39
    def test_map_str_map_str_float(self) -> None:
        """Map[str, Map[str, float]] double nested with int->float."""
        result = (
            A(tvm_ffi.Map[str, tvm_ffi.Map[str, float]]).convert({"outer": {"inner": 42}}).to_py()
        )
        assert result["outer"]["inner"] == 42.0
        assert type(result["outer"]["inner"]) is float

    @requires_py39
    def test_list_of_list_int(self) -> None:
        """List[List[int]] with bool->int conversion."""
        result = A(list[list[int]]).convert([[True, 1], [False, 2]]).to_py()
        assert [list(row) for row in result] == [[1, 1], [0, 2]]
        assert all(type(x) is int for row in result for x in row)

    @requires_py39
    def test_nested_failure_array_of_array(self) -> None:
        """Array[Array[int]] error propagation through nested arrays."""
        with pytest.raises(TypeError, match="expected int"):
            A(tuple[tuple[int, ...], ...]).check_value([[1, 2], [3, "bad"]])

    @requires_py39
    def test_empty_inner_containers(self) -> None:
        """Map[str, Array[int]] with empty inner arrays."""
        result = A(tvm_ffi.Map[str, tuple[int, ...]]).convert({"a": [], "b": []}).to_py()
        assert list(result["a"]) == []
        assert list(result["b"]) == []

    @requires_py39
    def test_array_of_array_of_array_int(self) -> None:
        """Three-level nested Array[int] conversion still works."""
        schema = A(tuple[tuple[tuple[int, ...], ...], ...])
        data = [[[1, 2], [True, False]], [[3], [4, 5, 6]]]
        result = schema.convert(data).to_py()
        assert list(result[0][0]) == [1, 2]
        assert list(result[0][1]) == [1, 0]
        assert type(result[0][1][0]) is int

    @requires_py39
    def test_map_of_map_of_array_float(self) -> None:
        """Nested map-to-array conversion still coerces inner values."""
        schema = A(tvm_ffi.Map[str, tvm_ffi.Map[str, tuple[float, ...]]])
        data = {"outer": {"inner": [1, 2, True]}}
        result = schema.convert(data).to_py()
        assert list(result["outer"]["inner"]) == [1.0, 2.0, 1.0]
        assert type(result["outer"]["inner"][0]) is float


# ---------------------------------------------------------------------------
# Category 24: Optional/Union wrapping containers
# ---------------------------------------------------------------------------
class TestOptionalUnionWrappingContainers:
    @requires_py39
    def test_optional_array_int_with_conversion(self) -> None:
        """Optional[Array[int]] converts inner bool elements."""
        schema = A(Optional[tuple[int, ...]])
        result = schema.convert([True, 2]).to_py()
        assert list(result) == [1, 2]
        assert type(result[0]) is int

    @requires_py39
    def test_optional_array_int_none(self) -> None:
        """Optional[Array[int]] accepts None."""
        result = A(Optional[tuple[int, ...]]).convert(None).to_py()
        assert result is None

    @requires_py39
    def test_optional_map_str_float(self) -> None:
        """Optional[Map[str, float]] converts inner int values."""
        result = A(Optional[tvm_ffi.Map[str, float]]).convert({"a": 1}).to_py()
        assert result["a"] == 1.0
        assert type(result["a"]) is float

    @requires_py39
    def test_optional_map_str_float_none(self) -> None:
        """Optional[Map[str, float]] accepts None."""
        result = A(Optional[tvm_ffi.Map[str, float]]).convert(None).to_py()
        assert result is None

    @requires_py39
    def test_union_array_int_or_map_str_int(self) -> None:
        """Union[Array[int], Map[str, int]] matches first with conversion."""
        schema = A(Union[tuple[int, ...], tvm_ffi.Map[str, int]])
        # list matches Array alternative
        result = schema.convert([True, 2]).to_py()
        assert list(result) == [1, 2]
        assert type(result[0]) is int

    @requires_py39
    def test_union_array_int_or_map_str_int_dict(self) -> None:
        """Union[Array[int], Map[str, int]] matches Map for dict input."""
        schema = A(Union[tuple[int, ...], tvm_ffi.Map[str, int]])
        result = schema.convert({"a": True}).to_py()
        assert result["a"] == 1
        assert type(result["a"]) is int

    @requires_py39
    def test_union_int_or_array_optional_float(self) -> None:
        """Union[int, Array[Optional[float]]] matches array with nested conversions."""
        schema = A(Union[int, tuple[Optional[float], ...]])
        result = schema.convert([True, None, 1]).to_py()
        assert list(result) == [1.0, None, 1.0]
        assert type(result[0]) is float
        assert result[1] is None

    @requires_py39
    def test_optional_optional_array_int(self) -> None:
        """Optional[Optional[Array[int]]] with inner conversion."""
        schema = A(Optional[Optional[tuple[int, ...]]])
        assert schema.convert(None).to_py() is None
        result = schema.convert([True, 2]).to_py()
        assert list(result) == [1, 2]
        assert type(result[0]) is int


# ---------------------------------------------------------------------------
# Category 25: Tuple nested with other types
# ---------------------------------------------------------------------------
class TestNestedTuple:
    @requires_py39
    def test_array_of_tuple_int_float(self) -> None:
        """Array[tuple[int, float]] with element-wise conversion."""
        result = A(tuple[tuple[int, float], ...]).convert([(True, 1), (2, True)]).to_py()
        # Check element values; FFI storage may normalize float 1.0 to int 1
        # when stored inside an ffi.Array, so we only check values not types.
        assert result[0][0] == 1
        assert result[0][1] == 1.0
        assert result[1][0] == 2
        assert result[1][1] == 1.0

    @requires_py39
    def test_map_str_tuple_int_str(self) -> None:
        """Map[str, tuple[int, str]] with inner bool->int conversion."""
        result = A(tvm_ffi.Map[str, tuple[int, str]]).convert({"a": (True, "hello")}).to_py()
        assert result["a"][0] == 1
        assert str(result["a"][1]) == "hello"
        assert type(result["a"][0]) is int

    @requires_py39
    def test_tuple_of_array_int_and_map(self) -> None:
        """tuple[Array[int], Map[str, float]] nested conversion."""
        schema = A(tuple[tuple[int, ...], tvm_ffi.Map[str, float]])
        result = schema.convert(([True, 2], {"k": 3})).to_py()
        assert list(result[0]) == [1, 2]
        assert result[1]["k"] == 3.0
        assert type(result[0][0]) is int
        assert type(result[1]["k"]) is float

    @requires_py39
    def test_tuple_of_optional_int_and_optional_float(self) -> None:
        """tuple[Optional[int], Optional[float]] with conversions."""
        schema = A(tuple[Optional[int], Optional[float]])
        result = schema.convert((True, None)).to_py()
        assert list(result) == [1, None]
        assert type(result[0]) is int
        assert result[1] is None

    @requires_py39
    def test_tuple_nested_failure(self) -> None:
        """tuple[Array[int], str] error propagation from inner array."""
        with pytest.raises(TypeError, match=r"element .0..*element .1..*expected int"):
            A(tuple[tuple[int, ...], str]).check_value(([1, "bad"], "ok"))


# ---------------------------------------------------------------------------
# Category 26: Deep nesting (3+ levels)
# ---------------------------------------------------------------------------
class TestDeepNesting:
    @requires_py39
    def test_map_str_array_optional_int(self) -> None:
        """Map[str, Array[Optional[int]]] with 3-level nesting and conversion."""
        result = (
            A(tvm_ffi.Map[str, tuple[Optional[int], ...]]).convert({"a": [1, None, True]}).to_py()
        )
        assert list(result["a"]) == [1, None, 1]
        assert type(result["a"][0]) is int
        assert result["a"][1] is None
        assert type(result["a"][2]) is int

    @requires_py39
    def test_array_map_str_optional_float(self) -> None:
        """Array[Map[str, Optional[float]]] with 3-level nesting."""
        result = (
            A(tuple[tvm_ffi.Map[str, Optional[float]], ...])
            .convert([{"x": 1, "y": None}, {"z": True}])
            .to_py()
        )
        assert result[0]["x"] == 1.0
        assert result[0]["y"] is None
        assert result[1]["z"] == 1.0
        assert type(result[0]["x"]) is float
        assert type(result[1]["z"]) is float

    @requires_py39
    def test_optional_array_map_str_int(self) -> None:
        """Optional[Array[Map[str, int]]] 3 levels deep."""
        schema = A(Optional[tuple[tvm_ffi.Map[str, int], ...]])
        result = schema.convert([{"a": True}, {"b": 2}]).to_py()
        assert result[0]["a"] == 1
        assert result[1]["b"] == 2
        assert type(result[0]["a"]) is int

        assert schema.convert(None).to_py() is None

    @requires_py39
    def test_map_str_array_array_int(self) -> None:
        """Map[str, Array[Array[int]]] 3-level container nesting."""
        result = (
            A(tvm_ffi.Map[str, tuple[tuple[int, ...], ...]])
            .convert({"m": [[True, 1], [False, 2]]})
            .to_py()
        )
        assert [list(row) for row in result["m"]] == [[1, 1], [0, 2]]
        assert all(type(x) is int for row in result["m"] for x in row)

    @requires_py39
    def test_array_array_optional_float(self) -> None:
        """Array[Array[Optional[float]]] deep nesting with None and conversion."""
        result = (
            A(tuple[tuple[Optional[float], ...], ...]).convert([[1, None], [True, 3.14]]).to_py()
        )
        assert list(result[0]) == [1.0, None]
        assert list(result[1]) == [1.0, 3.14]
        assert type(result[0][0]) is float
        assert result[0][1] is None
        assert type(result[1][0]) is float

    @requires_py39
    def test_deep_nesting_failure_propagation(self) -> None:
        """Error from deepest level propagates with full path info."""
        with pytest.raises(TypeError, match=r"value for key 'key'.*element .1..*expected int"):
            A(tvm_ffi.Map[str, tuple[Optional[int], ...]]).check_value({"key": [1, "bad"]})


# ---------------------------------------------------------------------------
# Category 27: FFI container inputs (tvm_ffi.Array/List/Map/Dict)
# ---------------------------------------------------------------------------
class TestFFIContainerInputs:
    @requires_py39
    def test_ffi_array_with_element_conversion(self) -> None:
        """tvm_ffi.Array([True, 2]) passes Array[int] with bool->int conversion."""
        arr = tvm_ffi.Array([True, 2, 3])
        result = A(tuple[int, ...]).convert(arr).to_py()
        assert list(result) == [1, 2, 3]
        assert type(result[0]) is int

    @requires_py39
    def test_ffi_array_any_passthrough(self) -> None:
        """tvm_ffi.Array passes Array[Any] as-is."""
        arr = tvm_ffi.Array([1, "x", None])
        result = A(tuple[typing.Any, ...]).convert(arr).to_py()
        assert result.same_as(arr)

    @requires_py39
    def test_ffi_list_with_list_schema(self) -> None:
        """tvm_ffi.List passes List[int] with conversion."""
        lst = tvm_ffi.List([True, 2])
        result = A(list[int]).convert(lst).to_py()
        assert list(result) == [1, 2]
        assert type(result[0]) is int

    @requires_py39
    def test_ffi_list_accepted_by_array_schema(self) -> None:
        """tvm_ffi.List passes Array schema (C++ allows cross-type via kOtherTypeIndex)."""
        lst = tvm_ffi.List([1, 2])
        A(tuple[int, ...]).check_value(lst)

    @requires_py39
    def test_ffi_array_accepted_by_list_schema(self) -> None:
        """tvm_ffi.Array passes List schema (C++ allows cross-type via kOtherTypeIndex)."""
        arr = tvm_ffi.Array([1, 2])
        A(list[int]).check_value(arr)

    @requires_py39
    def test_ffi_map_with_value_conversion(self) -> None:
        """tvm_ffi.Map passes Map[str, int] with bool->int conversion."""
        m = tvm_ffi.Map({"a": True, "b": 2})
        result = A(tvm_ffi.Map[str, int]).convert(m).to_py()
        assert result["a"] == 1
        assert result["b"] == 2
        assert type(result["a"]) is int

    @requires_py39
    def test_ffi_map_any_any_passthrough(self) -> None:
        """tvm_ffi.Map passes Map[Any, Any] as-is."""
        m = tvm_ffi.Map({"a": 1})
        result = A(tvm_ffi.Map[typing.Any, typing.Any]).convert(m).to_py()
        assert result.same_as(m)

    @requires_py39
    def test_ffi_dict_with_dict_schema(self) -> None:
        """tvm_ffi.Dict passes Dict[str, float] with int->float conversion."""
        d = tvm_ffi.Dict({"x": 1, "y": 2})
        result = A(dict[str, float]).convert(d).to_py()
        assert result["x"] == 1.0
        assert result["y"] == 2.0
        assert type(result["x"]) is float

    @requires_py39
    def test_ffi_dict_accepted_by_map_schema(self) -> None:
        """tvm_ffi.Dict passes Map schema (C++ allows cross-type via kOtherTypeIndex)."""
        d = tvm_ffi.Dict({"a": 1})
        A(tvm_ffi.Map[str, int]).check_value(d)

    @requires_py39
    def test_ffi_map_accepted_by_dict_schema(self) -> None:
        """tvm_ffi.Map passes Dict schema (C++ allows cross-type via kOtherTypeIndex)."""
        m = tvm_ffi.Map({"a": 1})
        A(dict[str, int]).check_value(m)

    @requires_py39
    def test_ffi_array_nested_optional_float(self) -> None:
        """tvm_ffi.Array with nested Optional[float] conversion."""
        arr = tvm_ffi.Array([1, None, True])
        result = A(tuple[Optional[float], ...]).convert(arr).to_py()
        assert list(result) == [1.0, None, 1.0]
        assert type(result[0]) is float
        assert result[1] is None

    @requires_py39
    def test_ffi_map_nested_array_int(self) -> None:
        """tvm_ffi.Map with value being a Python list, converted as Array[int]."""
        # Map values are already stored; create a map with array values
        m = tvm_ffi.Map({"k": tvm_ffi.Array([True, 2])})
        result = A(tvm_ffi.Map[str, tuple[int, ...]]).convert(m).to_py()
        assert list(result["k"]) == [1, 2]
        assert type(result["k"][0]) is int

    @requires_py39
    def test_ffi_array_wrong_element_type(self) -> None:
        """tvm_ffi.Array with wrong element type gives clear error."""
        arr = tvm_ffi.Array([1, "bad", 3])
        with pytest.raises(TypeError, match=r"element \[1\].*expected int"):
            A(tuple[int, ...]).check_value(arr)

    @requires_py39
    def test_ffi_map_wrong_value_type(self) -> None:
        """tvm_ffi.Map with wrong value type gives clear error."""
        m = tvm_ffi.Map({"a": 1, "b": "bad"})
        with pytest.raises(TypeError, match=r"value for key.*expected int"):
            A(tvm_ffi.Map[str, int]).check_value(m)

    def test_ffi_array_object_schema(self) -> None:
        """tvm_ffi.Array passes Object schema (it is a CObject)."""
        arr = tvm_ffi.Array([1, 2])
        A(tvm_ffi.core.Object).check_value(arr)

    def test_ffi_map_object_schema(self) -> None:
        """tvm_ffi.Map passes Object schema (it is a CObject)."""
        m = tvm_ffi.Map({"a": 1})
        A(tvm_ffi.core.Object).check_value(m)


# ---------------------------------------------------------------------------
# Category 28: Mixed Python and FFI containers in nesting
# ---------------------------------------------------------------------------
class TestMixedPythonFFIContainers:
    @requires_py39
    def test_python_list_of_ffi_arrays(self) -> None:
        """Python list containing tvm_ffi.Array elements, Array[Array[int]]."""
        inner1 = tvm_ffi.Array([True, 2])
        inner2 = tvm_ffi.Array([3, False])
        result = A(tuple[tuple[int, ...], ...]).convert([inner1, inner2]).to_py()
        assert [list(row) for row in result] == [[1, 2], [3, 0]]

    @requires_py39
    def test_python_dict_with_ffi_array_values(self) -> None:
        """Python dict with tvm_ffi.Array values, Map[str, Array[float]]."""
        val = tvm_ffi.Array([1, True])
        result = A(tvm_ffi.Map[str, tuple[float, ...]]).convert({"k": val}).to_py()
        assert list(result["k"]) == [1.0, 1.0]
        assert all(type(x) is float for x in result["k"])

    @requires_py39
    def test_ffi_map_with_python_list_in_union(self) -> None:
        """Union[Map[str, int], Array[int]] with tvm_ffi.Map input."""
        schema = A(Union[tvm_ffi.Map[str, int], tuple[int, ...]])
        m = tvm_ffi.Map({"a": True})
        result = schema.convert(m).to_py()
        assert result["a"] == 1
        assert type(result["a"]) is int

    @requires_py39
    def test_ffi_array_in_optional(self) -> None:
        """Optional[Array[int]] with tvm_ffi.Array input."""
        arr = tvm_ffi.Array([True, 2])
        result = A(Optional[tuple[int, ...]]).convert(arr).to_py()
        assert list(result) == [1, 2]
        assert type(result[0]) is int


# ---------------------------------------------------------------------------
# Category 29: Error propagation through deeply nested FFI containers
# ---------------------------------------------------------------------------
class TestNestedErrorPropagation:
    @requires_py39
    def test_array_array_int_inner_failure(self) -> None:
        """Error path: Array[Array[int]] -> element [1] -> element [0]."""
        with pytest.raises(TypeError, match=r"element \[1\].*element \[0\].*expected int, got str"):
            A(tuple[tuple[int, ...], ...]).convert([[1], ["bad"]])

    @requires_py39
    def test_map_array_int_inner_failure(self) -> None:
        """Error path: Map -> value for key 'k' -> element [2]."""
        with pytest.raises(
            TypeError,
            match=r"value for key 'k'.*element \[2\].*expected int, got str",
        ):
            A(tvm_ffi.Map[str, tuple[int, ...]]).convert({"k": [1, 2, "bad"]})

    @requires_py39
    def test_array_map_int_inner_failure(self) -> None:
        """Error path: Array -> element [0] -> value for key 'x'."""
        with pytest.raises(
            TypeError,
            match=r"element \[0\].*value for key 'x'.*expected int, got str",
        ):
            A(tuple[tvm_ffi.Map[str, int], ...]).convert([{"x": "bad"}])

    @requires_py39
    def test_optional_array_int_inner_failure(self) -> None:
        """Error path through Optional -> Array -> element."""
        with pytest.raises(TypeError, match=r"element \[1\].*expected int, got str"):
            A(Optional[tuple[int, ...]]).convert([1, "bad"])

    @requires_py39
    def test_tuple_array_int_inner_failure(self) -> None:
        """Error path: tuple -> element [0] -> element [1]."""
        with pytest.raises(TypeError, match=r"element \[0\].*element \[1\].*expected int, got str"):
            A(tuple[tuple[int, ...], str]).convert(([1, "bad"], "ok"))

    @requires_py39
    def test_deep_3_level_error(self) -> None:
        """Error at 3 levels deep: Map -> Array -> Optional -> type mismatch."""
        with pytest.raises(TypeError, match=r"value for key 'key'.*element .1..*expected int"):
            A(tvm_ffi.Map[str, tuple[Optional[int], ...]]).check_value({"key": [1, "bad"]})

    @requires_py39
    def test_ffi_array_nested_error(self) -> None:
        """Error from tvm_ffi.Array in nested context."""
        arr = tvm_ffi.Array([1, "bad", 3])
        with pytest.raises(TypeError, match=r"element \[1\].*expected int"):
            A(tuple[int, ...]).convert(arr)


# ---------------------------------------------------------------------------
# Category 30: Custom object type exact match
# ---------------------------------------------------------------------------
class TestCustomObjectExactMatch:
    def test_test_int_pair_pass(self) -> None:
        """TestIntPair passes TypeSchema('testing.TestIntPair')."""
        obj = TestIntPair(1, 2)
        A(TestIntPair).check_value(obj)

    def test_test_object_base_pass(self) -> None:
        """TestObjectBase passes its own schema."""
        obj = TestObjectBase(v_i64=10, v_f64=1.5, v_str="hi")
        A(TestObjectBase).check_value(obj)

    def test_test_object_derived_pass(self) -> None:
        """TestObjectDerived passes its own schema."""
        obj = TestObjectDerived(v_map={"a": 1}, v_array=[1], v_i64=0, v_f64=0.0, v_str="")
        A(TestObjectDerived).check_value(obj)

    def test_cxx_class_base_pass(self) -> None:
        """_TestCxxClassBase passes its own schema."""
        obj = _TestCxxClassBase(v_i64=1, v_i32=2)
        A(_TestCxxClassBase).check_value(obj)

    def test_cxx_class_derived_pass(self) -> None:
        """_TestCxxClassDerived passes its own schema."""
        obj = _TestCxxClassDerived(v_i64=1, v_i32=2, v_f64=3.0)
        A(_TestCxxClassDerived).check_value(obj)

    def test_cxx_class_derived_derived_pass(self) -> None:
        """_TestCxxClassDerivedDerived passes its own schema."""
        obj = _TestCxxClassDerivedDerived(v_i64=1, v_i32=2, v_f64=3.0, v_bool=True)
        A(_TestCxxClassDerivedDerived).check_value(obj)


# ---------------------------------------------------------------------------
# Category 31: Custom object type hierarchy (subclass passes parent schema)
# ---------------------------------------------------------------------------
class TestCustomObjectHierarchy:
    def test_derived_passes_base_schema(self) -> None:
        """TestObjectDerived passes TypeSchema('testing.TestObjectBase')."""
        obj = TestObjectDerived(v_map={"a": 1}, v_array=[1], v_i64=0, v_f64=0.0, v_str="")
        A(TestObjectBase).check_value(obj)

    def test_derived_passes_object_schema(self) -> None:
        """TestObjectDerived passes TypeSchema('Object')."""
        obj = TestObjectDerived(v_map={"a": 1}, v_array=[1], v_i64=0, v_f64=0.0, v_str="")
        A(tvm_ffi.core.Object).check_value(obj)

    def test_cxx_derived_passes_base(self) -> None:
        """_TestCxxClassDerived passes TestCxxClassBase schema."""
        obj = _TestCxxClassDerived(v_i64=1, v_i32=2, v_f64=3.0)
        A(_TestCxxClassBase).check_value(obj)

    def test_cxx_derived_derived_passes_base(self) -> None:
        """_TestCxxClassDerivedDerived passes TestCxxClassBase schema (2-level up)."""
        obj = _TestCxxClassDerivedDerived(v_i64=1, v_i32=2, v_f64=3.0, v_bool=True)
        A(_TestCxxClassBase).check_value(obj)

    def test_cxx_derived_derived_passes_derived(self) -> None:
        """_TestCxxClassDerivedDerived passes TestCxxClassDerived schema (1-level up)."""
        obj = _TestCxxClassDerivedDerived(v_i64=1, v_i32=2, v_f64=3.0, v_bool=True)
        A(_TestCxxClassDerived).check_value(obj)

    def test_all_custom_objects_pass_object_schema(self) -> None:
        """Every custom object passes the generic Object schema."""
        objs = [
            TestIntPair(1, 2),
            TestObjectBase(v_i64=10, v_f64=1.5, v_str="hi"),
            _TestCxxClassBase(v_i64=1, v_i32=2),
            _TestCxxClassDerived(v_i64=1, v_i32=2, v_f64=3.0),
            _TestCxxClassDerivedDerived(v_i64=1, v_i32=2, v_f64=3.0, v_bool=True),
        ]
        schema = A(tvm_ffi.core.Object)
        for obj in objs:
            schema.check_value(obj)


# ---------------------------------------------------------------------------
# Category 32: Custom object type rejection
# ---------------------------------------------------------------------------
class TestCustomObjectRejection:
    def test_wrong_object_type(self) -> None:
        """TestIntPair fails TypeSchema('testing.TestObjectBase')."""
        obj = TestIntPair(1, 2)
        with pytest.raises(TypeError, match=r"testing.TestIntPair"):
            A(TestObjectBase).check_value(obj)

    def test_base_fails_derived_schema(self) -> None:
        """Parent object fails child schema (TestObjectBase fails TestObjectDerived)."""
        obj = TestObjectBase(v_i64=10, v_f64=1.5, v_str="hi")
        with pytest.raises(TypeError, match=r"testing.TestObjectBase"):
            A(TestObjectDerived).check_value(obj)

    def test_non_object_fails_custom_schema(self) -> None:
        """Plain int fails custom object schema."""
        with pytest.raises(TypeError, match=r"expected testing\.TestIntPair.*got int"):
            A(TestIntPair).check_value(42)

    def test_none_fails_custom_schema(self) -> None:
        """None fails custom object schema."""
        with pytest.raises(TypeError, match="got None"):
            A(TestIntPair).check_value(None)

    def test_string_fails_custom_schema(self) -> None:
        """String fails custom object schema."""
        with pytest.raises(TypeError, match="got str"):
            A(TestIntPair).check_value("hello")

    def test_cxx_base_fails_derived_schema(self) -> None:
        """_TestCxxClassBase fails _TestCxxClassDerived schema."""
        obj = _TestCxxClassBase(v_i64=1, v_i32=2)
        with pytest.raises(TypeError):
            A(_TestCxxClassDerived).check_value(obj)

    def test_sibling_types_reject_each_other(self) -> None:
        """TestIntPair and TestCxxClassBase are unrelated -- reject each other."""
        pair = TestIntPair(1, 2)
        base = _TestCxxClassBase(v_i64=1, v_i32=2)
        with pytest.raises(TypeError):
            A(_TestCxxClassBase).check_value(pair)
        with pytest.raises(TypeError):
            A(TestIntPair).check_value(base)


# ---------------------------------------------------------------------------
# Category 33: Custom objects in containers
# ---------------------------------------------------------------------------
class TestCustomObjectInContainers:
    @requires_py39
    def test_array_of_custom_objects(self) -> None:
        """Array[testing.TestIntPair] with matching elements."""
        objs = [TestIntPair(1, 2), TestIntPair(3, 4)]
        A(tuple[TestIntPair, ...]).check_value(objs)

    @requires_py39
    def test_array_of_custom_objects_wrong_type(self) -> None:
        """Array[testing.TestIntPair] with wrong element type fails."""
        objs = [TestIntPair(1, 2), _TestCxxClassBase(v_i64=1, v_i32=2)]
        with pytest.raises(TypeError, match=r"element \[1\]"):
            A(tuple[TestIntPair, ...]).check_value(objs)

    @requires_py39
    def test_array_of_base_with_derived_elements(self) -> None:
        """Array[testing.TestObjectBase] accepts derived elements via hierarchy."""
        base = TestObjectBase(v_i64=1, v_f64=1.0, v_str="a")
        derived = TestObjectDerived(v_map={"a": 1}, v_array=[1], v_i64=0, v_f64=0.0, v_str="")
        A(tuple[TestObjectBase, ...]).check_value([base, derived])

    @requires_py39
    def test_map_str_to_custom_object(self) -> None:
        """Map[str, testing.TestIntPair] pass."""
        objs = {"a": TestIntPair(1, 2), "b": TestIntPair(3, 4)}
        A(tvm_ffi.Map[str, TestIntPair]).check_value(objs)

    @requires_py39
    def test_map_str_to_custom_object_wrong_value(self) -> None:
        """Map[str, testing.TestIntPair] with int value fails."""
        data = {"a": TestIntPair(1, 2), "b": 42}
        with pytest.raises(TypeError, match="value for key 'b'"):
            A(tvm_ffi.Map[str, TestIntPair]).check_value(data)

    @requires_py39
    def test_ffi_array_of_custom_objects(self) -> None:
        """tvm_ffi.Array of custom objects passes Array[Object]."""
        arr = tvm_ffi.Array([TestIntPair(1, 2), TestObjectBase(v_i64=1, v_f64=2.0, v_str="s")])
        A(tuple[tvm_ffi.core.Object, ...]).check_value(arr)

    @requires_py39
    def test_ffi_array_of_custom_objects_specific_type(self) -> None:
        """tvm_ffi.Array of TestIntPair passes Array[testing.TestIntPair]."""
        arr = tvm_ffi.Array([TestIntPair(1, 2), TestIntPair(3, 4)])
        A(tuple[TestIntPair, ...]).check_value(arr)

    @requires_py39
    def test_ffi_map_with_custom_object_values(self) -> None:
        """tvm_ffi.Map with custom object values passes."""
        m = tvm_ffi.Map({"x": TestIntPair(1, 2), "y": TestIntPair(3, 4)})
        A(tvm_ffi.Map[str, TestIntPair]).check_value(m)


# ---------------------------------------------------------------------------
# Category 34: Optional/Union with custom objects
# ---------------------------------------------------------------------------
class TestCustomObjectOptionalUnion:
    def test_optional_custom_object_with_value(self) -> None:
        """Optional[testing.TestIntPair] with actual object."""
        obj = TestIntPair(1, 2)
        A(Optional[TestIntPair]).check_value(obj)

    def test_optional_custom_object_with_none(self) -> None:
        """Optional[testing.TestIntPair] with None."""
        A(Optional[TestIntPair]).check_value(None)

    def test_optional_custom_object_wrong_type(self) -> None:
        """Optional[testing.TestIntPair] with wrong object type."""
        obj = _TestCxxClassBase(v_i64=1, v_i32=2)
        with pytest.raises(TypeError):
            A(Optional[TestIntPair]).check_value(obj)

    def test_union_custom_object_and_int(self) -> None:
        """Union[testing.TestIntPair, int] with object."""
        obj = TestIntPair(1, 2)
        A(Union[TestIntPair, int]).check_value(obj)

    def test_union_custom_object_and_int_with_int(self) -> None:
        """Union[testing.TestIntPair, int] with int."""
        A(Union[TestIntPair, int]).check_value(42)

    def test_union_custom_object_and_int_with_wrong(self) -> None:
        """Union[testing.TestIntPair, int] with str fails."""
        with pytest.raises(TypeError):
            A(Union[TestIntPair, int]).check_value("bad")

    def test_union_two_custom_objects(self) -> None:
        """Union of two custom types accepts both."""
        pair = TestIntPair(1, 2)
        base = _TestCxxClassBase(v_i64=1, v_i32=2)
        schema = A(Union[TestIntPair, _TestCxxClassBase])
        schema.check_value(pair)
        schema.check_value(base)

    def test_union_two_custom_objects_rejects_third(self) -> None:
        """Union of two custom types rejects a third."""
        obj = TestObjectBase(v_i64=1, v_f64=2.0, v_str="s")
        with pytest.raises(TypeError):
            A(Union[TestIntPair, _TestCxxClassBase]).check_value(obj)


# ---------------------------------------------------------------------------
# Category 35: Custom objects with from_type_index
# ---------------------------------------------------------------------------
class TestCustomObjectFromTypeIndex:
    def test_from_type_index_custom_object(self) -> None:
        """from_type_index resolves a custom object type and validates."""
        obj = TestIntPair(1, 2)
        tindex = tvm_ffi.core._object_type_key_to_index("testing.TestIntPair")
        assert tindex is not None
        schema = TypeSchema.from_type_index(tindex)
        assert schema.origin == "testing.TestIntPair"
        schema.check_value(obj)

    def test_from_type_index_rejects_wrong_object(self) -> None:
        """from_type_index schema rejects wrong object type."""
        tindex = tvm_ffi.core._object_type_key_to_index("testing.TestIntPair")
        assert tindex is not None
        schema = TypeSchema.from_type_index(tindex)
        with pytest.raises(TypeError):
            schema.check_value(_TestCxxClassBase(v_i64=1, v_i32=2))

    def test_from_type_index_hierarchy(self) -> None:
        """from_type_index for base type accepts derived objects."""
        tindex = tvm_ffi.core._object_type_key_to_index("testing.TestObjectBase")
        assert tindex is not None
        schema = TypeSchema.from_type_index(tindex)
        derived = TestObjectDerived(v_map={"a": 1}, v_array=[1], v_i64=0, v_f64=0.0, v_str="")
        schema.check_value(derived)


# ---------------------------------------------------------------------------
# Category 36: Custom objects in nested containers
# ---------------------------------------------------------------------------
class TestCustomObjectNestedContainers:
    @requires_py39
    def test_array_of_optional_custom_object(self) -> None:
        """Array[Optional[testing.TestIntPair]] with mix of objects and None."""
        data = [TestIntPair(1, 2), None, TestIntPair(3, 4)]
        A(tuple[Optional[TestIntPair], ...]).check_value(data)

    @requires_py39
    def test_map_str_to_array_of_custom_objects(self) -> None:
        """Map[str, Array[testing.TestIntPair]] with nested objects."""
        data = {
            "group1": [TestIntPair(1, 2), TestIntPair(3, 4)],
            "group2": [TestIntPair(5, 6)],
        }
        A(tvm_ffi.Map[str, tuple[TestIntPair, ...]]).check_value(data)

    @requires_py39
    def test_array_of_union_custom_objects(self) -> None:
        """Array[Union[testing.TestIntPair, testing.TestCxxClassBase]]."""
        data = [TestIntPair(1, 2), _TestCxxClassBase(v_i64=1, v_i32=2), TestIntPair(5, 6)]
        A(tuple[Union[TestIntPair, _TestCxxClassBase], ...]).check_value(data)

    @requires_py39
    def test_optional_array_of_custom_objects(self) -> None:
        """Optional[Array[testing.TestIntPair]] with array."""
        data = [TestIntPair(1, 2)]
        A(Optional[tuple[TestIntPair, ...]]).check_value(data)

    @requires_py39
    def test_optional_array_of_custom_objects_none(self) -> None:
        """Optional[Array[testing.TestIntPair]] with None."""
        A(Optional[tuple[TestIntPair, ...]]).check_value(None)

    @requires_py39
    def test_nested_error_with_custom_object(self) -> None:
        """Array[testing.TestIntPair] error message includes type keys."""
        data = [TestIntPair(1, 2), _TestCxxClassBase(v_i64=1, v_i32=2)]
        with pytest.raises(
            TypeError, match=r"element \[1\].*testing.TestIntPair.*testing.TestCxxClassBase"
        ):
            A(tuple[TestIntPair, ...]).check_value(data)

    @requires_py39
    def test_map_nested_error_with_custom_object(self) -> None:
        """Map value error for custom object includes key and type info."""
        data = {"ok": TestIntPair(1, 2), "bad": 42}
        with pytest.raises(
            TypeError, match=r"value for key 'bad'.*expected testing\.TestIntPair.*got int"
        ):
            A(tvm_ffi.Map[str, TestIntPair]).check_value(data)

    @requires_py39
    def test_deep_nested_custom_objects(self) -> None:
        """Map[str, Array[Optional[testing.TestIntPair]]] deep nesting."""
        data = {
            "a": [TestIntPair(1, 2), None],
            "b": [None, TestIntPair(3, 4), TestIntPair(5, 6)],
        }
        A(tvm_ffi.Map[str, tuple[Optional[TestIntPair], ...]]).check_value(data)

    @requires_py39
    def test_deep_nested_custom_objects_error(self) -> None:
        """Map[str, Array[testing.TestIntPair]] error at 3 levels."""
        data = {"k": [TestIntPair(1, 2), "bad"]}
        with pytest.raises(TypeError, match=r"value for key 'k'.*element .1."):
            A(tvm_ffi.Map[str, tuple[TestIntPair, ...]]).check_value(data)

    @requires_py39
    def test_tuple_with_custom_object(self) -> None:
        """tuple[testing.TestIntPair, int, str] with custom object."""
        data = (TestIntPair(1, 2), 42, "hello")
        A(tuple[TestIntPair, int, str]).check_value(data)

    @requires_py39
    def test_tuple_with_custom_object_wrong(self) -> None:
        """tuple[testing.TestIntPair, int] with wrong object in first position."""
        data = (_TestCxxClassBase(v_i64=1, v_i32=2), 42)
        with pytest.raises(TypeError, match=r"element \[0\]"):
            A(tuple[TestIntPair, int]).check_value(data)
