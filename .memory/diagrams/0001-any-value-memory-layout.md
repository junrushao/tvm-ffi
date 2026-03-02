---
diagram: "0001"
title: "TVMFFIAny 16-Byte Memory Layout"
format: "mermaid"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
related_designs:
  - ".memory/designs/0001-type-erased-any-value-system.md"
  - ".memory/designs/0005-c-abi-boundary-layer.md"
---

# TVMFFIAny 16-Byte Memory Layout

## Structure Layout

```mermaid
block-beta
  columns 4
  block:header["Bytes 0-3: type_index (int32_t)"]
    columns 1
    ti["type_index"]
  end
  block:pad["Bytes 4-7: union"]
    columns 1
    zp["zero_padding / small_str_len (uint32_t)"]
  end
  block:value["Bytes 8-15: union (8 bytes)"]
    columns 1
    val["v_int64 | v_float64 | v_ptr | v_c_str | v_obj | v_dtype | v_device | v_bytes[8] | v_uint64"]
  end
```

## Type Index Ranges

```mermaid
graph LR
  subgraph POD["POD/Special [0, 64)"]
    None["0: None"]
    Int["1: Int"]
    Bool["2: Bool"]
    Float["3: Float"]
    Ptr["4: OpaquePtr"]
    DType["5: DataType"]
    Dev["6: Device"]
    DLT["7: DLTensorPtr"]
    Raw["8: RawStr"]
    BA["9: ByteArrayPtr"]
    RV["10: ObjectRValueRef"]
    SS["11: SmallStr"]
    SB["12: SmallBytes"]
  end
  subgraph Static["Static Objects [64, 128)"]
    Obj["64: Object"]
    Str["65: String"]
    Bytes["66: Bytes"]
    Err["67: Error"]
    Func["68: Function"]
    Shape["69: Shape"]
    Tensor["70: Tensor"]
    Arr["71: Array"]
    Map["72: Map"]
    Mod["73: Module"]
    PyObj["74: OpaquePyObject"]
    List["75: List"]
    Dict["76: Dict"]
  end
  subgraph Dynamic["Dynamic Objects [128, +inf)"]
    Dyn["128+: User-defined types"]
  end
```

## Small String Optimization

```mermaid
graph TD
  A["String <= 7 bytes?"] -->|Yes| B["type_index = kTVMFFISmallStr(11)<br/>small_str_len = length<br/>v_bytes[0..6] = data + null terminator"]
  A -->|No| C["type_index = kTVMFFIStr(65)<br/>zero_padding = 0<br/>v_obj = StringObj*"]
```

## Evidence

- TVMFFIAny struct: `include/tvm/ffi/c_api.h` lines 280-333 @ `7d34eb8`
- TVMFFITypeIndex enum: `include/tvm/ffi/c_api.h` lines 84-192 @ `7d34eb8`
- Small string optimization: `include/tvm/ffi/any.h` AnyView constructors @ `7d34eb8`
