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

import tilus  # noqa: F401  # Registers the Tilus dialect.
import tvm_ffi
from tvm_ffi import std
from tvm_ffi._pyast_parser import parse


def _round_trip(node: object) -> None:
    assert tvm_ffi.structural_equal(parse(node.text()), node)


def _import(name: str):
    return importlib.import_module(name)


def test_parse_hand_written_global_layout() -> None:
    _import("tilus._tilus_lang")
    layout_mod = _import("tilus.ir.layout")

    source = 'tilus.GlobalLayout(shape=[16, 32], size=512, axes=["i0", "i1"], offset=0)'
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
        "std.f32, "
        "shape=[16, 32], "
        'layout=tilus.GlobalLayout(shape=[16, 32], size=512, axes=["i0", "i1"], offset=0)'
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
dst: tilus.RegTensor(
    std.f32,
    shape=[16, 32],
    layout=tilus.RegisterLayout(
        shape=[16, 32],
        mode_shape=[16, 32],
        spatial_modes=[],
        local_modes=[0, 1],
    ),
    ) = tilus.LoadGlobal(
        tilus.GlobalTensor(
            std.f32,
            shape=[16, 32],
            layout=tilus.GlobalLayout(
                shape=[16, 32],
                size=512,
                axes=["i0", "i1"],
                offset=0,
            ),
        ),
        offsets=[0, 0],
        dims=[0, 1],
    )
"""
    global_layout = layout_mod.global_row_major(16, 32)
    reg_layout = layout_mod.register_row_major(16, 32)
    src = tensor_mod.global_tensor("float32", (16, 32), layout=global_layout)
    dst_ty = tensor_mod.register_tensor("float32", (16, 32), layout=reg_layout)
    expected = inst_mod.LoadGlobalInst(
        output=std.Var(dst_ty, "dst"),
        inputs=[src],
        offsets=[0, 0],
        dims=[0, 1],
    )

    parsed = parse(source)
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)


def test_parse_tensor_layout_alias_conflict_is_rejected() -> None:
    _import("tilus._tilus_lang")

    source = "tilus.RegTensor(std.f32, shape=[2, 2], layout=None, optional_layout=None)"

    try:
        parse(source)
    except TypeError as err:
        assert "specify either optional_layout or layout, not both" in str(err)
    else:
        raise AssertionError("expected layout alias conflict to fail")


def test_parse_instruction_binding_inside_function() -> None:
    _import("tilus._tilus_lang")
    func_mod = _import("tilus.ir.func")
    tensor_mod = _import("tilus.ir.tensor")
    inst_mod = _import("tilus.ir.instructions.generic")

    source = """
@tilus.Function
def kernel(x: tilus.RegTensor(std.f32, shape=[2, 2])):
    y: tilus.RegTensor(std.f32, shape=[2, 2]) = tilus.Add(x, x)
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
            inst_mod.AddInst(inputs=[x, x], output=y),
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
with std.scope(tilus.TensorItemValue(tilus.RegTensor(std.f32, shape=[2, 2]))) as v:
    return v
"""
    ty = tensor_mod.register_tensor("float32", (2, 2))
    v = std.Var(ty, "v")
    expected = std.Scope([stmt_mod.TensorItemValue(ty, v)], [std.Return(v)])

    parsed = parse(source)
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)


def test_parse_hand_written_thread_group() -> None:
    _import("tilus._tilus_lang")
    stmt_mod = _import("tilus.ir.stmt")

    source = """
with tilus.thread_group(0, 32):
    return 1
"""
    expected = stmt_mod.ThreadGroup(
        thread_begin=0,
        num_threads=32,
        body=[std.Return(std.IntImm(std.AnyTy(), 1))],
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
    return 1
"""
    expected = func_mod.Function(
        symbol="kernel",
        args=[],
        ret_type=None,
        body=[std.Return(std.IntImm(std.AnyTy(), 1))],
        metadata=None,
    )

    parsed = parse(source)
    assert tvm_ffi.structural_equal(parsed, expected)
    _round_trip(expected)
