---
author: "TVM FFI team"
subject: "Add thread-local stream context to FFI extra/ via new C env API functions"
commit_shape: "standard"
commit_type: "feature"
secondary_commit_type: ""
potential_duplicate: ""
has_design_updates: true
scope:
  - "ffi/extra"
  - "c-abi"
---
# Add thread-local stream context to FFI extra/ via new C env API functions

## TL;DR
- Introduces `TVMFFIStreamHandle` (typedef `void*`) and two C-ABI functions `TVMFFIEnvSetStream`/`TVMFFIEnvGetCurrentStream` in `include/tvm/ffi/extra/c_env_api.h`.
- Implements a thread-local `StreamContext` class backed by a `vector<vector<TVMFFIStreamHandle>>` indexed by `[device_type][device_id]`, compiled into `src/ffi/extra/stream_context.cc`.
- Migrates per-device stream context management into the FFI env API to streamline cross-library stream integration.

## Key Exports

```python
# New typedef: opaque handle for an accelerator stream (weak reference, never owned by FFI)
TVMFFIStreamHandle = void*   # C typedef

def TVMFFIEnvSetStream(
    device_type: int32_t,
    device_id: int32_t,
    stream: TVMFFIStreamHandle,
    opt_out_original_stream: TVMFFIStreamHandle* = nullptr,
) -> int:
    # Interacts with: StreamContext.ThreadLocal() (internal thread-local singleton)
    # Invariant: stream is a weak reference owned externally; FFI only caches it
    # Invariant: opt_out_original_stream receives the previous stream value (for RAII swap)
    # Returns: 0 on success, nonzero on failure (TVM_FFI_SAFE_CALL_BEGIN/END boundary)
    ...

def TVMFFIEnvGetCurrentStream(
    device_type: int32_t,
    device_id: int32_t,
) -> TVMFFIStreamHandle:
    # Interacts with: StreamContext.ThreadLocal() (internal thread-local singleton)
    # Invariant: returns nullptr if no stream has been set for (device_type, device_id)
    # Note: uses TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END (logs and re-raises, does not swallow)
    ...

# Internal (not exported, not in header):
class StreamContext:
    """Thread-local stream table, lazily resized."""
    stream_table_: List[List[TVMFFIStreamHandle]]  # indexed [device_type][device_id]

    def SetStream(self, device_type: int32_t, device_id: int32_t,
                  stream: TVMFFIStreamHandle,
                  out_original_stream: TVMFFIStreamHandle*) -> None:
        # Resizes stream_table_ lazily on first access per device_type/device_id
        # Invariant: unset slots contain nullptr (initialized on resize)
        ...

    def GetStream(self, device_type: int32_t, device_id: int32_t) -> TVMFFIStreamHandle:
        # Returns nullptr for any out-of-range device_type or device_id
        ...

    @staticmethod
    def ThreadLocal() -> StreamContext*:
        # static thread_local instance — one per OS thread
        ...
```

## Impact
- API: Two new `TVM_FFI_DLL` C functions added to `c_env_api.h`; purely additive, no existing signatures modified.
- Behavioral: Per-device stream state is now accessible via the stable C ABI rather than through C++-only TLS. Prior per-device API stream management was migrated here.
- Flags/config: `stream_context.cc` is gated by `TVM_FFI_USE_EXTRA_CXX_API` in `CMakeLists.txt` (consistent with other `extra/` sources).
- Data formats/schemas: None.

## Design Elements
Design elements this commit consumes:
- **0001-c-abi**: `TVM_FFI_DLL` visibility macro, `TVM_FFI_SAFE_CALL_BEGIN/END` and `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` error-boundary macros, `c_env_api.h` header pattern for `TVMFFIEnv*` functions.
- **0005-error-system**: Safe-call boundary macros (`TVM_FFI_SAFE_CALL_BEGIN/END`, `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END`) wrap both C-linkage functions.
- The `extra/` subsystem pattern (see 0009-structural-eq-hash, 0001-c-abi design records): optional compilation under `TVM_FFI_USE_EXTRA_CXX_API`, C-stable headers in `include/tvm/ffi/extra/`, implementation in `src/ffi/extra/`.

Design elements this commit produces:
- **TVMFFIStreamHandle** (`typedef void*`): new opaque handle type for accelerator streams in the FFI C ABI.
- **TVMFFIEnvSetStream / TVMFFIEnvGetCurrentStream**: new `TVMFFIEnv*` API pair extending `c_env_api.h` with per-device, per-thread stream context management.
- **StreamContext** (internal): thread-local singleton holding `vector<vector<void*>>` for O(1) get/set per `(device_type, device_id)` with lazy resize.

## Usage Examples

Setting the current CUDA stream for device 0, saving the old one for RAII restore:

```cpp
// C++ caller (or any C ABI consumer)
TVMFFIStreamHandle old_stream = nullptr;
TVMFFIEnvSetStream(/*device_type=*/2, /*device_id=*/0, new_stream, &old_stream);

// ... do work on new_stream ...

// Restore old stream (RAII pattern)
TVMFFIEnvSetStream(2, 0, old_stream, nullptr);

// Query the active stream
TVMFFIStreamHandle cur = TVMFFIEnvGetCurrentStream(2, 0);
// cur == nullptr if never set
```

## Reflection

### Design docs / ADRs to write or update
- `/Users/junrus/Projects/tvm-ffi-knowledge/.knowledge/design-records/0001-c-abi.md`: Add `TVMFFIStreamHandle`, `TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream` to the C ABI Key Exports pseudocode section and note the stream context as an `extra/` env API subsystem. Mermaid sequence diagram showing RAII stream swap pattern would help.
- Consider creating a new design record `0010-stream-context.md` documenting the `extra/` stream context subsystem: `TVMFFIStreamHandle`, the `StreamContext` thread-local singleton, the lazy-resize invariant, the weak-reference ownership model, and the RAII swap pattern via `opt_out_original_stream`.

### Stale knowledge references
None — no existing `.knowledge/` files reference `TVMFFIEnvSetStream` or `TVMFFIEnvGetCurrentStream`. The `c_env_api.h` is mentioned in 0001-c-abi.md only for `TVMFFIEnvRegisterCAPI`/`TVMFFIEnvCheckSignals`; no update is strictly required but augmentation is recommended (see above).
