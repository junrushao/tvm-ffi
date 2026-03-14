# Container ABI Layout

Source: commit `7e0a4b35df078675af32624b9cd02d1b8da1353e`
Related: [0005-containers](../designs/0005-containers.md), [ADR 0009](../ADRs/0009-container-data-indirection.md)

## ArrayObj Memory Layout (After data_ Indirection)

```mermaid
block-beta
    columns 1

    block:header["ArrayObj Memory Layout"]
        columns 1
        h1["TVMFFIObject (16B): type_index | ref_counter | deleter"]
        h2["InplaceArrayBase fields"]
        h3["data_ (void*, 8B) -----> points to TVMFFIAny[0]"]
        h4["size_ (size_t, 8B)"]
        h5["capacity_ (int64_t, 8B)"]
        h6["data_deleter_ (void(*)(void*), 8B) = nullptr for inplace"]
        h7["TVMFFIAny[0] (16B) <-- data_ points here"]
        h8["TVMFFIAny[1] (16B)"]
        h9["... TVMFFIAny[n-1]"]
    end
```

## DenseMapObj Memory Layout

```mermaid
block-beta
    columns 2

    block:mapobj["DenseMapObj (heap object)"]
        columns 1
        m1["TVMFFIObject (16B)"]
        m2["data_ (void*) -------->"]
        m3["size_ (int64_t)"]
        m4["slots_ (int64_t) = actual slot count"]
        m5["data_deleter_ = BlockDeleter"]
        m6["fib_shift_ (int64_t)"]
        m7["iter_list_head_ / tail_"]
    end

    block:blocks["Separate Block[] allocation"]
        columns 1
        b1["Block[0]: {key Any, value Any, metadata}"]
        b2["Block[1]: ..."]
        b3["Block[slots_-1]: ..."]
    end
```

## Variant Dual Storage

```mermaid
classDiagram
    class Variant_AnyBacked {
        <<VariantBase false>>
        -Any data_ (16 bytes)
        +sizeof = 16
    }
    class Variant_ObjRefBacked {
        <<VariantBase true>>
        +sizeof = 8
    }
    class ObjectRef {
        -ObjectPtr data_ (8 bytes)
    }
    class Any {
        -TVMFFIAny data_ (16 bytes)
    }

    Any <|-- Variant_AnyBacked : "contains"
    ObjectRef <|-- Variant_ObjRefBacked : "inherits"

    note for Variant_AnyBacked "Used when any V is not ObjectRef\ne.g. Variant<int, String>"
    note for Variant_ObjRefBacked "Used when ALL V are ObjectRef\ne.g. Variant<String, Array<int>>"
```
