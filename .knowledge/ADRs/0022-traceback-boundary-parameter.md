---
scope:
  - "0015-traceback-system"
  - "0007-error-handling"
  - "0001-c-abi"
---
# TVMFFITraceback cross_ffi_boundary Parameter

**TL;DR**: The decision to add a 4th `cross_ffi_boundary` parameter to the `TVMFFITraceback` C API function, changing its signature from `(const char*, int, const char*)` to `(const char*, int, const char*, int)`. This is a breaking C ABI change that enables control over whether the traceback stops at or crosses the FFI call boundary.

## Context

When Python calls C++ which calls Python which calls C++ (nested FFI), the C++ traceback captures native stack frames. The FFI call boundary (marked by `TVMFFIFunctionCall` and Python ABI symbols like `slot_tp_call`, `_Py*`) is where the traceback should typically stop, because the Python side provides its own traceback for Python frames. Continuing past the boundary produces noisy tracebacks with irrelevant Python interpreter internal frames.

However, there is one critical scenario where crossing the boundary is necessary: segfault handlers. When a segfault occurs deep in a nested call stack, the signal handler needs the full stack trace across all boundaries to diagnose the crash. The previous 3-parameter `TVMFFITraceback` always stopped at the boundary, making segfault diagnostics incomplete.

Additionally, the previous design used a `TVM_FFI_TRACEBACK_HERE` macro that captured tracebacks inline. This was replaced by direct `TVMFFITraceback` calls in `TVM_FFI_THROW` and `TVM_FFI_LOG_AND_THROW`, which now pass `cross_ffi_boundary=0` by default.

Usecases:
- Normal error handling: `TVM_FFI_THROW(RuntimeError)` calls `TVMFFITraceback(__FILE__, __LINE__, func, 0)` to capture the C++ traceback up to the FFI boundary. The Python side adds Python frames via `TracebackManager`.
- Segfault handler: `TVMFFISegFaultHandler` calls `TVMFFITraceback(nullptr, 0, nullptr, 1)` to get the full stack across all boundaries for crash diagnosis.
- Python error back-propagation: `set_last_ffi_error` in `error.pxi` calls `TVMFFITraceback(NULL, 0, NULL, 0)` to capture the C++ frames between the Python callback and the FFI boundary, without crossing into the Python interpreter.

Design Decisions:
- **Add 4th parameter `cross_ffi_boundary`**: `int` type (not `bool`) for C ABI compatibility. Value `0` means stop at boundary (default, backward-compatible behavior), non-zero means cross.
- **Breaking C ABI change**: Any direct caller of `TVMFFITraceback` must update to the 4-parameter signature. This was deemed acceptable because: (a) `TVMFFITraceback` was primarily called from macros (`TVM_FFI_THROW`) that are updated in the same commit, (b) direct callers are rare (mainly internal code), and (c) the benefit of unified boundary control outweighs the migration cost.
- **Remove `TVM_FFI_TRACEBACK_HERE` macro**: Replaced by direct `TVMFFITraceback` calls with explicit `cross_ffi_boundary=0`. This simplifies the API surface (one function instead of a function plus a macro) and makes the boundary behavior explicit at every call site.
- **Rename `ShouldStopTraceback` to `DetectFFIBoundary`**: Clarifies the function's purpose. It detects whether a frame is at the FFI boundary, not whether the entire traceback should stop (which now depends on the `cross_ffi_boundary` parameter).

**Alternatives considered**:

1. **Always stop at boundary (no parameter)**:
   - Pros: Simpler API, no ABI break.
   - Cons: Segfault handlers produce incomplete tracebacks. No way to diagnose crashes in nested FFI calls. Users would have to use external debuggers (gdb, lldb) for all crash diagnostics.

2. **Always cross boundaries**:
   - Pros: No parameter needed, always full traceback.
   - Cons: Normal error tracebacks become noisy with Python interpreter frames (`_PyEval_EvalFrameDefault`, `PyObject_Call`, etc.) that are meaningless to users. The Python side already provides its own traceback for Python frames; duplicating them from the C++ side creates confusion and doubles traceback length.

3. **Separate function for each mode** (e.g., `TVMFFITracebackFull`):
   - Pros: No ABI break for existing callers.
   - Cons: Code duplication. Two functions to maintain. The single-function approach with a parameter is simpler and more composable.

4. **Global flag instead of per-call parameter**:
   - Pros: No function signature change.
   - Cons: Not thread-safe without TLS. Per-call parameter is more explicit and works correctly in concurrent scenarios.

**Consequences**:
- All existing callers of `TVMFFITraceback` must add the 4th parameter. In this commit, all call sites are updated.
- Downstream code that directly calls `TVMFFITraceback` (if any exists) will get a compile error until updated. This is intentional for safety.
- The `TracebackStorage` struct gains `stop_at_boundary` (bool) and `skip_frame_count` (size_t) fields, enabling richer frame control.
- The segfault handler now produces complete cross-boundary tracebacks, significantly improving crash diagnostics.
- `TVM_FFI_THROW` and `TVM_FFI_LOG_AND_THROW` macros are updated to pass `cross_ffi_boundary=0`.
- Rollback: reverting requires restoring the 3-parameter signature and re-introducing `TVM_FFI_TRACEBACK_HERE`. All downstream callers would need to be updated again.

## Implementation Notes

- Signature: `const TVMFFIByteArray* TVMFFITraceback(const char* filename, int lineno, const char* func, int cross_ffi_boundary)`
- When `cross_ffi_boundary == 0`: `TracebackStorage.stop_at_boundary = true`. `BacktraceFullCallback` returns 1 (stop) when `DetectFFIBoundary` matches.
- When `cross_ffi_boundary != 0`: `TracebackStorage.stop_at_boundary = false`. Frames are collected past FFI boundaries up to `max_frame_size`.
- MSVC workaround: `TVMFFIFunctionCall` uses `volatile int ret` to prevent tail-call optimization, ensuring the symbol appears in the call stack for boundary detection.
- Cython declaration: `const TVMFFIByteArray* TVMFFITraceback(const char* filename, int lineno, const char* func, int cross_ffi_boundary) nogil` in `base.pxi`.

## Related Design Docs

- [`.knowledge/designs/0015-traceback-system.md`](../designs/0015-traceback-system.md) -- Full traceback system design
- [`.knowledge/designs/0007-error-handling.md`](../designs/0007-error-handling.md) -- Error propagation that triggers traceback capture
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI surface including TVMFFITraceback
