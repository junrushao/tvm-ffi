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
"""Evaluate Python-shaped AST fragments into dialect IR nodes."""

from __future__ import annotations

import operator
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Callable, cast

from tvm_ffi.core import MISSING
from tvm_ffi.pyast import OperationKind

from . import pyast, std
from ._pyast_source import DiagnosticLevel, Source

_NATIVE_LITERAL_TYPES = (bool, int, float, str, type(None))
_TOP_LITERAL_GENERICS: tuple[tuple[type[Any], str], ...] = (
    (bool, "__literal_bool__"),
    (int, "__literal_int__"),
    (float, "__literal_float__"),
    (str, "__literal_str__"),
)
_NOOP_IDS = {"pass", "..."}
_SPECIAL_STMT_GENERICS = {
    "break": "__break__",
    "continue": "__continue__",
}
_NATIVE_GENERICS: dict[str, Callable[..., Any]] = {
    "__neg__": operator.neg,
    "__pos__": operator.pos,
    "__invert__": operator.invert,
    "__not__": operator.not_,
    "__add__": operator.add,
    "__sub__": operator.sub,
    "__mul__": operator.mul,
    "__truediv__": operator.truediv,
    "__floordiv__": operator.floordiv,
    "__mod__": operator.mod,
    "__pow__": operator.pow,
    "__lshift__": operator.lshift,
    "__rshift__": operator.rshift,
    "__and__": operator.and_,
    "__or__": operator.or_,
    "__xor__": operator.xor,
    "__matmul__": operator.matmul,
    "__lt__": operator.lt,
    "__le__": operator.le,
    "__gt__": operator.gt,
    "__ge__": operator.ge,
    "__eq__": operator.eq,
    "__ne__": operator.ne,
    "__is__": operator.is_,
    "__is_not__": operator.is_not,
    "__load__": operator.getitem,
    "__in__": lambda lhs, rhs: lhs in rhs,
    "__not_in__": lambda lhs, rhs: lhs not in rhs,
    "__logical_and__": lambda lhs, rhs: lhs and rhs,
    "__logical_or__": lambda lhs, rhs: lhs or rhs,
}

_DIALECT_REGISTRY: dict[str, Any] = {}
_OP_GENERICS: dict[int, str] = {
    OperationKind.USub: "__neg__",
    OperationKind.UAdd: "__pos__",
    OperationKind.Invert: "__invert__",
    OperationKind.Not: "__not__",
    OperationKind.Add: "__add__",
    OperationKind.Sub: "__sub__",
    OperationKind.Mult: "__mul__",
    OperationKind.Div: "__truediv__",
    OperationKind.FloorDiv: "__floordiv__",
    OperationKind.Mod: "__mod__",
    OperationKind.Pow: "__pow__",
    OperationKind.LShift: "__lshift__",
    OperationKind.RShift: "__rshift__",
    OperationKind.BitAnd: "__and__",
    OperationKind.BitOr: "__or__",
    OperationKind.BitXor: "__xor__",
    OperationKind.MatMult: "__matmul__",
    OperationKind.Lt: "__lt__",
    OperationKind.LtE: "__le__",
    OperationKind.Gt: "__gt__",
    OperationKind.GtE: "__ge__",
    OperationKind.Eq: "__eq__",
    OperationKind.NotEq: "__ne__",
    OperationKind.Is: "__is__",
    OperationKind.IsNot: "__is_not__",
    OperationKind.In: "__in__",
    OperationKind.NotIn: "__not_in__",
    OperationKind.And: "__logical_and__",
    OperationKind.Or: "__logical_or__",
}


class ParserError(Exception):
    """Error wrapper that keeps the source AST node attached to parse failures."""

    node: pyast.Node
    error: Exception

    def __init__(self, error: Exception, node: pyast.Node) -> None:
        """Record the original exception and the syntax node that triggered it."""
        super().__init__(str(error))
        self.node = node
        self.error = error


class _DiagnosticMessage(str):
    """String whose repr is itself, so KeyError renders diagnostics directly."""

    def __repr__(self) -> str:
        return str(self)


class VarTable:
    """Stacked lexical environment used while evaluating parser syntax."""

    def __init__(self) -> None:
        """Create an empty environment; callers push a frame before adding names."""
        self.frames: list[set[str]] = []
        self.name2value: dict[str, list[Any]] = defaultdict(list)

    def push_frame(self) -> None:
        """Enter a new lexical scope for function, region, branch, or top-level parsing."""
        self.frames.append(set())

    def pop_frame(self) -> None:
        """Leave the current lexical scope and hide names bound inside it."""
        frame = self.frames.pop()
        for name in frame:
            self.name2value[name].pop()

    def add(self, name: str, value: Any, *, allow_shadowing: bool = False) -> None:
        """Bind a syntax-visible name to a parser value in the current scope."""
        frame = self.frames[-1]
        values = self.name2value[name]
        if name in frame:
            if not allow_shadowing:
                raise ValueError(f"Variable already defined in current scope: {name}")
            values[-1] = value
            return
        frame.add(name)
        values.append(value)

    def get(self, name: str) -> Any:
        """Return the innermost visible value for ``name`` or ``MISSING`` if unknown."""
        values = self.name2value.get(name, [])
        return values[-1] if values else MISSING


def normalize_ty(value: Any) -> std.Ty:
    """Normalize annotations, type factories, and dtype strings to ``std.Ty``."""
    if isinstance(value, std.Ty):
        return value
    if hasattr(value, "to_dialect"):
        return value.to_dialect()
    if isinstance(value, str):
        return std.PrimTy(value)
    raise TypeError(f"expected std type, got {type(value).__name__}")


class Factory:
    """Base class for parser-side factories."""

    dialect = "std"

    def to_dialect(self) -> Any:
        """Return the concrete dialect value represented by this factory."""
        raise NotImplementedError

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Construct a parser or dialect value from call syntax."""
        raise NotImplementedError

    def __getitem__(self, indices: Sequence[Any]) -> Any:
        """Construct a parser or dialect value from indexing syntax."""
        raise TypeError(f"Bracket indexing is not supported for this type: {type(self).__name__}")


class TyFactory(Factory):
    """Factory base for type syntax such as ``std.i32`` and casts."""

    def to_dialect(self) -> std.Ty:
        """Return the concrete ``std.Ty`` represented by the factory."""
        raise NotImplementedError

    def _make_cast(self, value: Any) -> std.Cast:
        """Build a cast after validating that the call operand is expression-like."""
        if not isinstance(value, std.Expr) and not isinstance(value, (bool, int, float, str)):
            value_type = "TyFactory" if hasattr(value, "to_dialect") else type(value).__name__
            raise TypeError(f"expected expression, got {value_type}")
        return std.Cast(self.to_dialect(), value)


class Frame(Factory):
    """Parser frame for body-bearing IR constructs."""

    dialect = "std"
    body: list[Any]

    def bind_names(self, names: Sequence[str]) -> None:
        """Attach user-written target names to a frame's placeholder bindings.

        Base frames do not bind names, so this only succeeds for an empty target
        list.  Region frames override it for ``with ... as`` and ``for`` syntax.
        """
        if names:
            raise TypeError(f"{type(self).__name__} does not bind names")

    def bound_vars(self) -> list[Any]:
        """Return variables made visible by entering this frame."""
        return []


class DummyFrame(Frame):
    """Synthetic frame used for top-level and branch statement lists."""

    def __init__(self) -> None:
        """Create an empty statement accumulator."""
        self.body = []

    def to_dialect(self) -> list[Any]:
        """Return the accumulated statements without wrapping them in a node."""
        return self.body


class Parser:
    """Visitor that maps translated Python syntax into IR nodes.

    The parser uses concrete ``std`` classes for node classification and
    delegates dialect behavior to methods on registered language modules, such
    as ``__ffi_generics__``.
    """

    def __init__(
        self,
        source: Source,
        extra_vars: dict[str, Any] | None = None,
    ) -> None:
        """Prepare parser state for a source object and registered dialects.

        Used by ``parse`` and its typed wrappers.  ``extra_vars`` seeds names
        visible to expressions.
        """
        self.source = source
        self.var_table = VarTable()
        self.dialect_stack: list[str] = []
        self.generics: dict[tuple[str, Any], Callable[..., Any]] = {}
        self.scope_stack: list[Frame] = []

        extra_vars = extra_vars or {}
        registered_dialects = dict(_DIALECT_REGISTRY)
        self.dialects: dict[str, Any] = registered_dialects

        self.var_table.push_frame()
        for dialect, language in registered_dialects.items():
            self._install_dialect(dialect, language)
        if "std" in registered_dialects:
            self.dialect_stack.append("std")
        for name, value in extra_vars.items():
            self.var_table.add(name, value)

    def _install_dialect(self, dialect: str, language: Any) -> None:
        """Expose a registered language module's names, globals, and generic hooks.

        This is exercised once at parser construction.  It installs dialect
        namespaces such as ``std`` and registers generic handlers used later by
        operators, calls, loads, stores, and statements.
        """
        self.var_table.add(dialect, language, allow_shadowing=True)
        for name, value in getattr(language, "__ffi_globals__", {}).items():
            self.var_table.add(name, value, allow_shadowing=True)
        for key, handler in getattr(language, "__ffi_generics__", {}).items():
            generic_name, dispatch_key = key if isinstance(key, tuple) else (key, dialect)
            self.generics[(generic_name, dispatch_key)] = handler

    def visit(self, node: Any) -> Any:
        """Dispatch a translated AST node to ``visit_<NodeClass>``.

        Every syntax conversion funnels through this method.  It wraps parse
        failures with their source node, then lets ``run`` attach the rendered
        diagnostic to the original exception before re-raising it.
        """
        try:
            method = f"visit_{type(node).__name__}"
            visitor = getattr(self, method, None)
            if visitor is None:
                raise NotImplementedError(f"No {method} method")
            return visitor(node)
        except ParserError:
            raise
        except Exception as e:
            raise ParserError(e, node=node) from e

    def run(self) -> Any:
        """Parse the source root and convert the top-level body into a final result.

        Used by the public ``parse`` entrypoint after source normalization.  The
        parser collapses the accumulated top-level nodes into ``None``, one
        node, a module, or a list.
        """
        frame = DummyFrame()
        try:
            with self._with_frame(frame, var_table_frame=False):
                self.visit(self.source.ast_root)
        except ParserError as err:
            raise self._with_diagnostic(err.error, err.node) from None
        body = frame.body
        if not body:
            return None
        if len(body) == 1:
            return body[0]
        if all(isinstance(value, std.Func) for value in body):
            return std.Module(list(body))
        return list(body)

    def _with_diagnostic(self, error: Exception, node: pyast.Node) -> Exception:
        """Attach a rendered source diagnostic to ``error`` without printing it."""
        if isinstance(error, KeyError) and len(error.args) == 1:
            error_message = str(error.args[0])
        else:
            error_message = str(error)
        message = _DiagnosticMessage(
            self.source.format_error(
                node,
                error_message,
                DiagnosticLevel.ERROR,
            ).rstrip()
        )
        if error.args:
            error.args = (message, *error.args[1:])
        else:
            error.args = (message,)
        return error

    def _run_generics(self, generic_name: str, operands: tuple[Any, ...]) -> Any:
        """Run a dialect or native generic operation for parsed syntax.

        Operators such as ``+`` and statement forms such as assignment route
        here.  Dispatch first tries operand dialects, then the active dialect
        stack, and finally Python-native behavior for values that are not
        dialect nodes.

        Dispatch cases are ordered from most specific to most general:

        1. A unique non-literal operand dialect, keyed by its dialect mnemonic.
        2. The innermost active dialect when operands are literal-only or have
           no dialect-bearing operands, such as parser metadata.
        3. Ambiguous mixed dialect operands.
        4. Native Python operator behavior when every operand is dialect-free.
        5. A missing-handler error when no rule applies.
        """

        def _dialect_of(value: Any) -> str | None:
            """Return the dialect mnemonic advertised by a parsed value, if any."""
            dialect_mnemonic = getattr(type(value), "__ffi_dialect_mnemonic__", (None,))
            return dialect_mnemonic[0]

        def _is_python_literal(value: Any) -> bool:
            """Return whether ``value`` came from Python literal syntax."""
            if isinstance(value, _NATIVE_LITERAL_TYPES):
                return True
            if isinstance(value, (tuple, list, set)):
                return all(_is_python_literal(item) for item in value)
            if isinstance(value, dict):
                return all(
                    _is_python_literal(key) and _is_python_literal(item)
                    for key, item in value.items()
                )
            return False

        # Cases 1-3 only consider dialect-bearing, non-literal operands.
        # Parser metadata that does not advertise a dialect is ignored here, so
        # syntax like annotated binds and if-statements can use the active dialect.
        operand_dialects = [
            dialect
            for dialect in (_dialect_of(op) for op in operands if not _is_python_literal(op))
            if dialect is not None
        ]
        if len(set(operand_dialects)) == 1:
            # Case 1: Exactly one non-literal operand dialect is present, so
            # dispatch to that dialect's generic if it defines one.
            dialect: str = operand_dialects[0]
            if (handler := self.generics.get((generic_name, dialect))) is not None:
                return handler(*operands)
        elif not operand_dialects:
            # Case 2: Literal-only and parser-metadata-only operands have no
            # operand dialect, so use the innermost active parser dialect.
            for dialect in reversed(self.dialect_stack):
                if (handler := self.generics.get((generic_name, dialect))) is not None:
                    return handler(*operands)
        else:
            # Case 3: Multiple operand dialects remain, so any implicit choice
            # would be ambiguous.
            raise TypeError(
                f"ambiguous generic {generic_name}: operands come from dialects "
                f"{sorted(operand_dialects)}"
            )

        # Case 4: Native fallback is only valid when no operand advertises a
        # dialect mnemonic at all.
        if all(_dialect_of(op) is None for op in operands):
            if (handler := _NATIVE_GENERICS.get(generic_name)) is not None:
                return handler(*operands)
        # Case 5: No operand dialect, active dialect, or native rule was able
        # to handle this generic operation.
        raise KeyError(f"No handler found for operation: {generic_name}. Operands: {operands}")

    def _emit_stmt(self, stmt: Any) -> None:
        """Append a statement node to the active parser frame."""
        if not self.scope_stack:
            raise RuntimeError("no active scope frame")
        self.scope_stack[-1].body.append(stmt)

    def _emit_bound_stmt(self, stmt: Any) -> None:
        """Emit a statement and expose any variables it binds to later syntax."""
        self._emit_stmt(stmt)
        if isinstance(stmt, (std.BindExpr, std.VarDef)):
            for var in stmt.vars:
                self.var_table.add(var.name, var, allow_shadowing=True)

    @contextmanager
    def _with_frame(
        self,
        frame: Frame | None,
        *,
        dialect: str | None = None,
        var_table_frame: bool = True,
    ) -> Iterator[Frame | None]:
        """Temporarily enter a parser frame, dialect context, and lexical scope.

        Used for functions, classes, branches, and regions.  It keeps names
        introduced inside that construct from leaking unless the caller
        explicitly registers a resulting top-level binding.
        """
        if var_table_frame:
            self.var_table.push_frame()
        if dialect is not None:
            self.dialect_stack.append(dialect)
        if frame is not None:
            self.scope_stack.append(frame)
        try:
            yield frame
        finally:
            if frame is not None:
                self.scope_stack.pop()
            if dialect is not None:
                self.dialect_stack.pop()
            if var_table_frame:
                self.var_table.pop_frame()

    def _visit_stmts(self, stmts: Sequence[pyast.Stmt]) -> None:
        """Visit a statement sequence in order for a block-like syntax node."""
        for stmt in stmts:
            self.visit(stmt)

    def _visit_frame_expr(self, node: pyast.Expr) -> Frame:
        """Evaluate decorators and context managers as parser frames.

        Frame syntax is produced by normal parser-side factories such as
        ``@std.func`` and ``with std.scope(...)``.  Bare factories are called
        with no arguments so ``@std.func`` and ``@std.func()`` are equivalent.
        """
        value = self.visit(node)
        if callable(value) and not isinstance(value, (type, Frame)):
            value = value()
        if not isinstance(value, Frame):
            raise TypeError(f"expected parser frame, got {type(value).__name__}")
        return value

    ################################################################################

    def visit_StmtBlock(self, node: pyast.StmtBlock) -> None:
        """Evaluate a source block, including module body and branch bodies."""
        self._visit_stmts(node.stmts)

    def visit_Assign(self, node: pyast.Assign) -> None:
        """Handle Python assignment forms as dialect binds, declarations, or stores.

        Used for ``x = expr``, ``x: std.i32``, ``x: std.i32 = expr``, tuple/list
        destructuring, explicit ``std.BindExpr`` or ``std.VarDef`` RHS
        forms, and indexed assignment such as ``buf[i] = value``.
        """
        if node.aug_op != OperationKind.Undefined:
            raise NotImplementedError("augmented assignment is not supported")

        # Case 1. Inplace mutating a target (buffer, tuple, etc.) via indexing syntax
        #       target[*indices] = rhs
        if isinstance(node.lhs, pyast.Index):
            if node.rhs is None:
                raise TypeError("indexed assignment requires a rhs")
            target = self.visit(node.lhs.obj)
            indices = tuple(self.visit(index) for index in node.lhs.idx)
            rhs = self.visit(node.rhs)
            self._emit_stmt(self._run_generics("__store__", (target, rhs, *indices)))
            return

        names = _unpack_lhs_names(node.lhs)
        # Case 2. Type annotation-only without RHS:
        #       x: std.i32
        if node.rhs is None:
            if node.annotation is None:
                raise TypeError("assignment without rhs requires an annotation")
            ty = self.visit(node.annotation)
            self._emit_bound_stmt(self._run_generics("__bind_var_def__", (names, ty)))
            return

        rhs = self.visit(node.rhs)
        # Case 3. Regular assignment with or without annotation
        #       x = expr
        #       x: std.i32 = expr
        ty = self.visit(node.annotation) if node.annotation is not None else None

        if ty is None and isinstance(rhs, tuple):
            # multiple binding targets, e.g.
            #      x, y = expr1, expr2
            if len(rhs) != len(names):
                raise TypeError(f"expected {len(rhs)} binding target(s), got {len(names)}")
            for name, value in zip(names, rhs):
                self._emit_bound_stmt(
                    self._run_generics(
                        "__bind_expr__",
                        ([name], None, value),
                    )
                )
            return

        if ty is None and isinstance(rhs, std.VarDef):
            self._emit_bound_stmt(self._run_generics("__bind_var_def__", (names, rhs)))
            return
        self._emit_bound_stmt(self._run_generics("__bind_expr__", (names, ty, rhs)))

    def visit_ExprStmt(self, node: pyast.ExprStmt) -> None:
        """Handle expression statements as standalone IR statements or implicit binds.

        This covers ``pass`` and ``...`` no-ops, ``break`` and ``continue``,
        already-constructed statement nodes, top-level expressions returned by
        ``parse``, and expression statements inside bodies that need an
        anonymous bind to preserve evaluation order.
        """
        if isinstance(node.expr, pyast.Id):
            name = node.expr.name
            if name in _NOOP_IDS:
                return
            if name in _SPECIAL_STMT_GENERICS:
                self._emit_stmt(self._run_generics(_SPECIAL_STMT_GENERICS[name], ()))
                return

        value = self.visit(node.expr)
        if value is None:
            return
        if isinstance(value, std.Stmt):
            self._emit_bound_stmt(value)
            return
        if len(self.scope_stack) == 1:
            self._emit_stmt(_materialize_top_value(self._run_generics, value))
        else:
            self._emit_bound_stmt(self._run_generics("__bind_expr__", ([], None, value)))

    ######### Scopes #########

    def _visit_scope_frame_body(
        self,
        frame: Frame,
        body: Sequence[pyast.Stmt],
        target: pyast.Expr | None = None,
    ) -> Any:
        """Parse a body-bearing region and bind its ``as`` or loop target names.

        Used by ``for`` and ``with`` visitors after their header expression has
        produced a frame.  Placeholder variables inside the frame are renamed to
        match user-written targets before the body is visited.
        """
        with self._with_frame(frame, dialect=frame.dialect):
            if target is not None:
                frame.bind_names(_unpack_lhs_names(target))
                for var in frame.bound_vars():
                    self.var_table.add(var.name, var)
            self._visit_stmts(body)
        return frame.to_dialect()

    def _collect_args(self, frame: Any, args: Sequence[pyast.Assign]) -> list[Any]:
        """Convert function parameters and annotations into dialect variables.

        Called only for ``@std.func`` function definitions.  Missing
        annotations default to ``std.Any``; default argument values are rejected.
        """
        ret = []
        for arg_node in args:
            if not isinstance(arg_node.lhs, pyast.Id):
                raise TypeError("function arguments must be identifiers")
            if arg_node.rhs is not None:
                raise TypeError("default argument values are not supported")
            language = self.dialects.get(frame.dialect) or self.dialects["std"]
            default_ty = getattr(language, "Any", self.dialects["std"].Any)
            ty = normalize_ty(
                default_ty if arg_node.annotation is None else self.visit(arg_node.annotation)
            )
            arg = frame.make_arg(arg_node.lhs.name, ty)
            self.var_table.add(arg.name, arg)
            ret.append(arg)
        return ret

    def visit_Function(self, node: pyast.Function) -> None:
        """Parse a decorated Python function as an IR function.

        Exercised by printed or handwritten ``@std.func`` definitions.  It
        collects argument variables, parses the body in a function frame, emits
        the resulting ``std.Func``, and binds the function symbol for later
        references in the same top-level parse.
        """
        if node.is_async:
            raise NotImplementedError("async functions are not supported")
        if len(node.decorators) != 1:
            raise TypeError("IR functions require exactly one decorator")
        frame = self._visit_frame_expr(node.decorators[0])
        func_frame = cast(Any, frame)
        func_frame.symbol = node.name.name
        func_frame.ret_type = (
            normalize_ty(self.visit(node.return_type)) if node.return_type else None
        )
        with self._with_frame(frame, dialect=frame.dialect):
            func_frame.args = self._collect_args(func_frame, node.args)
            self._visit_stmts(node.body)
        func = frame.to_dialect()
        self._emit_stmt(func)
        self.var_table.add(func_frame.symbol, func, allow_shadowing=True)

    def visit_For(self, node: pyast.For) -> None:
        """Parse ``for target in range(...)`` as a dialect ``For`` region."""
        if node.is_async:
            raise NotImplementedError("async for is not supported")
        if node.orelse:
            raise NotImplementedError("for/else is not supported")
        frame = self._visit_frame_expr(node.rhs)
        self._emit_stmt(self._visit_scope_frame_body(frame, node.body, target=node.lhs))

    def visit_While(self, node: pyast.While) -> None:
        """Parse Python ``while cond:`` blocks as dialect ``While`` regions."""
        if node.orelse:
            raise NotImplementedError("while/else is not supported")
        frame = self._run_generics("__while__", (self.visit(node.cond),))
        if not isinstance(frame, Frame):
            raise TypeError(f"expected parser frame, got {type(frame).__name__}")
        self._emit_stmt(self._visit_scope_frame_body(frame, node.body))

    def visit_With(self, node: pyast.With) -> None:
        """Parse ``with`` regions such as ``with std.scope(...) as x:``."""
        if node.is_async:
            raise NotImplementedError("async with is not supported")
        frame = self._visit_frame_expr(node.rhs)
        self._emit_stmt(self._visit_scope_frame_body(frame, node.body, target=node.lhs))

    def visit_Class(self, node: pyast.Class) -> None:
        """Parse decorated classes as modules.

        Used by the module printer form ``@std.module class MyModule:``.  The
        language frame validates that the class body contains only functions.
        """
        if len(node.decorators) != 1:
            raise TypeError("IR module classes require exactly one decorator")
        if node.bases or node.kwargs_keys or node.kwargs_values:
            raise TypeError("IR module classes do not accept bases or keywords")
        frame = self._visit_frame_expr(node.decorators[0])
        with self._with_frame(frame, dialect=frame.dialect):
            self._visit_stmts(node.body)
        self._emit_stmt(frame.to_dialect())

    def visit_If(self, node: pyast.If) -> None:
        """Parse Python ``if`` statements into dialect conditional statements."""
        cond = self.visit(node.cond)
        then_body = self._visit_branch(node.then_branch)
        else_body = self._visit_branch(node.else_branch)
        self._emit_stmt(self._run_generics("__if__", (cond, then_body, else_body)))

    def _visit_branch(self, body: Sequence[pyast.Stmt]) -> list[Any]:
        """Parse one branch of an ``if`` into an isolated statement list."""
        frame = DummyFrame()
        with self._with_frame(frame):
            self._visit_stmts(body)
        return frame.body

    def visit_Return(self, node: pyast.Return) -> None:
        """Parse ``return`` statements, including tuple returns as multiple values."""
        values = _normalize_to_list(self.visit(node.value) if node.value is not None else None)
        self._emit_stmt(self._run_generics("__return__", tuple(values)))

    def visit_Assert(self, node: pyast.Assert) -> None:
        """Parse Python ``assert cond`` into a dialect assertion statement."""
        if node.msg is not None:
            raise NotImplementedError("assert messages are not supported")
        self._emit_stmt(self._run_generics("__assert__", (self.visit(node.cond),)))

    def visit_Break(self, node: pyast.Break) -> None:
        """Parse Python ``break`` into a dialect break statement."""
        self._emit_stmt(self._run_generics("__break__", ()))

    def visit_Continue(self, node: pyast.Continue) -> None:
        """Parse Python ``continue`` into a dialect continue statement."""
        self._emit_stmt(self._run_generics("__continue__", ()))

    ################################################################################

    def visit_Id(self, node: pyast.Id) -> Any:
        """Resolve an identifier from parser locals or Python builtins."""
        name = node.name
        value = self.var_table.get(name)
        if not MISSING.is_(value):
            return value
        import builtins  # noqa: PLC0415

        if name == "...":
            return Ellipsis
        if hasattr(builtins, name):
            return getattr(builtins, name)
        raise NameError(f"name {name!r} is not defined")

    def visit_Operation(self, node: pyast.Operation) -> Any:
        """Parse unary, binary, boolean, and comparison expressions via generics."""
        kind = pyast.OperationKind
        op = node.op
        operands = node.operands
        if op in (kind.And, kind.Or):  # Fold operations
            result = self.visit(operands[0])
            for operand in operands[1:]:
                result = self._run_generics(_OP_GENERICS[op], (result, self.visit(operand)))
            return result
        if op == kind.Parens:
            return self.visit(operands[0])
        if op == kind.IfThenElse:
            raise NotImplementedError("ternary expressions are not supported")
        if op == kind.ChainedCompare:
            return self._visit_chained_compare(operands)
        return self._run_generics(_OP_GENERICS[op], tuple(self.visit(op) for op in operands))

    def _visit_chained_compare(self, operands: Sequence[pyast.Expr]) -> Any:
        """Evaluate a chained comparison as pairwise compares joined by logical and."""
        result = None
        lhs = self.visit(operands[0])
        for cmp_node, rhs_node in zip(operands[1::2], operands[2::2]):
            if not isinstance(cmp_node, pyast.Literal):
                raise TypeError(
                    f"chained compare expects operator literals, got {type(cmp_node).__name__}"
                )
            rhs = self.visit(rhs_node)
            cmp_value = self._run_generics(_OP_GENERICS[cmp_node.value], (lhs, rhs))
            result = (
                cmp_value
                if result is None
                else self._run_generics("__logical_and__", (result, cmp_value))
            )
            lhs = rhs
        return result

    def visit_Attr(self, node: pyast.Attr) -> Any:
        """Evaluate attribute access such as ``std.i32`` or object attributes."""
        return getattr(self.visit(node.obj), node.name)

    def visit_Call(self, node: pyast.Call) -> Any:
        """Evaluate Python calls against parser factories, callables, or call generics.

        Used for direct factory syntax like ``std.IntImm(...)`` and for indirect
        call nodes when the callee is a dialect expression rather than a Python
        callable.
        """

        def _to_dialect(value: Any) -> Any:
            return value.to_dialect() if hasattr(value, "to_dialect") else value

        callee = self.visit(node.callee)
        positional = list(self._visit_container(node.args))
        if "" in node.kwargs_keys:
            raise TypeError("** keyword expansion is not supported")
        kwargs = {
            key: _to_dialect(self.visit(value))
            for key, value in zip(node.kwargs_keys, node.kwargs_values)
        }
        if callable(callee):
            return callee(*positional, **kwargs)
        return self._run_generics("__call__", (callee, *positional))

    def visit_Literal(self, node: pyast.Literal) -> Any:
        """Return native Python literal values before the language materializes them."""
        return node.value

    def visit_Index(self, node: pyast.Index) -> Any:
        """Parse indexing for type syntax, loads, and explicit slice literals.

        Factory objects handle syntax such as ``std.f32[1, 2]``.  Other values
        dispatch to the language ``__load__`` generic, so ``buf[i]`` becomes a
        dialect load expression.
        """
        obj = self.visit(node.obj)
        indices = tuple(self.visit(index) for index in node.idx)
        if any(index is Ellipsis for index in indices):
            raise TypeError("ellipsis indexing is not supported")
        if isinstance(obj, TyFactory):
            return obj.__getitem__(indices)
        return self._run_generics("__load__", (obj, *indices))

    def visit_Yield(self, node: pyast.Yield) -> Any:
        """Parse ``yield`` expressions into dialect yield statements."""
        values = _normalize_to_list(self.visit(node.value) if node.value is not None else None)
        return self._run_generics("__yield__", tuple(values))

    def visit_Lambda(self, node: pyast.Lambda) -> Any:
        """Reject lambda syntax; functions must use dialect function definitions."""
        raise NotImplementedError("lambda is not supported")

    def _visit_container(self, exprs: Iterable[pyast.Expr]) -> Iterator[Any]:
        """Evaluate container elements, expanding starred expressions."""
        for expr in exprs:
            if isinstance(expr, pyast.StarredExpr):
                yield from self.visit(expr.value)
            else:
                yield self.visit(expr)

    def visit_Tuple(self, node: pyast.Tuple) -> tuple[Any, ...]:
        """Parse tuple literals, used for destructuring and multi-value returns."""
        return tuple(self._visit_container(node.values))

    def visit_List(self, node: pyast.List) -> list[Any]:
        """Parse list literals for explicit node constructors and Python values."""
        return list(self._visit_container(node.values))

    def visit_Set(self, node: pyast.Set) -> set[Any]:
        """Parse set literals when they appear in constructor arguments."""
        return set(self._visit_container(node.values))

    def visit_Dict(self, node: pyast.Dict) -> dict[Any, Any]:
        """Parse dict literals and ``**`` expansions for attrs or call kwargs."""
        out = {}
        for k_node, v_node in zip(node.keys, node.values):
            if isinstance(k_node, pyast.StarredExpr) and isinstance(
                k_node.value, pyast.StarredExpr
            ):
                out.update(self.visit(k_node.value.value))
            else:
                out[self.visit(k_node)] = self.visit(v_node)
        return out

    def visit_Slice(self, node: pyast.Slice) -> Any:
        """Parse slice syntax into the language range object.

        Used for standalone range strings handled by ``parse("1:4")`` and any
        indexed expression that carries a slice component.
        """
        start = self.visit(node.start) if node.start is not None else None
        stop = self.visit(node.stop) if node.stop is not None else None
        step = self.visit(node.step) if node.step is not None else None
        return self._run_generics("__slice__", (start, stop, step))


def parse(
    program: Any,
    *,
    extra_vars: dict[str, Any] | None = None,
    feature_version: tuple[int, int] = sys.version_info[:2],
) -> Any:
    """Parse Python source, translated ``pyast`` nodes, or Python objects into IR.

    This is the main public entrypoint used by tests and users.  Strings are
    parsed as Python source, existing ``pyast.Node`` instances are evaluated
    directly, and inspectable Python functions/classes are first translated by
    ``Source``.  If a plain string is not valid Python but can be interpreted as
    a slice, the parser returns the corresponding range value.
    """
    from . import _std_lang as _  # noqa: PLC0415, F401

    if isinstance(program, str):
        try:
            source = Source(program, feature_version=feature_version)
        except SyntaxError:
            wrapped = Source(f"_slice_[{program}]", feature_version=feature_version)
            parser = Parser(
                wrapped,
                extra_vars=extra_vars,
            )
            if not isinstance(wrapped.ast_root, pyast.StmtBlock):
                raise
            stmt = wrapped.ast_root.stmts[0]
            if not isinstance(stmt, pyast.ExprStmt) or not isinstance(stmt.expr, pyast.Index):
                raise
            if len(stmt.expr.idx) != 1:
                raise
            return parser.visit(stmt.expr.idx[0])
    elif isinstance(program, pyast.Node):
        source = object.__new__(Source)
        text = program.to_python()
        source.source_name = "<pyast>"
        source.start_line = 1
        source.start_column = 0
        source.source = text
        source.full_source = text
        source.ast_root = program
        return source
    else:
        source = Source(program, feature_version=feature_version)
    return Parser(
        source,
        extra_vars=extra_vars,
    ).run()


def register_dialect(name: str, lang_mod: Any) -> None:
    """Register or replace a parser language module for a dialect mnemonic."""
    if not isinstance(name, str) or not name:
        raise ValueError("dialect name must be a non-empty string")
    _DIALECT_REGISTRY[name] = lang_mod


def _materialize_top_value(run_generics: Callable[[str, tuple[Any, ...]], Any], value: Any) -> Any:
    """Convert top-level parser values into IR nodes when possible.

    Used for expression-only parses like ``"1"`` or ``"std.i32"``.  Existing
    nodes are preserved, factories are converted to dialect types, and native
    literals become language immediate nodes.
    """
    if isinstance(value, std.Node):
        return value
    if hasattr(value, "to_dialect"):
        return value.to_dialect()
    for py_type, generic_name in _TOP_LITERAL_GENERICS:
        if isinstance(value, py_type):
            return run_generics(generic_name, (value,))
    return value


def _unpack_lhs_names(target: pyast.Expr) -> list[str]:
    """Extract flat binding names from assignment, ``for``, or ``with`` targets."""
    if isinstance(target, pyast.Id):
        return [target.name]
    if isinstance(target, (pyast.Tuple, pyast.List)):
        return [name for value in target.values for name in _unpack_lhs_names(value)]
    raise TypeError(f"unsupported binding target: {type(target).__name__}")


def _normalize_to_list(target: Any) -> list[Any]:
    """Normalize absent, scalar, or tuple values for return and yield generics."""
    if target is None:
        return []
    if isinstance(target, tuple):
        return list(target)
    return [target]
