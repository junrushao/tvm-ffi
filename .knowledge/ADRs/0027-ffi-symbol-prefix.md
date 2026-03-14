---
scope:
  - "0008-module-export-system"
  - "0013-module-system"
  - "0001-c-abi"
---
# __tvm_ffi_ Symbol Prefix for FFI-Exported DSO Functions

**TL;DR**: All FFI-exported function symbols in shared libraries are prefixed with `__tvm_ffi_` to prevent symbol collisions with non-FFI C functions. Internal infrastructure symbols use `__tvm_ffi__` (double underscore) to partition from user-exported functions.

## Context

Previously, `TVM_FFI_DLL_EXPORT_TYPED_FUNC(Foo, ...)` emitted `Foo` as the raw `extern "C"` symbol. In shared libraries that also contained non-FFI C functions (e.g., CUDA runtime functions, utility functions), the raw symbol name could collide, causing link-time or runtime errors when the wrong function was resolved.

The module system's `LibraryModuleObj::GetFunction` was looking up symbols by raw name via `Library::GetSymbol`, making it impossible to distinguish FFI-exported functions from other symbols in the same library.

## Alternatives

### 1. Global `__tvm_ffi_` prefix for all exported symbols (chosen)

`TVM_FFI_DLL_EXPORT_TYPED_FUNC(Foo, impl)` emits `__tvm_ffi_Foo`. The constant `symbol::tvm_ffi_symbol_prefix = "__tvm_ffi_"` defines the prefix. `Library::GetSymbolWithSymbolPrefix(name)` prepends it automatically.

- Pros: Simple, deterministic, prevents all user-FFI symbol collisions. Callers pass logical names; the prefix is transparent.
- Cons: Breaking ABI change -- all existing compiled `.so`/`.dll` modules must be recompiled. Requires upstream compiler backends (LLVM codegen) to emit prefixed names.

### 2. Per-library unique prefix (e.g., hash-based)

Each library gets a unique prefix derived from its content or name.

- Pros: Prevents collisions even between different FFI libraries loaded simultaneously.
- Cons: Complicates symbol resolution (the loader must know each library's prefix). Breaks the simple `prefix + name` lookup pattern.

### 3. Mangled C++ names (no extern "C")

Use C++ name mangling instead of `extern "C"` symbols.

- Pros: Natural namespacing via C++ namespaces.
- Cons: Name mangling is ABI-dependent (Itanium vs MSVC). Cannot be resolved by `dlsym`. Breaks the C ABI contract.

## Decision

Alternative 1. The prefix convention introduces a two-tier naming system:

- **User-exported functions**: `__tvm_ffi_<name>` (e.g., `__tvm_ffi_main`, `__tvm_ffi_add_one`). Single underscore between prefix and name.
- **Internal infrastructure symbols**: `__tvm_ffi__<name>` (e.g., `__tvm_ffi__library_ctx`, `__tvm_ffi__library_bin`). Double underscore between prefix and sub-name, preventing collision with user functions that happen to be named `library_ctx`.

The `Library` interface gains `GetSymbolWithSymbolPrefix(name)` as a virtual method. The base class default prepends `__tvm_ffi_` and delegates to `GetSymbol`. `SystemLibrary` overrides to handle its own `symbol_prefix_` stacking.

## Consequences

- All shared libraries built with `TVM_FFI_DLL_EXPORT_TYPED_FUNC` emit symbols with the `__tvm_ffi_` prefix. Existing compiled modules are incompatible and must be recompiled.
- Python `Module` now uses logical names (e.g., `"main"`) resolved to `__tvm_ffi_main` via the prefix mechanism.
- The `SystemLibrary` required a follow-up fix (commit `315f4bb` #18298) to handle prefix-tolerant lookups, since registered symbols may already include the prefix.

## Related Design Docs

- [`.knowledge/designs/0008-module-export-system.md`](../designs/0008-module-export-system.md) -- Export macro generates prefixed symbols
- [`.knowledge/designs/0013-module-system.md`](../designs/0013-module-system.md) -- Two-tier symbol resolution, well-known symbol renames
- Commit: `.knowledge/commits/2025-09-06-40e8a519f5270dfb18436b2f26c2d691cf24c9c1.md` + `40e8a51`
- Fix: `.knowledge/commits/2025-09-10-315f4bb00eac8b4d26cdcd6839fb1a077bab6976.md` + `315f4bb`
