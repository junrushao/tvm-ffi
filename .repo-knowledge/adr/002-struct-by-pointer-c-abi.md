# ADR 002: Pass Structs by Pointer in C API

- Status: Accepted
- Date: 2025-05-11
- Owners: Tianqi Chen

## Context

The TVM FFI C API (`c_api.h`) is consumed across multiple language runtimes
(Python/Cython, Rust, JavaScript/Wasm) and compiled with different toolchains
(GCC, Clang, MSVC, Emscripten). When small C structs such as `DLDataType`
(a 4-byte struct of bitfields) are passed by value, different compilers and
calling conventions disagree on whether the struct is passed in a register or
on the stack. This caused ABI mismatches observed during the WebAssembly
runtime migration.

Specifically, `TVMFFIDataTypeToString(DLDataType dtype, ...)` produced
incorrect behavior when the caller and callee were compiled with different
struct-passing conventions.

## Decision

All C API functions that accept struct-typed parameters must take them by
const pointer, not by value.

Applied change: `TVMFFIDataTypeToString(DLDataType dtype, ...)` was changed to
`TVMFFIDataTypeToString(const DLDataType* dtype, ...)`.

The wrapper `DLDataTypeToString(DLDataType dtype)` in C++ header `dtype.h` now
passes `&dtype` to the C API, keeping the C++ convenience API unchanged.

This rule applies to any future C API additions that take struct parameters.

## Consequences

- Positive: Eliminates struct-passing ABI mismatches across compilers and
  targets (native, WebAssembly, cross-compiled).
- Positive: The C++ convenience wrappers hide the pointer indirection, so
  C++ callers see no ergonomic cost.
- Negative: **Breaking C ABI change** for `TVMFFIDataTypeToString`. All direct C
  callers must update to pass `&dtype` instead of `dtype`.
- Migration/Rollout: Update all C call sites of `TVMFFIDataTypeToString`. The
  C++ wrapper was updated in the same commit, so C++ callers are unaffected.

## References
- Range summary: `.repo-knowledge/ranges/2025-05-29-7D34EB8-024E45C.md`
- Evidence commits: `076ac23e994e404c40a789ccc42a1497a31e1280`
- External references: DLPack specification (struct layout)

## Related Design Docs
- `.repo-knowledge/design/003-c-abi-stability.md`

## Notes
This decision is consistent with the general FFI design principle that the C ABI
layer should avoid any constructs whose behavior varies across calling
conventions. Pointers have uniform ABI semantics on all supported targets.
