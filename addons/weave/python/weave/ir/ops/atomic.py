# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Atomic, system-volatile, and multimem operation nodes."""

from __future__ import annotations

from tvm_ffi import dataclasses as dc
from tvm_ffi import dtype as tvm_dtype
from tvm_ffi import std

from .._utils import Op, normalize_domain, normalize_dtype

ATOMIC_OPS = ("add", "max", "min")
MEM_SPACES = ("gmem", "smem")
MULTIMEM_LOAD_PAYLOADS = ("f32x4", "f16x8", "bf16x8", "e4m3x16", "e5m2x16")
MULTIMEM_STORE_PAYLOADS = ("f32x4",)
MULTIMEM_SEMS = ("relaxed", "release")
MULTIMEM_SCOPES = ("gpu", "sys")


@dc.py_class("weave.AtomicOp", structural_eq="tree")
class AtomicOp(Op, mnemonic="weave.AtomicOp"):
    op: str = dc.field(kw_only=True, lang_kind="attr")
    src: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    index: std.Expr | None = dc.field(default=None, lang_kind="arg")
    space: str = dc.field(kw_only=True, lang_kind="attr")
    dtype: tvm_dtype | None = dc.field(default=None, lang_kind="attr")

    def __init__(
        self,
        src: std.Expr,
        dst: std.Expr,
        index: std.Expr | None = None,
        *,
        op: str,
        space: str,
        dtype: std.TyLike | None = None,
    ) -> None:
        dtype = normalize_dtype(dtype, field_name="dtype")
        self.__ffi_init__(op=op, src=src, dst=dst, index=index, space=space, dtype=dtype)
        self.__post_init__()

    def __post_init__(self) -> None:
        self.op = normalize_domain(self.op, ATOMIC_OPS, field_name="op")
        self.space = normalize_domain(self.space, MEM_SPACES, field_name="space")
        self.dtype = normalize_dtype(self.dtype, field_name="dtype")


@dc.py_class("weave.AtomicFetchAdd", structural_eq="tree")
class AtomicFetchAdd(Op, mnemonic="weave.AtomicFetchAdd"):
    dst: std.Expr = dc.field(lang_kind="arg")
    addr: std.Expr = dc.field(lang_kind="arg")
    val: std.Expr = dc.field(lang_kind="arg")
    index: std.Expr | None = dc.field(default=None, lang_kind="arg")
    dtype: tvm_dtype | None = dc.field(default=None, lang_kind="attr")

    def __init__(
        self,
        dst: std.Expr,
        addr: std.Expr,
        val: std.Expr,
        index: std.Expr | None = None,
        dtype: std.TyLike | None = None,
    ) -> None:
        self.__ffi_init__(
            dst,
            addr,
            val,
            index,
            normalize_dtype(dtype, field_name="dtype"),
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        self.dtype = normalize_dtype(self.dtype, field_name="dtype")


@dc.py_class("weave.RelaxedFmax", structural_eq="tree")
class RelaxedFmax(Op, mnemonic="weave.RelaxedFmax"):
    addr: std.Expr = dc.field(lang_kind="arg")
    val: std.Expr = dc.field(lang_kind="arg")
    space: str = dc.field(default="gmem", lang_kind="attr")

    def __post_init__(self) -> None:
        self.space = normalize_domain(self.space, MEM_SPACES, field_name="space")


@dc.py_class("weave.AtomicMaxF32Positive", structural_eq="tree")
class AtomicMaxF32Positive(Op, mnemonic="weave.AtomicMaxF32Positive"):
    addr: std.Expr = dc.field(lang_kind="arg")
    val: std.Expr = dc.field(lang_kind="arg")
    index: std.Expr | None = dc.field(default=None, lang_kind="arg")
    dst: std.Expr | None = dc.field(default=None, lang_kind="arg")


@dc.py_class("weave.SysVolatileLoad128", structural_eq="tree")
class SysVolatileLoad128(Op, mnemonic="weave.SysVolatileLoad128"):
    addr: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")


@dc.py_class("weave.SysVolatileStore128", structural_eq="tree")
class SysVolatileStore128(Op, mnemonic="weave.SysVolatileStore128"):
    addr: std.Expr = dc.field(lang_kind="arg")
    src: std.Expr = dc.field(lang_kind="arg")


@dc.py_class("weave.MultimemLdReduce", structural_eq="tree")
class MultimemLdReduce(Op, mnemonic="weave.MultimemLdReduce"):
    addr: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    payload: str = dc.field(default="f32x4", lang_kind="attr")

    def __post_init__(self) -> None:
        self.payload = normalize_domain(self.payload, MULTIMEM_LOAD_PAYLOADS, field_name="payload")


@dc.py_class("weave.MultimemStore", structural_eq="tree")
class MultimemStore(Op, mnemonic="weave.MultimemStore"):
    addr: std.Expr = dc.field(lang_kind="arg")
    src: std.Expr = dc.field(lang_kind="arg")
    payload: str = dc.field(default="f32x4", lang_kind="attr")

    def __post_init__(self) -> None:
        self.payload = normalize_domain(self.payload, MULTIMEM_STORE_PAYLOADS, field_name="payload")


@dc.py_class("weave.MultimemRedAddI32", structural_eq="tree")
class MultimemRedAddI32(Op, mnemonic="weave.MultimemRedAddI32"):
    addr: std.Expr = dc.field(lang_kind="arg")
    value: std.Expr = dc.field(lang_kind="arg")
    sem: str = dc.field(default="release", lang_kind="attr")
    scope: str = dc.field(default="sys", lang_kind="attr")

    def __post_init__(self) -> None:
        self.sem = normalize_domain(self.sem, MULTIMEM_SEMS, field_name="sem")
        self.scope = normalize_domain(self.scope, MULTIMEM_SCOPES, field_name="scope")


@dc.py_class("weave.AtomicMaxFloatEncode", structural_eq="tree")
class AtomicMaxFloatEncode(Op, mnemonic="weave.AtomicMaxFloatEncode"):
    dst: std.Expr = dc.field(lang_kind="arg")
    src: std.Expr = dc.field(lang_kind="arg")


@dc.py_class("weave.AtomicMaxFloatDecode", structural_eq="tree")
class AtomicMaxFloatDecode(Op, mnemonic="weave.AtomicMaxFloatDecode"):
    dst: std.Expr = dc.field(lang_kind="arg")
    src: std.Expr = dc.field(lang_kind="arg")


__all__ = [  # noqa: RUF022
    "AtomicOp",
    "AtomicFetchAdd",
    "RelaxedFmax",
    "AtomicMaxF32Positive",
    "SysVolatileLoad128",
    "SysVolatileStore128",
    "MultimemLdReduce",
    "MultimemStore",
    "MultimemRedAddI32",
    "AtomicMaxFloatEncode",
    "AtomicMaxFloatDecode",
]
