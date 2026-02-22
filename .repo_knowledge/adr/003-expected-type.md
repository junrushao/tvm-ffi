# ADR-003: Add `Expected<T>` for Exception-Free Error Handling

- **Status**: Accepted
- **Date**: 2026-02-06
- **Commits**: `0a9d4b6`
- **Issue**: #234

## Context

TVM-FFI's C++ API used exceptions exclusively for error reporting. While
exceptions are ergonomic, they have drawbacks:
1. **Performance**: Exception handling has non-trivial overhead in hot paths.
2. **Embedded/kernel contexts**: Some deployment targets restrict or disable
   exceptions.
3. **Explicit error handling**: Callers may prefer to inspect and handle
   errors without try/catch, similar to Rust's `Result` type.

## Decision

Introduce `Expected<T>` (modeled after Rust's `Result<T, Error>` and C++23's
`std::expected`):

```cpp
Expected<int> result = func.CallExpected<int>(arg1, arg2);
if (result.is_ok()) {
    use(result.value());
} else {
    handle(result.error());
}
```

Key design choices:
1. **Internal `Any` storage**: Rather than a tagged union, `Expected<T>`
   stores the value/error in an `Any`. This reuses existing type-erasure
   infrastructure.
2. **`Function::CallExpected<T>()`**: New method that uses the `safe_call`
   path and catches exceptions into `Expected`.
3. **Full `TypeTraits` integration**: `Expected<T>` can be stored in `Any`,
   passed through FFI boundaries, and has a proper TypeSchema.
4. **`Unexpected<E>` wrapper**: For explicit error-state construction with
   CTAD deduction guide.

## Consequences

- **Positive**: Callers can now choose between exception-based and
  exception-free error handling; `Expected<T>` integrates naturally with
  the existing type system.
- **Negative**: Two parallel error-handling patterns to maintain; Python
  and Rust bindings for `Expected<T>` are not yet implemented.
- **Follow-ups**: Python and Rust bindings for `Expected<T>`.

## Alternatives Considered

1. **C-style error codes**: Rejected — too low-level and loses error context.
2. **`std::optional<T>` + separate error**: Rejected — doesn't carry error
   information in the return type.
3. **Wait for C++23 `std::expected`**: Rejected — TVM-FFI targets C++17.
