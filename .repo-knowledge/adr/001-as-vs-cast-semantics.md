# ADR 001: as() vs cast() Semantics for Type-Erased Values

- Status: Accepted
- Date: 2025-05-14
- Owners: Tianqi Chen

## Context

The `AnyView` and `Any` containers previously exposed a single `as<T>()`
method that conflated two distinct operations:

1. **Strict type check**: "Is this value already of type `T`?" (no conversion).
2. **Type conversion**: "Can I obtain a value of type `T` from this?" (may
   coerce, e.g., `int64_t` to `double`, or `String` to `const char*`).

Callers could not distinguish between the two, leading to ambiguity: some call
sites expected strict checking (pattern matching on variants), while others
relied on implicit conversion (argument unpacking in function dispatch).

This affected correctness (values that should not convert were silently coerced)
and performance (conversion logic ran even when only a type check was needed).

## Decision

Split type extraction into two distinct APIs:

- **`as<T>()`** -- Strict type check. Returns `std::optional<T>`: the value if
  the stored type is already `T` (or a subtype for Object pointers), or
  `std::nullopt` otherwise. No conversion is performed. Does not throw.

- **`cast<T>()`** -- Full type conversion. May perform coercion. Throws
  `TypeError` if conversion is impossible.

- **`try_cast<T>()`** -- Non-throwing variant of `cast<T>()`. Returns
  `std::optional<T>`.

The `TypeTraits<T>` protocol was refactored to support this split:
- `CheckAnyStrict(const TVMFFIAny*)` -- returns `bool` for `as<T>()`.
- `CopyFromAnyViewAfterCheck(const TVMFFIAny*)` -- extracts value after strict
  check passed (used by `as<T>()`).
- `TryCastFromAnyView(const TVMFFIAny*)` -- returns `std::optional<T>` for
  `cast<T>()` / `try_cast<T>()`.

All container types (`Array`, `Map`, `Tuple`, `Variant`, `String`, `DLDataType`,
`Function`, `RValueRef`) were updated to implement the new three-hook protocol.

## Consequences

- Positive: Clear semantic contract. Callers explicitly choose between
  "check only" and "convert". Pattern-matching code uses `as`, dispatch code
  uses `cast`.
- Positive: Performance improvement for strict checks -- no conversion logic
  is invoked on the `as` path.
- Negative: **Breaking change** for existing code that called `as<T>()` and
  relied on implicit conversion. Those call sites must migrate to `cast<T>()`.
- Migration/Rollout: Audit all `as<T>()` call sites in downstream code. Replace
  with `cast<T>()` or `try_cast<T>()` where type conversion was the intent.

## References
- Range summary: `.repo-knowledge/ranges/2025-05-29-7D34EB8-024E45C.md`
- Evidence commits: `37a2e7c521435cbe2bd772480f0389c18bd9ce2c`
- External references: none

## Related Design Docs
- `.repo-knowledge/design/001-type-erased-value-system.md`

## Notes
The `as<T>()` overload where `T` is an Object subclass returns `const T*`
(a raw pointer or `nullptr`), implemented as `as<const T*>().value_or(nullptr)`.
This provides a convenient strict check for Object pointers, mirroring
`dynamic_cast<T*>` semantics.
