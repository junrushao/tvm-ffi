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
import tilus  # noqa: F401  # Registers the Tilus dialect.
import tvm_ffi
from tilus.ir import layout, tensor
from tvm_ffi import std
from tvm_ffi._pyast_parser import parse


def _imm(value: int) -> std.IntImm:
    return std.IntImm.from_py(value)


def _round_trip(node: object) -> None:
    assert tvm_ffi.structural_equal(parse(node.text()), node)


def _assert_rejects_non_integral(
    name: str, make: Callable[[object], object], bad_values: tuple[object, ...]
) -> None:
    for bad_value in bad_values:
        try:
            make(bad_value)
        except (TypeError, ValueError):
            continue
        raise AssertionError(f"{name} accepted non-integral value {bad_value!r}")


def test_swizzle_helpers_apply_convert_and_validate() -> None:
    swizzle = layout.Swizzle(base=1, bits=2, shift=1)

    assert swizzle(12).value == 10
    assert layout.Swizzle(base=0, bits=0, shift=0)(31).value == 31
    assert tvm_ffi.structural_equal(
        swizzle.to_byte_swizzle(4), layout.Swizzle(base=3, bits=2, shift=1)
    )

    with pytest.raises(ValueError, match="positive power of two"):
        swizzle.to_byte_swizzle(3)
    with pytest.raises(ValueError, match="non-negative"):
        layout.Swizzle(base=-1, bits=0, shift=0)


def test_shared_layout_swizzle_access_and_chaining_errors() -> None:
    base = layout.shared_row_major(2, 4)

    with pytest.raises(ValueError, match="does not have a swizzle"):
        _ = base.swizzle

    swizzle = layout.Swizzle(base=1, bits=2, shift=1)
    swizzled = base.apply_swizzle(swizzle)
    assert tvm_ffi.structural_equal(swizzled.swizzle, swizzle)
    _round_trip(swizzled)

    with pytest.raises(ValueError, match="chained swizzle"):
        swizzled.apply_swizzle(layout.Swizzle(base=0, bits=1, shift=0))


@pytest.mark.parametrize(
    "make,message",
    [
        (
            lambda: layout.register_layout((2, 2), mode_shape=(2,)),
            "does not cover shape",
        ),
        (
            lambda: layout.shared_layout((2, 2), mode_strides=(1,)),
            "mode_shape and mode_strides",
        ),
        (
            lambda: layout.TMemoryLayout(shape=(32, 8), column_strides=(0,), lane_offset=0),
            "same rank",
        ),
        (
            lambda: layout.tmemory_layout((16, 8)),
            r"shape\[0\] must be",
        ),
        (
            lambda: layout.GlobalLayout(shape=(_imm(2),), axes=("i0", "i1")),
            "shape and axes",
        ),
        (
            lambda: layout.GlobalLayout(shape=(_imm(2), _imm(3)), axes=("i0", "i0")),
            "axes must be unique",
        ),
    ],
)
def test_layout_rank_and_axis_validation(make: Callable[[], object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        make()


@pytest.mark.parametrize(
    "make",
    [
        lambda: layout.register_row_major(2, 0),
        lambda: layout.shared_row_major(-1, 2),
        lambda: layout.tmemory_layout((32, 0)),
        lambda: tensor.register_tensor("float32", (2, 0)),
        lambda: tensor.shared_tensor("float32", (0, 2)),
        lambda: tensor.tmemory_tensor("float32", (32, -1)),
    ],
)
def test_shape_extents_must_be_positive(make: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match="shape extents must be positive"):
        make()


def test_shape_extents_must_be_integral() -> None:
    cases: tuple[tuple[str, Callable[[object], object]], ...] = (
        ("register layout", lambda extent: layout.register_row_major(extent, 2)),
        ("shared layout", lambda extent: layout.shared_row_major(extent, 2)),
        ("tmemory layout", lambda extent: layout.tmemory_layout((32, extent))),
        ("register tensor", lambda extent: tensor.register_tensor("float32", (extent, 2))),
        ("shared tensor", lambda extent: tensor.shared_tensor("float32", (extent, 2))),
        ("global tensor", lambda extent: tensor.global_tensor("float32", (extent, 2))),
        ("tmemory tensor", lambda extent: tensor.tmemory_tensor("float32", (32, extent))),
    )

    for name, make in cases:
        for bad_extent in (1.5, "2", True):
            try:
                make(bad_extent)
            except (TypeError, ValueError):
                continue
            raise AssertionError(f"{name} accepted non-integral extent {bad_extent!r}")


def test_global_layout_helper_extents_must_be_integral() -> None:
    cases: tuple[tuple[str, Callable[[object], object]], ...] = (
        ("global layout", lambda extent: layout.global_layout((extent,))),
        ("global row-major layout", lambda extent: layout.global_row_major(extent)),
        ("global column-major layout", lambda extent: layout.global_column_major(extent)),
    )

    for name, make in cases:
        _assert_rejects_non_integral(name, make, (1.5, "2", True))


@pytest.mark.parametrize(
    "name,bad_values,make",
    [
        (
            "register mode_shape",
            (2.0, "2"),
            lambda value: layout.register_layout((2,), mode_shape=(value,), local_modes=(0,)),
        ),
        (
            "register mode_shape bool",
            (True,),
            lambda value: layout.register_layout((1,), mode_shape=(value,), local_modes=(0,)),
        ),
        (
            "register spatial_modes",
            (1.0, "1", True),
            lambda value: layout.register_layout(
                (2,), mode_shape=(1, 2), spatial_modes=(value,), local_modes=(0,)
            ),
        ),
        (
            "register local_modes",
            (1.0, "1", True),
            lambda value: layout.register_layout(
                (2,), mode_shape=(1, 2), spatial_modes=(0,), local_modes=(value,)
            ),
        ),
        (
            "shared mode_shape",
            (2.0, "2"),
            lambda value: layout.shared_layout((2,), mode_shape=(value,), mode_strides=(1,)),
        ),
        (
            "shared mode_shape bool",
            (True,),
            lambda value: layout.shared_layout((1,), mode_shape=(value,), mode_strides=(0,)),
        ),
        (
            "shared mode_strides",
            (1.0, "1", True),
            lambda value: layout.shared_layout((2,), mode_shape=(2,), mode_strides=(value,)),
        ),
    ],
)
def test_tuple_normalized_layout_mode_fields_must_be_integral(
    name: str, bad_values: tuple[object, ...], make: Callable[[object], object]
) -> None:
    _assert_rejects_non_integral(name, make, bad_values)


@pytest.mark.parametrize(
    "make",
    [
        lambda: tensor.register_tensor(std.AnyTy(), (2, 2)),
        lambda: tensor.shared_tensor(std.TensorTy([2], "float32"), (2, 2)),
        lambda: tensor.global_tensor(std.TupleTy([std.PrimTy("float32")]), (2, 2)),
        lambda: tensor.tmemory_tensor(std.AnyTy(), (32, 8)),
    ],
)
def test_tensor_helpers_reject_non_primitive_dtype(make: Callable[[], object]) -> None:
    with pytest.raises(TypeError, match="expected primitive dtype"):
        make()


@pytest.mark.parametrize(
    "make,message",
    [
        (
            lambda: tensor.register_tensor("float32", (2, 2)),
            "RegisterTensor layout is not defined",
        ),
        (
            lambda: tensor.shared_tensor("float32", (2, 2)),
            "SharedTensor layout is not defined",
        ),
        (
            lambda: tensor.global_tensor("float32", (2, 2)),
            "GlobalTensor layout is not defined",
        ),
        (
            lambda: tensor.tmemory_tensor("float32", (32, 8)),
            "TMemoryTensor layout is not defined",
        ),
    ],
)
def test_tensor_layout_property_requires_explicit_layout(
    make: Callable[[], tensor.Tensor], message: str
) -> None:
    ty = make()

    assert not ty.has_layout()
    with pytest.raises(ValueError, match=message):
        _ = ty.layout


@pytest.mark.parametrize(
    "make,message",
    [
        (
            lambda: tensor.register_tensor("float32", (2, 2), layout=layout.shared_row_major(2, 2)),
            "RegisterTensor layout must be a RegisterLayout",
        ),
        (
            lambda: tensor.shared_tensor("float32", (2, 2), layout=layout.global_row_major(2, 2)),
            "SharedTensor layout must be a SharedLayout",
        ),
        (
            lambda: tensor.global_tensor("float32", (2, 2), layout=layout.register_row_major(2, 2)),
            "GlobalTensor layout must be a GlobalLayout",
        ),
        (
            lambda: tensor.tmemory_tensor(
                "float32", (32, 8), layout=layout.shared_row_major(32, 8)
            ),
            "TMemoryTensor layout must be a TMemoryLayout",
        ),
    ],
)
def test_tensor_layout_type_validation(make: Callable[[], object], message: str) -> None:
    with pytest.raises(TypeError, match=message):
        make()


@pytest.mark.parametrize(
    "make",
    [
        lambda: tensor.register_tensor("float32", (2, 2), layout=layout.register_row_major(2, 3)),
        lambda: tensor.shared_tensor("float32", (2, 2), layout=layout.shared_row_major(2, 3)),
        lambda: tensor.global_tensor("float32", (2, 2), layout=layout.global_row_major(2, 3)),
        lambda: tensor.tmemory_tensor("float32", (32, 8), layout=layout.tmemory_row_major((64, 8))),
    ],
)
def test_tensor_layout_shape_must_match_tensor_shape(make: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match="shape"):
        make()


def test_register_shared_and_tmemory_helper_metadata() -> None:
    reg = layout.register_layout(
        (4, 8), mode_shape=(2, 2, 8), spatial_modes=(0,), local_modes=(1, 2)
    )
    assert reg.grouped_modes == ((0, 1), (2,))
    assert reg.spatial_shape == (2,)
    assert reg.local_shape == (2, 8)
    assert reg.spatial_size == 2
    assert reg.local_size == 16
    assert reg.size == 32

    shared_row = layout.shared_row_major(2, 3)
    shared_col = layout.shared_column_major(2, 3)
    assert shared_row.mode_strides == (3, 1)
    assert shared_col.mode_strides == (1, 2)
    assert shared_row.count_size() == 6
    assert shared_col.count_size() == 6

    tmem = layout.tmemory_layout((32, 4, 2))
    assert tmem.shape == (32, 4, 2)
    assert tmem.column_strides == (0, 2, 1)
    assert tmem.lane_offset == 0


def test_layout_and_tensor_text_round_trip_stays_concise() -> None:
    nodes = [
        layout.Swizzle(base=1, bits=2, shift=1),
        layout.global_column_major(2, 3),
        tensor.register_tensor("float32", (2, 2)),
    ]

    assert nodes[0].text() == "tilus.Swizzle(base=1, bits=2, shift=1)"
    assert nodes[1].text() == ('tilus.GlobalLayout([2, 3], 6, 0, axes=["i1", "i0"])')
    assert nodes[2].text() == "tilus.RegTensor(dtype=std.f32, shape=[2, 2])"
    for node in nodes:
        _round_trip(node)
