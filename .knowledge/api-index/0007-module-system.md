---
scope: "module-system"
---
# API Index: Module System

**Scope**: Module loading, import management, library abstraction, stream context, and env C API functions declared in `extra/module.h` and `extra/c_env_api.h`.
**Design docs**: [0013-module-system.md](../designs/0013-module-system.md)
**ADRs**: [0010-extra-api-isolation.md](../ADRs/0010-extra-api-isolation.md), [0013-env-api-naming-convention.md](../ADRs/0013-env-api-naming-convention.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `ModuleObj` | class (abstract) | `kind() -> const char*`, `GetPropertyMask() -> int`, `GetFunction(String) -> Optional<Function>`, `GetFunctionMetadata(String) -> Optional<String>` (virtual, default nullopt), `ImplementsFunction(String) -> bool`, `WriteToFile(String, String)`, `GetWriteFormats() -> Array<String>`, `SaveToBytes() -> Bytes`, `InspectSource(String) -> String`, `ImportModule(Module)`, `ClearImports()`, `GetFunction(String, bool) -> Optional<Function>`, `GetFunctionMetadata(String, bool) -> Optional<String>` (walks imports), `imports() -> const Array<Any>&`; `_type_index = 73`, `_type_key = "ffi.Module"`, `_type_final = true` | Abstract base for all dynamically-loadable modules |
| `Module` | class (ObjectRef) | `enum ModulePropertyMask { kBinarySerializable=1, kRunnable=2, kCompilationExportable=4 }`, `static LoadFromFile(String) -> Module`, `static VisitContextSymbols(TypedFunction<void(String, void*)>)` | Reference handle for ModuleObj |
| `Library` | class (internal, abstract) | `virtual void* GetSymbol(const String& name) = 0`, `virtual void* GetSymbolWithSymbolPrefix(const String& name)` (default: prepends `__tvm_ffi_` prefix) | Internal symbol-provider; no type_key/type_index, refcounting only |
| `LibraryModuleObj` | class (final) | `kind() = "library"`, `GetPropertyMask() = kBinarySerializable \| kRunnable`, `GetFunction(String) -> Optional<Function>`, `GetFunctionMetadata(String) -> Optional<String>` (resolves `__tvm_ffi__metadata_<name>`), `GetFunctionDoc(String) -> Optional<String>` (resolves `__tvm_ffi__doc_<name>`) | Wraps Library; returned functions hold self-strong-ref; metadata/doc resolve companion symbols (ac7bf68) |
| `DSOLibrary` | class (final, internal) | `DSOLibrary(String name)` (calls dlopen/LoadLibraryW), `GetSymbol(const String&) -> void*` (calls dlsym/GetProcAddress) | Platform-specific dynamic library loader |
| `SystemLibrary` | class (final, internal) | `SystemLibrary(String symbol_prefix)`, `GetSymbol(const String&) -> void*`, `GetSymbolWithSymbolPrefix(const String&) -> void*` | Backed by SystemLibSymbolRegistry; prefix-idempotent lookup (tries prefix+name then name) |
| `SystemLibSymbolRegistry` | class (internal, singleton) | `RegisterSymbol(string, void*)`, `GetSymbol(const char*) -> void*`, `static Global()` | Global in-process symbol table for statically-linked kernels |
| `SystemLibModuleRegistry` | class (internal, singleton) | `GetOrCreateModule(String prefix) -> Module`, `static Global()` | Mutex-protected cache of system lib Modules by prefix |
| `ContextSymbolRegistry` | class (internal, singleton) | `Register(String, void*)`, `InitContextSymbols(ObjectPtr<Library>)`, `VisitContextSymbols(TypedFunction)`, `static Global()` | Lazy-binding registry; initializes context symbols in loaded libraries |
| `EnvContext` | class (internal, thread_local) | `SetStream(int32_t device_type, int32_t device_id, TVMFFIStreamHandle, TVMFFIStreamHandle*)`, `GetStream(int32_t, int32_t) -> TVMFFIStreamHandle`, `SetTensorAllocator(DLPackTensorAllocator, int write_to_global, DLPackTensorAllocator*)`, `GetTensorAllocator() -> DLPackTensorAllocator`, `static ThreadLocal()` | Per-device per-thread stream tracking + tensor allocator context (renamed from StreamContext) |
| `tvm::ffi::symbol::tvm_ffi_symbol_prefix` | constexpr const char* | `"__tvm_ffi_"` | User-exported function prefix |
| `tvm::ffi::symbol::tvm_ffi_main` | constexpr const char* | `"__tvm_ffi_main"` | Well-known symbol: default entry point |
| `tvm::ffi::symbol::tvm_ffi_library_ctx` | constexpr const char* | `"__tvm_ffi__library_ctx"` | Well-known symbol: pointer to ModuleObj* (double underscore = internal) |
| `tvm::ffi::symbol::tvm_ffi_library_bin` | constexpr const char* | `"__tvm_ffi__library_bin"` | Well-known symbol: embedded binary data (double underscore = internal) |
| `tvm::ffi::symbol::tvm_ffi_metadata_prefix` | constexpr const char* | `"__tvm_ffi__metadata_"` | Well-known symbol: per-function metadata prefix (double underscore = internal) |
| `tvm::ffi::symbol::tvm_ffi_doc_prefix` | constexpr const char* | `"__tvm_ffi__doc_"` | Well-known symbol: per-function doc prefix (double underscore = internal, ac7bf68) |
| `TVMFFIStreamHandle` | typedef | `void*` | Opaque handle for device streams |
| `TVMFFIEnvSetStream` | C function | `(int32_t device_type, int32_t device_id, TVMFFIStreamHandle stream, TVMFFIStreamHandle* opt_out_original_stream) -> int` | Set thread-local stream for device; returns 0 on success |
| `TVMFFIEnvGetStream` | C function | `(int32_t device_type, int32_t device_id) -> TVMFFIStreamHandle` | Get thread-local stream for device; returns nullptr if unset |
| `TVMFFIEnvSetTensorAllocator` | C function | `(DLPackTensorAllocator allocator, int write_to_global_context, DLPackTensorAllocator* opt_out_original) -> int` | Set TLS (and optionally global) tensor allocator |
| `TVMFFIEnvGetTensorAllocator` | C function | `() -> DLPackTensorAllocator` | Get tensor allocator (TLS first, then global fallback) |
| `TVMFFIEnvModLookupFromImports` | C function | `(TVMFFIObjectHandle library_ctx, const char* func_name, TVMFFIObjectHandle* out) -> int` | Resolve function from module imports + global registry (cached) |
| `TVMFFIEnvModRegisterContextSymbol` | C function | `(const char* name, void* symbol) -> int` | Register context symbol for lazy library initialization |
| `TVMFFIEnvModRegisterSystemLibSymbol` | C function | `(const char* name, void* symbol) -> int` | Register symbol in system library table |

## Global Functions (registered via GlobalDef)
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.ModuleLoadFromFile` | `(String) -> Module` | Load module from file path (format from extension) |
| `ffi.ModuleGetFunction` | `(Module, String, bool) -> Optional<Function>` | Get function, optionally query imports |
| `ffi.ModuleImplementsFunction` | `(Module, String, bool) -> bool` | Check function existence |
| `ffi.ModuleGetPropertyMask` | `(Module) -> int` | Get property bitmask |
| `ffi.ModuleInspectSource` | `(Module, String) -> String` | Get source code |
| `ffi.ModuleGetKind` | `(Module) -> String` | Get module kind |
| `ffi.ModuleGetWriteFormats` | `(Module) -> Array<String>` | Get exportable formats |
| `ffi.ModuleWriteToFile` | `(Module, String, String) -> void` | Write module to file |
| `ffi.ModuleImportModule` | `(Module, Module) -> void` | Import another module |
| `ffi.ModuleClearImports` | `(Module) -> void` | Clear imports |
| `ffi.ModuleGetFunctionMetadata` | `(Module, String, bool) -> Optional<String>` | Get function metadata as JSON, optionally query imports |
| `ffi.ModuleGetFunctionDoc` | `(Module, String, bool) -> Optional<String>` | Get function docstring, optionally query imports (ac7bf68) |
| `ffi.Module.load_from_file.so` | `(String, String) -> Module` | SO/DLL/dylib loader via DSOLibrary |
| `ffi.SystemLib` | `(Optional<String>) -> Module` | Get/create system library module (cached by prefix) |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `Module.get_function_metadata` | `(self, name: str, query_imports: bool = False) -> dict[str, Any] \| None` | Get function metadata (parsed JSON dict with `type_schema` key), or None (ac7bf68) |
| `Module.get_function_doc` | `(self, name: str, query_imports: bool = False) -> str \| None` | Get function documentation string, or None (ac7bf68) |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | -- | Module system accessed via FFI global function calls |
