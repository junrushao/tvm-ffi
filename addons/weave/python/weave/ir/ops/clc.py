# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Cluster Launch Control operation nodes."""

from __future__ import annotations

from typing import ClassVar

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from .._utils import Op

CTA_DIMS = ("x", "y", "z")


@dc.py_class("weave.ClcTryCancel", structural_eq="tree")
class ClcTryCancel(Op, mnemonic="weave.ClcTryCancel"):
    response_addr: std.Expr = dc.field(lang_kind="arg")
    mbar_addr: std.Expr = dc.field(lang_kind="arg")
    multicast: bool = dc.field(default=False, lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("response_addr", "mbar_addr"))


@dc.py_class("weave.ClcQueryCancel", structural_eq="tree")
class ClcQueryCancel(Op, mnemonic="weave.ClcQueryCancel"):
    response_addr: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("response_addr", "dst"))


@dc.py_class("weave.ClcQueryCancelGetCtaId", structural_eq="tree")
class ClcQueryCancelGetCtaId(Op, mnemonic="weave.ClcQueryCancelGetCtaId"):
    response_addr: std.Expr = dc.field(lang_kind="arg")
    dst: std.Expr = dc.field(lang_kind="arg")
    dim: str = dc.field(default="x", lang_kind="attr")

    EXPR_FIELDS: ClassVar[frozenset[str]] = frozenset(("response_addr", "dst"))
    VALID_DOMAINS: ClassVar[dict[str, tuple[str, ...]]] = {"dim": CTA_DIMS}


@dc.py_class("weave.ClcFenceRelease", structural_eq="tree")
class ClcFenceRelease(Op, mnemonic="weave.ClcFenceRelease"):
    pass


__all__ = [  # noqa: RUF022
    "ClcTryCancel",
    "ClcQueryCancel",
    "ClcQueryCancelGetCtaId",
    "ClcFenceRelease",
]
