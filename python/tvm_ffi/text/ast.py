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
"""Text printer AST node definitions.

This module defines the abstract syntax tree (AST) used by the text printer to
represent Python-style source code. The hierarchy is:

* ``Node`` -- base class for all AST nodes, providing ``to_python()`` and
  ``print_python()`` methods as well as source-path tracking.
* ``Expr(Node)`` -- base class for expression nodes (literals, identifiers,
  attribute access, indexing, calls, operations, etc.). Supports Python
  operator overloading so that AST fragments can be composed with ``+``,
  ``-``, ``*``, comparison operators, and more.
* ``Stmt(Node)`` -- base class for statement nodes (assignments, control flow,
  function/class definitions, comments, etc.).

Concrete node types correspond closely to the Python AST: ``Literal``, ``Id``,
``Attr``, ``Index``, ``Call``, ``Operation``, ``Lambda``, ``Tuple``, ``List``,
``Dict``, ``Slice`` (expressions) and ``StmtBlock``, ``Assign``, ``If``,
``While``, ``For``, ``With``, ``ExprStmt``, ``Assert``, ``Return``,
``Function``, ``Class``, ``Comment``, ``DocString`` (statements).
"""

# ruff: noqa: D102
# tvm-ffi-stubgen(begin): import-section
# fmt: off
# isort: off
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from collections.abc import MutableSequence
    from tvm_ffi import Object
    from tvm_ffi.access_path import AccessPath
    from typing import Any
# isort: on
# fmt: on
# tvm-ffi-stubgen(end)

from collections.abc import Sequence
from typing import Any

from ..core import Object
from ..dataclasses import c_class
from . import _ffi_api


@c_class("ffi.text.PrinterConfig", init=False)
class PrinterConfig(Object):
    """Configuration for the Python-style text printer.

    Controls formatting behavior such as indentation, line numbering, and
    how free variables and duplicate variable names are handled.

    Attributes
    ----------
    def_free_var
        Whether to automatically define free variables that
        appear in the output. Default ``True``.
    indent_spaces
        Number of spaces per indentation level. Default ``2``.
    print_line_numbers
        If greater than zero, prefix each output line with
        its line number. ``0`` disables line numbers (default).
    num_context_lines
        Number of context lines to show around underlined
        regions when ``path_to_underline`` is set. ``-1`` means show all
        lines (default).
    print_addr_on_dup_var
        When ``True``, append an object address suffix
        to disambiguate variables that share the same name. Default
        ``False``.
    path_to_underline
        A list of ``AccessPath`` instances identifying
        sub-expressions to underline in the printed output. Default
        is an empty list.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import PrinterConfig, Id

        cfg = PrinterConfig(indent_spaces=4, print_line_numbers=1)
        node = Id(name="x")
        print(node.to_python(cfg))

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.PrinterConfig
    # fmt: off
    def_free_var: bool
    indent_spaces: int
    print_line_numbers: int
    num_context_lines: int
    print_addr_on_dup_var: bool
    path_to_underline: MutableSequence[AccessPath]
    if TYPE_CHECKING:
        def __init__(self, _0: bool, _1: int, _2: int, _3: int, _4: bool, _5: MutableSequence[AccessPath], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: bool, _1: int, _2: int, _3: int, _4: bool, _5: MutableSequence[AccessPath], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self,
        def_free_var: bool = True,
        indent_spaces: int = 2,
        print_line_numbers: int = 0,
        num_context_lines: int = -1,
        print_addr_on_dup_var: bool = False,
        path_to_underline: list[AccessPath] | None = None,
    ) -> None:
        """Initialize a PrinterConfig.

        Parameters
        ----------
        def_free_var
            Whether to automatically define free variables. Default ``True``.
        indent_spaces
            Number of spaces per indentation level. Default ``2``.
        print_line_numbers
            If greater than zero, prefix each output line with its line
            number. Default ``0``.
        num_context_lines
            Number of context lines to show around underlined regions.
            ``-1`` means show all lines. Default ``-1``.
        print_addr_on_dup_var
            When ``True``, append an object address suffix to disambiguate
            variables that share the same name. Default ``False``.
        path_to_underline
            A list of ``AccessPath`` instances identifying sub-expressions
            to underline. Default ``None`` (empty list).

        """
        if path_to_underline is None:
            path_to_underline = []
        self.__ffi_init__(
            def_free_var,
            indent_spaces,
            print_line_numbers,
            num_context_lines,
            print_addr_on_dup_var,
            path_to_underline,
        )


@c_class("ffi.text.ast.Node", init=False)
class Node(Object):
    """Base class for all text-printer AST nodes.

    Every AST node carries an optional list of ``source_paths`` that trace
    the node back to the original IR object it was derived from. The two
    main entry points for rendering are ``to_python()`` (returns a string)
    and ``print_python()`` (prints to stdout).

    Attributes
    ----------
    source_paths
        Access paths linking this node to the original IR
        objects it represents. Default is an empty list.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Id

        node = Id(name="x")
        source = node.to_python()  # "x"
        node.print_python()  # prints "x" to stdout

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Node
    # fmt: off
    source_paths: MutableSequence[AccessPath]
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
    if TYPE_CHECKING:
        def __ffi_shallow_copy__(self, /) -> Object: ...
        def to_python(self, _1: PrinterConfig, /) -> str: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def to_python(self, config: PrinterConfig | None = None) -> str:
        """Render this AST node as Python-style source code.

        Parameters
        ----------
        config
            Printer configuration. Uses default settings when ``None``.

        Returns
        -------
        source
            The rendered source code as a string.

        Examples
        --------
        .. code-block:: python

            from tvm_ffi.text.ast import Id

            node = Id(name="my_var")
            node.to_python()  # "my_var"

        """
        if config is None:
            config = PrinterConfig()
        return _ffi_api.DocToPythonScript(self, config)

    def print_python(
        self,
        config: PrinterConfig | None = None,
    ) -> None:
        """Print this AST node as Python-style source code to stdout.

        Convenience wrapper around ``to_python()`` that passes the result
        directly to ``print()``.

        Parameters
        ----------
        config
            Printer configuration. Uses default settings when ``None``.

        """
        if config is None:
            config = PrinterConfig()
        print(self.to_python(config))

    def add_path(self, path: Any) -> Node:
        """Append a source path to this node and return the node itself.

        This allows chaining, e.g. ``node.add_path(p1).add_path(p2)``.

        Parameters
        ----------
        path
            The access path to append.

        Returns
        -------
        self
            ``self``, for fluent chaining.

        """
        self.source_paths.append(path)
        return self


@c_class("ffi.text.ast.Expr", init=False)
class Expr(Node):
    """Base class for expression AST nodes.

    ``Expr`` extends ``Node`` with Python operator overloading and builder
    methods so that AST fragments can be composed using natural syntax:

    * **Arithmetic**: ``+``, ``-``, ``*``, ``/``, ``//``, ``%``, ``**``
    * **Bitwise**: ``&``, ``|``, ``^``, ``~``, ``<<``, ``>>``
    * **Comparison**: ``<``, ``<=``, ``>``, ``>=``, ``.eq()``, ``.ne()``
    * **Logical**: ``.logical_and()``, ``.logical_or()``
    * **Ternary**: ``.if_then_else(then, else_)``
    * **Access**: ``.attr("name")``, ``.index([...])``, ``[...]``
    * **Calls**: ``.call(*args)``, ``.call_kw(args, keys, values)``

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Id, Literal

        x = Id(name="x")
        y = Id(name="y")
        expr = (x + y).attr("shape").call(Literal(0))
        expr.print_python()  # (x + y).shape(0)

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Expr
    # fmt: off
    source_paths: MutableSequence[AccessPath]
    if TYPE_CHECKING:
        def __ffi_shallow_copy__(self, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __neg__(self) -> Expr:
        return Operation(OperationKind.USub, [self])

    def __invert__(self) -> Expr:
        return Operation(OperationKind.Invert, [self])

    def __add__(self, other: Expr) -> Expr:
        return Operation(OperationKind.Add, [self, other])

    def __sub__(self, other: Expr) -> Expr:
        return Operation(OperationKind.Sub, [self, other])

    def __mul__(self, other: Expr) -> Expr:
        return Operation(OperationKind.Mult, [self, other])

    def __truediv__(self, other: Expr) -> Expr:
        return Operation(OperationKind.Div, [self, other])

    def __floordiv__(self, other: Expr) -> Expr:
        return Operation(OperationKind.FloorDiv, [self, other])

    def __mod__(self, other: Expr) -> Expr:
        return Operation(OperationKind.Mod, [self, other])

    def __pow__(self, other: Expr) -> Expr:
        return Operation(OperationKind.Pow, [self, other])

    def __lshift__(self, other: Expr) -> Expr:
        return Operation(OperationKind.LShift, [self, other])

    def __rshift__(self, other: Expr) -> Expr:
        return Operation(OperationKind.RShift, [self, other])

    def __and__(self, other: Expr) -> Expr:
        return Operation(OperationKind.BitAnd, [self, other])

    def __or__(self, other: Expr) -> Expr:
        return Operation(OperationKind.BitOr, [self, other])

    def __xor__(self, other: Expr) -> Expr:
        return Operation(OperationKind.BitXor, [self, other])

    def __lt__(self, other: Expr) -> Expr:
        return Operation(OperationKind.Lt, [self, other])

    def __le__(self, other: Expr) -> Expr:
        return Operation(OperationKind.LtE, [self, other])

    def __gt__(self, other: Expr) -> Expr:
        return Operation(OperationKind.Gt, [self, other])

    def __ge__(self, other: Expr) -> Expr:
        return Operation(OperationKind.GtE, [self, other])

    def logical_and(self, other: Expr) -> Expr:
        """Build a logical ``and`` operation (``self and other``).

        Python's ``and`` operator cannot be overloaded, so this explicit
        method is provided instead.

        Parameters
        ----------
        other
            The right-hand operand.

        Returns
        -------
        result
            An ``Operation`` node representing ``self and other``.

        """
        return Operation(OperationKind.And, [self, other])

    def logical_or(self, other: Expr) -> Expr:
        """Build a logical ``or`` operation (``self or other``).

        Python's ``or`` operator cannot be overloaded, so this explicit
        method is provided instead.

        Parameters
        ----------
        other
            The right-hand operand.

        Returns
        -------
        result
            An ``Operation`` node representing ``self or other``.

        """
        return Operation(OperationKind.Or, [self, other])

    def if_then_else(self, then: Expr, else_: Expr) -> Expr:
        """Build a ternary conditional expression (``then if self else else_``).

        Parameters
        ----------
        then
            The value when the condition is true.
        else_
            The value when the condition is false.

        Returns
        -------
        result
            An ``Operation`` node representing the ternary expression.

        Examples
        --------
        .. code-block:: python

            from tvm_ffi.text.ast import Id, Literal

            cond = Id(name="flag")
            result = cond.if_then_else(Literal(1), Literal(0))
            result.print_python()  # 1 if flag else 0

        """
        return Operation(OperationKind.IfThenElse, [self, then, else_])

    def eq(self, other: Expr) -> Expr:
        """Build an equality comparison (``self == other``).

        Python's ``__eq__`` is not overloaded to preserve standard object
        identity semantics, so this explicit method is provided instead.

        Parameters
        ----------
        other
            The right-hand operand.

        Returns
        -------
        result
            An ``Operation`` node representing ``self == other``.

        """
        return Operation(OperationKind.Eq, [self, other])

    def ne(self, other: Expr) -> Expr:
        """Build an inequality comparison (``self != other``).

        Python's ``__ne__`` is not overloaded to preserve standard object
        identity semantics, so this explicit method is provided instead.

        Parameters
        ----------
        other
            The right-hand operand.

        Returns
        -------
        result
            An ``Operation`` node representing ``self != other``.

        """
        return Operation(OperationKind.NotEq, [self, other])

    def attr(self, name: str) -> Expr:
        """Build an attribute access expression (``self.name``).

        Parameters
        ----------
        name
            The attribute name.

        Returns
        -------
        result
            An ``Attr`` node representing ``self.name``.

        Examples
        --------
        .. code-block:: python

            from tvm_ffi.text.ast import Id

            obj = Id(name="module")
            obj.attr("forward").print_python()  # module.forward

        """
        return Attr(self, name)

    def index(self, indices: MutableSequence[Expr]) -> Expr:
        """Build a subscript/index expression (``self[indices]``).

        Parameters
        ----------
        indices
            A sequence of index expressions.

        Returns
        -------
        result
            An ``Index`` node representing ``self[indices]``.

        Examples
        --------
        .. code-block:: python

            from tvm_ffi.text.ast import Id, Literal

            arr = Id(name="arr")
            arr.index([Literal(0)]).print_python()  # arr[0]

        """
        return Index(self, indices)

    def call(self, *args: Expr) -> Expr:
        """Build a positional-only call expression (``self(args...)``).

        Parameters
        ----------
        *args
            Positional argument expressions.

        Returns
        -------
        result
            A ``Call`` node representing ``self(*args)``.

        Examples
        --------
        .. code-block:: python

            from tvm_ffi.text.ast import Id

            fn = Id(name="relu")
            fn.call(Id(name="x")).print_python()  # relu(x)

        """
        return Call(
            self,
            args,  # ty: ignore[invalid-argument-type]
            [],
            [],
        )

    def call_kw(
        self,
        args: Sequence[Expr],
        kwargs_keys: Sequence[str],
        kwargs_values: Sequence[Expr],
    ) -> Expr:
        """Build a call expression with keyword arguments.

        Renders as ``self(*args, key0=val0, key1=val1, ...)``.

        Parameters
        ----------
        args
            Positional argument expressions.
        kwargs_keys
            Keyword argument names.
        kwargs_values
            Keyword argument value expressions, in the same
            order as *kwargs_keys*.

        Returns
        -------
        result
            A ``Call`` node representing the keyword call.

        Examples
        --------
        .. code-block:: python

            from tvm_ffi.text.ast import Id, Literal

            fn = Id(name="conv2d")
            fn.call_kw(
                args=[Id(name="x")],
                kwargs_keys=["stride"],
                kwargs_values=[Literal(2)],
            ).print_python()  # conv2d(x, stride=2)

        """
        if not isinstance(args, Sequence):
            args = (args,)
        if not isinstance(kwargs_keys, Sequence):
            kwargs_keys = (kwargs_keys,)
        if not isinstance(kwargs_values, Sequence):
            kwargs_values = (kwargs_values,)
        return Call(
            self,
            args,  # ty: ignore[invalid-argument-type]
            kwargs_keys,  # ty: ignore[invalid-argument-type]
            kwargs_values,  # ty: ignore[invalid-argument-type]
        )

    def __getitem__(self, indices: Expr | Sequence[Expr]) -> Expr:
        """Build a subscript expression via Python's ``[]`` syntax.

        Delegates to ``self.index()``, wrapping a single index in a tuple
        if necessary.

        Parameters
        ----------
        indices
            One or more index expressions.

        Returns
        -------
        result
            An ``Index`` node representing ``self[indices]``.

        """
        if isinstance(indices, Sequence):
            return self.index(indices)  # ty: ignore[invalid-argument-type]
        return self.index([indices])


@c_class("ffi.text.ast.Stmt", init=False)
class Stmt(Node):
    """Base class for statement AST nodes.

    Statements represent executable constructs (assignments, loops,
    conditionals, etc.). Every statement may carry an optional trailing
    ``comment`` that is rendered as ``# comment`` after the statement.

    Attributes
    ----------
    comment
        An optional inline comment string. Default ``None``.

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Stmt
    # fmt: off
    source_paths: MutableSequence[AccessPath]
    comment: str | None
    if TYPE_CHECKING:
        def __ffi_shallow_copy__(self, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.StmtBlock")
class StmtBlock(Stmt):
    """A sequence of statements rendered as a block.

    Represents a group of statements that are printed together, typically
    as the body of a function, class, loop, or conditional.

    Attributes
    ----------
    stmts
        The list of statements in this block.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import StmtBlock, ExprStmt, Id

        block = StmtBlock(stmts=[ExprStmt(expr=Id(name="x"))])
        block.print_python()  # x

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.StmtBlock
    # fmt: off
    stmts: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, _0: MutableSequence[Stmt], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: MutableSequence[Stmt], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Literal")
class Literal(Expr):
    """A literal value expression (``42``, ``3.14``, ``"hello"``, ``True``, ``None``).

    Wraps an arbitrary Python value and renders it using its ``repr()``.

    Attributes
    ----------
    value
        The literal Python value.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Literal

        Literal(42).print_python()  # 42
        Literal("hello").print_python()  # "hello"

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Literal
    # fmt: off
    value: Any
    if TYPE_CHECKING:
        def __init__(self, _0: Any, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Any, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Id")
class Id(Expr):
    """An identifier / variable name expression.

    Renders as the bare name string.

    Attributes
    ----------
    name
        The identifier string.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Id

        Id(name="x").print_python()  # x

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Id
    # fmt: off
    name: str
    if TYPE_CHECKING:
        def __init__(self, _0: str, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: str, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Attr")
class Attr(Expr):
    """An attribute access expression (``obj.name``).

    Attributes
    ----------
    obj
        The object expression being accessed.
    name
        The attribute name.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Attr, Id

        Attr(obj=Id(name="self"), name="weight").print_python()  # self.weight

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Attr
    # fmt: off
    obj: Expr
    name: str
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: str, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: str, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Index")
class Index(Expr):
    """A subscript / index expression (``obj[idx0, idx1, ...]``).

    Attributes
    ----------
    obj
        The object expression being indexed.
    idx
        A list of index expressions.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Index, Id, Literal

        Index(obj=Id(name="x"), idx=[Literal(0)]).print_python()  # x[0]

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Index
    # fmt: off
    obj: Expr
    idx: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: MutableSequence[Expr], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: MutableSequence[Expr], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Call")
class Call(Expr):
    """A function call expression (``callee(args..., key=val, ...)``).

    Attributes
    ----------
    callee
        The callable expression.
    args
        Positional argument expressions.
    kwargs_keys
        Keyword argument names.
    kwargs_values
        Keyword argument value expressions, aligned with
        *kwargs_keys*.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Call, Id, Literal

        Call(
            callee=Id(name="f"),
            args=[Literal(1)],
            kwargs_keys=["dim"],
            kwargs_values=[Literal(0)],
        ).print_python()  # f(1, dim=0)

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Call
    # fmt: off
    callee: Expr
    args: MutableSequence[Expr]
    kwargs_keys: MutableSequence[str]
    kwargs_values: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: MutableSequence[Expr], _2: MutableSequence[str], _3: MutableSequence[Expr], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: MutableSequence[Expr], _2: MutableSequence[str], _3: MutableSequence[Expr], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


class OperationKind:
    """Enum-like class defining operation kinds for ``Operation`` nodes.

    Integer constants are grouped into three ranges:

    * **Unary** (``_UnaryStart`` .. ``_UnaryEnd``): ``USub`` (``-x``),
      ``Invert`` (``~x``), ``Not`` (``not x``).
    * **Binary** (``_BinaryStart`` .. ``_BinaryEnd``): arithmetic
      (``Add``, ``Sub``, ``Mult``, ``Div``, ``FloorDiv``, ``Mod``,
      ``Pow``), bitwise (``LShift``, ``RShift``, ``BitAnd``, ``BitOr``,
      ``BitXor``), comparison (``Lt``, ``LtE``, ``Eq``, ``NotEq``,
      ``Gt``, ``GtE``), and logical (``And``, ``Or``).
    * **Special** (``_SpecialStart`` .. ``SpecialEnd``): ``IfThenElse``
      (ternary conditional ``a if cond else b``).

    These constants are used as the ``op`` field of ``Operation`` nodes.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import OperationKind, Operation, Id

        x = Id(name="x")
        y = Id(name="y")
        add_op = Operation(OperationKind.Add, [x, y])
        add_op.print_python()  # x + y

    """

    Undefined = -1
    _UnaryStart = 0
    USub = 1
    Invert = 2
    Not = 3
    UAdd = 4
    _UnaryEnd = 5
    _BinaryStart = 5
    Add = 6
    Sub = 7
    Mult = 8
    Div = 9
    FloorDiv = 10
    Mod = 11
    Pow = 12
    LShift = 13
    RShift = 14
    BitAnd = 15
    BitOr = 16
    BitXor = 17
    Lt = 18
    LtE = 19
    Eq = 20
    NotEq = 21
    Gt = 22
    GtE = 23
    And = 24
    Or = 25
    MatMult = 26
    Is = 27
    IsNot = 28
    In = 29
    NotIn = 30
    _BinaryEnd = 31
    _SpecialStart = 32
    IfThenElse = 33
    ChainedCompare = 34
    Parens = 35
    SpecialEnd = 36


@c_class("ffi.text.ast.Operation")
class Operation(Expr):
    """A unary, binary, or special operation expression.

    The ``op`` field is one of the integer constants defined in
    ``OperationKind``. The ``operands`` list contains one element for
    unary ops, two for binary ops, or three for ``IfThenElse``.

    Attributes
    ----------
    op
        The operation kind (an ``OperationKind`` constant).
    operands
        The operand expressions.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Id, Operation, OperationKind

        x = Id(name="x")
        y = Id(name="y")
        expr = Operation(OperationKind.Add, [x, y])
        expr.print_python()  # x + y

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Operation
    # fmt: off
    op: int
    operands: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, _0: int, _1: MutableSequence[Expr], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: int, _1: MutableSequence[Expr], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Lambda")
class Lambda(Expr):
    """A lambda expression (``lambda args: body``).

    Attributes
    ----------
    args
        The parameter identifiers.
    body
        The body expression.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Lambda, Id

        Lambda(args=[Id(name="x")], body=Id(name="x")).print_python()
        # lambda x: x

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Lambda
    # fmt: off
    args: MutableSequence[Expr]
    body: Expr
    if TYPE_CHECKING:
        def __init__(self, _0: MutableSequence[Expr], _1: Expr, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: MutableSequence[Expr], _1: Expr, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Tuple")
class Tuple(Expr):
    """A tuple expression (``(a, b, c)``).

    Attributes
    ----------
    values
        The element expressions.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Tuple, Literal

        Tuple(values=[Literal(1), Literal(2)]).print_python()  # (1, 2)

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Tuple
    # fmt: off
    values: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, _0: MutableSequence[Expr], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: MutableSequence[Expr], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.List")
class List(Expr):
    """A list expression (``[a, b, c]``).

    Attributes
    ----------
    values
        The element expressions.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import List, Literal

        List(values=[Literal(1), Literal(2)]).print_python()  # [1, 2]

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.List
    # fmt: off
    values: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, _0: MutableSequence[Expr], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: MutableSequence[Expr], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Dict")
class Dict(Expr):
    """A dictionary expression (``{k0: v0, k1: v1, ...}``).

    Attributes
    ----------
    keys
        The key expressions.
    values
        The value expressions, aligned with *keys*.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Dict, Literal

        Dict(
            keys=[Literal("a")],
            values=[Literal(1)],
        ).print_python()  # {"a": 1}

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Dict
    # fmt: off
    keys: MutableSequence[Expr]
    values: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, _0: MutableSequence[Expr], _1: MutableSequence[Expr], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: MutableSequence[Expr], _1: MutableSequence[Expr], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Slice", init=False)
class Slice(Expr):
    """A slice expression (``start:stop:step``).

    All three components are optional. A ``None`` component is omitted
    from the rendered output.

    Attributes
    ----------
    start
        The start expression, or ``None``.
    stop
        The stop expression, or ``None``.
    step
        The step expression, or ``None``.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Slice, Literal

        Slice(start=Literal(0), stop=Literal(10)).print_python()  # 0:10

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Slice
    # fmt: off
    start: Expr | None
    stop: Expr | None
    step: Expr | None
    if TYPE_CHECKING:
        def __init__(self, _0: Expr | None, _1: Expr | None, _2: Expr | None, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr | None, _1: Expr | None, _2: Expr | None, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self,
        start: Expr | None = None,
        stop: Expr | None = None,
        step: Expr | None = None,
    ) -> None:
        """Initialize a Slice expression.

        Parameters
        ----------
        start
            The start expression, or ``None``. Default ``None``.
        stop
            The stop expression, or ``None``. Default ``None``.
        step
            The step expression, or ``None``. Default ``None``.

        """
        self.__ffi_init__(start, stop, step)


@c_class("ffi.text.ast.Assign", init=False)
class Assign(Stmt):
    """An assignment statement (``lhs = rhs`` or ``lhs: annotation = rhs``).

    When ``rhs`` is ``None`` the statement renders as a bare declaration
    (``lhs: annotation``). When ``annotation`` is ``None`` the type
    annotation is omitted.

    Attributes
    ----------
    lhs
        The left-hand-side target expression.
    rhs
        The right-hand-side value expression, or ``None``.
    annotation
        An optional type annotation expression.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Assign, Id, Literal

        Assign(lhs=Id(name="x"), rhs=Literal(42)).print_python()  # x = 42

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Assign
    # fmt: off
    lhs: Expr
    rhs: Expr | None
    annotation: Expr | None
    aug_op: int
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: Expr | None, _2: Expr | None, _3: int, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: Expr | None, _2: Expr | None, _3: int, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self,
        lhs: Expr,
        rhs: Expr | None = None,
        annotation: Expr | None = None,
        aug_op: int = -1,
    ) -> None:
        """Initialize an Assign statement.

        Parameters
        ----------
        lhs
            The left-hand-side target expression.
        rhs
            The right-hand-side value expression, or ``None``.
            Default ``None``.
        annotation
            An optional type annotation expression. Default ``None``.
        aug_op
            Augmented-assignment operator kind (``OperationKind`` value),
            or -1 for plain assignment. Default -1.

        """
        self.__ffi_init__(lhs, rhs, annotation, aug_op)


@c_class("ffi.text.ast.If")
class If(Stmt):
    """An ``if / elif / else`` conditional statement.

    Attributes
    ----------
    cond
        The condition expression.
    then_branch
        Statements executed when the condition is true.
    else_branch
        Statements executed when the condition is false
        (may be empty).

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import If, ExprStmt, Id

        If(
            cond=Id(name="flag"),
            then_branch=[ExprStmt(expr=Id(name="a"))],
            else_branch=[ExprStmt(expr=Id(name="b"))],
        ).print_python()
        # if flag:
        #   a
        # else:
        #   b

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.If
    # fmt: off
    cond: Expr
    then_branch: MutableSequence[Stmt]
    else_branch: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: MutableSequence[Stmt], _2: MutableSequence[Stmt], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: MutableSequence[Stmt], _2: MutableSequence[Stmt], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.While", init=False)
class While(Stmt):
    """A ``while`` loop statement.

    Attributes
    ----------
    cond
        The loop condition expression.
    body
        The loop body statements.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import While, ExprStmt, Id, Literal

        While(
            cond=Id(name="running"),
            body=[ExprStmt(expr=Id(name="step"))],
        ).print_python()
        # while running:
        #   step

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.While
    # fmt: off
    cond: Expr
    body: MutableSequence[Stmt]
    orelse: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: MutableSequence[Stmt], _2: MutableSequence[Stmt], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: MutableSequence[Stmt], _2: MutableSequence[Stmt], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self,
        cond: Expr,
        body: MutableSequence[Stmt],
        orelse: MutableSequence[Stmt] | None = None,
    ) -> None:
        if orelse is None:
            orelse = []
        self.__ffi_init__(cond, body, orelse)


@c_class("ffi.text.ast.For", init=False)
class For(Stmt):
    """A ``for`` loop statement (``for lhs in rhs: body``).

    Attributes
    ----------
    lhs
        The loop variable expression.
    rhs
        The iterable expression.
    body
        The loop body statements.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import For, ExprStmt, Id

        For(
            lhs=Id(name="i"),
            rhs=Id(name="items"),
            body=[ExprStmt(expr=Id(name="process"))],
        ).print_python()
        # for i in items:
        #   process

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.For
    # fmt: off
    lhs: Expr
    rhs: Expr
    body: MutableSequence[Stmt]
    is_async: bool
    orelse: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: Expr, _2: MutableSequence[Stmt], _3: bool, _4: MutableSequence[Stmt], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: Expr, _2: MutableSequence[Stmt], _3: bool, _4: MutableSequence[Stmt], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self,
        lhs: Expr,
        rhs: Expr,
        body: MutableSequence[Stmt],
        is_async: bool = False,
        orelse: MutableSequence[Stmt] | None = None,
    ) -> None:
        if orelse is None:
            orelse = []
        self.__ffi_init__(lhs, rhs, body, is_async, orelse)


@c_class("ffi.text.ast.With", init=False)
class With(Stmt):
    """A ``with`` context-manager statement (``with rhs as lhs: body``).

    When ``lhs`` is ``None``, the ``as lhs`` clause is omitted.

    Attributes
    ----------
    lhs
        The optional target expression (``as`` variable), or ``None``.
    rhs
        The context-manager expression.
    body
        The body statements.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import With, ExprStmt, Id

        With(
            lhs=Id(name="f"),
            rhs=Id(name="open_file"),
            body=[ExprStmt(expr=Id(name="read"))],
        ).print_python()
        # with open_file as f:
        #   read

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.With
    # fmt: off
    lhs: Expr | None
    rhs: Expr
    body: MutableSequence[Stmt]
    is_async: bool
    if TYPE_CHECKING:
        def __init__(self, _0: Expr | None, _1: Expr, _2: MutableSequence[Stmt], _3: bool, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr | None, _1: Expr, _2: MutableSequence[Stmt], _3: bool, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self,
        lhs: Expr | None,
        rhs: Expr,
        body: MutableSequence[Stmt],
        is_async: bool = False,
    ) -> None:
        self.__ffi_init__(lhs, rhs, body, is_async)


@c_class("ffi.text.ast.ExprStmt")
class ExprStmt(Stmt):
    """An expression used as a statement (e.g. a bare function call).

    Attributes
    ----------
    expr
        The expression to evaluate as a statement.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import ExprStmt, Id

        ExprStmt(expr=Id(name="do_something")).print_python()  # do_something

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.ExprStmt
    # fmt: off
    expr: Expr
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Assert", init=False)
class Assert(Stmt):
    """An ``assert`` statement (``assert cond, msg``).

    When ``msg`` is ``None``, only the condition is rendered.

    Attributes
    ----------
    cond
        The condition expression.
    msg
        An optional message expression, or ``None``.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Assert, Id, Literal

        Assert(cond=Id(name="x"), msg=Literal("x must be set")).print_python()
        # assert x, "x must be set"

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Assert
    # fmt: off
    cond: Expr
    msg: Expr | None
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: Expr | None, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: Expr | None, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self,
        cond: Expr,
        msg: Expr | None = None,
    ) -> None:
        """Initialize an Assert statement.

        Parameters
        ----------
        cond
            The condition expression.
        msg
            An optional message expression, or ``None``. Default ``None``.

        """
        self.__ffi_init__(cond, msg)


@c_class("ffi.text.ast.Return")
class Return(Stmt):
    """A ``return`` statement.

    When ``value`` is ``None``, renders as a bare ``return``.

    Attributes
    ----------
    value
        The return value expression, or ``None``.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Return, Literal

        Return(value=Literal(42)).print_python()  # return 42

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Return
    # fmt: off
    value: Expr | None
    if TYPE_CHECKING:
        def __init__(self, _0: Expr | None, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr | None, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Function", init=False)
class Function(Stmt):
    """A ``def`` function definition statement.

    Attributes
    ----------
    name
        The function name identifier.
    args
        The parameter list, each represented as an ``Assign`` node
        (the ``lhs`` is the parameter name; ``annotation`` and ``rhs``
        provide type hints and default values).
    decorators
        Decorator expressions applied above the function.
    return_type
        An optional return-type annotation expression.
    body
        The function body statements.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Function, Assign, Id, Return

        Function(
            name=Id(name="add"),
            args=[
                Assign(lhs=Id(name="a")),
                Assign(lhs=Id(name="b")),
            ],
            decorators=[],
            return_type=None,
            body=[Return(value=Id(name="a") + Id(name="b"))],
        ).print_python()
        # def add(a, b):
        #   return a + b

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Function
    # fmt: off
    name: Id
    args: MutableSequence[Assign]
    decorators: MutableSequence[Expr]
    return_type: Expr | None
    body: MutableSequence[Stmt]
    is_async: bool
    if TYPE_CHECKING:
        def __init__(self, _0: Id, _1: MutableSequence[Assign], _2: MutableSequence[Expr], _3: Expr | None, _4: MutableSequence[Stmt], _5: bool, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Id, _1: MutableSequence[Assign], _2: MutableSequence[Expr], _3: Expr | None, _4: MutableSequence[Stmt], _5: bool, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self,
        name: Id,
        args: MutableSequence[Assign],
        decorators: MutableSequence[Expr],
        return_type: Expr | None,
        body: MutableSequence[Stmt],
        is_async: bool = False,
    ) -> None:
        self.__ffi_init__(name, args, decorators, return_type, body, is_async)


@c_class("ffi.text.ast.Class", init=False)
class Class(Stmt):
    """A ``class`` definition statement.

    Attributes
    ----------
    name
        The class name identifier.
    decorators
        Decorator expressions applied above the class.
    body
        The class body statements.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Class, Id, ExprStmt

        Class(
            name=Id(name="MyClass"),
            decorators=[],
            body=[ExprStmt(expr=Id(name="pass"))],
        ).print_python()
        # class MyClass:
        #   pass

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Class
    # fmt: off
    name: Id
    bases: MutableSequence[Expr]
    decorators: MutableSequence[Expr]
    body: MutableSequence[Stmt]
    kwargs_keys: MutableSequence[str]
    kwargs_values: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, _0: Id, _1: MutableSequence[Expr], _2: MutableSequence[Expr], _3: MutableSequence[Stmt], _4: MutableSequence[str], _5: MutableSequence[Expr], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Id, _1: MutableSequence[Expr], _2: MutableSequence[Expr], _3: MutableSequence[Stmt], _4: MutableSequence[str], _5: MutableSequence[Expr], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self,
        name: Id,
        bases: MutableSequence[Expr] | None = None,
        decorators: MutableSequence[Expr] | None = None,
        body: MutableSequence[Stmt] | None = None,
        kwargs_keys: MutableSequence[str] | None = None,
        kwargs_values: MutableSequence[Expr] | None = None,
    ) -> None:
        if bases is None:
            bases = []
        if decorators is None:
            decorators = []
        if body is None:
            body = []
        if kwargs_keys is None:
            kwargs_keys = []
        if kwargs_values is None:
            kwargs_values = []
        self.__ffi_init__(name, bases, decorators, body, kwargs_keys, kwargs_values)


@c_class("ffi.text.ast.Comment", init=False)
class Comment(Stmt):
    """A standalone ``# comment`` line.

    The ``comment`` field (inherited from ``Stmt``) holds the comment text.
    It is rendered as a full-line comment rather than an inline comment.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import Comment

        Comment("TODO: refactor this").print_python()  # # TODO: refactor this

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Comment
    # fmt: off
    if TYPE_CHECKING:
        def __init__(self, _0: str | None, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: str | None, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, comment: str | None) -> None:
        """Initialize a Comment statement.

        Parameters
        ----------
        comment
            The comment text, or ``None``.

        """
        self.__ffi_init__(comment)


@c_class("ffi.text.ast.DocString", init=False)
class DocString(Stmt):
    r"""A triple-quoted docstring statement.

    Renders as a ``\"\"\"...\"\"\"``. The ``comment`` field (inherited from
    ``Stmt``) holds the docstring text.

    Examples
    --------
    .. code-block:: python

        from tvm_ffi.text.ast import DocString

        DocString("This is a docstring.").print_python()

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.DocString
    # fmt: off
    if TYPE_CHECKING:
        def __init__(self, _0: str | None, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: str | None, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, comment: str | None) -> None:
        """Initialize a DocString statement.

        Parameters
        ----------
        comment
            The docstring text, or ``None``.

        """
        self.__ffi_init__(comment)


@c_class("ffi.text.ast.Set")
class Set(Expr):
    """A set expression (``{a, b, c}``).

    Attributes
    ----------
    values
        The element expressions.

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Set
    # fmt: off
    values: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, _0: MutableSequence[Expr], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: MutableSequence[Expr], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.ComprehensionIter")
class ComprehensionIter(Node):
    """One ``for target in iter [if cond]...`` clause in a comprehension.

    Attributes
    ----------
    target
        The loop variable expression.
    iter
        The iterable expression.
    ifs
        Zero or more filter-condition expressions.

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.ComprehensionIter
    # fmt: off
    target: Expr
    iter: Expr
    ifs: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: Expr, _2: MutableSequence[Expr], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: Expr, _2: MutableSequence[Expr], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


class ComprehensionKind:
    """Enum-like class for comprehension kinds."""

    List = 0
    Set = 1
    Dict = 2
    Generator = 3


@c_class("ffi.text.ast.Comprehension")
class Comprehension(Expr):
    """A comprehension expression.

    Covers list comprehensions (``[elt for ...]``), set comprehensions
    (``{elt for ...}``), dict comprehensions (``{key: value for ...}``),
    and generator expressions (``(elt for ...)``).

    Attributes
    ----------
    kind
        The comprehension kind (a ``ComprehensionKind`` constant).
    elt
        The element expression (or key for dict comprehensions).
    value
        The value expression (only for dict comprehensions; ``None`` otherwise).
    iters
        The list of ``ComprehensionIter`` clauses.

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Comprehension
    # fmt: off
    kind: int
    elt: Expr
    value: Expr | None
    iters: MutableSequence[ComprehensionIter]
    if TYPE_CHECKING:
        def __init__(self, _0: int, _1: Expr, _2: Expr | None, _3: MutableSequence[ComprehensionIter], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: int, _1: Expr, _2: Expr | None, _3: MutableSequence[ComprehensionIter], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Yield", init=False)
class Yield(Expr):
    """A yield expression (``yield value``).

    Attributes
    ----------
    value
        The yielded value, or ``None`` for bare ``yield``.

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Yield
    # fmt: off
    value: Expr | None
    if TYPE_CHECKING:
        def __init__(self, _0: Expr | None, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr | None, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(self, value: Expr | None = None) -> None:
        """Initialize a Yield expression."""
        self.__ffi_init__(value)


@c_class("ffi.text.ast.YieldFrom")
class YieldFrom(Expr):
    """A yield-from expression (``yield from iterable``).

    Attributes
    ----------
    value
        The iterable to yield from.

    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.YieldFrom
    # fmt: off
    value: Expr
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.StarredExpr")
class StarredExpr(Expr):
    """A starred expression (``*value``)."""

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.StarredExpr
    # fmt: off
    value: Expr
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Await")
class AwaitExpr(Expr):
    """An await expression (``await value``)."""

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Await
    # fmt: off
    value: Expr
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.WalrusExpr")
class WalrusExpr(Expr):
    """A walrus / named expression (``target := value``)."""

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.WalrusExpr
    # fmt: off
    target: Expr
    value: Expr
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: Expr, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: Expr, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.FStr")
class FStr(Expr):
    """An f-string expression (``f"...{x}..."``).

    ``values`` is a list of ``Literal(str)`` for text parts and
    ``FStrValue`` for interpolated expressions.
    """

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.FStr
    # fmt: off
    values: MutableSequence[Expr]
    if TYPE_CHECKING:
        def __init__(self, _0: MutableSequence[Expr], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: MutableSequence[Expr], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.FStrValue", init=False)
class FStrValue(Expr):
    """A formatted value inside an f-string (``{value!r:.2f}``)."""

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.FStrValue
    # fmt: off
    value: Expr
    conversion: int
    format_spec: Expr | None
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: int, _2: Expr | None, /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: int, _2: Expr | None, /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)

    def __init__(
        self,
        value: Expr,
        conversion: int = -1,
        format_spec: Expr | None = None,
    ) -> None:
        self.__ffi_init__(value, conversion, format_spec)


@c_class("ffi.text.ast.ExceptHandler")
class ExceptHandler(Node):
    """One ``except [Type [as name]]:`` clause in a try statement."""

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.ExceptHandler
    # fmt: off
    type: Expr | None
    name: str | None
    body: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, _0: Expr | None, _1: str | None, _2: MutableSequence[Stmt], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr | None, _1: str | None, _2: MutableSequence[Stmt], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Try", init=False)
class Try(Stmt):
    """A ``try / except / else / finally`` statement."""

    body: MutableSequence[Stmt]
    handlers: MutableSequence[ExceptHandler]
    orelse: MutableSequence[Stmt]
    finalbody: MutableSequence[Stmt]

    def __init__(
        self,
        body: MutableSequence[Stmt],
        handlers: MutableSequence[ExceptHandler],
        orelse: MutableSequence[Stmt] | None = None,
        finalbody: MutableSequence[Stmt] | None = None,
    ) -> None:
        if orelse is None:
            orelse = []
        if finalbody is None:
            finalbody = []
        self.__ffi_init__(body, handlers, orelse, finalbody)


@c_class("ffi.text.ast.MatchCase")
class MatchCase(Node):
    """One ``case pattern [if guard]:`` clause in a match statement."""

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.MatchCase
    # fmt: off
    pattern: Expr
    guard: Expr | None
    body: MutableSequence[Stmt]
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: Expr | None, _2: MutableSequence[Stmt], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: Expr | None, _2: MutableSequence[Stmt], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


@c_class("ffi.text.ast.Match")
class Match(Stmt):
    """A ``match / case`` statement."""

    # tvm-ffi-stubgen(begin): object/ffi.text.ast.Match
    # fmt: off
    subject: Expr
    cases: MutableSequence[MatchCase]
    if TYPE_CHECKING:
        def __init__(self, _0: Expr, _1: MutableSequence[MatchCase], /) -> None: ...
        def __ffi_shallow_copy__(self, /) -> Object: ...
        @staticmethod
        def __c_ffi_init__(_0: Expr, _1: MutableSequence[MatchCase], /) -> Object: ...
    # fmt: on
    # tvm-ffi-stubgen(end)
