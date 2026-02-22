# Error Handling Evolution

> Range: `8b46833..ecc7471` (2025-12-12 to 2026-02-21, 100 commits)

## Overview

The error handling subsystem gained three major capabilities: generalized CHECK
macros with custom error kinds, an `Expected<T>` type for exception-free error
handling, and error cause chaining. Together these provide both exception-based
and exception-free paths with rich error typing.

## Timeline

| Date | SHA | Change |
|------|-----|--------|
| 2026-01-11 | `4c712ca` | Update Error to enable future compact cause chaining (#396) |
| 2026-02-03 | `b1611e0` | Unify EnvErrorAlreadySet to error.kind (#425) |
| 2026-02-06 | `0a9d4b6` | Add `ffi::Expected<T>` for exception-free handling (#399) |
| 2026-02-19 | `35cbc32` | Complete support of CHECK macros (#465) |

## Key Changes

### 1. Generalized CHECK Macros (`35cbc32`)

Previously only `ICHECK` macros existed, always throwing `InternalError`.

New macros accept a custom error kind:
```cpp
TVM_FFI_CHECK_EQ(x, y, ValueError);      // throws ValueError
TVM_FFI_CHECK_LT(size, max, IndexError);  // throws IndexError
TVM_FFI_CHECK(cond, TypeError);           // single-condition check
TVM_FFI_CHECK_NOTNULL(ptr, ValueError);   // null pointer check
```

`ICHECK` macros are now thin wrappers:
```cpp
#define TVM_FFI_ICHECK_EQ(x, y) TVM_FFI_CHECK_EQ(x, y, InternalError)
```

`DCHECK` macros are compiled out in release builds (`NDEBUG`):
```cpp
TVM_FFI_DCHECK_EQ(x, y);  // no-op when NDEBUG defined
```

**Files**: `include/tvm/ffi/error.h`

### 2. Expected<T> — Exception-Free Path (`0a9d4b6`)

New `Expected<T>` class modeled after Rust's `Result<T, Error>` and C++23
`std::expected`:

```cpp
Expected<int> result = func.CallExpected<int>(arg1, arg2);
if (result.is_ok()) {
    int val = result.value();
} else {
    Error err = result.error();
}
```

Key API:
- `Expected<T>` — holds either `T` or `Error`
- `Unexpected<E>` — explicit error-state constructor
- `Function::CallExpected<T>()` — exception-free function invocation
- `is_ok()`, `is_err()`, `value()`, `error()`, `value_or(default)`
- Full `TypeTraits` specialization for integration with Any type system

**Files**: `include/tvm/ffi/expected.h`, `include/tvm/ffi/function.h`

### 3. Error Cause Chaining (`4c712ca`)

Updated the `Error` type to support cause chaining for future compact error
propagation. This enables wrapping lower-level errors as causes of higher-level
errors, similar to Java's `Throwable.getCause()` or Rust's `Error::source()`.

**Files**: `include/tvm/ffi/c_api.h`, `include/tvm/ffi/error.h`

### 4. Unified EnvErrorAlreadySet (`b1611e0`)

Unified the `EnvErrorAlreadySet` handling to use `error.kind` consistently
across C++ and Cython. This ensures that errors propagated from the Python
environment maintain their kind when re-thrown through C++.

**Files**: `src/ffi/error.cc`, `python/tvm_ffi/cython/error.pxi`

## Architecture

```
Error Handling Strategies
├── Exception-based (existing)
│   ├── TVM_FFI_THROW(ErrorKind) << "message"
│   ├── TVM_FFI_CHECK_*(x, y, ErrorKind)  ← NEW (35cbc32)
│   ├── TVM_FFI_ICHECK_*(x, y)            (InternalError shorthand)
│   └── TVM_FFI_DCHECK_*(x, y)            ← NEW, debug-only (35cbc32)
│
└── Exception-free (new)
    ├── Expected<T>                        ← NEW (0a9d4b6)
    ├── Function::CallExpected<T>()        ← NEW (0a9d4b6)
    └── Unexpected<E>                      ← NEW (0a9d4b6)
```

## Design Decisions

1. **Expected<T> uses internal Any storage**: Rather than a tagged union,
   `Expected<T>` stores the value/error in an `Any`. This reuses the existing
   type-erasure infrastructure and avoids alignment/size complications.
   (`0a9d4b6`)

2. **CHECK macros are compile-time typed**: The `ErrorKind` parameter is a
   type name (not a string), enabling the macro to construct the correct
   exception type at compile time. (`35cbc32`)

3. **DCHECK uses `NDEBUG` guard**: Consistent with `assert()` and Google's
   approach. When `NDEBUG` is defined, `DCHECK` macros expand to nothing.
   (`35cbc32`)

## Tests

- `tests/cpp/test_error.cc` — CHECK macro tests (+81 lines, `35cbc32`)
- `tests/cpp/test_expected.cc` — 345 lines, ~25 test cases (`0a9d4b6`)
