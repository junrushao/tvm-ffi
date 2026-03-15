---
scope: "string-bytes"
status: "active"
last_updated_commit: "30f1e0af6a5c1ccab79a10560388756e3f95f7e6"
related_designs:
  - ".knowledge/designs/0011-small-string-optimization.md"
  - ".knowledge/designs/containers.md"
related_adrs:
  - ".knowledge/ADRs/003-type-index-ranges.md"
---
# API Index: String / Bytes

**Scope**: String and bytes value types, small-string optimization, equality/hash helpers.
**Design docs**: `.knowledge/designs/0011-small-string-optimization.md`, `.knowledge/designs/containers.md`
**ADRs**: `.knowledge/ADRs/003-type-index-ranges.md`

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFISmallBytesGetContentByteArray` | `static inline TVMFFIByteArray TVMFFISmallBytesGetContentByteArray(const TVMFFIAny* value)` | Extract content of a small string/bytes as byte array |
| `TVMFFIDataTypeToString` | `int TVMFFIDataTypeToString(const DLDataType* dtype, TVMFFIAny* out)` | Returns TVMFFIAny (may be small string) |
| `TVMFFIStringFromByteArray` | `int TVMFFIStringFromByteArray(const TVMFFIByteArray* input, TVMFFIAny* out)` | Create owned String (SSO-aware) from raw bytes; uses `TypeTraits<String>::MoveToAny` (added in 043d9f6) |
| `TVMFFIBytesFromByteArray` | `int TVMFFIBytesFromByteArray(const TVMFFIByteArray* input, TVMFFIAny* out)` | Create owned Bytes (SSO-aware) from raw bytes; uses `TypeTraits<Bytes>::MoveToAny` (added in 043d9f6) |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `String` | value type (`tvm::ffi`) | `data()`, `size()`, `c_str()`, `empty()`, `compare(const String&)`, `compare(const char*)` | UTF-8 string with SSO; not ObjectRef |
| `Bytes` | value type (`tvm::ffi`) | `data()`, `size()`, `empty()` | Raw byte container with SSO; not ObjectRef |
| `details::BytesBaseCell` | class (`tvm::ffi::details`) | `data()`, `size()`, `InitSpaceForSize<LargeObj>(size, small_idx, large_idx)`, `MoveToAny()`, `CopyFromAnyView()` | Private dual-storage manager for String/Bytes |
| `details::BytesObjBase` | class (`tvm::ffi::details`) | `Object + TVMFFIByteArray` | Base for heap-allocated string/bytes objects |
| `details::StringObj` | class (`tvm::ffi::details`) | `_type_index = kTVMFFIStr, _type_key = "ffi.String"` | Heap-allocated string object (large strings) |
| `details::BytesObj` | class (`tvm::ffi::details`) | `_type_index = kTVMFFIBytes, _type_key = "ffi.Bytes"` | Heap-allocated bytes object (large bytes) |
| `Optional<String>` | specialization | `has_value()`, `value()`, `value_or()` | Zero-overhead optional using BytesBaseCell(nullopt) |
| `Optional<Bytes>` | specialization | `has_value()`, `value()`, `value_or()` | Zero-overhead optional using BytesBaseCell(nullopt) |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `Bytes::memequal` | `static bool memequal(const void* lhs, const void* rhs, size_t lhs_count, size_t rhs_count)` | Equality-only comparison; short-circuits on length mismatch |
| `Bytes::memncmp` | `static int memncmp(const char* lhs, const char* rhs, size_t lhs_count, size_t rhs_count)` | Three-way byte comparison for ordering |
| `details::StableHashBytes` | `uint64_t StableHashBytes(const void* data, size_t size)` | FNV-1-like stable hash; aligned fast-path for 8-byte aligned data |
| `details::StableHashSmallStrBytes` | `uint64_t StableHashSmallStrBytes(const TVMFFIAny* value)` | Fast hash for inline small strings |
| `details::MakeInplaceBytes<Base>` | `ObjectPtr<Base> MakeInplaceBytes(const char* data, size_t length)` | Single-allocation string/bytes creation |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| (String/Bytes are transparently converted to/from Python str/bytes via TypeTraits in the packed calling convention) | | |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `tvm::ffi::StringObj` | `tvm::ffi::details::StringObj` | f9d2bff | Moved to details namespace |
| `tvm::ffi::BytesObj` | `tvm::ffi::details::BytesObj` | f9d2bff | Moved to details namespace |
| `tvm::ffi::BytesObjBase` | `tvm::ffi::details::BytesObjBase` | f9d2bff | Moved to details namespace |
| `String : ObjectRef` | `String` (value type) | 49e2ed4 | No longer inherits ObjectRef |
| `Bytes : ObjectRef` | `Bytes` (value type) | 49e2ed4 | No longer inherits ObjectRef |
| `TypeTraits<String>` via `ObjectRefWithFallbackTraitsBase` | Custom `TypeTraits<String>` | 49e2ed4 | Handles kTVMFFISmallStr/kTVMFFIStr |
| `TypeTraits<Bytes>` via `ObjectRefWithFallbackTraitsBase` | Custom `TypeTraits<Bytes>` | 49e2ed4 | Handles kTVMFFISmallBytes/kTVMFFIBytes |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| ba0ea87 | `2025-07-30-ba0ea87.md` | Bytes::memequal, aligned StableHashBytes, String::compare rewrite |
| f9d2bff | `2025-08-01-f9d2bff.md` | StringObj/BytesObj moved to details namespace |
| 49e2ed4 | `2025-08-04-49e2ed4.md` | SSO: SmallStr/SmallBytes, BytesBaseCell, String/Bytes as value types |

Plus 1 supporting commit (0342d85 SmallMap duplicate key fix).
