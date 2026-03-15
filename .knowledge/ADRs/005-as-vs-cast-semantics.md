---
scope:
  - ".knowledge/designs/any-system.md"
  - ".knowledge/designs/type-traits.md"
---
# ADR-005: Strict `as` vs Conversion `cast`/`try_cast` Semantics

**TL;DR**: Split the single `as<T>()` method into strict-only `as<T>()` (no conversion) and conversion-enabled `cast<T>()`/`try_cast<T>()`, making the common type-checking path cheaper and preventing accidental implicit conversions.

## Context
In the initial design (7d34eb8), `as<T>()` performed type conversion (e.g., `AnyView(1).as<double>()` returned `42.0` via int-to-float coercion). This had two problems:

Usecases:
- Containers (`Array<T>`) call `as<T>()` on every element to verify type invariants. With conversion semantics, each call attempted coercion even when only a strict match was needed -- wasted work.
- Pattern-matching code (e.g., checking if a value is exactly an `int64_t` vs a `double`) could not distinguish strict identity from coerced equivalence.

Design Decisions:
- `as<T>()` is redefined as strict-only: calls `TypeTraits<T>::CheckAnyStrict` + `CopyFromAnyViewAfterCheck`. Returns `nullopt` on type mismatch without attempting conversion.
- `cast<T>()` throws `TypeError` on failure, performing conversion via `TypeTraits<T>::TryCastFromAnyView`.
- `try_cast<T>()` returns `optional<T>`, performing the same conversion without throwing.
- `Any::as<T>() &&` (rvalue overload) enables move-based extraction on strict match.
- TypeTraits protocol methods renamed to match: `CheckAnyStorage` -> `CheckAnyStrict`, `CopyFromAnyStorageAfterCheck` -> `CopyFromAnyViewAfterCheck`, `MoveFromAnyStorageAfterCheck` -> `MoveFromAnyAfterCheck`, `TryConvertFromAnyView` -> `TryCastFromAnyView`.

## Alternatives

### A: Keep single `as<T>()` with conversion semantics
- Description: `as<T>()` continues to attempt type coercion on every call, matching the v1 behavior.
- Pros: Simpler API surface (one method instead of three).
- Cons: Container type checking is unnecessarily expensive (conversion attempt on every element); cannot express "is this exactly type T?" without accessing raw type_index; naming is misleading (`as` conventionally implies reinterpret, not convert in C++).
- Why rejected: The cost of conversion on every container element check was measured as significant in tight loops. The naming also caused confusion -- developers expected `as` to be a strict check.

### B: Use `get<T>()` for strict and `convert<T>()` for lenient
- Description: Introduce new method names rather than repurposing `as`/`cast`.
- Pros: Completely unambiguous naming; no existing code needs to understand the naming convention change.
- Cons: Diverges from the `as`/`cast` naming convention common in C++ (`static_cast`, `dynamic_cast`, `std::any::any_cast`) and other FFI systems; doubles the vocabulary that users must learn.
- Why rejected: The `as` = reinterpret, `cast` = convert convention is well-established in the C++ ecosystem. Introducing novel names would increase cognitive load without improving expressiveness.

## Implementation Notes
- `as<T>()` calls `TypeTraits<T>::CheckAnyStrict(&data_)` -- a single type_index comparison for POD types.
- `cast<T>()` first tries the fast path (`CheckAnyStrict` + `MoveFromAnyAfterCheck`) before falling back to `TryCastFromAnyView`.
- `ArgValueWithContext::operator T()` in function_details.h uses `try_cast<T>()` (not `as<T>()`) because packed function argument dispatch needs type conversion.
- `ffi.Shape` construction uses `try_cast<int64_t>()` to accept both int and bool inputs.

## Related Design Docs
- `.knowledge/designs/any-system.md` -- `as`/`cast`/`try_cast` API documentation
- `.knowledge/designs/type-traits.md` -- `CheckAnyStrict`/`TryCastFromAnyView` protocol
