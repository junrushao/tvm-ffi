---
scope:
  - "0004-function-system"
  - "0007-error-handling"
  - "0001-c-abi"
---
# Dual call/safe_call Design for FunctionObj

**TL;DR**: Every `FunctionObj` has two entry points: `call` (C++ path, propagates exceptions naturally) and `safe_call` (C path, catches exceptions and stores them in TLS). This dual design provides idiomatic error handling in both C++ and C contexts without forcing either side to use the other's convention.

## Context

The FFI must support function calls from three contexts:

1. **C++ to C++ (same DLL)**: Exceptions can propagate naturally. Adding try/catch at every call site would be wasteful.
2. **C++ to C boundary (cross DLL)**: Exceptions cannot cross C ABI boundaries (undefined behavior on most platforms). Errors must be translated to return codes.
3. **C to C++ (language bindings calling into C++ via C API)**: The C caller expects error codes, not exceptions.

A single calling convention would force one of these contexts to use an unnatural error handling pattern.

Usecases:
- C++ code calling `Function::operator()(args...)` uses the `call` path -- exceptions propagate naturally, no try/catch overhead.
- Python calling a C++ function goes through `TVMFFIFunctionCall` -> `safe_call` -> catch -> TLS error -> return code -> Python checks error.
- A C++ function importing a function from another DLL uses `ImportedFunctionObjImpl`, which redirects `call` through `safe_call` to safely cross the DLL boundary.

Design Decisions:
- **Two function pointers per FunctionObj**: `call` (`FCall`: C++ path) and `safe_call` (`TVMFFISafeCallType`: C path). Both are stored as function pointers in the object, not virtual methods, because the C ABI cannot use vtables.
- **safe_call catches all exceptions**: `TVM_FFI_SAFE_CALL_END` catches `Error` (stores in TLS, returns -1), `EnvErrorAlreadySet` (returns -2), and `std::exception` (wraps in `Error("InternalError", ...)`, returns -1).
- **call delegates to callable directly**: For `FunctionObjImpl<TCallable>`, `call` directly invokes `callable_(args, num_args, rv)` with no try/catch. Exceptions propagate to the C++ caller.
- **RedirectCallToSafeCall for imported functions**: When a function comes from another DLL, `call` is implemented as: invoke `safe_call`, check return code, rethrow if error. This ensures exceptions are properly caught and re-thrown at the DLL boundary.

**Alternatives considered**:

1. **Error codes everywhere (no exceptions in C++)**:
   - Pros: Single calling convention, works in `-fno-exceptions` builds.
   - Cons: Every C++ function must check and propagate error codes. Natural C++ control flow (RAII, destructors, exception safety) is lost. Rejected because C++ ergonomics matter for the large body of compiler code that uses the FFI.

2. **setjmp/longjmp for cross-boundary exception transport**:
   - Pros: No TLS dependency, can "throw" across C boundaries.
   - Cons: `longjmp` skips C++ destructors, violating RAII guarantees. This would corrupt any RAII-managed resources (locks, smart pointers, file handles) between the `setjmp` and `longjmp` sites. Rejected for safety.

3. **C++ exceptions across DLL boundaries (relying on same runtime)**:
   - Pros: Simplest implementation -- just let exceptions fly.
   - Cons: Undefined behavior when DLLs are compiled with different compilers, runtimes, or exception ABIs. Does not work for C callers at all. Rejected for portability.

**Consequences**:
- Every `FunctionObj` carries two function pointers (16 bytes of overhead per function object -- 8 for `call`, 8 for `safe_call`).
- Three distinct `FunctionObj` implementations (`FunctionObjImpl`, `ExternCFunctionObjImpl`, `ImportedFunctionObjImpl`) with different wiring of `call`/`safe_call`.
- Same-DLL C++ calls have zero overhead (direct function pointer call, no exception translation).
- Cross-DLL calls pay the cost of one try/catch per call (only on the error path, which is cold).

## Implementation Notes

- `FunctionObj::SafeCall` (the default safe_call): wraps `self->call(...)` in `TVM_FFI_SAFE_CALL_BEGIN/END`.
- `ExternCFunctionObjImpl`: wraps a C-style `(void* self, TVMFFISafeCallType, deleter)` triple. `call` redirects through `safe_call` because the C callback only provides safe_call semantics.
- `ImportedFunctionObjImpl`: wraps another `FunctionObj` from a different DLL. `call` and `safe_call` both redirect through the wrapped object's `safe_call` pointer.
- `ImportFromExternDLL` detects same-DLL functions by comparing `safe_call` pointers against `FunctionObj::SafeCall`, `ImportedFunctionObjImpl::SafeCall`, and `ExternCFunctionObjImpl::SafeCall`.
- Evidence: `include/tvm/ffi/function.h:84-115` (FunctionObj dual entry), `include/tvm/ffi/function.h:46-78` (SAFE_CALL macros), `include/tvm/ffi/function.h:169-214` (ExternC and Imported implementations), commit `7d34eb8`.

## Related Design Docs

- [`.knowledge/designs/0004-function-system.md`](../designs/0004-function-system.md) -- Full function system design
- [`.knowledge/designs/0007-error-handling.md`](../designs/0007-error-handling.md) -- SafeCallContext and exception transport
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- TVMFFISafeCallType and error return codes
