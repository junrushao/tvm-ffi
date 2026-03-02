---
diagram: "0013"
title: "TVMFFIObject Header Layout: Combined Reference Count"
format: "mermaid"
source_commits:
  - "13436f01111bc4218feb440a29a2e421bc148cc4"
  - "43d13e86ee24d1558f929e3b0faa3182ca1af872"
  - "ffa2dbf8bc18edb3114f18f619da08c4e3289de6"
related_designs:
  - ".memory/designs/0002-object-system-and-reference-counting.md"
  - ".memory/designs/0005-c-abi-boundary-layer.md"
  - ".memory/designs/0012-weak-reference-counting.md"
related_adrs:
  - ".memory/ADRs/0026-tvmffiobject-header-reorder-combined-refcount.md"
  - ".memory/ADRs/0002-combined-refcount-in-single-u64.md"
---

# TVMFFIObject Header Layout: Combined Reference Count

## Current Layout (24 bytes)

```mermaid
block-beta
  columns 4
  block:combined["Bytes 0-7: combined_ref_count (uint64_t)"]
    columns 2
    strong["Bits 0-31: strong count"]
    weak["Bits 32-63: weak count"]
  end
  block:tidx["Bytes 8-11: type_index (int32_t)"]
    columns 1
    t["Object type tag"]
  end
  block:pad["Bytes 12-15: __padding (uint32_t)"]
    columns 1
    p["Zero-initialized"]
  end
  block:del["Bytes 16-23: deleter (void*)(void*, int flags)"]
    columns 1
    d["TVMFFIObjectDeleterFlagBitMask"]
  end
```

## Combined Refcount Bit Layout

```mermaid
flowchart LR
  subgraph combined_ref_count["uint64_t combined_ref_count"]
    direction LR
    A["Bits 0-31\nstrong_ref_count\n(uint32_t)"] --- B["Bits 32-63\nweak_ref_count\n(uint32_t)"]
  end
  subgraph constants["Key Constants"]
    C["kCombinedRefCountStrongOne = 1"]
    D["kCombinedRefCountWeakOne = 1 << 32"]
    E["kCombinedRefCountBothOne\n= StrongOne | WeakOne"]
    F["kCombinedRefCountMaskUInt32\n= (1 << 32) - 1"]
  end
```

## DecRef Fast Path

```mermaid
flowchart TD
  A["DecRef()"] --> B["old = fetch_sub(combined_ref_count, 1, RELEASE)"]
  B --> C{"(old & mask) == 1?\n(strong was 1)"}
  C -->|No| D["Return\n(not last strong ref)"]
  C -->|Yes| E["acquire_fence()"]
  E --> F{"old == BothOne?\n(weak was also 1)"}
  F -->|Yes| G["deleter(self, Both)\n*FAST PATH*\nSingle atomic op total"]
  F -->|No| H["deleter(self, Strong)"]
  H --> I["DecWeakRef()"]
  I --> J{"last weak ref?"}
  J -->|Yes| K["deleter(self, Weak)\nFree memory"]
  J -->|No| L["Return\n(weak refs remain)"]
```

## Header Layout Evolution

```mermaid
flowchart TD
  A["Root commit (7d34eb8)\ncombined_ref_count : u64\ntype_index : i32\n__padding : u32\ndeleter : void*"] --> B["Weak refs (ca9c3d1)\nstrong_ref_count : u64\ntype_index : i32\nweak_ref_count : u32\ndeleter : void*"]
  B --> C["Reorder (13436f0)\nstrong_ref_count : u32\nweak_ref_count : u32\ntype_index : i32\n__padding : u32\ndeleter : void*"]
  C --> D["Re-combine (43d13e8)\ncombined_ref_count : u64\ntype_index : i32\n__padding : u32\ndeleter : void*"]
  D --> E["Zero-init (ffa2dbf)\n__padding = 0"]

  style D fill:#2d5016,stroke:#333,color:#fff
  style E fill:#2d5016,stroke:#333,color:#fff
```

## Evidence

- Header reorder (refcounts first): `include/tvm/ffi/c_api.h` @ `13436f0`
- Combined u64 refcount: `include/tvm/ffi/c_api.h`, `include/tvm/ffi/object.h` @ `43d13e8`
- Zero-init padding: `include/tvm/ffi/memory.h` @ `ffa2dbf`
- Constants (kCombinedRefCount*): `include/tvm/ffi/object.h` @ `43d13e8`
