---
adr: "0012"
title: "Remove Downcast<T>() from FFI, Use Any::cast<T>() Instead"
status: "accepted"
date: "2025-08-08"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "api-cleanup"
source_commits:
  - "4be1af7305d7326f70075452ce12f4896f5b93e9"
source_ledgers:
  - ".memory/commits/2025-08-08-4be1af7305d7326f70075452ce12f4896f5b93e9.md"
---

# ADR-0012: Remove Downcast<T>() from FFI, Use Any::cast<T>() Instead

## TL;DR
- All `Downcast<T>()` overloads (for `ObjectRef`, `Any`, `Any&&`, `std::optional<Any>`) are removed from `include/tvm/ffi/cast.h`. Callers must use `Any::cast<T>()` instead.
- `cast.h` is reduced to a minimal header containing only `GetRef<RefType>(ptr)` and `GetObjectPtr<BaseType>(ptr)` -- pointer-to-ref and pointer-to-ObjectPtr conversions with no value conversion semantics.

## Status
Accepted

## Context
After [ADR-0005](.memory/ADRs/0005-as-vs-cast-semantic-split.md) introduced `Any::cast<T>()` as the canonical converting accessor, `Downcast<T>()` became a redundant convenience wrapper. It duplicated the semantics of `cast<T>()` with a different call syntax (`Downcast<T>(any)` vs `any.cast<T>()`). Having two ways to do the same thing created unnecessary API surface and confusion about which to use.

Only one in-tree test (`test_string.cc`) still used `Downcast` directly, confirming that most call sites had already migrated to `cast<T>()`.

## Decision Drivers
- API minimalism: the core FFI surface should not carry redundant functions.
- Naming clarity: `Any::cast<T>()` is the canonical converting accessor per ADR-0005.
- Compile-time safety: removing `Downcast` forces callers to use the established `as`/`cast`/`try_cast` triple.

## Decision
Remove all four `Downcast<T>()` overloads from `cast.h`:
1. `Downcast<T>(ObjectRef)` -- use `any.cast<T>()`
2. `Downcast<T>(Any)` -- use `any.cast<T>()`
3. `Downcast<T>(Any&&)` -- use `std::move(any).cast<T>()`
4. `Downcast<T>(std::optional<Any>)` -- use conditional `cast<T>()`

Remove the `using ffi::Downcast;` alias from `namespace tvm`.

Update the sole in-tree caller in `test_string.cc` to use `r.cast<String>()`.

Simplify `cast.h` by:
- Replacing `TVM_FFI_INLINE` with plain `inline` on `GetRef`.
- Removing unnecessary includes (`dtype.h`, `error.h`, `<utility>`).
- Adding `using ffi::GetObjectPtr;` to `namespace tvm` (previously missing).

## Alternatives Considered
### Keep Downcast as a deprecated wrapper
- Pros: Softer migration. Downstream code continues to compile with a deprecation warning.
- Cons: Deprecated APIs accumulate. The warning noise discourages but does not enforce migration. The FFI layer is still pre-1.0, so breaking changes are acceptable.

### Move Downcast to a compatibility header
- Pros: Available for downstream code that needs it.
- Cons: Adds a file to maintain. Sends mixed signals about the preferred API.

## Why This Option Won
- The FFI is pre-1.0 and the breaking change is minimal (only one in-tree caller).
- `Any::cast<T>()` has been the canonical API since ADR-0005 and all significant call sites already use it.
- Removing `Downcast` reduces `cast.h` to its essential purpose: pointer-to-ref conversions.

## Consequences
### Positive
- `cast.h` is reduced from ~90 template lines to ~40 lines of straightforward pointer conversion.
- The API has a single, unambiguous casting path: `any.cast<T>()` / `any.try_cast<T>()`.
- Unnecessary includes (`dtype.h`, `error.h`) are removed, reducing compile-time for files that include `cast.h`.

### Negative
- **Breaking API change**: any downstream C++ code calling `tvm::Downcast<T>(...)` or `tvm::ffi::Downcast<T>(...)` will fail to compile.
- The commit message notes "move out of ffi to node for now," implying `Downcast` may reappear in a higher-level TVM layer. The FFI layer itself no longer carries the symbol.

### Risks
- Downstream code migration: out-of-tree callers must replace `Downcast<T>(x)` with `x.cast<T>()`. This is a mechanical transformation caught by the compiler (not a silent behavioral change).

## Implementation Notes
- `cast.h` retains only `GetRef<RefType>(ptr)` and `GetObjectPtr<BaseType>(ptr)`.
- `GetRef` now uses `inline` instead of `TVM_FFI_INLINE` (the latter was unnecessary for a template function).
- `namespace tvm` now has `using ffi::GetObjectPtr;` in addition to `using ffi::GetRef;`.

## Validation
- `tests/cpp/test_string.cc`: Updated from `Downcast<String>(r)` to `r.cast<String>()`.
- All existing tests pass without `Downcast`.

## Migration and Rollback
- Migration: search for `Downcast<` in downstream code and replace with `.cast<`. The compiler will flag all call sites.
- Rollback: revert the commit to restore `Downcast` overloads.

## Related Design Docs
- [.memory/designs/0001-type-erased-any-value-system.md](.memory/designs/0001-type-erased-any-value-system.md) -- `Any::cast<T>()` is the canonical converting accessor.

## Related Diagrams
- None

## Evidence Matrix
- `Downcast<T>()` overloads removed from `cast.h` -> `.memory/commits/2025-08-08-4be1af7305d7326f70075452ce12f4896f5b93e9.md` + `4be1af7` + `include/tvm/ffi/cast.h`
- `cast.h` reduced to `GetRef` + `GetObjectPtr` only -> `.memory/commits/2025-08-08-4be1af7305d7326f70075452ce12f4896f5b93e9.md` + `4be1af7` + `include/tvm/ffi/cast.h` (final state ~40 lines)
- `using ffi::Downcast` removed from `namespace tvm` -> `.memory/commits/2025-08-08-4be1af7305d7326f70075452ce12f4896f5b93e9.md` + `4be1af7` + `include/tvm/ffi/cast.h`
- `using ffi::GetObjectPtr` added to `namespace tvm` -> `.memory/commits/2025-08-08-4be1af7305d7326f70075452ce12f4896f5b93e9.md` + `4be1af7` + `include/tvm/ffi/cast.h`
- Test update: `Downcast<String>(r)` -> `r.cast<String>()` -> `.memory/commits/2025-08-08-4be1af7305d7326f70075452ce12f4896f5b93e9.md` + `4be1af7` + `tests/cpp/test_string.cc`

## Supersedes
None (follows up on [ADR-0005](.memory/ADRs/0005-as-vs-cast-semantic-split.md) which introduced `cast<T>()` but retained `Downcast`)

## Superseded By
None

## Follow-up Actions
- Monitor whether `Downcast` reappears in the higher-level TVM `node/` layer as the commit message suggests.
