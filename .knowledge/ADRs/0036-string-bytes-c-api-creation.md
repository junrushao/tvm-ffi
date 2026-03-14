---
scope:
  - "0001-c-abi"
  - "0005-containers"
  - "0014-python-bindings"
---
# TVMFFIStringFromByteArray / TVMFFIBytesFromByteArray C API

**TL;DR**: Adds formal C API functions for creating `String`/`Bytes` objects (supporting SSO) directly from `TVMFFIByteArray`, replacing the informal pattern of passing `kTVMFFIRawStr`/`kTVMFFIByteArrayPtr` and relying on callee-side conversion.

## Context

Previously, Cython packed string arguments as `kTVMFFIRawStr` (a raw `const char*` pointer) and bytes as `kTVMFFIByteArrayPtr` (a pointer to `TVMFFIByteArray`). The callee C++ function had to convert these to `String`/`Bytes` objects, which meant:
1. No SSO benefit at the packing site (the raw pointer form has no size field to detect small strings).
2. Inconsistent ownership semantics: the raw pointer was borrowed from a Python string, requiring the Python object to stay alive.
3. Each callee independently converted to `String`, duplicating the conversion logic.

Usecases:
- Every FFI function receiving `str` or `bytes` arguments from Python.
- Container construction: nested `list`/`dict` with string keys/values need `String` objects for the `Array`/`Map` constructors.

Design Decisions:
- Add `TVMFFIStringFromByteArray(const TVMFFIByteArray* input, TVMFFIAny* out)` and `TVMFFIBytesFromByteArray(const TVMFFIByteArray* input, TVMFFIAny* out)` to `c_api.h`.
- These functions create proper `String`/`Bytes` objects (using SSO for strings up to 7 bytes) and write the result into `TVMFFIAny`.
- Cython setters (`SetterStr_`, `SetterBytes_`) call these C APIs instead of passing raw pointers.
- String arguments now arrive at C++ as `kTVMFFISmallStr`/`kTVMFFIStr` objects rather than `kTVMFFIRawStr` pointers.

## Alternatives

### 1. Formal C API creation functions (chosen)
- Pros: Uniform ownership (caller creates, ref-counted). SSO benefit at packing time. Callee receives ready-to-use objects.
- Cons: Slight overhead for small strings that previously fit in zero-copy `kTVMFFIRawStr`. Extra function call per string argument.

### 2. Keep `kTVMFFIRawStr` with callee-side conversion
- Pros: Simpler packing. Zero-copy for small strings.
- Cons: No SSO. Callee must convert. Inconsistent ownership. Raw pointer lifetime depends on Python GC.

### 3. Add `TVMFFISmallStrFromCStr` micro-API
- Pros: Optimized for small strings only.
- Cons: Too specialized. Does not handle large strings. Two code paths instead of one.

## Decision

Option 1. The `TVMFFIStringFromByteArray` function internally checks `input->size <= kMaxSmallBytesLen` and uses SSO, otherwise allocates a heap `StringObj`. This unifies the creation path.

## Implementation Notes

- `TVMFFIPyArgSetterStr_` extracts `(data, size)` from the Python string via `PyUnicode_AsUTF8AndSize`, constructs a `TVMFFIByteArray`, and calls `TVMFFIStringFromByteArray`.
- `TVMFFIPyArgSetterBytes_` extracts `(data, size)` via `PyBytes_AS_STRING`/`PyBytes_GET_SIZE` and calls `TVMFFIBytesFromByteArray`.
- Temporary FFI objects from string/bytes creation are tracked via `TVMFFIPyPushTempFFIObject` (not `TVMFFIPyPushTempPyObject`), ensuring ref-count management through the FFI layer.
- The `_FUNC_CONVERT_TO_OBJECT` Python callback and `_STR_CONSTRUCTOR`/`_BYTES_CONSTRUCTOR` module-level variables are removed, simplifying the initialization chain.

## Consequences

- **ABI-level semantic change**: String arguments arrive as `kTVMFFIStr`/`kTVMFFISmallStr` objects instead of `kTVMFFIRawStr` pointers. Callee functions that special-case `kTVMFFIRawStr` must be updated.
- **SSO benefit**: Strings up to 7 bytes avoid heap allocation at the packing site.
- **Initialization simplification**: `_convert.py` no longer registers itself into the Cython core layer via `_set_func_convert_to_object`.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI where the functions are declared
- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- String/Bytes SSO design
- [`.knowledge/designs/0019-python-ffi-call-dispatch.md`](../designs/0019-python-ffi-call-dispatch.md) -- Setter architecture consuming these APIs
- Commit: `.knowledge/commits/2025-09-13-043d9f647677cc3b4a8baba198a2ced45f99cc98.md` + `043d9f6`
