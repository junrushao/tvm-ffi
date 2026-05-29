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

import tilus  # Registers the Tilus dialect.
import tvm_ffi
from tilus.ir.functors import IRRewriter, IRVisitor
from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi._pyast_parser import parse


@dc.py_class("test.tilus.FunctorLeaf")
class FunctorLeaf(std.Node, mnemonic="test_tilus.FunctorLeaf"):
    value: int = dc.field(lang_kind="arg")


@dc.py_class("test.tilus.FunctorBox")
class FunctorBox(std.Node, mnemonic="test_tilus.FunctorBox"):
    child: FunctorLeaf = dc.field(lang_kind="arg")
    items: list[FunctorLeaf] = dc.field(default_factory=list, lang_kind="arg")
    label: str = dc.field(default="", lang_kind="attr")


@dc.py_class("test.tilus.FunctorMap")
class FunctorMap(std.Node, mnemonic="test_tilus.FunctorMap"):
    mapping: dict[FunctorLeaf, FunctorLeaf] = dc.field(default_factory=dict, lang_kind="attr")


class IncrementLeaves(IRRewriter):
    def visit_FunctorLeaf(self, node: FunctorLeaf) -> FunctorLeaf:
        return dc.replace(node, value=node.value + 1)


class CollectLeaves(IRVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.values: list[int] = []

    def visit_FunctorLeaf(self, node: FunctorLeaf) -> None:
        self.values.append(node.value)


def _input_vars(node: object) -> dict[str, std.Var]:
    inputs = getattr(node, "inputs", ())
    return {value.name: value for value in inputs if isinstance(value, std.Var)}


def _round_trip(node: object) -> None:
    _import("tilus._tilus_lang")
    assert tvm_ffi.structural_equal(parse(node.text(), extra_vars=_input_vars(node)), node)


def _import(name: str):
    return importlib.import_module(name)


def _return_int_body(value: int = 1) -> list[std.Stmt]:
    literal = std.IntImm.from_py(value)
    result = std.Var(literal.ty, "result")
    return [std.BindExpr(literal, result), std.Return(result)]


def test_ir_rewriter_uses_dataclass_fields_and_replace() -> None:
    leaf = FunctorLeaf(1)
    node = FunctorBox(leaf, [leaf], label="box")

    rewritten = IncrementLeaves()(node)

    assert rewritten is not node
    assert rewritten.child.value == 2
    assert rewritten.items[0].value == 2
    assert node.child.value == 1


def test_ir_visitor_walks_dataclass_fields() -> None:
    first = FunctorLeaf(1)
    second = FunctorLeaf(2)
    node = FunctorBox(first, [second], label="box")

    visitor = CollectLeaves()
    visitor(node)

    assert visitor.values == [1, 2]


def test_ir_functors_walk_mapping_keys() -> None:
    key = FunctorLeaf(1)
    value = FunctorLeaf(2)
    node = FunctorMap({key: value})

    leaf_visitor = CollectLeaves()
    leaf_visitor(node)
    assert leaf_visitor.values == [1, 2]

    assert IRRewriter()(node) is node

    rewritten = IncrementLeaves()(node)
    rewritten_items = list(rewritten.mapping.items())
    assert rewritten_items[0][0].value == 2
    assert rewritten_items[0][1].value == 3


def test_layout_round_trip() -> None:
    layout_mod = _import("tilus.ir.layout")
    nodes = [
        layout_mod.Swizzle(base=1, bits=2, shift=1),
        layout_mod.global_row_major(16, 32),
        layout_mod.tmemory_row_major((32, 8)),
    ]
    for node in nodes:
        _round_trip(node)


def test_register_layout_helpers_cover_modes() -> None:
    layout_mod = _import("tilus.ir.layout")

    spatial = layout_mod.register_spatial_row_major(16, 32)
    assert spatial.local_size == 1
    assert spatial.spatial_size == 512

    split = layout_mod.register_layout((16, 32), mode_shape=(2, 8, 32))
    assert split.local_modes == (0, 1, 2)
    assert split.local_size == 512

    unit = layout_mod.register_row_major(1, 1)
    assert unit.grouped_modes == ((0,), (1,))


def test_tensor_round_trip() -> None:
    layout_mod = _import("tilus.ir.layout")
    tensor_mod = _import("tilus.ir.tensor")

    layout = layout_mod.global_row_major(16, 32)
    tensors = [
        tensor_mod.global_tensor("float32", (16, 32), layout=layout),
        tensor_mod.tmemory_tensor("float32", (32, 8), layout=layout_mod.tmemory_row_major((32, 8))),
    ]
    for tensor in tensors:
        _round_trip(tensor)


def test_instruction_round_trip() -> None:
    layout_mod = _import("tilus.ir.layout")
    tensor_mod = _import("tilus.ir.tensor")
    inst_mod = _import("tilus.ir.instructions.generic")

    src_ty = tensor_mod.global_tensor(
        "float32",
        (16, 32),
        layout=layout_mod.global_row_major(16, 32),
    )
    dst_ty = tensor_mod.register_tensor(
        "float32",
        (16, 32),
        layout=layout_mod.register_row_major(16, 32),
    )
    dst = std.Var(dst_ty, "dst")
    src = std.Var(src_ty, "src")
    inst = inst_mod.LoadGlobalInst(inputs=[src], output=dst, offsets=[0, 0], dims=[0, 1])
    _round_trip(inst)
    assert "inputs=" not in inst.text()
    assert "dst: " not in inst.text()
    assert "ty=tilus.RegTensor" in inst.text()


def test_hint_and_cuda_instruction_round_trip() -> None:
    layout_mod = _import("tilus.ir.layout")
    hints_mod = _import("tilus.ir.instructions.hints")
    tensor_mod = _import("tilus.ir.tensor")
    cuda_mod = _import("tilus.ir.instructions.cuda")
    src_ty = tensor_mod.global_tensor(
        "float32", (16, 32), layout=layout_mod.global_row_major(16, 32)
    )
    dst_ty = tensor_mod.shared_tensor(
        "float32", (16, 32), layout=layout_mod.shared_row_major(16, 32)
    )
    src = std.Var(src_ty, "src")
    dst = std.Var(dst_ty, "dst")

    nodes = [
        hints_mod.AssumeInst(condition=True),
        cuda_mod.CopyAsyncCommitGroupInst(),
        cuda_mod.CopyAsyncInst(inputs=[src, dst], offsets=[0, 1], dims=[0, 1]),
        cuda_mod.CopyAsyncGenericInst(ptr="ptr", axes=["i", "j"], offset=0),
    ]
    for node in nodes:
        _round_trip(node)

    config = cuda_mod.AtomicMmaConfig(
        name="mma",
        m=16,
        n=8,
        k=32,
        vec_k=8,
        la=layout_mod.register_row_major(16, 32),
        lb=layout_mod.register_row_major(32, 8),
        lc=layout_mod.register_row_major(16, 8),
        operand_type=std.PrimTy("float16"),
        acc_type=std.PrimTy("float32"),
    )
    _round_trip(config)


def test_thread_group_round_trip() -> None:
    stmt_mod = _import("tilus.ir.stmt")
    body = _return_int_body()
    stmt = stmt_mod.ThreadGroup(thread_begin=0, num_threads=32, body=body)
    _round_trip(stmt)


def test_tensor_item_round_trip() -> None:
    tensor_mod = _import("tilus.ir.tensor")
    stmt_mod = _import("tilus.ir.stmt")

    ty = tensor_mod.register_tensor("float32", (2, 2))
    value = stmt_mod.TensorItemValue(ty, std.Var(ty, "v"))
    ptr = stmt_mod.TensorItemPtr(ty, std.Var(ty, "p"), space="shared")
    for node in (value, ptr):
        _round_trip(node)


def test_tensor_item_scope_round_trip() -> None:
    tensor_mod = _import("tilus.ir.tensor")
    stmt_mod = _import("tilus.ir.stmt")

    ty = tensor_mod.register_tensor("float32", (2, 2))
    value = std.Var(ty, "v")
    scope = std.Scope(
        [stmt_mod.TensorItemValue(ty, value)],
        [std.Return(value)],
    )

    _round_trip(scope)


def test_metadata_round_trip() -> None:
    func_mod = _import("tilus.ir.func")

    _round_trip(
        func_mod.Metadata(
            grid_blocks=[1, 1, 1],
            cluster_blocks=[1, 1, 1],
            block_indices=["bx", "by", "bz"],
            param2divisibility={"x": 16},
            analysis=func_mod.Analysis(divisibility={"x": 16}),
        )
    )


def test_tensor_optional_layout_alias_is_rejected() -> None:
    layout_mod = _import("tilus.ir.layout")
    tensor_mod = _import("tilus.ir.tensor")

    try:
        tensor_mod.register_tensor(
            "float32",
            (2, 2),
            optional_layout=layout_mod.register_row_major(2, 2),
        )
    except TypeError:
        pass
    else:
        raise AssertionError("expected optional_layout alias to fail")


def test_public_printed_name_constructors_are_callable() -> None:
    layout_mod = _import("tilus.ir.layout")
    tensor_mod = _import("tilus.ir.tensor")
    inst_mod = _import("tilus.ir.instructions.generic")

    reg_layout = layout_mod.register_row_major(2, 2)
    global_layout = layout_mod.global_row_major(2, 2)
    reg_ty = tilus.RegTensor("float32", 2, 2, layout=reg_layout)
    src_ty = tilus.GlobalTensor("float32", 2, 2, layout=global_layout)

    assert tvm_ffi.structural_equal(
        reg_ty,
        tensor_mod.register_tensor("float32", (2, 2), layout=reg_layout),
    )
    assert tvm_ffi.structural_equal(
        tilus.RegisterTensor("float32", 2, 2, layout=reg_layout),
        reg_ty,
    )
    assert tvm_ffi.structural_equal(
        src_ty,
        tensor_mod.global_tensor("float32", (2, 2), layout=global_layout),
    )

    x = std.Var(reg_ty, "x")
    y = std.Var(reg_ty, "y")
    assert isinstance(tilus.Add(x, x, output=y), inst_mod.AddInst)
    assert isinstance(
        tilus.LoadGlobal(std.Var(src_ty, "src"), output=y, offsets=[0, 0], dims=[0, 1]),
        inst_mod.LoadGlobalInst,
    )

    shared_ty = tilus.SharedTensor("float32", 2, 2, layout=layout_mod.shared_row_major(2, 2))
    load_shared = tilus.LoadShared(std.Var(shared_ty, "shared"), output=y)
    assert isinstance(load_shared, inst_mod.LoadSharedInst)
    assert "ty=tilus.RegTensor" in load_shared.text()


def test_inst_stmt_requires_instruction() -> None:
    stmt_mod = _import("tilus.ir.stmt")

    try:
        stmt_mod.InstStmt(123)
    except TypeError:
        pass
    else:
        raise AssertionError("expected non-instruction InstStmt to fail")


def test_eval_and_inst_stmt_round_trip() -> None:
    stmt_mod = _import("tilus.ir.stmt")
    inst_mod = _import("tilus.ir.instructions.generic")

    _round_trip(stmt_mod.Evaluate(std.IntImm(std.AnyTy(), 1)))
    _round_trip(stmt_mod.InstStmt(inst_mod.NopInst()))


def test_function_round_trip() -> None:
    func_mod = _import("tilus.ir.func")

    func = func_mod.Function(
        symbol="kernel",
        args=[],
        ret_type=None,
        body=_return_int_body(),
        metadata=None,
    )
    _round_trip(func)


def test_public_ir_modules_are_importable() -> None:
    for name in [
        "tilus.ir.layout",
        "tilus.ir.tensor",
        "tilus.ir.inst",
        "tilus.ir.instructions",
        "tilus.ir.stmt",
        "tilus.ir.func",
    ]:
        _import(name)

    assert hasattr(tilus.ir, "LoadGlobalInst")
