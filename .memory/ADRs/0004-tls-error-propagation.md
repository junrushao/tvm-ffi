---
adr: "0004"
title: "Use Thread-Local Storage for Error Propagation Across C ABI Boundaries"
status: "accepted"
date: "2025-05-06"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "error-handling"
  - "abi"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
source_ledgers:
  - ".memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md"
---

# ADR-0004: Use Thread-Local Storage for Error Propagation Across C ABI Boundaries

## TL;DR
- C++ exceptions cannot cross C ABI boundaries. Instead, the safe-call convention catches exceptions, stores the error object in thread-local storage (TLS) via `TVMFFIErrorSetRaised`, and returns -1. The caller retrieves the error via `TVMFFIErrorMoveFromRaised`.
- This pattern allows rich, structured error objects (`ErrorObj` with kind, message, backtrace, cause chain) to propagate across language boundaries while the C ABI only communicates success/failure via an integer return code.

## Status
Accepted

## Context
TVM FFI supports cross-language function calls: C++ functions can be called from Python, Rust, or any language that can invoke C functions. C++ uses exceptions for error handling, but:
1. C++ exceptions cannot be caught across `extern "C"` function boundaries (undefined behavior in most ABIs).
2. Different languages have incompatible exception mechanisms (Python exceptions, Rust `Result`, etc.).
3. The error object is rich: it carries a kind string, message, backtrace, cause chain, and extra context -- too large to return via an integer error code alone.

A mechanism is needed to transport error information from the C++ callee to the foreign caller.

## Decision Drivers
- Safety: exceptions must never escape `extern "C"` functions.
- Richness: the error object must preserve full diagnostic information (kind, message, backtrace, cause chain).
- Thread safety: each thread must have its own error slot (no global state contention).
- Simplicity: the pattern must be easy for foreign language binding authors to implement.
- Performance: the success path must have zero overhead from error handling.

## Decision
Use a two-phase protocol:

1. **Safe-call boundary**: Every C ABI function wraps its implementation in `TVM_FFI_SAFE_CALL_BEGIN()` / `TVM_FFI_SAFE_CALL_END()` which catches all C++ exceptions at the boundary.
2. **Error storage**: On exception, the caught `Error` object is moved into a thread-local slot via `TVMFFIErrorSetRaised(TVMFFIObjectHandle error)`.
3. **Return code**: The function returns -1 to indicate failure (0 for success).
4. **Error retrieval**: The caller checks the return code. On -1, it calls `TVMFFIErrorMoveFromRaised(TVMFFIAny* error)` to move the error out of TLS. The caller then translates the error into its native exception type.

The `TVMFFISafeCallType` function pointer signature encodes this convention:
```c
typedef int (*TVMFFISafeCallType)(void* handle, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result);
```

The `ErrorObj` structure carries:
- `kind` (string): error category (e.g., "ValueError", "RuntimeError")
- `message` (string): human-readable description
- `backtrace` (string): C++ stack trace (most recent call first)
- `cause_chain` (optional ErrorObj): linked list of causing errors
- `extra_context` (optional Object): additional structured data
- `update_backtrace` (function pointer): allows appending cross-language backtrace frames

## Alternatives Considered
### Return error object via output parameter
- Pros: No TLS needed. Explicit data flow.
- Cons: Every function signature needs an extra `TVMFFIAny* error` parameter. This changes the packed calling convention and makes the common success path more expensive (extra parameter register usage).

### Return error via the result parameter (overloading rv)
- Pros: No TLS. Uses existing parameter.
- Cons: Conflates result and error in the same slot. The caller cannot distinguish between a valid result of object type and an error object without additional metadata. Also, `rv` is typed `TVMFFIAny*` and the caller may have already partially initialized it.

### errno-style global error code
- Pros: Familiar pattern. Simple.
- Cons: Cannot carry rich error objects. Not thread-safe without TLS (at which point it is the same as this design but less capable).

### setjmp/longjmp
- Pros: Can propagate errors without return codes.
- Cons: Bypasses C++ destructors (resource leaks). Not compatible with C++ RAII. Dangerous with complex call stacks.

## Why This Option Won
- The success path has zero overhead: no extra parameters, no extra checks beyond the integer return code.
- TLS is universally supported on target platforms (Linux, macOS, Windows).
- Rich error objects are preserved end-to-end, enabling Python to reconstruct meaningful tracebacks from C++ backtraces.
- The pattern is well-established (similar to Python's `PyErr_SetObject` / `PyErr_Fetch` and OpenGL's `glGetError`).
- The `update_backtrace` callback allows the caller to append its own stack frames as the error propagates up through multiple language boundaries.

## Consequences
### Positive
- Full error fidelity across C ABI boundaries.
- Thread-safe by construction (each thread has its own TLS slot).
- Zero-cost success path (no extra parameters or branches beyond return code check).
- The cause chain enables wrapping foreign errors (e.g., Python exception wrapped as cause of a C++ error).

### Negative
- The caller must always check the return code and call `TVMFFIErrorMoveFromRaised` on failure. Forgetting this leaks the error in TLS.
- If a caller calls two C ABI functions without retrieving the error from the first, the second call's error overwrites the first (only one TLS slot). This is documented but not enforced.
- TLS has platform-specific performance characteristics; on some systems, accessing `thread_local` variables is slower than register access.

### Risks
- Leaked errors in TLS if callers forget to retrieve them. Mitigated by documentation and binding-level wrappers that always check return codes.
- TLS initialization overhead on first access in a new thread. Mitigated by lazy initialization (negligible in practice).

## Implementation Notes
- `TVM_FFI_SAFE_CALL_BEGIN()` / `TVM_FFI_SAFE_CALL_END()` macros in `include/tvm/ffi/function.h` implement the try/catch boundary.
- `TVMFFIErrorSetRaised` and `TVMFFIErrorMoveFromRaised` are C ABI functions defined in the core library.
- `TVMFFIErrorCreate` constructs an error object from kind, message, and backtrace strings.
- `ErrorObj` in `include/tvm/ffi/error.h` defines the rich error structure.
- `TVM_FFI_THROW(ErrorType) << "message"` macro provides ergonomic C++ error creation with stream syntax.
- Backtrace capture uses libbacktrace (optional, controlled by `TVM_FFI_USE_LIBBACKTRACE`).

## Validation
- `tests/cpp/test_ffi_error.cc` tests error creation, TLS propagation, and cross-boundary error handling.
- Integration tests with Python bindings (in later commits) verify end-to-end error propagation.

## Migration and Rollback
- This is a foundational protocol from the root commit. Changing it requires updating all foreign language bindings.

## Related Design Docs
- [.memory/designs/0003-packed-function-and-global-registry.md](.memory/designs/0003-packed-function-and-global-registry.md)
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)

## Related Diagrams
- [.memory/diagrams/0003-function-call-flow.md](.memory/diagrams/0003-function-call-flow.md)

## Evidence Matrix
- TVMFFISafeCallType signature -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `include/tvm/ffi/c_api.h` lines 458-480
- TVM_FFI_SAFE_CALL_BEGIN/END -> `7d34eb8` + `include/tvm/ffi/function.h` lines 72-80
- ErrorObj structure -> `7d34eb8` + `include/tvm/ffi/error.h` + `include/tvm/ffi/c_api.h` lines 416-456
- TVMFFIErrorSetRaised/MoveFromRaised C API -> `7d34eb8` + `include/tvm/ffi/c_api.h`
- Ledger error system description -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` Design Elements: Error system

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Ensure all foreign language bindings (Python, Rust) implement the check-and-retrieve pattern consistently.
- Consider adding debug-mode detection for leaked errors in TLS (error set but never retrieved).
