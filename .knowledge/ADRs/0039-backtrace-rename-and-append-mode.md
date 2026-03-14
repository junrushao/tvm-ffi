---
scope:
  - "0007-error-handling"
  - "0015-traceback-system"
  - "0001-c-abi"
---
# Rename traceback to backtrace and add append-friendly storage order

**TL;DR**: The `traceback` field in `TVMFFIErrorCell` is renamed to `backtrace` throughout the C ABI, C++ API, Cython bindings, and Python layer. Storage order changes to "most recent call first" for O(1) append during error propagation. A new `TVMFFIBacktraceUpdateMode` enum and `update_mode` parameter on `update_backtrace` enable incremental backtrace building. This is an ABI-breaking change.

## Context

When errors propagate up the call stack through multiple C ABI boundaries (e.g., C++ -> Python callback -> C++), the backtrace needs to be incrementally extended at each boundary crossing. Under the previous design:

- The `traceback` field stored frames in "most recent call last" order (Python convention for display).
- The `update_traceback` function pointer took only `self` and `traceback_str`, always replacing the entire traceback.
- Incrementally building a traceback required reversing, appending, and re-reversing -- O(n) per boundary crossing.
- The naming "traceback" was ambiguous with Python's `traceback` module and `__traceback__` attribute.

Additionally, `TVMFFIErrorCreate` returned `TVMFFIObjectHandle` directly. On OOM during error creation, this would panic since there is no way to signal failure.

Usecases:
- Nested FFI calls (Python -> C++ -> Python -> C++) need efficient backtrace accumulation at each boundary.
- Segfault handlers need to replace backtraces entirely rather than append.
- The error creation path needs to handle OOM gracefully.

Design Decisions:
- Rename `traceback` to `backtrace` throughout the ABI for clarity:
  - `TVMFFIErrorCell.traceback` -> `TVMFFIErrorCell.backtrace`
  - `update_traceback` -> `update_backtrace`
  - `traceback.cc`/`traceback.h` -> `backtrace.cc`/`backtrace_utils.h`
  - `TVMFFIGetStackBacktrace` replaces the old traceback access API
- Change storage order to "most recent call first" (top of stack to bottom), making append O(1) -- new frames are simply concatenated.
- Add `TVMFFIBacktraceUpdateMode` enum:
  - `kTVMFFIBacktraceUpdateModeReplace = 0`: Replaces the entire backtrace.
  - `kTVMFFIBacktraceUpdateModeAppend = 1`: Appends new frames to the existing backtrace.
- `update_backtrace` signature changes to: `void (*)(TVMFFIObjectHandle self, const TVMFFIByteArray* backtrace, int32_t update_mode)`
- `TVMFFIErrorCreate` return type changes from `TVMFFIObjectHandle` to `int` (error code) with an `out` parameter, aligning with the standard C API pattern.

**Trade-offs**:
- Pro: O(1) append during error propagation; cleaner naming.
- Pro: `TVMFFIErrorCreate` can now handle OOM gracefully by returning an error code.
- Con: ABI-breaking change requiring all consumers to update.
- Con: Display code must now reverse the backtrace for Python-style "most recent call last" rendering.

**Alternatives considered**:
1. **Keep "traceback" naming, add mode parameter only**: Avoids the rename churn but leaves the naming ambiguity. Rejected because the rename is a one-time cost during an early development phase.
2. **Store both orders (forward + reverse)**: Avoids the need to reverse for display. Rejected because it doubles memory usage and adds complexity for marginal display-path benefit.
3. **Incremental traceback via linked list**: Each boundary crossing creates a new traceback node linked to the previous. Rejected because it introduces pointer indirection and complicates serialization.

## Implementation Notes
- Version bumped to `0.1.0b5` to signal the ABI break.
- Python-side `error.py` and Cython `error.pxi` updated to use `backtrace` field names.
- Display code in Python reverses the backtrace lines for user-facing output.
- The `TVMFFIBacktraceUpdateMode` enum is defined in `c_api.h` with C/C++ dual definition.

## Related Design Docs
- [`.knowledge/designs/0007-error-handling.md`](../designs/0007-error-handling.md) -- Error object model and TVMFFIErrorCell
- [`.knowledge/designs/0015-traceback-system.md`](../designs/0015-traceback-system.md) -- Cross-language traceback/backtrace system
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI surface affected by the rename
- [`.knowledge/ADRs/0022-traceback-boundary-parameter.md`](0022-traceback-boundary-parameter.md) -- Prior decision on cross_ffi_boundary parameter
- Evidence: `.knowledge/commits/2025-09-22-6f020c11c304ef11ac5d0dad904d41ebe42a3ffd.md` + commit `6f020c1`
