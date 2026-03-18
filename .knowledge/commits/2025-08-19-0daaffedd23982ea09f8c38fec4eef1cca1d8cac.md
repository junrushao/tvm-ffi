---
author: "Tianqi Chen <tqchen@users.noreply.github.com>"
subject: "Establish thread-local stream context in FFI env API"
commit_shape: "standard"
commit_type: "refactor"
potential_duplicate: ""
scope:
  - "c-env-api"
  - "stream-context"
---
# Establish thread-local stream context in FFI env API

## TL;DR
- Adds two new C ABI functions (`TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`) and a `TVMFFIStreamHandle` typedef to `c_env_api.h`, providing a device-indexed, thread-local stream context at the FFI layer.
- Implements a `StreamContext` class in `src/ffi/extra/stream_context.cc` using a 2D vector (`stream_table_[device_type][device_id]`) with lazy resizing.
- Migrates per-device stream management from downstream runtime code into the shared FFI environment, enabling consistent stream handling across library integrations.

## Key Exports

```python
# New opaque handle type
TVMFFIStreamHandle = void_ptr  # Opaque stream pointer (e.g. cudaStream_t, hipStream_t)

def TVMFFIEnvSetStream(
    device_type: int32,
    device_id: int32,
    stream: TVMFFIStreamHandle,
    opt_out_original_stream: Optional[Ptr[TVMFFIStreamHandle]]
) -> int:
    """Set the current stream for a (device_type, device_id) pair in TLS context.
    Returns 0 on success, nonzero on failure."""
    # Interacts with: StreamContext::ThreadLocal() (thread-local singleton)
    # Interacts with: TVM_FFI_SAFE_CALL_BEGIN/END (error propagation via TLS)
    # Invariant: stream is a weak reference -- caller owns the stream lifetime
    # Invariant: if opt_out_original_stream is not nullptr, the previous stream is written there
    # Extension: downstream runtime calls this to swap in a compute stream before kernel launches
    ...

def TVMFFIEnvGetCurrentStream(
    device_type: int32,
    device_id: int32
) -> TVMFFIStreamHandle:
    """Get the current stream for a (device_type, device_id) pair from TLS context.
    Returns nullptr if no stream was set."""
    # Interacts with: StreamContext::ThreadLocal()
    # Interacts with: TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END (logs but does not propagate via TLS)
    # Invariant: returns nullptr for any device pair that was never set
    ...

# Internal implementation (not exported, but architecturally significant):
class StreamContext:
    """Thread-local stream context. One instance per thread."""
    stream_table_: List[List[TVMFFIStreamHandle]]  # stream_table_[device_type][device_id]

    def SetStream(self, device_type: int32, device_id: int32,
                  stream: TVMFFIStreamHandle,
                  out_original_stream: Optional[Ptr[TVMFFIStreamHandle]]) -> None:
        # Invariant: lazily resizes both dimensions -- never shrinks
        # Invariant: new slots initialized to nullptr
        ...

    def GetStream(self, device_type: int32, device_id: int32) -> TVMFFIStreamHandle:
        # Returns nullptr if indices are out of range (no resize on read)
        ...

    @staticmethod
    def ThreadLocal() -> Ptr[StreamContext]:
        # Interacts with: C++ thread_local storage
        ...
```

## Impact
- API: Two new C ABI symbols (`TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`) and one new typedef (`TVMFFIStreamHandle`) added to `c_env_api.h`. Purely additive -- no existing symbols changed.
- Behavioral: Downstream code that previously maintained its own per-device stream tracking can now delegate to the FFI layer, getting thread-safety for free.
- Flags/config: `TVM_FFI_USE_EXTRA_CXX_API` CMake flag must be ON to include `stream_context.cc` in the build (same gate as other `src/ffi/extra/` files).
- Data formats/schemas: None.

## Design Elements
Design elements this commit consumes:
- **C env API pattern** (`c_env_api.h`) -- follows the existing `TVMFFIEnv*` naming convention and `extern "C"` + `TVM_FFI_DLL` export pattern established by `TVMFFIEnvLookupFromImports`, `TVMFFIEnvRegisterContextSymbol`, etc.
- **TVM_FFI_SAFE_CALL_BEGIN/END** (`include/tvm/ffi/function.h`) -- standard error-boundary macros for C ABI functions that return `int`.
- **TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END** (`include/tvm/ffi/base_details.h`) -- variant for functions that return a value directly (not int status), used by `TVMFFIEnvGetCurrentStream`.
- **CMake extra source list** (`CMakeLists.txt`) -- the `TVM_FFI_USE_EXTRA_CXX_API` guarded source list pattern.

Design elements this commit produces:
- **Thread-local stream context** -- a new per-thread, per-device stream registry at the FFI layer. This is the first FFI-level resource-context abstraction (previously only error TLS existed at this layer).
- **TVMFFIStreamHandle opaque type** -- establishes the convention that device streams are passed as opaque `void*` through the C ABI.

## Usage Examples

Setting and restoring a device stream from C (typical pattern for a kernel library):

```c
#include <tvm/ffi/extra/c_env_api.h>

// Before launching kernels on device (cuda:0), set the compute stream
TVMFFIStreamHandle original = NULL;
TVMFFIEnvSetStream(/*device_type=*/2, /*device_id=*/0,
                   my_cuda_stream, &original);

// ... launch kernels -- they pick up the stream via TVMFFIEnvGetCurrentStream(2, 0) ...

// Restore the original stream
TVMFFIEnvSetStream(2, 0, original, NULL);
```

Querying the current stream (e.g., from a runtime backend):

```c
TVMFFIStreamHandle stream = TVMFFIEnvGetCurrentStream(/*device_type=*/2, /*device_id=*/0);
if (stream != NULL) {
    // Use the stream for synchronization or kernel launch
}
// Returns NULL if no stream was ever set for this device
```

## Reflection

### Design docs to write or update
- `$REPO_MAIN/.knowledge/designs/0001-c-abi.md` -- Add `TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`, and `TVMFFIStreamHandle` to the "C API Function Table" section, and add a "Stream Context" subsection under Extension Points describing the thread-local device stream registry.

### ADRs to write or update
- None.

### Stale knowledge references
- None -- no existing `.knowledge/` files reference symbols renamed or removed by this commit.
