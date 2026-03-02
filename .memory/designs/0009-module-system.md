---
design: "0009"
title: "Module System: Dynamic Loading, Library Abstraction, and Import Graphs"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-08-17"
last_updated: "2025-10-01"
scope:
  - "ffi/extra/module"
  - "ffi/extra/library_module"
  - "ffi/extra/c_env_api"
  - "python/tvm_ffi/module.py"
  - "python/tvm_ffi/cpp"
source_commits:
  - "538bef49b4daa91970f0f9cea137acdcb696562a"
  - "023ea448be6e86e09f4ebaba5a235ee53f3cdeef"
  - "2d41a5115f6a91e2781012a3379f9626bc9e18a1"
  - "777cf8d51f2054d96e0413b7406ed38ef43a7b39"
  - "83805ec949227620d05e61358a4ecb4f0c931979"
  - "40e8a519f5270dfb18436b2f26c2d691cf24c9c1"
  - "825aeb9aff00911cc8500aeec9ebb3ade738b015"
  - "236e9e9e7378f9f9b7de0e01acbc48c3dd57c323"
  - "2df07e52ef8c8008be4ffa3a29e3f541ca98c1c2"
  - "4ffbc88b60f659a74619035e699986792c071e8d"
  - "db987299f74aadcb4d8003cc6009cb67a75662c8"
  - "8068d1df64275452ced5d7a960a4468f663f50de"
  - "315f4bb00eac8b4d26cdcd6839fb1a077bab6976"
  - "4fcf94f6e2dcce9901e0e42c30c7d4d57487619d"
  - "935a5a074686839ae42a9bc52581232beeb5b1fc"
source_ledgers:
  - ".memory/commits/2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md"
  - ".memory/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md"
  - ".memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md"
  - ".memory/commits/2025-08-30-777cf8d51f2054d96e0413b7406ed38ef43a7b39.md"
  - ".memory/commits/2025-09-05-83805ec949227620d05e61358a4ecb4f0c931979.md"
  - ".memory/commits/2025-09-06-40e8a519f5270dfb18436b2f26c2d691cf24c9c1.md"
  - ".memory/commits/2025-09-06-825aeb9aff00911cc8500aeec9ebb3ade738b015.md"
  - ".memory/commits/2025-09-07-236e9e9e7378f9f9b7de0e01acbc48c3dd57c323.md"
  - ".memory/commits/2025-09-08-2df07e52ef8c8008be4ffa3a29e3f541ca98c1c2.md"
  - ".memory/commits/2025-09-08-4ffbc88b60f659a74619035e699986792c071e8d.md"
  - ".memory/commits/2025-09-09-db987299f74aadcb4d8003cc6009cb67a75662c8.md"
  - ".memory/commits/2025-09-09-8068d1df64275452ced5d7a960a4468f663f50de.md"
  - ".memory/commits/2025-09-10-315f4bb00eac8b4d26cdcd6839fb1a077bab6976.md"
  - ".memory/commits/2025-09-29-4fcf94f6.md"
  - ".memory/commits/2025-10-01-935a5a07.md"
---

# Module System: Dynamic Loading, Library Abstraction, and Import Graphs

## TL;DR
- `ffi::Module` (`ModuleObj` / `Module`) is a first-class FFI object (type index 73, type key `"ffi.Module"`) providing a virtual interface for dynamically loadable function containers. It supports function lookup, import graphs with cycle detection, binary serialization, and source inspection.
- Two concrete library implementations -- `DSOLibrary` (dlopen/LoadLibraryW) and `SystemLibrary` (global symbol table) -- wrap platform-native symbol resolution behind a common `Library` abstraction. `LibraryModuleObj` adapts any `Library` into a `Module`, with functions looked up by `__tvm_ffi_<name>` symbol convention.
- The entire module subsystem lives in `extra/`, gated by `TVM_FFI_USE_EXTRA_CXX_API`, following the established isolation pattern from ADR-0009.

## Problem Statement
TVM compiles ML models into shared libraries that export functions via C ABI symbols. A module system is needed to load these libraries, discover exported functions by name, manage import dependencies between modules (e.g., a model module importing a runtime module), and support binary serialization of module dependency graphs. Without a formal module abstraction, each deployment target (DSO, system library, WASM) would need ad-hoc loading code, and import graph management would be duplicated across frontends.

## Context and Constraints
- The module system must work across platforms: Linux (dlopen), macOS (dlopen), Windows (LoadLibraryW), and Hexagon.
- Exported functions follow the packed calling convention (`TVMFFISafeCallType`): they accept `(void* self, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* rv)` and return `int`.
- Each returned function must hold a strong reference to its parent module to prevent premature unloading (use-after-free of function pointers).
- Import graph cycles must be detected at import time to prevent infinite recursion during function lookup.
- The `Library` abstraction intentionally has no type key or type index -- it only needs reference counting, not dynamic type dispatch.
- System libraries use a global symbol table populated by static initializers (`TVMFFIEnvModRegisterSystemLibSymbol`), enabling statically-linked deployments.

## Goals
- Provide a virtual `ModuleObj` base class with a complete interface for function lookup, import management, serialization, and source inspection.
- Provide platform-specific `DSOLibrary` and `SystemLibrary` implementations behind a common `Library` interface.
- Provide `LibraryModuleObj` as the standard adapter from `Library` to `Module`.
- Support binary import-tree serialization for embedding multiple module types in a single shared library.
- Provide `ContextSymbolRegistry` for late-binding context function pointers into loaded libraries without explicit link dependencies.
- Expose all module operations as global functions for cross-language access.

## Non-Goals
- Hot-reloading or unloading of modules (once loaded, a DSO stays loaded for the process lifetime).
- Module versioning or compatibility checking (consumers are responsible for version management).
- Thread-safe concurrent module loading (loading is assumed to be single-threaded; function calls on loaded modules are thread-safe).

## Design
### Components and Responsibilities

- **`ModuleObj`** (abstract class, `extra/module.h`): Virtual base class with reserved static type index `kTVMFFIModule = 73`. Pure virtual methods: `kind()` (returns module type string), `GetFunction(name)` (returns `Optional<Function>`). Virtual methods with defaults: `GetPropertyMask()` (0), `ImplementsFunction(name)` (delegates to GetFunction), `GetFunctionDoc(name)`, `GetFunctionMetadata(name)` (returns `Optional<String>` in JSON format, added in `777cf8d`), `WriteToFile(name, format)` (throws), `GetWriteFormats()` (empty), `SaveToBytes()` (throws), `InspectSource(format)` (empty). Non-virtual: `GetFunction(name, query_imports)`, `ImplementsFunction(name, query_imports)`, `ImportModule(other)` (with cycle detection), `ClearImports()`. The metadata API includes `ffi.ModuleGetFunctionMetadata` global function and supports query-imports overload for searching the import chain.

- **`Module`** (ref class, `extra/module.h`): `ObjectRef` wrapper with `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE`. Static methods: `LoadFromFile(file_name)` (dispatches to `ffi.Module.load_from_file.<format>` in global registry), `VisitContextSymbols(callback)`. Contains `ModulePropertyMask` enum: `kBinarySerializable = 0b001`, `kRunnable = 0b010`, `kCompilationExportable = 0b100`.

- **`Library`** (abstract class, `module_internal.h`): Internal-only base class extending `Object` without type key. Pure virtual: `GetSymbol(name)`. Virtual: `GetSymbolWithSymbolPrefix(name)` (prepends `__tvm_ffi_` prefix, standardized in commit `40e8a51`). Intentionally lacks type index because no dynamic downcasting is needed.

- **`DSOLibrary`** (final class, `library_module_dynamic_lib.cc`): Wraps `dlopen`/`LoadLibraryW`. Platform-specific: uses `dlsym` on Unix, `GetProcAddress` on Windows, with Hexagon `dlinfo` support. Registered as `ffi.Module.load_from_file.so`.

- **`SystemLibrary`** (final class, `library_module_system_lib.cc`): Backed by `SystemLibSymbolRegistry` (a `Map<String, void*>` singleton). Symbols are registered via `TVMFFIEnvModRegisterSystemLibSymbol` at static initialization time. Overrides `GetSymbolWithSymbolPrefix` to check both prefixed and unprefixed names, preventing double-prefix bugs when callers pass names already containing the prefix (fixed in commit `8068d1d`).

- **`LibraryModuleObj`** (final class, `library_module.cc`): Adapts `Library` to `Module`. `kind()` returns `"library"`. `GetPropertyMask()` returns `kBinarySerializable | kRunnable`. `GetFunction(name)` looks up `__tvm_ffi_<name>` symbol and wraps it as `ffi::Function`. Critically, each returned function captures a strong ref to the Module (`self_strong_ref`) to prevent premature DSO unloading. Supports `GetFunctionMetadata` and `GetFunctionDoc` via `__tvm_ffi__metadata_<name>` and `__tvm_ffi__doc_<name>` symbols.

- **`ContextSymbolRegistry`** (singleton, `library_module.cc`): Stores `(name, void*)` pairs. When a library is loaded via `CreateLibraryModule`, all matching symbol addresses in the library are patched with registered values. Enables late-binding of context functions (e.g., allocators) without explicit link dependencies.

- **`SystemLibModuleRegistry`** (singleton, `library_module_system_lib.cc`): Maps symbol prefix strings to cached `Module` instances, ensuring each prefix produces exactly one module for the process lifetime. Thread-safe via `std::mutex`.

- **`ModuleGlobals`** (singleton, `module.cc`): Stores `Map<Module, int>` of modules that should not be unloaded (frontend `keep_alive=True`). Thread-safe via `std::mutex`.

- **`BufferInStream`** (utility, `buffer_stream.h`): Read-only stream over a byte buffer. Supports reading length-prefixed strings, `std::vector<T>`, and arithmetic types with endian awareness.

- **`tvm_ffi.cpp.load_inline()`** (Python, `python/tvm_ffi/cpp/`): JIT compilation pipeline that compiles C++/CUDA inline source code into a shared library and loads it as a TVM FFI `Module`. Uses ninja for builds and content-hash-based caching in `~/.cache/tvm-ffi`. Supports CPU and CUDA source, auto-wraps user source with FFI headers and export macros via `_decorate_with_tvm_ffi()`. Configuration via `TVM_FFI_CACHE_DIR`, `TVM_FFI_CUDA_ARCH_LIST`, `MAX_JOBS` environment variables. Added in commit `83805ec`. API simplified in commit `825aeb9`: `cpp_source`/`cuda_source` renamed to `cpp_sources`/`cuda_sources` (accepting `str | Sequence[str]`), `cpp_functions`/`cuda_functions` replaced with unified `functions` parameter, `build_directory` parameter added. Windows support added in commit `2df07e5` (MSVC flags, `.dll` extension, colon escaping, `tvm_ffi.lib` linking). macOS support added in commit `4ffbc88` (linking `-ltvm_ffi`). Tests are `xfail` on Windows (commit `315f4bb`) due to remaining stability issues.

- **`tvm_ffi.utils.FileLock`** (Python, `python/tvm_ffi/utils/`): Cross-platform (Unix/Windows) advisory file locking utility for build cache concurrency safety. Used by `load_inline()` to prevent concurrent builds of the same source hash.

- **`ModuleObj::InternalUnsafe`** (nested struct, `module_internal.h`): Provides `GetImports()`, `GetFunctionFromImports()` (with static mutex for cache safety), and `RegisterReflection()`. The import lookup cache (`Map<String, Function>`) caches results to avoid repeated import-graph traversal.

### Data Contracts and Invariants

- **Type index**: `ModuleObj` uses static type index `kTVMFFIModule = 73`, declared via `TVM_FFI_DECLARE_OBJECT_INFO_STATIC`.
- **Mutable**: `_type_mutable = true` (imports can be added/cleared).
- **Import acyclicity**: `ImportModule` performs a BFS from the imported module, checking if the importing module is reachable. Throws `RuntimeError` on cycle detection.
- **Function lifetime**: Every `ffi::Function` returned by `LibraryModuleObj::GetFunction` captures a strong `Module` reference, guaranteeing the underlying DSO remains loaded as long as any function from it is alive.
- **Symbol convention**: Exported functions use `__tvm_ffi_<name>` prefix (standardized in commit `40e8a51`). User-visible names are prefix-free; the prefix is applied at the symbol lookup layer. Special internal symbols use double-underscore `__tvm_ffi__`: `__tvm_ffi__library_ctx` (context pointer), `__tvm_ffi__library_bin` (embedded binary data), `__tvm_ffi__metadata_<name>` (function metadata), `__tvm_ffi__doc_<name>` (function documentation). The `symbol::tvm_ffi_symbol_prefix` constant holds `"__tvm_ffi_"`. Python `Module.entry_name` is `"main"` (prefix applied internally, not `"__tvm_ffi_main__"`).
- **Binary import-tree format**: `<nbytes:u64> <indptr:vec<u64>> <child_indices:vec<u64>> [<kind:str> [<bytes:str>]]...`. CSR structure. `"_lib"` kind is a sentinel for the DSO module placeholder. Node 0 is the root module.
- **Import lookup cache**: `Map<String, Function>` guarded by a static `std::mutex`. Falls back to global registry if not found in imports.

### Control Flow

1. **Loading a DSO module**: `Module::LoadFromFile("lib.so")` -> extract format `"so"` -> look up `ffi.Module.load_from_file.so` in global registry -> calls `CreateLibraryModule(make_object<DSOLibrary>(path))` -> `ContextSymbolRegistry::InitContextSymbols(lib)` patches known symbols -> check for `__tvm_ffi__library_bin` -> if present, `ProcessLibraryBin` deserializes the import tree; otherwise, wrap as single `LibraryModuleObj`.

2. **Function lookup with imports**: `mod->GetFunction(name, true)` -> first check `this->GetFunction(name)` -> if not found and `query_imports`, iterate `imports_` recursively.

3. **Import lookup from generated code**: `TVMFFIEnvModLookupFromImports(ctx, name, &out)` -> `InternalUnsafe::GetFunctionFromImports(module, name)` -> check cache -> if miss, search imports recursively -> fall back to global registry -> cache result -> return raw `FunctionObj*`.

4. **System library loading**: `ffi.SystemLib(prefix)` -> `SystemLibModuleRegistry::GetOrCreateModule(prefix)` -> if not cached, `CreateLibraryModule(make_object<SystemLibrary>(prefix))` -> cache and return.

### Extension Points
- **New module types**: Subclass `ModuleObj`, implement `kind()` and `GetFunction()`, register a `ffi.Module.load_from_file.<format>` global function.
- **New library backends**: Subclass `Library`, implement `GetSymbol()`. Pass to `CreateLibraryModule()`.
- **Custom serialization**: Register `ffi.Module.load_from_bytes.<kind>` for deserializing binary-serialized module types within the import tree.
- **Context symbols**: Register via `TVMFFIEnvModRegisterContextSymbol` before loading libraries. The registry patches matching symbols at load time.
- **Inline compilation**: `tvm_ffi.cpp.load_inline()` provides JIT compilation of C++/CUDA sources into modules, with content-hash caching and ninja-based builds. Parallels PyTorch's `torch.utils.cpp_extension.load_inline` but targets TVM FFI ABI. Cross-platform support: Linux (primary), Windows (MSVC, commit `2df07e5`), macOS (commit `4ffbc88`).

## Alternatives Considered
### dlopen-only without abstraction
- Pros: Simpler, no `Library`/`Module` hierarchy.
- Cons: Cannot support system libraries (static linking), WASM, or other non-DSO deployment targets. No import graph support.

### Module as a C ABI struct (not C++ virtual)
- Pros: ABI-stable across compilers. No vtable.
- Cons: Much more cumbersome to extend. Each new method requires a new function pointer field. Virtual dispatch through the object system is already established and works well for the extra/ layer.

### Import graph as metadata file
- Pros: Human-readable. Separate from binary.
- Cons: Two files to distribute instead of one. Binary embedding is more convenient for deployment.

## Trade-offs
- **Optimized**: Deployment convenience (single `.so` can contain full module graph via binary embedding), function lookup performance (import lookup cache), platform coverage (dlopen + LoadLibraryW + system lib), safety (strong refs prevent use-after-free).
- **Sacrificed**: Module unloading (DSOs stay loaded forever), cross-process module sharing (modules are per-process), thread-safe module loading (assumed single-threaded).

## Interfaces and Compatibility
- **C++ API**: `ffi::Module`, `ffi::ModuleObj`, `Module::LoadFromFile`, `Module::VisitContextSymbols`, `ModulePropertyMask`.
- **C ABI** (in `extra/c_env_api.h`): `TVMFFIEnvModLookupFromImports`, `TVMFFIEnvModRegisterContextSymbol`, `TVMFFIEnvModRegisterSystemLibSymbol`.
- **Global functions**: `ffi.ModuleLoadFromFile`, `ffi.ModuleGetFunction`, `ffi.ModuleImplementsFunction`, `ffi.ModuleGetPropertyMask`, `ffi.ModuleInspectSource`, `ffi.ModuleGetKind`, `ffi.ModuleGetWriteFormats`, `ffi.ModuleWriteToFile`, `ffi.ModuleImportModule`, `ffi.ModuleClearImports`, `ffi.ModuleGlobalsAdd`, `ffi.ModuleGlobalsRemove`, `ffi.ModuleGetFunctionMetadata`, `ffi.ModuleGetFunctionDoc`, `ffi.SystemLib`, `ffi.Module.load_from_file.so`.
- **Python API** (in `python/tvm_ffi/module.py`, added in `2d41a51`): `Module` class (registered with `@register_object("ffi.Module")`), `load_module(path)`, `system_lib(prefix)`. The Python `Module` provides attribute-style function access (`mod.func_name`), `entry_func` property, `imports` property, `get_function(name, query_imports)`, `import_module(other)`, `inspect_source(fmt)`, `save(file_name, fmt)`, `export_library(file_name, fcompile, workspace_dir)`, and `__call__` dispatch to entry function. Functions accessed via `_ffi_api` lazy lookup pattern.
- **CMake**: All source files in `src/ffi/extra/`, gated by `TVM_FFI_USE_EXTRA_CXX_API`.
- **Symbol convention**: `__tvm_ffi_<name>`, `__tvm_ffi__library_ctx`, `__tvm_ffi__library_bin`, `__tvm_ffi__metadata_<name>`, `__tvm_ffi__doc_<name>`.

## Failure Modes and Mitigations
- **DSO not found**: `DSOLibrary::Load` throws with `dlerror()` message on Unix, or `"Failed to load dynamic shared library"` on Windows.
- **Symbol not found**: `GetFunction` returns `std::nullopt`. `TVMFFIEnvModLookupFromImports` throws `RuntimeError` with the function name.
- **Cyclic import**: `ImportModule` detects cycles via BFS and throws `RuntimeError`.
- **Missing loader**: `LoadFromFile` throws if `ffi.Module.load_from_file.<format>` is not registered, with a diagnostic message suggesting correct runtime/architecture.
- **Corrupted binary**: `ProcessLibraryBin` uses `TVM_FFI_ICHECK` assertions on stream reads and child indices.
- **Import lookup cache contention**: Static mutex serializes all `GetFunctionFromImports` calls across all modules. Acceptable for the common case (single-threaded module loading, occasional cross-module calls).

## Observability and Validation
- Module reflection: `ObjectDef<ModuleObj>().def_ro("imports_", ...)` exposes imports for cross-language introspection.
- `ffi.ModuleGetKind` returns the module kind string.
- `ffi.ModuleGetPropertyMask` returns capability bitmask.
- The `ffi.ModuleLoadFromFile` -> `ffi.Module.load_from_file.<format>` dispatch chain is visible in the global function registry.

## Migration and Rollout
- This is a new subsystem, not replacing existing infrastructure in the FFI library itself. It formalizes what was previously `runtime::Module` in the main TVM project into the standalone FFI layer.
- Downstream consumers that previously used `runtime::Module` should migrate to `ffi::Module` by including `<tvm/ffi/extra/module.h>`.
- The binary import-tree format is compatible with existing compiled TVM models.

## Diagrams
- [.memory/diagrams/0007-module-system-architecture.md](.memory/diagrams/0007-module-system-architecture.md)

## Related ADRs
- [.memory/ADRs/0009-extra-api-isolation.md](.memory/ADRs/0009-extra-api-isolation.md) -- module system follows the extra/ isolation pattern.
- [.memory/ADRs/0013-module-scoped-c-api-naming.md](.memory/ADRs/0013-module-scoped-c-api-naming.md) -- `TVMFFIEnvMod*` naming convention for module-scoped C API symbols.

## Evidence Matrix
- `ModuleObj` class with virtual interface -> `.memory/commits/2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md` + `538bef4` + `include/tvm/ffi/extra/module.h` (224 lines)
- `Module` ref class with `LoadFromFile`, `ModulePropertyMask` -> `538bef4` + `include/tvm/ffi/extra/module.h` lines 218-276
- `Library` abstract class (no type key) -> `538bef4` + `src/ffi/extra/module_internal.h` lines 42-64
- `DSOLibrary` with dlopen/LoadLibraryW -> `538bef4` + `src/ffi/extra/library_module_dynamic_lib.cc` (118 lines)
- `SystemLibrary` with global symbol table -> `538bef4` + `src/ffi/extra/library_module_system_lib.cc` (129 lines)
- `LibraryModuleObj` wrapping `Library` -> `538bef4` + `src/ffi/extra/library_module.cc` lines 36-87
- Binary import-tree deserialization (`ProcessLibraryBin`) -> `538bef4` + `src/ffi/extra/library_module.cc` lines 109-163
- `ContextSymbolRegistry` singleton -> `538bef4` + `src/ffi/extra/library_module.cc` lines 166-193
- `BufferInStream` utility -> `538bef4` + `src/ffi/extra/buffer_stream.h` (127 lines)
- Import cycle detection in `ImportModule` -> `538bef4` + `src/ffi/extra/module.cc` lines 103-120
- Import lookup cache with static mutex -> `538bef4` + `src/ffi/extra/module_internal.h` lines 69-94
- Global functions registration -> `538bef4` + `src/ffi/extra/module.cc` lines 164-196
- C ABI symbols renamed with `Mod` infix -> `.memory/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md` + `023ea44` + `include/tvm/ffi/extra/c_env_api.h`
- Static type index `kTVMFFIModule = 73` -> `538bef4` + `include/tvm/ffi/extra/module.h` line 183
- `object.h` mutable ref macro fix -> `538bef4` + `include/tvm/ffi/object.h`
- Well-known symbols (`tvm_ffi_main`, `tvm_ffi_library_ctx`, `tvm_ffi_library_bin`, `tvm_ffi_metadata_prefix`, `tvm_ffi_doc_prefix`) -> `538bef4` + `include/tvm/ffi/extra/module.h` lines 281-296
- Python `Module` class with `@register_object("ffi.Module")` -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `python/tvm_ffi/module.py`
- Python `load_module()` and `system_lib()` helpers -> `2d41a51` + `python/tvm_ffi/module.py`
- End-to-end Python example (`examples/get_started/run_example.py`) demonstrating `tvm_ffi.load_module()` with numpy and torch tensors -> `2d41a51` + `examples/get_started/run_example.py`
- `ModuleObj::GetFunctionMetadata` virtual method (JSON format) -> `.memory/commits/2025-08-30-777cf8d51f2054d96e0413b7406ed38ef43a7b39.md` + `777cf8d` + `include/tvm/ffi/extra/module.h`
- `tvm_ffi_metadata_prefix` symbol constant -> `777cf8d` + `include/tvm/ffi/extra/module.h`
- `ffi.ModuleGetFunctionMetadata` global function -> `777cf8d` + `src/ffi/extra/module.cc`
- `load_inline()` JIT compilation pipeline -> `.memory/commits/2025-09-05-83805ec949227620d05e61358a4ecb4f0c931979.md` + `83805ec` + `python/tvm_ffi/cpp/`
- `FileLock` cross-platform lock -> `83805ec` + `python/tvm_ffi/utils/`
- `_decorate_with_tvm_ffi()` auto-wrapping -> `83805ec` + `python/tvm_ffi/cpp/`
- Inline module tests -> `83805ec` + `tests/python/test_load_inline.py`
- `__tvm_ffi_` symbol prefix standardization -> `.memory/commits/2025-09-06-40e8a519f5270dfb18436b2f26c2d691cf24c9c1.md` + `40e8a51` + `include/tvm/ffi/extra/module.h`
- `symbol::tvm_ffi_symbol_prefix` constant -> `40e8a51` + `include/tvm/ffi/extra/module.h`
- `Library::GetSymbolWithSymbolPrefix` virtual method -> `40e8a51` + `src/ffi/extra/module_internal.h`
- `load_inline` API simplification (torch convention) -> `.memory/commits/2025-09-06-825aeb9aff00911cc8500aeec9ebb3ade738b015.md` + `825aeb9` + `python/tvm_ffi/cpp/`
- `load_inline` xfail on non-Linux -> `.memory/commits/2025-09-07-236e9e9e7378f9f9b7de0e01acbc48c3dd57c323.md` + `236e9e9` + `tests/python/test_load_inline.py`
- `load_inline` Windows fix (MSVC, .dll, colon escaping) -> `.memory/commits/2025-09-08-2df07e52ef8c8008be4ffa3a29e3f541ca98c1c2.md` + `2df07e5` + `python/tvm_ffi/cpp/load_inline.py`
- `load_inline` macOS fix (libtvm_ffi.dylib linking) -> `.memory/commits/2025-09-08-4ffbc88b60f659a74619035e699986792c071e8d.md` + `4ffbc88` + `python/tvm_ffi/cpp/load_inline.py`
- SystemLibrary double-prefix fix -> `.memory/commits/2025-09-09-8068d1df64275452ced5d7a960a4468f663f50de.md` + `8068d1d` + `src/ffi/extra/library_module_system_lib.cc`
- Windows xfail + version bump to 0.1.0a9 -> `.memory/commits/2025-09-10-315f4bb00eac8b4d26cdcd6839fb1a077bab6976.md` + `315f4bb` + `tests/python/test_load_inline.py`, `pyproject.toml`
- `build_inline` utility (returns path to compiled .so, `load_inline` refactored as thin wrapper) -> `.memory/commits/2025-09-29-4fcf94f6.md` + `4fcf94f` + `python/tvm_ffi/cpp/`
- `TVMFFIFieldInfo/TVMFFIMethodInfo.type_schema` renamed to `metadata`, `ModuleObj::GetFunctionDoc` virtual method, `ffi.ModuleGetFunctionDoc` global function, doc/metadata separation -> `.memory/commits/2025-10-01-935a5a07.md` + `935a5a0` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/extra/module.h`

## Open Questions
- Should the import lookup cache be per-module instead of using a global static mutex?
- Should `Library` have a type key to support cross-language introspection of the library type?
- Should there be a `Module::Unload()` API for long-running applications that need to reclaim DSO resources?

## Confidence and Risk
- Confidence: high
- Residual risks: The static mutex in `GetFunctionFromImports` could become a bottleneck under heavy concurrent cross-module function calls. The `Library` class having no type key means it cannot be inspected cross-language. DSOs are never unloaded, which could be an issue for long-running applications that load many transient modules.
