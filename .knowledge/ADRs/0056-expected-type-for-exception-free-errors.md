---
scope:
  - "0007-error-handling"
  - "0004-function-system"
---
# Expected<T> for Exception-Free Error Handling

**TL;DR**: A new `Expected<T>` class (analogous to Rust `Result<T, Error>` or C++23 `std::expected`) was added to enable exception-free error handling in C++ FFI code, complementing (not replacing) the existing exception-based approach.

## Context

The existing FFI error handling uses C++ exceptions: functions throw `Error`, which is caught at C ABI boundaries by `TVM_FFI_SAFE_CALL_END` and stored in TLS. Callers retrieve the error via `TVMFFIErrorMoveFromRaised`. This works well for the general case but has limitations:

1. **Performance-sensitive paths**: Exception throwing/catching has non-trivial overhead on some platforms.
2. **Composability**: Checking if a function succeeded requires try/catch blocks, making error-conditional logic verbose.
3. **C++23 alignment**: `std::expected` is the emerging C++ standard for value-or-error return types.

GitHub issue #234 requested an exception-free API similar to Rust's `Result`.

## Decision

Add `Expected<T>` as a new vocabulary type:
- `Expected<T>` holds either a success value of type `T` or an `Error`, stored internally as `Any`.
- `is_ok()` / `is_err()` / `has_value()` for status checking.
- `value()` returns T or throws the contained Error.
- `error()` returns Error or throws RuntimeError.
- `value_or(default)` for safe extraction.
- `Unexpected<E>` wrapper for explicit error construction.
- `Function::CallExpected<T>(args...)` calls a function via `safe_call` and wraps any exception into `Expected<T>` as an error.
- Full `TypeTraits<Expected<T>>` specialization allowing `Expected<T>` to participate in the Any type system. The TypeTraits unwraps the Expected: an Ok value serializes as T, an Err serializes as Error.

## Rationale

1. **Dual convention**: `Expected<T>` provides an opt-in exception-free path. Existing exception-based code is unaffected. Callers choose per call site.
2. **Any transparency**: The TypeTraits specialization means functions returning `Expected<T>` work seamlessly with the FFI -- Ok values appear as T to callers expecting T, and errors appear as Error objects.
3. **CallExpected**: Rather than requiring all functions to return `Expected<T>`, `CallExpected` wraps any function call. This means existing FFI functions gain exception-free callability without modification.
4. **Not replacing exceptions**: `Expected<T>` complements the exception path. The C ABI boundary still uses exceptions internally; `Expected<T>` is a C++-side convenience.

## Alternatives Considered

1. **Use `std::expected` directly (C++23)**: The project targets C++17, so `std::expected` is not available without polyfills. The custom `Expected<T>` integrates with the FFI `Any` type system, which `std::expected` would not.
2. **Use `std::optional<T>` for success + separate error query**: Loses error details; callers must check a separate error source.
3. **Return `Any` and let callers check type**: This is what `CallExpected` does internally, but wrapping it in `Expected<T>` provides type safety and ergonomic API.
4. **Add a `noexcept` variant of every FFI function**: Combinatorial explosion of function overloads.

## Implementation Notes

- `include/tvm/ffi/expected.h`: `Expected<T>` class, `Unexpected<E>` wrapper, `TypeTraits<Expected<T>>` specialization.
- `include/tvm/ffi/function.h`: `Function::CallExpected<T>()` method.
- `include/tvm/ffi/function_details.h`: Forward declaration of `Expected<T>`.
- `include/tvm/ffi/tvm_ffi.h`: Includes `expected.h`.
- `tests/cpp/test_expected.cc`: 345-line test suite covering basic Ok/Err, TypeTraits roundtrip, CallExpected, registered functions returning Expected, nested types (Optional, Array), and ObjectRef inheritance edge cases.

## Related Design Docs

- [`.knowledge/designs/0007-error-handling.md`](../designs/0007-error-handling.md)
- [`.knowledge/designs/0004-function-system.md`](../designs/0004-function-system.md)
- Commit: `.knowledge/commits/2026-02-06-0a9d4b681cb017e9103efa6cc20d687c065a26fe.md`
