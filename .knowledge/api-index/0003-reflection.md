---
scope: "reflection"
status: "active"
last_updated_commit: "8fcd9245186df3d6570e641dfc1c84239a9f9a40"
related_designs:
  - ".knowledge/designs/reflection.md"
related_adrs:
  - ".knowledge/ADRs/008-globaldef-replaces-register-global.md"
  - ".knowledge/ADRs/009-reflection-structural-eq-hash.md"
---
# API Index: Reflection System

**Scope**: Type registration, field/method introspection, and reflection-based object creation.
**Design docs**: `.knowledge/designs/reflection.md`
**ADRs**: `.knowledge/ADRs/008-globaldef-replaces-register-global.md`

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFITypeRegisterField` | `int TVMFFITypeRegisterField(int32_t type_index, const TVMFFIFieldInfo* info)` | Register a field descriptor for a type |
| `TVMFFITypeRegisterMethod` | `int TVMFFITypeRegisterMethod(int32_t type_index, const TVMFFIMethodInfo* info)` | Register a method descriptor for a type |
| `TVMFFITypeRegisterMetadata` | `int TVMFFITypeRegisterMetadata(int32_t type_index, const TVMFFITypeMetadata* metadata)` | Register creator/size/eq-hash metadata |
| `TVMFFITypeRegisterAttr` | `int TVMFFITypeRegisterAttr(int32_t type_index, const TVMFFIByteArray* attr_name, const TVMFFIAny* attr_value)` | Register per-type attribute value |
| `TVMFFIGetTypeAttrColumn` | `const TVMFFITypeAttrColumn* TVMFFIGetTypeAttrColumn(const TVMFFIByteArray* attr_name)` | Retrieve column-oriented type attribute array |
| `TVMFFIFunctionSetGlobalFromMethodInfo` | `int TVMFFIFunctionSetGlobalFromMethodInfo(const TVMFFIMethodInfo* info, int allow_override)` | Register global function with metadata |
| `TVMFFITypeGetOrAllocIndex` | `int32_t TVMFFITypeGetOrAllocIndex(const char* key, int32_t static_idx, int32_t parent_idx, int32_t child_slots, int32_t overflow)` | Allocate/retrieve type index |
| `TVMFFIGetTypeInfo` | `const TVMFFITypeInfo* TVMFFIGetTypeInfo(int32_t type_index)` | Query type metadata |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `ObjectDef<Class>` | class template | `def_ro(name, field_ptr, extra...)`, `def_rw(name, field_ptr, extra...)`, `def(name, func, extra...)`, `def_static(name, func, extra...)` | Type registration builder |
| `GlobalDef` | class | `def(name, func, extra...)`, `def_packed(name, func, extra...)`, `def_method(name, func, extra...)` | Global function registration builder |
| `ReflectionDefBase` | class | `FieldGetter<T>`, `FieldSetter<T>`, `ObjectCreatorDefault<T>`, `GetMethod` | Shared base for ObjectDef/GlobalDef |
| `FieldGetter` (accessor) | class | `Any operator()(const Object* obj) const` | Runtime field reader |
| `FieldSetter` (accessor) | class | `void operator()(const Object* obj, AnyView value) const` | Runtime field writer |
| `DefaultValue` | class | `explicit DefaultValue(Any value)` | FieldInfoTrait for setting default values |
| `AttachFieldFlag` | class | `AttachFieldFlag(int64_t)`, `SEqHashDef()`, `SEqHashIgnore()` | FieldInfoTrait for per-field bitmask flags |
| `TypeAttrDef<Class>` | class template | `def(name, func)`, `attr(name, value)` | Per-type attribute registration builder |
| `TypeAttrColumn` | class | `TypeAttrColumn(string_view)`, `AnyView operator[](int32_t)` | Runtime O(1) per-type-index attribute lookup |
| `EnsureTypeAttrColumn` | function | `void EnsureTypeAttrColumn(string_view name)` | Pre-create a type attribute column |
| `FieldInfoTrait` | struct | base class | Extension point for field metadata |
| `ObjectCreator` | class (`tvm::ffi::reflection`) | `ObjectCreator(string_view type_key)`, `Any operator()(const Map<String, Any>& fields) const` | Create object from type key + field map via reflection metadata (since 7cb9273) |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `TVM_FFI_STATIC_INIT_BLOCK()` | GCC/Clang: `__attribute__((constructor)) static void FnName()`. MSVC: `static void FnName(); static int RegVar = [](){ FnName(); return 0; }(); static void FnName()` | Function-style static init macro (refactored from lambda-body in 7b813f8) |
| `reflection::GetFieldInfo` | `const TVMFFIFieldInfo* GetFieldInfo(string_view type_key, const char* field)` | Lookup field descriptor |
| `reflection::GetMethodInfo` | `const TVMFFIMethodInfo* GetMethodInfo(string_view type_key, const char* method)` | Lookup method descriptor |
| `reflection::GetMethod` | `Function GetMethod(string_view type_key, const char* method)` | Retrieve method as Function |
| `reflection::ForEachFieldInfo` | `template<Callback> void ForEachFieldInfo(const TypeInfo* info, Callback cb)` | Iterate all fields parent-to-child (void callback) |
| `reflection::ForEachFieldInfoWithEarlyStop` | `template<Callback> bool ForEachFieldInfoWithEarlyStop(const TypeInfo* info, Callback cb)` | Iterate with bool callback for early stop |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.MakeObjectFromPackedArgs` | `(type_key_or_index, field1_name, field1_value, ...) -> ObjectRef` | Create object via reflection from packed keyword args |
| `ffi.GetRegisteredTypeKeys` | `() -> Array<String>` | Return all registered type keys (since 8fcd924) |
| `tvm_ffi.registry.get_registered_type_keys` | `() -> list[str]` | Python wrapper for `ffi.GetRegisteredTypeKeys` (since 8fcd924) |
| `tvm_ffi.cython._lookup_type_attr` | `(type_index: int, attr_key: str) -> Any` | Query type attribute via `TVMFFIGetTypeAttrColumn` (since 4edf4f3) |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `ReflectionDef` | `ObjectDef<Class>` | a419ed1 | Type-safe template replacement |
| `TVM_FFI_REFLECTION_DEF(T)` | `TVM_FFI_STATIC_INIT_BLOCK() { ObjectDef<T>()... }` | a419ed1 | General-purpose init block |
| `TVM_FFI_STATIC_INIT_BLOCK(Body)` | `TVM_FFI_STATIC_INIT_BLOCK() { Body }` | 7b813f8 | Lambda-body macro -> function-style macro |
| `TVM_FFI_ATTRIBUTE_UNUSED` | (removed) | 7b813f8 | Was `[[maybe_unused]]`; now inlined in macro |
| `TVM_FFI_STATIC_INIT_BLOCK_VAR_DEF` | (removed) | 7b813f8 | Internal helper replaced by two-branch implementation |
| `def_readonly` | `def_ro` | 1a85688 | Shortened name |
| `def_readwrite` | `def_rw` | 1a85688 | Shortened name |
| `ReflectionFieldGetter` | `reflection::FieldGetter` | 1a85688 | Moved to reflection namespace |
| `GetReflectionFieldInfo` | `reflection::GetFieldInfo` | 1a85688 | Moved to reflection namespace |
| `TVMFFIRegisterTypeField` | `TVMFFITypeRegisterField` | 1a85688 | Consistent naming |
| `TVMFFIGetOrAllocTypeIndex` | `TVMFFITypeGetOrAllocIndex` | 1a85688 | Consistent naming |
| `TVMFFIErrorSetRaisedByCStr` | `TVMFFIErrorSetRaisedFromCStr` | a419ed1 | Better naming |
| `TVM_FFI_REGISTER_GLOBAL` | `GlobalDef().def(...)` | 26b68b0 | Removed, use GlobalDef |
| `Function::Registry` | `GlobalDef` | 26b68b0 | Removed class |
| `reflection.h` | `registry.h` + `accessor.h` | e95b43b | Split into two headers |
| `namespace refl` (alias) | removed | a419ed1 | Use `reflection` directly |
| `ReflectionDefBase::GetMethod<Class, Func>` | `ReflectionDefBase::GetMethod<Func>` | f4ede98 | Removed Class template parameter |
| `GlobalDef::GetMethod_` (private overloads) | `ReflectionDefBase::GetMethod` | f4ede98 | Simplified; member-function-pointer overloads removed |
| `TVMFFITypeExtraInfo` | `TVMFFITypeMetadata` | 162d600 | Improved naming |
| `TVMFFITypeRegisterExtraInfo` | `TVMFFITypeRegisterMetadata` | 162d600 | Consistent with rename |
| `TVMFFITypeInfo::extra_info` | `TVMFFITypeInfo::metadata` | 162d600 | Consistent with rename |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 1a85688 | `2025-06-15-1a85688.md` | Reflection API redesign: def_ro/def_rw, FieldFlagBitMask, method reflection |
| a419ed1 | `2025-06-16-a419ed1.md` | ObjectDef<T>, TVMFFITypeExtraInfo, TVM_FFI_STATIC_INIT_BLOCK |
| b333288 | `2025-07-03-b333288.md` | GlobalDef for global function registration |
| 26b68b0 | `2025-07-15-26b68b0.md` | Remove TVM_FFI_REGISTER_GLOBAL and Function::Registry |
| e95b43b | `2025-07-14-e95b43b.md` | Split reflection.h into registry.h + accessor.h |

| 9445fe7 | `2025-07-19-9445fe7.md` | AttachFieldFlag, structural eq/hash field flags |
| 162d600 | `2025-07-22-162d600.md` | TypeAttr system, TVMFFITypeMetadata rename |

| 7cb9273 | `2025-08-05-7cb92736b2ed.md` | ObjectCreator class for reflection-based object factory |
| f4ede98 | `2025-08-06-f4ede982f002.md` | GetMethod simplification (remove Class template param); reflection_extra.cc consolidation |

| 7b813f8 | `2025-09-13-7b813f8bc6a548d9aebb24ec5d19c0aa8b89c6a7.md` | TVM_FFI_STATIC_INIT_BLOCK refactored to function-style macro |

| 4edf4f3 | `2025-11-08-4edf4f30.md` | `_lookup_type_attr` Cython function for per-type attribute lookup |
| 8fcd924 | `2025-11-09-8fcd9245.md` | `TypeTable::GetRegisteredTypeKeys()`, `ffi.GetRegisteredTypeKeys`, Python wrapper |

Plus 7 supporting commits.
