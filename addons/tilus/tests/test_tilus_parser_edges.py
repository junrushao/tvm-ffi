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

from collections.abc import Callable

import pytest
import tilus  # Registers the Tilus dialect.
import tvm_ffi
from tilus.ir import layout, stmt, tensor
from tilus.ir.inst import Instruction
from tilus.ir.instructions import generic
from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi._pyast_parser import parse

_PUBLIC_TENSOR_CASES: tuple[
    tuple[str, Callable[[std.TyLike, tuple[int, ...]], tensor.Tensor]], ...
] = (
    ("RegTensor", tensor.register_tensor),
    ("RegisterTensor", tensor.register_tensor),
    ("SharedTensor", tensor.shared_tensor),
    ("GlobalTensor", tensor.global_tensor),
    ("TMemoryTensor", tensor.tmemory_tensor),
)


def _return_int_body(value: int = 1) -> list[std.Stmt]:
    literal = std.IntImm.from_py(value)
    result = std.Var(literal.ty, "result")
    return [std.BindExpr(literal, result), std.Return(result)]


def test_prints_public_constructor_names() -> None:
    ty = tensor.register_tensor("float32", (2, 2))
    lhs = std.Var(ty, "lhs")
    rhs = std.Var(ty, "rhs")
    inst = tilus.Add(lhs, rhs, ty=ty)

    assert tilus.Add is generic.AddInst
    assert ty.text() == "tilus.RegTensor(dtype=std.f32, shape=[2, 2])"
    assert inst.text() == (
        "v = tilus.Add(lhs, rhs, ty=tilus.RegTensor(dtype=std.f32, shape=[2, 2]))"
    )
    assert tvm_ffi.structural_equal(parse(ty.text()), ty)
    assert tvm_ffi.structural_equal(parse(inst.text(), extra_vars={"lhs": lhs, "rhs": rhs}), inst)


@pytest.mark.parametrize(
    "ctor_name,make_expected",
    _PUBLIC_TENSOR_CASES,
)
def test_parse_tensor_keyword_fields_match_default_printer(
    ctor_name: str,
    make_expected: Callable[[std.TyLike, tuple[int, ...]], tensor.Tensor],
) -> None:
    source = f"tilus.{ctor_name}(dtype=std.f32, shape=[2], optional_layout=None)"
    expected = make_expected("float32", (2,))

    assert tvm_ffi.structural_equal(parse(source), expected)


def test_parse_tensor_item_ptr_scope_binding() -> None:
    source = """
with std.scope(tilus.TensorItemPtr(tilus.SharedTensor(std.f32, 4))) as ptr:
    return ptr
"""
    ty = tensor.shared_tensor("float32", (4,))
    ptr = std.Var(ty, "ptr")
    expected = std.Scope([stmt.TensorItemPtr(ptr)], [std.Return(ptr)])

    assert tvm_ffi.structural_equal(parse(source), expected)


def test_parse_positional_instruction_inputs_with_attrs() -> None:
    ty = tensor.register_tensor("float32", (2,))
    lhs = std.Var(ty, "lhs")
    rhs = std.Var(ty, "rhs")
    expected = generic.StoreGlobalInst(lhs, rhs, offsets=[0], dims=[0])

    parsed = parse(
        "tilus.StoreGlobal(lhs, rhs, offsets=[0], dims=[0])",
        extra_vars={"lhs": lhs, "rhs": rhs},
    )

    assert tvm_ffi.structural_equal(parsed, expected)
    assert expected.text() == "tilus.StoreGlobal(lhs, rhs, [0], dims=[0])"


def test_public_instruction_constructors_reject_input_mode_errors() -> None:
    ty = tensor.register_tensor("float32", (2,))
    lhs = std.Var(ty, "lhs")
    rhs = std.Var(ty, "rhs")

    with pytest.raises(TypeError, match=r"missing.*rhs"):
        tilus.Add(lhs)
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'inputs'"):
        tilus.Add(lhs, inputs=[lhs, rhs])
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'inputs'"):
        tilus.Add(lhs, rhs, inputs=None)
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'inputs'"):
        tilus.Add(inputs=1)
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'inputs'"):
        tilus.SyncThreads(inputs=None)
    with pytest.raises(TypeError, match="takes at most 0 positional"):
        tilus.SyncThreads(lhs)


@pytest.mark.parametrize(
    "source,exc,message",
    [
        ("tilus.Add(lhs)", TypeError, "missing.*rhs"),
        ("tilus.Add(lhs, inputs=[lhs, rhs])", TypeError, "unexpected keyword argument 'inputs'"),
        ("tilus.Add(lhs, rhs, inputs=None)", TypeError, "unexpected keyword argument 'inputs'"),
        ("tilus.Add(inputs=1)", TypeError, "unexpected keyword argument 'inputs'"),
        ("tilus.SyncThreads(inputs=None)", TypeError, "unexpected keyword argument 'inputs'"),
        ("tilus.SyncThreads(lhs)", TypeError, "takes at most 0 positional"),
    ],
)
def test_parse_public_instruction_constructors_reject_input_mode_errors(
    source: str, exc: type[Exception], message: str
) -> None:
    ty = tensor.register_tensor("float32", (2,))
    lhs = std.Var(ty, "lhs")
    rhs = std.Var(ty, "rhs")

    with pytest.raises(exc, match=message):
        parse(source, extra_vars={"lhs": lhs, "rhs": rhs})


@pytest.mark.parametrize(
    "source,message",
    [
        ("tilus.CopyAsyncCommitGroup(lhs)", "takes at most 0 positional"),
        (
            "tilus.Tcgen05Slice(ty=tilus.TMemoryTensor(std.f32, 2), offsets=[0], slice_dims=[0])",
            "missing.*src",
        ),
        ("tilus.CopyAsync(lhs, offsets=[0], dims=[0])", "missing required argument: 'dst'"),
    ],
)
def test_parse_representative_cuda_instruction_arity_errors(source: str, message: str) -> None:
    ty = tensor.register_tensor("float32", (2,))
    lhs = std.Var(ty, "lhs")

    with pytest.raises(TypeError, match=message):
        parse(source, extra_vars={"lhs": lhs})


def test_parse_reduce_rejects_invalid_op_domain() -> None:
    ty = tensor.register_tensor("float32", (2,))
    lhs = std.Var(ty, "lhs")

    with pytest.raises(ValueError, match="op must be one of"):
        parse(
            'tilus.Reduce(lhs, ty=tilus.RegTensor(std.f32, 2), dim=0, op="median")',
            extra_vars={"lhs": lhs},
        )


def test_parse_cta_group_rejects_bool_domain_value() -> None:
    with pytest.raises(ValueError, match="cta_group must be one of"):
        parse("tilus.Tcgen05Alloc(cta_group=True)")


def test_parse_instruction_assignment_uses_constructor_ty() -> None:
    ty = tensor.register_tensor("float32", (2,))
    lhs = std.Var(ty, "lhs")
    rhs = std.Var(ty, "rhs")

    parsed = parse(
        "out = tilus.Add(lhs, rhs, ty=tilus.RegTensor(std.f32, 2))",
        extra_vars={"lhs": lhs, "rhs": rhs},
    )

    assert isinstance(parsed, generic.AddInst)
    assert parsed.output is not None
    assert tvm_ffi.structural_equal(parsed.output.ty, ty)


def test_parse_instruction_assignment_requires_ty_or_output() -> None:
    ty = tensor.register_tensor("float32", (2,))
    lhs = std.Var(ty, "lhs")

    with pytest.raises(TypeError, match="exactly one of `ty` and `output`"):
        parse("out = tilus.Cast(lhs)", extra_vars={"lhs": lhs})


def test_instruction_subclass_can_define_multiple_outputs() -> None:
    @dc.py_class("test_tilus.ParserEdgesMultiOutputInst", structural_eq="tree")
    class MultiOutputInst(Instruction, mnemonic="test_tilus.MultiOutputInst"):
        src: std.Expr = dc.field(lang_kind="arg")
        lhs_output: std.Var = dc.field(lang_kind="out")
        rhs_output: std.Var = dc.field(lang_kind="out")

        def outputs(self) -> tuple[std.Var, ...]:
            return (self.lhs_output, self.rhs_output)

        def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
            if len(name) != 2:
                raise TypeError(f"expected 2 binding target(s), got {len(name)}")
            self.lhs_output.name = name[0]
            self.rhs_output.name = name[1]
            return (self.lhs_output, self.rhs_output)

    ty = tensor.register_tensor("float32", (2,))
    src = std.Var(ty, "src")
    lhs_output = std.Var(ty, "")
    rhs_output = std.Var(ty, "")
    inst = MultiOutputInst(src, lhs_output, rhs_output)

    assert not hasattr(inst, "output")
    outputs = inst.__ffi_update_var_name__("lhs", "rhs")
    assert [var.name for var in outputs] == ["lhs", "rhs"]
    assert lhs_output.name == "lhs"
    assert rhs_output.name == "rhs"
    assert list(inst.outputs()) == list(outputs)
    assert list(std.collect_dialect_fields(inst).outs) == list(outputs)


def test_parse_instruction_assignment_renames_unbound_output() -> None:
    ty = tensor.register_tensor("float32", (2,))
    lhs = std.Var(ty, "lhs")
    rhs = std.Var(ty, "rhs")
    out = std.Var(ty, "")

    parsed = parse(
        "bound = tilus.Add(lhs, rhs, output=out)",
        extra_vars={"lhs": lhs, "rhs": rhs, "out": out},
    )

    assert isinstance(parsed, generic.AddInst)
    assert parsed.output is not None
    assert parsed.output.name == "bound"
    assert out.name == "bound"
    assert tvm_ffi.structural_equal(parsed.output.ty, ty)


def test_instruction_update_var_name_mutates_in_place() -> None:
    ty = tensor.register_tensor("float32", (2,))
    lhs = std.Var(ty, "lhs")
    rhs = std.Var(ty, "rhs")
    inst = tilus.Add(lhs, rhs, ty=ty)
    output = inst.output

    bind_vars = inst.__ffi_update_var_name__("out")
    assert inst.output is not None
    assert output.name == "out"
    assert inst.output.name == "out"
    assert tvm_ffi.structural_equal(inst.output.ty, ty)
    assert bind_vars == (inst.output,)


@pytest.mark.parametrize(
    "ctor_name,make_expected",
    _PUBLIC_TENSOR_CASES,
)
@pytest.mark.parametrize(
    "shape_args",
    [
        "2, 3",
    ],
)
def test_parse_tensor_shape_args(
    ctor_name: str,
    make_expected: Callable[[std.TyLike, tuple[int, ...]], tensor.Tensor],
    shape_args: str,
) -> None:
    expected = make_expected("float32", (2, 3))

    assert tvm_ffi.structural_equal(parse(f"tilus.{ctor_name}(std.f32, {shape_args})"), expected)


@pytest.mark.parametrize("ctor_name,make_expected", _PUBLIC_TENSOR_CASES)
def test_public_tensor_constructor_shape_forms(
    ctor_name: str,
    make_expected: Callable[[std.TyLike, tuple[int, ...]], tensor.Tensor],
) -> None:
    ctor = getattr(tilus, ctor_name)
    expected = make_expected("float32", (2, 3))

    assert tvm_ffi.structural_equal(ctor("float32", 2, 3), expected)


@pytest.mark.parametrize(
    "source,exc,message",
    [
        (
            "tilus.RegTensor(std.f32, [2, 3])",
            TypeError,
            "shape extents must be integers",
        ),
        (
            "tilus.RegTensor(std.f32, (2, 3))",
            TypeError,
            "shape extents must be integers",
        ),
        (
            "tilus.RegTensor(std.f32, 0)",
            ValueError,
            "shape extents must be positive",
        ),
        (
            "tilus.RegTensor(std.f32, 2, unknown=1)",
            TypeError,
            "unexpected keyword argument 'unknown'",
        ),
    ],
)
def test_parse_tensor_shape_errors(source: str, exc: type[Exception], message: str) -> None:
    with pytest.raises(exc, match=message):
        parse(source)


def test_parse_tensor_rejects_non_integral_shape_extents() -> None:
    for ctor_name, _ in _PUBLIC_TENSOR_CASES:
        for shape in ("1.5", '"2"', "True"):
            with pytest.raises((TypeError, ValueError), match="shape extents must be integers"):
                parse(f"tilus.{ctor_name}(std.f32, {shape})")


@pytest.mark.parametrize(
    "source",
    [
        "tilus.GlobalLayout(1.5)",
        'tilus.GlobalLayout("2")',
        "tilus.GlobalLayout(True)",
    ],
)
def test_parse_global_layout_rejects_non_integral_shape_extents(source: str) -> None:
    with pytest.raises((TypeError, ValueError), match="shape extent must be an integer"):
        parse(source)


@pytest.mark.parametrize(
    "source,expected",
    [
        ("tilus.RegisterLayout(shape=[2])", layout.register_layout((2,))),
        ("tilus.SharedLayout(shape=[2])", layout.shared_layout((2,))),
        ("tilus.GlobalLayout(shape=[2])", layout.global_layout((2,))),
        ("tilus.TMemoryLayout(shape=[32, 8])", layout.tmemory_layout((32, 8))),
    ],
)
def test_parse_layout_shape_keyword_matches_default_printer(
    source: str, expected: layout.Layout
) -> None:
    assert tvm_ffi.structural_equal(parse(source), expected)


@pytest.mark.parametrize(
    "source",
    [
        "tilus.RegisterLayout(True, mode_shape=[1], spatial_modes=[], local_modes=[0])",
        "tilus.RegisterLayout([2, 3])",
        "tilus.RegisterLayout((2, 3))",
        ("tilus.RegisterLayout(2, mode_shape=[True, 2], spatial_modes=[], local_modes=[0, 1])"),
        ("tilus.RegisterLayout(2, mode_shape=[1, 2], spatial_modes=[True], local_modes=[0])"),
        ("tilus.RegisterLayout(2, mode_shape=[1, 2], spatial_modes=[0], local_modes=[True])"),
        "tilus.SharedLayout(True, mode_shape=[1], mode_strides=[0])",
        "tilus.SharedLayout([2, 3])",
        "tilus.SharedLayout((2, 3))",
        "tilus.SharedLayout(2, mode_shape=[True, 2], mode_strides=[0, 1])",
        "tilus.SharedLayout(2, mode_shape=[2], mode_strides=[True])",
        "tilus.GlobalLayout(2, size=True, axes=['i0'], offset=0)",
        "tilus.GlobalLayout(2, size=2, axes=['i0'], offset=True)",
        "tilus.TMemoryLayout([32, 8])",
        "tilus.TMemoryLayout((32, 8))",
        "tilus.TMemoryLayout(32, True, column_strides=[0, 0], lane_offset=0)",
        "tilus.TMemoryLayout(32, 2, column_strides=[0, True], lane_offset=0)",
        "tilus.TMemoryLayout(32, 2, column_strides=[0, 1], lane_offset=True)",
    ],
)
def test_parse_layout_constructors_reject_bool_integer_fields(source: str) -> None:
    with pytest.raises((TypeError, ValueError), match=r"must be an integer|tuple entries"):
        parse(source)


def test_public_layout_constructors_match_parser_forms() -> None:
    cases = [
        (tilus.GlobalLayout(2, 3), "tilus.GlobalLayout(2, 3)"),
        (tilus.RegisterLayout(2, 3), "tilus.RegisterLayout(2, 3)"),
        (
            tilus.RegisterLayout(2, mode_shape=[2], spatial_modes=[], local_modes=[0]),
            "tilus.RegisterLayout(2, mode_shape=[2], spatial_modes=[], local_modes=[0])",
        ),
        (tilus.SharedLayout(2, 3), "tilus.SharedLayout(2, 3)"),
        (tilus.TMemoryLayout(32, 8), "tilus.TMemoryLayout(32, 8)"),
    ]

    for direct, source in cases:
        assert tvm_ffi.structural_equal(parse(source), direct)


@pytest.mark.parametrize(
    "make",
    [
        lambda: tilus.RegisterLayout([2, 3]),
        lambda: tilus.RegisterLayout((2, 3)),
        lambda: tilus.SharedLayout([2, 3]),
        lambda: tilus.SharedLayout((2, 3)),
        lambda: tilus.TMemoryLayout([32, 8]),
        lambda: tilus.TMemoryLayout((32, 8)),
    ],
)
def test_public_layout_constructors_reject_aggregate_shape_args(make) -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        make()


@pytest.mark.parametrize(
    "make,exc,message",
    [
        (
            lambda: tilus.RegTensor("float32", [2, 3]),
            TypeError,
            "shape extents must be integers",
        ),
        (
            lambda: tilus.RegTensor("float32", (2, 3)),
            TypeError,
            "shape extents must be integers",
        ),
        (
            lambda: tilus.RegTensor("float32", 0),
            ValueError,
            "shape extents must be positive",
        ),
        (
            lambda: tilus.RegTensor(std.AnyTy(), 2),
            TypeError,
            "expected primitive dtype",
        ),
        (
            lambda: tilus.RegTensor("float32", 2, unknown=1),
            TypeError,
            "unexpected keyword argument 'unknown'",
        ),
    ],
)
def test_public_tensor_constructor_errors(make, exc: type[Exception], message: str) -> None:
    with pytest.raises(exc, match=message):
        make()


def test_public_tensor_constructor_rejects_non_integral_shape_extents() -> None:
    for ctor_name, _ in _PUBLIC_TENSOR_CASES:
        ctor = getattr(tilus, ctor_name)
        for bad_extent in (1.5, "2", True):
            try:
                ctor("float32", bad_extent)
            except (TypeError, ValueError):
                continue
            raise AssertionError(f"{ctor_name} accepted non-integral extent {bad_extent!r}")


@pytest.mark.parametrize(
    "ty,expected_text",
    [
        (
            tensor.register_tensor("float32", (2, 2), layout=layout.register_row_major(2, 2)),
            "tilus.RegTensor(dtype=std.f32, optional_layout=tilus.RegisterLayout("
            "local_modes=[0, 1], mode_shape=[2, 2], shape=[2, 2], spatial_modes=[]"
            "), shape=[2, 2])",
        ),
        (
            tensor.shared_tensor("float32", (2, 2), layout=layout.shared_row_major(2, 2)),
            "tilus.SharedTensor(dtype=std.f32, optional_layout=tilus.SharedLayout("
            "mode_shape=[2, 2], mode_strides=[2, 1], shape=[2, 2]"
            "), shape=[2, 2])",
        ),
        (
            tensor.global_tensor("float32", (2, 2), layout=layout.global_row_major(2, 2)),
            "tilus.GlobalTensor(dtype=std.f32, optional_layout=tilus.GlobalLayout("
            '[2, 2], 4, 0, axes=["i0", "i1"]'
            "), shape=[2, 2])",
        ),
        (
            tensor.tmemory_tensor("float32", (32, 8), layout=layout.tmemory_row_major((32, 8))),
            "tilus.TMemoryTensor(dtype=std.f32, optional_layout=tilus.TMemoryLayout("
            "column_strides=[0, 1], lane_offset=0, shape=[32, 8]"
            "), shape=[32, 8])",
        ),
    ],
)
def test_layout_bearing_tensor_text_uses_default_field_names(
    ty: tensor.Tensor, expected_text: str
) -> None:
    text = ty.text()

    assert text == expected_text
    assert "optional_layout=" in text
    assert tvm_ffi.structural_equal(parse(text), ty)


def test_parse_thread_group_public_alias() -> None:
    source = """
with tilus.ThreadGroup(1, 2):
    result = 1
    return result
"""
    expected = stmt.ThreadGroup(
        thread_begin=1,
        num_threads=2,
        body=_return_int_body(),
    )

    parsed = parse(source)

    assert tvm_ffi.structural_equal(parsed, expected)
    assert expected.text() == (
        "with tilus.ThreadGroup(num_threads=2, thread_begin=1):\n  result = 1\n  return result"
    )
