---
scope: "python-ffi-call-dispatch"
---
# API Index: Python FFI Call Dispatch

**Scope**: C++ types, Cython setters, and Python protocol attributes for the type-cached FFI call dispatch system.
**Design docs**: [0015-python-ffi-call-dispatch.md](../designs/0015-python-ffi-call-dispatch.md)
**ADRs**: [0016-type-cached-ffi-dispatch.md](../ADRs/0016-type-cached-ffi-dispatch.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `TVMFFIPyCallStack` | class | `vector<TVMFFIAny> args_stack; int64_t args_stack_top; vector<PyObject*> extra_temp_py_objects_stack` | Thread-local argument buffer with overflow stack for value protocol temps (3dd7a81) |
| `TVMFFIPyCallContext` | struct | `TVMFFIAny* packed_args; int device_type; int device_id; void* stream; const DLPackExchangeAPI* dlpack_c_exchange_api; TVMFFIPyCallStack* call_stack; void** temp_ffi_objects; int num_temp_ffi_objects; void** temp_py_objects; int num_temp_py_objects; DLPackToPyObject c_dlpack_to_pyobject; DLPackTensorAllocator c_dlpack_tensor_allocator` | Per-call RAII guard: argument buffer, device context, temp object tracking (refactored to standalone class in 3dd7a81) |
| `TVMFFIPyArgSetter` | struct | `int (*func)(TVMFFIPyArgSetter*, TVMFFIPyCallContext*, PyObject*, TVMFFIAny*); const DLPackExchangeAPI* dlpack_c_exchange_api` | Per-type dispatch entry with function pointer and optional DLPack exchange API struct pointer (field renamed in 5393647) |
| `TVMFFIPyArgSetterFactory` | typedef | `int (*)(PyObject* arg, TVMFFIPyArgSetter* out)` | Factory called on cache miss to populate setter for new type |
| `TVMFFIPyCallManager` | class (TLS singleton) | `ThreadLocal()$`, `FuncCall(factory, handle, args, result, ret, release_gil, out_importer) -> int`, `ConstructorCall(factory, handle, args, result, ret, parent_ctx) -> int`, `SetField(factory, setter, ptr, arg, ret) -> int`, `PyObjectToFFIAny(factory, arg, out, ret) -> int`, `GetDispatchMapSize() -> size_t` | Thread-local manager with type dispatch cache |
| `TVMFFIPySetArgumentGenericDispatcher` | inline function | `(factory, ctx, py_arg, out) -> int` | Dispatches a Python object through the generic setter; enables recursive value protocol resolution (3dd7a81) |
| `TVMFFIPyPushExtraTempPyObject` | inline function | `(ctx, arg) -> void` | Push extra temporary Python objects to overflow stack for value protocol results (3dd7a81) |
| `DLPackExchangeAPI` | struct (dlpack.h) | `header: {version, prev_api}; managed_tensor_allocator; managed_tensor_from_py_object_no_sync; managed_tensor_to_py_object_no_sync; dltensor_from_py_object_no_sync; current_work_stream` | Versioned struct bundling all DLPack conversion function pointers (22a7894) |
| `TVMFFIPyFuncCall` | inline function | `(factory, handle, args, result, ret, release_gil, out_importer) -> int` | Top-level FFI call entry point (delegates to TVMFFIPyCallManager) |
| `TVMFFIPyConstructorCall` | inline function | `(factory, handle, args, result, ret, parent_ctx) -> int` | Nested constructor call (no GIL release, propagates context to parent) |
| `TVMFFIPyCallFieldSetter` | inline function | `(factory, setter, ptr, arg, ret) -> int` | Field setter via dispatch system |
| `TVMFFIPyPyObjectToFFIAny` | inline function | `(factory, arg, out, ret) -> int` | Convert PyObject to owned Any via dispatch |
| `TVMFFIPyGetDispatchMapSize` | inline function | `() -> size_t` | Diagnostic: number of cached type entries |
| `TVMFFIPyPushTempFFIObject` | inline function | `(TVMFFIPyCallContext*, TVMFFIObjectHandle) -> void` | Register temp FFI object for RAII cleanup |
| `TVMFFIPyPushTempPyObject` | inline function | `(TVMFFIPyCallContext*, PyObject*) -> void` | Register temp Python object for RAII cleanup |
| `TVMFFIPyArgSetterInt_` | C++ setter | `(setter, ctx, arg, out) -> int` | Setter for Python int |
| `TVMFFIPyArgSetterFloat_` | C++ setter | `(setter, ctx, arg, out) -> int` | Setter for Python float |
| `TVMFFIPyArgSetterBool_` | C++ setter | `(setter, ctx, arg, out) -> int` | Setter for Python bool |
| `TVMFFIPyArgSetterNone_` | C++ setter | `(setter, ctx, arg, out) -> int` | Setter for Python None |
| `TVMFFIStringFromByteArray` | C function (c_api.h) | `(const TVMFFIByteArray* input, TVMFFIAny* out) -> int` | Construct String from raw bytes (SSO-aware) |
| `TVMFFIBytesFromByteArray` | C function (c_api.h) | `(const TVMFFIByteArray* input, TVMFFIAny* out) -> int` | Construct Bytes from raw bytes (SSO-aware) |
| `TVMFFIEnvSetDLPackManagedTensorAllocator` | C function (extra/c_env_api.h) | `(DLPackManagedTensorAllocator, int, DLPackManagedTensorAllocator*) -> int` | Set TLS/global tensor allocator (renamed f679fe5) |
| `TVMFFIEnvGetDLPackManagedTensorAllocator` | C function (extra/c_env_api.h) | `() -> DLPackManagedTensorAllocator` | Get tensor allocator (renamed f679fe5) |
| `TVMFFIEnvTensorAlloc` | C function (extra/c_env_api.h) | `(DLTensor*, TVMFFIObjectHandle*) -> int` | Allocate tensor inside libtvm_ffi (f679fe5) |
| `Tensor::FromEnvAlloc` | static method | `(int (*)(DLTensor*, TVMFFIObjectHandle*), ShapeView, DLDataType, DLDevice) -> Tensor` | Create tensor via env allocator (f679fe5) |
| `TVMFFIPyArgSetterDLPackDataTypeProtocol_` | Cython setter | `(setter, ctx, arg, out) -> int` | Setter for `__dlpack_data_type__` protocol; unpacks 3-tuple into DLDataType (5e648f0) |
| `TVMFFIPyArgSetterDLPackDeviceProtocol_` | Cython setter | `(setter, ctx, arg, out) -> int` | Setter for `__dlpack_device__` protocol (non-tensor); unpacks 2-tuple into Device (0f8bf9f) |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `Function.release_gil` | `bool` (property, default `True`) | Controls whether GIL is released during FFI call |
| `__dlpack_c_exchange_api__` | `PyCapsule` (type attr, name `"dlpack_exchange_api"`) | Pointer to `DLPackExchangeAPI` struct wrapped in PyCapsule; renamed from `__c_dlpack_exchange_api__` in 5393647; migrated from `int` in 7f3bb77. Backward compat: `_check_and_update_dlpack_c_exchange_api` detects old name and auto-creates new one. |
| `__tvm_ffi_value__` | `() -> Any` (protocol) | Generic value conversion protocol (3dd7a81); returned value undergoes full recursive dispatch via `TVMFFIPySetArgumentGenericDispatcher`. Dispatched after `__tvm_ffi_float__`, before Exception. |
| `__tvm_ffi_object__` | `() -> tvm_ffi.Object` (protocol) | Duck-typing protocol for FFI Object wrappers; dynamic type index (8873700) |
| `__cuda_stream__` | `() -> tuple[str, int]` (protocol) | CUDA stream protocol; int packed as kTVMFFIOpaquePtr (b0537f0) |
| `__tvm_ffi_opaque_ptr__` | `() -> int` (protocol) | Opaque void* pointer protocol; packed as kTVMFFIOpaquePtr (42e0612) |
| `__dlpack_data_type__` | `() -> tuple[int, int, int]` (protocol) | DLPack dtype protocol; returns `(type_code, bits, lanes)` tuple, auto-converted to DLDataType. Dispatched after numpy.dtype, before Exception. (5e648f0) |
| `__dlpack_device__` | `() -> tuple[int, int]` (protocol, non-tensor only) | DLPack device protocol; returns `(device_type, device_id)` tuple, auto-converted to Device. Guard: requires no `__dlpack__` attr (prevents tensor misclassification). (0f8bf9f) |
| `__tvm_ffi_int__` | `() -> int` (protocol) | Duck-typing protocol for custom integer types; value passed as `kTVMFFIInt` (c1df05f) |
| `__tvm_ffi_float__` | `() -> float` (protocol) | Duck-typing protocol for custom float types; value passed as `kTVMFFIFloat` (c1df05f) |
| `TVMFFIPyArgSetterCUDAStreamProtocol_` | Cython setter | `(setter, ctx, arg, out) -> int` | Setter for `__cuda_stream__` protocol objects; renamed from `TVMFFIPyArgSetterCUDAStream_` (6c85e56) |
| `TVMFFIPyArgSetterCUDADriverStreamFallback_` | Cython setter | `(setter, ctx, arg, out) -> int` | Fallback for `cuda.bindings.driver.CUstream` without `__cuda_stream__` protocol (6c85e56) |
| `TVMFFIPyArgSetterIntegral_` | Cython setter | `(setter, ctx, arg, out) -> int` | Setter for `numbers.Integral` subclasses (e.g., `np.int32`) via Cython cast (c1df05f) |
| `TVMFFIPyArgSetterReal_` | Cython setter | `(setter, ctx, arg, out) -> int` | Setter for `numbers.Real` subclasses (e.g., `np.float64`) via Cython cast (c1df05f) |
| `TVMFFIPyArgSetterIntProtocol_` | Cython setter | `(setter, ctx, arg, out) -> int` | Setter for `__tvm_ffi_int__` protocol (c1df05f) |
| `TVMFFIPyArgSetterFloatProtocol_` | Cython setter | `(setter, ctx, arg, out) -> int` | Setter for `__tvm_ffi_float__` protocol (c1df05f) |
| `TVMFFIPyArgSetterFFIObjectProtocol_` | Cython setter | `(setter, ctx, arg, out) -> int` | Renamed from `TVMFFIPyArgSetterFFIObjectCompatible_`; handles `__tvm_ffi_object__` protocol (c1df05f) |
| `TVMFFIPyArgSetterFFIValueProtocol_` | Cython setter | `(setter, ctx, arg, out) -> int` | Setter for `__tvm_ffi_value__` protocol; calls method, pushes result to extra_temp_py_objects_stack, recursively dispatches (3dd7a81) |
| `_get_dlpack_exchange_api` | Cython function (tensor.pxi) | `(object dlpack_exchange_api_obj, const DLPackExchangeAPI** out_ptr) -> int` | Extracts `DLPackExchangeAPI*` from either `int` (cast) or `PyCapsule` (name `"dlpack_exchange_api"`); raises `ValueError` if neither (7f3bb77) |
| `_create_dlpack_exchange_api_capsule` | Python function (_optional_torch_c_dlpack.py) | `(ptr_as_int: int) -> PyCapsule` | Creates PyCapsule wrapping raw pointer with name `"dlpack_exchange_api"` via `ctypes.pythonapi.PyCapsule_New` (7f3bb77) |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | -- | Dispatch system is Python/Cython-specific |
