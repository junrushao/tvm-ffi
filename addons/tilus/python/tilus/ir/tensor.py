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
"""Tilus tensor type nodes."""

from __future__ import annotations

from collections.abc import Sequence

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

from .layout import GlobalLayout, Layout, RegisterLayout, SharedLayout, TMemoryLayout


def _prim_ty(dtype: std.TyLike) -> std.PrimTy:
    if isinstance(dtype, std.Ty):
        ty = dtype
    elif hasattr(dtype, "to_dialect"):
        ty = dtype.to_dialect()
    else:
        ty = std.PrimTy(dtype)
    if not isinstance(ty, std.PrimTy):
        raise TypeError(f"expected primitive dtype, got {type(ty).__name__}")
    return ty


def _shape(values: Sequence[int]) -> tuple[int, ...]:
    shape = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"shape extents must be integers, got {value!r}")
        shape.append(value)
    if any(value < 1 for value in shape):
        raise ValueError(f"shape extents must be positive, got {tuple(shape)}")
    return tuple(shape)


def _layout_shape(layout: Layout) -> tuple[int, ...] | None:
    shape = layout.shape
    if isinstance(layout, GlobalLayout):
        extents = []
        for extent in shape:
            if not isinstance(extent, std.IntImm):
                return None
            extents.append(int(extent.value))
        return tuple(extents)
    return tuple(int(extent) for extent in shape)


def _check_layout_shape(tensor_shape: tuple[int, ...], layout: Layout | None) -> None:
    if layout is None:
        return
    layout_shape = _layout_shape(layout)
    if layout_shape is not None and layout_shape != tensor_shape:
        raise ValueError(f"tensor shape {tensor_shape} must match layout shape {layout_shape}")


def _collect_tensor_fields(obj: Tensor) -> std.FieldCollectionResult:
    attrs: dict[str, object] = {}
    if obj.optional_layout is not None:
        attrs["layout"] = obj.optional_layout
    return std.FieldCollectionResult(
        args=[obj.dtype, *obj.shape],
        attrs=attrs,
        var_def=[],
        body=[],
    )


@dc.py_class("tilus.Tensor", structural_eq="tree", init=False)
class Tensor(std.Ty, mnemonic="tilus.Tensor"):
    """Base class for Tilus memory-space tensor types."""

    __ffi_dialect_field_collector__ = staticmethod(_collect_tensor_fields)

    dtype: std.PrimTy = dc.field(lang_kind="arg")
    shape: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    optional_layout: Layout | None = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        _shape(self.shape)

    def has_layout(self) -> bool:
        """Return whether this tensor has an explicit layout."""
        return self.optional_layout is not None


@dc.py_class("tilus.RegisterTensor", structural_eq="tree")
class RegisterTensor(Tensor, mnemonic="tilus.RegTensor"):
    """A tensor stored in per-thread registers."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.optional_layout is not None and not isinstance(
            self.optional_layout, RegisterLayout
        ):
            raise TypeError("RegisterTensor layout must be a RegisterLayout")
        _check_layout_shape(self.shape, self.optional_layout)

    @property
    def layout(self) -> RegisterLayout:
        """Return the register layout, or raise if absent."""
        if self.optional_layout is None:
            raise ValueError("RegisterTensor layout is not defined")
        if not isinstance(self.optional_layout, RegisterLayout):
            raise TypeError("RegisterTensor layout must be a RegisterLayout")
        return self.optional_layout


@dc.py_class("tilus.SharedTensor", structural_eq="tree")
class SharedTensor(Tensor, mnemonic="tilus.SharedTensor"):
    """A tensor stored in shared memory."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.optional_layout is not None and not isinstance(self.optional_layout, SharedLayout):
            raise TypeError("SharedTensor layout must be a SharedLayout")
        _check_layout_shape(self.shape, self.optional_layout)

    @property
    def layout(self) -> SharedLayout:
        """Return the shared-memory layout, or raise if absent."""
        if self.optional_layout is None:
            raise ValueError("SharedTensor layout is not defined")
        if not isinstance(self.optional_layout, SharedLayout):
            raise TypeError("SharedTensor layout must be a SharedLayout")
        return self.optional_layout


@dc.py_class("tilus.GlobalTensor", structural_eq="tree")
class GlobalTensor(Tensor, mnemonic="tilus.GlobalTensor"):
    """A tensor stored in global memory."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.optional_layout is not None and not isinstance(self.optional_layout, GlobalLayout):
            raise TypeError("GlobalTensor layout must be a GlobalLayout")
        _check_layout_shape(self.shape, self.optional_layout)

    @property
    def layout(self) -> GlobalLayout:
        """Return the global-memory layout, or raise if absent."""
        if self.optional_layout is None:
            raise ValueError("GlobalTensor layout is not defined")
        if not isinstance(self.optional_layout, GlobalLayout):
            raise TypeError("GlobalTensor layout must be a GlobalLayout")
        return self.optional_layout


@dc.py_class("tilus.TMemoryTensor", structural_eq="tree")
class TMemoryTensor(Tensor, mnemonic="tilus.TMemoryTensor"):
    """A tensor stored in tensor memory."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.optional_layout is not None and not isinstance(self.optional_layout, TMemoryLayout):
            raise TypeError("TMemoryTensor layout must be a TMemoryLayout")
        _check_layout_shape(self.shape, self.optional_layout)

    @property
    def layout(self) -> TMemoryLayout:
        """Return the tensor-memory layout, or raise if absent."""
        if self.optional_layout is None:
            raise ValueError("TMemoryTensor layout is not defined")
        if not isinstance(self.optional_layout, TMemoryLayout):
            raise TypeError("TMemoryTensor layout must be a TMemoryLayout")
        return self.optional_layout


def register_tensor(
    dtype: std.TyLike,
    shape: Sequence[int],
    layout: RegisterLayout | None = None,
) -> RegisterTensor:
    """Create a register tensor type."""
    return RegisterTensor(
        _prim_ty(dtype),
        shape=_shape(shape),
        optional_layout=layout,
    )


def shared_tensor(
    dtype: std.TyLike,
    shape: Sequence[int],
    layout: SharedLayout | None = None,
) -> SharedTensor:
    """Create a shared tensor type."""
    return SharedTensor(
        _prim_ty(dtype),
        shape=_shape(shape),
        optional_layout=layout,
    )


def global_tensor(
    dtype: std.TyLike,
    shape: Sequence[int],
    layout: GlobalLayout | None = None,
) -> GlobalTensor:
    """Create a global tensor type."""
    return GlobalTensor(
        _prim_ty(dtype),
        shape=_shape(shape),
        optional_layout=layout,
    )


def tmemory_tensor(
    dtype: std.TyLike,
    shape: Sequence[int],
    layout: TMemoryLayout | None = None,
) -> TMemoryTensor:
    """Create a tensor-memory tensor type."""
    return TMemoryTensor(
        _prim_ty(dtype),
        shape=_shape(shape),
        optional_layout=layout,
    )


__all__ = [
    "GlobalTensor",
    "RegisterTensor",
    "SharedTensor",
    "TMemoryTensor",
    "Tensor",
    "global_tensor",
    "register_tensor",
    "shared_tensor",
    "tmemory_tensor",
]
