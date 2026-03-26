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
"""Function/module-level Tilus text-format round-trip tests."""

from __future__ import annotations

from textwrap import dedent
from typing import Any

import pytest
import tilus  # noqa: F401  # Registers the Tilus dialect.
import tvm_ffi
from tvm_ffi._pyast_parser import parse


def _text(ir: Any) -> str:
    if isinstance(ir, list):
        return "\n\n".join(_text(item) for item in ir)
    return ir.text()


def _assert_text_roundtrip(source: str) -> str:
    parsed = parse(dedent(source).strip())
    printed = _text(parsed)
    reparsed = parse(printed)

    assert tvm_ffi.structural_equal(parsed, reparsed), printed
    assert tvm_ffi.structural_equal(reparsed, parsed), printed
    assert _text(reparsed) == printed
    return printed


# Functions
@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def empty_kernel():
                pass
            """,
            id="empty-body",
        ),
        pytest.param(
            """
            @tilus.function
            def untyped_passthrough(x):
                return x
            """,
            id="lowercase-decorator-untyped-arg",
        ),
        pytest.param(
            """
            @tilus.Function
            def scalar_sum(m: std.i32, n: std.i32) -> std.i32:
                total: std.i32 = m + n
                return total
            """,
            id="typed-scalar-signature-and-return",
        ),
        pytest.param(
            """
            @tilus.Function
            def tuple_return(m: std.i32, x: std.f32):
                return m, x
            """,
            id="tuple-return-body",
        ),
        pytest.param(
            """
            @tilus.Function
            def no_value_return(flag: std.bool):
                if flag:
                    return
                return
            """,
            id="return-without-value",
        ),
        pytest.param(
            """
            @tilus.Function(metadata=tilus.Metadata(
                grid_blocks=[1, 2, 3],
                cluster_blocks=[1, 1, 1],
                block_indices=["bx", "by", "bz"],
                num_warps=4,
                param2divisibility={"m": 16, "n": 8},
                analysis=tilus.Analysis(
                    divisibility={"m": 16},
                    lower_bound={"m": 0},
                    upper_bound={"m": 128},
                ),
            ))
            def with_metadata(m: std.i32, n: std.i32) -> std.i32:
                total: std.i32 = m + n
                return total
            """,
            id="decorator-metadata",
        ),
        pytest.param(
            """
            @tilus.Function
            def tensor_alias_return(
                x: tilus.RegisterTensor(std.f32, 2, 2),
            ) -> tilus.RegisterTensor(std.f32, 2, 2):
                y = tilus.Add(x, x, ty=tilus.RegisterTensor(std.f32, 2, 2))
                return y
            """,
            id="tensor-alias-return-annotation",
        ),
        pytest.param(
            """
            @tilus.Function
            def memory_space_signature(
                global_x: tilus.GlobalTensor(std.f16, 16),
                shared_x: tilus.SharedTensor(std.f16, 16),
                reg_x: tilus.RegTensor(std.f16, 16),
            ) -> tilus.RegTensor(std.f16, 16):
                return reg_x
            """,
            id="mixed-memory-space-signature",
        ),
        pytest.param(
            """
            @tilus.Function
            def thread_group_return(
                x: tilus.RegTensor(std.f32, 2, 2),
            ) -> tilus.RegTensor(std.f32, 2, 2):
                with tilus.thread_group(0, 32):
                    y = tilus.Add(x, x, ty=tilus.RegTensor(std.f32, 2, 2))
                    return y
            """,
            id="nested-thread-group-return",
        ),
    ],
)
def test_tilus_function_text_round_trip(source: str) -> None:
    _assert_text_roundtrip(source)


def test_tilus_function_alias_prints_canonical_decorator_and_tensor_name() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.function
        def alias_surface(
            x: tilus.RegisterTensor(std.f32, 2),
        ) -> tilus.RegisterTensor(std.f32, 2):
            return x
        """
    )

    assert printed.startswith("@tilus.Function")
    assert "@tilus.function" not in printed
    assert "tilus.RegisterTensor" not in printed
    assert printed.count("tilus.RegTensor") == 2


def test_tilus_functions_inside_std_module_round_trip() -> None:
    printed = _assert_text_roundtrip(
        """
        @std.module
        class KernelPair:
            @tilus.Function(metadata=tilus.Metadata(
                grid_blocks=[2, 1, 1],
                cluster_blocks=[1, 1, 1],
                block_indices=["bx", "by", "bz"],
                num_warps=4,
            ))
            def load_tile(src: tilus.GlobalTensor(std.f32, 16)):
                tile = tilus.LoadGlobal(
                    src,
                    ty=tilus.RegTensor(std.f32, 16),
                    offsets=[0],
                    dims=[0],
                )
                return tile

            @tilus.function
            def store_tile(
                dst: tilus.GlobalTensor(std.f32, 16),
                tile: tilus.RegTensor(std.f32, 16),
            ):
                tilus.StoreGlobal(dst, tile, offsets=[0], dims=[0])
        """
    )

    assert printed.startswith("@std.module")
    assert printed.count("@tilus.Function") == 2
    assert "@tilus.function" not in printed


# Layouts
@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def register_layout_arg(
                x: tilus.RegTensor(
                    std.f32,
                    8, 16,
                    layout=tilus.RegisterLayout(
                        8, 16,
                        mode_shape=[2, 4, 16],
                        spatial_modes=[0],
                        local_modes=[1, 2],
                    ),
                ),
            ):
                return x
            """,
            id="register-layout-arg",
        ),
        pytest.param(
            """
            @tilus.Function
            def shared_layout_arg(
                x: tilus.SharedTensor(
                    std.f16,
                    8, 16,
                    layout=tilus.SharedLayout(
                        8, 16,
                        mode_shape=[8, 16],
                        mode_strides=[16, 1],
                        optional_swizzle=tilus.Swizzle(1, 2, 1),
                    ),
                ),
            ):
                return x
            """,
            id="shared-layout-arg-with-swizzle",
        ),
        pytest.param(
            """
            @tilus.Function
            def global_layout_arg(
                x: tilus.GlobalTensor(
                    std.f32,
                    16, 32,
                    layout=tilus.GlobalLayout(
                        16, 32,
                        size=512,
                        axes=["row", "col"],
                        offset=4,
                    ),
                ),
            ):
                return x
            """,
            id="global-layout-arg",
        ),
        pytest.param(
            """
            @tilus.Function
            def tmemory_layout_arg(
                x: tilus.TMemoryTensor(
                    std.f32,
                    64, 16, 8,
                    layout=tilus.TMemoryLayout(
                        64, 16, 8,
                        column_strides=[0, 8, 1],
                        lane_offset=4,
                    ),
                ),
            ):
                return x
            """,
            id="tmemory-layout-arg",
        ),
    ],
)
def test_layouts_in_function_arg_annotations_roundtrip(source: str) -> None:
    _assert_text_roundtrip(source)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def load_global_with_layouts(
                src: tilus.GlobalTensor(
                    std.f32,
                    8, 16,
                    layout=tilus.GlobalLayout(
                        8, 16,
                        size=128,
                        axes=["m", "n"],
                        offset=0,
                    ),
                ),
            ):
                tile = tilus.LoadGlobal(
                    src,
                    offsets=[0, 0],
                    dims=[0, 1],
                    ty=tilus.RegTensor(
                        std.f32,
                        8, 16,
                        layout=tilus.RegisterLayout(
                            8, 16,
                            mode_shape=[2, 4, 16],
                            spatial_modes=[0],
                            local_modes=[1, 2],
                        ),
                    ),
                )
                return tile
            """,
            id="global-to-register",
        ),
        pytest.param(
            """
            @tilus.Function
            def load_and_store_shared_with_layouts(
                src: tilus.SharedTensor(
                    std.f32,
                    4, 8,
                    layout=tilus.SharedLayout(
                        4, 8,
                        mode_shape=[4, 8],
                        mode_strides=[8, 1],
                        optional_swizzle=tilus.Swizzle(0, 2, 1),
                    ),
                ),
                dst: tilus.SharedTensor(
                    std.f32,
                    4, 8,
                    layout=tilus.SharedLayout(
                        4, 8,
                        mode_shape=[4, 8],
                        mode_strides=[8, 1],
                    ),
                ),
            ):
                tile = tilus.LoadShared(
                    src,
                    ty=tilus.RegTensor(
                        std.f32,
                        4, 8,
                        layout=tilus.RegisterLayout(
                            4, 8,
                            mode_shape=[4, 8],
                            spatial_modes=[],
                            local_modes=[0, 1],
                        ),
                    ),
                )
                tilus.StoreShared(dst, tile)
                return tile
            """,
            id="shared-to-register-to-shared",
        ),
        pytest.param(
            """
            @tilus.Function
            def annotate_and_reduce_layout(
                x: tilus.RegTensor(
                    std.f32,
                    2, 4,
                    layout=tilus.RegisterLayout(
                        2, 4,
                        mode_shape=[2, 4],
                        spatial_modes=[0],
                        local_modes=[1],
                    ),
                ),
            ):
                hinted = tilus.AnnotateLayout(
                    x,
                    ty=tilus.RegTensor(
                        std.f32,
                        2, 4,
                        layout=tilus.RegisterLayout(
                            2, 4,
                            mode_shape=[2, 4],
                            spatial_modes=[],
                            local_modes=[0, 1],
                        ),
                    ),
                    layout=tilus.RegisterLayout(
                        2, 4,
                        mode_shape=[2, 4],
                        spatial_modes=[],
                        local_modes=[0, 1],
                    ),
                )
                reduced = tilus.Reduce(
                    hinted,
                    dim=1,
                    op="sum",
                    keepdim=False,
                    ty=tilus.RegTensor(
                        std.f32,
                        2,
                        layout=tilus.RegisterLayout(
                            2,
                            mode_shape=[2],
                            spatial_modes=[],
                            local_modes=[0],
                        ),
                    ),
                )
                return reduced
            """,
            id="annotate-layout-and-reduce-output",
        ),
    ],
)
def test_layouts_on_instruction_outputs_inside_functions_roundtrip(source: str) -> None:
    _assert_text_roundtrip(source)


def test_symbolic_global_layout_expression_inside_function_roundtrips() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function
        def symbolic_global_layout(m: std.i32):
            src: tilus.GlobalTensor(
                std.f32,
                16,
                layout=tilus.GlobalLayout(
                    m + 1,
                    size=m + 1,
                    axes=["logical"],
                    offset=tilus.Swizzle(1, 2, 1)(m),
                ),
            )
            tile = tilus.LoadGlobal(
                src,
                ty=tilus.RegTensor(std.f32, 16),
                offsets=[m],
                dims=[0],
            )
            return tile
        """
    )

    assert "offset=" in printed
    assert "tilus.GlobalLayout(m + std.i32(1)," in printed


def test_multi_function_layout_unit_roundtrips() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function
        def module_register_layout(
            x: tilus.RegTensor(
                std.f32,
                2, 2,
                layout=tilus.RegisterLayout(
                    2, 2,
                    mode_shape=[2, 2],
                    spatial_modes=[],
                    local_modes=[0, 1],
                ),
            ),
        ):
            y = tilus.Add(
                x,
                x,
                ty=tilus.RegTensor(
                    std.f32,
                    2, 2,
                    layout=tilus.RegisterLayout(
                        2, 2,
                        mode_shape=[2, 2],
                        spatial_modes=[],
                        local_modes=[0, 1],
                    ),
                ),
            )
            return y

        @tilus.Function
        def module_shared_layout(
            src: tilus.SharedTensor(
                std.f32,
                2, 2,
                layout=tilus.SharedLayout(
                    2, 2,
                    mode_shape=[2, 2],
                    mode_strides=[2, 1],
                ),
            ),
        ):
            y = tilus.LoadShared(
                src,
                ty=tilus.RegTensor(
                    std.f32,
                    2, 2,
                    layout=tilus.RegisterLayout(
                        2, 2,
                        mode_shape=[2, 2],
                        spatial_modes=[],
                        local_modes=[0, 1],
                    ),
                ),
            )
            return y
        """
    )

    assert printed.count("@tilus.Function") == 2


# Tensors
@pytest.mark.parametrize(
    "source,expected",
    [
        pytest.param(
            """
            @tilus.Function
            def register_alias_flow(
                src: tilus.RegisterTensor(std.f32, 2, 3),
            ) -> tilus.RegisterTensor(std.f32, 2, 3):
                acc = tilus.Add(src, src, ty=tilus.RegisterTensor(std.f32, 2, 3))
                out = tilus.Mul(acc, src, ty=tilus.RegTensor(std.f32, 2, 3))
                return out
            """,
            ("tilus.RegTensor",),
            id="register-alias-args-locals-return",
        ),
        pytest.param(
            """
            @tilus.Function
            def memory_space_flow(
                src: tilus.GlobalTensor(std.f32, 16),
                dst: tilus.GlobalTensor(std.f32, 16),
                scratch: tilus.SharedTensor(std.f32, 16),
            ):
                loaded = tilus.LoadGlobal(
                    src,
                    ty=tilus.RegTensor(std.f32, 16),
                    offsets=[0],
                    dims=[0],
                )
                tilus.StoreShared(scratch, loaded)
                reread = tilus.LoadShared(scratch, ty=tilus.RegTensor(std.f32, 16))
                tilus.StoreGlobal(dst, reread, offsets=[0], dims=[0])
            """,
            ("tilus.GlobalTensor", "tilus.SharedTensor", "tilus.RegTensor"),
            id="global-shared-register-function-body",
        ),
        pytest.param(
            """
            @tilus.Function
            def layout_alias_flow(
                shared: tilus.SharedTensor(
                    std.f16,
                    4,
                    8,
                    layout=tilus.SharedLayout(
                        4,
                        8,
                        mode_shape=[4, 8],
                        mode_strides=[8, 1],
                        optional_swizzle=tilus.Swizzle(1, 2, 1),
                    ),
                ),
                global_tensor: tilus.GlobalTensor(
                    std.f16,
                    4,
                    8,
                    layout=tilus.GlobalLayout(4, 8),
                ),
                tmem: tilus.TMemoryTensor(
                    std.f32,
                    32,
                    8,
                    layout=tilus.TMemoryLayout(
                        32,
                        8,
                        column_strides=[0, 1],
                        lane_offset=0,
                    ),
                ),
            ):
                tile = tilus.LoadShared(
                    shared,
                    ty=tilus.RegTensor(
                        std.f16,
                        4, 8,
                        layout=tilus.RegisterLayout(
                            4, 8,
                            mode_shape=[4, 8],
                            spatial_modes=[],
                            local_modes=[0, 1],
                        ),
                    ),
                )
                tilus.StoreGlobal(global_tensor, tile, offsets=[0, 0], dims=[0, 1])
                return tmem
            """,
            ("layout=", "tilus.TMemoryTensor"),
            id="layout-aliases-inside-function",
        ),
        pytest.param(
            """
            @tilus.Function
            def tensor_item_bindings():
                with std.scope(
                    tilus.TensorItemValue(tilus.RegTensor(std.f32, 1)),
                    tilus.TensorItemPtr(tilus.SharedTensor(std.f32, 1), space="shared"),
                    tilus.TensorItemPtr(tilus.GlobalTensor(std.f32, 1), space="global"),
                    tilus.TensorItemPtr(tilus.TMemoryTensor(std.f32, 1), space="tmem"),
                ) as (value, shared_ptr, global_ptr, tmem_ptr):
                    return value
            """,
            ("tilus.TensorItemValue", "tilus.TensorItemPtr", "tilus.TMemoryTensor"),
            id="tensor-item-value-and-pointers-in-function",
        ),
    ],
)
def test_tensor_functions_round_trip(source: str, expected: tuple[str, ...]) -> None:
    printed = _assert_text_roundtrip(source)

    assert printed.startswith("@tilus.Function")
    assert "tilus.RegisterTensor" not in printed
    for fragment in expected:
        assert fragment in printed


def test_tensor_return_types_round_trip_inside_std_module() -> None:
    printed = _assert_text_roundtrip(
        """
        @std.module
        class TensorModule:
            @tilus.Function
            def return_register(
                buf: tilus.RegTensor(std.f32, 2, 2),
            ) -> tilus.RegTensor(std.f32, 2, 2):
                return buf

            @tilus.Function
            def return_shared(
                buf: tilus.SharedTensor(std.f16, 4, 8),
            ) -> tilus.SharedTensor(std.f16, 4, 8):
                return buf

            @tilus.Function
            def return_global(
                buf: tilus.GlobalTensor(std.i32, 16),
            ) -> tilus.GlobalTensor(std.i32, 16):
                return buf

            @tilus.Function
            def return_tmemory(
                buf: tilus.TMemoryTensor(std.f32, 32, 8),
            ) -> tilus.TMemoryTensor(std.f32, 32, 8):
                return buf
        """
    )

    assert printed.startswith("@std.module")
    assert printed.count("@tilus.Function") == 4
    for tensor_name in (
        "tilus.RegTensor",
        "tilus.SharedTensor",
        "tilus.GlobalTensor",
        "tilus.TMemoryTensor",
    ):
        assert tensor_name in printed


# Generic Insts
@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def global_arithmetic_pipeline(
                lhs: tilus.GlobalTensor(std.f32, 64),
                rhs: tilus.GlobalTensor(std.f32, 64),
                dst: tilus.GlobalTensor(std.f32, 64),
            ):
                for tile in range(0, 4, step=1, tag="tiles"):
                    left = tilus.LoadGlobal(
                        lhs,
                        ty=tilus.RegTensor(std.f32, 16),
                        offsets=[tile * 16],
                        dims=[0],
                    )
                    right = tilus.LoadGlobal(
                        rhs,
                        ty=tilus.RegTensor(std.f32, 16),
                        offsets=[tile * 16],
                        dims=[0],
                    )
                    summed = tilus.Add(left, right, ty=tilus.RegTensor(std.f32, 16))
                    delta = tilus.Sub(summed, left, ty=tilus.RegTensor(std.f32, 16))
                    scaled = tilus.Mul(delta, right, ty=tilus.RegTensor(std.f32, 16))
                    quotient = tilus.Div(scaled, summed, ty=tilus.RegTensor(std.f32, 16))
                    tilus.StoreGlobal(dst, quotient, offsets=[tile * 16], dims=[0])
            """,
            id="global-load-arithmetic-store",
        ),
        pytest.param(
            """
            @tilus.Function
            def cast_reduced_tile(
                src: tilus.GlobalTensor(std.f32, 8, 4),
                dst: tilus.GlobalTensor(std.i32, 8),
            ):
                tile = tilus.LoadGlobal(
                    src,
                    ty=tilus.RegTensor(std.f32, 8, 4),
                    offsets=[0, 0],
                    dims=[0, 1],
                )
                reduced = tilus.Reduce(
                    tile,
                    ty=tilus.RegTensor(std.f32, 8),
                    dim=1,
                    op="max",
                    keepdim=False,
                )
                casted = tilus.Cast(reduced, ty=tilus.RegTensor(std.i32, 8))
                tilus.StoreGlobal(dst, casted, offsets=[0], dims=[0])
            """,
            id="reduce-cast-store",
        ),
        pytest.param(
            """
            @tilus.Function
            def shared_memory_round_trip(
                src: tilus.GlobalTensor(std.f16, 8),
                dst: tilus.GlobalTensor(std.f16, 8),
            ):
                loaded = tilus.LoadGlobal(
                    src,
                    ty=tilus.RegTensor(std.f16, 8),
                    offsets=[0],
                    dims=[0],
                )
                with std.scope(
                    tilus.TensorItemPtr(tilus.SharedTensor(std.f16, 8), space="shared")
                ) as shared:
                    tilus.StoreShared(shared, loaded)
                    tilus.SyncThreads()
                    reread = tilus.LoadShared(shared, ty=tilus.RegTensor(std.f16, 8))
                    tilus.Nop()
                    tilus.StoreGlobal(dst, reread, offsets=[0], dims=[0])
            """,
            id="shared-store-load-sync",
        ),
        pytest.param(
            """
            @tilus.Function
            def tensor_item_value_flow(dst: tilus.GlobalTensor(std.f32, 4)):
                with std.scope(
                    tilus.TensorItemValue(tilus.RegTensor(std.f32, 4)),
                    role="accumulator",
                ) as acc:
                    squared = tilus.Mul(acc, acc, ty=tilus.RegTensor(std.f32, 4))
                    shifted = tilus.Add(squared, acc, ty=tilus.RegTensor(std.f32, 4))
                    tilus.StoreGlobal(dst, shifted, offsets=[0], dims=[0])
            """,
            id="tensor-item-value-arithmetic",
        ),
    ],
)
def test_generic_instruction_functions_round_trip(source: str) -> None:
    printed = _assert_text_roundtrip(source)

    assert printed.startswith("@tilus.Function")


def test_multiple_generic_instruction_functions_round_trip_as_translation_unit() -> None:
    source = """
    @tilus.Function
    def load_add_store(
        lhs: tilus.GlobalTensor(std.f32, 4),
        rhs: tilus.GlobalTensor(std.f32, 4),
        dst: tilus.GlobalTensor(std.f32, 4),
    ):
        a = tilus.LoadGlobal(lhs, offsets=[0], dims=[0], ty=tilus.RegTensor(std.f32, 4))
        b = tilus.LoadGlobal(rhs, offsets=[0], dims=[0], ty=tilus.RegTensor(std.f32, 4))
        out = tilus.Add(a, b, ty=tilus.RegTensor(std.f32, 4))
        tilus.StoreGlobal(dst, out, offsets=[0], dims=[0])

    @tilus.Function
    def reduce_min_store(
        src: tilus.GlobalTensor(std.f32, 2, 4),
        dst: tilus.GlobalTensor(std.f32, 2),
    ):
        tile = tilus.LoadGlobal(
            src,
            ty=tilus.RegTensor(std.f32, 2, 4),
            offsets=[0, 0],
            dims=[0, 1],
        )
        out = tilus.Reduce(tile, dim=1, op="min", ty=tilus.RegTensor(std.f32, 2))
        tilus.StoreGlobal(dst, out, offsets=[0], dims=[0])
    """
    parsed = parse(dedent(source).strip())
    printed = "\n\n".join(func.text() for func in parsed)
    reparsed = parse(printed)

    assert tvm_ffi.structural_equal(parsed, reparsed), printed
    assert tvm_ffi.structural_equal(reparsed, parsed), printed
    assert "\n\n@tilus.Function" in printed
    assert "\n\n".join(func.text() for func in reparsed) == printed


# Cuda Memory
@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def copy_async_group(
                src: tilus.GlobalTensor(std.f32, 64),
                dst: tilus.SharedTensor(std.f32, 64),
                lane: std.i32,
            ):
                tilus.CopyAsync(
                    src,
                    dst,
                    offsets=[lane * 4],
                    dims=[0],
                    evict="evict_last",
                    check_bounds=False,
                )
                tilus.CopyAsync(
                    src,
                    dst,
                    offsets=[lane * 4 + 16],
                    dims=[0],
                    evict="evict_first",
                )
                tilus.CopyAsyncCommitGroup()
                tilus.CopyAsyncWaitGroup(n=1)
                tilus.CopyAsyncWaitAll()
            """,
            id="cp-async-global-shared-group",
        ),
        pytest.param(
            """
            @tilus.Function
            def copy_async_generic_with_ordering(tile: std.i32, ready: std.bool):
                tilus.FenceProxyAsync(space="global")
                tilus.CopyAsyncGeneric(
                    ptr="gmem",
                    axes=["block", "lane"],
                    offset=tile * 128,
                    mask=ready,
                    evict="evict_unchanged",
                )
                tilus.CopyAsyncCommitGroup()
                tilus.CopyAsyncWaitGroup(n=0)
                tilus.FenceProxyAsyncRelease()
            """,
            id="cp-async-generic-with-fences",
        ),
    ],
)
def test_cp_async_functions_round_trip(source: str) -> None:
    _assert_text_roundtrip(source)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def bulk_global_to_shared(
                src: tilus.GlobalTensor(std.f16, 16, 16),
                dst: tilus.SharedTensor(std.f16, 16, 16),
                barrier: std.i32,
            ):
                tilus.AllocBarrier(counts=[1, None, 4])
                tilus.ArriveExpectTxBarrier(
                    barrier=barrier,
                    transaction_bytes=512,
                    sem="release",
                    scope="cluster",
                )
                tilus.CopyAsyncBulkGlobalToShared(
                    src,
                    dst,
                    offsets=[0, 8],
                    dims=[0, 1],
                    mbarrier=barrier,
                    evict="evict_last",
                    check_bounds=False,
                )
                tilus.CopyAsyncBulkCommitGroup()
                tilus.CopyAsyncBulkWaitGroup(n=0)
                tilus.WaitBarrier(
                    barrier=barrier,
                    phase=1,
                    sem="acquire",
                    scope="cluster",
                )
            """,
            id="bulk-global-to-shared-with-mbarrier",
        ),
        pytest.param(
            """
            @tilus.Function
            def bulk_cluster_shared(
                src: tilus.GlobalTensor(std.f16, 8, 8),
                local: tilus.SharedTensor(std.f16, 8, 8),
                remote: tilus.SharedTensor(std.f16, 8, 8),
                barrier: std.i32,
            ):
                tilus.ArriveExpectTxMulticastBarrier(
                    barrier=barrier,
                    transaction_bytes=256,
                    multicast=3,
                    sem="relaxed",
                    scope="cluster",
                )
                tilus.CopyAsyncBulkGlobalToClusterShared(
                    src,
                    local,
                    offsets=[1, 0],
                    dims=[0, 1],
                    mbarrier=barrier,
                    cta_mask=7,
                    evict="evict_first",
                    check_bounds=True,
                )
                tilus.CopyAsyncBulkSharedToClusterShared(
                    local,
                    remote,
                    mbarrier=barrier,
                    remote_rank=2,
                )
                tilus.CopyAsyncBulkCommitGroup()
                tilus.CopyAsyncBulkWaitGroup(n=1)
            """,
            id="bulk-global-cluster-and-remote-shared",
        ),
        pytest.param(
            """
            @tilus.Function
            def bulk_shared_to_global(
                src: tilus.SharedTensor(std.f32, 2, 4),
                dst: tilus.GlobalTensor(std.f32, 2, 4),
                col: std.i32,
            ):
                tilus.CopyAsyncBulkSharedToGlobal(
                    src,
                    dst,
                    offsets=[0, col],
                    dims=[0, 1],
                    check_bounds=False,
                    l2_evict="no_allocate",
                )
                tilus.CopyAsyncBulkCommitGroup()
                tilus.CopyAsyncBulkWaitGroup(n=0)
                tilus.FenceProxyAsync(space="shared::cluster")
            """,
            id="bulk-shared-to-global",
        ),
    ],
)
def test_cp_async_bulk_functions_round_trip(source: str) -> None:
    _assert_text_roundtrip(source)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def tensor_map_global_to_shared(
                src: tilus.GlobalTensor(std.f16, 32, 16),
                dst: tilus.SharedTensor(std.f16, 32, 16),
                row: std.i32,
                barrier: std.i32,
            ):
                tilus.ArriveExpectTxRemoteBarrier(
                    barrier=barrier,
                    transaction_bytes=1024,
                    target_rank=1,
                    sem="release",
                    scope="cluster",
                )
                tilus.CopyAsyncTensorGlobalToShared(
                    src,
                    dst,
                    offsets=[row, 0],
                    dims=[0, 1],
                    mbarrier=barrier,
                    cta_group=2,
                    multicast_mask=3,
                    cache_policy=5,
                )
                tilus.CopyAsyncTensorCommitGroup()
                tilus.CopyAsyncTensorWaitGroup(n=0, read=True)
                tilus.WaitBarrier(
                    barrier=barrier,
                    phase=0,
                    sem="relaxed",
                    scope="cluster",
                )
            """,
            id="tensor-global-to-shared-with-remote-barrier",
        ),
        pytest.param(
            """
            @tilus.Function
            def tensor_map_shared_to_global(
                src: tilus.SharedTensor(std.f16, 32, 16),
                dst: tilus.GlobalTensor(std.f16, 32, 16),
                col: std.i32,
                semaphore: std.i32,
            ):
                tilus.LockSemaphore(semaphore=semaphore, value=1)
                tilus.CopyAsyncTensorSharedToGlobal(
                    src,
                    dst,
                    offsets=[0, col],
                    dims=[0, 1],
                    cache_policy=7,
                )
                tilus.CopyAsyncTensorCommitGroup()
                tilus.CopyAsyncTensorWaitGroup(n=0, read=False)
                tilus.ReleaseSemaphore(semaphore=semaphore, value=0)
            """,
            id="tensor-shared-to-global-with-semaphore",
        ),
    ],
)
def test_cp_async_tensor_functions_round_trip(source: str) -> None:
    _assert_text_roundtrip(source)


def test_cuda_memory_module_round_trips_multiple_functions() -> None:
    _assert_text_roundtrip(
        """
        @tilus.Function
        def producer(
            src: tilus.GlobalTensor(std.f32, 8),
            dst: tilus.SharedTensor(std.f32, 8),
        ):
            tilus.CopyAsync(src, dst, offsets=[0], dims=[0])
            tilus.CopyAsyncCommitGroup()

        @tilus.Function
        def consumer(barrier: std.i32):
            tilus.ArriveBarrier(
                barrier=barrier,
                count=1,
                sem="relaxed",
                scope="cta",
            )
            tilus.WaitBarrier(
                barrier=barrier,
                phase=1,
                sem="relaxed",
                scope="cta",
            )
            tilus.CopyAsyncWaitAll()
        """
    )


# Cuda Math
@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def dot_tile(
                a: tilus.RegTensor(std.f16, 16, 8),
                b: tilus.RegTensor(std.f16, 8, 16),
            ) -> tilus.RegTensor(std.f32, 16, 16):
                acc = tilus.Dot(a, b, ty=tilus.RegTensor(std.f32, 16, 16))
                return acc

            @tilus.Function
            def simt_dot_tile(
                a: tilus.RegTensor(std.f16, 16, 8),
                b: tilus.RegTensor(std.f16, 8, 16),
            ) -> tilus.RegTensor(std.f32, 16, 16):
                acc = tilus.SimtDot(
                    a,
                    b,
                    ty=tilus.RegTensor(std.f32, 16, 16),
                    warp_spatial=[1, 2],
                    warp_repeat=[2, 1],
                    thread_spatial=[1, 2],
                    thread_repeat=[4, 1],
                )
                return acc
            """,
            id="dot-and-simt-dot-module",
        ),
        pytest.param(
            """
            @tilus.Function
            def wgmma_grouped_mma(
                a: tilus.SharedTensor(std.f16, 64, 64),
                b: tilus.SharedTensor(std.f16, 64, 64),
                ar: tilus.RegTensor(std.f16, 64, 64),
            ) -> tilus.RegTensor(std.f32, 64, 64):
                tilus.WgmmaFence()
                acc_ss = tilus.WgmmaMmaSS(a, b, ty=tilus.RegTensor(std.f32, 64, 64))
                acc_rs = tilus.WgmmaMmaRS(ar, b, ty=tilus.RegTensor(std.f32, 64, 64))
                tilus.WgmmaCommitGroup()
                tilus.WgmmaWaitGroup(n=0)
                return acc_ss
            """,
            id="wgmma-group-and-mma",
        ),
        pytest.param(
            """
            @tilus.Function(
                metadata=tilus.Metadata(
                    grid_blocks=[1, 1, 1],
                    cluster_blocks=[1, 1, 1],
                    block_indices=["bx", "by", "bz"],
                    num_warps=4,
                )
            )
            def tcgen05_mma(
                a: tilus.SharedTensor(std.f16, 64, 64),
                b: tilus.SharedTensor(std.f16, 64, 64),
                t: tilus.TMemoryTensor(std.f32, 32, 8),
                use_d: std.bool,
            ) -> tilus.RegTensor(std.f32, 64, 64):
                tilus.Tcgen05Alloc(cta_group=2)
                tile = tilus.Tcgen05Slice(
                    t,
                    ty=tilus.TMemoryTensor(std.f32, 32, 8),
                    offsets=[0, 4],
                    slice_dims=[0, 1],
                )
                tilus.Tcgen05Commit(mbarrier=0, cta_group=2, multicast_mask=3)
                out_ss = tilus.Tcgen05MmaSS(
                    a,
                    b,
                    ty=tilus.RegTensor(std.f32, 64, 64),
                    enable_input_d=use_d,
                    cta_group=2,
                )
                out_ts = tilus.Tcgen05MmaTS(
                    tile,
                    b,
                    ty=tilus.RegTensor(std.f32, 64, 64),
                    enable_input_d=False,
                    cta_group=1,
                )
                tilus.Tcgen05Wait(wait_load=True, wait_store=False)
                tilus.Tcgen05RelinquishAllocPermit(cta_group=2)
                tilus.Tcgen05Dealloc()
                return out_ss
            """,
            id="tcgen05-mma-pipeline",
        ),
        pytest.param(
            """
            @tilus.Function
            def tcgen05_auxiliary_steps():
                tilus.Tcgen05View()
                tilus.Tcgen05Load()
                tilus.Tcgen05Store()
                tilus.Tcgen05Copy()
            """,
            id="tcgen05-auxiliary-steps",
        ),
        pytest.param(
            """
            @tilus.Function(
                metadata=tilus.Metadata(
                    grid_blocks=[2, 1, 1],
                    cluster_blocks=[1, 1, 1],
                    block_indices=["bx", "by", "bz"],
                    num_warps=8,
                )
            )
            def mixed_cuda_math(
                a: tilus.RegTensor(std.f16, 16, 16),
                b: tilus.RegTensor(std.f16, 16, 16),
                smem_a: tilus.SharedTensor(std.f16, 64, 64),
                smem_b: tilus.SharedTensor(std.f16, 64, 64),
            ) -> tilus.RegTensor(std.f32, 16, 16):
                simt = tilus.SimtDot(
                    a,
                    b,
                    ty=tilus.RegTensor(std.f32, 16, 16),
                    warp_spatial=[2, 1],
                    warp_repeat=[1, 2],
                    thread_spatial=[2, 1],
                    thread_repeat=[1, 4],
                )
                tilus.WgmmaFence()
                wgmma = tilus.WgmmaMmaSS(smem_a, smem_b, ty=tilus.RegTensor(std.f32, 64, 64))
                tilus.WgmmaCommitGroup()
                tilus.WgmmaWaitGroup(n=1)
                return simt
            """,
            id="mixed-math-function-with-metadata",
        ),
    ],
)
def test_handwritten_cuda_math_text_roundtrips(source: str) -> None:
    _assert_text_roundtrip(source)


# Scopes
@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def thread_group_branch(flag: std.bool) -> std.i32:
                with tilus.thread_group(0, 32):
                    if flag:
                        one = 1
                        return one
                    zero = 0
                    return zero
            """,
            id="thread-group-branch-return",
        ),
        pytest.param(
            """
            @tilus.Function
            def nested_thread_groups() -> std.i32:
                with tilus.thread_group(0, 64):
                    with tilus.thread_group(16, 16):
                        seven = 7
                        return seven
                minus_one = -1
                return minus_one
            """,
            id="nested-thread-groups",
        ),
    ],
)
def test_thread_group_functions_text_round_trip(source: str) -> None:
    printed = _assert_text_roundtrip(source)

    assert "tilus.ThreadGroup" in printed


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def lexical_scope_return(x: std.i32) -> std.i32:
                with std.scope(kind="lexical"):
                    y: std.i32 = x + 1
                    return y
            """,
            id="lexical-scope-return",
        ),
        pytest.param(
            """
            @tilus.Function
            def tensor_item_value_return() -> tilus.RegTensor(std.f32, 2, 2):
                with std.scope(
                    tilus.TensorItemValue(tilus.RegTensor(std.f32, 2, 2))
                ) as value:
                    return value
            """,
            id="tensor-item-value-return",
        ),
        pytest.param(
            """
            @tilus.Function
            def tensor_item_ptr_load() -> tilus.RegTensor(std.f32, 4):
                with std.scope(
                    tilus.TensorItemPtr(tilus.SharedTensor(std.f32, 4), space="shared")
                ) as ptr:
                    loaded = tilus.LoadShared(ptr, ty=tilus.RegTensor(std.f32, 4))
                    return loaded
            """,
            id="tensor-item-ptr-load",
        ),
        pytest.param(
            """
            @tilus.Function
            def mixed_tensor_item_scope() -> tilus.RegTensor(std.i32, 1):
                with std.scope(
                    tilus.TensorItemValue(tilus.RegTensor(std.i32, 1)),
                    tilus.TensorItemPtr(tilus.SharedTensor(std.i32, 1), space="shared"),
                    role="mixed",
                ) as (value, ptr):
                    tilus.StoreShared(ptr, value)
                    return value
            """,
            id="mixed-tensor-item-scope",
        ),
    ],
)
def test_std_scope_functions_text_round_trip(source: str) -> None:
    printed = _assert_text_roundtrip(source)

    assert "std.scope" in printed


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def scoped_thread_group_return(
                x: tilus.RegTensor(std.f32, 2),
            ) -> tilus.RegTensor(std.f32, 2):
                with std.scope(
                    tilus.TensorItemValue(tilus.RegTensor(std.f32, 2))
                ) as tile:
                    with tilus.thread_group(0, 32):
                        return tile
                return x
            """,
            id="scope-inside-thread-group-return",
        ),
        pytest.param(
            """
            @tilus.Function
            def looped_nested_scopes(
                src: tilus.GlobalTensor(std.f32, 8),
                dst: tilus.GlobalTensor(std.f32, 8),
            ):
                for phase in range(0, 2, tag="phase"):
                    with tilus.thread_group(0, 32):
                        tile = tilus.LoadGlobal(
                            src,
                            ty=tilus.RegTensor(std.f32, 4),
                            offsets=[phase * 4],
                            dims=[0],
                        )
                        if phase == 0:
                            with std.scope(stage="first"):
                                tilus.StoreGlobal(dst, tile, offsets=[0], dims=[0])
                        else:
                            with std.scope(stage="second"):
                                tilus.StoreGlobal(dst, tile, offsets=[4], dims=[0])
            """,
            id="for-if-thread-group-scopes",
        ),
        pytest.param(
            """
            @tilus.Function
            def while_scope(i: std.i32):
                while i < 4:
                    with std.scope(stage="loop"):
                        tilus.Eval(i)
                    break
            """,
            id="while-scope",
        ),
    ],
)
def test_nested_tilus_and_std_scope_functions_text_round_trip(source: str) -> None:
    printed = _assert_text_roundtrip(source)

    assert printed.startswith("@tilus.Function")
    assert "std.scope" in printed


def test_scoped_functions_inside_module_text_round_trip() -> None:
    printed = _assert_text_roundtrip(
        """
        @std.module
        class ScopedModule:
            @tilus.Function
            def stage_value() -> tilus.RegTensor(std.f16, 8):
                with std.scope(
                    tilus.TensorItemValue(tilus.RegTensor(std.f16, 8)),
                    stage="accumulator",
                ) as acc:
                    with tilus.thread_group(0, 32):
                        return acc

            @tilus.Function
            def stage_store(
                dst: tilus.GlobalTensor(std.f16, 8),
                src: tilus.RegTensor(std.f16, 8),
            ):
                with std.scope(
                    tilus.TensorItemPtr(tilus.SharedTensor(std.f16, 8), space="shared"),
                    stage="shared",
                ) as shared:
                    tilus.StoreShared(shared, src)
                    loaded = tilus.LoadShared(shared, ty=tilus.RegTensor(std.f16, 8))
                    tilus.StoreGlobal(dst, loaded, offsets=[0], dims=[0])
        """
    )

    assert printed.startswith("@std.module")
    assert printed.count("@tilus.Function") == 2


# Hints Metadata
@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function(
                metadata=tilus.Metadata(
                    grid_blocks=[1, 2, 3],
                    cluster_blocks=[1, 1, 1],
                    block_indices=["block_x", "block_y", "block_z"],
                    num_warps=4,
                )
            )
            def launch_metadata_kernel(m: std.i32):
                tilus.Assume(condition=m >= 0)
            """,
            id="launch-metadata-and-assume",
        ),
        pytest.param(
            """
            @tilus.Function(
                metadata=tilus.Metadata(
                    analysis=tilus.Analysis(
                        divisibility={"m": 16, "n": 32},
                        lower_bound={"m": 0, "n": 0},
                        upper_bound={"m": 4096, "n": 2048},
                    ),
                    block_indices=["bx", "by", "bz"],
                    cluster_blocks=[1, 1, 1],
                    grid_blocks=[128, 64, 1],
                    num_warps=8,
                    param2divisibility={"m": 16, "n": 32},
                )
            )
            def analyzed_tile_kernel(
                m: std.i32,
                n: std.i32,
                x: tilus.RegTensor(std.f32, 2, 2),
            ):
                tilus.Assume(condition=(m % 16 == 0) and (n % 32 == 0))
                y = tilus.AnnotateLayout(
                    x,
                    ty=tilus.RegTensor(std.f32, 2, 2),
                    layout=tilus.RegisterLayout(
                        2, 2,
                        mode_shape=[2, 2],
                        spatial_modes=[],
                        local_modes=[0, 1],
                    ),
                )
                return y
            """,
            id="analysis-maps-and-register-layout-hint",
        ),
        pytest.param(
            """
            @tilus.Function(
                metadata=tilus.Metadata(
                    analysis=tilus.Analysis(
                        divisibility={"rows": 8},
                        lower_bound={"rows": 1},
                        upper_bound={"rows": 1024},
                    ),
                    param2divisibility={"rows": 8},
                )
            )
            def shared_layout_hint_kernel(
                rows: std.i32,
                x: tilus.SharedTensor(std.f16, 4, 8),
            ):
                tilus.Assume(condition=(rows >= 1) and (rows <= 1024))
                y = tilus.AnnotateLayout(
                    x,
                    ty=tilus.SharedTensor(
                                        std.f16,
                                        4, 8,
                                        layout=tilus.SharedLayout(
                                            4, 8,
                                            mode_shape=[4, 8],
                                            mode_strides=[8, 1],
                                            optional_swizzle=tilus.Swizzle(1, 2, 1),
                                        ),
                    ),
                    layout=tilus.SharedLayout(
                        4, 8,
                        mode_shape=[4, 8],
                        mode_strides=[8, 1],
                        optional_swizzle=tilus.Swizzle(1, 2, 1),
                    ),
                )
                return y
            """,
            id="shared-layout-hint-with-analysis-bounds",
        ),
        pytest.param(
            """
            @tilus.Function(metadata=tilus.Metadata(param2divisibility={"m": 16}))
            def nested_hint_scope(
                m: std.i32,
                x: tilus.RegTensor(std.f32, 4),
            ):
                tilus.Assume(condition=m % 16 == 0)
                with tilus.thread_group(0, 32):
                    hinted = tilus.AnnotateLayout(
                        x,
                        ty=tilus.RegTensor(
                                                std.f32,
                                                4,
                                                layout=tilus.RegisterLayout(
                                                    4,
                                                    mode_shape=[4],
                                                    spatial_modes=[],
                                                    local_modes=[0],
                                                ),
                        ),
                        layout=tilus.RegisterLayout(
                            4,
                            mode_shape=[4],
                            spatial_modes=[],
                            local_modes=[0],
                        ),
                    )
                    tilus.Assume(condition=m >= 16)
                    return hinted
            """,
            id="nested-thread-group-hints",
        ),
    ],
)
def test_hint_metadata_functions_roundtrip(source: str) -> None:
    printed = _assert_text_roundtrip(source)

    assert printed.startswith("@tilus.Function")
    assert "tilus.Assume" in printed


def test_module_level_hint_metadata_functions_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        @std.module
        class HintMetadataModule:
            @tilus.Function(
                metadata=tilus.Metadata(
                    grid_blocks=[32, 1, 1],
                    cluster_blocks=[1, 1, 1],
                    block_indices=["bx", "by", "bz"],
                    num_warps=4,
                    param2divisibility={"m": 16},
                    analysis=tilus.Analysis(
                        divisibility={"m": 16},
                        lower_bound={"m": 0},
                        upper_bound={"m": 1024},
                    ),
                )
            )
            def guarded_load(
                m: std.i32,
                src: tilus.GlobalTensor(std.f32, 16),
            ):
                tilus.Assume(condition=(m >= 0) and (m < 1024))
                tile = tilus.LoadGlobal(
                    src,
                    ty=tilus.RegTensor(std.f32, 16),
                    offsets=[0],
                    dims=[0],
                )
                return tile

            @tilus.Function(metadata=tilus.Metadata(param2divisibility={"n": 8}))
            def annotated_store(
                n: std.i32,
                dst: tilus.GlobalTensor(std.f32, 16),
                tile: tilus.RegTensor(std.f32, 16),
            ):
                tilus.Assume(condition=n % 8 == 0)
                hinted = tilus.AnnotateLayout(
                    tile,
                    ty=tilus.RegTensor(
                                        std.f32,
                                        16,
                                        layout=tilus.RegisterLayout(
                                            16,
                                            mode_shape=[16],
                                            spatial_modes=[],
                                            local_modes=[0],
                                        ),
                    ),
                    layout=tilus.RegisterLayout(
                        16,
                        mode_shape=[16],
                        spatial_modes=[],
                        local_modes=[0],
                    ),
                )
                tilus.StoreGlobal(dst, hinted, offsets=[0], dims=[0])
        """
    )

    assert printed.startswith("@std.module")
    assert printed.count("@tilus.Function") == 2
    assert "param2divisibility" in printed


def test_multi_function_hint_metadata_translation_unit_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function(
            metadata=tilus.Metadata(
                analysis=tilus.Analysis(
                    divisibility={"m": 4},
                    lower_bound={"m": 0},
                    upper_bound={"m": 256},
                ),
                param2divisibility={"m": 4},
            )
        )
        def assume_only_translation_unit(m: std.i32):
            tilus.Assume(condition=(m >= 0) and (m <= 256))

        @tilus.Function(metadata=tilus.Metadata(grid_blocks=[1, 1, 1]))
        def annotate_only_translation_unit(x: tilus.RegTensor(std.f32, 2)):
            y = tilus.AnnotateLayout(
                x,
                ty=tilus.RegTensor(
                                std.f32,
                                2,
                                layout=tilus.RegisterLayout(
                                    2,
                                    mode_shape=[2],
                                    spatial_modes=[],
                                    local_modes=[0],
                                ),
                ),
                layout=tilus.RegisterLayout(
                    2,
                    mode_shape=[2],
                    spatial_modes=[],
                    local_modes=[0],
                ),
            )
            return y
        """
    )

    assert printed.count("@tilus.Function") == 2
    assert "tilus.Analysis" in printed
    assert "tilus.AnnotateLayout" in printed


# Cuda Sync Atomic
@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def shared_and_global_atomic_pipeline(
                smem: tilus.SharedTensor(std.u32, 4),
                gmem: tilus.GlobalTensor(std.u32, 4),
                value: tilus.RegTensor(std.u32, 4),
                rank: std.i32,
            ) -> tilus.RegTensor(std.u32, 4):
                mapped = tilus.MapSharedAddr(
                    smem,
                    ty=tilus.RegTensor(std.u32, 4),
                    target_rank=rank,
                )
                tilus.AtomicShared(smem, value, op="add", sem="release", scope="cta")
                tilus.AtomicGlobal(gmem, value, op="exch", sem="acq_rel", scope="gpu")
                tilus.FenceProxyAsync(space="shared::cluster")
                tilus.ClusterSyncThreads()
                tilus.FenceProxyAsyncRelease()
                return mapped
            """,
            id="shared-global-atomic-map-shared",
        ),
        pytest.param(
            """
            @tilus.Function
            def scatter_atomic_tiles(
                smem: tilus.SharedTensor(std.i32, 4, 8),
                gmem: tilus.GlobalTensor(std.i32, 4, 8),
                tile: tilus.RegTensor(std.i32, 4, 8),
            ):
                for row in range(0, 4, step=1, tag="atomic_rows"):
                    tilus.AtomicScatterShared(
                        smem,
                        tile,
                        op="min",
                        dim=0,
                        sem="relaxed",
                        scope="cluster",
                    )
                    tilus.AtomicScatterGlobal(
                        gmem,
                        tile,
                        op="max",
                        dim=1,
                        sem="acquire",
                        scope="sys",
                    )
                    tilus.FenceProxyAsync(space="global")
            """,
            id="scatter-atomics-inside-loop",
        ),
        pytest.param(
            """
            @tilus.Function
            def barrier_lifecycle(barrier: std.i32, phase: std.i32, bytes: std.i32):
                tilus.AllocBarrier(counts=[1, None, 4])
                tilus.ArriveBarrier(
                    barrier=barrier,
                    count=2,
                    sem="release",
                    scope="cluster",
                )
                tilus.WaitBarrier(
                    barrier=barrier,
                    phase=phase,
                    sem="acquire",
                    scope="cluster",
                )
                tilus.ArriveExpectTxBarrier(
                    barrier=barrier + 1,
                    transaction_bytes=bytes,
                    sem="relaxed",
                    scope="cta",
                )
                tilus.ArriveExpectTxMulticastBarrier(
                    barrier=barrier + 2,
                    transaction_bytes=bytes * 2,
                    multicast=3,
                    sem="release",
                    scope="cluster",
                )
                tilus.ArriveExpectTxRemoteBarrier(
                    barrier=barrier + 3,
                    transaction_bytes=bytes // 2,
                    target_rank=1,
                    sem="relaxed",
                    scope="cluster",
                )
            """,
            id="mbarrier-lifecycle",
        ),
        pytest.param(
            """
            @tilus.Function
            def semaphore_cluster_launch_control(
                semaphore: std.i32,
                active: std.bool,
                mbarrier: std.i32,
            ):
                if active:
                    tilus.LockSemaphore(semaphore=semaphore, value=1)
                    tilus.ClcTryCancel(mbarrier=mbarrier, multicast=3)
                    tilus.ClcQueryResponse()
                    tilus.ClusterSyncThreads()
                else:
                    tilus.FenceProxyAsync(space="shared::cta")
                tilus.ReleaseSemaphore(semaphore=semaphore, value=0)
            """,
            id="semaphore-clc-control-flow",
        ),
        pytest.param(
            """
            @tilus.Function
            def scoped_shared_mapping(
                dst: tilus.GlobalTensor(std.u32, 8),
                value: tilus.RegTensor(std.u32, 8),
                rank: std.i32,
            ):
                with std.scope(
                    tilus.TensorItemPtr(tilus.SharedTensor(std.u32, 8), space="shared"),
                    role="remote_smem",
                ) as shared:
                    mapped = tilus.MapSharedAddr(
                        shared,
                        ty=tilus.RegTensor(std.u32, 8),
                        target_rank=rank,
                    )
                    tilus.AtomicShared(shared, value, op="or", sem="acquire", scope="cluster")
                    tilus.FenceProxyAsync(space="shared::cluster")
                    tilus.AtomicGlobal(dst, mapped, op="cas", sem="release", scope="sys")
            """,
            id="typed-local-map-shared",
        ),
    ],
)
def test_cuda_sync_atomic_functions_round_trip(source: str) -> None:
    printed = _assert_text_roundtrip(source)

    assert printed.startswith("@tilus.Function")


def test_cuda_sync_atomic_functions_inside_std_module_round_trip() -> None:
    printed = _assert_text_roundtrip(
        """
        @std.module
        class SyncAtomicModule:
            @tilus.Function
            def atomic_store(
                dst: tilus.GlobalTensor(std.u32, 4),
                value: tilus.RegTensor(std.u32, 4),
            ):
                tilus.FenceProxyAsync(space="global")
                tilus.AtomicGlobal(dst, value, op="inc", sem="acq_rel", scope="gpu")
                tilus.FenceProxyAsyncRelease()

            @tilus.Function
            def barrier_and_semaphore(barrier: std.i32, semaphore: std.i32):
                tilus.AllocBarrier(counts=[None, 2])
                tilus.ArriveBarrier(
                    barrier=barrier,
                    count=1,
                    sem="release",
                    scope="cta",
                )
                tilus.WaitBarrier(
                    barrier=barrier,
                    phase=0,
                    sem="relaxed",
                    scope="cta",
                )
                tilus.LockSemaphore(semaphore=semaphore, value=1)
                tilus.ReleaseSemaphore(semaphore=semaphore, value=0)
        """
    )

    assert printed.startswith("@std.module")
    assert printed.count("@tilus.Function") == 2


# Kernels
@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function(
                metadata=tilus.Metadata(
                    grid_blocks=[4, 1, 1],
                    cluster_blocks=[1, 1, 1],
                    block_indices=["bx", "by", "bz"],
                    num_warps=4,
                )
            )
            def tiled_vector_add(
                a: tilus.GlobalTensor(std.f32, 1024),
                b: tilus.GlobalTensor(std.f32, 1024),
                c: tilus.GlobalTensor(std.f32, 1024),
                scratch: tilus.SharedTensor(std.f32, 256),
            ):
                for tile in range(0, 4, step=1, tag="tiles"):
                    with tilus.thread_group(0, 128):
                        av = tilus.LoadGlobal(
                            a,
                            ty=tilus.RegTensor(std.f32, 256),
                            offsets=[tile * 256],
                            dims=[0],
                        )
                        bv = tilus.LoadGlobal(
                            b,
                            ty=tilus.RegTensor(std.f32, 256),
                            offsets=[tile * 256],
                            dims=[0],
                        )
                        cv = tilus.Add(av, bv, ty=tilus.RegTensor(std.f32, 256))
                        if tile < 2:
                            tilus.StoreShared(scratch, cv)
                        else:
                            tilus.StoreGlobal(c, cv, offsets=[tile * 256], dims=[0])
                        tilus.SyncThreads()
            """,
            id="tiled-vector-add",
        ),
        pytest.param(
            """
            @tilus.Function
            def scoped_shared_pipeline(
                src: tilus.GlobalTensor(std.f16, 64, 64),
                dst: tilus.GlobalTensor(std.f16, 64, 64),
            ):
                with std.scope(
                    tilus.TensorItemPtr(tilus.SharedTensor(std.f16, 16, 16), space="shared"),
                    pragma="stage_shared",
                ) as tile:
                    for phase in range(0, 2, tag="phase"):
                        tilus.CopyAsync(
                            src,
                            tile,
                            offsets=[phase * 16, 0],
                            dims=[0, 1],
                            evict="evict_last",
                        )
                        tilus.CopyAsyncCommitGroup()
                        tilus.CopyAsyncWaitGroup(n=0)
                        loaded = tilus.LoadShared(tile, ty=tilus.RegTensor(std.f16, 16, 16))
                        tilus.StoreGlobal(dst, loaded, offsets=[phase * 16, 0], dims=[0, 1])
            """,
            id="scoped-shared-pipeline",
        ),
        pytest.param(
            """
            @tilus.function
            def reduction_with_control(
                x: tilus.GlobalTensor(std.f32, 128, 16),
                y: tilus.GlobalTensor(std.f32, 128),
            ):
                for row in range(0, 128, step=16):
                    tile = tilus.LoadGlobal(
                        x,
                        ty=tilus.RegTensor(std.f32, 16, 16),
                        offsets=[row, 0],
                        dims=[0, 1],
                    )
                    reduced = tilus.Reduce(
                        tile,
                        ty=tilus.RegTensor(std.f32, 16),
                        dim=1,
                        op="sum",
                        keepdim=False,
                    )
                    with std.while_(row < 128, tag="single_pass"):
                        if row < 64:
                            tilus.StoreGlobal(y, reduced, offsets=[row], dims=[0])
                        else:
                            tilus.AtomicGlobal(y, reduced, op="add", sem="release", scope="gpu")
                        break
            """,
            id="reduction-with-control",
        ),
        pytest.param(
            """
            @tilus.Function
            def mma_epilogue(
                a: tilus.SharedTensor(std.f16, 64, 64),
                b: tilus.SharedTensor(std.f16, 64, 64),
                out: tilus.GlobalTensor(std.f32, 64, 64),
            ):
                with std.scope(pragma="mma_stage"):
                    tilus.WgmmaFence()
                    for k in range(0, 2, tag="k_tiles"):
                        acc = tilus.WgmmaMmaSS(a, b, ty=tilus.RegTensor(std.f32, 64, 64))
                        tilus.WgmmaCommitGroup()
                        tilus.WgmmaWaitGroup(n=0)
                        if k == 0:
                            scaled = tilus.Mul(acc, acc, ty=tilus.RegTensor(std.f32, 64, 64))
                            tilus.StoreGlobal(out, scaled, offsets=[0, 0], dims=[0, 1])
                        else:
                            tilus.StoreGlobal(out, acc, offsets=[0, 0], dims=[0, 1])
            """,
            id="mma-epilogue",
        ),
    ],
)
def test_kernel_text_round_trips(source: str) -> None:
    _assert_text_roundtrip(source)


def test_kernel_module_text_round_trips() -> None:
    printed = _assert_text_roundtrip(
        """
        @std.module
        class FusedKernelModule:
            @tilus.Function(metadata=tilus.Metadata(
                grid_blocks=[8, 1, 1],
                cluster_blocks=[1, 1, 1],
                block_indices=["bx", "by", "bz"],
                num_warps=4,
                analysis=tilus.Analysis(
                    divisibility={"row": 16},
                    lower_bound={"row": 0},
                    upper_bound={"row": 1024},
                ),
            ))
            def stage_tile(
                src: tilus.GlobalTensor(
                    std.f16,
                    128, 64,
                    layout=tilus.GlobalLayout(
                        128, 64,
                        size=8192,
                        axes=["row", "col"],
                        offset=0,
                    ),
                ),
                shared: tilus.SharedTensor(
                    std.f16,
                    16, 64,
                    layout=tilus.SharedLayout(
                        16, 64,
                        mode_shape=[16, 64],
                        mode_strides=[64, 1],
                        optional_swizzle=tilus.Swizzle(1, 2, 1),
                    ),
                ),
                row: std.i32,
                barrier: std.i32,
            ):
                with tilus.thread_group(0, 128):
                    tilus.ArriveExpectTxBarrier(
                        barrier=barrier,
                        transaction_bytes=2048,
                        sem="release",
                        scope="cta",
                    )
                    tilus.CopyAsyncBulkGlobalToShared(
                        src,
                        shared,
                        offsets=[row, 0],
                        dims=[0, 1],
                        mbarrier=barrier,
                        evict="evict_last",
                    )
                    tilus.CopyAsyncBulkCommitGroup()
                    tilus.CopyAsyncBulkWaitGroup(n=0)
                    tilus.WaitBarrier(
                        barrier=barrier,
                        phase=1,
                        sem="acquire",
                        scope="cta",
                    )

            @tilus.Function
            def mma_epilogue(
                a: tilus.SharedTensor(std.f16, 64, 64),
                b: tilus.SharedTensor(std.f16, 64, 64),
                out: tilus.GlobalTensor(std.f32, 64, 64),
                do_square: std.bool,
            ) -> tilus.RegTensor(
                std.f32,
                64, 64,
                layout=tilus.RegisterLayout(
                    64, 64,
                    mode_shape=[16, 4, 16, 4],
                    spatial_modes=[0, 2],
                    local_modes=[1, 3],
                ),
            ):
                tilus.Assume(condition=do_square or (not do_square))
                tilus.WgmmaFence()
                acc = tilus.WgmmaMmaSS(
                    a,
                    b,
                    ty=tilus.RegTensor(
                        std.f32,
                        64, 64,
                        layout=tilus.RegisterLayout(
                            64, 64,
                            mode_shape=[16, 4, 16, 4],
                            spatial_modes=[0, 2],
                            local_modes=[1, 3],
                        ),
                    ),
                )
                tilus.WgmmaCommitGroup()
                tilus.WgmmaWaitGroup(n=0)
                if do_square:
                    scaled = tilus.Mul(acc, acc, ty=tilus.RegTensor(std.f32, 64, 64))
                    tilus.StoreGlobal(out, scaled, offsets=[0, 0], dims=[0, 1])
                else:
                    tilus.StoreGlobal(out, acc, offsets=[0, 0], dims=[0, 1])
                return acc
        """
    )

    assert printed.startswith("@std.module")
    assert printed.count("@tilus.Function") == 2


# Parser Edges
@pytest.mark.parametrize(
    "decorator,tensor_ctor,expected_name",
    [
        pytest.param("tilus.function", "tilus.RegisterTensor", "lowercase_alias", id="aliases"),
        pytest.param("tilus.Function", "tilus.RegTensor", "canonical_surface", id="canonical"),
    ],
)
def test_function_surface_aliases_canonicalize(
    decorator: str, tensor_ctor: str, expected_name: str
) -> None:
    printed = _assert_text_roundtrip(
        f"""
        @{decorator}
        def {expected_name}(
            x: {tensor_ctor}(std.f32, 2, 2),
        ) -> {tensor_ctor}(std.f32, 2, 2):
            return x
        """
    )

    assert printed.startswith("@tilus.Function")
    assert f"def {expected_name}" in printed
    assert "@tilus.function" not in printed
    assert "tilus.RegisterTensor" not in printed
    assert printed.count("tilus.RegTensor") == 2


def test_multiple_top_level_functions_with_comments_and_blank_lines_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        # Leading comments and extra blank lines are accepted by Python parsing.
        @tilus.function
        def load_alias(
            src: tilus.GlobalTensor(std.f32, 8),
        ) -> tilus.RegTensor(std.f32, 8):
            # Body comments are intentionally not preserved by the IR printer.
            tile = tilus.LoadGlobal(
                src,
                ty=tilus.RegTensor(std.f32, 8),
                offsets=[0],
                dims=[0],
            )
            return tile


        @tilus.Function(metadata=tilus.Metadata())
        def empty_defaults():
            pass
        """
    )

    assert printed.count("@tilus.Function") == 2
    assert "\n\n@tilus.Function" in printed
    assert "# " not in printed
    assert "@tilus.function" not in printed
    assert "block_indices=[]" in printed


def test_std_module_with_tilus_functions_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        @std.module
        class ParserEdgeModule:
            @tilus.Function
            def load_tile(
                src: tilus.GlobalTensor(std.f32, 4),
            ) -> tilus.RegTensor(std.f32, 4):
                tile = tilus.LoadGlobal(
                    src,
                    ty=tilus.RegTensor(std.f32, 4),
                    offsets=[0],
                    dims=[0],
                )
                return tile

            @tilus.function
            def store_tile(
                dst: tilus.GlobalTensor(std.f32, 4),
                tile: tilus.RegisterTensor(std.f32, 4),
            ):
                tilus.StoreGlobal(dst, tile, offsets=[0], dims=[0])
        """
    )

    assert printed.startswith("@std.module")
    assert printed.count("@tilus.Function") == 2
    assert "@tilus.function" not in printed
    assert "tilus.RegisterTensor" not in printed


def test_mixed_module_and_free_function_translation_unit_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        @std.module
        class MixedUnit:
            @tilus.Function
            def identity(
                x: tilus.RegTensor(std.f32, 2),
            ) -> tilus.RegTensor(std.f32, 2):
                return x

        @tilus.Function
        def free_function(flag: std.bool):
            if flag:
                return
            return
        """
    )

    assert printed.startswith("@std.module")
    assert "\n\n@tilus.Function" in printed
    assert "def free_function" in printed


def test_default_instruction_attrs_stabilize_inside_function_bodies() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function(metadata=tilus.Metadata())
        def default_attrs(
            src: tilus.GlobalTensor(std.f32, 1),
            tile: tilus.RegTensor(std.f32, 1),
        ):
            loaded = tilus.LoadGlobal(src, ty=tilus.RegTensor(std.f32, 1))
            reduced = tilus.Reduce(tile, ty=tilus.RegTensor(std.f32, 1))
            return loaded, reduced
        """
    )

    for fragment in [
        "block_indices=[]",
        "cluster_blocks=[]",
        "grid_blocks=[]",
        "dims=[]",
        "offsets=[]",
        "dim=0",
        "keepdim=False",
        'op="sum"',
    ]:
        assert fragment in printed


def test_nested_function_definition_is_preserved_as_function_body_edge_case() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function
        def outer():
            @tilus.Function
            def inner():
                pass
        """
    )

    assert printed.count("@tilus.Function") == 2
    assert "def outer" in printed
    assert "def inner" in printed


# Expr Attrs
@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            @tilus.Function
            def arithmetic_load_store_offsets(
                src: tilus.GlobalTensor(std.f32, 128, 128),
                dst: tilus.GlobalTensor(std.f32, 128, 128),
                row: std.i32,
                col: std.i32,
                stride: std.i32,
                base: std.i32,
            ):
                tile = tilus.LoadGlobal(
                    src,
                    ty=tilus.RegTensor(std.f32, 4, 4),
                    offsets=[
                        base + row * stride + col,
                        ((row + 1) << 2) + (col & 3),
                    ],
                    dims=[0, 1],
                )
                tilus.StoreGlobal(
                    dst,
                    tile,
                    offsets=[
                        base + (row + 1) * stride + col,
                        ((row + col + 15) // 16) * 16,
                    ],
                    dims=[0, 1],
                )
                return tile
            """,
            id="arithmetic-load-store-offsets",
        ),
        pytest.param(
            """
            @tilus.Function
            def guarded_copy_async_attrs(
                src: tilus.GlobalTensor(std.f32, 256),
                dst: tilus.SharedTensor(std.f32, 64),
                row: std.i32,
                col: std.i32,
                limit: std.i32,
                stride: std.i32,
            ):
                tilus.CopyAsync(
                    src,
                    dst,
                    offsets=[row * stride + col],
                    dims=[0],
                    evict="evict_last",
                    check_bounds=True,
                )
                tilus.CopyAsyncGeneric(
                    ptr="gmem",
                    axes=["row", "col"],
                    offset=(row * stride + col) * 4,
                    mask=(row < limit) and ((col & 1) == 0),
                    evict="no_allocate",
                )
                tilus.CopyAsyncCommitGroup()
                tilus.CopyAsyncWaitGroup(n=1)
            """,
            id="guarded-copy-async-attrs",
        ),
    ],
)
def test_expression_attrs_inside_instruction_functions_roundtrip(source: str) -> None:
    printed = _assert_text_roundtrip(source)

    assert printed.startswith("@tilus.Function")


def test_symbolic_global_layout_attrs_inside_function_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function
        def symbolic_layout_attrs(
            m: std.i32,
            n: std.i32,
            row: std.i32,
            col: std.i32,
            base: std.i32,
            stride: std.i32,
        ):
            logical_src: tilus.GlobalTensor(
                std.f32,
                8,
                layout=tilus.GlobalLayout(
                    m + 1, n * 2,
                    size=((m + 1) * (n * 2) + 31) // 32 * 32,
                    axes=["m", "n"],
                    offset=tilus.Swizzle(1, 2, 1)(base + col) + row * stride,
                ),
            )
            logical = tilus.LoadGlobal(
                logical_src,
                ty=tilus.RegTensor(std.f32, 8),
                offsets=[(row * stride + col) % (m + 1), col & 7],
                dims=[0, 1],
            )
            return logical
        """
    )

    assert "tilus.GlobalLayout" in printed
    assert "offset=" in printed


def test_predicate_and_scope_expression_attrs_inside_function_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function
        def predicate_attrs(
            dst: tilus.GlobalTensor(std.f32, 16),
            row: std.i32,
            col: std.i32,
            m: std.i32,
            n: std.i32,
        ):
            with std.scope(predicate=(row < m) and ((col + 1) <= n), stage="guarded"):
                tilus.Eval((row + col) * (m - n), pred=((row + col) % 2) == 0)
                tilus.Assume(condition=((row + col) % 16 == 0) or (m <= n))
                value = tilus.LoadGlobal(
                    dst,
                    ty=tilus.RegTensor(std.f32, 16),
                    offsets=[(row + col) & 15],
                    dims=[0],
                )
                tilus.StoreGlobal(dst, value, offsets=[(row * 2 + col) & 15], dims=[0])
        """
    )

    assert "predicate=" in printed
    assert "pred=" in printed


def test_barrier_and_bulk_copy_expression_attrs_inside_function_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function
        def barrier_bulk_copy_attrs(
            src: tilus.GlobalTensor(std.f16, 256),
            dst: tilus.SharedTensor(std.f16, 256),
            row: std.i32,
            col: std.i32,
            phase: std.i32,
            stride: std.i32,
            mbarrier: std.i32,
        ):
            tilus.AllocBarrier(counts=[(row + col) * 4, None, (phase + 1) * 16])
            tilus.ArriveExpectTxBarrier(
                barrier=mbarrier + phase,
                transaction_bytes=((row + 1) * stride + col) * 2,
                sem="release",
                scope="cluster",
            )
            tilus.CopyAsyncBulkGlobalToShared(
                src,
                dst,
                offsets=[row * stride + col],
                dims=[0],
                mbarrier=mbarrier + (phase & 1),
                evict="evict_first",
                check_bounds=False,
            )
            tilus.WaitBarrier(
                barrier=mbarrier + phase,
                phase=(phase + 1) & 1,
                sem="acquire",
                scope="cluster",
            )
            tilus.CopyAsyncBulkCommitGroup()
            tilus.CopyAsyncBulkWaitGroup(n=0)
        """
    )

    assert "tilus.ArriveExpectTxBarrier" in printed
    assert "check_bounds=False" in printed


def test_tensor_copy_expression_attrs_inside_function_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function
        def tensor_copy_attrs(
            src: tilus.GlobalTensor(std.f16, 64, 64),
            dst: tilus.SharedTensor(std.f16, 64, 64),
            row: std.i32,
            col: std.i32,
            stride: std.i32,
            phase: std.i32,
            mbarrier: std.i32,
        ):
            tilus.CopyAsyncTensorGlobalToShared(
                src,
                dst,
                offsets=[row * stride + col, (row + col) & 31],
                dims=[0, 1],
                mbarrier=mbarrier + phase,
                cta_group=1,
                multicast_mask=(1 << ((phase & 1) + 1)) - 1,
                cache_policy=phase + 1,
            )
            tilus.CopyAsyncTensorSharedToGlobal(
                dst,
                src,
                offsets=[(row + 1) * stride + col, col & 31],
                dims=[0, 1],
                cache_policy=(phase + 2) * 4,
            )
            tilus.CopyAsyncTensorCommitGroup()
            tilus.CopyAsyncTensorWaitGroup(n=1, read=True)
        """
    )

    assert "multicast_mask=" in printed
    assert "cache_policy=" in printed


def test_reduce_and_layout_attr_lists_inside_function_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function
        def reduce_layout_attr_lists(
            src: tilus.GlobalTensor(std.f32, 8, 4),
            dst: tilus.GlobalTensor(std.f32, 8),
            row: std.i32,
            col: std.i32,
        ):
            tile = tilus.LoadGlobal(
                src,
                offsets=[row, col],
                dims=[0, 1],
                ty=tilus.RegTensor(
                    std.f32,
                    8, 4,
                    layout=tilus.RegisterLayout(
                        8, 4,
                        mode_shape=[2, 4, 4],
                        spatial_modes=[0],
                        local_modes=[1, 2],
                    ),
                ),
            )
            hinted = tilus.AnnotateLayout(
                tile,
                ty=tilus.RegTensor(
                    std.f32,
                    8, 4,
                    layout=tilus.RegisterLayout(
                        8, 4,
                        mode_shape=[2, 4, 4],
                        spatial_modes=[0],
                        local_modes=[1, 2],
                    ),
                ),
                layout=tilus.RegisterLayout(
                    8, 4,
                    mode_shape=[2, 4, 4],
                    spatial_modes=[0],
                    local_modes=[1, 2],
                ),
            )
            reduced = tilus.Reduce(
                hinted,
                ty=tilus.RegTensor(std.f32, 8),
                dim=1,
                op="max",
                keepdim=False,
            )
            tilus.StoreGlobal(dst, reduced, offsets=[row], dims=[0])
            return reduced
        """
    )

    assert "spatial_modes=[0]" in printed
    assert "tilus.Reduce" in printed


def test_multi_function_expression_attr_unit_roundtrip() -> None:
    printed = _assert_text_roundtrip(
        """
        @tilus.Function(
            metadata=tilus.Metadata(
                grid_blocks=[2, 1, 1],
                block_indices=["bx", "by", "bz"],
            )
        )
        def metadata_expr_attrs(
            src: tilus.GlobalTensor(std.f32, 128),
            dst: tilus.GlobalTensor(std.f32, 128),
            grid_m: std.i32,
            grid_n: std.i32,
            base: std.i32,
        ):
            value = tilus.LoadGlobal(
                src,
                ty=tilus.RegTensor(std.f32, 8),
                offsets=[base + (grid_m * grid_n) % 128],
                dims=[0],
            )
            tilus.StoreGlobal(dst, value, offsets=[base & 127], dims=[0])

        @tilus.Function
        def tcgen05_expr_attrs(
            tile: tilus.TMemoryTensor(std.f32, 64, 16, 8),
            src: tilus.SharedTensor(std.f32, 64, 16),
            phase: std.i32,
            row: std.i32,
            col: std.i32,
            mbarrier: std.i32,
        ):
            sliced = tilus.Tcgen05Slice(
                tile,
                ty=tilus.TMemoryTensor(std.f32, 16, 8),
                offsets=[(row + phase) & 15, col * 8],
                slice_dims=[0, 2],
            )
            tilus.Tcgen05Alloc(cta_group=1)
            tilus.Tcgen05Commit(
                mbarrier=mbarrier + phase,
                cta_group=1,
                multicast_mask=3,
            )
            tilus.Tcgen05Wait(wait_load=True, wait_store=False)
            return sliced
        """
    )

    assert printed.count("@tilus.Function") == 2
    assert "grid_blocks=" in printed
    assert "tilus.Tcgen05Slice" in printed
