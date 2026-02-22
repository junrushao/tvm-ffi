# ADR 007: Downcast Removal from FFI Layer

- Status: Accepted
- Date: 2025-08-08
- Owners: Tianqi Chen

## Context

The `Downcast<T>(ref)` family of functions in `include/tvm/ffi/cast.h`
provided type-narrowing functionality for `ObjectRef`, `Any`, and
`Optional<Any>` values. Four overloads existed:

1. `Downcast<SubRef>(BaseRef)` -- narrow an ObjectRef to a subtype
2. `Downcast<T>(Any)` -- extract a typed value from Any (lvalue)
3. `Downcast<T>(Any&&)` -- extract from rvalue Any
4. `Downcast<T>(Optional<Any>)` -- extract from optional Any

This functionality duplicated `Any::cast<T>()`, which was introduced as part
of the `as`/`cast` semantic split (ADR 001, `37a2e7c`). Having two parallel
mechanisms for the same operation was confusing and increased the API surface
of the FFI layer unnecessarily.

## Decision

Remove the `Downcast` family of functions from the FFI layer entirely:

- All four `Downcast` overloads removed from `include/tvm/ffi/cast.h`
  (~82 lines deleted).
- The `using ffi::Downcast;` declaration removed from the `tvm` namespace.
- Unused includes (`dtype.h`, `error.h`, `<utility>`) cleaned up from
  `cast.h`.
- Only `GetRef` and `GetObjectPtr` remain in `cast.h`.

Callers should use:
- `ref.cast<T>()` for `Any`/`AnyView` inputs (equivalent to the old
  `Downcast<T>(any)`)
- `GetRef<T>(ptr)` for raw `ObjectObj*` -> `ObjectRef` upcasting

The `Downcast` functionality may be reinstated in a higher-level layer (e.g.,
`node/`) if needed for backward compatibility with the main TVM compiler, but
it does not belong in the minimal FFI layer.

## Consequences

- Positive: Reduced FFI API surface. One canonical way to extract typed values
  from `Any` (`cast<T>()`).
- Positive: Cleaner `cast.h` header (only `GetRef` and `GetObjectPtr`).
- Negative: **Breaking change** for all downstream code using `Downcast`.
  This includes the main TVM compiler codebase, which uses `Downcast`
  extensively.
- Migration/Rollout: Replace `Downcast<T>(ref)` with `ref.cast<T>()` for
  `Any` inputs. Replace `Downcast<SubRef>(base_ref)` with
  `base_ref.as<SubRef>()` (strict check) or reconstruct via `GetRef`.

## References
- Range summary: `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
- Evidence commits: `4be1af7305d7326f70075452ce12f4896f5b93e9`
- External references: none

## Related Design Docs
- `.repo-knowledge/design/001-type-erased-value-system.md`
- `.repo-knowledge/design/002-namespace-and-api-migration.md`

## Notes
The test migration in `tests/cpp/test_string.cc` demonstrates the canonical
replacement: `Downcast<String>(r)` becomes `r.cast<String>()`. This is the
pattern that downstream code should follow.
