---
scope:
  - ".knowledge/designs/error-handling.md"
  - ".knowledge/designs/c-abi.md"
---
# Backtrace Storage Order and Naming Convention

**TL;DR**:
- Backtraces are stored in most-recent-call-first order (reversed from the Python convention) and renamed from `traceback` to `backtrace` across the entire API surface.
- This enables O(1) append during error propagation and introduces `TVMFFIBacktraceUpdateMode` for replace/append semantics.

## Context
When an error propagates through multiple FFI boundaries (C++ -> Python -> C++ -> Python), each boundary adds frames to the traceback. Under the old convention:
- Traceback was stored most-recent-call-last (Python convention).
- Appending new frames during propagation required reversing the existing trace, appending, and re-reversing -- or prepending to a string, which is O(n).
- The name `traceback` conflicted with Python's `traceback` module and implied Python's specific display convention.

Usecases:
- Error thrown in C++ kernel, propagated through two FFI boundaries (C++ -> Cython -> Python), must accumulate frames from each boundary efficiently.
- Error re-raised in Python callback, re-enters C++ via packed function call, picks up additional C++ frames.

Design Decisions:
- **Store backtraces in most-recent-call-first order.** New frames are appended to the end (O(1) string concatenation). Display reversal (`TracebackMostRecentCallLast()`) is performed once at display time.
- **Rename `traceback` to `backtrace` across C ABI, C++, and Python.** The term "backtrace" is more neutral (matches GDB/glibc convention) and avoids confusion with Python's `traceback` module.
- **Add `TVMFFIBacktraceUpdateMode` enum** with `kTVMFFIBacktraceUpdateModeReplace = 0` and `kTVMFFIBacktraceUpdateModeAppend = 1` to give callers control over update semantics.
- **Change `TVMFFIErrorCreate` to return `int`** with an out-parameter, adding `std::bad_alloc` safety on the error-creation path.

## Alternatives
### Keep most-recent-call-last order with O(n) prepend
- Description: Maintain the Python-native display order in storage. Prepend new frames during propagation.
- Pros: Storage matches display; no reversal needed for printing.
- Cons: String prepend is O(n) per frame added. For deep call stacks with multiple FFI boundaries, this becomes quadratic in the total frame count. The TLS propagation pattern adds frames at each boundary crossing, making this a hot path.
- Why rejected: Performance degradation is measurable in error-heavy workloads (e.g., recursive compilation with many FFI round-trips). The reversal at display time is a one-time O(n) cost, acceptable since errors are displayed rarely compared to propagation.

### Use a structured list of frame objects instead of string concatenation
- Description: Store frames as a vector of `(filename, lineno, func)` tuples. Append is O(1) amortized.
- Pros: Clean structured data; no string parsing at display time; O(1) append.
- Cons: Requires new C ABI types for frame structs; breaks the existing `TVMFFIByteArray`-based error cell layout; forces all language bindings to implement structured frame handling instead of simple string operations. The string-based backtrace is consumed by Python's traceback reconstruction which already parses it via regex -- adding a second structured representation doubles the surface area.
- Why rejected: Too invasive for the current C ABI stability guarantees. The string-based representation is sufficient and already consumed by all existing bindings. The append-order optimization solves the performance problem without ABI restructuring.

## Implementation Notes
- The full rename mapping covers 20+ symbols across C ABI, C++, Python, and file names. See commit 6f020c1 for the complete rename table.
- `Error::TracebackMostRecentCallLast()` reverses lines for display. Used by `Error::what()`.
- `TVMFFIErrorCreate` signature changed from `TVMFFIObjectHandle TVMFFIErrorCreate(...)` to `int TVMFFIErrorCreate(..., TVMFFIObjectHandle* out)` with `std::bad_alloc` handling.
- Python `_traceback_to_backtrace_str` now stores lines in most-recent-first order. `_with_append_backtrace` no longer calls `reversed()` when reconstructing Python tracebacks.
- Version bumped from `0.1.0b4` to `0.1.0b5` due to ABI break.

Key signatures:
```c
enum TVMFFIBacktraceUpdateMode : int32_t {
    kTVMFFIBacktraceUpdateModeReplace = 0,
    kTVMFFIBacktraceUpdateModeAppend = 1,
};

int TVMFFIErrorCreate(const TVMFFIByteArray* kind, const TVMFFIByteArray* message,
                      const TVMFFIByteArray* backtrace, TVMFFIObjectHandle* out);

void (*update_backtrace)(TVMFFIObjectHandle self, const TVMFFIByteArray* backtrace,
                         int32_t update_mode);
```

## Related Design Docs
- `.knowledge/designs/error-handling.md` -- Error system design (updated with backtrace naming)
- `.knowledge/designs/c-abi.md` -- C ABI struct layout (`TVMFFIErrorCell`)
- `.knowledge/designs/0014-python-bindings.md` -- Python Error class, traceback reconstruction
