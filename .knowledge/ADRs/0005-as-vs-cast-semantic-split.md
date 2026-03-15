---
scope:
  - "0002-any-value-system"
  - "0005-type-traits"
---
# Separate strict as() from coercing cast()/try_cast()

**TL;DR**: The decision to split `Any`/`AnyView` value extraction into three methods: `as<T>()` (strict, no coercion), `try_cast<T>()` (coercing, returns optional), and `cast<T>()` (coercing, throws on failure).

## Context
- Before this change, `as<T>()` called `TryCastFromAnyView` (coercing), meaning `AnyView(1).as<double>()` would succeed by implicitly converting int to double.
- This was problematic for container invariant checking: `Array<int>` needs to verify that stored elements are exactly `int` (not coercible-to-int values like `bool`). The `CheckAnyStrict` method provides exact-match semantics, but the primary user-facing API `as<T>()` was coercing.
- The confusion between "strict check" and "coercing conversion" made it easy to introduce subtle bugs when writing container code or type validation logic.

Usecases:
- Container type invariants: `Array<T>` uses strict checking to ensure all elements exactly match type `T`. Using `as<T>()` (now strict) aligns the user-facing API with the container invariant.
- Function argument conversion: Packed function arguments benefit from coercion (passing `int` where `double` is expected). `cast<T>()` (coercing) serves this use case.
- Optional value extraction: When you want to check if a value is a specific type without exceptions, `as<T>()` (strict) and `try_cast<T>()` (coercing) return `optional`.

Design Decisions:
- **`as<T>()` = strict**: Uses `CheckAnyStrict` + `CopyFromAnyViewAfterCheck`. Returns `nullopt` for type mismatches, even when coercion would succeed. This matches the semantics of "view this value AS type T" (identity, not conversion).
- **`try_cast<T>()` = coercing**: Uses `TryCastFromAnyView`. Returns `nullopt` only when conversion is truly impossible. This is the "CAST this value TO type T" semantic.
- **`cast<T>()` = coercing + throw**: Same as `try_cast` but throws `TypeError` instead of returning `nullopt`. Primary API for function argument unpacking.
- **TypeTraits method renames**: `CheckAnyStorage` -> `CheckAnyStrict`, `CopyFromAnyStorageAfterCheck` -> `CopyFromAnyViewAfterCheck`, `MoveFromAnyStorageAfterCheck` -> `MoveFromAnyAfterCheck`, `TryConvertFromAnyView` -> `TryCastFromAnyView`. The new names reflect the strict/cast distinction.

## Implementation Notes
- `as<T>()` on `Any` also has an rvalue-ref overload `as() &&` that moves from the storage after the strict check.
- `ArgValueWithContext` (used in packed function argument conversion) switched from `as<T>()` to `try_cast<T>()` to preserve the coercing behavior needed for function arguments.
- All built-in TypeTraits specializations (int, bool, float, ObjectRef, etc.) were updated with the renamed method names.
- **Downcast removed from FFI** (commit `4be1af7`): All four `Downcast` template overloads have been removed from `tvm/ffi/cast.h`. After this change, `cast.h` contains only `GetRef<RefType>(const ObjectType*)` and `GetObjectPtr<BaseType>(ObjectType*)`. The `Downcast<T>(Any)` overloads were redundant wrappers around `Any::cast<T>()`. The `ObjectRef`-to-`ObjectRef` overload was relocated outside FFI (to `node/`). `using ffi::GetObjectPtr` was added to the `tvm` namespace (previously missing).

## Related Design Docs
- [0002-any-value-system.md](.knowledge/designs/0002-any-value-system.md)
- [0005-type-traits.md](.knowledge/designs/0005-type-traits.md)
- [0008-containers.md](.knowledge/designs/0008-containers.md) — container element invariant uses `CheckAnyStrict`
