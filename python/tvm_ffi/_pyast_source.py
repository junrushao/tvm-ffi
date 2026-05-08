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

import enum
import inspect
import linecache
import sys
from types import CodeType, FrameType, FunctionType, MethodType, ModuleType, TracebackType
from typing import Any, Callable, Type, Union, cast

from typing_extensions import TypeAlias

from . import pyast
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


_ANSI_BOLD = "\033[1m"
_ANSI_RESET = "\033[0m"
_ANSI_FG_RESET = "\033[39m"
_ANSI_BLUE = "\033[34m"
_ANSI_RED = "\033[31m"
_ANSI_YELLOW = "\033[33m"


_DIAGNOSTIC_RENDER_INFO = {
    DiagnosticLevel.BUG: ("bug", _ANSI_BLUE),
    DiagnosticLevel.ERROR: ("error", _ANSI_RED),
    DiagnosticLevel.WARNING: ("warning", _ANSI_YELLOW),
    DiagnosticLevel.NOTE: ("note", _ANSI_FG_RESET),
    DiagnosticLevel.HELP: ("help", _ANSI_FG_RESET),
}


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

    def format_error(
        self,
        node: pyast.Node,
        message: str,
        level: DiagnosticLevel,
        *,
        color: bool = False,
    ) -> str:
        """Render a source diagnostic without writing it to stderr."""
        lineno = node.lineno if node.lineno > 0 else 1
        col_offset = node.col_offset if node.col_offset >= 0 else 0
        end_lineno = node.end_lineno if node.end_lineno > 0 else lineno
        end_col_offset = node.end_col_offset if node.end_col_offset >= 0 else col_offset + 1
        end_lineno = max(end_lineno, lineno)
        if end_lineno == lineno and end_col_offset <= col_offset:
            end_col_offset = col_offset + 1

        lineno += self.start_line - 1
        end_lineno += self.start_line - 1
        col_offset += self.start_column + 1
        end_col_offset += self.start_column + 1

        diagnostic_type, diagnostic_color = _DIAGNOSTIC_RENDER_INFO[level]
        if color:
            header = (
                f"{_ANSI_BOLD}{diagnostic_color}{diagnostic_type}: "
                f"{_ANSI_FG_RESET}{message}\n"
                f"{_ANSI_BLUE} --> {_ANSI_FG_RESET}{_ANSI_RESET}"
                f"{self.source_name}:{lineno}:{col_offset}\n"
            )
        else:
            header = (
                f"{diagnostic_type}: {message}\n --> {self.source_name}:{lineno}:{col_offset}\n"
            )
        output = [header]

        source_lines = self.full_source.splitlines()
        line_no_width = len(f" {end_lineno} ")
        empty_line_header = " " * line_no_width
        output.append(f"{empty_line_header}|  \n")

        for current_lineno in range(lineno, end_lineno + 1):
            line_text = (
                source_lines[current_lineno - 1] if 0 < current_lineno <= len(source_lines) else ""
            )
            line_header = f" {current_lineno} ".rjust(line_no_width)
            output.append(f"{line_header}|  {line_text}\n")
            marker_start = col_offset if current_lineno == lineno else 1
            marker_end = end_col_offset if current_lineno == end_lineno else len(line_text) + 1
            marker_end = max(marker_start + 1, marker_end)
            marker = "".join(
                "^" if marker_start <= i < marker_end else " " for i in range(1, len(line_text) + 1)
            )
            if not marker.strip():
                marker = " " * (marker_start - 1) + "^"
            output.append(f"{empty_line_header}|  {marker}\n")

        return "".join(output)


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
