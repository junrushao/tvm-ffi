---
diagram: "0010"
title: "Weak Reference Lifecycle and Promotion Flow"
format: "mermaid"
source_commits:
  - "ca9c3d10bb9640bffb972302f7064e49e592a526"
related_designs:
  - ".memory/designs/0012-weak-reference-counting.md"
  - ".memory/designs/0002-object-system-and-reference-counting.md"
---

# Weak Reference Lifecycle and Promotion Flow

## Object Header Layout (Post Weak-RC)

```mermaid
block-beta
  columns 4
  block:strong["Bytes 0-7: strong_ref_count (uint64_t)"]
    columns 1
    s["Atomic +1/-1 for strong incref/decref"]
  end
  block:tidx["Bytes 8-11: type_index (int32_t)"]
    columns 1
    t["Object type tag"]
  end
  block:weak["Bytes 12-15: weak_ref_count (uint32_t)"]
    columns 1
    w["Starts at 1, inc/dec for weak ptrs"]
  end
  block:del["Bytes 16-23: deleter (void*)(void*, int)"]
    columns 1
    d["Called with flag bitmask"]
  end
```

## Deleter Flag Protocol

```mermaid
flowchart TD
  A["Object::DecRef()<br/>strong_ref_count -= 1"] --> B{"old strong == 1?<br/>(was last strong ref)"}
  B -->|No| Z["Done (still alive)"]
  B -->|Yes| C["acquire fence"]
  C --> D{"weak_ref_count == 1?<br/>(no outstanding weak refs)"}
  D -->|Yes| E["deleter(self, Both=3)<br/>Destroy object + Free memory"]
  D -->|No| F["deleter(self, Strong=1)<br/>Destroy object only"]
  F --> G["DecWeakRef()"]
  G --> H{"old weak == 1?<br/>(was last weak ref)"}
  H -->|Yes| I["acquire fence<br/>deleter(self, Weak=2)<br/>Free memory only"]
  H -->|No| J["Done (memory kept for weak refs)"]
```

## WeakObjectPtr Promotion (lock)

```mermaid
sequenceDiagram
  participant W as WeakObjectPtr<T>
  participant Obj as TVMFFIObject
  participant S as Strong Ref Owner

  Note over W,S: Successful Promotion
  W->>Obj: TryPromoteWeakPtr()
  loop CAS loop
    Obj->>Obj: old = atomic_load(strong_ref_count)
    alt old == 0
      Obj-->>W: return false (already destroyed)
    else old > 0
      Obj->>Obj: CAS(strong_ref_count, old, old+1)
      alt CAS success
        Obj-->>W: return true
      else CAS failed (concurrent decref)
        Note over Obj: Retry CAS loop
      end
    end
  end
  W->>W: Return ObjectPtr<T> (strong ref)

  Note over W,S: Failed Promotion
  S->>Obj: DecRef() -> strong=0
  Obj->>Obj: deleter(self, Strong) [destroy]
  W->>Obj: TryPromoteWeakPtr()
  Obj->>Obj: atomic_load(strong_ref_count) == 0
  Obj-->>W: return false
  W->>W: Return null ObjectPtr<T>
```

## Full Lifecycle: Strong + Weak References

```mermaid
sequenceDiagram
  participant A as make_object
  participant S1 as ObjectPtr<T> (strong 1)
  participant S2 as ObjectPtr<T> (strong 2)
  participant W1 as WeakObjectPtr<T>
  participant Obj as Object [strong=1, weak=1]

  Note over A,Obj: Phase 1: Construction
  A->>Obj: Allocate, strong=1, weak=1

  Note over S1,Obj: Phase 2: Copy strong ref
  S1->>Obj: IncRef() -> strong=2

  Note over W1,Obj: Phase 3: Create weak ref
  S1->>W1: WeakObjectPtr(s1)
  W1->>Obj: IncWeakRef() -> weak=2

  Note over S2,Obj: Phase 4: Drop one strong ref
  S2->>Obj: DecRef() -> strong=1

  Note over S1,Obj: Phase 5: Drop last strong ref
  S1->>Obj: DecRef() -> strong=0
  Obj->>Obj: weak==2 (not 1), so:
  Obj->>Obj: deleter(self, Strong=1) [destroy]
  Obj->>Obj: DecWeakRef() -> weak=1

  Note over W1,Obj: Phase 6: Try promote (fails)
  W1->>Obj: TryPromoteWeakPtr()
  Obj-->>W1: false (strong==0)

  Note over W1,Obj: Phase 7: Drop weak ref
  W1->>Obj: DecWeakRef() -> weak=0
  Obj->>Obj: deleter(self, Weak=2) [free memory]
```

## Common Case: No Weak References

```mermaid
sequenceDiagram
  participant S as ObjectPtr<T>
  participant Obj as Object [strong=1, weak=1]

  S->>Obj: DecRef() -> strong=0
  Note over Obj: weak==1 (no external weak refs)
  Obj->>Obj: deleter(self, Both=3)<br/>Destroy + Free in single call
  Note over Obj: Optimal path: one deleter call
```

## Evidence

- TVMFFIObject header with split refcounts: `include/tvm/ffi/c_api.h` @ `ca9c3d1`
- WeakObjectPtr template: `include/tvm/ffi/object.h` @ `ca9c3d1`
- TryPromoteWeakPtr CAS loop: `include/tvm/ffi/object.h` @ `ca9c3d1`
- TVMFFIObjectDeleterFlagBitMask: `include/tvm/ffi/c_api.h` @ `ca9c3d1`
- SimpleObjAllocator deleter with flags: `include/tvm/ffi/memory.h` @ `ca9c3d1`
- DecRef common-case optimization: `include/tvm/ffi/object.h` @ `ca9c3d1`
