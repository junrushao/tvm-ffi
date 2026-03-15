---
scope: "env-api"
status: "active"
last_updated_commit: "6e9100c13b83f1ab42cd067cc0121aad8766a507"
related_designs:
  - ".knowledge/designs/c-abi.md"
  - ".knowledge/designs/error-handling.md"
  - ".knowledge/designs/0013-module-system.md"
  - ".knowledge/designs/0018-dlpack-fast-path.md"
related_adrs: []
---
# API Index: Extra C Environment API

**Scope**: Thread-local stream context, tensor allocator, host-side environment callbacks (signal checking, Python interop), and module-side callee helpers. All declared in `extra/c_env_api.h`, compiled under `TVM_FFI_USE_EXTRA_CXX_API`.
**Design docs**: `.knowledge/designs/c-abi.md` (Core/Extra split section), `.knowledge/designs/error-handling.md` (LOG_EXCEPTION pattern), `.knowledge/designs/0013-module-system.md` (module-side APIs), `.knowledge/designs/0018-dlpack-fast-path.md` (tensor allocator)
**ADRs**: None

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFIEnvSetStream` | `int TVMFFIEnvSetStream(int32_t device_type, int32_t device_id, TVMFFIStreamHandle stream, TVMFFIStreamHandle* opt_out_original_stream)` | Set thread-local stream for a device; optionally returns previous; uses SAFE_CALL pattern (renamed back from `TVMFFIEnvSetCurrentStream` in f81ab9c) |
| `TVMFFIEnvGetStream` | `TVMFFIStreamHandle TVMFFIEnvGetStream(int32_t device_type, int32_t device_id)` | Get current stream for device (NULL if none); uses LOG_EXCEPTION pattern (renamed from `TVMFFIEnvGetCurrentStream` in f81ab9c) |
| `TVMFFIEnvSetDLPackManagedTensorAllocator` | `int TVMFFIEnvSetDLPackManagedTensorAllocator(DLPackManagedTensorAllocator allocator, int write_to_global_context, DLPackManagedTensorAllocator* opt_out_original_allocator)` | Set thread-local (and optionally global) DLPack managed tensor allocator (renamed from `TVMFFIEnvSetTensorAllocator` in f679fe5) |
| `TVMFFIEnvGetDLPackManagedTensorAllocator` | `DLPackManagedTensorAllocator TVMFFIEnvGetDLPackManagedTensorAllocator()` | Get current allocator (TLS first, then global fallback); uses LOG_EXCEPTION pattern (renamed from `TVMFFIEnvGetTensorAllocator` in f679fe5) |
| `TVMFFIEnvTensorAlloc` | `int TVMFFIEnvTensorAlloc(DLTensor* prototype, TVMFFIObjectHandle* out)` | High-level API: allocate tensor via DLPack allocator and wrap as TensorObj inside libtvm_ffi; avoids module unloading order issues (added in f679fe5) |
| `TVMFFIEnvCheckSignals` | `int TVMFFIEnvCheckSignals()` | Check Python signals via `PyErr_CheckSignals`; acquires GIL; returns 0 on success, -1 on signal |
| `TVMFFIEnvRegisterCAPI` | `int TVMFFIEnvRegisterCAPI(const char* name, void* symbol)` | Register env-specific C API callbacks (PyErr_CheckSignals, PyGILState_*) |
| `TVMFFIEnvModLookupFromImports` | `int TVMFFIEnvModLookupFromImports(TVMFFIObjectHandle library_ctx, const char* func_name, TVMFFIObjectHandle* out)` | Callee-side: look up function from module imports |
| `TVMFFIEnvModRegisterContextSymbol` | `int TVMFFIEnvModRegisterContextSymbol(const char* name, void* symbol)` | Callee-side: register context symbol for lazy library init |
| `TVMFFIEnvModRegisterSystemLibSymbol` | `int TVMFFIEnvModRegisterSystemLibSymbol(const char* name, void* symbol)` | Callee-side: register system library symbol |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `TVMFFIStreamHandle` | typedef | `typedef void*` | Opaque handle for device streams |
| `DLPackManagedTensorAllocator` | typedef | `int (*)(DLTensor*, DLManagedTensorVersioned**, void*, void(*)(void*,const char*,const char*))` | C function pointer for allocating DLPack managed tensors (renamed from `DLPackTensorAllocator` in 9829dec, now from upstream dlpack.h) |
| `EnvContext` | class (internal) | `SetStream(...)`, `GetStream(...)`, `SetDLPackManagedTensorAllocator(...)`, `GetDLPackManagedTensorAllocator()`, `ThreadLocal()`, `GlobalTensorAllocator()` | Thread-local singleton holding stream table + tensor allocator (renamed from `StreamContext` in f81ab9c; methods renamed in 9829dec) |
| `EnvCAPIRegistry` | class (internal) | `Register(name, fptr)`, `EnvCheckSignals() -> int`, `pyerr_check_signals`, `py_gil_state_ensure`, `py_gil_state_release` | Singleton managing Python env callbacks |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN` | `try { (void)0` | Begin error boundary for direct-return C APIs |
| `TVM_FFI_LOG_EXCEPTION_CALL_END(Name)` | `} catch (const std::exception& err) { std::cerr << ... << err.what(); exit(-1); }` | End error boundary: log to stderr and abort on exception |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `core._env_set_current_stream` | `(device_type: int, device_id: int, stream: uint64) -> uint64` | Cython wrapper for `TVMFFIEnvSetStream`; returns previous stream handle (added in 3197cd0) |
| `StreamContext` | `StreamContext(device: Device, stream: Union[int, c_void_p])` | Context manager for FFI thread-local stream save/restore (added in 3197cd0) |
| `TorchStreamContext` | `TorchStreamContext(context: Optional[Any])` | Context manager bridging torch and FFI stream contexts (added in 3197cd0) |
| `use_raw_stream` | `(device: Device, stream: Union[int, c_void_p]) -> StreamContext` | Factory for StreamContext (added in 3197cd0) |
| `use_torch_stream` | `(context: Optional[Any] = None) -> TorchStreamContext` | Factory for TorchStreamContext (added in 3197cd0) |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| (No Rust bindings) | -- | -- |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `TVMFFIEnvLookupFromImports` | `TVMFFIEnvModLookupFromImports` | 023ea44 | `Mod` infix added to distinguish callee-side APIs |
| `TVMFFIEnvRegisterContextSymbol` | `TVMFFIEnvModRegisterContextSymbol` | 023ea44 | `Mod` infix |
| `TVMFFIEnvRegisterSystemLibSymbol` | `TVMFFIEnvModRegisterSystemLibSymbol` | 023ea44 | `Mod` infix |
| `TVMFFIEnvRegisterCAPI` (old sig) | `TVMFFIEnvRegisterCAPI` (new sig) | 023ea44 | Parameter changed from `const TVMFFIByteArray* name` to `const char* name` |
| `TVMFFIEnvSetStream` | `TVMFFIEnvSetCurrentStream` | db98729 | Renamed for consistency; **then reverted back** to `TVMFFIEnvSetStream` in f81ab9c |
| `TVMFFIEnvSetCurrentStream` | `TVMFFIEnvSetStream` | f81ab9c | Reverted to shorter name |
| `TVMFFIEnvGetCurrentStream` | `TVMFFIEnvGetStream` | f81ab9c | Reverted to shorter name |
| `StreamContext` | `EnvContext` | f81ab9c | Expanded to hold tensor allocator alongside stream table |
| `DLPackTensorAllocator` | `DLPackManagedTensorAllocator` | 9829dec | Renamed to match upstream dlpack.h typedef |
| `TVMFFIEnvSetTensorAllocator` | `TVMFFIEnvSetDLPackManagedTensorAllocator` | f679fe5 | Align C API name with DLPack naming |
| `TVMFFIEnvGetTensorAllocator` | `TVMFFIEnvGetDLPackManagedTensorAllocator` | f679fe5 | Align C API name with DLPack naming |
| `EnvContext::SetTensorAllocator` | `EnvContext::SetDLPackManagedTensorAllocator` | 9829dec | Internal method rename |
| `EnvContext::GetTensorAllocator` | `EnvContext::GetDLPackManagedTensorAllocator` | 9829dec | Internal method rename |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 538bef4 | `2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md` | Initial module env APIs (TVMFFIEnvLookupFromImports, etc.) |
| 0daaffed | `2025-08-19-0daaffedd23982ea09f8c38fec4eef1cca1d8cac.md` | Thread-local stream context APIs (TVMFFIEnvSetStream, TVMFFIEnvGetCurrentStream) |
| 023ea44 | `2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md` | Mod infix renames; move CheckSignals/RegisterCAPI to extra; signature change |
| f81ab9c | `2025-09-12-f81ab9c25ae4d2a42706747c50c5c410c51d6cdd.md` | Revert stream rename; add TVMFFIEnvSetTensorAllocator/GetTensorAllocator; EnvContext |

(plus 2 supporting commits: db98729 stream rename, 6014406 benchmark-only)
| 3197cd0 | `2025-09-15-3197cd0949ae9bb9a41eb5a429a4b1519d061db4.md` | Python StreamContext, TorchStreamContext, `core._env_set_current_stream` |
| 9829dec | `2025-10-15-9829dec9.md` | `DLPackTensorAllocator` -> `DLPackManagedTensorAllocator` rename |
| f679fe5 | `2025-10-15-f679fe54.md` | `TVMFFIEnvTensorAlloc`, env API renames to align with DLPack |
