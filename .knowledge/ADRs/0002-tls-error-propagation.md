---
scope:
  - "0005-error-system.md"
  - "0004-function-system.md"
  - "0001-c-abi.md"
---
# ADR: TLS-Based Error Propagation Across Safe-Call Boundaries

**TL;DR**: Decision to use thread-local storage (TLS) for propagating error objects across C ABI boundaries (`safe_call` returns), instead of passing error pointers through function arguments.

## Context
- C++ exceptions cannot propagate across shared library boundaries or into non-C++ languages (Python, Rust).
- The C ABI function signature `TVMFFISafeCallType(void* self, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result)` already uses 4 arguments. Adding an `Error**` parameter would increase the signature to 5, complicating codegen.
- Compiler codegen for chained FFI calls (e.g., `f(g(x))`) needs a simple pattern for error checking between calls. With TLS, each call returns an int status code; the codegen just checks `ret_code != 0` between calls without threading error pointers through.
- The error object itself (`ErrorObj`) is a full FFI Object with kind, message, and traceback, requiring ref-counted lifetime management -- passing as a raw pointer through function arguments would complicate ownership.

Usecases:
- Python binding calls a C++ function that throws `TypeError`. The safe-call boundary catches the exception, stores the `Error` object in TLS, returns -1. Python checks the return code, retrieves the error via `TVMFFIErrorMoveFromRaised`, and re-raises as a Python `TypeError`.
- Chained function calls in compiled code: `a = call1(x); b = call2(a); c = call3(b);` -- each call returns 0 or -1, codegen inserts a branch after each call to check the return code. No error pointer to propagate.
- Python `KeyboardInterrupt` during a long-running C++ computation: `TVMFFIEnvCheckSignals()` detects the pending signal, throws `EnvErrorAlreadySet`. Safe-call catches it and returns -2, signaling "error is in the frontend, not in TLS."

Design Decisions:
- **Error objects stored in thread-local storage**: `TVMFFIErrorSetRaised(error)` stores a ref-counted `ErrorObj` in TLS. `TVMFFIErrorMoveFromRaised(result)` moves it out, clearing TLS.
- **Return codes (updated in b1611e0)**: 0 = success, -1 = error in TLS (retrieve with `TVMFFIErrorMoveFromRaised`). The former `-2` code (frontend error already set) is deprecated; `EnvErrorAlreadySet` is now a regular `Error` with `kind="EnvErrorAlreadySet"` propagated through the standard `-1` TLS path. Backward-compatible `-2` handling is retained with a TODO to remove.
- **Catch-all in safe-call boundary**: `TVM_FFI_SAFE_CALL_END` catches `Error` and `std::exception`, ensuring no C++ exception escapes the DLL boundary. `EnvErrorAlreadySet` is now caught as a regular `Error` (kind="EnvErrorAlreadySet") through the same `-1` path (b1611e0). Unknown `std::exception` is wrapped in `Error("InternalError", ex.what(), "")`.
- **Move semantics**: `TVMFFIErrorMoveFromRaised` transfers ownership of the error object from TLS to the caller, avoiding unnecessary ref-count bumps.

## Implementation Notes
- The `TVMFFISafeCallType` signature remains a clean 4-argument C function: `int (void* self, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result)`.
- TLS storage is a single `thread_local TVMFFIObjectHandle` slot. Only one error can be in-flight per thread at a time.
- `TVM_FFI_CHECK_SAFE_CALL(func)` is the C++ macro for callers: checks return code, retrieves error from TLS if -1, throws `EnvErrorAlreadySet` if -2.
- The trade-off of requiring TLS runtime support is accepted because all target platforms (Linux, macOS, Windows, WASM with `__thread`) support TLS.

## Related Design Docs
- [0005-error-system.md](../designs/0005-error-system.md) -- ErrorObj, Error, EnvErrorAlreadySet
- [0004-function-system.md](../designs/0004-function-system.md) -- Safe-call boundary, TVM_FFI_SAFE_CALL_BEGIN/END
- [0001-c-abi.md](../designs/0001-c-abi.md) -- TVMFFISafeCallType signature, TVMFFIErrorSetRaised/MoveFromRaised
