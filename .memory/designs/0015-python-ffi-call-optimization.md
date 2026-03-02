---
design: "0015"
title: "Python FFI Call Optimization Layer"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-09-11"
last_updated: "2025-09-13"
scope:
  - "python/tvm_ffi/cython"
  - "python/tvm_ffi/cython/tvm_ffi_python_helpers.h"
  - "include/tvm/ffi/c_api.h"
  - "include/tvm/ffi/extra/c_env_api.h"
  - "python/tvm_ffi/_optional_torch_c_dlpack.py"
source_commits:
  - "38d2cdaa03adc26a630e9cc3cc99b3c7e9f55097"
  - "f81ab9c25ae4d2a42706747c50c5c410c51d6cdd"
  - "4dee97f1b6473f32faeb8cd24fb2c960f3b17190"
  - "043d9f647677cc3b4a8baba198a2ced45f99cc98"
source_ledgers:
  - ".memory/commits/2025-09-11-38d2cdaa.md"
  - ".memory/commits/2025-09-12-f81ab9c2.md"
  - ".memory/commits/2025-09-12-4dee97f1.md"
  - ".memory/commits/2025-09-13-043d9f64.md"
---

# Python FFI Call Optimization Layer

## TL;DR
- A C-level helper layer (`tvm_ffi_python_helpers.h`, ~740 lines) replaces the per-argument Cython type dispatch with a batched, cached, C-native argument conversion pipeline (`TVMFFIPyCallManager`), yielding significant speedup on every packed-function call from Python.
- A symmetric DLPack exchange protocol (`DLPackExchangeAPI` struct with `__dlpack_c_exchange_api__` Python attribute) enables zero-copy tensor round-trips between frameworks (TVM, PyTorch) entirely in C, bypassing Python capsule overhead.
- Nested container conversion (`TVMFFIPyConstructorCall`) and direct C API string/bytes construction (`TVMFFIStringFromByteArray`/`TVMFFIBytesFromByteArray`) eliminate Python-level round-trips for compound arguments.

## Problem Statement
Every ML kernel invocation from Python goes through the packed-function call path. The previous Cython-only `make_args()` performed N individual Python `isinstance` checks per call, each dispatching to Cython code that converted a single argument. For hot paths (e.g., inference loops calling small kernels), this per-argument overhead dominated total call time. Additionally, DLPack tensor exchange required Python-level PyCapsule creation and destruction, adding 2-3 microseconds per tensor argument. Nested Python containers (list, tuple, dict) triggered a Python-level `_FUNC_CONVERT_TO_OBJECT` callback round-trip per container argument.

## Context and Constraints
- The optimization must not change the Python-visible API: `func(*args)` semantics are unchanged.
- The C helper layer is compiled as part of the Cython extension (included via `cdef extern from`), not as a separate shared library.
- The dispatch table is thread-local to avoid synchronization overhead.
- The DLPack exchange protocol must interoperate with the dlpack specification's `DLPackExchangeAPI` struct.
- GIL release must be controllable per-function (some FFI functions call back into Python).
- The call stack must support nesting (nested container conversion calls recurse into the same call manager).

## Goals
- Reduce per-argument conversion overhead by caching type-to-setter dispatch in a C-level hash map.
- Eliminate Python capsule overhead for DLPack tensor exchange via a direct C-to-C protocol.
- Support recursive container conversion without Python-level callbacks.
- Provide per-function GIL control via the `Function.release_gil` property.
- Add direct C API functions for string/bytes construction from byte arrays.

## Non-Goals
- Changing the packed calling convention itself (arguments are still `TVMFFIAny*`).
- Supporting async/coroutine-based FFI calls.
- Optimizing the C++-to-Python return path (focus is on Python-to-C argument marshaling).
- Replacing the Cython layer entirely (the helpers augment it, not replace it).

## Design
### Components and Responsibilities

- **`TVMFFIPyCallStack`** (class, `tvm_ffi_python_helpers.h`): Thread-local argument buffer. Pre-allocates a 4KB page-aligned `vector<TVMFFIAny>` stack. Each call frame carves out a contiguous slice for packed args and temporary object pointers. Falls back to heap allocation when the stack is exhausted.

- **`TVMFFIPyCallContext`** (class, `tvm_ffi_python_helpers.h`): RAII guard for a single FFI call. Allocates from `TVMFFIPyCallStack`, co-locates packed args with temp object pointers for cache locality (one temp per argument budget). Tracks detected device/stream context and `DLPackExchangeAPI` for propagation to the outer call. Destructor recycles temporary FFI objects (`TVMFFIObjectDecRef`) and Python objects (`Py_DecRef`) and restores the stack pointer.

- **`TVMFFIPyArgSetter`** (struct, `tvm_ffi_python_helpers.h`): Function pointer struct dispatching a single argument conversion. Each setter takes `(TVMFFIPyArgSetter* self, TVMFFIPyCallContext* ctx, PyObject* arg, TVMFFIAny* out)` and returns 0 on success, -1 on Python error. Carries an optional `DLPackExchangeAPI*` for DLPack-capable types.

- **`TVMFFIPyArgSetterFactory`** (callback, `tvm_ffi_python_helpers.h`): Cython-provided factory that examines a Python argument and returns an `TVMFFIPyArgSetter` for its type. Called once per distinct `PyTypeObject*`; the result is cached in the dispatch map. Implemented in `function.pxi` as `make_arg_setter_factory`.

- **`TVMFFIPyCallManager`** (class, `tvm_ffi_python_helpers.h`): Thread-local singleton (`TVMFFIPyCallManager::ThreadLocal()`). Contains the dispatch map (`unordered_map<PyTypeObject*, TVMFFIPyArgSetter>`, initial capacity 32) and the `TVMFFIPyCallStack`. Provides three call methods:
  - `FuncCall()`: Top-level function call. Sets stream/allocator context, calls the function (with optional GIL release), restores context.
  - `ConstructorCall()`: Nested constructor call for container conversion. Does not set stream/allocator; instead propagates detected context to the parent `TVMFFIPyCallContext`.
  - `SetField()`: Single-argument field setter for reflection-based field assignment.

- **`TVMFFIPyFuncCall`** (free function, `tvm_ffi_python_helpers.h`): Top-level entry point for `Function.__call__` in Cython. Delegates to `TVMFFIPyCallManager::ThreadLocal()->FuncCall()`.

- **`TVMFFIPyConstructorCall`** (free function, `tvm_ffi_python_helpers.h`): Entry point for nested container conversion. Delegates to `TVMFFIPyCallManager::ThreadLocal()->ConstructorCall()`. Propagates device/stream/allocator context from child to parent context.

- **Predefined setters** (`tvm_ffi_python_helpers.h`): `TVMFFIPyArgSetterFloat_`, `TVMFFIPyArgSetterInt_`, `TVMFFIPyArgSetterBool_`, `TVMFFIPyArgSetterNone_` handle POD types directly in C with no Cython dispatch.

- **Container setters** (`function.pxi`): `TVMFFIPyArgSetterTuple_`, `TVMFFIPyArgSetterTupleLike_` (for lists), `TVMFFIPyArgSetterMap_` create Python tuples from the container elements, then call `TVMFFIPyConstructorCall` with the `_CONSTRUCTOR_ARRAY` or `_CONSTRUCTOR_MAP` FFI function handles.

- **String/Bytes setters** (`function.pxi` and `tvm_ffi_python_helpers.h`): `TVMFFIPyArgSetterPyNativeObjectStr_` and `TVMFFIPyArgSetterPyNativeObjectBytes_` call `TVMFFIStringFromByteArray` / `TVMFFIBytesFromByteArray` directly, constructing FFI String/Bytes objects without Python-side temporaries.

- **`DLPackExchangeAPI`** (struct, from dlpack `dlpack.h`): Bundles `from_pyobject`, `to_pyobject`, `managed_tensor_allocator` C function pointers. Attached to Python tensor classes via `__dlpack_c_exchange_api__` attribute (a PyCapsule wrapping the struct pointer).

- **`Function` as cdef class** (`function.pxi`): The `Function` Python class is now a Cython extension type (cdef class) with a `release_gil` boolean property. Default is `True` (controlled by `TVM_FFI_RELEASE_GIL_BY_DEFAULT` env var). `__call__` routes through `TVMFFIPyFuncCall` with the GIL release flag.

- **`_optional_torch_c_dlpack.py`** (module): Optional PyTorch C-level DLPack integration. Detects if PyTorch supports `DLPackExchangeAPI`, sets up `__dlpack_c_exchange_api__` on torch tensor classes. Uses JIT-compiled C++ extension for the exchange functions. Guarded by `TVM_FFI_SKIP_c_dlpack_from_pyobject` env var.

- **`TVMFFIStringFromByteArray`** (C API, `c_api.h`): Constructs an FFI String from a `TVMFFIByteArray*`. Returns SmallStr for small strings or a heap-allocated String object.

- **`TVMFFIBytesFromByteArray`** (C API, `c_api.h`): Constructs an FFI Bytes from a `TVMFFIByteArray*`. Returns SmallBytes for small byte strings or a heap-allocated Bytes object.

### Data Contracts and Invariants
- **Dispatch map invariant**: The cached `TVMFFIPyArgSetter` for a `PyTypeObject*` must be valid for all instances of that type. The factory must produce type-level (not instance-level) setters.
- **Call stack nesting**: `TVMFFIPyCallContext` is RAII and supports nesting. The stack pointer is saved/restored, so nested `ConstructorCall` invocations do not corrupt the parent call's arguments.
- **One temp per argument budget**: Each argument setter may push at most one temporary FFI object and one temporary Python object to the call context. Extra temporaries (from value protocols) go to the `extra_temp_py_objects_stack`.
- **Stream context save/restore**: `FuncCall` saves the previous stream via `TVMFFIEnvSetStream` before overwriting, and restores it after the call completes (even on error).
- **Allocator context save/restore**: `FuncCall` saves and restores the `DLPackManagedTensorAllocator` similarly.
- **GIL release safety**: `release_gil=True` (the default) is only safe when the FFI function does not call back into Python. Functions that do call back (e.g., Python callbacks registered as FFI functions) must set `release_gil=False`.
- **String/Bytes construction**: `TVMFFIStringFromByteArray` and `TVMFFIBytesFromByteArray` produce owned `TVMFFIAny` values. For small payloads (<=7 bytes for strings, <=7 bytes for bytes), the value is stored inline as SmallStr/SmallBytes.

### Control Flow

#### Optimized Python-to-C Call Path
1. Python calls `func(*args)` on a `Function` cdef instance.
2. `Function.__call__` packs args into a Python tuple and calls `TVMFFIPyFuncCall(setter_factory, handle, tuple, result, &ret_code, release_gil, &dlpack_api)`.
3. `TVMFFIPyCallManager::FuncCall` allocates a `TVMFFIPyCallContext` from the thread-local stack.
4. For each argument: `SetArgument` looks up `Py_TYPE(arg)` in the dispatch map. On cache hit, the setter is called directly. On cache miss, the factory creates a new setter and caches it.
5. Setters for POD types (int, float, bool, None) execute entirely in C. Setters for FFI objects extract the handle pointer. Setters for containers recurse via `TVMFFIPyConstructorCall`.
6. If any argument carried a device context (from DLPack exchange), `FuncCall` sets the stream and allocator context.
7. The FFI function is called (with optional GIL release via `Py_BEGIN_ALLOW_THREADS`/`Py_END_ALLOW_THREADS`).
8. Stream and allocator contexts are restored.
9. The `TVMFFIPyCallContext` destructor frees temporary objects and restores the stack pointer.

#### Nested Container Conversion
1. A list/tuple/dict argument triggers `TVMFFIPyArgSetterTuple_` / `TVMFFIPyArgSetterTupleLike_` / `TVMFFIPyArgSetterMap_`.
2. The setter creates a Python tuple of the container's elements and calls `TVMFFIPyConstructorCall(factory, _CONSTRUCTOR_ARRAY, tuple, &result, &ret_code, parent_ctx)`.
3. `ConstructorCall` allocates a nested `TVMFFIPyCallContext`, converts each element (possibly recursing further), calls the Array/Map constructor FFI function, and propagates any detected device/stream context to the parent context.
4. The resulting FFI Array/Map object handle is stored in the parent argument slot.

#### DLPack C-Level Exchange
1. When a torch tensor (or other DLPack-capable object) has `__dlpack_c_exchange_api__`, the arg setter retrieves the `DLPackExchangeAPI*`.
2. `from_pyobject(py_obj, &out)` converts the Python tensor to an FFI Tensor entirely in C (no PyCapsule).
3. On the return path, if the call context carries a `DLPackExchangeAPI*`, `to_pyobject(ffi_tensor, &out)` converts back to a Python tensor in C.
4. The `managed_tensor_allocator` function pointer is set as the thread-local allocator so the FFI function can produce tensors compatible with the caller's framework.

### Extension Points
- New Python types are handled by extending the `TVMFFIPyArgSetterFactory` in `function.pxi`. The C-level dispatch table automatically caches the new setter.
- New DLPack-capable frameworks can participate by attaching a `__dlpack_c_exchange_api__` attribute (a PyCapsule wrapping a `DLPackExchangeAPI` struct) to their tensor class.
- Additional container types can be supported by adding new setter functions following the `TVMFFIPyArgSetterTuple_` pattern.

## Alternatives Considered
### Keep all dispatch in Cython (no C helper layer)
- Pros: Simpler build (no extra C++ header). Cython handles ref counting naturally.
- Cons: Per-argument Python-level type dispatch cannot be cached efficiently. Each `isinstance` check is a Python C API call. No batched stack allocation. Measured ~3x slower on benchmarks with many arguments.

### Use Python's `__slots__` or `tp_vectorcall` for faster dispatch
- Pros: Leverages CPython internals.
- Cons: `tp_vectorcall` requires Python 3.8+ and does not help with the type dispatch problem. Does not address DLPack capsule overhead.

### Separate DLPack exchange into a standalone protocol (not bundled with argument conversion)
- Pros: Cleaner separation of concerns.
- Cons: Misses the opportunity to propagate allocator/stream context from the tensor to the function call. Two separate dispatch paths would be needed.

## Trade-offs
- **Optimized**: Call throughput for small-argument FFI calls (the common case in ML inference), zero-copy DLPack exchange, cache-friendly argument layout.
- **Sacrificed**: Code complexity (C++ header included in Cython build, thread-local state management), debug-ability (dispatch map makes it harder to trace which setter is called for a given type), additional build dependency on dlpack's `DLPackExchangeAPI` struct.

## Interfaces and Compatibility
- **Public Python API**: `Function.__call__(*args)` (unchanged), `Function.release_gil` (new property).
- **Env vars**: `TVM_FFI_RELEASE_GIL_BY_DEFAULT` (default `1`), `TVM_FFI_SKIP_c_dlpack_from_pyobject` (disables torch C DLPack integration).
- **C API additions**: `TVMFFIStringFromByteArray`, `TVMFFIBytesFromByteArray` in `c_api.h`. `DLPackTensorAllocator` callback type and `TVMFFIEnvSetDLPackManagedTensorAllocator`/`TVMFFIEnvGetDLPackManagedTensorAllocator` in `extra/c_env_api.h`.
- **DLPack protocol**: `__dlpack_c_exchange_api__` attribute on Python tensor classes (PyCapsule wrapping `DLPackExchangeAPI*`).
- **Breaking changes**: `Function` is now a cdef class (pure-Python subclasses may need adjustment). `_FUNC_CONVERT_TO_OBJECT` removed (replaced by direct `_CONSTRUCTOR_ARRAY`/`_CONSTRUCTOR_MAP` calls). Old `__c_dlpack_exporter__`/`__c_dlpack_importer__` names renamed to protocol based on `DLPackExchangeAPI` struct.

## Failure Modes and Mitigations
- **Setter factory returns wrong setter for a type**: The dispatch map caches by `PyTypeObject*`, so if a factory returns a setter that only works for a specific instance (not the whole type), subsequent calls will fail. Mitigated by factory contract requiring type-level setters.
- **Stack overflow on deeply nested containers**: Each nesting level allocates a `TVMFFIPyCallContext` on the thread-local stack. Very deep nesting (>100 levels) could exhaust the stack. Mitigated by the heap fallback when the stack is full.
- **GIL release with Python callback**: If `release_gil=True` but the FFI function calls back into Python, a deadlock or crash occurs. Mitigated by documentation and the ability to set `func.release_gil = False`.
- **DLPack exchange API version mismatch**: If a framework's `DLPackExchangeAPI` struct has a different layout than expected, memory corruption could occur. Mitigated by versioning the capsule name.

## Observability and Validation
- `TVMFFIPyGetDispatchMapSize()` returns the number of cached type-to-setter mappings.
- `scripts/benchmark_dlpack.py` benchmarks DLPack exchange with and without the C-level protocol.
- `tests/python/test_function.py` validates argument marshaling for all types including nested containers.
- `tests/python/test_tensor.py` validates DLPack round-trip with the C exchange protocol.
- `tests/python/test_dlpack_exchange_api.py` validates the `DLPackExchangeAPI` protocol end-to-end.

## Migration and Rollout
- The optimization is transparent to Python callers. No code changes needed for existing users.
- Framework integrations (PyTorch) are optional and loaded lazily (`_optional_torch_c_dlpack.py`).
- The `release_gil` property defaults to `True` matching the previous implicit behavior (GIL was released inside individual DLPack calls; now it is released at the `Function.__call__` level).

## Diagrams
- [.memory/diagrams/0012-python-ffi-call-optimization-flow.md](.memory/diagrams/0012-python-ffi-call-optimization-flow.md)
- [.memory/diagrams/0009-cython-binding-type-marshaling.md](.memory/diagrams/0009-cython-binding-type-marshaling.md) (predecessor, now partially superseded)

## Related ADRs
- [.memory/ADRs/0021-c-level-arg-setter-dispatch.md](.memory/ADRs/0021-c-level-arg-setter-dispatch.md)
- [.memory/ADRs/0022-struct-based-dlpack-exchange.md](.memory/ADRs/0022-struct-based-dlpack-exchange.md)

## Evidence Matrix
- `TVMFFIPyCallManager` class (thread-local, dispatch map, call stack) -> `.memory/commits/2025-09-11-38d2cdaa.md` + `38d2cdaa` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- `TVMFFIPyFuncCall` entry point -> `38d2cdaa` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- `TVMFFIPyArgSetter` / `TVMFFIPyArgSetterFactory` dispatch -> `38d2cdaa` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- Predefined POD setters (Float, Int, Bool, None) -> `38d2cdaa` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- Cached `DLManagedTensorVersioned` in `TensorObj` -> `38d2cdaa` + `include/tvm/ffi/container/tensor.h`
- `Function.__call__` routing through `TVMFFIPyFuncCall` -> `38d2cdaa` + `python/tvm_ffi/cython/function.pxi`
- `DLPackExchangeAPI` struct-based exchange protocol -> `.memory/commits/2025-09-12-f81ab9c2.md` + `f81ab9c2` + `python/tvm_ffi/cython/base.pxi`, `python/tvm_ffi/cython/function.pxi`
- `DLPackTensorAllocator` / `TVMFFIEnvSetDLPackManagedTensorAllocator` -> `f81ab9c2` + `include/tvm/ffi/extra/c_env_api.h`
- `Function` as cdef class with `release_gil` -> `f81ab9c2` + `python/tvm_ffi/cython/function.pxi`
- `_optional_torch_c_dlpack.py` PyTorch integration -> `f81ab9c2` + `python/tvm_ffi/_optional_torch_c_dlpack.py`
- `stream_context.cc` renamed to `env_context.cc` -> `f81ab9c2` + `src/ffi/extra/env_context.cc`
- DLPack naming refactor (`__c_dlpack_from_pyobject__` / `__c_dlpack_to_pyobject__`) -> `.memory/commits/2025-09-12-4dee97f1.md` + `4dee97f1` + `python/tvm_ffi/cython/function.pxi`
- `TVMFFIStringFromByteArray` / `TVMFFIBytesFromByteArray` C APIs -> `.memory/commits/2025-09-13-043d9f64.md` + `043d9f64` + `include/tvm/ffi/c_api.h`, `src/ffi/object.cc`
- `TVMFFIPyConstructorCall` nested container conversion -> `043d9f64` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`, `python/tvm_ffi/cython/function.pxi`
- Container setters (Tuple, TupleLike, Map) -> `043d9f64` + `python/tvm_ffi/cython/function.pxi`
- String/Bytes direct setters (`TVMFFIPyArgSetterPyNativeObjectStr_`, `TVMFFIPyArgSetterPyNativeObjectBytes_`) -> `043d9f64` + `python/tvm_ffi/cython/function.pxi`
- `_FUNC_CONVERT_TO_OBJECT` removal, replaced by `_CONSTRUCTOR_ARRAY`/`_CONSTRUCTOR_MAP` -> `043d9f64` + `python/tvm_ffi/cython/function.pxi`

## Open Questions
- Should the dispatch map support invalidation when a type's structure changes (e.g., `__tvm_ffi_value__` is dynamically added)?
- Should there be a mechanism to register custom setters from Python for third-party types without modifying the factory?
- The `DLPackExchangeAPI` struct is from dlpack; if dlpack changes the struct, the cached setters become invalid.

## Confidence and Risk
- Confidence: high
- Residual risks: The thread-local dispatch map grows monotonically (no eviction). In long-running processes with many distinct Python types, this could consume memory. The `DLPackExchangeAPI` struct layout is controlled by the dlpack project; layout changes would require rebuilding the Cython extension. The `release_gil=True` default is safe for most FFI functions but could cause issues if a function unexpectedly calls back into Python.
