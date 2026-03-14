---
scope:
  - "0013-module-system"
  - "0011-extra-api-tier"
---
# Module Placed in Extra API Tier

**TL;DR**: `ModuleObj`/`Module` and the entire library-loading stack (LibraryModuleObj, DSOLibrary, SystemLibrary, ProcessLibraryBin) are placed in the extra API tier (`include/tvm/ffi/extra/`, `src/ffi/extra/`) rather than the core FFI, keeping the core library minimal for consumers that only need packed functions and type-erased values.

## Context

The `Module` concept originated in `runtime::Module` in the main TVM codebase, where it was part of the monolithic runtime. When extracting a standalone FFI library, the question arose: should Module be a core component (always compiled) or an optional component (gated by build option)?

The module system includes substantial infrastructure: an abstract base class, library loading via dlopen, a binary import-tree deserializer, context symbol registration, and system library management. Not all FFI consumers need this -- lightweight inference runtimes that receive pre-loaded functions via the global registry have no use for dynamic module loading.

Usecases:
- Lightweight inference deployment: only needs packed functions, error handling, and containers. Module loading is unnecessary and adds binary size.
- Full compiler stack: needs module loading for kernel library compilation, serialization, and import management.
- Cross-language bindings (Python, Rust): may or may not need module loading depending on use case.

Design Decisions:
- Place `ModuleObj` in `include/tvm/ffi/extra/module.h` with `TVM_FFI_EXTRA_CXX_API` visibility.
- Place all implementation files (`module.cc`, `library_module.cc`, `library_module_dynamic_lib.cc`, `library_module_system_lib.cc`) in `src/ffi/extra/`, gated by `TVM_FFI_USE_EXTRA_CXX_API`.
- Reserve static type index `kTVMFFIModule = 73` in the core `c_api.h` type index enum so that the type index is stable even when the module implementation is not compiled.
- The `c_env_api.h` header (declaring `TVMFFIEnvModLookupFromImports` etc.) is also in the extra tier.

## Implementation Notes

- `ModuleObj` uses `TVM_FFI_EXTRA_CXX_API` visibility for its class, and `TVM_FFI_DECLARE_STATIC_OBJECT_INFO` with the pre-assigned type index.
- The `Library` internal class has no type index at all -- it is never exposed across the FFI boundary and only needs Object ref-counting for lifetime management.
- Four new `.cc` files are added to the `TVM_FFI_USE_EXTRA_CXX_API` gated source list in CMakeLists.txt.
- Evidence: commit `538bef4` (`.knowledge/commits/2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md`)

## Alternatives Considered

1. **Make Module a core component**: Always compiled, no gating needed. But increases the minimal library size (4 new compilation units, dlopen dependency) for consumers that only need packed functions. The core FFI should remain minimal.

2. **Separate CMake target for Module**: Finer control than the extra tier. But adds build system complexity (a third tier). The extra API tier already provides the gating mechanism and the Module is conceptually aligned with other extra-tier components (higher-level convenience features built on core primitives).

3. **Keep Module in upstream TVM only**: Do not extract into the standalone FFI library. But downstream projects that use the FFI library for kernel loading would have to depend on the full TVM runtime or reimplement module loading themselves.

## Consequences

- Consumers that disable `TVM_FFI_USE_EXTRA_CXX_API` get a smaller core library without module-loading symbols.
- The `kTVMFFIModule` type index exists in the core enum regardless, so code that checks type indices can still reference it.
- Any new module-related features (e.g., new loader formats) must be added to the extra tier, not the core.

## Related Design Docs

- [`.knowledge/designs/0013-module-system.md`](../designs/0013-module-system.md) -- Full module system design
- [`.knowledge/designs/0011-extra-api-tier.md`](../designs/0011-extra-api-tier.md) -- Extra API tier design and gating
- [`.knowledge/ADRs/0012-extra-cxx-api-macro.md`](0012-extra-cxx-api-macro.md) -- TVM_FFI_EXTRA_CXX_API macro decision
