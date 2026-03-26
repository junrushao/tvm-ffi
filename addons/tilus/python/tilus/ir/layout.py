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
"""Tilus layout dialect nodes."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TypeAlias

from tvm_ffi import dataclasses as dc
from tvm_ffi import std

ExprLike: TypeAlias = "std.Expr | bool | int | float | str"


def prod(values: Iterable[ExprLike]) -> ExprLike:
    """Return the product of a sequence, preserving std expressions."""
    result: ExprLike = 1
    for value in values:
        result = result * value  # type: ignore[operator]
    return result


def _strict_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer, got {value!r}")
    return value


def _shape(values: Sequence[int]) -> tuple[int, ...]:
    shape = tuple(_strict_int(value, "shape extents") for value in values)
    if any(value < 1 for value in shape):
        raise ValueError(f"shape extents must be positive, got {shape}")
    return shape


def _tuple(values: Sequence[int] | None = None) -> tuple[int, ...]:
    return tuple(_strict_int(value, "tuple entries") for value in (values or ()))


def _expr(value: ExprLike) -> std.Expr:
    return value if isinstance(value, std.Expr) else std.Expr.literal(value)


def _integer_expr(value: ExprLike, field_name: str, *, positive: bool = False) -> std.Expr:
    if isinstance(value, std.IntImm):
        if positive and value.value < 1:
            raise ValueError(f"{field_name} must be positive, got {value.value}")
        return value
    if isinstance(value, (std.BoolImm, std.FloatImm, std.StringImm)):
        raise TypeError(f"{field_name} must be an integer expression")
    if isinstance(value, std.Expr):
        return value
    int_value = _strict_int(value, field_name)
    if positive and int_value < 1:
        raise ValueError(f"{field_name} must be positive, got {int_value}")
    return std.IntImm.from_py(int_value)


def _expr_tuple(values: Sequence[ExprLike]) -> tuple[std.Expr, ...]:
    return tuple(_expr(value) for value in values)


def _integer_expr_tuple(values: Sequence[ExprLike], field_name: str) -> tuple[std.Expr, ...]:
    return tuple(_integer_expr(value, field_name, positive=True) for value in values)


def _int_prod(values: Iterable[int]) -> int:
    return int(prod(values))


def _get_mode_groups(
    shape: Sequence[int], mode_shape: Sequence[int]
) -> tuple[tuple[int, ...], ...]:
    if any(factor < 1 for factor in mode_shape):
        raise ValueError(f"mode_shape entries must be positive, got {tuple(mode_shape)}")
    groups: list[tuple[int, ...]] = []
    mode = 0
    for extent in shape:
        remaining = extent
        begin = mode
        if remaining == 1:
            if mode < len(mode_shape) and mode_shape[mode] == 1:
                mode += 1
            groups.append(tuple(range(begin, mode)))
            continue
        while remaining > 1 and mode < len(mode_shape):
            factor = mode_shape[mode]
            if remaining % factor != 0:
                raise ValueError(f"mode {factor} does not divide remaining extent {remaining}")
            remaining //= factor
            mode += 1
        if remaining != 1:
            raise ValueError(f"mode_shape {tuple(mode_shape)} does not cover shape {tuple(shape)}")
        groups.append(tuple(range(begin, mode)))
    if mode != len(mode_shape):
        raise ValueError(
            f"mode_shape {tuple(mode_shape)} has unused modes for shape {tuple(shape)}"
        )
    return tuple(groups)


def _strides_from_ranks(shape: Sequence[int], ranks: Sequence[int]) -> tuple[int, ...]:
    if len(shape) != len(ranks):
        raise ValueError(
            f"shape and ranks must have the same length, got {len(shape)} vs {len(ranks)}"
        )
    if len(ranks) != len(set(ranks)) or any(rank < 0 or rank >= len(shape) for rank in ranks):
        raise ValueError(f"ranks must be unique and in range [0, {len(shape)}), got {tuple(ranks)}")
    return tuple(
        _int_prod(shape[axis] for axis in range(len(shape)) if ranks[axis] > ranks[dim])
        for dim in range(len(shape))
    )


def _collect_register_layout_fields(obj: RegisterLayout) -> std.FieldCollectionResult:
    return std.FieldCollectionResult(
        args=list(obj.shape),
        attrs={
            "local_modes": obj.local_modes,
            "mode_shape": obj.mode_shape,
            "spatial_modes": obj.spatial_modes,
        },
    )


def _collect_shared_layout_fields(obj: SharedLayout) -> std.FieldCollectionResult:
    attrs = {
        "mode_shape": obj.mode_shape,
        "mode_strides": obj.mode_strides,
    }
    if obj.optional_swizzle is not None:
        attrs["optional_swizzle"] = obj.optional_swizzle
    return std.FieldCollectionResult(args=list(obj.shape), attrs=attrs)


def _collect_global_layout_fields(obj: GlobalLayout) -> std.FieldCollectionResult:
    return std.FieldCollectionResult(
        args=list(obj.shape),
        attrs={
            "axes": obj.axes,
            "offset": obj.offset,
            "size": obj.size,
        },
    )


def _collect_tmemory_layout_fields(obj: TMemoryLayout) -> std.FieldCollectionResult:
    return std.FieldCollectionResult(
        args=list(obj.shape),
        attrs={
            "column_strides": obj.column_strides,
            "lane_offset": obj.lane_offset,
        },
    )


@dc.py_class("tilus.Layout", frozen=True, init=False, structural_eq="tree")
class Layout(std.Node, mnemonic="tilus.Layout"):
    """Base class for Tilus layout descriptors."""


@dc.py_class("tilus.Swizzle", frozen=True, structural_eq="tree")
class Swizzle(std.Node, mnemonic="tilus.Swizzle"):
    """XOR swizzle descriptor."""

    base: int = dc.field(lang_kind="arg")
    bits: int = dc.field(lang_kind="arg")
    shift: int = dc.field(lang_kind="arg")

    def __post_init__(self) -> None:
        if self.base < 0 or self.bits < 0 or self.shift < 0:
            raise ValueError("base, bits, and shift must be non-negative")

    def __call__(self, index: ExprLike) -> std.Expr:
        """Apply this swizzle to an index expression."""
        expr = _expr(index)
        if self.bits == 0:
            return expr
        mask = ((1 << self.bits) - 1) << (self.base + self.shift)
        return expr ^ ((expr & mask) >> self.shift)

    def to_byte_swizzle(self, nbytes: int) -> Swizzle:
        """Convert an element swizzle into a byte-offset swizzle."""
        if nbytes <= 0 or nbytes & (nbytes - 1):
            raise ValueError(f"nbytes must be a positive power of two, got {nbytes}")
        return Swizzle(self.base + nbytes.bit_length() - 1, self.bits, self.shift)


@dc.py_class("tilus.RegisterLayout", frozen=True, structural_eq="tree")
class RegisterLayout(Layout, mnemonic="tilus.RegisterLayout"):
    """Register tensor layout."""

    __ffi_dialect_field_collector__ = staticmethod(_collect_register_layout_fields)

    shape: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    mode_shape: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    spatial_modes: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    local_modes: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")

    def __post_init__(self) -> None:
        _shape(self.shape)
        _get_mode_groups(self.shape, self.mode_shape)
        if self.mode_shape and _int_prod(self.mode_shape) != _int_prod(self.shape):
            raise ValueError("mode_shape product must match shape product")
        used_modes: list[int] = []
        for mode in self.spatial_modes:
            if mode < 0:
                continue
            if mode >= len(self.mode_shape):
                raise ValueError(f"spatial mode {mode} is out of range")
            used_modes.append(mode)
        for mode in self.local_modes:
            if mode < 0 or mode >= len(self.mode_shape):
                raise ValueError(f"local mode {mode} is out of range")
            used_modes.append(mode)
        if len(used_modes) != len(set(used_modes)):
            raise ValueError("spatial_modes and local_modes must not reuse modes")

    @property
    def grouped_modes(self) -> tuple[tuple[int, ...], ...]:
        """Return mode groups corresponding to each shape dimension."""
        return _get_mode_groups(self.shape, self.mode_shape)

    @property
    def spatial_shape(self) -> tuple[int, ...]:
        """Return the serialized shape of spatial modes."""
        return tuple(self.mode_shape[mode] if mode >= 0 else -mode for mode in self.spatial_modes)

    @property
    def local_shape(self) -> tuple[int, ...]:
        """Return the serialized shape of local modes."""
        return tuple(self.mode_shape[mode] for mode in self.local_modes)

    @property
    def local_size(self) -> int:
        """Return the number of local elements per worker."""
        return _int_prod(self.mode_shape[mode] for mode in self.local_modes)

    @property
    def spatial_size(self) -> int:
        """Return the number of spatial workers addressed by the layout."""
        return _int_prod(self.spatial_shape)

    @property
    def size(self) -> int:
        """Return the total logical element count."""
        return _int_prod(self.shape)

    def with_shape(self, shape: Sequence[int]) -> RegisterLayout:
        """Return this register layout with a different logical shape."""
        return register_layout(shape, self.mode_shape, self.spatial_modes, self.local_modes)


@dc.py_class("tilus.SharedLayout", frozen=True, structural_eq="tree")
class SharedLayout(Layout, mnemonic="tilus.SharedLayout"):
    """Shared-memory tensor layout."""

    __ffi_dialect_field_collector__ = staticmethod(_collect_shared_layout_fields)

    shape: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    mode_shape: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    mode_strides: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    optional_swizzle: Swizzle | None = dc.field(default=None, lang_kind="attr")

    def __post_init__(self) -> None:
        _shape(self.shape)
        if len(self.mode_shape) != len(self.mode_strides):
            raise ValueError("mode_shape and mode_strides must have the same length")
        if any(stride < 0 for stride in self.mode_strides):
            raise ValueError("mode_strides must be non-negative")
        if _int_prod(self.mode_shape) != _int_prod(self.shape):
            raise ValueError("mode_shape product must match shape product")
        _get_mode_groups(self.shape, self.mode_shape)

    @property
    def swizzle(self) -> Swizzle:
        """Return the swizzle, or raise if this layout is not swizzled."""
        if self.optional_swizzle is None:
            raise ValueError("this layout does not have a swizzle")
        return self.optional_swizzle

    def count_size(self) -> int:
        """Return the minimum shared-memory element count needed by the layout."""
        if not self.mode_shape:
            return _int_prod(self.shape)
        return 1 + sum(
            (extent - 1) * stride for extent, stride in zip(self.mode_shape, self.mode_strides)
        )

    def apply_swizzle(self, swizzle: Swizzle) -> SharedLayout:
        """Return a copy with a swizzle attached."""
        if self.optional_swizzle is not None:
            raise ValueError("chained swizzle is not supported")
        return shared_layout(self.shape, self.mode_shape, self.mode_strides, swizzle)


@dc.py_class("tilus.GlobalLayout", frozen=True, structural_eq="tree")
class GlobalLayout(Layout, mnemonic="tilus.GlobalLayout"):
    """Global-memory tensor layout."""

    __ffi_dialect_field_collector__ = staticmethod(_collect_global_layout_fields)

    shape: tuple[std.Expr, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    size: std.Expr = dc.field(default_factory=lambda: std.IntImm.from_py(1), lang_kind="attr")
    axes: tuple[str, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    offset: std.Expr = dc.field(default_factory=lambda: std.IntImm.from_py(0), lang_kind="attr")

    def __post_init__(self) -> None:
        if len(self.shape) != len(self.axes):
            raise ValueError("shape and axes must have the same rank")
        if len(self.axes) != len(set(self.axes)):
            raise ValueError("axes must be unique")
        for extent in self.shape:
            _integer_expr(extent, "shape extent", positive=True)
        _integer_expr(self.size, "size")
        _integer_expr(self.offset, "offset")


@dc.py_class("tilus.TMemoryLayout", frozen=True, structural_eq="tree")
class TMemoryLayout(Layout, mnemonic="tilus.TMemoryLayout"):
    """Tensor-memory layout."""

    __ffi_dialect_field_collector__ = staticmethod(_collect_tmemory_layout_fields)

    shape: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    column_strides: tuple[int, ...] = dc.field(default_factory=tuple, lang_kind="attr")
    lane_offset: int = dc.field(default=0, lang_kind="attr")

    def __post_init__(self) -> None:
        _shape(self.shape)
        if len(self.shape) != len(self.column_strides):
            raise ValueError("shape and column_strides must have the same rank")
        if any(stride < 0 for stride in self.column_strides):
            raise ValueError("column_strides must be non-negative")
        if len(self.shape) < 2:
            raise ValueError("TMemoryLayout requires at least two dimensions")
        if self.shape[0] not in (32, 64, 128):
            raise ValueError(f"shape[0] must be 32, 64, or 128, got {self.shape[0]}")
        if self.column_strides[0] != 0:
            raise ValueError(f"column_strides[0] must be 0, got {self.column_strides[0]}")


def register_layout(
    shape: Sequence[int],
    mode_shape: Sequence[int] | None = None,
    spatial_modes: Sequence[int] | None = None,
    local_modes: Sequence[int] | None = None,
) -> RegisterLayout:
    """Create a register layout."""
    normalized_shape = _shape(shape)
    normalized_modes = _tuple(mode_shape) or normalized_shape
    normalized_local_modes = (
        tuple(range(len(normalized_modes))) if local_modes is None else _tuple(local_modes)
    )
    return RegisterLayout(
        shape=normalized_shape,
        mode_shape=normalized_modes,
        spatial_modes=_tuple(spatial_modes),
        local_modes=normalized_local_modes,
    )


def register_row_major(*shape: int) -> RegisterLayout:
    """Create a local row-major register layout."""
    return register_layout(shape)


def register_spatial_row_major(*shape: int) -> RegisterLayout:
    """Create a spatial row-major register layout."""
    normalized_shape = _shape(shape)
    return register_layout(
        normalized_shape,
        mode_shape=normalized_shape,
        spatial_modes=tuple(range(len(normalized_shape))),
        local_modes=(),
    )


def shared_layout(
    shape: Sequence[int],
    mode_shape: Sequence[int] | None = None,
    mode_strides: Sequence[int] | None = None,
    optional_swizzle: Swizzle | None = None,
) -> SharedLayout:
    """Create a shared-memory layout."""
    normalized_shape = _shape(shape)
    normalized_modes = _tuple(mode_shape) or normalized_shape
    if mode_strides is None:
        mode_strides = _strides_from_ranks(normalized_modes, tuple(range(len(normalized_modes))))
    return SharedLayout(
        shape=normalized_shape,
        mode_shape=normalized_modes,
        mode_strides=_tuple(mode_strides),
        optional_swizzle=optional_swizzle,
    )


def shared_row_major(*shape: int) -> SharedLayout:
    """Create a row-major shared-memory layout."""
    return shared_layout(shape)


def shared_column_major(*shape: int) -> SharedLayout:
    """Create a column-major shared-memory layout."""
    normalized_shape = _shape(shape)
    ranks = tuple(reversed(range(len(normalized_shape))))
    return shared_layout(
        normalized_shape,
        mode_shape=normalized_shape,
        mode_strides=_strides_from_ranks(normalized_shape, ranks),
    )


def global_layout(shape: Sequence[ExprLike]) -> GlobalLayout:
    """Create a compact row-major global-memory layout."""
    return global_row_major(*shape)


def global_row_major(*shape: ExprLike) -> GlobalLayout:
    """Create a compact row-major global-memory layout."""
    expr_shape = _integer_expr_tuple(shape, "shape extent")
    size = std.IntImm.from_py(1)
    for extent in expr_shape:
        size = size * extent
    return GlobalLayout(
        shape=expr_shape,
        size=size,
        axes=tuple(f"i{axis}" for axis in range(len(expr_shape))),
        offset=std.IntImm.from_py(0),
    )


def global_column_major(*shape: ExprLike) -> GlobalLayout:
    """Create a compact column-major global-memory layout."""
    expr_shape = _integer_expr_tuple(shape, "shape extent")
    size = std.IntImm.from_py(1)
    for extent in expr_shape:
        size = size * extent
    return GlobalLayout(
        shape=expr_shape,
        size=size,
        axes=tuple(f"i{axis}" for axis in reversed(range(len(expr_shape)))),
        offset=std.IntImm.from_py(0),
    )


def tmemory_layout(shape: Sequence[int]) -> TMemoryLayout:
    """Create a row-major tensor-memory layout."""
    normalized_shape = _shape(shape)
    strides = [0] * len(normalized_shape)
    stride = 1
    for axis in reversed(range(1, len(normalized_shape))):
        strides[axis] = stride
        stride *= normalized_shape[axis]
    return TMemoryLayout(shape=normalized_shape, column_strides=tuple(strides), lane_offset=0)


def tmemory_row_major(shape: Sequence[int]) -> TMemoryLayout:
    """Create a row-major tensor-memory layout."""
    return tmemory_layout(shape)


__all__ = [
    "GlobalLayout",
    "Layout",
    "RegisterLayout",
    "SharedLayout",
    "Swizzle",
    "TMemoryLayout",
    "global_column_major",
    "global_layout",
    "global_row_major",
    "prod",
    "register_layout",
    "register_row_major",
    "register_spatial_row_major",
    "shared_column_major",
    "shared_layout",
    "shared_row_major",
    "tmemory_layout",
    "tmemory_row_major",
]
