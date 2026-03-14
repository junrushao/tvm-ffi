---
scope:
  - "0002-any-system"
  - "0010-type-attr-columns"
---
# Customized AnyHash/AnyEqual via Object Type Attributes

**TL;DR**: Object types can register custom `__any_hash__` and `__any_equal__` functions via `TypeAttrColumn`, enabling domain-specific value-level hashing and equality for `Map<K,V>` and other `AnyHash`/`AnyEqual` consumers without modifying the core `Any` dispatch logic.

## Context

Before commit `39d9b2b` (#451), `AnyHash` and `AnyEqual` had a fixed dispatch table: strings/bytes used content comparison, all other types (including objects) used bitwise comparison of `type_index` + `v_int64` (which is pointer identity for objects). This meant two structurally identical objects at different addresses would hash differently and compare as unequal, preventing them from being used as `Map` keys based on value semantics.

Some domain types (e.g., IR nodes wrapping integers or floats) need value-based equality: two `TInt(42)` objects at different addresses should be considered equal when used as map keys or in deduplication contexts. The structural equality system (`StructuralEqual`/`StructuralHash`) provides deep comparison, but it lives in the "extra" tier and is too heavyweight for the hot-path `AnyHash`/`AnyEqual` used by `Map`.

Usecases:
- IR integer/float wrapper types used as `Map` keys need value-based hashing and equality.
- Custom string-like or symbol types that wrap non-standard representations need content-based comparison at the `Any` level.
- Any object type that participates as a key in `Map<K,V>` and needs value semantics rather than identity semantics.

Design Decisions:
- **`TypeAttrColumn`-based registration**: Custom hash/equal functions are registered as `__any_hash__` and `__any_equal__` type attributes via `TypeAttrDef<T>`. This reuses the existing extensible attribute system rather than adding new fields to `TVMFFITypeMetadata` or new enum values.
- **Dual dispatch path** (opaque pointer vs FFI Function): The custom function stored in the column can be either a raw C++ function pointer (stored as `kTVMFFIOpaquePtr`, zero FFI overhead) or an FFI `Function` object (cross-language callable). The opaque-pointer path is preferred for performance-critical types.
- **Checked at the `AnyHash`/`AnyEqual` level**: The column lookup happens inside `AnyHash::operator()` and `AnyEqual::operator()`, gated by `type_index >= kTVMFFIStaticObjectBegin` (only for objects, not POD types). The column pointer is `static`-cached per function, so the `TVMFFIGetTypeAttrColumn` call happens at most once.
- **Pre-created columns**: `EnsureTypeAttrColumn("__any_hash__")` and `EnsureTypeAttrColumn("__any_equal__")` are called during container module initialization (in `src/ffi/container.cc`), guaranteeing the columns exist before any type registration.

**Alternatives considered**:

1. **Virtual method on Object**: Requires vtable changes, breaks C ABI, and would add overhead to all objects regardless of whether they use custom hashing.
2. **New `TVMFFISEqHashKind` enum value for AnyHash/AnyEqual**: Couples value-level hash/equal to the structural equality system. The two concerns are orthogonal: `AnyHash`/`AnyEqual` operate on `Any` values (including non-objects), while `StructuralEqual`/`StructuralHash` operate on object graphs.
3. **Hardcoded switch on type_index in AnyHash/AnyEqual**: Does not scale. Every new type with custom hash semantics would require modifying the core `any.h` header.
4. **Specialization via TypeTraits**: `AnyHash`/`AnyEqual` operate on type-erased `Any`, not on typed values. `TypeTraits` specialization would require re-erasing the type after dispatch, adding complexity.

**Consequences**:
- `Map<K,V>` with object keys now supports value-based equality when the key type registers `__any_hash__`/`__any_equal__`.
- The `AnyHash::operator()` and `AnyEqual::operator()` gain a branch for object types (after the string/bytes check). This adds one static pointer check per call for objects, which is negligible.
- Types registering `__any_hash__` without `__any_equal__` (or vice versa) will silently produce incorrect behavior in `Map`. There is no compile-time or runtime enforcement that both must be registered together.
- The opaque-pointer fast path bypasses the FFI safe-call boundary. If the custom function throws a C++ exception, it will propagate uncaught. This is acceptable because custom hash/equal functions are expected to be lightweight and non-throwing.

**Rollback**: Removing the feature requires reverting the `AnyHash`/`AnyEqual` changes in `any.h` and removing the `EnsureTypeAttrColumn` calls. Registered type attributes would become inert (unused columns).

## Implementation Notes

- `AnyHash` and `AnyEqual` are modified in `include/tvm/ffi/any.h`.
- `GetAnyHashTypeAttrColumn()` and `GetAnyEqualTypeAttrColumn()` are `static` member functions that cache the column pointer on first call.
- `CallCustomAnyHash` and `CallCustomAnyEqual` are `static` member functions with dual dispatch: `kTVMFFIOpaquePtr` for raw function pointers, `kTVMFFIFunction` for FFI functions.
- Registration example (raw pointer, fast path):
  ```cpp
  TypeAttrDef<TIntObj>()
    .attr("__any_hash__", reinterpret_cast<void*>(&TInt::CustomAnyHash))
    .attr("__any_equal__", reinterpret_cast<void*>(&TInt::CustomAnyEqual));
  ```
- Registration example (FFI Function, cross-language):
  ```cpp
  TypeAttrDef<TFloatObj>()
    .def("__any_hash__", &TFloat::CustomAnyHash)
    .def("__any_equal__", &TFloat::CustomAnyEqual);
  ```
- Note: `TVM_FFI_ICHECK_NOTNULL` and `TVM_FFI_ICHECK_EQ` macros (from `error.h`, moved from `function_details.h`) are used for internal consistency checks within the custom call dispatch. These were relocated as part of this commit to avoid a circular dependency on `function.h`.
- Evidence: `.knowledge/commits/2026-02-15-39d9b2b400646be720e98f001353cc0d8d4b0234.md` + `39d9b2b`

## Related Design Docs

- [`.knowledge/designs/0002-any-system.md`](../designs/0002-any-system.md) -- AnyHash/AnyEqual design
- [`.knowledge/designs/0010-type-attr-columns.md`](../designs/0010-type-attr-columns.md) -- TypeAttrColumn system
- [`.knowledge/designs/0009-structural-equal-hash.md`](../designs/0009-structural-equal-hash.md) -- Structural equal/hash (related but distinct from value-level AnyHash/AnyEqual)
