---
adr: "0013"
title: "Module-Scoped C API Naming Convention (TVMFFIEnvMod* Prefix)"
status: "accepted"
date: "2025-08-20"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "c-api"
  - "naming"
source_commits:
  - "023ea448be6e86e09f4ebaba5a235ee53f3cdeef"
source_ledgers:
  - ".memory/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md"
---

# ADR-0013: Module-Scoped C API Naming Convention (TVMFFIEnvMod* Prefix)

## TL;DR
- C ABI functions that operate in module-scoped context (import lookup, context symbol registration, system library symbol registration) use the `TVMFFIEnvMod*` prefix, distinguishing them from host-environment-scoped functions (`TVMFFIEnv*`).
- Three symbols were renamed: `TVMFFIEnvLookupFromImports` -> `TVMFFIEnvModLookupFromImports`, `TVMFFIEnvRegisterContextSymbol` -> `TVMFFIEnvModRegisterContextSymbol`, `TVMFFIEnvRegisterSystemLibSymbol` -> `TVMFFIEnvModRegisterSystemLibSymbol`.

## Status
Accepted

## Context
When the module system was introduced (commit `538bef4`), three C ABI functions were added to `extra/c_env_api.h` with the generic `TVMFFIEnv*` prefix: `TVMFFIEnvLookupFromImports`, `TVMFFIEnvRegisterContextSymbol`, and `TVMFFIEnvRegisterSystemLibSymbol`. However, these functions operate specifically in the context of the module system (looking up functions from module imports, registering symbols into the module loading context), not in the host environment context (Python signal checking, GIL management, C API registration).

The same `TVMFFIEnv*` prefix was used for both categories, creating ambiguity about whether a function is a module-scoped operation or a host-environment operation.

## Decision Drivers
- Naming clarity: C ABI symbol names should convey their scope and purpose without requiring documentation lookup.
- Taxonomy consistency: Host-environment operations (signals, GIL, C API registration) should be visually distinguishable from module-scoped operations (import lookup, symbol registration).
- Forward compatibility: As more C ABI functions are added, a clear naming scheme prevents future ambiguity.

## Decision
Insert a `Mod` infix between `TVMFFIEnv` and the operation name for all C ABI functions that operate in the module context:

| Before | After |
|--------|-------|
| `TVMFFIEnvLookupFromImports` | `TVMFFIEnvModLookupFromImports` |
| `TVMFFIEnvRegisterContextSymbol` | `TVMFFIEnvModRegisterContextSymbol` |
| `TVMFFIEnvRegisterSystemLibSymbol` | `TVMFFIEnvModRegisterSystemLibSymbol` |

Host-environment functions retain the `TVMFFIEnv*` prefix without the `Mod` infix:
- `TVMFFIEnvCheckSignals` (host environment: Python signal checking)
- `TVMFFIEnvRegisterCAPI` (host environment: C API registration from Python)
- `TVMFFIEnvSetStream` / `TVMFFIEnvGetStream` (host environment: stream context)

## Alternatives Considered
### Keep flat TVMFFIEnv* prefix for all
- Pros: Simpler. No migration.
- Cons: Ambiguous. Module-scoped and host-environment operations are indistinguishable by name alone. As the C API grows, the flat namespace becomes increasingly confusing.

### Use TVMFFIMod* as a separate top-level prefix
- Pros: Even clearer separation.
- Cons: Inconsistent with the established `TVMFFIEnv*` pattern for environment-adjacent APIs. The module APIs are still "environment" APIs in the sense that they are called by generated code running in the environment.

### Use TVMFFIModule* prefix
- Pros: Fully explicit.
- Cons: Verbose. Collides conceptually with `TVMFFIModuleLoadFromFile` which is a user-facing module API, not a callee-side environment API.

## Why This Option Won
- The `TVMFFIEnvMod*` infix preserves the `Env` namespace (these are still environment APIs called by generated code) while adding a clear module-scope qualifier.
- Minimal naming change: just inserting `Mod` after `Env`.
- Consistent with the two-level taxonomy: `TVMFFIEnv*` (host environment) vs. `TVMFFIEnvMod*` (module environment).

## Consequences
### Positive
- Clear naming taxonomy visible at the C ABI level.
- Future module-scoped C API functions have an established naming pattern.
- Host-environment vs. module-environment distinction is immediately apparent from function names.

### Negative
- Breaking change for C ABI consumers that call the three renamed functions.
- Foreign language bindings (Python Cython, Rust) must update their symbol references.

### Risks
- If the `TVMFFIEnv` prefix accumulates too many sub-scopes (e.g., `TVMFFIEnvMod*`, `TVMFFIEnvStream*`, `TVMFFIEnvAlloc*`), the naming scheme becomes complex. Mitigated by the fact that only module-scoped operations needed disambiguation; stream and allocation APIs remain flat `TVMFFIEnv*`.

## Implementation Notes
- The rename was applied in commit `023ea44` across: `include/tvm/ffi/extra/c_env_api.h`, `src/ffi/extra/module.cc`, `src/ffi/extra/library_module.cc`, `src/ffi/extra/library_module_system_lib.cc`, `src/ffi/extra/module_internal.h`.
- In the same commit, `TVMFFIEnvRegisterCAPI` parameter type changed from `const TVMFFIByteArray*` to `const char*` for simplicity.

## Validation
- All in-tree call sites (C++ source files in `src/ffi/extra/`) were updated to use the new names.
- The project builds and tests pass with the renamed symbols.

## Migration and Rollback
- Foreign language bindings must update from the old symbol names to the new ones.
- Rollback: revert the rename in the header and source files.

## Related Design Docs
- [.memory/designs/0009-module-system.md](.memory/designs/0009-module-system.md)
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)

## Related Diagrams
None

## Evidence Matrix
- `TVMFFIEnvLookupFromImports` -> `TVMFFIEnvModLookupFromImports` -> `.memory/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md` + `023ea44` + `include/tvm/ffi/extra/c_env_api.h` line 130
- `TVMFFIEnvRegisterContextSymbol` -> `TVMFFIEnvModRegisterContextSymbol` -> `023ea44` + `include/tvm/ffi/extra/c_env_api.h` line 143
- `TVMFFIEnvRegisterSystemLibSymbol` -> `TVMFFIEnvModRegisterSystemLibSymbol` -> `023ea44` + `include/tvm/ffi/extra/c_env_api.h` line 152
- `TVMFFIEnvRegisterCAPI` parameter type change (`const TVMFFIByteArray*` -> `const char*`) -> `023ea44` + `include/tvm/ffi/extra/c_env_api.h` line 114
- `EnvCAPIRegistry` moved from `src/ffi/function.cc` to `src/ffi/extra/env_c_api.cc` -> `023ea44` + `src/ffi/extra/env_c_api.cc` (148 lines)
- `TVMFFIEnvCheckSignals` and `TVMFFIEnvRegisterCAPI` removed from `c_api.h`, added to `extra/c_env_api.h` -> `023ea44` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/extra/c_env_api.h`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Update Python Cython bindings to use the renamed symbols.
- Update Rust `tvm-ffi-sys` bindings to reference the new symbol names.
