---
diagram: "0002"
title: "Object Type Hierarchy and IsInstance Check Flow"
format: "mermaid"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
  - "49e2ed4a169918d346fe8f96c208a4cec56cf3e8"
  - "ca9c3d10bb9640bffb972302f7064e49e592a526"
  - "13436f01111bc4218feb440a29a2e421bc148cc4"
  - "43d13e86ee24d1558f929e3b0faa3182ca1af872"
related_designs:
  - ".memory/designs/0002-object-system-and-reference-counting.md"
  - ".memory/designs/0004-container-library.md"
  - ".memory/designs/0012-weak-reference-counting.md"
---

# Object Type Hierarchy and IsInstance Check Flow

## Builtin Object Hierarchy

```mermaid
classDiagram
  class TVMFFIObject {
    +uint64_t combined_ref_count
    +int32_t type_index
    +uint32_t __padding
    +void(*deleter)(void*, int flags)
  }
  class Object {
    +IsInstance~T~() bool
    +GetTypeKey() String
  }
  class details_StringObj {
    +TVMFFIByteArray byte_data
    +char[] inline_data
    Note: heap-only, in details namespace
  }
  class details_BytesObj {
    +TVMFFIByteArray byte_data
    +char[] inline_data
    Note: heap-only, in details namespace
  }
  class ErrorObj {
    +TVMFFIErrorCell error_cell
  }
  class FunctionObj {
    +TVMFFIFunctionCell func_cell
    +cpp_call()
    +safe_call()
  }
  class SeqBaseObj {
    +TVMFFISeqCell seq_cell
  }
  class ArrayObj
  class MapObj
  class ShapeObj {
    +TVMFFIShapeCell shape_cell
  }
  class TensorObj {
    +DLTensor dl_tensor
  }

  TVMFFIObject <|-- Object : C layout header
  Object <|-- details_StringObj : heap strings only
  Object <|-- details_BytesObj : heap bytes only
  Object <|-- ErrorObj
  Object <|-- FunctionObj
  Object <|-- SeqBaseObj
  Object <|-- ShapeObj
  Object <|-- TensorObj
  SeqBaseObj <|-- ArrayObj
  SeqBaseObj <|-- MapObj
```

## Ref Wrapper Pattern

```mermaid
classDiagram
  class ObjectRef {
    -ObjectPtr~Object~ data_
    +defined() bool
    +as~T~() const T*
  }
  class ObjectPtr~T~ {
    -T* data_
    +get() T*
    +reset()
    +use_count() int
  }
  class WeakObjectPtr~T~ {
    -T* data_
    +lock() ObjectPtr~T~
    +use_count() int
  }
  class Function {
    +operator()(...) Any
  }
  class Array~T~ {
    +size() int64_t
    +operator[](i) T
    +push_back(val)
  }

  ObjectRef *-- ObjectPtr : owns
  ObjectRef <|-- Function
  ObjectRef <|-- Array
```

## Value Types (Not ObjectRef)

```mermaid
classDiagram
  class BytesBaseCell {
    -TVMFFIAny data_
    +data() const char*
    +size() size_t
    Note: 16 bytes, SSO for <=7 bytes
  }
  class String {
    -BytesBaseCell data_
    +data() const char*
    +size() size_t
  }
  class Bytes {
    -BytesBaseCell data_
    +data() const char*
    +size() size_t
  }

  BytesBaseCell --* String : backs
  BytesBaseCell --* Bytes : backs
```

## IsInstance Check Flow

```mermaid
flowchart TD
  A["IsInstance<T>(obj)"] --> B{"obj.type_index in<br/>[T::_type_index,<br/>T::_type_index + num_slots)?"}
  B -->|Yes| C["Return true<br/>(fast path: slot range check)"]
  B -->|No| D{"type_depth >=<br/>T::_type_depth?"}
  D -->|No| E["Return false"]
  D -->|Yes| F{"ancestors[T::_type_depth - 1]<br/>== T::type_info?"}
  F -->|Yes| G["Return true<br/>(ancestor table walk)"]
  F -->|No| E
```

## TVMFFIObject Header Layout (24 bytes)

```mermaid
block-beta
  columns 4
  block:combined["Bytes 0-7: combined_ref_count (uint64_t)"]
    columns 1
    s["Strong bits [0:31] + Weak bits [32:63]"]
  end
  block:tidx["Bytes 8-11: type_index (int32_t)"]
    columns 1
    t["Object type tag"]
  end
  block:pad["Bytes 12-15: __padding (uint32_t)"]
    columns 1
    w["Zero-initialized"]
  end
  block:del["Bytes 16-23: deleter (void*)(void*, int flags)"]
    columns 1
    d["Called with TVMFFIObjectDeleterFlagBitMask"]
  end
```

## Evidence

- Object class definition: `include/tvm/ffi/object.h` @ `7d34eb8`
- TVMFFIObject struct: `include/tvm/ffi/c_api.h` lines 227-278 @ `7d34eb8`
- TVMFFIObject header split refcounts (strong/weak): `include/tvm/ffi/c_api.h` @ `ca9c3d1`
- TVMFFIObject header reorder (refcounts first): `include/tvm/ffi/c_api.h` @ `13436f0`
- TVMFFIObject combined u64 refcount: `include/tvm/ffi/c_api.h`, `include/tvm/ffi/object.h` @ `43d13e8`
- WeakObjectPtr template: `include/tvm/ffi/object.h` @ `ca9c3d1`
- TypeTable and IsInstance: `src/ffi/object.cc` @ `7d34eb8`
- IsInstance fast path (slot-range check): `TVM_FFI_DECLARE_OBJECT_INFO` macro in `include/tvm/ffi/object.h` @ `7d34eb8`
- String/Bytes rewritten as value types (BytesBaseCell): `include/tvm/ffi/string.h` @ `49e2ed4`
- StringObj/BytesObj moved to `namespace details`: `include/tvm/ffi/string.h` @ `f9d2bff`
