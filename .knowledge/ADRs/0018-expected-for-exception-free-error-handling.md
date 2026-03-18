---
scope:
  - "0005-error-system"
  - "0004-function-system"
  - "0006-type-traits"
---
# ADR: Expected<T> for Exception-Free Error Handling

**TL;DR**: Decision to add `Expected<T>` (analogous to Rust's `Result<T, E>` / C++23's `std::expected`) and `Function::CallExpected<T>()` to enable exception-free FFI function invocation, complementing the existing TLS-based error propagation.

## Context
- The existing error system requires exceptions for error propagation: functions throw `Error`, the safe-call boundary catches it into TLS, and the caller retrieves it. This works well for the FFI boundary but forces exception use even for C++-to-C++ calls where the caller would prefer inline error handling.
- Performance-sensitive code paths (tight loops calling FFI functions) pay the cost of exception setup/teardown even on the success path.
- Rust developers are accustomed to `Result<T, E>` and find exception-based error handling unidiomatic.
- C++23 introduced `std::expected<T, E>` for the same purpose, but the project targets C++17.

Usecases:
- A C++ function that divides two numbers wants to return an error for division by zero without throwing.
- A caller invoking an FFI function in a loop wants to check for errors inline without try/catch overhead.
- Library code wants to compose fallible operations without exception unwinding.

Design Decisions:
- **`Expected<T>` as a value type backed by `Any`**: Internally stores either `T` or `Error` in a single `Any` field. `is_ok()` checks `data_.as<Error>()` first (handles T-is-ObjectRef-subclass edge cases).
- **`Function::CallExpected<T>()`**: Calls `safe_call` directly (not `CallPacked`), catches the `-1` return code, and wraps the TLS error into `Unexpected` instead of re-throwing.
- **Full `TypeTraits<Expected<T>>` integration**: `Expected<T>` participates in the `Any` type system. `CheckAnyStrict` accepts both `T` and `Error`. Enables `Expected<T>` as function return type through the FFI.
- **`Unexpected<E>` wrapper**: Explicit error construction to disambiguate `Expected<ObjectRef>(some_error)` from implicit Error conversion.

## Implementation Notes
- `Expected<Error>` is a compile-time error (`static_assert`). Use `Error` directly.
- `value()` throws the contained `Error` if `is_err()` -- still supports exception-based unwinding when desired.
- `value_or(default)` provides a pure non-throwing access path.
- `TypeSchema` for `Expected<T>` is `{"type":"Expected","args":[T_schema, {"type":"ffi.Error"}]}`, enabling cross-language schema introspection.

## Related Design Docs
- [0005-error-system.md](../designs/0005-error-system.md) -- Expected<T> as extension to the error system
- [0004-function-system.md](../designs/0004-function-system.md) -- Function::CallExpected<T>() API
- [0006-type-traits.md](../designs/0006-type-traits.md) -- TypeTraits<Expected<T>> integration
