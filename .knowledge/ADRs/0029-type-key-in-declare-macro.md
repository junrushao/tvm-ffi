---
scope:
  - "0003-object-system"
---
# Embed Type Key in Object Declaration Macro

**TL;DR**: Object declaration macros now accept the type key as their first parameter and define `_type_key` internally, eliminating the separate `static constexpr const char* _type_key = "...";` line.

## Context

Previously, declaring an object type required two lines that could silently desynchronize:

```cpp
class FooObj : public Object {
  static constexpr const char* _type_key = "my.Foo";
  TVM_FFI_DECLARE_BASE_OBJECT_INFO(FooObj, Object);  // <-- doesn't know about _type_key
};
```

Copy-paste errors could cause `_type_key` to be wrong for the class, since the macro did not reference or validate it. Additionally, four separate `TVM_FFI_DEFINE_*_OBJECT_REF_METHODS` macros (nullable, not-nullable, mutable, mutable-not-nullable) created a 2x2 matrix that was nearly identical except for const-qualification.

## Alternatives

### 1. Embed type key in macro, unify mutable dispatch (chosen)

New macros: `TVM_FFI_DECLARE_OBJECT_INFO("key", T, P)` defines `_type_key` internally. Ref-method macros reduced to two (nullable/non-nullable) with mutability auto-derived from `_type_mutable`.

- Pros: Eliminates desync bugs. Reduces macro matrix from 2x2 to 1x2. The type key is always visible at the macro call site.
- Cons: Slightly less flexibility for types that compute `_type_key` dynamically (none exist today). Requires a `_PREDEFINED_TYPE_KEY` escape hatch for the `Object` base class.

### 2. Keep separate _type_key with static_assert validation

Add `static_assert` inside the macro to verify `_type_key` is defined.

- Pros: No API change, backward compatible.
- Cons: Does not prevent wrong values, only prevents missing declarations. Does not address the 2x2 macro matrix problem.

## Decision

Alternative 1. Macro naming convention: `TVM_FFI_DECLARE_OBJECT_INFO[_SUFFIX]` where suffix encodes the variant (`_STATIC`, `_FINAL`, `_PREDEFINED_TYPE_KEY`). The base macro `TVM_FFI_DECLARE_OBJECT_INFO` is the common case.

Mutability is now derived automatically: `std::conditional_t<ObjectName::_type_mutable, ObjectName*, const ObjectName*>`.

## Consequences

- Breaking change: all downstream `TVM_FFI_DECLARE_*_OBJECT_INFO` and `TVM_FFI_DEFINE_*_OBJECT_REF_METHODS` call sites must be updated.
- Old macro names no longer exist. `TVM_FFI_DEFINE_MUTABLE_OBJECT_REF_METHODS` and `TVM_FFI_DEFINE_MUTABLE_NOTNULLABLE_OBJECT_REF_METHODS` are removed.
- Types must correctly set `_type_mutable = true` on the Obj class (previously the explicit `MUTABLE` macro variant was the opt-in).

## Related Design Docs

- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- Object Declaration Macros section
- Commit: `.knowledge/commits/2025-09-09-a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806.md` + `a08fa6e`
