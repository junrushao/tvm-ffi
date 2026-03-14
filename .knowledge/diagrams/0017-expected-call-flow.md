# Expected<T> Call Flow and Type System Integration

Source: commit `0a9d4b681cb017e9103efa6cc20d687c065a26fe`
Related: [0007-error-handling](../designs/0007-error-handling.md), [ADR 0056](../ADRs/0056-expected-type-for-exception-free-errors.md)

## CallExpected<T> Flow

```mermaid
sequenceDiagram
    participant Caller as C++ Caller
    participant Func as Function::CallExpected<T>
    participant SC as safe_call
    participant TLS as SafeCallContext (TLS)
    participant Impl as Function Implementation

    Caller->>Func: func.CallExpected<int>(arg1, arg2)
    Func->>Func: Pack args into AnyView[]
    Func->>SC: safe_call(func, args, num_args, &result)

    alt Implementation succeeds
        SC->>Impl: call packed function
        Impl-->>SC: return value in result
        SC-->>Func: ret_code = 0
        Func->>Func: result.try_cast<T>()
        alt Cast succeeds
            Func-->>Caller: Expected<int>(value)
        else Cast fails, try Error
            Func->>Func: result.try_cast<Error>()
            alt Is Error (function returned Expected)
                Func-->>Caller: Expected<int>(Unexpected(error))
            else Type mismatch
                Func-->>Caller: Expected<int>(Unexpected(TypeError))
            end
        end
    else Implementation throws
        SC->>Impl: call packed function
        Impl--xSC: throws Error
        SC->>TLS: SetSafeCallRaised(error)
        SC-->>Func: ret_code = -1
        Func->>TLS: MoveFromSafeCallRaised()
        Func-->>Caller: Expected<int>(Unexpected(error))
    end
```

## Expected<T> TypeTraits Serialization

```mermaid
flowchart TD
    subgraph "Expected<T> to Any"
        E["Expected<T>"]
        E -->|"is_ok()"| OK["TypeTraits<T>::MoveToAny(value)"]
        E -->|"is_err()"| ERR["TypeTraits<Error>::MoveToAny(error)"]
        OK --> ANY["Any (contains T)"]
        ERR --> ANY_E["Any (contains Error)"]
    end

    subgraph "Any to Expected<T>"
        A["Any"]
        A -->|"TypeTraits<T>::CheckAnyStrict?"| CHK_T{T?}
        CHK_T -->|yes| REC_T["Expected<T>(value)"]
        CHK_T -->|no| CHK_E{Error?}
        CHK_E -->|yes| REC_E["Expected<T>(Unexpected(error))"]
        CHK_E -->|no| FAIL["TryCast returns nullopt"]
    end
```

## Expected<T> Class Hierarchy

```mermaid
classDiagram
    class Expected~T~ {
        -Any data_
        +Expected(T value)
        +Expected(Error error)
        +Expected(Unexpected~E~ u)
        +is_ok() bool
        +is_err() bool
        +has_value() bool
        +value() T
        +error() Error
        +value_or(U default) T
    }

    class Unexpected~E~ {
        -E error_
        +Unexpected(E error)
        +error() E
    }

    class Function {
        +CallExpected~T~(args...) Expected~T~
    }

    class TypeTraits~Expected_T~ {
        +CopyToAnyView()
        +MoveToAny()
        +CheckAnyStrict()
        +TryCastFromAnyView()
        +TypeStr() string
        +TypeSchema() string
    }

    Expected~T~ <.. Unexpected~E~ : "constructs from"
    Function ..> Expected~T~ : "CallExpected returns"
    TypeTraits~Expected_T~ ..> Expected~T~ : "serializes/deserializes"
```
