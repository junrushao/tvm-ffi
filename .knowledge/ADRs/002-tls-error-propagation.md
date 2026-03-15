# ADR-002: TLS-Based Error Propagation in C ABI

> Status: Accepted
> Decided in: commit 7d34eb8 ("[REFACTOR] Introduce and modernize FFI system")

## Context

The C ABI needs a way to propagate structured error objects (with kind, message,
and traceback) across function call boundaries. Two main approaches exist:

1. **Return-argument style**: Pass an error output pointer as a function argument.
   Each function signature gains an extra `TVMFFIObjectHandle* error` parameter.
2. **TLS style**: Store the error in thread-local storage. The callee sets it,
   the caller retrieves it.

## Decision

Use TLS-based error propagation via `TVMFFIErrorSetRaised` / `TVMFFIErrorMoveFromRaised`.

The calling convention returns an integer status code:
- `0`: success
- `-1`: error stored in TLS (retrieve via `TVMFFIErrorMoveFromRaised`)
- `-2`: frontend error already set (e.g., Python signal)

From the C ABI header comment:
> "We decided to leverage TVMFFIErrorMoveFromRaised and TVMFFIErrorSetRaised
> for C function error propagation. This design choice, while introducing a
> dependency for TLS runtime, simplifies error propagation in chains of calls
> in compiler codegen. As we do not need to propagate error through argument
> but simply set them in the runtime environment."

## Consequences

### Positive

- Simplifies codegen for chains of calls: intermediate code only checks a return
  code, does not need to forward error pointers
- The `TVMFFISafeCallType` signature stays clean: `(void* self, const TVMFFIAny* args,
  int32_t num_args, TVMFFIAny* result)` -- no extra error parameter
- Error objects are full `ErrorObj` instances with kind, message, and traceback,
  not just error codes or strings
- The `-2` return code handles frontend-signaled errors (Python signals) without
  needing to allocate an error object in the FFI layer

### Negative

- Requires TLS runtime support (may be problematic on some embedded platforms)
- Not thread-safe if the same thread makes nested FFI calls that both error
  (the inner error would overwrite the outer) -- mitigated by the convention
  that callers immediately retrieve errors after a -1 return
- Single-error-per-thread model does not support error chaining natively

### Neutral

- Compatible with the C++ exception model: `TVM_FFI_SAFE_CALL_BEGIN/END` catches
  C++ exceptions and stores them in TLS, while `TVM_FFI_CHECK_SAFE_CALL` retrieves
  them and rethrows
