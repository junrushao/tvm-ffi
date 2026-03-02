---
diagram: "0016"
title: "Python FFI Protocol Dispatch Flow"
created: "2025-10-16"
last_updated: "2025-10-20"
related_designs:
  - ".memory/designs/0022-python-ffi-interop-protocols.md"
  - ".memory/designs/0011-cython-binding-layer.md"
source_commits:
  - "4bc89254"
  - "8873700a"
  - "42e0612"
  - "b0537f04"
  - "5e648f05"
  - "0f8bf9fc"
---

# Python FFI Protocol Dispatch Flow

This diagram shows how the Cython `TVMFFIPyArgSetterFactory` dispatches argument
conversion based on duck-typing protocols. Protocol checks happen once per Python
type and are cached for subsequent calls.

```mermaid
flowchart TD
    A["Function.__call__(arg)"] --> B["TVMFFIPyCallManager::SetArgument()"]
    B --> C{"Cached setter\nfor type(arg)?"}
    C -- "Yes" --> D["Call cached setter"]
    C -- "No (cache miss)" --> E["TVMFFIPyArgSetterFactory(arg_class)"]

    E --> F{"Is FFI Object\nor Function?"}
    F -- "Yes" --> G["Dedicated FFI setter"]

    F -- "No" --> H{"hasattr\n__tvm_ffi_object__?"}
    H -- "Yes" --> I["TVMFFIPyArgSetterFFI\nObjectCompatible_"]

    H -- "No" --> J{"hasattr\n__tvm_ffi_opaque_ptr__?"}
    J -- "Yes" --> K["TVMFFIPyArgSetterFFI\nOpaquePtrCompatible_"]

    J -- "No" --> L{"hasattr\n__cuda_stream__?"}
    L -- "Yes" --> M["TVMFFIPyArgSetter\nCUDAStream_"]

    L -- "No" --> L2{"hasattr\n__dlpack_data_type__?"}
    L2 -- "Yes" --> M2["TVMFFIPyArgSetter\nDLPackDataTypeProtocol_"]

    L2 -- "No" --> L3{"hasattr __dlpack_device__\nAND NOT __dlpack__?"}
    L3 -- "Yes" --> M3["TVMFFIPyArgSetter\nDLPackDeviceProtocol_"]

    L3 -- "No" --> N{"hasattr\n__dlpack__?"}
    N -- "Yes" --> O["DLPack tensor conversion\n(Exchange API or PyCapsule)"]

    N -- "No" --> P["Wrap as\nOpaquePyObject"]

    G --> Q["Cache setter\nfor type(arg)"]
    I --> Q
    K --> Q
    M --> Q
    M2 --> Q
    M3 --> Q
    O --> Q
    P --> Q
    Q --> D

    D --> R["Packed arg ready\nfor FFI call"]

    subgraph "Protocol Priority (high to low)"
        direction LR
        S1["FFI native"] ~~~ S2["__tvm_ffi_object__"]
        S2 ~~~ S3["__tvm_ffi_opaque_ptr__"]
        S3 ~~~ S4["__cuda_stream__"]
        S4 ~~~ S4b["__dlpack_data_type__"]
        S4b ~~~ S4c["__dlpack_device__"]
        S4c ~~~ S5["__dlpack__"]
        S5 ~~~ S6["OpaquePyObject"]
    end
```

## Protocol Return Types

```mermaid
classDiagram
    class TVMFFIPyArgSetterFactory {
        +dispatch(arg_class) TVMFFIPyArgSetter
    }

    class __tvm_ffi_object__ {
        <<protocol>>
        +__tvm_ffi_object__() Object
    }
    note for __tvm_ffi_object__ "Returns cached FFI Object\nSetter extracts handle\nType index: kTVMFFIObject+"

    class __tvm_ffi_opaque_ptr__ {
        <<protocol>>
        +__tvm_ffi_opaque_ptr__() int
    }
    note for __tvm_ffi_opaque_ptr__ "Returns raw pointer as int\nType index: kTVMFFIOpaquePtr"

    class __cuda_stream__ {
        <<protocol>>
        +__cuda_stream__() int
    }
    note for __cuda_stream__ "Returns CUDA stream handle\nType index: kTVMFFIOpaquePtr\nAligns with NVIDIA protocol"

    class __dlpack_data_type__ {
        <<protocol>>
        +__dlpack_data_type__() tuple
    }
    note for __dlpack_data_type__ "Returns (type_code, bits, lanes)\nConverts to DLDataType\nDLPack dtype exchange"

    class __dlpack_device__ {
        <<protocol>>
        +__dlpack_device__() tuple
    }
    note for __dlpack_device__ "Returns (device_type, device_id)\nConverts to TVMFFIDevice\nOnly when __dlpack__ absent"

    class __dlpack__ {
        <<protocol>>
        +__dlpack__() PyCapsule
        +__dlpack_device__() tuple
    }
    note for __dlpack__ "Standard DLPack tensor exchange\nFallback if no C exchange API"

    TVMFFIPyArgSetterFactory --> __tvm_ffi_object__
    TVMFFIPyArgSetterFactory --> __tvm_ffi_opaque_ptr__
    TVMFFIPyArgSetterFactory --> __cuda_stream__
    TVMFFIPyArgSetterFactory --> __dlpack_data_type__
    TVMFFIPyArgSetterFactory --> __dlpack_device__
    TVMFFIPyArgSetterFactory --> __dlpack__
```
