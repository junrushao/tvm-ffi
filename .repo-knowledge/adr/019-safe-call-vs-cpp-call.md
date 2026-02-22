# ADR 019: Dual Call Pointer Design in TVMFFIFunctionCell (safe_call vs cpp_call)

- Status: Accepted
- Date: 2025-09-26
- Owners: Tianqi Chen

## Context

Cross-DLL function calls cannot safely throw C++ exceptions because different
DLLs may use different C++ runtimes or exception handling ABIs. All packed
function calls previously used `safe_call`, which catches exceptions at the
callee boundary, stores the error in thread-local storage (TLS), and returns
an integer error code. The caller then checks the return code and re-throws
from TLS if needed (`TVM_FFI_CHECK_SAFE_CALL`).

This catch-store-rethrow round-trip is correct but adds overhead. For
same-DLL calls (the hot path in most workloads), the caller and callee share
the same C++ runtime, so exception-safe wrapping is unnecessary.

## Decision

A second function pointer, `cpp_call`, was added to `TVMFFIFunctionCell`
alongside the existing `safe_call`:

```c
typedef struct {
  TVMFFISafeCallType safe_call;
  void* cpp_call;
} TVMFFIFunctionCell;
```

`safe_call` retains its original role: a C-ABI-compatible call that catches
exceptions and stores them in TLS, returning an integer error code. `cpp_call`
is a direct C++ call that throws exceptions normally instead of catching them.
Its signature matches `FunctionObj::FCall` (`void (*)(const FunctionObj*,
const AnyView*, int32_t, Any*)`), but is stored as `void*` in the C struct
to avoid depending on the C++ compiler.

`FunctionObj::CallPacked` dispatches through `cpp_call` when it is non-null,
falling back to `safe_call` otherwise:

```cpp
FCall call_ptr =
    this->cpp_call ? reinterpret_cast<FCall>(this->cpp_call) : CppCallDedirectToSafeCall;
(*call_ptr)(this, args, num_args, result);
```

The conditional expression is written so the compiler can lower it to a
branchless select.

Functions created within C++ (`FunctionObjImpl<TCallable>`) set both
`safe_call` and `cpp_call`. Functions originating from external C callbacks
(`ExternCFunctionObjImpl`, `ExternCFunctionObjNullHandleImpl`) set
`cpp_call = nullptr`, which causes `CallPacked` to route through
`CppCallDedirectToSafeCall`, a static method that forwards to `safe_call`
and re-throws via `TVM_FFI_CHECK_SAFE_CALL`.

## Consequences

- Positive: Near-zero overhead for same-DLL function calls. The hot path
  avoids exception catching, TLS storage, error-code checking, and
  re-throwing entirely.
- Positive: Cross-DLL calls remain correct and safe. They add only one
  pointer comparison versus prior behavior.
- Positive: The `safe_call` path is still available for `CallExpected`, which
  uses it to implement exception-free error handling without `cpp_call`.
- Negative: ABI-breaking change to `TVMFFIFunctionCell` (added `cpp_call`
  field). All consuming code must be rebuilt against the new headers.
- Negative: Two call paths increase the surface area for subtle bugs if a
  function incorrectly sets `cpp_call` for a cross-DLL callable.

## References
- Evidence commit: `4fe8b2b`
- Source: `include/tvm/ffi/c_api.h` (`TVMFFIFunctionCell` definition)
- Source: `include/tvm/ffi/function.h` (`FunctionObj::CallPacked`, `FunctionObjImpl`, `ExternCFunctionObjImpl`)

## Related Design Docs
- `.repo-knowledge/design/003-c-abi-stability.md`

## Notes
`FunctionObjImpl::SafeCall` delegates to `cpp_call` internally rather than
re-implementing the callable logic, ensuring the two paths share a single
code path for the actual function body. The only difference is whether
exceptions are caught (`safe_call`) or propagated directly (`cpp_call`).
