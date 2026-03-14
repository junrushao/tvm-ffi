# Weak Reference Counting Destruction Protocol

Source: commit `ca9c3d10bb9640bffb972302f7064e49e592a526`
Related: [0003-object-system](../designs/0003-object-system.md), [ADR 0023](../ADRs/0023-weak-rc-abi-design.md)

## Two-Phase Destruction: Three Scenarios

```mermaid
sequenceDiagram
    participant User as Caller
    participant Strong as ObjectPtr<T>
    participant Weak as WeakObjectPtr<T>
    participant Obj as TVMFFIObject
    participant Del as Deleter

    Note over User,Del: Scenario 1: Strong-only (common case)
    Note over Obj: strong=1, weak=1 (implicit)
    User->>Strong: Drop last strong ref
    Strong->>Obj: DecRef: strong 1->0
    Obj->>Obj: DecWeakRef (implicit): weak 1->0
    Obj->>Del: deleter(obj, Both=0b11)
    Del->>Del: Call destructor + free memory
    Note over Obj: DESTROYED

    Note over User,Del: Scenario 2: Weak outlives strong
    Note over Obj: strong=1, weak=2 (1 implicit + 1 explicit)
    User->>Strong: Drop last strong ref
    Strong->>Obj: DecRef: strong 1->0
    Obj->>Obj: DecWeakRef (implicit): weak 2->1
    Obj->>Del: deleter(obj, Strong=0b01)
    Del->>Del: Call destructor only (memory stays)
    Note over Obj: DESTROYED but memory live
    User->>Weak: Drop last weak ref
    Weak->>Obj: DecWeakRef: weak 1->0
    Obj->>Del: deleter(obj, Weak=0b10)
    Del->>Del: Free memory only
    Note over Obj: FREED

    Note over User,Del: Scenario 3: TryPromoteWeakPtr
    Note over Obj: strong=1, weak=2
    User->>Weak: lock()
    Weak->>Obj: TryPromoteWeakPtr()
    alt strong > 0
        Obj->>Obj: CAS: strong old->old+1
        Obj-->>Weak: Success: ObjectPtr<T>
    else strong == 0
        Obj-->>Weak: Failure: nullptr
    end
```

## TVMFFIObject Header Layout (24 bytes)

```mermaid
block-beta
    columns 1
    block:header["TVMFFIObject (24 bytes)"]
        columns 3
        ti["type_index\n(int32, 4B)\noffset 0"]
        wrc["weak_ref_count\n(uint32, 4B)\noffset 4"]
        src["strong_ref_count\n(uint64, 8B)\noffset 8"]
    end
    block:deleter[""]
        columns 1
        del["deleter(TVMFFIObject*, int flags)\nor __ensure_align (int64)\n(8B) offset 16"]
    end
    block:cell["Cell data starts at offset 24"]
        columns 1
        cd["Specialized cell: FunctionCell, ErrorCell, ShapeCell, etc."]
    end
```

## Deleter Flag Dispatch

```mermaid
graph TD
    A["DecRef: strong -> 0"] --> B{"weak == 1\n(implicit only)?"}
    B -->|"Yes"| C["deleter(obj, Both=0b11)\nDestructor + Free"]
    B -->|"No"| D["deleter(obj, Strong=0b01)\nDestructor only"]
    D --> E["DecWeakRef (implicit):\nweak N -> N-1"]
    E --> F{"weak == 0?"}
    F -->|"No"| G["Memory stays live\n(weak ptrs can observe)"]
    F -->|"Yes"| H["deleter(obj, Weak=0b10)\nFree memory"]

    I["Last WeakObjectPtr destroyed"] --> J["DecWeakRef:\nweak -> 0"]
    J --> H
```
