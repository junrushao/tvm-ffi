---
scope:
  - "0019-python-ffi-call-dispatch"
  - "0014-python-bindings"
---
# Type-Dispatched Argument Setter (TVMFFIPyCallManager)

**TL;DR**: Replaces the O(n) `isinstance`-chain in Cython `make_args` with a C++ type-dispatched call manager that caches per-`PyTypeObject*` setter function pointers in a thread-local hash map, achieving O(1) argument dispatch on repeat calls.

## Context

The Cython `make_args` function performed a 20-item `isinstance` priority chain per argument on every FFI call. For hot paths (e.g., repeated calls with the same `(int, torch.Tensor, int)` signature), the cumulative `isinstance` overhead was a significant fraction of total call time. Temporary arguments were tracked in a Python `list`, adding allocation and `append` overhead.

Usecases:
- Training loops calling FFI kernels with torch.Tensor arguments millions of times per epoch.
- Short-running FFI functions (e.g., shape queries) where call overhead dominates computation time.
- Nested container conversion (list/dict of tensors) where each element re-enters the dispatch chain.

Design Decisions:
- Move from Cython `isinstance`-chain to C++ `unordered_map<PyTypeObject*, TVMFFIPyArgSetter>` with thread-local storage.
- Introduce a factory/setter/manager three-layer architecture where the factory (Cython) classifies types once and the setter (C/C++ function pointer) handles all subsequent instances.
- Pre-allocate a thread-local C++ stack for packed arguments and temporary tracking, with heap fallback for large argument lists.
- Define POD-type setters (`int`, `float`, `bool`, `None`) directly in C++ using CPython API, avoiding Cython overhead for the most common types.

## Alternatives

### 1. Cython-level caching with Python `dict[type, callable]`
- Pros: Stays in readable Cython. Easier debugging.
- Cons: Python dict lookup (~100ns) vs C++ unordered_map (~20ns). Python function call overhead per setter. Does not eliminate Python list for temporaries.

### 2. Typed function wrappers (per-signature specialization)
- Pros: Zero dispatch overhead for known signatures.
- Cons: Combinatorial explosion. Cannot handle dynamic argument types.

### 3. Keep `isinstance`-chain (status quo before `38d2cda`)
- Pros: Simple, readable, proven.
- Cons: O(n) per argument. Measurable overhead on hot paths. Python list allocation for temporaries.

## Decision

Option 1 (C++ type-dispatched caching) was chosen. Key constraint: the `TVMFFIPyArgSetterFactory` callback must produce a setter correct for _all_ instances of a `PyTypeObject*`, not just the specific instance. This type-level caching invariant holds because FFI semantics are determined by Python type identity, not by value.

## Implementation Notes

- `tvm_ffi_python_helpers.h` (447 lines at introduction) is included in the Cython build via `target_include_directories(tvm_ffi_cython PRIVATE)`.
- Call sites (`Function.__call__`, `ConstructorCall`, `FieldSetter.__call__`, `tvm_ffi_callback`) delegate to C++ inline functions (`TVMFFIPyFuncCall`, `TVMFFIPyCallFieldSetter`, `TVMFFIPyPyObjectToFFIAny`).
- GIL release moved from Cython `with nogil` to C++ `Py_BEGIN_ALLOW_THREADS`/`Py_END_ALLOW_THREADS`, controlled by `Function.release_gil` property.

## Consequences

- **Performance**: O(1) argument dispatch on repeat calls. Pre-allocated stack eliminates Python list overhead.
- **Debugging**: Critical dispatch logic moved from readable Cython to C++. Type-related bugs may be harder to diagnose.
- **Build dependency**: The Cython extension now depends on a C++ header (`tvm_ffi_python_helpers.h`), tightening the build coupling.
- **Migration**: The old `make_args` function, `FuncCall`, `FuncCall3`, and `temp_args` Python list are fully removed.
- **Rollback**: Would require reverting to the `isinstance`-chain pattern and re-introducing `make_args`.

## Related Design Docs

- [`.knowledge/designs/0019-python-ffi-call-dispatch.md`](../designs/0019-python-ffi-call-dispatch.md) -- Full design of the call dispatch system
- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Python bindings package
- Commit: `.knowledge/commits/2025-09-11-38d2cdaa03adc26a630e9cc3cc99b3c7e9f55097.md` + `38d2cda`
