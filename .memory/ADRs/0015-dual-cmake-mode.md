---
adr: "0015"
title: "Dual CMake Mode: Root Project vs Subproject"
status: "accepted"
date: "2025-08-24"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "Downstream C++ project authors"
tags:
  - "architecture"
  - "build-system"
  - "cmake"
source_commits:
  - "2d41a5115f6a91e2781012a3379f9626bc9e18a1"
source_ledgers:
  - ".memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md"
---

# ADR-0015: Dual CMake Mode: Root Project vs Subproject

## TL;DR
- The CMakeLists.txt is split into two sections: an unconditional section (always executed) that defines library targets (`tvm_ffi_header`, `tvm_ffi_objs`, `tvm_ffi_shared`, `tvm_ffi_static`), and a conditional section (only when root project) that adds tests, Python module build, install targets, and debug options.
- The guard `if (NOT ${PROJECT_NAME} STREQUAL ${CMAKE_PROJECT_NAME}) return() endif()` cleanly separates the two modes, with an early return when used as subproject.

## Status
Accepted

## Context
TVM FFI serves two use cases for C++ consumers: (1) as a pip-installable Python package where downstream CMake projects use `find_package(tvm_ffi CONFIG)` to discover pre-built libraries, and (2) as a CMake subproject included via `add_subdirectory()` in larger builds (e.g., the main TVM compiler). These two modes have conflicting requirements: the root project mode needs install rules, Python module compilation, and test targets, while the subproject mode must only provide library targets without polluting the parent build with tests, install rules, or Python-specific options.

## Decision Drivers
- Subproject consumers (e.g., main TVM compiler) should get minimal, predictable targets without side effects (no tests, no install rules, no Python module build).
- Root project consumers (Python package build via scikit-build-core) need the full build: library + Cython module + install targets.
- CMake function names must be namespaced to avoid collisions when used as a subproject.
- The split must be simple and maintainable -- a single guard point, not scattered conditionals.

## Decision
Split the CMakeLists.txt at a single guard:

```cmake
if (NOT ${PROJECT_NAME} STREQUAL ${CMAKE_PROJECT_NAME})
  return()
endif()
```

**Unconditional section** (always executed, both modes):
- `tvm_ffi_header` (INTERFACE library with include paths)
- `tvm_ffi_objs` (OBJECT library with all C++ sources)
- `tvm_ffi_shared` and `tvm_ffi_static` (via `tvm_ffi_add_target_from_obj`)
- libbacktrace linking
- MSVC flags and debug symbol options

**Root-project-only section** (after guard):
- `TVM_FFI_ATTACH_DEBUG_SYMBOLS`, `TVM_FFI_BUILD_TESTS` options
- CxxWarning and Sanitizer includes
- `tvm_ffi_add_prefix_map` for traceback path remapping
- GoogleTest-based test targets (conditional on `TVM_FFI_BUILD_TESTS`)
- Python/Cython module build (conditional on `TVM_FFI_BUILD_PYTHON_MODULE`)
- Install rules for shared library, headers, CMake config

All CMake utility functions use `tvm_ffi_` prefix (`tvm_ffi_add_target_from_obj`, `tvm_ffi_add_prefix_map`, `tvm_ffi_add_msvc_flags`, `tvm_ffi_add_apple_dsymutil`) to avoid namespace collisions.

## Alternatives Considered
### Separate CMakeLists.txt files
- Pros: Complete isolation, no guard needed.
- Cons: Duplicated target definitions, harder to keep in sync. Source lists, compiler options, and library dependencies would need to be maintained in two places.

### CMake option (`TVM_FFI_AS_SUBPROJECT`)
- Pros: Explicit, discoverable.
- Cons: Requires parent builds to set the option. The `PROJECT_NAME != CMAKE_PROJECT_NAME` pattern is a well-known CMake idiom that works automatically.

### FetchContent-only (no add_subdirectory)
- Pros: Modern CMake pattern, clear dependency boundaries.
- Cons: Forces all consumers to use FetchContent. Some projects (like the main TVM compiler) need the flexibility of add_subdirectory for tighter integration.

## Why This Option Won
- **Automatic detection**: The `PROJECT_NAME != CMAKE_PROJECT_NAME` guard requires zero configuration from subproject consumers. It just works.
- **Single source of truth**: All targets are defined once. The guard only controls what additional targets and options are added.
- **Well-known pattern**: This is a standard CMake idiom used by projects like Google Test, nlohmann/json, and fmt.
- **Namespace safety**: The `tvm_ffi_` prefix on utility functions prevents collisions without requiring CMake namespaces.

## Consequences
### Positive
- Subproject inclusion is zero-configuration: `add_subdirectory(ffi)` gets library targets.
- Root project build gets full functionality (tests, Python module, install).
- CMake function names cannot collide with parent project functions.

### Negative
- The `return()` statement at the guard point means the rest of the file is unreachable in subproject mode. This is intentional but can be surprising to CMake newcomers.
- Options like `TVM_FFI_BUILD_TESTS` are invisible in subproject mode (they are defined after the guard).

### Risks
- If a subproject consumer needs test targets, they must build tvm_ffi as a root project separately. Mitigation: this is by design -- test targets should not pollute parent builds.
- The `PROJECT_NAME` guard breaks if the parent project accidentally uses `project(tvm_ffi ...)` as its own project name. Mitigation: this would be a naming conflict that should be resolved at the parent level.

## Implementation Notes
- `cmake/Utils/Library.cmake`: All functions use `tvm_ffi_` prefix. `tvm_ffi_add_target_from_obj(tvm_ffi tvm_ffi_objs)` creates `tvm_ffi_static` and `tvm_ffi_shared` from the object library. Output goes to `${CMAKE_BINARY_DIR}/lib/`.
- `cmake/tvm_ffi-config.cmake`: Used by downstream projects after `find_package(tvm_ffi CONFIG)`. Creates `tvm_ffi::header` and `tvm_ffi::shared` imported targets by querying paths from `python -m tvm_ffi.config`.
- The Cython module (`TVM_FFI_BUILD_PYTHON_MODULE`) uses `Python_add_library` with optional SABI support and links against `tvm_ffi_objs` directly.

## Validation
- `cmake . -B build_sub -DCMAKE_BUILD_TYPE=Debug` from a parent project that includes tvm_ffi via `add_subdirectory()` should only define `tvm_ffi_header`, `tvm_ffi_objs`, `tvm_ffi_shared`, `tvm_ffi_static` targets.
- `cmake . -B build_root -DTVM_FFI_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Debug` from the tvm_ffi root should additionally define test targets.
- `cmake . -B build -DTVM_FFI_BUILD_PYTHON_MODULE=ON` should build the Cython extension.

## Migration and Rollback
- Rollback: Remove the `return()` guard and wrap root-only sections in `if(PROJECT_IS_TOP_LEVEL)` (CMake 3.21+ variable). Functionally equivalent but requires newer CMake.
- Migration for existing consumers: no changes needed -- `add_subdirectory()` continues to work, and root builds gain new options.

## Related Design Docs
- [.memory/designs/0010-python-packaging-architecture.md](.memory/designs/0010-python-packaging-architecture.md)

## Related Diagrams
- [.memory/diagrams/0008-python-package-architecture.md](.memory/diagrams/0008-python-package-architecture.md)

## Evidence Matrix
- Guard pattern -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `CMakeLists.txt` (`if (NOT ${PROJECT_NAME} STREQUAL ${CMAKE_PROJECT_NAME}) return() endif()`)
- `tvm_ffi_` prefix on functions -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `cmake/Utils/Library.cmake`
- Python module build section -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `CMakeLists.txt` (TVM_FFI_BUILD_PYTHON_MODULE section)
- `tvm_ffi-config.cmake` -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `cmake/tvm_ffi-config.cmake`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Consider switching to `PROJECT_IS_TOP_LEVEL` variable when minimum CMake version is raised to 3.21+.
- Document the subproject integration pattern in developer docs.
