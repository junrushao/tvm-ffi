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
"""Language-module registration for IR dialects.

A *dialect* is a Python module (e.g. ``tvm_ffi.testing.dialect_fixtures``) that
declares ``@py_class`` / ``@c_class`` IR nodes and ends with a call to
:func:`finalize_module`. Finalization walks every IR class, classifies
each into one of the :class:`Tier` paths, and registers placeholder
parser-dispatch handlers under the names that the printer would emit
(``T.prim_func``, ``T.int32``, …). A sibling ``.pyi`` is regenerated
so static type checkers see the registered surface.

This module only addresses **what name to register, not what to
register**: every handler installed here is a placeholder that raises
``NotImplementedError`` if called. Real dispatch bodies land in a
follow-up PR.

Tiers
-----
* :attr:`Tier.MANUAL` — ``__ffi_text_print__`` is registered on the
  class. The user supplies a manual printer and the inverse parser; the
  registry honours their explicit ``@parse_hook`` declarations.
* :attr:`Tier.TRAIT` — ``__ffi_ir_traits__`` is registered (and
  :attr:`Tier.MANUAL` does not apply). Trait-driven; the per-trait rule
  table below picks the registry slot.
* :attr:`Tier.DEFAULT` — neither of the above. Default printing emits
  the class name as a callee, so the registry binds the class name to
  a default parser handler.

The classifier function (:func:`_classify`) is pure and table-driven; it
returns a list of :class:`RegEntry` for each class. ``finalize_module``
collects every entry, applies user overrides (``@parse_hook`` on
module-level functions, plus the kwargs to ``finalize_module``), checks
for duplicates, and writes attributes onto the dialect module.
"""

from __future__ import annotations

import enum
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from . import _dtype
from . import ir_traits as tr
from ._parse_decorators import (
    RESERVED_DICT_SLOTS,
    RESERVED_FN_SLOTS,
    ParseHookSpec,
    get_hook_spec,
    get_slot_field,
)
from .core import _lookup_type_attr
from .dataclasses.py_class import _register_print_prefix
from .pyast import OperationKind

# ---------------------------------------------------------------------------
# Slot-target taxonomy
# ---------------------------------------------------------------------------


# Module-level reserved slot names that hold dicts (sub-keyed by op-kind
# or literal-format string).
_OP_SLOT = "__ffi_parse_op__"
_MAKE_CONST_SLOT = "__ffi_parse_make_const__"


@dataclass(frozen=True)
class RegEntry:
    """One name-binding to install on a dialect module.

    Attributes
    ----------
    target
        The attribute name on the dialect module. For a free name this
        is e.g. ``"prim_func"`` (resulting in ``T.prim_func``); for a
        reserved C0 keyword it's the dunder itself
        (``"__ffi_parse_func__"``).
    handler
        Placeholder callable to install. May be ``None`` for entries
        that only carry a sub-key without a handler (e.g. dtype
        instances that are non-callable).
    sub_key
        For dict-typed slots (``__ffi_parse_op__``,
        ``__ffi_parse_make_const__``), the dict key under which the
        handler lands; for direct-attr slots, ``None``.
    source_class
        The IR class that produced this entry; used in conflict-error
        messages so users can see which classes collide.

    """

    target: str
    handler: Callable[..., Any] | None
    sub_key: Any = None
    source_class: type | None = None


# ---------------------------------------------------------------------------
# Tier detection
# ---------------------------------------------------------------------------


class Tier(enum.Enum):
    """Which registration path a class follows.

    The tier is determined by which TypeAttrColumn entries are
    registered on the class:

    * :attr:`MANUAL` — ``__ffi_text_print__`` is registered. The user
      supplies a hand-written printer + parser; the registry honours
      explicit ``@parse_hook`` declarations and contributes nothing
      automatically.
    * :attr:`TRAIT` — ``__ffi_ir_traits__`` is registered (and
      ``__ffi_text_print__`` is not). Trait-driven; the per-trait rule
      table picks the registry slot.
    * :attr:`DEFAULT` — neither of the above. The registry binds the
      class name as the default callee.
    """

    MANUAL = "manual"
    TRAIT = "trait"
    DEFAULT = "default"


def _tier(cls: type) -> Tier:
    """Return the registration :class:`Tier` for ``cls``.

    Precondition: ``cls`` is a ``@py_class`` / ``@c_class``-decorated
    type (i.e. carries ``__tvm_ffi_type_info__``). The gate lives in
    :func:`_classify`; this helper assumes the check has already run.
    """
    info = cls.__tvm_ffi_type_info__  # type: ignore[attr-defined]
    if _lookup_type_attr(info.type_index, "__ffi_text_print__") is not None:
        return Tier.MANUAL
    if _lookup_type_attr(info.type_index, "__ffi_ir_traits__") is not None:
        return Tier.TRAIT
    return Tier.DEFAULT


def _trait(cls: type) -> tr.IRTraits | None:
    """Return the trait Object on ``cls`` or ``None`` if absent.

    Precondition (same as :func:`_tier`): ``cls`` carries
    ``__tvm_ffi_type_info__``.
    """
    info = cls.__tvm_ffi_type_info__  # type: ignore[attr-defined]
    val = _lookup_type_attr(info.type_index, "__ffi_ir_traits__")
    return val if isinstance(val, tr.IRTraits) else None


# ---------------------------------------------------------------------------
# Placeholders
# ---------------------------------------------------------------------------


def _placeholder(label: str) -> Callable[..., Any]:
    """Build a parser-dispatch placeholder labelled ``label``.

    The returned callable raises :class:`NotImplementedError` when
    invoked. The label appears in the error message and as the
    ``__name__`` so introspection tools can identify the slot.
    """

    def _dispatch(*_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError(
            f"Parser dispatch for {label!r} is not yet implemented; this "
            "build only registers the names. The handler body lands in "
            "a follow-up PR.",
        )

    safe = label.replace(".", "_").replace("-", "_")
    _dispatch.__name__ = f"_parse_{safe}"
    _dispatch.__qualname__ = _dispatch.__name__
    _dispatch.__doc__ = f"Placeholder parser for {label!r}."
    _dispatch.__ffi_parse_placeholder__ = True  # type: ignore[attr-defined]
    return _dispatch


# ---------------------------------------------------------------------------
# Per-trait classification
# ---------------------------------------------------------------------------


def _label(cls: type, suffix: str) -> str:
    """Build a placeholder label like ``"mini.tir.For:for"`` for diagnostics."""
    return f"{cls.__module__}.{cls.__name__}:{suffix}"


def _kind_literal(text_printer_kind: str | None) -> str | None:
    """Return ``text_printer_kind`` if it is a literal name, else ``None``.

    A trait can carry ``text_printer_kind`` as either:

    * a literal callee like ``"prim_func"`` or ``"T.serial"`` — usable
      as-is for registration (we strip the dialect prefix); or
    * a ``$method:`` / ``$global:`` ref — opaque at registration time,
      so the user must supply ``@parse_hook`` overrides explicitly.
    """
    if text_printer_kind is None:
        return None
    if text_printer_kind.startswith("$"):
        return None
    # ``"T.serial"`` → ``"serial"``; bare names pass through.
    if "." in text_printer_kind:
        return text_printer_kind.rsplit(".", 1)[1]
    return text_printer_kind


def _classify_binop(cls: type, t: tr.BinOpTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    label = _label(cls, "binop")
    if tier is Tier.TRAIT:
        # Map ``op`` → OperationKind. Unknown ops (custom strings) drop
        # the op-dict entry and rely solely on text_printer_func_name.
        op_kind = _BINOP_BY_OP.get(t.op)
        out: list[RegEntry] = []
        if op_kind is not None:
            out.append(
                RegEntry(_OP_SLOT, _placeholder(label), op_kind, cls),
            )
        if t.text_printer_func_name is not None:
            name = _kind_literal(t.text_printer_func_name)
            if name is not None:
                out.append(
                    RegEntry(name, _placeholder(label), None, cls),
                )
        return out
    # Tier.MANUAL — fall through to user @parse_hook overrides; the
    # classifier contributes nothing.
    return []


def _classify_unaryop(cls: type, t: tr.UnaryOpTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        op_kind = _UNARYOP_BY_OP.get(t.op)
        if op_kind is None:
            return []
        return [RegEntry(_OP_SLOT, _placeholder(_label(cls, "unop")), op_kind, cls)]
    return []


def _classify_value(cls: type, t: tr.ValueTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        return [
            RegEntry(
                "__ffi_parse_make_var__",
                _placeholder(_label(cls, "make_var")),
                None,
                cls,
            ),
        ]
    return []


def _classify_literal(cls: type, t: tr.LiteralTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        fmt = t.format if t.format is not None else "default"
        return [
            RegEntry(
                _MAKE_CONST_SLOT,
                _placeholder(_label(cls, f"make_const[{fmt}]")),
                fmt,
                cls,
            ),
        ]
    return []


def _classify_call(cls: type, t: tr.CallTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        # Prefer ``text_printer_callee`` (literal); fall back to ``op``;
        # if neither is a literal, the user must override via @parse_hook.
        callee = (
            _kind_literal(t.text_printer_callee)
            if t.text_printer_callee is not None
            else _kind_literal(t.op)
        )
        if callee is not None:
            return [RegEntry(callee, _placeholder(_label(cls, "call")), None, cls)]
        return []
    return []


def _classify_load(cls: type, t: tr.LoadTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        return [
            RegEntry(
                "__ffi_parse_load__",
                _placeholder(_label(cls, "load")),
                None,
                cls,
            ),
        ]
    return []


def _classify_store(cls: type, t: tr.StoreTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        return [
            RegEntry(
                "__ffi_parse_store__",
                _placeholder(_label(cls, "store")),
                None,
                cls,
            ),
        ]
    return []


def _classify_assign(cls: type, t: tr.AssignTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        kind = _kind_literal(t.text_printer_kind)
        if kind is not None:
            return [RegEntry(kind, _placeholder(_label(cls, "assign")), None, cls)]
        return [
            RegEntry(
                "__ffi_parse_assign__",
                _placeholder(_label(cls, "assign")),
                None,
                cls,
            ),
        ]
    return []


def _classify_assert(cls: type, t: tr.AssertTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        return [
            RegEntry(
                "__ffi_parse_assert__",
                _placeholder(_label(cls, "assert")),
                None,
                cls,
            ),
        ]
    return []


def _classify_return(cls: type, t: tr.ReturnTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        return [
            RegEntry(
                "__ffi_parse_return__",
                _placeholder(_label(cls, "return")),
                None,
                cls,
            ),
        ]
    return []


def _classify_func(cls: type, t: tr.FuncTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        kind = _kind_literal(t.text_printer_kind)
        if kind is not None:
            return [RegEntry(kind, _placeholder(_label(cls, "func")), None, cls)]
        return [
            RegEntry(
                "__ffi_parse_func__",
                _placeholder(_label(cls, "func")),
                None,
                cls,
            ),
        ]
    return []


def _classify_for(cls: type, t: tr.ForTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        # Three-way:
        #   * ``text_printer_kind`` is None  → bind ``__ffi_parse_for__``
        #     so ``finalize_module(iter_aliases={"range": "T.serial"})``
        #     can install the ``range`` alias on top.
        #   * literal kind (``"serial"`` or ``"T.serial"``) → register
        #     that name directly.
        #   * opaque ``$method:`` / ``$global:`` ref → emit nothing; the
        #     user must enumerate kinds with
        #     ``@parse_hook(["serial", "parallel", ...])``.
        if t.text_printer_kind is None:
            return [
                RegEntry(
                    "__ffi_parse_for__",
                    _placeholder(_label(cls, "for")),
                    None,
                    cls,
                ),
            ]
        kind = _kind_literal(t.text_printer_kind)
        if kind is not None:
            return [RegEntry(kind, _placeholder(_label(cls, "for")), None, cls)]
        return []
    return []


def _classify_with(cls: type, t: tr.WithTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        # Mirrors ``_classify_for``:
        #   * None              → reserved ``__ffi_parse_with__`` slot.
        #   * literal kind       → register that name directly.
        #   * ``$method`/$global → empty; user supplies ``@parse_hook``.
        if t.text_printer_kind is None:
            return [
                RegEntry(
                    "__ffi_parse_with__",
                    _placeholder(_label(cls, "with")),
                    None,
                    cls,
                ),
            ]
        kind = _kind_literal(t.text_printer_kind)
        if kind is not None:
            return [RegEntry(kind, _placeholder(_label(cls, "with")), None, cls)]
        return []
    return []


def _classify_while(cls: type, t: tr.WhileTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        return [
            RegEntry(
                "__ffi_parse_while__",
                _placeholder(_label(cls, "while")),
                None,
                cls,
            ),
        ]
    return []


def _classify_if(cls: type, t: tr.IfTraits, tier: Tier) -> list[RegEntry]:
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        return [
            RegEntry(
                "__ffi_parse_if__",
                _placeholder(_label(cls, "if")),
                None,
                cls,
            ),
        ]
    return []


def _classify_prim_ty(cls: type, t: tr.PrimTyTraits, tier: Tier) -> list[RegEntry]:
    # Per design: PrimTy classes don't claim a single registry name —
    # the dtype handles (T.int32, T.float32, …) handle that surface,
    # registered separately in finalize_module(). DEFAULT-tier classes
    # still land their class name so a default Call(...) parse can
    # resolve.
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    return []


def _classify_type_named(cls: type, tier: Tier, name: str) -> list[RegEntry]:
    """Apply the common per-type-trait shape: register one fixed name.

    Used by ``BufferTy`` / ``TensorTy`` / ``FuncTy`` / ``TupleTy`` /
    ``ShapeTy``: each trait registers exactly one callee name.
    """
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    if tier is Tier.TRAIT:
        return [RegEntry(name, _placeholder(_label(cls, name.lower())), None, cls)]
    return []


def _class_name_entry(cls: type) -> RegEntry:
    """DEFAULT-tier / fallback: register the class name as the callee target."""
    return RegEntry(cls.__name__, _placeholder(_label(cls, "default")), None, cls)


# Trait → classifier dispatch table. Order matters when subclasses are
# present (more specific traits should appear before bases); since the
# trait hierarchy is shallow we just match on ``type(...) is`` exactly.
_CLASSIFIERS: list[tuple[type, Callable[..., list[RegEntry]]]] = [
    (tr.BinOpTraits, _classify_binop),
    (tr.UnaryOpTraits, _classify_unaryop),
    (tr.ValueTraits, _classify_value),
    (tr.LiteralTraits, _classify_literal),
    (tr.CallTraits, _classify_call),
    (tr.LoadTraits, _classify_load),
    (tr.StoreTraits, _classify_store),
    (tr.AssignTraits, _classify_assign),
    (tr.AssertTraits, _classify_assert),
    (tr.ReturnTraits, _classify_return),
    (tr.FuncTraits, _classify_func),
    (tr.ForTraits, _classify_for),
    (tr.WithTraits, _classify_with),
    (tr.WhileTraits, _classify_while),
    (tr.IfTraits, _classify_if),
    (tr.PrimTyTraits, _classify_prim_ty),
    (tr.TensorTyTraits, lambda c, _t, ti: _classify_type_named(c, ti, "Tensor")),
    (tr.BufferTyTraits, lambda c, _t, ti: _classify_type_named(c, ti, "Buffer")),
    (tr.FuncTyTraits, lambda c, _t, ti: _classify_type_named(c, ti, "FuncType")),
    (tr.TupleTyTraits, lambda c, _t, ti: _classify_type_named(c, ti, "Tuple")),
    (tr.ShapeTyTraits, lambda c, _t, ti: _classify_type_named(c, ti, "Shape")),
]


# Mapping from ``BinOpTraits.op`` strings to ``OperationKind`` values.
# Only kinds the printer would render via the OperationAST sugar path
# qualify; custom op strings (handled via ``text_printer_func_name``)
# don't get a ``__ffi_parse_op__`` slot.
_BINOP_BY_OP: dict[str, int] = {
    "+": OperationKind.Add,
    "-": OperationKind.Sub,
    "*": OperationKind.Mult,
    "/": OperationKind.Div,
    "//": OperationKind.FloorDiv,
    "%": OperationKind.Mod,
    "**": OperationKind.Pow,
    "<<": OperationKind.LShift,
    ">>": OperationKind.RShift,
    "&": OperationKind.BitAnd,
    "|": OperationKind.BitOr,
    "^": OperationKind.BitXor,
    "<": OperationKind.Lt,
    "<=": OperationKind.LtE,
    "==": OperationKind.Eq,
    "!=": OperationKind.NotEq,
    ">": OperationKind.Gt,
    ">=": OperationKind.GtE,
    "and": OperationKind.And,
    "or": OperationKind.Or,
    "@": OperationKind.MatMult,
}

_UNARYOP_BY_OP: dict[str, int] = {
    "-": OperationKind.USub,
    "+": OperationKind.UAdd,
    "~": OperationKind.Invert,
    "not": OperationKind.Not,
}


def _classify(cls: type) -> list[RegEntry]:
    """Top-level classifier: dispatch on the class's tier and trait.

    Returns ``[]`` for any class that is not a ``@py_class`` /
    ``@c_class`` (i.e. lacks ``__tvm_ffi_type_info__``) — finalize_module
    has no business registering names for non-FFI types. The gate lives
    here so :func:`_tier` and :func:`_trait` can stay lean.
    """
    if getattr(cls, "__tvm_ffi_type_info__", None) is None:
        return []
    tier = _tier(cls)
    if tier is Tier.MANUAL:
        # MANUAL tier contributes no auto-registered entries; the
        # user's ``@parse_hook`` decorations land them.
        return []
    if tier is Tier.DEFAULT:
        return [_class_name_entry(cls)]
    # tier is Tier.TRAIT
    trait = _trait(cls)
    if trait is None:
        # Defensive: TRAIT was selected only because __ffi_ir_traits__
        # was set, but the value isn't a trait Object. Fall through to
        # the default-callee path.
        return [_class_name_entry(cls)]
    for trait_cls, classifier in _CLASSIFIERS:
        if type(trait) is trait_cls:
            return classifier(cls, trait, tier)
    # Unknown trait subclass — treat as default.
    return [_class_name_entry(cls)]


# ---------------------------------------------------------------------------
# Dtype handle (the multi-mode T.int32 surface)
# ---------------------------------------------------------------------------


@dataclass
class _DtypeHandle:
    """Multi-mode dispatcher for a single dtype name on a dialect module.

    ``T.int32`` evaluates to a ``_DtypeHandle`` whose ``.dtype`` is the
    underlying :class:`tvm_ffi.dtype`. Calling it routes:

    * ``T.int32(var_name="x")`` → ``__ffi_parse_make_var__`` placeholder
    * ``T.int32(value=42)``     → ``__ffi_parse_make_const__["int"]``
      (or ``["float"]`` / ``["bool"]`` based on the dtype kind)
    * ``T.int32()``             → returns the handle itself (acts as a
      bare ``PrimTy`` placeholder)

    All routes are placeholders in this PR — they raise
    ``NotImplementedError``. The structure exists so the registered
    name surface matches what the printer emits.
    """

    dtype: Any  # tvm_ffi.dtype instance
    name: str  # canonical dtype string (e.g. "int32")
    module: Any = None  # set by finalize_module after registration

    def __call__(self, *args: Any, var_name: Any = None, value: Any = None, **kw: Any) -> Any:
        if var_name is not None:
            handler = _module_attr(self.module, "__ffi_parse_make_var__")
            return handler(self.dtype, var_name=var_name, **kw)
        if value is not None:
            const_dict = _module_attr(self.module, "__ffi_parse_make_const__")
            fmt = _dtype_const_format(self.name)
            handler = const_dict.get(fmt) if isinstance(const_dict, dict) else None
            if handler is None:
                raise NotImplementedError(
                    f"No __ffi_parse_make_const__[{fmt!r}] handler "
                    f"registered on dialect for dtype {self.name!r}.",
                )
            return handler(self.dtype, value=value, **kw)
        if args or kw:
            raise TypeError(
                f"{self.name}: pass exactly one of var_name=... or "
                "value=...; positional args not accepted.",
            )
        return self  # bare PrimTy reference

    def __repr__(self) -> str:
        return f"<dtype handle T.{self.name}>"


def _module_attr(module: Any, name: str) -> Any:
    """Look up a parser-protocol slot, raising if unset."""
    val = getattr(module, name, None)
    if val is None:
        raise NotImplementedError(
            f"Dialect module {getattr(module, '__name__', '?')!r} has no {name!r} registered.",
        )
    return val


def _dtype_const_format(dtype_name: str) -> str:
    """Map a dtype string to its LiteralTraits-format key."""
    if dtype_name == "bool":
        return "bool"
    if dtype_name.startswith(("int", "uint")):
        return "int"
    return "float"


# ---------------------------------------------------------------------------
# Default dtype set
# ---------------------------------------------------------------------------


#: The dtypes registered on every dialect by default. Mirrors the
#: literal block in :mod:`tvm_ffi._dtype` (lines 331-351).
DEFAULT_DTYPE_NAMES: tuple[str, ...] = (
    "bool",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "float16",
    "float32",
    "float64",
    "bfloat16",
    "float8_e4m3fn",
    "float8_e4m3fnuz",
    "float8_e5m2",
    "float8_e5m2fnuz",
    "float8_e8m0fnu",
    "float4_e2m1fnx2",
)


# ---------------------------------------------------------------------------
# Conflict-resolved registry
# ---------------------------------------------------------------------------


@dataclass
class _Registry:
    """Mutable accumulator collecting :class:`RegEntry` rows by target.

    Each binding tracks whether it came from a user override
    (``@parse_hook`` at module scope) or from the classifier; the latter
    raises on duplicate, the former silently shadows future classifier
    entries for the same slot.
    """

    # Map from ``target`` to either:
    # * a single RegEntry (no sub-key) — for free-name and reserved-fn slots
    # * a dict[sub_key, RegEntry] — for the two reserved-dict slots
    bindings: dict[str, Any] = field(default_factory=dict)
    # Set of (target, sub_key) pairs that came from user overrides.
    overridden: set[tuple[str, Any]] = field(default_factory=set)

    def add(self, entry: RegEntry, *, override: bool = False) -> None:
        target = entry.target
        key = (target, entry.sub_key)
        if target in RESERVED_DICT_SLOTS:
            sub = self.bindings.setdefault(target, {})
            if not isinstance(sub, dict):
                raise _conflict(
                    target,
                    None,
                    sub.source_class if isinstance(sub, RegEntry) else None,
                    entry.source_class,
                )
            existing = sub.get(entry.sub_key)
            if existing is not None:
                if override and key in self.overridden:
                    # Two ``@parse_hook`` overrides claiming the same
                    # slot — unambiguously a user error.
                    raise _override_conflict(target, entry.sub_key, existing, entry)
                if not override and key in self.overridden:
                    # User override already claimed this slot; classifier
                    # silently steps aside.
                    return
                if not override:
                    raise _conflict(
                        target,
                        entry.sub_key,
                        existing.source_class,
                        entry.source_class,
                    )
            sub[entry.sub_key] = entry
            if override:
                self.overridden.add(key)
            return
        existing = self.bindings.get(target)
        if existing is not None:
            if override and key in self.overridden:
                # Two ``@parse_hook`` overrides on the same target.
                raise _override_conflict(target, None, existing, entry)
            if not override and key in self.overridden:
                return  # user override wins; skip classifier entry
            if not override:
                existing_cls = existing.source_class if isinstance(existing, RegEntry) else None
                raise _conflict(target, None, existing_cls, entry.source_class)
        self.bindings[target] = entry
        if override:
            self.overridden.add(key)


def _conflict(
    target: str,
    sub_key: Any,
    cls_a: type | None,
    cls_b: type | None,
) -> RuntimeError:
    sub = f"[{sub_key!r}]" if sub_key is not None else ""
    a = cls_a.__name__ if cls_a is not None else "<unknown>"
    b = cls_b.__name__ if cls_b is not None else "<unknown>"
    return RuntimeError(
        f"finalize_module: duplicate registration for {target}{sub} "
        f"(claimed by both {a} and {b}). Resolve by passing an explicit "
        f"override into finalize_module(...) or decorating a manual "
        f"parser with @parse_hook.",
    )


def _override_conflict(
    target: str,
    sub_key: Any,
    existing: RegEntry,
    incoming: RegEntry,
) -> RuntimeError:
    """Two ``@parse_hook`` decorators claim the same slot — user error.

    Identifies the colliding functions by ``__qualname__`` so the user
    can find both call-sites in the dialect file.
    """
    sub = f"[{sub_key!r}]" if sub_key is not None else ""
    a = getattr(existing.handler, "__qualname__", "<unknown fn>")
    b = getattr(incoming.handler, "__qualname__", "<unknown fn>")
    return RuntimeError(
        f"finalize_module: @parse_hook slot {target}{sub} is claimed by "
        f"both {a!r} and {b!r}. Each registry slot can carry at most one "
        "@parse_hook override.",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def finalize_module(
    module_name: str,
    prefix: str,
    *,
    default_dtypes: dict[type, Any] | None = None,
    extra_dtypes: tuple[str, ...] | frozenset[str] | None = None,
    iter_aliases: dict[str, str] | None = None,
    auto_stub: bool = True,
) -> None:
    """Finalize a dialect module by registering parser-dispatch names.

    Walks ``sys.modules[module_name]`` for ``@py_class`` / ``@c_class``
    decorated IR types, classifies each into a :class:`Tier`, and installs
    placeholder dispatch handlers on the module. Honours
    ``@parse_hook``-decorated module-level functions as explicit
    overrides. Each FFI class also gets the dialect's printer prefix
    registered as ``__ffi_print_prefix__`` (so the C++ printer renders
    ``T.prim_func``, ``R.func`` etc. without a hard-coded prefix). After
    registration, the dtype handle surface (``T.int32``, …) is installed
    and an optional sibling ``.pyi`` stub is regenerated.

    Parameters
    ----------
    module_name
        Fully-qualified module name (``__name__`` from the dialect
        file's last line).
    prefix
        The dialect's printer prefix (e.g. ``"T"`` for tir, ``"R"`` for
        relax). Registered onto every FFI-decorated class in this
        module via ``__ffi_print_prefix__``; classes that already
        declare the attribute in their body are left alone.
    default_dtypes
        Mapping from Python builtin type (``int``, ``float``, ``bool``)
        to the dtype name that should accept un-annotated values of
        that type. The classifier honours these as the dtype that
        backs ``__ffi_parse_make_const__`` for the corresponding
        format. Default: ``{int: "int32", float: "float32", bool: "bool"}``.
    extra_dtypes
        Extra dtype names to register beyond
        :data:`DEFAULT_DTYPE_NAMES`. Each name must be parseable as a
        :class:`tvm_ffi.dtype`.
    iter_aliases
        Mapping like ``{"range": "T.serial"}`` — installs ``range`` (or
        any other Python builtin name) as an alias for an existing
        registered for-loop kind. Used to make ``for i in range(...)``
        parse as the dialect's default for-loop kind.
    auto_stub
        When ``True`` (default), regenerate the sibling ``.pyi`` stub
        listing every registered name on this module.

    Raises
    ------
    RuntimeError
        On any duplicate registration (two classes claiming the same
        slot without an explicit override).
    KeyError
        If ``module_name`` is not in ``sys.modules`` (the dialect file
        must have been imported before its own ``finalize_module()``
        call returns).

    Notes
    -----
    Every registered handler is a placeholder raising
    :class:`NotImplementedError`. This function only addresses **what
    name to register**, not **what to register**.

    """
    if module_name not in sys.modules:
        raise KeyError(
            f"finalize_module({module_name!r}): module not in sys.modules. "
            "Call this from the dialect file itself (after all "
            "@py_class declarations).",
        )
    module = sys.modules[module_name]

    registry = _Registry()

    # -- 1. printer prefix on every FFI-decorated class --
    # Walk the same set the rest of finalize_module operates on, but
    # filter additionally on ``__ffi_print_prefix__`` already present in
    # ``cls.__dict__`` so an explicit per-class override stays intact.
    for cls in _iter_dataclasses(module):
        if "__ffi_print_prefix__" in cls.__dict__:
            continue
        _register_print_prefix(cls, prefix)

    # -- 2. user @parse_hook overrides at module scope come first --
    user_overrides = _collect_module_hooks(module)
    for entry in user_overrides:
        registry.add(entry, override=True)

    # -- 3. classify every IR class in the module --
    for cls in _iter_dataclasses(module):
        # The registry silently honours any user overrides already
        # added; classifier entries that collide raise.
        for entry in _classify(cls):
            registry.add(entry)

    # -- 4. install bindings on the module --
    _install_bindings(module, registry)

    # -- 5. dtype handles + default-range alias --
    _install_dtype_handles(module, extra_dtypes or ())
    _install_iter_aliases(module, iter_aliases or {})
    _install_default_dtypes(module, default_dtypes)

    # -- 6. parse-slot inverses on tier-2 classes --
    _attach_parse_slots(module)

    # -- 6. optional .pyi regeneration --
    if auto_stub:
        # Local import to break the cycle: dialect_stubgen imports
        # _DtypeHandle / DEFAULT_DTYPE_NAMES from this module.
        from .stub.dialect_stubgen import write_dialect_stub  # noqa: PLC0415

        write_dialect_stub(module)


# ---------------------------------------------------------------------------
# Module walking
# ---------------------------------------------------------------------------


def _iter_dataclasses(module: Any) -> list[type]:
    """Return every ``@py_class`` / ``@c_class``-decorated type owned by ``module``.

    Foreign re-exports (classes whose ``__module__`` is different from
    the target) are skipped — only types declared in this dialect.
    The own-``__dict__`` check on ``__tvm_ffi_type_info__`` excludes
    undecorated subclasses that merely inherit the marker from an FFI
    base — registering attrs on those would clobber the parent's
    TypeAttrColumn entry.
    """
    out: list[type] = []
    target = module.__name__
    seen: set[int] = set()
    for value in module.__dict__.values():
        if not isinstance(value, type):
            continue
        if "__tvm_ffi_type_info__" not in value.__dict__:
            continue
        if not getattr(value, "__tvm_ffi_is_dataclass__", False):
            continue
        if getattr(value, "__module__", None) != target:
            continue
        if id(value) in seen:
            continue
        seen.add(id(value))
        out.append(value)
    return out


def _collect_module_hooks(module: Any) -> list[RegEntry]:
    """Gather entries from every ``@parse_hook``-decorated module-level fn.

    Dedupes by function identity: ``@parse_hook(...)`` fns are typically
    re-installed on the module under each declared name (e.g.
    ``@parse_hook("serial", "parallel")`` ends up at ``module.serial``,
    ``module.parallel``, AND its original definition name). Without
    dedup, a second ``finalize_module`` call would yield the same fn
    multiple times and trip the override-conflict check.
    """
    out: list[RegEntry] = []
    seen: set[int] = set()
    for value in module.__dict__.values():
        spec = get_hook_spec(value)
        if spec is None:
            continue
        if id(value) in seen:
            continue
        seen.add(id(value))
        out.extend(_entries_from_hook(spec, value, source_class=None))
    return out


def _entries_from_hook(
    spec: ParseHookSpec,
    fn: Callable[..., Any],
    *,
    source_class: type | None,
) -> list[RegEntry]:
    """Convert a :class:`ParseHookSpec` to a flat list of :class:`RegEntry`."""
    out: list[RegEntry] = []
    for name in spec.named_callees:
        out.append(RegEntry(name, fn, None, source_class))
    for slot in spec.fn_slots:
        if slot not in RESERVED_FN_SLOTS:
            raise ValueError(
                f"@parse_hook: {slot!r} is not a recognized reserved slot.",
            )
        out.append(RegEntry(slot, fn, None, source_class))
    for op_kind in spec.op_kinds:
        out.append(RegEntry(_OP_SLOT, fn, op_kind, source_class))
    for fmt in spec.make_const_formats:
        out.append(RegEntry(_MAKE_CONST_SLOT, fn, fmt, source_class))
    return out


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------


def _install_bindings(module: Any, registry: _Registry) -> None:
    """Apply every accumulated :class:`RegEntry` as an attribute on ``module``."""
    # Direct attrs and reserved-fn slots
    for target, entry in registry.bindings.items():
        if target in RESERVED_DICT_SLOTS:
            assert isinstance(entry, dict)
            sub_dict = {k: v.handler for k, v in entry.items() if v.handler is not None}
            _set_attr(module, target, sub_dict)
            continue
        assert isinstance(entry, RegEntry)
        if entry.handler is None:
            continue
        _set_attr(module, target, entry.handler)


def _set_attr(module: Any, name: str, value: Any) -> None:
    """Set ``module.<name> = value`` only if ``value`` is fresh.

    User code declared on the module always wins — never overwrite.
    """
    if hasattr(module, name) and getattr(module, name) is not value:
        # Already declared by the user (or a prior finalize call).
        # Skip silently; this is the "user explicit wins" rule.
        existing = getattr(module, name)
        # For dict-typed slots, merge new sub-keys into the existing
        # dict rather than overwriting wholesale.
        if isinstance(existing, dict) and isinstance(value, dict):
            for k, v in value.items():
                existing.setdefault(k, v)
        return
    setattr(module, name, value)


def _install_dtype_handles(module: Any, extended: tuple[str, ...] | frozenset[str]) -> None:
    """Install ``module.<dtype>`` handles for every default + extended dtype."""
    names = list(DEFAULT_DTYPE_NAMES) + [n for n in extended if n not in DEFAULT_DTYPE_NAMES]
    for name in names:
        if hasattr(module, name) and not isinstance(getattr(module, name), _DtypeHandle):
            # User defined it themselves — leave alone.
            continue
        try:
            dt = _dtype.dtype(name)
        except Exception as exc:
            raise ValueError(
                f"finalize_module: cannot construct dtype {name!r}: {exc}",
            ) from exc
        handle = _DtypeHandle(dtype=dt, name=name, module=module)
        setattr(module, name, handle)


def _install_iter_aliases(module: Any, mapping: dict[str, str]) -> None:
    """Install ``range = T.serial`` (or whichever alias the user requested).

    Each entry in ``mapping`` aliases a Python builtin iterator name (key)
    onto an already-registered for-loop kind (value). The value may be a
    bare name (``"serial"``) or a dotted form (``"T.serial"``); the
    dialect prefix is stripped.
    """
    for alias_name, target_path in mapping.items():
        target_name = target_path.rsplit(".", 1)[-1] if "." in target_path else target_path
        if hasattr(module, alias_name):
            continue
        target = getattr(module, target_name, None)
        if target is None:
            raise RuntimeError(
                f"finalize_module: iter_aliases entry {alias_name!r} "
                f"references unknown name {target_path!r}; finalize the "
                "module's main classifier first or check the spelling.",
            )
        setattr(module, alias_name, target)


def _install_default_dtypes(module: Any, mapping: dict[type, Any] | None) -> None:
    """Stash ``default_dtypes`` mapping on the module for downstream parsers.

    The actual mapping is normalized to ``{"int": "int32", ...}`` and
    put on ``module.__ffi_parse_default_dtypes__``.
    """
    canonical: dict[str, str] = {}
    for k, v in (mapping or {int: "int32", float: "float32", bool: "bool"}).items():
        if isinstance(k, type) and isinstance(v, str):
            canonical[k.__name__] = v
        elif isinstance(k, type) and isinstance(v, _DtypeHandle):
            canonical[k.__name__] = v.name
    if not hasattr(module, "__ffi_parse_default_dtypes__"):
        setattr(module, "__ffi_parse_default_dtypes__", canonical)


def _attach_parse_slots(module: Any) -> None:
    """Collect ``@parse_slot`` methods on each tier-2 class for later use.

    The slot routines are stored as a dict on the class as
    ``__ffi_parse_slots__``; the parser PR consumes them when inverting
    a trait field via $method/$global. This walk only runs for
    :attr:`Tier.TRAIT` classes — :attr:`Tier.MANUAL` classes manage
    their own parsing wholesale, and :attr:`Tier.DEFAULT` classes have
    no field-inverse needs.
    """
    for cls in _iter_dataclasses(module):
        if _tier(cls) is not Tier.TRAIT:
            continue
        slots: dict[str, Callable[..., Any]] = {}
        for name in dir(cls):
            value = getattr(cls, name, None)
            field_name = get_slot_field(value)
            if field_name is None or not callable(value):
                continue
            if field_name in slots:
                raise RuntimeError(
                    f"@parse_slot: {cls.__name__} declares two methods for field {field_name!r}",
                )
            slots[field_name] = value
        if slots:
            cls.__ffi_parse_slots__ = slots  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Introspection helpers (used by tests and the stub generator)
# ---------------------------------------------------------------------------


def registered_names(module: Any) -> set[str]:
    """Return every attribute name installed by :func:`finalize_module`.

    Skips Python-special dunders (``__name__``, ``__doc__``, …) and
    user-declared classes; keeps only the parser-dispatch surface plus
    dtype handles plus reserved C0 slots.
    """
    out: set[str] = set()
    for name, value in module.__dict__.items():
        if name.startswith("__") and name.endswith("__"):
            if name in RESERVED_FN_SLOTS or name in RESERVED_DICT_SLOTS:
                out.add(name)
            elif name == "__ffi_parse_default_dtypes__":
                out.add(name)
            continue
        if isinstance(value, _DtypeHandle):
            out.add(name)
            continue
        # Only count placeholder dispatchers we installed.
        if getattr(value, "__ffi_parse_placeholder__", False):
            out.add(name)
            continue
        # User @parse_hook function lives on the module; count it too.
        if get_hook_spec(value) is not None:
            out.add(name)
    return out
