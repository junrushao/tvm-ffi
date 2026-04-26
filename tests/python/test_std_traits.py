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
"""Tests for trait-driven printing of ``tvm_ffi.std`` nodes."""

from __future__ import annotations

import tvm_ffi as ffi
from tvm_ffi import pyast, std


def _int_imm(value: int) -> std.IntImm:
    return std.IntImm(std.AnyTy(), value)


def _i32() -> std.PrimTy:
    return std.PrimTy(ffi.dtype("int32"))


def test_std_expr_and_range_printing() -> None:
    x = std.Value(ty=_i32(), name="x")
    y = std.Value(ty=_i32(), name="y")
    buffer = std.Value(
        ty=std.TensorTy([_int_imm(4)], ffi.dtype("int32")),
        name="A",
    )

    assert pyast.to_python(std.Add._make(x, y)) == "x + y"
    assert (
        pyast.to_python(
            std.Load(ty=_i32(), value=buffer, indices=[std.Range(_int_imm(0), _int_imm(10), None)])
        )
        == "A[0:10]"
    )


def test_std_dtype_names_print_short() -> None:
    shape = [_int_imm(4)]

    assert pyast.to_python(std.PrimTy(ffi.dtype("int32"))) == "std.i32"
    assert pyast.to_python(std.TensorTy(shape, ffi.dtype("float32"))) == "f32[4]"
    assert pyast.to_python(std.TensorTy(shape, ffi.dtype("uint32"))) == "u32[4]"
    assert pyast.to_python(std.TensorTy(shape, ffi.dtype("bfloat16"))) == "bf16[4]"


def test_std_func_and_module_printing() -> None:
    buffer = std.Value(
        ty=std.TensorTy([_int_imm(4)], ffi.dtype("int32")),
        name="A",
    )
    x = std.Value(ty=_i32(), name="x")
    func = std.Func(
        symbol="f",
        args=[buffer, x],
        ret_type=None,
        body=[
            std.Store(value=buffer, indices=[std.Range(_int_imm(0), None, None)], rhs=x),
            std.Return([x]),
        ],
        attrs=std.DictAttrs(values={"private": True, "tag": "nms"}),
    )

    assert (
        pyast.to_python(func)
        == """
@std.function(private=True, tag="nms")
def f(A: i32[4], x: std.i32):
  A[0] = x
  return x
""".strip()
    )
    assert (
        pyast.to_python(std.Module([func]))
        == """
@std.ir_module
class Module:
  @std.function(private=True, tag="nms")
  def f(A: i32[4], x: std.i32):
    A[0] = x
    return x
""".strip()
    )


def test_std_attrs_print_as_dict_literal() -> None:
    assert pyast.to_python(std.Attrs()) == "{}"
    assert pyast.to_python(std.DictAttrs(values={"z": 1, "a": 2})) == '{"a": 2, "z": 1}'
