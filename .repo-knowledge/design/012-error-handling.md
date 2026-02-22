# 012 — Error Handling and Exception Architecture

- Doc ID: 012-error-handling
- Status: Approved
- Last Updated: 2026-02-22
- Owners: Tianqi Chen

## Overview

Error handling in TVM FFI spans three languages (C, C++, Python) and must
cross FFI/ABI boundaries safely. The design uses thread-local storage (TLS)
to propagate errors across C boundaries: a function returns 0 for success or
-1 for failure, and the caller retrieves the error object from TLS via
`TVMFFIErrorMoveFromRaised`. Errors are first-class objects in the TVM FFI
Object system (type index `kTVMFFIError = 67`), ref-counted like any other
object. Within a single compilation unit, C++ exception-based `throw`/`catch`
is used; across ABI boundaries, return-code-based propagation is used. Stack
traces from all languages are preserved and concatenated as errors cross
boundaries, producing unified tracebacks that include both C++ and Python
frames.

## Key Design

### Error type hierarchy

At the C level, `TVMFFIErrorCell` (defined in `c_api.h`) is the struct that
follows the `TVMFFIObject` header in error objects:

```c
typedef struct {
  TVMFFIByteArray kind;
  TVMFFIByteArray message;
  TVMFFIByteArray backtrace;
  void (*update_backtrace)(TVMFFIObjectHandle self,
                           const TVMFFIByteArray* backtrace,
                           int32_t update_mode);
  TVMFFIObjectHandle cause_chain;
  TVMFFIObjectHandle extra_context;
} TVMFFIErrorCell;
```

At the C++ level, `ErrorObj` inherits from both `Object` and `TVMFFIErrorCell`:

```cpp
class ErrorObj : public Object, public TVMFFIErrorCell {
 public:
  ErrorObj() {
    this->cause_chain = nullptr;
    this->extra_context = nullptr;
  }
  ~ErrorObj() {
    if (this->cause_chain != nullptr) {
      details::ObjectUnsafe::DecRefObjectHandle(this->cause_chain);
    }
    if (this->extra_context != nullptr) {
      details::ObjectUnsafe::DecRefObjectHandle(this->extra_context);
    }
  }
  static constexpr const int32_t _type_index = TypeIndex::kTVMFFIError;
  TVM_FFI_DECLARE_OBJECT_INFO_STATIC(StaticTypeKey::kTVMFFIError, ErrorObj, Object);
};
```

The `Error` ref-wrapper inherits from both `ObjectRef` and `std::exception`.
This dual inheritance is critical: it allows `Error` to be caught as
`std::exception` in standard C++ code AND to be stored in `Any` containers
as a ref-counted object.

```cpp
class Error : public ObjectRef, public std::exception {
 public:
  Error(std::string kind, std::string message, std::string backtrace);
  Error(std::string kind, std::string message, std::string backtrace,
        std::optional<Error> cause_chain, std::optional<ObjectRef> extra_context);

  std::string kind() const;
  std::string message() const;
  std::string backtrace() const;
  std::optional<Error> cause_chain() const;
  std::optional<ObjectRef> extra_context() const;
  std::string TracebackMostRecentCallLast() const;
  std::string FullMessage() const;
  const char* what() const noexcept(true) override;

  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(Error, ObjectRef, ErrorObj);
};
```

Internally, `details::ErrorObjFromStd` owns the string data via `std::string`
members and provides the `UpdateBacktrace` callback. The memory layout is:
`[TVMFFIObject header | TVMFFIErrorCell fields | std::string kind_data_ |
std::string message_data_ | std::string backtrace_data_]`.

### C ABI error protocol

The safe call convention uses the `TVMFFISafeCallType` signature:

```c
typedef int (*TVMFFISafeCallType)(void* handle, const TVMFFIAny* args,
                                   int32_t num_args, TVMFFIAny* result);
```

Return value: 0 for success, -1 for error. On error, the caller retrieves the
error via `TVMFFIErrorMoveFromRaised`.

The rationale for TLS-based error propagation is stated in the `c_api.h`
documentation: it simplifies error propagation in chains of compiler-generated
calls, as there is no need to pass the error through function arguments. The
C API provides four functions for setting errors:

1. `TVMFFIErrorSetRaised(TVMFFIObjectHandle error)` -- stores an existing
   Error object in TLS.
2. `TVMFFIErrorSetRaisedFromCStr(const char* kind, const char* message)` --
   creates an Error from C strings and auto-captures a backtrace.
3. `TVMFFIErrorSetRaisedFromCStrParts(const char* kind, const char** parts,
   int32_t num_parts)` -- for code generators that compose messages from
   reusable parts to reduce binary size of error strings.
4. `TVMFFIErrorMoveFromRaised(TVMFFIObjectHandle* result)` -- moves the error
   out of TLS, clearing the TLS slot.

The `TVMFFIErrorSetRaisedFromCStrParts` function is designed for compiler
code generation. For example, multiple error messages that share a common
function signature string (`"matmul(x: Tensor, y: Tensor, z: Tensor)"`) can
reuse it as one part, with the specific error detail as another part, reducing
storage duplication.

Two C API functions create error objects directly:

1. `TVMFFIErrorCreate(kind, message, backtrace, out)` -- unlike other C APIs,
   on failure this returns -1 for `MemoryError` without using TLS (to avoid
   infinite recursion in the error-handling loop).
2. `TVMFFIErrorCreateWithCauseAndExtraContext(kind, message, backtrace,
   cause_chain, extra_context, out)` -- creates an error with cause chaining.

The TLS implementation lives in `SafeCallContext` (`src/ffi/error.cc`):

```cpp
class SafeCallContext {
 public:
  void SetRaised(TVMFFIObjectHandle error);
  void MoveFromRaised(TVMFFIObjectHandle* result);

  static SafeCallContext* ThreadLocal() {
    static thread_local SafeCallContext ctx;
    return &ctx;
  }
 private:
  ObjectPtr<ErrorObj> last_error_;
};
```

### TVM_FFI_THROW and ErrorBuilder

`TVM_FFI_THROW(ErrorKind)` is the primary macro for raising errors in C++.
It creates a `details::ErrorBuilder` with the error kind as a stringified token,
captures a backtrace at the throw site, and allows streaming the message via
`<<`:

```cpp
#define TVM_FFI_THROW(ErrorKind)                                               \
  ::tvm::ffi::details::ErrorBuilder(                                           \
      #ErrorKind,                                                              \
      TVMFFIBacktrace(__FILE__, __LINE__, TVM_FFI_FUNC_SIG, 0),                \
      TVM_FFI_ALWAYS_LOG_BEFORE_THROW)                                         \
      .stream()
```

The `ErrorBuilder` class uses a deliberate pattern where the destructor throws.
The `<<` chaining builds up the message in an `ostringstream`, and when the
temporary `ErrorBuilder` is destroyed, the destructor constructs and throws
the `Error`:

```cpp
class ErrorBuilder {
 public:
  explicit ErrorBuilder(std::string kind, std::string backtrace,
                        bool log_before_throw);
  [[noreturn]] ~ErrorBuilder() noexcept(false) {
    ::tvm::ffi::Error error(std::move(kind_), stream_.str(),
                            std::move(backtrace_));
    if (log_before_throw_) {
      std::cerr << error.FullMessage();
    }
    throw error;
  }
  std::ostringstream& stream() { return stream_; }
 protected:
  std::string kind_;
  std::ostringstream stream_;
  std::string backtrace_;
  bool log_before_throw_;
};
```

Usage:

```cpp
TVM_FFI_THROW(ValueError) << "x must be positive, got " << x;
```

`TVM_FFI_LOG_AND_THROW(ErrorKind)` is a variant that always logs to stderr
before throwing, useful for startup and fatal errors where the exception may
not be caught. The `TVM_FFI_ALWAYS_LOG_BEFORE_THROW` compile flag (default 0)
can make all throws log first, which is useful in Wasm environments where
exceptions may be silently swallowed.

### Two-tier check macros

The check macros separate user-facing checks from internal invariant checks:

**Tier 1: `TVM_FFI_CHECK`** -- caller specifies the error kind:

```cpp
#define TVM_FFI_CHECK(cond, ErrorKind) \
  if (!(cond)) TVM_FFI_THROW(ErrorKind) \
    << "Check failed: (" #cond << ") is false: "

#define TVM_FFI_CHECK_BINARY_OP(name, op, x, y, ErrorKind)                \
  if (auto __tvm_ffi_log_err =                                            \
      ::tvm::ffi::details::LogCheck##name(x, y))                          \
  TVM_FFI_THROW(ErrorKind) << "Check failed: " << #x " " #op " " #y     \
                           << *__tvm_ffi_log_err << ": "
```

Typed variants: `TVM_FFI_CHECK_EQ`, `_LT`, `_GT`, `_LE`, `_GE`, `_NE`,
`_NOTNULL`. These produce messages like `"Check failed: x == y (3 vs. 5) :"`.

**Tier 2: `TVM_FFI_ICHECK`** -- always throws `InternalError`:

```cpp
#define TVM_FFI_ICHECK(x) TVM_FFI_CHECK(x, InternalError)
```

For developer-facing invariants that should never be violated in correct usage.
Typed variants: `TVM_FFI_ICHECK_EQ`, `_LT`, `_GT`, `_LE`, `_GE`, `_NE`,
`_NOTNULL`.

**Tier 3: `TVM_FFI_DCHECK`** -- debug-only checks (compiled out in release):

```cpp
#ifndef NDEBUG
#define TVM_FFI_DCHECK(x) TVM_FFI_ICHECK(x)
#else
#define TVM_FFI_DCHECK(x) \
  while (false) TVM_FFI_ICHECK(x)
#endif
```

Example usage showing the three tiers:

```cpp
TVM_FFI_CHECK(index >= 0, IndexError) << "negative index";     // user-facing
TVM_FFI_ICHECK_LT(ptr_offset, buffer_size) << "OOB";           // internal invariant
TVM_FFI_DCHECK_EQ(state, kInitialized);                         // debug only
```

The `LogCheck_EQ`, `LogCheck_LT`, etc. template functions handle signed/unsigned
comparison warning suppression via `#pragma GCC diagnostic ignored "-Wsign-compare"`.

### Error::what() vs Error::FullMessage() split

A key decision (commit `4bccb3e`) separated two methods on `Error`:

- `what()` returns `obj->message.data` directly -- zero allocation, truly
  `noexcept`, just the message text.
- `FullMessage()` constructs
  `"Traceback (most recent call last):\n{reversed_trace}{kind}: {message}\n"`
  -- may allocate, suitable for display.

```cpp
const char* what() const noexcept(true) override {
  ErrorObj* obj = static_cast<ErrorObj*>(data_.get());
  return obj->message.data;
}

std::string FullMessage() const {
  ErrorObj* obj = static_cast<ErrorObj*>(data_.get());
  return (std::string("Traceback (most recent call last):\n") +
          TracebackMostRecentCallLast() +
          std::string(obj->kind.data, obj->kind.size) + std::string(": ") +
          std::string(obj->message.data, obj->message.size) + '\n');
}
```

The previous design had `what()` allocating a TLS string with the full traceback,
which violated the `noexcept` contract and caused issues with LLVM JIT. The new
design makes `what()` safe for use in any context while `FullMessage()` is used
for human-readable display (e.g., in `ErrorBuilder::~ErrorBuilder()` for stderr
logging).

### Cause chaining

To support Python `raise B from A` semantics across FFI boundaries, two fields
were added to `TVMFFIErrorCell` (appended for ABI backward compatibility,
commit `4c712ca`):

- `cause_chain` (`TVMFFIObjectHandle`): singly-linked list of prior Error
  objects.
- `extra_context` (`TVMFFIObjectHandle`): opaque object for frontend-specific
  state (e.g., captured Python exception).

The five-argument `Error` constructor creates errors with cause chains:

```cpp
Error(std::string kind, std::string message, std::string backtrace,
      std::optional<Error> cause_chain, std::optional<ObjectRef> extra_context) {
  ObjectPtr<ErrorObj> error_obj = make_object<details::ErrorObjFromStd>(
      std::move(kind), std::move(message), std::move(backtrace));
  if (cause_chain.has_value()) {
    error_obj->cause_chain =
        details::ObjectUnsafe::MoveObjectRefToTVMFFIObjectPtr(
            *std::move(cause_chain));
  }
  if (extra_context.has_value()) {
    error_obj->extra_context =
        details::ObjectUnsafe::MoveObjectRefToTVMFFIObjectPtr(
            *std::move(extra_context));
  }
  data_ = std::move(error_obj);
}
```

The `cause_chain()` accessor returns `std::optional<Error>`:

```cpp
std::optional<Error> cause_chain() const {
  ErrorObj* obj = static_cast<ErrorObj*>(data_.get());
  if (obj->cause_chain != nullptr) {
    return details::ObjectUnsafe::ObjectRefFromObjectPtr<Error>(
        details::ObjectUnsafe::ObjectPtrFromUnowned<ErrorObj>(
            static_cast<Object*>(obj->cause_chain)));
  } else {
    return std::nullopt;
  }
}
```

Memory management is manual: `ErrorObj`'s destructor DecRefs both `cause_chain`
and `extra_context` handles. The C API function
`TVMFFIErrorCreateWithCauseAndExtraContext` provides this from C.

### Cross-language stack trace preservation

Backtrace storage convention: **most recent call first** (reversed from
Python's display order). This was established in commit `6f020c1`. The
rationale is O(1) append during error propagation up the stack -- new frames
are simply appended to the end. For display, the order is reversed on demand by
`TracebackMostRecentCallLast()` and `FullMessage()`.

Each frame uses the format: `  File "filename", line N, in funcname\n`
(Python-compatible even for C++ frames).

`TVMFFIBacktrace(filename, lineno, func, cross_ffi_boundary)` returns a
`const TVMFFIByteArray*` (TLS-owned). The traceback limit is configurable via
the `TVM_TRACEBACK_LIMIT` environment variable (default 512 frames).

`BacktraceStorage` (`src/ffi/backtrace_utils.h`) accumulates frames:

```cpp
struct BacktraceStorage {
  std::ostringstream backtrace_stream_;
  size_t line_count_ = 0;
  size_t max_frame_size = GetBacktraceLimit();
  size_t skip_frame_count = 0;
  bool stop_at_boundary = true;

  void Append(const char* filename, const char* func, int lineno) {
    backtrace_stream_ << "  File \"" << filename << "\"";
    backtrace_stream_ << ", line " << lineno;
    backtrace_stream_ << ", in " << func << '\n';
    line_count_++;
  }
};
```

Frame filtering (`ShouldExcludeFrame`) excludes internal FFI frames:
`tvm::ffi::Function*`, `tvm::ffi::details::*`, `TVMFFIBacktrace`,
`TVMFFIErrorSetRaisedFromCStr*`, `__libc_*`, `ffi_call_*`, and frames from
internal header files (`error.h`, `function.h`, `function_details.h`, `any.h`,
`include/c++/`).

Boundary detection (`DetectFFIBoundary`) stops at FFI boundary frames:
`TVMFFIFunctionCall`, `slot_tp_call`, `_Py*`, `PyObject*`.

The `update_backtrace` function pointer in `TVMFFIErrorCell` supports two
modes: `kTVMFFIBacktraceUpdateModeReplace` (0) and
`kTVMFFIBacktraceUpdateModeAppend` (1). This is used to concatenate C++ and
Python traces as errors cross boundaries.

On the Python side (`error.pxi`, `set_last_ffi_error`), backtrace
concatenation works as follows:

```python
# For errors originating in C++ (round-tripping):
ffi_error.update_backtrace(py_backtrace + c_backtrace)

# For fresh Python errors:
ffi_error = Error(kind, message, py_backtrace + c_backtrace)
```

The `_traceback_to_backtrace_str` function converts Python `TracebackType` to
the reversed-order backtrace string (to match the "most recent call first"
storage convention).

### Safe call boundary: TVM_FFI_SAFE_CALL_BEGIN/END

These macros wrap the C++/C ABI boundary where exceptions are caught and
converted to return codes:

```cpp
#define TVM_FFI_SAFE_CALL_BEGIN() \
  try {                           \
  (void)0

#define TVM_FFI_SAFE_CALL_END()                                          \
  return 0;                                                              \
  }                                                                      \
  catch (const ::tvm::ffi::Error& err) {                                 \
    ::tvm::ffi::details::SetSafeCallRaised(err);                         \
    return -1;                                                           \
  }                                                                      \
  catch (const std::exception& ex) {                                     \
    ::tvm::ffi::details::SetSafeCallRaised(                              \
        ::tvm::ffi::Error("InternalError", ex.what(), ""));              \
    return -1;                                                           \
  }                                                                      \
  TVM_FFI_UNREACHABLE()
```

The inverse macro converts return codes back to exceptions:

```cpp
#define TVM_FFI_CHECK_SAFE_CALL(func)                      \
  {                                                        \
    int ret_code = (func);                                 \
    if (ret_code != 0) {                                   \
      throw ::tvm::ffi::details::MoveFromSafeCallRaised(); \
    }                                                      \
  }
```

For functions in the error-handling loop itself (e.g., `TVMFFIErrorCreate`),
`TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` is used instead to avoid infinite
recursion. It catches exceptions, logs them to stderr, and calls `exit(-1)`:

```cpp
#define TVM_FFI_LOG_EXCEPTION_CALL_BEGIN() \
  try {                                    \
  (void)0

#define TVM_FFI_LOG_EXCEPTION_CALL_END(Name)                            \
  }                                                                     \
  catch (const std::exception& err) {                                   \
    std::cerr << "Exception caught during " << #Name << ":\n"           \
              << err.what() << std::endl;                                \
    exit(-1);                                                           \
  }
```

Primary usage: `FunctionObjImpl::SafeCall` wraps the packed function call
boundary. `TVM_FFI_DLL_EXPORT_TYPED_FUNC` wraps exported module functions.

### Python exception type mapping

Two global dictionaries map between error kind strings and Python types:
`ERROR_NAME_TO_TYPE` (string to Python type) and `ERROR_TYPE_TO_NAME`
(Python type to string).

Pre-registered mappings in `error.py`:

```python
register_error("RuntimeError", RuntimeError)
register_error("ValueError", ValueError)
register_error("TypeError", TypeError)
register_error("AttributeError", AttributeError)
register_error("KeyError", KeyError)
register_error("IndexError", IndexError)
register_error("AssertionError", AssertionError)
register_error("MemoryError", MemoryError)
```

`register_error` supports both decorator and function-call forms:

```python
def register_error(name_or_cls=None, cls=None):
    if isinstance(name_or_cls, type):
        cls = name_or_cls
        name_or_cls = cls.__name__
    def register(mycls):
        err_name = name_or_cls if isinstance(name_or_cls, str) else mycls.__name__
        core.ERROR_NAME_TO_TYPE[err_name] = mycls
        core.ERROR_TYPE_TO_NAME[mycls] = err_name
        return mycls
    if cls is None:
        return register
    return register(cls)
```

Error reconstruction (`Error.py_error()` in Cython) converts an FFI Error to
a Python exception:

```python
def py_error(self) -> BaseException:
    error_cls = ERROR_NAME_TO_TYPE.get(self.kind, RuntimeError)
    py_error = error_cls(self.message)
    py_error = _WITH_APPEND_BACKTRACE(py_error, self.backtrace)
    py_error.__tvm_ffi_error__ = self
    return py_error
```

The `__tvm_ffi_error__` attribute enables round-trip: when a Python exception
with this attribute crosses back through FFI, the existing FFI Error object is
reused instead of creating a new one.

Error capture (`set_last_ffi_error` in Cython) converts a Python exception to
an FFI Error:

```python
cdef inline int set_last_ffi_error(error) except -1:
    kind = ERROR_TYPE_TO_NAME.get(type(error), "RuntimeError")
    message = error.__str__()
    py_backtrace = _TRACEBACK_TO_BACKTRACE_STR(error.__traceback__)
    c_backtrace = bytearray_to_str(TVMFFIBacktrace(NULL, 0, NULL, 0))
    if hasattr(error, "__tvm_ffi_error__"):
        ffi_error = error.__tvm_ffi_error__
        ffi_error.update_backtrace(py_backtrace + c_backtrace)
        TVMFFIErrorSetRaised(ffi_error.chandle)
    else:
        ffi_error = Error(kind, message, py_backtrace + c_backtrace)
        TVMFFIErrorSetRaised(ffi_error.chandle)
```

`CHECK_CALL` in Cython handles the return value:

```python
cdef inline int CHECK_CALL(int ret) except -2:
    if ret == 0:
        return 0
    if ret == -2:
        raise raise_existing_error()
    error = move_from_last_error()
    if error.kind == "EnvErrorAlreadySet":
        raise raise_existing_error()
    raise error.py_error()
```

### EnvErrorAlreadySet and signal checking

`EnvErrorAlreadySet` is a special error kind that signals the frontend
(Python) already has an error set. It is created by a factory function:

```cpp
inline Error EnvErrorAlreadySet() { return Error("EnvErrorAlreadySet", "", ""); }
```

Used with `TVMFFIEnvCheckSignals()` to support Python signal handling
(e.g., Ctrl-C / `KeyboardInterrupt`) in long-running C++ functions:

```cpp
void ExampleLongRunningFunction() {
  if (TVMFFIEnvCheckSignals() != 0) {
    throw ::tvm::ffi::EnvErrorAlreadySet();
  }
  // do work here
}
```

Python-side `CHECK_CALL` special-cases this: if `error.kind ==
"EnvErrorAlreadySet"`, it re-raises the existing Python error without
conversion.

### Expected<T> for exception-free error handling

`Expected<T>` provides exception-free error handling, similar to
`std::expected<T, Error>` (C++23) or Rust's `Result<T, Error>`. Introduced
in commit `0a9d4b6`.

```cpp
template <typename T>
class Expected {
 public:
  static_assert(!std::is_same_v<T, Error>,
                "Expected<Error> is not allowed. Use Error directly.");

  Expected(T value);              // implicit from success value
  Expected(Error error);          // implicit from error
  Expected(Unexpected<E> unexpected);  // from Unexpected wrapper

  bool is_ok() const;
  bool is_err() const;
  bool has_value() const;
  T value() const&;       // throws contained Error if is_err()
  Error error() const&;   // throws RuntimeError if is_ok()
  T value_or(U&& default_value) const;
 private:
  Any data_;  // Holds either T or Error
};
```

`Function::CallExpected<T>` uses the `safe_call` path (not `cpp_call`) to
catch exceptions and return them as `Unexpected`:

```cpp
template <typename T = Any, typename... Args>
Expected<T> CallExpected(Args&&... args) const {
  // ... pack args ...
  int ret_code = func_obj->safe_call(func_obj, args_pack, kNumArgs, &result);
  if (ret_code == 0) {
    if constexpr (std::is_same_v<T, Any>) {
      return std::move(result);
    } else {
      if (auto val = result.template try_cast<T>()) return *std::move(val);
      if (auto err = result.template try_cast<Error>()) return Unexpected(std::move(*err));
      return Unexpected(Error("TypeError", "CallExpected: result type mismatch...", ""));
    }
  } else {
    return Unexpected(details::MoveFromSafeCallRaised());
  }
}
```

`TypeTraits<Expected<T>>` allows `Expected<T>` to be passed through the FFI
as an `Any` value transparently: it stores either `T` or `Error` in the
underlying `Any`.

### GC cycle optimization for error objects

When Python-side traceback frames are attached to error objects, reference
cycles form between exception objects, traceback objects, and frame objects.
Without breaking these cycles, objects held by those frames (e.g., Tensors) are
freed slowly by the garbage collector rather than immediately by reference
counting.

The cycle diagram from `error.py` illustrates the problem:

```
        [Stack Frames]                            [Heap Objects]
    +-------------------+
    | outside functions | -----------------------> [ Tensor ]
    +-------------------+                   (Held by cycle, slow to free)
            ^
            | f_back
    +-------------------+  locals      py_error
    | py_error (this)   | -----+--------------> [ BaseException ]
    +-------------------+      |                       |
            ^                  |                       | (with_traceback)
            | f_back           |                       v
    +-------------------+      +--------------> [ Traceback Obj ]
    | append_traceback  |                   tb         |
    +-------------------+                              |
            ^                                          |
            | f_back                                   |
    +-------------------+                              |
    | _get_frame        | <----------------------------+
    +-------------------+      (Cycle closes here)
```

The solution (commit `6ccbdb6`, PR #327) uses two techniques:

1. `TracebackManager.append_traceback` uses a nested `create` function to
   avoid holding the frame object in its local variables, which would extend
   the cycle.

2. `_with_append_backtrace` explicitly `del py_error, tb` in a `finally`
   block:

```python
def _with_append_backtrace(py_error, backtrace):
    tb = py_error.__traceback__
    try:
        for filename, lineno, func in _parse_backtrace(backtrace):
            tb = _TRACEBACK_MANAGER.append_traceback(tb, filename, lineno, func)
        return py_error.with_traceback(tb)
    finally:
        del py_error, tb
```

The `finally` block executes after the return value is captured but before
the function frame is cleaned up, breaking the reference cycle.

Additionally, `TracebackManager._get_cached_code_object` caches compiled code
objects by `(filename, lineno, func)` key to avoid repeated `ast.parse` +
`compile` calls.

## APIs

### C API

```c
// Error propagation via TLS
void TVMFFIErrorSetRaised(TVMFFIObjectHandle error);
void TVMFFIErrorSetRaisedFromCStr(const char* kind, const char* message);
void TVMFFIErrorSetRaisedFromCStrParts(const char* kind, const char** message_parts,
                                       int32_t num_parts);
void TVMFFIErrorMoveFromRaised(TVMFFIObjectHandle* result);

// Error object creation
int TVMFFIErrorCreate(const TVMFFIByteArray* kind, const TVMFFIByteArray* message,
                      const TVMFFIByteArray* backtrace, TVMFFIObjectHandle* out);
int TVMFFIErrorCreateWithCauseAndExtraContext(
    const TVMFFIByteArray* kind, const TVMFFIByteArray* message,
    const TVMFFIByteArray* backtrace, TVMFFIObjectHandle cause_chain,
    TVMFFIObjectHandle extra_context, TVMFFIObjectHandle* out);

// Backtrace capture
const TVMFFIByteArray* TVMFFIBacktrace(const char* filename, int lineno,
                                       const char* func, int cross_ffi_boundary);
```

### C++ API

```cpp
// Error creation
TVM_FFI_THROW(ErrorKind) << "message";
TVM_FFI_LOG_AND_THROW(ErrorKind) << "message";

// Check macros
TVM_FFI_CHECK(cond, ErrorKind) << "message";
TVM_FFI_CHECK_EQ(x, y, ErrorKind) << "message";
TVM_FFI_ICHECK(cond) << "message";
TVM_FFI_DCHECK(cond);

// Safe call boundary
TVM_FFI_SAFE_CALL_BEGIN();
TVM_FFI_SAFE_CALL_END();
TVM_FFI_CHECK_SAFE_CALL(c_api_call);

// Exception-free error handling
Expected<T> result = func.CallExpected<T>(args...);

// Signal checking
Error EnvErrorAlreadySet();
```

### Python API

```python
# Register custom error types
@tvm_ffi.error.register_error
class MyError(RuntimeError):
    pass

@tvm_ffi.error.register_error("CustomName")
class AnotherError(RuntimeError):
    pass

# Error object (from Cython)
error = tvm_ffi.Error(kind, message, backtrace)
error.kind        # str
error.message     # str
error.backtrace   # str
error.py_error()  # -> BaseException
```

## Implementation

Key source files:

| File | Role |
|------|------|
| `include/tvm/ffi/c_api.h` | C ABI: `TVMFFIErrorCell`, `TVMFFISafeCallType`, error C API functions |
| `include/tvm/ffi/error.h` | C++ API: `ErrorObj`, `Error`, `ErrorBuilder`, CHECK/ICHECK/DCHECK macros |
| `include/tvm/ffi/expected.h` | `Expected<T>`, `Unexpected<E>` for exception-free handling |
| `include/tvm/ffi/function.h` | `SAFE_CALL_BEGIN/END`, `CHECK_SAFE_CALL`, `Function::CallExpected<T>` |
| `include/tvm/ffi/base_details.h` | `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` |
| `src/ffi/error.cc` | `SafeCallContext` TLS implementation, C API function bodies |
| `src/ffi/backtrace_utils.h` | `BacktraceStorage`, frame filtering, boundary detection |
| `python/tvm_ffi/error.py` | `register_error`, `TracebackManager`, GC cycle optimization |
| `python/tvm_ffi/cython/error.pxi` | Cython `Error` class, `CHECK_CALL`, `set_last_ffi_error`, `py_error()` |
| `python/tvm_ffi/core.pyi` | Type stubs for `Error` class |

Tests:
- `tests/cpp/test_error.cc` -- C++ error creation and propagation
- `tests/python/test_error.py` -- Python error mapping and traceback reconstruction

## History

- **6f020c1** 2025-09-22 -- Updated backtrace storage to "most recent call first" order for append-friendly propagation
- **9c0b869** 2025-10-30 -- Added example coverage to `register_error` docstring
- **227bdd0** 2025-11-04 -- Improved error propagation in allocation paths
- **4bccb3e** 2025-11-07 -- Split `Error::what()` (zero-alloc, message only) from `Error::FullMessage()` (full traceback)
- **6ccbdb6** 2025-12-12 -- Removed reference cycle in error handling for faster GC (PR #327)
- **4c712ca** 2026-01-11 -- Added `cause_chain` and `extra_context` fields to `TVMFFIErrorCell` for error cause chaining
- **e1bd421** 2026-01-13 -- Fixed error propagation in the case of tensor arguments
- **0a9d4b6** 2026-02-06 -- Added `ffi::Expected<T>` for exception-free error handling

## Related

- ADRs:
  - `.repo-knowledge/adr/013-error-what-vs-fullmessage.md`
  - `.repo-knowledge/adr/016-error-cause-chaining.md`
- Related design docs:
  - `.repo-knowledge/design/001-type-erased-value-system.md`
  - `.repo-knowledge/design/003-c-abi-stability.md`
- Sphinx documentation:
  - `docs/concepts/exception_handling.rst`
