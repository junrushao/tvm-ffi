# TypeAttr Registration and Lookup Flow

Source: commits `162d600`, `2ec11f5`, `59a837e`
Related: [0010-type-attr-columns](../designs/0010-type-attr-columns.md), [0006-reflection](../designs/0006-reflection.md)

## Registration Path

```mermaid
sequenceDiagram
    participant Init as TVM_FFI_STATIC_INIT_BLOCK
    participant TADef as TypeAttrDef~MyObj~
    participant Base as ReflectionDefBase
    participant CApi as TVMFFITypeRegisterAttr
    participant TT as TypeTable
    participant Col as TypeAttrColumnData

    Init->>TADef: TypeAttrDef~MyObj~()
    Note over TADef: type_index = MyObj::RuntimeTypeIndex()
    Note over TADef: type_key = MyObj::_type_key

    TADef->>TADef: .def("__s_equal__", &MyObj::SEqual)
    TADef->>Base: GetMethod~MyObj~(&MyObj::SEqual)
    Note over Base: Function::FromTyped wraps member fn ptr
    Base-->>TADef: Function object
    Note over TADef: name = type_key + ".__s_equal__"
    Note over TADef: value = AnyView(func).CopyToTVMFFIAny()
    TADef->>CApi: TVMFFITypeRegisterAttr(type_index, "__s_equal__", &value)

    CApi->>TT: RegisterTypeAttr(type_index, name, value)
    alt Column does not exist
        TT->>Col: Create new TypeAttrColumnData
        Note over Col: data_ = std::vector~Any~()
        TT->>TT: type_attr_name_to_column_index_[name] = new_index
    else Column exists
        TT->>Col: Get existing column by index
    end
    Note over Col: Resize data_ to max(size, type_index + 1)
    Note over Col: Check data_[type_index] == nullptr (guard)
    Col->>Col: data_[type_index] = value
    Note over Col: Update TVMFFITypeAttrColumn.data and .size
```

## Lookup Path

```mermaid
sequenceDiagram
    participant Code as Structural Equal/Hash
    participant TACol as TypeAttrColumn
    participant CApi as TVMFFIGetTypeAttrColumn
    participant TT as TypeTable

    Code->>TACol: static TypeAttrColumn col("__s_equal__")
    Note over TACol: Constructor caches column pointer

    TACol->>CApi: TVMFFIGetTypeAttrColumn("__s_equal__")
    CApi->>TT: GetTypeAttrColumn("__s_equal__")
    TT-->>CApi: const TVMFFITypeAttrColumn* (or nullptr)
    CApi-->>TACol: column pointer cached

    Code->>TACol: col[type_index]
    alt type_index < column->size
        TACol->>TACol: reinterpret data[type_index] as AnyView
        TACol-->>Code: AnyView (function or null)
    else type_index >= column->size
        TACol-->>Code: AnyView() (null)
    end

    alt AnyView != nullptr
        Code->>Code: Call custom __s_equal__ function
    else AnyView == nullptr
        Code->>Code: Default field-by-field comparison
    end
```

## EnsureTypeAttrColumn (Forward Declaration)

```mermaid
sequenceDiagram
    participant ReadCode as Read-Path Code (e.g. StructuralEqual)
    participant CApi as TVMFFITypeRegisterAttr
    participant TT as TypeTable

    Note over ReadCode: Called during static init,<br/>before any type registers attributes

    ReadCode->>CApi: TVMFFITypeRegisterAttr(kTVMFFINone, "__s_equal__", nullptr)
    Note over CApi: type_index == kTVMFFINone is sentinel
    CApi->>TT: RegisterTypeAttr(kTVMFFINone, "__s_equal__", nullptr)
    Note over TT: Create column if not exists
    Note over TT: Skip value insertion (type_index is sentinel)
    TT-->>CApi: OK

    Note over ReadCode: Column now exists,<br/>TVMFFIGetTypeAttrColumn("__s_equal__")<br/>will return non-null pointer
```
