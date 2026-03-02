---
diagram: "0015"
title: "TensorView Type Hierarchy and TypeSchema Metadata Flow"
related_designs:
  - ".memory/designs/0018-tensorview-non-owning-tensor-view.md"
  - ".memory/designs/0019-typeschema-metadata-system.md"
  - ".memory/designs/0020-external-function-construction.md"
source_commits:
  - "1ec623678adea0ddba482d8d56d4ab2be440e694"
  - "28fe3cc7fc23b725ddefbb3ca1e1899a7dfd530c"
  - "a15364746d60766bfaf6e0a6ccdb2353ceee7d7d"
  - "f6303b23fd97909b59f6ff67b85f2203371f5db1"
---

# TensorView Type Hierarchy and TypeSchema Metadata Flow

## TensorView in the Type System

```mermaid
classDiagram
    class DLTensor {
        +void* data
        +DLDevice device
        +int32_t ndim
        +DLDataType dtype
        +int64_t* shape
        +int64_t* strides
        +uint64_t byte_offset
    }

    class TensorObj {
        +DLTensor dl_tensor
        +int64_t* shape_data_ (inline)
        +int64_t* strides_data_ (inline)
    }

    class Tensor {
        +ShapeView shape()
        +ShapeView strides()
        +void* data_ptr()
        +DLDataType dtype()
    }

    class TensorView {
        -DLTensor tensor_
        +TensorView(const Tensor&)
        +TensorView(const DLTensor*)
        +TensorView(Tensor&&) = delete
        +ShapeView shape()
        +ShapeView strides()
        +void* data_ptr()
        +bool IsContiguous()
    }

    class TypeTraits_TensorView {
        +kTVMFFIDLTensorPtr type_index
        +TryCastFromAnyView()
        No MoveToAny
        No MoveFromAny
    }

    TensorObj --|> ObjectObj : inherits
    Tensor --> TensorObj : ref wrapper
    TensorView --> DLTensor : copies struct
    TensorView ..> Tensor : accepts (const ref)
    TensorView ..> DLTensor : accepts (pointer)
    TypeTraits_TensorView --> TensorView : specializes for

    note for TensorView "Non-owning: does NOT extend\ndata lifetime. Cannot be\nstored in Any or containers."
```

## TypeSchema Metadata Generation Flow

```mermaid
flowchart TD
    A["C++ Type T\n(e.g., Array&lt;String&gt;)"] --> B["TypeSchema&lt;T&gt;::v()"]
    B --> C["JSON string\n{\"type\":\"ffi.Array\",\"args\":[{\"type\":\"ffi.String\"}]}"]

    D["ObjectDef&lt;T&gt;::def_ro(name, &T::field)"] --> E["TypeSchema&lt;FieldType&gt;::v()"]
    E --> F["Metadata(\"type_schema\", json)"]
    F --> G["TVMFFIFieldInfo.metadata"]

    H["GlobalDef::def(name, func)"] --> I["TypeSchema&lt;FuncType&gt;::v()"]
    I --> J["Metadata(\"type_schema\", json)"]
    J --> K["TVMFFIMethodInfo.metadata"]

    G --> L["Python: TypeField.metadata[\"type_schema\"]"]
    K --> M["Python: get_global_func_metadata(name)"]

    L --> N["TypeSchema.from_json_str(json)"]
    M --> N
    N --> O["TypeSchema(origin='list', args=(TypeSchema('str'),))"]
    O --> P["repr() → 'list[str]'"]
    O --> Q["repr(ty_map=...) → 'Sequence[str]'"]

    style A fill:#e1f5fe
    style C fill:#fff3e0
    style O fill:#e8f5e9
```

## External Function Construction Paths

```mermaid
flowchart TD
    subgraph ExternC["__from_extern_c__ Path"]
        EC1["Python: Function.__from_extern_c__(ptr, keep_alive=engine)"]
        EC2["Py_IncRef(engine)"]
        EC3["TVMFFIFunctionCreate(\n  safe_call=ptr,\n  handle=engine,\n  deleter=TVMFFIPyObjectDeleter)"]
        EC4["FFI Function"]
        EC1 --> EC2 --> EC3 --> EC4
    end

    subgraph MLIR["__from_mlir_packed_safe_call__ Path"]
        ML1["Python: Function.__from_mlir_packed_safe_call__(ptr, keep_alive=engine)"]
        ML2["TVMFFIPyMLIRPackedSafeCallCreate(\n  mlir_fn=ptr, keep_alive=engine)"]
        ML3["TVMFFIFunctionCreate(\n  safe_call=Invoke,\n  handle=adapter,\n  deleter=Deleter)"]
        ML4["FFI Function"]
        ML1 --> ML2 --> ML3 --> ML4
    end

    subgraph Calling["MLIR Adapter Calling Convention"]
        CA1["TVMFFIPyMLIRPackedSafeCall::Invoke(\n  handle, args, num_args, rv)"]
        CA2["Build void* array:\n  [0]=handle, [1]=args,\n  [2]=&num_args, [3]=rv,\n  [4]=&ret_code"]
        CA3["mlir_packed_safe_call_(array)"]
        CA4["return ret_code"]
        CA1 --> CA2 --> CA3 --> CA4
    end

    subgraph GIL["GIL Safety (TVMFFIPyObjectDeleter)"]
        G1{"Py_GIL_DISABLED?"}
        G2["No-op\n(free-threaded)"]
        G3["PyGILState_Ensure()\n→ Py_DecRef()\n→ PyGILState_Release()"]
        G1 -->|Yes| G2
        G1 -->|No| G3
    end

    EC4 -.-> Calling
    ML4 -.-> Calling

    style ExternC fill:#fce4ec
    style MLIR fill:#e8eaf6
    style Calling fill:#fff8e1
    style GIL fill:#e0f2f1
```
