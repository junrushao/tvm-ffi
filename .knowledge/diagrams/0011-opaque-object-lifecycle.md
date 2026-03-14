# Opaque PyObject Lifecycle

Source: commit `91d69f0658eef18fd9c99d4ac195ad5319db3787`
Related: [0014-python-bindings](../designs/0014-python-bindings.md), [ADR 0026](../ADRs/0026-opaque-pyobject-fallback.md)

## Round-Trip Lifecycle

```mermaid
sequenceDiagram
    participant Py as Python Caller
    participant Args as make_args (Cython)
    participant FFI as C++ FFI (Any/Container)
    participant Ret as make_ret (Cython)

    Note over Py: obj = SomeUnknownPythonType()
    Py->>Args: func(obj)
    Args->>Args: No known type match (step 20: fallback)
    Args->>Args: _convert_to_opaque_object(obj)
    Args->>Args: Py_INCREF(obj)
    Args->>Args: TVMFFIObjectCreateOpaque(handle=PyObject*,<br/>type_index=kTVMFFIOpaquePyObject,<br/>deleter=tvm_ffi_pyobject_deleter)
    Args->>FFI: Pass as ObjectRef/Any

    Note over FFI: Object stored in Any,<br/>container, or returned

    FFI->>Ret: Return TVMFFIAny with v_obj
    Ret->>Ret: type_index == kTVMFFIOpaquePyObject
    Ret->>Ret: make_ret_opaque_object()
    Ret->>Ret: TVMFFIOpaqueObjectGetCellPtr(obj)
    Ret->>Ret: Cast handle back to PyObject*
    Ret->>Py: Return original Python object
    Note over Py: result is obj (identity preserved)

    Note over Py,Ret: Destruction (when FFI Object released)
    FFI->>FFI: DecRef -> strong_ref_count = 0
    FFI->>FFI: deleter(obj, flags)
    FFI->>FFI: tvm_ffi_pyobject_deleter:<br/>Py_DECREF(handle)
```

## Object Structure

```mermaid
block-beta
    columns 1
    block:header["TVMFFIObject Header (24 bytes)"]
        columns 3
        ti["type_index = 74\n(kTVMFFIOpaquePyObject)"]
        wrc["weak_ref_count"]
        src["strong_ref_count"]
    end
    block:cell["TVMFFIOpaqueObjectCell (offset 24)"]
        columns 1
        handle["void* handle\n(points to PyObject*)"]
    end
```

## Integration with make_args Priority Order

```mermaid
flowchart TD
    A["Python argument"] --> B{"NDArray?"}
    B -->|No| C{"Object?"}
    C -->|No| D{"torch.Tensor?"}
    D -->|No| E{"... (steps 4-19) ..."}
    E -->|No match| F["Step 20: Opaque fallback"]
    F --> G["_convert_to_opaque_object()"]
    G --> H["Py_INCREF + TVMFFIObjectCreateOpaque"]
    H --> I["Set out.type_index = kTVMFFIObject\nout.v_obj = opaque_obj"]
```
