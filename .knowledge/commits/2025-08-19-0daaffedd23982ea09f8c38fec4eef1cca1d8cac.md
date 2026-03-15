---
author: "Tianqi Chen"
subject: "Establish thread-local stream context in FFI extra env API"
commit_shape: "standard"
commit_type: "feature"
scope:
  - "c-abi-layer"
  - "extra-api-isolation"
---
# Establish thread-local stream context in FFI extra env API
## TL;DR
- Adds a per-device, per-thread stream context to the FFI extra environment API, enabling centralized stream management across device backends.
- Introduces two new C ABI functions (`TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`) and a new opaque handle type (`TVMFFIStreamHandle`).
- Implementation uses a `thread_local` 2D vector (`stream_table_[device_type][device_id]`) that grows on demand; no allocation/deallocation of the stream itself.

## Key Exports

**Types**:
```c
typedef void* TVMFFIStreamHandle;
```
Opaque handle representing a device stream. The FFI layer does not own or manage the stream's lifecycle -- it is a weak reference cached by the caller's module.

**Functions**:
```c
TVM_FFI_DLL int TVMFFIEnvSetStream(
    int32_t device_type,
    int32_t device_id,
    TVMFFIStreamHandle stream,
    TVMFFIStreamHandle* opt_out_original_stream);
```
Sets the current stream for `(device_type, device_id)` in thread-local storage. Optionally returns the previous stream via `opt_out_original_stream` (pass `nullptr` to skip). Returns 0 on success, nonzero on failure.

```c
TVM_FFI_DLL TVMFFIStreamHandle TVMFFIEnvGetCurrentStream(
    int32_t device_type,
    int32_t device_id);
```
Returns the current stream for `(device_type, device_id)`, or `nullptr` if none has been set. Uses `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` (logs rather than propagates exceptions to TLS).

**Internal class** (not exported, but architecturally significant):
```cpp
// tvm::ffi::StreamContext  (src/ffi/extra/stream_context.cc)
class StreamContext {
  void SetStream(int32_t device_type, int32_t device_id,
                 TVMFFIStreamHandle stream, TVMFFIStreamHandle* out_original_stream);
  TVMFFIStreamHandle GetStream(int32_t device_type, int32_t device_id);
  static StreamContext* ThreadLocal();  // thread_local singleton
 private:
  std::vector<std::vector<TVMFFIStreamHandle>> stream_table_;
};
```

## Impact
- API: Two new C ABI symbols added to `c_env_api.h`. No existing symbols changed.
- Behavioral: None -- purely additive. Existing device-specific stream management in downstream code is unaffected until migrated.
- Flags/config: Compiled only when `TVM_FFI_USE_EXTRA_CXX_API=ON` (default ON), via new entry in `CMakeLists.txt`.
- Data formats/schemas: None.

## Design Elements
Design elements this commit consumes:
- **C ABI layer** ([0001-c-abi-layer.md](../designs/0001-c-abi-layer.md)): Uses `TVM_FFI_DLL` export macro, follows C ABI function signature conventions (return `int`, 0=success).
- **Extra API isolation** ([ADR 0010](../ADRs/0010-extra-api-isolation.md)): Places new code in `include/tvm/ffi/extra/c_env_api.h` and `src/ffi/extra/stream_context.cc`, guarded by `TVM_FFI_USE_EXTRA_CXX_API`.
- **Error handling macros** ([0006-error-handling.md](../designs/0006-error-handling.md)): `TVM_FFI_SAFE_CALL_BEGIN/END` for `TVMFFIEnvSetStream` (propagates exceptions to TLS, returns nonzero). `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` for `TVMFFIEnvGetCurrentStream` (logs exception, returns value directly).

Design elements this commit produces:
- **Stream context**: Thread-local per-device stream tracking via `TVMFFIEnvSetStream`/`TVMFFIEnvGetCurrentStream`. This is a new cross-cutting concern in the FFI layer -- any backend that manages device streams (CUDA, ROCm, Vulkan, etc.) can use this centralized context instead of maintaining its own TLS.

## Usage Examples
Setting and querying a device stream from C:
```c
// Set a CUDA stream for device 0
TVMFFIStreamHandle old_stream = NULL;
int ret = TVMFFIEnvSetStream(
    /*device_type=*/2,  // kDLCUDA
    /*device_id=*/0,
    my_cuda_stream,
    &old_stream);       // optionally capture previous stream

// Later: retrieve current stream for the same device
TVMFFIStreamHandle cur = TVMFFIEnvGetCurrentStream(2, 0);
// cur == my_cuda_stream (assuming same thread)
```

## Reflection

### Design docs to write or update
- `$REPO_MAIN/.knowledge/designs/0001-c-abi-layer.md`: Add `TVMFFIEnvSetStream` and `TVMFFIEnvGetCurrentStream` to the exported C functions table and mention `TVMFFIStreamHandle` as a new ABI type.
- `$REPO_MAIN/.knowledge/designs/XXXX-stream-context.md`: New design doc for stream context -- covering the thread-local storage pattern, the 2D vector growth strategy, the weak-reference ownership model, and intended migration path from per-device stream management. A Mermaid sequence diagram showing set/get flow across threads would help.

### ADRs to write or update
- `$REPO_MAIN/.knowledge/ADRs/0010-extra-api-isolation.md`: Add `stream_context.cc` to the list of extra API source files and `TVMFFIEnvSetStream`/`TVMFFIEnvGetCurrentStream` to the list of extra C API functions.

### Stale knowledge references
None -- no symbols were renamed or removed by this commit.
