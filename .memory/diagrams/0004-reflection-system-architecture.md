---
diagram: "0004"
title: "Reflection System Architecture"
format: "mermaid"
source_commits:
  - "1a856886c8c14c6271e156d1ce4d76335d42f0ff"
  - "a419ed175aac752a3df2ee73faad360a2824ecd8"
  - "e9094866e1e58535f2456b92c1072449f6a2716a"
  - "b333288162ba3a883dbf6b1ce23672f687d70163"
  - "e95b43b0a36325fc17ad3918e3572cf11fabae13"
  - "162d6009252dd44950a9aa9b890cbbce6b8e5155"
  - "9445fe734839cffc8bdf881788528b7763f7be03"
related_designs:
  - ".memory/designs/0006-reflection-system.md"
  - ".memory/designs/0002-object-system-and-reference-counting.md"
  - ".memory/designs/0007-structural-equal-hash-system.md"
---

# Reflection System Architecture

## Header Organization (Write Path vs Read Path)

```mermaid
graph TD
  subgraph "Write Path: reflection/registry.h"
    RDB["ReflectionDefBase"]
    OD["ObjectDef&lt;T&gt;"]
    GD["GlobalDef"]
    TAD["TypeAttrDef&lt;T&gt;"]
    IT["InfoTrait subclasses<br/>(DefaultValue, Metadata,<br/>AttachFieldFlag)"]
    OD -->|inherits| RDB
    GD -->|inherits| RDB
    TAD -->|inherits| RDB
    IT -.->|applied via variadic args| OD
    IT -.->|applied via variadic args| GD
  end

  subgraph "Read Path: reflection/accessor.h"
    FG["FieldGetter"]
    FS["FieldSetter"]
    FEFI["ForEachFieldInfo"]
    FEFIES["ForEachFieldInfoWithEarlyStop"]
    GFI["GetFieldInfo"]
    TACol["TypeAttrColumn"]
  end

  subgraph "C ABI: c_api.h"
    FI["TVMFFIFieldInfo"]
    MI["TVMFFIMethodInfo"]
    TM["TVMFFITypeMetadata<br/>(was TypeExtraInfo)"]
    TAC["TVMFFITypeAttrColumn"]
    TI["TVMFFITypeInfo"]
    TI -->|contains| FI
    TI -->|contains| MI
    TI -->|contains| TM
  end

  OD -->|"TVMFFITypeRegisterField"| FI
  OD -->|"TVMFFITypeRegisterMethod"| MI
  OD -->|"TVMFFITypeRegisterMetadata"| TM
  TAD -->|"TVMFFITypeRegisterAttr"| TAC
  GD -->|"TVMFFIFunctionSetGlobalFromMethodInfo"| MI
  FG -->|reads| FI
  FS -->|reads| FI
  FEFI -->|walks| TI
  TACol -->|"TVMFFIGetTypeAttrColumn"| TAC
```

## ObjectDef Registration Flow

```mermaid
sequenceDiagram
  participant Init as TVM_FFI_STATIC_INIT_BLOCK
  participant OD as ObjectDef<FooObj>
  participant TT as TypeTable
  participant CAPI as C ABI

  Init->>OD: ObjectDef<FooObj>("doc")
  OD->>CAPI: TVMFFITypeRegisterExtraInfo(type_index, {creator, total_size, doc})
  CAPI->>TT: Store TVMFFITypeMetadata
  Init->>OD: .def_ro("x", &FooObj::x, DefaultValue(0))
  OD->>OD: Build TVMFFIFieldInfo {name, offset, size, flags, default_value, getter}
  OD->>CAPI: TVMFFITypeRegisterField(type_index, field_info)
  CAPI->>TT: Append field to TypeInfo
  Init->>OD: .def("method", &Foo::Method)
  OD->>OD: Wrap method via GetMethod -> Function
  OD->>OD: Build TVMFFIMethodInfo {name, method, type_schema}
  OD->>CAPI: TVMFFITypeRegisterMethod(type_index, method_info)
  CAPI->>TT: Append method to TypeInfo
```

## GlobalDef Registration Flow

```mermaid
sequenceDiagram
  participant Init as TVM_FFI_STATIC_INIT_BLOCK
  participant GD as GlobalDef
  participant CAPI as C ABI
  participant GFT as GlobalFunctionTable

  Init->>GD: GlobalDef()
  Init->>GD: .def("func.name", my_func, "docstring")
  GD->>GD: Wrap my_func via Function::FromTyped
  GD->>GD: Build TVMFFIMethodInfo {name, method, doc, type_schema}
  GD->>CAPI: TVMFFIFunctionSetGlobalFromMethodInfo(method_info)
  CAPI->>GFT: Store Entry(function + metadata)
```

## MakeObjectFromPackedArgs Flow

```mermaid
flowchart TD
  A["MakeObjectFromPackedArgs(type_key, field_args...)"] --> B["Look up type_index from type_key"]
  B --> C["Get TVMFFITypeMetadata.creator"]
  C --> D["Call creator() to allocate object"]
  D --> E["Walk ancestors parent-to-child"]
  E --> F{"For each ancestor's fields"}
  F --> G{"Field name in args?"}
  G -->|Yes| H["Set field from arg value"]
  G -->|No| I{"Has default?"}
  I -->|Yes| J["Set field from default_value"]
  I -->|No| K["Throw TypeError: missing required field"]
  H --> F
  J --> F
  F -->|done| L["Return constructed object"]
```

## ForEachFieldInfo Ancestor Traversal

```mermaid
flowchart LR
  subgraph "type_ancestors (pointer chain)"
    A0["ancestors[0]<br/>→ Object TypeInfo"]
    A1["ancestors[1]<br/>→ BaseObj TypeInfo"]
    A2["ancestors[2]<br/>→ DerivedObj TypeInfo"]
  end

  subgraph "Field iteration order"
    F0["Object fields (none)"]
    F1["BaseObj.x, BaseObj.y"]
    F2["DerivedObj.z"]
  end

  A0 --> F0
  A1 --> F1
  A2 --> F2
  F0 --> F1 --> F2
```

## Evidence

- ObjectDef template: `include/tvm/ffi/reflection/registry.h` @ `1a8568`, `a419ed`
- GlobalDef class: `include/tvm/ffi/reflection/registry.h` @ `b33328`
- TVMFFIFieldInfo/MethodInfo/TypeExtraInfo structs: `include/tvm/ffi/c_api.h` @ `a419ed`
- Header split (registry.h + accessor.h): @ `e95b43`
- ForEachFieldInfo: `include/tvm/ffi/reflection/accessor.h` @ `837800`
- MakeObjectFromPackedArgs: `src/ffi/object.cc` @ `e90948`
- Ancestor pointer chain: `include/tvm/ffi/c_api.h` @ `837800`
- TypeAttrDef<T>: `include/tvm/ffi/reflection/registry.h` @ `162d600`
- TypeAttrColumn accessor: `include/tvm/ffi/reflection/accessor.h` @ `162d600`
- TVMFFITypeMetadata (renamed from TypeExtraInfo): `include/tvm/ffi/c_api.h` @ `162d600`
- AttachFieldFlag (SEqHash field annotations): `include/tvm/ffi/reflection/registry.h` @ `9445fe7`
