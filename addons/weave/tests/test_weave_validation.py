# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Focused validation tests for Weave IR constructors."""

from __future__ import annotations

import pytest
import weave  # noqa: F401
from weave.ir import (
    AtomicOp,
    BarrierSignal,
    Const,
    Elementwise,
    GmemLoad,
    MbarrierSpec,
    SmemStore,
    Tcgen05Cp,
    i32,
)


def test_expr_fields_reject_raw_strings() -> None:
    with pytest.raises(TypeError):
        SmemStore("src", 1)
    with pytest.raises(TypeError):
        Elementwise(op="add", inputs=["a", 1])


def test_domain_fields_are_validated() -> None:
    with pytest.raises(ValueError):
        BarrierSignal(MbarrierSpec("full", 1), "bad", 0)
    with pytest.raises(ValueError):
        AtomicOp("bad", 1, 2, space="gmem", dtype=i32)
    with pytest.raises(ValueError):
        Tcgen05Cp(1, 2, shape="bad")


def test_dtype_fields_reject_raw_strings() -> None:
    with pytest.raises(TypeError):
        GmemLoad(1, 2, count=1, dtype="f32", dst_dtype=i32)


def test_structured_barrier_refs_reject_raw_strings() -> None:
    with pytest.raises(TypeError):
        BarrierSignal("full", "arrive", Const("stage", i32))
