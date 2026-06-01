# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Parser integration for the Weave dialect."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, ClassVar

from tvm_ffi import std
from tvm_ffi._pyast_parser import Frame, FuncFrame, register_dialect
from tvm_ffi._std_lang import (
    bind_one_var,
    parse_func_args,
    std_generics,
)

from .ir import config, expr, handles, swizzle, types
from .ir import kernel as kernel_ir
from .ir import task as task_ir
from .ir.ops import atomic, barriers, clc, elementwise, memory, mma


class WeaveFrame(Frame):
    """Base parser frame for Weave body-bearing constructs."""

    dialect = "weave"


class KernelFactory(WeaveFrame, FuncFrame):
    """Parser frame for ``@weave.Kernel`` function definitions."""

    def __init__(self, constants: Any = None, **attrs: Any) -> None:
        if constants is not None:
            attrs.setdefault("constants", constants)
        self.attrs = attrs
        self.symbol = ""
        self.args: list[std.Var] = []
        self.ret_type: std.Ty | None = None
        self.body: list[Any] = []

    def parse_args(self, args: list[tuple[str, Any]]) -> list[std.Var]:
        self.args = parse_func_args(args)
        return self.args

    def to_dialect(self) -> kernel_ir.Kernel:
        return kernel_ir.Kernel(
            symbol=self.symbol,
            args=self.args,
            ret_type=self.ret_type,
            body=self.body,
            **self.attrs,
        )


class TaskSpecFactory(WeaveFrame):
    """Parser frame for ``with weave.TaskSpec(...):``."""

    def __init__(
        self,
        name: str,
        kind: str,
        assigned_role: Any,
        sync_before: Any = (),
        sync_after: Any = (),
        **attrs: Any,
    ) -> None:
        self.name = name
        self.kind = kind
        self.assigned_role = assigned_role
        attrs.setdefault("sync_before", sync_before)
        attrs.setdefault("sync_after", sync_after)
        self.attrs = attrs
        self.body: list[Any] = []

    def to_dialect(self) -> task_ir.TaskSpec:
        return task_ir.TaskSpec(
            self.name,
            self.kind,
            self.assigned_role,
            body=self.body,
            **self.attrs,
        )


class _ScopeFactory(WeaveFrame):
    node_cls: type

    def __init__(self, **attrs: Any) -> None:
        if attrs:
            unexpected = next(iter(attrs))
            raise TypeError(f"unexpected keyword argument: {unexpected}")
        self.body: list[Any] = []

    def to_dialect(self) -> Any:
        return self.node_cls(body=self.body)


class BlockFactory(_ScopeFactory):
    node_cls = task_ir.Block


class LeaderCtaBlockFactory(_ScopeFactory):
    node_cls = task_ir.LeaderCtaBlock


class ElectedThreadBlockFactory(_ScopeFactory):
    node_cls = task_ir.ElectedThreadBlock


class ConditionalIterationFactory(WeaveFrame):
    """Parser frame for ``with weave.ConditionalIteration(...):``."""

    def __init__(self, iter_var: Any, last_expr: Any = None) -> None:
        self.iter_var = iter_var
        self.last_expr = last_expr
        self.body: list[Any] = []

    def to_dialect(self) -> task_ir.ConditionalIteration:
        return task_ir.ConditionalIteration(self.iter_var, last_expr=self.last_expr, body=self.body)


class ForLoopFactory(WeaveFrame):
    """Parser frame for ``for i in weave.ForLoop(...):``."""

    def __init__(
        self,
        extent: Any,
        start: Any = None,
        step_expr: Any = None,
        *,
        step: int | None = None,
        constexpr: bool | None = None,
        unroll: int | None = None,
        ctype: str | None = None,
        ty: Any = None,
    ) -> None:
        self.extent = extent
        self.start = start
        self.step = step
        self.step_expr = step_expr
        self.constexpr = constexpr
        self.unroll = unroll
        self.ctype = ctype
        self.var = std.Var(std.normalize_ty(ty) if ty is not None else std.PrimTy("int32"), "")
        self.body: list[Any] = []

    def bind_names(self, names: Sequence[str]) -> tuple[std.Var, ...]:
        self.var = bind_one_var(
            names,
            self.var.ty,
            error=f"expected one loop variable, got {len(names)}",
        )
        return (self.var,)

    def to_dialect(self) -> task_ir.ForLoop:
        return task_ir.ForLoop(
            extent=self.extent,
            var=self.var,
            body=self.body,
            start=self.start,
            step=self.step,
            step_expr=self.step_expr,
            constexpr=self.constexpr,
            unroll=self.unroll,
            ctype=self.ctype,
        )


class _LmNamespace:
    """Parser and Python namespace that mirrors Loom's ``lm`` types."""

    i8 = types.i8
    i16 = types.i16
    i32 = types.i32
    i64 = types.i64
    u8 = types.u8
    u16 = types.u16
    u32 = types.u32
    u64 = types.u64
    f16 = types.f16
    bf16 = types.bf16
    f32 = types.f32
    f64 = types.f64
    f8_e4m3 = types.f8_e4m3
    f8_e5m2 = types.f8_e5m2
    f8_e8m0fnu = types.f8_e8m0fnu
    f4_e2m1fn = types.f4_e2m1fn
    f32x2 = types.f32x2
    bf16x2 = types.bf16x2
    raw = types.RawTy()
    ue4m3 = types.Ue4m3Ty()
    constexpr = types.ConstexprTy()
    tma2d = types.TmaTy(2)
    tma3d = types.TmaTy(3)
    tma4d = types.TmaTy(4)
    tma5d = types.TmaTy(5)
    tma_gather = types.TmaGatherTy()
    tma_reduce = types.TmaReduceTy()
    grid_counter = types.GridCounterTy()

    @staticmethod
    def ptr(
        elem_ty: std.TyLike | None = None,
        *,
        const: bool = False,
        volatile: bool = False,
        space: str | None = None,
    ) -> types.PtrTy:
        return types.PtrTy(elem_ty, const=const, volatile=volatile, space=space)

    @staticmethod
    def uniform(base: std.TyLike) -> types.UniformTy:
        return types.UniformTy(base)


class WeaveLang:
    """Parser-visible Weave namespace."""

    __ffi_globals__: ClassVar[dict[str, Any]] = {}
    __ffi_generics__: ClassVar[dict[Any, Callable[..., Any]]] = {}

    lm = _LmNamespace()
    Kernel = KernelFactory
    kernel = KernelFactory
    TaskSpec = TaskSpecFactory
    task = TaskSpecFactory
    ForLoop = ForLoopFactory
    Block = BlockFactory
    LeaderCtaBlock = LeaderCtaBlockFactory
    ElectedThreadBlock = ElectedThreadBlockFactory
    ConditionalIteration = ConditionalIterationFactory

    BarrierEdge = config.BarrierEdge
    EpilogueConfig = config.EpilogueConfig
    GridConfig = config.GridConfig
    PipelineConfig = config.PipelineConfig
    PipelineProtocol = config.PipelineProtocol
    Pipeline = config.PipelineSpec
    PipelineSpec = config.PipelineSpec
    SmemAllocation = config.SmemAllocation
    TaskTiming = config.TaskTiming
    TmemAllocation = config.TmemAllocation
    TmemConfig = config.TmemConfig
    WarpConfig = config.WarpConfig
    WarpRole = config.WarpRole

    AddrOf = expr.AddrOf
    BarrierRef = expr.BarrierRef
    BuiltinRef = expr.BuiltinRef
    Const = expr.Const
    ConstexprTy = types.ConstexprTy
    Deref = expr.Deref
    Field = expr.Field
    GridCounterTy = types.GridCounterTy
    PtrTy = types.PtrTy
    RawTy = types.RawTy
    ReinterpretCast = expr.ReinterpretCast
    SmemDescRef = expr.SmemDescRef
    SmemRef = expr.SmemRef
    SmemSwizzleAddress = expr.SmemSwizzleAddress
    SmemSwizzleOffset = expr.SmemSwizzleOffset
    Swizzle = swizzle.Swizzle
    TmaGatherTy = types.TmaGatherTy
    TmaReduceTy = types.TmaReduceTy
    TmaTy = types.TmaTy
    TmemRef = expr.TmemRef
    Ue4m3Ty = types.Ue4m3Ty
    UniformTy = types.UniformTy

    Buffer = handles.BufferRef
    BufferRef = handles.BufferRef
    EpilogueParams = handles.EpilogueParams
    Mbarrier = handles.MbarrierSpec
    MbarrierSpec = handles.MbarrierSpec
    MmaParams = handles.MmaParams
    NamedBarrierSpec = handles.NamedBarrierSpec
    PhaseDomain = handles.PhaseDomain
    PhaseVar = handles.PhaseVar
    ProcessGroup = handles.ProcessGroup
    Param = handles.ScalarParam
    ScalarParam = handles.ScalarParam
    SmemPool = handles.SmemPool
    SmemView = handles.SmemView
    SoftmaxParams = handles.SoftmaxParams
    SymmetricMemory = handles.SymmetricMemory
    TmaDescriptor = handles.TmaDescriptor
    TmaLoadParams = handles.TmaLoadParams
    TmemRegion = handles.TmemRegion

    Assign = task_ir.Assign
    VarDecl = task_ir.VarDecl

    BuiltinVar = memory.BuiltinVar
    TmemRegionLoad = memory.TmemRegionLoad
    TmemRegionStore = memory.TmemRegionStore
    SmemDesc = memory.SmemDesc
    GmemLoad = memory.GmemLoad
    GmemStore = memory.GmemStore
    SmemStore = memory.SmemStore
    SmemLoad = memory.SmemLoad
    SmemRead = memory.SmemRead
    SmemLoadRegs = memory.SmemLoadRegs
    SmemWrite = memory.SmemWrite
    SmemLoadVec = memory.SmemLoadVec
    SmemStoreVec = memory.SmemStoreVec
    TmaStore = memory.TmaStore
    TmaReduceOp = memory.TmaReduceOp
    TmaGatherLoad = memory.TmaGatherLoad
    ScaleFactorCopy = memory.ScaleFactorCopy
    MetadataCopy = memory.MetadataCopy

    Elementwise = elementwise.Elementwise
    PredicatedStore = elementwise.PredicatedStore
    ThreshMask = elementwise.ThreshMask
    BitmaskFill = elementwise.BitmaskFill
    MaskFill = elementwise.MaskFill
    RegArrayCast = elementwise.RegArrayCast

    BarrierSync = barriers.BarrierSync
    BarrierTryWait = barriers.BarrierTryWait
    BarrierWait = barriers.BarrierWait
    BarrierSignal = barriers.BarrierSignal
    MBarrierArrive = barriers.MBarrierArrive
    PeerArriveCommit = barriers.PeerArriveCommit
    MulticastCommit = barriers.MulticastCommit
    DualCommit = barriers.DualCommit
    Fence = barriers.Fence
    ThreadFence = barriers.ThreadFence
    ClusterSync = barriers.ClusterSync
    GridSync = barriers.GridSync
    GridDepSync = barriers.GridDepSync
    GridDepLaunch = barriers.GridDepLaunch
    ClusterMapa = barriers.ClusterMapa
    ClusterBarrierArrive = barriers.ClusterBarrierArrive
    CpAsyncBulkSmem2SmemCluster = barriers.CpAsyncBulkSmem2SmemCluster
    WarpReduce = barriers.WarpReduce
    BlockReduce = barriers.BlockReduce
    CrossWarpReduce = barriers.CrossWarpReduce
    WarpGroupReduce = barriers.WarpGroupReduce
    StAsync = barriers.StAsync

    Tcgen05Cp = mma.Tcgen05Cp
    PackedF32x2 = mma.PackedF32x2
    FragmentOp = mma.FragmentOp
    MmaTile = mma.MmaTile

    AtomicOp = atomic.AtomicOp
    AtomicFetchAdd = atomic.AtomicFetchAdd
    RelaxedFmax = atomic.RelaxedFmax
    AtomicMaxF32Positive = atomic.AtomicMaxF32Positive
    SysVolatileLoad128 = atomic.SysVolatileLoad128
    SysVolatileStore128 = atomic.SysVolatileStore128
    MultimemLdReduce = atomic.MultimemLdReduce
    MultimemStore = atomic.MultimemStore
    MultimemRedAddI32 = atomic.MultimemRedAddI32
    AtomicMaxFloatEncode = atomic.AtomicMaxFloatEncode
    AtomicMaxFloatDecode = atomic.AtomicMaxFloatDecode

    ClcTryCancel = clc.ClcTryCancel
    ClcQueryCancel = clc.ClcQueryCancel
    ClcQueryCancelGetCtaId = clc.ClcQueryCancelGetCtaId
    ClcFenceRelease = clc.ClcFenceRelease


WeaveLang.__ffi_globals__ = {"lm": WeaveLang.lm}
WeaveLang.__ffi_generics__ = std_generics()

register_dialect("weave", WeaveLang)


__all__ = ["WeaveLang"]
