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

import pickle

import tvm_ffi


def test_string() -> None:
    fecho = tvm_ffi.get_global_func("testing.echo")
    s = tvm_ffi.core.String("hello")
    s2 = fecho(s)
    assert s2 == "hello"
    s3 = tvm_ffi.convert("hello")
    assert isinstance(s3, str)

    x = "hello long string"
    assert fecho(x) == x

    s4 = pickle.loads(pickle.dumps(s))
    assert s4 == "hello"


def test_bytes() -> None:
    fecho = tvm_ffi.get_global_func("testing.echo")
    b = tvm_ffi.core.Bytes(b"hello")
    assert isinstance(b, tvm_ffi.core.Bytes)
    b2 = fecho(b)
    assert b2 == b"hello"

    b3 = tvm_ffi.convert(b"hello")
    assert isinstance(b3, tvm_ffi.core.Bytes)
    assert isinstance(b3, bytes)

    b4 = tvm_ffi.convert(bytearray(b"hello"))
    assert isinstance(b4, tvm_ffi.core.Bytes)
    assert isinstance(b4, bytes)

    b5 = pickle.loads(pickle.dumps(b))
    assert b5 == b"hello"
    assert isinstance(b5, tvm_ffi.core.Bytes)


def test_string_find_substr() -> None:
    s = tvm_ffi.core.String("hello world")
    assert s.find("world") == 6
    assert s.find("hello") == 0
    assert s.find("o") == 4
    assert s.find("o", 5) == 7
    assert s.find("notfound") == -1
    assert s.find("") == 0
    assert s.find("", 5) == 5
    assert s.find("", 11) == 11
    assert s.find("", 20) == -1

    assert s[6:11] == "world"
    assert s[0:5] == "hello"
    assert s[6:] == "world"
    assert s[:5] == "hello"


def test_small_str_to_object_ref() -> None:
    """Small strings (<=7 bytes) should be accepted by ObjectRef parameters."""
    f = tvm_ffi.get_global_func("testing.schema_id_object")
    # Small string (uses inline kTVMFFISmallStr storage)
    result = f("small")
    assert result == "small"
    # Empty string (smallest possible small string)
    result = f("")
    assert result == ""
    # Exactly 7 bytes (max small string length)
    result = f("1234567")
    assert result == "1234567"
    # 8 bytes (crosses into heap-allocated kTVMFFIStr)
    result = f("12345678")
    assert result == "12345678"
    # Long string (already heap-allocated, should still work)
    result = f("long long string")
    assert result == "long long string"


def test_small_bytes_to_object_ref() -> None:
    """Small bytes (<=7 bytes) should be accepted by ObjectRef parameters."""
    f = tvm_ffi.get_global_func("testing.schema_id_object")
    result = f(b"small")
    assert result == b"small"
    result = f(b"")
    assert result == b""
    result = f(b"1234567")
    assert result == b"1234567"
    result = f(b"12345678")
    assert result == b"12345678"
