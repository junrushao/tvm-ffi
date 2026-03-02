---
adr: "0005"
title: "Split as() (Strict Check) from cast()/try_cast() (Converting) in Any/AnyView"
status: "accepted"
date: "2025-05-14"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "type-system"
  - "api-design"
source_commits:
  - "37a2e7c521435cbe2bd772480f0389c18bd9ce2c"
source_ledgers:
  - ".memory/commits/2025-05-14-37a2e7c521435cbe2bd772480f0389c18bd9ce2c.md"
---

# ADR-0005: Split as() (Strict Check) from cast()/try_cast() (Converting) in Any/AnyView

## TL;DR
- The previous `as<T>()` method on `Any`/`AnyView` conflated two distinct operations: strict type checking and type conversion. This ADR splits them into `as<T>()` (strict, no conversion) and `cast<T>()`/`try_cast<T>()` (with conversion), along with a corresponding rename of the `TypeTraits<T>` protocol methods.
- This makes the API contract explicit: callers choose whether they want "is this already type T?" vs "can this be converted to type T?".

## Status
Accepted

## Context
The original `as<T>()` method on `AnyView` and `Any` performed both strict type checking and type conversion (e.g., int to float). This dual behavior was confusing:
1. Callers who wanted to check "is this value exactly an int?" would get `true` even when the value was a float that could be converted to int.
2. Container validation (`Array<T>`) used `as<T>()` for element checking, which could silently accept elements of the wrong type as long as they were convertible.
3. The `TypeTraits<T>` protocol method names (`CheckAnyStorage`, `CopyFromAnyStorageAfterCheck`, `TryConvertFromAnyView`) did not clearly distinguish the strict and converting paths.

The codebase needed a clear separation of "reinterpret" (the value already has this type) from "convert" (the value can be transformed to this type).

## Decision Drivers
- API clarity: users should know whether they are doing a strict type check or a lossy conversion.
- Container safety: `Array<T>` element validation should use strict checks, not converting checks.
- Naming consistency: the public API names and the `TypeTraits` protocol names should align.
- Performance: strict checks should be cheaper than conversions (no actual conversion work).

## Decision
Split the single `as<T>()` into three distinct operations:

| Method | Behavior | Returns | Throws |
|--------|----------|---------|--------|
| `as<T>()` | Strict type check only, no conversion | `std::optional<T>` | Never |
| `try_cast<T>()` | Attempts conversion, returns nullopt on failure | `std::optional<T>` | Never |
| `cast<T>()` | Attempts conversion, throws on failure | `T` | `TypeError` |

Rename the `TypeTraits<T>` protocol methods to match:

| Old Name | New Name | Purpose |
|----------|----------|---------|
| `CheckAnyStorage` | `CheckAnyStrict` | Returns true if the value is exactly type T |
| `CopyFromAnyStorageAfterCheck` | `CopyFromAnyViewAfterCheck` | Copy value from AnyView after strict check passed |
| `MoveFromAnyStorageAfterCheck` | `MoveFromAnyAfterCheck` | Move value from Any after strict check passed |
| `TryConvertFromAnyView` | `TryCastFromAnyView` | Attempt conversion, return nullopt on failure |

Add `Any::as<T>() &&` rvalue overload for move-out with strict check.

## Alternatives Considered
### Keep single as<T>() with a boolean flag for strict mode
- Pros: No API surface increase. Single entry point.
- Cons: Flag parameters are error-prone (callers can forget the flag). No compile-time distinction. Template specialization would need to handle both modes.

### Use different method names: as_strict<T>() and as_convert<T>()
- Pros: Both methods have "as" in the name, maintaining naming consistency.
- Cons: "as_strict" is verbose. "as_convert" is unusual. The chosen `as`/`cast`/`try_cast` naming follows the C++ and Python ecosystems (Python has `int(x)` as cast, C++ has `static_cast`/`dynamic_cast`).

### Add only try_cast, keep as() as-is
- Pros: Minimal disruption.
- Cons: Does not clarify the semantics of `as()`. Container code would still need to decide which to use.

## Why This Option Won
- The `as`/`cast`/`try_cast` naming is intuitive: `as` = "view as" (reinterpret), `cast` = "convert to" (may fail), `try_cast` = "try to convert" (graceful failure).
- The `TypeTraits` renaming from "Storage" to "Strict"/"View" is semantically more accurate: `CheckAnyStrict` conveys "strict type match", while `CheckAnyStorage` implied storage format concerns.
- Container validation (`Array<T>` element checks) now correctly uses `CheckAnyStrict`, ensuring type-safe containers without silent conversions.
- The rvalue `as<T>() &&` overload enables efficient move-out patterns that were not possible with the previous API.

## Consequences
### Positive
- API contracts are explicit and self-documenting.
- Container type checking is stricter and more correct.
- Converting behavior is opt-in (callers must explicitly choose `cast`/`try_cast`).
- `TypeTraits` protocol names align with public API names.

### Negative
- **Breaking API change**: all code using `AnyView::as<T>()` or `Any::as<T>()` that relied on implicit conversion must switch to `try_cast<T>()` or `cast<T>()`.
- **Breaking TypeTraits protocol**: all custom `TypeTraits<T>` specializations must rename their methods.
- Three methods where there was one increases API surface.

### Risks
- Downstream code migration: any out-of-tree `TypeTraits` specialization using old method names will fail to compile. Mitigated by the rename being a compile-time error (not a silent behavioral change).
- Confusion between `as` and `try_cast` for new users. Mitigated by clear documentation: `as` = "already is", `cast`/`try_cast` = "convert to".

## Implementation Notes
- `Any::as<T>()` calls `TypeTraits<T>::CheckAnyStrict` + `CopyFromAnyViewAfterCheck` (no conversion).
- `Any::cast<T>()` calls `TypeTraits<T>::TryCastFromAnyView` and throws `TypeError` on `nullopt`.
- `Any::try_cast<T>()` calls `TypeTraits<T>::TryCastFromAnyView` and returns the `optional` directly.
- Container slow paths (`Array`, `Map`) use `try_cast<T>()` where conversion is actually desired (e.g., element-by-element error diagnostics).
- `DLTensor*` type traits gain `CheckAnyStrict` and `CopyFromAnyViewAfterCheck` (previously missing).
- 16 files changed, 318 insertions, 197 deletions.

## Validation
- `tests/cpp/test_any.cc`: New tests for `as<T>()` strict behavior, `try_cast<T>()` conversion, and `cast<T>()` throwing behavior.
- `tests/cpp/test_dtype.cc`: Updated to use `cast<T>()` where conversion is needed.
- `tests/cpp/test_string.cc`: Updated to use the new method names.

## Migration and Rollback
- All in-tree call sites were migrated in the same commit.
- Out-of-tree migration: search for `->as<` and `::as<` and replace with `->try_cast<` or `->cast<` where conversion was intended. Replace TypeTraits method names mechanically.
- Rollback would require reverting the entire API change, which is not recommended given the improved clarity.

## Related Design Docs
- [.memory/designs/0001-type-erased-any-value-system.md](.memory/designs/0001-type-erased-any-value-system.md)

## Related Diagrams
- [.memory/diagrams/0001-any-value-memory-layout.md](.memory/diagrams/0001-any-value-memory-layout.md)

## Evidence Matrix
- `as<T>()` strict-only change -> `.memory/commits/2025-05-14-37a2e7c521435cbe2bd772480f0389c18bd9ce2c.md` + `37a2e7` + `include/tvm/ffi/any.h`
- `cast<T>()`/`try_cast<T>()` introduction -> `37a2e7` + `include/tvm/ffi/any.h`
- TypeTraits rename (CheckAnyStorage -> CheckAnyStrict, etc.) -> `37a2e7` + `include/tvm/ffi/type_traits.h`
- Container updates (Array, Map, Tuple, Variant) -> `37a2e7` + `include/tvm/ffi/container/array.h`, `map.h`, `tuple.h`, `variant.h`
- DLTensor* strict check addition -> `37a2e7` + `include/tvm/ffi/dtype.h`
- Rvalue as<T>()&& overload -> `37a2e7` + `include/tvm/ffi/any.h`

## Supersedes
None (refines the original `as<T>()` API from design 0001)

## Superseded By
None

## Follow-up Actions
- Ensure Python and Rust bindings reflect the `as`/`cast`/`try_cast` distinction in their APIs.
- Update design doc 0001 to reference the new method names.
- ~~Remove legacy `Downcast<T>()` wrapper~~ -- completed in [ADR-0012](.memory/ADRs/0012-remove-downcast-favor-any-cast.md) (commit `4be1af7`).
