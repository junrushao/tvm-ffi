---
scope:
  - "0006-error-handling"
---
# ADR 0026: Expected<T> for Exception-Free FFI Error Handling

**TL;DR**: Introduce `Expected<T>` (analogous to Rust's `Result<T, Error>` / C++23's `std::expected`) and `Function::CallExpected<T>` to provide an exception-free error handling path for C++ FFI callers, using `Any` internally for storage and `TypeTraits<Expected<T>>` for full Any-system participation.

## Context

The TVM FFI error handling model is TLS-based: C++ throws, `SAFE_CALL_END` catches and stores in TLS, the caller retrieves via `TVMFFIErrorMoveFromRaised`. This works well for cross-language boundaries but forces C++ callers into `try/catch` even when they want explicit error handling.

Usecases:
- C++ callers who want to handle function call failures without try/catch overhead (e.g., probing for optional capabilities, fallback logic).
- Embedding scenarios where exceptions are disabled or undesirable (e.g., kernel code, signal handlers).
- C++ library code that already returns `Expected` to its own callers and wants FFI calls to compose cleanly.

Design Decisions:
- `Expected<T>` stores its state as `Any data_`, discriminated by `data_.as<Error>()`. If it yields a value, the Expected is in error state; otherwise it holds `T`.
- `Function::CallExpected<T>(args...)` uses the `safe_call` function pointer (same C ABI path as `TVMFFIFunctionCall`), catching exceptions at the boundary and returning them as `Expected<T>` instead of re-throwing.
- `Expected<Error>` is statically prohibited (`static_assert`) because the discriminant would be ambiguous.
- Full `TypeTraits<Expected<T>>` specialization enables `Expected<T>` to participate in the Any type system, making it a valid function return type. `CheckAnyStrict` returns `true` for both `T` and `Error`.
- `Unexpected<E>` provides explicit error construction with CTAD guide.

## Implementation Notes
- `Expected<T>` is defined in `include/tvm/ffi/expected.h`, included from `function.h` and `tvm_ffi.h`.
- The `Any` storage approach avoids introducing a `std::variant` or tagged union, reusing the existing type-erased container. The tradeoff is an extra `as<Error>()` check per `is_ok()` call vs. a dedicated discriminant field, but this matches the philosophy of the codebase (reuse existing primitives).
- `CallExpected` internally calls `safe_call`, checks the return code, and on failure calls `MoveFromSafeCallRaised()` to retrieve the error, wrapping it as `Expected<T>(Error(...))`.
- Alternative considered: **`std::expected<T, Error>` (C++23)** -- would require C++23, which the project targets C++17 for. Also, `std::expected` does not integrate with the `Any` type system or have `TypeTraits`.
- Alternative considered: **Always use try/catch** -- simpler, but forces exception-based control flow on callers. Some platforms (embedded, WASM) have poor exception support.

## Related Design Docs
- [0006-error-handling.md](../designs/0006-error-handling.md) -- Error handling design that Expected extends
- [0004-function-system.md](../designs/0004-function-system.md) -- Function::CallExpected uses the safe_call path
- [0005-type-traits.md](../designs/0005-type-traits.md) -- TypeTraits<Expected<T>> specialization
