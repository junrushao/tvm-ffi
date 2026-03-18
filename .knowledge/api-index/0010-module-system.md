---
scope: "module-system"
---
# API Index: Module System

**Scope**: Module type (`ModuleObj`/`Module`), Library abstraction, loading infrastructure, C env API for module interaction.
**Design docs**: [0011-module-system.md](../designs/0011-module-system.md)
**ADRs**: [0007-module-as-static-object.md](../ADRs/0007-module-as-static-object.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `ModuleObj` | class | `kind() -> str`, `GetFunction(name) -> Optional<Function>`, `GetFunction(name, query_imports) -> Optional<Function>`, `GetFunctionMetadata(name) -> Optional<String>`, `GetFunctionMetadata(name, query_imports) -> Optional<String>`, `GetFunctionDoc(name) -> Optional<String>` (935a5a0), `GetFunctionDoc(name, query_imports) -> Optional<String>` (935a5a0), `ImportModule(other)`, `GetPropertyMask() -> int`, `WriteToFile(file, format)`, `SaveToBytes() -> Bytes`, `InspectSource(format) -> String`, `GetWriteFormats() -> Array<String>`, `ImplementsFunction(name) -> bool`, `ClearImports()` | Base module object type (kTVMFFIModule = 73) |
| `Module` | class | `static LoadFromFile(file_name) -> Module`, `static VisitContextSymbols(callback)`, `ModulePropertyMask` enum | Module handle (non-nullable, mutable ObjectRef) |
| `Module::ModulePropertyMask` | enum | `kBinarySerializable=0b001`, `kRunnable=0b010`, `kCompilationExportable=0b100` | Module capability flags |
| `Library` | class (internal) | `virtual GetSymbol(name: String) -> void_ptr`, `virtual GetSymbolWithSymbolPrefix(name: String) -> void_ptr` | Abstract symbol provider. `GetSymbolWithSymbolPrefix` prepends `__tvm_ffi_` prefix |
| `DSOLibrary` | class (internal) | `GetSymbol(name) -> void_ptr` | Dynamic shared object loader (dlopen/LoadLibraryW) |
| `SystemLibrary` | class (internal) | `GetSymbol(name) -> void_ptr`, overrides `GetSymbolWithSymbolPrefix` to compose system_prefix + ffi_prefix | Static symbol table for AOT/embedded |
| `symbol::tvm_ffi_symbol_prefix` | const char* | `"__tvm_ffi_"` | Canonical prefix for all FFI function symbols in shared libraries |
| `symbol::tvm_ffi_library_ctx` | const char* | `"__tvm_ffi__library_ctx"` | Library context pointer (double underscore = internal) |
| `symbol::tvm_ffi_library_bin` | const char* | `"__tvm_ffi__library_bin"` | Embedded binary data (double underscore = internal) |
| `symbol::tvm_ffi_main` | const char* | `"__tvm_ffi_main"` | Default entry function symbol |
| `symbol::tvm_ffi_metadata_prefix` | const char* | `"__tvm_ffi__metadata_"` | Prefix for function metadata symbols (double underscore = internal) |
| `symbol::tvm_ffi_doc_prefix` | const char* | `"__tvm_ffi__doc_"` | Prefix for function docstring symbols (double underscore = internal, ac7bf68) |
| `LibraryModuleObj` | class | `GetFunction(name)`, `GetFunctionMetadata(name)` (looks up `__tvm_ffi__metadata_` symbol), `GetFunctionDoc(name)` (looks up `__tvm_ffi__doc_` symbol, ac7bf68) | Concrete module wrapping Library with metadata/doc symbol resolution |

## C ABI (c_env_api.h)
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFIEnvModLookupFromImports` | `int (TVMFFIObjectHandle library_ctx, const char* func_name, TVMFFIObjectHandle* out)` | Look up function from module import tree (cached, mutex-protected) |
| `TVMFFIEnvModRegisterContextSymbol` | `int (const char* name, void* symbol)` | Register context symbol for library modules |
| `TVMFFIEnvModRegisterSystemLibSymbol` | `int (const char* name, void* ptr)` | Register symbol in system library table |

## Registered Global Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.ModuleLoadFromFile` | `def(file_name: str) -> Module` | Load module from file |
| `ffi.ModuleGetFunction` | `def(module: Module, name: str, query_imports: bool) -> Optional[Function]` | Get function from module |
| `ffi.ModuleImplementsFunction` | `def(module: Module, name: str, query_imports: bool) -> bool` | Check if module implements function |
| `ffi.ModuleGetPropertyMask` | `def(module: Module) -> int` | Get module property mask |
| `ffi.ModuleInspectSource` | `def(module: Module, format: str) -> str` | Get module source code |
| `ffi.ModuleGetKind` | `def(module: Module) -> str` | Get module kind string |
| `ffi.ModuleWriteToFile` | `def(module: Module, file: str, format: str)` | Write module to file |
| `ffi.ModuleGetWriteFormats` | `def(module: Module) -> Array[str]` | Get supported write formats |
| `ffi.ModuleImportModule` | `def(module: Module, other: Module)` | Import a module |
| `ffi.ModuleClearImports` | `def(module: Module)` | Clear all imports |
| `ffi.ModuleGetFunctionMetadata` | `def(module: Module, name: str, query_imports: bool) -> Optional[str]` | Get function metadata JSON from module |
| `ffi.ModuleGetFunctionDoc` | `def(module: Module, name: str, query_imports: bool) -> Optional[str]` | Get function docstring from module (935a5a0) |
| `ffi.Module.load_from_file.so` | `def(file_name: str) -> Module` | Load DSO module |
| `ffi.SystemLib` | `def() -> Module` | Get or create system library module |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `tvm_ffi.cpp.build_inline` | `def build_inline(name: str, *, cpp_sources=None, cuda_sources=None, functions=None, ..., embed_cubin=None) -> str` | Compile inline C++/CUDA to shared library path without loading (4fcf94f). `embed_cubin: Mapping[str, bytes]` for CUBIN embedding (d49effd) |
| `tvm_ffi.cpp.load_inline` | `def load_inline(name: str, *, cpp_sources=None, cuda_sources=None, functions=None, ..., embed_cubin=None) -> Module` | Compile and load inline C++/CUDA. Thin wrapper: `load_module(build_inline(...))`. `embed_cubin` parameter (d49effd) |
| `Module.get_function_metadata` | `def get_function_metadata(self, name: str, query_imports: bool = False) -> dict[str, Any] \| None` | Get metadata JSON dict for DLL-exported function (ac7bf68) |
| `Module.get_function_doc` | `def get_function_doc(self, name: str, query_imports: bool = False) -> str \| None` | Get docstring for DLL-exported function (ac7bf68) |
| `tvm_ffi.cpp.build` | `def build(name: str, *, cpp_files=None, cuda_files=None, ...) -> str` | Compile C++/CUDA files to shared library path (c897e4c). No auto header/export decoration |
| `tvm_ffi.cpp.load` | `def load(name: str, *, cpp_files=None, cuda_files=None, ...) -> Module` | Compile files and load as Module (c897e4c). Thin wrapper: `load_module(build(...))` |
| `tvm_ffi.load_module` | `def load_module(path: str \| PathLike, keep_module_alive: bool = True) -> Module` | Load Module; pins in ModuleGlobals by default to prevent dlclose (8dcaec1f) |
| `tvm_ffi.cpp.load_inline` | (updated) `keep_module_alive: bool = True` param added | Passes keep_module_alive through to load_module (8dcaec1f) |
| `tvm_ffi.cpp.load` | (updated) `keep_module_alive: bool = True` param added | Passes keep_module_alive through to load_module (8dcaec1f) |
| `tvm_ffi.libinfo.load_lib_module` | `def load_lib_module(package: str, target_name: str, keep_module_alive: bool = True) -> Module` | Locate + load shared library as Module via importlib.metadata (f255650b) |
| `ffi.ModuleGlobalsAdd` | `def(mod: Module) -> None` | Pin module in ModuleGlobals singleton (8dcaec1f) |
| `ffi.ModuleGlobalsRemove` | `def(mod: Module) -> None` | Unpin module from ModuleGlobals (8dcaec1f) |
