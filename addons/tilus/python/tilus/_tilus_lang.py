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
from typing import Any, ClassVar, TypeVar, cast

from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi._pyast_parser import Frame, FuncFrame, register_dialect
from tvm_ffi._std_lang import (
    Std,
    bind_one_var,
    parse_func_args,
    std_generics,
)

from .ir import func, inst, instructions, layout, stmt, tensor

_TensorT = TypeVar("_TensorT", bound=tensor.Tensor)


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


@dataclass(frozen=True)
class _TensorItemBuilder:
    __ffi_dialect_mnemonic__: ClassVar[tuple[str, str]] = ("tilus", "TensorItemBuilder")

    cls: type
    tensor_value: tensor.Tensor

    def __ffi_scope_bind__(self) -> std.Stmt:
        """Build a placeholder tensor-item binding for ``std.scope(... ) as``."""
        var = std.Var(self.tensor_value, "")
        if self.cls is stmt.TensorItemPtr:
            return stmt.TensorItemPtr(var)
        return stmt.TensorItemValue(var)


def _make_tensor(
    cls: type[_TensorT],
    dtype: std.TyLike | None,
    shape_args: tuple[Any, ...],
    layout_value: layout.Layout | None,
    *,
    shape: Any = None,
    optional_layout: layout.Layout | None = None,
) -> _TensorT:
    if dtype is None:
        raise TypeError("missing required argument 'dtype'")
    if shape is not None:
        if shape_args:
            raise TypeError("tensor shape supplied both positionally and by keyword")
        shape_args = tuple(shape)
    if optional_layout is not None:
        if layout_value is not None:
            raise TypeError("tensor layout supplied both as layout and optional_layout")
        layout_value = optional_layout
    return cast(Any, cls)(
        tensor._prim_ty(dtype),
        shape=tensor._shape(shape_args),
        optional_layout=layout_value,
    )


def _bind_expr(names: Sequence[str], ty: Any, expr: Any) -> Any:
    if isinstance(expr, inst.Instruction):
        if any(output.name for output in expr.outputs()):
            raise TypeError("instruction RHS must not already define an output")
        if ty is not None:
            raise TypeError(
                "constructor out assignment does not support type annotations; "
                "pass type information to the constructor"
            )
        bound = dc.replace(expr)
        bound.__ffi_update_var_name__(*names)
        return bound
    if isinstance(expr, _TensorItemBuilder):
        bind_ty = ty if ty is not None else expr.tensor_value
        var = bind_one_var(names, bind_ty)
        if expr.cls is stmt.TensorItemPtr:
            return stmt.TensorItemPtr(var)
        return stmt.TensorItemValue(var)
    return Std.__ffi_generics__["__bind_expr__"](names, ty, expr)


class TilusLang:
    """Parser-visible Tilus language namespace."""

    __ffi_globals__: ClassVar[dict[str, Any]] = {}
    __ffi_generics__: ClassVar[dict[Any, Callable[..., Any]]] = {}

    Swizzle = layout.Swizzle

    @staticmethod
    def RegisterLayout(
        *shape_args: Any,
        shape: Any = None,
        mode_shape: Any = None,
        spatial_modes: Any = None,
        local_modes: Any = None,
    ) -> layout.RegisterLayout:
        if shape is not None:
            if shape_args:
                raise TypeError("RegisterLayout shape supplied both positionally and by keyword")
            shape_args = tuple(shape)
        return layout.register_layout(
            shape_args,
            mode_shape=mode_shape,
            spatial_modes=spatial_modes,
            local_modes=local_modes,
        )

    @staticmethod
    def SharedLayout(
        *shape_args: Any,
        shape: Any = None,
        mode_shape: Any = None,
        mode_strides: Any = None,
        optional_swizzle: layout.Swizzle | None = None,
    ) -> layout.SharedLayout:
        if shape is not None:
            if shape_args:
                raise TypeError("SharedLayout shape supplied both positionally and by keyword")
            shape_args = tuple(shape)
        return layout.shared_layout(
            shape_args,
            mode_shape=mode_shape,
            mode_strides=mode_strides,
            optional_swizzle=optional_swizzle,
        )

    @staticmethod
    def GlobalLayout(
        *shape_args: Any,
        shape: Any = None,
        size: Any = None,
        axes: Any = None,
        offset: Any = 0,
    ) -> layout.GlobalLayout:
        if shape is not None:
            if shape_args:
                raise TypeError("GlobalLayout shape supplied both positionally and by keyword")
            shape_args = (shape,)
        if shape_args and isinstance(shape_args[0], (list, tuple)):
            if len(shape_args) > 3:
                raise TypeError("GlobalLayout accepts at most shape, size, and offset")
            shape_tuple = tuple(shape_args[0])
            if len(shape_args) >= 2:
                if size is not None:
                    raise TypeError("GlobalLayout size supplied both positionally and by keyword")
                size = shape_args[1]
            if len(shape_args) >= 3:
                if offset != 0:
                    raise TypeError("GlobalLayout offset supplied both positionally and by keyword")
                offset = shape_args[2]
        else:
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
        shape: Any = None,
        column_strides: Any = None,
        lane_offset: Any = 0,
    ) -> layout.TMemoryLayout:
        if shape is not None:
            if shape_args:
                raise TypeError("TMemoryLayout shape supplied both positionally and by keyword")
            shape_args = tuple(shape)
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
        dtype: std.TyLike | None = None,
        *shape_args: Any,
        layout: layout.Layout | None = None,
        optional_layout: layout.Layout | None = None,
        shape: Any = None,
    ) -> tensor.RegisterTensor:
        return _make_tensor(
            tensor.RegisterTensor,
            dtype,
            shape_args,
            layout,
            shape=shape,
            optional_layout=optional_layout,
        )

    RegisterTensor = RegTensor

    @staticmethod
    def SharedTensor(
        dtype: std.TyLike | None = None,
        *shape_args: Any,
        layout: layout.Layout | None = None,
        optional_layout: layout.Layout | None = None,
        shape: Any = None,
    ) -> tensor.SharedTensor:
        return _make_tensor(
            tensor.SharedTensor,
            dtype,
            shape_args,
            layout,
            shape=shape,
            optional_layout=optional_layout,
        )

    @staticmethod
    def GlobalTensor(
        dtype: std.TyLike | None = None,
        *shape_args: Any,
        layout: layout.Layout | None = None,
        optional_layout: layout.Layout | None = None,
        shape: Any = None,
    ) -> tensor.GlobalTensor:
        return _make_tensor(
            tensor.GlobalTensor,
            dtype,
            shape_args,
            layout,
            shape=shape,
            optional_layout=optional_layout,
        )

    @staticmethod
    def TMemoryTensor(
        dtype: std.TyLike | None = None,
        *shape_args: Any,
        layout: layout.Layout | None = None,
        optional_layout: layout.Layout | None = None,
        shape: Any = None,
    ) -> tensor.TMemoryTensor:
        return _make_tensor(
            tensor.TMemoryTensor,
            dtype,
            shape_args,
            layout,
            shape=shape,
            optional_layout=optional_layout,
        )

    ThreadGroup = ThreadGroupFactory
    thread_group = ThreadGroupFactory
    Function = FunctionFactory
    function = FunctionFactory
    Metadata = func.Metadata
    Analysis = func.Analysis

    Eval = stmt.Evaluate

    @staticmethod
    def TensorItemPtr(
        tensor_value: tensor.Tensor | None = None,
        *,
        ty: tensor.Tensor | None = None,
    ) -> _TensorItemBuilder:
        if ty is not None:
            if tensor_value is not None:
                raise TypeError("TensorItemPtr type supplied both positionally and by keyword")
            tensor_value = ty
        if tensor_value is None:
            raise TypeError("missing required tensor type")
        return _TensorItemBuilder(stmt.TensorItemPtr, tensor_value)

    @staticmethod
    def TensorItemValue(
        tensor_value: tensor.Tensor | None = None,
        *,
        ty: tensor.Tensor | None = None,
    ) -> _TensorItemBuilder:
        if ty is not None:
            if tensor_value is not None:
                raise TypeError("TensorItemValue type supplied both positionally and by keyword")
            tensor_value = ty
        if tensor_value is None:
            raise TypeError("missing required tensor type")
        return _TensorItemBuilder(stmt.TensorItemValue, tensor_value)

    AtomicShared = instructions.AtomicSharedInst
    AtomicGlobal = instructions.AtomicGlobalInst
    AtomicScatterShared = instructions.AtomicScatterSharedInst
    AtomicScatterGlobal = instructions.AtomicScatterGlobalInst
    ClcTryCancel = instructions.ClusterLaunchControlTryCancelInst
    ClcQueryResponse = instructions.ClusterLaunchControlQueryResponseInst
    ClusterSyncThreads = instructions.ClusterSyncThreadsInst
    CopyAsync = instructions.CopyAsyncInst
    CopyAsyncGeneric = instructions.CopyAsyncGenericInst
    CopyAsyncCommitGroup = instructions.CopyAsyncCommitGroupInst
    CopyAsyncWaitGroup = instructions.CopyAsyncWaitGroupInst
    CopyAsyncWaitAll = instructions.CopyAsyncWaitAllInst
    CopyAsyncBulkGlobalToShared = instructions.CopyAsyncBulkGlobalToSharedInst
    CopyAsyncBulkGlobalToClusterShared = instructions.CopyAsyncBulkGlobalToClusterSharedInst
    CopyAsyncBulkSharedToGlobal = instructions.CopyAsyncBulkSharedToGlobalInst
    CopyAsyncBulkSharedToClusterShared = instructions.CopyAsyncBulkSharedToClusterSharedInst
    CopyAsyncBulkCommitGroup = instructions.CopyAsyncBulkCommitGroupInst
    CopyAsyncBulkWaitGroup = instructions.CopyAsyncBulkWaitGroupInst
    CopyAsyncTensorGlobalToShared = instructions.CopyAsyncTensorGlobalToSharedInst
    CopyAsyncTensorSharedToGlobal = instructions.CopyAsyncTensorSharedToGlobalInst
    CopyAsyncTensorCommitGroup = instructions.CopyAsyncTensorCommitGroupInst
    CopyAsyncTensorWaitGroup = instructions.CopyAsyncTensorWaitGroupInst
    FenceProxyAsync = instructions.FenceProxyAsync
    FenceProxyAsyncRelease = instructions.FenceProxyAsyncRelease
    MapSharedAddr = instructions.MapSharedAddrInst
    AllocBarrier = instructions.AllocBarrierInst
    ArriveBarrier = instructions.ArriveBarrierInst
    ArriveExpectTxBarrier = instructions.ArriveExpectTxBarrierInst
    WaitBarrier = instructions.WaitBarrierInst
    ArriveExpectTxMulticastBarrier = instructions.ArriveExpectTxMulticastBarrierInst
    ArriveExpectTxRemoteBarrier = instructions.ArriveExpectTxRemoteBarrierInst
    Dot = instructions.DotInst
    AtomicMmaConfig = instructions.AtomicMmaConfig
    LockSemaphore = instructions.LockSemaphoreInst
    ReleaseSemaphore = instructions.ReleaseSemaphoreInst
    SimtDot = instructions.SimtDotInst
    Tcgen05Alloc = instructions.Tcgen05AllocInst
    Tcgen05Dealloc = instructions.Tcgen05DeallocInst
    Tcgen05RelinquishAllocPermit = instructions.Tcgen05RelinquishAllocPermitInst
    Tcgen05Slice = instructions.Tcgen05SliceInst
    Tcgen05View = instructions.Tcgen05ViewInst
    Tcgen05Load = instructions.Tcgen05LoadInst
    Tcgen05Store = instructions.Tcgen05StoreInst
    Tcgen05Wait = instructions.Tcgen05WaitInst
    Tcgen05Copy = instructions.Tcgen05CopyInst
    Tcgen05Commit = instructions.Tcgen05CommitInst
    Tcgen05MmaSS = instructions.Tcgen05MmaSSInst
    Tcgen05MmaTS = instructions.Tcgen05MmaTSInst
    WgmmaFence = instructions.WgmmaFenceInst
    WgmmaCommitGroup = instructions.WgmmaCommitGroupInst
    WgmmaWaitGroup = instructions.WgmmaWaitGroupInst
    WgmmaMmaSS = instructions.WgmmaMmaSSInst
    WgmmaMmaRS = instructions.WgmmaMmaRSInst
    Add = instructions.AddInst
    Cast = instructions.CastInst
    Div = instructions.DivInst
    LoadGlobal = instructions.LoadGlobalInst
    LoadShared = instructions.LoadSharedInst
    Mul = instructions.MulInst
    Nop = instructions.NopInst
    Reduce = instructions.ReduceInst
    StoreGlobal = instructions.StoreGlobalInst
    StoreShared = instructions.StoreSharedInst
    Sub = instructions.SubInst
    SyncThreads = instructions.SyncThreadsInst
    AnnotateLayout = instructions.AnnotateLayoutInst
    Assume = instructions.AssumeInst


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
