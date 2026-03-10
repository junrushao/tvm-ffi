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
"""Tests for Python-defined TVM-FFI types: ``@py_class`` decorator and low-level Field API."""

# ruff: noqa: D102, PLR0124, PLW1641
from __future__ import annotations

import copy
import inspect
import itertools
import sys
from typing import ClassVar

import pytest
from tvm_ffi import core
from tvm_ffi.core import Object, TypeInfo
from tvm_ffi.dataclasses import KW_ONLY, Field, field, py_class
from tvm_ffi.registry import _add_class_attrs, _install_dataclass_dunders

_needs_310 = pytest.mark.skipif(sys.version_info < (3, 10), reason="X | Y syntax requires 3.10+")

# ---------------------------------------------------------------------------
# Unique type key generator (avoids collisions across tests)
# ---------------------------------------------------------------------------
_counter = itertools.count()


def _unique_key(base: str) -> str:
    return f"testing.py_class_dec.{base}_{next(_counter)}"


def _get_type_info(cls: type) -> TypeInfo:
    ret = cls.__tvm_ffi_type_info__  # ty: ignore[unresolved-attribute]
    assert isinstance(ret, TypeInfo), f"Expected TypeInfo, got {type(ret)}"
    return ret


# ---------------------------------------------------------------------------
# Low-level helpers for _make_type-based tests
# ---------------------------------------------------------------------------
_counter_ff = itertools.count()


def _unique_key_ff(base: str) -> str:
    """Return a globally unique type key for low-level field tests."""
    return f"testing.py_class.{base}_{next(_counter_ff)}"


def _make_type(
    name: str,
    fields: list[Field],
    *,
    parent: type = core.Object,
    eq: bool = False,
    unsafe_hash: bool = False,
    repr: bool = True,
) -> type:
    """Create, register, and fully set up a Python-defined TVM-FFI type.

    Returns the ready-to-use Python class.
    """
    type_key = _unique_key_ff(name)
    parent_info = core._type_cls_to_type_info(parent)
    assert parent_info is not None
    cls = type(name, (parent,), {"__slots__": ()})
    info = core._register_py_class(parent_info, type_key, cls)
    info._register_fields(fields)
    setattr(cls, "__tvm_ffi_type_info__", info)
    _add_class_attrs(cls, info)
    _install_dataclass_dunders(
        cls,
        init=True,
        repr=repr,
        eq=eq,
        order=False,
        unsafe_hash=unsafe_hash,
    )
    return cls


# ###########################################################################
#  1. Basic registration
# ###########################################################################
class TestBasicRegistration:
    """@py_class decorator with different calling conventions."""

    def test_bare_decorator(self) -> None:
        @py_class(_unique_key("Bare"))
        class Bare(Object):
            x: int

        info = _get_type_info(Bare)
        assert info is not None
        assert len(info.fields) == 1
        assert info.fields[0].name == "x"

    def test_decorator_with_options(self) -> None:
        @py_class(_unique_key("Opts"), eq=True)
        class Opts(Object):
            x: int

        assert hasattr(Opts, "__eq__")
        assert Opts(x=1) == Opts(x=1)

    def test_auto_type_key(self) -> None:
        @py_class(_unique_key("AutoKey"))
        class AutoKey(Object):
            x: int

        info = _get_type_info(AutoKey)
        assert info.type_key.startswith("testing.")

    def test_explicit_type_key(self) -> None:
        key = _unique_key("ExplicitKey")

        @py_class(key)
        class ExplicitKey(Object):
            x: int

        assert _get_type_info(ExplicitKey).type_key == key

    def test_empty_class(self) -> None:
        @py_class(_unique_key("Empty"))
        class Empty(Object):
            pass

        obj = Empty()
        assert obj is not None

    def test_isinstance_check(self) -> None:
        @py_class(_unique_key("InstCheck"))
        class InstCheck(Object):
            x: int

        obj = InstCheck(x=42)
        assert isinstance(obj, InstCheck)
        assert isinstance(obj, Object)


# ###########################################################################
#  2. Field parsing
# ###########################################################################
class TestFieldParsing:
    """Annotation-to-Field conversion."""

    def test_int_field(self) -> None:
        @py_class(_unique_key("IntFld"))
        class IntFld(Object):
            x: int

        obj = IntFld(x=42)
        assert obj.x == 42

    def test_float_field(self) -> None:
        @py_class(_unique_key("FltFld"))
        class FltFld(Object):
            x: float

        obj = FltFld(x=3.14)
        assert abs(obj.x - 3.14) < 1e-10

    def test_str_field(self) -> None:
        @py_class(_unique_key("StrFld"))
        class StrFld(Object):
            x: str

        obj = StrFld(x="hello")
        assert obj.x == "hello"

    def test_bool_field(self) -> None:
        @py_class(_unique_key("BoolFld"))
        class BoolFld(Object):
            x: bool

        obj = BoolFld(x=True)
        assert obj.x is True

    @_needs_310
    def test_optional_field(self) -> None:
        @py_class(_unique_key("OptFld"))
        class OptFld(Object):
            x: int | None

        obj = OptFld(x=42)
        assert obj.x == 42
        obj2 = OptFld(x=None)
        assert obj2.x is None

    def test_multiple_fields(self) -> None:
        @py_class(_unique_key("Multi"))
        class Multi(Object):
            a: int
            b: float
            c: str

        obj = Multi(a=1, b=2.0, c="three")
        assert obj.a == 1
        assert obj.b == 2.0
        assert obj.c == "three"


# ###########################################################################
#  3. Defaults
# ###########################################################################
class TestDefaults:
    """Default values and default_factory."""

    def test_bare_default(self) -> None:
        @py_class(_unique_key("BareDef"))
        class BareDef(Object):
            x: int
            y: int = 10

        obj = BareDef(x=1)
        assert obj.y == 10

    def test_field_default(self) -> None:
        @py_class(_unique_key("FldDef"))
        class FldDef(Object):
            x: int = field(default=42)

        obj = FldDef()
        assert obj.x == 42

    def test_field_default_factory(self) -> None:
        call_count = 0

        def make_default() -> int:
            nonlocal call_count
            call_count += 1
            return 99

        @py_class(_unique_key("FldFact"))
        class FldFact(Object):
            x: int = field(default_factory=make_default)

        obj1 = FldFact()
        assert obj1.x == 99
        obj2 = FldFact()
        assert obj2.x == 99
        assert call_count == 2

    def test_default_and_factory_mutually_exclusive(self) -> None:
        with pytest.raises(ValueError, match="cannot specify both"):
            field(default=1, default_factory=int)

    def test_non_callable_factory_rejected(self) -> None:
        with pytest.raises(TypeError, match="default_factory must be a callable"):
            field(default_factory=42)  # ty: ignore[invalid-argument-type]

    def test_required_before_optional(self) -> None:
        @py_class(_unique_key("ReqOpt"))
        class ReqOpt(Object):
            a: int
            b: int = 10

        obj = ReqOpt(1)
        assert obj.a == 1
        assert obj.b == 10


# ###########################################################################
#  4. KW_ONLY
# ###########################################################################
class TestKwOnly:
    """Keyword-only field support."""

    def test_kw_only_sentinel(self) -> None:
        @py_class(_unique_key("KWSent"))
        class KWSent(Object):
            a: int
            _: KW_ONLY
            b: int = 10

        obj = KWSent(1, b=20)  # ty: ignore[missing-argument]
        assert obj.a == 1
        assert obj.b == 20
        with pytest.raises(TypeError):
            KWSent(1, 2)  # ty: ignore[invalid-argument-type]

    def test_decorator_level_kw_only(self) -> None:
        @py_class(_unique_key("DecKW"), kw_only=True)
        class DecKW(Object):
            a: int
            b: int = 10

        obj = DecKW(a=1)
        assert obj.a == 1
        assert obj.b == 10
        with pytest.raises(TypeError):
            DecKW(1)  # ty: ignore[missing-argument,too-many-positional-arguments]

    def test_field_level_kw_only_override(self) -> None:
        @py_class(_unique_key("FldKW"))
        class FldKW(Object):
            a: int
            b: int = field(default=10, kw_only=True)

        obj = FldKW(1)
        assert obj.a == 1
        assert obj.b == 10
        with pytest.raises(TypeError):
            FldKW(1, 2)  # b is keyword-only


# ###########################################################################
#  5. ClassVar
# ###########################################################################
class TestClassVar:
    """ClassVar annotations are skipped."""

    def test_classvar_skipped(self) -> None:
        @py_class(_unique_key("CV"))
        class CV(Object):
            x: int
            count: ClassVar[int] = 0

        info = _get_type_info(CV)
        field_names = [f.name for f in info.fields]
        assert "x" in field_names
        assert "count" not in field_names

    def test_classvar_preserved_on_class(self) -> None:
        @py_class(_unique_key("CVPres"))
        class CVPres(Object):
            x: int
            tag: ClassVar[str] = "hello"

        assert CVPres.tag == "hello"


# ###########################################################################
#  6. Init generation
# ###########################################################################
class TestInit:
    """Auto-generated __init__."""

    def test_positional_args(self) -> None:
        @py_class(_unique_key("Pos"))
        class Pos(Object):
            a: int
            b: str

        obj = Pos(1, "hello")
        assert obj.a == 1
        assert obj.b == "hello"

    def test_keyword_args(self) -> None:
        @py_class(_unique_key("Kw"))
        class Kw(Object):
            a: int
            b: str

        obj = Kw(a=1, b="hello")
        assert obj.a == 1
        assert obj.b == "hello"

    def test_init_false_field(self) -> None:
        @py_class(_unique_key("NoInit"))
        class NoInit(Object):
            a: int
            b: int = field(default=99, init=False)

        obj = NoInit(a=1)
        assert obj.a == 1
        assert obj.b == 99

    def test_user_defined_init_preserved(self) -> None:
        @py_class(_unique_key("UserInit"), init=False)
        class UserInit(Object):
            a: int

            def __init__(self, val: int) -> None:
                self.__ffi_init__(val)

        obj = UserInit(42)
        assert obj.a == 42

    def test_required_after_optional_reordered(self) -> None:
        """Required positional fields are reordered before optional ones in __init__."""

        @py_class(_unique_key("ReorderOwn"))
        class ReorderOwn(Object):
            x: int = 0
            y: int  # ty: ignore[dataclass-field-order]

        sig = inspect.signature(ReorderOwn.__init__)
        param_names = [n for n in sig.parameters if n != "self"]
        assert param_names[0] == "y"  # required comes first
        assert param_names[1] == "x"  # optional comes second

        obj = ReorderOwn(y=1)  # ty: ignore[missing-argument]
        assert obj.x == 0
        assert obj.y == 1

    def test_required_after_optional_in_parent(self) -> None:
        """Child required fields are reordered before parent optional fields."""

        @py_class(_unique_key("OptParent"))
        class OptParent(Object):
            x: int
            y: int = 0

        @py_class(_unique_key("ReqChild"))
        class ReqChild(OptParent):
            z: int

        sig = inspect.signature(ReqChild.__init__)
        param_names = [n for n in sig.parameters if n != "self"]
        # required (x, z) before optional (y)
        assert param_names == ["x", "z", "y"]

        obj = ReqChild(x=1, z=3)
        assert obj.x == 1
        assert obj.y == 0
        assert obj.z == 3

    def test_kw_only_exempt_from_reorder(self) -> None:
        """kw_only fields are not reordered with positional fields."""

        @py_class(_unique_key("KwReorder"))
        class KwReorder(Object):
            x: int = 0
            _: KW_ONLY  # ty: ignore[dataclass-field-order]
            y: int  # ty: ignore[dataclass-field-order]

        sig = inspect.signature(KwReorder.__init__)
        params = sig.parameters
        assert params["x"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert params["y"].kind == inspect.Parameter.KEYWORD_ONLY

        obj = KwReorder(y=1)  # ty: ignore[missing-argument]
        assert obj.x == 0
        assert obj.y == 1

    def test_mixed_positional_and_kw_only_with_defaults(self) -> None:
        """Mixed positional/kw_only fields with defaults produce correct signature."""

        @py_class(_unique_key("MixedSig"))
        class MixedSig(Object):
            a: int = 0
            b: int  # ty: ignore[dataclass-field-order]
            _: KW_ONLY  # ty: ignore[dataclass-field-order]
            c: int = 10
            d: int  # ty: ignore[dataclass-field-order]

        sig = inspect.signature(MixedSig.__init__)
        param_names = [n for n in sig.parameters if n != "self"]
        # positional: b (required) before a (optional); kw_only: d (required) before c (optional)
        assert param_names == ["b", "a", "d", "c"]

        obj = MixedSig(b=2, d=4)  # ty: ignore[missing-argument]
        assert obj.a == 0
        assert obj.b == 2
        assert obj.c == 10
        assert obj.d == 4

    def test_init_false_excluded_from_signature(self) -> None:
        """init=False fields do not appear in __init__ signature."""

        @py_class(_unique_key("InitFalseSig"))
        class InitFalseSig(Object):
            a: int
            b: int = field(default=99, init=False)
            c: str

        sig = inspect.signature(InitFalseSig.__init__)
        param_names = [n for n in sig.parameters if n != "self"]
        assert "b" not in param_names
        assert "a" in param_names
        assert "c" in param_names


# ###########################################################################
#  7. __post_init__
# ###########################################################################
class TestPostInit:
    """__post_init__ support."""

    def test_post_init_called(self) -> None:
        post_init_called = False

        @py_class(_unique_key("PostInit"))
        class PostInit(Object):
            x: int

            def __post_init__(self) -> None:
                nonlocal post_init_called
                post_init_called = True

        PostInit(x=1)
        assert post_init_called

    def test_post_init_sees_field_values(self) -> None:
        @py_class(_unique_key("PostInitVal"))
        class PostInitVal(Object):
            x: int
            y: int = 10

            def __post_init__(self) -> None:
                # Fields should be set before __post_init__ is called
                assert self.x is not None
                assert self.y == 10

        PostInitVal(x=5)


# ###########################################################################
#  8. Repr
# ###########################################################################
class TestRepr:
    """__repr__ generation."""

    def test_repr_generated(self) -> None:
        @py_class(_unique_key("Repr"))
        class Repr(Object):
            x: int
            y: str

        obj = Repr(x=1, y="hello")
        r = repr(obj)
        assert "1" in r
        assert "hello" in r

    def test_repr_disabled(self) -> None:
        @py_class(_unique_key("NoRepr"), repr=False)
        class NoRepr(Object):
            x: int

        obj = NoRepr(x=1)
        # Should use default object repr
        r = repr(obj)
        assert "NoRepr" in r or "object at" in r


# ###########################################################################
#  9. Equality
# ###########################################################################
class TestEquality:
    """__eq__ and __ne__ generation."""

    def test_eq_enabled(self) -> None:
        @py_class(_unique_key("Eq"), eq=True)
        class Eq(Object):
            x: int
            y: str

        assert Eq(x=1, y="a") == Eq(x=1, y="a")
        assert Eq(x=1, y="a") != Eq(x=2, y="a")

    def test_eq_disabled_by_default(self) -> None:
        @py_class(_unique_key("NoEq"))
        class NoEq(Object):
            x: int

        a = NoEq(x=1)
        b = NoEq(x=1)
        # Without eq, identity comparison
        assert a != b
        assert a == a


# ###########################################################################
# 10. Order
# ###########################################################################
class TestOrder:
    """Comparison methods."""

    def test_order_enabled(self) -> None:
        @py_class(_unique_key("Ord"), eq=True, order=True)
        class Ord(Object):
            x: int

        assert Ord(x=1) < Ord(x=2)
        assert Ord(x=2) > Ord(x=1)
        assert Ord(x=1) <= Ord(x=1)
        assert Ord(x=1) >= Ord(x=1)


# ###########################################################################
# 11. Hash
# ###########################################################################
class TestHash:
    """__hash__ generation."""

    def test_unsafe_hash(self) -> None:
        @py_class(_unique_key("Hash"), eq=True, unsafe_hash=True)
        class Hash(Object):
            x: int

        a = Hash(x=1)
        b = Hash(x=1)
        assert hash(a) == hash(b)
        # Can be used in sets
        s = {a, b}
        assert len(s) == 1


# ###########################################################################
# 12. Copy
# ###########################################################################
class TestCopy:
    """__copy__, __deepcopy__, __replace__."""

    def test_shallow_copy(self) -> None:
        @py_class(_unique_key("SCopy"))
        class SCopy(Object):
            x: int

        obj = SCopy(x=42)
        obj2 = copy.copy(obj)
        assert obj2.x == 42

    def test_deep_copy(self) -> None:
        @py_class(_unique_key("DCopy"))
        class DCopy(Object):
            x: int

        obj = DCopy(x=42)
        obj2 = copy.deepcopy(obj)
        assert obj2.x == 42

    def test_replace(self) -> None:
        @py_class(_unique_key("Repl"))
        class Repl(Object):
            x: int
            y: str

        obj = Repl(x=1, y="a")
        obj2 = obj.__replace__(x=2)  # ty: ignore[unresolved-attribute]
        assert obj2.x == 2
        assert obj2.y == "a"


# ###########################################################################
# 13. Inheritance
# ###########################################################################
class TestInheritance:
    """Inheritance between py_class types."""

    def test_child_adds_fields(self) -> None:
        @py_class(_unique_key("Parent"))
        class Parent(Object):
            x: int

        @py_class(_unique_key("Child"))
        class Child(Parent):
            y: str

        obj = Child(x=1, y="hello")
        assert obj.x == 1
        assert obj.y == "hello"

    def test_child_isinstance(self) -> None:
        @py_class(_unique_key("P2"))
        class P2(Object):
            x: int

        @py_class(_unique_key("C2"))
        class C2(P2):
            y: str

        obj = C2(x=1, y="hello")
        assert isinstance(obj, C2)
        assert isinstance(obj, P2)
        assert isinstance(obj, Object)

    def test_three_level_inheritance(self) -> None:
        @py_class(_unique_key("L1"))
        class L1(Object):
            a: int

        @py_class(_unique_key("L2"))
        class L2(L1):
            b: int

        @py_class(_unique_key("L3"))
        class L3(L2):
            c: int

        obj = L3(a=1, b=2, c=3)
        assert obj.a == 1
        assert obj.b == 2
        assert obj.c == 3


# ###########################################################################
# 14. Forward references / deferred resolution
# ###########################################################################
class TestForwardReferences:
    """Deferred annotation resolution for mutual and self-references."""

    @_needs_310
    def test_self_reference(self) -> None:
        @py_class(_unique_key("SelfRef"))
        class SelfRef(Object):
            value: int
            next_node: SelfRef | None

        leaf = SelfRef(value=2, next_node=None)
        head = SelfRef(value=1, next_node=leaf)
        assert head.next_node is not None
        assert head.next_node.value == 2

    @_needs_310
    def test_mutual_reference(self) -> None:
        """Two classes that reference each other."""

        @py_class(_unique_key("Foo"))
        class Foo(Object):
            value: int
            bar: Bar | None

        @py_class(_unique_key("Bar"))
        class Bar(Object):
            value: int
            foo: Foo | None

        bar = Bar(value=2, foo=None)
        foo = Foo(value=1, bar=bar)
        assert foo.bar is not None
        assert foo.bar.value == 2

    @_needs_310
    def test_deferred_resolution_on_instantiation(self) -> None:
        """Forward ref resolved on first instantiation."""

        @py_class(_unique_key("Early"))
        class Early(Object):
            value: int
            ref: Late | None

        # At this point, Early's fields are deferred because Late doesn't exist

        @py_class(_unique_key("Late"))
        class Late(Object):
            value: int

        # Now Early should resolve (either via flush or on instantiation)
        obj = Early(value=1, ref=Late(value=2))
        assert obj.ref is not None
        assert obj.ref.value == 2


# ###########################################################################
# 15. User-defined dunder preservation
# ###########################################################################
class TestDunderPreservation:
    """User-defined dunders are not overwritten."""

    def test_user_repr_preserved(self) -> None:
        @py_class(_unique_key("UserRepr"))
        class UserRepr(Object):
            x: int

            def __repr__(self) -> str:
                return f"Custom({self.x})"

        obj = UserRepr(x=42)
        assert repr(obj) == "Custom(42)"

    def test_user_eq_preserved(self) -> None:
        @py_class(_unique_key("UserEq"), eq=True)
        class UserEq(Object):
            x: int

            def __eq__(self, other: object) -> bool:
                return False

        assert not (UserEq(x=1) == UserEq(x=1))
