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

import importlib

import pytest
import tilus  # Registers the Tilus dialect.
import tvm_ffi
from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi._pyast_parser import parse


def _input_vars(node: object) -> dict[str, std.Var]:
    values = (
        getattr(node, field.name)
        for field in dc.fields(type(node))
        if field.lang_kind == "arg" and field.name is not None
    )
    return {value.name: value for value in values if isinstance(value, std.Var)}


def _round_trip(node: object) -> None:
    assert tvm_ffi.structural_equal(parse(node.text(), extra_vars=_input_vars(node)), node)


def _import(name: str):
    return importlib.import_module(name)


def _return_int_body(value: int = 1) -> list[std.Stmt]:
    literal = std.IntImm.from_py(value)
    result = std.Var(literal.ty, "result")
    return [std.BindExpr(literal, result), std.Return(result)]


def test_parse_hand_written_global_layout() -> None:
    _import("tilus._tilus_lang")
    layout_mod = _import("tilus.ir.layout")

    source = 'tilus.GlobalLayout(16, 32, size=512, axes=["i0", "i1"], offset=0)'
    expected = layout_mod.global_row_major(16, 32)

    parsed = parse(source)
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)


def test_parse_hand_written_global_tensor() -> None:
    _import("tilus._tilus_lang")
    layout_mod = _import("tilus.ir.layout")
    tensor_mod = _import("tilus.ir.tensor")

    source = (
        "tilus.GlobalTensor("
        "std.f32, 16, 32, "
        'layout=tilus.GlobalLayout(16, 32, size=512, axes=["i0", "i1"], offset=0)'
        ")"
    )
    layout = layout_mod.global_row_major(16, 32)
    expected = tensor_mod.global_tensor("float32", (16, 32), layout=layout)

    parsed = parse(source)
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)


def test_parse_hand_written_instruction() -> None:
    _import("tilus._tilus_lang")
    layout_mod = _import("tilus.ir.layout")
    tensor_mod = _import("tilus.ir.tensor")
    inst_mod = _import("tilus.ir.instructions.generic")

    source = """
dst = tilus.LoadGlobal(
    src,
    ty=tilus.RegTensor(
        std.f32,
        16, 32,
        layout=tilus.RegisterLayout(
            16, 32,
            mode_shape=[16, 32],
            spatial_modes=[],
            local_modes=[0, 1],
        ),
    ),
    offsets=[0, 0],
    dims=[0, 1],
)
"""
    global_layout = layout_mod.global_row_major(16, 32)
    reg_layout = layout_mod.register_row_major(16, 32)
    src_ty = tensor_mod.global_tensor("float32", (16, 32), layout=global_layout)
    src = std.Var(src_ty, "src")
    dst_ty = tensor_mod.register_tensor("float32", (16, 32), layout=reg_layout)
    expected = inst_mod.LoadGlobalInst(
        src,
        output=std.Var(dst_ty, "dst"),
        offsets=[0, 0],
        dims=[0, 1],
    )

    parsed = parse(source, extra_vars={"src": src})
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)


def test_parse_load_shared_instruction_ty_hint() -> None:
    _import("tilus._tilus_lang")
    layout_mod = _import("tilus.ir.layout")
    tensor_mod = _import("tilus.ir.tensor")
    inst_mod = _import("tilus.ir.instructions.generic")

    source = """
dst = tilus.LoadShared(
    shared,
    ty=tilus.RegTensor(
        std.f32,
        8,
        layout=tilus.RegisterLayout(
            8,
            mode_shape=[8],
            spatial_modes=[],
            local_modes=[0],
        ),
    ),
)
"""
    shared_ty = tensor_mod.shared_tensor(
        "float32",
        (8,),
        layout=layout_mod.shared_layout((8,), mode_shape=(8,), mode_strides=(1,)),
    )
    dst_ty = tensor_mod.register_tensor(
        "float32",
        (8,),
        layout=layout_mod.register_layout((8,), mode_shape=(8,), local_modes=(0,)),
    )
    expected = inst_mod.LoadSharedInst(
        std.Var(shared_ty, "shared"),
        output=std.Var(dst_ty, "dst"),
    )

    parsed = parse(source, extra_vars={"shared": std.Var(shared_ty, "shared")})
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)


def test_parse_load_global_ty_hint_must_match_operand() -> None:
    _import("tilus._tilus_lang")

    source = """
dst = tilus.LoadGlobal(
    src,
    ty=tilus.RegTensor(std.f16, 16),
    offsets=[0],
    dims=[0],
)
"""

    src = std.Var(tilus.GlobalTensor("float32", 16), "src")
    with pytest.raises(TypeError, match="must match src dtype and storage scope"):
        parse(source, extra_vars={"src": src})


def test_parse_tensor_optional_layout_alias_matches_default_printer() -> None:
    _import("tilus._tilus_lang")

    source = "tilus.RegTensor(std.f32, 2, 2, optional_layout=None)"
    expected = tilus.RegTensor("float32", 2, 2)

    assert tvm_ffi.structural_equal(parse(source), expected)


def test_parse_instruction_binding_inside_function() -> None:
    _import("tilus._tilus_lang")
    func_mod = _import("tilus.ir.func")
    tensor_mod = _import("tilus.ir.tensor")
    inst_mod = _import("tilus.ir.instructions.generic")

    source = """
@tilus.Function
def kernel(x: tilus.RegTensor(std.f32, 2, 2)):
    y = tilus.Add(x, x, ty=tilus.RegTensor(std.f32, 2, 2))
    return y
"""
    ty = tensor_mod.register_tensor("float32", (2, 2))
    x = std.Var(ty, "x")
    y = std.Var(ty, "y")
    expected = func_mod.Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[
            inst_mod.AddInst(x, x, output=y),
            std.Return(y),
        ],
        metadata=None,
    )

    parsed = parse(source)
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)


def test_parse_tensor_item_scope_binding() -> None:
    _import("tilus._tilus_lang")
    tensor_mod = _import("tilus.ir.tensor")
    stmt_mod = _import("tilus.ir.stmt")

    source = """
with std.scope(tilus.TensorItemValue(tilus.RegTensor(std.f32, 2, 2))) as v:
    return v
"""
    ty = tensor_mod.register_tensor("float32", (2, 2))
    v = std.Var(ty, "v")
    expected = std.Scope([stmt_mod.TensorItemValue(v)], [std.Return(v)])

    parsed = parse(source)
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)


def test_parse_hand_written_thread_group() -> None:
    _import("tilus._tilus_lang")
    stmt_mod = _import("tilus.ir.stmt")

    source = """
with tilus.thread_group(0, 32):
    result = 1
    return result
"""
    expected = stmt_mod.ThreadGroup(
        thread_begin=0,
        num_threads=32,
        body=_return_int_body(),
    )

    parsed = parse(source)
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)


def test_parse_hand_written_function() -> None:
    _import("tilus._tilus_lang")
    func_mod = _import("tilus.ir.func")

    source = """
@tilus.function
def kernel():
    result = 1
    return result
"""
    expected = func_mod.Function(
        symbol="kernel",
        args=[],
        ret_type=None,
        body=_return_int_body(),
        metadata=None,
    )

    parsed = parse(source)
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)
