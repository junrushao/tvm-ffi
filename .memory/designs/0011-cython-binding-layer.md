---
design: "0011"
title: "Cython Binding Layer"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-08-24"
last_updated: "2025-10-20"
scope:
  - "python/tvm_ffi/cython"
  - "python/tvm_ffi/cython/tvm_ffi_python_helpers.h"
  - "python/tvm_ffi/error.py"
  - "python/tvm_ffi/registry.py"
  - "python/tvm_ffi/_optional_torch_c_dlpack.py"
source_commits:
  - "2d41a5115f6a91e2781012a3379f9626bc9e18a1"
  - "3702e50506a865f4aa4b8342ac5632502c1c40a3"
  - "1b071590342940eebe006140aa37e09874fee4b9"
  - "91d69f0658eef18fd9c99d4ac195ad5319db3787"
  - "3a551d83f7c05106fa8033a61970a5ce34aa8aef"
  - "1b824e88743a89343ad7493691bbdf5fdf2830c9"
  - "a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806"
  - "38d2cdaa03adc26a630e9cc3cc99b3c7e9f55097"
  - "f81ab9c25ae4d2a42706747c50c5c410c51d6cdd"
  - "4dee97f1b6473f32faeb8cd24fb2c960f3b17190"
  - "043d9f647677cc3b4a8baba198a2ced45f99cc98"
  - "af82dbb9a4cbb31f1ac9dc38195eaae747c31bcb"
  - "cc93373b344715422d158d14b5502d7c673a0153"
  - "98cb8af49ff599c217fce96c3d4f57c0f52b8ec4"
  - "bdad2184551353e49a9b6882f7b9a75a258862bb"
  - "43ffe571bfef2a3f2c2dc254ca3e5dc10e093daa"
  - "9b3be5d12df257bef9a75e46ae8086b55b8cad49"
  - "ebea4dc8bd023187a7549321e2360af4f7d684b2"
  - "cfff30bd59e401e426ed6f3a3de5f7280ce5aed0"
  - "fde8dabbba8aa0ea8133a02fcd9ff0190d830948"
  - "935a5a074686839ae42a9bc52581232beeb5b1fc"
  - "70927743bd9f9e24eba65a06eb7a695137c49522"
  - "28fe3cc7fc23b725ddefbb3ca1e1899a7dfd530c"
  - "368af824845424ea439b9f3d68bf4a710afb38b1"
  - "c046b17108484780b8b13142e1c1a46e263ec979"
  - "dd4fb0ae92ab69b1cc0280e812a18a58273d4ae6"
  - "22c049b8f3b64e7e2f17b28df044b065ae3fba83"
  - "b64b46f32e845b650850d73a5828a2d3f07d3406"
  - "a15364746d60766bfaf6e0a6ccdb2353ceee7d7d"
  - "f6303b23fd97909b59f6ff67b85f2203371f5db1"
  - "22a78943"
  - "4bc89254"
  - "8873700a"
  - "b0537f04"
  - "965fc464"
  - "42e0612"
  - "9186b44d"
  - "7b57a466"
  - "da7007fd"
  - "e10d1ed7"
  - "5e648f05"
  - "0f8bf9fc"
source_ledgers:
  - ".memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md"
  - ".memory/commits/2025-08-31-3702e50506a865f4aa4b8342ac5632502c1c40a3.md"
  - ".memory/commits/2025-09-04-1b071590342940eebe006140aa37e09874fee4b9.md"
  - ".memory/commits/2025-09-05-91d69f0658eef18fd9c99d4ac195ad5319db3787.md"
  - ".memory/commits/2025-09-06-3a551d83f7c05106fa8033a61970a5ce34aa8aef.md"
  - ".memory/commits/2025-09-08-1b824e88743a89343ad7493691bbdf5fdf2830c9.md"
  - ".memory/commits/2025-09-09-a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806.md"
  - ".memory/commits/2025-09-11-38d2cdaa.md"
  - ".memory/commits/2025-09-12-f81ab9c2.md"
  - ".memory/commits/2025-09-12-4dee97f1.md"
  - ".memory/commits/2025-09-13-043d9f64.md"
  - ".memory/commits/2025-09-14-af82dbb9a4cbb31f1ac9dc38195eaae747c31bcb.md"
  - ".memory/commits/2025-09-14-cc93373b344715422d158d14b5502d7c673a0153.md"
  - ".memory/commits/2025-09-25-98cb8af4.md"
  - ".memory/commits/2025-09-25-bdad2184.md"
  - ".memory/commits/2025-09-26-43ffe571.md"
  - ".memory/commits/2025-09-26-9b3be5d1.md"
  - ".memory/commits/2025-09-26-ebea4dc8.md"
  - ".memory/commits/2025-09-26-cfff30bd.md"
  - ".memory/commits/2025-09-27-fde8dabb.md"
  - ".memory/commits/2025-10-01-935a5a07.md"
  - ".memory/commits/2025-10-03-70927743.md"
  - ".memory/commits/2025-10-03-28fe3cc7.md"
  - ".memory/commits/2025-10-07-368af824.md"
  - ".memory/commits/2025-10-07-c046b171.md"
  - ".memory/commits/2025-10-08-dd4fb0ae.md"
  - ".memory/commits/2025-10-08-22c049b8.md"
  - ".memory/commits/2025-10-10-b64b46f3.md"
  - ".memory/commits/2025-10-10-a1536474.md"
  - ".memory/commits/2025-10-11-f6303b23.md"
  - ".memory/commits/2025-10-11-22a78943.md"
  - ".memory/commits/2025-10-13-4bc89254.md"
  - ".memory/commits/2025-10-14-8873700a.md"
  - ".memory/commits/2025-10-13-b0537f04.md"
  - ".memory/commits/2025-10-13-965fc464.md"
  - ".memory/commits/2025-10-16-42e0612.md"
  - ".memory/commits/2025-10-14-9186b44d.md"
  - ".memory/commits/2025-10-14-7b57a466.md"
  - ".memory/commits/2025-10-14-da7007fd.md"
  - ".memory/commits/2025-10-20-e10d1ed7.md"
  - ".memory/commits/2025-10-20-5e648f05.md"
  - ".memory/commits/2025-10-20-0f8bf9fc.md"
---

# Cython Binding Layer

## TL;DR
- The Cython binding layer (~1900 lines across 8 `.pxi` files included from `core.pyx`) plus a C-level helper layer (`tvm_ffi_python_helpers.h`, ~740 lines) provides high-performance Python bindings to the TVM FFI C API, handling type-erased argument marshaling, return value conversion, error propagation with cross-language traceback stitching, and object lifecycle management.
- Type dispatch for argument conversion is implemented as a cached C-level dispatch table (`TVMFFIPyCallManager`) mapping `PyTypeObject*` to `TVMFFIPyArgSetter` function pointers, with a Cython factory callback for cache misses. Return value conversion uses a type-index switch in `make_ret()` (C-to-Python), covering all 20+ type indices including automatic torch tensor and DLPack conversion.
- DLPack tensor exchange supports both the standard PyCapsule protocol and an optimized C-struct-based protocol (`DLPackExchangeAPI` via `__dlpack_c_exchange_api__` attribute) for zero-copy tensor transfer without PyCapsule overhead. See [design 0015](.memory/designs/0015-python-ffi-call-optimization.md) for the full optimization layer design.
- Error propagation preserves full stack traces across the Python/C++ boundary by combining C++ tracebacks (from `TVMFFITraceback`) with Python tracebacks (from `traceback.format_exception`) into synthetic Python frame objects.

## Problem Statement
The FFI layer's packed calling convention operates on type-erased `TVMFFIAny` values via C ABI functions. Python needs high-performance bindings that can marshal Python objects to/from these type-erased values with minimal overhead, since every ML kernel call goes through this path. The bindings must also propagate errors bidirectionally (C++ exceptions to Python exceptions and vice versa) while preserving meaningful stack traces across the language boundary.

## Context and Constraints
- Cython is chosen over ctypes (too slow) and pybind11 (no Stable ABI, too opaque) for direct C struct access and minimal call overhead.
- The binding must handle all `TVMFFITypeIndex` values (None, Int, Bool, Float, OpaquePtr, DataType, Device, DLTensorPtr, RawStr, ByteArrayPtr, ObjectRValueRef, SmallStr, SmallBytes, plus all static object types starting at index 64).
- torch tensor arguments must be auto-converted via DLPack without explicit user conversion, and CUDA stream context must be propagated.
- The Cython extension depends on `libtvm_ffi` symbols being available at runtime (via RTLD_GLOBAL loading in `__init__.py`).

## Goals
- Provide zero-overhead argument packing (`make_args`) and return value unpacking (`make_ret`) for all FFI type indices.
- Support automatic DLPack conversion for torch tensors and any object with `__dlpack__`.
- Propagate errors bidirectionally with traceback stitching (C++ stack frames appear in Python exceptions and vice versa).
- Manage object lifecycle (ref counting) transparently via the `Object` cdef class.
- Support the Python Stable ABI (Limited API) when built with Python 3.12+.

## Non-Goals
- Providing a pure-Python fallback binding (ctypes-based). The Cython path is required.
- Auto-generating the binding from C header annotations. The binding is hand-written for control.
- Supporting async/await or coroutine-based FFI calls.

## Design
### Components and Responsibilities
- **`base.pxi`**: C API declarations (cdef extern), TVMFFITypeIndex enum, struct definitions (TVMFFIAny, TVMFFIObject, DLTensor, etc.), low-level C function prototypes, and centralized byte-array-to-Python conversion helpers (`bytearray_to_str`, `bytearray_to_bytes`; refactored in commit `cc93373`).
- **`object.pxi`**: `Object` cdef class (the Python-side base class for all FFI objects), ref counting (`__cinit__`/`__dealloc__`), type-index-to-class dispatch table, pickle support, and `ObjectGeneric`/`ObjectRValueRef` helpers.
- **`function.pxi`**: `Function` cdef class (with `release_gil` property, default `True`), `TVMFFIPyArgSetterFactory` callback for cache-miss dispatch, `make_ret()` for C-to-Python unmarshaling, automatic torch/DLPack conversion (via `DLPackExchangeAPI` C struct or PyCapsule fallback), stream context propagation, container setters (`TVMFFIPyArgSetterTuple_`, `TVMFFIPyArgSetterTupleLike_`, `TVMFFIPyArgSetterMap_`), and the `Function.__call__` fast path routing through `TVMFFIPyFuncCall`.
- **`tvm_ffi_python_helpers.h`**: C++ header (~740 lines) included in the Cython build. Provides `TVMFFIPyCallManager` (thread-local dispatch map + call stack), `TVMFFIPyCallContext` (RAII call frame), `TVMFFIPyArgSetter` (function pointer struct), predefined POD setters (Int, Float, Bool, None), `TVMFFIPyFuncCall` / `TVMFFIPyConstructorCall` / `TVMFFIPyCallFieldSetter` entry points. See [design 0015](.memory/designs/0015-python-ffi-call-optimization.md).
- **`error.pxi`**: `Error` cdef class (wraps `TVMFFIErrorCell`), `CHECK_CALL()` for C API return code checking, `set_last_ffi_error()` for Python-to-C error propagation, and `move_from_last_error()` for C-to-Python error retrieval.
- **`ndarray.pxi`**: `NDArray` cdef class (wraps `TVMFFITensor`, renamed from `TVMFFINDArray` in commit `3a551d8`), DLPack import/export (defaults relaxed to `require_alignment=0, require_contiguous=False` in commit `1b824e8`; see [ADR-0019](.memory/ADRs/0019-relaxed-dlpack-import-defaults.md)), numpy/torch interop, and `from_dlpack()` function.
- **`string.pxi`**: `ByteArrayArg` helper for passing Python strings/bytes to C, encoding helpers (`c_str`, `py_str`).
- **`dtype.pxi`**: `DataType` cdef class for DLDataType, conversion from string/numpy dtype.
- **`device.pxi`**: `Device` cdef class for DLDevice, device type enum. DLPack device type constants (`kDLCPU`, `kDLCUDA`, `kDLROCm`, etc.) declared from `dlpack/dlpack.h` in `base.pxi` (commit `a08fa6e`).
- **`DLTensorTestWrapper`** (cdef class, `tensor.pxi`): Test utility wrapping a Tensor that implements `__tvm_ffi_env_stream__`, `__dlpack__`, `__dlpack_device__` for testing the stream exchange protocol (commit `a08fa6e`).
- **`OpaquePyObject`** (cdef class, `object.pxi`): Wraps arbitrary Python objects as ref-counted FFI objects. Provides `.pyobject()` to retrieve the original Python object. Added in commit `91d69f0`. See [ADR-0017](.memory/ADRs/0017-opaque-pyobject.md).
- **`type_info.pxi`**: `TypeSchema` dataclass for parsed JSON type schemas, `TypeField`/`TypeMethod` metadata access, `_TYPE_SCHEMA_ORIGIN_CONVERTER` mapping table. See [Design 0019](.memory/designs/0019-typeschema-metadata-system.md).
- **`Function.__from_extern_c__`** (static method, `function.pxi`): Constructs an FFI `Function` from a raw C function pointer (as `int`). Added in commit `a1536474`.
- **`Function.__from_mlir_packed_safe_call__`** (static method, `function.pxi`): Constructs an FFI `Function` from an MLIR execution engine packed function pointer via `TVMFFIPyMLIRPackedSafeCall` adapter. Added in commit `f6303b23`. See [Design 0020](.memory/designs/0020-external-function-construction.md).
- **`TVMFFIPyObjectDeleter`** (C function, `tvm_ffi_python_helpers.h`): GIL-safe Python object reference decrementer replacing Cython `tvm_ffi_pyobject_deleter`. Works under both standard and free-threaded Python via `TVMFFIPyWithGILIfNotFreeThreaded`. Added in commit `b64b46f3`. See [ADR-0030](.memory/ADRs/0030-free-threaded-python-support.md).
- **`TVMFFIPyArgSetterFFIObjectCompatible_`** (Cython setter, `function.pxi`): Handles objects implementing `__tvm_ffi_object__()` protocol. Calls the protocol method, extracts the `TVMFFIObjectHandle`, and packs it as an object argument. Added in commit `4bc89254` as `TVMFFIPyArgSetterFFITensorCompatible_` for `__tvm_ffi_tensor__`, then generalized in commit `8873700a`.
- **`TVMFFIPyArgSetterFFIOpaquePtrCompatible_`** (Cython setter, `function.pxi`): Handles objects implementing `__tvm_ffi_opaque_ptr__()` protocol. Converts the return value to `kTVMFFIOpaquePtr`. Added in commit `42e0612`.
- **`TVMFFIPyArgSetterCUDAStream_`** (Cython setter, `function.pxi`): Handles objects implementing `__cuda_stream__()` protocol (NVIDIA cuda-python interop). Extracts stream handle as opaque pointer. Added in commit `b0537f04`. See [Design 0022](.memory/designs/0022-python-ffi-interop-protocols.md).

### Data Contracts and Invariants
- Argument conversion is dispatched by `TVMFFIPyCallManager::SetArgument()` via cached `TVMFFIPyArgSetter` function pointers. Each setter must set `out->type_index` and the corresponding union field. The output is pre-zeroed (`type_index = kTVMFFINone`, `zero_padding = 0`, `v_int64 = 0`) before the setter is called. Unrecognized Python types are wrapped as `OpaquePyObject` (commit `91d69f0`) instead of raising `TypeError`. String arguments are converted via `TVMFFIStringFromByteArray` (commit `043d9f6`). Container arguments (list, tuple, dict) are recursively converted via `TVMFFIPyConstructorCall` with `_CONSTRUCTOR_ARRAY`/`_CONSTRUCTOR_MAP` (commit `043d9f6`).
- `make_ret()` must handle every valid `TVMFFITypeIndex` value. Unknown type indices raise `ValueError`.
- For object-typed arguments, `out[i].v_ptr` holds a raw `TVMFFIObjectHandle` pointer. The Python `Object` instance must be kept alive (via `temp_args` list) until the C call completes.
- `CHECK_CALL()` must translate C API return codes: 0 = success, -1 = error in thread-local storage (retrieved via `move_from_last_error()`), -2 = existing Python exception (re-raised).
- torch tensor auto-conversion captures the CUDA stream via `torch._C._cuda_getCurrentRawStream(device_id)` (native PyTorch C API, changed from JIT-compiled custom extension in commit `1b07159`) and passes it as the FFI stream context for CUDA device arguments.
- For non-torch DLPack objects with `__tvm_ffi_env_stream__` (commit `a08fa6e`), `make_args()` calls the protocol method to get the stream handle and sets it via `TVMFFIEnvSetCurrentStream` before the FFI call. See [design 0014](.memory/designs/0014-stream-exchange-protocol.md) for the full protocol specification.

### Control Flow

#### Python-to-C Call Path (`Function.__call__`)
1. Caller invokes `func(*args)` on a `Function` cdef instance.
2. `Function.__call__` packs args into a Python tuple and calls `TVMFFIPyFuncCall(setter_factory, handle, tuple, result, &ret_code, release_gil, &dlpack_api)`.
3. `TVMFFIPyCallManager::FuncCall()` allocates a `TVMFFIPyCallContext` from the thread-local stack and iterates arguments, dispatching each via the cached `TVMFFIPyArgSetter` dispatch map.
4. For DLPack-capable objects: if `DLPackExchangeAPI` is available, `from_pyobject()` converts in C; otherwise, falls back to `__dlpack__` PyCapsule.
5. For containers (list, tuple, dict): `TVMFFIPyConstructorCall` recursively converts elements and calls `_CONSTRUCTOR_ARRAY`/`_CONSTRUCTOR_MAP`.
6. Stream and allocator context is set if detected from DLPack arguments.
7. `TVMFFIFunctionCall()` is called (with optional GIL release via `Py_BEGIN_ALLOW_THREADS`).
8. Stream and allocator context is restored.
9. `CHECK_CALL()` checks the return code. On error, `move_from_last_error()` retrieves the `Error` object, converts to Python exception via `Error.py_error()`.
10. On success, `make_ret()` converts the `TVMFFIAny` result to a Python object.

See [design 0015](.memory/designs/0015-python-ffi-call-optimization.md) and [diagram 0012](.memory/diagrams/0012-python-ffi-call-optimization-flow.md) for the full optimized call flow.

#### Error Propagation (C++ -> Python)
1. C++ code throws via `TVM_FFI_THROW(ErrorKind) << "message"`.
2. `TVMFFITraceback()` captures the C++ stack trace.
3. The error is stored in thread-local storage via `TVMFFIErrorSetRaised()`.
4. `TVMFFIFunctionCall()` returns -1.
5. `CHECK_CALL()` calls `move_from_last_error()` to retrieve the `Error` object.
6. `Error.py_error()` creates a Python exception, appending the C++ traceback as synthetic Python frames via `TracebackManager.append_traceback()`.

#### Error Propagation (Python -> C++)
1. Python callback (registered as FFI function) raises an exception.
2. The Cython callback wrapper catches the exception and calls `set_last_ffi_error()`.
3. `set_last_ffi_error()` creates an `Error` object with the Python traceback (via `_TRACEBACK_TO_STR`) plus the C++ traceback (via `TVMFFITraceback(NULL, 0, NULL, 0)`).
4. If the Python exception has `__tvm_ffi_error__` (it originated from C++), the existing `Error` object's traceback is updated instead.
5. `TVMFFIErrorSetRaised()` stores the error for retrieval by the C++ caller.

### Extension Points
- New type indices can be added by extending `make_args()` and `make_ret()` in `function.pxi`.
- New DLPack-compatible frameworks (e.g., JAX, paddle) can be auto-converted via the `__dlpack__` protocol check.
- Custom error types can be registered via `register_error()` in `error.py`.

## Alternatives Considered
### Pure ctypes FFI
- Pros: No compilation step, works on any Python, no Cython dependency.
- Cons: ~10x slower argument marshaling (Python-level struct packing), no direct C struct access, complex error propagation logic in pure Python. Unacceptable for the hot path.

### pybind11 bindings
- Pros: Cleaner C++ integration, automatic type conversion.
- Cons: No Stable ABI support (per-version wheels needed), less control over marshaling hot path, larger binary size. The FFI's type-index-based dispatch does not map well to pybind11's template-driven approach.

### nanobind
- Pros: Lighter than pybind11, better support for recent CPython internals.
- Cons: Same Stable ABI limitation as pybind11. Less mature at the time of implementation.

## Trade-offs
- **Cython code complexity vs. performance**: 1900 lines of hand-tuned Cython provides zero-overhead access but is harder to maintain than auto-generated bindings.
- **torch auto-conversion vs. explicit API**: Auto-converting torch tensors via DLPack in `make_args()` is convenient but adds implicit framework coupling. The `__dlpack__` protocol check provides a generic fallback.
- **Synthetic traceback frames vs. string tracebacks**: Converting C++ tracebacks to synthetic Python frame objects (`types.FrameType` via `eval` + code object replacement) produces proper Python tracebacks that work with debuggers and logging, but the code is complex.

## Interfaces and Compatibility
- **Public Cython classes**: `Object`, `Function`, `NDArray`, `DataType`, `Device`, `Error` (all cdef classes).
- **Public pure-Python API**: `register_object()`, `register_global_func()`, `get_global_func()`, `register_error()`, `from_dlpack()`.
- **C API consumed**: All `TVMFFI*` functions from `c_api.h`, plus `TVMFFITraceback()` from `traceback.h`.

## Failure Modes and Mitigations
- **Missing libtvm_ffi symbols**: If `libtvm_ffi` is not loaded with RTLD_GLOBAL before importing `core`, the Cython extension fails with undefined symbol errors. Mitigation: `__init__.py` loads the library before any Cython import.
- **Type index mismatch**: If C++ adds a new type index not handled by `make_ret()`, `ValueError("Unhandled type index %d")` is raised. Mitigation: comprehensive switch coverage with explicit error for unknown indices.
- **torch DLPack version incompatibility**: Different torch versions may export different DLPack versions. Mitigation: the `from_dlpack()` function handles both DLManagedTensor and DLManagedTensorVersioned.

## Observability and Validation
- `pytest tests/python/test_function.py` validates argument marshaling for all type indices.
- `pytest tests/python/test_error.py` validates bidirectional error propagation with traceback stitching.
- `pytest tests/python/test_ndarray.py` validates DLPack interop.
- `pytest tests/python/test_object.py` validates object lifecycle and type dispatch.

## Migration and Rollout
- The Cython binding layer is the only supported Python binding path. There is no pure-Python fallback.
- Adding new type indices requires updating both `make_args()` and `make_ret()` in `function.pxi`.

## Diagrams
- [.memory/diagrams/0009-cython-binding-type-marshaling.md](.memory/diagrams/0009-cython-binding-type-marshaling.md)
- [.memory/diagrams/0012-python-ffi-call-optimization-flow.md](.memory/diagrams/0012-python-ffi-call-optimization-flow.md)

## Related ADRs
- [.memory/ADRs/0014-scikit-build-core-sabi-packaging.md](.memory/ADRs/0014-scikit-build-core-sabi-packaging.md)
- [.memory/ADRs/0017-opaque-pyobject.md](.memory/ADRs/0017-opaque-pyobject.md)
- [.memory/ADRs/0019-relaxed-dlpack-import-defaults.md](.memory/ADRs/0019-relaxed-dlpack-import-defaults.md)
- [.memory/ADRs/0021-c-level-arg-setter-dispatch.md](.memory/ADRs/0021-c-level-arg-setter-dispatch.md)
- [.memory/ADRs/0022-struct-based-dlpack-exchange.md](.memory/ADRs/0022-struct-based-dlpack-exchange.md)
- [.memory/ADRs/0030-free-threaded-python-support.md](.memory/ADRs/0030-free-threaded-python-support.md)
- [.memory/designs/0019-typeschema-metadata-system.md](.memory/designs/0019-typeschema-metadata-system.md)
- [.memory/designs/0020-external-function-construction.md](.memory/designs/0020-external-function-construction.md)
- [.memory/designs/0022-python-ffi-interop-protocols.md](.memory/designs/0022-python-ffi-interop-protocols.md)

## Evidence Matrix
- `make_args()` type dispatch -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `python/tvm_ffi/cython/function.pxi`
- `make_ret()` type dispatch -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `python/tvm_ffi/cython/function.pxi`
- `CHECK_CALL()` error propagation -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `python/tvm_ffi/cython/error.pxi`
- `TracebackManager` synthetic frames -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `python/tvm_ffi/error.py`
- `Object` cdef class lifecycle -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `python/tvm_ffi/cython/object.pxi`
- torch auto-conversion in `make_args()` -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `python/tvm_ffi/cython/function.pxi`
- None arg zero-init fix (v_int64 = 0 for kTVMFFINone) -> `.memory/commits/2025-08-31-3702e50506a865f4aa4b8342ac5632502c1c40a3.md` + `3702e50` + `python/tvm_ffi/cython/function.pxi`
- torch stream getter changed to native `torch._C._cuda_getCurrentRawStream` -> `.memory/commits/2025-09-04-1b071590342940eebe006140aa37e09874fee4b9.md` + `1b07159` + `python/tvm_ffi/cython/function.pxi`
- OpaquePyObject: auto-wrapping in make_args, unwrapping in make_ret -> `.memory/commits/2025-09-05-91d69f0658eef18fd9c99d4ac195ad5319db3787.md` + `91d69f0` + `python/tvm_ffi/cython/function.pxi`, `python/tvm_ffi/cython/object.pxi`
- `tvm_ffi_pyobject_deleter` shared deleter (renamed from callback_deleter) -> `91d69f0` + `python/tvm_ffi/cython/function.pxi`
- NDArray->Tensor rename in Cython (`TVMFFINDArray` -> `TVMFFITensor`, `kTVMFFINDArray` -> `kTVMFFITensor`) -> `.memory/commits/2025-09-06-3a551d83f7c05106fa8033a61970a5ce34aa8aef.md` + `3a551d8` + `python/tvm_ffi/cython/base.pxi`, `python/tvm_ffi/cython/ndarray.pxi`
- Relaxed DLPack import defaults (`require_alignment=0, require_contiguous=False`) -> `.memory/commits/2025-09-08-1b824e88743a89343ad7493691bbdf5fdf2830c9.md` + `1b824e8` + `python/tvm_ffi/cython/ndarray.pxi`, `python/tvm_ffi/cython/function.pxi`
- `__tvm_ffi_env_stream__` protocol in `make_args()` -> `.memory/commits/2025-09-09-a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806.md` + `a08fa6e` + `python/tvm_ffi/cython/function.pxi`
- DLPack device type constants in `base.pxi` -> `a08fa6e` + `python/tvm_ffi/cython/base.pxi`
- `DLTensorTestWrapper` test class -> `a08fa6e` + `python/tvm_ffi/cython/tensor.pxi`
- `TVM_FFI_BUILD_DOCS` env guard around `import torch` -> `3a551d8` + `python/tvm_ffi/cython/`
- `TVMFFIPyCallManager` C-level dispatch (replaces per-argument isinstance) -> `.memory/commits/2025-09-11-38d2cdaa.md` + `38d2cdaa` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- `TVMFFIPyFuncCall` entry point for `Function.__call__` -> `38d2cdaa` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`, `python/tvm_ffi/cython/function.pxi`
- `DLPackExchangeAPI` struct-based exchange, `__dlpack_c_exchange_api__` attr -> `.memory/commits/2025-09-12-f81ab9c2.md` + `f81ab9c2` + `python/tvm_ffi/cython/function.pxi`, `python/tvm_ffi/cython/base.pxi`
- `Function` as cdef class with `release_gil` property -> `f81ab9c2` + `python/tvm_ffi/cython/function.pxi`
- `_optional_torch_c_dlpack.py` PyTorch C DLPack integration -> `f81ab9c2` + `python/tvm_ffi/_optional_torch_c_dlpack.py`
- DLPack naming refactor (`DLPackFromPyObject`/`DLPackToPyObject`) -> `.memory/commits/2025-09-12-4dee97f1.md` + `4dee97f1` + `python/tvm_ffi/cython/function.pxi`
- `TVMFFIPyConstructorCall` nested container conversion -> `.memory/commits/2025-09-13-043d9f64.md` + `043d9f64` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`, `python/tvm_ffi/cython/function.pxi`
- `TVMFFIStringFromByteArray`/`TVMFFIBytesFromByteArray` direct string construction -> `043d9f64` + `include/tvm/ffi/c_api.h`, `src/ffi/object.cc`
- `_FUNC_CONVERT_TO_OBJECT` removed, replaced by `_CONSTRUCTOR_ARRAY`/`_CONSTRUCTOR_MAP` -> `043d9f64` + `python/tvm_ffi/cython/function.pxi`
- `bytearray_to_str`/`bytearray_to_bytes` centralization -> `.memory/commits/2025-09-14-cc93373b344715422d158d14b5502d7c673a0153.md` + `cc93373` + `python/tvm_ffi/cython/base.pxi`, `dtype.pxi`, `function.pxi`, `object.pxi`, `string.pxi`
- `method_pyfunc.__name__` fix (dedented out of `if doc is not None:`) -> `.memory/commits/2025-09-14-af82dbb9a4cbb31f1ac9dc38195eaae747c31bcb.md` + `af82dbb` + `python/tvm_ffi/cython/function.pxi`
- Auto-create Python fallback classes for unregistered C++ object types, `_lookup_or_register_type_info_from_type_key`, `TypeInfo.type_ancestors` -> `.memory/commits/2025-09-25-98cb8af4.md` + `98cb8af` + `python/tvm_ffi/cython/object.pxi`, `python/tvm_ffi/registry.py`
- Fix `kTVMFFIOpaquePyObject` abort on type mismatch (register builtin type index) -> `.memory/commits/2025-09-25-bdad2184.md` + `bdad218` + `src/ffi/object.cc`
- Only set `__doc__` when C++ reflection provides non-empty docstring -> `.memory/commits/2025-09-26-43ffe571.md` + `43ffe57` + `python/tvm_ffi/cython/object.pxi`
- `_DISPATCH_TYPE_KEEP_ALIVE` set to prevent GC of registered Python types in C++ dispatcher -> `.memory/commits/2025-09-26-cfff30bd.md` + `cfff30b` + `python/tvm_ffi/cython/function.pxi`
- CUDA stream fix: `ctx.device_id` -> `ctx.device_type` in DLPack export -> `.memory/commits/2025-09-27-fde8dabb.md` + `fde8dab` + `python/tvm_ffi/cython/function.pxi`
- Trainium device type `kDLTrn = 17` -> `.memory/commits/2025-10-01-935a5a07.md` + `935a5a0` + `python/tvm_ffi/cython/base.pxi`
- `TVM_FFI_INLINE` always_inline on Cython Python helpers -> `.memory/commits/2025-09-26-000e1970.md` + `000e197` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- Tensor memory leak fix (`TVMFFIObjectDecRef` after DLPack conversion) -> `.memory/commits/2025-10-03-70927743.md` + `70927743` + `python/tvm_ffi/cython/tensor.pxi`
- TypeSchema, Metadata, type_info.pxi components -> `.memory/commits/2025-10-03-28fe3cc7.md` + `28fe3cc7` + `python/tvm_ffi/cython/type_info.pxi`
- Self-type in member function schemas -> `.memory/commits/2025-10-07-368af824.md` + `368af824` + `python/tvm_ffi/cython/type_info.pxi`
- `DataType` -> `dtype` in schema display -> `.memory/commits/2025-10-07-c046b171.md` + `c046b171` + `python/tvm_ffi/cython/type_info.pxi`
- `TypeSchema.repr(ty_map=...)` -> `.memory/commits/2025-10-08-dd4fb0ae.md` + `dd4fb0ae` + `python/tvm_ffi/cython/type_info.pxi`
- `get_raw_stream` Cython binding -> `.memory/commits/2025-10-08-22c049b8.md` + `22c049b8` + `python/tvm_ffi/cython/base.pxi`
- Free-threaded Python: `TVMFFIPyObjectDeleter`, `TVMFFIPyWithGILIfNotFreeThreaded`, Stable ABI disable -> `.memory/commits/2025-10-10-b64b46f3.md` + `b64b46f3` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`, `python/tvm_ffi/cython/function.pxi`
- `Function.__from_extern_c__` static method -> `.memory/commits/2025-10-10-a1536474.md` + `a1536474` + `python/tvm_ffi/cython/function.pxi`
- `Function.__from_mlir_packed_safe_call__` with MLIR adapter -> `.memory/commits/2025-10-11-f6303b23.md` + `f6303b23` + `python/tvm_ffi/cython/function.pxi`, `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- Unified `DLPackExchangeAPI` struct replacing separate function pointers -> `.memory/commits/2025-10-11-22a78943.md` + `22a78943` + `python/tvm_ffi/cython/`, `python/tvm_ffi/_optional_torch_c_dlpack.py`
- `__tvm_ffi_tensor__` protocol (initial, tensor-specific) -> `.memory/commits/2025-10-13-4bc89254.md` + `4bc89254` + `python/tvm_ffi/cython/function.pxi`
- `__tvm_ffi_object__` protocol (generalized from tensor) -> `.memory/commits/2025-10-14-8873700a.md` + `8873700a` + `python/tvm_ffi/cython/function.pxi`, `object.pxi`
- `__cuda_stream__` protocol in arg setter factory -> `.memory/commits/2025-10-13-b0537f04.md` + `b0537f04` + `python/tvm_ffi/cython/function.pxi`
- `__cuda_stream__` monkey-patch for older PyTorch -> `.memory/commits/2025-10-13-965fc464.md` + `965fc464` + `python/tvm_ffi/_optional_torch_c_dlpack.py`
- `__tvm_ffi_opaque_ptr__` protocol -> `.memory/commits/2025-10-16-42e0612.md` + `42e0612` + `python/tvm_ffi/cython/function.pxi`
- `Function::InvokeExternC` C++ method -> `.memory/commits/2025-10-14-9186b44d.md` + `9186b44d` + `include/tvm/ffi/function.h`
- `FunctionInfo` specialization for ObjectRef member functions -> `.memory/commits/2025-10-14-7b57a466.md` + `7b57a466` + `include/tvm/ffi/function_details.h`
- Split testing.cc into separate libtvm_ffi_testing.so -> `.memory/commits/2025-10-14-da7007fd.md` + `da7007fd` + `CMakeLists.txt`, `src/ffi/testing/`
- Docstring migration from `.pyi` stubs into Cython `.pxi` sources -> `.memory/commits/2025-10-20-e10d1ed7.md` + `e10d1ed7` + `python/tvm_ffi/cython/` (device, dtype, error, function, object, string, tensor, type_info), `python/tvm_ffi/core.pyi`
- `__dlpack_data_type__` protocol setter (`TVMFFIPyArgSetterDLPackDataTypeProtocol_`) -> `.memory/commits/2025-10-20-5e648f05.md` + `5e648f05` + `python/tvm_ffi/cython/function.pxi`
- `__dlpack_device__` protocol setter (`TVMFFIPyArgSetterDLPackDeviceProtocol_`) -> `.memory/commits/2025-10-20-0f8bf9fc.md` + `0f8bf9fc` + `python/tvm_ffi/cython/function.pxi`

## Open Questions
- Whether to add a pure-Python (ctypes-based) fallback for environments where Cython compilation is impossible (e.g., PyPy, constrained embedded systems).
- Whether to auto-detect and support additional DLPack-compatible frameworks (JAX, cupy, paddle) with framework-specific optimizations.

## Confidence and Risk
- Confidence: high
- Residual risks: The torch auto-conversion path captures CUDA streams via `torch._C._cuda_getCurrentRawStream(device_id)`, a private PyTorch C API (changed from JIT-compiled extension in `1b07159`). This eliminates JIT compilation overhead but depends on a private API that may change across PyTorch versions. The OpaquePyObject auto-wrapping (commit `91d69f0`) silently wraps unrecognized types, which could mask bugs where the user intended a specific FFI type.
