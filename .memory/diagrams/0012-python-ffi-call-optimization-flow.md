---
diagram: "0012"
title: "Python FFI Call Optimization Flow"
format: "mermaid"
source_commits:
  - "38d2cdaa03adc26a630e9cc3cc99b3c7e9f55097"
  - "f81ab9c25ae4d2a42706747c50c5c410c51d6cdd"
  - "043d9f647677cc3b4a8baba198a2ced45f99cc98"
related_designs:
  - ".memory/designs/0015-python-ffi-call-optimization.md"
---

# Python FFI Call Optimization Flow

## Optimized Call Path (TVMFFIPyFuncCall)

```mermaid
sequenceDiagram
    participant Py as Python Caller
    participant Fn as Function (cdef class)
    participant CM as TVMFFIPyCallManager<br/>(thread-local)
    participant DM as Dispatch Map<br/>(PyTypeObject* -> Setter)
    participant S as TVMFFIPyArgSetter<br/>(C function ptr)
    participant Ctx as TVMFFIPyCallContext<br/>(RAII)
    participant CAPI as TVMFFIFunctionCall

    Py->>Fn: func(*args)
    Fn->>CM: TVMFFIPyFuncCall(factory, handle, tuple, ...)
    CM->>Ctx: Allocate from TVMFFIPyCallStack (4KB)

    loop For each argument
        CM->>DM: Lookup Py_TYPE(arg)
        alt Cache hit
            DM-->>CM: Return cached setter
        else Cache miss
            CM->>Fn: factory(arg, &setter)
            Fn-->>CM: New TVMFFIPyArgSetter
            CM->>DM: Cache setter for PyTypeObject*
        end
        CM->>S: setter(ctx, arg, out)
        S-->>CM: Set TVMFFIAny fields
    end

    Note over CM,CAPI: Set stream/allocator context if detected
    alt release_gil = True
        CM->>CAPI: Py_BEGIN_ALLOW_THREADS
        CM->>CAPI: TVMFFIFunctionCall(handle, packed_args, n, result)
        CM->>CAPI: Py_END_ALLOW_THREADS
    else release_gil = False
        CM->>CAPI: TVMFFIFunctionCall(handle, packed_args, n, result)
    end
    Note over CM,CAPI: Restore stream/allocator context

    Ctx-->>CM: ~TVMFFIPyCallContext: DecRef temps, restore stack
    CM-->>Fn: Return (ret_code, result)
    Fn-->>Py: Convert result to Python object
```

## Argument Setter Dispatch (Cached Per-Type)

```mermaid
flowchart TD
    A["SetArgument(factory, ctx, py_arg, out)"] --> B{"Py_TYPE(arg) in<br/>dispatch_map?"}
    B -->|Yes: Cache Hit| C["Call cached setter(ctx, arg, out)"]
    B -->|No: Cache Miss| D["factory(arg, &setter)"]
    D --> E["dispatch_map[PyTypeObject*] = setter"]
    E --> C

    C --> F{"Setter Type"}
    F -->|"TVMFFIPyArgSetterInt_"| G["out.type_index = kTVMFFIInt<br/>out.v_int64 = PyLong_AsLongLong(arg)"]
    F -->|"TVMFFIPyArgSetterFloat_"| H["out.type_index = kTVMFFIFloat<br/>out.v_float64 = PyFloat_AsDouble(arg)"]
    F -->|"TVMFFIPyArgSetterBool_"| I["out.type_index = kTVMFFIBool<br/>out.v_int64 = PyLong_AsLong(arg)"]
    F -->|"TVMFFIPyArgSetterNone_"| J["out.type_index = kTVMFFINone<br/>out.v_int64 = 0"]
    F -->|"Object setter"| K["out.type_index = obj.type_index<br/>out.v_ptr = chandle"]
    F -->|"DLPack setter"| L["DLPackExchangeAPI.from_pyobject<br/>or fallback to __dlpack__"]
    F -->|"Container setter"| M["TVMFFIPyConstructorCall<br/>(recursive)"]
    F -->|"String setter"| N["TVMFFIStringFromByteArray"]
    F -->|"Bytes setter"| O["TVMFFIBytesFromByteArray"]
    F -->|"General setter"| P["__tvm_ffi_value__ protocol<br/>or wrap as OpaquePyObject"]
```

## Nested Container Conversion (TVMFFIPyConstructorCall)

```mermaid
flowchart TD
    A["Python list [1, 2.0, 'hello']"] --> B["TVMFFIPyArgSetterTupleLike_"]
    B --> C["Create Python tuple (1, 2.0, 'hello')"]
    C --> D["TVMFFIPyConstructorCall<br/>(factory, _CONSTRUCTOR_ARRAY, tuple,<br/>result, ret_code, parent_ctx)"]
    D --> E["Allocate nested TVMFFIPyCallContext"]

    E --> F["SetArgument(factory, ctx, 1, &arg[0])"]
    F --> G["Cached: TVMFFIPyArgSetterInt_"]

    E --> H["SetArgument(factory, ctx, 2.0, &arg[1])"]
    H --> I["Cached: TVMFFIPyArgSetterFloat_"]

    E --> J["SetArgument(factory, ctx, 'hello', &arg[2])"]
    J --> K["TVMFFIStringFromByteArray"]

    G --> L["TVMFFIFunctionCall(_CONSTRUCTOR_ARRAY, args, 3, result)"]
    I --> L
    K --> L

    L --> M["Result: ffi.Array<Any>"]
    M --> N["Propagate ctx (device, stream, allocator)<br/>to parent_ctx"]
    N --> O["Return to parent call"]
```

## DLPack C-Level Exchange Flow

```mermaid
flowchart TD
    A["torch.Tensor argument"] --> B{"Has __dlpack_c_exchange_api__?"}

    B -->|Yes: C Exchange Path| C["Retrieve DLPackExchangeAPI*<br/>from cached PyCapsule"]
    C --> D["api.from_pyobject(tensor, &out)"]
    D --> E["FFI Tensor (zero-copy, no PyCapsule)"]
    C --> F["Store api in TVMFFIPyCallContext"]
    F --> G["Set managed_tensor_allocator<br/>via TVMFFIEnvSetDLPackManagedTensorAllocator"]

    B -->|No: Standard Path| H["obj.__dlpack__(stream=...)"]
    H --> I["PyCapsule<DLManagedTensor>"]
    I --> J["Extract DLManagedTensor*"]
    J --> E

    E --> K["Pack as kTVMFFITensor"]

    subgraph "Return Path (if DLPackExchangeAPI available)"
        L["FFI result is Tensor"] --> M["api.to_pyobject(tensor, &out)"]
        M --> N["torch.Tensor (zero-copy)"]
    end
```

## Call Stack Memory Layout

```mermaid
block-beta
    columns 1
    block:stack["TVMFFIPyCallStack (4KB pre-allocated)"]
        columns 4
        a1["arg[0]<br/>TVMFFIAny<br/>16 bytes"] a2["arg[1]<br/>TVMFFIAny<br/>16 bytes"] a3["arg[2]<br/>TVMFFIAny<br/>16 bytes"] space:1
        t1["temp_ffi[0]<br/>void*"] t2["temp_ffi[1]<br/>void*"] t3["temp_ffi[2]<br/>void*"] space:1
        p1["temp_py[0]<br/>void*"] p2["temp_py[1]<br/>void*"] p3["temp_py[2]<br/>void*"] space:1
    end
    block:nested["Nested Call (container conversion)"]
        columns 4
        na1["nested arg[0]"] na2["nested arg[1]"] space:2
        nt1["nested temp[0]"] nt2["nested temp[1]"] space:2
    end
    block:free["Free space / heap fallback"]
        columns 1
        f1["Remaining stack or heap-allocated overflow"]
    end

    style stack fill:#e1f5fe
    style nested fill:#fff3e0
    style free fill:#f5f5f5
```

## Evidence

- `TVMFFIPyCallManager` class: `python/tvm_ffi/cython/tvm_ffi_python_helpers.h` @ `38d2cdaa`
- `TVMFFIPyFuncCall` entry: `python/tvm_ffi/cython/tvm_ffi_python_helpers.h` @ `38d2cdaa`
- `TVMFFIPyArgSetter` dispatch: `python/tvm_ffi/cython/tvm_ffi_python_helpers.h` @ `38d2cdaa`
- Predefined POD setters: `python/tvm_ffi/cython/tvm_ffi_python_helpers.h` @ `38d2cdaa`
- `DLPackExchangeAPI` integration: `python/tvm_ffi/cython/function.pxi` @ `f81ab9c2`
- `TVMFFIPyConstructorCall`: `python/tvm_ffi/cython/tvm_ffi_python_helpers.h` @ `043d9f64`
- Container setters: `python/tvm_ffi/cython/function.pxi` @ `043d9f64`
- `TVMFFIStringFromByteArray` / `TVMFFIBytesFromByteArray`: `include/tvm/ffi/c_api.h` @ `043d9f64`
