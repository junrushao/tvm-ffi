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

from typing import Any, ClassVar

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from .._utils import Op, normalize_expr_sequence, validate_cta_group, var_with_ty_hint
from ..dtypes import BarrierRef
from ..handles import MbarrierSpec

SIGNAL_ACTIONS = ("arrive", "arrive_expect_tx", "commit")
FENCE_KINDS = ("after_thread_sync", "before_thread_sync")
THREAD_FENCE_SCOPES = ("block", "device", "system")
REDUCE_OPS = ("add", "max", "min")
FINALIZE_MODES = ("none", "rsqrt")
BarrierHandle = MbarrierSpec | BarrierRef


def _reject_string_handle(value: Any, field_name: str) -> None:
    if isinstance(value, (str, std.StringImm)):
        raise TypeError(f"{field_name} expects a structured handle, not raw string")


@dc.py_class("weave.BarrierSync", structural_eq="tree")
class BarrierSync(Op, mnemonic="weave.BarrierSync"):
    barrier_id: int = dc.field(default=0, lang_kind="attr")


@dc.py_class("weave.BarrierTryWait", structural_eq="tree")
class BarrierTryWait(Op, mnemonic="weave.BarrierTryWait"):
    barrier: BarrierHandle = dc.field(lang_kind="arg")
    stage: std.Expr = dc.field(lang_kind="arg")
    phase: std.Expr = dc.field(lang_kind="arg")
    dst: std.Var = dc.field(lang_kind="var_def", structural_eq="def-recursive")
    stage_is_deterministic: bool = dc.field(default=True, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("stage", "phase"))

    def __init__(
        self,
        barrier: BarrierHandle,
        stage: std.Expr,
        phase: std.Expr,
        dst: std.Var | None = None,
        stage_is_deterministic: bool = True,
        *,
        ty: Any = None,
    ) -> None:
        self.__ffi_init__(
            barrier,
            stage,
            phase,
            var_with_ty_hint(dst, ty, field_name="dst"),
            stage_is_deterministic,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        _reject_string_handle(self.barrier, "barrier")
        super().__post_init__()

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        dst = std.Var(self.dst.ty, name[0])
        object.__setattr__(self, "dst", dst)
        self.__post_init__()
        return (dst,)


@dc.py_class("weave.BarrierWait", structural_eq="tree")
class BarrierWait(Op, mnemonic="weave.BarrierWait"):
    barrier: BarrierHandle = dc.field(lang_kind="arg")
    stage: std.Expr = dc.field(lang_kind="arg")
    phase: std.Expr = dc.field(lang_kind="arg")
    token: std.Expr | None = dc.field(default=None, lang_kind="attr")
    stage_is_deterministic: bool = dc.field(default=True, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("stage", "phase", "token"))

    def __post_init__(self) -> None:
        _reject_string_handle(self.barrier, "barrier")
        super().__post_init__()


@dc.py_class("weave.BarrierSignal", structural_eq="tree")
class BarrierSignal(Op, mnemonic="weave.BarrierSignal"):
    barrier: BarrierHandle = dc.field(lang_kind="arg")
    action: str = dc.field(lang_kind="arg")
    stage: std.Expr = dc.field(lang_kind="arg")
    tx_bytes: std.Expr | None = dc.field(default=None, lang_kind="attr")
    arrive_count: std.Expr | None = dc.field(default=None, lang_kind="attr")
    cta_group: Any = dc.field(default=1, lang_kind="attr")
    cluster: bool = dc.field(default=False, lang_kind="attr")
    stage_is_deterministic: bool = dc.field(default=True, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")
    transaction_group: str = dc.field(default="", lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("stage", "tx_bytes", "arrive_count"))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"action": SIGNAL_ACTIONS}

    def __post_init__(self) -> None:
        _reject_string_handle(self.barrier, "barrier")
        super().__post_init__()
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))


@dc.py_class("weave.MBarrierArrive", structural_eq="tree")
class MBarrierArrive(Op, mnemonic="weave.MBarrierArrive"):
    addr: std.Expr = dc.field(lang_kind="arg")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("addr",))


@dc.py_class("weave.PeerArriveCommit", structural_eq="tree")
class PeerArriveCommit(Op, mnemonic="weave.PeerArriveCommit"):
    barrier: BarrierHandle = dc.field(lang_kind="arg")
    stage: std.Expr = dc.field(lang_kind="arg")
    cta_group: Any = dc.field(default=2, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("stage",))

    def __post_init__(self) -> None:
        _reject_string_handle(self.barrier, "barrier")
        super().__post_init__()
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))


@dc.py_class("weave.MulticastCommit", structural_eq="tree")
class MulticastCommit(Op, mnemonic="weave.MulticastCommit"):
    barrier: BarrierHandle = dc.field(lang_kind="arg")
    stage: std.Expr = dc.field(lang_kind="arg")
    multicast_mask: std.Expr = dc.field(lang_kind="arg")
    cta_group: Any = dc.field(default=2, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("stage", "multicast_mask"))

    def __post_init__(self) -> None:
        _reject_string_handle(self.barrier, "barrier")
        super().__post_init__()
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))


@dc.py_class("weave.DualCommit", structural_eq="tree")
class DualCommit(Op, mnemonic="weave.DualCommit"):
    barrier_0: BarrierHandle = dc.field(lang_kind="arg")
    barrier_1: BarrierHandle = dc.field(lang_kind="arg")
    stage_0: std.Expr = dc.field(lang_kind="arg")
    stage_1: std.Expr = dc.field(lang_kind="arg")
    cta_group: Any = dc.field(default=1, lang_kind="attr")
    elected: bool = dc.field(default=False, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("stage_0", "stage_1"))

    def __post_init__(self) -> None:
        _reject_string_handle(self.barrier_0, "barrier_0")
        _reject_string_handle(self.barrier_1, "barrier_1")
        super().__post_init__()
        object.__setattr__(self, "cta_group", validate_cta_group(self.cta_group))


@dc.py_class("weave.Fence", structural_eq="tree")
class Fence(Op, mnemonic="weave.Fence"):
    kind: str = dc.field(default="after_thread_sync", lang_kind="attr")

    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"kind": FENCE_KINDS}


@dc.py_class("weave.ThreadFence", structural_eq="tree")
class ThreadFence(Op, mnemonic="weave.ThreadFence"):
    scope: str = dc.field(default="device", lang_kind="attr")

    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"scope": THREAD_FENCE_SCOPES}


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
class ClusterMapa(Op, mnemonic="weave.ClusterMapa"):
    src_addr: std.Expr = dc.field(lang_kind="arg")
    peer_rank: std.Expr = dc.field(lang_kind="arg")
    dst: std.Var = dc.field(lang_kind="var_def", structural_eq="def-recursive")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src_addr", "peer_rank"))

    def __init__(
        self,
        src_addr: std.Expr,
        peer_rank: std.Expr,
        dst: std.Var | None = None,
        *,
        ty: Any = None,
    ) -> None:
        self.__ffi_init__(
            src_addr,
            peer_rank,
            var_with_ty_hint(dst, ty, field_name="dst"),
        )
        self.__post_init__()

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        dst = std.Var(self.dst.ty, name[0])
        object.__setattr__(self, "dst", dst)
        self.__post_init__()
        return (dst,)


@dc.py_class("weave.ClusterBarrierArrive", structural_eq="tree")
class ClusterBarrierArrive(Op, mnemonic="weave.ClusterBarrierArrive"):
    barrier: std.Expr = dc.field(lang_kind="arg")
    tx_count: std.Expr | None = dc.field(default=None, lang_kind="attr")
    peer_rank: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("barrier", "tx_count", "peer_rank"))


@dc.py_class("weave.CpAsyncBulkSmem2SmemCluster", structural_eq="tree")
class CpAsyncBulkSmem2SmemCluster(Op, mnemonic="weave.CpAsyncBulkSmem2SmemCluster"):
    dst_addr: std.Expr = dc.field(lang_kind="arg")
    src_addr: std.Expr = dc.field(lang_kind="arg")
    bytes: std.Expr = dc.field(lang_kind="arg")
    barrier: BarrierHandle | None = dc.field(default=None, lang_kind="attr")
    mbar_addr: std.Expr | None = dc.field(default=None, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(
        ("dst_addr", "src_addr", "bytes", "mbar_addr")
    )

    def __post_init__(self) -> None:
        if self.barrier is not None:
            _reject_string_handle(self.barrier, "barrier")
        super().__post_init__()


@dc.py_class("weave.WarpReduce", structural_eq="tree")
class WarpReduce(Op, mnemonic="weave.WarpReduce"):
    val: std.Expr = dc.field(lang_kind="arg")
    op: str = dc.field(default="add", lang_kind="attr")
    dst: std.Var | None = dc.field(default=None, lang_kind="var_def", structural_eq="def-recursive")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("val",))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"op": REDUCE_OPS}

    def __init__(
        self,
        val: std.Expr,
        op: str = "add",
        dst: std.Var | None = None,
        *,
        ty: Any = None,
    ) -> None:
        self.__ffi_init__(
            val,
            op,
            var_with_ty_hint(dst, ty, field_name="dst")
            if dst is not None or ty is not None
            else None,
        )
        self.__post_init__()

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if self.dst is None:
            if len(name) == 0:
                return ()
            raise TypeError(f"expected 0 binding target(s), got {len(name)}")
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        dst = std.Var(self.dst.ty, name[0])
        object.__setattr__(self, "dst", dst)
        self.__post_init__()
        return (dst,)


@dc.py_class("weave.BlockReduce", structural_eq="tree")
class BlockReduce(Op, mnemonic="weave.BlockReduce"):
    val: std.Expr = dc.field(lang_kind="arg")
    smem: std.Expr = dc.field(lang_kind="arg")
    op: str = dc.field(default="add", lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("val", "smem"))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"op": REDUCE_OPS}


@dc.py_class("weave.CrossWarpReduce", structural_eq="tree")
class CrossWarpReduce(Op, mnemonic="weave.CrossWarpReduce"):
    src: std.Expr = dc.field(lang_kind="arg")
    smem: std.Expr = dc.field(lang_kind="arg")
    dst: std.Var = dc.field(lang_kind="var_def", structural_eq="def-recursive")
    op: str = dc.field(default="add", lang_kind="attr")
    finalize: str = dc.field(default="none", lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "smem"))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {
        "op": REDUCE_OPS,
        "finalize": FINALIZE_MODES,
    }

    def __init__(
        self,
        src: std.Expr,
        smem: std.Expr,
        dst: std.Var | None = None,
        op: str = "add",
        finalize: str = "none",
        *,
        ty: Any = None,
    ) -> None:
        self.__ffi_init__(
            src,
            smem,
            var_with_ty_hint(dst, ty, field_name="dst"),
            op,
            finalize,
        )
        self.__post_init__()

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        dst = std.Var(self.dst.ty, name[0])
        object.__setattr__(self, "dst", dst)
        self.__post_init__()
        return (dst,)


@dc.py_class("weave.WarpGroupReduce", structural_eq="tree")
class WarpGroupReduce(Op, mnemonic="weave.WarpGroupReduce"):
    src: std.Expr = dc.field(lang_kind="arg")
    smem: std.Expr = dc.field(lang_kind="arg")
    dst: std.Var = dc.field(lang_kind="var_def", structural_eq="def-recursive")
    op: str = dc.field(default="add", lang_kind="attr")
    num_warp_groups: int = dc.field(default=2, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("src", "smem"))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"op": REDUCE_OPS}

    def __init__(
        self,
        src: std.Expr,
        smem: std.Expr,
        dst: std.Var | None = None,
        op: str = "add",
        num_warp_groups: int = 2,
        *,
        ty: Any = None,
    ) -> None:
        self.__ffi_init__(
            src,
            smem,
            var_with_ty_hint(dst, ty, field_name="dst"),
            op,
            num_warp_groups,
        )
        self.__post_init__()

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        dst = std.Var(self.dst.ty, name[0])
        object.__setattr__(self, "dst", dst)
        self.__post_init__()
        return (dst,)


@dc.py_class("weave.StAsync", structural_eq="tree")
class StAsync(Op, mnemonic="weave.StAsync"):
    dst_addr: std.Expr = dc.field(lang_kind="arg")
    srcs: list[std.Expr] = dc.field(default_factory=list, lang_kind="attr")
    bytes: int = dc.field(default=8, lang_kind="attr")
    barrier: std.Expr | None = dc.field(default=None, lang_kind="attr")
    src_is_int: bool = dc.field(default=False, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("dst_addr", "barrier"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "srcs", normalize_expr_sequence(self.srcs, field_name="srcs"))
        super().__post_init__()
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
