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
"""IR printer and helper functions for text output.

This module provides the ``IRPrinter`` class -- a stateful printer that
converts arbitrary TVM FFI objects into AST nodes while tracking variable
bindings and scoping frames -- together with convenience factory functions
for creating ``Literal`` nodes (``Int``, ``Float``, ``Str``, ``Bool``,
``None_``) and top-level utilities (``to_python``, ``print_python``) for
one-shot rendering.

Examples
--------
.. code-block:: python

    from tvm_ffi.text.ir_printer import IRPrinter, to_python, Int

    # One-shot rendering
    source = to_python(my_obj)

    # Manual AST construction
    node = Int(42)
    print(node.print_python())

"""

# ruff: noqa: D102
# tvm-ffi-stubgen(begin): import-section
# fmt: off
# isort: off
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from collections.abc import MutableMapping, MutableSequence
    from tvm_ffi import Object
    from tvm_ffi.access_path import AccessPath
    from tvm_ffi.text import PrinterConfig
    from tvm_ffi.text.ast import Expr, Id, Stmt
    from typing import Any, Callable
# isort: on
# fmt: on
# tvm-ffi-stubgen(end)

import contextlib
from collections.abc import Generator
from typing import Any, TypeVar

import tvm_ffi
from tvm_ffi import Object
from tvm_ffi.access_path import AccessPath

from ..dataclasses import c_class
from .ast import Expr, Literal, PrinterConfig, Stmt


def Int(value: int) -> Literal:
    """Create an integer ``Literal`` node.

    Parameters
    ----------
    value
        The integer value to wrap.

    Returns
    -------
    Literal
        A ``Literal`` node containing the integer value.

    Examples
    --------
    .. code-block:: python

        Int(42).print_python()  # 42

    """
    return Literal(value)


def Float(value: float) -> Literal:
    """Create a floating-point ``Literal`` node.

    Parameters
    ----------
    value
        The floating-point value to wrap.

    Returns
    -------
    Literal
        A ``Literal`` node containing the floating-point value.

    Examples
    --------
    .. code-block:: python

        Float(3.14).print_python()  # 3.14

    """
    return Literal(value)


def Str(value: str) -> Literal:
    """Create a string ``Literal`` node.

    Parameters
    ----------
    value
        The string value to wrap.

    Returns
    -------
    Literal
        A ``Literal`` node containing the string value.

    Examples
    --------
    .. code-block:: python

        Str("hello").print_python()  # "hello"

    """
    return Literal(value)


def Bool(value: bool) -> Literal:
    """Create a boolean ``Literal`` node.

    Parameters
    ----------
    value
        The boolean value to wrap.

    Returns
    -------
    Literal
        A ``Literal`` node containing the boolean value.

    Examples
    --------
    .. code-block:: python

        Bool(True).print_python()  # True

    """
    return Literal(value)


def None_() -> Literal:
    """Create a ``None`` ``Literal`` node.

    Returns
    -------
    Literal
        A ``Literal`` node containing ``None``.

    Examples
    --------
    .. code-block:: python

        None_().print_python()  # None

    """
    return Literal(None)


@c_class("ffi.text.VarInfo")
class VarInfo(Object):
    """Metadata for a variable tracked by ``IRPrinter``.

    Attributes
    ----------
    name
        The display name assigned to the variable, or ``None`` if
        a name has not yet been chosen (see ``var_def_no_name``).
    creator
        A ``Function`` callable that, when invoked by the printer,
        produces the definition site AST for this variable.

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.VarInfo
    # fmt: off
    name: str | None
    creator: Callable[..., Any]
    if TYPE_CHECKING:
        def __init__(self, _0: str | None, _1: Callable[..., Any], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: str | None, _1: Callable[..., Any], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


FrameType = TypeVar("FrameType", bound=Object)


@c_class("ffi.text.DefaultFrame", init=False)
class DefaultFrame(Object):
    """The default scoping frame used by ``IRPrinter``.

    A frame collects statements emitted while it is active on the printer's
    frame stack. ``DefaultFrame`` is the simplest frame type and simply
    holds a mutable list of ``Stmt`` nodes.

    Attributes
    ----------
    stmts
        The list of statements accumulated in this frame.

    Examples
    --------
    .. code-block:: python

        printer = IRPrinter()
        with printer.with_frame(DefaultFrame()) as frame:
            # ... emit statements ...
            pass
        print(frame.stmts)

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.DefaultFrame
    # fmt: off
    stmts: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, _0: MutableSequence[Stmt], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: MutableSequence[Stmt], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, stmts: list[Stmt] | None = None) -> None:
        if stmts is None:
            stmts = []
        self.__ffi_init__(stmts)


@c_class("ffi.text.IRPrinter", init=False)
class IRPrinter(Object):
    """Stateful printer that converts TVM FFI objects into text-printer AST nodes.

    ``IRPrinter`` manages variable bindings and a stack of scoping frames.
    When called on an object, it dispatches to the object's registered
    printer handler to produce AST nodes, automatically defining and
    referencing variables as needed.

    Attributes
    ----------
    cfg
        The ``PrinterConfig`` controlling output formatting.
    obj2info
        Mapping from IR objects to their ``VarInfo`` metadata.
    defined_names
        Mapping from variable name strings to usage counts
        (used for de-duplication).
    frames
        The current stack of scoping frames.
    frame_vars
        Mapping from frame objects to the set of variables
        defined within that frame.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ir_printer import IRPrinter
        from tvm_ffi.text.ast import PrinterConfig
        from tvm_ffi.access_path import AccessPath

        printer = IRPrinter(PrinterConfig(indent_spaces=4))
        node = printer(my_obj, AccessPath.root())
        print(node.to_python())

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.IRPrinter
    # fmt: off
    cfg: PrinterConfig
    obj2info: MutableMapping[Any, VarInfo]
    defined_names: MutableMapping[str, int]
    frames: MutableSequence[Any]
    frame_vars: MutableMapping[Any, Any]
    if TYPE_CHECKING:
        def __init__(self, _0: PrinterConfig, _1: MutableMapping[Any, VarInfo], _2: MutableMapping[str, int], _3: MutableSequence[Any], _4: MutableMapping[Any, Any], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: PrinterConfig, _1: MutableMapping[Any, VarInfo], _2: MutableMapping[str, int], _3: MutableSequence[Any], _4: MutableMapping[Any, Any], /) -> Object: ...
        def var_is_defined(self, _1: Object, /) -> bool: ...
        def var_def(self, _1: str, _2: Object, _3: Object | None, /) -> Id: ...
        def var_def_no_name(self, _1: Callable[..., Any], _2: Object, _3: Object | None, /) -> None: ...
        def var_remove(self, _1: Object, /) -> None: ...
        def var_get(self, _1: Object, /) -> Expr | None: ...
        def frame_push(self, _1: Object, /) -> None: ...
        def frame_pop(self, /) -> None: ...
        def __call__(self, _1: Any, _2: AccessPath, /) -> Any: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, cfg: PrinterConfig | None = None) -> None:
        if cfg is None:
            cfg = PrinterConfig()
        self.__ffi_init__(cfg, {}, {}, [], {})

    def __call__(self, obj: Any, path: AccessPath) -> Any:
        """Convert *obj* to a text format AST node using this printer's state.

        Parameters
        ----------
        obj
            The TVM FFI object to convert.
        path
            The access path describing how *obj* was reached.

        Returns
        -------
        Any
            The resulting AST node.

        Examples
        --------
        .. code-block:: python

            from tvm_ffi.access_path import AccessPath

            printer = IRPrinter()
            node = printer(my_obj, AccessPath.root())

        """
        info = type(self).__tvm_ffi_type_info__  # type: ignore[attr-defined]
        call_fn = next(m.func for m in info.methods if m.name == "__call__")
        return call_fn(self, obj, path)

    @contextlib.contextmanager
    def with_frame(self, frame: FrameType) -> Generator[FrameType, None, None]:
        """Context manager that pushes *frame* and pops it on exit.

        Any variables defined while the frame is active are associated with
        it and cleaned up when the frame is popped.

        Parameters
        ----------
        frame
            The frame object to activate.

        Yields
        ------
        FrameType
            The same *frame* object, for convenience.

        Examples
        --------
        .. code-block:: python

            printer = IRPrinter()
            with printer.with_frame(DefaultFrame()) as f:
                # statements emitted here go into f.stmts
                pass

        """
        self.frame_push(frame)
        try:
            yield frame
        finally:
            self.frame_pop()


def to_python(obj: Any, cfg: PrinterConfig | None = None) -> str:
    """Convert any TVM FFI object to Python-style source code.

    This is a top-level convenience function that creates a fresh
    ``IRPrinter``, converts *obj*, and returns the rendered string.

    Parameters
    ----------
    obj
        The TVM FFI object to render.
    cfg
        Printer configuration. Uses default settings when ``None``.

    Returns
    -------
    str
        The rendered Python-style source code.

    Examples
    --------
    .. code-block:: python

        source = to_python(my_function)
        print(source)

    """
    _c_to_python = tvm_ffi.get_global_func("ffi.text.ToPython")
    if cfg is None:
        cfg = PrinterConfig()
    return _c_to_python(obj, cfg)


def print_python(
    obj: Any,
    cfg: PrinterConfig | None = None,
) -> None:
    """Print any TVM FFI object as Python-style source code to stdout.

    Convenience wrapper around ``to_python()`` that passes the result
    directly to ``print()``.

    Parameters
    ----------
    obj
        The TVM FFI object to render.
    cfg
        Printer configuration. Uses default settings when ``None``.

    Examples
    --------
    .. code-block:: python

        print_python(my_function)

    """
    print(to_python(obj, cfg=cfg))
