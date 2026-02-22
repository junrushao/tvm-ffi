---
sha: "cdc1ccca64bf6fda32da0be266cc727e0c3bcb34"
date: "2025-10-08T09:55:14-07:00"
author: "Junru Shao"
subject: "chore: Clean up libbacktrace-related outputs (#92)"
nature: ["build"]
tags: ["chore"]
scope: ["cmake", "CMakeLists.txt"]
risk: "low"
---

# cdc1ccc — chore: Clean up libbacktrace-related outputs (#92)

## TL;DR
- Suppresses verbose libbacktrace build output by enabling `LOG_CONFIGURE`, `LOG_INSTALL`, `LOG_BUILD`, and `LOG_OUTPUT_ON_FAILURE` in `ExternalProject_Add`.
- Replaces the broken `--host=${MACHINE_NAME}` flag (undefined CMake variable) with proper auto-detected target triple via a new `DetectTargetTriple.cmake` utility.
- Adds `cmake/Utils/DetectTargetTriple.cmake` (303 lines) that detects target triples across many platforms and toolchains.

## Why (intent / motivation)
- Libbacktrace building was emitting excessive output that was neither informative nor readable.
- The `MACHINE_NAME` variable was never defined, making the `--host` cross-compile flag a no-op; proper detection is needed for cross-compilation scenarios (Android, iOS, MinGW, MSVC, etc.).

## What changed (facts from diff)
- `CMakeLists.txt`: includes `DetectTargetTriple.cmake` early; removes stray `BUILD_COMMAND make` duplication.
- `cmake/Utils/AddLibbacktrace.cmake`: uses `detect_target_triple(TVM_FFI_MACHINE_NAME)` for the `--host` flag; adds `LOG_*` directives; removes erroneous status message.
- `cmake/Utils/DetectTargetTriple.cmake` (new): multi-stage detection via compiler `-dumpmachine`, platform variables, and fallback synthesis for Emscripten, Android, iOS, Windows MSVC/MinGW, macOS, Linux.

## Public surface changes (if any)
- API: none
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none
- How to verify manually: Build with `cmake . -B build_cpp -DTVM_FFI_USE_LIBBACKTRACE=ON`; verify output is minimal and `--host` is correctly set.
- CI impact: none

## Risk & rollout notes
- Risk level: low — build system change; behavior unchanged at runtime
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `CMakeLists.txt` +2/-0 (modified)
- `cmake/Utils/AddLibbacktrace.cmake` +17/-7 (modified)
- `cmake/Utils/DetectTargetTriple.cmake` +303/-0 (added)

### Notable symbols / endpoints / configs touched
- `detect_target_triple()` function in `DetectTargetTriple.cmake`
- `TVM_FFI_MACHINE_NAME` CMake variable

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/cdc1ccca64bf6fda32da0be266cc727e0c3bcb34.md`
