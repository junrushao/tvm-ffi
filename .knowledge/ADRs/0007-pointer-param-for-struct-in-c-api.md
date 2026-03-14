---
scope:
  - "0001-c-abi"
---
# Pointer-Based Parameters for Small Structs in C API

**TL;DR**: C API functions accept small C structs (`DLDataType`, `DLDevice`) via `const T*` (pointer) instead of `T` (by value) to ensure ABI portability across WebAssembly/Emscripten and native platforms.

## Context

`TVMFFIDataTypeToString` originally accepted `DLDataType` by value. On WebAssembly/Emscripten, passing small C structs by value across the FFI boundary has inconsistent calling conventions -- different compilers may pass small structs in registers vs. on the stack differently across the WASM FFI boundary, causing ABI compatibility bugs.

Usecases:
- Calling `TVMFFIDataTypeToString` from Python/Cython through the C API on WASM targets.
- Any future C API function that accepts `DLDataType`, `DLDevice`, or similar small structs.

Design Decisions:
- **Pass by pointer**: `TVMFFIDataTypeToString(const DLDataType* dtype, ...)` instead of `TVMFFIDataTypeToString(DLDataType dtype, ...)`. The pointer indirection cost is negligible for utility functions.
- **Convention applies to all small structs**: Any future C API function receiving a struct parameter should use `const T*`.

**Alternatives considered**:

1. **Pass by value (status quo)**: Simpler but breaks WASM interop.
2. **Flatten struct fields into scalar parameters**: Avoids both pointer indirection and struct ABI issues, but changes the API surface more invasively and is fragile when struct fields change.

**Consequences**:
- All language bindings calling `TVMFFIDataTypeToString` must pass a pointer instead of a value.
- Negligible performance cost (one level of indirection for utility functions).
- Aligns input parameter convention with output parameters (which already use `T*`).

## Implementation Notes

- `TVMFFIDataTypeToString` changed from `DLDataType` to `const DLDataType*` in `include/tvm/ffi/c_api.h`.
- The C++ wrapper `DLDataTypeToString` in `include/tvm/ffi/dtype.h` was updated to pass `&dtype`.
- Evidence: `include/tvm/ffi/c_api.h`, commit `076ac23`.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI conventions
