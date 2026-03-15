---
scope: "module-system"
status: "active"
last_updated_commit: "f255650b8e5121452dd60805b206a0cb5bcb6525"
related_designs:
  - ".knowledge/designs/0013-module-system.md"
related_adrs:
  - ".knowledge/ADRs/011-module-loader-dispatch.md"
---
# API Index: Module System

**Scope**: Module loading, function lookup, import management, binary serialization, system library
**Design docs**: `.knowledge/designs/0013-module-system.md`
**ADRs**: `.knowledge/ADRs/011-module-loader-dispatch.md`

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFIEnvModLookupFromImports` | `int TVMFFIEnvModLookupFromImports(TVMFFIObjectHandle library_ctx, const char* func_name, TVMFFIObjectHandle* out)` | Look up function from module's imports; mutex-protected caching; falls back to global registry |
| `TVMFFIEnvModRegisterContextSymbol` | `int TVMFFIEnvModRegisterContextSymbol(const char* name, void* symbol)` | Register a context symbol for lazy init on library load |
| `TVMFFIEnvModRegisterSystemLibSymbol` | `int TVMFFIEnvModRegisterSystemLibSymbol(const char* name, void* symbol)` | Register a symbol in the system library symbol table |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `ModuleObj` | class (abstract) | `virtual kind() -> const char*`, `virtual GetFunction(String) -> Optional<Function>`, `virtual GetPropertyMask() -> int`, `virtual ImportModule(Module)`, `imports_: Array<Any>`, `import_lookup_cache_: Map<String,Function>` | Abstract base for all module types; static type index 73 |
| `Module` | class (ref) | `LoadFromFile(String) -> Module`, `VisitContextSymbols(callback)`, `enum ModulePropertyMask {kBinarySerializable=1, kRunnable=2, kCompilationExportable=4}` | Ref wrapper for `ModuleObj`; non-nullable, mutable |
| `Library` | class (abstract, internal) | `virtual GetSymbol(const String&) -> void*`, `virtual GetSymbolWithSymbolPrefix(const String&) -> void*` | Internal symbol lookup abstraction; no type_key. `GetSymbolWithSymbolPrefix` prepends `__tvm_ffi_` prefix (added in 40e8a51) |
| `LibraryModuleObj` | class (final, internal) | `kind() -> "library"`, `GetPropertyMask() -> kBinarySerializable|kRunnable`, `lib_: ObjectPtr<Library>` | Wraps a Library; wraps TVMFFISafeCallType symbols into Function closures |
| `DSOLibrary` | class (final, internal) | `GetSymbol(name) -> void*`, `Load(name)`, `Unload()` | Platform-specific dlopen/LoadLibraryW wrapper |
| `SystemLibrary` | class (final, internal) | `GetSymbol(name) -> void*`, `symbol_prefix_: String` | Delegates to SystemLibSymbolRegistry; supports prefix matching |
| `SystemLibSymbolRegistry` | class (internal) | `RegisterSymbol(name, ptr)`, `GetSymbol(name) -> void*` | Global singleton `Map<String, void*>` symbol table |
| `SystemLibModuleRegistry` | class (internal) | `GetOrCreateModule(prefix) -> Module` | Ensures at most one Module per symbol prefix |
| `ContextSymbolRegistry` | class (internal) | `Register(name, symbol)`, `InitContextSymbols(lib)`, `VisitContextSymbols(callback)` | Patches context function pointers into loaded libraries |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `CreateLibraryModule` | `Module CreateLibraryModule(ObjectPtr<Library> lib)` | Create a module from a Library; handles embedded binary deserialization |
| `ProcessLibraryBin` | `Module ProcessLibraryBin(const char* library_bin, ObjectPtr<Library> opt_lib, void** library_ctx_addr = nullptr)` | Parse CSR binary format, reconstruct import tree |
| `LoadModuleFromBytes` | `Module LoadModuleFromBytes(const std::string& kind, const Bytes& bytes)` | Dispatch to `ffi.Module.load_from_bytes.<kind>` |
| `ffi::symbol::tvm_ffi_symbol_prefix` | `constexpr const char* = "__tvm_ffi_"` | Prefix for all FFI function symbols (added in 40e8a51) |
| `ffi::symbol::tvm_ffi_library_ctx` | `constexpr const char* = "__tvm_ffi__library_ctx"` | Symbol name for library context pointer (double underscore after prefix) |
| `ffi::symbol::tvm_ffi_library_bin` | `constexpr const char* = "__tvm_ffi__library_bin"` | Symbol name for embedded binary data |
| `ffi::symbol::tvm_ffi_main` | `constexpr const char* = "__tvm_ffi_main"` | Symbol name for default entry function |
| `ffi::symbol::tvm_ffi_metadata_prefix` | `constexpr const char* = "__tvm_ffi__metadata_"` | Prefix for per-function metadata symbols |
| `ffi::symbol::tvm_ffi_doc_prefix` | `constexpr const char* = "__tvm_ffi__doc_"` | Prefix for per-function docstring symbols (since ac7bf68) |

## C ABI Functions (continued)
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFIHandleInitOnce` | `int TVMFFIHandleInitOnce(void** handle_addr, int (*init_func)(void** result))` | Thread-safe once-only handle initialization with acquire-load fast path (since 25c25aec) |
| `TVMFFIHandleDeinitOnce` | `int TVMFFIHandleDeinitOnce(void** handle_addr, int (*deinit_func)(void* handle))` | Thread-safe once-only handle deinitialization via atomic exchange (since 25c25aec) |
| `TVMFFITensorCreateUnsafeView` | `int TVMFFITensorCreateUnsafeView(TVMFFIObjectHandle source, const DLTensor* prototype, TVMFFIObjectHandle* out)` | Create tensor view sharing source data; copies shape/strides from prototype (since 8888eb4b) |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `load_module` | `def load_module(path: str \| PathLike, keep_module_alive: bool = True) -> Module` | Load shared library module; `keep_module_alive` prevents premature GC (since 8dcaec1f) |
| `tvm_ffi.libinfo.load_lib_module` | `def load_lib_module(name: str) -> Module` | Convenience: find library by basename + load with keep_alive (since f255650b) |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| (No Rust API in this commit group) | -- | -- |

## Registered Global Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.ModuleLoadFromFile` | `(String) -> Module` | Load module from file path |
| `ffi.ModuleGetFunction` | `(Module, String, bool) -> Optional<Function>` | Get function, optionally from imports |
| `ffi.ModuleImplementsFunction` | `(Module, String, bool) -> bool` | Check if function exists |
| `ffi.ModuleGetFunctionDoc` | `(Module, String, bool) -> Optional<String>` | Get function docstring, optionally from imports (since 935a5a0; `LibraryModuleObj` implementation since ac7bf68) |
| `ffi.ModuleGetFunctionMetadata` | `(Module, String, bool) -> Optional<String>` | Get function metadata (JSON), optionally from imports |
| `ffi.ModuleGetPropertyMask` | `(Module) -> int` | Get property bitmask |
| `ffi.ModuleInspectSource` | `(Module, String) -> String` | Get source code |
| `ffi.ModuleGetKind` | `(Module) -> String` | Get module kind string |
| `ffi.ModuleGetWriteFormats` | `(Module) -> Array<String>` | Get supported write formats |
| `ffi.ModuleWriteToFile` | `(Module, String, String)` | Write module to file |
| `ffi.ModuleImportModule` | `(Module, Module)` | Import sub-module |
| `ffi.ModuleClearImports` | `(Module)` | Clear all imports |
| `ffi.Module.load_from_file.so` | `(String, String) -> Module` | DSO loader (registered by library_module_dynamic_lib.cc) |
| `ffi.SystemLib` | `(String?) -> Module` | Get/create system library module |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `TVMFFIEnvLookupFromImports` | `TVMFFIEnvModLookupFromImports` | 023ea44 | Added `Mod` infix to distinguish callee-side APIs |
| `TVMFFIEnvRegisterContextSymbol` | `TVMFFIEnvModRegisterContextSymbol` | 023ea44 | Added `Mod` infix |
| `TVMFFIEnvRegisterSystemLibSymbol` | `TVMFFIEnvModRegisterSystemLibSymbol` | 023ea44 | Added `Mod` infix |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 538bef4 | `2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md` | Initial module system: ModuleObj, Library, DSOLibrary, SystemLibrary, binary format |
| 023ea44 | `2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md` | Mod infix rename; move env APIs to extra |
| ac7bf68 | `2025-11-20-ac7bf68058b392c3a8475619016fde48bd08334b.md` | GetFunctionDoc, tvm_ffi_doc_prefix, LibraryModuleObj metadata/doc, Python Module methods |
| 25c25aec | `2025-12-05-25c25aec22acadcf1aeb839297fe156bc0cf7183.md` | TVMFFIHandleInitOnce/TVMFFIHandleDeinitOnce C API |
| 8888eb4b | `2025-12-12-8888eb4b254486fb1fb5baad7e9f24bc1cfac63a.md` | TVMFFITensorCreateUnsafeView, Tensor::as_strided, FromNDAllocStrided |
| 8dcaec1f | `2025-12-11-8dcaec1fb47bf7873b105385b7d2808d51f6b342.md` | load_module keep_module_alive parameter |
| f255650b | `2025-12-12-f255650b8e5121452dd60805b206a0cb5bcb6525.md` | tvm_ffi.libinfo.load_lib_module convenience function |

