---
scope: "type-traits"
status: "active"
last_updated_commit: "c3fc8f7f0e95a97beed342b6ddec4c3f6add0441"
related_designs:
  - ".knowledge/designs/type-traits.md"
related_adrs:
  - ".knowledge/ADRs/005-as-vs-cast-semantics.md"
---
# API Index: TypeTraits Protocol

**Scope**: Compile-time protocol for type-erased value conversion, including all built-in specializations and base classes.
**Design docs**: `.knowledge/designs/type-traits.md`
**ADRs**: `.knowledge/ADRs/005-as-vs-cast-semantics.md`

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `TypeTraits<T>` | struct template | `CopyToAnyView`, `MoveToAny`, `CheckAnyStrict`, `CopyFromAnyViewAfterCheck`, `MoveFromAnyAfterCheck`, `TryCastFromAnyView`, `TypeStr`, `GetMismatchTypeInfo` | Full type-erased conversion protocol |
| `TypeTraitsBase` | struct | `convert_enabled=true`, `storage_enabled=true`, `field_static_type_index=kTVMFFIAny` | Base class providing defaults |
| `ObjectRefTypeTraitsBase<T>` | struct template | Inherits TypeTraitsBase; handles nullable/non-nullable ObjectRef | Base for ObjectRef subtypes |
| `FallbackOnlyTraitsBase<T, F...>` | struct template | `TryCastFromAnyView` iterates fallback types | Base for conversion-only types |
| `ObjectRefWithFallbackTraitsBase<T, F...>` | struct template | Combines ObjectRef + fallback | Base for ObjectRef with conversion fallbacks |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `TypeTraits<T>::CopyToAnyView` | `static void CopyToAnyView(const T& src, TVMFFIAny* result)` | Write T into non-owning AnyView slot |
| `TypeTraits<T>::MoveToAny` | `static void MoveToAny(T src, TVMFFIAny* result)` | Write T into owning Any slot |
| `TypeTraits<T>::CheckAnyStrict` | `static bool CheckAnyStrict(const TVMFFIAny* src)` | Strict type match check |
| `TypeTraits<T>::CopyFromAnyViewAfterCheck` | `static T CopyFromAnyViewAfterCheck(const TVMFFIAny* src)` | Extract after strict check (copy) |
| `TypeTraits<T>::MoveFromAnyAfterCheck` | `static T MoveFromAnyAfterCheck(TVMFFIAny* src)` | Extract after strict check (move) |
| `TypeTraits<T>::TryCastFromAnyView` | `static std::optional<T> TryCastFromAnyView(const TVMFFIAny* src)` | Lenient conversion attempt |
| `TypeTraits<IntEnum>` (enum) | SFINAE: `is_integeral_enum_v<T>` (two-phase: `is_enum_v` then `is_integral_v<underlying_type_t>`) | Auto-specialization for enum class types; maps to kTVMFFIInt |
| `TypeTraits<TensorView>` | `storage_enabled=false`, `field_static_type_index=kTVMFFIDLTensorPtr`; `TryCastFromAnyView` accepts DLTensorPtr + Tensor | Non-owning tensor view (added in 1ec6236) |
| `TypeTraits<TObject*>` | `static_assert(!is_const_v<T> implies T::_type_mutable)` | Mutable/const object pointer extraction |
| `TypeTraits<std::vector<T>>` | `storage_enabled=false`; maps to `Array`; `TryCast` iterates elements | STL vector bridge (extra/stl.h, c3fc8f7f) |
| `TypeTraits<std::tuple<T...>>` | `storage_enabled=false`; maps to `Array` (size-checked); element-wise unpack | STL tuple bridge (extra/stl.h, c3fc8f7f) |
| `TypeTraits<std::pair<K,V>>` | Delegates to `TypeTraits<std::tuple<K,V>>` | STL pair bridge (extra/stl.h, c3fc8f7f) |
| `TypeTraits<std::array<T,N>>` | `storage_enabled=false`; maps to `Array` (size N checked); fixed-size | STL array bridge (extra/stl.h, c3fc8f7f) |
| `TypeTraits<std::map<K,V>>` | `storage_enabled=false`; maps to `Map` | STL ordered map bridge (extra/stl.h, c3fc8f7f) |
| `TypeTraits<std::unordered_map<K,V>>` | `storage_enabled=false`; maps to `Map`; `CanReserve=true` | STL unordered map bridge (extra/stl.h, c3fc8f7f) |
| `TypeTraits<std::optional<T>>` | Delegates to T or `kTVMFFINone` for nullopt | STL optional bridge (extra/stl.h, c3fc8f7f) |
| `TypeTraits<std::variant<Args...>>` | `CheckAnyStrict` fold-expression; `TryCast` iterates alternatives | STL variant bridge (extra/stl.h, c3fc8f7f) |
| `TypeTraits<std::function<Ret(Args...)>>` | `storage_enabled=false`; wraps via `TypedFunction` proxy; `kTVMFFIFunction` | STL function bridge (extra/stl.h, c3fc8f7f) |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `CheckAnyStorage` | `CheckAnyStrict` | 37a2e7c | Renamed for clarity |
| `CopyFromAnyStorageAfterCheck` | `CopyFromAnyViewAfterCheck` | 37a2e7c | Renamed |
| `MoveFromAnyStorageAfterCheck` | `MoveFromAnyAfterCheck` | 37a2e7c | Renamed |
| `TryConvertFromAnyView` | `TryCastFromAnyView` | 37a2e7c | Renamed |
| `TypeTraits<const TObject*>` (const-only) | `TypeTraits<TObject*>` (both) | 1a85688 | Generalized with _type_mutable guard |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 37a2e7c | `2025-05-14-37a2e7c.md` | Protocol method renames (CheckAnyStrict etc.) |
| 1a85688 | `2025-06-15-1a85688.md` | field_static_type_index default; mutable pointer traits |
| f7311e4 | `2025-06-27-f7311e4.md` | Enum TypeTraits specialization |
| a5a08b2 | `2025-06-27-a5a08b2.md` | DLDataType padding fix |

| 1ec6236 | `2025-10-01-1ec6236.md` | TensorView TypeTraits (storage_enabled=false, dual TryCast) |
| 28fe3cc | `2025-10-03-28fe3cc.md` | TypeSchema() method on all TypeTraits |
| 5fba9e8 | `2025-10-04-5fba9e8.md` | GCC 8.x enum SFINAE fix (is_integeral_enum_v) |

| c3fc8f7f | `2025-11-30-c3fc8f7f.md` | STL container TypeTraits (extra/stl.h): vector, tuple, pair, array, map, unordered_map, optional, variant, function |

Plus 3 supporting commits (296e2f7, 88d5130d use-after-move fix, 5a82940e test fix).
