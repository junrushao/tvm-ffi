---
diagram: "0007"
title: "Module System Architecture"
format: "mermaid"
source_commits:
  - "538bef49b4daa91970f0f9cea137acdcb696562a"
  - "023ea448be6e86e09f4ebaba5a235ee53f3cdeef"
  - "40e8a519f5270dfb18436b2f26c2d691cf24c9c1"
  - "8068d1df64275452ced5d7a960a4468f663f50de"
  - "a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806"
related_designs:
  - ".memory/designs/0009-module-system.md"
---

# Module System Architecture

## Class Hierarchy

```mermaid
classDiagram
  class Object {
    +uint64_t strong_ref_count
    +int32_t type_index
    +uint32_t weak_ref_count
  }
  class ModuleObj {
    <<abstract>>
    +kind() const char*
    +GetFunction(name) Optional~Function~
    +GetPropertyMask() int
    +ImplementsFunction(name) bool
    +GetFunctionDoc(name) Optional~String~
    +GetFunctionMetadata(name) Optional~String~
    +ImportModule(other)
    +ClearImports()
    +WriteToFile(file, format)
    +SaveToBytes() Bytes
    +InspectSource(format) String
    -Array~Any~ imports_
    -Map~String,Function~ import_lookup_cache_
  }
  class Module {
    +LoadFromFile(file) Module$
    +VisitContextSymbols(cb)$
    +ModulePropertyMask
  }
  class Library {
    <<abstract, no type key>>
    +GetSymbol(name) void*
    +GetSymbolWithSymbolPrefix(name) void*
  }
  class LibraryModuleObj {
    +kind() = "library"
    +GetFunction(name) Optional~Function~
    +GetFunctionMetadata(name) Optional~String~
    +GetFunctionDoc(name) Optional~String~
    -ObjectPtr~Library~ lib_
  }
  class DSOLibrary {
    +GetSymbol(name) void*
    -void* lib_handle_
  }
  class SystemLibrary {
    +GetSymbol(name) void*
    +GetSymbolWithSymbolPrefix(name) void*
    -String symbol_prefix_
  }

  Object <|-- ModuleObj : type_index=73
  Object <|-- Library : no type index
  ModuleObj <|-- LibraryModuleObj
  Library <|-- DSOLibrary
  Library <|-- SystemLibrary
  Module --> ModuleObj : wraps (ObjectRef)
  LibraryModuleObj --> Library : owns (ObjectPtr)
```

## Module Loading Flow (DSO)

```mermaid
flowchart TD
  A["Module::LoadFromFile('lib.so')"] --> B["Extract format: 'so'"]
  B --> C["Lookup 'ffi.Module.load_from_file.so'<br/>in global registry"]
  C --> D["CreateLibraryModule(make_object<DSOLibrary>(path))"]
  D --> E["DSOLibrary::Load(path)<br/>dlopen / LoadLibraryW"]
  E --> F["ContextSymbolRegistry::InitContextSymbols(lib)<br/>Patch known symbols into DSO"]
  F --> G{"__tvm_ffi__library_bin<br/>symbol exists?"}
  G -->|Yes| H["ProcessLibraryBin:<br/>Deserialize import tree (CSR)<br/>Create sub-modules from bytes"]
  G -->|No| I["Wrap as single LibraryModuleObj"]
  H --> J["Root Module"]
  I --> J
```

## Function Lookup Flow

```mermaid
flowchart TD
  A["mod->GetFunction(name, query_imports=true)"] --> B{"this->GetFunction(name)<br/>found?"}
  B -->|Yes| C["Return function"]
  B -->|No| D{"query_imports?"}
  D -->|No| E["Return nullopt"]
  D -->|Yes| F["For each import in imports_:<br/>import->GetFunction(name, true)"]
  F --> G{"Found in any import?"}
  G -->|Yes| C
  G -->|No| E

  H["TVMFFIEnvModLookupFromImports(ctx, name)"] --> I{"Check<br/>import_lookup_cache_?"}
  I -->|Hit| J["Return cached Function*"]
  I -->|Miss| K["Search imports recursively"]
  K --> L{"Found?"}
  L -->|No| M["Try global registry:<br/>Function::GetGlobal(name)"]
  L -->|Yes| N["Cache in import_lookup_cache_"]
  M --> O{"Found?"}
  O -->|Yes| N
  O -->|No| P["Throw RuntimeError"]
  N --> J
```

## Import Cycle Detection

```mermaid
flowchart TD
  A["mod->ImportModule(other)"] --> B["BFS from 'other':<br/>visited = {other}<br/>stack = [other]"]
  B --> C["Pop node, iterate its imports"]
  C --> D{"Any unvisited import?"}
  D -->|Yes| E["Add to visited and stack"]
  E --> C
  D -->|No| F{"Stack empty?"}
  F -->|No| C
  F -->|Yes| G{"'this' in visited?"}
  G -->|Yes| H["Throw RuntimeError:<br/>Cyclic dependency detected"]
  G -->|No| I["imports_.push_back(other)"]
```

## C API Symbol Taxonomy

```mermaid
flowchart LR
  subgraph "Host Environment (TVMFFIEnv*)"
    A1["TVMFFIEnvCheckSignals"]
    A2["TVMFFIEnvRegisterCAPI"]
    A3["TVMFFIEnvSetCurrentStream"]
    A4["TVMFFIEnvGetCurrentStream"]
  end
  subgraph "Module Environment (TVMFFIEnvMod*)"
    B1["TVMFFIEnvModLookupFromImports"]
    B2["TVMFFIEnvModRegisterContextSymbol"]
    B3["TVMFFIEnvModRegisterSystemLibSymbol"]
  end
```

## Symbol Prefix Convention

```mermaid
flowchart TD
  subgraph "User-Exported Functions"
    U1["Source: ExportName"]
    U2["Symbol: __tvm_ffi_ExportName"]
  end
  subgraph "Internal/Special Symbols"
    I1["__tvm_ffi__library_ctx"]
    I2["__tvm_ffi__library_bin"]
    I3["__tvm_ffi__metadata_NAME"]
    I4["__tvm_ffi__doc_NAME"]
  end
  subgraph "Lookup Layer"
    L1["GetFunction('ExportName')"]
    L2["GetSymbolWithSymbolPrefix prepends __tvm_ffi_"]
    L3["SystemLibrary: tries prefixed first, falls back to unprefixed"]
  end
  U1 -->|"TVM_FFI_DLL_EXPORT_TYPED_FUNC"| U2
  L1 --> L2
  L2 --> U2
  L2 --> L3
```

## Binary Import-Tree Layout

```mermaid
block-beta
  columns 1
  block:header["Header (8 bytes)"]
    nbytes["nbytes : uint64_t"]
  end
  block:csr["Import Tree (CSR)"]
    columns 2
    indptr["indptr : vec<uint64_t>"]
    children["child_indices : vec<uint64_t>"]
  end
  block:modules["Module Entries (repeated)"]
    columns 2
    kind["kind : string"]
    data["bytes : string (if kind != '_lib')"]
  end
```

## Evidence

- `symbol::tvm_ffi_symbol_prefix` constant: `include/tvm/ffi/extra/module.h` @ `40e8a51`
- `Library::GetSymbolWithSymbolPrefix`: `src/ffi/extra/module_internal.h` @ `40e8a51`
- SystemLibrary prefix-tolerant lookup: `src/ffi/extra/library_module_system_lib.cc` @ `8068d1d`
- Stream API renames (`TVMFFIEnvSetCurrentStream`): `include/tvm/ffi/extra/c_env_api.h` @ `a08fa6e`
- `ModuleObj` class: `include/tvm/ffi/extra/module.h` @ `538bef4`
- `Library` abstract class: `src/ffi/extra/module_internal.h` @ `538bef4`
- `DSOLibrary`: `src/ffi/extra/library_module_dynamic_lib.cc` @ `538bef4`
- `SystemLibrary`: `src/ffi/extra/library_module_system_lib.cc` @ `538bef4`
- `LibraryModuleObj`: `src/ffi/extra/library_module.cc` @ `538bef4`
- `ProcessLibraryBin`: `src/ffi/extra/library_module.cc` lines 109-163 @ `538bef4`
- C API renames (`TVMFFIEnvMod*`): `include/tvm/ffi/extra/c_env_api.h` @ `023ea44`
- `EnvCAPIRegistry` moved to `src/ffi/extra/env_c_api.cc` @ `023ea44`
