---
scope:
  - "0019-python-ffi-call-dispatch"
---
# Generic Value Protocols (`__tvm_ffi_value__`, `__tvm_ffi_int__`, `__tvm_ffi_float__`)

**TL;DR**: Three opt-in Python dunder protocols allow arbitrary Python classes to participate in FFI argument dispatch without modifying the core dispatch chain: `__tvm_ffi_int__` and `__tvm_ffi_float__` for numeric types, and `__tvm_ffi_value__` as a generic fallback that returns any FFI-compatible Python value.

## Context

The existing `TVMFFIPyArgSetterFactory_` dispatch chain handles known types (Tensor, Object, int, float, str, etc.) but has no extension point for third-party Python types (e.g., `numpy.int32`, framework-specific scalars, custom enum types) to integrate without modifying the core Cython code.

Usecases:
- Allowing `numpy.int32`/`numpy.float64` to pass through FFI calls as integers/floats without explicit conversion.
- Enabling custom types (e.g., `torch.Tensor` device indices, ML framework scalars) to participate in FFI dispatch.
- Providing a generic escape hatch for any Python object that knows how to convert itself to an FFI-compatible value.

Design Decisions:
- **Three-tier protocol**: `__tvm_ffi_int__` -> `__tvm_ffi_float__` -> `__tvm_ffi_value__`, checked in that order in the factory fallback path. Integer and float protocols are separate because they map to distinct C-level setter functions (no Python intermediary needed).
- **`__tvm_ffi_value__` returns a Python object**: The protocol method returns a new Python object that is then dispatched through the generic dispatcher (`TVMFFIPySetArgumentGenericDispatcher`). This enables arbitrary conversion chains (e.g., a custom type -> tvm_ffi.Tensor).
- **Extra temporary stack**: Because `__tvm_ffi_value__` creates a temporary Python object that must survive until the FFI call completes, a new `extra_temp_py_objects_stack` was added to `TVMFFIPyCallStack` (separate from the per-argument temp budget).
- **Refactored call stack**: `TVMFFIPyCallContext` was promoted from an inner class of `TVMFFIPyCallManager` to a standalone class, with `TVMFFIPyCallStack` managing the thread-local memory. This enables the extra temp stack to be shared across nested calls.

Alternatives considered:
- **Extend isinstance chain**: Would require modifying core Cython code for each new type. Not scalable.
- **Single `__tvm_ffi_value__` protocol only**: Simpler but would add Python method dispatch overhead for common numeric types that could be handled more efficiently.

## Implementation Notes

- `TVMFFIPyArgSetterIntProtocol_` calls `arg.__tvm_ffi_int__()` and writes the result directly as int64.
- `TVMFFIPyArgSetterFloatProtocol_` calls `arg.__tvm_ffi_float__()` and writes as float64.
- `TVMFFIPyArgSetterFFIValueProtocol_` calls `arg.__tvm_ffi_value__()`, pushes the result to `extra_temp_py_objects_stack` for lifetime management, then re-dispatches.
- `numbers.Integral` and `numbers.Real` handling was moved to a more conservative fallback path, with the custom protocols taking priority.

## Related Design Docs

- [`.knowledge/designs/0019-python-ffi-call-dispatch.md`](../designs/0019-python-ffi-call-dispatch.md)
- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md)
- Evidence: `.knowledge/commits/2025-12-04-3dd7a8173363bdf79806610818121e83e99b3b56.md` + `3dd7a81`
- Evidence: `.knowledge/commits/2025-11-08-c1df05f3555d4e2a9e1a32822c0f41ccb8467251.md` + `c1df05f`
