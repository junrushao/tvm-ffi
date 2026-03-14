# Core Type Hierarchy and Dependency Graph

Source: commit `7d34eb8abfe987bf0031e4d4ff479895d867a966`
Related: [0001-c-abi](../designs/0001-c-abi.md), [0002-any-system](../designs/0002-any-system.md), [0003-object-system](../designs/0003-object-system.md)

## C Struct to C++ Class Mapping

```mermaid
classDiagram
    direction TB

    class TVMFFIAny {
        <<C struct, 16B>>
        int32_t type_index
        uint32_t zero_padding / small_str_len
        union value [8B]
    }
    class TVMFFIObject {
        <<C struct, 16B>>
        int32_t type_index
        int32_t ref_counter
        deleter fn ptr
    }
    class TVMFFIFunctionCell {
        <<C struct>>
        safe_call: TVMFFISafeCallType
    }
    class TVMFFIErrorCell {
        <<C struct>>
        kind: TVMFFIByteArray
        message: TVMFFIByteArray
        traceback: TVMFFIByteArray
        update_traceback: fn ptr
    }
    class TVMFFIByteArray {
        <<C struct>>
        data: const char*
        size: size_t
    }

    class AnyView {
        <<C++, layout = TVMFFIAny>>
        +as~T~() optional~T~
        +cast~T~() T
    }
    class Any {
        <<C++, layout = TVMFFIAny>>
        +reset()
        +as~T~() optional~T~
        +cast~T~() T
    }
    class Object {
        <<C++>>
        #TVMFFIObject header_
        +IsInstance~T~() bool
        +type_index() int32_t
    }
    class ObjectPtr~T~ {
        <<intrusive smart ptr>>
        -Object* data_
    }
    class ObjectRef {
        <<ref wrapper>>
        #ObjectPtr~Object~ data_
    }
    class FunctionObj {
        +call: FCall
        +safe_call: TVMFFISafeCallType
    }
    class ErrorObj {
        +kind, message, traceback
    }
    class ArrayObj {
        +size_, capacity_
        +trailing Any[]
    }
    class MapObj {
        +dense hash table
    }
    class details_StringObj {
        +TVMFFIByteArray
    }
    class BytesBaseCell {
        <<value type, 16B>>
        +TVMFFIAny data_
        +data() / size()
    }
    class ShapeObj {
        +TVMFFIShapeCell
    }
    class NDArrayObj {
        +DLTensor
    }

    TVMFFIAny ..> AnyView : "same layout"
    TVMFFIAny ..> Any : "same layout"
    TVMFFIObject <|-- Object : "header_ field"
    Object <.. ObjectPtr : "points to"
    ObjectPtr <|-- ObjectRef : "holds"

    Object <|-- FunctionObj
    TVMFFIFunctionCell <|-- FunctionObj
    Object <|-- ErrorObj
    TVMFFIErrorCell <|-- ErrorObj
    Object <|-- ArrayObj
    Object <|-- MapObj
    Object <|-- details_StringObj : "heap strings only"
    Object <|-- ShapeObj
    Object <|-- NDArrayObj

    class Function { <<ObjectRef>> }
    class Error { <<ObjectRef + exception>> }
    class Array~T~ { <<ObjectRef>> }
    class Map~K,V~ { <<ObjectRef>> }
    class String { <<value type, BytesBaseCell>> }
    class Bytes { <<value type, BytesBaseCell>> }
    class Shape { <<ObjectRef>> }
    class NDArray { <<ObjectRef>> }

    FunctionObj <.. Function : "ContainerType"
    ErrorObj <.. Error : "ContainerType"
    ArrayObj <.. Array : "ContainerType"
    MapObj <.. Map : "ContainerType"
    BytesBaseCell <.. String : "backing (SSO or heap)"
    BytesBaseCell <.. Bytes : "backing (SSO or heap)"
    ShapeObj <.. Shape : "ContainerType"
    NDArrayObj <.. NDArray : "ContainerType"
```

## TypeTraits Conversion Arrows

```mermaid
graph LR
    subgraph "C++ Types"
        INT[int/int64_t]
        FLOAT[float/double]
        BOOL[bool]
        DEVICE[DLDevice]
        DTYPE[DLDataType]
        CSTR["const char*"]
        OBJREF[ObjectRef subclass]
        OBJPTR["const T*"]
    end
    subgraph "Any/AnyView"
        AV["AnyView (16B)"]
        A["Any (16B)"]
    end

    INT -->|"CopyToAnyView / MoveToAny"| AV
    INT -->|"CopyToAnyView / MoveToAny"| A
    FLOAT --> AV
    FLOAT --> A
    BOOL --> AV
    BOOL --> A
    DEVICE --> AV
    DEVICE --> A
    DTYPE --> AV
    DTYPE --> A
    CSTR -->|"CopyToAnyView (raw)"| AV
    CSTR -->|"MoveToAny (promotes to String)"| A
    OBJREF -->|"CopyToAnyView (no IncRef)"| AV
    OBJREF -->|"MoveToAny (transfer ownership)"| A
    OBJPTR -->|"CopyToAnyView"| AV

    AV -->|"TryConvertFromAnyView"| INT
    AV -->|"TryConvertFromAnyView"| FLOAT
    AV -->|"TryConvertFromAnyView"| BOOL
    A -->|"cast<T>()"| OBJREF
```
