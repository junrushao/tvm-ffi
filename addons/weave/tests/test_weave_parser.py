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

import tvm_ffi
import weave  # noqa: F401
from tvm_ffi._pyast_parser import parse
from weave.ir import Assign, Block, Const, Kernel, PipelineConfig, TaskSpec, i32


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
    assert parsed.var.name == "k"
    assert len(parsed.body) == 1


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
