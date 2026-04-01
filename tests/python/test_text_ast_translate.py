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
"""Tests for Python ast -> TVM-FFI AST converter."""

from __future__ import annotations

import ast
import itertools
import textwrap

import pytest
import tvm_ffi.text as tvmt
from tvm_ffi.text.ast_translate import ast_translate


def _roundtrip(source: str, *, indent: int = 4) -> str:
    """Parse source, convert to TVM-FFI AST, render back to Python."""
    node = ast_translate(textwrap.dedent(source))
    cfg = tvmt.PrinterConfig(indent_spaces=indent)
    return node.to_python(cfg)


# ---------------------------------------------------------------------------
# Expression round-trips
# ---------------------------------------------------------------------------

EXPR_CASES = [
    # Literals
    ("42", "42"),
    ("3.14", "3.1400000000000001"),
    ('"hello"', '"hello"'),
    ("True", "True"),
    ("False", "False"),
    ("None", "None"),
    # Identifiers
    ("x", "x"),
    ("my_var", "my_var"),
    # Attribute access
    ("x.y", "x.y"),
    ("a.b.c", "a.b.c"),
    # Index / subscript
    ("x[0]", "x[0]"),
    ("x[0, 1]", "x[0, 1]"),
    # Slice
    ("x[1:2]", "x[1:2]"),
    ("x[::2]", "x[::2]"),
    ("x[:5]", "x[:5]"),
    # Call
    ("f()", "f()"),
    ("f(1, 2)", "f(1, 2)"),
    ("f(x, y=1)", "f(x, y=1)"),
    # Unary ops
    ("-x", "-x"),
    ("~x", "~x"),
    ("not x", "not x"),
    ("+x", "+x"),
    # Binary ops
    ("x + y", "x + y"),
    ("x - y", "x - y"),
    ("x * y", "x * y"),
    ("x / y", "x / y"),
    ("x // y", "x // y"),
    ("x % y", "x % y"),
    ("x ** y", "x ** y"),
    ("x << y", "x << y"),
    ("x >> y", "x >> y"),
    ("x & y", "x & y"),
    ("x | y", "x | y"),
    ("x ^ y", "x ^ y"),
    # Comparison
    ("x < y", "x < y"),
    ("x <= y", "x <= y"),
    ("x > y", "x > y"),
    ("x >= y", "x >= y"),
    ("x == y", "x == y"),
    ("x != y", "x != y"),
    # Boolean ops
    ("x and y", "x and y"),
    ("x or y", "x or y"),
    ("a and b and c", "a and b and c"),
    ("a or b or c", "a or b or c"),
    # Ternary / IfExp
    ("a if cond else b", "a if cond else b"),
    # Lambda
    ("lambda x: x", "lambda x: x"),
    ("lambda x, y: x + y", "lambda x, y: x + y"),
    # Tuple / List / Dict
    ("(1, 2, 3)", "(1, 2, 3)"),
    ("[1, 2, 3]", "[1, 2, 3]"),
    ('{"a": 1, "b": 2}', '{"a": 1, "b": 2}'),
]


@pytest.mark.parametrize("source,expected", EXPR_CASES, ids=itertools.count())
def test_expr_roundtrip(source: str, expected: str) -> None:
    tree = ast.parse(source, mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == expected


# ---------------------------------------------------------------------------
# Chained comparison
# ---------------------------------------------------------------------------


def test_chained_comparison() -> None:
    tree = ast.parse("a < b < c", mode="eval")
    node = ast_translate(tree)
    result = node.to_python()
    assert result == "a < b < c"


def test_triple_chained_comparison() -> None:
    tree = ast.parse("a < b <= c < d", mode="eval")
    node = ast_translate(tree)
    result = node.to_python()
    assert result == "a < b <= c < d"


# ---------------------------------------------------------------------------
# Statement round-trips
# ---------------------------------------------------------------------------


def test_assign() -> None:
    result = _roundtrip("x = 42")
    assert "x = 42" in result


def test_annotated_assign() -> None:
    result = _roundtrip("x: int = 42")
    assert "x: int = 42" in result


def test_annotated_assign_no_value() -> None:
    result = _roundtrip("x: int")
    assert "x: int" in result


def test_augmented_assign() -> None:
    result = _roundtrip("x += 1")
    assert "x += 1" in result


def test_multi_target_assign() -> None:
    result = _roundtrip("a = b = 1")
    assert "a = b = 1" in result


def test_if_else() -> None:
    source = """\
    if x:
        a
    else:
        b
    """
    result = _roundtrip(source)
    assert "if x:" in result
    assert "else:" in result


def test_if_elif_else() -> None:
    source = """\
    if x:
        a
    elif y:
        b
    else:
        c
    """
    result = _roundtrip(source)
    assert "if x:" in result
    assert "if y:" in result


def test_while() -> None:
    source = """\
    while cond:
        step
    """
    result = _roundtrip(source)
    assert "while cond:" in result


def test_for() -> None:
    source = """\
    for i in items:
        process
    """
    result = _roundtrip(source)
    assert "for i in items:" in result


def test_with_single() -> None:
    source = """\
    with ctx() as c:
        body
    """
    result = _roundtrip(source)
    assert "with ctx() as c:" in result


def test_with_multi() -> None:
    source = """\
    with a() as x, b() as y:
        body
    """
    result = _roundtrip(source)
    assert "with a() as x, b() as y:" in result


def test_function_def() -> None:
    source = """\
    def add(a, b):
        return a + b
    """
    result = _roundtrip(source)
    assert "def add(a, b):" in result
    assert "return a + b" in result


def test_function_def_with_types() -> None:
    source = """\
    def greet(name: str) -> str:
        return name
    """
    result = _roundtrip(source)
    assert "name: str" in result
    assert "-> str:" in result


def test_function_def_with_defaults() -> None:
    source = """\
    def f(a, b=1, c=2):
        pass
    """
    result = _roundtrip(source)
    assert "b = 1" in result
    assert "c = 2" in result


def test_function_def_with_decorator() -> None:
    source = """\
    @staticmethod
    def f():
        pass
    """
    result = _roundtrip(source)
    assert "@staticmethod" in result
    assert "def f():" in result


def test_class_def() -> None:
    source = """\
    class Foo:
        x = 1
    """
    result = _roundtrip(source)
    assert "class Foo:" in result


def test_class_def_with_decorator() -> None:
    source = """\
    @dataclass
    class Foo:
        x = 1
    """
    result = _roundtrip(source)
    assert "@dataclass" in result


def test_return() -> None:
    result = _roundtrip("return 42")
    assert "return 42" in result


def test_return_bare() -> None:
    result = _roundtrip("return")
    assert "return" in result


def test_assert_simple() -> None:
    result = _roundtrip("assert x")
    assert "assert x" in result


def test_assert_with_msg() -> None:
    result = _roundtrip('assert x, "error"')
    assert "assert x" in result


def test_pass() -> None:
    result = _roundtrip("pass")
    assert "pass" in result


def test_break() -> None:
    source = """\
    while True:
        break
    """
    result = _roundtrip(source)
    assert "break" in result


def test_continue() -> None:
    source = """\
    while True:
        continue
    """
    result = _roundtrip(source)
    assert "continue" in result


def test_import() -> None:
    result = _roundtrip("import os")
    assert "import os" in result


def test_import_from() -> None:
    result = _roundtrip("from os import path")
    assert "from os import path" in result


def test_delete() -> None:
    result = _roundtrip("del x")
    assert "del x" in result


def test_raise() -> None:
    result = _roundtrip("raise ValueError")
    assert "raise ValueError" in result


def test_raise_bare() -> None:
    result = _roundtrip("raise")
    assert "raise" in result


def test_global() -> None:
    result = _roundtrip("global x")
    assert "global x" in result


def test_nonlocal() -> None:
    source = """\
    def f():
        nonlocal x
    """
    result = _roundtrip(source)
    assert "nonlocal x" in result


# ---------------------------------------------------------------------------
# Docstring detection
# ---------------------------------------------------------------------------


def test_function_docstring() -> None:
    source = '''\
    def f():
        """My docstring."""
        pass
    '''
    result = _roundtrip(source)
    assert "My docstring." in result
    assert '"""' in result


def test_module_docstring() -> None:
    source = '"""Module docstring."""\nx = 1'
    result = _roundtrip(source)
    assert "Module docstring." in result
    assert '"""' in result


def test_class_docstring() -> None:
    source = '''\
    class Foo:
        """Class doc."""
        pass
    '''
    result = _roundtrip(source)
    assert "Class doc." in result
    assert '"""' in result


# ---------------------------------------------------------------------------
# Source string input
# ---------------------------------------------------------------------------


def test_from_source_string() -> None:
    node = ast_translate("x = 1")
    assert isinstance(node, tvmt.ast.StmtBlock)


def test_from_ast_node() -> None:
    tree = ast.parse("x + 1", mode="eval")
    node = ast_translate(tree)
    assert isinstance(node, tvmt.ast.Expr)


# ---------------------------------------------------------------------------
# Unsupported constructs
# ---------------------------------------------------------------------------


def test_try_except() -> None:
    result = _roundtrip("try:\n    pass\nexcept:\n    pass")
    assert "try:" in result
    assert "except:" in result


def test_try_except_finally() -> None:
    source = "try:\n    a\nexcept ValueError as e:\n    b\nfinally:\n    c"
    result = _roundtrip(source)
    assert "try:" in result
    assert "except ValueError as e:" in result
    assert "finally:" in result


def test_matmul() -> None:
    tree = ast.parse("a @ b", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "a @ b"


def test_is_operator() -> None:
    tree = ast.parse("x is None", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "x is None"


def test_is_not_operator() -> None:
    tree = ast.parse("x is not None", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "x is not None"


def test_in_operator() -> None:
    tree = ast.parse("x in y", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "x in y"


def test_not_in_operator() -> None:
    tree = ast.parse("x not in y", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "x not in y"


def test_starred_expr() -> None:
    node = ast.Expression(body=ast.Starred(value=ast.Name(id="x"), ctx=ast.Load()))
    ast.fix_missing_locations(node)
    result = ast_translate(node)
    assert result.to_python() == "*x"


def test_kwargs_splat() -> None:
    tree = ast.parse("f(**d)", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "f(**d)"


def test_fstring() -> None:
    tree = ast.parse('f"hello {x}"', mode="eval")
    node = ast_translate(tree)
    result = node.to_python()
    assert "hello" in result
    assert "{x}" in result


def test_walrus_expr() -> None:
    tree = ast.parse("(x := 10)", mode="eval")
    node = ast_translate(tree)
    result = node.to_python()
    assert "x := 10" in result


def test_await_expr() -> None:
    source = "async def f():\n    await coro()"
    result = _roundtrip(source)
    assert "async def" in result
    assert "await coro()" in result


def test_async_for() -> None:
    source = "async def f():\n    async for x in items:\n        pass"
    result = _roundtrip(source)
    assert "async for" in result


def test_async_with() -> None:
    source = "async def f():\n    async with ctx():\n        pass"
    result = _roundtrip(source)
    assert "async with" in result


def test_class_bases() -> None:
    source = "class Foo(Bar, Baz):\n    pass"
    result = _roundtrip(source)
    assert "class Foo(Bar, Baz):" in result


def test_while_else() -> None:
    source = "while cond:\n    a\nelse:\n    b"
    result = _roundtrip(source)
    assert "while cond:" in result
    assert "else:" in result


def test_for_else() -> None:
    source = "for x in items:\n    a\nelse:\n    b"
    result = _roundtrip(source)
    assert "for x in items:" in result
    assert "else:" in result


def test_function_varargs() -> None:
    source = "def f(*args, **kwargs):\n    pass"
    result = _roundtrip(source)
    assert "*args" in result
    assert "**kwargs" in result


# ---------------------------------------------------------------------------
# New node types: set, comprehension, yield
# ---------------------------------------------------------------------------


def test_set_literal() -> None:
    tree = ast.parse("{1, 2, 3}", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "{1, 2, 3}"


def test_list_comprehension() -> None:
    tree = ast.parse("[x for x in items]", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "[x for x in items]"


def test_set_comprehension() -> None:
    tree = ast.parse("{x for x in items}", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "{x for x in items}"


def test_dict_comprehension() -> None:
    tree = ast.parse("{k: v for k, v in items}", mode="eval")
    node = ast_translate(tree)
    result = node.to_python()
    assert "k: v" in result
    assert "for (k, v) in items" in result


def test_generator_expression() -> None:
    tree = ast.parse("(x for x in items)", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "(x for x in items)"


def test_comprehension_with_filter() -> None:
    tree = ast.parse("[x for x in items if x > 0]", mode="eval")
    node = ast_translate(tree)
    assert node.to_python() == "[x for x in items if x > 0]"


def test_comprehension_nested() -> None:
    tree = ast.parse("[x + y for x in xs for y in ys]", mode="eval")
    node = ast_translate(tree)
    result = node.to_python()
    assert "for x in xs" in result
    assert "for y in ys" in result


def test_yield_value() -> None:
    source = """\
    def gen():
        yield 1
    """
    result = _roundtrip(source)
    assert "yield 1" in result


def test_yield_bare() -> None:
    source = """\
    def gen():
        yield
    """
    result = _roundtrip(source)
    assert "yield" in result


def test_yield_from() -> None:
    source = """\
    def gen():
        yield from items
    """
    result = _roundtrip(source)
    assert "yield from items" in result


# ---------------------------------------------------------------------------
# Span information
# ---------------------------------------------------------------------------


def test_span_info_expr() -> None:
    tree = ast.parse("x + 1", mode="eval")
    node = ast_translate(tree)
    # The top-level BinOp node should have span info
    assert node.lineno == 1
    assert node.col_offset == 0
    assert node.end_lineno == 1
    assert node.end_col_offset == 5


def test_span_info_stmt() -> None:
    node = ast_translate("x = 42")
    # StmtBlock wrapping
    assert isinstance(node, tvmt.ast.StmtBlock)
    stmt = node.stmts[0]
    assert stmt.lineno == 1
    assert stmt.col_offset == 0


def test_span_info_default() -> None:
    # Manually constructed nodes have -1 span
    node = tvmt.ast.Id("x")
    assert node.lineno == -1
    assert node.col_offset == -1
    assert node.end_lineno == -1
    assert node.end_col_offset == -1


# ---------------------------------------------------------------------------
# Complex round-trip
# ---------------------------------------------------------------------------


def test_complex_function() -> None:
    source = """\
    @decorator
    def compute(x: int, y: int = 0) -> int:
        \"\"\"Compute sum.\"\"\"
        if x > 0:
            return x + y
        else:
            return y
    """
    result = _roundtrip(source)
    assert "@decorator" in result
    assert "def compute" in result
    assert "Compute sum." in result
    assert "if x > 0:" in result
    assert "return x + y" in result
    assert "return y" in result
