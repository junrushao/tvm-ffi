---
scope:
  - "0001-c-abi"
---
# Remove v_char32 from TVMFFIAny Union for C Compilation Compatibility

**TL;DR**: The `char32_t v_char32[2]` field was removed from the `TVMFFIAny` value union because `char32_t` is a C++-only type, preventing `c_api.h` from compiling with a pure C compiler. The field overlapped with `v_bytes[8]` (same offset, same size), so no data layout change occurred.

## Context

The `TVMFFIAny` union contained a `char32_t v_char32[2]` member intended for small UCS-4 string storage. However, `char32_t` is defined in `<uchar.h>` in C++ but is not a standard C type in all compilers. When the project needed to support pure-C compiler backends (for compiler codegen targeting the FFI ABI convention), `c_api.h` failed to compile with C compilers because of this field.

The same commit (c100338d) also:
- Moved the `DLPackTensorAllocator` typedef inside the `extern "C"` block (it was outside, causing linkage issues in C).
- Added a forward declaration for `DLManagedTensorVersioned` (needed for the typedef).
- Added a C example (`examples/quick_start/src/add_one_c.c`) demonstrating pure-C FFI usage.

Usecases:
- Compiler backends that generate pure C code targeting the FFI ABI (e.g., `__tvm_ffi_add_one_c` symbol).
- Embedded or minimal environments where only a C compiler is available.

Design Decisions:
- Remove `v_char32[2]` entirely rather than guarding it with `#ifdef __cplusplus`. This keeps the union definition identical between C and C++ compilation, avoiding subtle ABI divergence. The field overlapped with `v_bytes[8]` at the same offset and size (8 bytes), so existing code using `v_bytes` for small string storage is unaffected.

## Alternatives Considered

### Alternative: `#ifdef __cplusplus` guard around `v_char32`

- Would preserve the field for C++ callers while hiding it from C.
- Risk: The union layout would differ between C and C++ compilation units if padding or alignment differed between `char32_t[2]` and other members. In practice the overlap with `v_bytes[8]` is safe, but the principle of identical-layout-across-languages is violated.
- Rejected because: the `v_char32` field had no known consumers; all small string operations used `v_bytes[8]` directly.

### Alternative: Include `<uchar.h>` for C compilation

- `char32_t` is available in C11 via `<uchar.h>`, but not all C compilers support it (e.g., MSVC's C mode historically had limited C11 support).
- Rejected because: adding a C11 requirement for an unused field is unnecessary complexity.

## Consequences

- **Breaking change**: Any code directly referencing `any.v_char32` will fail to compile. No known consumers existed at the time of removal.
- **No data layout change**: `v_char32[2]` (8 bytes) occupied the same union space as `v_bytes[8]`. The `TVMFFIAny` struct remains 16 bytes.
- **C compilation enabled**: `c_api.h` can now be compiled by any C99+ compiler, enabling pure-C compiler codegen backends.

## Implementation Notes

- Commit `c100338d` removes the field, moves `DLPackTensorAllocator` inside `extern "C"`, adds `DLManagedTensorVersioned` forward declaration, and adds a pure-C example.
- The companion `--cflags` CLI option (`python -m tvm_ffi.config --cflags`) provides C compilation flags without `-std=c++17`.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- TVMFFIAny union layout definition
- [`.knowledge/designs/0008-module-export-system.md`](../designs/0008-module-export-system.md) -- `__tvm_ffi_` symbol prefix convention used by the C example
