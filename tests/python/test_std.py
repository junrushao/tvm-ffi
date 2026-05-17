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

from __future__ import annotations

from typing import Any, cast

import pytest
import tvm_ffi
from tvm_ffi import core, pyast, std
from tvm_ffi.access_path import AccessPath
from tvm_ffi.dataclasses import fields


class TestAnyTy:
    def test_constructor(self) -> None:
        node = std.AnyTy()

        assert isinstance(node, std.AnyTy)
        assert tuple(field.name for field in fields(std.AnyTy)) == ()

    def test_text_format(self) -> None:
        node = std.AnyTy()

        assert node.text() == "std.Any"

    def test_structural_equality(self) -> None:
        lhs = std.AnyTy()
        rhs = std.AnyTy()
        different = std.PrimTy("int32")

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestPrimTy:
    def test_constructor(self) -> None:
        node = std.PrimTy("int32")

        assert isinstance(node, std.PrimTy)
        assert tuple(field.name for field in fields(std.PrimTy)) == ("dtype",)
        assert node.dtype == tvm_ffi.int32

    def test_constructor_accepts_dtype_aliases(self) -> None:
        assert std.PrimTy("i32").dtype == tvm_ffi.int32
        assert std.PrimTy("f32").dtype == tvm_ffi.float32
        assert std.PrimTy("bf16").dtype == tvm_ffi.bfloat16

    def test_text_format(self) -> None:
        node = std.PrimTy("int32")

        assert node.text() == "std.i32"
        assert std.PrimTy("float16").text() == "std.f16"
        assert std.PrimTy("bfloat16").text() == "std.bf16"
        assert std.PrimTy("uint8").text() == "std.u8"
        assert std.PrimTy("float8_e4m3fn").text() == "std.f8_e4m3fn"

    def test_dialect_print_map(self) -> None:
        node = std.PrimTy("int32")

        assert node.text(pyast.PrinterConfig(dialect_print_map={"std": "*"})) == "i32"
        assert node.text(pyast.PrinterConfig(dialect_print_map={"std": "core"})) == "core.i32"

    def test_structural_equality(self) -> None:
        lhs = std.PrimTy("int32")
        rhs = std.PrimTy("int32")
        different = std.PrimTy("float32")

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestAttrs:
    def test_from_any_converts_none_to_empty_dict_attrs(self) -> None:
        node = core._to_py_class_value(core.TypeSchema.from_annotation(std.Attrs).convert(None))

        assert isinstance(node, std.DictAttrs)
        assert dict(node.values) == {}
        assert node.text() == "std.DictAttrs()"

    def test_from_any_converts_python_dict_to_dict_attrs(self) -> None:
        node = core._to_py_class_value(
            core.TypeSchema.from_annotation(std.Attrs).convert({"tag": "demo"})
        )

        assert isinstance(node, std.DictAttrs)
        assert dict(node.values) == {"tag": "demo"}
        assert node.text() == 'std.DictAttrs(tag="demo")'


class TestAggregate:
    def test_range_is_aggregate(self) -> None:
        node = std.Range(start=1)

        assert isinstance(node, std.Aggregate)
        assert issubclass(std.Range, std.Aggregate)
        assert tuple(field.name for field in fields(std.Aggregate)) == ()


class TestTupleTy:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        f32 = std.PrimTy("float32")
        node = std.TupleTy(fields=[i32, f32])

        assert isinstance(node, std.TupleTy)
        assert tuple(field.name for field in fields(std.TupleTy)) == ("fields",)
        assert list(node.fields) == [i32, f32]

    def test_text_format(self) -> None:
        node = std.TupleTy(fields=[std.PrimTy("int32"), std.PrimTy("float32")])

        assert node.text() == "std.Tuple[std.i32, std.f32]"

    def test_structural_equality(self) -> None:
        lhs = std.TupleTy(fields=[std.PrimTy("int32"), std.PrimTy("float32")])
        rhs = std.TupleTy(fields=[std.PrimTy("int32"), std.PrimTy("float32")])
        different = std.TupleTy(fields=[std.PrimTy("int32")])

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestTensorTy:
    def test_constructor(self) -> None:
        node = std.TensorTy(shape=[1, 2], dtype="float32")

        assert isinstance(node, std.TensorTy)
        assert tuple(field.name for field in fields(std.TensorTy)) == ("shape", "dtype")
        shape = list(node.shape)
        assert isinstance(shape[0], std.IntImm)
        assert isinstance(shape[1], std.IntImm)
        assert shape[0].value == 1
        assert shape[1].value == 2
        assert node.dtype == tvm_ffi.float32

    def test_text_format(self) -> None:
        node = std.TensorTy(
            shape=[1, 2],
            dtype="float32",
        )

        assert node.text() == "std.f32[1, 2]"
        assert (
            std.TensorTy(
                shape=[14, 21],
                dtype="int32",
            ).text()
            == "std.i32[14, 21]"
        )

    def test_structural_equality(self) -> None:
        lhs = std.TensorTy(
            shape=[1, 2],
            dtype="float32",
        )
        rhs = std.TensorTy(
            shape=[1, 2],
            dtype="float32",
        )
        different = std.TensorTy(shape=[2], dtype="float32")

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestExpr:
    def test_from_any_converts_python_bool_to_bool_imm(self) -> None:
        node = core._to_py_class_value(core.TypeSchema.from_annotation(std.Expr).convert(True))

        assert isinstance(node, std.BoolImm)
        assert isinstance(node.ty, std.AnyTy)
        assert node.value is True
        assert node.text() == "True"

    def test_from_any_converts_python_int_to_int_imm(self) -> None:
        node = core._to_py_class_value(core.TypeSchema.from_annotation(std.Expr).convert(7))

        assert isinstance(node, std.IntImm)
        assert isinstance(node.ty, std.AnyTy)
        assert node.value == 7
        assert node.text() == "7"

    def test_from_any_converts_python_float_to_float_imm(self) -> None:
        node = core._to_py_class_value(core.TypeSchema.from_annotation(std.Expr).convert(1.5))

        assert isinstance(node, std.FloatImm)
        assert isinstance(node.ty, std.AnyTy)
        assert node.value == 1.5
        assert node.text() == "1.5"

    def test_from_any_converts_python_string_to_string_imm(self) -> None:
        node = core._to_py_class_value(core.TypeSchema.from_annotation(std.Expr).convert("hello"))

        assert isinstance(node, std.StringImm)
        assert isinstance(node.ty, std.AnyTy)
        assert node.value == "hello"
        assert node.text() == '"hello"'


class TestVar:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Var(ty=i32, name="x")

        assert isinstance(node, std.Var)
        assert tuple(field.name for field in fields(std.Var)) == ("ty", "name")
        assert node.ty == i32
        assert node.name == "x"

    def test_text_format(self) -> None:
        node = std.Var(ty=std.PrimTy("int32"), name="x")

        assert node.text() == "x"

    def test_structural_equality(self) -> None:
        lhs = std.Var(ty=std.PrimTy("int32"), name="x")
        rhs = std.Var(ty=std.PrimTy("int32"), name="renamed")
        different = std.Var(ty=std.PrimTy("float32"), name="x")

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestFunc:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.Func(
            symbol="main",
            attrs={"tag": "demo"},
            args=[x],
            ret_type=i32,
            body=[std.Return(x)],
        )

        assert isinstance(node, std.Func)
        assert tuple(field.name for field in fields(std.Func)) == (
            "attrs",
            "symbol",
            "args",
            "ret_type",
            "body",
        )
        assert node.symbol == "main"
        assert isinstance(node.attrs, std.DictAttrs)
        assert dict(node.attrs.values) == {"tag": "demo"}
        assert list(node.args) == [x]
        assert node.ret_type == i32
        assert len(node.body) == 1

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.Func(
            symbol="main",
            attrs={"tag": "demo"},
            args=[x],
            ret_type=i32,
            body=[std.Return(x)],
        )

        assert node.text() == (
            '@std.func(tag="demo")\ndef main(x: std.i32) -> std.i32:\n  return x'
        )

    def test_text_format_without_return_type(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.Func(
            symbol="main",
            args=[x],
            ret_type=None,
            body=[std.Return(x)],
        )

        assert node.text() == "@std.func\ndef main(x: std.i32):\n  return x"

    def test_text_format_preserves_typed_immediate_operands(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        y = std.Var(ty=i32, name="y")
        node = std.Func(
            symbol="main",
            args=[x],
            ret_type=i32,
            body=[
                std.BindExpr(std.Add(x, std.IntImm(i32, 1), ty=i32), y),
                std.Return(y),
            ],
        )

        assert node.text() == (
            "@std.func\ndef main(x: std.i32) -> std.i32:\n  y = x + std.i32(1)\n  return y"
        )

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs_x = std.Var(ty=i32, name="x")
        rhs_x = std.Var(ty=i32, name="x")
        other_x = std.Var(ty=i32, name="x")
        lhs = std.Func(
            symbol="main",
            attrs={"tag": "demo"},
            args=[lhs_x],
            ret_type=i32,
            body=[std.Return(lhs_x)],
        )
        rhs = std.Func(
            symbol="main",
            attrs={"tag": "demo"},
            args=[rhs_x],
            ret_type=i32,
            body=[std.Return(rhs_x)],
        )
        different = std.Func(
            symbol="other",
            attrs={"tag": "demo"},
            args=[other_x],
            ret_type=i32,
            body=[std.Return(other_x)],
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)

    def test_attrs_defaults_to_none_and_ret_type_is_required(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        func_ctor = cast(Any, std.Func)

        without_attrs = func_ctor(symbol="main", args=[x], ret_type=i32, body=[])
        assert without_attrs.attrs is None

        with pytest.raises(TypeError):
            func_ctor(symbol="main", args=[x], body=[])

        func = std.Func(symbol="main", args=[x], ret_type=None, body=[])
        assert func.attrs is None
        assert func.ret_type is None

    def test_attrs_field_accepts_dict_attrs_and_none(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        attrs = {"tag": "demo"}
        with_attrs = std.Func(
            symbol="main",
            attrs=attrs,
            args=[x],
            ret_type=i32,
            body=[std.Return(x)],
        )
        with_plain_dict_attrs = std.Func(
            symbol="main",
            attrs={"tag": "demo"},
            args=[x],
            ret_type=i32,
            body=[std.Return(x)],
        )
        with_empty_attrs = std.Func(
            symbol="main",
            attrs={},
            args=[x],
            ret_type=i32,
            body=[std.Return(x)],
        )
        without_attrs = std.Func(
            symbol="main",
            args=[x],
            ret_type=i32,
            body=[std.Return(x)],
        )

        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == attrs
        assert isinstance(with_plain_dict_attrs.attrs, std.DictAttrs)
        assert dict(with_plain_dict_attrs.attrs.values) == {"tag": "demo"}
        assert isinstance(with_empty_attrs.attrs, std.DictAttrs)
        assert without_attrs.attrs is None
        assert with_attrs.text() == (
            '@std.func(tag="demo")\ndef main(x: std.i32) -> std.i32:\n  return x'
        )
        assert (
            with_plain_dict_attrs.text()
            == '@std.func(tag="demo")\ndef main(x: std.i32) -> std.i32:\n  return x'
        )
        assert with_empty_attrs.text() == "@std.func\ndef main(x: std.i32) -> std.i32:\n  return x"
        assert without_attrs.text() == "@std.func\ndef main(x: std.i32) -> std.i32:\n  return x"


class TestModule:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        func = std.Func(
            symbol="main",
            attrs={"tag": "demo"},
            args=[x],
            ret_type=i32,
            body=[std.Return(x)],
        )
        node = std.Module(funcs=[func])

        assert isinstance(node, std.Module)
        assert tuple(field.name for field in fields(std.Module)) == ("funcs",)
        assert list(node.funcs) == [func]

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.Module(
            funcs=[
                std.Func(
                    symbol="main",
                    attrs={"tag": "demo"},
                    args=[x],
                    ret_type=i32,
                    body=[std.Return(x)],
                )
            ]
        )

        assert node.text() == (
            '@std.module\nclass MyModule:\n  @std.func(tag="demo")\n'
            "  def main(x: std.i32) -> std.i32:\n    return x"
        )

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs_x = std.Var(ty=i32, name="x")
        rhs_x = std.Var(ty=i32, name="x")
        other_x = std.Var(ty=i32, name="x")
        lhs = std.Module(
            funcs=[
                std.Func(
                    symbol="main",
                    attrs={"tag": "demo"},
                    args=[lhs_x],
                    ret_type=i32,
                    body=[std.Return(lhs_x)],
                )
            ]
        )
        rhs = std.Module(
            funcs=[
                std.Func(
                    symbol="main",
                    attrs={"tag": "demo"},
                    args=[rhs_x],
                    ret_type=i32,
                    body=[std.Return(rhs_x)],
                )
            ]
        )
        different = std.Module(
            funcs=[
                std.Func(
                    symbol="other",
                    attrs={"tag": "demo"},
                    args=[other_x],
                    ret_type=i32,
                    body=[std.Return(other_x)],
                )
            ]
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestRange:
    def test_constructor(self) -> None:
        node = std.Range(start=1, stop=2, step=3)

        assert isinstance(node, std.Range)
        assert tuple(field.name for field in fields(std.Range)) == ("start", "stop", "step")
        assert isinstance(node.start, std.IntImm)
        assert isinstance(node.stop, std.IntImm)
        assert isinstance(node.step, std.IntImm)
        assert node.start.value == 1
        assert node.stop.value == 2
        assert node.step.value == 3

    def test_constructor_without_start(self) -> None:
        node = std.Range(start=None, stop=2, step=3)

        assert isinstance(node, std.Range)
        assert node.start is None
        assert isinstance(node.stop, std.IntImm)
        assert isinstance(node.step, std.IntImm)
        assert node.stop.value == 2
        assert node.step.value == 3

    def test_constructor_single_positional_arg_is_stop(self) -> None:
        node = std.Range(10)

        assert node.start is None
        assert isinstance(node.stop, std.IntImm)
        assert node.stop.value == 10
        assert node.step is None
        assert node.text() == "std.Range(10)"

    def test_stop_only_text_format_is_canonical(self) -> None:
        lhs = std.Range(10)
        rhs = std.Range(None, 10)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert lhs.text() == "std.Range(10)"
        assert rhs.text() == "std.Range(10)"

    def test_from_any_converts_python_int_to_single_point_range(self) -> None:
        node = core._to_py_class_value(core.TypeSchema.from_annotation(std.Range).convert(7))

        assert isinstance(node, std.Range)
        assert isinstance(node.start, std.IntImm)
        assert node.start.value == 7
        assert node.stop is None
        assert node.step is None
        assert node.text() == "std.Range(7, None)"

    def test_text_format(self) -> None:
        node = std.Range(start=1, stop=2, step=3)

        assert node.text() == "std.Range(1, 2, 3)"

    def test_text_format_without_stop_or_step(self) -> None:
        node = std.Range(start=1)

        assert node.text() == "std.Range(1, None)"

    def test_text_format_without_step(self) -> None:
        node = std.Range(start=1, stop=2)

        assert node.text() == "std.Range(1, 2)"

    def test_text_format_without_stop(self) -> None:
        node = std.Range(start=1, step=3)

        assert node.text() == "std.Range(1, None, 3)"

    def test_text_format_without_start(self) -> None:
        node = std.Range(start=None, stop=2, step=3)

        assert node.text() == "std.Range(None, 2, 3)"

    def test_text_format_without_start_or_step(self) -> None:
        node = std.Range(start=None, stop=2)

        assert node.text() == "std.Range(2)"

    def test_text_format_without_start_or_stop(self) -> None:
        node = std.Range(start=None, step=3)

        assert node.text() == "std.Range(None, None, 3)"

    def test_text_format_without_any_part(self) -> None:
        node = std.Range()

        assert node.text() == "std.Range()"

    def test_structural_equality(self) -> None:
        lhs = std.Range(start=1, stop=2, step=3)
        rhs = std.Range(start=1, stop=2, step=3)
        different = std.Range(start=1, stop=2)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)

    def test_structural_equality_without_start(self) -> None:
        lhs = std.Range(start=None, stop=2, step=3)
        rhs = std.Range(start=None, stop=2, step=3)
        different = std.Range(start=1, stop=2, step=3)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)

    def test_default_arguments(self) -> None:
        node = std.Range()

        assert node.start is None
        assert node.stop is None
        assert node.step is None

    def test_rejects_mismatched_concrete_dtypes(self) -> None:
        i32 = std.PrimTy("int32")
        f32 = std.PrimTy("float32")

        with pytest.raises(TypeError, match="does not match previous range operand"):
            std.Range(start=std.IntImm(i32, 1), stop=std.FloatImm(f32, 2.0))

    def test_allows_any_typed_operands(self) -> None:
        any_ty = std.AnyTy()
        f32 = std.PrimTy("float32")
        node = std.Range(start=std.IntImm(any_ty, 1), stop=std.FloatImm(f32, 2.0))

        assert isinstance(node.start, std.IntImm)
        assert isinstance(node.stop, std.FloatImm)


class TestIntImm:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.IntImm(ty=i32, value=1)

        assert isinstance(node, std.IntImm)
        assert tuple(field.name for field in fields(std.IntImm)) == ("ty", "value")
        assert node.ty == i32
        assert node.value == 1

    def test_text_format(self) -> None:
        node = std.IntImm(ty=std.PrimTy("int64"), value=1)

        assert node.text() == "1"

    def test_text_format_preserves_non_default_type(self) -> None:
        node = std.IntImm(ty=std.PrimTy("int32"), value=1)

        assert node.text() == "std.i32(1)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.IntImm(ty=i32, value=1)
        rhs = std.IntImm(ty=i32, value=1)
        different = std.IntImm(ty=i32, value=2)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestBoolImm:
    def test_constructor(self) -> None:
        bool_ty = std.PrimTy("bool")
        node = std.BoolImm(ty=bool_ty, value=True)

        assert isinstance(node, std.BoolImm)
        assert tuple(field.name for field in fields(std.BoolImm)) == ("ty", "value")
        assert node.ty == bool_ty
        assert node.value is True

    def test_text_format(self) -> None:
        assert std.BoolImm(ty=std.PrimTy("bool"), value=True).text() == "True"
        assert std.BoolImm(ty=std.PrimTy("bool"), value=False).text() == "False"

    def test_structural_equality(self) -> None:
        bool_ty = std.PrimTy("bool")
        lhs = std.BoolImm(ty=bool_ty, value=True)
        rhs = std.BoolImm(ty=bool_ty, value=True)
        different = std.BoolImm(ty=bool_ty, value=False)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestFloatImm:
    def test_constructor(self) -> None:
        f32 = std.PrimTy("float32")
        node = std.FloatImm(ty=f32, value=1.5)

        assert isinstance(node, std.FloatImm)
        assert tuple(field.name for field in fields(std.FloatImm)) == ("ty", "value")
        assert node.ty == f32
        assert node.value == 1.5

    def test_text_format(self) -> None:
        node = std.FloatImm(ty=std.PrimTy("float32"), value=1.5)

        assert node.text() == "1.5"

    def test_text_format_preserves_non_default_type(self) -> None:
        node = std.FloatImm(ty=std.PrimTy("float64"), value=1.5)

        assert node.text() == "std.f64(1.5)"

    def test_structural_equality(self) -> None:
        f32 = std.PrimTy("float32")
        lhs = std.FloatImm(ty=f32, value=1.5)
        rhs = std.FloatImm(ty=f32, value=1.5)
        different = std.FloatImm(ty=f32, value=2.5)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestStringImm:
    def test_constructor(self) -> None:
        any_ty = std.AnyTy()
        node = std.StringImm(ty=any_ty, value="hello")

        assert isinstance(node, std.StringImm)
        assert tuple(field.name for field in fields(std.StringImm)) == ("ty", "value")
        assert node.ty == any_ty
        assert node.value == "hello"

    def test_text_format(self) -> None:
        node = std.StringImm(ty=std.AnyTy(), value="hello")

        assert node.text() == '"hello"'

    def test_structural_equality(self) -> None:
        any_ty = std.AnyTy()
        lhs = std.StringImm(ty=any_ty, value="hello")
        rhs = std.StringImm(ty=std.AnyTy(), value="hello")
        different = std.StringImm(ty=std.AnyTy(), value="world")

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


_ARITHMETIC_EXPR_CLASSES: list[Any] = [
    std.Add,
    std.Sub,
    std.Mul,
    std.CDiv,
    std.FloorDiv,
    std.FloorMod,
    std.CMod,
    std.Pow,
    std.LShift,
    std.RShift,
    std.Min,
    std.Max,
]

_BITWISE_BINARY_EXPR_CLASSES: list[Any] = [
    std.BitwiseAnd,
    std.BitwiseOr,
    std.BitwiseXor,
]

_COMPARISON_EXPR_CLASSES: list[Any] = [
    std.Eq,
    std.Ne,
    std.Le,
    std.Ge,
    std.Gt,
    std.Lt,
]

_LOGICAL_BINARY_EXPR_CLASSES: list[Any] = [
    std.And,
    std.Or,
]


class TestDerivedOperandTypeChecks:
    @pytest.mark.parametrize("cls", _ARITHMETIC_EXPR_CLASSES)
    def test_arithmetic_constructor_allows_matching_non_any_operands(self, cls: Any) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(i32, "x")
        one = std.IntImm(i32, 1)
        node = cls(x, one, ty=i32)

        assert tvm_ffi.structural_equal(node.ty, i32)
        assert tvm_ffi.structural_equal(node.a.ty, i32)
        assert tvm_ffi.structural_equal(node.b.ty, i32)

    @pytest.mark.parametrize("cls", _ARITHMETIC_EXPR_CLASSES)
    def test_arithmetic_constructor_rejects_mismatched_non_any_operands(self, cls: Any) -> None:
        i32 = std.PrimTy("int32")
        i64 = std.PrimTy("int64")
        x = std.Var(i32, "x")
        y = std.Var(i64, "y")

        with pytest.raises(TypeError, match="does not match operand"):
            cls(x, y, ty=i32)

    @pytest.mark.parametrize("cls", _ARITHMETIC_EXPR_CLASSES)
    def test_arithmetic_constructor_allows_any_operand(self, cls: Any) -> None:
        i32 = std.PrimTy("int32")
        any_ty = std.AnyTy()
        x = std.Var(i32, "x")
        one = std.IntImm(any_ty, 1)
        node = cls(x, one, ty=i32)

        assert tvm_ffi.structural_equal(node.ty, i32)
        assert tvm_ffi.structural_equal(node.a.ty, i32)
        assert tvm_ffi.structural_equal(node.b.ty, any_ty)

    @pytest.mark.parametrize("cls", _ARITHMETIC_EXPR_CLASSES)
    def test_arithmetic_constructor_allows_any_result(self, cls: Any) -> None:
        i32 = std.PrimTy("int32")
        any_ty = std.AnyTy()
        x = std.Var(i32, "x")
        one = std.IntImm(i32, 1)
        node = cls(x, one, ty=any_ty)

        assert tvm_ffi.structural_equal(node.ty, any_ty)
        assert tvm_ffi.structural_equal(node.a.ty, i32)
        assert tvm_ffi.structural_equal(node.b.ty, i32)

    @pytest.mark.parametrize("cls", _ARITHMETIC_EXPR_CLASSES)
    def test_arithmetic_constructor_rejects_mismatched_concrete_operands_with_any_result(
        self, cls: Any
    ) -> None:
        any_ty = std.AnyTy()
        i32 = std.PrimTy("int32")
        i64 = std.PrimTy("int64")
        x = std.Var(i32, "x")
        y = std.Var(i64, "y")

        with pytest.raises(TypeError, match="does not match operand"):
            cls(x, y, ty=any_ty)

    @pytest.mark.parametrize("cls", _BITWISE_BINARY_EXPR_CLASSES)
    def test_bitwise_binary_constructor_uses_integer_operands_and_result(self, cls: Any) -> None:
        i32 = std.PrimTy("int32")
        node = cls(1, 2, ty=i32)

        assert tvm_ffi.structural_equal(node.ty, i32)
        assert tvm_ffi.structural_equal(node.a.ty, i32)
        assert tvm_ffi.structural_equal(node.b.ty, i32)

    @pytest.mark.parametrize("cls", _BITWISE_BINARY_EXPR_CLASSES)
    def test_bitwise_binary_constructor_rejects_non_integer_dtype(self, cls: Any) -> None:
        f32 = std.PrimTy("float32")

        with pytest.raises(TypeError, match="result dtype must be integer"):
            cls(1, 2, ty=f32)

    @pytest.mark.parametrize("cls", _COMPARISON_EXPR_CLASSES)
    def test_comparison_constructor_uses_bool_result(self, cls: Any) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        x = std.Var(i32, "x")
        node = cls(x, 1, ty=bool_ty)

        assert tvm_ffi.structural_equal(node.ty, bool_ty)
        assert tvm_ffi.structural_equal(node.a.ty, i32)
        assert tvm_ffi.structural_equal(node.b.ty, i32)

    @pytest.mark.parametrize("cls", _COMPARISON_EXPR_CLASSES)
    def test_comparison_constructor_rejects_non_bool_result(self, cls: Any) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(i32, "x")
        y = std.Var(i32, "y")

        with pytest.raises(TypeError, match="result dtype must be bool8"):
            cls(x, y, ty=i32)

    @pytest.mark.parametrize("cls", _COMPARISON_EXPR_CLASSES)
    def test_comparison_constructor_rejects_result_lane_mismatch(self, cls: Any) -> None:
        i32 = std.PrimTy("int32")
        boolx4 = std.PrimTy("boolx4")
        x = std.Var(i32, "x")
        y = std.Var(i32, "y")

        with pytest.raises(TypeError, match="result dtype lane count"):
            cls(x, y, ty=boolx4)

    @pytest.mark.parametrize("cls", _LOGICAL_BINARY_EXPR_CLASSES)
    def test_logical_binary_constructor_uses_bool_operands_and_result(self, cls: Any) -> None:
        bool_ty = std.PrimTy("bool")
        node = cls(True, False, ty=bool_ty)

        assert tvm_ffi.structural_equal(node.ty, bool_ty)
        assert tvm_ffi.structural_equal(node.a.ty, bool_ty)
        assert tvm_ffi.structural_equal(node.b.ty, bool_ty)

    @pytest.mark.parametrize("cls", _LOGICAL_BINARY_EXPR_CLASSES)
    def test_logical_binary_constructor_rejects_non_bool_dtype(self, cls: Any) -> None:
        i32 = std.PrimTy("int32")

        with pytest.raises(TypeError, match="result dtype must be bool8"):
            cls(1, 2, ty=i32)

    def test_unary_constructor_allows_matching_non_any_operand(self) -> None:
        bool_ty = std.PrimTy("bool")
        node = std.Not(std.BoolImm(bool_ty, True), ty=bool_ty)

        assert tvm_ffi.structural_equal(node.ty, bool_ty)
        assert tvm_ffi.structural_equal(node.operand.ty, bool_ty)

    def test_unary_constructor_rejects_mismatched_non_any_operand(self) -> None:
        bool_ty = std.PrimTy("bool")
        boolx4 = std.PrimTy("boolx4")

        with pytest.raises(TypeError, match="does not match operand"):
            std.Not(std.BoolImm(boolx4, True), ty=bool_ty)

    def test_unary_constructor_rejects_non_bool_dtype(self) -> None:
        i32 = std.PrimTy("int32")

        with pytest.raises(TypeError, match="result dtype must be bool8"):
            std.Not(std.IntImm(i32, 1), ty=i32)

    def test_unary_constructor_allows_any_operand(self) -> None:
        bool_ty = std.PrimTy("bool")
        any_ty = std.AnyTy()
        node = std.Not(std.BoolImm(any_ty, True), ty=bool_ty)

        assert tvm_ffi.structural_equal(node.ty, bool_ty)
        assert tvm_ffi.structural_equal(node.operand.ty, any_ty)

    def test_unary_constructor_allows_any_operand_with_any_result(self) -> None:
        any_ty = std.AnyTy()
        node = std.Not(1, ty=any_ty)

        assert tvm_ffi.structural_equal(node.ty, any_ty)
        assert tvm_ffi.structural_equal(node.operand.ty, any_ty)

    def test_bitwise_not_constructor_rejects_non_integer_dtype(self) -> None:
        f32 = std.PrimTy("float32")

        with pytest.raises(TypeError, match="result dtype must be integer"):
            std.BitwiseNot(std.FloatImm(f32, 1.0), ty=f32)

    def test_abs_constructor_preserves_operand_type(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Abs(-1, ty=i32)

        assert tvm_ffi.structural_equal(node.ty, i32)
        assert tvm_ffi.structural_equal(node.operand.ty, i32)


class TestAdd:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        one = 1
        two = 2
        node = std.Add(ty=i32, a=one, b=two)

        assert isinstance(node, std.Add)
        assert tuple(field.name for field in fields(std.Add)) == ("ty", "a", "b")
        assert node.ty == i32
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.value == one
        assert node.b.value == two

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Add(ty=i32, a=1, b=2)

        assert node.text() == "std.i32(1) + std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Add(ty=i32, a=1, b=2)
        rhs = std.Add(ty=i32, a=1, b=2)
        different = std.Add(
            ty=i32,
            a=1,
            b=3,
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestSub:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        one = 1
        two = 2
        node = std.Sub(ty=i32, a=one, b=two)

        assert isinstance(node, std.Sub)
        assert tuple(field.name for field in fields(std.Sub)) == ("ty", "a", "b")
        assert node.ty == i32
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.value == one
        assert node.b.value == two

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Sub(ty=i32, a=1, b=2)

        assert node.text() == "std.i32(1) - std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Sub(ty=i32, a=1, b=2)
        rhs = std.Sub(ty=i32, a=1, b=2)
        different = std.Sub(
            ty=i32,
            a=1,
            b=3,
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestMul:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        one = 1
        two = 2
        node = std.Mul(ty=i32, a=one, b=two)

        assert isinstance(node, std.Mul)
        assert tuple(field.name for field in fields(std.Mul)) == ("ty", "a", "b")
        assert node.ty == i32
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.value == one
        assert node.b.value == two

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Mul(ty=i32, a=1, b=2)

        assert node.text() == "std.i32(1) * std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Mul(ty=i32, a=1, b=2)
        rhs = std.Mul(ty=i32, a=1, b=2)
        different = std.Mul(
            ty=i32,
            a=1,
            b=3,
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestFloorDiv:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        one = 1
        two = 2
        node = std.FloorDiv(ty=i32, a=one, b=two)

        assert isinstance(node, std.FloorDiv)
        assert tuple(field.name for field in fields(std.FloorDiv)) == ("ty", "a", "b")
        assert node.ty == i32
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.value == one
        assert node.b.value == two

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.FloorDiv(
            ty=i32,
            a=1,
            b=2,
        )

        assert node.text() == "std.i32(1) // std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.FloorDiv(
            ty=i32,
            a=1,
            b=2,
        )
        rhs = std.FloorDiv(
            ty=i32,
            a=1,
            b=2,
        )
        different = std.FloorDiv(
            ty=i32,
            a=1,
            b=3,
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestFloorMod:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        one = 1
        two = 2
        node = std.FloorMod(ty=i32, a=one, b=two)

        assert isinstance(node, std.FloorMod)
        assert tuple(field.name for field in fields(std.FloorMod)) == ("ty", "a", "b")
        assert node.ty == i32
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.value == one
        assert node.b.value == two

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.FloorMod(
            ty=i32,
            a=1,
            b=2,
        )

        assert node.text() == "std.i32(1) % std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.FloorMod(
            ty=i32,
            a=1,
            b=2,
        )
        rhs = std.FloorMod(
            ty=i32,
            a=1,
            b=2,
        )
        different = std.FloorMod(
            ty=i32,
            a=1,
            b=3,
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestAdditionalBinaryOps:
    @pytest.mark.parametrize(
        "cls_name,text",
        [
            ("CDiv", "std.i32(1) / std.i32(2)"),
            ("CMod", "std.CMod(std.i32(1), std.i32(2), ty=std.i32)"),
            ("Pow", "std.i32(1) ** std.i32(2)"),
            ("LShift", "std.i32(1) << std.i32(2)"),
            ("RShift", "std.i32(1) >> std.i32(2)"),
            ("BitwiseAnd", "std.i32(1) & std.i32(2)"),
            ("BitwiseOr", "std.i32(1) | std.i32(2)"),
            ("BitwiseXor", "std.i32(1) ^ std.i32(2)"),
        ],
    )
    def test_constructor_and_text_format(self, cls_name: str, text: str) -> None:
        cls = getattr(std, cls_name)
        i32 = std.PrimTy("int32")
        node = cls(ty=i32, a=1, b=2)

        assert isinstance(node, cls)
        assert tuple(field.name for field in fields(cls)) == ("ty", "a", "b")
        assert node.ty == i32
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.value == 1
        assert node.b.value == 2
        assert node.text() == text

    @pytest.mark.parametrize(
        "cls_name",
        ["CDiv", "CMod", "Pow", "LShift", "RShift", "BitwiseAnd", "BitwiseOr", "BitwiseXor"],
    )
    def test_structural_equality(self, cls_name: str) -> None:
        cls = getattr(std, cls_name)
        i32 = std.PrimTy("int32")
        lhs = cls(ty=i32, a=1, b=2)
        rhs = cls(ty=i32, a=1, b=2)
        different = cls(ty=i32, a=1, b=3)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestMin:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        one = 1
        two = 2
        node = std.Min(ty=i32, a=one, b=two)

        assert isinstance(node, std.Min)
        assert tuple(field.name for field in fields(std.Min)) == ("ty", "a", "b")
        assert node.ty == i32
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.value == one
        assert node.b.value == two

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Min(ty=i32, a=1, b=2)

        assert node.text() == "min(std.i32(1), std.i32(2))"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Min(ty=i32, a=1, b=2)
        rhs = std.Min(ty=i32, a=1, b=2)
        different = std.Min(
            ty=i32,
            a=1,
            b=3,
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestMax:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        one = 1
        two = 2
        node = std.Max(ty=i32, a=one, b=two)

        assert isinstance(node, std.Max)
        assert tuple(field.name for field in fields(std.Max)) == ("ty", "a", "b")
        assert node.ty == i32
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.value == one
        assert node.b.value == two

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Max(ty=i32, a=1, b=2)

        assert node.text() == "max(std.i32(1), std.i32(2))"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Max(ty=i32, a=1, b=2)
        rhs = std.Max(ty=i32, a=1, b=2)
        different = std.Max(
            ty=i32,
            a=1,
            b=3,
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestEq:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        one = std.IntImm(i32, 1)
        two = std.IntImm(i32, 2)
        node = std.Eq(ty=bool_ty, a=one, b=two)

        assert isinstance(node, std.Eq)
        assert tuple(field.name for field in fields(std.Eq)) == ("ty", "a", "b")
        assert node.ty == bool_ty
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.ty == i32
        assert node.b.ty == i32
        assert node.a.value == 1
        assert node.b.value == 2

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Eq(ty=std.PrimTy("bool"), a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))

        assert node.text() == "std.i32(1) == std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        lhs = std.Eq(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        rhs = std.Eq(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        different = std.Eq(
            ty=bool_ty,
            a=std.IntImm(i32, 1),
            b=std.IntImm(i32, 3),
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestNe:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        one = std.IntImm(i32, 1)
        two = std.IntImm(i32, 2)
        node = std.Ne(ty=bool_ty, a=one, b=two)

        assert isinstance(node, std.Ne)
        assert tuple(field.name for field in fields(std.Ne)) == ("ty", "a", "b")
        assert node.ty == bool_ty
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.ty == i32
        assert node.b.ty == i32
        assert node.a.value == 1
        assert node.b.value == 2

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Ne(ty=std.PrimTy("bool"), a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))

        assert node.text() == "std.i32(1) != std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        lhs = std.Ne(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        rhs = std.Ne(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        different = std.Ne(
            ty=bool_ty,
            a=std.IntImm(i32, 1),
            b=std.IntImm(i32, 3),
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestLe:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        one = std.IntImm(i32, 1)
        two = std.IntImm(i32, 2)
        node = std.Le(ty=bool_ty, a=one, b=two)

        assert isinstance(node, std.Le)
        assert tuple(field.name for field in fields(std.Le)) == ("ty", "a", "b")
        assert node.ty == bool_ty
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.ty == i32
        assert node.b.ty == i32
        assert node.a.value == 1
        assert node.b.value == 2

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Le(ty=std.PrimTy("bool"), a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))

        assert node.text() == "std.i32(1) <= std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        lhs = std.Le(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        rhs = std.Le(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        different = std.Le(
            ty=bool_ty,
            a=std.IntImm(i32, 1),
            b=std.IntImm(i32, 3),
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestGe:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        one = std.IntImm(i32, 1)
        two = std.IntImm(i32, 2)
        node = std.Ge(ty=bool_ty, a=one, b=two)

        assert isinstance(node, std.Ge)
        assert tuple(field.name for field in fields(std.Ge)) == ("ty", "a", "b")
        assert node.ty == bool_ty
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.ty == i32
        assert node.b.ty == i32
        assert node.a.value == 1
        assert node.b.value == 2

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Ge(ty=std.PrimTy("bool"), a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))

        assert node.text() == "std.i32(1) >= std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        lhs = std.Ge(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        rhs = std.Ge(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        different = std.Ge(
            ty=bool_ty,
            a=std.IntImm(i32, 1),
            b=std.IntImm(i32, 3),
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestGt:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        one = std.IntImm(i32, 1)
        two = std.IntImm(i32, 2)
        node = std.Gt(ty=bool_ty, a=one, b=two)

        assert isinstance(node, std.Gt)
        assert tuple(field.name for field in fields(std.Gt)) == ("ty", "a", "b")
        assert node.ty == bool_ty
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.ty == i32
        assert node.b.ty == i32
        assert node.a.value == 1
        assert node.b.value == 2

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Gt(ty=std.PrimTy("bool"), a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))

        assert node.text() == "std.i32(1) > std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        lhs = std.Gt(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        rhs = std.Gt(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        different = std.Gt(
            ty=bool_ty,
            a=std.IntImm(i32, 1),
            b=std.IntImm(i32, 3),
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestLt:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        one = std.IntImm(i32, 1)
        two = std.IntImm(i32, 2)
        node = std.Lt(ty=bool_ty, a=one, b=two)

        assert isinstance(node, std.Lt)
        assert tuple(field.name for field in fields(std.Lt)) == ("ty", "a", "b")
        assert node.ty == bool_ty
        assert isinstance(node.a, std.IntImm)
        assert isinstance(node.b, std.IntImm)
        assert node.a.ty == i32
        assert node.b.ty == i32
        assert node.a.value == 1
        assert node.b.value == 2

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Lt(ty=std.PrimTy("bool"), a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))

        assert node.text() == "std.i32(1) < std.i32(2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        bool_ty = std.PrimTy("bool")
        lhs = std.Lt(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        rhs = std.Lt(ty=bool_ty, a=std.IntImm(i32, 1), b=std.IntImm(i32, 2))
        different = std.Lt(
            ty=bool_ty,
            a=std.IntImm(i32, 1),
            b=std.IntImm(i32, 3),
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestAnd:
    def test_constructor(self) -> None:
        bool_ty = std.PrimTy("bool")
        node = std.And(ty=bool_ty, a=True, b=False)

        assert isinstance(node, std.And)
        assert tuple(field.name for field in fields(std.And)) == ("ty", "a", "b")
        assert node.ty == bool_ty
        assert isinstance(node.a, std.BoolImm)
        assert isinstance(node.b, std.BoolImm)
        assert node.a.value is True
        assert node.b.value is False

    def test_text_format(self) -> None:
        bool_ty = std.PrimTy("bool")
        node = std.And(ty=bool_ty, a=True, b=False)

        assert node.text() == "std.And(True, False, ty=std.bool)"

    def test_structural_equality(self) -> None:
        bool_ty = std.PrimTy("bool")
        lhs = std.And(ty=bool_ty, a=True, b=False)
        rhs = std.And(ty=bool_ty, a=True, b=False)
        different = std.And(
            ty=bool_ty,
            a=False,
            b=False,
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestOr:
    def test_constructor(self) -> None:
        bool_ty = std.PrimTy("bool")
        node = std.Or(ty=bool_ty, a=True, b=False)

        assert isinstance(node, std.Or)
        assert tuple(field.name for field in fields(std.Or)) == ("ty", "a", "b")
        assert node.ty == bool_ty
        assert isinstance(node.a, std.BoolImm)
        assert isinstance(node.b, std.BoolImm)
        assert node.a.value is True
        assert node.b.value is False

    def test_text_format(self) -> None:
        bool_ty = std.PrimTy("bool")
        node = std.Or(ty=bool_ty, a=True, b=False)

        assert node.text() == "std.Or(True, False, ty=std.bool)"

    def test_structural_equality(self) -> None:
        bool_ty = std.PrimTy("bool")
        lhs = std.Or(ty=bool_ty, a=True, b=False)
        rhs = std.Or(ty=bool_ty, a=True, b=False)
        different = std.Or(
            ty=bool_ty,
            a=False,
            b=False,
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestNot:
    def test_constructor(self) -> None:
        bool_ty = std.PrimTy("bool")
        operand = True
        node = std.Not(ty=bool_ty, operand=operand)

        assert isinstance(node, std.Not)
        assert tuple(field.name for field in fields(std.Not)) == ("ty", "operand")
        assert node.ty == bool_ty
        assert isinstance(node.operand, std.BoolImm)
        assert node.operand.value is operand

    def test_text_format(self) -> None:
        bool_ty = std.PrimTy("bool")
        node = std.Not(ty=bool_ty, operand=True)

        assert node.text() == "std.Not(True, ty=std.bool)"

    def test_from_any_converts_python_int_to_not(self) -> None:
        node = core._to_py_class_value(core.TypeSchema.from_annotation(std.Not).convert(1))

        assert isinstance(node, std.Not)
        assert isinstance(node.ty, std.AnyTy)
        assert isinstance(node.operand, std.IntImm)
        assert node.operand.value == 1
        assert node.text() == "std.Not(1, ty=std.Any)"

    def test_structural_equality(self) -> None:
        bool_ty = std.PrimTy("bool")
        lhs = std.Not(ty=bool_ty, operand=True)
        rhs = std.Not(ty=bool_ty, operand=True)
        different = std.Not(ty=bool_ty, operand=False)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestBitwiseNot:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.BitwiseNot(1, ty=i32)

        assert isinstance(node, std.BitwiseNot)
        assert tuple(field.name for field in fields(std.BitwiseNot)) == ("ty", "operand")
        assert node.ty == i32
        assert isinstance(node.operand, std.IntImm)
        assert node.operand.value == 1

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.BitwiseNot(std.Var(i32, "x"), ty=i32)

        assert node.text() == "~x"


class TestAbs:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Abs(-1, ty=i32)

        assert isinstance(node, std.Abs)
        assert tuple(field.name for field in fields(std.Abs)) == ("ty", "operand")
        assert node.ty == i32
        assert isinstance(node.operand, std.IntImm)
        assert node.operand.value == -1

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Abs(std.Var(i32, "x"), ty=i32)

        assert node.text() == "abs(x)"


class TestIfExpr:
    def test_constructor(self) -> None:
        bool_ty = std.PrimTy("bool")
        i32 = std.PrimTy("int32")
        node = std.IfExpr(True, 1, 2, ty=i32)

        assert isinstance(node, std.IfExpr)
        assert tuple(field.name for field in fields(std.IfExpr)) == (
            "ty",
            "cond",
            "then_expr",
            "else_expr",
        )
        assert node.ty == i32
        assert tvm_ffi.structural_equal(node.cond.ty, bool_ty)
        assert tvm_ffi.structural_equal(node.then_expr.ty, i32)
        assert tvm_ffi.structural_equal(node.else_expr.ty, i32)

    def test_text_format(self) -> None:
        bool_ty = std.PrimTy("bool")
        i32 = std.PrimTy("int32")
        cond = std.Var(bool_ty, "cond")
        x = std.Var(i32, "x")
        y = std.Var(i32, "y")
        node = std.IfExpr(cond, x, y, ty=i32)

        assert node.text() == "x if cond else y"


class TestExprOperators:
    @pytest.mark.parametrize(
        "expr,text",
        [
            (std.Var(std.PrimTy("int64"), "x"), "x"),
            (std.Var(std.PrimTy("int32"), "y"), "y"),
            (std.IntImm(std.PrimTy("int64"), -1), "-1"),
            (std.IntImm(std.PrimTy("int64"), 1), "1"),
            (std.IntImm(std.PrimTy("int32"), 65536), "std.i32(65536)"),
            (std.BoolImm(std.PrimTy("bool"), True), "True"),
            (std.BoolImm(std.PrimTy("bool"), False), "False"),
            (std.FloatImm(std.PrimTy("float64"), 0.0), "std.f64(0.0)"),
            (std.FloatImm(std.PrimTy("float64"), 1.0), "std.f64(1.0)"),
            (std.FloatImm(std.PrimTy("float64"), -1.0), "std.f64(-1.0)"),
        ],
    )
    def test_mlc_expr_leaf_text_cases(self, expr: std.Expr, text: str) -> None:
        assert expr.text() == text

    def test_mlc_cast_case(self) -> None:
        x = std.Var(std.PrimTy("int64"), "x")

        assert x.cast("int32").text() == "std.i32(x)"

    def test_mlc_arithmetic_binary_cases(self) -> None:
        i64 = std.PrimTy("int64")
        x = std.Var(i64, "x")
        y = std.Var(i64, "y")
        cases = [
            (x + y, std.Add, "x + y"),
            (x - y, std.Sub, "x - y"),
            (x * y, std.Mul, "x * y"),
            (std.truncdiv(x, y), std.CDiv, "x / y"),
            (std.truncmod(x, y), std.CMod, "std.CMod(x, y, ty=std.i64)"),
            (x // y, std.FloorDiv, "x // y"),
            (x % y, std.FloorMod, "x % y"),
            (std.min(x, y), std.Min, "min(x, y)"),
            (std.max(x, y), std.Max, "max(x, y)"),
        ]

        for expr, cls, text in cases:
            assert isinstance(expr, cls)
            assert expr.text() == text

    def test_mlc_comparison_cases(self) -> None:
        i64 = std.PrimTy("int64")
        x = std.Var(i64, "x")
        y = std.Var(i64, "y")
        cases = [
            (std.eq(x, y), std.Eq, "x == y"),
            (std.ne(x, y), std.Ne, "x != y"),
            (x >= y, std.Ge, "x >= y"),
            (x <= y, std.Le, "x <= y"),
            (x > y, std.Gt, "x > y"),
            (x < y, std.Lt, "x < y"),
        ]

        for expr, cls, text in cases:
            assert isinstance(expr, cls)
            assert isinstance(expr.ty, std.PrimTy)
            assert expr.ty.dtype == tvm_ffi.bool
            assert expr.text() == text

    def test_mlc_logical_select_and_range_cases(self) -> None:
        bool_ty = std.PrimTy("bool")
        i64 = std.PrimTy("int64")
        cond = std.Var(bool_ty, "cond")
        x = std.Var(bool_ty, "x")
        y = std.Var(bool_ty, "y")
        min_var = std.Var(i64, "min")
        extent = std.Var(i64, "extent")
        true_value = std.Var(i64, "true_value")
        false_value = std.Var(i64, "false_value")

        assert std.logical_and(x, y).text() == "x and y"
        assert std.logical_or(x, y).text() == "x or y"
        assert std.logical_not(x).text() == "not x"
        assert std.select(cond, true_value, false_value).text() == (
            "true_value if cond else false_value"
        )
        assert std.Range(min_var, extent).text() == "std.Range(min, extent)"

    def test_python_dunders_construct_std_nodes(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(i32, "x")

        cases = [
            (x + 1, std.Add, "x + std.i32(1)"),
            (1 + x, std.Add, "std.i32(1) + x"),
            (x - 1, std.Sub, "x - std.i32(1)"),
            (1 - x, std.Sub, "std.i32(1) - x"),
            (x * 2, std.Mul, "x * std.i32(2)"),
            (x / 2, std.CDiv, "x / std.i32(2)"),
            (x // 2, std.FloorDiv, "x // std.i32(2)"),
            (x % 2, std.FloorMod, "x % std.i32(2)"),
            (x**2, std.Pow, "x ** std.i32(2)"),
            (x << 1, std.LShift, "x << std.i32(1)"),
            (x >> 1, std.RShift, "x >> std.i32(1)"),
            (x & 3, std.BitwiseAnd, "x & std.i32(3)"),
            (x | 3, std.BitwiseOr, "x | std.i32(3)"),
            (x ^ 3, std.BitwiseXor, "x ^ std.i32(3)"),
            (~x, std.BitwiseNot, "~x"),
            (-x, std.Sub, "std.i32(0) - x"),
            (abs(x), std.Abs, "abs(x)"),
        ]

        for expr, cls, text in cases:
            assert isinstance(expr, cls)
            assert expr.text() == text

    def test_python_comparison_dunders_construct_std_nodes(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(i32, "x")

        cases = [
            (x < 2, std.Lt, "x < std.i32(2)"),
            (x <= 2, std.Le, "x <= std.i32(2)"),
            (x > 2, std.Gt, "x > std.i32(2)"),
            (x >= 2, std.Ge, "x >= std.i32(2)"),
            (x == 2, std.Eq, "x == std.i32(2)"),
            (x != 2, std.Ne, "x != std.i32(2)"),
        ]

        for expr, cls, text in cases:
            assert isinstance(expr, cls)
            assert isinstance(expr.ty, std.PrimTy)
            assert expr.ty.dtype == tvm_ffi.bool
            assert expr.text() == text

    def test_python_named_operator_helpers(self) -> None:
        bool_ty = std.PrimTy("bool")
        i32 = std.PrimTy("int32")
        cond = std.Var(bool_ty, "cond")
        x = std.Var(i32, "x")

        assert std.min(x, 1).text() == "min(x, std.i32(1))"
        assert std.max(x, 1).text() == "max(x, std.i32(1))"
        assert cond.logical_and(True).text() == "cond"
        assert cond.logical_or(False).text() == "cond"
        assert cond.logical_not().text() == "not cond"
        assert cond.if_then_else(x, 1).text() == "x if cond else std.i32(1)"
        assert x.astype(std.PrimTy("float32")).text() == "std.f32(x)"

    def test_operator_helpers_are_exposed_as_global_funcs(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(i32, "x")

        assert tvm_ffi.get_global_func("ffi.std.add")(x, 1).text() == "x + std.i32(1)"
        assert tvm_ffi.get_global_func("ffi.std.eq")(x, 1).text() == "x == std.i32(1)"
        assert tvm_ffi.get_global_func("ffi.std.bitwise_not")(x).text() == "~x"

    def test_python_bool_context_rejected(self) -> None:
        x = std.Var(std.PrimTy("bool"), "x")

        with pytest.raises(TypeError, match=r"Cannot use std\.Expr as a Python bool"):
            bool(x)


class TestLoad:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        first = std.Range(start=1, stop=2)
        second = std.Range(
            start=1,
            stop=2,
            step=3,
        )
        node = std.Load(x, first, second)

        assert isinstance(node, std.Load)
        assert tuple(field.name for field in fields(std.Load)) == (
            "ty",
            "lhs",
            "indices",
        )
        assert node.ty == i32
        assert node.lhs == x
        assert list(node.indices) == [first, second]

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Load(
            std.Var(ty=i32, name="x"),
            std.Range(
                start=1,
                stop=2,
            ),
            std.Range(
                start=1,
                stop=2,
                step=3,
            ),
            ty=i32,
        )

        assert node.text() == "x[1:2, 1:2:3]"

    def test_text_format_index_variants(self) -> None:
        i32 = std.PrimTy("int32")

        no_indices = std.Load(std.Var(ty=i32, name="x"))
        assert no_indices.text() == "x[()]"

        point = std.Load(std.Var(ty=i32, name="x"), 1)
        assert point.text() == "x[1]"

        slice_without_step = std.Load(
            std.Var(ty=i32, name="x"),
            std.Range(
                start=1,
                stop=2,
            ),
        )
        assert slice_without_step.text() == "x[1:2]"

        slice_without_start = std.Load(
            std.Var(ty=i32, name="x"),
            std.Range(
                start=None,
                stop=2,
            ),
        )
        assert slice_without_start.text() == "x[:2]"

        slice_without_stop = std.Load(
            std.Var(ty=i32, name="x"),
            std.Range(
                start=1,
                step=3,
            ),
        )
        assert slice_without_stop.text() == "x[1::3]"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Load(
            std.Var(ty=i32, name="x"),
            std.Range(
                start=1,
                stop=2,
            ),
            std.Range(
                start=1,
                stop=2,
                step=3,
            ),
            ty=i32,
        )
        rhs = std.Load(
            std.Var(ty=i32, name="x"),
            std.Range(
                start=1,
                stop=2,
            ),
            std.Range(
                start=1,
                stop=2,
                step=3,
            ),
            ty=i32,
        )
        different = std.Load(std.Var(ty=i32, name="x"), 2, ty=i32)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)

    def test_rejects_result_dtype_mismatch(self) -> None:
        i32 = std.PrimTy("int32")
        f32 = std.PrimTy("float32")

        with pytest.raises(TypeError, match="result type"):
            std.Load(std.Var(ty=i32, name="x"), ty=f32)


class TestCast:
    def test_constructor(self) -> None:
        f32 = std.PrimTy("float32")
        value = 1
        node = std.Cast(ty=f32, value=value)

        assert isinstance(node, std.Cast)
        assert tuple(field.name for field in fields(std.Cast)) == ("ty", "value")
        assert node.ty == f32
        assert isinstance(node.value, std.IntImm)
        assert node.value.value == value

    def test_text_format(self) -> None:
        node = std.Cast(
            ty=std.PrimTy("int32"),
            value=1,
        )

        assert node.text() == "std.Cast(std.i32, 1)"

    def test_text_format_uses_dtype_abbreviation(self) -> None:
        node = std.Cast(
            ty=std.PrimTy("float32"),
            value=1,
        )

        assert node.text() == "std.Cast(std.f32, 1)"

    def test_structural_equality(self) -> None:
        lhs = std.Cast(
            ty=std.PrimTy("float32"),
            value=1,
        )
        rhs = std.Cast(
            ty=std.PrimTy("float32"),
            value=1,
        )
        different = std.Cast(
            ty=std.PrimTy("int32"),
            value=1,
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestCall:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        one = 1
        two = 2
        node = std.Call("callee", one, two, tag="demo", ty=i32)

        assert isinstance(node, std.Call)
        assert tuple(field.name for field in fields(std.Call)) == (
            "ty",
            "callee",
            "args",
            "attr",
        )
        assert tvm_ffi.structural_equal(node.ty, i32)
        assert node.callee == "callee"
        args = list(node.args)
        assert isinstance(args[0], std.IntImm)
        assert isinstance(args[1], std.IntImm)
        assert args[0].value == one
        assert args[1].value == two
        assert isinstance(node.attr, std.DictAttrs)
        assert dict(node.attr.values) == {"tag": "demo"}

    def test_constructor_converts_python_args_and_attr(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Call("callee", 1, 2, tag="demo", ty=i32)

        args = list(node.args)
        assert isinstance(args[0], std.IntImm)
        assert isinstance(args[1], std.IntImm)
        assert isinstance(node.attr, std.DictAttrs)
        assert node.text() == 'std.Call(callee, 1, 2, tag="demo", ty=std.i32)'

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Call("callee", 1, 2, ty=i32)

        assert node.text() == "std.Call(callee, 1, 2, ty=std.i32)"

    def test_text_format_without_args(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Call("callee", ty=i32)

        assert node.text() == "std.Call(callee, ty=std.i32)"

    def test_text_format_with_func_callee(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        callee = std.Func(
            symbol="helper",
            args=[x],
            ret_type=i32,
            body=[std.Return(x)],
        )
        node = std.Call(callee, 1, ty=i32)

        assert node.text() == "std.Call(helper, 1, ty=std.i32)"

    def test_text_format_with_attr(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Call("callee", 1, 2, tag="demo", ty=i32)

        assert node.text() == 'std.Call(callee, 1, 2, tag="demo", ty=std.i32)'

    def test_text_format_with_empty_attr(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Call("callee", ty=i32)

        assert node.text() == "std.Call(callee, ty=std.i32)"

    def test_text_format_with_sorted_attr_keys(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Call("callee", z=2, a=1, ty=i32)

        assert node.text() == "std.Call(callee, a=1, z=2, ty=std.i32)"

    def test_attr_default(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Call("callee", ty=i32)

        assert node.attr is None
        assert node.text() == "std.Call(callee, ty=std.i32)"

    def test_attr_field_accepts_dict_attrs_and_none(self) -> None:
        i32 = std.PrimTy("int32")
        with_attr = std.Call("callee", tag="demo", ty=i32)
        without_attr = std.Call("callee", ty=i32)

        assert isinstance(with_attr.attr, std.DictAttrs)
        assert dict(with_attr.attr.values) == {"tag": "demo"}
        assert without_attr.attr is None
        assert with_attr.text() == 'std.Call(callee, tag="demo", ty=std.i32)'
        assert without_attr.text() == "std.Call(callee, ty=std.i32)"

    def test_any_call_uses_generic_python_call_syntax(self) -> None:
        node = std.Call("callee", 1, 2, ty=std.AnyTy())

        assert node.text() == "callee(1, 2)"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Call("callee", 1, 2, tag="demo", ty=i32)
        rhs = std.Call("callee", 1, 2, tag="demo", ty=i32)
        different = std.Call("callee", 1, 2, tag="other", ty=i32)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestIfStmt:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        y = std.Var(ty=i32, name="y")
        two = 2
        cond = std.Lt(ty=std.PrimTy("bool"), a=x, b=two)
        then_body = [std.Return(x)]
        else_body = [std.Return(y)]
        node = std.IfStmt(cond=cond, then_body=then_body, else_body=else_body)

        assert isinstance(node, std.IfStmt)
        assert tuple(field.name for field in fields(std.IfStmt)) == (
            "attrs",
            "cond",
            "then_body",
            "else_body",
        )
        assert node.attrs is None
        assert node.cond == cond
        assert list(node.then_body) == then_body
        assert list(node.else_body) == else_body

        with_attrs = std.IfStmt(
            cond=cond,
            then_body=then_body,
            else_body=else_body,
            tag="demo",
        )
        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == {"tag": "demo"}

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        y = std.Var(ty=i32, name="y")
        node = std.IfStmt(
            cond=std.Lt(ty=std.PrimTy("bool"), a=x, b=2),
            then_body=[std.Return(x)],
            else_body=[std.Return(y)],
        )

        assert node.text() == "if x < std.i32(2):\n  return x\nelse:\n  return y"

    def test_text_format_with_empty_else_body(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.IfStmt(
            cond=std.Lt(ty=std.PrimTy("bool"), a=x, b=2),
            then_body=[std.Return(x)],
            else_body=[],
        )

        assert node.text() == "if x < std.i32(2):\n  return x"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.IfStmt(
            cond=std.Lt(
                ty=std.PrimTy("bool"),
                a=std.Var(ty=i32, name="x"),
                b=2,
            ),
            then_body=[std.Return(std.Var(ty=i32, name="x"))],
            else_body=[std.Return(std.Var(ty=i32, name="y"))],
        )
        rhs = std.IfStmt(
            cond=std.Lt(
                ty=std.PrimTy("bool"),
                a=std.Var(ty=i32, name="x"),
                b=2,
            ),
            then_body=[std.Return(std.Var(ty=i32, name="x"))],
            else_body=[std.Return(std.Var(ty=i32, name="y"))],
        )
        different = std.IfStmt(
            cond=std.Gt(
                ty=std.PrimTy("bool"),
                a=std.Var(ty=i32, name="x"),
                b=2,
            ),
            then_body=[std.Return(std.Var(ty=i32, name="x"))],
            else_body=[std.Return(std.Var(ty=i32, name="y"))],
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)

    def test_rejects_non_bool_condition(self) -> None:
        i32 = std.PrimTy("int32")

        with pytest.raises(TypeError, match="condition dtype must be bool8"):
            std.IfStmt(cond=std.IntImm(i32, 1), then_body=[], else_body=[])


class TestFor:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        range_node = std.Range(
            start=1,
            stop=2,
        )
        body = [std.Store(x, 2, 1)]
        node = std.For(
            start=range_node.start,
            stop=range_node.stop,
            step=range_node.step,
            attrs={"tag": "demo"},
            body=body,
            vars=[x],
        )

        assert isinstance(node, std.For)
        assert not isinstance(node, std.Scope)
        assert not issubclass(std.For, std.Scope)
        assert tuple(field.name for field in fields(std.For)) == (
            "attrs",
            "start",
            "stop",
            "step",
            "vars",
            "body",
        )
        assert node.start == range_node.start
        assert node.stop == range_node.stop
        assert node.step == range_node.step
        assert node.attrs is not None
        assert list(node.vars) == [x]
        assert list(node.body) == body

    def test_attrs_field_accepts_dict_attrs_and_none(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        cond_range = std.Range(
            start=1,
            stop=2,
        )
        body = [std.Store(x, 2, 1)]
        attrs = {"pragma": "unroll"}
        with_attrs = std.For(
            start=cond_range.start,
            stop=cond_range.stop,
            step=cond_range.step,
            attrs=attrs,
            body=body,
            vars=[x],
        )
        without_attrs = std.For(
            start=cond_range.start,
            stop=cond_range.stop,
            step=cond_range.step,
            body=body,
            vars=[x],
        )
        with_empty_attrs = std.For(
            start=cond_range.start,
            stop=cond_range.stop,
            step=cond_range.step,
            attrs={},
            body=body,
            vars=[x],
        )

        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == attrs
        assert without_attrs.attrs is None
        assert with_attrs.text() == 'for x in range(1, 2, pragma="unroll"):\n  x[1] = 2'
        assert without_attrs.text() == "for x in range(1, 2):\n  x[1] = 2"
        assert with_empty_attrs.text() == "for x in range(1, 2):\n  x[1] = 2"

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.For(
            start=1,
            stop=2,
            step=None,
            attrs={"tag": "demo"},
            body=[std.Store(x, 2, 1)],
            vars=[x],
        )

        assert node.text() == 'for x in range(1, 2, tag="demo"):\n  x[1] = 2'

    def test_text_format_with_sorted_attrs(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.For(
            start=1,
            stop=2,
            step=None,
            attrs={"z": 3, "a": 1},
            body=[std.Store(x, 2, 1)],
            vars=[x],
        )

        assert node.text() == "for x in range(1, 2, a=1, z=3):\n  x[1] = 2"

    def test_text_format_preserves_sparse_range_fields(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        start_only = std.For(
            start=1,
            stop=None,
            step=None,
            body=[],
            vars=[x],
        )
        step_only = std.For(
            start=None,
            stop=None,
            step=2,
            body=[],
            vars=[x],
        )

        assert start_only.text() == "for x in range(1, None):\n  pass"
        assert step_only.text() == "for x in range(None, None, 2):\n  pass"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.For(
            start=1,
            stop=2,
            step=None,
            attrs={"tag": "demo"},
            body=[std.Store(std.Var(ty=i32, name="x"), 2, 1)],
            vars=[std.Var(ty=i32, name="x")],
        )
        rhs = std.For(
            start=1,
            stop=2,
            step=None,
            attrs={"tag": "demo"},
            body=[std.Store(std.Var(ty=i32, name="x"), 2, 1)],
            vars=[std.Var(ty=i32, name="x")],
        )
        different = std.For(
            start=1,
            stop=3,
            step=None,
            attrs={"tag": "demo"},
            body=[std.Store(std.Var(ty=i32, name="x"), 2, 1)],
            vars=[std.Var(ty=i32, name="x")],
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestWhile:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        y = std.Var(ty=i32, name="y")
        cond = std.Lt(ty=std.PrimTy("bool"), a=x, b=2)
        body = [std.BindExpr(std.IntImm(std.PrimTy("int64"), 2), y)]
        node = std.While(
            cond=cond,
            attrs={"tag": "demo"},
            body=body,
        )

        assert isinstance(node, std.While)
        assert not isinstance(node, std.Scope)
        assert not issubclass(std.While, std.Scope)
        assert tuple(field.name for field in fields(std.While)) == (
            "attrs",
            "cond",
            "body",
        )
        assert node.cond == cond
        assert node.attrs is not None
        assert list(node.body) == body

    def test_attrs_field_accepts_dict_attrs_and_none(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        y = std.Var(ty=i32, name="y")
        cond = std.Lt(ty=std.PrimTy("bool"), a=x, b=2)
        body = [std.BindExpr(std.IntImm(std.PrimTy("int64"), 2), y)]
        attrs = {"pragma": "pipeline"}
        with_attrs = std.While(
            cond=cond,
            attrs=attrs,
            body=body,
        )
        without_attrs = std.While(
            cond=cond,
            body=body,
        )
        with_empty_attrs = std.While(
            cond=cond,
            attrs={},
            body=body,
        )

        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == attrs
        assert without_attrs.attrs is None
        assert with_attrs.text() == 'with std.while_(x < std.i32(2), pragma="pipeline"):\n  y = 2'
        assert without_attrs.text() == "while x < std.i32(2):\n  y = 2"
        assert with_empty_attrs.text() == "while x < std.i32(2):\n  y = 2"

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.While(
            cond=std.Lt(ty=std.PrimTy("bool"), a=x, b=2),
            attrs={"tag": "demo"},
            body=[
                std.BindExpr(
                    std.IntImm(std.PrimTy("int64"), 2),
                    std.Var(ty=i32, name="y"),
                )
            ],
        )

        assert node.text() == 'with std.while_(x < std.i32(2), tag="demo"):\n  y = 2'

    def test_text_format_with_simple_while(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.While(
            cond=std.Lt(ty=std.PrimTy("bool"), a=x, b=2),
            body=[
                std.BindExpr(
                    std.IntImm(std.PrimTy("int64"), 2),
                    std.Var(ty=i32, name="y"),
                )
            ],
        )

        assert node.text() == "while x < std.i32(2):\n  y = 2"

    def test_text_format_with_sorted_attrs(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.While(
            cond=std.Lt(ty=std.PrimTy("bool"), a=x, b=2),
            attrs={"z": 3, "a": 1},
            body=[
                std.BindExpr(
                    std.IntImm(std.PrimTy("int64"), 2),
                    std.Var(ty=i32, name="y"),
                )
            ],
        )

        assert node.text() == "with std.while_(x < std.i32(2), a=1, z=3):\n  y = 2"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.While(
            cond=std.Lt(
                ty=std.PrimTy("bool"),
                a=std.Var(ty=i32, name="x"),
                b=2,
            ),
            attrs={"tag": "demo"},
            body=[
                std.BindExpr(
                    std.IntImm(std.PrimTy("int64"), 2),
                    std.Var(ty=i32, name="y"),
                )
            ],
        )
        rhs = std.While(
            cond=std.Lt(
                ty=std.PrimTy("bool"),
                a=std.Var(ty=i32, name="x"),
                b=2,
            ),
            attrs={"tag": "demo"},
            body=[
                std.BindExpr(
                    std.IntImm(std.PrimTy("int64"), 2),
                    std.Var(ty=i32, name="y"),
                )
            ],
        )
        different = std.While(
            cond=std.Gt(
                ty=std.PrimTy("bool"),
                a=std.Var(ty=i32, name="x"),
                b=2,
            ),
            attrs={"tag": "demo"},
            body=[
                std.BindExpr(
                    std.IntImm(std.PrimTy("int64"), 2),
                    std.Var(ty=i32, name="y"),
                )
            ],
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)

    def test_rejects_vector_bool_condition(self) -> None:
        boolx4 = std.PrimTy("boolx4")

        with pytest.raises(TypeError, match="condition dtype must be scalar bool"):
            std.While(cond=std.BoolImm(boolx4, True), body=[])


class TestScope:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        body = [std.Return(x)]
        node = std.Scope(
            attrs={"tag": "demo"},
            binds=[std.VarDef(x)],
            body=body,
        )

        assert isinstance(node, std.Scope)
        assert tuple(field.name for field in fields(std.Scope)) == (
            "attrs",
            "binds",
            "body",
        )
        assert node.attrs is not None
        assert isinstance(node.binds[0], std.VarDef)
        assert list(node.binds[0].vars) == [x]
        assert list(node.body) == body

    def test_attrs_field_accepts_dict_attrs_and_none(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        body = [std.Return(x)]
        attrs = {"pragma": "scope"}
        with_attrs = std.Scope(attrs=attrs, binds=[], body=body)
        without_attrs = std.Scope(binds=[], body=body)
        with_empty_attrs = std.Scope(
            attrs={},
            binds=[],
            body=body,
        )

        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == attrs
        assert without_attrs.attrs is None
        assert with_attrs.text() == 'with std.scope(pragma="scope"):\n  return x'
        assert without_attrs.text() == "return x"
        assert with_empty_attrs.text() == "return x"

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.Scope(
            binds=[std.VarDef(x)],
            body=[std.Return(x)],
        )

        assert node.text() == "with std.scope(std.VarDef(std.i32)) as x:\n  return x"

    def test_text_format_with_simple_scope(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.Scope(binds=[], body=[std.Return(x)])

        assert node.text() == "return x"

    def test_text_format_with_sorted_attrs_and_vars(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        state = std.Var(ty=i32, name="state")
        node = std.Scope(
            attrs={"z": 3, "a": 1},
            binds=[
                std.VarDef(x),
                std.VarDef(state),
            ],
            body=[std.Return(x)],
        )

        assert (
            node.text() == "with std.scope(std.VarDef(std.i32), std.VarDef(std.i32), "
            "a=1, z=3) as (x, state):\n  return x"
        )

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Scope(
            attrs={"tag": "demo"},
            binds=[std.VarDef(std.Var(ty=i32, name="x"))],
            body=[std.Return(std.Var(ty=i32, name="x"))],
        )
        rhs = std.Scope(
            attrs={"tag": "demo"},
            binds=[std.VarDef(std.Var(ty=i32, name="x"))],
            body=[std.Return(std.Var(ty=i32, name="x"))],
        )
        different = std.Scope(
            attrs={"tag": "other"},
            binds=[std.VarDef(std.Var(ty=i32, name="x"))],
            body=[std.Return(std.Var(ty=i32, name="x"))],
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestBindExpr:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        value = 1
        expr = std.IntImm(std.PrimTy("int64"), value)
        attrs = {"tag": "demo"}
        var = std.Var(ty=i32, name="y")
        node = std.BindExpr(expr, var, **attrs)

        assert isinstance(node, std.BindExpr)
        assert tuple(field.name for field in fields(std.BindExpr)) == ("attrs", "vars", "expr")
        assert list(node.vars) == [var]
        assert isinstance(node.attrs, std.DictAttrs)
        assert dict(node.attrs.values) == attrs
        assert isinstance(node.expr, std.IntImm)
        assert node.expr.value == value

    def test_constructor_normalizes_python_literals(self) -> None:
        int_bind = std.BindExpr(1)
        bool_bind = std.BindExpr(True)
        float_bind = std.BindExpr(1.5)
        str_bind = std.BindExpr("x")

        assert isinstance(int_bind.expr, std.IntImm)
        assert tvm_ffi.structural_equal(int_bind.expr.ty, std.PrimTy("int64"))
        assert int_bind.expr.value == 1

        assert isinstance(bool_bind.expr, std.BoolImm)
        assert tvm_ffi.structural_equal(bool_bind.expr.ty, std.PrimTy("bool"))
        assert bool_bind.expr.value is True

        assert isinstance(float_bind.expr, std.FloatImm)
        assert tvm_ffi.structural_equal(float_bind.expr.ty, std.PrimTy("float32"))
        assert float_bind.expr.value == 1.5

        assert isinstance(str_bind.expr, std.StringImm)
        assert tvm_ffi.structural_equal(str_bind.expr.ty, std.AnyTy())
        assert str_bind.expr.value == "x"

    def test_attrs_field_accepts_dict_attrs_and_none(self) -> None:
        i32 = std.PrimTy("int32")
        i64 = std.PrimTy("int64")
        var = std.Var(ty=i32, name="y")
        with_attrs = std.BindExpr(std.IntImm(i64, 1), var, tag="demo")
        with_empty_attrs = std.BindExpr(std.IntImm(i64, 1), var)
        without_attrs = std.BindExpr(std.IntImm(i64, 1), var)

        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == {"tag": "demo"}
        assert with_empty_attrs.attrs is None
        assert without_attrs.attrs is None
        assert with_attrs.text() == 'y = std.BindExpr(1, tag="demo")'
        assert with_empty_attrs.text() == "y = 1"
        assert without_attrs.text() == "y = 1"

    def test_text_format_without_vars(self) -> None:
        i64 = std.PrimTy("int64")
        assert std.BindExpr(std.IntImm(i64, 1), tag="demo").text() == 'std.BindExpr(1, tag="demo")'
        assert std.BindExpr(std.IntImm(i64, 1)).text() == "1"

    def test_text_format_with_single_var(self) -> None:
        i32 = std.PrimTy("int32")
        i64 = std.PrimTy("int64")
        with_attrs = std.BindExpr(std.IntImm(i64, 1), std.Var(ty=i32, name="y"), tag="demo")
        without_attrs = std.BindExpr(std.IntImm(i64, 1), std.Var(ty=i32, name="y"))

        assert with_attrs.text() == 'y = std.BindExpr(1, tag="demo")'
        assert without_attrs.text() == "y = 1"

    def test_text_format_with_multiple_vars(self) -> None:
        i32 = std.PrimTy("int32")
        i64 = std.PrimTy("int64")
        with_attrs = std.BindExpr(
            std.IntImm(i64, 1),
            std.Var(ty=i32, name="y"),
            std.Var(ty=i32, name="z"),
            z=2,
            a=1,
        )
        without_attrs = std.BindExpr(
            std.IntImm(i64, 1),
            std.Var(ty=i32, name="y"),
            std.Var(ty=i32, name="z"),
        )

        assert with_attrs.text() == "y, z = std.BindExpr(1, a=1, z=2)"
        assert without_attrs.text() == "y, z = 1"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        i64 = std.PrimTy("int64")
        lhs = std.BindExpr(std.IntImm(i64, 1), std.Var(ty=i32, name="y"), tag="demo")
        rhs = std.BindExpr(std.IntImm(i64, 1), std.Var(ty=i32, name="renamed"), tag="demo")
        different = std.BindExpr(std.IntImm(i64, 2), std.Var(ty=i32, name="y"), tag="demo")

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestVarDef:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        var = std.Var(ty=i32, name="y")
        node = std.VarDef(var, tag="demo")

        assert isinstance(node, std.VarDef)
        assert tuple(field.name for field in fields(std.VarDef)) == ("attrs", "vars")
        assert list(node.vars) == [var]
        assert isinstance(node.attrs, std.DictAttrs)
        assert dict(node.attrs.values) == {"tag": "demo"}

    def test_constructor_normalizes_types_to_unnamed_vars(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.VarDef(i32, "float32")

        assert len(node.vars) == 2
        assert node.vars[0].name == ""
        assert tvm_ffi.structural_equal(node.vars[0].ty, i32)
        assert node.vars[1].name == ""
        assert tvm_ffi.structural_equal(node.vars[1].ty, std.PrimTy("float32"))
        assert node.text() == "v, v_1 = std.VarDef(std.i32, std.f32)"

    def test_text_format_without_attrs(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.VarDef(std.Var(ty=i32, name="y"))

        assert node.text() == "y = std.VarDef(std.i32)"

    def test_text_format_with_attrs(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.VarDef(std.Var(ty=i32, name="y"), tag="demo")

        assert node.text() == 'y = std.VarDef(std.i32, tag="demo")'
        assert std.VarDef(std.Var(ty=i32, name="y")).text() == "y = std.VarDef(std.i32)"

    def test_text_format_with_multiple_vars(self) -> None:
        i32 = std.PrimTy("int32")
        bf16_3x12 = std.TensorTy(shape=[3, 12], dtype="bfloat16")
        with_attrs = std.VarDef(
            std.Var(ty=i32, name="y"),
            std.Var(ty=bf16_3x12, name="z"),
            tag="demo",
        )
        without_attrs = std.VarDef(
            std.Var(ty=i32, name="y"),
            std.Var(ty=bf16_3x12, name="z"),
        )

        assert with_attrs.text() == 'y, z = std.VarDef(std.i32, std.bf16[3, 12], tag="demo")'
        assert without_attrs.text() == "y, z = std.VarDef(std.i32, std.bf16[3, 12])"

    def test_text_format_without_vars(self) -> None:
        assert std.VarDef().text() == "pass"
        assert std.VarDef(tag="demo").text() == 'std.VarDef(tag="demo")'

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.VarDef(std.Var(ty=i32, name="y"), tag="demo")
        rhs = std.VarDef(std.Var(ty=i32, name="renamed"), tag="demo")
        different = std.VarDef(std.Var(ty=i32, name="y"), tag="other")

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestStore:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        index = 1
        rhs = 2
        node = std.Store(x, rhs, index)

        assert isinstance(node, std.Store)
        assert tuple(field.name for field in fields(std.Store)) == (
            "attrs",
            "lhs",
            "indices",
            "rhs",
        )
        assert node.attrs is None
        assert node.lhs == x
        indices = list(node.indices)
        assert isinstance(indices[0], std.Range)
        assert isinstance(indices[0].start, std.IntImm)
        assert indices[0].start.value == index
        assert isinstance(node.rhs, std.IntImm)
        assert node.rhs.value == rhs

        with_attrs = std.Store(x, rhs, index, tag="demo")
        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == {"tag": "demo"}

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Store(std.Var(ty=i32, name="x"), 2, 1)
        with_attrs = std.Store(std.Var(ty=i32, name="x"), 2, 1, tag="demo")

        assert node.text() == "x[1] = 2"
        assert with_attrs.text() == 'std.Store(x, 2, 1, tag="demo")'

    def test_text_format_index_variants(self) -> None:
        i32 = std.PrimTy("int32")

        no_indices = std.Store(std.Var(ty=i32, name="x"), 2)
        assert no_indices.text() == "x[()] = 2"

        slice_without_step = std.Store(
            std.Var(ty=i32, name="x"),
            3,
            std.Range(
                start=1,
                stop=2,
            ),
        )
        assert slice_without_step.text() == "x[1:2] = 3"

        slice_without_start = std.Store(
            std.Var(ty=i32, name="x"),
            3,
            std.Range(
                start=None,
                stop=2,
            ),
        )
        assert slice_without_start.text() == "x[:2] = 3"

        mixed_indices = std.Store(
            std.Var(ty=i32, name="x"),
            4,
            std.Range(
                start=1,
                stop=2,
            ),
            3,
        )
        assert mixed_indices.text() == "x[1:2, 3] = 4"

    def test_constructor_converts_python_indices_and_rhs(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Store(std.Var(ty=i32, name="x"), 2, 1)

        index = next(iter(node.indices))
        assert isinstance(index, std.Range)
        assert isinstance(index.start, std.IntImm)
        assert isinstance(node.rhs, std.IntImm)
        assert node.text() == "x[1] = 2"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Store(std.Var(ty=i32, name="x"), 2, 1)
        rhs = std.Store(std.Var(ty=i32, name="x"), 2, 1)
        different = std.Store(std.Var(ty=i32, name="x"), 3, 1)

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)

    def test_rejects_rhs_dtype_mismatch(self) -> None:
        i32 = std.PrimTy("int32")
        f32 = std.PrimTy("float32")

        with pytest.raises(TypeError, match="stored value type"):
            std.Store(std.Var(ty=i32, name="x"), std.FloatImm(f32, 2.0), 1)


class TestAssert:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        cond = std.Lt(ty=std.PrimTy("bool"), a=x, b=2)
        node = std.Assert(cond=cond)

        assert isinstance(node, std.Assert)
        assert tuple(field.name for field in fields(std.Assert)) == ("attrs", "cond")
        assert node.attrs is None
        assert node.cond == cond

        with_attrs = std.Assert(cond, tag="demo")
        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == {"tag": "demo"}

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")

        assert (
            std.Assert(std.Lt(ty=std.PrimTy("bool"), a=x, b=std.IntImm(i32, 2))).text()
            == "assert x < std.i32(2)"
        )
        assert (
            std.Assert(std.Lt(ty=std.PrimTy("bool"), a=x, b=std.IntImm(i32, 2)), tag="demo").text()
            == 'std.Assert(x < std.i32(2), tag="demo")'
        )

    def test_constructor_converts_python_cond(self) -> None:
        node = std.Assert(1)

        assert isinstance(node.cond, std.IntImm)
        assert node.cond.value == 1
        assert node.text() == "assert 1"

    def test_rejects_non_bool_concrete_condition(self) -> None:
        i32 = std.PrimTy("int32")

        with pytest.raises(TypeError, match="condition dtype must be bool8"):
            std.Assert(std.IntImm(i32, 1))

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Assert(
            std.Lt(ty=std.PrimTy("bool"), a=std.Var(ty=i32, name="x"), b=2), tag="demo"
        )
        rhs = std.Assert(
            std.Lt(ty=std.PrimTy("bool"), a=std.Var(ty=i32, name="renamed"), b=2), tag="demo"
        )
        different = std.Assert(
            std.Lt(ty=std.PrimTy("bool"), a=std.Var(ty=i32, name="x"), b=3), tag="demo"
        )

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestReturn:
    def test_constructor(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        y = std.Var(ty=i32, name="y")
        node = std.Return(x, y)

        assert isinstance(node, std.Return)
        assert tuple(field.name for field in fields(std.Return)) == ("attrs", "exprs")
        assert node.attrs is None
        assert list(node.exprs) == [x, y]

        with_attrs = std.Return(x, y, tag="demo")
        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == {"tag": "demo"}

    def test_text_format(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Return(std.Var(ty=i32, name="x"), std.Var(ty=i32, name="y"))
        with_attrs = std.Return(std.Var(ty=i32, name="x"), tag="demo")

        assert node.text() == "return (x, y)"
        assert with_attrs.text() == 'std.Return(x, tag="demo")'

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Return(std.Var(ty=i32, name="x"), std.Var(ty=i32, name="y"))
        rhs = std.Return(std.Var(ty=i32, name="renamed_x"), std.Var(ty=i32, name="renamed_y"))
        different = std.Return(std.Var(ty=i32, name="x"))

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestYield:
    def test_constructor(self) -> None:
        x = std.Var(ty=std.PrimTy("int32"), name="x")
        y = std.Var(ty=std.PrimTy("int32"), name="y")
        node = std.Yield(x, y)

        assert isinstance(node, std.Yield)
        assert tuple(field.name for field in fields(std.Yield)) == ("attrs", "exprs")
        assert node.attrs is None
        assert list(node.exprs) == [x, y]

        with_attrs = std.Yield(x, y, tag="demo")
        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == {"tag": "demo"}

    def test_text_format(self) -> None:
        node = std.Yield(std.Var(ty=std.PrimTy("int32"), name="x"))
        with_attrs = std.Yield(std.Var(ty=std.PrimTy("int32"), name="x"), tag="demo")

        assert node.text() == "yield x"
        assert with_attrs.text() == 'std.Yield(x, tag="demo")'

    def test_text_format_with_multiple_vars(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Yield(std.Var(ty=i32, name="x"), std.Var(ty=i32, name="y"))

        assert node.text() == "yield (x, y)"

    def test_text_format_without_vars(self) -> None:
        node = std.Yield()

        assert node.text() == "yield"

    def test_structural_equality(self) -> None:
        i32 = std.PrimTy("int32")
        lhs = std.Yield(std.Var(ty=i32, name="x"), std.Var(ty=i32, name="y"))
        rhs = std.Yield(std.Var(ty=i32, name="renamed_x"), std.Var(ty=i32, name="renamed_y"))
        different = std.Yield(std.Var(ty=i32, name="x"))

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestBreak:
    def test_constructor(self) -> None:
        node = std.Break()

        assert isinstance(node, std.Break)
        assert tuple(field.name for field in fields(std.Break)) == ("attrs",)
        assert node.attrs is None

        with_attrs = std.Break(tag="demo")
        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == {"tag": "demo"}

    def test_text_format(self) -> None:
        node = std.Break()
        with_attrs = std.Break(tag="demo")

        assert node.text() == "break"
        assert with_attrs.text() == 'std.Break(tag="demo")'

    def test_structural_equality(self) -> None:
        lhs = std.Break()
        rhs = std.Break()
        different = std.Continue()

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestContinue:
    def test_constructor(self) -> None:
        node = std.Continue()

        assert isinstance(node, std.Continue)
        assert tuple(field.name for field in fields(std.Continue)) == ("attrs",)
        assert node.attrs is None

        with_attrs = std.Continue(tag="demo")
        assert isinstance(with_attrs.attrs, std.DictAttrs)
        assert dict(with_attrs.attrs.values) == {"tag": "demo"}

    def test_text_format(self) -> None:
        node = std.Continue()
        with_attrs = std.Continue(tag="demo")

        assert node.text() == "continue"
        assert with_attrs.text() == 'std.Continue(tag="demo")'

    def test_structural_equality(self) -> None:
        lhs = std.Continue()
        rhs = std.Continue()
        different = std.Break()

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestDictAttrs:
    def test_constructor(self) -> None:
        node = std.DictAttrs(tag="demo")

        assert isinstance(node, std.DictAttrs)
        assert tuple(field.name for field in fields(std.DictAttrs)) == ("values",)
        assert dict(node.values) == {"tag": "demo"}

    def test_text_format(self) -> None:
        node = std.DictAttrs(tag="demo")

        assert node.text() == 'std.DictAttrs(tag="demo")'

    def test_text_format_sorts_keys(self) -> None:
        node = std.DictAttrs(z=2, a=1)

        assert node.text() == "std.DictAttrs(a=1, z=2)"

    def test_text_format_empty(self) -> None:
        node = std.DictAttrs()

        assert node.text() == "std.DictAttrs()"

    def test_text_print_hook_returns_keyword_only_call_ast(self) -> None:
        node = std.DictAttrs(z=2, a=1)
        ast_node = pyast.IRPrinter()(node, AccessPath.root())

        assert isinstance(ast_node, pyast.Call)
        assert list(ast_node.args) == []
        assert list(ast_node.kwargs_keys) == ["a", "z"]
        assert [value.to_python() for value in ast_node.kwargs_values] == ["1", "2"]

    def test_mapping_protocol(self) -> None:
        node = std.DictAttrs(tag="demo", count=2)

        assert len(node) == 2
        assert dict(node) == {"tag": "demo", "count": 2}
        assert set(node) == {"tag", "count"}
        assert node["tag"] == "demo"
        assert node.get("count") == 2
        assert node.get("missing", "fallback") == "fallback"
        assert "tag" in node
        assert "missing" not in node
        assert set(node.keys()) == {"tag", "count"}
        assert dict(node.items()) == {"tag": "demo", "count": 2}

    def test_structural_equality(self) -> None:
        lhs = std.DictAttrs(tag="demo")
        rhs = std.DictAttrs(tag="demo")
        different = std.DictAttrs(tag="other")

        assert tvm_ffi.structural_equal(lhs, rhs)
        assert tvm_ffi.structural_hash(lhs) == tvm_ffi.structural_hash(rhs)
        assert not tvm_ffi.structural_equal(lhs, different)


class TestDialectMnemonic:
    def test_base_classes_have_python_dialect_mnemonics_but_no_type_attr(self) -> None:
        cases = [
            (std.Node, ("std", "Node")),
            (std.Ty, ("std", "Ty")),
            (std.Stmt, ("std", "Stmt")),
            (std.Expr, ("std", "Expr")),
            (std.Attrs, ("std", "Attrs")),
            (std.Aggregate, ("std", "Aggregate")),
        ]
        for cls, dialect_mnemonic in cases:
            cls_any = cast(Any, cls)
            info = cls_any.__tvm_ffi_type_info__

            assert cls_any.__ffi_dialect_mnemonic__ == dialect_mnemonic
            assert core._lookup_type_attr(info.type_index, "__ffi_dialect_mnemonic__") is None

    def test_concrete_classes_have_exact_ffi_dialect_mnemonics(self) -> None:
        cases = [
            (std.AnyTy, ("std", "Any")),
            (std.PrimTy, ("std", "Prim")),
            (std.TupleTy, ("std", "Tuple")),
            (std.TensorTy, ("std", "Tensor")),
            (std.Range, ("std", "Range")),
            (std.DictAttrs, ("std", "DictAttrs")),
            (std.Var, ("std", "Var")),
            (std.Func, ("std", "Func")),
            (std.Module, ("std", "Module")),
            (std.BoolImm, ("std", "BoolImm")),
            (std.IntImm, ("std", "IntImm")),
            (std.FloatImm, ("std", "FloatImm")),
            (std.StringImm, ("std", "StringImm")),
            (std.Add, ("std", "Add")),
            (std.Sub, ("std", "Sub")),
            (std.Mul, ("std", "Mul")),
            (std.CDiv, ("std", "CDiv")),
            (std.FloorDiv, ("std", "FloorDiv")),
            (std.FloorMod, ("std", "FloorMod")),
            (std.CMod, ("std", "CMod")),
            (std.Pow, ("std", "Pow")),
            (std.LShift, ("std", "LShift")),
            (std.RShift, ("std", "RShift")),
            (std.BitwiseAnd, ("std", "BitwiseAnd")),
            (std.BitwiseOr, ("std", "BitwiseOr")),
            (std.BitwiseXor, ("std", "BitwiseXor")),
            (std.Min, ("std", "Min")),
            (std.Max, ("std", "Max")),
            (std.Eq, ("std", "Eq")),
            (std.Ne, ("std", "Ne")),
            (std.Le, ("std", "Le")),
            (std.Ge, ("std", "Ge")),
            (std.Gt, ("std", "Gt")),
            (std.Lt, ("std", "Lt")),
            (std.And, ("std", "And")),
            (std.Or, ("std", "Or")),
            (std.Not, ("std", "Not")),
            (std.BitwiseNot, ("std", "BitwiseNot")),
            (std.Abs, ("std", "Abs")),
            (std.IfExpr, ("std", "IfExpr")),
            (std.Load, ("std", "Load")),
            (std.Cast, ("std", "Cast")),
            (std.Call, ("std", "Call")),
            (std.IfStmt, ("std", "IfStmt")),
            (std.Scope, ("std", "Scope")),
            (std.For, ("std", "For")),
            (std.While, ("std", "While")),
            (std.BindExpr, ("std", "BindExpr")),
            (std.VarDef, ("std", "VarDef")),
            (std.Store, ("std", "Store")),
            (std.Assert, ("std", "Assert")),
            (std.Return, ("std", "Return")),
            (std.Yield, ("std", "Yield")),
            (std.Break, ("std", "Break")),
            (std.Continue, ("std", "Continue")),
        ]

        for cls, dialect_mnemonic in cases:
            cls_any = cast(Any, cls)
            info = cls_any.__tvm_ffi_type_info__

            assert cls_any.__ffi_dialect_mnemonic__ == dialect_mnemonic
            assert (
                tuple(core._lookup_type_attr(info.type_index, "__ffi_dialect_mnemonic__"))
                == dialect_mnemonic
            )

    def test_every_exported_concrete_node_has_registered_dialect_mnemonic(self) -> None:
        abstract = {std.Node, std.Ty, std.Stmt, std.Expr, std.Attrs, std.Aggregate}
        concrete_classes = []
        for name in std.__all__:
            cls = getattr(std, name)
            if isinstance(cls, type) and issubclass(cls, std.Node) and cls not in abstract:
                concrete_classes.append(cls)

        assert len(concrete_classes) == 55
        for cls in concrete_classes:
            cls_any = cast(Any, cls)
            info = cls_any.__tvm_ffi_type_info__
            dialect_mnemonic = tuple(
                core._lookup_type_attr(info.type_index, "__ffi_dialect_mnemonic__")
            )

            expected_mnemonic = {
                std.AnyTy: ("std", "Any"),
                std.PrimTy: ("std", "Prim"),
                std.TupleTy: ("std", "Tuple"),
                std.TensorTy: ("std", "Tensor"),
            }.get(cls, ("std", cls.__name__))
            assert dialect_mnemonic[:2] == expected_mnemonic
            assert cls_any.__ffi_dialect_mnemonic__ == dialect_mnemonic
            assert info.type_key == f"ffi.std.{cls.__name__}"

    def test_dialect_mnemonics_are_unique_and_well_formed(self) -> None:
        abstract = {std.Node, std.Ty, std.Stmt, std.Expr, std.Attrs, std.Aggregate}
        dialect_mnemonics = []
        for name in std.__all__:
            cls = getattr(std, name)
            if isinstance(cls, type) and issubclass(cls, std.Node) and cls not in abstract:
                cls_any = cast(Any, cls)
                info = cls_any.__tvm_ffi_type_info__
                dialect_mnemonics.append(
                    tuple(core._lookup_type_attr(info.type_index, "__ffi_dialect_mnemonic__"))
                )

        full_mnemonics = [f"{item[0]}${item[1]}" for item in dialect_mnemonics]
        assert len(full_mnemonics) == len(set(full_mnemonics))
        for dialect_mnemonic in dialect_mnemonics:
            assert len(dialect_mnemonic) == 2
            dialect, name = dialect_mnemonic
            assert dialect == "std"
            assert name.isidentifier()

    def test_dialect_mnemonics_are_classvars_not_reflected_fields(self) -> None:
        abstract = {std.Node, std.Ty, std.Stmt, std.Expr, std.Attrs, std.Aggregate}
        for name in std.__all__:
            cls = getattr(std, name)
            if isinstance(cls, type) and issubclass(cls, std.Node) and cls not in abstract:
                assert "__ffi_dialect_mnemonic__" in cls.__annotations__
                assert "__ffi_dialect_mnemonic__" in cls.__dict__
                assert "__ffi_dialect_mnemonic__" not in [field.name for field in fields(cls)]
                assert "__ffi_mnemonic__" not in cls.__dict__
                assert "__ffi_text_generics__" not in cls.__dict__

    def test_text_print_hooks_and_dialect_mnemonics_are_independent_type_attrs(self) -> None:
        for cls in [std.Node, std.Expr, std.AnyTy, std.Var, std.Add, std.Func, std.DictAttrs]:
            cls_any = cast(Any, cls)
            info = cls_any.__tvm_ffi_type_info__
            text_print = core._lookup_type_attr(info.type_index, "__ffi_text_print__")
            dialect_mnemonic = core._lookup_type_attr(info.type_index, "__ffi_dialect_mnemonic__")

            assert callable(text_print)
            if cls in [std.Node, std.Expr]:
                assert dialect_mnemonic is None
            else:
                expected_mnemonic = {
                    std.AnyTy: ("std", "Any"),
                    std.PrimTy: ("std", "Prim"),
                    std.TupleTy: ("std", "Tuple"),
                    std.TensorTy: ("std", "Tensor"),
                }.get(cls, ("std", cls.__name__))
                assert tuple(dialect_mnemonic)[:2] == expected_mnemonic

    def test_instance_runtime_types_resolve_to_class_dialect_mnemonics(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(i32, "x")
        one = std.IntImm(i32, 1)
        cases = [
            (i32, std.PrimTy),
            (x, std.Var),
            (std.BoolImm(std.PrimTy("bool"), True), std.BoolImm),
            (std.Range(start=0, stop=4), std.Range),
            (std.Add(x, one, ty=i32), std.Add),
            (std.CDiv(x, one, ty=i32), std.CDiv),
            (std.Call("callee", x, tag="demo", ty=i32), std.Call),
            (std.BindExpr(one, x), std.BindExpr),
            (std.VarDef(x, tag="demo"), std.VarDef),
            (std.Store(x, one), std.Store),
            (std.Assert(std.BoolImm(std.PrimTy("bool"), True)), std.Assert),
            (std.Return(x), std.Return),
            (std.Yield(x), std.Yield),
            (std.Break(), std.Break),
            (std.Continue(), std.Continue),
        ]

        for node, cls in cases:
            cls_any = cast(Any, cls)
            info = cls_any.__tvm_ffi_type_info__

            assert isinstance(node, cls)
            expected_mnemonic = {
                std.AnyTy: ("std", "Any"),
                std.PrimTy: ("std", "Prim"),
                std.TupleTy: ("std", "Tuple"),
                std.TensorTy: ("std", "Tensor"),
            }.get(cls, ("std", cls.__name__))
            dialect_mnemonic = tuple(
                core._lookup_type_attr(info.type_index, "__ffi_dialect_mnemonic__")
            )
            assert dialect_mnemonic[:2] == expected_mnemonic

    def test_all_concrete_classes_have_two_element_dialect_mnemonics(self) -> None:
        abstract = {std.Node, std.Ty, std.Stmt, std.Expr, std.Attrs, std.Aggregate}
        for name in std.__all__:
            cls = getattr(std, name)
            if isinstance(cls, type) and issubclass(cls, std.Node) and cls not in abstract:
                cls_any = cast(Any, cls)
                info = cls_any.__tvm_ffi_type_info__

                assert len(cls_any.__ffi_dialect_mnemonic__) == 2
                assert len(core._lookup_type_attr(info.type_index, "__ffi_dialect_mnemonic__")) == 2


class TestTextSugar:
    def test_operation_sugar_preserves_typed_immediate_operands(self) -> None:
        i32 = std.PrimTy("int32")
        node = std.Add(std.IntImm(i32, 1), std.IntImm(i32, 2), ty=i32)
        printer = pyast.IRPrinter()

        assert printer(node, AccessPath.root()).to_python() == "std.i32(1) + std.i32(2)"

    def test_no_operand_statement_sugar(self) -> None:
        node = std.Break()
        printer = pyast.IRPrinter()

        assert printer(node, AccessPath.root()).to_python() == "break"

    def test_explicit_forms_preserve_attrs(self) -> None:
        i32 = std.PrimTy("int32")
        printer = pyast.IRPrinter()

        bind_expr = printer(
            std.BindExpr(std.IntImm(i32, 1), tag="demo"),
            AccessPath.root(),
        )
        bind_var_def = printer(
            std.VarDef(tag="demo"),
            AccessPath.root(),
        )

        assert bind_expr.to_python() == 'std.BindExpr(std.i32(1), tag="demo")'
        assert bind_var_def.to_python() == 'std.VarDef(tag="demo")'

    def test_operation_sugar_uses_named_operands(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(i32, "x")
        node = std.Add(x, std.IntImm(i32, 1), ty=i32)

        printer = pyast.IRPrinter()
        assert printer(node, AccessPath.root()).to_python() == "x + std.i32(1)"

    def test_literal_only_ops_use_explicit_form(self) -> None:
        i64 = std.PrimTy("int64")
        node = std.Add(1, 2, ty=i64)
        printer = pyast.IRPrinter()

        assert printer(node, AccessPath.root()).to_python() == "std.Add(1, 2, ty=std.i64)"

        printer.dialect_stack = ["other"]

        assert printer(node, AccessPath.root()).to_python() == "std.Add(1, 2, ty=std.i64)"

    def test_operand_dialect_allows_sugar_outside_active_stack(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(i32, "x")
        node = std.Add(x, 1, ty=i32)
        printer = pyast.IRPrinter()
        printer.dialect_stack = ["other"]

        assert printer(node, AccessPath.root()).to_python() == "x + std.i32(1)"

    def test_any_type_uses_generic_with_any_operand(self) -> None:
        any_ty = std.AnyTy()
        x = std.Var(any_ty, "x")
        node = std.Add(x, 1, ty=any_ty)
        printer = pyast.IRPrinter()

        assert printer(node, AccessPath.root()).to_python() == "x + 1"


class TestDialectPrintMap:
    def test_dialect_prefix_can_be_dropped(self) -> None:
        node = std.DictAttrs(tag="demo")
        cfg = pyast.PrinterConfig(dialect_print_map={"std": "*"})

        assert node.text(cfg) == 'DictAttrs(tag="demo")'

    def test_dialect_prefix_can_be_renamed(self) -> None:
        node = std.DictAttrs(tag="demo")
        cfg = pyast.PrinterConfig(dialect_print_map={"std": "core"})

        assert node.text(cfg) == 'core.DictAttrs(tag="demo")'

    def test_full_mnemonic_can_drop_prefix(self) -> None:
        node = std.DictAttrs(tag="demo")
        cfg = pyast.PrinterConfig(dialect_print_map={"std$DictAttrs": "*"})

        assert node.text(cfg) == 'DictAttrs(tag="demo")'

    def test_full_mnemonic_can_use_explicit_name(self) -> None:
        node = std.DictAttrs(tag="demo")
        cfg = pyast.PrinterConfig(dialect_print_map={"std$DictAttrs": "std.MyAttrs"})

        assert node.text(cfg) == 'std.MyAttrs(tag="demo")'

    def test_full_mnemonic_takes_precedence_over_dialect(self) -> None:
        node = std.DictAttrs(tag="demo")
        cfg = pyast.PrinterConfig(dialect_print_map={"std": "core", "std$DictAttrs": "*"})

        assert node.text(cfg) == 'DictAttrs(tag="demo")'

    def test_dialect_prefix_applies_to_func_decorator(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.Func(
            symbol="main",
            args=[x],
            ret_type=i32,
            body=[std.Return(x)],
        )
        cfg = pyast.PrinterConfig(dialect_print_map={"std": "core"})

        assert node.text(cfg) == "@core.func\ndef main(x: core.i32) -> core.i32:\n  return x"

    def test_full_mnemonic_applies_to_func_decorator(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.Func(
            symbol="main",
            attrs={"tag": "demo"},
            args=[x],
            ret_type=i32,
            body=[std.Return(x)],
        )
        cfg = pyast.PrinterConfig(dialect_print_map={"std$func": "ffi_func"})

        assert (
            node.text(cfg) == '@ffi_func(tag="demo")\ndef main(x: std.i32) -> std.i32:\n  return x'
        )

    def test_dialect_prefix_applies_to_call_and_cast_helpers(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        cfg = pyast.PrinterConfig(dialect_print_map={"std": "*"})

        assert (
            std.Call("callee", x, tag="demo", ty=i32).text(cfg)
            == 'Call(callee, x, tag="demo", ty=i32)'
        )
        assert std.Cast(i32, x).text(cfg) == "i32(x)"

    def test_full_mnemonic_does_not_override_prim_type_cast_sugar(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        cfg = pyast.PrinterConfig(dialect_print_map={"std$Cast": "ffi.cast"})

        assert std.Cast(i32, x).text(cfg) == "std.i32(x)"

    def test_full_mnemonic_applies_to_call_helper(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        cfg = pyast.PrinterConfig(dialect_print_map={"std$Call": "ffi.call"})

        assert (
            std.Call("callee", x, tag="demo", ty=i32).text(cfg)
            == 'ffi.call(callee, x, tag="demo", ty=std.i32)'
        )

    def test_dialect_prefix_applies_to_for_range_mnemonic(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.For(
            start=1,
            stop=2,
            step=None,
            body=[std.Store(x, 2, 1)],
            vars=[x],
        )
        cfg = pyast.PrinterConfig(dialect_print_map={"": "core"})

        assert node.text(cfg) == "for x in core.range(1, 2):\n  x[1] = 2"

    def test_full_mnemonic_applies_to_for_range_mnemonic(self) -> None:
        i32 = std.PrimTy("int32")
        x = std.Var(ty=i32, name="x")
        node = std.For(
            start=1,
            stop=2,
            step=None,
            body=[std.Store(x, 2, 1)],
            vars=[x],
        )
        cfg = pyast.PrinterConfig(dialect_print_map={"$range": "ffi.range"})

        assert node.text(cfg) == "for x in ffi.range(1, 2):\n  x[1] = 2"


def test_std_base_classes_cannot_be_constructed_directly() -> None:
    for cls in [std.Node, std.Ty, std.Stmt, std.Expr, std.Attrs, std.Aggregate]:
        ctor = cast(Any, cls)
        with pytest.raises(TypeError, match="cannot be constructed directly"):
            ctor()
