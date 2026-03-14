# Rust Crate Architecture and Type Mapping

Source: commit `09477ce10de566f8cf511cce7dfe56e77759f100`
Related: [0022-rust-bindings](../designs/0022-rust-bindings.md), [ADR 0043](../ADRs/0043-native-rust-ref-counting.md), [ADR 0044](../ADRs/0044-manual-c-api-transcription-in-rust.md)

## Three-Crate Workspace Dependency Graph

```mermaid
graph TD
    subgraph "Rust Workspace (rust/)"
        TF["tvm-ffi<br/><i>Safe public API</i>"]
        SYS["tvm-ffi-sys<br/><i>Raw C ABI #[repr(C)]</i>"]
        MAC["tvm-ffi-macros<br/><i>Proc-macros</i>"]
    end

    subgraph "External Dependencies"
        LIB["libtvm_ffi.so/.dylib<br/><i>C++ shared library</i>"]
        CFG["tvm-ffi-config --libdir<br/><i>Python CLI tool</i>"]
        PASTE["paste crate<br/><i>Token pasting</i>"]
    end

    TF -->|"depends on"| SYS
    TF -->|"depends on"| MAC
    MAC -->|"depends on"| PASTE
    SYS -->|"links at runtime"| LIB
    SYS -.->|"build.rs queries"| CFG
    TF -.->|"build.rs queries"| CFG
```

## Rust-to-C++ Type Mapping

```mermaid
graph LR
    subgraph "Rust (tvm-ffi)"
        R_ANY["Any / AnyView&lt;'a&gt;"]
        R_OBJ["ObjectArc&lt;T&gt;"]
        R_FUNC["Function"]
        R_ERR["Error"]
        R_STR["String / Bytes"]
        R_ARR["Array&lt;T&gt;"]
        R_TRAIT["AnyCompatible<br/><i>unsafe trait</i>"]
        R_OC["ObjectCore<br/><i>unsafe trait</i>"]
        R_ORC["ObjectRefCore<br/><i>unsafe trait</i>"]
    end

    subgraph "C ABI (tvm-ffi-sys)"
        C_ANY["TVMFFIAny<br/>#[repr(C)]"]
        C_OBJ["TVMFFIObject<br/>AtomicU64 + deleter"]
        C_FUNC["TVMFFIFunctionCell<br/>safe_call + cxx_call"]
        C_ERR["TVMFFIErrorCell<br/>kind + msg + bt"]
        C_BA["TVMFFIByteArray<br/>*data + size"]
    end

    subgraph "C++ (include/tvm/ffi/)"
        CPP_ANY["Any / AnyView"]
        CPP_OBJ["ObjectPtr&lt;T&gt;"]
        CPP_FUNC["Function"]
        CPP_ERR["Error"]
        CPP_STR["String / Bytes"]
        CPP_ARR["Array&lt;T&gt;"]
        CPP_TT["TypeTraits&lt;T&gt;"]
    end

    R_ANY ---|"wraps"| C_ANY
    R_OBJ ---|"wraps"| C_OBJ
    R_FUNC ---|"wraps"| C_FUNC
    R_ERR ---|"wraps"| C_ERR
    R_STR ---|"SSO via"| C_ANY
    R_STR ---|"heap via"| C_BA
    R_ARR ---|"ArrayObj #[repr(C)]"| CPP_ARR

    C_ANY ---|"identical layout"| CPP_ANY
    C_OBJ ---|"identical layout"| CPP_OBJ
    C_FUNC ---|"identical layout"| CPP_FUNC
    C_ERR ---|"identical layout"| CPP_ERR

    R_TRAIT -.->|"analogous to"| CPP_TT
    R_OC -.->|"analogous to"| CPP_OBJ
```

## ObjectArc Lifecycle: Native Ref-Counting

```mermaid
sequenceDiagram
    participant User as Rust Code
    participant Arc as ObjectArc&lt;T&gt;
    participant Header as TVMFFIObject.combined_ref_count
    participant Del as Deleter (extern "C")

    Note over Header: Initial: strong=1, weak=1<br/>(COMBINED_REF_COUNT_BOTH_ONE)

    User->>Arc: .clone()
    Arc->>Header: fetch_add(1, Relaxed)
    Note over Header: strong=2, weak=1

    User->>Arc: drop first clone
    Arc->>Header: fetch_sub(STRONG_ONE, Relaxed)
    Note over Header: strong=1, weak=1

    User->>Arc: drop last clone
    Arc->>Header: fetch_sub(STRONG_ONE, Relaxed)
    Note over Header: old was BOTH_ONE
    Arc->>Arc: fence(Acquire)
    Arc->>Del: deleter(ptr, Both=0b11)
    Del->>Del: drop_in_place(obj) + dealloc(ptr)
    Note over Header: FREED
```

## CallbackFunctionObjImpl Memory Layout

```mermaid
block-beta
    columns 1
    block:layout["CallbackFunctionObjImpl&lt;F&gt; (#[repr(C)])"]
        columns 1
        block:funcobj["FunctionObj"]
            columns 2
            obj["Object<br/>(TVMFFIObject header, 24B)"]
            cell["TVMFFIFunctionCell<br/>(safe_call + cxx_call, 16B)"]
        end
        cb["F: Fn(&[AnyView]) -> Result&lt;Any&gt;<br/>(Rust closure, variable size)"]
    end

    style funcobj fill:#e8f4fd
    style cb fill:#fdf2e8
```

The `safe_call` pointer in `TVMFFIFunctionCell` points to a monomorphized `invoke_callback` function that casts the handle back to `CallbackFunctionObjImpl<F>` to call the closure. The `ObjectArc` is created as `ObjectArc<CallbackFunctionObjImpl<F>>` (so the deleter knows the full type for drop), then transmuted to `ObjectArc<FunctionObj>` via `into_raw`/`from_raw` pointer casting.

## String/Bytes Dual Storage

```mermaid
graph TD
    subgraph "Small Path (<=7 bytes)"
        SA["TVMFFIAny"]
        SA --> |"type_index"| SI["kTVMFFISmallStr / kTVMFFISmallBytes"]
        SA --> |"small_str_len"| SL["length (0-7)"]
        SA --> |"data_union.v_bytes"| SD["inline [u8; 8]"]
    end

    subgraph "Large Path (>7 bytes)"
        LA["TVMFFIAny"]
        LA --> |"type_index"| LI["kTVMFFIStr / kTVMFFIBytes"]
        LA --> |"data_union.v_obj"| LP["*mut StringObj/BytesObj"]
        LP --> OBJ["ObjectArc&lt;StringObj&gt;"]
        OBJ --> HDR["TVMFFIObject header"]
        OBJ --> BA["TVMFFIByteArray {data, size}"]
        OBJ --> TRAIL["trailing u8 data + null terminator"]
        BA -.-> |"data ptr"| TRAIL
    end
```
