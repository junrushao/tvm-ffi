---
scope:
  - "0001-c-abi"
  - "0013-module-system"
---
# TVMFFIEnvMod* Naming Convention for Module-Scoped C APIs

**TL;DR**: C API functions that operate in the context of a loaded module (callee-side operations called by generated kernel code) use the `TVMFFIEnvMod*` prefix, distinguishing them from general host-environment operations that use the flat `TVMFFIEnv*` prefix.

## Context

When the module system was first formalized (commit `538bef4`), three C API functions were introduced with the `TVMFFIEnv*` prefix:
- `TVMFFIEnvLookupFromImports` -- resolve a function from a module's import tree
- `TVMFFIEnvRegisterContextSymbol` -- register a context symbol for library init
- `TVMFFIEnvRegisterSystemLibSymbol` -- register a symbol in the system library

These names were ambiguous: the `TVMFFIEnv*` prefix was already used for general host-environment operations (`TVMFFIEnvCheckSignals`, `TVMFFIEnvRegisterCAPI`) that have nothing to do with modules. A developer encountering `TVMFFIEnvLookupFromImports` could not tell from the name alone whether it operated on a module context or the global environment.

Usecases:
- Generated kernel code calling `TVMFFIEnvModLookupFromImports(library_ctx, name, &out)` to resolve imported functions at runtime. The `Mod` infix makes it clear this requires a module context handle.
- Library init code calling `TVMFFIEnvModRegisterContextSymbol(name, symbol)` to register symbols. The `Mod` infix signals this is module-system infrastructure, not general environment setup.

Design Decisions:
- Rename all three module-scoped C API symbols to include a `Mod` infix:
  - `TVMFFIEnvLookupFromImports` -> `TVMFFIEnvModLookupFromImports`
  - `TVMFFIEnvRegisterContextSymbol` -> `TVMFFIEnvModRegisterContextSymbol`
  - `TVMFFIEnvRegisterSystemLibSymbol` -> `TVMFFIEnvModRegisterSystemLibSymbol`
- Future module-scoped C API functions should follow the `TVMFFIEnvMod*` pattern.
- General environment operations (signal checking, C API registration) retain the flat `TVMFFIEnv*` prefix.

## Implementation Notes

- This is a **breaking change** for callers of the renamed symbols. Internal callers (Cython bindings, module implementations) were updated in the same commit.
- The rename was performed alongside a broader C API reorganization that also moved `TVMFFIEnvCheckSignals` and `TVMFFIEnvRegisterCAPI` from `c_api.h` to the extra-tier `c_env_api.h`.
- `TVMFFIEnvRegisterCAPI` also had its signature changed: `const TVMFFIByteArray*` -> `const char*` for the name parameter.
- Evidence: commit `023ea44` (`.knowledge/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md`)

## Alternatives Considered

1. **Use a separate `TVMFFIMod*` prefix**: Clearer separation from `TVMFFIEnv*`, but these functions are still "environment" APIs from the callee perspective (they query the host environment on behalf of a loaded module). The `Env` part indicates they are environment-facing.

2. **Keep the flat `TVMFFIEnv*` naming**: Simpler, no rename needed. But conflates module-scoped operations with global-scoped operations, making the API surface harder to understand as it grows.

3. **Use namespaced headers instead of naming convention**: Split into separate header files per category. But C does not have namespaces, so the naming convention is the standard approach for C API symbol disambiguation.

## Consequences

- The `c_env_api.h` header now has clear visual grouping: stream context APIs (`TVMFFIEnv*`), general env APIs (`TVMFFIEnv*`), and module-scoped APIs (`TVMFFIEnvMod*`).
- Downstream callers of the old symbol names must update. This affects generated kernel code and any library that calls these functions directly.
- Future module-scoped C APIs have a clear naming pattern to follow.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI naming conventions
- [`.knowledge/designs/0013-module-system.md`](../designs/0013-module-system.md) -- Module system design
