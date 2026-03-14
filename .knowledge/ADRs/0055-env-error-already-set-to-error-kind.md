---
scope:
  - "0007-error-handling"
  - "0001-c-abi"
---
# Unify EnvErrorAlreadySet to Error Kind String

**TL;DR**: The dedicated `EnvErrorAlreadySet` C++ exception class and its special error code `-2` were replaced with a normal `Error` object with `kind == "EnvErrorAlreadySet"`, transported through the standard TLS error path (error code `-1`).

## Context

The original error handling design had three return codes from `safe_call`:
- `0`: Success.
- `-1`: Error occurred, retrievable via `TVMFFIErrorMoveFromRaised`.
- `-2`: Frontend environment (Python) already has an exception set; do not fetch from TLS.

The `-2` path was handled by a separate `catch (const EnvErrorAlreadySet&)` arm in `TVM_FFI_SAFE_CALL_END`. The `EnvErrorAlreadySet` struct was a plain `std::exception` subclass, not part of the `Error` object system. This created asymmetry: every call site that checked return codes needed three branches, and the C ABI documented three possible return values.

The only real use case for `EnvErrorAlreadySet` was propagating Python `KeyboardInterrupt` (SIGINT) through C++ code during autotuning. The signal check (`TVMFFIEnvCheckSignals`) sets a Python exception and throws `EnvErrorAlreadySet` to unwind the C++ stack.

## Decision

Replace `EnvErrorAlreadySet` with a regular `Error` object:
- `EnvErrorAlreadySet()` becomes an inline function returning `Error("EnvErrorAlreadySet", "", "")`.
- The `catch (const EnvErrorAlreadySet&)` arm in `TVM_FFI_SAFE_CALL_END` is removed; the error is now caught as `Error` and stored in TLS via the normal `-1` path.
- The Python/Cython side checks `error.kind == "EnvErrorAlreadySet"` after `TVMFFIErrorMoveFromRaised`, and if true, raises the existing Python exception.
- Backward compatibility: the `-2` return code is still handled for a transitional period (marked with TODO for removal).

## Rationale

1. **Simplifies the C ABI**: Two return codes (0 and -1) instead of three. Cleaner for all language bindings.
2. **Removes boilerplate**: Every `TVM_FFI_SAFE_CALL_END` had a separate catch arm. Every `TVM_FFI_CALL_THEN_THROW` had a separate `-2` check. Both are eliminated.
3. **Consistent error object model**: All errors flow through the `Error` object system, making logging, cause chaining, and error introspection uniform.
4. **Limited blast radius**: Only downstream C++ code using `EnvErrorAlreadySet` is affected. The only known use case (autotuning KeyboardInterrupt) works identically since `EnvErrorAlreadySet()` still produces a throwable `Error`.

## Alternatives Considered

1. **Keep `-2` but make it carry an Error object**: Store the error in TLS even for `-2`. This was rejected as it would still require three-way branching in call sites.
2. **Remove EnvErrorAlreadySet entirely**: Drop the function and require callers to construct `Error("EnvErrorAlreadySet", ...)` manually. This was rejected for backward compatibility -- existing code calling `throw EnvErrorAlreadySet()` should continue to compile.

## Implementation Notes

- `include/tvm/ffi/error.h`: `EnvErrorAlreadySet` struct removed, replaced with `inline Error EnvErrorAlreadySet()`.
- `include/tvm/ffi/function.h`: `TVM_FFI_SAFE_CALL_END` no longer catches `EnvErrorAlreadySet`; `TVM_FFI_CALL_THEN_THROW` no longer checks `-2`.
- `include/tvm/ffi/c_api.h`: Error code `-2` documentation removed.
- `python/tvm_ffi/cython/error.pxi`, `function.pxi`, `type_info.pxi`: Check `error.kind == "EnvErrorAlreadySet"` after TLS retrieval; keep backward `-2` handling with TODO.

## Related Design Docs

- [`.knowledge/designs/0007-error-handling.md`](../designs/0007-error-handling.md)
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md)
- Commit: `.knowledge/commits/2026-02-03-b1611e0cf669518dd01367806ab0bfda7b20841d.md`
