---
scope:
  - "0004-function-system"
  - "0001-c-abi-layer"
---
# Expose C++ Fast-Call Pointer in TVMFFIFunctionCell as Nullable cpp_call

**TL;DR**: The decision to move the C++ fast-call pointer from `FunctionObj::call` (a C++ class member) into `TVMFFIFunctionCell::cpp_call` (a `void*` at the C ABI level), with nullable semantics replacing the prior always-valid dual-pointer invariant.

## Context
- `FunctionObj` previously held two function pointers: `FCall call` (C++ exception-propagating) and `TVMFFISafeCallType safe_call` (C ABI exception-catching). Both were required to be non-null.
- The `call` pointer was only accessible from C++ code. Language bindings that loaded functions across DLL boundaries (via `ImportFromExternDLL`) needed a `RedirectCallToSafeCall` wrapper class that set `call` to a trampoline redirecting through `safe_call`. This added an extra heap-allocated wrapper object per imported function.
- Cross-DLL functions inherently cannot use the C++ `call` path (exceptions don't cross DLL boundaries). Making `call` nullable at the ABI level removes the need for wrapper objects.

Usecases:
- Loading functions from external shared libraries (`Function::FromExternC`) where only the C ABI safe_call is available.
- Lightweight wrapping of raw C function pointers without closure (`ExternCFunctionObjNullHandleImpl`).
- Exposing the C++ call pointer to potential future language bindings that can handle C++ exceptions.

Design Decisions:
- **`TVMFFIFunctionCell` gains `void* cpp_call`**: The C++ fast-call pointer is exposed at the C ABI level alongside `safe_call`. This makes both call paths visible to all language bindings, not just C++.
- **Nullable semantics**: `cpp_call` may be NULL for functions that only have a C ABI entry point. `CallPacked` checks `cpp_call != nullptr` and falls back to `CppCallDedirectToSafeCall` when NULL.
- **Removal of ImportFromExternDLL/ImportedFunctionObjImpl/RedirectCallToSafeCall**: These existed solely to provide a non-null `call` for cross-DLL functions. With nullable `cpp_call`, they are unnecessary.
- **ExternCFunctionObjNullHandleImpl added**: Lightweight `FunctionObj` for raw C function pointers with no closure (`self == nullptr, deleter == nullptr`), setting `cpp_call = nullptr`.

## Implementation Notes
- `FunctionObjImpl<TCallable>` constructor now sets `this->cpp_call = reinterpret_cast<void*>(CppCall)` instead of `this->call = Call`
- `FunctionObjImpl::SafeCall` dispatches through `self->cpp_call` (was in `FunctionObj` base)
- `ExternCFunctionObjImpl` sets `this->cpp_call = nullptr`; no longer inherits `RedirectCallToSafeCall`
- `TVM_FFI_DLL_EXPORT_TYPED_FUNC` args parameter changed from `TVMFFIAny*` to `const TVMFFIAny*`

## Related Design Docs
- [0004-function-system.md](../designs/0004-function-system.md) -- Function class hierarchy and CallPacked dispatch
- [0001-c-abi-layer.md](../designs/0001-c-abi-layer.md) -- TVMFFIFunctionCell C ABI struct
