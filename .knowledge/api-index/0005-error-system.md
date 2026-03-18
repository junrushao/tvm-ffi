---
scope: "error-system"
---
# API Index: Error System

**Scope**: C++ Error, ErrorObj, error macros, and check macros.
**Design docs**: [0005-error-system.md](../designs/0005-error-system.md)
**ADRs**: [0002-tls-error-propagation.md](../ADRs/0002-tls-error-propagation.md), [0018-expected-for-exception-free-error-handling.md](../ADRs/0018-expected-for-exception-free-error-handling.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `ErrorObj` | class | Inherits `Object` + `TVMFFIErrorCell` (kind, message, backtrace, update_backtrace) | Object-based error with structured fields |
| `Error` | class | `Error(kind, message, backtrace)`, `kind() -> string`, `message() -> string`, `backtrace() -> string`, `TracebackMostRecentCallLast() -> string`, `UpdateBacktrace(backtrace, update_mode)`, `what() -> const char*` (message only), `FullMessage() -> string` (full traceback+kind+message) | Managed error ref, also std::exception. Non-nullable. `what()` returns message only (noexcept); use `FullMessage()` for full formatted output. |
| `EnvErrorAlreadySet()` | function | `Error EnvErrorAlreadySet()` -> returns `Error("EnvErrorAlreadySet", "", "")` | Factory function replacing former exception class (b1611e0). Returns regular Error with kind-based dispatch. |
| `Expected<T>` | class template | `Expected(T)`, `Expected(Error)`, `Expected(Unexpected<E>)`, `is_ok() -> bool`, `is_err() -> bool`, `value() -> T`, `error() -> Error`, `value_or(U) -> T` | Exception-free error container: holds either T or Error (0a9d4b6) |
| `Unexpected<E>` | class template | `Unexpected(E error)`, `error() -> E` | Explicit error wrapper for Expected construction (0a9d4b6) |
| `TVMFFIErrorCreateWithCauseAndExtraContext` | C ABI function | `int TVMFFIErrorCreateWithCauseAndExtraContext(kind, message, backtrace, cause_chain, extra_context, out)` | Create error with cause chain and extra context fields (4c712ca) |
| `ErrorBuilder` | class | `ostringstream& stream()`, destructor throws Error | Internal: stream-style error construction |
| `TVM_FFI_THROW(ErrorKind)` | macro | `ErrorBuilder("ErrorKind", TVMFFIBacktrace(...), TVM_FFI_ALWAYS_LOG_BEFORE_THROW).stream()` | Throw an error with automatic backtrace capture |
| `TVM_FFI_LOG_AND_THROW(ErrorKind)` | macro | Same as THROW but logs to stderr first | For startup errors that cannot be caught |
| `TVM_FFI_CHECK(cond, ErrorKind)` | macro | `if (!(cond)) TVM_FFI_THROW(ErrorKind) << ...` | Assert condition, throw caller-specified ErrorKind on failure |
| `TVM_FFI_ICHECK(x)` | macro | `if (!(x)) TVM_FFI_THROW(InternalError) << ...` | Assert condition, throw InternalError on failure |
| `TVM_FFI_ICHECK_LT(x, y)` | macro | `if (x >= y) TVM_FFI_THROW(InternalError) << ...` | Assert x < y with formatted error (shows values) |
| `TVM_FFI_ICHECK_GT(x, y)` | macro | `if (x <= y) TVM_FFI_THROW(InternalError) << ...` | Assert x > y |
| `TVM_FFI_ICHECK_LE(x, y)` | macro | `if (x > y) TVM_FFI_THROW(InternalError) << ...` | Assert x <= y |
| `TVM_FFI_ICHECK_GE(x, y)` | macro | `if (x < y) TVM_FFI_THROW(InternalError) << ...` | Assert x >= y |
| `TVM_FFI_ICHECK_EQ(x, y)` | macro | `if (x != y) TVM_FFI_THROW(InternalError) << ...` | Assert x == y |
| `TVM_FFI_ICHECK_NE(x, y)` | macro | `if (x == y) TVM_FFI_THROW(InternalError) << ...` | Assert x != y |
| `TVM_FFI_ICHECK_NOTNULL(x)` | macro | `if (x == nullptr) TVM_FFI_THROW(InternalError) << ...` | Assert pointer is not null |
