---
diagram: "0003"
title: "Function Dual-Dispatch and Safe Call Flow"
format: "mermaid"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
related_designs:
  - ".memory/designs/0003-packed-function-and-global-registry.md"
---

# Function Dual-Dispatch and Safe Call Flow

## Dual Dispatch Architecture

```mermaid
flowchart TD
  subgraph Caller
    CppCaller["C++ caller<br/>(same DSO)"]
    CCaller["C / foreign caller<br/>(across ABI)"]
  end

  subgraph FunctionObj
    CppCall["cpp_call<br/>(TVMFFIAny* args, int n, TVMFFIAny* rv)<br/>Direct C++ with exceptions"]
    SafeCall["safe_call<br/>(void* self, TVMFFIAny* args, int n, TVMFFIAny* rv) -> int<br/>C ABI with error code"]
  end

  CppCaller --> CppCall
  CCaller --> SafeCall

  CppCall -->|"success"| RetVal["Return value in rv"]
  CppCall -->|"exception"| CppExc["C++ exception propagates"]

  SafeCall -->|"return 0"| RetVal2["Return value in rv"]
  SafeCall -->|"return -1"| TLSErr["Error stored in TLS<br/>TVMFFIErrorSetRaised"]
```

## Safe Call Error Propagation

```mermaid
sequenceDiagram
  participant Caller as Foreign Caller (Python/Rust)
  participant SafeCall as safe_call (C ABI)
  participant CppImpl as C++ Implementation
  participant TLS as Thread-Local Storage

  Caller->>SafeCall: safe_call(handle, args, n, rv)
  SafeCall->>CppImpl: try { cpp_call(args, n, rv) }
  alt Success
    CppImpl-->>SafeCall: returns normally
    SafeCall-->>Caller: return 0 (rv filled)
  else Exception
    CppImpl-->>SafeCall: throws Error
    SafeCall->>TLS: TVMFFIErrorSetRaised(error)
    SafeCall-->>Caller: return -1
    Caller->>TLS: TVMFFIErrorMoveFromRaised(&error)
    Note over Caller: Re-raise as native exception
  end
```

## Global Function Registry

```mermaid
flowchart LR
  subgraph Registration["Registration (C++ init time)"]
    Macro["TVM_FFI_REGISTER_GLOBAL('name')"]
    SetGlobal["TVMFFIFunctionSetGlobal"]
    Table["GlobalFunctionTable<br/>(Map<String, Entry>)"]
    Macro --> SetGlobal --> Table
  end

  subgraph Lookup["Lookup (any language)"]
    GetGlobal["TVMFFIFunctionGetGlobal('name')"]
    GetGlobal --> Table
    Table -->|found| FuncObj["Function object"]
    Table -->|not found| Err["Error: not registered"]
  end
```

## TypedFunction Wrapper

```mermaid
flowchart TD
  A["TypedFunction<R(Args...)>"] --> B["operator()(args...)"]
  B --> C["Pack each arg via TypeTraits<Arg>::CopyToAnyView"]
  C --> D["Call underlying Function::operator()(AnyView...)"]
  D --> E["Unpack result via any.cast<R>()"]
```

## Evidence

- FunctionObj dual dispatch: `include/tvm/ffi/function.h` cpp_call/safe_call fields @ `7d34eb8`
- TVM_FFI_SAFE_CALL_BEGIN/END macros: `include/tvm/ffi/function.h` @ `7d34eb8`
- GlobalFunctionTable: `src/ffi/function.cc` @ `7d34eb8`
- TVMFFISafeCallType: `include/tvm/ffi/c_api.h` lines 458-480 @ `7d34eb8`
- TVMFFIErrorSetRaised/MoveFromRaised: `include/tvm/ffi/c_api.h` @ `7d34eb8`
