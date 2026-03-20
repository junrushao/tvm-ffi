---
author: "tqchen"
subject: "Establish stream context in FFI env API"
commit_shape: "standard"
commit_type: "feature"
potential_duplicate: ""
has_design_updates: true
scope:
  - "ffi/extra"
  - "ffi/c-env-api"
---
# Establish stream context in FFI env API
## TL;DR
- Adds a thread-local stream context to the FFI env API (`c_env_api.h`), providing `TVMFFIEnvSetStream` and `TVMFFIEnvGetCurrentStream` for per-device stream management.
- Migrates the concept of per-device stream tracking from scattered device API implementations into the centralized FFI environment layer.
- Implements `StreamContext` as a thread-local class backed by a 2D vector indexed by `(device_type, device_id)`.

## Key Exports

```python
# --- C Env API: Stream Context ---
# New opaque handle type for device streams
TVMFFIStreamHandle = void_ptr  # typedef void* TVMFFIStreamHandle

def TVMFFIEnvSetStream(
    device_type: int32,
    device_id: int32,
    stream: TVMFFIStreamHandle,
    opt_out_original_stream: Optional[Ptr[TVMFFIStreamHandle]]  # nullable out-param
) -> int:
    """Set the current stream for a (device_type, device_id) pair."""
    # Interacts with: StreamContext::ThreadLocal()->SetStream()
    # Interacts with: TVM_FFI_SAFE_CALL_BEGIN/END (error propagation via return code)
    # Invariant: stream is a weak reference — caller owns the stream lifetime
    # Invariant: opt_out_original_stream receives the previously-set stream if non-null
    # Extension: called by device runtime integrations (CUDA, Metal, etc.) to register active stream
    ...

def TVMFFIEnvGetCurrentStream(device_type: int32, device_id: int32) -> TVMFFIStreamHandle:
    """Get the current stream for a (device_type, device_id) pair."""
    # Interacts with: StreamContext::ThreadLocal()->GetStream()
    # Interacts with: TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END (logs exception, returns value directly)
    # Invariant: returns nullptr if no stream has been set for (device_type, device_id)
    ...

# --- Internal: StreamContext (C++ only, not part of C ABI surface) ---
class StreamContext:
    """Thread-local stream registry indexed by (device_type, device_id)."""
    stream_table_: List[List[TVMFFIStreamHandle]]  # 2D vector, auto-grows

    def SetStream(self, device_type: int32, device_id: int32,
                  stream: TVMFFIStreamHandle,
                  out_original_stream: Optional[Ptr[TVMFFIStreamHandle]]) -> None:
        # Invariant: auto-resizes stream_table_ to fit (device_type, device_id)
        ...

    def GetStream(self, device_type: int32, device_id: int32) -> TVMFFIStreamHandle:
        # Invariant: returns nullptr for out-of-bounds indices (no exception)
        ...

    @staticmethod
    def ThreadLocal() -> StreamContext:
        # Interacts with: thread_local storage (one instance per thread)
        ...
```

## Impact
- API: Adds two new C API functions (`TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`) and one typedef (`TVMFFIStreamHandle`) to `c_env_api.h`. Purely additive; no existing API changes.
- Behavioral: None -- new functionality only.
- Flags/config: `TVM_FFI_USE_EXTRA_CXX_API` CMake flag must be ON (existing flag) to include `stream_context.cc` in the build.
- Data formats/schemas: None.

## Design Elements
Design elements this commit consumes:
- **C ABI error handling macros** (`TVM_FFI_SAFE_CALL_BEGIN/END`, `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END`) from `function.h` and `base_details.h` — documented in [0001-ffi-c-abi](../design-records/0001-ffi-c-abi.md) and [0005-ffi-error-protocol](../design-records/0005-ffi-error-protocol.md).
- **`TVM_FFI_DLL` export macro** from `c_api.h` — documented in [0001-ffi-c-abi](../design-records/0001-ffi-c-abi.md).
- **C env API pattern** (`TVMFFIEnv*` function naming, `c_env_api.h` header location) established by existing `TVMFFIEnvLookupFromImports`, `TVMFFIEnvRegisterContextSymbol`, `TVMFFIEnvRegisterSystemLibSymbol`.

Design elements this commit produces:
- **Stream context C env API** — `TVMFFIStreamHandle`, `TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`. A minimalistic thread-local stream registry for per-device stream tracking. Not yet documented in any design record.
- **`StreamContext` internal class** — thread-local 2D vector storage pattern for (device_type, device_id)-indexed context. Establishes a pattern for future per-device thread-local state.

## Usage Examples
**Context**: A device runtime integration (e.g., CUDA) sets the active stream before dispatching kernels, and retrieves it at dispatch time.
```c
// Set stream for CUDA device 0 (device_type=2 for kDLCUDA)
TVMFFIStreamHandle original = NULL;
int ret = TVMFFIEnvSetStream(2, 0, my_cuda_stream, &original);
// original now holds the previously-set stream (or NULL if none)

// Later, in kernel dispatch code:
TVMFFIStreamHandle current = TVMFFIEnvGetCurrentStream(2, 0);
// current == my_cuda_stream (or NULL if unset)

// Restore original stream after work
TVMFFIEnvSetStream(2, 0, original, NULL);
```

## Reflection

### Design docs / ADRs to write or update
- `$REPO_MAIN/.knowledge/design-records/0001-ffi-c-abi.md` — Add `TVMFFIStreamHandle`, `TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream` to the C env API section. Note the two error-handling conventions used (safe-call return code vs. direct-return with log-on-exception).

### Stale knowledge references
None.
