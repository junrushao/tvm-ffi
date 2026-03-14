# Reflection Registration Flow

Source: commits `11a4a02`, `1a85688`, `a419ed1`, `b333288`, `e95b43b`, `162d600`, `9445fe7`
Related: [0006-reflection](../designs/0006-reflection.md), [0004-function-system](../designs/0004-function-system.md), [0010-type-attr-columns](../designs/0010-type-attr-columns.md)

## ObjectDef Registration (Type-Level Fields, Methods, Metadata)

```mermaid
sequenceDiagram
    participant Init as TVM_FFI_STATIC_INIT_BLOCK
    participant ODef as ObjectDef~FooObj~
    participant Base as ReflectionDefBase
    participant CApi as C API (c_api.h)
    participant TT as TypeTable

    Init->>ODef: ObjectDef~FooObj~()
    Note over ODef: type_index = FooObj::_GetOrAllocRuntimeTypeIndex()
    Note over ODef: type_key = FooObj::_type_key

    ODef->>ODef: .def_ro("name", &FooObj::name_, "docstring")
    ODef->>Base: RegisterField(field_ptr, &info)
    Note over Base: offset = GetFieldByteOffsetToObject(field_ptr)
    Note over Base: getter = FieldGetter~T~, setter = FieldSetter~T~
    Note over Base: ApplyFieldInfoTrait (docstring, DefaultValue)
    Base->>CApi: TVMFFITypeRegisterField(type_index, &info)
    CApi->>TT: entry->type_fields_data.push_back(info)

    ODef->>ODef: .def("compute", &FooObj::Compute)
    ODef->>Base: GetMethod(&FooObj::Compute)
    Note over Base: Function::FromTyped wraps member fn ptr
    Base->>CApi: TVMFFITypeRegisterMethod(type_index, &method_info)
    CApi->>TT: entry->type_methods_data.push_back(info)

    Note over ODef: RegisterMetadata()
    ODef->>CApi: TVMFFITypeRegisterMetadata(type_index, &metadata)
    Note over CApi: metadata = {creator, total_size, doc, structural_eq_hash_kind}
    CApi->>TT: entry->metadata = &metadata
```

## TypeAttrDef Registration (Per-Type Extensible Attributes)

```mermaid
sequenceDiagram
    participant Init as TVM_FFI_STATIC_INIT_BLOCK
    participant TADef as TypeAttrDef~FooObj~
    participant Base as ReflectionDefBase
    participant CApi as TVMFFITypeRegisterAttr
    participant TT as TypeTable
    participant Col as TypeAttrColumnData

    Init->>TADef: TypeAttrDef~FooObj~()
    Note over TADef: type_index = FooObj::RuntimeTypeIndex()
    Note over TADef: type_key = FooObj::_type_key

    TADef->>TADef: .def("__s_equal__", &FooObj::SEqual)
    TADef->>Base: GetMethod~FooObj~(&FooObj::SEqual)
    Base-->>TADef: Function object
    Note over TADef: Convert to TVMFFIAny
    TADef->>CApi: TVMFFITypeRegisterAttr(type_index, "__s_equal__", &value)

    CApi->>TT: RegisterTypeAttr(type_index, name, value)
    TT->>Col: Resize column, set data_[type_index] = value
    Note over Col: Update TVMFFITypeAttrColumn.data and .size
```

## GlobalDef Registration (Global Functions with Metadata)

```mermaid
sequenceDiagram
    participant Init as TVM_FFI_STATIC_INIT_BLOCK
    participant GDef as GlobalDef
    participant FT as Function::FromTyped
    participant CApi as TVMFFIFunctionSetGlobalFromMethodInfo
    participant GFT as GlobalFunctionTable

    Init->>GDef: GlobalDef()
    GDef->>GDef: .def("my_func", lambda, "docstring")
    GDef->>FT: Function::FromTyped(lambda)
    FT-->>GDef: Function object
    Note over GDef: Construct TVMFFIMethodInfo
    Note over GDef: {name, doc, type_schema, flags, method=Function}
    GDef->>CApi: TVMFFIFunctionSetGlobalFromMethodInfo(&info)
    CApi->>GFT: Update(&info, can_override=false)
    Note over GFT: Create Entry(info) in Map~String,Any~
```

## MakeObjectFromPackedArgs (Reflection-Based Construction)

```mermaid
flowchart TD
    A["MakeObjectFromPackedArgs(type_key, k1, v1, k2, v2, ...)"] --> B["Resolve type_key -> type_index"]
    B --> C["TVMFFIGetTypeInfo(type_index)"]
    C --> D{"metadata->creator != nullptr?"}
    D -->|No| E["Throw: type not default-constructible"]
    D -->|Yes| F["creator(&handle) -> empty object"]
    F --> G["Walk type_acenstors[1..depth-1] (parent to child)"]
    G --> H["For each ancestor: iterate fields"]
    H --> I{"Field name matches a kN arg?"}
    I -->|Yes| J["Call field setter with vN"]
    I -->|No| K{"Has default value?"}
    K -->|Yes| L["Apply default"]
    K -->|No| M["Track as missing required field"]
    H --> N["Iterate own type fields"]
    N --> O{"All required fields set?"}
    O -->|No| P["Throw: missing required fields"]
    O -->|Yes| Q["Return constructed Object"]
```
