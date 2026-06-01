# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Barrier, fence, synchronization, and reduction operation nodes."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from .._utils import (
    Op,
    OutputOp,
    normalize_domain,
    validate_cta_group,
    var_with_ty_hint,
)
from ..handles import MbarrierSpec

SIGNAL_ACTIONS = ("arrive", "arrive_expect_tx", "commit")
FENCE_KINDS = ("after_thread_sync", "before_thread_sync")
THREAD_FENCE_SCOPES = ("block", "device", "system")
REDUCE_OPS = ("add", "max", "min")
FINALIZE_MODES = ("none", "rsqrt")


def _check_mbarrier(value: MbarrierSpec, field_name: str) -> None:
    if not isinstance(value, MbarrierSpec):
        raise TypeError(f"{field_name} expects MbarrierSpec, got {type(value).__name__}")


@dc.py_class("weave.BarrierSync", structural_eq="tree")
class BarrierSync(Op, mnemonic="weave.BarrierSync"):
    barrier_id: int = dc.field(default=0, lang_kind="attr")


@dc.py_class("weave.BarrierTryWait", structural_eq="tree")
class BarrierTryWait(OutputOp, mnemonic="weave.BarrierTryWait"):
    stage: std.Expr = dc.field(lang_kind="arg")
    phase: std.Expr = dc.field(lang_kind="arg")
    dst: std.Var = dc.field(lang_kind="out", structural_eq="def-recursive")
    stage_is_deterministic: bool = dc.field(default=True, lang_kind="attr")
    barrier: MbarrierSpec = dc.field(kw_only=True, lang_kind="attr")

    def __init__(
        self,
        stage: std.Expr,
        phase: std.Expr,
        dst: std.Var | None = None,
        stage_is_deterministic: bool = True,
        *,
        barrier: MbarrierSpec,
        ty: std.TyLike | None = None,
    ) -> None:
        self.__ffi_init__(
            stage=stage,
            phase=phase,
            dst=var_with_ty_hint(dst, ty, field_name="dst"),
            stage_is_deterministic=stage_is_deterministic,
            barrier=barrier,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        _check_mbarrier(self.barrier, "barrier")

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        self.dst.name = name[0]
        self.__post_init__()
        return (self.dst,)


@dc.py_class("weave.BarrierWait", structural_eq="tree")
class BarrierWait(Op, mnemonic="weave.BarrierWait"):
    stage: std.Expr = dc.field(lang_kind="arg")
    phase: std.Expr = dc.field(lang_kind="arg")
    token: std.Expr | None = dc.field(default=None, lang_kind="arg")
    stage_is_deterministic: bool = dc.field(default=True, lang_kind="attr")
    barrier: MbarrierSpec = dc.field(kw_only=True, lang_kind="attr")

    def __post_init__(self) -> None:
        _check_mbarrier(self.barrier, "barrier")


@dc.py_class("weave.BarrierSignal", structural_eq="tree")
class BarrierSignal(Op, mnemonic="weave.BarrierSignal"):
    stage: std.Expr = dc.field(lang_kind="arg")
    tx_bytes: std.Expr | None = dc.field(default=None, lang_kind="arg")
    arrive_count: std.Expr | None = dc.field(default=None, lang_kind="arg")
    action: str = dc.field(kw_only=True, lang_kind="attr")
    barrier: MbarrierSpec = dc.field(kw_only=True, lang_kind="attr")
    cta_group: int = dc.field(default=1, lang_kind="attr")
    cluster: bool = dc.field(default=False, lang_kind="attr")
    stage_is_deterministic: bool = dc.field(default=True, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")
    transaction_group: str = dc.field(default="", lang_kind="attr")

    def __init__(
        self,
        stage: std.Expr,
        tx_bytes: std.Expr | None = None,
        arrive_count: std.Expr | None = None,
        *,
        action: str,
        barrier: MbarrierSpec,
        cta_group: int = 1,
        cluster: bool = False,
        stage_is_deterministic: bool = True,
        elected: bool = False,
        transaction_group: str = "",
    ) -> None:
        self.__ffi_init__(
            stage=stage,
            tx_bytes=tx_bytes,
            arrive_count=arrive_count,
            action=action,
            barrier=barrier,
            cta_group=validate_cta_group(cta_group),
            cluster=cluster,
            stage_is_deterministic=stage_is_deterministic,
            elected=elected,
            transaction_group=transaction_group,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        _check_mbarrier(self.barrier, "barrier")
        self.action = normalize_domain(self.action, SIGNAL_ACTIONS, field_name="action")
        self.cta_group = validate_cta_group(self.cta_group)


@dc.py_class("weave.MBarrierArrive", structural_eq="tree")
class MBarrierArrive(Op, mnemonic="weave.MBarrierArrive"):
    addr: std.Expr = dc.field(lang_kind="arg")


@dc.py_class("weave.PeerArriveCommit", structural_eq="tree")
class PeerArriveCommit(Op, mnemonic="weave.PeerArriveCommit"):
    stage: std.Expr = dc.field(lang_kind="arg")
    barrier: MbarrierSpec = dc.field(kw_only=True, lang_kind="attr")
    cta_group: int = dc.field(default=2, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")

    def __init__(
        self,
        stage: std.Expr,
        *,
        barrier: MbarrierSpec,
        cta_group: int = 2,
        elected: bool = False,
    ) -> None:
        self.__ffi_init__(
            stage=stage,
            barrier=barrier,
            cta_group=validate_cta_group(cta_group),
            elected=elected,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        _check_mbarrier(self.barrier, "barrier")
        self.cta_group = validate_cta_group(self.cta_group)


@dc.py_class("weave.MulticastCommit", structural_eq="tree")
class MulticastCommit(Op, mnemonic="weave.MulticastCommit"):
    stage: std.Expr = dc.field(lang_kind="arg")
    multicast_mask: std.Expr = dc.field(lang_kind="arg")
    barrier: MbarrierSpec = dc.field(kw_only=True, lang_kind="attr")
    cta_group: int = dc.field(default=2, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")

    def __init__(
        self,
        stage: std.Expr,
        multicast_mask: std.Expr,
        *,
        barrier: MbarrierSpec,
        cta_group: int = 2,
        elected: bool = False,
    ) -> None:
        self.__ffi_init__(
            stage=stage,
            multicast_mask=multicast_mask,
            barrier=barrier,
            cta_group=validate_cta_group(cta_group),
            elected=elected,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        _check_mbarrier(self.barrier, "barrier")
        self.cta_group = validate_cta_group(self.cta_group)


@dc.py_class("weave.DualCommit", structural_eq="tree")
class DualCommit(Op, mnemonic="weave.DualCommit"):
    stage_0: std.Expr = dc.field(lang_kind="arg")
    stage_1: std.Expr = dc.field(lang_kind="arg")
    barrier_0: MbarrierSpec = dc.field(kw_only=True, lang_kind="attr")
    barrier_1: MbarrierSpec = dc.field(kw_only=True, lang_kind="attr")
    cta_group: int = dc.field(default=1, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")

    def __init__(
        self,
        stage_0: std.Expr,
        stage_1: std.Expr,
        *,
        barrier_0: MbarrierSpec,
        barrier_1: MbarrierSpec,
        cta_group: int = 1,
        elected: bool = False,
    ) -> None:
        self.__ffi_init__(
            stage_0=stage_0,
            stage_1=stage_1,
            barrier_0=barrier_0,
            barrier_1=barrier_1,
            cta_group=validate_cta_group(cta_group),
            elected=elected,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        _check_mbarrier(self.barrier_0, "barrier_0")
        _check_mbarrier(self.barrier_1, "barrier_1")
        self.cta_group = validate_cta_group(self.cta_group)


@dc.py_class("weave.Fence", structural_eq="tree")
class Fence(Op, mnemonic="weave.Fence"):
    kind: str = dc.field(default="after_thread_sync", lang_kind="attr")

    def __post_init__(self) -> None:
        self.kind = normalize_domain(self.kind, FENCE_KINDS, field_name="kind")


@dc.py_class("weave.ThreadFence", structural_eq="tree")
class ThreadFence(Op, mnemonic="weave.ThreadFence"):
    scope: str = dc.field(default="device", lang_kind="attr")

    def __post_init__(self) -> None:
        self.scope = normalize_domain(self.scope, THREAD_FENCE_SCOPES, field_name="scope")


@dc.py_class("weave.ClusterSync", structural_eq="tree")
class ClusterSync(Op, mnemonic="weave.ClusterSync"):
    pass


@dc.py_class("weave.GridSync", structural_eq="tree")
class GridSync(Op, mnemonic="weave.GridSync"):
    pass


@dc.py_class("weave.GridDepSync", structural_eq="tree")
class GridDepSync(Op, mnemonic="weave.GridDepSync"):
    pass


@dc.py_class("weave.GridDepLaunch", structural_eq="tree")
class GridDepLaunch(Op, mnemonic="weave.GridDepLaunch"):
    pass


@dc.py_class("weave.ClusterMapa", structural_eq="tree")
class ClusterMapa(OutputOp, mnemonic="weave.ClusterMapa"):
    src_addr: std.Expr = dc.field(lang_kind="arg")
    peer_rank: std.Expr = dc.field(lang_kind="arg")
    dst: std.Var = dc.field(lang_kind="out", structural_eq="def-recursive")

    def __init__(
        self,
        src_addr: std.Expr,
        peer_rank: std.Expr,
        dst: std.Var | None = None,
        *,
        ty: std.TyLike | None = None,
    ) -> None:
        self.__ffi_init__(
            src_addr,
            peer_rank,
            var_with_ty_hint(dst, ty, field_name="dst"),
        )

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        self.dst.name = name[0]
        return (self.dst,)


@dc.py_class("weave.ClusterBarrierArrive", structural_eq="tree")
class ClusterBarrierArrive(Op, mnemonic="weave.ClusterBarrierArrive"):
    barrier: std.Expr = dc.field(lang_kind="arg")
    tx_count: std.Expr | None = dc.field(default=None, lang_kind="arg")
    peer_rank: std.Expr | None = dc.field(default=None, lang_kind="arg")


@dc.py_class("weave.CpAsyncBulkSmem2SmemCluster", structural_eq="tree")
class CpAsyncBulkSmem2SmemCluster(Op, mnemonic="weave.CpAsyncBulkSmem2SmemCluster"):
    dst_addr: std.Expr = dc.field(lang_kind="arg")
    src_addr: std.Expr = dc.field(lang_kind="arg")
    bytes: std.Expr = dc.field(lang_kind="arg")
    mbar_addr: std.Expr | None = dc.field(default=None, lang_kind="arg")
    barrier: MbarrierSpec | None = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        if self.barrier is not None:
            _check_mbarrier(self.barrier, "barrier")


@dc.py_class("weave.WarpReduce", structural_eq="tree")
class WarpReduce(OutputOp, mnemonic="weave.WarpReduce"):
    val: std.Expr = dc.field(lang_kind="arg")
    dst: std.Var = dc.field(lang_kind="out", structural_eq="def-recursive")
    op: str = dc.field(default="add", lang_kind="attr")

    def __init__(
        self,
        val: std.Expr,
        op: str = "add",
        dst: std.Var | None = None,
        *,
        ty: std.TyLike | None = None,
    ) -> None:
        self.__ffi_init__(
            val,
            var_with_ty_hint(dst, ty, field_name="dst"),
            op,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        self.op = normalize_domain(self.op, REDUCE_OPS, field_name="op")

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        self.dst.name = name[0]
        self.__post_init__()
        return (self.dst,)


@dc.py_class("weave.BlockReduce", structural_eq="tree")
class BlockReduce(Op, mnemonic="weave.BlockReduce"):
    val: std.Expr = dc.field(lang_kind="arg")
    smem: std.Expr = dc.field(lang_kind="arg")
    op: str = dc.field(default="add", lang_kind="attr")

    def __post_init__(self) -> None:
        self.op = normalize_domain(self.op, REDUCE_OPS, field_name="op")


@dc.py_class("weave.CrossWarpReduce", structural_eq="tree")
class CrossWarpReduce(OutputOp, mnemonic="weave.CrossWarpReduce"):
    src: std.Expr = dc.field(lang_kind="arg")
    smem: std.Expr = dc.field(lang_kind="arg")
    dst: std.Var = dc.field(lang_kind="out", structural_eq="def-recursive")
    op: str = dc.field(default="add", lang_kind="attr")
    finalize: str = dc.field(default="none", lang_kind="attr")

    def __init__(
        self,
        src: std.Expr,
        smem: std.Expr,
        dst: std.Var | None = None,
        op: str = "add",
        finalize: str = "none",
        *,
        ty: std.TyLike | None = None,
    ) -> None:
        self.__ffi_init__(
            src,
            smem,
            var_with_ty_hint(dst, ty, field_name="dst"),
            op,
            finalize,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        self.op = normalize_domain(self.op, REDUCE_OPS, field_name="op")
        self.finalize = normalize_domain(self.finalize, FINALIZE_MODES, field_name="finalize")

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        self.dst.name = name[0]
        self.__post_init__()
        return (self.dst,)


@dc.py_class("weave.WarpGroupReduce", structural_eq="tree")
class WarpGroupReduce(OutputOp, mnemonic="weave.WarpGroupReduce"):
    src: std.Expr = dc.field(lang_kind="arg")
    smem: std.Expr = dc.field(lang_kind="arg")
    dst: std.Var = dc.field(lang_kind="out", structural_eq="def-recursive")
    op: str = dc.field(default="add", lang_kind="attr")
    num_warp_groups: int = dc.field(default=2, lang_kind="attr")

    def __init__(
        self,
        src: std.Expr,
        smem: std.Expr,
        dst: std.Var | None = None,
        op: str = "add",
        num_warp_groups: int = 2,
        *,
        ty: std.TyLike | None = None,
    ) -> None:
        self.__ffi_init__(
            src,
            smem,
            var_with_ty_hint(dst, ty, field_name="dst"),
            op,
            num_warp_groups,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        self.op = normalize_domain(self.op, REDUCE_OPS, field_name="op")

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        self.dst.name = name[0]
        self.__post_init__()
        return (self.dst,)


@dc.py_class("weave.StAsync", structural_eq="tree")
class StAsync(Op, mnemonic="weave.StAsync"):
    dst_addr: std.Expr = dc.field(lang_kind="arg")
    srcs: list[std.Expr] = dc.field(default_factory=list, lang_kind="arg")
    barrier: std.Expr | None = dc.field(default=None, lang_kind="arg")
    bytes: int = dc.field(default=8, lang_kind="attr")
    src_is_int: bool = dc.field(default=False, lang_kind="attr")

    def __post_init__(self) -> None:
        if self.bytes not in (4, 8, 16):
            raise ValueError("bytes must be one of 4, 8, 16")


__all__ = [  # noqa: RUF022
    "BarrierSync",
    "BarrierTryWait",
    "BarrierWait",
    "BarrierSignal",
    "MBarrierArrive",
    "PeerArriveCommit",
    "MulticastCommit",
    "DualCommit",
    "Fence",
    "ThreadFence",
    "ClusterSync",
    "GridSync",
    "GridDepSync",
    "GridDepLaunch",
    "ClusterMapa",
    "ClusterBarrierArrive",
    "CpAsyncBulkSmem2SmemCluster",
    "WarpReduce",
    "BlockReduce",
    "CrossWarpReduce",
    "WarpGroupReduce",
    "StAsync",
]
