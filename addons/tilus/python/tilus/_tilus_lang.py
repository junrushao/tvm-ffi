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
"""Parser integration for the Tilus dialect."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any, ClassVar

from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi._pyast_parser import Factory, Frame, FuncFrame, register_dialect
from tvm_ffi._std_lang import (
    Std,
    bind_one_var,
    parse_func_args,
    std_generics,
)
from tvm_ffi.core import MISSING

from .ir import func, inst, instructions, layout, stmt, tensor


class TilusFrame(Frame):
    """Base parser frame for Tilus body-bearing constructs."""

    dialect = "tilus"


class ThreadGroupFactory(TilusFrame):
    """Parser frame for ``with tilus.ThreadGroup(...):``."""

    def __init__(self, thread_begin: int, num_threads: int) -> None:
        self.thread_begin = thread_begin
        self.num_threads = num_threads
        self.body: list[Any] = []

    def to_dialect(self) -> stmt.ThreadGroup:
        return stmt.ThreadGroup(self.thread_begin, self.num_threads, self.body)


class FunctionFactory(TilusFrame, FuncFrame):
    """Parser frame for ``@tilus.Function`` definitions."""

    def __init__(self, metadata: func.Metadata | None = None) -> None:
        self.symbol = ""
        self.args: list[std.Var] = []
        self.ret_type: std.Ty | None = None
        self.body: list[Any] = []
        self.metadata = metadata

    def parse_args(self, args: list[tuple[str, Any]]) -> list[std.Var]:
        self.args = parse_func_args(args)
        return self.args

    def to_dialect(self) -> func.Function:
        return func.Function(
            symbol=self.symbol,
            args=self.args,
            ret_type=self.ret_type,
            body=self.body,
            metadata=self.metadata,
        )


class InstructionFactory(Factory):
    """Parser-visible constructor for Tilus instructions."""

    dialect = "tilus"

    def __init__(self, cls: type[inst.Instruction]) -> None:
        self.cls = cls

    def __call__(
        self,
        *operands: Any,
        output: std.Var | None = None,
        **attrs: Any,
    ) -> inst.Instruction:
        return _make_instruction(self.cls, *operands, output=output, **attrs)


@dataclass(frozen=True)
class _TensorItemBuilder:
    __ffi_dialect_mnemonic__: ClassVar[tuple[str, str]] = ("tilus", "TensorItemBuilder")

    cls: type
    tensor_value: tensor.Tensor
    space: str | None = None

    def __ffi_scope_bind__(self) -> std.Stmt:
        """Build a placeholder tensor-item binding for ``std.scope(... ) as``."""
        var = std.Var(self.tensor_value, "")
        if self.cls is stmt.TensorItemPtr:
            return stmt.TensorItemPtr(self.tensor_value, var, self.space)
        return stmt.TensorItemValue(self.tensor_value, var)


def _make_tensor(
    cls: type[tensor.Tensor],
    dtype: std.TyLike,
    shape_args: tuple[Any, ...],
    layout_value: layout.Layout | None,
) -> tensor.Tensor:
    return cls(
        tensor._prim_ty(dtype),
        shape=tensor._shape(shape_args),
        optional_layout=layout_value,
    )


def _make_instruction(
    cls: type[inst.Instruction],
    *operands: Any,
    output: std.Var | None = None,
    **attrs: Any,
) -> inst.Instruction:
    if "inputs" in attrs:
        raise TypeError(
            f"{cls.__name__} operands must be passed positionally; "
            "`inputs` keyword is not supported"
        )
    ty = attrs.pop("ty", MISSING)
    instruction = cls(inputs=list(operands), output=output, **attrs)
    if not MISSING.is_(ty):
        inst.validate_instruction_ty_hint(instruction, ty)
    return instruction


def _bind_expr(names: Sequence[str], ty: Any, expr: Any) -> Any:
    if isinstance(expr, inst.Instruction):
        if expr.output is not None:
            raise TypeError("instruction RHS must not already define an output")
        explicit_ty = inst.pop_instruction_ty_hint(expr)
        if ty is None:
            ty = explicit_ty or inst.infer_instruction_output_ty(expr)
        if ty is None:
            raise TypeError("instruction assignment requires an inferable output type")
        bound = dc.replace(expr, output=bind_one_var(names, ty))
        bound.__post_init__()
        if explicit_ty is not None:
            inst.validate_instruction_output_ty(bound, explicit_ty)
        return bound
    if isinstance(expr, _TensorItemBuilder):
        bind_ty = ty if ty is not None else expr.tensor_value
        var = bind_one_var(names, bind_ty)
        if expr.cls is stmt.TensorItemPtr:
            return stmt.TensorItemPtr(expr.tensor_value, var, expr.space)
        return stmt.TensorItemValue(expr.tensor_value, var)
    return Std.__ffi_generics__["__bind_expr__"](names, ty, expr)


class TilusLang:
    """Parser-visible Tilus language namespace."""

    __ffi_globals__: ClassVar[dict[str, Any]] = {}
    __ffi_generics__: ClassVar[dict[Any, Callable[..., Any]]] = {}

    Swizzle = layout.Swizzle

    @staticmethod
    def RegisterLayout(
        *shape_args: Any,
        mode_shape: Any = None,
        spatial_modes: Any = None,
        local_modes: Any = None,
    ) -> layout.RegisterLayout:
        return layout.register_layout(
            shape_args,
            mode_shape=mode_shape,
            spatial_modes=spatial_modes,
            local_modes=local_modes,
        )

    @staticmethod
    def SharedLayout(
        *shape_args: Any,
        mode_shape: Any = None,
        mode_strides: Any = None,
        optional_swizzle: layout.Swizzle | None = None,
    ) -> layout.SharedLayout:
        return layout.shared_layout(
            shape_args,
            mode_shape=mode_shape,
            mode_strides=mode_strides,
            optional_swizzle=optional_swizzle,
        )

    @staticmethod
    def GlobalLayout(
        *shape_args: Any,
        size: Any = None,
        axes: Any = None,
        offset: Any = 0,
    ) -> layout.GlobalLayout:
        shape_tuple = tuple(shape_args)
        if axes is None:
            axes = tuple(f"i{axis}" for axis in range(len(shape_tuple)))
        else:
            for axis in axes:
                if not isinstance(axis, str):
                    raise TypeError(f"axes entries must be strings, got {axis!r}")
        if size is None:
            size = layout.prod(shape_tuple)
        return layout.GlobalLayout(
            shape=tuple(
                layout._integer_expr(extent, "shape extent", positive=True)
                for extent in shape_tuple
            ),
            size=layout._integer_expr(size, "size"),
            axes=tuple(axes),
            offset=layout._integer_expr(offset, "offset"),
        )

    @staticmethod
    def TMemoryLayout(
        *shape_args: Any,
        column_strides: Any = None,
        lane_offset: Any = 0,
    ) -> layout.TMemoryLayout:
        shape = tuple(shape_args)
        if column_strides is None and lane_offset == 0:
            return layout.tmemory_layout(shape)
        return layout.TMemoryLayout(
            shape=layout._shape(shape),
            column_strides=layout._tuple(column_strides or ()),
            lane_offset=layout._strict_int(lane_offset, "lane_offset"),
        )

    @staticmethod
    def RegTensor(
        dtype: std.TyLike,
        *shape_args: Any,
        layout: layout.Layout | None = None,
    ) -> tensor.RegisterTensor:
        return _make_tensor(
            tensor.RegisterTensor,
            dtype,
            shape_args,
            layout,
        )

    RegisterTensor = RegTensor

    @staticmethod
    def SharedTensor(
        dtype: std.TyLike,
        *shape_args: Any,
        layout: layout.Layout | None = None,
    ) -> tensor.SharedTensor:
        return _make_tensor(
            tensor.SharedTensor,
            dtype,
            shape_args,
            layout,
        )

    @staticmethod
    def GlobalTensor(
        dtype: std.TyLike,
        *shape_args: Any,
        layout: layout.Layout | None = None,
    ) -> tensor.GlobalTensor:
        return _make_tensor(
            tensor.GlobalTensor,
            dtype,
            shape_args,
            layout,
        )

    @staticmethod
    def TMemoryTensor(
        dtype: std.TyLike,
        *shape_args: Any,
        layout: layout.Layout | None = None,
    ) -> tensor.TMemoryTensor:
        return _make_tensor(
            tensor.TMemoryTensor,
            dtype,
            shape_args,
            layout,
        )

    ThreadGroup = ThreadGroupFactory
    thread_group = ThreadGroupFactory
    Function = FunctionFactory
    function = FunctionFactory
    Metadata = func.Metadata
    Analysis = func.Analysis

    Eval = stmt.Evaluate
    Inst = stmt.InstStmt

    @staticmethod
    def TensorItemPtr(
        tensor_value: tensor.Tensor,
        space: str | None = None,
    ) -> _TensorItemBuilder:
        return _TensorItemBuilder(stmt.TensorItemPtr, tensor_value, space)

    @staticmethod
    def TensorItemValue(tensor_value: tensor.Tensor) -> _TensorItemBuilder:
        return _TensorItemBuilder(stmt.TensorItemValue, tensor_value)

    AtomicShared = partial(_make_instruction, instructions.AtomicSharedInst)
    AtomicGlobal = partial(_make_instruction, instructions.AtomicGlobalInst)
    AtomicScatterShared = partial(_make_instruction, instructions.AtomicScatterSharedInst)
    AtomicScatterGlobal = partial(_make_instruction, instructions.AtomicScatterGlobalInst)
    ClcTryCancel = partial(_make_instruction, instructions.ClusterLaunchControlTryCancelInst)
    ClcQueryResponse = partial(
        _make_instruction, instructions.ClusterLaunchControlQueryResponseInst
    )
    ClusterSyncThreads = partial(_make_instruction, instructions.ClusterSyncThreadsInst)
    CopyAsync = partial(_make_instruction, instructions.CopyAsyncInst)
    CopyAsyncGeneric = partial(_make_instruction, instructions.CopyAsyncGenericInst)
    CopyAsyncCommitGroup = partial(_make_instruction, instructions.CopyAsyncCommitGroupInst)
    CopyAsyncWaitGroup = partial(_make_instruction, instructions.CopyAsyncWaitGroupInst)
    CopyAsyncWaitAll = partial(_make_instruction, instructions.CopyAsyncWaitAllInst)
    CopyAsyncBulkGlobalToShared = partial(
        _make_instruction, instructions.CopyAsyncBulkGlobalToSharedInst
    )
    CopyAsyncBulkGlobalToClusterShared = partial(
        _make_instruction, instructions.CopyAsyncBulkGlobalToClusterSharedInst
    )
    CopyAsyncBulkSharedToGlobal = partial(
        _make_instruction, instructions.CopyAsyncBulkSharedToGlobalInst
    )
    CopyAsyncBulkSharedToClusterShared = partial(
        _make_instruction, instructions.CopyAsyncBulkSharedToClusterSharedInst
    )
    CopyAsyncBulkCommitGroup = partial(_make_instruction, instructions.CopyAsyncBulkCommitGroupInst)
    CopyAsyncBulkWaitGroup = partial(_make_instruction, instructions.CopyAsyncBulkWaitGroupInst)
    CopyAsyncTensorGlobalToShared = partial(
        _make_instruction, instructions.CopyAsyncTensorGlobalToSharedInst
    )
    CopyAsyncTensorSharedToGlobal = partial(
        _make_instruction, instructions.CopyAsyncTensorSharedToGlobalInst
    )
    CopyAsyncTensorCommitGroup = partial(
        _make_instruction, instructions.CopyAsyncTensorCommitGroupInst
    )
    CopyAsyncTensorWaitGroup = partial(_make_instruction, instructions.CopyAsyncTensorWaitGroupInst)
    FenceProxyAsync = partial(_make_instruction, instructions.FenceProxyAsync)
    FenceProxyAsyncRelease = partial(_make_instruction, instructions.FenceProxyAsyncRelease)
    MapSharedAddr = partial(_make_instruction, instructions.MapSharedAddrInst)
    AllocBarrier = partial(_make_instruction, instructions.AllocBarrierInst)
    ArriveBarrier = partial(_make_instruction, instructions.ArriveBarrierInst)
    ArriveExpectTxBarrier = partial(_make_instruction, instructions.ArriveExpectTxBarrierInst)
    WaitBarrier = partial(_make_instruction, instructions.WaitBarrierInst)
    ArriveExpectTxMulticastBarrier = partial(
        _make_instruction, instructions.ArriveExpectTxMulticastBarrierInst
    )
    ArriveExpectTxRemoteBarrier = partial(
        _make_instruction, instructions.ArriveExpectTxRemoteBarrierInst
    )
    Dot = partial(_make_instruction, instructions.DotInst)
    AtomicMmaConfig = instructions.AtomicMmaConfig
    LockSemaphore = partial(_make_instruction, instructions.LockSemaphoreInst)
    ReleaseSemaphore = partial(_make_instruction, instructions.ReleaseSemaphoreInst)
    SimtDot = partial(_make_instruction, instructions.SimtDotInst)
    Tcgen05Alloc = partial(_make_instruction, instructions.Tcgen05AllocInst)
    Tcgen05Dealloc = partial(_make_instruction, instructions.Tcgen05DeallocInst)
    Tcgen05RelinquishAllocPermit = partial(
        _make_instruction, instructions.Tcgen05RelinquishAllocPermitInst
    )
    Tcgen05Slice = partial(_make_instruction, instructions.Tcgen05SliceInst)
    Tcgen05View = partial(_make_instruction, instructions.Tcgen05ViewInst)
    Tcgen05Load = partial(_make_instruction, instructions.Tcgen05LoadInst)
    Tcgen05Store = partial(_make_instruction, instructions.Tcgen05StoreInst)
    Tcgen05Wait = partial(_make_instruction, instructions.Tcgen05WaitInst)
    Tcgen05Copy = partial(_make_instruction, instructions.Tcgen05CopyInst)
    Tcgen05Commit = partial(_make_instruction, instructions.Tcgen05CommitInst)
    Tcgen05MmaSS = partial(_make_instruction, instructions.Tcgen05MmaSSInst)
    Tcgen05MmaTS = partial(_make_instruction, instructions.Tcgen05MmaTSInst)
    WgmmaFence = partial(_make_instruction, instructions.WgmmaFenceInst)
    WgmmaCommitGroup = partial(_make_instruction, instructions.WgmmaCommitGroupInst)
    WgmmaWaitGroup = partial(_make_instruction, instructions.WgmmaWaitGroupInst)
    WgmmaMmaSS = partial(_make_instruction, instructions.WgmmaMmaSSInst)
    WgmmaMmaRS = partial(_make_instruction, instructions.WgmmaMmaRSInst)
    Add = partial(_make_instruction, instructions.AddInst)
    Cast = partial(_make_instruction, instructions.CastInst)
    Div = partial(_make_instruction, instructions.DivInst)
    LoadGlobal = InstructionFactory(instructions.LoadGlobalInst)
    LoadShared = InstructionFactory(instructions.LoadSharedInst)
    Mul = partial(_make_instruction, instructions.MulInst)
    Nop = partial(_make_instruction, instructions.NopInst)
    Reduce = partial(_make_instruction, instructions.ReduceInst)
    StoreGlobal = partial(_make_instruction, instructions.StoreGlobalInst)
    StoreShared = partial(_make_instruction, instructions.StoreSharedInst)
    Sub = partial(_make_instruction, instructions.SubInst)
    SyncThreads = partial(_make_instruction, instructions.SyncThreadsInst)
    AnnotateLayout = partial(_make_instruction, instructions.AnnotateLayoutInst)
    Assume = partial(_make_instruction, instructions.AssumeInst)


TilusLang.__ffi_globals__ = {
    "thread_group": TilusLang.thread_group,
    "register_tensor": tensor.register_tensor,
    "shared_tensor": tensor.shared_tensor,
    "global_tensor": tensor.global_tensor,
    "tmemory_tensor": tensor.tmemory_tensor,
}

TilusLang.__ffi_generics__ = std_generics({"__bind_expr__": _bind_expr})

register_dialect("tilus", TilusLang)


__all__ = ["TilusLang"]
