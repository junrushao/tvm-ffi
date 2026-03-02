---
design: "0020"
title: "External Function Construction: extern C and MLIR Packed Calling Convention"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-10-10"
last_updated: "2025-10-11"
scope:
  - "python/tvm_ffi/cython/function"
  - "python/tvm_ffi/cython/tvm_ffi_python_helpers"
  - "ffi/function"
source_commits:
  - "b64b46f32e845b650850d73a5828a2d3f07d3406"
  - "a15364746d60766bfaf6e0a6ccdb2353ceee7d7d"
  - "f6303b23fd97909b59f6ff67b85f2203371f5db1"
source_ledgers:
  - ".memory/commits/2025-10-10-b64b46f3.md"
  - ".memory/commits/2025-10-10-a1536474.md"
  - ".memory/commits/2025-10-11-f6303b23.md"
---

# External Function Construction: extern C and MLIR Packed Calling Convention

## TL;DR
- `Function.__from_extern_c__` and `Function.__from_mlir_packed_safe_call__` enable constructing FFI `Function` objects from JIT-compiled function pointers (e.g., from LLVM/MLIR execution engines), bridging external calling conventions to the TVM FFI packed protocol.
- A keep-alive object pattern ensures the JIT execution engine stays alive as long as any function it produced is in use, using `TVMFFIPyObjectDeleter` for GIL-safe reference management.
- Free-threaded Python (PEP 703) support is achieved through `TVMFFIPyWithGILIfNotFreeThreaded`, which conditionally acquires the GIL only when running under standard CPython builds.

## Problem Statement
DSLs and compilers that use JIT compilation (LLVM, MLIR) produce native function pointers at runtime. These functions need to be callable through the TVM FFI packed convention so they can be used like any other FFI function -- passed to other functions, stored in registries, and called from Python. Two calling conventions must be supported: the TVM FFI `TVMFFISafeCallType` convention (extern C) and the MLIR execution engine's `void(void**)` packed convention. Additionally, the transition to free-threaded Python (no GIL) requires careful handling of Python object references in C++ destructor code.

## Context and Constraints
- JIT-compiled functions are transient: the execution engine that produced them must stay alive for the function pointer to remain valid.
- MLIR execution engines produce functions with `void(void**)` signature where arguments are passed as an array of `void*` pointers. This differs from TVM FFI's `int(void*, TVMFFIAny*, int32_t, TVMFFIAny*)` safe call convention.
- Free-threaded Python (`Py_GIL_DISABLED`) is incompatible with the Python Stable ABI (Limited API), requiring build-time detection and fallback.
- Python object references decremented from C++ code need GIL acquisition in standard CPython but not in free-threaded builds.

## Goals
- Provide Python APIs for constructing FFI Functions from extern C and MLIR packed function pointers.
- Ensure JIT execution engine lifetime is tied to function lifetime via keep-alive objects.
- Support both GIL-enabled and GIL-disabled (free-threaded) Python builds.
- Fix `OpaqueObject` type registration to properly participate in the Object type hierarchy.

## Non-Goals
- Supporting arbitrary foreign calling conventions (only TVM FFI safe call and MLIR packed are supported).
- Thread-safety of function construction (construction is assumed to happen on the calling thread).
- Automatic discovery of JIT-compiled functions (callers must provide the function pointer explicitly).

## Design
### Components and Responsibilities

- **`Function.__from_extern_c__(c_symbol, *, keep_alive_object=None)`** (static method, `function.pxi`): Constructs an FFI `Function` from a raw C function pointer (as `int`). The C function must match `TVMFFISafeCallType` signature: `int(void*, const TVMFFIAny*, int32_t, TVMFFIAny*)` and ignore the first argument (function handle). Uses `TVMFFIFunctionCreate` C API with `TVMFFIPyObjectDeleter` for the keep-alive reference.

- **`Function.__from_mlir_packed_safe_call__(mlir_packed_symbol, *, keep_alive_object=None)`** (static method, `function.pxi`): Constructs an FFI `Function` from an MLIR execution engine function pointer with `void(void**)` signature. Creates an intermediate `TVMFFIPyMLIRPackedSafeCall` adapter object that translates calling conventions.

- **`TVMFFIPyMLIRPackedSafeCall`** (C++ class, `tvm_ffi_python_helpers.h`): Adapter that bridges MLIR's `void(void**)` packed convention to TVM FFI's `int(void*, TVMFFIAny*, int32_t, TVMFFIAny*)` safe call convention. The adapter unpacks the `void**` array into `{handle, args, num_args, rv, ret_code}` fields and routes through the MLIR function. Lifecycle managed via `Create`/`Invoke`/`Deleter` triple: `TVMFFIPyMLIRPackedSafeCallCreate` allocates, `TVMFFIPyMLIRPackedSafeCallInvoke` is the safe_call dispatch, and `TVMFFIPyMLIRPackedSafeCallDeleter` frees.

- **`TVMFFIPyObjectDeleter`** (C function, `tvm_ffi_python_helpers.h`): GIL-safe Python object reference decrementer. Replaces the Cython `tvm_ffi_pyobject_deleter` (which used `with gil` syntax) with a C-level implementation that conditionally acquires the GIL.

- **`TVMFFIPyWithGILIfNotFreeThreaded`** (C++ class, `tvm_ffi_python_helpers.h`): RAII helper for conditional GIL acquisition. Under standard CPython (`!Py_GIL_DISABLED`), the constructor calls `PyGILState_Ensure()` and the destructor calls `PyGILState_Release()`. Under free-threaded Python (`Py_GIL_DISABLED`), the class is a no-op.

- **CMake free-threaded detection** (`CMakeLists.txt`): Detects free-threaded Python at configure time by checking for `Py_GIL_DISABLED`. When detected, disables `USE_SABI` (Stable ABI) since free-threaded Python is not compatible with the Limited API.

- **`OpaqueObject` type registration fix** (`src/ffi/object.cc`): Changed from `ReserveBuiltinTypeIndex` (which did not set up the type hierarchy) to `GetOrAllocTypeIndex` with `type_depth=1` and `parent_type_index=kTVMFFIObject`, so `OpaqueObject` is properly recognized as an Object subtype. This was caught by free-threaded Python ref count tests.

### Data Contracts and Invariants
- **Keep-alive lifetime invariant**: The `keep_alive_object` Python reference is held by the FFI `Function` via `TVMFFIPyObjectDeleter`. The reference is only released when the `Function` is destroyed. This ensures the JIT execution engine outlives all functions it produced.
- **MLIR packed convention**: The MLIR function receives a `void**` array where: `[0]` = handle (always null for TVM FFI), `[1]` = `const TVMFFIAny* args`, `[2]` = `int32_t* num_args`, `[3]` = `TVMFFIAny* rv`, `[4]` = `int* ret_code`. The adapter populates this array and reads back `ret_code` as the return value.
- **GIL safety**: `TVMFFIPyObjectDeleter` is always safe to call from C++ code regardless of GIL state, because it acquires the GIL when needed. Under free-threaded Python, GIL acquisition is a no-op.
- **Stable ABI exclusion**: Free-threaded Python builds disable the Stable ABI (`USE_SABI=OFF`) at CMake configure time. This is non-negotiable since `Py_GIL_DISABLED` is incompatible with the Limited API.

### Control Flow

#### `__from_extern_c__` path:
1. Python caller provides a function pointer (as int) and optional keep-alive object.
2. `Py_IncRef(keep_alive_object)` to prevent GC during FFI function lifetime.
3. `TVMFFIFunctionCreate(c_symbol, keep_alive_object_ptr, TVMFFIPyObjectDeleter, &chandle)` creates the FFI function.
4. The returned `Function` object wraps the handle.
5. On function destruction, `TVMFFIPyObjectDeleter` decrements the keep-alive reference (with GIL if needed).

#### `__from_mlir_packed_safe_call__` path:
1. Python caller provides an MLIR packed function pointer and optional keep-alive object.
2. `TVMFFIPyMLIRPackedSafeCallCreate(mlir_fn, keep_alive_obj)` creates an adapter holding both the function pointer and the keep-alive reference.
3. `TVMFFIFunctionCreate(TVMFFIPyMLIRPackedSafeCallInvoke, adapter, TVMFFIPyMLIRPackedSafeCallDeleter, &chandle)` wraps the adapter as an FFI function.
4. On each call, `TVMFFIPyMLIRPackedSafeCallInvoke` translates the calling convention.
5. On destruction, `TVMFFIPyMLIRPackedSafeCallDeleter` frees the adapter (which decrements the keep-alive reference).

### Extension Points
- **New calling conventions**: Add a new adapter class (following the `TVMFFIPyMLIRPackedSafeCall` pattern) with `Create`/`Invoke`/`Deleter` triple for any new foreign calling convention.
- **Non-Python keep-alive**: The `TVMFFIPyObjectDeleter` pattern could be generalized to non-Python reference-counted objects via a generic deleter callback.

## Alternatives Considered
### Implement the adapter in core C++ (not Python helper layer)
- Pros: Accessible from Rust and other languages.
- Cons: MLIR execution engine may eventually support direct extern C function pointers, making the adapter unnecessary. Keeping it in the Python helper layer avoids polluting the core API with a potentially temporary bridge.

### Use ctypes to wrap function pointers on the Python side
- Pros: No Cython changes needed.
- Cons: Performance overhead from ctypes marshaling. Cannot use `TVMFFIFunctionCreate` C API directly. No keep-alive object integration.

### Require MLIR to produce TVM FFI-compatible functions directly
- Pros: No adapter needed.
- Cons: Requires MLIR-side changes. The MLIR packed convention is well-established and used by many MLIR-based systems.

## Trade-offs
- **Optimized**: JIT integration flexibility (two calling conventions supported), lifetime safety (keep-alive pattern), forward-compatible with free-threaded Python.
- **Sacrificed**: Extra indirection for MLIR calls (one adapter invocation per call), Python helper layer complexity (~100 lines of C++ for the MLIR adapter), Stable ABI loss for free-threaded Python builds.

## Interfaces and Compatibility
- **Python API**: `Function.__from_extern_c__(c_symbol: int, *, keep_alive_object=None) -> Function`, `Function.__from_mlir_packed_safe_call__(mlir_packed_symbol: int, *, keep_alive_object=None) -> Function`.
- **C++ helper API**: `TVMFFIPyMLIRPackedSafeCallCreate`, `TVMFFIPyMLIRPackedSafeCallInvoke`, `TVMFFIPyMLIRPackedSafeCallDeleter`, `TVMFFIPyObjectDeleter`, `TVMFFIPyWithGILIfNotFreeThreaded`.
- **C API**: `TVMFFIFunctionCreate(safe_call_fn, handle, deleter, out_handle)` is the underlying creation API.
- **Breaking change**: `keep_alive_object` parameter in `__from_extern_c__` changed to keyword-only (commit `f6303b23`).

## Failure Modes and Mitigations
- **Invalid function pointer**: If the provided `c_symbol` or `mlir_packed_symbol` is not a valid function pointer, calling the resulting FFI function will crash. Mitigation: documentation emphasizes that callers must provide valid function pointers.
- **Keep-alive object GC**: If the keep-alive object is not provided and the execution engine is garbage collected, the function pointer becomes invalid. Mitigation: documentation recommends always passing the execution engine as the keep-alive object.
- **GIL deadlock in destructor**: If `TVMFFIPyObjectDeleter` is called while the GIL is already held in a way that would deadlock, `PyGILState_Ensure` handles this correctly (it's reentrant). No known deadlock scenarios.
- **Free-threaded Python + Stable ABI**: Detected at CMake configure time; build will automatically disable Stable ABI. If somehow enabled manually, compilation will fail due to missing Limited API symbols.

## Observability and Validation
- `testing.get_add_one_c_symbol` / `testing.get_mlir_packed_add_one_c_symbol` C++ test helpers return function pointer addresses for roundtrip testing.
- `tests/python/test_function.py` tests extern C and MLIR packed function construction, calling, and keep-alive behavior.
- Free-threaded Python is tested in CI matrix.

## Migration and Rollout
- New APIs: no migration needed.
- `tvm_ffi_pyobject_deleter` (Cython) replaced by `TVMFFIPyObjectDeleter` (C++). Internal change, no user-facing impact.

## Diagrams
None (the calling convention translation is straightforward and documented in the Control Flow section).

## Related ADRs
- [.memory/ADRs/0030-free-threaded-python-support.md](.memory/ADRs/0030-free-threaded-python-support.md)

## Evidence Matrix
- `Function.__from_extern_c__` static method -> `.memory/commits/2025-10-10-a1536474.md` + `a1536474` + `python/tvm_ffi/cython/function.pxi`
- `Function.__from_mlir_packed_safe_call__` static method -> `.memory/commits/2025-10-11-f6303b23.md` + `f6303b23` + `python/tvm_ffi/cython/function.pxi`
- `TVMFFIPyMLIRPackedSafeCall` adapter class -> `f6303b23` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- `TVMFFIPyObjectDeleter` GIL-safe deleter -> `.memory/commits/2025-10-10-b64b46f3.md` + `b64b46f3` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- `TVMFFIPyWithGILIfNotFreeThreaded` conditional GIL helper -> `b64b46f3` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- Free-threaded Python CMake detection -> `b64b46f3` + `CMakeLists.txt`
- OpaqueObject type registration fix -> `b64b46f3` + `src/ffi/object.cc`
- `keep_alive_object` changed to keyword-only in `__from_extern_c__` -> `f6303b23` + `python/tvm_ffi/cython/function.pxi`
- `testing.get_add_one_c_symbol` test helper -> `a1536474` + `src/ffi/extra/testing.cc`
- `testing.get_mlir_packed_add_one_c_symbol` test helper -> `f6303b23` + `src/ffi/extra/testing.cc`

## Open Questions
- Should `__from_extern_c__` validate that the function pointer is within a valid executable region?
- Should the MLIR packed adapter eventually be promoted to the core C++ layer for Rust accessibility?
- Will MLIR execution engines eventually support direct TVM FFI safe call convention, making the adapter unnecessary?

## Confidence and Risk
- Confidence: high
- Residual risks: The MLIR packed convention adapter lives in the Python helper layer, meaning Rust bindings cannot use it. If Rust needs MLIR integration, the adapter would need to be moved to core C++. The free-threaded Python support is compile-time only (via `Py_GIL_DISABLED`); runtime detection is not supported, which means the same binary cannot support both GIL and no-GIL Python.
