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
from tvm_ffi._pyast_parser import Frame, register_dialect
from tvm_ffi._std_lang import (
    bind_one_var,
    parse_func_args,
    register_mnemonic_namespace,
    std_generics,
)

from .ir import config, dtypes, handles, kernel, task
from .ir.ops import atomic, barriers, clc, elementwise, memory, mma


class WeaveFrame(Frame):
    """Base parser frame for Weave body-bearing constructs."""

    dialect = "weave"


class KernelFactory(WeaveFrame):
    """Parser frame for ``@weave.Kernel`` function definitions."""

    def __init__(self, **attrs: Any) -> None:
        self.attrs = attrs
        self.symbol = ""
        self.args: list[std.Var] = []
        self.ret_type: std.Ty | None = None
        self.body: list[Any] = []

    def parse_args(self, args: list[tuple[str, Any]]) -> list[std.Var]:
        self.args = parse_func_args(args)
        return self.args

    def to_dialect(self) -> kernel.Kernel:
        return kernel.Kernel(
            symbol=self.symbol,
            args=self.args,
            ret_type=self.ret_type,
            body=self.body,
            **self.attrs,
        )


class TaskSpecFactory(WeaveFrame):
    """Parser frame for ``with weave.TaskSpec(...):``."""

    def __init__(self, name: str, kind: str, assigned_role: Any, **attrs: Any) -> None:
        self.name = name
        self.kind = kind
        self.assigned_role = assigned_role
        self.attrs = attrs
        self.body: list[Any] = []

    def to_dialect(self) -> task.TaskSpec:
        return task.TaskSpec(
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
    node_cls = task.Block


class LeaderCtaBlockFactory(_ScopeFactory):
    node_cls = task.LeaderCtaBlock


class ElectedThreadBlockFactory(_ScopeFactory):
    node_cls = task.ElectedThreadBlock


class ConditionalIterationFactory(WeaveFrame):
    """Parser frame for ``with weave.ConditionalIteration(...):``."""

    def __init__(self, iter_var: Any, *, last_expr: Any = None) -> None:
        self.iter_var = iter_var
        self.last_expr = last_expr
        self.body: list[Any] = []

    def to_dialect(self) -> task.ConditionalIteration:
        return task.ConditionalIteration(self.iter_var, last_expr=self.last_expr, body=self.body)


class ForLoopFactory(WeaveFrame):
    """Parser frame for ``for i in weave.ForLoop(...):``."""

    def __init__(
        self,
        extent: Any,
        *,
        start: Any = None,
        step: int | None = None,
        step_expr: Any = None,
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

    def bind_names(self, names: Sequence[str]) -> None:
        self.var = bind_one_var(
            names,
            self.var.ty,
            error=f"expected one loop variable, got {len(names)}",
        )

    def bound_vars(self) -> list[std.Var]:
        return [self.var]

    def to_dialect(self) -> task.ForLoop:
        return task.ForLoop(
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


class WeaveLang:
    """Parser-visible Weave namespace."""

    __ffi_globals__: ClassVar[dict[str, Any]] = {}
    __ffi_generics__: ClassVar[dict[Any, Callable[..., Any]]] = {}

    lm = dtypes.lm
    Kernel = KernelFactory
    kernel = KernelFactory
    TaskSpec = TaskSpecFactory
    task = TaskSpecFactory
    ForLoop = ForLoopFactory
    Block = BlockFactory
    LeaderCtaBlock = LeaderCtaBlockFactory
    ElectedThreadBlock = ElectedThreadBlockFactory
    ConditionalIteration = ConditionalIterationFactory


_FRAME_CLASS_NAMES = frozenset(
    {
        "Kernel",
        "TaskSpec",
        "ForLoop",
        "Block",
        "LeaderCtaBlock",
        "ElectedThreadBlock",
        "ConditionalIteration",
    }
)


def _register_module_classes(module: Any) -> None:
    register_mnemonic_namespace(
        WeaveLang,
        (module,),
        dialect="weave",
        skip_names=_FRAME_CLASS_NAMES,
    )


for _module in (
    config,
    dtypes,
    handles,
    kernel,
    task,
    memory,
    elementwise,
    barriers,
    mma,
    atomic,
    clc,
):
    _register_module_classes(_module)


WeaveLang.__ffi_globals__ = {"lm": dtypes.lm}
WeaveLang.__ffi_generics__ = std_generics()

register_dialect("weave", WeaveLang)


__all__ = ["WeaveLang"]
