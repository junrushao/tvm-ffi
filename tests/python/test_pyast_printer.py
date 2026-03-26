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
"""Tests for tvm_ffi.pyast printer, ported from mlc-python's test_printer_ir_printer.py."""

from __future__ import annotations

import re
from typing import Any, List

import pytest
from tvm_ffi import Object, pyast
from tvm_ffi.access_path import AccessPath
from tvm_ffi.dataclasses import field as dc_field
from tvm_ffi.dataclasses import py_class


@py_class("testing.text.toy_ir.Node")
class Node(Object):
    """Base class for all toy IR nodes."""


@py_class("testing.text.toy_ir.Expr")
class Expr(Node):
    """Base class for toy IR expression nodes."""


@py_class("testing.text.toy_ir.Stmt")
class Stmt(Node):
    """Base class for toy IR statement nodes."""


@py_class("testing.text.toy_ir.Var", structural_eq="var")
class Var(Expr):
    """A variable reference in the toy IR."""

    name: str = dc_field(structural_eq="ignore")

    def __add__(self, other: Var) -> Add:
        return Add(lhs=self, rhs=other)

    def __ffi_text_print__(self, printer: pyast.IRPrinter, path: AccessPath) -> Any:
        if not printer.var_is_defined(self):
            printer.var_def(self.name, self, None)
        ret = printer.var_get(self)
        assert ret is not None
        return ret


@py_class("testing.text.toy_ir.Add", structural_eq="dag")
class Add(Expr):
    """Binary addition expression in the toy IR."""

    lhs: Expr
    rhs: Expr

    def __ffi_text_print__(self, printer: pyast.IRPrinter, path: AccessPath) -> Any:
        lhs = printer(self.lhs, path=path.attr("lhs"))
        rhs = printer(self.rhs, path=path.attr("rhs"))
        return lhs + rhs


@py_class("testing.text.toy_ir.Assign", structural_eq="tree")
class Assign(Stmt):
    """Assignment statement in the toy IR."""

    rhs: Expr
    lhs: Var = dc_field(structural_eq="def")

    def __ffi_text_print__(self, printer: pyast.IRPrinter, path: AccessPath) -> Any:
        rhs = printer(self.rhs, path=path.attr("rhs"))
        printer.var_def(self.lhs.name, self.lhs, None)
        lhs = printer(self.lhs, path=path.attr("lhs"))
        return pyast.Assign(lhs, rhs)


@py_class("testing.text.toy_ir.Func", structural_eq="tree")
class Func(Node):
    """A function definition in the toy IR."""

    name: str = dc_field(structural_eq="ignore")
    args: List[Var] = dc_field(structural_eq="def")  # noqa: UP006
    stmts: List[Stmt]  # noqa: UP006
    ret: Var

    def __ffi_text_print__(self, printer: pyast.IRPrinter, path: AccessPath) -> Any:
        with printer.with_frame(pyast.DefaultFrame()):
            for arg in self.args:
                printer.var_def(arg.name, arg, None)
            args = [
                printer(arg, path=path.attr("args").array_item(i))
                for i, arg in enumerate(self.args)
            ]
            stmts = [
                printer(stmt, path=path.attr("stmts").array_item(i))
                for i, stmt in enumerate(self.stmts)
            ]
            ret_stmt = pyast.Return(printer(self.ret, path=path.attr("ret")))
            return pyast.Function(
                pyast.Id(self.name),
                [pyast.Assign(arg, None) for arg in args],
                [],
                None,
                [*stmts, ret_stmt],
            )


def _to_python(value: Any, config: pyast.PrinterConfig | None = None) -> str:
    return pyast.to_python(value, config)


def _sample_func() -> Func:
    a = Var(name="a")
    b = Var(name="b")
    c = Var(name="c")
    return Func(name="f", args=[a, b], stmts=[Assign(lhs=c, rhs=Add(a, b))], ret=c)


def test_var_print() -> None:
    assert _to_python(Var(name="a")) == "a"


def test_var_print_name_normalize() -> None:
    assert _to_python(Var(name="a/0/b")) == "a_0_b"


def test_add_print() -> None:
    a = Var(name="a")
    b = Var(name="b")
    assert _to_python(Add(lhs=a, rhs=b)) == "a + b"


def test_assign_print() -> None:
    a = Var(name="a")
    b = Var(name="b")
    assert _to_python(Assign(lhs=a, rhs=b)) == "a = b"


def test_break_continue_print() -> None:
    assert pyast.Break().to_python() == "break"
    assert pyast.Continue().to_python() == "continue"


def test_func_print() -> None:
    a = Var(name="a")
    b = Var(name="b")
    c = Var(name="c")
    d = Var(name="d")
    e = Var(name="e")
    stmts: list[Stmt] = [
        Assign(lhs=d, rhs=Add(a, b)),
        Assign(lhs=e, rhs=Add(d, c)),
    ]
    assert (
        _to_python(Func(name="f", args=[a, b, c], stmts=stmts, ret=e))
        == """
def f(a, b, c):
  d = a + b
  e = d + c
  return e
""".strip()
    )


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "None"),
        (42, "42"),
        ("hey", '"hey"'),
        (True, "True"),
    ],
)
def test_print_builtin(value: Any, expected: str) -> None:
    node = pyast.IRPrinter()(value, AccessPath.root())
    assert node.to_python() == expected


def test_duplicated_vars() -> None:
    a = Var(name="a")
    b = Var(name="a")
    f = Func(
        name="f",
        args=[a],
        stmts=[Assign(lhs=b, rhs=Add(a, a))],
        ret=b,
    )
    assert (
        _to_python(f)
        == """
def f(a):
  a_1 = a + a
  return a_1
""".strip()
    )
    assert re.fullmatch(
        r"^def f\(a\):\n"
        r"  a_0x[0-9A-Fa-f]+ = a \+ a\n"
        r"  return a_0x[0-9A-Fa-f]+$",
        _to_python(f, pyast.PrinterConfig(print_addr_on_dup_var=True)),
    )


@pytest.mark.parametrize(
    "path, expected",
    [
        (
            AccessPath.root().attr("args").array_item(0),
            """
def f(a, b):
      ^
  c = a + b
  return c
""",
        ),
        (
            AccessPath.root().attr("args").array_item(1),
            """
def f(a, b):
         ^
  c = a + b
  return c
""",
        ),
        (
            AccessPath.root().attr("stmts").array_item(0),
            """
def f(a, b):
  c = a + b
  ^^^^^^^^^
  return c
""",
        ),
        (
            AccessPath.root().attr("stmts").array_item(0).attr("lhs"),
            """
def f(a, b):
  c = a + b
  ^
  return c
""",
        ),
        (
            AccessPath.root().attr("stmts").array_item(0).attr("rhs"),
            """
def f(a, b):
  c = a + b
      ^^^^^
  return c
""",
        ),
        (
            AccessPath.root().attr("stmts").array_item(0).attr("rhs").attr("lhs"),
            """
def f(a, b):
  c = a + b
      ^
  return c
""",
        ),
        (
            AccessPath.root().attr("stmts").array_item(0).attr("rhs").attr("rhs"),
            """
def f(a, b):
  c = a + b
          ^
  return c
""",
        ),
        (
            AccessPath.root().attr("ret"),
            """
def f(a, b):
  c = a + b
  return c
         ^
""",
        ),
    ],
)
def test_print_underscore(path: AccessPath, expected: str) -> None:
    actual = _to_python(_sample_func(), pyast.PrinterConfig(path_to_underline=[path]))
    assert actual.strip() == expected.strip()
