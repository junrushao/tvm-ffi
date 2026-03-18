---
scope:
  - "0011-module-system"
  - "0004-function-system"
---
# FFI Symbol Prefix Convention for DSO-Exported Functions

**TL;DR**: All FFI-exported DSO symbols are mandated to carry the `__tvm_ffi_` prefix, with a two-tier naming scheme (single underscore for user functions, double underscore for internal symbols) to prevent namespace collisions.

## Context
When a shared library exports functions via `TVM_FFI_DLL_EXPORT_TYPED_FUNC(Name, Func)`, the resulting C symbol name could collide with non-FFI functions in the same library or system namespace. For example, exporting `add_one` would create a C symbol `add_one`, which conflicts with any other `add_one` function linked into the same process. Additionally, internal module symbols (`library_ctx`, `library_bin`, `metadata_`) could collide with user-defined FFI function names.

Usecases:
- User exports `add_one` and `library_ctx` in the same library without collision
- System library aggregates symbols from multiple independently compiled modules without name conflicts
- Generated code safely uses `__tvm_ffi_` prefix as a well-known convention for symbol discovery

Design Decisions:
- **All FFI-exported DSO symbols must start with `__tvm_ffi_`**. The macro `TVM_FFI_DLL_EXPORT_TYPED_FUNC(Name, Func)` now emits `__tvm_ffi_Name` instead of raw `Name`.
- **Two-tier naming scheme**: User FFI functions use single underscore separator (`__tvm_ffi_<name>`), while internal/special symbols use double underscore (`__tvm_ffi__<name>`). This prevents a user function named `library_ctx` from colliding with the internal `__tvm_ffi__library_ctx` symbol.
- **`Library::GetSymbolWithSymbolPrefix(name)`** transparently prepends `__tvm_ffi_` during function lookup. Callers use logical names (e.g., `"main"`) without knowing the mangled symbol name. `SystemLibrary` overrides this to compose `system_prefix + ffi_prefix + name`.
- **Alternatives rejected**:
  - *No prefix (status quo before this decision)*: Allowed symbol collisions, especially in system library scenarios where multiple modules contribute to the same symbol table.
  - *Library-scoped prefix (e.g., `__mylib_Name`)*: Would prevent cross-library interop since the prefix is not known at lookup time. The universal `__tvm_ffi_` prefix enables uniform lookup.

## Implementation Notes
- `symbol::tvm_ffi_symbol_prefix = "__tvm_ffi_"` is the canonical prefix constant
- Internal symbols: `tvm_ffi_library_ctx = "__tvm_ffi__library_ctx"`, `tvm_ffi_library_bin = "__tvm_ffi__library_bin"`, `tvm_ffi_metadata_prefix = "__tvm_ffi__metadata_"`, `tvm_ffi_doc_prefix = "__tvm_ffi__doc_"` (ac7bf68), `tvm_ffi_main = "__tvm_ffi_main"`
- CUBIN embedding symbols: `__tvm_ffi__cubin_<name>` / `__tvm_ffi__cubin_<name>_end` for embedded CUBIN data (d49effd). Follows double-underscore internal namespace convention
- ABI-breaking: all pre-compiled `.so` libraries must be recompiled after this change
- Python `Module.entry_name` changes from `"__tvm_ffi_main__"` to `"main"` (prefix applied at C++ layer)

## Related Design Docs
- [0011-module-system.md](../designs/0011-module-system.md) -- Symbol naming conventions, Library class
- [0004-function-system.md](../designs/0004-function-system.md) -- `TVM_FFI_DLL_EXPORT_TYPED_FUNC` macro

### Evidence
- `commits/2025-09-06-40e8a519f5270dfb18436b2f26c2d691cf24c9c1.md` (40e8a51)
