---
sha: "023ea448be6e86e09f4ebaba5a235ee53f3cdeef"
date: "2025-08-20T09:57:31-04:00"
author: "Tianqi Chen"
subject: "[FFI][REFACTOR] Cleanup API locations (#18218)"
nature: ["refactor"]
tags: ["api-cleanup", "env-api", "extra-api"]
scope: ["include/tvm/ffi", "src/ffi", "CMakeLists.txt"]
risk: "medium"
---

# 023ea44 — [FFI][REFACTOR] Cleanup API locations (#18218)

## TL;DR
- Reorganizes C API declarations in `c_api.h` by moving sections to their logical order (basic object API first, then function calling API, then DLPack, then dtype, then reflection).
- Extracts `EnvCAPIRegistry` (Python signal/GIL management) from `src/ffi/function.cc` into a new `src/ffi/extra/env_c_api.cc` under `TVM_FFI_USE_EXTRA_CXX_API`.
- Moves `src/ffi/testing.cc` to `src/ffi/extra/testing.cc`.
- Renames `TVMFFIEnvLookupFromImports` → `TVMFFIEnvModLookupFromImports`, `TVMFFIEnvRegisterContextSymbol` → `TVMFFIEnvModRegisterContextSymbol`, `TVMFFIEnvRegisterSystemLibSymbol` → `TVMFFIEnvModRegisterSystemLibSymbol`.
- Moves `TVMFFIEnvCheckSignals` and `TVMFFIEnvRegisterCAPI` from `function.cc` to `env_c_api.cc`; changes `TVMFFIEnvRegisterCAPI` signature from `(const TVMFFIByteArray*, void*)` to `(const char*, void*)`.

## Why (intent / motivation)
- The env API and module-related API were scattered across `function.cc` and the core layer. Moving them to the extra layer keeps the core minimal and enables proper separation of concerns.

## What changed (facts from diff)
- `include/tvm/ffi/c_api.h`: Reordered API sections; no net new declarations (moved from bottom to top and vice versa). Removed `TVMFFIEnvCheckSignals` and `TVMFFIEnvRegisterCAPI` from core header.
- `include/tvm/ffi/extra/c_env_api.h`: Added `TVMFFIEnvCheckSignals` and `TVMFFIEnvRegisterCAPI(const char*, void*)`; renamed `TVMFFIEnvLookupFromImports` → `TVMFFIEnvModLookupFromImports`, etc.
- `src/ffi/extra/env_c_api.cc` (new): `EnvCAPIRegistry` implementation with Python GIL/signal support; `TVMFFIEnvCheckSignals`, `TVMFFIEnvRegisterCAPI` implementations.
- `src/ffi/function.cc`: Removed ~119 lines (EnvCAPIRegistry class + C API implementations).
- `src/ffi/{testing.cc → extra/testing.cc}`: Renamed/moved; added `#include <tvm/ffi/extra/c_env_api.h>`.
- `CMakeLists.txt`: Removed `src/ffi/testing.cc` from core; added `src/ffi/extra/env_c_api.cc` and `src/ffi/extra/testing.cc` to extra sources.

## Public surface changes (if any)
- API: `TVMFFIEnvLookupFromImports` renamed to `TVMFFIEnvModLookupFromImports`; `TVMFFIEnvRegisterContextSymbol` → `TVMFFIEnvModRegisterContextSymbol`; `TVMFFIEnvRegisterSystemLibSymbol` → `TVMFFIEnvModRegisterSystemLibSymbol`. `TVMFFIEnvRegisterCAPI` signature changed (bytearray → char*). These functions now require `TVM_FFI_USE_EXTRA_CXX_API`.
- Flags/config: `testing.cc` is now only included with extra API.
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none (refactor only)
- How to verify manually: Rebuild with and without `TVM_FFI_USE_EXTRA_CXX_API`.
- CI impact: Breaking rename of module-related env API symbols.

## Risk & rollout notes
- Risk level: medium — Renames public C API symbols. Any callee code using the old names must be updated.
- Rollout/migration: Rename call sites: `TVMFFIEnvLookupFromImports` → `TVMFFIEnvModLookupFromImports`, etc.
- Follow-ups: Python bindings need to be updated to use `TVMFFIEnvModLookupFromImports`.

## Evidence
### Changed files
- `CMakeLists.txt` +2/-1 (M)
- `include/tvm/ffi/c_api.h` +179/-192 (M) — reorder sections
- `include/tvm/ffi/extra/c_env_api.h` +20/-5 (M) — renamed symbols + new entries
- `src/ffi/extra/env_c_api.cc` +148/-0 (A)
- `src/ffi/extra/library_module.cc` +1/-1 (M) — rename
- `src/ffi/extra/library_module_system_lib.cc` +1/-1 (M) — rename
- `src/ffi/extra/module.cc` +2/-2 (M) — rename
- `src/ffi/extra/module_internal.h` +1/-1 (M) — comment update
- `src/ffi/{testing.cc → extra/testing.cc}` +1/-0 (R098) — moved + include
- `src/ffi/function.cc` +0/-119 (M) — removed EnvCAPIRegistry

### Notable symbols / endpoints / configs touched
- `TVMFFIEnvModLookupFromImports` (renamed from `TVMFFIEnvLookupFromImports`)
- `TVMFFIEnvModRegisterContextSymbol` (renamed)
- `TVMFFIEnvModRegisterSystemLibSymbol` (renamed)
- `TVMFFIEnvCheckSignals`, `TVMFFIEnvRegisterCAPI` (moved to extra)
- `EnvCAPIRegistry` (moved to `env_c_api.cc`)

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md`
