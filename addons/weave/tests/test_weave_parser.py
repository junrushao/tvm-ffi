# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Parser surface tests for Weave frames."""

from __future__ import annotations

from textwrap import dedent

import pytest
import tvm_ffi
import weave  # noqa: F401
import weave.ir as wi
from _roundtrip import assert_source_roundtrip
from tvm_ffi import std
from tvm_ffi._pyast_parser import parse
from weave.ir import (
    Assign,
    Block,
    BufferRef,
    Const,
    ElectedThreadBlock,
    Kernel,
    LeaderCtaBlock,
    MbarrierSpec,
    PipelineConfig,
    PipelineSpec,
    TaskSpec,
    f32,
    i32,
)


def _parse(source: str):
    return parse(dedent(source).strip())


def test_parse_task_and_block_frames() -> None:
    parsed = _parse(
        """
        with weave.TaskSpec("load", "producer", "tma", pipeline="main"):
            with weave.Block():
                weave.Assign(weave.Const("x", result_ty=std.i32), 1, op="=")
        """
    )
    expected = TaskSpec(
        "load",
        "producer",
        "tma",
        pipeline="main",
        body=[Block([Assign(Const("x", i32), 1)])],
    )
    assert tvm_ffi.structural_equal(parsed, expected)


def test_parse_for_loop_frame_binds_induction_var() -> None:
    parsed = _parse(
        """
        for k in weave.ForLoop(4, start=0, step=1, ty=std.i32):
            break
        """
    )
    expected = wi.ForLoop(4, std.Var(i32, "k"), body=[std.Break()], start=0, step=1)

    assert tvm_ffi.structural_equal(parsed, expected)


def test_parse_named_scope_frames() -> None:
    parsed = _parse(
        """
        with weave.Block():
            with weave.LeaderCtaBlock():
                weave.Assign(weave.Const("leader", result_ty=std.i32), 1, op="=")
            with weave.ElectedThreadBlock():
                weave.Assign(weave.Const("elected", result_ty=std.i32), 2, op="=")
        """
    )
    expected = Block(
        [
            LeaderCtaBlock([Assign(Const("leader", i32), 1)]),
            ElectedThreadBlock([Assign(Const("elected", i32), 2)]),
        ]
    )
    assert tvm_ffi.structural_equal(parsed, expected)


def test_parse_lowercase_task_alias_canonicalizes() -> None:
    parsed = _parse(
        """
        with weave.task("compute", "consumer", "mma", depends_on=["load"]):
            pass
        """
    )

    assert isinstance(parsed, TaskSpec)
    assert parsed.name == "compute"
    assert parsed.depends_on == ("load",)
    printed = parsed.text()
    assert printed.startswith("with weave.TaskSpec(")
    assert 'name="compute"' in printed


def test_parse_direct_constructor_mnemonics_and_lm_namespace() -> None:
    assert tvm_ffi.structural_equal(
        _parse('weave.Pipeline("main", 2, style="warp_specialized", cta_group=2)'),
        PipelineSpec("main", 2, style="warp_specialized", cta_group=2),
    )
    assert tvm_ffi.structural_equal(
        _parse('weave.Mbarrier("full", 2, producers=["load"], consumers=["mma"])'),
        MbarrierSpec("full", 2, producers=("load",), consumers=("mma",)),
    )
    assert tvm_ffi.structural_equal(
        _parse('weave.Buffer("A", weave.lm.f32, shape=[128, 64])'),
        BufferRef("A", f32, (128, 64)),
    )


def test_parse_kernel_decorator_surface() -> None:
    parsed = _parse(
        """
        @weave.Kernel(pipeline=weave.PipelineConfig(num_stages=1, style="sequential"))
        def kernel():
            with weave.TaskSpec("load", "producer", "tma"):
                pass
        """
    )
    expected = Kernel(
        "kernel",
        [],
        None,
        [TaskSpec("load", "producer", "tma")],
        pipeline=PipelineConfig(num_stages=1, style="sequential"),
    )
    assert tvm_ffi.structural_equal(parsed, expected)


def test_parse_lowercase_aliases_canonicalize() -> None:
    printed = assert_source_roundtrip(
        """
        @weave.kernel
        def kernel():
            with weave.task("load", "producer", "tma"):
                pass
        """
    )

    assert printed.startswith("@weave.Kernel")
    assert "with weave.TaskSpec" in printed
    assert "@weave.kernel" not in printed
    assert "with weave.task" not in printed


def test_parse_scope_factories_and_for_loop_options() -> None:
    parsed = _parse(
        """
        with weave.LeaderCtaBlock():
            with weave.ElectedThreadBlock():
                for stage in weave.ForLoop(
                    4,
                    start=0,
                    step_expr=1,
                    constexpr=True,
                    unroll=2,
                    ctype="int",
                    ty=std.i32,
                ):
                    with weave.ConditionalIteration(stage, last_expr=(stage == 3)):
                        weave.Assign(weave.Const("stage", result_ty=std.i32), stage)
        """
    )
    stage = std.Var(i32, "stage")
    expected = LeaderCtaBlock(
        [
            ElectedThreadBlock(
                [
                    wi.ForLoop(
                        4,
                        stage,
                        body=[
                            wi.ConditionalIteration(
                                stage,
                                last_expr=stage == 3,
                                body=[Assign(Const("stage", i32), stage)],
                            )
                        ],
                        start=0,
                        step_expr=1,
                        constexpr=True,
                        unroll=2,
                        ctype="int",
                    )
                ]
            )
        ]
    )

    assert tvm_ffi.structural_equal(parsed, expected)


def test_parse_lm_namespace_in_signature() -> None:
    parsed = _parse(
        """
        @weave.Kernel
        def typed(
            ptr: weave.lm.ptr(weave.lm.f32, const=True, volatile=True, space="global"),
        ) -> weave.lm.uniform(weave.lm.i32):
            result = 1
            return result
        """
    )

    assert isinstance(parsed.args[0].ty, wi.PtrTy)
    assert parsed.args[0].ty.const is True
    assert parsed.args[0].ty.volatile is True
    assert isinstance(parsed.ret_type, wi.UniformTy)


def test_parse_direct_constructor_namespace() -> None:
    parsed = _parse(
        """
        weave.Buffer(
            "A",
            std.f16,
            shape=[128, 64],
            tma=weave.TmaDescriptor(2, box_shape=[16, 64]),
        )
        """
    )
    expected = wi.BufferRef("A", wi.f16, (128, 64), tma=wi.TmaDescriptor(2, (16, 64)))

    assert tvm_ffi.structural_equal(parsed, expected)


@pytest.mark.parametrize(
    "source, match",
    [
        pytest.param(
            """
            with weave.Block(unexpected=True):
                pass
            """,
            "unexpected keyword argument",
            id="scope-unexpected-kwarg",
        ),
        pytest.param(
            """
            for i, j in weave.ForLoop(4):
                pass
            """,
            "expected one loop variable",
            id="for-loop-multiple-targets",
        ),
        pytest.param(
            """
            with weave.ConditionalIteration(object()):
                pass
            """,
            "expected ffi.std.Expr",
            id="conditional-invalid-expr",
        ),
        pytest.param(
            """
            @weave.Kernel(unknown=1)
            def kernel():
                pass
            """,
            "unexpected keyword argument",
            id="kernel-unknown-attr",
        ),
    ],
)
def test_parse_weave_frame_errors(source: str, match: str) -> None:
    with pytest.raises((TypeError, ValueError), match=match):
        _parse(source)
