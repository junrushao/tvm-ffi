---
adr: "0024"
title: "Reverse backtrace storage order to most-recent-call-first for append-friendly error propagation"
status: "accepted"
date: "2025-09-22"
deciders:
  - "Tianqi Chen"
consulted:
  - "Junru Shao"
informed:
  - "TVM FFI contributors"
tags:
  - "abi"
  - "error-handling"
  - "backtrace"
source_commits:
  - "6f020c11c304ef11ac5d0dad904d41ebe42a3ffd"
source_ledgers:
  - ".memory/commits/2025-09-22-6f020c1.md"
---

# ADR-0024: Reverse backtrace storage order to most-recent-call-first for append-friendly error propagation

## TL;DR
- The internal backtrace storage in `TVMFFIErrorCell` was changed from most-recent-call-last (Python traceback order) to most-recent-call-first (stack-unwinding order), enabling O(1) append as errors propagate up the call stack.
- This is an ABI-breaking change: the `TVMFFIErrorCell.traceback` field was renamed to `backtrace`, `update_traceback` became `update_backtrace` with an additional `update_mode` parameter, and `TVMFFIErrorCreate` changed signature. The beta version was bumped accordingly.

## Status
accepted

## Context
When an error propagates through multiple FFI boundaries (C++ -> Python -> C++ -> Python), each layer may need to append its own stack frames to the error's backtrace. Under the previous most-recent-call-last storage order, appending a new frame required prepending to the string, which is an O(n) operation involving a full copy. This is wasteful on the error propagation path, which should be as efficient as possible.

The Python traceback convention (most recent call last) is the natural display format but not the natural append format. The key insight is to separate the storage order (optimized for building) from the display order (optimized for reading).

Additionally, the naming convention `traceback` (a Python term) was replaced with `backtrace` (a more language-neutral term) for the C ABI fields, reserving `traceback` for the rendered Python-style output.

## Decision Drivers
- Error propagation must be efficient: appending backtrace frames during stack unwinding should be O(1) amortized, not O(n).
- The C ABI should use language-neutral naming (`backtrace`) rather than Python-specific naming (`traceback`).
- The rendered error output should still follow Python conventions (most recent call last) for user-facing messages.
- The project is in pre-release beta, so ABI breaks are acceptable with a version bump.

## Decision
Store backtrace strings in most-recent-call-first order internally. Add `TVMFFIBacktraceUpdateMode` enum with `kTVMFFIBacktraceUpdateModeReplace` and `kTVMFFIBacktraceUpdateModeAppend`. The `update_backtrace` function pointer takes the update mode as a third parameter. When rendering for display, `Error::TracebackMostRecentCallLast()` reverses the line order.

Specific ABI changes:
1. `TVMFFIErrorCell.traceback` renamed to `TVMFFIErrorCell.backtrace`.
2. `TVMFFIErrorCell.update_traceback(self, traceback)` replaced by `TVMFFIErrorCell.update_backtrace(self, backtrace, update_mode)`.
3. `TVMFFITraceback(filename, lineno, func, cross_ffi)` renamed to `TVMFFIBacktrace(...)`.
4. `TVMFFIErrorCreate(kind, message, traceback)` changed to `TVMFFIErrorCreate(kind, message, backtrace, out)`, returning `int` error code instead of a raw handle, and taking an output parameter. This prevents error-in-error scenarios (if allocation fails, caller can report `MemoryError` to the logger rather than trying to set a TLS error).

## Alternatives Considered
### Keep most-recent-call-last order, optimize prepend
- Pros: No ABI change. Display order matches storage order.
- Cons: String prepend is inherently O(n) for contiguous buffers. Could use a rope or deque, but that adds complexity to a simple byte-array field.

### Store backtrace as a linked list of frames
- Pros: O(1) prepend or append regardless of order.
- Cons: Linked list adds allocation overhead per frame. Cannot be represented as a single `TVMFFIByteArray` in the C ABI. Breaks the simple string-based storage model.

## Why This Option Won
- Append to the end of a string is O(1) amortized with `std::string::append`, matching the natural stack-unwinding direction.
- The reversal for display is a single O(n) pass done once at render time, not on every error propagation step.
- The ABI rename from `traceback` to `backtrace` clarifies the semantic distinction: `backtrace` is the raw stack data; `traceback` is the rendered Python-style output.
- The change to `TVMFFIErrorCreate` returning an error code prevents recursive error creation failures.

## Consequences
### Positive
- Error propagation with backtrace appending is now O(1) amortized per FFI boundary crossing.
- Naming is cleaner: `backtrace` (storage) vs `TracebackMostRecentCallLast` (display).
- `TVMFFIErrorCreate` is safer: returns error code instead of potentially null handle.

### Negative
- ABI break: all language bindings must be recompiled (Cython `error.pxi`, `base.pxi`, `function.pxi`; Python `error.py`).
- Internal display code must call `TracebackMostRecentCallLast()` to reverse lines before printing.

### Risks
- Consumers who directly read `TVMFFIErrorCell.backtrace` and display it without reversing will see frames in the wrong order. Mitigation: the `Error::what()` method and Cython error formatting both call the reversal function.

## Implementation Notes
- `src/ffi/traceback.cc` renamed to `src/ffi/backtrace.cc`; internal helper header renamed to `backtrace_utils.h`.
- `ErrorObjFromStd::UpdateBacktrace` handles both `Replace` and `Append` modes, using `std::string::append` for the append case.
- `Error::TracebackMostRecentCallLast()` reverses lines by scanning for `\n` delimiters and iterating in reverse.
- `TVM_FFI_THROW` and `TVM_FFI_LOG_AND_THROW` macros updated to call `TVMFFIBacktrace` instead of `TVMFFITraceback`.
- Beta version bumped in `pyproject.toml` and `CMakeLists.txt`.

## Validation
- `tests/cpp/test_error.cc`: Tests error creation, backtrace content, and `TracebackMostRecentCallLast` rendering.
- `tests/python/test_error.py`: Tests Python-side error formatting with reversed backtrace.
- `tests/cpp/test_example.cc`: Updated to use new naming.

## Migration and Rollback
- All language bindings must be recompiled against the new headers.
- Rollback would require reverting the ABI changes and re-bumping the version. Given pre-release beta status, this is acceptable.

## Related Design Docs
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md) (defines the C ABI error structs)

## Related Diagrams
- None.

## Evidence Matrix
- `TVMFFIErrorCell.backtrace` field rename and `update_backtrace` signature change -> `.memory/commits/2025-09-22-6f020c1.md` + `6f020c1` + `include/tvm/ffi/c_api.h`
- `TVMFFIBacktraceUpdateMode` enum -> `.memory/commits/2025-09-22-6f020c1.md` + `6f020c1` + `include/tvm/ffi/c_api.h`
- `Error::TracebackMostRecentCallLast()` line-reversal method -> `.memory/commits/2025-09-22-6f020c1.md` + `6f020c1` + `include/tvm/ffi/error.h`
- `TVMFFIErrorCreate` signature change (returns int, takes output param) -> `.memory/commits/2025-09-22-6f020c1.md` + `6f020c1` + `include/tvm/ffi/c_api.h`
- `TVMFFITraceback` renamed to `TVMFFIBacktrace` -> `.memory/commits/2025-09-22-6f020c1.md` + `6f020c1` + `include/tvm/ffi/c_api.h`
- `src/ffi/traceback.cc` renamed to `src/ffi/backtrace.cc` -> `.memory/commits/2025-09-22-6f020c1.md` + `6f020c1` + `src/ffi/backtrace.cc`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Update Rust bindings to use new `TVMFFIBacktrace` / `TVMFFIErrorCreate` API.
- Consider adding a `TVMFFIBacktraceUpdateMode` value for "prepend" if a future use case requires it.
