# String Dual Storage Layout (Small String Optimization)

Source: commits `0342d85`, `f9d2bff`
Related: [0005-containers](../designs/0005-containers.md), [0002-any-system](../designs/0002-any-system.md), [ADR 0013](../ADRs/0013-small-string-optimization.md)

## BytesBaseCell Dual Representation

```mermaid
block-beta
    columns 1

    block:small["Small String (len <= 7): type_index = kTVMFFISmallStr (11)"]
        columns 1
        s1["Bytes 0-3: type_index (int32_t) = 11"]
        s2["Bytes 4-7: small_str_len (uint32_t) = N"]
        s3["Bytes 8-14: v_bytes[0..6] = content (N bytes + padding)"]
        s4["Byte 15: v_bytes[7] = null terminator or padding"]
    end

    block:heap["Heap String (len >= 8): type_index = kTVMFFIStr (65)"]
        columns 1
        h1["Bytes 0-3: type_index (int32_t) = 65"]
        h2["Bytes 4-7: zero_padding (uint32_t) = 0"]
        h3["Bytes 8-15: v_obj (Object*) -> details::StringObj on heap"]
    end

    block:none["Null (Optional<String> nullopt): type_index = kTVMFFINone (0)"]
        columns 1
        n1["Bytes 0-3: type_index (int32_t) = 0"]
        n2["Bytes 4-7: zero_padding = 0"]
        n3["Bytes 8-15: v_int64 = 0"]
    end
```

## Heap StringObj Layout (when len >= 8)

```mermaid
block-beta
    columns 1

    block:obj["details::StringObj (heap-allocated)"]
        columns 1
        o1["TVMFFIObject (16B): type_index=65 | ref_counter | deleter"]
        o2["TVMFFIByteArray: data (const char*) | size (size_t)"]
        o3["Trailing content: char[0] char[1] ... char[N-1] '\\0'"]
    end
```

## AnyHash Cross-Representation Consistency

```mermaid
flowchart TD
    A["AnyHash(value)"] --> B{"type_index?"}

    B -->|"kTVMFFISmallStr (11)"| C["Use canonical type key = kTVMFFIStr (65)\nHash content via StableHashSmallStrBytes\n(raw v_uint64 modulo prime on LE)"]
    B -->|"kTVMFFIStr (65)"| D["Use type key = kTVMFFIStr (65)\nHash content via StableHashBytes"]
    B -->|"kTVMFFISmallBytes (12)"| E["Use canonical type key = kTVMFFIBytes (66)\nHash content via StableHashSmallStrBytes"]
    B -->|"kTVMFFIBytes (66)"| F["Use type key = kTVMFFIBytes (66)\nHash content via StableHashBytes"]

    C --> G["Same hash for same content"]
    D --> G
    E --> H["Same hash for same content"]
    F --> H
```

## AnyEqual Cross-Representation Combinations

```mermaid
flowchart TD
    A["AnyEqual(lhs, rhs)"] --> B{"Both small string?"}
    B -->|"Yes: both kTVMFFISmallStr"| C["16-byte bitwise compare\nlhs_int64[0]==rhs_int64[0] &&\nlhs_int64[1]==rhs_int64[1]"]

    B -->|No| D{"Mixed representations?"}
    D -->|"SmallStr vs HeapStr"| E["Compare small content\nvs BytesObjBase content\nvia Bytes::memequal"]
    D -->|"HeapStr vs SmallStr"| E
    D -->|"SmallStr vs SmallBytes"| F["return false\n(different type families)"]
    D -->|"Both HeapStr"| G["Bytes::memequal\non BytesObjBase content"]
    D -->|"Both non-string POD"| H["16-byte bitwise compare\n(zero_padding guaranteed 0)"]
```
