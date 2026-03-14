---
author: "Tianqi Chen"
subject: "Add thread-local stream context management to FFI env API"
scope:
  - "extra-api-tier"
  - "c-abi"
impact: "medium"
---
# Add thread-local stream context management to FFI env API
## TL;DR
- Introduces two new C API functions (`TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`) in `include/tvm/ffi/extra/c_env_api.h` for per-device, per-thread GPU stream context management, centralizing what was previously scattered per-device API stream handling in the upstream TVM runtime.
- Implements the backing `StreamContext` class in `src/ffi/extra/stream_context.cc` using a thread-local 2D vector indexed by `(device_type, device_id)`, storing `void*` stream handles as weak references.
- The new source file is gated under `TVM_FFI_USE_EXTRA_CXX_API` in `CMakeLists.txt`, following the established extra-tier pattern.

## Impact
- API: Two new `extern "C"` functions added to `c_env_api.h`. These are additive; no existing API is changed or broken. Downstream consumers (e.g., TVM runtime, kernel libraries) can migrate per-device stream tracking to these centralized FFI calls.
- Flags/config: none -- gated by the existing `TVM_FFI_USE_EXTRA_CXX_API` CMake option (default ON).
- Data formats/schemas: none.

## Design Elements
Design elements this commit **consumes**:

- **Extra API tier** ([`.knowledge/designs/0011-extra-api-tier.md`](../designs/0011-extra-api-tier.md)): The stream context is added as a new extra-tier module following the established pattern: header in `include/tvm/ffi/extra/`, implementation in `src/ffi/extra/`, CMake-gated under `TVM_FFI_USE_EXTRA_CXX_API`. The `TVM_FFI_DLL` visibility macro is used (not `TVM_FFI_EXTRA_CXX_API`) because the API is `extern "C"` and follows C ABI conventions.
- **C ABI layer** ([`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md)): The new functions are declared as `extern "C"` with `TVM_FFI_DLL` visibility in `c_env_api.h`, following the C ABI visibility conventions. They accept only POD types (`int32_t`, `void*`) and return `int` error codes, consistent with the C ABI contract.
- **Error handling** ([`.knowledge/designs/0007-error-handling.md`](../designs/0007-error-handling.md)): The two functions use different error-handling macros based on their return type:
  - `TVMFFIEnvSetStream` returns `int` (0 = success, nonzero = failure) and uses `TVM_FFI_SAFE_CALL_BEGIN/END` -- the standard safe-call boundary for C API functions that return error codes.
  - `TVMFFIEnvGetCurrentStream` returns `TVMFFIStreamHandle` (a `void*`) directly and uses `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END(TVMFFIEnvGetCurrentStream)` -- the log-and-abort pattern for functions that cannot return an error code in their return value. If an exception occurs, it logs to stderr and calls `exit(-1)`.

Design elements this commit **produces**:

- **Stream context management pattern**: A new `StreamContext` class implementing thread-local, per-device stream tracking as a 2D `vector<vector<TVMFFIStreamHandle>>` indexed by `(device_type, device_id)`. This establishes a pattern for lightweight thread-local context in the FFI layer. The design intentionally does not manage stream allocation or deallocation -- it only records which stream is active. The `opt_out_original_stream` parameter on `SetStream` enables RAII-style save/restore patterns by callers.
- **`TVMFFIStreamHandle` typedef**: A new opaque `void*` handle type for streams, providing minimal type documentation even though it is semantically identical to `void*`.

## Key Implementations

### StreamContext class (`src/ffi/extra/stream_context.cc`)

The core data structure is:
```
std::vector<std::vector<TVMFFIStreamHandle>> stream_table_
```

Indexed as `stream_table_[device_type][device_id]`. Both dimensions grow on demand: if a `SetStream` call references a `device_type` or `device_id` beyond the current vector size, the vector is resized with `nullptr` fill. `GetStream` returns `nullptr` for any out-of-range query (no resize on read).

**Thread-local singleton**: `StreamContext::ThreadLocal()` returns a `static thread_local StreamContext` instance. Each thread has its own independent stream table. This means:
- No locking is needed.
- Stream context set in one thread is invisible to other threads.
- Thread destruction automatically cleans up the table.

**Invariants**:
- `stream_table_[device_type][device_id]` is always a weak reference (raw `void*`). The caller owns the stream lifetime.
- Default stream state for any `(device_type, device_id)` pair is `nullptr` (no stream set).
- Negative `device_type` or `device_id` values will cause undefined behavior due to the unsigned comparison in `static_cast<size_t>(device_type)`. This is not guarded, but device types and IDs are expected to be non-negative by convention in DLPack/TVM.

**Error handling asymmetry**:
- `TVMFFIEnvSetStream` uses `TVM_FFI_SAFE_CALL_BEGIN/END` because it returns `int` and can report errors via the return code + TLS mechanism. A `std::bad_alloc` from `vector::resize` would be caught and stored in TLS.
- `TVMFFIEnvGetCurrentStream` uses `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` because it returns `TVMFFIStreamHandle` directly. There is no room for an error code in the return value. In practice, `GetStream` cannot throw (no allocations, no bounds violations), so this is a defensive choice.

**Extension points**:
- The stream context could be extended with additional per-device metadata (e.g., stream priority, synchronization state) by adding fields alongside the `TVMFFIStreamHandle` in the inner vector.
- If cross-thread stream visibility is ever needed, the thread-local storage would need to be replaced with a shared concurrent data structure.

### Integration with c_env_api.h

The stream context API is placed *before* the existing module symbol management section in `c_env_api.h`, grouped under a `// Stream context` comment block. This positions it as a peer to the module import/registration APIs, all under the `TVMFFIEnv*` naming convention for environment-level APIs that kernel libraries call.

## Reflection

### Design docs to write

- **`.knowledge/designs/0011-extra-api-tier.md` -- update to include stream context**: The extra-tier design doc's inventory of modules (structural equal/hash, JSON, serialization, reflection_extra, library_module) should be updated to include `stream_context.cc` and the `TVMFFIEnvSetStream`/`TVMFFIEnvGetCurrentStream` API. This helps future commit mining by establishing stream context as a known extra-tier component.
  - Content outline: Add `stream_context.cc` to the directory layout section; add `TVMFFIEnvSetStream`/`TVMFFIEnvGetCurrentStream` to the key interfaces list; note that unlike other extra-tier APIs, these are `extern "C"` (C ABI compatible) rather than C++ only.
  - Future commit mining benefit: Any GPU runtime integration, CUDA/ROCm stream management, or multi-device scheduling commits that touch stream handling would reference this component.

- **`.knowledge/designs/0013-env-api.md` -- document the c_env_api.h surface**: The `c_env_api.h` header now hosts two distinct categories of environment APIs (stream context management and module symbol management), but there is no design doc that describes the `TVMFFIEnv*` API family as a cohesive design element. A dedicated doc would cover:
  - The `TVMFFIEnv*` naming convention and its role as the API surface that kernel libraries call (as opposed to host-side user-facing APIs).
  - The stream context management pattern (thread-local, weak-reference, per-device).
  - The module import/symbol registration APIs (`TVMFFIEnvLookupFromImports`, `TVMFFIEnvRegisterContextSymbol`, `TVMFFIEnvRegisterSystemLibSymbol`).
  - Future commit mining benefit: Any commit adding new `TVMFFIEnv*` functions or modifying kernel library integration would reference this doc.

### ADRs to write

- **`.knowledge/ADRs/0018-thread-local-stream-context.md`**: Records the decision to use thread-local storage for per-device stream context in the FFI layer.
  - Context: The upstream TVM runtime had per-device stream management scattered across individual device APIs. Centralizing it in the FFI layer enables library modules compiled against the FFI to discover the current stream without device-specific API dependencies.
  - Alternatives: (1) Global shared state with locking -- simpler cross-thread visibility but introduces contention. (2) Explicit stream passing as function arguments -- fully explicit but requires changing the packed calling convention for every kernel invocation. (3) Per-module stream context -- isolates modules but makes it impossible for a host to set a stream once and have all modules observe it.
  - Trade-offs: Thread-local is zero-contention and matches the common GPU programming pattern (e.g., CUDA's per-thread default stream), but cross-thread stream visibility requires explicit coordination by the caller.

### Design diagrams to draw

- **Mermaid diagram in `.knowledge/designs/0013-env-api.md`**: Should depict the relationship between kernel library modules, the `TVMFFIEnv*` C API surface, and the internal implementations (StreamContext, library module symbol lookup). Show how a kernel library calls `TVMFFIEnvGetCurrentStream` to discover the active stream, and how the host runtime calls `TVMFFIEnvSetStream` before invoking the kernel.

### Skill evolution (`/commit-ledger`)

- **Classify error-handling patterns in Step 4**: This commit uses two different error-handling macros (`TVM_FFI_SAFE_CALL_BEGIN/END` vs `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END`) for the two API functions. The skill's Step 4 (Mining Key Implementations) could benefit from a sub-bullet: "Identify which error-handling boundary macro is used and why -- this reveals whether the function follows the standard safe-call pattern (returns `int` error code) or the log-and-abort pattern (returns a non-error-code type)." This would make it easier to spot when a commit introduces a new C API function that deviates from the common pattern.

## Self-Evolution of Skill /commit-ledger
- The procedure worked well for this commit. One observation: the commit is relatively small (3 files, ~115 lines of additions) but introduces a new architectural concept (thread-local stream context) that has significant implications for downstream consumers. The current procedure correctly identifies this via Step 3.2 (Producers), but it might benefit from a "downstream impact estimation" sub-step that explicitly asks: "Who will call these new APIs, and what existing code will be migrated to use them?" The commit message itself hints at this ("migrate the existing per device API stream context management to ffi env API"), but a structured prompt would ensure the analyst always considers the migration surface.
