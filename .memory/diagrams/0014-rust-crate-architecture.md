---
diagram: "0014"
title: "Rust Crate Workspace Architecture and Type Mapping"
format: "mermaid"
source_commits:
  - "09477ce10de566f8cf511cce7dfe56e77759f100"
related_designs:
  - ".memory/designs/0017-rust-ffi-binding-layer.md"
---

# Rust Crate Workspace Architecture and Type Mapping

## Three-Crate Workspace

```mermaid
flowchart TD
    subgraph Workspace["rust/ workspace"]
        direction TB
        subgraph SYS["tvm-ffi-sys"]
            direction LR
            c_api_rs["c_api.rs<br/>#[repr(C)] ABI structs<br/>extern C declarations"]
            dlpack_rs["dlpack.rs<br/>DLPack types"]
            c_env_rs["c_env_api.rs<br/>Environment APIs"]
            build_sys["build.rs<br/>Links libtvm_ffi"]
        end
        subgraph MACROS["tvm-ffi-macros (proc-macro)"]
            direction LR
            derive_obj["#[derive(Object)]<br/>Generates ObjectCore impl"]
            derive_ref["#[derive(ObjectRef)]<br/>Generates ObjectRefCore<br/>+ AnyCompatible impl"]
        end
        subgraph FFI["tvm-ffi"]
            direction LR
            any_mod["any.rs<br/>Any, AnyView"]
            obj_mod["object.rs<br/>ObjectArc, ObjectCore<br/>Native inc_ref/dec_ref"]
            traits_mod["type_traits.rs<br/>AnyCompatible trait"]
            func_mod["function.rs<br/>Function, FunctionObj"]
            str_mod["string.rs<br/>String, Bytes (SSO)"]
            err_mod["error.rs<br/>Error, ErrorKind"]
            macro_mod["macros.rs<br/>check_safe_call!, bail!<br/>into_typed_fn!, etc."]
            tensor_mod["collections/<br/>Tensor, Shape, Array"]
            mod_mod["extra/module.rs<br/>Module"]
            build_ffi["build.rs<br/>tvm-ffi-config, examples"]
        end
    end

    SYS -->|"depends on"| FFI
    MACROS -->|"proc-macro dep"| FFI
    build_sys -->|"tvm-ffi-config --libdir"| PYTHON["Python package<br/>(tvm-ffi-config CLI)"]
    FFI -->|"links"| NATIVE["libtvm_ffi.so<br/>libtvm_ffi_testing.so"]
```

## Type Mapping: Rust to C++ to C ABI

```mermaid
classDiagram
    class RustAny["Rust: Any / AnyView&lt;'a&gt;"] {
        -TVMFFIAny data
        +try_as~T~() Option~T~
        +type_index() i32
    }
    class CppAny["C++: Any / AnyView"] {
        -TVMFFIAny data
        +as~T~() T
        +cast~T~() T
    }
    class CAny["C: TVMFFIAny"] {
        +int32_t type_index
        +uint32_t small_str_len
        +union data_union 8B
    }

    class RustObjectArc["Rust: ObjectArc&lt;T&gt;"] {
        -NonNull~T~ ptr
        +strong_count() usize
        +clone() inc_ref native
        +drop() dec_ref native
    }
    class CppObjectPtr["C++: ObjectPtr&lt;T&gt;"] {
        -T* data_
        +use_count() int
    }
    class CObject["C: TVMFFIObject"] {
        +uint64_t combined_ref_count
        +int32_t type_index
        +deleter fn ptr
    }

    class RustFunction["Rust: Function"] {
        -ObjectArc~FunctionObj~ data
        +call_packed() Result~Any~
        +from_typed() Function
        +get_global() Function
    }
    class CppFunction["C++: Function"] {
        -ObjectPtr~FunctionObj~ data_
        +operator()() Any
    }
    class CFunc["C: TVMFFIFunctionCell"] {
        +safe_call fn ptr
        +cpp_call void*
    }

    class RustString["Rust: String / Bytes"] {
        -TVMFFIAny data
        +as_str() str
        Note: SSO <=7B inline
    }
    class CppString["C++: String / Bytes"] {
        -TVMFFIAny data_
        +data() char*
        Note: SSO <=7B inline
    }

    CAny <.. RustAny : repr_C match
    CAny <.. CppAny : layout match
    CObject <.. RustObjectArc : native atomics
    CObject <.. CppObjectPtr : native atomics
    CFunc <.. RustFunction : calls safe_call
    CFunc <.. CppFunction : calls cpp_call
    RustString .. CppString : identical TVMFFIAny layout
```

## Ref-Counting Flow in Rust

```mermaid
flowchart TD
    A["ObjectArc::clone()"] -->|"fetch_add(1, Relaxed)"| B["Strong count += 1"]

    C["ObjectArc::drop()"] -->|"fetch_sub(STRONG_ONE, Relaxed)"| D{"old == BOTH_ONE?"}
    D -->|Yes| E["fence(Acquire)<br/>deleter(Both)<br/><b>Fast path</b>: single owner, no weak refs"]
    D -->|No| F{"strong bits == 1?"}
    F -->|Yes| G["fence(Acquire)<br/>deleter(Strong)<br/>fetch_sub(WEAK_ONE, Release)"]
    G --> H{"weak count == 0?"}
    H -->|Yes| I["fence(Acquire)<br/>deleter(Weak)<br/>Free memory"]
    H -->|No| J["Memory kept alive<br/>for weak refs"]
    F -->|No| K["No action<br/>Non-final decrement"]
```

## CallbackFunctionObjImpl Struct Inheritance

```mermaid
classDiagram
    class TVMFFIObject {
        +AtomicU64 combined_ref_count
        +i32 type_index
        +u32 padding
        +deleter fn ptr
    }
    class Object {
        -TVMFFIObject header
    }
    class FunctionObj {
        -Object object
        -TVMFFIFunctionCell cell
    }
    class CallbackFunctionObjImpl_F_ {
        -FunctionObj function
        -F callback
        Note: repr_C struct inheritance
    }

    TVMFFIObject <|-- Object : offset 0
    Object <|-- FunctionObj : offset 0
    FunctionObj <|-- CallbackFunctionObjImpl_F_ : offset 0

    note for CallbackFunctionObjImpl_F_ "ObjectArc created as CallbackFunctionObjImpl<F><br/>then cast to ObjectArc<FunctionObj><br/>Custom deleter drops F correctly"
```

## String/Bytes Dual Representation

```mermaid
flowchart TD
    INPUT["Input: &str / &[u8]"]
    INPUT --> CHECK{"len <= 7?"}
    CHECK -->|Yes| SMALL["SmallStr/SmallBytes<br/>type_index = kTVMFFISmallStr/kTVMFFISmallBytes<br/>small_str_len = len<br/>data inline in v_bytes[0..len]"]
    CHECK -->|No| HEAP["Heap StringObj/BytesObj<br/>type_index = kTVMFFIStr/kTVMFFIBytes<br/>ObjectArc::new_with_extra_items()<br/>Trailing bytes after TVMFFIByteArray + null terminator"]

    SMALL --> REPR["16-byte TVMFFIAny<br/>No heap allocation<br/>No ref counting"]
    HEAP --> REPR2["16-byte TVMFFIAny<br/>v_obj -> heap object<br/>Ref counted via ObjectArc"]
```

## Evidence

- Three-crate workspace: `rust/Cargo.toml` @ `09477ce`
- `tvm-ffi-sys` ABI structs: `rust/tvm-ffi-sys/src/c_api.rs` @ `09477ce`
- `tvm-ffi-sys/build.rs` with `tvm-ffi-config`: `rust/tvm-ffi-sys/build.rs` @ `09477ce`
- `#[derive(Object)]` / `#[derive(ObjectRef)]`: `rust/tvm-ffi-macros/src/object_macros.rs` @ `09477ce`
- Native ref-counting: `rust/tvm-ffi/src/object.rs` `unsafe_` module @ `09477ce`
- `CallbackFunctionObjImpl<F>`: `rust/tvm-ffi/src/function.rs` @ `09477ce`
- String/Bytes dual representation: `rust/tvm-ffi/src/string.rs` @ `09477ce`
- `ObjectArc::new` and `new_with_extra_items`: `rust/tvm-ffi/src/object.rs` @ `09477ce`
