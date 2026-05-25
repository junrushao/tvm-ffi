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

from typing import ClassVar

import pytest
import tilus
from tilus.ir import instructions
from tilus.ir.inst import Instruction, InstructionError
from tilus.ir.instructions import cuda, generic
from tvm_ffi import std


def test_atomic_string_domains_are_validated() -> None:
    cuda.AtomicGlobalInst(inputs=[1, 2], op="add", sem="acq_rel", scope="sys")
    cuda.AtomicGlobalInst(inputs=[1, 2], op="exch")
    cuda.AtomicGlobalInst(inputs=[1, 2], op="inc")

    with pytest.raises(ValueError, match="op must be one of"):
        cuda.AtomicGlobalInst(inputs=[1, 2], op="nand")
    with pytest.raises(ValueError, match="sem must be one of"):
        cuda.AtomicGlobalInst(inputs=[1, 2], op="add", sem="volatile")
    with pytest.raises(ValueError, match="scope must be one of"):
        cuda.AtomicSharedInst(inputs=[1, 2], op="add", scope="warp")


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
    cuda.CopyAsyncInst(inputs=[1, 2], offsets=[0], dims=[0], evict="evict_last")
    cuda.CopyAsyncBulkSharedToGlobalInst(
        inputs=[1, 2], offsets=[0], dims=[0], l2_evict="evict_first"
    )

    with pytest.raises(ValueError, match="space must be one of"):
        cuda.FenceProxyAsync(space="local")
    with pytest.raises(ValueError, match="evict must be one of"):
        cuda.CopyAsyncInst(inputs=[1, 2], offsets=[0], dims=[0], evict="cache_all")
    with pytest.raises(ValueError, match="l2_evict must be one of"):
        cuda.CopyAsyncBulkSharedToGlobalInst(
            inputs=[1, 2], offsets=[0], dims=[0], l2_evict="sticky"
        )


def test_optional_string_domains_allow_none() -> None:
    cuda.CopyAsyncInst(inputs=[1, 2], offsets=[0], dims=[0], evict=None)
    cuda.CopyAsyncGenericInst(ptr="ptr", axes=["i"], offset=0, evict=None)
    cuda.CopyAsyncBulkGlobalToSharedInst(
        inputs=[1, 2], offsets=[0], dims=[0], mbarrier=0, evict=None
    )
    cuda.CopyAsyncBulkSharedToGlobalInst(inputs=[1, 2], offsets=[0], dims=[0], l2_evict=None)


def test_required_domains_reject_none() -> None:
    with pytest.raises((TypeError, ValueError), match="op"):
        cuda.AtomicGlobalInst(inputs=[1, 2], op=None)
    with pytest.raises((TypeError, ValueError), match="space"):
        cuda.FenceProxyAsync(space=None)
    with pytest.raises((TypeError, ValueError), match="cta_group"):
        cuda.Tcgen05AllocInst(cta_group=None)


def test_zero_input_instructions_reject_inputs() -> None:
    with pytest.raises(InstructionError, match="expects 0 input"):
        generic.SyncThreadsInst(inputs=[1])
    with pytest.raises(InstructionError, match="expects 0 input"):
        cuda.CopyAsyncCommitGroupInst(inputs=[1])


def test_obvious_instruction_arity_is_validated() -> None:
    generic.LoadGlobalInst(inputs=[1], offsets=[0], dims=[0])
    generic.AddInst(inputs=[1, 2])

    with pytest.raises(InstructionError, match="expects 1 input"):
        generic.LoadGlobalInst(inputs=[], offsets=[0], dims=[0])
    with pytest.raises(InstructionError, match="expects 2 input"):
        generic.AddInst(inputs=[1])
    with pytest.raises(ValueError, match="offsets and dims must have the same length"):
        generic.LoadGlobalInst(inputs=[1], offsets=[0], dims=[0, 1])
    with pytest.raises(ValueError, match="offsets and dims must have the same length"):
        cuda.CopyAsyncInst(inputs=[1, 2], offsets=[0, 1], dims=[0])
    with pytest.raises(ValueError, match="warp_spatial and warp_repeat must have the same length"):
        cuda.SimtDotInst(
            inputs=[1, 2],
            warp_spatial=[1],
            warp_repeat=[1, 1],
            thread_spatial=[1],
            thread_repeat=[1],
        )
    with pytest.raises(
        ValueError, match="warp_spatial and thread_spatial must have the same length"
    ):
        cuda.SimtDotInst(
            inputs=[1, 2],
            warp_spatial=[1],
            warp_repeat=[1],
            thread_spatial=[1, 1],
            thread_repeat=[1, 1],
        )


def test_load_type_inputs_must_match_output_dtype_and_shape() -> None:
    src = std.Var(tilus.GlobalTensor("float32", 16), "src")
    valid_output = std.Var(tilus.RegTensor("float32", 16), "dst")
    tilus.LoadGlobal(src, output=valid_output, ty=src.ty, offsets=[0], dims=[0])

    with pytest.raises(TypeError, match="must match output dtype and shape"):
        tilus.LoadGlobal(
            src,
            ty=src.ty,
            output=std.Var(tilus.RegTensor("float32", 8), "dst"),
            offsets=[0],
            dims=[0],
        )
    with pytest.raises(TypeError, match="must match output dtype and shape"):
        tilus.LoadGlobal(
            src,
            ty=src.ty,
            output=std.Var(tilus.RegTensor("float16", 16), "dst"),
            offsets=[0],
            dims=[0],
        )


@pytest.mark.parametrize(
    "cls,kwargs,expected_inputs",
    [
        (cuda.AtomicGlobalInst, {"op": "add"}, 2),
        (cuda.CopyAsyncInst, {"offsets": [0], "dims": [0]}, 2),
        (cuda.CopyAsyncBulkSharedToClusterSharedInst, {"mbarrier": 0, "remote_rank": 1}, 2),
        (
            cuda.CopyAsyncTensorGlobalToSharedInst,
            {"offsets": [0], "dims": [0], "mbarrier": 0, "cta_group": 1},
            2,
        ),
        (
            cuda.SimtDotInst,
            {
                "warp_spatial": [1],
                "warp_repeat": [1],
                "thread_spatial": [1],
                "thread_repeat": [1],
            },
            2,
        ),
        (cuda.Tcgen05SliceInst, {"offsets": [0], "slice_dims": [0]}, 1),
        (cuda.Tcgen05MmaSSInst, {"enable_input_d": True, "cta_group": 1}, 2),
        (cuda.WgmmaMmaRSInst, {}, 2),
    ],
)
def test_representative_cuda_instruction_operands_are_validated(
    cls: type[Instruction],
    kwargs: dict[str, object],
    expected_inputs: int,
) -> None:
    if expected_inputs > 0:
        cls(inputs=[1] * expected_inputs, **kwargs)
        with pytest.raises(
            InstructionError, match=rf"{cls.__name__} expects {expected_inputs} input"
        ):
            cls(inputs=[1] * (expected_inputs - 1), **kwargs)
    else:
        cls(**kwargs)

    with pytest.raises(InstructionError, match=rf"{cls.__name__} expects {expected_inputs} input"):
        cls(inputs=[1] * (expected_inputs + 1), **kwargs)


def test_explicit_inputs_none_is_rejected() -> None:
    with pytest.raises(TypeError, match="inputs"):
        generic.AddInst(inputs=None)
    with pytest.raises(TypeError, match="inputs"):
        generic.SyncThreadsInst(inputs=None)


@pytest.mark.parametrize("bad_input", [object(), {"x": 1}, [object()]])
def test_instruction_inputs_reject_non_expr_values(bad_input: object) -> None:
    with pytest.raises(TypeError, match=r"expected ffi\.std\.Expr"):
        generic.AddInst(inputs=[bad_input, 1])


def test_reduce_op_domain_is_validated() -> None:
    generic.ReduceInst(inputs=[1], dim=0, op="sum")
    generic.ReduceInst(inputs=[1], dim=0, op="max")
    generic.ReduceInst(inputs=[1], dim=0, op="min")

    with pytest.raises(ValueError, match="op must be one of"):
        generic.ReduceInst(inputs=[1], dim=0, op="median")
    with pytest.raises(TypeError, match="op"):
        generic.ReduceInst(inputs=[1], dim=0, op=None)


@pytest.mark.parametrize(
    "make,message",
    [
        (
            lambda: generic.StoreGlobalInst(inputs=[1, 2], offsets=[0], dims=[0, 1]),
            "offsets and dims must have the same length",
        ),
        (
            lambda: cuda.CopyAsyncBulkGlobalToSharedInst(
                inputs=[1, 2], offsets=[0], dims=[0, 1], mbarrier=0
            ),
            "offsets and dims must have the same length",
        ),
        (
            lambda: cuda.CopyAsyncTensorGlobalToSharedInst(
                inputs=[1, 2], offsets=[0], dims=[0, 1], mbarrier=0, cta_group=1
            ),
            "offsets and dims must have the same length",
        ),
        (
            lambda: cuda.Tcgen05SliceInst(inputs=[1], offsets=[0], slice_dims=[0, 1]),
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
            inputs=[1, 2],
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
        kwargs.update(inputs=[1, 2], offsets=[0], dims=[0], mbarrier=0)
    elif cls is cuda.Tcgen05CommitInst:
        kwargs.update(mbarrier=0)
    elif cls in (cuda.Tcgen05MmaSSInst, cuda.Tcgen05MmaTSInst):
        kwargs.update(inputs=[1, 2], enable_input_d=True)
    return cls(**kwargs)


@pytest.mark.parametrize(
    "class_name",
    [
        name
        for name in instructions.__all__
        if hasattr(getattr(instructions, name), "VALID_CTA_GROUPS")
    ],
)
def test_all_cta_group_instruction_domains_are_validated(class_name: str) -> None:
    cls = getattr(instructions, class_name)

    for valid in cls.VALID_CTA_GROUPS:
        _make_cta_group_instruction(cls, valid)

    with pytest.raises(ValueError, match="cta_group must be one of"):
        _make_cta_group_instruction(cls, 0)
    with pytest.raises(ValueError, match="cta_group must be one of"):
        _make_cta_group_instruction(cls, std.BoolImm.from_py(True))


def test_int_domains_handle_intimm_and_reject_symbolic_values() -> None:
    class IntImmCtaGroupInst(Instruction, mnemonic="tilus.TestIntImmCtaGroup"):
        VALID_CTA_GROUPS: ClassVar[tuple[int, ...]] = (1, 2)
        cta_group: ClassVar[std.Expr] = std.IntImm.from_py(2)

    class SymbolicCtaGroupInst(Instruction, mnemonic="tilus.TestSymbolicCtaGroup"):
        VALID_CTA_GROUPS: ClassVar[tuple[int, ...]] = (1, 2)
        cta_group: ClassVar[std.Expr] = std.Var(std.PrimTy("int32"), "cta")

    IntImmCtaGroupInst()
    cuda.CopyAsyncTensorGlobalToSharedInst(
        inputs=[1, 2],
        offsets=[0],
        dims=[0],
        mbarrier=0,
        cta_group=std.IntImm.from_py(2),
    )
    cuda.CopyAsyncWaitGroupInst(n=std.IntImm.from_py(0))

    with pytest.raises(ValueError, match="cta_group must be one of"):
        SymbolicCtaGroupInst()
    with pytest.raises(ValueError, match="cta_group must be one of"):
        cuda.CopyAsyncTensorGlobalToSharedInst(
            inputs=[1, 2],
            offsets=[0],
            dims=[0],
            mbarrier=0,
            cta_group=std.Var(std.PrimTy("int32"), "cta"),
        )
    with pytest.raises(ValueError, match="n must be a non-negative integer constant"):
        cuda.CopyAsyncWaitGroupInst(n=std.Var(std.PrimTy("int32"), "n"))


def test_tuple_expected_input_arity_is_validated() -> None:
    class FlexibleInputInst(Instruction, mnemonic="tilus.TestFlexibleInput"):
        EXPECTED_INPUTS: ClassVar[tuple[int, ...]] = (1, 3)

    FlexibleInputInst(inputs=[1])
    FlexibleInputInst(inputs=[1, 2, 3])

    with pytest.raises(InstructionError, match="expects one of 1, 3 input"):
        FlexibleInputInst(inputs=[1, 2])
