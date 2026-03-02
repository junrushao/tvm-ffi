---
diagram: "0009"
title: "Cython Binding Type Marshaling Flow"
format: "mermaid"
source_commits:
  - "2d41a5115f6a91e2781012a3379f9626bc9e18a1"
  - "3702e50506a865f4aa4b8342ac5632502c1c40a3"
  - "1b071590342940eebe006140aa37e09874fee4b9"
  - "91d69f0658eef18fd9c99d4ac195ad5319db3787"
related_designs:
  - ".memory/designs/0011-cython-binding-layer.md"
---

# Cython Binding Type Marshaling Flow

## Python-to-C Argument Marshaling (make_args)

```mermaid
flowchart TD
  A["make_args(py_args, out, temp_args)"] --> B{"For each arg in py_args"}
  B --> C{"isinstance checks<br/>(ordered by priority)"}
  C -->|NDArray| D["type_index = kTVMFFINDArray<br/>v_ptr = chandle"]
  C -->|Object| E["type_index = object.type_index<br/>v_ptr = chandle"]
  C -->|torch.Tensor| F["Auto-convert via DLPack:<br/>to_dlpack -> from_dlpack<br/>Capture CUDA stream"]
  F --> D
  C -->|__dlpack__| G["from_dlpack(arg)"]
  G --> D
  C -->|PyNativeObject| H["Unwrap __tvm_ffi_object__"]
  H --> E
  C -->|bool| I["type_index = kTVMFFIBool<br/>v_int64 = arg"]
  C -->|Integral| J["type_index = kTVMFFIInt<br/>v_int64 = arg"]
  C -->|float| K["type_index = kTVMFFIFloat<br/>v_float64 = arg"]
  C -->|dtype| L["type_index = kTVMFFIDataType<br/>v_dtype = arg.__tvm_ffi_dtype__"]
  C -->|Device| M["type_index = kTVMFFIDevice<br/>v_device = cdevice"]
  C -->|str| N["type_index = kTVMFFIRawStr<br/>v_c_str = c_str(arg)"]
  C -->|None| O["type_index = kTVMFFINone<br/>v_int64 = 0 (zero-init)"]
  C -->|Real| P["type_index = kTVMFFIFloat<br/>v_float64 = arg"]
  C -->|bytes/bytearray| Q["type_index = kTVMFFIByteArrayPtr<br/>v_ptr = ByteArrayArg(arg)"]
  C -->|list/tuple/dict| R["Convert via _FUNC_CONVERT_TO_OBJECT<br/>Recurse as Object"]
  C -->|"Unknown type (fallback)"| S["Wrap as OpaquePyObject<br/>type_index = kTVMFFIOpaquePyObject"]
```

## C-to-Python Return Value Unmarshaling (make_ret)

```mermaid
flowchart TD
  A["make_ret(TVMFFIAny result)"] --> B{"result.type_index"}
  B -->|kTVMFFINDArray| C["make_ndarray_from_any(result)"]
  B -->|kTVMFFIOpaquePyObject| C2["Unwrap to original<br/>Python object"]
  B -->|">= kTVMFFIStaticObjectBegin (64)"| D["make_ret_object(result)<br/>Lookup class by type_index"]
  B -->|kTVMFFINone| E["return None"]
  B -->|kTVMFFIBool| F["return bool(v_int64)"]
  B -->|kTVMFFIInt| G["return v_int64"]
  B -->|kTVMFFIFloat| H["return v_float64"]
  B -->|kTVMFFISmallStr| I["make_ret_small_str<br/>SmallBytesGetContent -> py_str"]
  B -->|kTVMFFISmallBytes| J["make_ret_small_bytes<br/>SmallBytesGetContent -> PyBytes"]
  B -->|kTVMFFIOpaquePtr| K["return ctypes_handle(v_ptr)"]
  B -->|kTVMFFIDataType| L["make_ret_dtype"]
  B -->|kTVMFFIDevice| M["make_ret_device"]
  B -->|kTVMFFIDLTensorPtr| N["make_ret_dltensor"]
  B -->|"Other"| O["ValueError:<br/>Unhandled type index"]
```

## Bidirectional Error Propagation

```mermaid
sequenceDiagram
  participant Py as Python
  participant Cyx as Cython Layer
  participant CAPI as C API (libtvm_ffi)
  participant CPP as C++ Code

  Note over Py,CPP: C++ -> Python Error Path
  CPP->>CPP: TVM_FFI_THROW(ValueError) << "msg"
  CPP->>CAPI: TVMFFITraceback(file, line, sig, 0)<br/>Captures C++ stack
  CPP->>CAPI: TVMFFIErrorSetRaised(error)
  CAPI-->>Cyx: TVMFFIFunctionCall returns -1
  Cyx->>Cyx: CHECK_CALL(-1)
  Cyx->>Cyx: move_from_last_error()
  Cyx->>Cyx: Error.py_error()
  Cyx->>Py: TracebackManager.append_traceback()<br/>Creates synthetic Python frames<br/>from C++ stack trace
  Py->>Py: raise ValueError("msg")<br/>with stitched traceback

  Note over Py,CPP: Python -> C++ Error Path
  Py->>Cyx: Python callback raises Exception
  Cyx->>Cyx: set_last_ffi_error(error)
  Cyx->>CAPI: TVMFFITraceback(NULL, 0, NULL, 0)<br/>Captures C++ stack at boundary
  Cyx->>Cyx: Combine C++ trace + Python trace
  Cyx->>CAPI: TVMFFIErrorSetRaised(ffi_error)
  CAPI-->>CPP: C API returns -1
  CPP->>CPP: Error retrieved from TLS
```

## Object Lifecycle (Ref Counting)

```mermaid
sequenceDiagram
  participant Py as Python Object
  participant Cyx as Cython Object cdef class
  participant CAPI as C API
  participant CPP as C++ ObjectObj

  Note over Py,CPP: Object Creation
  Py->>Cyx: __cinit__: chandle = NULL
  CAPI->>CPP: Allocate ObjectObj<br/>ref_count = 1
  CAPI-->>Cyx: chandle = ObjectHandle

  Note over Py,CPP: Object Return from C++
  CAPI-->>Cyx: make_ret_object(result)
  Cyx->>Cyx: Lookup cls from _OBJECT_TYPE_MAP[type_index]
  Cyx->>Py: Create Python wrapper<br/>chandle = v_ptr (ownership transferred)

  Note over Py,CPP: Object Pass to C++
  Cyx->>CAPI: out[i].v_ptr = chandle<br/>No ref count change (borrowed)

  Note over Py,CPP: Object Destruction
  Py->>Cyx: __dealloc__
  Cyx->>CAPI: TVMFFIObjectFree(chandle)
  CAPI->>CPP: Decrement ref_count
  CPP->>CPP: If ref_count == 0: deleter(self)
```

## torch Tensor Auto-Conversion Detail

```mermaid
flowchart TD
  A["torch.Tensor argument"] --> B["torch.utils.dlpack.to_dlpack(tensor)"]
  B --> C["from_dlpack(capsule)"]
  C --> D["NDArray wrapping DLTensor"]
  D --> E["Pack as kTVMFFINDArray"]
  A --> F{"tensor.is_cuda?"}
  F -->|Yes| G["Capture device from DLTensor"]
  G --> H["torch._C._cuda_getCurrentRawStream(device_id)<br/>(native PyTorch C API)"]
  H --> I["Set ctx_stream for FFI call"]
  F -->|No| J["No stream context"]
  E --> K["Function call with stream context"]
  I --> K
  J --> K
```

## Evidence

- `make_args()`: `python/tvm_ffi/cython/function.pxi` @ `2d41a51`
- `make_ret()`: `python/tvm_ffi/cython/function.pxi` @ `2d41a51`
- `CHECK_CALL()`: `python/tvm_ffi/cython/error.pxi` @ `2d41a51`
- `set_last_ffi_error()`: `python/tvm_ffi/cython/error.pxi` @ `2d41a51`
- `TracebackManager`: `python/tvm_ffi/error.py` @ `2d41a51`
- `Object.__dealloc__`: `python/tvm_ffi/cython/object.pxi` @ `2d41a51`
- torch auto-conversion: `python/tvm_ffi/cython/function.pxi` `make_args` torch branch @ `2d41a51`
- None arg zero-init (v_int64 = 0): `python/tvm_ffi/cython/function.pxi` @ `3702e50`
- torch stream via native API (`torch._C._cuda_getCurrentRawStream`): `python/tvm_ffi/cython/function.pxi` @ `1b07159`
- OpaquePyObject wrapping/unwrapping: `python/tvm_ffi/cython/function.pxi`, `python/tvm_ffi/cython/object.pxi` @ `91d69f0`
