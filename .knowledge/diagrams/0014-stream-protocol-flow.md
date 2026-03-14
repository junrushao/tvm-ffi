# __tvm_ffi_env_stream__ Protocol in make_args

Source: commit `db987299f74aadcb4d8003cc6009cb67a75662c8`
Related: [0014-python-bindings](../designs/0014-python-bindings.md), [0011-extra-api-tier](../designs/0011-extra-api-tier.md), [ADR 0030](../ADRs/0030-generic-stream-exchange-protocol.md)

## Decision Tree in make_args (DLPack branch)

```mermaid
flowchart TD
    A["arg has __dlpack__?"] -->|"Yes"| B["ffi_arg = from_dlpack(arg)"]
    B --> C{"device != kDLCPU?"}
    C -->|"No (CPU)"| DONE["Pack ffi_arg as Tensor"]
    C -->|"Yes (GPU)"| D{"ctx_dev_type == -1?<br/>(no stream set yet)"}
    D -->|"No (already set)"| DONE
    D -->|"Yes (first GPU arg)"| E{"arg has __tvm_ffi_env_stream__?"}
    E -->|"Yes"| F["stream = arg.__tvm_ffi_env_stream__()"]
    F --> G["Set ctx_dev_type, ctx_dev_id, ctx_stream"]
    G --> DONE
    E -->|"No"| DONE

    A -->|"No"| OTHER["Try other make_args branches"]
```

## Parallel: torch.Tensor vs Generic Protocol

```mermaid
flowchart LR
    subgraph "torch.Tensor path (priority 3)"
        T1["isinstance(arg, torch.Tensor)"] --> T2["Check CUDA device"]
        T2 --> T3["torch._C._cuda_getCurrentRawStream(dev_id)"]
        T3 --> T4["Set ctx_stream"]
    end

    subgraph "__dlpack__ path (priority 4)"
        D1["hasattr(arg, '__dlpack__')"] --> D2["from_dlpack(arg)"]
        D2 --> D3["Check non-CPU device"]
        D3 --> D4["hasattr(arg, '__tvm_ffi_env_stream__')"]
        D4 --> D5["arg.__tvm_ffi_env_stream__()"]
        D5 --> D6["Set ctx_stream"]
    end

    subgraph "FuncCall"
        FC1["TVMFFIEnvSetCurrentStream(\n  dev_type, dev_id, stream, &old)"]
        FC2["TVMFFIFunctionCall(...)"]
        FC3["TVMFFIEnvSetCurrentStream(\n  dev_type, dev_id, old, NULL)"]
        FC1 --> FC2 --> FC3
    end

    T4 --> FC1
    D6 --> FC1
```
