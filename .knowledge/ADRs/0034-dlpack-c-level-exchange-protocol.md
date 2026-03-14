---
scope:
  - "0020-dlpack-exchange-acceleration"
  - "0014-python-bindings"
---
# C-Level DLPack Exchange Protocol (__c_dlpack_from_pyobject__ / __c_dlpack_to_pyobject__)

**TL;DR**: Introduces non-standard C function pointer attributes on framework tensor classes (`__c_dlpack_from_pyobject__`, `__c_dlpack_to_pyobject__`, `__c_dlpack_tensor_allocator__`) to bypass the Python `__dlpack__` protocol overhead for high-frequency tensor exchange in TVM FFI.

## Context

The standard Python `__dlpack__` protocol involves PyCapsule creation (~50ns), Python method dispatch (~100ns), and capsule destruction (~30ns) per tensor exchange. For FFI functions called millions of times with tensor arguments, these costs dominate. A C-level bypass avoids all Python object creation in the tensor exchange hot path.

Usecases:
- Training loops passing `torch.Tensor` arguments to FFI kernel functions at high frequency.
- Return-path conversion: FFI functions returning `Tensor` need to auto-convert back to `torch.Tensor`.
- Kernel output allocation: C++ code needs to allocate tensors using the caller's framework allocator (e.g., `torch.empty`).

Design Decisions:
- Register C function pointers as integer attributes (`int64_t` cast) on the framework's tensor class (e.g., `torch.Tensor.__c_dlpack_from_pyobject__`).
- Three function types: export (`DLPackFromPyObject`), import (`DLPackToPyObject`), allocate (`DLPackTensorAllocator`).
- The argument setter caches these function pointers per `PyTypeObject*` alongside the setter function pointer, avoiding repeated `getattr` lookups.
- A JIT-compiled C++ extension (`_optional_torch_c_dlpack.py`) provides the PyTorch implementation using `torch.utils.cpp_extension.load_inline`.

## Alternatives

### 1. C-level bypass via class attributes (chosen)
- Pros: Zero Python overhead in the hot path. Fully opt-in per framework. No TVM FFI changes needed for new frameworks.
- Cons: Non-standard extension. Function pointer stored as integer is fragile. Requires JIT C++ compilation per framework.

### 2. Optimize the Python `__dlpack__` path
- Pros: Standard-compliant. No new protocol.
- Cons: Fundamentally limited by CPython overhead (PyCapsule, method dispatch). Cannot achieve zero-Python-overhead.

### 3. Cache the DLPack conversion result per tensor
- Pros: Zero cost on subsequent passes of the same tensor identity.
- Cons: No invalidation mechanism for in-place mutations. Stale cache risk. Memory overhead for cache entries.

### 4. Upstream C-level protocol in dlpack.h specification
- Pros: Standardized across all frameworks.
- Cons: Multi-year adoption timeline. Requires DLPack spec committee approval. TVM FFI needs the improvement now.

## Decision

Option 1. The naming evolved across commits: `__dlpack_c_exporter__` -> `__c_dlpack_exporter__` -> `__c_dlpack_from_pyobject__` (final). The final names describe data flow direction (`From`/`To` PyObject) rather than role (`Exporter`/`Importer`).

## Implementation Notes

- The `_optional_torch_c_dlpack.py` module is loaded lazily on first `torch.Tensor` encounter. It JIT-compiles using `torch.utils.cpp_extension.load_inline` with TVM FFI headers.
- The `TVM_FFI_SKIP_c_dlpack_from_pyobject` environment variable disables the C-level bypass (falls back to Python `__dlpack__`).
- `TVM_FFI_RELEASE_GIL_BY_DEFAULT` environment variable controls whether FFI calls release the GIL (default "1"). Short-running functions can set `release_gil=False` to avoid ~50ns GIL release/acquire overhead.

## Consequences

- **Performance**: Eliminates ~180ns Python overhead per tensor argument on repeat calls.
- **Fragility**: Function pointers cast to `int64_t` have no type safety. A framework returning the wrong function pointer signature causes undefined behavior.
- **Framework coupling**: The JIT extension requires `torch.utils.cpp_extension` and a C++ compiler at runtime.
- **Rollback**: Disabling via `TVM_FFI_SKIP_c_dlpack_from_pyobject=1` falls back to the standard `__dlpack__` path.
- **Return-path auto-conversion**: When `__c_dlpack_to_pyobject__` is available, FFI functions returning `Tensor` automatically convert to `torch.Tensor`, providing seamless framework integration.

## Related Design Docs

- [`.knowledge/designs/0020-dlpack-exchange-acceleration.md`](../designs/0020-dlpack-exchange-acceleration.md) -- Full DLPack acceleration design
- [`.knowledge/designs/0019-python-ffi-call-dispatch.md`](../designs/0019-python-ffi-call-dispatch.md) -- Call dispatch consuming DLPack setters
- [`.knowledge/ADRs/0020-thread-local-stream-context.md`](0020-thread-local-stream-context.md) -- TLS extended to EnvContext
- Commits: `.knowledge/commits/2025-09-11-38d2cdaa03adc26a630e9cc3cc99b3c7e9f55097.md` + `38d2cda`, `.knowledge/commits/2025-09-12-f81ab9c25ae4d2a42706747c50c5c410c51d6cdd.md` + `f81ab9c`, `.knowledge/commits/2025-09-12-4dee97f1b6473f32faeb8cd24fb2c960f3b17190.md` + `4dee97f`
