---
scope: "dlpack-fast-path"
status: "active"
last_updated_commit: "7f3bb77155645f90f7d221889b3795704ffd7d6f"
related_designs:
  - ".knowledge/designs/0018-dlpack-fast-path.md"
  - ".knowledge/designs/0014-python-bindings.md"
related_adrs:
  - ".knowledge/ADRs/012-cython-binding-layer.md"
---
# API Index: DLPack Fast-Path Protocol

**Scope**: C-level DLPack bypass protocol for zero-overhead tensor conversion between Python frameworks and TVM FFI, including the type-dispatch call manager, environment tensor allocator, and per-function GIL control.
**Design docs**: `.knowledge/designs/0018-dlpack-fast-path.md`, `.knowledge/designs/0014-python-bindings.md`
**ADRs**: `.knowledge/ADRs/012-cython-binding-layer.md`

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFIStringFromByteArray` | `int TVMFFIStringFromByteArray(const TVMFFIByteArray* input, TVMFFIAny* out)` | Create owned String (SSO-aware) from raw bytes (added in 043d9f6) |
| `TVMFFIBytesFromByteArray` | `int TVMFFIBytesFromByteArray(const TVMFFIByteArray* input, TVMFFIAny* out)` | Create owned Bytes (SSO-aware) from raw bytes (added in 043d9f6) |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `DLPackExchangeAPI` | C struct | `header`, `managed_tensor_allocator`, `managed_tensor_from_py_object_no_sync`, `managed_tensor_to_py_object_no_sync`, `dltensor_from_py_object_no_sync`, `current_work_stream` | Unified function pointer table for DLPack exchange (since 22a7894) |
| `DLPackManagedTensorAllocator` | typedef | `int (*)(DLTensor*, DLManagedTensorVersioned**, void*, void(*)(void*, const char*, const char*))` | Allocate DLPack tensor from prototype (renamed from `DLPackTensorAllocator` in 9829dec) |
| `TVMFFIPyCallContext` | struct | `packed_args`, `device_type`, `device_id`, `stream`, `temp_ffi_objects[]`, `temp_py_objects[]`, `c_dlpack_exchange_api` | Per-call state; `c_dlpack_exchange_api` replaces old separate pointers (since 22a7894) |
| `TVMFFIPyArgSetter` | struct | `func` (dispatch fn ptr), `c_dlpack_exchange_api` | Type-dispatched argument conversion functor; single struct pointer replaces three fields |
| `TVMFFIPyCallManager` | class | `FuncCall(...)`, `ConstructorCall(...)`, `SetArgument(...)`, `ThreadLocal()` | Thread-local call manager with dispatch table and call stack allocator |
| `Tensor::FromEnvAlloc` | static method | `Tensor (int (*)(DLTensor*, TVMFFIObjectHandle*), ShapeView, DLDataType, DLDevice)` | Create tensor via environment allocator (replaced `FromDLPackAlloc` in f679fe5) |
| `TensorObj::cached_dl_managed_tensor_versioned_` | field | `mutable atomic<DLManagedTensorVersioned*>` | CAS-based cached DLPack export |
| `EmbeddedDLManagedTensorVersionedDeleter` | function | DLPack deleter that only does `DecRef` on TensorObj | Prevents double-free of cached struct |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `TVMFFIPyFuncCall` | `int (TVMFFIPyArgSetterFactory, void*, PyObject*, TVMFFIAny*, int*, bool, DLPackToPyObject*)` | Main entry point for FFI function calls from Python |
| `TVMFFIPyCallFieldSetter` | `int (TVMFFIPyArgSetterFactory, TVMFFIFieldSetter, void*, PyObject*, int*)` | Entry point for field setter calls |
| `TVMFFIPyPyObjectToFFIAny` | `int (TVMFFIPyArgSetterFactory, PyObject*, TVMFFIAny*, int*)` | Convert single Python object to owned TVMFFIAny |
| `TVMFFIPyConstructorCall` | `int (TVMFFIPyArgSetterFactory, void*, PyObject*, TVMFFIAny*, int*, TVMFFIPyCallContext*)` | Nested constructor call with context propagation |
| `TVMFFIPyGetDispatchMapSize` | `size_t ()` | Debug: returns thread-local dispatch table size |
| `TVMFFIPyPushTempFFIObject` | `void (TVMFFIPyCallContext*, void*)` | Push temp FFI object for post-call cleanup |
| `TVMFFIPyPushTempPyObject` | `void (TVMFFIPyCallContext*, void*)` | Push temp Python object for post-call Py_DecRef |
| `TVMFFIPyArgSetterFloat_` | `int (TVMFFIPyArgSetter*, TVMFFIPyCallContext*, PyObject*, TVMFFIAny*) noexcept` | POD setter: `kTVMFFIFloat` via `PyFloat_AsDouble` |
| `TVMFFIPyArgSetterInt_` | `int (TVMFFIPyArgSetter*, TVMFFIPyCallContext*, PyObject*, TVMFFIAny*) noexcept` | POD setter: `kTVMFFIInt` with overflow check |
| `TVMFFIPyArgSetterBool_` | same | POD setter: `kTVMFFIBool` |
| `TVMFFIPyArgSetterNone_` | same | POD setter: `kTVMFFINone` |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `Function.release_gil` | `@property; bool` | Per-function GIL control; default from `TVM_FFI_RELEASE_GIL_BY_DEFAULT` env var (default 1) |
| `__c_dlpack_exchange_api__` | class attribute (`int` or `PyCapsule`) | Points to `DLPackExchangeAPI` struct; replaces three separate attributes (since 22a7894). Accepts PyCapsule with name `"dlpack_exchange_api"` since 7f3bb77. |
| `_create_dlpack_exchange_api_capsule` | `(ptr_as_int: int) -> PyCapsule` | Creates a PyCapsule wrapping a DLPackExchangeAPI pointer (in `_optional_torch_c_dlpack.py`, since 7f3bb77) |
| `_get_dlpack_exchange_api` | Cython helper `(obj, &out_ptr) except -1` | Dispatches `__c_dlpack_exchange_api__` value: `int` or `PyCapsule` (in `tensor.pxi`, since 7f3bb77) |
| `tvm_ffi._optional_torch_c_dlpack` | module | Manages torch DLPack extension via three-tier priority: native PyTorch > prebuilt `torch_c_dlpack_ext` > JIT compile. Sets `__c_dlpack_exchange_api__` on `torch.Tensor`. Disabled when `TVM_FFI_DISABLE_TORCH_C_DLPACK=1` (since e6a654a) |
| `torch_c_dlpack_ext` | standalone package | AOT-compiled prebuilt DLPack exchange library; pip-installable addon (since f703a0c) |
| `torch_c_dlpack_ext.core.load_torch_c_dlpack_extension` | `() -> None` | Loads prebuilt `.so`/`.dylib`/`.dll` matching current torch version/device (since f703a0c) |
| `tvm_ffi.libinfo.find_python_helper_include_path` | `() -> str` | Locate `tvm_ffi_python_helpers.h` |
| `tvm_ffi.libinfo.include_paths` | `() -> list[str]` | All FFI-related C++ include paths |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| (No Rust bindings) | -- | DLPack fast path is Python-specific |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `__c_dlpack_from_pyobject__`, `__c_dlpack_to_pyobject__`, `__c_dlpack_tensor_allocator__` | `__c_dlpack_exchange_api__` | 22a7894 | Three attributes replaced by single struct pointer |
| `DLPackFromPyObject`, `DLPackToPyObject` typedefs | (removed from `tvm_ffi_python_helpers.h`) | 9829dec | Now only defined in `dlpack.h` via Cython ctypedef |
| `DLPackTensorAllocator` | `DLPackManagedTensorAllocator` | 9829dec | Renamed to match upstream dlpack.h |
| `TVMFFIEnvSetTensorAllocator` | `TVMFFIEnvSetDLPackManagedTensorAllocator` | f679fe5 | Align C API name with DLPack naming |
| `TVMFFIEnvGetTensorAllocator` | `TVMFFIEnvGetDLPackManagedTensorAllocator` | f679fe5 | Align C API name with DLPack naming |
| `Tensor::FromDLPackAlloc` | `Tensor::FromEnvAlloc` | f679fe5 | Simplified signature; uses `TVMFFIEnvTensorAlloc` |
| `TVMFFIPyArgSetterDLPackCExporter_` | `TVMFFIPyArgSetterDLPackExchangeAPI_` | 22a7894 | Renamed to match struct-based protocol |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 38d2cda | `2025-09-11-38d2cdaa03adc26a630e9cc3cc99b3c7e9f55097.md` | Type-dispatch call manager, cached DLPack, arg setter factory, CallStack RAII |
| f81ab9c | `2025-09-12-f81ab9c25ae4d2a42706747c50c5c410c51d6cdd.md` | DLPack exporter/importer/allocator, per-function GIL, EnvContext, torch integration |
| 4dee97f | `2025-09-12-4dee97f1b6473f32faeb8cd24fb2c960f3b17190.md` | Rename Exporter/Importer -> FromPyObject/ToPyObject |
| 043d9f6 | `2025-09-13-043d9f647677cc3b4a8baba198a2ced45f99cc98.md` | String/Bytes C API, nested container Cython setters, ConstructorCall |

| 7092774 | `2025-10-03-70927743.md` | Fix memory leak in make_tensor_from_chandle DLPack return path |
| e6a654a | `2025-10-28-e6a654aaaad469ca455057821db01a995f312e2f.md` | Refactor torch C DLPack to standalone build script + ctypes.CDLL |
| f703a0c | `2025-10-31-f703a0cf9358fa30d8faee719f905c58d8ca6ee3.md` | Standalone `torch_c_dlpack_ext` addon package |
| 227bdd0 | `2025-11-04-227bdd0c5c70f186fac3b3c99427a032424ed58e.md` | Fix error propagation in TVMFFIEnvTensorAlloc; register MemoryError |

| 7f3bb77 | `2025-11-26-7f3bb77155645f90f7d221889b3795704ffd7d6f.md` | PyCapsule-based `__c_dlpack_exchange_api__`; `_get_dlpack_exchange_api` Cython helper; `_create_dlpack_exchange_api_capsule` |

(plus 5 supporting commits: 30f1e0a scaffolding, bc2f408 _LIB fix, 70577053 version-tagged names, a06d0df Linux build fix, a5241e5 import fix)
