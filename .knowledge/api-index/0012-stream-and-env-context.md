---
scope: "stream-and-env-context"
---
# API Index: Stream Exchange and Environment Context

**Scope**: Thread-local environment context, stream exchange protocols, DLPack fast-path converters, and Python stream context managers.
**Design docs**: [0014-stream-and-env-context.md](../designs/0014-stream-and-env-context.md)
**ADRs**: [0011-cached-type-dispatch-ffi-call.md](../ADRs/0011-cached-type-dispatch-ffi-call.md), [0015-dlpack-exchange-api-struct.md](../ADRs/0015-dlpack-exchange-api-struct.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `EnvContext` | class | `stream_table_`, `dlpack_allocator_`, `ThreadLocal()`, `GlobalTensorAllocator()` | Thread-local env context managing streams and tensor allocator (was `StreamContext`, f81ab9c) |
| `TVMFFIEnvSetStream` | C ABI function | `(device_type, device_id, stream, opt_out_original) -> int` | Set per-device stream in TLS (was `TVMFFIEnvSetCurrentStream`, renamed f81ab9c) |
| `TVMFFIEnvGetStream` | C ABI function | `(device_type, device_id) -> TVMFFIStreamHandle` | Get per-device stream from TLS (was `TVMFFIEnvGetCurrentStream`, renamed f81ab9c) |
| `TVMFFIEnvSetDLPackManagedTensorAllocator` | C ABI function | `(allocator, write_to_global, opt_out_original) -> int` | Set DLPack tensor allocator in TLS and/or global context (renamed from TVMFFIEnvSetTensorAllocator, 9829dec/f679fe5) |
| `TVMFFIEnvGetDLPackManagedTensorAllocator` | C ABI function | `() -> DLPackManagedTensorAllocator` | Get tensor allocator (TLS first, global fallback) (renamed from TVMFFIEnvGetTensorAllocator, 9829dec/f679fe5) |
| `TVMFFIEnvTensorAlloc` | C ABI function | `(DLTensor* prototype, TVMFFIObjectHandle* out) -> int` | Allocate ffi::Tensor via env allocator; wrapping inside libtvm_ffi (f679fe5) |
| `DLPackManagedTensorAllocator` | typedef | `fn(prototype, out, error_ctx, SetError) -> int` | C-style allocator callback for DLPack tensors (renamed from DLPackTensorAllocator, 9829dec) |
| `Tensor::FromEnvAlloc` | static method | `(env_alloc, shape, dtype, device) -> Tensor` | Create tensor via env allocator function pointer (renamed from FromDLPackAlloc, f679fe5) |
| `DLPackExchangeAPI` | struct | `header`, `managed_tensor_allocator`, `managed_tensor_from_py_object_no_sync`, `managed_tensor_to_py_object_no_sync`, `dltensor_from_py_object_no_sync`, `current_work_stream` | Unified DLPack exchange struct (22a7894). Replaces separate function pointer dunders |
| `DLPackExchangeAPIHeader` | struct | `version: DLPackVersion`, `prev_api: Ptr[DLPackExchangeAPIHeader]` | Versioned header for API chaining (22a7894) |
| ~~`DLPackFromPyObject`~~ | typedef | Replaced by `DLPackManagedTensorFromPyObjectNoSync` | Renamed to `_no_sync` variant in DLPackExchangeAPI (22a7894) |
| ~~`DLPackToPyObject`~~ | typedef | Replaced by `DLPackManagedTensorToPyObjectNoSync` | Renamed to `_no_sync` variant in DLPackExchangeAPI (22a7894) |
| `DLPackDLTensorFromPyObjectNoSync` | typedef | `fn(py_obj, out_dltensor) -> int` | Non-owning DLTensor conversion (NEW in 22a7894) |
| `DLPackCurrentWorkStream` | typedef | `fn(device_type, device_id, out_stream) -> int` | Explicit stream query (NEW in 22a7894) |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `StreamContext` | `class StreamContext` | Context manager for save/restore of FFI env stream |
| `TorchStreamContext` | `class TorchStreamContext` | Bridge torch.cuda.Stream/CUDAGraph to FFI env stream |
| `use_torch_stream` | `def use_torch_stream(context: Optional[Any] = None) -> TorchStreamContext` | Factory for TorchStreamContext |
| `use_raw_stream` | `def use_raw_stream(device: Device, stream: Union[int, c_void_p]) -> StreamContext` | Factory for raw StreamContext |
| `get_raw_stream` | `def get_raw_stream(device: Device) -> int` | Get current FFI env stream for device. Read-side complement to `use_raw_stream` (22c049b) |
| `__tvm_ffi_env_stream__` | protocol dunder | `def __tvm_ffi_env_stream__(self) -> int` | Any `__dlpack__`-capable object can implement for automatic TLS stream exchange |
| `__cuda_stream__` | protocol dunder | `def __cuda_stream__(self) -> tuple[str, int]` | NVIDIA stream protocol; auto-converts to `kTVMFFIOpaquePtr` (b0537f0). Distinct from `__tvm_ffi_env_stream__` (passes value, does not set TLS) |
| `__dlpack_c_exchange_api__` | class attribute (PyCapsule) | Pointer to `DLPackExchangeAPI` struct via PyCapsule. Renamed from `__c_dlpack_exchange_api__` (5393647); backward compat via `_check_and_update_dlpack_c_exchange_api()` | Unified DLPack exchange API (22a7894). Replaces 3 separate dunders |
| ~~`__c_dlpack_from_pyobject__`~~ | class attribute (int) | Replaced by `DLPackExchangeAPI` struct | Removed (22a7894) |
| ~~`__c_dlpack_to_pyobject__`~~ | class attribute (int) | Replaced by `DLPackExchangeAPI` struct | Removed (22a7894) |
| ~~`__c_dlpack_tensor_allocator__`~~ | class attribute (int) | Replaced by `DLPackExchangeAPI` struct | Removed (22a7894) |
