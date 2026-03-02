---
author: "Tianqi Chen <tqchen@users.noreply.github.com>"
subject: "Add thread-local stream context to FFI env C API"
scope:
  - "ffi/extra"
  - "c_env_api"
impact: "medium"
---
# [FFI][REFACTOR] Establish Stream Context in ffi (#18216)
## TL;DR
- Adds a thread-local `StreamContext` class that stores per-device stream handles in a 2D vector indexed by `(device_type, device_id)`.
- Exposes two new C ABI functions: `TVMFFIEnvSetStream` (set current stream, optionally return previous) and `TVMFFIEnvGetCurrentStream` (get current stream).
- Wires the new `stream_context.cc` into the CMake build under `TVM_FFI_USE_EXTRA_CXX_API`.

## Impact
- API: Two new C ABI symbols (`TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`) and one new typedef (`TVMFFIStreamHandle = void*`). These are additive; no existing callers affected.
- Flags/config: None. Guarded by existing `TVM_FFI_USE_EXTRA_CXX_API` CMake option.
- Data formats/schemas: None.

## Design Elements
Design elements this commit consumes:
- `TVM_FFI_SAFE_CALL_BEGIN/END` and `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` macros for C ABI error handling.
- `c_env_api.h` header as the home for environment-level C functions (previously only `TVMFFIEnvModuleLookupFunc`).

Design elements this commit produces:
- **Thread-local stream context pattern**: `StreamContext::ThreadLocal()` returns a `thread_local` singleton. The 2D vector (`stream_table_[device_type][device_id]`) grows on demand. Streams are weak references (not owned).
- **`TVMFFIEnvSetStream` swap idiom**: Atomically sets a new stream and optionally returns the old one via an output pointer, enabling RAII-style save/restore patterns.

## Reflection
- The stream table uses `std::vector<std::vector<void*>>` with dynamic resizing. This is simple but not contiguous; for a small number of device types and IDs this is fine.
- `TVMFFIEnvGetCurrentStream` uses `TVM_FFI_LOG_EXCEPTION_CALL_END` (log-only, no error return) because it returns a raw pointer, not an int error code. This is consistent with the design that non-int-returning C APIs log rather than propagate errors.
- The commit message says "migrate the existing per device API stream context management to ffi env API", indicating upstream TVM previously managed streams elsewhere and this centralizes it.
