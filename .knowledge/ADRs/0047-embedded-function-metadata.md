---
scope:
  - "0008-module-export-system"
  - "0023-type-schema-and-stubgen"
---
# Embedded Function Metadata and Documentation Symbols

**TL;DR**: Exported functions optionally carry companion `__tvm_ffi__metadata_<name>` and `__tvm_ffi__doc_<name>` symbols in the shared library, enabling cross-language introspection of function type schemas and documentation without invoking the function itself.

## Context

Compiler integration frameworks (JAX/XLA, MLIR) need to validate function signatures at compile time without executing them. Previously, type information was only available via the in-process global registry, which requires loading the library and calling reflection APIs.

Usecases:
- Ahead-of-time signature validation for compiler frameworks generating calls to FFI functions.
- Documentation generation tools that read function signatures and docstrings directly from shared libraries.
- Python stub generation (`tvm-ffi-stubgen`) consuming metadata from loaded modules.

Design Decisions:
- **Opt-in via compile flag**: `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` (default 0) gates metadata export. When enabled, `TVM_FFI_DLL_EXPORT_TYPED_FUNC` additionally emits a `__tvm_ffi__metadata_<name>` symbol returning JSON `{"type_schema": "<schema>"}` as a `String`.
- **Separate doc macro**: `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC(ExportName, DocString)` emits `__tvm_ffi__doc_<name>` when metadata is enabled. Separation keeps documentation optional and avoids bloating the binary when docs are not needed.
- **Main-lib allocation**: Metadata strings are allocated via `TVMFFIStringFromByteArray` (going through libtvm_ffi) rather than from the loaded module's allocator, preventing use-after-free if the module is unloaded while strings are still referenced.
- **Companion symbol convention**: `__tvm_ffi__metadata_` and `__tvm_ffi__doc_` extend the existing `__tvm_ffi_` prefix convention from [ADR 0027](0027-ffi-symbol-prefix.md).

Alternatives considered:
- **Embed metadata in ELF sections**: Would avoid extra symbols but is platform-specific and harder to query programmatically.
- **Always emit metadata**: Simpler but increases binary size for production deployments that do not need introspection.

## Implementation Notes

- `TVM_FFI_DLL_EXPORT_TYPED_FUNC` was split into `TVM_FFI_DLL_EXPORT_TYPED_FUNC_IMPL_` (core wrapper) and the public macro (which conditionally adds metadata).
- Python `Module.get_function_metadata(name)` and `Module.get_function_doc(name)` query these symbols via the `LibraryModuleObj` interface.
- Metadata strings were initially allocated in-module; commit `dcacb98` switched to `TVMFFIStringFromByteArray` for main-lib allocation to prevent use-after-unload.

## Related Design Docs

- [`.knowledge/designs/0008-module-export-system.md`](../designs/0008-module-export-system.md)
- [`.knowledge/designs/0023-type-schema-and-stubgen.md`](../designs/0023-type-schema-and-stubgen.md)
- [`.knowledge/ADRs/0027-ffi-symbol-prefix.md`](0027-ffi-symbol-prefix.md)
- Evidence: `.knowledge/commits/2025-11-20-ac7bf68058b392c3a8475619016fde48bd08334b.md` + `ac7bf68`
- Evidence: `.knowledge/commits/2025-12-02-dcacb98d189241d52ef51c1d63fb0e9f6c98a4b0.md` + `dcacb98`
