---
scope:
  - "0002-any-system"
  - "0005-containers"
---
# Split as() (Strict) from cast()/try_cast() (Lenient)

**TL;DR**: `as<T>()` performs strict, non-converting type checks (via `CheckAnyStrict`), while `cast<T>()`/`try_cast<T>()` perform lenient type conversion (via `TryCastFromAnyView`). Previously both methods called `TryConvertFromAnyView`, making them behaviorally identical.

## Context

Before this change, `AnyView::as<T>()` and `AnyView::cast<T>()` both called `TryConvertFromAnyView`, making `as()` a confusing synonym for `cast()` that returned `optional` instead of throwing. This caused problems:

- `Variant<int, float>` where `as<float>()` would match an int-holding variant via int->float conversion, violating the expectation of strict type checking.
- Container element validation used `CheckAnyStorage` (strict) internally, but user-facing `as()` used conversion (lenient), creating an inconsistency.

Usecases:
- `Variant<int, float>::as<float>()` should return `nullopt` when the variant holds an `int`, not silently convert.
- `Array<float>` element validation (strict) should be consistent with user-facing `as<float>()`.
- Function argument unpacking should use lenient conversion (`try_cast`), since `int` arguments to `float` parameters should succeed.

Design Decisions:
- **Three-method API**: `as<T>()` (strict, returns `optional`), `try_cast<T>()` (lenient, returns `optional`), `cast<T>()` (lenient, throws on failure).
- **TypeTraits method renames**: `CheckAnyStorage` -> `CheckAnyStrict`, `CopyFromAnyStorageAfterCheck` -> `CopyFromAnyViewAfterCheck`, `MoveFromAnyStorageAfterCheck` -> `MoveFromAnyAfterCheck`, `TryConvertFromAnyView` -> `TryCastFromAnyView`.
- **Function arg unpacking uses try_cast**: `ArgValueWithContext::operator T()` calls `try_cast<T>()` for lenient argument conversion.

**Alternatives considered**:

1. **Single method with boolean `strict` parameter**: Rejected for ergonomic reasons -- `as<T>(true)` vs `as<T>(false)` is less readable than `as<T>()` vs `try_cast<T>()`.
2. **Name the strict method `exact<T>()` or `get<T>()`**: Rejected for consistency with C++ standard library naming.
3. **Keep single method**: Rejected because conflating strict and lenient causes bugs in Variant and container code.

**Consequences**:
- Breaking API change: existing callers using `as<T>()` for converting access must migrate to `try_cast<T>()`.
- Breaking TypeTraits protocol: all five renamed methods must be updated in out-of-tree specializations.
- Clear semantic contract: `as` = strict, `try_cast`/`cast` = lenient. No ambiguity.

## Implementation Notes

- `AnyView::as<T>()` calls `CheckAnyStrict` + `CopyFromAnyViewAfterCheck`.
- `AnyView::try_cast<T>()` calls `TryCastFromAnyView` (which internally tries `CheckAnyStrict` first as a fast path).
- `Any::as<T>() &&` (rvalue) calls `CheckAnyStrict` + `MoveFromAnyAfterCheck`.
- Evidence: `include/tvm/ffi/any.h`, `include/tvm/ffi/type_traits.h`, commit `37a2e7c`.

## Related Design Docs

- [`.knowledge/designs/0002-any-system.md`](../designs/0002-any-system.md) -- TypeTraits protocol and Any access methods
- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- Container storage invariant uses CheckAnyStrict
