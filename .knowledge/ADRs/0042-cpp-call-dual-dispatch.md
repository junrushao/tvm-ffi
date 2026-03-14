---
scope:
  - "0004-function-system"
  - "0001-c-abi"
---
# Add cpp_call to TVMFFIFunctionCell for Same-DLL Exception-Based Calls

**TL;DR**: `TVMFFIFunctionCell` gains a `void* cpp_call` field that stores a C++-style call pointer (throws exceptions on error). Same-DLL callers use `cpp_call` to bypass the `safe_call` error-code overhead; cross-DLL and C-origin callers use `safe_call` with `cpp_call = nullptr`.

## Context

The function system's dual `call`/`safe_call` design (ADR-0005) originally stored the C++ call pointer as a `FunctionObj::call` member field alongside `TVMFFIFunctionCell::safe_call`. This created several problems:

- `ImportedFunctionObjImpl` needed to redirect `call` through `safe_call` for cross-DLL functions, adding the `RedirectCallToSafeCall<Derived>` CRTP helper and `ImportFromExternDLL` static method.
- The C++-level `call` pointer was not accessible from the C ABI layer, since it was a C++ member above the `TVMFFIFunctionCell`.
- The `ImportedFunctionObjImpl` pattern added complexity for a use case (cross-DLL function import) that was rarely exercised.

Usecases:
- Same-DLL C++ code calling FFI functions can bypass error-code translation by using `cpp_call` directly, avoiding the `try/catch` overhead of `safe_call`.
- C-origin functions (from loaded modules) set `cpp_call = nullptr`, indicating that all calls must go through `safe_call`.

Design Decisions:
- Add `void* cpp_call` to `TVMFFIFunctionCell` in `c_api.h`, making the fast path visible at the C ABI level.
- `CallPacked` dispatches: if `cpp_call != nullptr`, call it directly (C++ exception path); otherwise, call `CppCallDedirectToSafeCall` which wraps `safe_call` with exception translation.
- Remove `FunctionObj::call` C++ member.
- Remove `ImportedFunctionObjImpl` and `ImportFromExternDLL` entirely.
- Add `ExternCFunctionObjNullHandleImpl` for the common case of raw C function pointers without closure.

## Implementation Notes

- `TVMFFIFunctionCell` now has two fields: `safe_call` (always set) and `cpp_call` (set for C++-origin functions, `nullptr` for C-origin).
- `TVM_FFI_DLL_EXPORT_TYPED_FUNC` signature updated: `args` parameter becomes `const TVMFFIAny*`.
- `FunctionObjImpl<TCallable>` sets `cpp_call` to a static C++ call function, `safe_call` wraps it with `TVM_FFI_SAFE_CALL_BEGIN/END`.
- `ExternCFunctionObjImpl` and `ExternCFunctionObjNullHandleImpl` set `cpp_call = nullptr`.

### Alternatives Considered

**Alternative A: Keep `call` as C++ member field (status quo)**
- Pros: No ABI change. C++ call path works.
- Cons: `call` pointer not visible at C ABI level. Requires `ImportedFunctionObjImpl` CRTP for cross-DLL functions.

**Alternative B: Always use `safe_call` (remove fast path)**
- Pros: Simpler, single call path.
- Cons: Forces `try/catch` overhead on every same-DLL call. Measurable overhead for high-frequency function invocations (e.g., per-element container operations).

### Consequences

- **ABI-breaking**: `TVMFFIFunctionCell` gains a field. All compiled code must be recompiled.
- **Simplification**: `ImportedFunctionObjImpl`, `RedirectCallToSafeCall`, and `ImportFromExternDLL` are removed, reducing the class hierarchy.
- **Rollback**: Reverting requires reintroducing `FunctionObj::call` member and `ImportedFunctionObjImpl`.

## Related Design Docs

- [`.knowledge/designs/0004-function-system.md`](../designs/0004-function-system.md) -- Function system and dual-entry object
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- `TVMFFIFunctionCell` C struct
- [`.knowledge/ADRs/0005-safe-call-abi-boundary.md`](0005-safe-call-abi-boundary.md) -- Original dual call/safe_call decision
- Commit: `.knowledge/commits/2025-09-29-4fe8b2b79dfeb469b2499acecb3e10038ddcee0f.md` + `4fe8b2b`
