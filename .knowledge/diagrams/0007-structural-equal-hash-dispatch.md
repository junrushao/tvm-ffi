# Structural Equal/Hash Dispatch

Source: commits `9445fe7`, `2ec11f5`, `59a837e`, `3fc0391`
Related: [0009-structural-equal-hash](../designs/0009-structural-equal-hash.md), [0010-type-attr-columns](../designs/0010-type-attr-columns.md)

## StructuralEqual Dispatch Flow

```mermaid
flowchart TD
    A["CompareAny(lhs, rhs)"] --> B{"type_index < kTVMFFIStaticObjectBegin?"}

    B -->|Yes: POD| C{"type_index == kTVMFFIFloat?"}
    C -->|Yes| D{"std::isnan(lhs)?"}
    D -->|Yes| E["return std::isnan(rhs)\n(NaN == NaN)"]
    D -->|No| F["return lhs.v_int64 == rhs.v_int64"]
    C -->|No| F

    B -->|No: Object| G{"Switch on type_index"}
    G -->|kTVMFFIStr / kTVMFFIBytes| H["Content compare\nvia Bytes::memequal"]
    G -->|kTVMFFIArray| I["Element-wise\nrecursive compare"]
    G -->|kTVMFFIMap| J["Order-independent\nmap compare"]
    G -->|kTVMFFIShape| K["Element-wise\nshape compare"]
    G -->|kTVMFFINDArray| L["Tensor content\ncompare (CPU only)"]
    G -->|Other object| M["CompareObject(lhs, rhs)"]

    M --> N{"metadata != nullptr?"}
    N -->|No| O["throw TypeError"]
    N -->|Yes| P{"structural_eq_hash_kind?"}

    P -->|Unsupported| O
    P -->|UniqueInstance| Q["return same_as(lhs, rhs)"]
    P -->|ConstTreeNode| R{"same_as(lhs, rhs)?"}
    R -->|Yes| S["return true\n(pointer fast-path)"]
    R -->|No| T["Fall through to field compare"]

    P -->|TreeNode| T
    P -->|DAGNode| U["Check memoization table"]
    U -->|Seen| V["return memoized result"]
    U -->|New| T
    P -->|FreeVar| W["Check variable mapping"]
    W -->|Mapped| X["return mapping matches"]
    W -->|Unmapped| Y["Establish new mapping"]

    T --> Z{"TypeAttrColumn __s_equal__\n[type_index] != nullptr?"}
    Z -->|Yes: Custom| AA["Call custom __s_equal__\n(self, other, callback)"]
    Z -->|No: Default| AB["ForEachFieldInfoWithEarlyStop\nrecursive field compare"]
```

## StructuralHash Dispatch Flow

```mermaid
flowchart TD
    A["HashAny(value)"] --> B{"type_index < kTVMFFIStaticObjectBegin?"}

    B -->|Yes: POD| C{"kTVMFFIFloat && isnan?"}
    C -->|Yes| D["Canonicalize to quiet_NaN\nthen hash v_uint64"]
    C -->|No| E["StableHashCombine\n(type_index, v_uint64)"]

    B -->|No: Object| F{"Switch on type_index"}
    F -->|kTVMFFIStr / kTVMFFIBytes| G["StableHashBytes\non content"]
    F -->|kTVMFFIArray| H["Hash each element\naccumulate via StableHashCombine"]
    F -->|kTVMFFIMap| I["Sort entries by key hash\ntie-break: skip value hash"]
    F -->|kTVMFFIShape| J["Hash each dimension"]
    F -->|kTVMFFINDArray| K["Hash tensor content"]
    F -->|Other object| L["HashObject"]

    L --> M{"metadata != nullptr?"}
    M -->|No| N["throw TypeError"]
    M -->|Yes| O{"structural_eq_hash_kind?"}

    O -->|Unsupported| N
    O -->|UniqueInstance| P["StableHashCombine(type_key_hash, ptr)"]
    O -->|FreeVar / DAGNode| Q["Assign graph counter\nhash with counter"]
    O -->|TreeNode / ConstTreeNode| R{"TypeAttrColumn __s_hash__\n[type_index] != nullptr?"}
    R -->|Yes: Custom| S["Call custom __s_hash__\n(self, init_hash, callback)"]
    R -->|No: Default| T["ForEachFieldInfo\nhash each field\nvia StableHashCombine"]
```

## AccessPath Mismatch Construction

```mermaid
flowchart TD
    A["GetFirstMismatch(lhs, rhs)"] --> B["Start recursive compare\nwith empty path stack"]

    B --> C["CompareAny(lhs_field, rhs_field)"]
    C -->|Equal| D["Continue to next field"]
    C -->|Not equal| E["Push AccessStep to stack"]

    E --> F{"Mismatch in which context?"}
    F -->|Object field| G["AccessStep::Field(name)"]
    F -->|Array element| H["AccessStep::ArrayItem(index)"]
    F -->|Map entry| I["AccessStep::MapItem(key)"]
    F -->|Missing in one side| J["AccessStep::*Missing variant"]

    G --> K["Reverse path stack\nreturn AccessPathPair"]
    H --> K
    I --> K
    J --> K
```
