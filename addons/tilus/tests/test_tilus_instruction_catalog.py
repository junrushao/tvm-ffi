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
"""Round-trip coverage for every public Tilus instruction node."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable

import pytest
import tilus
import tvm_ffi
from tilus.ir import instructions, layout, tensor
from tilus.ir.inst import Instruction
from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi._pyast_parser import parse


def _input_vars(node: object) -> dict[str, std.Var]:
    values = (
        getattr(node, field.name)
        for field in dc.fields(type(node))
        if field.lang_kind == "arg" and field.name is not None
    )
    return {value.name: value for value in values if isinstance(value, std.Var)}


def _round_trip(node: object) -> None:
    parsed = parse(node.text(), extra_vars=_input_vars(node))
    assert tvm_ffi.structural_equal(parsed, node), node.text()


def _reg_layout() -> layout.RegisterLayout:
    return layout.register_row_major(2, 2)


def _shared_layout() -> layout.SharedLayout:
    return layout.shared_row_major(2, 2)


def _global_layout() -> layout.GlobalLayout:
    return layout.global_row_major(2, 2)


def _reg_tensor() -> tensor.RegisterTensor:
    return tensor.register_tensor("float32", (2, 2), layout=_reg_layout())


def _shared_tensor() -> tensor.SharedTensor:
    return tensor.shared_tensor("float32", (2, 2), layout=_shared_layout())


def _global_tensor() -> tensor.GlobalTensor:
    return tensor.global_tensor("float32", (2, 2), layout=_global_layout())


def _reg_value(name: str = "reg") -> std.Var:
    return std.Var(_reg_tensor(), name)


def _shared_value(name: str = "shared") -> std.Var:
    return std.Var(_shared_tensor(), name)


def _global_value(name: str = "global") -> std.Var:
    return std.Var(_global_tensor(), name)


def _output() -> std.Var:
    return std.Var(_reg_tensor(), "dst")


def _unary_tensor_inst(cls: Callable[..., object]) -> object:
    return cls(_reg_value("src"), output=_output())


def _binary_tensor_inst(cls: Callable[..., object]) -> object:
    return cls(_reg_value("lhs"), _reg_value("rhs"), output=_output())


def _nullary_inst(cls: Callable[..., object]) -> object:
    return cls()


def _atomic_mma_config() -> instructions.AtomicMmaConfig:
    return instructions.AtomicMmaConfig(
        name="mma",
        m=16,
        n=8,
        k=32,
        vec_k=8,
        la=layout.register_row_major(16, 32),
        lb=layout.register_row_major(32, 8),
        lc=layout.register_row_major(16, 8),
        operand_type=tvm_ffi.dtype("float16"),
        acc_type=tvm_ffi.dtype("float32"),
    )


_CATALOG_FACTORIES: dict[str, Callable[[], object]] = {
    "AddInst": lambda: _binary_tensor_inst(instructions.AddInst),
    "AllocBarrierInst": lambda: instructions.AllocBarrierInst(counts=[1, 4]),
    "AnnotateLayoutInst": lambda: instructions.AnnotateLayoutInst(
        _reg_value("src"),
        layout=_reg_layout(),
        output=_output(),
    ),
    "ArriveBarrierInst": lambda: instructions.ArriveBarrierInst(barrier=0, count=1),
    "ArriveExpectTxBarrierInst": lambda: instructions.ArriveExpectTxBarrierInst(
        barrier=0,
        transaction_bytes=16,
    ),
    "ArriveExpectTxMulticastBarrierInst": lambda: instructions.ArriveExpectTxMulticastBarrierInst(
        barrier=0,
        transaction_bytes=16,
        multicast_mask=3,
    ),
    "ArriveExpectTxRemoteBarrierInst": lambda: instructions.ArriveExpectTxRemoteBarrierInst(
        barrier=0,
        transaction_bytes=16,
        target_rank=1,
    ),
    "AssumeInst": lambda: instructions.AssumeInst(condition=True),
    "AtomicGlobalInst": lambda: instructions.AtomicGlobalInst(
        _global_value("ptr"),
        _reg_value("value"),
        op="add",
    ),
    "AtomicMmaConfig": _atomic_mma_config,
    "AtomicScatterGlobalInst": lambda: instructions.AtomicScatterGlobalInst(
        _global_value("ptr"),
        _reg_value("value"),
        op="add",
        dim=1,
    ),
    "AtomicScatterSharedInst": lambda: instructions.AtomicScatterSharedInst(
        _shared_value("ptr"),
        _reg_value("value"),
        op="add",
        dim=1,
    ),
    "AtomicSharedInst": lambda: instructions.AtomicSharedInst(
        _shared_value("ptr"),
        _reg_value("value"),
        op="add",
    ),
    "CastInst": lambda: _unary_tensor_inst(instructions.CastInst),
    "ClusterLaunchControlQueryResponseInst": lambda: _nullary_inst(
        instructions.ClusterLaunchControlQueryResponseInst
    ),
    "ClusterLaunchControlTryCancelInst": lambda: instructions.ClusterLaunchControlTryCancelInst(
        mbarrier=0,
        multicast=1,
    ),
    "ClusterSyncThreadsInst": lambda: _nullary_inst(instructions.ClusterSyncThreadsInst),
    "CopyAsyncBulkCommitGroupInst": lambda: _nullary_inst(
        instructions.CopyAsyncBulkCommitGroupInst
    ),
    "CopyAsyncBulkGlobalToClusterSharedInst": lambda: (
        instructions.CopyAsyncBulkGlobalToClusterSharedInst(
            _global_value("src"),
            _shared_value("dst"),
            offsets=[0, 1],
            dims=[0, 1],
            mbarrier=0,
            cta_mask=3,
            evict="evict_last",
            check_bounds=False,
        )
    ),
    "CopyAsyncBulkGlobalToSharedInst": lambda: instructions.CopyAsyncBulkGlobalToSharedInst(
        _global_value("src"),
        _shared_value("dst"),
        offsets=[0, 1],
        dims=[0, 1],
        mbarrier=0,
        evict="evict_last",
        check_bounds=False,
    ),
    "CopyAsyncBulkSharedToClusterSharedInst": lambda: (
        instructions.CopyAsyncBulkSharedToClusterSharedInst(
            _shared_value("src"),
            _shared_value("dst"),
            mbarrier=0,
            remote_rank=1,
        )
    ),
    "CopyAsyncBulkSharedToGlobalInst": lambda: instructions.CopyAsyncBulkSharedToGlobalInst(
        _shared_value("src"),
        _global_value("dst"),
        offsets=[0, 1],
        dims=[0, 1],
        check_bounds=False,
        l2_evict="evict_last",
    ),
    "CopyAsyncBulkWaitGroupInst": lambda: instructions.CopyAsyncBulkWaitGroupInst(n=1),
    "CopyAsyncCommitGroupInst": lambda: _nullary_inst(instructions.CopyAsyncCommitGroupInst),
    "CopyAsyncGenericInst": lambda: instructions.CopyAsyncGenericInst(
        ptr="ptr",
        axes=["i", "j"],
        offset=4,
        mask=True,
        evict="evict_first",
    ),
    "CopyAsyncInst": lambda: instructions.CopyAsyncInst(
        _global_value("src"),
        _shared_value("dst"),
        offsets=[0, 1],
        dims=[0, 1],
        evict="evict_last",
        check_bounds=False,
    ),
    "CopyAsyncTensorCommitGroupInst": lambda: _nullary_inst(
        instructions.CopyAsyncTensorCommitGroupInst
    ),
    "CopyAsyncTensorGlobalToSharedInst": lambda: instructions.CopyAsyncTensorGlobalToSharedInst(
        _global_value("src"),
        _shared_value("dst"),
        offsets=[0, 1],
        dims=[0, 1],
        mbarrier=0,
        cta_group=1,
        multicast_mask=3,
        cache_policy=5,
    ),
    "CopyAsyncTensorSharedToGlobalInst": lambda: instructions.CopyAsyncTensorSharedToGlobalInst(
        _shared_value("src"),
        _global_value("dst"),
        offsets=[0, 1],
        dims=[0, 1],
        cache_policy=5,
    ),
    "CopyAsyncTensorWaitGroupInst": lambda: instructions.CopyAsyncTensorWaitGroupInst(
        n=1,
        read=True,
    ),
    "CopyAsyncWaitAllInst": lambda: _nullary_inst(instructions.CopyAsyncWaitAllInst),
    "CopyAsyncWaitGroupInst": lambda: instructions.CopyAsyncWaitGroupInst(n=1),
    "DivInst": lambda: _binary_tensor_inst(instructions.DivInst),
    "DotInst": lambda: _binary_tensor_inst(instructions.DotInst),
    "FenceProxyAsync": lambda: instructions.FenceProxyAsync(space="global"),
    "FenceProxyAsyncRelease": lambda: _nullary_inst(instructions.FenceProxyAsyncRelease),
    "LoadGlobalInst": lambda: instructions.LoadGlobalInst(
        _global_value("src"),
        output=_output(),
        offsets=[0, 1],
        dims=[0, 1],
    ),
    "LoadSharedInst": lambda: instructions.LoadSharedInst(
        _shared_value("src"),
        output=_output(),
    ),
    "LockSemaphoreInst": lambda: instructions.LockSemaphoreInst(semaphore=0, value=1),
    "MapSharedAddrInst": lambda: instructions.MapSharedAddrInst(
        _shared_value("src"),
        target_rank=1,
        output=_output(),
    ),
    "MulInst": lambda: _binary_tensor_inst(instructions.MulInst),
    "NopInst": lambda: _nullary_inst(instructions.NopInst),
    "ReduceInst": lambda: instructions.ReduceInst(
        _reg_value("src"),
        output=_output(),
        dim=1,
        op="max",
        keepdim=True,
    ),
    "ReleaseSemaphoreInst": lambda: instructions.ReleaseSemaphoreInst(semaphore=0, value=1),
    "SimtDotInst": lambda: instructions.SimtDotInst(
        _reg_value("lhs"),
        _reg_value("rhs"),
        output=_output(),
        warp_spatial=[1, 1],
        warp_repeat=[1, 1],
        thread_spatial=[1, 1],
        thread_repeat=[1, 1],
    ),
    "StoreGlobalInst": lambda: instructions.StoreGlobalInst(
        _global_value("dst"),
        _reg_value("value"),
        offsets=[0, 1],
        dims=[0, 1],
    ),
    "StoreSharedInst": lambda: instructions.StoreSharedInst(
        _shared_value("dst"),
        _reg_value("value"),
    ),
    "SubInst": lambda: _binary_tensor_inst(instructions.SubInst),
    "SyncThreadsInst": lambda: _nullary_inst(instructions.SyncThreadsInst),
    "Tcgen05AllocInst": lambda: instructions.Tcgen05AllocInst(cta_group=1),
    "Tcgen05CommitInst": lambda: instructions.Tcgen05CommitInst(
        mbarrier=0,
        cta_group=1,
        multicast_mask=3,
    ),
    "Tcgen05CopyInst": lambda: _nullary_inst(instructions.Tcgen05CopyInst),
    "Tcgen05DeallocInst": lambda: _nullary_inst(instructions.Tcgen05DeallocInst),
    "Tcgen05LoadInst": lambda: _nullary_inst(instructions.Tcgen05LoadInst),
    "Tcgen05MmaSSInst": lambda: instructions.Tcgen05MmaSSInst(
        _reg_value("lhs"),
        _reg_value("rhs"),
        output=_output(),
        enable_input_d=True,
        cta_group=1,
    ),
    "Tcgen05MmaTSInst": lambda: instructions.Tcgen05MmaTSInst(
        _reg_value("lhs"),
        _reg_value("rhs"),
        output=_output(),
        enable_input_d=False,
        cta_group=1,
    ),
    "Tcgen05RelinquishAllocPermitInst": lambda: instructions.Tcgen05RelinquishAllocPermitInst(
        cta_group=2
    ),
    "Tcgen05SliceInst": lambda: instructions.Tcgen05SliceInst(
        _reg_value("src"),
        output=_output(),
        offsets=[0, 1],
        slice_dims=[0, 1],
    ),
    "Tcgen05StoreInst": lambda: _nullary_inst(instructions.Tcgen05StoreInst),
    "Tcgen05ViewInst": lambda: _nullary_inst(instructions.Tcgen05ViewInst),
    "Tcgen05WaitInst": lambda: instructions.Tcgen05WaitInst(
        wait_load=True,
        wait_store=False,
    ),
    "WgmmaCommitGroupInst": lambda: _nullary_inst(instructions.WgmmaCommitGroupInst),
    "WgmmaFenceInst": lambda: _nullary_inst(instructions.WgmmaFenceInst),
    "WgmmaMmaRSInst": lambda: _binary_tensor_inst(instructions.WgmmaMmaRSInst),
    "WgmmaMmaSSInst": lambda: _binary_tensor_inst(instructions.WgmmaMmaSSInst),
    "WgmmaWaitGroupInst": lambda: instructions.WgmmaWaitGroupInst(n=1),
    "WaitBarrierInst": lambda: instructions.WaitBarrierInst(barrier=0, phase=1),
}


def test_instruction_catalog_factories_cover_public_exports() -> None:
    assert set(_CATALOG_FACTORIES) == set(instructions.__all__)


def test_instruction_package_exports_all_discovered_modules() -> None:
    discovered: set[str] = set()
    for module_info in pkgutil.walk_packages(
        instructions.__path__,
        prefix=f"{instructions.__name__}.",
    ):
        if module_info.ispkg:
            continue
        module = importlib.import_module(module_info.name)
        for name in getattr(module, "__all__", ()):
            value = getattr(module, name)
            if isinstance(value, type):
                assert getattr(instructions, name) is value
                discovered.add(name)

    assert discovered == set(instructions.__all__)


def test_public_instruction_constructors_cover_exported_mnemonics() -> None:
    for class_name in instructions.__all__:
        cls = getattr(instructions, class_name)
        mnemonic = cls.__ffi_dialect_mnemonic__[1]
        assert mnemonic in tilus.__all__
        constructor = getattr(tilus, mnemonic)

        node = _CATALOG_FACTORIES[class_name]()
        kwargs = {
            field.name: getattr(node, field.name)
            for field in dc.fields(node)
            if field.name is not None
        }
        if issubclass(cls, Instruction):
            operands = [
                getattr(node, field.name)
                for field in dc.fields(node)
                if field.lang_kind == "arg" and field.name is not None
            ]
            for field in dc.fields(node):
                if field.lang_kind == "arg" and field.name is not None:
                    kwargs.pop(field.name, None)
            output = kwargs.pop("output", None)
            if output is not None:
                kwargs["output"] = output
            constructed = constructor(*operands, **kwargs)
        else:
            constructed = constructor(**kwargs)

        assert isinstance(constructed, cls)
        assert tvm_ffi.structural_equal(constructed, node)


@pytest.mark.parametrize("class_name", instructions.__all__)
def test_exported_instruction_round_trip(class_name: str) -> None:
    cls = getattr(instructions, class_name)
    try:
        node = _CATALOG_FACTORIES[class_name]()
    except KeyError:
        pytest.fail(f"missing representative instance for {class_name}")

    assert isinstance(node, cls)
    _round_trip(node)
