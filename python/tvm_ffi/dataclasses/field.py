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
"""Field descriptor and ``field()`` helper for Python-defined TVM-FFI types."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import Any, ClassVar

from ..core import MISSING, TypeSchema

# Re-export the stdlib KW_ONLY sentinel so type checkers recognise
# ``_: KW_ONLY`` as a keyword-only boundary rather than a real field.
# dataclasses.KW_ONLY was added in Python 3.10; on older runtimes we
# define a class sentinel (a class, not an instance, so that ``_: KW_ONLY``
# is a valid type annotation for static analysers targeting 3.9).
if sys.version_info >= (3, 10):
    from dataclasses import KW_ONLY
else:

    class KW_ONLY:
        """Sentinel type: annotations after ``_: KW_ONLY`` are keyword-only."""


class Field:
    """Descriptor for a single field in a Python-defined TVM-FFI type.

    When constructed directly (low-level API), *name* and *_ty_schema*
    should be provided.  When returned by :func:`field` (``@py_class``
    workflow), both are ``None`` and filled in by the decorator.

    Parameters
    ----------
    name : str | None
        The field name.  ``None`` when created via :func:`field`; filled
        in by the ``@py_class`` decorator.
    _ty_schema : TypeSchema | None
        Private: the internal :class:`TypeSchema` used by the reflection
        layer.  ``None`` when created via :func:`field`; filled in by
        the ``@py_class`` decorator.  Consumers should use :attr:`type`
        instead.
    type : Any
        The resolved Python annotation (e.g. ``int``, ``list[str]``,
        ``Optional[X]``).  Filled in by the ``@py_class`` / ``@c_class``
        decorator via :func:`typing.get_type_hints`; ``None`` until then
        or when the annotation cannot be resolved.
    default : object
        Default value for the field. Mutually exclusive with *default_factory*.
        ``MISSING`` when not set.
    default_factory : Callable[[], object] | None
        A zero-argument callable that produces the default value.
        Mutually exclusive with *default*.  ``None`` when not set.
    frozen : bool
        Whether this field is read-only after ``__init__``.
    init : bool
        Whether this field appears in the auto-generated ``__init__``.
    repr : bool
        Whether this field appears in ``__repr__`` output.
    hash : bool | None
        Whether this field participates in recursive hashing.
        ``None`` means "follow *compare*" (the native dataclass default).
    compare : bool
        Whether this field participates in recursive comparison.
    kw_only : bool | None
        Whether this field is keyword-only in ``__init__``.
        ``None`` means "inherit from the decorator-level *kw_only* flag".
    structural_eq : str | None
        Structural equality/hashing annotation for this field.  Valid
        values are:

        - ``None`` (default): the field participates normally in
          structural comparison and hashing.
        - ``"ignore"``: the field is excluded from structural equality
          and hashing entirely (e.g. source spans, caches).
        - ``"def"``: the field is a **definition region** that introduces
          new variable bindings.  Free variables encountered inside this
          field are mapped by position, enabling alpha-equivalence.
    doc : str | None
        Optional docstring for the field.
    std_field : str | None
        Name of the std-kind field that this field resolves when a foreign
        dialect reuses a std print builder.
    print : PrintRole | Sequence[PrintRole] | None
        Print role declaration consumed by std-kind print builders.

    """

    __slots__ = (
        "_ty_schema",
        "compare",
        "default",
        "default_factory",
        "doc",
        "frozen",
        "hash",
        "init",
        "kw_only",
        "name",
        "print",
        "repr",
        "std_field",
        "structural_eq",
        "type",
    )
    name: str | None
    _ty_schema: TypeSchema | None
    type: Any
    default: object
    default_factory: Callable[[], object] | None
    frozen: bool
    init: bool
    repr: bool
    hash: bool | None
    compare: bool
    kw_only: bool | None
    structural_eq: str | None
    doc: str | None
    std_field: str | None
    print: tuple[PrintRole, ...] | None

    #: Valid values for the *structural_eq* parameter.
    _VALID_STRUCTURAL_EQ_VALUES: ClassVar[frozenset[str | None]] = frozenset(
        {None, "ignore", "def"}
    )
    #: Metadata key used to lower ``field(std_field=...)`` into reflection.
    _STD_FIELD_METADATA_KEY: ClassVar[str] = "std_field"
    #: Metadata key used to lower ``field(print=...)`` into reflection.
    _PRINT_METADATA_KEY: ClassVar[str] = "print"

    def __init__(  # noqa: PLR0913
        self,
        name: str | None = None,
        _ty_schema: TypeSchema | None = None,
        *,
        default: object = MISSING,
        default_factory: Callable[[], object] | None = MISSING,  # type: ignore[assignment]
        frozen: bool = False,
        init: bool = True,
        repr: bool = True,
        hash: bool | None = True,
        compare: bool = False,
        kw_only: bool | None = False,
        structural_eq: str | None = None,
        doc: str | None = None,
        std_field: str | None = None,
        print: PrintRole | Sequence[PrintRole] | None = None,
    ) -> None:
        # MISSING means "parameter not provided".
        # An explicit None from the user fails the callable() check,
        # matching stdlib dataclasses semantics.
        if default_factory is not MISSING:
            if default is not MISSING:
                raise ValueError("cannot specify both default and default_factory")
            if not callable(default_factory):
                raise TypeError(
                    f"default_factory must be a callable, got {type(default_factory).__name__}"
                )
        if structural_eq not in Field._VALID_STRUCTURAL_EQ_VALUES:
            raise ValueError(
                f"structural_eq must be one of "
                f"{sorted(Field._VALID_STRUCTURAL_EQ_VALUES, key=str)}, "
                f"got {structural_eq!r}"
            )
        if std_field is not None and (not isinstance(std_field, str) or not std_field):
            raise ValueError(f"std_field must be a non-empty string or None, got {std_field!r}")
        self.name = name
        self._ty_schema = _ty_schema
        self.type = None
        self.default = default
        self.default_factory = default_factory
        self.frozen = frozen
        self.init = init
        self.repr = repr
        self.hash = hash
        self.compare = compare
        self.kw_only = kw_only
        self.structural_eq = structural_eq
        self.doc = doc
        self.std_field = std_field
        self.print = _normalize_print_roles(print)

    def dialect_metadata(self) -> dict[str, Any]:
        """Return field-local dialect metadata for reflection."""
        metadata: dict[str, Any] = {}
        if self.std_field is not None:
            metadata[self._STD_FIELD_METADATA_KEY] = self.std_field
        if self.print is not None:
            roles = [role.to_json() for role in self.print]
            metadata[self._PRINT_METADATA_KEY] = roles[0] if len(roles) == 1 else roles
        return metadata


class PrintRole:
    """A field contribution consumed by a std-kind print builder."""

    __slots__ = ("attrs", "kind", "render", "target")

    kind: str
    target: str | None
    render: str | None
    attrs: dict[str, object]

    def __init__(
        self,
        kind: str,
        *,
        target: str | None = None,
        render: str | None = None,
        extra_attrs: dict[str, object] | None = None,
    ) -> None:
        if not isinstance(kind, str) or not kind:
            raise ValueError(f"print role kind must be a non-empty string, got {kind!r}")
        if target is not None and (not isinstance(target, str) or not target):
            raise ValueError(f"print role target must be a non-empty string, got {target!r}")
        if render is not None and (not isinstance(render, str) or not render):
            raise ValueError(f"print role render must be a non-empty string, got {render!r}")
        self.kind = kind
        self.target = target
        self.render = render
        self.attrs = {} if extra_attrs is None else dict(extra_attrs)

    def to_json(self) -> dict[str, object]:
        """Return the JSON-serializable representation stored in reflection."""
        result: dict[str, object] = {"kind": self.kind}
        if self.target is not None:
            result["target"] = self.target
        if self.render is not None:
            result["render"] = self.render
        result.update(self.attrs)
        return result


def _normalize_print_roles(
    value: PrintRole | Sequence[PrintRole] | None,
) -> tuple[PrintRole, ...] | None:
    if value is None:
        return None
    if isinstance(value, PrintRole):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        roles = tuple(value)
        if not roles:
            raise ValueError("print role sequence must not be empty")
        if all(isinstance(role, PrintRole) for role in roles):
            return roles
    raise TypeError("print must be a PrintRole, a non-empty sequence of PrintRole, or None")


def _body_role(kind: str, body: str, *, order: int = 0, render: str | None = None) -> PrintRole:
    if not isinstance(order, int):
        raise TypeError(f"order must be an int, got {type(order).__name__}")
    return PrintRole(kind, target=body, render=render, extra_attrs={"order": order})


def ignore() -> PrintRole:
    """Mark a field as intentionally consumed without printed syntax."""
    return PrintRole("ignore")


def body_prepend(body: str, *, order: int = 0, render: str | None = None) -> PrintRole:
    """Print this field before the named body field."""
    return _body_role("body_prepend", body, order=order, render=render)


def body_append(body: str, *, order: int = 0, render: str | None = None) -> PrintRole:
    """Print this field after the named body field."""
    return _body_role("body_append", body, order=order, render=render)


def body_wrap(body: str, *, order: int = 0, render: str | None = None) -> PrintRole:
    """Wrap the named body field with syntax produced from this field."""
    return _body_role("body_wrap", body, order=order, render=render)


def slot(slot_name: str, *, render: str | None = None, **attrs: object) -> PrintRole:
    """Declare a contribution to a named print-builder slot."""
    if not isinstance(slot_name, str) or not slot_name:
        raise ValueError(f"slot name must be a non-empty string, got {slot_name!r}")
    role_attrs = dict(attrs)
    role_attrs["slot"] = slot_name
    return PrintRole("slot", render=render, extra_attrs=role_attrs)


def call_arg(index: int, *, render: str | None = None) -> PrintRole:
    """Declare that a field contributes to a positional call argument."""
    if not isinstance(index, int) or index < 0:
        raise ValueError(f"call_arg index must be a non-negative int, got {index!r}")
    return slot("call.args", index=index, render=render)


def call_kwarg(name: str, *, render: str | None = None) -> PrintRole:
    """Declare that a field contributes to a named call keyword argument."""
    if not isinstance(name, str) or not name:
        raise ValueError(f"call_kwarg name must be a non-empty string, got {name!r}")
    return slot("call.kwargs", name=name, render=render)


def attrs(*, render: str | None = None) -> PrintRole:
    """Declare that a field contributes an attrs bundle."""
    return slot("attrs", render=render)


def annotation_of(target: str, *, render: str | None = None) -> PrintRole:
    """Declare that a field contributes an annotation to another slot."""
    if target not in {"args", "return"}:
        raise ValueError(f"annotation target must be 'args' or 'return', got {target!r}")
    return slot(f"{target}.annotation", render=render)


def field(  # noqa: PLR0913
    *,
    default: object = MISSING,
    default_factory: Callable[[], object] | None = MISSING,  # type: ignore[assignment]
    frozen: bool = False,
    init: bool = True,
    repr: bool = True,
    hash: bool | None = None,
    compare: bool = True,
    kw_only: bool | None = None,
    structural_eq: str | None = None,
    doc: str | None = None,
    std_field: str | None = None,
    print: PrintRole | Sequence[PrintRole] | None = None,
) -> Any:
    """Customize a field in a ``@py_class``-decorated class.

    Returns a :class:`Field` sentinel whose *name* and *_ty_schema*
    are ``None``.  The ``@py_class`` decorator fills them in later
    from the class annotations.

    The return type is ``Any`` because ``dataclass_transform`` field
    specifiers must be assignable to any annotated type (e.g.
    ``x: int = field(default=0)``).

    Parameters
    ----------
    default
        Default value for the field.  Mutually exclusive with *default_factory*.
    default_factory
        A zero-argument callable that produces the default value.
        Mutually exclusive with *default*.
    frozen
        Whether this field is read-only after ``__init__``.  When True,
        the Python property descriptor has no setter; use the
        ``type(obj).field_name.set(obj, value)`` escape hatch when
        mutation is necessary.
    init
        Whether this field appears in the auto-generated ``__init__``.
    repr
        Whether this field appears in ``__repr__`` output.
    hash
        Whether this field participates in recursive hashing.
        ``None`` (default) means "follow *compare*".
    compare
        Whether this field participates in recursive comparison.
    kw_only
        Whether this field is keyword-only in ``__init__``.
        ``None`` means "inherit from the decorator-level ``kw_only`` flag".
    structural_eq
        Structural equality/hashing annotation. ``None`` (default) means
        the field participates normally. ``"ignore"`` excludes the field
        from structural comparison and hashing. ``"def"`` marks the field
        as a definition region for variable binding.
    doc
        Optional docstring for the field.
    std_field
        Name of the std-kind field that this field resolves when a foreign
        dialect reuses a std print builder.
    print
        Print role declaration consumed by std-kind print builders.

    Returns
    -------
    Any
        A :class:`Field` sentinel recognised by ``@py_class``.

    Examples
    --------
    .. code-block:: python

        @py_class
        class Point(Object):
            x: float
            y: float = field(default=0.0, repr=False)


        @py_class(structural_eq="tree")
        class MyFunc(Object):
            params: Array = field(structural_eq="def")
            body: Expr
            span: Object = field(structural_eq="ignore")

    """
    return Field(
        default=default,
        default_factory=default_factory,
        frozen=frozen,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        kw_only=kw_only,
        structural_eq=structural_eq,
        doc=doc,
        std_field=std_field,
        print=print,
    )
