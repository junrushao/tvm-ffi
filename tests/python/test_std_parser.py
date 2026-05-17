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

import sys
from typing import Any, ClassVar

import pytest
import tvm_ffi
from tvm_ffi import std
from tvm_ffi._pyast_parser import parse, register_dialect

################################################################################
# Helpers
################################################################################


I32 = std.PrimTy("int32")
I64 = std.PrimTy("int64")
F32 = std.PrimTy("float32")
F64 = std.PrimTy("float64")
BOOL = std.PrimTy("bool")
ANY = std.AnyTy()


def _equal(actual: Any, expected: Any) -> bool:
    """Structural equality wrapper for parser results."""
    return tvm_ffi.structural_equal(actual, expected)


def _assert_parse_equal(text: str, expected: Any, **kwargs: Any) -> None:
    parsed = parse(text, **kwargs)
    assert _equal(parsed, expected), (
        f"parse({text!r}) != expected\n  parsed:   {parsed!r}\n  expected: {expected!r}"
    )


def _assert_roundtrip(node: Any, **kwargs: Any) -> None:
    text = node.text()
    parsed = parse(text, **kwargs)
    assert _equal(parsed, node), (
        f"round-trip failed for {node!r}\n  text:   {text!r}\n  parsed: {parsed!r}"
    )


################################################################################
# Types
################################################################################


class TestParseAnyTy:
    def test_any_via_attribute(self) -> None:
        _assert_parse_equal("std.Any", std.AnyTy())

    def test_any_round_trip(self) -> None:
        _assert_roundtrip(std.AnyTy())

    def test_any_indexing_is_rejected(self) -> None:
        with pytest.raises(TypeError, match=r"use std\.f32"):
            parse("std.Any[4, 8]")


class TestParsePrimTy:
    @pytest.mark.parametrize(
        "src,dtype",
        [
            ("std.bool", "bool"),
            ("std.i8", "int8"),
            ("std.i16", "int16"),
            ("std.i32", "int32"),
            ("std.i64", "int64"),
            ("std.u8", "uint8"),
            ("std.u16", "uint16"),
            ("std.u32", "uint32"),
            ("std.u64", "uint64"),
            ("std.f16", "float16"),
            ("std.f32", "float32"),
            ("std.f64", "float64"),
            ("std.bf16", "bfloat16"),
            ("std.f8_e3m4", "float8_e3m4"),
            ("std.f8_e4m3", "float8_e4m3"),
            ("std.f8_e4m3b11fnuz", "float8_e4m3b11fnuz"),
            ("std.f8_e4m3fn", "float8_e4m3fn"),
            ("std.f8_e4m3fnuz", "float8_e4m3fnuz"),
            ("std.f8_e5m2", "float8_e5m2"),
            ("std.f8_e5m2fnuz", "float8_e5m2fnuz"),
            ("std.f8_e8m0fnu", "float8_e8m0fnu"),
            ("std.f6_e2m3fn", "float6_e2m3fn"),
            ("std.f6_e3m2fn", "float6_e3m2fn"),
            ("std.f4_e2m1fn", "float4_e2m1fn"),
            ("std.f4_e2m1fnx2", "float4_e2m1fnx2"),
        ],
    )
    def test_dtype_aliases(self, src: str, dtype: str) -> None:
        _assert_parse_equal(src, std.PrimTy(dtype))

    def test_explicit_factory(self) -> None:
        _assert_parse_equal('std.Prim("int32")', std.PrimTy("int32"))
        _assert_parse_equal('std.Prim("i32")', std.PrimTy("int32"))

    def test_round_trip_every_dtype(self) -> None:
        for dtype in (
            "bool",
            "int8",
            "int16",
            "int32",
            "int64",
            "uint8",
            "uint32",
            "float16",
            "float32",
            "float64",
            "bfloat16",
            "float8_e3m4",
            "float8_e4m3",
            "float8_e4m3b11fnuz",
            "float8_e4m3fn",
            "float8_e4m3fnuz",
            "float8_e5m2",
            "float8_e5m2fnuz",
            "float8_e8m0fnu",
            "float6_e2m3fn",
            "float6_e3m2fn",
            "float4_e2m1fn",
            "float4_e2m1fnx2",
        ):
            _assert_roundtrip(std.PrimTy(dtype))


class TestParseTupleTy:
    def test_pair(self) -> None:
        _assert_parse_equal(
            "std.Tuple[std.i32, std.f32]",
            std.TupleTy([I32, F32]),
        )

    def test_single(self) -> None:
        _assert_parse_equal("std.Tuple[std.i32]", std.TupleTy([I32]))

    def test_call_form(self) -> None:
        _assert_parse_equal(
            "std.Tuple(std.i32, std.f32)",
            std.TupleTy([I32, F32]),
        )

    def test_string_dtype(self) -> None:
        _assert_parse_equal(
            'std.Tuple["int32", "f32"]',
            std.TupleTy([I32, F32]),
        )

    def test_nested(self) -> None:
        _assert_parse_equal(
            "std.Tuple[std.Tuple[std.i32, std.f32], std.bool]",
            std.TupleTy([std.TupleTy([I32, F32]), std.PrimTy("bool")]),
        )

    def test_round_trip(self) -> None:
        _assert_roundtrip(std.TupleTy([I32, F32]))
        _assert_roundtrip(std.TupleTy([std.TupleTy([I32]), F32]))


class TestParseTensorTy:
    def test_2d(self) -> None:
        _assert_parse_equal("std.f32[4, 8]", std.TensorTy([4, 8], "float32"))

    def test_1d(self) -> None:
        _assert_parse_equal("std.i32[16]", std.TensorTy([16], "int32"))

    def test_singleton_shape_with_trailing_comma(self) -> None:
        _assert_parse_equal("std.f32[4,]", std.TensorTy([4], "float32"))

    def test_n_dim(self) -> None:
        _assert_parse_equal("std.bf16[2, 3, 4, 5]", std.TensorTy([2, 3, 4, 5], "bfloat16"))

    def test_explicit_factory(self) -> None:
        _assert_parse_equal('std.Tensor((4, 8), "int32")', std.TensorTy([4, 8], "int32"))
        _assert_parse_equal('std.Tensor((4, 8), "float32")', std.TensorTy([4, 8], "float32"))

    def test_empty_brackets_rejected_by_python(self) -> None:
        with pytest.raises(SyntaxError):
            parse("std.f32[]")

    def test_round_trip(self) -> None:
        _assert_roundtrip(std.TensorTy([4, 8], "float32"))
        _assert_roundtrip(std.TensorTy([14, 21], "int32"))


################################################################################
# Literals / Immediates
################################################################################


class TestParseLiterals:
    """Python literals are materialized to the type chosen by their context."""

    def test_top_int_imm_default_i64(self) -> None:
        _assert_parse_equal("7", std.IntImm(I64, 7))

    def test_top_int_imm_negative(self) -> None:
        _assert_parse_equal("-3", std.IntImm(I64, -3))

    def test_top_float_imm_default_f32(self) -> None:
        _assert_parse_equal("1.5", std.FloatImm(F32, 1.5))

    def test_top_float_imm_negative(self) -> None:
        _assert_parse_equal("-1.5", std.FloatImm(F32, -1.5))

    def test_top_zero_int(self) -> None:
        _assert_parse_equal("0", std.IntImm(I64, 0))

    def test_top_zero_float(self) -> None:
        _assert_parse_equal("0.0", std.FloatImm(F32, 0.0))

    def test_in_context_int_uses_inferred_type(self) -> None:
        parsed = parse("1 + 2")
        assert isinstance(parsed, std.IntImm)
        assert _equal(parsed.ty, I64)
        assert parsed.value == 3

    def test_in_context_float_uses_inferred_type(self) -> None:
        parsed = parse("1.5 + 1.5")
        assert isinstance(parsed, std.FloatImm)
        assert _equal(parsed.ty, F32)
        assert parsed.value == 3.0

    def test_bool_true(self) -> None:
        _assert_parse_equal("True", std.BoolImm(std.PrimTy("bool"), True))

    def test_bool_false(self) -> None:
        _assert_parse_equal("False", std.BoolImm(std.PrimTy("bool"), False))

    def test_none_top_level(self) -> None:
        # `None` parses to the Python None which materialises as no top result.
        assert parse("None") is None

    def test_string_imm_via_factory(self) -> None:
        _assert_parse_equal(
            'std.StringImm(std.Any, "hello")',
            std.StringImm(ANY, "hello"),
        )

    def test_bool_imm_via_factory(self) -> None:
        _assert_parse_equal(
            "std.BoolImm(std.bool, True)",
            std.BoolImm(std.PrimTy("bool"), True),
        )

    def test_int_imm_round_trip(self) -> None:
        _assert_roundtrip(std.IntImm(I32, 7))
        _assert_roundtrip(std.IntImm(I32, -42))

    def test_float_imm_round_trip(self) -> None:
        _assert_roundtrip(std.FloatImm(F32, 1.5))
        _assert_roundtrip(std.FloatImm(F32, -2.25))

    def test_bool_imm_round_trip(self) -> None:
        _assert_roundtrip(std.BoolImm(std.PrimTy("bool"), True))
        _assert_roundtrip(std.BoolImm(std.PrimTy("bool"), False))


################################################################################
# Variables
################################################################################


class TestParseVariables:
    def test_extra_vars(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal("x", x, extra_vars={"x": x})

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(NameError):
            parse("foo")

    def test_undefined_attribute_raises(self) -> None:
        with pytest.raises(AttributeError):
            parse("std.no_such_dtype")

    def test_unicode_extra_var(self) -> None:
        value = std.Var(I64, "café")
        parsed = parse("café", extra_vars={"café": value})
        assert parsed.same_as(value)

    def test_extra_var_consistent_within_parse(self) -> None:
        value = std.Var(I64, "n")
        parsed = parse("n + n", extra_vars={"n": value})
        assert isinstance(parsed.a, std.Var)
        assert isinstance(parsed.b, std.Var)
        assert parsed.a.name == parsed.b.name == "n"
        assert parsed.a.same_as(value)
        assert parsed.b.same_as(value)

    def test_extra_var_collision_with_language(self) -> None:
        # The language module is installed first; extra_vars cannot shadow it.
        # The collision raises during `Parser.__init__` before the AST walk.
        with pytest.raises(ValueError, match="already defined"):
            parse("std", extra_vars={"std": 42})


################################################################################
# Binary, unary, and comparison operators
################################################################################


class TestParseArithmeticOps:
    def test_add(self) -> None:
        _assert_parse_equal("1 + 2", std.IntImm(I64, 3))

    def test_sub(self) -> None:
        _assert_parse_equal("5 - 3", std.IntImm(I64, 2))

    def test_mul(self) -> None:
        _assert_parse_equal("3 * 4", std.IntImm(I64, 12))

    def test_div(self) -> None:
        _assert_parse_equal("6 / 2", std.IntImm(I64, 3))

    def test_div_float_uses_cdiv(self) -> None:
        _assert_parse_equal(
            "std.f32(6) / std.f32(2)",
            std.FloatImm(F32, 3.0),
        )

    def test_floordiv(self) -> None:
        _assert_parse_equal("7 // 2", std.IntImm(I64, 3))

    def test_floordiv_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="__floordiv__ only supports integer types"):
            parse("std.f32(7) // std.f32(2)")

    def test_floormod(self) -> None:
        _assert_parse_equal("7 % 2", std.IntImm(I64, 1))

    def test_mod_int_uses_floormod(self) -> None:
        _assert_parse_equal(
            "std.i32(7) % std.i32(2)",
            std.IntImm(I32, 1),
        )

    def test_mod_float_uses_cmod(self) -> None:
        _assert_parse_equal(
            "std.f32(7) % std.f32(2)",
            std.FloatImm(F32, 1.0),
        )

    def test_pow(self) -> None:
        _assert_parse_equal("2 ** 3", std.IntImm(I64, 8))

    def test_lshift(self) -> None:
        _assert_parse_equal("1 << 3", std.IntImm(I64, 8))

    def test_rshift(self) -> None:
        _assert_parse_equal("16 >> 2", std.IntImm(I64, 4))

    def test_xor(self) -> None:
        _assert_parse_equal("1 ^ 2", std.IntImm(I64, 3))

    def test_bitwise_and(self) -> None:
        _assert_parse_equal("1 & 2", std.IntImm(I64, 0))

    def test_bitwise_or(self) -> None:
        _assert_parse_equal("1 | 2", std.IntImm(I64, 3))

    def test_min_call(self) -> None:
        _assert_parse_equal("min(1, 2)", std.IntImm(I64, 1))

    def test_max_call(self) -> None:
        _assert_parse_equal("max(1, 2)", std.IntImm(I64, 2))

    def test_min_resolves_qualified_or_unqualified(self) -> None:
        assert _equal(parse("min(1, 2)"), parse("std.min(1, 2)"))

    def test_min_max_require_exactly_two_args(self) -> None:
        with pytest.raises(TypeError, match=r"min\(\) missing .*rhs"):
            parse("min(1)")
        with pytest.raises(TypeError, match=r"min\(\) takes 2 positional arguments"):
            parse("min(1, 2, 3)")
        with pytest.raises(TypeError, match=r"max\(\) missing .*rhs"):
            parse("max(1)")

    def test_paren_grouping(self) -> None:
        a = std.Var(I64, "a")
        b = std.Var(I64, "b")
        c = std.Var(I64, "c")
        _assert_parse_equal(
            "(a + b) * c",
            std.Mul(std.Add(a, b, ty=I64), c, ty=I64),
            extra_vars={"a": a, "b": b, "c": c},
        )

    def test_left_associativity(self) -> None:
        # `a + b + c` is `(a + b) + c`.
        a = std.Var(I64, "a")
        b = std.Var(I64, "b")
        c = std.Var(I64, "c")
        _assert_parse_equal(
            "a + b + c",
            std.Add(std.Add(a, b, ty=I64), c, ty=I64),
            extra_vars={"a": a, "b": b, "c": c},
        )

    def test_anyty_dominates_other_side(self) -> None:
        a = std.Var(ANY, "a")
        b = std.Var(I32, "b")
        _assert_parse_equal(
            "a + b",
            std.Add(a, b, ty=ANY),
            extra_vars={"a": a, "b": b},
        )

    def test_mismatched_int_widths_promote(self) -> None:
        a = std.Var(I32, "a")
        b = std.Var(I64, "b")
        _assert_parse_equal(
            "a + b",
            std.Add(std.Cast(I64, a), b, ty=I64),
            extra_vars={"a": a, "b": b},
        )

    def test_bool_int_arith_is_type_mismatch(self) -> None:
        with pytest.raises(TypeError, match="type mismatch"):
            parse("True + 1")

    def test_int_plus_float_promotes_to_float(self) -> None:
        _assert_parse_equal("1 + 1.5", std.FloatImm(F32, 2.5))

    def test_operator_precedence(self) -> None:
        a = std.Var(I64, "a")
        b = std.Var(I64, "b")
        c = std.Var(I64, "c")
        parsed = parse("a + b * c", extra_vars={"a": a, "b": b, "c": c})
        assert isinstance(parsed, std.Add)
        assert isinstance(parsed.b, std.Mul)

    def test_min_call_structurally_nested(self) -> None:
        a = std.Var(I64, "a")
        b = std.Var(I64, "b")
        c = std.Var(I64, "c")
        _assert_parse_equal(
            "min(min(a, b), c)",
            std.Min(std.Min(a, b, ty=I64), c, ty=I64),
            extra_vars={"a": a, "b": b, "c": c},
        )


class TestParseUnaryOps:
    def test_logical_not(self) -> None:
        x = std.Var(BOOL, "x")
        _assert_parse_equal("not x", std.Not(x, ty=BOOL), extra_vars={"x": x})

    def test_bitwise_invert(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal("~x", std.BitwiseNot(x, ty=I32), extra_vars={"x": x})

    def test_abs_call(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal("abs(x)", std.Abs(x, ty=I32), extra_vars={"x": x})

    def test_unary_minus_literal_at_top(self) -> None:
        # Native fold: `-1` is folded to Python -1, then materialized at i64.
        _assert_parse_equal("-1", std.IntImm(I64, -1))

    def test_unary_plus_literal_at_top(self) -> None:
        _assert_parse_equal("+1", std.IntImm(I64, 1))

    def test_unary_minus_var(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal("-x", std.Sub(0, x, ty=I32), extra_vars={"x": x})

    def test_unary_plus_var(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal("+x", x, extra_vars={"x": x})


class TestParseComparisons:
    def test_eq(self) -> None:
        _assert_parse_equal("1 == 2", std.BoolImm(BOOL, False))

    def test_ne(self) -> None:
        _assert_parse_equal("1 != 2", std.BoolImm(BOOL, True))

    def test_lt(self) -> None:
        _assert_parse_equal("1 < 2", std.BoolImm(BOOL, True))

    def test_le(self) -> None:
        _assert_parse_equal("1 <= 2", std.BoolImm(BOOL, True))

    def test_gt(self) -> None:
        _assert_parse_equal("1 > 2", std.BoolImm(BOOL, False))

    def test_ge(self) -> None:
        _assert_parse_equal("1 >= 2", std.BoolImm(BOOL, False))

    def test_chained_compare(self) -> None:
        _assert_parse_equal(
            "1 < 2 < 3",
            std.BoolImm(BOOL, True),
        )

    def test_chained_three_way(self) -> None:
        _assert_parse_equal(
            "1 < 2 == 2",
            std.BoolImm(BOOL, True),
        )


class TestParseLogical:
    def test_logical_and(self) -> None:
        x = std.Var(BOOL, "x")
        y = std.Var(BOOL, "y")
        _assert_parse_equal("x and y", std.And(x, y, ty=BOOL), extra_vars={"x": x, "y": y})

    def test_logical_or(self) -> None:
        x = std.Var(BOOL, "x")
        y = std.Var(BOOL, "y")
        _assert_parse_equal("x or y", std.Or(x, y, ty=BOOL), extra_vars={"x": x, "y": y})

    def test_logical_and_short_circuit_chain(self) -> None:
        x = std.Var(BOOL, "x")
        y = std.Var(BOOL, "y")
        z = std.Var(BOOL, "z")
        _assert_parse_equal(
            "x and y and z",
            std.And(std.And(x, y, ty=BOOL), z, ty=BOOL),
            extra_vars={"x": x, "y": y, "z": z},
        )

    def test_logical_bool_literals(self) -> None:
        _assert_parse_equal("True and False", std.BoolImm(BOOL, False))
        _assert_parse_equal("True or False", std.BoolImm(BOOL, True))

    def test_logical_rejects_non_bool(self) -> None:
        with pytest.raises(TypeError, match=r"expected bool dtype for lhs, but got int64"):
            parse("1 and 2")
        with pytest.raises(TypeError, match=r"expected bool dtype for lhs, but got int64"):
            parse("1 or 2")


class TestParseIfExpr:
    def test_if_expr(self) -> None:
        cond = std.Var(BOOL, "cond")
        x = std.Var(I32, "x")
        y = std.Var(I32, "y")
        _assert_parse_equal(
            "x if cond else y",
            std.IfExpr(cond, x, y, ty=I32),
            extra_vars={"cond": cond, "x": x, "y": y},
        )


class TestParseNativeFallbackOps:
    """Operators not registered by std still fall back to `_NATIVE_GENERICS`."""

    def test_pow_right_associativity_builds_ir(self) -> None:
        a = std.Var(I64, "a")
        b = std.Var(I64, "b")
        c = std.Var(I64, "c")
        _assert_parse_equal(
            "a ** b ** c",
            std.Pow(a, std.Pow(b, c, ty=I64), ty=I64),
            extra_vars={"a": a, "b": b, "c": c},
        )

    def test_is_literal_folds(self) -> None:
        _assert_parse_equal("1 is 2", std.BoolImm(std.PrimTy("bool"), False))

    def test_in_literal_folds(self) -> None:
        _assert_parse_equal("1 in [1, 2]", std.BoolImm(std.PrimTy("bool"), True))

    def test_no_handler_raises_for_non_literal(self) -> None:
        a = std.Var(ANY, "a")
        b = std.Var(ANY, "b")
        with pytest.raises(KeyError):
            parse("a @ b", extra_vars={"a": a, "b": b})


################################################################################
# Cast
################################################################################


class TestParseCast:
    def test_dtype_call_cast(self) -> None:
        x = std.Var(I64, "x")
        _assert_parse_equal("std.i32(x)", std.Cast(I32, x), extra_vars={"x": x})

    def test_explicit_cast_node(self) -> None:
        x = std.Var(I64, "x")
        _assert_parse_equal("std.Cast(std.i32, x)", std.Cast(I32, x), extra_vars={"x": x})

    def test_dtype_call_literal(self) -> None:
        _assert_parse_equal("std.i64(5)", std.IntImm(I64, 5))
        _assert_parse_equal("std.f32(1)", std.FloatImm(F32, 1.0))
        _assert_parse_equal("std.bool(True)", std.BoolImm(std.PrimTy("bool"), True))

    def test_cast_rejects_type_factory_as_value(self) -> None:
        with pytest.raises(TypeError, match="expected expression, got TyFactory"):
            parse("std.f32(std.i32)")

    def test_cast_into_anyty(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal("std.Any(x)", std.Cast(ANY, x), extra_vars={"x": x})

    def test_nested_casts(self) -> None:
        x = std.Var(I64, "x")
        _assert_parse_equal(
            "std.f32(std.i32(x))",
            std.Cast(F32, std.Cast(I32, x)),
            extra_vars={"x": x},
        )

    def test_cast_chain_through_three_types(self) -> None:
        parsed = parse("std.f64(std.f32(std.i32(1)))")
        assert isinstance(parsed, std.FloatImm)
        assert _equal(parsed.ty, F64)
        assert parsed.value == 1.0

    def test_cast_in_binop_preserves_target_type(self) -> None:
        parsed = parse("std.i32(1) + std.i32(2)")
        assert isinstance(parsed, std.IntImm)
        assert _equal(parsed.ty, I32)
        assert parsed.value == 3

    def test_round_trip(self) -> None:
        _assert_roundtrip(std.Cast(I32, 1))
        _assert_roundtrip(std.Cast(F32, 1))


################################################################################
# Load / Store
################################################################################


class TestParseLoad:
    def test_load_one_index(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal("x[1]", std.Load(x, 1), extra_vars={"x": x})

    def test_load_two_indices(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal(
            "x[1, 2]",
            std.Load(x, 1, 2),
            extra_vars={"x": x},
        )

    def test_load_slice_index(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal(
            "x[1:2]",
            std.Load(x, std.Range(1, 2)),
            extra_vars={"x": x},
        )

    def test_load_mixed_indices(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal(
            "x[1:2, 3]",
            std.Load(x, std.Range(1, 2), 3),
            extra_vars={"x": x},
        )

    def test_load_negative_index(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal(
            "x[-1]",
            std.Load(x, std.Range(start=std.IntImm(I64, -1))),
            extra_vars={"x": x},
        )

    def test_load_explicit_node(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal(
            "std.Load(x, 1, ty=std.i32)",
            std.Load(x, 1, ty=I32),
            extra_vars={"x": x},
        )

    def test_load_explicit_range_arg(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal(
            "std.Load(x, std.Range(1, 2), ty=std.i32)",
            std.Load(x, std.Range(1, 2), ty=I32),
            extra_vars={"x": x},
        )

    def test_load_from_tensor_yields_dtype(self) -> None:
        ty = std.TensorTy([4, 8], "float32")
        a = std.Var(ty, "a")
        parsed = parse("a[1, 2]", extra_vars={"a": a})
        # A 2-rank tensor indexed twice yields a scalar PrimTy(float32).
        assert _equal(parsed.ty, F32)

    def test_load_from_anyty_yields_anyty(self) -> None:
        a = std.Var(ANY, "a")
        parsed = parse("a[1]", extra_vars={"a": a})
        assert _equal(parsed.ty, ANY)

    def test_load_from_tuple_uses_literal_field_type(self) -> None:
        a = std.Var(std.TupleTy([I32, F32]), "a")
        assert _equal(parse("a[0]", extra_vars={"a": a}).ty, I32)
        assert _equal(parse("a[1]", extra_vars={"a": a}).ty, F32)

    def test_nested_load(self) -> None:
        x = std.Var(I32, "x")
        parsed = parse("x[1][2]", extra_vars={"x": x})
        assert isinstance(parsed, std.Load)
        assert isinstance(parsed.lhs, std.Load)

    def test_literal_index_base_fails(self) -> None:
        with pytest.raises(TypeError, match="base must be an expression"):
            parse("1[2]")

    def test_full_slice(self) -> None:
        x = std.Var(I32, "x")
        parsed = parse("x[:]", extra_vars={"x": x})
        idx = next(iter(parsed.indices))
        assert isinstance(idx, std.Range)
        assert idx.start is None and idx.stop is None and idx.step is None

    def test_ellipsis_indexing_rejected(self) -> None:
        x = std.Var(I32, "x")
        with pytest.raises(TypeError, match="ellipsis indexing is not supported"):
            parse("x[...]", extra_vars={"x": x})

    def test_slice_with_var_bounds(self) -> None:
        x = std.Var(I32, "x")
        parsed = parse(
            "x[start:stop:step]",
            extra_vars={
                "x": x,
                "start": std.Var(I32, "start"),
                "stop": std.Var(I32, "stop"),
                "step": std.Var(I32, "step"),
            },
        )
        idx = next(iter(parsed.indices))
        assert isinstance(idx.start, std.Var)

    def test_load_round_trip(self) -> None:
        x = std.Var(I32, "x")
        _assert_roundtrip(std.Load(x, 1, ty=I32), extra_vars={"x": x})
        _assert_roundtrip(
            std.Load(x, std.Range(1, 2), std.Range(1, 2, 3), ty=I32),
            extra_vars={"x": x},
        )


class TestParseStore:
    def test_store_simple(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal(
            "x[1] = 2",
            self._wrap(std.Store(x, 2, 1)),
            extra_vars={"x": x},
        )

    def test_store_slice(self) -> None:
        x = std.Var(I32, "x")
        _assert_parse_equal(
            "x[1:2] = 3",
            self._wrap(std.Store(x, 3, std.Range(1, 2))),
            extra_vars={"x": x},
        )

    def test_store_into_literal_materializes_lhs(self) -> None:
        result = parse("@std.func\ndef f():\n  1[2] = 3")
        store = result.body[0]

        assert isinstance(store, std.Store)
        assert isinstance(store.lhs, std.IntImm)

    def test_store_tuple_rhs_fails(self) -> None:
        with pytest.raises(TypeError, match=r"Expected `ffi.std.Expr` but got `ffi.Array`"):
            parse("@std.func\ndef f(x: std.i32):\n  x[:] = (1, 2)")

    def test_store_into_anyty(self) -> None:
        result = parse("@std.func\ndef f(a: std.Any):\n  a[1] = 2")
        assert isinstance(result.body[0], std.Store)

    def test_store_with_attrs(self) -> None:
        result = parse('@std.func\ndef f(x: std.i32):\n  std.Store(x, 2, 1, tag="demo")')
        store = result.body[0]
        assert isinstance(store, std.Store)
        assert isinstance(store.attrs, std.DictAttrs)

    def test_nested_store_target(self) -> None:
        x = std.Var(I32, "x")
        result = parse("@std.func\ndef f(x: std.i32):\n  x[1][2] = 3", extra_vars={"x": x})
        store = result.body[0]
        assert isinstance(store.lhs, std.Load)

    def test_store_round_trip(self) -> None:
        x = std.Var(I32, "x")
        _assert_roundtrip(std.Store(x, 2, 1), extra_vars={"x": x})
        _assert_roundtrip(std.Store(x, 4, std.Range(None, 2), 3), extra_vars={"x": x})

    @staticmethod
    def _wrap(stmt: Any) -> Any:
        # Single top-level statement is returned directly by `parse`.
        return stmt


class TestGenericsDispatchMetadata:
    def test_bind_var_def_uses_active_dialect_for_parser_metadata(self) -> None:
        # The generic operands are parser metadata, roughly:
        # __bind_var_def__(["x"], std.i32).
        result = parse("@std.func\ndef f():\n  x: std.i32")

        assert isinstance(result.body[0], std.VarDef)
        assert result.body[0].vars[0].name == "x"
        assert _equal(result.body[0].vars[0].ty, I32)

    def test_if_uses_operand_dialect_with_body_list_metadata(self) -> None:
        # The generic operands include statement body lists, roughly:
        # __if__(std.Lt(...), [std.Return(...)], []).
        x = std.Var(I32, "x")
        result = parse("if x < 2:\n  return x", extra_vars={"x": x})

        assert isinstance(result, std.IfStmt)
        assert isinstance(result.then_body[0], std.Return)
        assert result.else_body == []


################################################################################
# Range / Slice
################################################################################


class TestParseRange:
    def test_full(self) -> None:
        _assert_parse_equal("1:10:2", std.Range(1, 10, 2))

    def test_negative(self) -> None:
        _assert_parse_equal(
            "-1:-3:-1",
            std.Range(std.IntImm(I64, -1), std.IntImm(I64, -3), std.IntImm(I64, -1)),
        )

    def test_start_stop(self) -> None:
        _assert_parse_equal("1:10", std.Range(1, 10))

    def test_start_only_via_slice(self) -> None:
        # NB: the printer collapses Range(start=1) to "1"; the slice form below
        # is the explicit way to write "Range(start=1) with no stop/step".
        _assert_parse_equal("1::", std.Range(start=1))

    def test_stop_only(self) -> None:
        _assert_parse_equal(":10", std.Range(stop=10))

    def test_step_only(self) -> None:
        _assert_parse_equal("::2", std.Range(step=2))

    def test_no_start(self) -> None:
        _assert_parse_equal(":10:2", std.Range(None, 10, 2))

    def test_no_stop(self) -> None:
        _assert_parse_equal("1::2", std.Range(start=1, step=2))

    def test_empty(self) -> None:
        _assert_parse_equal(":", std.Range())

    def test_explicit_factory(self) -> None:
        _assert_parse_equal("std.Range(1, 10, 2)", std.Range(1, 10, 2))

    def test_factory_positional(self) -> None:
        _assert_parse_equal("std.Range(10)", std.Range(None, 10))
        _assert_parse_equal("std.Range(1, 10)", std.Range(1, 10))
        _assert_parse_equal("std.Range(1, None)", std.Range(start=1))
        _assert_parse_equal("std.Range(None, 10)", std.Range(None, 10))
        _assert_parse_equal("std.Range(None, None, 2)", std.Range(None, None, 2))
        _assert_parse_equal("std.Range()", std.Range())

    def test_range_rejects_non_integer_bound(self) -> None:
        n = std.Var(I64, "n")
        with pytest.raises(
            TypeError, match=r"range expects Python integers or integer expressions"
        ):
            parse(
                "@std.func\ndef f():\n  for i in range(0.5, n, 2):\n    pass",
                extra_vars={"n": n},
            )

    def test_round_trip(self) -> None:
        for node in [
            std.Range(1),
            std.Range(1, None),
            std.Range(1, 10),
            std.Range(1, 10, 2),
            std.Range(1, None, 2),
            std.Range(None, 10),
            std.Range(None, 10, 2),
            std.Range(None, None, 2),
            std.Range(),
        ]:
            _assert_roundtrip(node)


################################################################################
# Calls
################################################################################


class TestParseCall:
    def test_simple_call(self) -> None:
        _assert_parse_equal(
            "std.Call(callee, 1, 2, ty=std.i32)",
            std.Call("callee", 1, 2, ty=I32),
            extra_vars={"callee": "callee"},
        )

    def test_call_with_attrs(self) -> None:
        _assert_parse_equal(
            'std.Call(callee, 1, tag="demo", ty=std.i32)',
            std.Call("callee", 1, tag="demo", ty=I32),
            extra_vars={"callee": "callee"},
        )

    def test_call_with_keyword_type(self) -> None:
        _assert_parse_equal(
            "std.Call(callee, 1, ty=std.i32)",
            std.Call("callee", 1, ty=I32),
            extra_vars={"callee": "callee"},
        )

    def test_generic_python_call(self) -> None:
        _assert_parse_equal(
            "callee(1, 2)",
            std.Call("callee", 1, 2, ty=std.AnyTy()),
            extra_vars={"callee": "callee"},
        )

    def test_starred_call_args(self) -> None:
        _assert_parse_equal(
            "std.Call(callee, *[1, 2], ty=std.i32)",
            std.Call("callee", 1, 2, ty=I32),
            extra_vars={"callee": "callee"},
        )

    def test_starred_call_kwargs(self) -> None:
        with pytest.raises(TypeError, match=r"\*\* keyword expansion is not supported"):
            parse(
                'std.Call(callee, **{"tag": "demo"}, ty=std.i32)',
                extra_vars={"callee": "callee"},
            )

    def test_call_no_args(self) -> None:
        _assert_parse_equal(
            "std.Call(callee, ty=std.i32)",
            std.Call("callee", ty=I32),
            extra_vars={"callee": "callee"},
        )

    def test_call_kwargs_sorted(self) -> None:
        node = std.Call("callee", a=1, z=2, ty=I32)
        _assert_roundtrip(node, extra_vars={"callee": "callee"})

    def test_call_with_func_callee(self) -> None:
        # When the callee is a Func, the printer emits its symbol; the
        # parser then resolves the bare identifier through the var-table.
        x = std.Var(I32, "x")
        callee = std.Func(
            symbol="helper",
            args=[x],
            ret_type=I32,
            body=[std.Return(x)],
        )
        node = std.Call(callee, 1, ty=I32)
        text = node.text()
        parsed = parse(text, extra_vars={"helper": callee})
        assert isinstance(parsed, std.Call)
        assert tvm_ffi.structural_equal(parsed.ty, I32)
        assert next(iter(parsed.args)).value == 1

    def test_call_round_trip_no_attrs(self) -> None:
        _assert_roundtrip(std.Call("callee", 1, 2, ty=I32), extra_vars={"callee": "callee"})

    def test_call_round_trip_with_attrs(self) -> None:
        _assert_roundtrip(
            std.Call("callee", 1, tag="demo", ty=I32),
            extra_vars={"callee": "callee"},
        )

    def test_call_int_literal_as_callee_fails(self) -> None:
        with pytest.raises(TypeError, match="callee must be a name"):
            parse("1(2)")

    def test_builtin_abs_resolves_to_std_abs(self) -> None:
        _assert_parse_equal("abs(1)", std.IntImm(I64, 1))


################################################################################
# DictAttrs
################################################################################


class TestParseDictAttrs:
    def test_one_kw(self) -> None:
        _assert_parse_equal('std.DictAttrs(tag="demo")', std.DictAttrs(tag="demo"))

    def test_many_kws_sorted(self) -> None:
        _assert_parse_equal(
            "std.DictAttrs(a=1, z=2)",
            std.DictAttrs(a=1, z=2),
        )

    def test_empty(self) -> None:
        _assert_parse_equal("std.DictAttrs()", std.DictAttrs())

    def test_list_value(self) -> None:
        _assert_roundtrip(std.DictAttrs(items=[1, 2, 3]))

    def test_deeply_nested_values(self) -> None:
        attrs = parse(
            'std.DictAttrs(config={"pad": (1, 3, 5), '
            '"levels": [{"tile": (2, 4)}, {"axis": (0, 1)}]})'
        )

        assert isinstance(attrs, std.DictAttrs)
        config = attrs["config"]
        assert config["pad"] == (1, 3, 5)
        assert config["levels"][0]["tile"] == (2, 4)
        assert config["levels"][1]["axis"] == (0, 1)

    def test_round_trip(self) -> None:
        _assert_roundtrip(std.DictAttrs())
        _assert_roundtrip(std.DictAttrs(tag="demo"))
        _assert_roundtrip(std.DictAttrs(a=1, z=2))


################################################################################
# Bindings — BindExpr, VarDef, annotated declarations
################################################################################


class TestParseBindings:
    def test_simple_bind_expr(self) -> None:
        x = std.Var(I64, "x")
        expected = std.Func(
            symbol="f",
            args=[],
            ret_type=None,
            body=[std.BindExpr(std.IntImm(I64, 1), std.Var(I64, "y"))],
        )
        _assert_parse_equal(
            "@std.func\ndef f():\n  y = 1",
            expected,
        )
        del x  # unused -- keeps lint happy

    def test_explicit_bind_expr_with_attrs(self) -> None:
        # `std.BindExpr` materializes native literals through the same
        # `__literal_int__` path as plain assignment.
        expected = std.Func(
            symbol="f",
            args=[],
            ret_type=None,
            body=[std.BindExpr(std.IntImm(I64, 1), std.Var(I64, "y"), tag="demo")],
        )
        _assert_parse_equal(
            '@std.func\ndef f():\n  y = std.BindExpr(1, tag="demo")',
            expected,
        )

    def test_bind_var_def(self) -> None:
        expected = std.Func(
            symbol="f",
            args=[],
            ret_type=None,
            body=[std.VarDef(std.Var(I32, "y"))],
        )
        _assert_parse_equal(
            "@std.func\ndef f():\n  y = std.VarDef(std.i32)",
            expected,
        )

    def test_bind_var_def_multi(self) -> None:
        expected = std.Func(
            symbol="f",
            args=[],
            ret_type=None,
            body=[std.VarDef(std.Var(I32, "a"), std.Var(F32, "b"))],
        )
        _assert_parse_equal(
            "@std.func\ndef f():\n  a, b = std.VarDef(std.i32, std.f32)",
            expected,
        )

    def test_bind_var_def_empty(self) -> None:
        expected = std.VarDef()
        _assert_parse_equal("std.VarDef()", expected)

    def test_bind_expr_empty_requires_expr(self) -> None:
        with pytest.raises(TypeError, match="missing 1 required positional argument"):
            parse("std.BindExpr()")

    def test_bind_var_def_unpack_arity_mismatch(self) -> None:
        with pytest.raises(TypeError, match="expected 2 binding target"):
            parse("@std.func\ndef f():\n  a, b, c = std.VarDef(std.i32, std.f32)")

    def test_annotated_decl_no_rhs(self) -> None:
        expected = std.Func(
            symbol="f",
            args=[],
            ret_type=None,
            body=[std.VarDef(std.Var(I32, "x"))],
        )
        _assert_parse_equal(
            "@std.func\ndef f():\n  x: std.i32",
            expected,
        )

    def test_annotated_assign_with_rhs_materializes_typed_literal(self) -> None:
        # Annotated bind with a native literal marks the literal's type directly.
        expected = std.Func(
            symbol="f",
            args=[],
            ret_type=None,
            body=[
                std.BindExpr(
                    std.IntImm(I32, 5),
                    std.Var(I32, "x"),
                )
            ],
        )
        _assert_parse_equal(
            "@std.func\ndef f():\n  x: std.i32 = 5",
            expected,
        )

    def test_non_default_typed_literal_bind_prints_rhs_type(self) -> None:
        node = std.Func(
            symbol="f",
            args=[],
            ret_type=None,
            body=[std.BindExpr(std.IntImm(I32, 5), std.Var(I32, "x"))],
        )
        assert node.text() == "@std.func\ndef f():\n  x = std.i32(5)"
        _assert_roundtrip(node)

    def test_string_bind(self) -> None:
        expected = std.Func(
            symbol="f",
            args=[],
            ret_type=None,
            body=[
                std.BindExpr(
                    std.StringImm(ANY, "hello"),
                    std.Var(ANY, "y"),
                )
            ],
        )
        _assert_parse_equal('@std.func\ndef f():\n  y = "hello"', expected)

    def test_round_trip_simple(self) -> None:
        # Plain integer binds round-trip through the `__literal_int__` default.
        _assert_roundtrip(std.BindExpr(std.IntImm(I64, 1), std.Var(I64, "y")))
        _assert_roundtrip(std.VarDef(std.Var(I32, "y")))
        _assert_roundtrip(std.BindExpr(std.IntImm(I64, 1), std.Var(I64, "y"), tag="demo"))
        _assert_roundtrip(std.VarDef(std.Var(I32, "y"), tag="demo"))

    def test_rebinding_same_name_emits_distinct_bindings(self) -> None:
        result = parse("@std.func\ndef f():\n  x = 1\n  x = 2")
        assert len(result.body) == 2
        assert all(isinstance(stmt, std.BindExpr) for stmt in result.body)


################################################################################
# Statements: assert / return / yield / break / continue / pass / ...
################################################################################


class TestParseStatements:
    def test_assert_simple(self) -> None:
        x = std.Var(I32, "x")
        expected = std.Assert(std.Lt(x, 2, ty=BOOL))
        _assert_parse_equal("assert x < 2", expected, extra_vars={"x": x})

    def test_assert_with_attrs(self) -> None:
        x = std.Var(I32, "x")
        expected = std.Func(
            symbol="f",
            args=[std.Var(I32, "x")],
            ret_type=None,
            body=[
                std.Assert(
                    std.Lt(std.Var(I32, "x"), 2, ty=BOOL),
                    tag="demo",
                )
            ],
        )
        _assert_parse_equal(
            '@std.func\ndef f(x: std.i32):\n  std.Assert(x < 2, tag="demo")',
            expected,
        )
        del x

    def test_assert_with_deeply_nested_attrs(self) -> None:
        result = parse(
            "@std.func\n"
            "def f():\n"
            "  std.Assert(1, pad=(1, 3, 5), "
            'config={"levels": [{"tile": (2, 4)}, {"axis": (0, 1)}]})'
        )

        assert isinstance(result, std.Func)
        stmt = result.body[0]
        assert isinstance(stmt, std.Assert)
        assert isinstance(stmt.attrs, std.DictAttrs)
        assert stmt.attrs["pad"] == (1, 3, 5)
        config = stmt.attrs["config"]
        assert config["levels"][0]["tile"] == (2, 4)
        assert config["levels"][1]["axis"] == (0, 1)

    def test_return_var(self) -> None:
        x = std.Var(I32, "x")
        expected = std.Return(x)
        _assert_parse_equal("return x", expected, extra_vars={"x": x})

    def test_return_tuple(self) -> None:
        x = std.Var(I32, "x")
        y = std.Var(I32, "y")
        expected = std.Return(x, y)
        _assert_parse_equal("return x, y", expected, extra_vars={"x": x, "y": y})

    def test_return_empty(self) -> None:
        _assert_parse_equal("return", std.Return())

    def test_return_none_is_empty_return(self) -> None:
        result = parse("@std.func\ndef f():\n  return None")
        assert isinstance(result.body[0], std.Return)
        assert list(result.body[0].exprs) == []

    def test_return_literal_and_expression(self) -> None:
        result = parse("@std.func\ndef f() -> std.i32:\n  return 0")
        assert isinstance(result.body[0].exprs[0], std.IntImm)
        result = parse("@std.func\ndef f() -> std.i32:\n  return 1 + 2")
        assert isinstance(result.body[0].exprs[0], std.IntImm)

    def test_yield_var(self) -> None:
        x = std.Var(I32, "x")
        expected = std.Yield(x)
        _assert_parse_equal("yield x", expected, extra_vars={"x": x})

    def test_yield_empty(self) -> None:
        _assert_parse_equal("yield", std.Yield())

    def test_yield_literal(self) -> None:
        result = parse("@std.func\ndef f():\n  yield 1")
        assert isinstance(result.body[0].exprs[0], std.IntImm)

    def test_break(self) -> None:
        _assert_parse_equal("break", std.Break())

    def test_continue(self) -> None:
        _assert_parse_equal("continue", std.Continue())

    def test_pass_is_noop_inside_func(self) -> None:
        expected = std.Func(symbol="f", args=[], ret_type=None, body=[])
        _assert_parse_equal("@std.func\ndef f():\n  pass", expected)

    def test_ellipsis_is_noop_inside_func(self) -> None:
        expected = std.Func(symbol="f", args=[], ret_type=None, body=[])
        _assert_parse_equal("@std.func\ndef f():\n  ...", expected)

    def test_pass_at_top_level(self) -> None:
        assert parse("pass") is None

    def test_ellipsis_at_top_level(self) -> None:
        assert parse("...") is None

    def test_break_continue_round_trip(self) -> None:
        _assert_roundtrip(std.Break())
        _assert_roundtrip(std.Continue())

    def test_top_level_assert(self) -> None:
        # Assert at top level lifts directly to a `std.Assert` value.
        result = parse("assert 1 == 1")
        assert isinstance(result, std.Assert)

    def test_assert_with_chained_compare(self) -> None:
        result = parse("@std.func\ndef f(x: std.i32):\n  assert 0 < x < 10")
        assert isinstance(result.body[0], std.Assert)
        assert isinstance(result.body[0].cond, std.And)

    def test_top_level_return(self) -> None:
        result = parse("return")
        assert isinstance(result, std.Return)
        assert list(result.exprs) == []

    def test_break_continue_attrs_round_trip_explicitly(self) -> None:
        break_text = std.Break(tag="demo").text()
        continue_text = std.Continue(tag="demo").text()
        assert break_text == 'std.Break(tag="demo")'
        assert continue_text == 'std.Continue(tag="demo")'
        assert dict(parse(break_text).attrs.values) == {"tag": "demo"}
        assert dict(parse(continue_text).attrs.values) == {"tag": "demo"}

    def test_break_outside_loop_is_allowed(self) -> None:
        result = parse("@std.func\ndef f():\n  break")
        assert isinstance(result.body[0], std.Break)


################################################################################
# Functions
################################################################################


class TestParseFunc:
    def test_basic(self) -> None:
        expected = std.Func(
            symbol="main",
            args=[std.Var(I32, "x")],
            ret_type=I32,
            body=[std.Return(std.Var(I32, "x"))],
        )
        _assert_parse_equal(
            "@std.func\ndef main(x: std.i32) -> std.i32:\n  return x",
            expected,
        )

    def test_with_attrs(self) -> None:
        expected = std.Func(
            symbol="main",
            attrs={"tag": "demo"},
            args=[std.Var(I32, "x")],
            ret_type=I32,
            body=[std.Return(std.Var(I32, "x"))],
        )
        _assert_parse_equal(
            '@std.func(tag="demo")\ndef main(x: std.i32) -> std.i32:\n  return x',
            expected,
        )

    def test_no_return_type(self) -> None:
        expected = std.Func(
            symbol="main",
            args=[std.Var(I32, "x")],
            ret_type=None,
            body=[std.Return(std.Var(I32, "x"))],
        )
        _assert_parse_equal(
            "@std.func\ndef main(x: std.i32):\n  return x",
            expected,
        )

    def test_no_args(self) -> None:
        expected = std.Func(symbol="f", args=[], ret_type=None, body=[])
        _assert_parse_equal("@std.func\ndef f():\n  pass", expected)

    def test_decorator_empty_parens(self) -> None:
        expected = std.Func(symbol="f", args=[], ret_type=None, body=[])
        _assert_parse_equal("@std.func()\ndef f():\n  pass", expected)

    def test_unannotated_arg_defaults_to_anyty(self) -> None:
        expected = std.Func(
            symbol="f",
            args=[std.Var(ANY, "x")],
            ret_type=None,
            body=[],
        )
        _assert_parse_equal("@std.func\ndef f(x):\n  pass", expected)

    def test_multi_arg(self) -> None:
        expected = std.Func(
            symbol="f",
            args=[std.Var(I32, "x"), std.Var(F32, "y")],
            ret_type=None,
            body=[],
        )
        _assert_parse_equal(
            "@std.func\ndef f(x: std.i32, y: std.f32):\n  pass",
            expected,
        )

    def test_duplicate_arg_name_fails_at_second_arg(self) -> None:
        with pytest.raises(ValueError, match="already defined"):
            parse("@std.func\ndef f(x: std.i32, x: std.f32):\n  pass")

    def test_nested_function(self) -> None:
        # Nested @std.func is parsed as a body statement.
        expected = std.Func(
            symbol="outer",
            args=[],
            ret_type=None,
            body=[
                std.Func(
                    symbol="inner",
                    args=[],
                    ret_type=None,
                    body=[],
                )
            ],
        )
        _assert_parse_equal(
            "@std.func\ndef outer():\n  @std.func\n  def inner():\n    pass",
            expected,
        )

    def test_round_trip(self) -> None:
        x = std.Var(I32, "x")
        _assert_roundtrip(
            std.Func(
                symbol="main",
                args=[x],
                ret_type=I32,
                body=[std.Return(x)],
            )
        )
        _assert_roundtrip(
            std.Func(
                symbol="main",
                attrs={"tag": "demo"},
                args=[x],
                ret_type=I32,
                body=[std.Return(x)],
            )
        )


################################################################################
# Module
################################################################################


class TestParseModule:
    def test_empty_class_module(self) -> None:
        _assert_parse_equal("@std.module\nclass M:\n  pass", std.Module([]))

    def test_class_form(self) -> None:
        expected = std.Module(
            [
                std.Func(
                    symbol="main",
                    attrs={"tag": "demo"},
                    args=[std.Var(I32, "x")],
                    ret_type=I32,
                    body=[std.Return(std.Var(I32, "x"))],
                )
            ]
        )
        _assert_parse_equal(
            "@std.module\nclass M:\n"
            '  @std.func(tag="demo")\n'
            "  def main(x: std.i32) -> std.i32:\n"
            "    return x",
            expected,
        )

    def test_class_form_two_funcs(self) -> None:
        expected = std.Module(
            [
                std.Func(
                    symbol="f",
                    args=[],
                    ret_type=None,
                    body=[],
                ),
                std.Func(
                    symbol="g",
                    args=[],
                    ret_type=None,
                    body=[],
                ),
            ]
        )
        _assert_parse_equal(
            "@std.module\n"
            "class M:\n"
            "  @std.func\n"
            "  def f():\n"
            "    pass\n"
            "  @std.func\n"
            "  def g():\n"
            "    pass",
            expected,
        )

    def test_top_level_two_funcs_returns_module(self) -> None:
        # Multiple `@std.func`-decorated functions at top level collapse into
        # an implicit Module via `__ffi_parse_top_result__`.
        expected = std.Module(
            [
                std.Func(symbol="f", args=[], ret_type=None, body=[]),
                std.Func(symbol="g", args=[], ret_type=None, body=[]),
            ]
        )
        _assert_parse_equal(
            "@std.func\ndef f():\n  pass\n@std.func\ndef g():\n  pass",
            expected,
        )

    def test_top_level_duplicate_func_names_are_kept(self) -> None:
        result = parse("@std.func\ndef f():\n  pass\n@std.func\ndef f():\n  pass")
        assert isinstance(result, std.Module)
        assert len(result.funcs) == 2

    def test_class_module_rejects_non_func_body(self) -> None:
        with pytest.raises(TypeError, match="got BindExpr"):
            parse("@std.module\nclass M:\n  x = 1")

    def test_round_trip_two_funcs(self) -> None:
        x = std.Var(I32, "x")
        _assert_roundtrip(
            std.Module(
                [
                    std.Func(
                        symbol="main",
                        args=[x],
                        ret_type=I32,
                        body=[std.Return(x)],
                    ),
                    std.Func(
                        symbol="helper",
                        args=[x],
                        ret_type=I32,
                        body=[std.Return(x)],
                    ),
                ]
            )
        )


################################################################################
# If
################################################################################


class TestParseIf:
    def test_with_else(self) -> None:
        x = std.Var(I32, "x")
        y = std.Var(I32, "y")
        expected = std.IfStmt(
            std.Lt(std.Var(I32, "x"), 2, ty=BOOL),
            [std.Return(std.Var(I32, "x"))],
            [std.Return(std.Var(I32, "y"))],
        )
        _assert_parse_equal(
            "if x < 2:\n  return x\nelse:\n  return y",
            expected,
            extra_vars={"x": x, "y": y},
        )

    def test_without_else(self) -> None:
        x = std.Var(I32, "x")
        expected = std.IfStmt(
            std.Lt(std.Var(I32, "x"), 2, ty=BOOL),
            [std.Return(std.Var(I32, "x"))],
            [],
        )
        _assert_parse_equal(
            "if x < 2:\n  return x",
            expected,
            extra_vars={"x": x},
        )

    def test_nested_if(self) -> None:
        expected = std.Func(
            symbol="f",
            args=[std.Var(I32, "x")],
            ret_type=I32,
            body=[
                std.IfStmt(
                    std.Lt(std.Var(I32, "x"), 0, ty=BOOL),
                    [std.Return(std.Var(I32, "x"))],
                    [
                        std.IfStmt(
                            std.Lt(std.Var(I32, "x"), 5, ty=BOOL),
                            [std.Return(std.Var(I32, "x"))],
                            [std.Return(std.Var(I32, "x"))],
                        )
                    ],
                )
            ],
        )
        _assert_parse_equal(
            "@std.func\n"
            "def f(x: std.i32) -> std.i32:\n"
            "  if x < 0:\n"
            "    return x\n"
            "  else:\n"
            "    if x < 5:\n"
            "      return x\n"
            "    else:\n"
            "      return x",
            expected,
        )

    def test_chained_compare_in_cond(self) -> None:
        x = std.Var(I32, "x")
        expected = std.IfStmt(
            std.And(
                std.Lt(0, std.Var(I32, "x"), ty=BOOL),
                std.Lt(std.Var(I32, "x"), 10, ty=BOOL),
                ty=BOOL,
            ),
            [],
            [],
        )
        _assert_parse_equal(
            "if 0 < x < 10:\n  pass",
            expected,
            extra_vars={"x": x},
        )

    def test_round_trip(self) -> None:
        x = std.Var(I64, "x")
        y = std.Var(I64, "y")
        _assert_roundtrip(
            std.IfStmt(
                std.Lt(x, 2, ty=BOOL),
                [std.Return(x)],
                [std.Return(y)],
            ),
            extra_vars={"x": x, "y": y},
        )
        _assert_roundtrip(
            std.IfStmt(std.Lt(x, 2, ty=BOOL), [std.Return(x)], []),
            extra_vars={"x": x},
        )


################################################################################
# For
################################################################################


class TestParseFor:
    def test_basic(self) -> None:
        x = std.Var(I64, "x")
        expected = std.For(
            start=1,
            stop=2,
            step=None,
            body=[std.Store(x, 2, 1)],
            vars=[x],
        )
        _assert_parse_equal("for x in range(1, 2):\n  x[1] = 2", expected)

    def test_with_attrs(self) -> None:
        x = std.Var(I64, "x")
        expected = std.For(
            start=1,
            stop=2,
            step=None,
            body=[std.Store(x, 2, 1)],
            vars=[x],
            attrs={"tag": "demo"},
        )
        _assert_parse_equal(
            'for x in range(1, 2, tag="demo"):\n  x[1] = 2',
            expected,
        )

    def test_with_one_arg_range(self) -> None:
        i = std.Var(I64, "i")
        expected = std.For(
            start=None,
            stop=10,
            step=None,
            body=[],
            vars=[i],
        )
        _assert_parse_equal("for i in range(10):\n  pass", expected)

    def test_with_three_arg_range(self) -> None:
        i = std.Var(I64, "i")
        expected = std.For(
            start=0,
            stop=10,
            step=2,
            body=[],
            vars=[i],
        )
        _assert_parse_equal("for i in range(0, 10, 2):\n  pass", expected)

    def test_non_frame_iterator_fails(self) -> None:
        with pytest.raises(TypeError, match="expected parser frame"):
            parse("@std.func\ndef f():\n  for i in 1 + 2:\n    pass")

    def test_std_range_node_is_not_a_for_frame(self) -> None:
        with pytest.raises(TypeError, match="expected parser frame, got Range"):
            parse("@std.func\ndef f():\n  for i in std.Range(1, 10):\n    pass")

    def test_range_resolves_qualified_or_unqualified(self) -> None:
        a = parse("@std.func\ndef f():\n  for i in range(10):\n    pass")
        b = parse("@std.func\ndef f():\n  for i in std.range(10):\n    pass")
        assert _equal(a.body[0].start, b.body[0].start)
        assert _equal(a.body[0].stop, b.body[0].stop)
        assert _equal(a.body[0].step, b.body[0].step)

    def test_explicit_for_factory(self) -> None:
        i = std.Var(ANY, "i")
        expected = std.For(
            start=1,
            stop=10,
            step=2,
            body=[],
            vars=[i],
            attrs={"tag": "demo"},
        )
        _assert_parse_equal(
            'for i in std.for_(std.Range(1, 10, 2), tag="demo"):\n  pass',
            expected,
        )

    def test_python_true_range(self) -> None:
        result = parse("@std.func\ndef f():\n  for i in range(True):\n    pass")
        assert isinstance(result.body[0], std.For)

    def test_typed_bound_propagates_to_loop_var(self) -> None:
        n = std.Var(I64, "n")
        result = parse(
            "@std.func\ndef f():\n  for i in range(n):\n    pass\n",
            extra_vars={"n": n},
        )
        loop_var = result.body[0].vars[0]
        assert _equal(loop_var.ty, I64)

    def test_underscore_target(self) -> None:
        # `_` is a regular name bound to the loop induction var.
        underscore = std.Var(I64, "_")
        expected = std.For(
            start=None,
            stop=10,
            step=None,
            body=[],
            vars=[underscore],
        )
        _assert_parse_equal("for _ in range(10):\n  pass", expected)

    def test_nested_for(self) -> None:
        i = std.Var(I64, "i")
        j = std.Var(I64, "j")
        expected = std.For(
            start=None,
            stop=10,
            step=None,
            body=[
                std.For(
                    start=None,
                    stop=10,
                    step=None,
                    body=[],
                    vars=[j],
                )
            ],
            vars=[i],
        )
        _assert_parse_equal(
            "for i in range(10):\n  for j in range(10):\n    pass",
            expected,
        )

    def test_round_trip(self) -> None:
        x = std.Var(I64, "x")
        _assert_roundtrip(
            std.For(
                start=1,
                stop=2,
                step=None,
                body=[std.Store(x, 2, 1)],
                vars=[x],
            )
        )
        _assert_roundtrip(
            std.For(
                start=1,
                stop=2,
                step=None,
                body=[std.Store(x, 2, 1)],
                vars=[x],
                attrs={"tag": "demo"},
            )
        )

    def test_round_trip_sparse_range_fields(self) -> None:
        x = std.Var(I64, "x")
        for node in [
            std.For(
                start=1,
                stop=None,
                step=None,
                body=[],
                vars=[x],
            ),
            std.For(
                start=None,
                stop=None,
                step=2,
                body=[],
                vars=[x],
            ),
        ]:
            _assert_roundtrip(node)


################################################################################
# While
################################################################################


class TestParseWhile:
    def test_simple(self) -> None:
        x = std.Var(I32, "x")
        y = std.Var(I64, "y")
        expected = std.While(
            cond=std.Lt(std.Var(I32, "x"), 2, ty=BOOL),
            body=[std.BindExpr(std.IntImm(I64, 2), y)],
        )
        _assert_parse_equal(
            "while x < 2:\n  y = 2",
            expected,
            extra_vars={"x": x},
        )
        del y

    def test_while_true(self) -> None:
        result = parse("@std.func\ndef f():\n  while True:\n    break")
        assert isinstance(result.body[0], std.While)
        assert isinstance(result.body[0].cond, std.BoolImm)
        assert result.body[0].cond.value is True

    def test_with_form_with_attrs(self) -> None:
        x = std.Var(I32, "x")
        y = std.Var(I64, "y")
        expected = std.While(
            cond=std.Lt(std.Var(I32, "x"), 2, ty=BOOL),
            body=[std.BindExpr(std.IntImm(I64, 2), y)],
            attrs={"tag": "demo"},
        )
        _assert_parse_equal(
            'with std.while_(x < 2, tag="demo"):\n  y = 2',
            expected,
            extra_vars={"x": x},
        )
        del y

    def test_round_trip(self) -> None:
        x = std.Var(I64, "x")
        y = std.Var(I64, "y")
        _assert_roundtrip(
            std.While(
                cond=std.Lt(x, 2, ty=BOOL),
                body=[std.BindExpr(std.IntImm(I64, 2), y)],
            ),
            extra_vars={"x": x, "y": y},
        )
        _assert_roundtrip(
            std.While(
                cond=std.Lt(x, 2, ty=BOOL),
                body=[std.BindExpr(std.IntImm(I64, 2), y)],
                attrs={"tag": "demo"},
            ),
            extra_vars={"x": x, "y": y},
        )


################################################################################
# Scope (with form)
################################################################################


class TestParseScope:
    def test_with_scope_no_as(self) -> None:
        result = parse("@std.func\ndef f():\n  with std.scope():\n    pass")
        assert isinstance(result.body[0], std.Scope)
        assert list(result.body[0].binds) == []

    def test_with_one_bind(self) -> None:
        expected = std.Scope(
            [std.VarDef(std.Var(I32, "x"))],
            [std.Return(std.Var(I32, "x"))],
        )
        _assert_parse_equal(
            "with std.scope(std.VarDef(std.i32)) as x:\n  return x",
            expected,
        )

    def test_with_attrs(self) -> None:
        x = std.Var(I32, "x")
        expected = std.Func(
            symbol="f",
            args=[std.Var(I32, "x")],
            ret_type=None,
            body=[
                std.Scope(
                    [],
                    [std.Return(std.Var(I32, "x"))],
                    attrs={"pragma": "scope"},
                )
            ],
        )
        _assert_parse_equal(
            '@std.func\ndef f(x: std.i32):\n  with std.scope(pragma="scope"):\n    return x',
            expected,
        )
        del x

    def test_with_multiple_targets(self) -> None:
        x = std.Var(I32, "x")
        y = std.Var(F32, "y")
        expected = std.Scope(
            [
                std.VarDef(x),
                std.VarDef(y),
            ],
            [],
        )
        _assert_parse_equal(
            "with std.scope(std.VarDef(std.i32), std.VarDef(std.f32)) as (x, y):\n  pass",
            expected,
        )

    def test_with_mixed_bind_initializers(self) -> None:
        result = parse(
            "@std.func\ndef f():\n  with std.scope(std.VarDef(std.i32), 1) as (a, b):\n    pass"
        )
        scope = result.body[0]
        assert isinstance(scope.binds[0], std.VarDef)
        assert isinstance(scope.binds[1], std.BindExpr)

    def test_nested_with_has_distinct_scopes(self) -> None:
        result = parse(
            "@std.func\n"
            "def f():\n"
            "  with std.scope(std.VarDef(std.i32)) as a:\n"
            "    with std.scope(std.VarDef(std.f32)) as b:\n"
            "      pass"
        )
        outer = result.body[0]
        assert isinstance(outer, std.Scope)
        assert isinstance(outer.body[0], std.Scope)

    def test_round_trip(self) -> None:
        x = std.Var(I32, "x")
        _assert_roundtrip(
            std.Scope(
                [std.VarDef(x)],
                [std.Return(x)],
            )
        )


################################################################################
# Slice expression at top level
################################################################################


class TestParseSliceTop:
    """Top-level slice expressions go through the `_slice_[...]` parse
    fallback because Python rejects bare slices.
    """

    def test_full(self) -> None:
        _assert_parse_equal("1:10:2", std.Range(1, 10, 2))

    def test_partial(self) -> None:
        _assert_parse_equal("1:10", std.Range(1, 10))

    def test_empty(self) -> None:
        _assert_parse_equal(":", std.Range())


################################################################################
# Containers (literal)
################################################################################


class TestParseContainers:
    def test_tuple_literal(self) -> None:
        # Top-level tuple expr is materialized as-is (it's not a node, not a
        # frame, and not a literal-the-language-knows-about).
        result = parse("1, 2, 3")
        assert result == (1, 2, 3)

    def test_singleton_tuple_literal(self) -> None:
        assert parse("(1,)") == (1,)

    def test_paren_int_unwraps(self) -> None:
        _assert_parse_equal("(1)", std.IntImm(I64, 1))

    def test_top_level_dict_passes_through(self) -> None:
        assert parse('{"a": 1}') == {"a": 1}

    def test_top_level_empty_list_passes_through(self) -> None:
        assert parse("[]") == []

    def test_list_literal_in_call(self) -> None:
        x = std.Var(I32, "x")
        parsed = parse("std.Load(x, *[1, 2], ty=std.i32)", extra_vars={"x": x})
        assert _equal(parsed, std.Load(x, 1, 2, ty=I32))


################################################################################
# Round-trip: every concrete printer output from test_std.py
################################################################################


class TestRoundtripFromTestStd:
    """Round-trip every shape that `test_std.py` asserts on, so the parser
    doesn't drift away from the printer's output.
    """

    def test_all_types(self) -> None:
        for node in [
            std.AnyTy(),
            std.PrimTy("int32"),
            std.PrimTy("float32"),
            std.PrimTy("bfloat16"),
            std.PrimTy("uint8"),
            std.PrimTy("float8_e4m3fn"),
            std.TupleTy([I32, F32]),
            std.TensorTy([4, 8], "float32"),
            std.TensorTy([14, 21], "int32"),
        ]:
            _assert_roundtrip(node)

    def test_all_imms(self) -> None:
        _assert_roundtrip(std.IntImm(I64, 7))
        _assert_roundtrip(std.IntImm(I64, -42))
        _assert_roundtrip(std.IntImm(I64, 0))
        _assert_roundtrip(std.FloatImm(F32, 1.5))
        _assert_roundtrip(std.FloatImm(F32, -2.5))

    @pytest.mark.parametrize(
        "node",
        [
            std.Add(1, 2, ty=I64),
            std.Sub(5, 3, ty=I64),
            std.Mul(3, 4, ty=I64),
            std.CDiv(6, 2, ty=I64),
            std.FloorDiv(6, 2, ty=I64),
            std.FloorMod(7, 3, ty=I64),
            std.CMod(7, 3, ty=I64),
            std.BitwiseAnd(1, 2, ty=I64),
            std.BitwiseOr(1, 2, ty=I64),
            std.BitwiseXor(1, 2, ty=I64),
            std.Min(1, 2, ty=I64),
            std.Max(1, 2, ty=I64),
            std.Eq(1, 2, ty=BOOL),
            std.Ne(1, 2, ty=BOOL),
            std.Le(1, 2, ty=BOOL),
            std.Ge(1, 2, ty=BOOL),
            std.Gt(1, 2, ty=BOOL),
            std.Lt(1, 2, ty=BOOL),
            std.And(1, 2, ty=BOOL),
            std.Or(1, 2, ty=BOOL),
            std.Not(1, ty=BOOL),
            std.BitwiseNot(1, ty=I64),
            std.Abs(-1, ty=I64),
        ],
    )
    def test_all_binops_and_unary(self, node: Any) -> None:
        _assert_roundtrip(node)

    def test_load(self) -> None:
        x = std.Var(I32, "x")
        for indices in [[1], [1, 2], [std.Range(1, 2)], [std.Range(1, 2), 3]]:
            _assert_roundtrip(std.Load(x, *indices, ty=I32), extra_vars={"x": x})

    def test_call_round_trip(self) -> None:
        for node in [
            std.Call("callee", 1, 2, ty=I32),
            std.Call("callee", ty=I32),
            std.Call("callee", 1, tag="demo", ty=I32),
            std.Call("callee", a=1, z=2, ty=I32),
        ]:
            _assert_roundtrip(node, extra_vars={"callee": "callee"})

    def test_dict_attrs(self) -> None:
        for node in [
            std.DictAttrs(),
            std.DictAttrs(tag="demo"),
            std.DictAttrs(a=1, z=2),
        ]:
            _assert_roundtrip(node)

    def test_func_with_comments_strips_them(self) -> None:
        # Pure comment lines are dropped during AST translation.
        expected = std.Func(symbol="f", args=[], ret_type=None, body=[])
        _assert_parse_equal(
            "@std.func\ndef f():\n  # this is a comment\n  pass",
            expected,
        )

    def test_func_multi_stmt_body_round_trip(self) -> None:
        x = std.Var(I32, "x")
        y = std.Var(I32, "y")
        node = std.Func(
            symbol="f",
            args=[x],
            ret_type=I32,
            body=[
                std.BindExpr(std.Add(x, 1, ty=I32), y),
                std.Return(y),
            ],
        )
        _assert_roundtrip(node)

    def test_func_round_trip(self) -> None:
        x = std.Var(I32, "x")
        for node in [
            std.Func(
                symbol="main",
                args=[x],
                ret_type=I32,
                body=[std.Return(x)],
            ),
            std.Func(
                symbol="main",
                args=[x],
                ret_type=None,
                body=[std.Return(x)],
            ),
            std.Func(
                symbol="main",
                attrs={"tag": "demo"},
                args=[x],
                ret_type=I32,
                body=[std.Return(x)],
            ),
        ]:
            _assert_roundtrip(node)

    def test_module_round_trip(self) -> None:
        x = std.Var(I32, "x")
        node = std.Module(
            [
                std.Func(
                    symbol="main",
                    attrs={"tag": "demo"},
                    args=[x],
                    ret_type=I32,
                    body=[std.Return(x)],
                ),
                std.Func(
                    symbol="helper",
                    args=[x],
                    ret_type=I32,
                    body=[std.Return(x)],
                ),
            ]
        )
        _assert_roundtrip(node)

    def test_for_round_trip(self) -> None:
        x = std.Var(I64, "x")
        for node in [
            std.For(
                start=1,
                stop=2,
                step=None,
                body=[std.Store(x, 2, 1)],
                vars=[x],
            ),
            std.For(
                start=1,
                stop=2,
                step=None,
                body=[std.Store(x, 2, 1)],
                vars=[x],
                attrs={"tag": "demo"},
            ),
        ]:
            _assert_roundtrip(node)

    def test_scope_round_trip(self) -> None:
        x = std.Var(I32, "x")
        node = std.Scope(
            [std.VarDef(x)],
            [std.Return(x)],
        )
        _assert_roundtrip(node)

    def test_while_round_trip(self) -> None:
        x = std.Var(I64, "x")
        y = std.Var(I64, "y")
        for node in [
            std.While(
                cond=std.Lt(x, 2, ty=BOOL),
                body=[std.BindExpr(std.IntImm(I64, 2), y)],
            ),
            std.While(
                cond=std.Lt(x, 2, ty=BOOL),
                body=[std.BindExpr(std.IntImm(I64, 2), y)],
                attrs={"tag": "demo"},
            ),
        ]:
            _assert_roundtrip(node, extra_vars={"x": x, "y": y})

    def test_if_round_trip(self) -> None:
        x = std.Var(I64, "x")
        y = std.Var(I64, "y")
        _assert_roundtrip(
            std.IfStmt(
                std.Lt(x, 2, ty=BOOL),
                [std.Return(x)],
                [std.Return(y)],
            ),
            extra_vars={"x": x, "y": y},
        )
        _assert_roundtrip(
            std.IfStmt(std.Lt(x, 2, ty=BOOL), [std.Return(x)], []),
            extra_vars={"x": x},
        )

    def test_bind_round_trip(self) -> None:
        # Plain and attrs-wrapped binds both round-trip through literal generics.
        x_i32 = std.Var(I32, "x")
        for node in [
            std.BindExpr(std.IntImm(I32, 1), x_i32),
            std.BindExpr(std.IntImm(I32, 1), x_i32, tag="demo"),
            std.VarDef(x_i32),
            std.VarDef(x_i32, tag="demo"),
        ]:
            _assert_roundtrip(node)

    def test_store_round_trip(self) -> None:
        x = std.Var(I32, "x")
        _assert_roundtrip(std.Store(x, 2, 1), extra_vars={"x": x})
        _assert_roundtrip(std.Store(x, 4, std.Range(1, 2), 3), extra_vars={"x": x})

    def test_assert_return_yield_round_trip(self) -> None:
        x = std.Var(I64, "x")
        for node in [
            std.Assert(std.Lt(x, 2, ty=BOOL)),
            std.Assert(std.Lt(x, 2, ty=BOOL), tag="demo"),
            std.Return(x),
            std.Return(x, x),
            std.Return(),
            std.Yield(x),
            std.Yield(),
            std.Break(),
            std.Continue(),
        ]:
            _assert_roundtrip(node, extra_vars={"x": x})


################################################################################
# Type inference
################################################################################


class TestTypeInference:
    def test_binop_anyty_lhs_dominates(self) -> None:
        a = std.Var(ANY, "a")
        b = std.Var(I32, "b")
        parsed = parse("a + b", extra_vars={"a": a, "b": b})
        assert _equal(parsed.ty, ANY)

    def test_binop_anyty_rhs_dominates(self) -> None:
        a = std.Var(I32, "a")
        b = std.Var(ANY, "b")
        parsed = parse("a + b", extra_vars={"a": a, "b": b})
        assert _equal(parsed.ty, ANY)

    def test_binop_both_anyty_stays_anyty(self) -> None:
        a = std.Var(ANY, "a")
        b = std.Var(ANY, "b")
        parsed = parse("a + b", extra_vars={"a": a, "b": b})
        assert _equal(parsed.ty, ANY)

    def test_anyty_in_three_way_binop_dominates(self) -> None:
        a = std.Var(ANY, "a")
        b = std.Var(I32, "b")
        c = std.Var(ANY, "c")
        parsed = parse("a + b + c", extra_vars={"a": a, "b": b, "c": c})
        assert _equal(parsed.ty, ANY)

    def test_load_element_type_partial(self) -> None:
        # Indexing one dim of a 3-rank tensor yields a 2-rank tensor.
        ty = std.TensorTy([4, 8, 16], "float32")
        a = std.Var(ty, "a")
        parsed = parse("a[0]", extra_vars={"a": a})
        assert isinstance(parsed.ty, std.TensorTy)
        assert [int(d.value) for d in parsed.ty.shape] == [8, 16]

    def test_load_element_type_full(self) -> None:
        # Indexing every dim yields the base scalar type.
        ty = std.TensorTy([4, 8], "float32")
        a = std.Var(ty, "a")
        parsed = parse("a[1, 2]", extra_vars={"a": a})
        assert _equal(parsed.ty, F32)

    def test_load_element_type_zero_index(self) -> None:
        # `x[()]` is a 0-index load — element type is the base type.
        x = std.Var(I32, "x")
        parsed = parse("x[()]", extra_vars={"x": x})
        assert _equal(parsed.ty, I32)

    def test_for_loop_var_inherits_neighbor_type(self) -> None:
        x = std.Var(I64, "x")
        result = parse(
            "@std.func\ndef f(): \n  for i in range(x):\n    pass\n",
            extra_vars={"x": x},
        )
        for_stmt = result.body[0]
        loop_var = for_stmt.vars[0]
        assert _equal(loop_var.ty, I64)

    def test_for_default_int_when_all_literal(self) -> None:
        result = parse("@std.func\ndef f():\n  for i in range(0, 10):\n    pass")
        for_stmt = result.body[0]
        loop_var = for_stmt.vars[0]
        assert _equal(loop_var.ty, I64)


################################################################################
# Parser API: parse and options
################################################################################


class TestParserAPI:
    def test_parse_string(self) -> None:
        assert _equal(parse("std.i32"), I32)

    def test_parse_pyast_node(self) -> None:
        text = std.PrimTy("int32").text()
        assert _equal(parse(parse(text).text()), I32)

    def test_register_dialect_exposes_registered_namespace(self) -> None:
        class ToyExpr:
            __ffi_dialect_mnemonic__ = ("toy_parser_api", "Expr")

        class Toy:
            __ffi_globals__: ClassVar[dict[str, Any]] = {}
            __ffi_generics__: ClassVar[dict[str, Any]] = {
                "__add__": lambda lhs, rhs: ("toy_add", lhs, rhs),
            }

            value = ToyExpr()

        register_dialect("toy_parser_api", Toy)
        assert parse("toy_parser_api.value + 1") == ("toy_add", Toy.value, 1)

    def test_extra_vars(self) -> None:
        x = std.Var(I32, "x")
        assert _equal(parse("x", extra_vars={"x": x}), x)

    def test_empty_input(self) -> None:
        assert parse("") is None

    def test_single_value_returns_value(self) -> None:
        # The top-result hook unwraps a single value.
        assert _equal(parse("1 + 2"), std.IntImm(I64, 3))

    def test_multi_value_returns_list(self) -> None:
        result = parse("1\n2")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_mixed_top_level_values_and_funcs_returns_list(self) -> None:
        result = parse("1\n@std.func\ndef f():\n  pass")
        assert isinstance(result, list)
        assert isinstance(result[0], std.IntImm)
        assert isinstance(result[1], std.Func)

    def test_top_level_funcs_collapse_to_module(self) -> None:
        result = parse("@std.func\ndef f():\n  pass\n@std.func\ndef g():\n  pass")
        assert isinstance(result, std.Module)
        assert len(result.funcs) == 2

    def test_leading_and_trailing_whitespace(self) -> None:
        _assert_parse_equal("   1 + 2   ", std.IntImm(I64, 3))
        _assert_parse_equal("1 + 2\n", std.IntImm(I64, 3))

    def test_parse_callable(self) -> None:
        # The parser also accepts a Python callable; it inspects the source
        # via `inspect`. The function body must have an explicit @std.func
        # decorator (or it's treated as a plain `def`).
        with pytest.raises(TypeError, match="exactly one decorator"):

            def _no_decorator(x: Any) -> Any:
                return x

            parse(_no_decorator)

    def test_feature_version_passes_through(self) -> None:
        # Pinning a feature version still parses ordinary expressions.
        assert _equal(parse("1 + 2", feature_version=(3, 12)), std.IntImm(I64, 3))

    def test_extra_vars_none(self) -> None:
        # `None` is the documented sentinel for "no extras"; passing it
        # explicitly should behave identically to omitting the kwarg.
        assert _equal(parse("std.i32", extra_vars=None), I32)

    def test_min_resolves_via_language_globals(self) -> None:
        # `min` is seeded by the language module's __ffi_globals__.
        # It must resolve even though unknown identifiers are rejected.
        result = parse("min")
        assert callable(result)

    def test_state_isolation_between_parse_calls(self) -> None:
        parse("y = 1")
        with pytest.raises(NameError, match="not defined"):
            parse("y")


################################################################################
# Errors / unsupported features
################################################################################


class TestParserErrors:
    def test_caught_error_is_quiet_and_carries_diagnostic(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(TypeError) as exc_info:
            parse("std.Any[4, 8]")
        captured = capsys.readouterr()
        assert captured.err == ""
        message = str(exc_info.value)
        assert message.startswith("error: std.Any cannot be indexed")
        assert " --> <str>:1:1" in message
        assert "std.Any[4, 8]" in message

    def test_key_error_diagnostic_renders_without_repr_quotes(self) -> None:
        a = std.Var(ANY, "a")
        b = std.Var(ANY, "b")
        with pytest.raises(KeyError) as exc_info:
            parse("a @ b", extra_vars={"a": a, "b": b})
        message = str(exc_info.value)
        assert message.startswith("error: No handler found")
        assert " --> <str>:1:1" in message

    def test_lambda_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="lambda"):
            parse("lambda x: x")

    def test_aug_assign_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="augmented"):
            parse("@std.func\ndef f(x: std.i32):\n  x += 1")

    def test_for_else_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="for/else"):
            parse("@std.func\ndef f():\n  for i in range(10):\n    pass\n  else:\n    pass")

    def test_while_else_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="while/else"):
            parse("@std.func\ndef f(x: std.i32):\n  while x < 10:\n    pass\n  else:\n    pass")

    def test_async_def_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="async functions"):
            parse("@std.func\nasync def f():\n  pass")

    def test_async_for_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="async for"):
            parse("@std.func\ndef f():\n  async for i in range(10):\n    pass")

    def test_async_with_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="async with"):
            parse("@std.func\ndef f():\n  async with std.scope():\n    pass")

    def test_ternary_expression_supported(self) -> None:
        _assert_parse_equal("1 if 1 else 2", std.IntImm(I64, 1))

    def test_walrus_unsupported(self) -> None:
        with pytest.raises(NotImplementedError):
            parse("(x := 1)")

    def test_comprehension_unsupported(self) -> None:
        with pytest.raises(NotImplementedError):
            parse("[i for i in range(10)]")

    def test_fstring_unsupported(self) -> None:
        with pytest.raises(NotImplementedError):
            parse('f"{1}"')

    def test_assert_with_message_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="assert messages"):
            parse('@std.func\ndef f():\n  assert 1 < 2, "bad"')

    def test_default_arg_unsupported(self) -> None:
        with pytest.raises(TypeError, match="default argument"):
            parse("@std.func\ndef f(x: std.i32 = 5):\n  pass")

    def test_starred_func_arg_unsupported(self) -> None:
        with pytest.raises(TypeError, match="must be identifiers"):
            parse("@std.func\ndef f(*args):\n  pass")

    def test_kw_func_arg_unsupported(self) -> None:
        with pytest.raises(TypeError, match="must be identifiers"):
            parse("@std.func\ndef f(**kwargs):\n  pass")

    def test_func_no_decorator(self) -> None:
        with pytest.raises(TypeError, match="exactly one decorator"):
            parse("def f():\n  pass")

    def test_func_multi_decorator(self) -> None:
        with pytest.raises(TypeError, match="exactly one decorator"):
            parse("@std.func\n@std.func\ndef f():\n  pass")

    def test_non_frame_decorator_fails(self) -> None:
        with pytest.raises(TypeError, match="expected parser frame"):
            parse("@std.IntImm\ndef f():\n  pass")

    def test_class_no_decorator(self) -> None:
        with pytest.raises(TypeError, match="exactly one decorator"):
            parse("class M:\n  pass")

    def test_class_with_bases_unsupported(self) -> None:
        with pytest.raises(TypeError, match="bases or keywords"):
            parse("@std.module\nclass M(Foo):\n  pass")

    def test_starred_assign_target_unsupported(self) -> None:
        with pytest.raises(TypeError, match="binding target"):
            parse("@std.func\ndef f():\n  *a, b = std.VarDef(std.i32, std.f32)")

    def test_chained_assign_unsupported(self) -> None:
        with pytest.raises(TypeError):
            parse("@std.func\ndef f():\n  x = y = 1")

    def test_multi_target_for_unsupported(self) -> None:
        with pytest.raises(TypeError):
            parse("@std.func\ndef f():\n  for i, j in range(10):\n    pass")

    def test_undefined_name_raises(self) -> None:
        with pytest.raises(NameError, match="not defined"):
            parse("foo + 1")

    def test_binop_promotes_mismatched_int_widths(self) -> None:
        a = std.Var(I32, "a")
        b = std.Var(I64, "b")
        _assert_parse_equal(
            "a + b",
            std.Add(std.Cast(I64, a), b, ty=I64),
            extra_vars={"a": a, "b": b},
        )

    def test_indexed_assign_no_rhs(self) -> None:
        x = std.Var(I32, "x")
        with pytest.raises(TypeError, match="indexed assignment"):
            parse("@std.func\ndef f(x: std.i32):\n  x[1]: std.i32")
        del x

    def test_unknown_generic_no_handler(self) -> None:
        a = std.Var(ANY, "a")
        b = std.Var(ANY, "b")
        with pytest.raises(KeyError, match="No handler found"):
            parse("a @ b", extra_vars={"a": a, "b": b})

    def test_string_at_top_level_is_docstring(self) -> None:
        # Standalone string literals are turned into pyast.DocString by the
        # AST translator; the parser doesn't know how to handle that.
        with pytest.raises(NotImplementedError, match="DocString"):
            parse('"hello"')

    def test_docstring_inside_function_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="DocString"):
            parse('@std.func\ndef f():\n  """docstring"""\n  pass')

    def test_try_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="No visit_Try"):
            parse("@std.func\ndef f():\n  try:\n    pass\n  except Exception:\n    pass")

    @pytest.mark.skipif(sys.version_info < (3, 10), reason="match syntax requires Python 3.10+")
    def test_match_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="No visit_Match"):
            parse("@std.func\ndef f(x: std.i32):\n  match x:\n    case 1:\n      pass")

    def test_starred_at_top_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="No visit_StarredExpr"):
            parse("*x")


################################################################################
# Architectural invariants
################################################################################


class TestParserArchitecture:
    def test_parser_reuses_language_module_globals(self) -> None:
        # The language module's `__ffi_globals__` are seeded into the
        # parser frame and resolve as ordinary identifiers.
        result = parse("min(1, 2)")
        assert _equal(result, std.IntImm(I64, 1))
        result = parse("max(1, 2)")
        assert _equal(result, std.IntImm(I64, 2))
        result = parse("@std.func\ndef f():\n  for i in range(10):\n    pass")
        assert isinstance(result.body[0], std.For)
