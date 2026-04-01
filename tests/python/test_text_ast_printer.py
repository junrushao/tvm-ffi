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
"""Tests for text printer AST nodes, ported from mlc-python's test_printer_ast.py."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

import pytest
import tvm_ffi.text as tvmt

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


@pytest.mark.parametrize(
    "doc,expected",
    [
        (tvmt.ast.Literal(None), "None"),
        (tvmt.ast.Literal(True), "True"),
        (tvmt.ast.Literal(False), "False"),
        (tvmt.ast.Literal("test"), '"test"'),
        (tvmt.ast.Literal(""), '""'),
        (tvmt.ast.Literal('""'), r'"\"\""'),
        (tvmt.ast.Literal("\n\t\\test\r"), r'"\n\t\\test\r"'),
        (tvmt.ast.Literal(0), "0"),
        (tvmt.ast.Literal(-1), "-1"),
        (tvmt.ast.Literal(3.25), "3.25"),
        (tvmt.ast.Literal(-0.5), "-0.5"),
    ],
    ids=itertools.count(),
)
def test_print_literal(doc: tvmt.ast.Node, expected: str) -> None:
    assert doc.to_python() == expected


@pytest.mark.parametrize(
    "name",
    [
        "test",
        "_test",
        "TestCase",
        "test_case",
        "test123",
    ],
    ids=itertools.count(),
)
def test_print_id(name: str) -> None:
    doc = tvmt.ast.Id(name)
    assert doc.to_python() == name


@pytest.mark.parametrize(
    "attr",
    [
        "attr",
        "_attr",
        "Attr",
        "attr_1",
    ],
    ids=itertools.count(),
)
def test_print_attr(attr: str) -> None:
    doc = tvmt.ast.Id("x").attr(attr)
    assert doc.to_python() == f"x.{attr}"


@pytest.mark.parametrize(
    "indices, expected",
    [
        (
            (),
            "[()]",
        ),
        (
            (tvmt.ast.Literal(1),),
            "[1]",
        ),
        (
            (tvmt.ast.Literal(2), tvmt.ast.Id("x")),
            "[2, x]",
        ),
        (
            (tvmt.ast.Slice(tvmt.ast.Literal(1), tvmt.ast.Literal(2)),),
            "[1:2]",
        ),
        (
            (tvmt.ast.Slice(tvmt.ast.Literal(1)), tvmt.ast.Id("y")),
            "[1:, y]",
        ),
        (
            (tvmt.ast.Slice(), tvmt.ast.Id("y")),
            "[:, y]",
        ),
        (
            (tvmt.ast.Id("x"), tvmt.ast.Id("y"), tvmt.ast.Id("z")),
            "[x, y, z]",
        ),
    ],
    ids=itertools.count(),
)
def test_print_index(indices: tuple[tvmt.ast.Expr, ...], expected: str) -> None:
    doc = tvmt.ast.Id("x")[indices]
    assert doc.to_python() == f"x{expected}"


UNARY_OP_TOKENS = {
    tvmt.ast.OperationKind.USub: "-",
    tvmt.ast.OperationKind.Invert: "~",
    tvmt.ast.OperationKind.Not: "not ",
}


@pytest.mark.parametrize(
    "op_kind, expected_token",
    list(UNARY_OP_TOKENS.items()),
    ids=UNARY_OP_TOKENS.keys(),
)
def test_print_unary_operation(op_kind: int, expected_token: str) -> None:
    doc = tvmt.ast.Operation(op_kind, [tvmt.ast.Id("x")])
    assert doc.to_python() == f"{expected_token}x"


BINARY_OP_TOKENS = {
    tvmt.ast.OperationKind.Add: "+",
    tvmt.ast.OperationKind.Sub: "-",
    tvmt.ast.OperationKind.Mult: "*",
    tvmt.ast.OperationKind.Div: "/",
    tvmt.ast.OperationKind.FloorDiv: "//",
    tvmt.ast.OperationKind.Mod: "%",
    tvmt.ast.OperationKind.Pow: "**",
    tvmt.ast.OperationKind.LShift: "<<",
    tvmt.ast.OperationKind.RShift: ">>",
    tvmt.ast.OperationKind.BitAnd: "&",
    tvmt.ast.OperationKind.BitOr: "|",
    tvmt.ast.OperationKind.BitXor: "^",
    tvmt.ast.OperationKind.Lt: "<",
    tvmt.ast.OperationKind.LtE: "<=",
    tvmt.ast.OperationKind.Eq: "==",
    tvmt.ast.OperationKind.NotEq: "!=",
    tvmt.ast.OperationKind.Gt: ">",
    tvmt.ast.OperationKind.GtE: ">=",
    tvmt.ast.OperationKind.And: "and",
    tvmt.ast.OperationKind.Or: "or",
}


@pytest.mark.parametrize(
    "op_kind, expected_token",
    list(BINARY_OP_TOKENS.items()),
    ids=BINARY_OP_TOKENS.keys(),
)
def test_print_binary_operation(op_kind: int, expected_token: str) -> None:
    doc = tvmt.ast.Operation(op_kind, [tvmt.ast.Id("x"), tvmt.ast.Id("y")])
    assert doc.to_python() == f"x {expected_token} y"


SPECIAL_OP_CASES = [
    (
        tvmt.ast.OperationKind.IfThenElse,
        [tvmt.ast.Literal(True), tvmt.ast.Literal("true"), tvmt.ast.Literal("false")],
        '"true" if True else "false"',
    ),
    (
        tvmt.ast.OperationKind.IfThenElse,
        [tvmt.ast.Id("x"), tvmt.ast.Literal(None), tvmt.ast.Literal(1)],
        "None if x else 1",
    ),
]


@pytest.mark.parametrize(
    "op_kind, operands, expected",
    SPECIAL_OP_CASES,
    ids=[kind for (kind, *_) in SPECIAL_OP_CASES],
)
def test_print_special_operation(
    op_kind: int,
    operands: list[tvmt.ast.Expr],
    expected: str,
) -> None:
    doc = tvmt.ast.Operation(op_kind, operands)
    assert doc.to_python() == expected


@pytest.mark.parametrize(
    "args, kwargs, expected",
    [
        (
            (),
            {},
            "()",
        ),
        (
            (),
            {"key0": tvmt.ast.Id("u")},
            "(key0=u)",
        ),
        (
            (),
            {"key0": tvmt.ast.Id("u"), "key1": tvmt.ast.Id("v")},
            "(key0=u, key1=v)",
        ),
        (
            (tvmt.ast.Id("x"),),
            {},
            "(x)",
        ),
        (
            (tvmt.ast.Id("x"),),
            {"key0": tvmt.ast.Id("u")},
            "(x, key0=u)",
        ),
        (
            (tvmt.ast.Id("x"),),
            {"key0": tvmt.ast.Id("u"), "key1": tvmt.ast.Id("v")},
            "(x, key0=u, key1=v)",
        ),
        (
            (tvmt.ast.Id("x"), (tvmt.ast.Id("y"))),
            {},
            "(x, y)",
        ),
        (
            (tvmt.ast.Id("x"), (tvmt.ast.Id("y"))),
            {"key0": tvmt.ast.Id("u")},
            "(x, y, key0=u)",
        ),
        (
            (tvmt.ast.Id("x"), (tvmt.ast.Id("y"))),
            {"key0": tvmt.ast.Id("u"), "key1": tvmt.ast.Id("v")},
            "(x, y, key0=u, key1=v)",
        ),
    ],
    ids=itertools.count(),
)
def test_print_call(
    args: tuple[tvmt.ast.Expr, ...],
    kwargs: dict[str, tvmt.ast.Expr],
    expected: str,
) -> None:
    kwargs_keys: list[str] = []
    kwargs_values: list[tvmt.ast.Expr] = []
    for key, value in kwargs.items():
        kwargs_keys.append(key)
        kwargs_values.append(value)
    doc = tvmt.ast.Id("f").call_kw(
        args,
        kwargs_keys,
        kwargs_values,
    )
    assert doc.to_python() == f"f{expected}"


@pytest.mark.parametrize(
    "args, expected",
    [
        (
            (),
            "lambda : 0",
        ),
        (
            (tvmt.ast.Id("x"),),
            "lambda x: 0",
        ),
        (
            (tvmt.ast.Id("x"), tvmt.ast.Id("y")),
            "lambda x, y: 0",
        ),
        (
            (tvmt.ast.Id("x"), tvmt.ast.Id("y"), tvmt.ast.Id("z")),
            "lambda x, y, z: 0",
        ),
    ],
    ids=itertools.count(),
)
def test_print_lambda(args: tuple[tvmt.ast.Id, ...], expected: str) -> None:
    doc = tvmt.ast.Lambda(
        args,  # ty: ignore[invalid-argument-type]
        tvmt.ast.Literal(0),
    )
    assert doc.to_python() == expected


@pytest.mark.parametrize(
    "elements, expected",
    [
        (
            (),
            "[]",
        ),
        (
            [tvmt.ast.Id("x")],
            "[x]",
        ),
        (
            [tvmt.ast.Id("x"), tvmt.ast.Id("y")],
            "[x, y]",
        ),
        (
            [tvmt.ast.Id("x"), tvmt.ast.Id("y"), tvmt.ast.Id("z")],
            "[x, y, z]",
        ),
    ],
    ids=itertools.count(),
)
def test_print_list(elements: list[tvmt.ast.Expr], expected: str) -> None:
    doc = tvmt.ast.List(elements)
    assert doc.to_python() == expected


@pytest.mark.parametrize(
    "elements, expected",
    [
        (
            (),
            "()",
        ),
        (
            [tvmt.ast.Id("x")],
            "(x,)",
        ),
        (
            [tvmt.ast.Id("x"), tvmt.ast.Id("y")],
            "(x, y)",
        ),
        (
            [tvmt.ast.Id("x"), tvmt.ast.Id("y"), tvmt.ast.Id("z")],
            "(x, y, z)",
        ),
    ],
    ids=itertools.count(),
)
def test_print_tuple(elements: list[tvmt.ast.Id], expected: str) -> None:
    doc = tvmt.ast.Tuple(elements)  # ty: ignore[invalid-argument-type]
    assert doc.to_python() == expected


@pytest.mark.parametrize(
    "content, expected",
    [
        (
            {},
            "{}",
        ),
        (
            {tvmt.ast.Literal("key_x"): tvmt.ast.Id("x")},
            '{"key_x": x}',
        ),
        (
            {
                tvmt.ast.Literal("key_x"): tvmt.ast.Id("x"),
                tvmt.ast.Literal("key_y"): tvmt.ast.Id("y"),
            },
            '{"key_x": x, "key_y": y}',
        ),
        (
            {
                tvmt.ast.Literal("key_x"): tvmt.ast.Id("x"),
                tvmt.ast.Literal("key_y"): tvmt.ast.Id("y"),
                tvmt.ast.Literal("key_z"): tvmt.ast.Id("z"),
            },
            '{"key_x": x, "key_y": y, "key_z": z}',
        ),
    ],
    ids=itertools.count(),
)
def test_print_dict(content: dict[tvmt.ast.Expr, tvmt.ast.Expr], expected: str) -> None:
    keys = []
    values = []
    for key, value in content.items():
        keys.append(key)
        values.append(value)
    doc = tvmt.ast.Dict(keys, values)
    assert doc.to_python() == expected


@pytest.mark.parametrize(
    "slice_doc, expected",
    [
        (
            tvmt.ast.Slice(),
            ":",
        ),
        (
            tvmt.ast.Slice(tvmt.ast.Literal(1)),
            "1:",
        ),
        (
            tvmt.ast.Slice(None, tvmt.ast.Literal(2)),
            ":2",
        ),
        (
            tvmt.ast.Slice(tvmt.ast.Literal(1), tvmt.ast.Literal(2)),
            "1:2",
        ),
        (
            tvmt.ast.Slice(None, None, tvmt.ast.Literal(3)),
            "::3",
        ),
        (
            tvmt.ast.Slice(tvmt.ast.Literal(1), None, tvmt.ast.Literal(3)),
            "1::3",
        ),
        (
            tvmt.ast.Slice(None, tvmt.ast.Literal(2), tvmt.ast.Literal(3)),
            ":2:3",
        ),
        (
            tvmt.ast.Slice(tvmt.ast.Literal(1), tvmt.ast.Literal(2), tvmt.ast.Literal(3)),
            "1:2:3",
        ),
    ],
    ids=itertools.count(),
)
def test_print_slice(slice_doc: tvmt.ast.Slice, expected: str) -> None:
    doc = tvmt.ast.Id("x")[slice_doc]
    assert doc.to_python() == f"x[{expected}]"


@pytest.mark.parametrize(
    "stmts, expected",
    [
        (
            [],
            "",
        ),
        (
            [tvmt.ast.ExprStmt(tvmt.ast.Id("x"))],
            "x",
        ),
        (
            [tvmt.ast.ExprStmt(tvmt.ast.Id("x")), tvmt.ast.ExprStmt(tvmt.ast.Id("y"))],
            """
x
y""",
        ),
    ],
    ids=itertools.count(),
)
def test_print_stmt_block_doc(stmts: list[tvmt.ast.Stmt], expected: str) -> None:
    doc = tvmt.ast.StmtBlock(stmts)
    assert doc.to_python() == expected.strip()


@pytest.mark.parametrize(
    "doc, expected",
    [
        (
            tvmt.ast.Assign(tvmt.ast.Id("x"), tvmt.ast.Id("y"), None),
            "x = y",
        ),
        (
            tvmt.ast.Assign(tvmt.ast.Id("x"), tvmt.ast.Id("y"), tvmt.ast.Id("int")),
            "x: int = y",
        ),
        (
            tvmt.ast.Assign(tvmt.ast.Id("x"), None, tvmt.ast.Id("int")),
            "x: int",
        ),
        (
            tvmt.ast.Assign(
                tvmt.ast.Tuple([tvmt.ast.Id("x"), tvmt.ast.Id("y")]), tvmt.ast.Id("z"), None
            ),
            "x, y = z",
        ),
        (
            tvmt.ast.Assign(
                tvmt.ast.Tuple(
                    [tvmt.ast.Id("x"), tvmt.ast.Tuple([tvmt.ast.Id("y"), tvmt.ast.Id("z")])]
                ),
                tvmt.ast.Id("z"),
                None,
            ),
            "x, (y, z) = z",
        ),
        (
            tvmt.ast.Assign(
                tvmt.ast.Tuple([]),
                tvmt.ast.Operation(
                    tvmt.ast.OperationKind.Add,
                    [tvmt.ast.Id("x"), tvmt.ast.Id("y")],
                ),
                None,
            ),
            "x + y",
        ),
    ],
    ids=itertools.count(),
)
def test_print_assign_doc(doc: tvmt.ast.Assign, expected: str) -> None:
    assert doc.to_python() == expected


@pytest.mark.parametrize(
    "then_branch, else_branch, expected",
    [
        (
            [tvmt.ast.ExprStmt(tvmt.ast.Id("x"))],
            [],
            """
if pred:
    x""",
        ),
        (
            [],
            [tvmt.ast.ExprStmt(tvmt.ast.Id("y"))],
            """
if pred:
    pass
else:
    y""",
        ),
        (
            [tvmt.ast.ExprStmt(tvmt.ast.Id("x"))],
            [tvmt.ast.ExprStmt(tvmt.ast.Id("y"))],
            """
if pred:
    x
else:
    y""",
        ),
    ],
    ids=itertools.count(),
)
def test_print_if_doc(
    then_branch: list[tvmt.ast.Stmt], else_branch: list[tvmt.ast.Stmt], expected: str
) -> None:
    doc = tvmt.ast.If(tvmt.ast.Id("pred"), then_branch, else_branch)
    assert doc.to_python(tvmt.PrinterConfig(indent_spaces=4)) == expected.strip()


@pytest.mark.parametrize(
    "body, expected",
    [
        (
            [tvmt.ast.ExprStmt(tvmt.ast.Id("x"))],
            """
while pred:
    x
            """,
        ),
        (
            [],
            """
while pred:
    pass
""",
        ),
    ],
    ids=itertools.count(),
)
def test_print_while_doc(body: list[tvmt.ast.Stmt], expected: str) -> None:
    doc = tvmt.ast.While(tvmt.ast.Id("pred"), body)
    assert doc.to_python(tvmt.PrinterConfig(indent_spaces=4)) == expected.strip()


@pytest.mark.parametrize(
    "body, expected",
    [
        (
            [tvmt.ast.ExprStmt(tvmt.ast.Id("x"))],
            """
for x in y:
    x
""",
        ),
        (
            [],
            """
for x in y:
    pass
""",
        ),
    ],
    ids=itertools.count(),
)
def test_print_for_doc(body: list[tvmt.ast.Stmt], expected: str) -> None:
    doc = tvmt.ast.For(tvmt.ast.Id("x"), tvmt.ast.Id("y"), body)
    assert doc.to_python(tvmt.PrinterConfig(indent_spaces=4)) == expected.strip()


@pytest.mark.parametrize(
    "lhs, body, expected",
    [
        (
            tvmt.ast.Id("c"),
            [tvmt.ast.ExprStmt(tvmt.ast.Id("x"))],
            """
with context() as c:
    x
""",
        ),
        (
            tvmt.ast.Id("c"),
            [],
            """
with context() as c:
    pass
""",
        ),
        (
            None,
            [],
            """
with context():
    pass
""",
        ),
        (
            None,
            [tvmt.ast.ExprStmt(tvmt.ast.Id("x"))],
            """
with context():
    x
""",
        ),
    ],
    ids=itertools.count(),
)
def test_print_with_scope(lhs: tvmt.ast.Id, body: list[tvmt.ast.Stmt], expected: str) -> None:
    doc = tvmt.ast.With(
        lhs,
        tvmt.ast.Id("context").call(),
        body,
    )
    assert doc.to_python(tvmt.PrinterConfig(indent_spaces=4)) == expected.strip()


def test_print_expr_stmt_doc() -> None:
    doc = tvmt.ast.ExprStmt(tvmt.ast.Id("f").call(tvmt.ast.Id("x")))
    assert doc.to_python() == "f(x)"


@pytest.mark.parametrize(
    "msg, expected",
    [
        (
            None,
            """
            assert True
            """,
        ),
        (
            tvmt.ast.Literal("test message"),
            """
            assert True, "test message"
            """,
        ),
    ],
    ids=itertools.count(),
)
def test_print_assert_doc(msg: tvmt.ast.Expr | None, expected: str) -> None:
    test = tvmt.ast.Literal(True)
    doc = tvmt.ast.Assert(test, msg)
    assert doc.to_python().strip() == expected.strip()


@pytest.mark.parametrize(
    "value, expected",
    [(tvmt.ast.Literal(None), "return None"), (tvmt.ast.Id("x"), "return x")],
    ids=itertools.count(),
)
def test_print_return_doc(value: tvmt.ast.Expr, expected: str) -> None:
    doc = tvmt.ast.Return(value)
    assert doc.to_python() == expected.strip()


@pytest.mark.parametrize(
    "args, decorators, return_type, body, expected",
    [
        (
            [],
            [],
            None,
            [],
            """
def func():
    pass
""",
        ),
        (
            [tvmt.ast.Assign(tvmt.ast.Id("x"), None, tvmt.ast.Id("int"))],
            [],
            tvmt.ast.Id("int"),
            [],
            """
def func(x: int) -> int:
    pass
""",
        ),
        (
            [tvmt.ast.Assign(tvmt.ast.Id("x"), tvmt.ast.Literal(1), tvmt.ast.Id("int"))],
            [],
            tvmt.ast.Literal(None),
            [],
            """
def func(x: int = 1) -> None:
    pass
""",
        ),
        (
            [],
            [tvmt.ast.Id("wrap")],
            tvmt.ast.Literal(None),
            [],
            """
@wrap
def func() -> None:
    pass
""",
        ),
        (
            [],
            [tvmt.ast.Id("wrap_outter"), tvmt.ast.Id("wrap_inner")],
            tvmt.ast.Literal(None),
            [],
            """
@wrap_outter
@wrap_inner
def func() -> None:
    pass
""",
        ),
        (
            [
                tvmt.ast.Assign(tvmt.ast.Id("x"), None, tvmt.ast.Id("int")),
                tvmt.ast.Assign(tvmt.ast.Id("y"), tvmt.ast.Literal(1), tvmt.ast.Id("int")),
            ],
            [tvmt.ast.Id("wrap")],
            tvmt.ast.Literal(None),
            [],
            """
@wrap
def func(x: int, y: int = 1) -> None:
    pass
""",
        ),
        (
            [
                tvmt.ast.Assign(tvmt.ast.Id("x"), None, tvmt.ast.Id("int")),
                tvmt.ast.Assign(tvmt.ast.Id("y"), tvmt.ast.Literal(1), tvmt.ast.Id("int")),
            ],
            [tvmt.ast.Id("wrap")],
            tvmt.ast.Literal(None),
            [
                tvmt.ast.Assign(
                    tvmt.ast.Id("y"),
                    tvmt.ast.Operation(
                        tvmt.ast.OperationKind.Add, [tvmt.ast.Id("x"), tvmt.ast.Literal(1)]
                    ),
                ),
                tvmt.ast.Assign(
                    tvmt.ast.Id("y"),
                    tvmt.ast.Operation(
                        tvmt.ast.OperationKind.Sub, [tvmt.ast.Id("y"), tvmt.ast.Literal(1)]
                    ),
                ),
            ],
            """
@wrap
def func(x: int, y: int = 1) -> None:
    y = x + 1
    y = y - 1
""",
        ),
    ],
    ids=itertools.count(),
)
def test_print_function_doc(
    args: list[tvmt.ast.Assign],
    decorators: list[tvmt.ast.Id],
    body: list[tvmt.ast.Stmt],
    return_type: tvmt.ast.Expr | None,
    expected: str,
) -> None:
    doc = tvmt.ast.Function(
        tvmt.ast.Id("func"),
        args,
        decorators,  # ty: ignore[invalid-argument-type]
        return_type,
        body,
    )
    assert doc.to_python(tvmt.PrinterConfig(indent_spaces=4)) == expected.strip()


def get_func_doc_for_class(name: str) -> tvmt.ast.Function:
    args = [
        tvmt.ast.Assign(tvmt.ast.Id("x"), None, tvmt.ast.Id("int")),
        tvmt.ast.Assign(tvmt.ast.Id("y"), tvmt.ast.Literal(1), tvmt.ast.Id("int")),
    ]
    body = [
        tvmt.ast.Assign(
            tvmt.ast.Id("y"),
            tvmt.ast.Operation(tvmt.ast.OperationKind.Add, [tvmt.ast.Id("x"), tvmt.ast.Literal(1)]),
        ),
        tvmt.ast.Assign(
            tvmt.ast.Id("y"),
            tvmt.ast.Operation(tvmt.ast.OperationKind.Sub, [tvmt.ast.Id("y"), tvmt.ast.Literal(1)]),
        ),
    ]
    return tvmt.ast.Function(
        tvmt.ast.Id(name),
        args,
        [tvmt.ast.Id("wrap")],
        tvmt.ast.Literal(None),
        body,
    )


@pytest.mark.parametrize(
    "decorators, body, expected",
    [
        (
            [],
            [],
            """
class TestClass:
    pass
""",
        ),
        (
            [tvmt.ast.Id("wrap")],
            [],
            """
@wrap
class TestClass:
    pass
""",
        ),
        (
            [tvmt.ast.Id("wrap_outter"), tvmt.ast.Id("wrap_inner")],
            [],
            """
@wrap_outter
@wrap_inner
class TestClass:
    pass
""",
        ),
        (
            [tvmt.ast.Id("wrap")],
            [get_func_doc_for_class("f1")],
            """
@wrap
class TestClass:
    @wrap
    def f1(x: int, y: int = 1) -> None:
        y = x + 1
        y = y - 1
""",
        ),
        (
            [tvmt.ast.Id("wrap")],
            [get_func_doc_for_class("f1"), get_func_doc_for_class("f2")],
            """
@wrap
class TestClass:
    @wrap
    def f1(x: int, y: int = 1) -> None:
        y = x + 1
        y = y - 1

    @wrap
    def f2(x: int, y: int = 1) -> None:
        y = x + 1
        y = y - 1""",
        ),
    ],
    ids=itertools.count(),
)
def test_print_class_doc(
    decorators: list[tvmt.ast.Id],
    body: list[tvmt.ast.Function],
    expected: str,
) -> None:
    doc = tvmt.ast.Class(
        tvmt.ast.Id("TestClass"),
        [],  # bases
        decorators,  # ty: ignore[invalid-argument-type]
        body,  # ty: ignore[invalid-argument-type]
    )
    assert doc.to_python(tvmt.PrinterConfig(indent_spaces=4)) == expected.strip()


@pytest.mark.parametrize(
    "comment, expected",
    [
        ("", "#"),
        ("test comment 1", "# test comment 1"),
        (
            "test comment 1\ntest comment 2",
            """
# test comment 1
# test comment 2
""",
        ),
    ],
    ids=itertools.count(),
)
def test_print_comment_doc(comment: str, expected: str) -> None:
    doc = tvmt.ast.Comment(comment)
    assert doc.to_python().strip() == expected.strip()


@pytest.mark.parametrize(
    "comment, expected",
    [
        (
            "",
            '""""""',
        ),
        (
            "test comment 1",
            '"""test comment 1"""',
        ),
        (
            "test comment 1\ntest comment 2",
            '"""test comment 1\ntest comment 2"""',
        ),
    ],
    ids=itertools.count(),
)
def test_print_doc_string_doc(comment: str, expected: str) -> None:
    doc = tvmt.ast.DocString(comment)
    assert doc.to_python().strip() == expected.strip()


@pytest.mark.parametrize(
    "doc, comment, expected",
    [
        (
            tvmt.ast.Assign(tvmt.ast.Id("x"), tvmt.ast.Id("y"), tvmt.ast.Id("int")),
            "comment",
            """
x: int = y  # comment
""",
        ),
        (
            tvmt.ast.If(
                tvmt.ast.Id("x"),
                [tvmt.ast.ExprStmt(tvmt.ast.Id("y"))],
                [tvmt.ast.ExprStmt(tvmt.ast.Id("z"))],
            ),
            "comment",
            """
# comment
if x:
    y
else:
    z
""",
        ),
        (
            tvmt.ast.If(
                tvmt.ast.Id("x"),
                [tvmt.ast.ExprStmt(tvmt.ast.Id("y"))],
                [tvmt.ast.ExprStmt(tvmt.ast.Id("z"))],
            ),
            "comment line 1\ncomment line 2",
            """
# comment line 1
# comment line 2
if x:
    y
else:
    z
""",
        ),
        (
            tvmt.ast.While(
                tvmt.ast.Literal(True),
                [
                    tvmt.ast.Assign(tvmt.ast.Id("x"), tvmt.ast.Id("y")),
                ],
            ),
            "comment",
            """
# comment
while True:
    x = y
""",
        ),
        (
            tvmt.ast.For(tvmt.ast.Id("x"), tvmt.ast.Id("y"), []),
            "comment",
            """
# comment
for x in y:
    pass
""",
        ),
        (
            tvmt.ast.With(tvmt.ast.Id("x"), tvmt.ast.Id("y"), []),
            "comment",
            """
# comment
with y as x:
    pass
""",
        ),
        (
            tvmt.ast.ExprStmt(tvmt.ast.Id("x")),
            "comment",
            """
x  # comment
            """,
        ),
        (
            tvmt.ast.Assert(tvmt.ast.Literal(True)),
            "comment",
            """
assert True  # comment
            """,
        ),
        (
            tvmt.ast.Return(tvmt.ast.Literal(1)),
            "comment",
            """
return 1  # comment
            """,
        ),
        (
            get_func_doc_for_class("f"),
            "comment",
            '''
@wrap
def f(x: int, y: int = 1) -> None:
    """
    comment
    """
    y = x + 1
    y = y - 1
''',
        ),
        (
            get_func_doc_for_class("f"),
            "comment line 1\n\ncomment line 3",
            '''
@wrap
def f(x: int, y: int = 1) -> None:
    """
    comment line 1

    comment line 3
    """
    y = x + 1
    y = y - 1
''',
        ),
        (
            tvmt.ast.Class(tvmt.ast.Id("TestClass"), [], [tvmt.ast.Id("wrap")], []),
            "comment",
            '''
@wrap
class TestClass:
    """
    comment
    """
    pass
''',
        ),
        (
            tvmt.ast.Class(tvmt.ast.Id("TestClass"), [], [tvmt.ast.Id("wrap")], []),
            "comment line 1\n\ncomment line 3",
            '''
@wrap
class TestClass:
    """
    comment line 1

    comment line 3
    """
    pass
''',
        ),
    ],
    ids=itertools.count(),
)
def test_print_doc_comment(
    doc: tvmt.ast.Stmt,
    comment: str,
    expected: str,
) -> None:
    doc.comment = comment
    assert doc.to_python(tvmt.PrinterConfig(indent_spaces=4)) == expected.strip()


@pytest.mark.parametrize(
    "doc",
    [
        tvmt.ast.Assign(tvmt.ast.Id("x"), tvmt.ast.Id("y"), tvmt.ast.Id("int")),
        tvmt.ast.ExprStmt(tvmt.ast.Id("x")),
        tvmt.ast.Assert(tvmt.ast.Id("x")),
        tvmt.ast.Return(tvmt.ast.Id("x")),
    ],
)
def test_print_invalid_multiline_doc_comment(doc: tvmt.ast.Stmt) -> None:
    doc.comment = "1\n2"
    with pytest.raises(ValueError) as e:
        doc.to_python()
    assert "cannot have newline" in str(e.value)


def generate_expr_precedence_test_cases() -> list[ParameterSet]:
    x = tvmt.ast.Id("x")
    y = tvmt.ast.Id("y")
    z = tvmt.ast.Id("z")

    def negative(a: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.USub, [a])

    def invert(a: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Invert, [a])

    def not_(a: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Not, [a])

    def add(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Add, [a, b])

    def sub(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Sub, [a, b])

    def mult(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Mult, [a, b])

    def div(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Div, [a, b])

    def mod(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Mod, [a, b])

    def pow(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Pow, [a, b])

    def lshift(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.LShift, [a, b])

    def bit_and(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.BitAnd, [a, b])

    def bit_or(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.BitOr, [a, b])

    def bit_xor(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.BitXor, [a, b])

    def lt(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Lt, [a, b])

    def eq(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Eq, [a, b])

    def not_eq(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.NotEq, [a, b])

    def and_(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.And, [a, b])

    def or_(a: tvmt.ast.Expr, b: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.Or, [a, b])

    def if_then_else(a: tvmt.ast.Expr, b: tvmt.ast.Expr, c: tvmt.ast.Expr) -> tvmt.ast.Expr:
        return tvmt.ast.Operation(tvmt.ast.OperationKind.IfThenElse, [a, b, c])

    test_cases = {
        "attr-call-index": [
            (
                add(x, y).attr("test"),
                "(x + y).test",
            ),
            (
                add(x, y.attr("test")),
                "x + y.test",
            ),
            (
                x[z].call(y),
                "x[z](y)",
            ),
            (
                x.call(y)[z],
                "x(y)[z]",
            ),
            (
                x.call(y).call(z),
                "x(y)(z)",
            ),
            (
                x.call(y).attr("test"),
                "x(y).test",
            ),
            (
                x.attr("test").call(y),
                "x.test(y)",
            ),
            (
                x.attr("test").attr("test2"),
                "x.test.test2",
            ),
            (
                tvmt.ast.Lambda([x], x).call(y),
                "(lambda x: x)(y)",
            ),
            (
                add(x, y)[z][add(z, z)].attr("name"),
                "(x + y)[z][z + z].name",
            ),
        ],
        "power": [
            (
                pow(pow(x, y), z),
                "(x ** y) ** z",
            ),
            (
                pow(x, pow(y, z)),
                "x ** y ** z",
            ),
            (
                pow(negative(x), negative(y)),
                "(-x) ** -y",
            ),
            (
                pow(add(x, y), add(y, z)),
                "(x + y) ** (y + z)",
            ),
        ],
        "unary": [
            (
                invert(negative(y)),
                "~-y",
            ),
            (
                negative(y).attr("test"),
                "(-y).test",
            ),
            (
                negative(y.attr("test")),
                "-y.test",
            ),
            (
                mult(negative(x), negative(y)),
                "-x * -y",
            ),
            (
                negative(add(invert(x), negative(y))),
                "-(~x + -y)",
            ),
        ],
        "add-mult": [
            (
                mult(x, mult(y, z)),
                "x * (y * z)",
            ),
            (
                mult(mult(x, y), z),
                "x * y * z",
            ),
            (
                mult(x, add(y, z)),
                "x * (y + z)",
            ),
            (
                mult(add(y, z), x),
                "(y + z) * x",
            ),
            (
                add(x, mod(y, z)),
                "x + y % z",
            ),
            (
                add(mult(y, z), x),
                "y * z + x",
            ),
            (
                add(add(x, y), add(y, z)),
                "x + y + (y + z)",
            ),
            (
                div(add(x, y), add(y, z)),
                "(x + y) / (y + z)",
            ),
        ],
        "shift": [
            (
                div(x, lshift(y, z)),
                "x / (y << z)",
            ),
            (
                mult(lshift(y, z), x),
                "(y << z) * x",
            ),
            (
                lshift(x, mult(y, z)),
                "x << y * z",
            ),
            (
                lshift(mult(x, y), z),
                "x * y << z",
            ),
            (
                lshift(mult(x, y), z),
                "x * y << z",
            ),
            (
                lshift(lshift(x, y), z),
                "x << y << z",
            ),
            (
                lshift(x, lshift(y, z)),
                "x << (y << z)",
            ),
        ],
        "bitwise": [
            (
                add(bit_or(x, y), bit_or(y, z)),
                "(x | y) + (y | z)",
            ),
            (
                bit_and(bit_or(x, y), bit_or(y, z)),
                "(x | y) & (y | z)",
            ),
            (
                bit_or(bit_and(x, y), bit_and(y, z)),
                "x & y | y & z",
            ),
            (
                bit_and(bit_xor(x, bit_or(y, z)), z),
                "(x ^ (y | z)) & z",
            ),
        ],
        "comparison": [
            (
                not_eq(add(x, y), z),
                "x + y != z",
            ),
            (
                eq(pow(x, y), z),
                "x ** y == z",
            ),
            (
                lt(x, div(y, z)),
                "x < y / z",
            ),
            (
                lt(x, if_then_else(y, y, y)),
                "x < (y if y else y)",
            ),
        ],
        "boolean": [
            (
                not_(and_(x, y)),
                "not (x and y)",
            ),
            (
                and_(not_(x), y),
                "not x and y",
            ),
            (
                and_(or_(x, y), z),
                "(x or y) and z",
            ),
            (
                or_(x, or_(y, z)),
                "x or (y or z)",
            ),
            (
                or_(or_(x, y), z),
                "x or y or z",
            ),
            (
                or_(and_(x, y), z),
                # Maybe we should consider adding parentheses here
                # for readability, even though it's not necessary.
                "x and y or z",
            ),
            (
                and_(or_(not_(x), y), z),
                "(not x or y) and z",
            ),
            (
                and_(lt(x, y), lt(y, z)),
                "x < y and y < z",
            ),
            (
                or_(not_(eq(x, y)), lt(y, z)),
                # Same as the previous one, the code here is not
                # readable without parentheses.
                "not x == y or y < z",
            ),
            (
                and_(if_then_else(x, y, z), x),
                "(y if x else z) and x",
            ),
            (
                not_(if_then_else(x, y, z)),
                "not (y if x else z)",
            ),
        ],
        "if-then-else": [
            (
                if_then_else(x, if_then_else(y, y, y), z),
                "y if y else y if x else z",
            ),
            (
                if_then_else(if_then_else(x, x, x), y, z),
                "y if (x if x else x) else z",
            ),
            (
                if_then_else(x, y, if_then_else(z, z, z)),
                "y if x else (z if z else z)",
            ),
            (
                if_then_else(lt(x, x), add(y, y), mult(z, z)),
                "y + y if x < x else z * z",
            ),
            (
                if_then_else(
                    tvmt.ast.Lambda([x], x),
                    tvmt.ast.Lambda([y], y),
                    tvmt.ast.Lambda([z], z),
                ),
                "(lambda y: y) if (lambda x: x) else (lambda z: z)",
            ),
        ],
        "lambda": [
            (
                tvmt.ast.Lambda([x, y], add(z, z)),
                "lambda x, y: z + z",
            ),
            (
                add(tvmt.ast.Lambda([x, y], z), z),
                "(lambda x, y: z) + z",
            ),
            (
                tvmt.ast.Lambda([x, y], add(z, z)).call(x, y),
                "(lambda x, y: z + z)(x, y)",
            ),
            (
                tvmt.ast.Lambda([x], tvmt.ast.Lambda([y], z)),
                "lambda x: lambda y: z",
            ),
        ],
    }

    return [
        pytest.param(*args, id=f"{group_name}-{i}")
        for group_name, cases in test_cases.items()
        for i, args in enumerate(cases)
    ]


@pytest.mark.parametrize("doc, expected", generate_expr_precedence_test_cases())
def test_expr_precedence(doc: tvmt.ast.Expr, expected: str) -> None:
    assert doc.to_python() == expected
