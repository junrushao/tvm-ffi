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
"""Field descriptor for Python-defined TVM-FFI types."""

from __future__ import annotations

from typing import Any

from ..core import MISSING, TypeSchema


class Field:
    """Descriptor for a single field in a Python-defined TVM-FFI type.

    Parameters
    ----------
    name : str
        The field name (must match the attribute name on the class).
    ty : TypeSchema
        The type schema describing the field's type.
    default : Any
        Default value for the field. Mutually exclusive with *default_factory*.
    default_factory : Callable[[], Any]
        A zero-argument callable that produces the default value.
        Mutually exclusive with *default*.
    init : bool
        Whether this field appears in the auto-generated ``__init__``.
    repr : bool
        Whether this field appears in ``__repr__`` output.
    hash : bool
        Whether this field participates in recursive hashing.
    compare : bool
        Whether this field participates in recursive comparison.
    kw_only : bool
        Whether this field is keyword-only in ``__init__``.
    doc : str | None
        Optional docstring for the field.

    """

    __slots__ = (
        "compare",
        "default",
        "default_factory",
        "doc",
        "hash",
        "init",
        "kw_only",
        "name",
        "repr",
        "ty",
    )
    name: str
    ty: TypeSchema
    default: Any
    default_factory: Any
    init: bool
    repr: bool
    hash: bool
    compare: bool
    kw_only: bool
    doc: str | None

    def __init__(
        self,
        name: str,
        ty: TypeSchema,
        *,
        default: Any = MISSING,
        default_factory: Any = MISSING,
        init: bool = True,
        repr: bool = True,
        hash: bool = True,
        compare: bool = True,
        kw_only: bool = False,
        doc: str | None = None,
    ) -> None:
        if default is not MISSING and default_factory is not MISSING:
            raise ValueError("cannot specify both default and default_factory")
        self.name = name
        self.ty = ty
        self.default = default
        self.default_factory = default_factory
        self.init = init
        self.repr = repr
        self.hash = hash
        self.compare = compare
        self.kw_only = kw_only
        self.doc = doc
