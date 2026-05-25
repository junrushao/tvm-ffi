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
from typing import Any, ClassVar

from tvm_ffi import dataclasses as dc
from tvm_ffi import std
from tvm_ffi._pyast_parser import Frame, register_dialect
from tvm_ffi._std_lang import (
    Std,
    bind_one_var,
    parse_func_args,
    register_mnemonic_namespace,
    std_generics,
)

from .ir import func, inst, instructions, layout, stmt, tensor
from .ir.instructions import generic, hints


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


class FunctionFactory(TilusFrame):
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
    space: str | None = None

    def __ffi_scope_bind__(self) -> std.Stmt:
        """Build a placeholder tensor-item binding for ``std.scope(... ) as``."""
        var = std.Var(self.tensor_value, "")
        if self.cls is stmt.TensorItemPtr:
            return stmt.TensorItemPtr(self.tensor_value, var, self.space)
        return stmt.TensorItemValue(self.tensor_value, var)


def _tensor_ctor(cls: type, dtype: std.TyLike, *shape: Any, **kwargs: Any) -> tensor.Tensor:
    if "shape" in kwargs:
        if shape:
            raise TypeError("shape specified both positionally and by keyword")
        shape_value = kwargs.pop("shape")
        try:
            shape = tuple(shape_value)
        except TypeError:
            raise TypeError(
                f"shape must be a sequence of integer extents, got {type(shape_value).__name__}"
            ) from None
    elif len(shape) == 1 and isinstance(shape[0], (list, tuple)):
        shape = tuple(shape[0])
    has_optional_layout = "optional_layout" in kwargs
    optional_layout = kwargs.pop("optional_layout", None)
    has_layout = "layout" in kwargs
    layout_value = kwargs.pop("layout", None)
    if has_optional_layout and has_layout:
        raise TypeError("specify either optional_layout or layout, not both")
    if kwargs:
        unexpected = next(iter(kwargs))
        raise TypeError(f"unexpected keyword argument: {unexpected}")
    optional_layout = optional_layout if optional_layout is not None else layout_value
    ty = std.normalize_ty(dtype)
    if not isinstance(ty, std.PrimTy):
        raise TypeError(f"expected primitive dtype, got {type(ty).__name__}")
    return cls(ty, shape=tensor._shape(shape), optional_layout=optional_layout)


def _tensor_ctor_for(cls: type) -> Callable[..., tensor.Tensor]:
    def make(dtype: std.TyLike, *shape: Any, **kwargs: Any) -> tensor.Tensor:
        return _tensor_ctor(cls, dtype, *shape, **kwargs)

    make.__name__ = cls.__ffi_dialect_mnemonic__[1]
    make.__qualname__ = make.__name__
    return make


def _expr(value: Any) -> std.Expr:
    return value if isinstance(value, std.Expr) else std.Expr.literal(value)


def _global_layout_ctor(*shape: Any, **kwargs: Any) -> layout.GlobalLayout:
    if "shape" in kwargs:
        if shape:
            raise TypeError("shape specified both positionally and by keyword")
        shape = tuple(kwargs.pop("shape"))
    elif len(shape) == 1 and isinstance(shape[0], (list, tuple)):
        shape = tuple(shape[0])
    size = kwargs.pop("size", None)
    axes = kwargs.pop("axes", None)
    offset = kwargs.pop("offset", 0)
    if kwargs:
        unexpected = next(iter(kwargs))
        raise TypeError(f"unexpected keyword argument: {unexpected}")
    if axes is None:
        axes = tuple(f"i{axis}" for axis in range(len(shape)))
    else:
        for axis in axes:
            if not isinstance(axis, str):
                raise TypeError(f"axes entries must be strings, got {axis!r}")
    if size is None:
        size = layout.prod(shape)
    return layout.GlobalLayout(
        shape=tuple(
            layout._integer_expr(extent, "shape extent", positive=True) for extent in shape
        ),
        size=layout._integer_expr(size, "size"),
        axes=tuple(axes),
        offset=layout._integer_expr(offset, "offset"),
    )


def _apply_positional_kwargs(
    names: tuple[str, ...],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    if len(args) > len(names):
        raise TypeError(f"expected at most {len(names)} positional arguments, got {len(args)}")
    out = dict(kwargs)
    for name, value in zip(names, args):
        if name in out:
            raise TypeError(f"{name} specified both positionally and by keyword")
        out[name] = value
    return out


def _register_layout_ctor(*args: Any, **kwargs: Any) -> layout.RegisterLayout:
    kwargs = _apply_positional_kwargs(
        ("shape", "mode_shape", "spatial_modes", "local_modes"), args, kwargs
    )
    shape = kwargs.pop("shape", ())
    mode_shape = kwargs.pop("mode_shape", None)
    spatial_modes = kwargs.pop("spatial_modes", None)
    local_modes = kwargs.pop("local_modes", None)
    if kwargs:
        unexpected = next(iter(kwargs))
        raise TypeError(f"unexpected keyword argument: {unexpected}")
    return layout.register_layout(
        shape,
        mode_shape=mode_shape,
        spatial_modes=spatial_modes,
        local_modes=local_modes,
    )


def _shared_layout_ctor(*args: Any, **kwargs: Any) -> layout.SharedLayout:
    kwargs = _apply_positional_kwargs(
        ("shape", "mode_shape", "mode_strides", "optional_swizzle"), args, kwargs
    )
    shape = kwargs.pop("shape", ())
    mode_shape = kwargs.pop("mode_shape", None)
    mode_strides = kwargs.pop("mode_strides", None)
    optional_swizzle = kwargs.pop("optional_swizzle", None)
    if kwargs:
        unexpected = next(iter(kwargs))
        raise TypeError(f"unexpected keyword argument: {unexpected}")
    return layout.shared_layout(
        shape,
        mode_shape=mode_shape,
        mode_strides=mode_strides,
        optional_swizzle=optional_swizzle,
    )


def _tmemory_layout_ctor(*args: Any, **kwargs: Any) -> layout.TMemoryLayout:
    kwargs = _apply_positional_kwargs(("shape", "column_strides", "lane_offset"), args, kwargs)
    shape = kwargs.pop("shape", ())
    column_strides = kwargs.pop("column_strides", None)
    lane_offset = kwargs.pop("lane_offset", 0)
    if kwargs:
        unexpected = next(iter(kwargs))
        raise TypeError(f"unexpected keyword argument: {unexpected}")
    if column_strides is None and lane_offset == 0:
        return layout.tmemory_layout(shape)
    return layout.TMemoryLayout(
        shape=layout._shape(shape),
        column_strides=layout._tuple(column_strides or ()),
        lane_offset=layout._strict_int(lane_offset, "lane_offset"),
    )


def _instruction_ctor(cls: type[inst.Instruction]) -> Callable[..., inst.Instruction]:
    def make(*args: Any, **kwargs: Any) -> inst.Instruction:
        output = kwargs.pop("output", None)
        has_inputs = "inputs" in kwargs
        inputs = kwargs.pop("inputs", None)
        if has_inputs and inputs is None:
            raise TypeError("inputs must not be None")
        if not has_inputs:
            inputs_list = list(args)
            args = ()
        else:
            try:
                inputs_list = list(inputs)
            except TypeError:
                raise TypeError(
                    f"inputs must be an iterable of operands, got {type(inputs).__name__}"
                ) from None
        if args:
            raise TypeError(f"{cls.__name__} unexpected positional arguments: {args!r}")
        return cls(inputs=inputs_list, output=output, **kwargs)

    make.__name__ = cls.__ffi_dialect_mnemonic__[1]
    make.__qualname__ = make.__name__
    return make


def _make_var(names: Sequence[str], ty: Any) -> std.Var:
    return bind_one_var(names, ty)


def _bind_expr(names: Sequence[str], ty: Any, expr: Any) -> Any:
    if isinstance(expr, inst.Instruction):
        if expr.output is not None:
            raise TypeError("instruction RHS must not already define an output")
        if ty is None:
            raise TypeError("instruction assignment requires a type annotation")
        return dc.replace(expr, output=_make_var(names, ty))
    if isinstance(expr, _TensorItemBuilder):
        bind_ty = ty if ty is not None else expr.tensor_value
        var = _make_var(names, bind_ty)
        if expr.cls is stmt.TensorItemPtr:
            return stmt.TensorItemPtr(expr.tensor_value, var, expr.space)
        return stmt.TensorItemValue(expr.tensor_value, var)
    return Std.__ffi_generics__["__bind_expr__"](names, ty, expr)


class TilusLang:
    """Parser-visible Tilus language namespace."""

    __ffi_globals__: ClassVar[dict[str, Any]] = {}
    __ffi_generics__: ClassVar[dict[Any, Callable[..., Any]]] = {}

    Swizzle = layout.Swizzle
    RegisterLayout = staticmethod(_register_layout_ctor)
    SharedLayout = staticmethod(_shared_layout_ctor)
    GlobalLayout = _global_layout_ctor
    TMemoryLayout = staticmethod(_tmemory_layout_ctor)

    RegTensor = staticmethod(_tensor_ctor_for(tensor.RegisterTensor))
    RegisterTensor = RegTensor
    SharedTensor = staticmethod(_tensor_ctor_for(tensor.SharedTensor))
    GlobalTensor = staticmethod(_tensor_ctor_for(tensor.GlobalTensor))
    TMemoryTensor = staticmethod(_tensor_ctor_for(tensor.TMemoryTensor))

    ThreadGroup = ThreadGroupFactory
    thread_group = ThreadGroupFactory
    Function = FunctionFactory
    function = FunctionFactory
    Metadata = func.Metadata
    Analysis = func.Analysis

    Eval = stmt.Evaluate
    Inst = stmt.InstStmt

    TensorItemPtr = staticmethod(
        lambda tensor_value, space=None: _TensorItemBuilder(stmt.TensorItemPtr, tensor_value, space)
    )
    TensorItemValue = staticmethod(
        lambda tensor_value: _TensorItemBuilder(stmt.TensorItemValue, tensor_value)
    )

    LoadGlobal = staticmethod(_instruction_ctor(generic.LoadGlobalInst))
    StoreGlobal = staticmethod(_instruction_ctor(generic.StoreGlobalInst))
    LoadShared = staticmethod(_instruction_ctor(generic.LoadSharedInst))
    StoreShared = staticmethod(_instruction_ctor(generic.StoreSharedInst))
    Cast = staticmethod(_instruction_ctor(generic.CastInst))
    Add = staticmethod(_instruction_ctor(generic.AddInst))
    Sub = staticmethod(_instruction_ctor(generic.SubInst))
    Mul = staticmethod(_instruction_ctor(generic.MulInst))
    Div = staticmethod(_instruction_ctor(generic.DivInst))
    Reduce = staticmethod(_instruction_ctor(generic.ReduceInst))
    SyncThreads = staticmethod(_instruction_ctor(generic.SyncThreadsInst))
    Nop = staticmethod(_instruction_ctor(generic.NopInst))
    AnnotateLayout = staticmethod(_instruction_ctor(hints.AnnotateLayoutInst))
    Assume = staticmethod(_instruction_ctor(hints.AssumeInst))


def _instruction_namespace_value(cls: type[Any]) -> Any:
    if issubclass(cls, inst.Instruction):
        return staticmethod(_instruction_ctor(cls))
    return cls


def _register_instruction_constructors() -> None:
    register_mnemonic_namespace(
        TilusLang,
        (instructions,),
        dialect="tilus",
        skip_mnemonics={"Instruction"},
        expose_export_name=False,
        value_for=_instruction_namespace_value,
    )


_register_instruction_constructors()


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
