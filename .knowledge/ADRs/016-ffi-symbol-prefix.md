---
scope:
  - ".knowledge/designs/0013-module-system.md"
  - ".knowledge/designs/function-system.md"
  - ".knowledge/designs/c-abi.md"
---
# ADR-016: __tvm_ffi_ Symbol Prefix for DLL-Exported Functions

**TL;DR**:
- All FFI-convention functions exported from shared libraries now carry the `__tvm_ffi_` prefix in their C symbol names. `TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, Func)` emits `__tvm_ffi_##ExportName` instead of `ExportName`.
- Internal/special symbols use double underscore after the prefix (`__tvm_ffi__library_ctx`) while user functions use single underscore (`__tvm_ffi_main`), creating a two-tier namespace that prevents collisions.
- `Library::GetSymbolWithSymbolPrefix` is the new virtual method for resolving FFI function symbols with the prefix applied transparently.

## Context

When loading shared libraries via the module system, the FFI needs to distinguish its own exported functions (which follow `TVMFFISafeCallType` calling convention) from arbitrary non-FFI symbols in the same DSO. Without a naming prefix, a user function named `library_ctx` would collide with the FFI's internal `__tvm_ffi_library_ctx` context pointer symbol.

The same problem exists for `SystemLibrary`, which stores symbols from potentially multiple libraries in a single global registry. Without prefixed names, function name collisions between different libraries are likely.

## Decision

Prefix all user-facing FFI function symbols with `__tvm_ffi_`:
- `TVM_FFI_DLL_EXPORT_TYPED_FUNC(AddOne, AddOne_)` emits `extern "C" int __tvm_ffi_AddOne(...)` instead of `extern "C" int AddOne(...)`
- Internal symbols use double underscore after prefix: `__tvm_ffi__library_ctx`, `__tvm_ffi__library_bin`, `__tvm_ffi__metadata_`
- User symbols use single underscore: `__tvm_ffi_main`, `__tvm_ffi_AddOne`

The lookup layer (`Library::GetSymbolWithSymbolPrefix`) prepends the prefix transparently, so callers use logical names (e.g., `"main"`, `"AddOne"`) and the prefix is applied internally.

## Alternatives

### Alternative A: No prefix (status quo before this change)
- Description: Export functions with their bare names.
- Pros: Simpler; no lookup indirection.
- Cons: Symbol collisions possible between FFI functions and non-FFI symbols in the same DSO. Internal symbols (`library_ctx`, `library_bin`) could collide with user function names.
- Why rejected: Collision risk is unacceptable for a general-purpose module system.

### Alternative B: Per-library unique prefix
- Description: Each library gets a unique prefix (e.g., from library name hash).
- Pros: Zero collision risk even between different FFI libraries.
- Cons: Prefix must be communicated between compile-time and load-time; adds complexity to the build system; makes static library registration harder.
- Why rejected: The global `__tvm_ffi_` prefix is sufficient for the collision prevention goal. Per-library uniqueness is not needed because the module system already uses separate symbol tables (DSOLibrary has its own `dlopen` handle).

### Alternative C: C++ name mangling
- Description: Use C++ mangled names instead of `extern "C"`.
- Pros: Automatic uniqueness via full signature encoding.
- Cons: Not C-compatible; cannot be used from C, Rust, or other non-C++ languages; not portable across compilers.
- Why rejected: The FFI is explicitly designed for C ABI compatibility.

## Implementation Notes
- The prefix constant is `ffi::symbol::tvm_ffi_symbol_prefix = "__tvm_ffi_"` in `include/tvm/ffi/extra/module.h`.
- `Library::GetSymbolWithSymbolPrefix(name)` is a new virtual method that prepends the prefix and delegates to `GetSymbol`.
- `SystemLibrary` overrides `GetSymbolWithSymbolPrefix` to handle its own `symbol_prefix_` layered on top, with fallback to unprefixed lookup (added in 315f4bb to handle double-prefix edge cases).
- Python `Module.entry_name` changed from `"__tvm_ffi_main__"` to `"main"` because the prefix is now applied by the lookup layer.
- Commit 40e8a51 introduced the convention; commit 315f4bb fixed SystemLibrary fallback.

## Related Design Docs
- `.knowledge/designs/0013-module-system.md` -- Library, SystemLibrary, symbol constants
- `.knowledge/designs/function-system.md` -- `TVM_FFI_DLL_EXPORT_TYPED_FUNC` macro
- `.knowledge/designs/c-abi.md` -- `TVM_FFI_DLL_EXPORT`, `TVMFFISafeCallType`
