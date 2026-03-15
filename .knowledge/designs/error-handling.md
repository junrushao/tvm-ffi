# Error Handling Design

> Established in commit 7d34eb8 ("[REFACTOR] Introduce and modernize FFI system")

## Overview

TVM FFI uses object-based error handling. Errors are heap-allocated `ErrorObj` instances
that carry a kind (string), message, and traceback. Errors cross the C ABI boundary
via TLS (thread-local storage), not through return arguments.

## Error Object

### ErrorObj (`include/tvm/ffi/error.h`)

```cpp
class ErrorObj : public Object, public TVMFFIErrorCell {
    // TVMFFIErrorCell provides:
    //   TVMFFIByteArray kind
    //   TVMFFIByteArray message
    //   TVMFFIByteArray backtrace               // renamed from traceback in 6f020c1
    //   void (*update_backtrace)(TVMFFIObjectHandle self,
    //                            const TVMFFIByteArray* backtrace,
    //                            int32_t update_mode)   // renamed + gains update_mode param
};
```

Type index: `kTVMFFIError = 67`. The cell fields are accessible from C via
`TVMFFIErrorGetCellPtr(obj)`.

### Error (`include/tvm/ffi/error.h`)

The reference wrapper. Inherits from both `ObjectRef` and `std::exception`:

```cpp
class Error : public ObjectRef, public std::exception {
    Error(string kind, string message, string backtrace);
    string kind() const;
    string message() const;
    string backtrace() const;                               // renamed from traceback() in 6f020c1
    string TracebackMostRecentCallLast() const;             // reverses lines for Python-style display
    string FullMessage() const;                              // full error with kind, message, traceback (since 4bccb3e)
    const char* what() const noexcept;                      // returns only message.data (since 4bccb3e; was full message)
    void UpdateBacktrace(const TVMFFIByteArray*, int32_t);  // renamed + gains update_mode param
};
// Backtrace storage order: most-recent-call-first (since 6f020c1).
// This enables O(1) append during error propagation.
// TracebackMostRecentCallLast() reverses lines for display.
// See .knowledge/ADRs/017-backtrace-storage-order.md for decision rationale.
```

`what()` returns only `message.data` (the error message string, not the full traceback). This conforms to `std::exception::what()` which should not throw or allocate.

`FullMessage()` returns the full formatted error string:
```
Traceback (most recent call last):
<traceback>
<kind>: <message>
```

This split (since 4bccb3e) ensures `what()` is noexcept-safe (no thread_local allocation) while `FullMessage()` provides the complete diagnostic output. `ErrorBuilder` uses `FullMessage()` for logging before throw.

### ErrorObjFromStd

Internal implementation class that stores kind, message, and traceback as
`std::string` members and sets up the `TVMFFIByteArray` pointers.

## TLS Error Propagation

### Setting an Error

1. C++ code throws `tvm::ffi::Error`
2. `TVM_FFI_SAFE_CALL_END()` catches it, calls `TVMFFIErrorSetRaised(error_handle)`
3. Error object is stored in a thread-local variable
4. Returns -1 to the C caller

Alternatively, C code can set errors directly without throwing:
- `TVMFFIErrorSetRaisedFromCStr(kind, message)` — from a single C string.
- `TVMFFIErrorSetRaisedFromCStrParts(kind, message_parts, num_parts)` — by concatenating
  an array of C string parts (NULL entries are skipped). This is useful for DSL compilers
  that store reusable error message fragments (e.g., function signatures) as global constants
  to reduce binary size duplication. Added in 550e92f.

### Retrieving an Error

1. Caller sees return code -1
2. Calls `TVMFFIErrorMoveFromRaised(&handle)` to retrieve and clear the TLS error
3. Wraps the handle back into an `Error` object and throws it

### Frontend Error (code -2)

`EnvErrorAlreadySet` is a lightweight exception indicating that the frontend
(e.g., Python) already has an error set (typically from a signal handler). The
FFI catches this and returns -2, allowing the frontend to handle its own error.

## Error Boundary Macros

```cpp
// Wrapping C++ code for C ABI:
TVM_FFI_SAFE_CALL_BEGIN();
    // ... C++ code that may throw ...
TVM_FFI_SAFE_CALL_END();
// Catches: Error -> TLS + return -1
//          EnvErrorAlreadySet -> return -2
//          std::exception -> wrap as InternalError + return -1

// Checking C ABI return code in C++:
TVM_FFI_CHECK_SAFE_CALL(c_api_function(...));
// -1 -> retrieve TLS error and throw
// -2 -> throw EnvErrorAlreadySet
```

### Log-and-Abort Error Boundary

For C API functions that return a value directly (not through an out-parameter), TLS-based error propagation is infeasible because the return value occupies the function's return channel. These functions use a separate pattern:

```cpp
TVM_FFI_LOG_EXCEPTION_CALL_BEGIN();
    return some_value;
TVM_FFI_LOG_EXCEPTION_CALL_END(FunctionName);
```

On exception: logs the error message to stderr and calls `exit(-1)`. This is intentionally harsh -- functions using this pattern should be very unlikely to throw (e.g., looking up a value in a thread-local table).

**When to use which pattern:**
- `TVM_FFI_SAFE_CALL_BEGIN/END`: Function returns `int` (0 = success, -1 = error). Results go through out-parameters. This is the default pattern.
- `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END`: Function returns a value directly (e.g., `void*`, `TVMFFIStreamHandle`). No out-parameter for error. Used only for functions where exceptions should be extremely rare.

Example: `TVMFFIEnvGetStream` returns `TVMFFIStreamHandle` directly and uses the log-and-abort pattern, while `TVMFFIEnvSetStream` returns `int` and uses the safe-call pattern (commit 0daaffed; names reverted to `TVMFFIEnvSetStream`/`TVMFFIEnvGetStream` in f81ab9c).

## TVM_FFI_THROW Macro

Stream-style error creation with automatic traceback:

```cpp
TVM_FFI_THROW(RuntimeError) << "something went wrong: " << value;
```

Expands to an `ErrorBuilder` that:
1. Calls `TVMFFIBacktrace(__FILE__, __LINE__, __func__)` for stack trace (renamed from `TVMFFITraceback` in 6f020c1)
2. Collects the streamed message via `std::ostringstream`
3. In its destructor, constructs an `Error` and throws it
4. If `TVM_FFI_ALWAYS_LOG_BEFORE_THROW` is set to 1, also logs the error to stderr
   before throwing (useful for WebAssembly and other environments where exceptions
   may not propagate clearly)

Variant: `TVM_FFI_LOG_AND_THROW` always logs to stderr before throwing regardless of
`TVM_FFI_ALWAYS_LOG_BEFORE_THROW` (intended for startup errors where exceptions cannot
be caught).

## Check Macros

### User-facing typed checks (since 327e8cc6)

```cpp
TVM_FFI_CHECK(ErrorKind, condition) << "message";
```

Throws the specified `ErrorKind` (e.g., `ValueError`, `IndexError`) when `condition` is false. The error message includes the stringified condition.

### Internal checks (throw InternalError)

```cpp
TVM_FFI_ICHECK(condition) << "message";
TVM_FFI_ICHECK_LT(x, y) << "message";
TVM_FFI_ICHECK_GT(x, y) << "message";
TVM_FFI_ICHECK_LE(x, y) << "message";
TVM_FFI_ICHECK_GE(x, y) << "message";
TVM_FFI_ICHECK_EQ(x, y) << "message";
TVM_FFI_ICHECK_NE(x, y) << "message";
TVM_FFI_ICHECK_NOTNULL(ptr);
```

The binary comparison macros print both values on failure (e.g., "(3 vs. 5)").

## Configuration Flags

- `TVM_FFI_USE_LIBBACKTRACE` (default 1) -- Enable libbacktrace for stack traces
- `TVM_FFI_BACKTRACE_ON_SEGFAULT` (default 1) -- Install SEGFAULT signal handler
- `TVM_FFI_ALWAYS_LOG_BEFORE_THROW` (default 0) -- When enabled, all `TVM_FFI_THROW`
  invocations log the error to stderr before throwing. Added in 076ac23 for web runtime
  support where exception propagation may be unreliable.

## Boundary-Aware Traceback Collection

Since commit 2d41a51, `TVMFFIBacktrace` (renamed from `TVMFFITraceback` in 6f020c1) accepts a 4th parameter `cross_ffi_boundary`:

```c
const TVMFFIByteArray* TVMFFIBacktrace(
    const char* filename, int lineno, const char* func, int cross_ffi_boundary);
```

When `cross_ffi_boundary == 0` (default, used by `TVM_FFI_THROW` and `TVM_FFI_LOG_AND_THROW`):
- Traceback stops at FFI boundaries (Python interpreter frames, `TVMFFIFunctionCall`).
- FFI boundary detection recognizes: `TVMFFIFunctionCall`, Python interpreter symbols (`_Py*`, `PyObject*`), CPython slot functions (`slot_tp_call`, `object_is_not_callable`).
- Frame skip logic: skips 2 frames (the `TVMFFIBacktrace` function itself and its direct caller).
- `filename`/`func` can be `nullptr` to suppress caller-supplied frame info (used by `TVMFFIErrorSetRaisedFromCStr`).

When `cross_ffi_boundary == 1`:
- Captures the full call stack without boundary filtering.

The previous `TVM_FFI_TRACEBACK_HERE` macro was removed; callers now invoke `TVMFFIBacktrace(...)` directly.

## Python Traceback Reconstruction

The Python binding layer (`error.py`) reconstructs native Python tracebacks from C++ traceback strings:

### TracebackManager

1. **Parse**: `_parse_backtrace(backtrace_str)` (renamed from `_parse_traceback` in 6f020c1) extracts `(filename, lineno, func)` tuples via regex matching `File "...", line N, in ...`.
2. **Compile**: `_get_cached_code_object(filename, lineno, func)` compiles `ast.parse("_getframe()")` with the target filename, replaces `co_name` and `co_firstlineno`, and caches by `(filename, lineno, func)` key.
3. **Frame creation**: `_create_frame(filename, lineno, func)` evaluates the code object with `{"_getframe": sys._getframe}` context to capture a frame pointing to the target location.
4. **Chain**: `append_traceback(tb, filename, lineno, func)` creates `types.TracebackType(tb, frame, frame.f_lasti, lineno)`.
5. **Assemble**: `_with_append_backtrace(py_error, backtrace)` (renamed from `_with_append_traceback` in 6f020c1) iterates parsed frames to build the full traceback chain. Since backtrace storage is most-recent-call-first, the function no longer calls `reversed()`.

### Error Kind Mapping

Python exception classes are registered via `register_error`:
```python
register_error("RuntimeError", RuntimeError)
register_error("ValueError", ValueError)
register_error("TypeError", TypeError)
register_error("AttributeError", AttributeError)
register_error("KeyError", KeyError)
register_error("IndexError", IndexError)
register_error("AssertionError", AssertionError)
register_error("MemoryError", MemoryError)  # since 227bdd0; canonical error kind for allocation failures
```

When `Error.py_error()` is called, it looks up the error kind in `ERROR_NAME_TO_TYPE` and creates the appropriate Python exception with the reconstructed traceback.

### Bidirectional Error Propagation

When a Python callback raises an exception during an FFI call:
1. `set_last_ffi_error(error)` in `error.pxi` collects both the Python backtrace (`_TRACEBACK_TO_BACKTRACE_STR`, renamed from `_TRACEBACK_TO_STR` in 6f020c1) and C++ backtrace (`TVMFFIBacktrace(NULL, 0, NULL, 0)`).
2. If the error originated from C++ (has `__tvm_ffi_error__` attribute), the existing FFI error is updated with the combined traceback.
3. Otherwise, a new `Error` is created with the combined traceback.
4. The error is set in TLS via `TVMFFIErrorSetRaised`.

## Key Files

- `include/tvm/ffi/error.h` -- ErrorObj, Error, ErrorBuilder, assertion macros
- `include/tvm/ffi/c_api.h` -- TVMFFIErrorCell, error C API declarations
- `src/ffi/error.cc` -- TLS error storage, TVMFFIErrorCreate, C API wrappers
- `src/ffi/backtrace.cc` -- TVMFFIBacktrace implementation (libbacktrace) (renamed from `traceback.cc` in 6f020c1)
- `src/ffi/backtrace_win.cc` -- Windows backtrace implementation (renamed from `traceback_win.cc` in 6f020c1)
- `python/tvm_ffi/error.py` -- TracebackManager, error registration, traceback reconstruction
- `python/tvm_ffi/cython/error.pxi` -- Cython Error class, CHECK_CALL, set_last_ffi_error

### Evidence Matrix
- `Error::FullMessage()` / `what()` split -> `2025-11-07-4bccb3ed.md` + commit 4bccb3e
