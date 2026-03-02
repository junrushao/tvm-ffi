---
adr: "0009"
title: "Isolate Non-Core C++ APIs into extra/ Directory"
status: "accepted"
date: "2025-07-30"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "build-system"
source_commits:
  - "9445fe734839cffc8bdf881788528b7763f7be03"
  - "2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec"
  - "3fc0391e29dac100ad37db45348090438e1db739"
  - "de541e37ad3820033856cc8a0af55e896af55a3b"
  - "8eaefe04a044292e071263aca309b6991124c566"
  - "f4ede982f00257881d9ba7fe82dd8abc07e14690"
  - "1a271f00321b8cc16b72e58436716a05e2f62500"
  - "538bef49b4daa91970f0f9cea137acdcb696562a"
  - "0daaffedd23982ea09f8c38fec4eef1cca1d8cac"
  - "023ea448be6e86e09f4ebaba5a235ee53f3cdeef"
source_ledgers:
  - ".memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md"
  - ".memory/commits/2025-07-26-2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec.md"
  - ".memory/commits/2025-07-30-3fc0391e29dac100ad37db45348090438e1db739.md"
  - ".memory/commits/2025-08-04-de541e37ad3820033856cc8a0af55e896af55a3b.md"
  - ".memory/commits/2025-08-05-8eaefe04a044292e071263aca309b6991124c566.md"
  - ".memory/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md"
  - ".memory/commits/2025-08-15-1a271f00321b8cc16b72e58436716a05e2f62500.md"
  - ".memory/commits/2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md"
  - ".memory/commits/2025-08-19-0daaffedd23982ea09f8c38fec4eef1cca1d8cac.md"
  - ".memory/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md"
---

# ADR-0009: Isolate Non-Core C++ APIs into extra/ Directory

## TL;DR
- Non-core C++ APIs (structural equal/hash, and potentially other convenience features) are isolated into `include/tvm/ffi/extra/` with a dedicated `TVM_FFI_EXTRA_CXX_API` visibility macro, gated by a `TVM_FFI_USE_EXTRA_CXX_API` CMake option (default ON).
- This establishes a layering boundary: core FFI (always built) vs. extra C++ APIs (conditionally built), reducing compile-time overhead and shared library size for minimal deployments.

## Status
Accepted

## Context
The structural equal/hash system, built on top of the reflection infrastructure, adds significant code to the shared library (three `.cc` files with complex traversal logic). Not all consumers need deep structural comparison -- minimal builds that only need object creation, function calls, and serialization should be able to exclude these features. Additionally, the structural equal/hash classes are C++-linkage-only APIs that may have ABI compatibility issues across MSVC/Itanium, unlike the core C ABI functions.

The `TVM_FFI_EXTRA_CXX_API` macro was initially defined in `c_api.h` (commit `9445fe7`) but was later moved to `extra/base.h` (commit `3fc0391`) to properly isolate it from the core header.

## Decision Drivers
- Build size: minimal deployments should exclude non-essential features.
- Compile time: translation units that do not use structural comparison should not pay the compilation cost.
- ABI clarity: C++ linkage APIs have different ABI stability guarantees than the core C ABI.
- Layering: the core FFI should have no dependency on structural comparison.

## Decision
Create an `include/tvm/ffi/extra/` directory with `base.h` as the root header. Move structural equal/hash headers and source files into this namespace. Gate the source compilation with `TVM_FFI_USE_EXTRA_CXX_API` CMake option.

Specifically:
- `include/tvm/ffi/extra/base.h` defines `TVM_FFI_EXTRA_CXX_API` macro (equivalent to `TVM_FFI_DLL`).
- `include/tvm/ffi/extra/structural_equal.h` and `structural_hash.h` contain the public API.
- `src/ffi/extra/structural_equal.cc` and `structural_hash.cc` are conditionally compiled.
- `include/tvm/ffi/reflection/access_path.h` and `src/ffi/reflection/access_path.cc` remain in the always-compiled core (access paths are used by the reflection accessor read path, not only by structural comparison).
- Test files in `tests/cpp/extra/` are conditionally included.

## Alternatives Considered
### Keep everything in core
- Pros: Simpler build. No conditional compilation.
- Cons: All consumers pay the cost of structural comparison code. Minimal builds are unnecessarily large. C++ ABI issues affect all consumers.

### Separate shared library (libtvm_ffi_extra.so)
- Pros: Complete isolation. Can be loaded on demand.
- Cons: Additional shared library to distribute and manage. Cross-DSO function calls add overhead. Complicates packaging.

### Header-only implementation
- Pros: No link-time dependency. Consumer opts in by including the header.
- Cons: Structural equal/hash implementations are complex (~500+ lines) and would significantly increase compile time for every TU that includes them. Templates would need to be instantiated in every TU.

## Why This Option Won
- The directory + CMake flag approach gives fine-grained control with minimal complexity. The source files are either compiled or not; no runtime overhead.
- Keeping `access_path.cc` in core ensures that reflection accessors (which use `AccessPath` for field traversal error reporting) work without the extra flag.
- The `TVM_FFI_EXTRA_CXX_API` macro explicitly documents the ABI stability boundary: these APIs use C++ linkage and may not work across compiler boundaries, unlike the core C ABI.

## Consequences
### Positive
- Minimal builds exclude ~1500 lines of structural comparison code.
- Clear layering: adding a new "extra" feature follows the established pattern.
- The `TVM_FFI_EXTRA_CXX_API` macro signals to developers which APIs have weaker ABI guarantees.

### Negative
- Conditional compilation adds complexity to `CMakeLists.txt`.
- Consumers must check `TVM_FFI_USE_EXTRA_CXX_API` before using structural comparison.
- The same functionality is also accessible through C ABI global functions (`ffi.reflection.GetFirstStructuralMismatch`, `ffi.reflection.StructuralHash`), creating two access paths for the same feature.

### Risks
- Feature fragmentation: if too many APIs move to `extra/`, it becomes unclear what is "core." Mitigated by the stated principle: "minimize the number of extra C++ APIs."
- Build configuration drift: downstream projects may assume `extra/` is always available. Mitigated by the default ON setting.

## Implementation Notes
- `TVM_FFI_USE_EXTRA_CXX_API` defaults to `ON` in `CMakeLists.txt`.
- Source files are added conditionally: `if(TVM_FFI_USE_EXTRA_CXX_API)` guards the list.
- Test files are in `tests/cpp/extra/` and similarly gated.
- Include path change: `#include <tvm/ffi/reflection/structural_equal.h>` becomes `#include <tvm/ffi/extra/structural_equal.h>`.
- Subsequent commits added more `extra/` content following this pattern: `extra/json.h` (JSON parser/writer), `extra/serialization.h` (object graph serialization), `extra/base64.h` (base64 utilities), `extra/reflection_extra.cc` (AccessStep/AccessPath reflection registration + `MakeObjectFromPackedArgs`), `extra/module.h` and four `library_module*.cc` files (module system with DSOLibrary, SystemLibrary, LibraryModuleObj), `extra/stream_context.cc` (thread-local per-device stream handles), `extra/env_c_api.cc` (host environment C API: signals, GIL, C API registration), `extra/testing.cc` (test utilities). All follow the same `TVM_FFI_USE_EXTRA_CXX_API` gating. `extra/c_env_api.h` serves as the C header for environment and module-scoped C API functions, with a `TVMFFIEnv*` vs. `TVMFFIEnvMod*` naming convention (see [ADR-0013](.memory/ADRs/0013-module-scoped-c-api-naming.md)).

## Validation
- `tests/cpp/extra/test_reflection_structural_equal_hash.cc`: Comprehensive test of all SEqHash kinds and custom dispatch.
- CMake build with `-DTVM_FFI_USE_EXTRA_CXX_API=OFF` verifies the library builds without structural comparison.

## Migration and Rollback
- Include path change from `tvm/ffi/reflection/structural_*.h` to `tvm/ffi/extra/structural_*.h` is a breaking change for downstream C++ code.
- Rollback: revert the move and remove the CMake flag. The code itself is unchanged.

## Related Design Docs
- [.memory/designs/0007-structural-equal-hash-system.md](.memory/designs/0007-structural-equal-hash-system.md)
- [.memory/designs/0008-json-ecosystem.md](.memory/designs/0008-json-ecosystem.md)
- [.memory/designs/0009-module-system.md](.memory/designs/0009-module-system.md)

## Related Diagrams
- [.memory/diagrams/0005-structural-equal-hash-flow.md](.memory/diagrams/0005-structural-equal-hash-flow.md)

## Evidence Matrix
- `TVM_FFI_EXTRA_CXX_API` macro in `extra/base.h` -> `.memory/commits/2025-07-30-3fc0391e29dac100ad37db45348090438e1db739.md` + `3fc0391` + `include/tvm/ffi/extra/base.h`
- `TVM_FFI_USE_EXTRA_CXX_API` CMake option -> `.memory/commits/2025-07-26-2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec.md` + `2ec11f5` + `CMakeLists.txt`
- `access_path.cc` promoted to always-compiled core -> `.memory/commits/2025-07-30-3fc0391e29dac100ad37db45348090438e1db739.md` + `3fc0391`
- `AccessKind` rename (kArrayIndex->kArrayItem, kMapKey->kMapItem) -> `.memory/commits/2025-07-30-3fc0391e29dac100ad37db45348090438e1db739.md` + `3fc0391`
- Initial `TVM_FFI_EXTRA_CXX_API` in `c_api.h` -> `.memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md` + `9445fe7`
- JSON parser/writer in `extra/` -> `.memory/commits/2025-08-04-de541e37ad3820033856cc8a0af55e896af55a3b.md` + `de541e3` + `include/tvm/ffi/extra/json.h`, `src/ffi/extra/json_parser.cc`, `src/ffi/extra/json_writer.cc`
- Object graph serialization in `extra/` -> `.memory/commits/2025-08-05-8eaefe04a044292e071263aca309b6991124c566.md` + `8eaefe0` + `include/tvm/ffi/extra/serialization.h`, `src/ffi/extra/serialization.cc`
- `MakeObjectFromPackedArgs` moved to `extra/reflection_extra.cc` -> `.memory/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md` + `f4ede98`
- FastMath-safe helpers in `extra/` parser/writer -> `.memory/commits/2025-08-15-1a271f00321b8cc16b72e58436716a05e2f62500.md` + `1a271f0`
- Module system in `extra/` (`module.h`, `module.cc`, `library_module.cc`, `library_module_dynamic_lib.cc`, `library_module_system_lib.cc`, `module_internal.h`, `buffer_stream.h`) -> `.memory/commits/2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md` + `538bef4`
- Stream context in `extra/` (`stream_context.cc`) -> `.memory/commits/2025-08-19-0daaffedd23982ea09f8c38fec4eef1cca1d8cac.md` + `0daaffe`
- `EnvCAPIRegistry` moved to `extra/env_c_api.cc` -> `.memory/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md` + `023ea44`
- `testing.cc` moved to `extra/testing.cc` -> `023ea44`
- `c_env_api.h` as home for all environment C APIs -> `538bef4` + `0daaffe` + `023ea44`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Monitor the set of `extra/` APIs; if it grows significantly, consider whether a separate shared library is warranted.
- Document the ABI stability boundary between core and extra APIs in the public documentation.
