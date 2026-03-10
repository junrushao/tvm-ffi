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
from typing import Callable

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
