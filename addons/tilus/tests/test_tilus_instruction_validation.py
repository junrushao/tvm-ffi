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

import pytest
import tilus
from tilus.ir import instructions
from tilus.ir.inst import Instruction
from tilus.ir.instructions import cuda, generic
from tvm_ffi import std


def _output() -> std.Var:
    return std.Var(std.PrimTy("int32"), "out")


def test_atomic_string_domains_are_validated() -> None:
    cuda.AtomicGlobalInst(1, 2, op="add", sem="acq_rel", scope="sys")
    cuda.AtomicGlobalInst(1, 2, op="exch")
    cuda.AtomicGlobalInst(1, 2, op="inc")

    with pytest.raises(ValueError, match="op must be one of"):
        cuda.AtomicGlobalInst(1, 2, op="nand")
    with pytest.raises(ValueError, match="sem must be one of"):
        cuda.AtomicGlobalInst(1, 2, op="add", sem="volatile")
    with pytest.raises(ValueError, match="scope must be one of"):
        cuda.AtomicSharedInst(1, 2, op="add", scope="warp")


def test_cuda_barrier_string_domains_are_validated() -> None:
    cuda.ArriveBarrierInst(barrier=0, count=1, sem="relaxed", scope="cluster")
    cuda.WaitBarrierInst(barrier=0, phase=0, sem="relaxed", scope="cluster")

    with pytest.raises(ValueError, match="sem must be one of"):
        cuda.ArriveBarrierInst(barrier=0, count=1, sem="acquire")
    with pytest.raises(ValueError, match="sem must be one of"):
        cuda.WaitBarrierInst(barrier=0, phase=0, sem="release")
    with pytest.raises(ValueError, match="scope must be one of"):
        cuda.ArriveBarrierInst(barrier=0, count=1, scope="gpu")


def test_cuda_fence_and_cache_string_domains_are_validated() -> None:
    cuda.FenceProxyAsync(space="shared::cta")
    cuda.CopyAsyncInst(1, 2, offsets=[0], dims=[0], evict="evict_last")
    cuda.CopyAsyncBulkSharedToGlobalInst(1, 2, offsets=[0], dims=[0], l2_evict="evict_first")

    with pytest.raises(ValueError, match="space must be one of"):
        cuda.FenceProxyAsync(space="local")
    with pytest.raises(ValueError, match="evict must be one of"):
        cuda.CopyAsyncInst(1, 2, offsets=[0], dims=[0], evict="cache_all")
    with pytest.raises(ValueError, match="l2_evict must be one of"):
        cuda.CopyAsyncBulkSharedToGlobalInst(1, 2, offsets=[0], dims=[0], l2_evict="sticky")


def test_optional_string_domains_allow_none() -> None:
    cuda.CopyAsyncInst(1, 2, offsets=[0], dims=[0], evict=None)
    cuda.CopyAsyncGenericInst(ptr="ptr", axes=["i"], offset=0, evict=None)
    cuda.CopyAsyncBulkGlobalToSharedInst(1, 2, offsets=[0], dims=[0], mbarrier=0, evict=None)
    cuda.CopyAsyncBulkSharedToGlobalInst(1, 2, offsets=[0], dims=[0], l2_evict=None)


def test_required_domains_reject_none() -> None:
    with pytest.raises((TypeError, ValueError), match="op"):
        cuda.AtomicGlobalInst(1, 2, op=None)
    with pytest.raises((TypeError, ValueError), match="space"):
        cuda.FenceProxyAsync(space=None)
    with pytest.raises((TypeError, ValueError), match="cta_group"):
        cuda.Tcgen05AllocInst(cta_group=None)


def test_instruction_field_validations_are_applied() -> None:
    generic.LoadGlobalInst(1, output=_output(), offsets=[0], dims=[0])
    generic.AddInst(1, 2, output=_output())

    with pytest.raises(ValueError, match="offsets and dims must have the same length"):
        generic.LoadGlobalInst(1, output=_output(), offsets=[0], dims=[0, 1])
    with pytest.raises(ValueError, match="offsets and dims must have the same length"):
        cuda.CopyAsyncInst(1, 2, offsets=[0, 1], dims=[0])
    with pytest.raises(ValueError, match="warp_spatial and warp_repeat must have the same length"):
        cuda.SimtDotInst(
            1,
            2,
            output=_output(),
            warp_spatial=[1],
            warp_repeat=[1, 1],
            thread_spatial=[1],
            thread_repeat=[1],
        )
    with pytest.raises(
        ValueError, match="warp_spatial and thread_spatial must have the same length"
    ):
        cuda.SimtDotInst(
            1,
            2,
            output=_output(),
            warp_spatial=[1],
            warp_repeat=[1],
            thread_spatial=[1, 1],
            thread_repeat=[1, 1],
        )


def test_load_type_hints_must_match_input_dtype_and_scope() -> None:
    src = std.Var(tilus.GlobalTensor("float32", 16), "src")
    tilus.LoadGlobal(src, ty=tilus.RegTensor("float32", 8), offsets=[0], dims=[0])

    with pytest.raises(TypeError, match="must match src dtype and storage scope"):
        tilus.LoadGlobal(
            src,
            ty=tilus.RegTensor("float16", 8),
            offsets=[0],
            dims=[0],
        )
    with pytest.raises(TypeError, match="must match src dtype and storage scope"):
        tilus.LoadGlobal(
            std.Var(tilus.SharedTensor("float32", 16), "src"),
            ty=tilus.RegTensor("float32", 8),
            offsets=[0],
            dims=[0],
        )
    with pytest.raises(TypeError, match="register or global tensor"):
        tilus.LoadGlobal(
            src,
            ty=tilus.SharedTensor("float32", 8),
            offsets=[0],
            dims=[0],
        )
    with pytest.raises(TypeError, match="exactly one of `ty` and `output`"):
        tilus.LoadGlobal(
            src,
            output=std.Var(tilus.RegTensor("float32", 8), "dst"),
            ty=tilus.RegTensor("float32", 8),
            offsets=[0],
            dims=[0],
        )


def test_explicit_inputs_none_is_rejected() -> None:
    with pytest.raises(TypeError, match="inputs"):
        generic.AddInst(inputs=None)
    with pytest.raises(TypeError, match="inputs"):
        generic.SyncThreadsInst(inputs=None)


@pytest.mark.parametrize("bad_input", [object(), {"x": 1}, [object()]])
def test_instruction_inputs_reject_non_expr_values(bad_input: object) -> None:
    with pytest.raises(TypeError, match=r"expected ffi\.std\.Expr"):
        generic.AddInst(bad_input, 1, output=_output())


def test_reduce_op_domain_is_validated() -> None:
    generic.ReduceInst(1, output=_output(), dim=0, op="sum")
    generic.ReduceInst(1, output=_output(), dim=0, op="max")
    generic.ReduceInst(1, output=_output(), dim=0, op="min")

    with pytest.raises(ValueError, match="op must be one of"):
        generic.ReduceInst(1, output=_output(), dim=0, op="median")
    with pytest.raises(TypeError, match="op"):
        generic.ReduceInst(1, output=_output(), dim=0, op=None)


@pytest.mark.parametrize(
    "make,message",
    [
        (
            lambda: generic.StoreGlobalInst(1, 2, offsets=[0], dims=[0, 1]),
            "offsets and dims must have the same length",
        ),
        (
            lambda: cuda.CopyAsyncBulkGlobalToSharedInst(
                1, 2, offsets=[0], dims=[0, 1], mbarrier=0
            ),
            "offsets and dims must have the same length",
        ),
        (
            lambda: cuda.CopyAsyncTensorGlobalToSharedInst(
                1, 2, offsets=[0], dims=[0, 1], mbarrier=0, cta_group=1
            ),
            "offsets and dims must have the same length",
        ),
        (
            lambda: cuda.Tcgen05SliceInst(1, output=_output(), offsets=[0], slice_dims=[0, 1]),
            "offsets and slice_dims must have the same length",
        ),
    ],
)
def test_additional_matching_attr_lengths_are_validated(make, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        make()


def test_cuda_integer_domains_are_validated() -> None:
    cuda.Tcgen05AllocInst(cta_group=1)
    cuda.CopyAsyncWaitGroupInst(n=0)

    with pytest.raises(ValueError, match="cta_group must be one of"):
        cuda.Tcgen05AllocInst(cta_group=3)
    with pytest.raises(ValueError, match="n must be a non-negative integer constant"):
        cuda.CopyAsyncWaitGroupInst(n=-1)


def test_integer_domains_reject_bool_values() -> None:
    with pytest.raises(ValueError, match="cta_group must be one of"):
        cuda.Tcgen05AllocInst(cta_group=True)
    with pytest.raises(ValueError, match="cta_group must be one of"):
        cuda.CopyAsyncTensorGlobalToSharedInst(
            1,
            2,
            offsets=[0],
            dims=[0],
            mbarrier=0,
            cta_group=std.BoolImm.from_py(True),
        )
    with pytest.raises(ValueError, match="n must be a non-negative integer constant"):
        cuda.CopyAsyncWaitGroupInst(n=False)


def _make_cta_group_instruction(cls: type[Instruction], cta_group: object) -> Instruction:
    kwargs: dict[str, object] = {"cta_group": cta_group}
    if cls is cuda.CopyAsyncTensorGlobalToSharedInst:
        return cls(1, 2, offsets=[0], dims=[0], mbarrier=0, **kwargs)
    elif cls is cuda.Tcgen05CommitInst:
        kwargs.update(mbarrier=0)
    elif cls in (cuda.Tcgen05MmaSSInst, cuda.Tcgen05MmaTSInst):
        return cls(1, 2, output=_output(), enable_input_d=True, **kwargs)
    return cls(**kwargs)


@pytest.mark.parametrize(
    "class_name",
    [
        "Tcgen05AllocInst",
        "Tcgen05RelinquishAllocPermitInst",
        "Tcgen05CommitInst",
        "Tcgen05MmaSSInst",
        "Tcgen05MmaTSInst",
        "CopyAsyncTensorGlobalToSharedInst",
    ],
)
def test_all_cta_group_instruction_domains_are_validated(class_name: str) -> None:
    cls = getattr(instructions, class_name)

    for valid in (1, 2):
        _make_cta_group_instruction(cls, valid)

    with pytest.raises(ValueError, match="cta_group must be one of"):
        _make_cta_group_instruction(cls, 0)
    with pytest.raises(ValueError, match="cta_group must be one of"):
        _make_cta_group_instruction(cls, std.BoolImm.from_py(True))


def test_int_domains_reject_std_expr_values() -> None:
    with pytest.raises(ValueError, match="cta_group must be one of"):
        cuda.Tcgen05AllocInst(cta_group=std.Var(std.PrimTy("int32"), "cta"))
    with pytest.raises(ValueError, match="cta_group must be one of"):
        cuda.Tcgen05AllocInst(cta_group=std.IntImm.from_py(2))
    with pytest.raises(ValueError, match="cta_group must be one of"):
        cuda.CopyAsyncTensorGlobalToSharedInst(
            1,
            2,
            offsets=[0],
            dims=[0],
            mbarrier=0,
            cta_group=std.Var(std.PrimTy("int32"), "cta"),
        )
    with pytest.raises(ValueError, match="cta_group must be one of"):
        cuda.CopyAsyncTensorGlobalToSharedInst(
            1,
            2,
            offsets=[0],
            dims=[0],
            mbarrier=0,
            cta_group=std.IntImm.from_py(2),
        )
    with pytest.raises(ValueError, match="n must be a non-negative integer constant"):
        cuda.CopyAsyncWaitGroupInst(n=std.Var(std.PrimTy("int32"), "n"))
    with pytest.raises(ValueError, match="n must be a non-negative integer constant"):
        cuda.CopyAsyncWaitGroupInst(n=std.IntImm.from_py(0))
