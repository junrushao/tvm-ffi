---
adr: "0021"
title: "C-Level Argument Setter Dispatch for Python FFI Calls"
status: "accepted"
date: "2025-09-11"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python)"
tags:
  - "performance"
  - "python-interop"
source_commits:
  - "38d2cdaa03adc26a630e9cc3cc99b3c7e9f55097"
  - "043d9f647677cc3b4a8baba198a2ced45f99cc98"
source_ledgers:
  - ".memory/commits/2025-09-11-38d2cdaa.md"
  - ".memory/commits/2025-09-13-043d9f64.md"
---

# ADR-0021: C-Level Argument Setter Dispatch for Python FFI Calls

## TL;DR
- Python-to-C argument conversion is moved from per-argument Cython `isinstance` dispatch to a C-level cached dispatch table (`TVMFFIPyCallManager`) that maps `PyTypeObject*` to pre-built setter function pointers, amortizing type resolution cost to once per type per thread.
- Nested container arguments (list, tuple, dict) are recursively converted via `TVMFFIPyConstructorCall` within the same C call frame, eliminating the Python-level `_FUNC_CONVERT_TO_OBJECT` callback.

## Status
Accepted

## Context
The packed-function call path is the hottest path in the Python FFI. Every FFI call previously performed N `isinstance` checks in Cython for N arguments, with each check dispatching to Cython code that called Python C API functions. For small-kernel inference loops with 3-5 arguments per call, argument marshaling overhead dominated actual kernel execution time. Profiling showed that `isinstance` checks and Cython-level branching accounted for ~40% of per-call overhead.

Additionally, compound arguments (Python lists, tuples, dicts) triggered a `_FUNC_CONVERT_TO_OBJECT` callback that recursed back into Python to construct FFI Array/Map objects, adding Python frame overhead for each nesting level.

## Decision Drivers
- Per-call overhead must be minimized for ML inference hot paths (target: sub-microsecond argument marshaling for 3-5 POD arguments).
- The solution must cache type dispatch results across calls within a thread.
- Compound arguments must be convertible without Python-level callback round-trips.
- The approach must be thread-safe without requiring locks (hot path cannot afford synchronization).
- POD type conversion (int, float, bool, None) should execute entirely in C with no Cython dispatch.

## Decision
Introduce `TVMFFIPyCallManager`, a thread-local singleton containing:
1. A `std::unordered_map<PyTypeObject*, TVMFFIPyArgSetter>` dispatch map (initial capacity 32).
2. A `TVMFFIPyCallStack` with a pre-allocated 4KB argument buffer.
3. A `TVMFFIPyArgSetterFactory` callback (implemented in Cython) that creates setters on cache miss.

The call flow is:
1. `Function.__call__` packs Python args into a tuple and calls `TVMFFIPyFuncCall`.
2. For each argument, `SetArgument` looks up `Py_TYPE(arg)` in the dispatch map.
3. On cache hit: call the setter directly (C function pointer, no Python dispatch).
4. On cache miss: call the Cython factory to create a setter, cache it, then call it.
5. POD types have predefined C setters (`TVMFFIPyArgSetterInt_`, etc.) that never touch Cython.

For compound arguments, `TVMFFIPyConstructorCall` allocates a nested `TVMFFIPyCallContext` and recursively converts elements, calling the `ffi.Array` or `ffi.Map` constructor function directly. Context (device, stream, allocator) detected during nested conversion is propagated to the parent context.

## Alternatives Considered
### Keep Cython isinstance dispatch with micro-optimizations
- Pros: No new C++ code. Simpler maintenance.
- Cons: Cannot cache type dispatch results (isinstance is called every time). Cannot eliminate Python frame overhead for containers. Measured ~3x slower on benchmarks.

### Use Python's `tp_vectorcall` protocol
- Pros: Leverages CPython optimization for function calls.
- Cons: Applies to the function call itself, not to argument type dispatch. Does not help with the per-argument conversion problem. Requires Python 3.8+.

### Store setters in a Python `dict` instead of C++ `unordered_map`
- Pros: No C++ code needed. Cython can use a Python dict.
- Cons: Python dict lookup has higher overhead than C++ `unordered_map` (hash function, key comparison through Python C API). The dispatch map is accessed on every argument of every call, so even small overhead differences are amplified.

### Use a switch statement on `tp_flags` or type slots
- Pros: No hash map lookup.
- Cons: Python type flags do not map cleanly to FFI type indices. Many FFI types (NDArray, DataType, Device, PyNativeObject) share the same `tp_flags` values. Would still need a fallback hash map.

## Why This Option Won
- The `unordered_map<PyTypeObject*, setter>` approach has O(1) lookup with very low constant factor (pointer hashing, pointer comparison).
- Thread-local storage eliminates synchronization overhead entirely.
- The C-level stack allocation (`TVMFFIPyCallStack`) co-locates packed args with temp pointers for cache locality.
- The design is extensible: new types only need a factory extension, and the caching is automatic.
- Nested container conversion via `TVMFFIPyConstructorCall` eliminates the slowest part of compound argument handling.

## Consequences
### Positive
- Argument marshaling for POD-heavy calls (int, float) is effectively free after first call (pure C function pointer dispatch).
- Nested containers (list of ints, dict of strings) are converted without Python frame overhead.
- The 4KB pre-allocated stack avoids heap allocation for calls with up to ~256 arguments.
- The dispatch map size can be monitored via `TVMFFIPyGetDispatchMapSize()`.

### Negative
- Added code complexity: ~740 lines of C++ header code included in the Cython build.
- The dispatch map grows monotonically (no eviction). Long-running processes with many distinct Python types will accumulate entries.
- Debugging is harder: the actual setter function called for a given argument type is determined by the dispatch map, not by visible Cython code.

### Risks
- Factory correctness: if the `TVMFFIPyArgSetterFactory` returns a setter that is instance-specific rather than type-specific, cached dispatch will produce wrong results for subsequent instances. Mitigated by clear documentation and testing.
- Stack overflow for deeply nested containers: each nesting level allocates a `TVMFFIPyCallContext`. Mitigated by heap fallback when the stack is exhausted.

## Implementation Notes
- `tvm_ffi_python_helpers.h` is included via `cdef extern from` in `function.pxi`. It compiles as part of the Cython extension, not as a separate translation unit.
- `TVMFFIPyCallManager::ThreadLocal()` uses `thread_local` storage, which is supported on all target platforms (GCC, Clang, MSVC).
- The `TVMFFIPyCallContext` destructor uses `try/catch` to handle rare C++ exceptions during cleanup, converting them to Python errors via `PyErr_SetString`.
- Container setters create temporary Python tuples for constructor arguments. These tuples are pushed to the `extra_temp_py_objects_stack` for cleanup after the call.

## Validation
- `tests/python/test_function.py` tests argument marshaling for all types including nested containers.
- `scripts/benchmark_dlpack.py` benchmarks per-call overhead.
- `TVMFFIPyGetDispatchMapSize()` is callable from Python for diagnostics.

## Migration and Rollback
- No migration needed: the optimization is transparent to Python callers.
- Rollback would require reverting `function.pxi` to the pre-`38d2cdaa` Cython `make_args()` dispatch path and removing `tvm_ffi_python_helpers.h`.
- The `_FUNC_CONVERT_TO_OBJECT` callback would need to be restored for container conversion.

## Related Design Docs
- [.memory/designs/0015-python-ffi-call-optimization.md](.memory/designs/0015-python-ffi-call-optimization.md)
- [.memory/designs/0011-cython-binding-layer.md](.memory/designs/0011-cython-binding-layer.md)

## Related Diagrams
- [.memory/diagrams/0012-python-ffi-call-optimization-flow.md](.memory/diagrams/0012-python-ffi-call-optimization-flow.md)

## Evidence Matrix
- `TVMFFIPyCallManager` with dispatch map -> `.memory/commits/2025-09-11-38d2cdaa.md` + `38d2cdaa` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- `TVMFFIPyArgSetter` struct -> `38d2cdaa` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h` lines 162-189
- `TVMFFIPyFuncCall` entry point -> `38d2cdaa` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h` lines 497-504
- Predefined POD setters -> `38d2cdaa` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h` lines 195-229
- `TVMFFIPyConstructorCall` for nested containers -> `.memory/commits/2025-09-13-043d9f64.md` + `043d9f64` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- Container setters (Tuple, TupleLike, Map) -> `043d9f64` + `python/tvm_ffi/cython/function.pxi`
- `_FUNC_CONVERT_TO_OBJECT` removal -> `043d9f64` + `python/tvm_ffi/cython/function.pxi`
- `TVMFFIStringFromByteArray` / `TVMFFIBytesFromByteArray` -> `043d9f64` + `include/tvm/ffi/c_api.h`

## Supersedes
None (this is a new approach; the previous `make_args()` dispatch was not documented as an ADR)

## Superseded By
None

## Follow-up Actions
- Consider adding dispatch map eviction for very long-running processes.
- Profile the factory callback cost to determine if it is worth optimizing (currently Cython, could be moved to C).
- Evaluate whether the dispatch map should use a robin-hood or Swiss table implementation for even faster lookup.
