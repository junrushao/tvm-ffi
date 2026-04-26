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
from __future__ import annotations

import dataclasses as dc
import enum
import inspect
import linecache
import operator
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from types import CodeType, FrameType, FunctionType, MethodType, ModuleType, TracebackType
from typing import Any, Callable, Type, Union, cast

from typing_extensions import TypeAlias

from tvm_ffi.core import MISSING

from . import pyast, std
from ._pyast_translator import ast_translate

_SourceObjectType: TypeAlias = Union[
    ModuleType,
    Type[Any],
    MethodType,
    FunctionType,
    TracebackType,
    FrameType,
    CodeType,
    Callable[..., Any],
]


class DiagnosticLevel(enum.IntEnum):
    """The diagnostic level, see diagnostic.h for more details."""

    BUG = 10
    ERROR = 20
    WARNING = 30
    NOTE = 40
    HELP = 50


class Source:
    source_name: str
    start_line: int
    start_column: int
    source: str
    full_source: str
    ast_root: pyast.Node

    def __init__(self, program: str | pyast.Node, feature_version: tuple[int, int]) -> None:
        if isinstance(program, str):
            self.source_name = "<str>"
            self.start_line = 1
            self.start_column = 0
            self.source = program
            self.full_source = program
            self.ast_root = ast_translate(self.source, feature_version=feature_version)
            return

        source_obj = cast(_SourceObjectType, program)
        self.source_name = inspect.getsourcefile(source_obj) or inspect.getfile(source_obj)
        lines, self.start_line = getsourcelines(source_obj)
        if lines:
            self.start_column = len(lines[0]) - len(lines[0].lstrip())
        else:
            self.start_column = 0
        if self.start_column and lines:
            self.source = "\n".join([l[self.start_column :].rstrip() for l in lines])
        else:
            self.source = "".join(lines)
        try:
            # It will cause a problem when running in Jupyter Notebook.
            # `mod` will be <module '__main__'>, which is a built-in module
            # and `getsource` will throw a TypeError
            mod = inspect.getmodule(source_obj)
            if mod:
                self.full_source = inspect.getsource(mod)
            else:
                self.full_source = self.source
        except TypeError:
            # It's a work around for Jupyter problem.
            # Since `findsource` is an internal API of inspect, we just use it
            # as a fallback method.
            src, _ = inspect.findsource(source_obj)
            self.full_source = "".join(src)
        self.ast_root = ast_translate(self.source, feature_version=feature_version)

    def report_error(self, node: pyast.Node, message: str, level: DiagnosticLevel) -> None:
        lineno = node.lineno or 1
        col_offset = node.col_offset or self.start_column
        end_lineno = node.end_lineno or lineno
        end_col_offset = node.end_col_offset or col_offset

        lineno += self.start_line - 1
        end_lineno += self.start_line - 1
        col_offset += self.start_column + 1
        end_col_offset += self.start_column + 1
        # TODO: emit and render
        # self.ctx.emit(
        #     diagnostics.Diagnostic(
        #         level=level,
        #         span=Span(
        #             source_name=SourceName(self.source.source_name),
        #             line=lineno,
        #             end_line=end_lineno,
        #             column=col_offset,
        #             end_column=end_col_offset,
        #         ),
        #         message=message,
        #     )
        # )


_getfile: Callable[[_SourceObjectType], str] = inspect.getfile
_findsource: Callable[[_SourceObjectType], tuple[list[str], int]] = inspect.findsource


def _patched_inspect_getfile(obj: _SourceObjectType) -> str:
    """Work out which source or compiled file an object was defined in."""
    if not inspect.isclass(obj):
        return _getfile(obj)
    cls = cast(type[Any], obj)
    mod = getattr(cls, "__module__", None)
    if mod is not None:
        file = getattr(sys.modules[mod], "__file__", None)
        if file is not None:
            return file
    for _, member in inspect.getmembers(cls):
        if inspect.isfunction(member):
            if cls.__qualname__ + "." + member.__name__ == member.__qualname__:
                return inspect.getfile(member)
    raise TypeError(f"Source for {obj!r} not found")


def _source_lines_for_class(obj: type[Any]) -> list[str]:
    """Return the entire source file and starting line number for an object."""
    file_name = inspect.getsourcefile(obj)
    if file_name:
        linecache.checkcache(file_name)
    else:
        file_name = inspect.getfile(obj)
        if not (file_name.startswith("<") and file_name.endswith(">")):
            raise OSError("source code not available")

    module = inspect.getmodule(obj, file_name)
    if module:
        lines = linecache.getlines(file_name, module.__dict__)
    else:
        lines = linecache.getlines(file_name)
    if not lines:
        raise OSError("could not get source code")
    return lines


def _class_scope_name(tokens: list[str]) -> str | None:
    """Return the class or nested function scope name represented by tokens."""
    if len(tokens) <= 1:
        return None
    if tokens[0] == "def":
        return tokens[1].split(":")[0].split("(")[0] + "<locals>"
    if tokens[0] == "class":
        return tokens[1].split(":")[0].split("(")[0]
    return None


def _skip_comment_line(line: str, in_comment: bool) -> tuple[bool, bool]:
    """Return updated triple-quoted-comment state and whether to skip line."""
    n_comment = line.count('"""')
    if n_comment:
        return in_comment ^ bool(n_comment & 1), True
    if in_comment:
        return in_comment, True
    return in_comment, False


def findsource(obj: _SourceObjectType) -> tuple[list[str], int]:
    """Return the entire source file and starting line number for an object."""
    if not inspect.isclass(obj):
        return _findsource(obj)

    cls = cast(type[Any], obj)
    lines = _source_lines_for_class(cls)
    qual_names = cls.__qualname__.replace(".<locals>", "<locals>").split(".")
    in_comment = False
    scope_stack: list[str] = []
    indent_info: dict[str, int] = {}
    for i, line in enumerate(lines):
        in_comment, skip_line = _skip_comment_line(line, in_comment)
        if skip_line:
            continue

        indent = len(line) - len(line.lstrip())
        tokens = line.split()
        name = _class_scope_name(tokens)
        if name is None:
            continue

        while scope_stack and indent_info[scope_stack[-1]] >= indent:
            scope_stack.pop()
        scope_stack.append(name)
        indent_info[name] = indent
        if scope_stack == qual_names:
            return lines, i

    raise OSError("could not find class definition")


def getsourcelines(obj: _SourceObjectType) -> tuple[list[str], int]:
    """Extract the block of code at the top of the given list of lines."""
    obj = cast(_SourceObjectType, inspect.unwrap(cast(Callable[..., Any], obj)))
    lines, l_num = findsource(obj)
    return inspect.getblock(lines[l_num:]), l_num + 1


inspect.getfile = _patched_inspect_getfile  # ty: ignore[invalid-assignment]


@dc.dataclass
class VarTable:
    frames: list[set[str]] = dc.field(default_factory=list)
    name2value: dict[str, list[Any]] = dc.field(default_factory=lambda: defaultdict(list))

    @contextmanager
    def with_frame(self) -> Iterator[None]:
        frame = set[str]()
        self.frames.append(frame)
        try:
            yield
        finally:
            self.frames.pop()
            for v in frame:
                self.name2value[v].pop()
            frame.clear()

    def add(self, name: str, value: Any, *, allow_shadowing: bool) -> None:
        frame: set[str] = self.frames[-1]
        n2v: list[Any] = self.name2value[name]
        if name in frame:
            if allow_shadowing:
                n2v[-1] = value
            else:
                raise ValueError(f"Variable already defined in current scope: {name}")
        else:
            frame.add(name)
            n2v.append(value)

    # def get(self) -> dict[str, Any]:
    #     return {key: values[-1] for key, values in self.name2value.items() if values}

    def get(self, name: str) -> Any:
        values = self.name2value.get(name, [])
        if not values:
            return MISSING
        return values[-1]


class ParseError(Exception):
    node: pyast.Node

    def __init__(self, message: str, node: pyast.Node) -> None:
        super().__init__(message)
        self.node = node


@dc.dataclass
class Parser:
    source: Source
    extra_vars: dc.InitVar[dict[str, Any]]
    var_table: VarTable = dc.field(default_factory=VarTable)
    dialect_stack: list[str] = dc.field(default_factory=list)
    generics: dict[
        tuple[
            str,  # generics name
            type[std.Ty] | str,  # dialect name, or first operand type
        ],
        Callable[..., Any],
    ] = dc.field(default_factory=dict)
    _debug_indent: int = 0

    def __post_init__(self, extra_vars: dict[str, Any]) -> None:
        self.var_table.frames.append(set())
        for k, v in extra_vars.items():
            self.var_table.add(k, v, allow_shadowing=False)

    def visit(self, node: Any) -> Any:
        try:
            method = "visit_" + node.__class__.__name__
            visitor = getattr(self, method, self.generic_visit)
            return visitor(node)
        except ParseError:
            raise
        except Exception as e:
            raise ParseError(f"Error while visiting {node.to_python()}: {e}", node=node) from e

    def run(self) -> Any:
        return self.visit(self.source.ast_root)

    def generic_visit(self, node: Any) -> None:
        raise NotImplementedError(f"No visit_{type(node).__name__} method")

    def _add_var(self, name: str, value: std.Value, allow_shadowing: bool) -> None:
        assert isinstance(name, str)
        assert isinstance(value, std.Value)
        if isinstance(value, std.Value) and value.name == "_":
            value.name = name
        self._debug_print(f"[add_var] {name}: {value.ty}")
        self.var_table.add(name, value, allow_shadowing=allow_shadowing)

    def _run_generics(self, generics: str, operands: tuple[Any, ...]) -> Any:
        for op in operands:
            if isinstance(op, std.Expr):
                if handler := self.generics.get((generics, type(op.ty))):
                    return handler(*operands)
        for dialect in reversed(self.dialect_stack):
            if handler := self.generics.get((generics, dialect)):
                return handler(*operands)
        if handler := _NATIVE_GENERICS.get(generics):
            return handler(*operands)
        raise KeyError(f"No handler found for operation: {generics}. Operands: {operands}")

    def _bind_values(
        self,
        lhs: pyast.Expr,
        rhs: Any,
        allow_shadowing: bool,
        result: dict[str, Any],
    ) -> None:
        if isinstance(lhs, pyast.Id):
            self._add_var(lhs.name, rhs, allow_shadowing=allow_shadowing)
            result[lhs.name] = rhs
        elif isinstance(lhs, (pyast.Tuple, pyast.List)):
            starred_positions = [
                i for i, t in enumerate(lhs.values) if isinstance(t, pyast.StarredExpr)
            ]
            if starred_positions:
                raise ParseError("Star is not supported in assignment", node=lhs)
            if len(lhs.values) != len(rhs):
                raise ParseError(
                    f"Cannot unpack {len(rhs)} RHS values into {len(lhs.values)} LHS targets",
                    node=lhs,
                )
            for target, value in zip(lhs.values, rhs):
                self._bind_values(target, value, allow_shadowing=allow_shadowing, result=result)
        elif isinstance(lhs, (pyast.StarredExpr, pyast.Attr, pyast.Index)):
            raise ParseError(
                f"cannot bind into {type(lhs).__name__}; "
                "eval_assign only produces new local bindings",
                node=lhs,
            )
        else:
            raise ParseError(f"unsupported assignment target: {type(lhs).__name__}", node=lhs)

    def _debug_print(self, message: str) -> None:
        print(f"{' ' * self._debug_indent}{message}")

    def _visit_stmts(self, stmts: Sequence[pyast.Stmt]) -> list[std.Stmt]:
        result = []
        for stmt in stmts:
            if (
                isinstance(stmt, pyast.ExprStmt)
                and isinstance(stmt.expr, pyast.Id)
                and stmt.expr.name in ["pass", "..."]
            ):
                # TODO: HACK: ignore `pass` and `...` for now
                continue
            result.append(self.visit(stmt))
        return result

    ################################################################################

    def visit_StmtBlock(self, node: pyast.StmtBlock) -> list[std.Stmt]:
        return self._visit_stmts(node.stmts)

    def visit_Function(self, node: pyast.Function) -> std.Func:
        assert isinstance(node, pyast.Function)
        assert node.return_type is None
        assert not node.is_async
        assert len(node.decorators) == 1

        self._debug_print("## Function")
        self._debug_indent += 2
        func_frame = self.visit(node.decorators[0]).__ffi_parse__
        func_frame.symbol = node.name.name
        func_frame.ret_type = None  # TODO: support return type annotation
        self._debug_print(f"symbol: {func_frame.symbol}")
        with self.var_table.with_frame():
            args: list[std.Value] = []
            for arg in node.args:
                assert isinstance(arg, pyast.Assign) and isinstance(arg.lhs, pyast.Id)
                value = std.Value(name=arg.lhs.name, ty=self.visit(arg.annotation))
                args.append(value)
                self._add_var(value.name, value, allow_shadowing=False)
            func_frame.args = args
            func_frame.body = self._visit_stmts(node.body)
        self._debug_indent -= 2
        return func_frame.to_dialect()

    def visit_Assign(self, node: pyast.Assign) -> std.Stmt:
        self._debug_print("## Assign")
        self._debug_indent += 2
        rhs = self.visit(node.rhs)
        if isinstance(node.lhs, pyast.Index):
            # `Store` - inplace write into a buffer
            target = self.visit(node.lhs.obj)
            indices = [self.visit(index) for index in node.lhs.idx]
            stmt = self._run_generics("__store__", (target, rhs, *indices))
        elif isinstance(rhs, std.SingleBinding):
            self._bind_values(node.lhs, rhs.value, allow_shadowing=True, result={})
            stmt = rhs
        elif isinstance(rhs, std.TupleBinding):
            self._bind_values(node.lhs, rhs.values, allow_shadowing=True, result={})
            stmt = rhs
        else:
            # TODO: 1) support `std.Expr`, 2) error out on `std.NullBinding`
            raise ParseError(f"unsupported assignment rhs type: {type(rhs).__name__}", node=node)
        self._debug_print(stmt.text())
        self._debug_indent -= 2
        return stmt

    def visit_For(self, node: pyast.For) -> std.Stmt:
        self._debug_print("## For")
        self._debug_indent += 2
        with self.var_table.with_frame():
            for_frame = self.visit(node.rhs)  # visit: T.range(...)
            # TODO: handle multi-variable unpacking in for loop properly
            self._bind_values(node.lhs, for_frame.value, allow_shadowing=False, result={})
            for_frame.body = self._visit_stmts(node.body)
        self._debug_indent -= 2
        return for_frame.to_dialect()

    def visit_If(self, node: pyast.If) -> std.Stmt:
        self._debug_print("## If stmt")
        self._debug_indent += 2
        cond = self.visit(node.cond)
        self._debug_print(f"cond: {cond}")
        then_body = self._visit_stmts(node.then_branch)
        else_body = self._visit_stmts(node.else_branch)
        self._debug_indent -= 2
        return self._run_generics("__if_stmt__", (cond, then_body, else_body))

    ################################################################################

    def visit_Id(self, node: pyast.Id) -> Any:
        import builtins  # noqa: PLC0415 # TODO: maybe have builtin in scope?

        name = node.name
        value = self.var_table.get(name)
        if not MISSING.is_(value):
            return value
        if hasattr(builtins, name):
            return getattr(builtins, name)
        raise ParseError(f"name {name!r} is not defined", node=node)

    def visit_Operation(self, node: pyast.Operation) -> Any:
        K = pyast.OperationKind
        op = node.op
        op_name = K._NAMES[op]
        operands = node.operands
        if op in [K.And, K.Or]:  # Handle: `and`, `or`
            result = self.visit(operands[0])
            for child in operands[1:]:
                val = self.visit(child)
                result = self._run_generics(op_name, (result, val))
            return result
        if op == K.Parens:
            return self.visit(operands[0])
        if op == K.IfThenElse:
            raise NotImplementedError("if-then-else expression is not supported yet")
        if op == K.ChainedCompare:
            raise NotImplementedError("chained comparison is not supported yet")
        values = tuple(self.visit(o) for o in operands)
        return self._run_generics(op_name, values)

    def visit_Attr(self, node: pyast.Attr) -> Any:
        obj = self.visit(node.obj)
        return getattr(obj, node.name)

    def visit_Call(self, node: pyast.Call) -> Any:
        callee = self.visit(node.callee)
        positional: list[Any] = []
        for arg in node.args:
            if isinstance(arg, pyast.StarredExpr):
                positional.extend(self.visit(arg.value))
            else:
                positional.append(self.visit(arg))
        kwargs: dict[str, Any] = {}
        for key, val_node in zip(node.kwargs_keys, node.kwargs_values):
            if key == "":
                kwargs.update(self.visit(val_node))
            else:
                kwargs[key] = self.visit(val_node)
        return callee(*positional, **kwargs)

    def visit_Literal(self, node: pyast.Literal) -> Any:
        return node.value

    def visit_Index(self, node: pyast.Index) -> Any:
        obj = self.visit(node.obj)
        indices = [self.visit(i) for i in node.idx]
        return self._run_generics("__load__", (obj, *indices))

    def visit_ExprStmt(self, node: pyast.ExprStmt) -> Any:
        raise NotImplementedError  # TODO: implement it

    def _generic_visit(self, node: Any) -> None:
        from ._pyast_visitor import iter_fields  # noqa: PLC0415

        if not isinstance(node, pyast.Node):
            raise TypeError(f"expected Node, got {type(node).__name__}")
        for _name, value in iter_fields(node):
            if isinstance(value, pyast.Node):
                self.visit(value)
            elif isinstance(value, (list, Sequence)):
                for item in value:
                    if isinstance(item, pyast.Node):
                        self.visit(item)

    def _visit_container(self, exprs: Iterable[pyast.Expr]) -> Iterator[Any]:
        # Use by Tuple, List, Set, Dict
        for e in exprs:
            if isinstance(e, pyast.StarredExpr):
                yield from self.visit(e.value)
            else:
                yield self.visit(e)

    def visit_Tuple(self, node: pyast.Tuple) -> tuple:
        return tuple(self._visit_container(node.values))

    def visit_List(self, node: pyast.List) -> list:
        return list(self._visit_container(node.values))

    def visit_Set(self, node: pyast.Set) -> set:
        return set(self._visit_container(node.values))

    def visit_Dict(self, node: pyast.Dict) -> dict:
        out: dict = {}
        for k_node, v_node in zip(node.keys, node.values):
            if isinstance(k_node, pyast.StarredExpr) and isinstance(
                k_node.value, pyast.StarredExpr
            ):
                out.update(self.visit(k_node.value.value))
            else:
                out[self.visit(k_node)] = self.visit(v_node)
        return out

    def visit_Slice(self, node: pyast.Slice) -> slice:
        start = self.visit(node.start) if node.start is not None else None
        stop = self.visit(node.stop) if node.stop is not None else None
        step = self.visit(node.step) if node.step is not None else None
        return slice(start, stop, step)


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
    "__in__": lambda a, b: a in b,
    "__not_in__": lambda a, b: a not in b,
    "__logical_and__": lambda a, b: a and b,
    "__logical_or__": lambda a, b: a or b,
    "__if_stmt__": lambda cond, then_body, else_body: std.IfStmt(
        cond=cond,
        then_body=then_body,
        else_body=else_body,
    ),
}
