# Two-Tier Symbol Resolution in Module System

Source: commit `40e8a519f5270dfb18436b2f26c2d691cf24c9c1` (symbol prefix), `315f4bb00eac8b4d26cdcd6839fb1a077bab6976` (SystemLibrary fix)
Related: [0013-module-system](../designs/0013-module-system.md), [0008-module-export-system](../designs/0008-module-export-system.md), [ADR 0027](../ADRs/0027-ffi-symbol-prefix.md)

## LibraryModuleObj Function Discovery

```mermaid
sequenceDiagram
    participant Caller as Python/C++ Caller
    participant LMO as LibraryModuleObj
    participant Lib as Library (abstract)
    participant DSO as DSOLibrary
    participant Sys as SystemLibrary

    Caller->>LMO: GetFunction("foo")
    LMO->>Lib: GetSymbolWithSymbolPrefix("foo")

    alt DSOLibrary path
        Lib->>DSO: GetSymbolWithSymbolPrefix("foo")
        Note over DSO: Base class default:<br/>GetSymbol("__tvm_ffi_" + "foo")
        DSO->>DSO: dlsym(handle, "__tvm_ffi_foo")
        DSO-->>LMO: void* faddr
    else SystemLibrary path
        Lib->>Sys: GetSymbolWithSymbolPrefix("foo")
        Note over Sys: Custom override:<br/>Try "__tvm_ffi_" + prefix_ + "foo"
        Sys->>Sys: registry.lookup("__tvm_ffi_" + prefix_ + "foo")
        alt Found
            Sys-->>LMO: void* faddr
        else Not found (fallback)
            Sys->>Sys: registry.lookup(prefix_ + "foo")
            Sys-->>LMO: void* faddr or nullptr
        end
    end

    LMO->>LMO: Wrap faddr as Function<br/>with captured Module ref
    LMO-->>Caller: Optional<Function>
```

## Symbol Naming Convention

```mermaid
graph TD
    subgraph "User-Exported Functions"
        UF["__tvm_ffi_main<br/>__tvm_ffi_add_one<br/>__tvm_ffi_my_kernel"]
    end
    subgraph "Internal Infrastructure Symbols"
        IS["__tvm_ffi__library_ctx<br/>__tvm_ffi__library_bin<br/>__tvm_ffi__metadata_prefix"]
    end
    subgraph "Naming Rule"
        NR["User: __tvm_ffi_ + name<br/>(single underscore)<br/><br/>Internal: __tvm_ffi__ + name<br/>(double underscore)"]
    end

    UF --- NR
    IS --- NR
```

## SystemLibrary Prefix-Tolerant Lookup

```mermaid
flowchart TD
    A["GetSymbol(name)"] --> B{"Try: prefix_ + name"}
    B -->|"Found"| Z["Return symbol"]
    B -->|"Not found"| C{"Try: name as-is"}
    C -->|"Found"| Z
    C -->|"Not found"| Y["Return nullptr"]

    D["GetSymbolWithSymbolPrefix(name)"] --> E{"Try: __tvm_ffi_ + prefix_ + name"}
    E -->|"Found"| Z2["Return symbol"]
    E -->|"Not found"| F{"Try: prefix_ + name"}
    F -->|"Found"| Z2
    F -->|"Not found"| G{"Try: __tvm_ffi_ + name"}
    G -->|"Found"| Z2
    G -->|"Not found"| Y2["Return nullptr"]
```
