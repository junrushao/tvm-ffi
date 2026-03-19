---
author: "tqchen"
subject: "Establish thread-local stream context API in FFI env layer"
commit_shape: "standard"
commit_type: "feature"
potential_duplicate: ""
has_design_updates: false
scope:
  - "ffi/c-api"
  - "ffi/extra"
---
# Establish thread-local stream context API in FFI env layer
## TL;DR
- Adds `TVMFFIEnvSetStream` and `TVMFFIEnvGetCurrentStream` C ABI functions to `c_env_api.h` for per-device, per-thread stream tracking.
- Implements `StreamContext` as a thread-local class in `src/ffi/extra/stream_context.cc` backed by a 2D vector indexed by `(device_type, device_id)`.
- Migrates stream context management from per-device API into the FFI env layer, centralizing it for cross-library integration.

## Key Exports

```python
# --- New type alias ---
TVMFFIStreamHandle = void_ptr  # Opaque handle for device streams (e.g., CUDA streams)

# --- New C ABI functions (c_env_api.h) ---
def TVMFFIEnvSetStream(
    device_type: int32,
    device_id: int32,
    stream: TVMFFIStreamHandle,
    opt_out_original_stream: Optional[TVMFFIStreamHandle_ptr],
) -> int:
    """Set the current stream for a device in thread-local context."""
    # Interacts with: StreamContext::ThreadLocal() (thread-local singleton)
    # Invariant: stream is a weak reference owned by the caller/module, not freed here
    # Returns: 0=success, nonzero=error (via TVM_FFI_SAFE_CALL_BEGIN/END)

def TVMFFIEnvGetCurrentStream(device_type: int32, device_id: int32) -> TVMFFIStreamHandle:
    """Get the current stream for a device from thread-local context."""
    # Interacts with: StreamContext::ThreadLocal()
    # Invariant: returns nullptr if no stream has been set for the device
    # Returns: stream handle directly (error logging via TVM_FFI_LOG_EXCEPTION_CALL)

# --- Internal class (not public API, but key to understanding) ---
class StreamContext:
    """Thread-local stream registry indexed by (device_type, device_id)."""
    stream_table_: List[List[TVMFFIStreamHandle]]  # 2D vector, lazily resized

    def SetStream(self, device_type: int32, device_id: int32,
                  stream: TVMFFIStreamHandle,
                  out_original_stream: Optional[TVMFFIStreamHandle_ptr]) -> None:
        # Invariant: resizes stream_table_ on demand (never shrinks)
        # Extension: new device types auto-accommodated via resize
        ...

    def GetStream(self, device_type: int32, device_id: int32) -> TVMFFIStreamHandle:
        # Returns nullptr for unset (device_type, device_id) pairs
        ...

    @staticmethod
    def ThreadLocal() -> StreamContext:
        # Singleton per thread via static thread_local
        ...
```

## Impact
- API: Additive -- two new C ABI functions in `c_env_api.h`. No existing signatures changed.
- Behavioral: None -- no existing functions affected.
- Flags/config: Compiled only when `TVM_FFI_USE_EXTRA_CXX_API=ON` (default ON).
- Data formats/schemas: None.

## Design Elements
Design elements this commit consumes:
- **C ABI conventions** (0007-c-abi): uses `TVM_FFI_DLL` visibility macro, `extern "C"` linkage, return-code error convention.
- **Error handling macros** (0004-error-propagation): `TVM_FFI_SAFE_CALL_BEGIN/END` for `SetStream` (returns int), `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` for `GetCurrentStream` (returns handle directly).

Design elements this commit produces:
- **Thread-local stream context**: New concept -- a minimalistic per-thread table mapping `(device_type, device_id)` to opaque stream handles. Designed for downstream libraries (CUDA, ROCm, etc.) to share stream state via FFI without direct coupling.
- **`TVMFFIStreamHandle` type alias**: Opaque `void*` handle for streams, exposed at C ABI level.

## Usage Examples
No callers exist within this commit's diff. Expected usage pattern:

```c
// Set a CUDA stream for device 0 in the current thread
TVMFFIStreamHandle original = NULL;
int ret = TVMFFIEnvSetStream(/*device_type=*/kDLCUDA, /*device_id=*/0,
                              my_cuda_stream, &original);
// original now holds the previously-set stream (or NULL)

// Later, retrieve it
TVMFFIStreamHandle current = TVMFFIEnvGetCurrentStream(kDLCUDA, 0);
// current == my_cuda_stream
```

## Reflection

### Design docs to write or update
- `0007-c-abi.md`: Add `TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`, and `TVMFFIStreamHandle` to the C API Functions section under a "Stream Context" subsection.

### Stale knowledge references
None
