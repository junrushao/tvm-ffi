---
diagram: "0011"
title: "Stream Exchange Flow (__tvm_ffi_env_stream__ Protocol)"
format: "mermaid"
source_commits:
  - "a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806"
related_designs:
  - ".memory/designs/0014-stream-exchange-protocol.md"
---

# Stream Exchange Flow

## Sequence Diagram: Generic Protocol Path

```mermaid
sequenceDiagram
    participant Caller as Python Caller
    participant MakeArgs as make_args() [Cython]
    participant Obj as tensor_arg (Python)
    participant SetStream as TVMFFIEnvSetCurrentStream
    participant FuncCall as TVMFFIFunctionCall
    participant Restore as Restore Stream

    Caller->>MakeArgs: func(tensor_arg)
    MakeArgs->>Obj: hasattr(__tvm_ffi_env_stream__)?
    Obj-->>MakeArgs: Yes
    MakeArgs->>Obj: __dlpack_device__()
    Obj-->>MakeArgs: (device_type, device_id)
    alt device_type != kDLCPU
        MakeArgs->>Obj: __tvm_ffi_env_stream__()
        Obj-->>MakeArgs: stream_handle (int)
        MakeArgs->>SetStream: TVMFFIEnvSetCurrentStream(device_type, device_id, stream_handle)
        SetStream-->>MakeArgs: saved previous stream
    end
    MakeArgs->>Obj: __dlpack__()
    Obj-->>MakeArgs: DLManagedTensor
    MakeArgs->>MakeArgs: from_dlpack() -> Tensor
    MakeArgs->>FuncCall: TVMFFIFunctionCall(func, packed_args, n, &rv)
    FuncCall-->>MakeArgs: return code
    MakeArgs->>Restore: Restore saved stream context
```

## Sequence Diagram: torch-Specific Fast Path

```mermaid
sequenceDiagram
    participant Caller as Python Caller
    participant MakeArgs as make_args() [Cython]
    participant Torch as torch.Tensor
    participant TorchAPI as torch._C._cuda_getCurrentRawStream
    participant SetStream as TVMFFIEnvSetCurrentStream
    participant FuncCall as TVMFFIFunctionCall

    Caller->>MakeArgs: func(torch_tensor)
    MakeArgs->>MakeArgs: isinstance(torch_tensor, torch.Tensor)?
    Note right of MakeArgs: torch path detected
    MakeArgs->>Torch: device.type == "cuda"?
    Torch-->>MakeArgs: Yes
    MakeArgs->>TorchAPI: torch._C._cuda_getCurrentRawStream(device_id)
    TorchAPI-->>MakeArgs: stream_handle
    MakeArgs->>SetStream: TVMFFIEnvSetCurrentStream(kDLCUDA, device_id, stream_handle)
    MakeArgs->>Torch: torch.utils.dlpack.to_dlpack()
    Torch-->>MakeArgs: DLManagedTensor
    MakeArgs->>FuncCall: TVMFFIFunctionCall(...)
```

## Stream Context Thread-Local Storage

```mermaid
flowchart TD
    subgraph "Thread 1"
        T1["StreamContext (TLS)"]
        T1a["CUDA:0 -> stream 0x7f00"]
        T1b["CUDA:1 -> stream 0x7f10"]
    end
    subgraph "Thread 2"
        T2["StreamContext (TLS)"]
        T2a["CUDA:0 -> stream 0x8f00"]
    end

    T1 --> T1a
    T1 --> T1b
    T2 --> T2a

    SetCurrent["TVMFFIEnvSetCurrentStream(kDLCUDA, 0, handle)"]
    GetCurrent["TVMFFIEnvGetCurrentStream(kDLCUDA, 0, &out)"]

    SetCurrent --> T1
    GetCurrent --> T1
```

## Protocol Decision Tree

```mermaid
flowchart TD
    A["Argument in make_args()"] --> B{"isinstance<br/>torch.Tensor?"}
    B -->|Yes| C["torch fast path:<br/>torch._C._cuda_getCurrentRawStream"]
    B -->|No| D{"has __dlpack__?"}
    D -->|No| E["Not a tensor,<br/>use other dispatch"]
    D -->|Yes| F{"has __tvm_ffi_env_stream__?"}
    F -->|No| G["Import via __dlpack__<br/>no stream exchange"]
    F -->|Yes| H["Call __dlpack_device__()"]
    H --> I{"device_type<br/>== kDLCPU?"}
    I -->|Yes| G
    I -->|No| J["Call __tvm_ffi_env_stream__()<br/>Set stream via TVMFFIEnvSetCurrentStream"]
    J --> G
    C --> K["Set stream + import via DLPack"]
```

## Evidence

- `__tvm_ffi_env_stream__` protocol dispatch in `make_args()`: `python/tvm_ffi/cython/function.pxi` @ `a08fa6e`
- `TVMFFIEnvSetCurrentStream` / `TVMFFIEnvGetCurrentStream`: `include/tvm/ffi/extra/c_env_api.h` @ `a08fa6e`
- `DLTensorTestWrapper`: `python/tvm_ffi/cython/tensor.pxi` @ `a08fa6e`
- torch fast path: `python/tvm_ffi/cython/function.pxi` @ `a08fa6e`
- `StreamContext` thread-local: `src/ffi/extra/stream_context.cc` @ `a08fa6e`
