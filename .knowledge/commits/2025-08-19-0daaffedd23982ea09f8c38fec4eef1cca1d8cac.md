---
author: "Tianqi Chen"
subject: "Establish thread-local stream context in FFI env API for per-device stream management"
commit_shape: "standard"
scope:
  - "c-abi"
  - "error-handling"
impact: "medium"
abi_breaking: false
related_commits: []
---
# Establish thread-local stream context in FFI env API for per-device stream management

## TL;DR
- Introduces `TVMFFIStreamHandle` typedef and two new C API functions (`TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`) in `c_env_api.h` for thread-local per-device stream context management.
- Adds `StreamContext` class in `src/ffi/extra/stream_context.cc` backed by a 2D `vector<vector<void*>>` table indexed by `(device_type, device_id)`, accessed via `thread_local` singleton.
- Wires the new source file into the `TVM_FFI_USE_EXTRA_CXX_API` CMake build.

## Key Exports

**Types/Typedefs**:
- `TVMFFIStreamHandle` -- `typedef void*`. Opaque handle representing a device stream. Declared in `include/tvm/ffi/extra/c_env_api.h`.

**Functions**:
- `TVMFFIEnvSetStream(int32_t device_type, int32_t device_id, TVMFFIStreamHandle stream, TVMFFIStreamHandle* opt_out_original_stream) -> int` -- Sets the current stream for a `(device_type, device_id)` pair in the thread-local context. Optionally returns the previous stream via `opt_out_original_stream` (pass `nullptr` to skip). Returns 0 on success; uses `TVM_FFI_SAFE_CALL_BEGIN/END` for error boundary.
- `TVMFFIEnvGetCurrentStream(int32_t device_type, int32_t device_id) -> TVMFFIStreamHandle` -- Returns the current stream for the given device, or `nullptr` if none set. Uses `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` (log-and-abort on exception, no TLS error propagation).

**Internal Classes** (not public API, but architecturally significant):
- `tvm::ffi::StreamContext` -- Thread-local singleton managing a 2D `vector<vector<TVMFFIStreamHandle>>` table. Key methods: `SetStream(device_type, device_id, stream, out_original_stream)`, `GetStream(device_type, device_id)`, `ThreadLocal()`.

## Impact
- API: Two new C API functions added to `c_env_api.h`. No existing APIs modified.
- ABI: No breakage. Purely additive -- new symbols only.
- Behavioral: None -- no existing function behavior is changed.
- Flags/config: None. The new file is compiled under the existing `TVM_FFI_USE_EXTRA_CXX_API` flag (default ON).
- Data formats/schemas: None.

## Design Elements
Design elements this commit consumes:
- **C ABI error boundary macros** (`TVM_FFI_SAFE_CALL_BEGIN/END`, `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END`) from `.knowledge/designs/error-handling.md`. `TVMFFIEnvSetStream` uses the standard safe-call pattern (catch -> TLS -> return -1). `TVMFFIEnvGetCurrentStream` uses the log-exception pattern (catch -> log -> abort) because it returns a value directly rather than through an out-parameter, so TLS error propagation is not feasible.
- **`TVM_FFI_DLL` visibility macro** from `.knowledge/designs/c-abi.md` for marking both functions as exported symbols.
- **`c_env_api.h` env API header** -- existing header for environment-level C functions (module lookup, context symbols). This commit adds the stream section before the existing module symbol management section.
- **CMake `TVM_FFI_USE_EXTRA_CXX_API` flag** -- gates compilation of non-core C++ extras in `src/ffi/extra/`.

Design elements this commit produces:
- **Thread-local stream context** -- A new per-thread, per-device stream tracking mechanism in the FFI layer. This centralizes stream management that was previously scattered across per-device-type backends, providing a single C ABI for stream get/set that all device backends can use.
- **`TVMFFIStreamHandle` opaque type** -- Establishes the convention that streams are opaque `void*` handles at the FFI boundary. The FFI layer does not allocate or deallocate streams; it only records weak references.
- **Dual error-handling pattern for C API returns** -- This commit demonstrates when to use `TVM_FFI_SAFE_CALL` (int return with TLS error) vs `TVM_FFI_LOG_EXCEPTION_CALL` (direct value return with abort-on-error). The choice depends on whether the function returns a value directly.

## Usage Examples

### Setting and getting stream context from C
**Context**: A device backend sets its current stream, then later retrieves it for kernel dispatch.
```c
// Set the CUDA stream (device_type=2) for device 0
TVMFFIStreamHandle old_stream = NULL;
int ret = TVMFFIEnvSetStream(/*device_type=*/2, /*device_id=*/0,
                              my_cuda_stream, &old_stream);
// old_stream now holds the previous stream (or NULL if none was set)

// Later, retrieve the current stream for the same device
TVMFFIStreamHandle current = TVMFFIEnvGetCurrentStream(2, 0);
// current == my_cuda_stream
```

### Scoped stream swap pattern
**Context**: Temporarily switching a device stream and restoring the original.
```c
TVMFFIStreamHandle saved;
TVMFFIEnvSetStream(device_type, device_id, new_stream, &saved);
// ... execute kernels on new_stream ...
TVMFFIEnvSetStream(device_type, device_id, saved, NULL);  // restore
```

## Reflection

### Design docs to write or update
- `.knowledge/designs/c-abi.md` -- Add `TVMFFIStreamHandle`, `TVMFFIEnvSetStream`, and `TVMFFIEnvGetCurrentStream` to the "C API Function Summary" table and document the stream context section. Note the dual error-handling patterns (safe-call vs log-exception) and when each is appropriate.
- `.knowledge/designs/error-handling.md` -- Document the `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` pattern as a distinct error boundary for functions that return values directly (not through out-params). Currently only `TVM_FFI_SAFE_CALL_BEGIN/END` is documented.

### ADRs to write or update
None.

### Stale knowledge references
None.
