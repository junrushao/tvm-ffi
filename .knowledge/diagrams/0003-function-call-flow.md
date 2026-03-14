# Function Call Flow (C++ -> C ABI -> C++)

Source: commit `7d34eb8abfe987bf0031e4d4ff479895d867a966`
Related: [0004-function-system](../designs/0004-function-system.md), [0007-error-handling](../designs/0007-error-handling.md), [ADR 0005](../ADRs/0005-safe-call-abi-boundary.md)

## Same-DLL C++ Call (Fast Path)

```mermaid
sequenceDiagram
    participant Caller as C++ Caller
    participant Op as Function::operator()
    participant FObj as FunctionObj::CallPacked
    participant Impl as FunctionObjImpl::Call
    participant Lambda as User Lambda

    Caller->>Op: f(42, "hello")
    Note over Op: AnyView args[2]<br/>PackedArgs::Fill(args, 42, "hello")
    Op->>FObj: CallPacked(args, 2, &result)
    FObj->>Impl: this->call(this, args, 2, &result)
    Impl->>Lambda: callable_(args, 2, &result)
    Lambda-->>Impl: writes to *result
    Impl-->>FObj: return
    FObj-->>Op: return
    Op-->>Caller: return result (Any)
```

## Cross-DLL Call via safe_call (Error Path)

```mermaid
sequenceDiagram
    participant PyCaller as Python/Cython
    participant CApi as TVMFFIFunctionCall
    participant SafeCall as FunctionObj::safe_call
    participant Call as FunctionObj::call
    participant TLS as SafeCallContext (TLS)
    participant PyCheck as Python Error Check

    PyCaller->>CApi: TVMFFIFunctionCall(func, args, n, &result)
    CApi->>SafeCall: func->safe_call(func, args, n, &result)
    Note over SafeCall: TVM_FFI_SAFE_CALL_BEGIN()
    SafeCall->>Call: self->call(self, args, n, result)

    alt Success
        Call-->>SafeCall: normal return
        Note over SafeCall: return 0
        SafeCall-->>CApi: return 0
        CApi-->>PyCaller: return 0

    else C++ Error thrown
        Call--xSafeCall: throw Error("TypeError", "...")
        Note over SafeCall: catch(Error& err)
        SafeCall->>TLS: SetSafeCallRaised(err)
        Note over SafeCall: return -1
        SafeCall-->>CApi: return -1
        CApi-->>PyCaller: return -1
        PyCaller->>TLS: TVMFFIErrorMoveFromRaised(&error)
        Note over PyCaller: Convert to Python exception<br/>raise TVMError(...)

    else Frontend Error (e.g., KeyboardInterrupt)
        Call--xSafeCall: throw EnvErrorAlreadySet()
        Note over SafeCall: catch(EnvErrorAlreadySet&)
        Note over SafeCall: return -2
        SafeCall-->>CApi: return -2
        CApi-->>PyCaller: return -2
        PyCaller->>PyCheck: Check Python error state
        Note over PyCheck: Python already has the error set
    end
```

## ImportedFunctionObjImpl: Cross-DLL Redirect

```mermaid
sequenceDiagram
    participant Caller as C++ Caller (DLL A)
    participant Import as ImportedFunctionObjImpl
    participant Foreign as FunctionObj (DLL B)
    participant TLS as SafeCallContext

    Caller->>Import: call(this, args, n, rv)
    Note over Import: RedirectCallToSafeCall::Call
    Import->>Foreign: foreign->safe_call(foreign, args, n, rv)
    alt Success
        Foreign-->>Import: return 0
        Import-->>Caller: return (normal)
    else Error
        Foreign-->>Import: return -1
        Import->>TLS: MoveFromSafeCallRaised()
        Import--xCaller: throw Error(...)
    end
```
