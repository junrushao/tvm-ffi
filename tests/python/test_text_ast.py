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
"""AST roundtrip fidelity tests.

Each test converts Python source -> TVM-FFI AST -> Python source -> re-parse,
then checks that the re-parsed AST matches the original. Tests are derived from
roundtrip failures discovered against the TVM, GraphIR, and DKG codebases
(~4800 files total).

Bug categories and their root causes
=====================================

1. **Printer emitting wrong syntax** — the C++ printer produced output that
   Python couldn't parse back identically (docstring formatting, f-string
   escaping, control characters, triple-quote escaping, null bytes).

2. **Converter losing information** — the Python-to-TVM-FFI converter dropped
   structure that mattered for roundtrip (AugAssign, chained comparisons,
   UAdd, multi-target assign, positional-only args, type params, class
   keywords, multi-item with, lambda defaults/varargs).

3. **Converter not parenthesizing** — removing parens changed semantics or
   structure (nested ternary body, nested BoolOp, nested Compare,
   comprehension ternary iter, starred ternary).

4. **Literal edge cases** — special constant values that can't survive a
   naive Literal roundtrip (Ellipsis, large ints, float inf/nan, emoji/
   4-byte UTF-8, null bytes).
"""

from __future__ import annotations

import ast
import sys
import textwrap
import warnings

import pytest
from tvm_ffi.text.ast_translate import ast_translate


def _roundtrip_ast(source: str) -> ast.AST:
    """Parse *source*, roundtrip through TVM-FFI AST, re-parse, return the new AST."""
    source = textwrap.dedent(source)
    original = ast.parse(source)
    rendered = ast_translate(original).to_python()
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        return ast.parse(rendered)


def _roundtrip_src(source: str) -> str:
    """Parse *source*, roundtrip through TVM-FFI AST, return the rendered source."""
    source = textwrap.dedent(source)
    return ast_translate(source).to_python()


# ===================================================================
# 1. PRINTER BUGS — wrong output from the C++ text printer
# ===================================================================


class TestDocstringFormatting:
    """Bug: PrintDocString added \\n + indentation around content.

    ``\"\"\"hello\"\"\"`` became ``\"\"\"\\nhello\\n\"\"\"`` which re-parsed
    as ``'\\nhello\\n'`` instead of ``'hello'``.

    Fix: DocStringAST printer emits content verbatim between triple quotes.
    """

    def test_single_line_module(self):
        b = _roundtrip_ast('"""Module doc."""\nx = 1')
        assert b.body[0].value.value == "Module doc."

    def test_single_line_class(self):
        b = _roundtrip_ast('class C:\n    """Class doc."""\n    pass')
        assert b.body[0].body[0].value.value == "Class doc."

    def test_single_line_function(self):
        b = _roundtrip_ast('def f():\n    """Func doc."""\n    pass')
        assert b.body[0].body[0].value.value == "Func doc."

    def test_multiline_preserved(self):
        src = textwrap.dedent("""\
            def f():
                \"\"\"Line one.

                Line two.
                \"\"\"
                pass
        """)
        original_doc = ast.parse(src).body[0].body[0].value.value
        b = _roundtrip_ast(src)
        assert b.body[0].body[0].value.value == original_doc


class TestDocstringBackslash:
    r"""Bug: ``\\frac`` in docstring became form-feed (``\f`` = 0x0C).

    The printer emitted the raw string content between ``\"\"\"``, so a
    literal backslash ``\\`` followed by ``f`` was interpreted as the
    ``\\f`` escape sequence by Python's parser.

    Fix: escape ``\\`` to ``\\\\`` in DocStringAST content.
    """

    def test_backslash_frac(self):
        src = 'def f():\n    """Has \\\\frac{1}{2}."""\n    pass'
        original_doc = ast.parse(src).body[0].body[0].value.value
        b = _roundtrip_ast(src)
        assert b.body[0].body[0].value.value == original_doc


class TestDocstringTripleQuote:
    """Bug: docstring containing ``\\\"\\\"\\\"`` broke triple-quoting.

    A docstring with an embedded code example like ``asm=\\\"\\\"\\\"``
    caused premature termination of the enclosing triple-quoted string.

    Fix: escape the third consecutive ``\"`` as ``\\\\\"`` to break
    the triple-quote sequence.
    """

    def test_embedded_triple_quote(self):
        src = 'def f():\n    """example: x=\\\"\\\"\\\"hello\\\"\\\"\\\"."""\n    pass'
        original_doc = ast.parse(src).body[0].body[0].value.value
        b = _roundtrip_ast(src)
        assert b.body[0].body[0].value.value == original_doc


class TestEmptyDocstring:
    """Bug: empty docstring ``\\\"\\\"\\\"\\\"\\\"\\\"`` was silently dropped.

    The printer skipped empty strings, changing the body length
    (e.g. dropping a docstring before a ``match`` statement).

    Fix: emit ``\\\"\\\"\\\"\\\"\\\"\\\"`` even for empty content.
    """

    def test_empty_docstring_preserved(self):
        src = 'def f():\n    """"""\n    pass'
        b = _roundtrip_ast(src)
        assert len(b.body[0].body) == 2  # docstring + pass


class TestFStringEscaping:
    """Bug: literal ``{``, ``}``, ``\\r``, ``\\t``, ``\\x00`` in f-string
    text parts were not escaped.

    - ``{`` became an expression delimiter instead of literal text.
    - ``\\r`` (carriage return) caused unterminated string literal.
    - ``\\x00`` (null byte) caused "cannot contain null bytes" error.

    Fix: escape ``{``/``}`` to ``{{``/``}}``, and control chars to
    ``\\xNN`` in the FStr printer.
    """

    def test_literal_braces(self):
        rendered = _roundtrip_src('x = f"a{{b}}c"')
        ast.parse(rendered)

    def test_carriage_return(self):
        # \r in f-string text must not produce a raw CR in the output
        src = 'x = f"\\ra"'
        rendered = _roundtrip_src(src)
        ast.parse(rendered)

    def test_tab(self):
        # \t in f-string text must be escaped
        src = 'x = f"\\ta"'
        rendered = _roundtrip_src(src)
        ast.parse(rendered)

    def test_null_byte(self):
        src = 'x = f"\\x00"'
        rendered = _roundtrip_src(src)
        ast.parse(rendered)


class TestStringNullByte:
    """Bug: ``PrintEscapeString`` emitted raw null bytes for ``\\x00``.

    ASCII control characters (< 0x20) fell through to the plain ``char``
    output branch, producing unparseable output.

    Fix: escape control chars as ``\\xNN`` in ``PrintEscapeString``.
    """

    def test_null_in_literal(self):
        rendered = _roundtrip_src('x = "\\x00"')
        ast.parse(rendered)


class TestStringEmoji:
    """Bug: 4-byte UTF-8 characters (emoji) were escaped byte-by-byte.

    ``PrintEscapeString`` only handled 1/2/3-byte UTF-8 sequences.
    4-byte emoji like U+1F7E5 fell through to ``\\xNN`` per-byte escapes,
    producing ``\\xf0\\x9f\\x9f\\xa5`` which re-parsed as 4 Latin-1 chars.

    Fix: added 4-byte UTF-8 handler emitting ``\\UNNNNNNNN``.
    """

    def test_emoji_roundtrip(self):
        b = _roundtrip_ast('x = "\\U0001f7e5"')
        assert b.body[0].value.value == "\U0001f7e5"


# ===================================================================
# 2. CONVERTER BUGS — information lost during Python AST conversion
# ===================================================================


class TestAugAssign:
    """Bug: ``x += 1`` became ``x = x + 1`` (lost AugAssign type).

    The converter desugared augmented assignment into a plain Assign with
    an Operation RHS, which re-parsed as ``ast.Assign`` not ``ast.AugAssign``.

    Fix: added ``aug_op`` field to ``AssignAST`` (``OperationASTObj::Kind``).
    """

    def test_roundtrip(self):
        b = _roundtrip_ast("x += 1")
        assert isinstance(b.body[0], ast.AugAssign)

    @pytest.mark.parametrize(
        "op",
        ["+=", "-=", "*=", "/=", "//=", "%=", "**=", "<<=", ">>=", "&=", "|=", "^=", "@="],
    )
    def test_all_ops(self, op):
        b = _roundtrip_ast(f"x {op} y")
        assert isinstance(b.body[0], ast.AugAssign)


class TestChainedComparison:
    """Bug: ``a < b < c`` became ``a < b and b < c`` (Compare -> BoolOp).

    The converter decomposed chained comparisons into pairwise binary
    ops joined with ``and``, which re-parsed as ``BoolOp`` not ``Compare``.

    Fix: added ``kChainedCompare`` operation kind that interleaves values
    and op-kind literals: ``[a, Literal(Lt), b, Literal(Lt), c]``.
    """

    def test_preserves_type(self):
        b = _roundtrip_ast("x = a < b < c")
        assert isinstance(b.body[0].value, ast.Compare)

    def test_triple(self):
        b = _roundtrip_ast("x = a < b <= c < d")
        assert len(b.body[0].value.ops) == 3

    def test_rendered(self):
        assert "a < b < c" in _roundtrip_src("x = a < b < c")


class TestUAdd:
    """Bug: ``+x`` was stripped to ``x`` (UAdd discarded).

    The converter had a special case that dropped ``ast.UAdd``, treating
    it as a no-op. But ``+x`` and ``x`` produce different ASTs.

    Fix: added ``kUAdd`` to the ``OperationASTObj::Kind`` enum.
    """

    def test_preserved(self):
        b = _roundtrip_ast("x = +y")
        assert isinstance(b.body[0].value, ast.UnaryOp)


class TestMultiTargetAssign:
    """Bug: ``a = b = 1`` split into two statements, changing body length.

    The converter emitted separate ``Assign`` nodes per target, which
    re-parsed as two statements instead of one with two targets.

    Fix: encode multi-target as ``Assign(lhs=Parens(Tuple([a, b])), rhs=c)``.
    The printer detects this pattern and joins targets with `` = ``.
    """

    def test_rendered(self):
        assert "a = b = 1" in _roundtrip_src("a = b = 1")

    def test_ast_structure(self):
        b = _roundtrip_ast("a = b = 1")
        assert len(b.body) == 1
        assert len(b.body[0].targets) == 2


class TestListUnpackTarget:
    """Bug: ``[y] = expr`` became ``y = expr`` (List target lost).

    Multi-target assign used ``List`` LHS, which collided with Python's
    list-unpacking targets like ``[y] = expr``.

    Fix: use ``Parens(Tuple(...))`` for multi-target, and ``_convert_target``
    to preserve ``ast.List`` vs ``ast.Tuple`` distinction.
    """

    def test_list_target_preserved(self):
        b = _roundtrip_ast("[y] = items")
        assert isinstance(b.body[0].targets[0], ast.List)


class TestSingleElementTupleUnpack:
    """Bug: ``a, = expr`` became ``a = expr`` (trailing comma lost).

    The Assign printer used ``PrintJoinedDocs`` for Tuple LHS, which
    omitted the trailing comma for single-element tuples.

    Fix: add trailing comma when Tuple LHS has exactly 1 element.
    """

    def test_trailing_comma(self):
        b = _roundtrip_ast("a, = expr")
        assert isinstance(b.body[0].targets[0], ast.Tuple)
        assert len(b.body[0].targets[0].elts) == 1


class TestPositionalOnlyArgs:
    """Bug: ``def f(a, b, /):`` became ``def f(a, b):`` (``/`` lost).

    The converter merged ``posonlyargs`` into ``args`` without inserting
    the ``/`` separator.

    Fix: insert ``Assign(lhs=Id(\"/\"))`` after the last positional-only arg.
    """

    def test_posonly_separator(self):
        b = _roundtrip_ast("def f(a, b, /):\n    pass")
        assert len(b.body[0].args.posonlyargs) == 2
        assert len(b.body[0].args.args) == 0


class TestLambdaVarargs:
    """Bug: ``lambda *x: x`` became ``lambda: x`` (vararg lost).

    The lambda converter only extracted ``args.args``, ignoring
    ``vararg``, ``kwonlyargs``, and ``kwarg``.

    Fix: changed ``LambdaAST`` args from ``List<IdAST>`` to
    ``List<ExprAST>`` and used ``_convert_arguments`` for lambdas.
    """

    def test_varargs(self):
        b = _roundtrip_ast("f(lambda *x: x)")
        assert b.body[0].value.args[0].args.vararg is not None

    def test_kwargs(self):
        b = _roundtrip_ast("f(lambda **kw: kw)")
        assert b.body[0].value.args[0].args.kwarg is not None


class TestLambdaDefaults:
    """Bug: ``lambda x=1: x`` became ``lambda x: x`` (default lost).

    The lambda converter only used ``a.lhs`` from ``_convert_arguments``,
    discarding ``a.rhs`` (the default value).

    Fix: render args with defaults as ``Id(\"x=1\")`` text, since
    ``LambdaAST`` args are ``List<ExprAST>`` (can't hold ``Assign`` stmts).
    """

    def test_default_preserved(self):
        b = _roundtrip_ast("f(lambda x=1: x)")
        assert len(b.body[0].value.args[0].args.defaults) == 1


class TestClassKeywords:
    """Bug: ``class Foo(metaclass=X):`` became ``class Foo:`` (keywords lost).

    The converter only passed ``bases``, ignoring ``keywords`` like
    ``metaclass=``.

    Fix: added ``kwargs_keys``/``kwargs_values`` fields to ``ClassAST``.
    """

    def test_metaclass(self):
        b = _roundtrip_ast("class Foo(metaclass=Bar):\n    pass")
        assert len(b.body[0].keywords) == 1
        assert b.body[0].keywords[0].arg == "metaclass"


class TestMultiItemWith:
    """Bug: ``with a(), b():`` became nested ``with a(): with b():``.

    The converter created nested ``With`` nodes, which re-parsed as
    separate ``With`` statements with 1 item each.

    Fix: encode multiple items as ``Tuple`` of context exprs / targets
    in a single ``With`` node.
    """

    def test_multi_item(self):
        b = _roundtrip_ast("with a() as x, b() as y:\n    pass")
        assert len(b.body[0].items) == 2


@pytest.mark.skipif(sys.version_info < (3, 12), reason="type params require 3.12+")
class TestTypeParams:
    """Bug: ``class Foo[T]:`` became ``class Foo:`` (type params lost).

    The converter didn't handle PEP 695 ``type_params`` on classes/functions.

    Fix: encode type params in the name string: ``Id(\"Foo[T]\")``.
    """

    def test_class_type_param(self):
        b = _roundtrip_ast("class Foo[T]:\n    pass")
        assert len(b.body[0].type_params) == 1

    def test_type_alias(self):
        b = _roundtrip_ast("type X = int")
        assert isinstance(b.body[0], ast.TypeAlias)


class TestSingleElementTupleSubscript:
    """Bug: ``x[1,]`` became ``x[1]`` (single-element tuple slice lost).

    The converter unwrapped all ``ast.Tuple`` slices into individual
    indices, even single-element tuples.

    Fix: only unwrap multi-element tuples; keep single-element tuples
    as ``Index(obj, [Tuple([elem])])``.
    """

    def test_tuple_subscript(self):
        b = _roundtrip_ast("x[1,]")
        assert isinstance(b.body[0].value.slice, ast.Tuple)


# ===================================================================
# 3. PARENTHESIZATION BUGS — parens dropped, changing semantics
# ===================================================================


class TestNestedTernary:
    """Bug: ``(B if A else C) if X else Z`` lost parens around body.

    Without parens, ``B if A else C if X else Z`` parses right-to-left
    as ``B if A else (C if X else Z)`` — a different structure.

    Fix: converter wraps ternary body in ``Parens`` when it's itself
    a ternary. The printer's behavior for direct API is unchanged.
    """

    def test_body_ternary(self):
        b = _roundtrip_ast("x = (4 if n > 4096 else 2) if isinstance(n, int) else 1")
        val = b.body[0].value
        assert isinstance(val.body, ast.IfExp)  # inner ternary is the body


class TestNestedBoolOp:
    """Bug: ``(a and b) and c`` became flat ``a and b and c``.

    Python flattens ``BoolOp``: ``a and b and c`` parses as
    ``And([a, b, c])`` (3 values), not ``And([And([a, b]), c])`` (2 values).

    Fix: converter wraps nested same-operator BoolOps in ``Parens``.
    """

    def test_nested_and(self):
        b = _roundtrip_ast("x = (a and b) and c")
        val = b.body[0].value
        assert len(val.values) == 2  # not flattened to 3


class TestNestedCompare:
    """Bug: ``(a == b) == c`` became chained ``a == b == c``.

    Without parens, ``a == b == c`` is a chained Compare with 2 ops,
    not a simple Compare whose left is itself a Compare.

    Fix: converter wraps Compare left in ``Parens`` when it's a Compare.
    """

    def test_nested_eq(self):
        b = _roundtrip_ast("x = (a == b) == c")
        val = b.body[0].value
        assert len(val.comparators) == 1  # not chained to 2


class TestComprehensionTernaryIter:
    """Bug: ``[x for x in ([4,8] if c else [4])]`` lost iter parens.

    Without parens, ``for x in [4,8] if c else [4]`` is ambiguous —
    ``if`` looks like a comprehension filter, causing a syntax error.

    Fix: converter wraps ternary iters in ``Parens``.
    """

    def test_ternary_iter(self):
        rendered = _roundtrip_src("y = [x for x in ([4, 8] if c else [4])]")
        ast.parse(rendered)  # must not raise SyntaxError


class TestStarredTernary:
    """Bug: ``*([x] if c else [])`` lost parens around the ternary.

    Without parens, ``*[x] if c else []`` is ambiguous syntax.

    Fix: converter wraps ternary value of ``Starred`` in ``Parens``.
    """

    def test_starred_ternary(self):
        rendered = _roundtrip_src("y = [*([x] if c else [])]")
        ast.parse(rendered)


# ===================================================================
# 4. LITERAL EDGE CASES — special values that need special rendering
# ===================================================================


class TestEllipsis:
    """Bug: ``Constant(Ellipsis)`` rendered as ``Ellipsis`` (a Name).

    ``repr(Ellipsis)`` is ``'Ellipsis'``, which re-parses as
    ``Name('Ellipsis')`` instead of ``Constant(Ellipsis)``.

    Fix: render as ``Id(\"...\")`` which parses as ``Constant(Ellipsis)``.
    """

    def test_ellipsis(self):
        b = _roundtrip_ast("x: tuple[int, ...]")
        slc = b.body[0].annotation.slice
        assert isinstance(slc.elts[1], ast.Constant)
        assert slc.elts[1].value is ...


class TestLargeInt:
    """Bug: integers > 2^63 - 1 caused ``OverflowError``.

    The FFI stores integers as ``int64_t``, so values like ``2**64 - 1``
    (UINT64_MAX) overflow.

    Fix: fall back to ``Id(repr(value))`` for out-of-range integers.
    """

    def test_uint64_max(self):
        b = _roundtrip_ast("x = 18446744073709551615")
        assert b.body[0].value.value == 18446744073709551615


class TestFloatInf:
    """Bug: ``float('inf')`` rendered as ``inf`` which parses as a Name.

    Fix: render as ``1e999`` which Python parses as ``Constant(value=inf)``.
    """

    def test_inf(self):
        b = _roundtrip_ast("x = 1e999")
        assert b.body[0].value.value == float("inf")

    def test_neg_inf(self):
        b = _roundtrip_ast("x = -1e999")
        val = b.body[0].value
        assert isinstance(val, ast.UnaryOp)


# ===================================================================
# OTHER — miscellaneous constructs that should roundtrip correctly
# ===================================================================


def test_dict_unpacking():
    rendered = _roundtrip_src("z = {**d}")
    assert "**d:" not in rendered
    ast.parse(rendered)


def test_bare_star_separator():
    b = _roundtrip_ast("def f(a, *, key=1):\n    pass")
    assert b.body[0].args.vararg is None
    assert len(b.body[0].args.kwonlyargs) == 1


def test_tuple_default_in_args():
    rendered = _roundtrip_src("def f(x=(0, 0)):\n    pass")
    ast.parse(rendered)
    assert "(0, 0)" in rendered


def test_async_def():
    b = _roundtrip_ast("async def f():\n    pass")
    assert isinstance(b.body[0], ast.AsyncFunctionDef)


def test_class_bases():
    b = _roundtrip_ast("class C(A, B):\n    pass")
    assert [base.id for base in b.body[0].bases] == ["A", "B"]


def test_while_else():
    b = _roundtrip_ast("while c:\n    a = 1\nelse:\n    b = 2")
    assert len(b.body[0].orelse) > 0


def test_for_else():
    b = _roundtrip_ast("for x in items:\n    a = 1\nelse:\n    b = 2")
    assert len(b.body[0].orelse) > 0


def test_try_except():
    b = _roundtrip_ast("try:\n    a = 1\nexcept ValueError:\n    b = 2")
    assert isinstance(b.body[0], ast.Try)


@pytest.mark.skipif(sys.version_info < (3, 10), reason="match requires 3.10+")
def test_match():
    rendered = _roundtrip_src("match x:\n    case 1:\n        a = 1\n    case _:\n        b = 2")
    assert "match x:" in rendered
