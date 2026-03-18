---
scope: "type-traits"
---
# API Index: TypeTraits Protocol

**Scope**: C++ TypeTraits template specializations and helper base classes for FFI type conversion.
**Design docs**: [0006-type-traits.md](../designs/0006-type-traits.md)
**ADRs**: [0001-unified-any-object-abi.md](../ADRs/0001-unified-any-object-abi.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `TypeTraits<T>` | struct template | `convert_enabled`, `storage_enabled`, `CopyToAnyView(T, result)`, `MoveToAny(T, result)`, `CheckAnyStrict(src) -> bool` (renamed), `CopyFromAnyViewAfterCheck(src) -> T` (renamed), `MoveFromAnyAfterCheck(src) -> T` (renamed), `TryCastFromAnyView(src) -> Optional<T>` (renamed), `TypeStr() -> string`, `TypeSchema() -> string` (28fe3cc), `GetMismatchTypeInfo(src) -> string` | Compile-time protocol for FFI type conversion |
| `details::TypeSchemaImpl<T>` | struct template | `static std::string v()` | JSON type schema generator; primary delegates to `TypeTraits<T>::TypeSchema()`; specializations for void, Any, AnyView (28fe3cc) |
| `details::TypeSchema<T>` | using | `TypeSchemaImpl<remove_const_t<remove_reference_t<T>>>` | TypeSchemaImpl with const/reference stripped (28fe3cc) |
| `TypeTraits<IntEnum>` | specialization | Auto-derives for any `enum class` with integral underlying type | Generic enum TypeTraits (maps to kTVMFFIInt) |
| `TypeTraitsNoCR<T>` | using | `TypeTraits<remove_const_t<remove_reference_t<T>>>` | TypeTraits with const/reference stripped |
| `TypeTraitsBase` | struct | `convert_enabled=true`, `storage_enabled=true`, `GetMismatchTypeInfo(src)` | Common base for TypeTraits specializations |
| `TypeTraits<std::nullptr_t>` | specialization | Maps to `kTVMFFINone`, `v_int64=0` | None/null representation |
| `TypeTraits<bool>` | specialization | Maps to `kTVMFFIBool`, accepts int via TryConvert | Bool with implicit int->bool conversion |
| `TypeTraits<StrictBool>` | specialization | Maps to `kTVMFFIBool`, rejects int | Bool without implicit int->bool conversion |
| `TypeTraits<Int>` (integral) | specialization | Maps to `kTVMFFIInt`, `v_int64`, accepts bool via TryConvert. uint64_t/size_t: runtime overflow guard throws OverflowError when > INT64_MAX (86bbddfd) | All integral types (int8..int64, uint8..uint64) |
| `TypeTraits<Float>` (floating) | specialization | Maps to `kTVMFFIFloat`, `v_float64`, accepts int/bool via TryConvert | float and double |
| `TypeTraits<void*>` | specialization | Maps to `kTVMFFIOpaquePtr`, `v_ptr`, accepts None | Opaque pointer |
| `TypeTraits<DLDevice>` | specialization | Maps to `kTVMFFIDevice`, `v_device` | DLPack device |
| `TypeTraits<DLTensor*>` | specialization | Maps to `kTVMFFIDLTensorPtr`, `storage_enabled=false`, `MoveToAny` throws, accepts Tensor via TryConvert | DLTensor pointer (non-owning, cannot store in Any) |
| `TypeTraits<TensorView>` | specialization | Maps to `kTVMFFIDLTensorPtr`, `storage_enabled=false`, `MoveToAny` not provided, `TryCastFromAnyView` accepts `kTVMFFIDLTensorPtr` or `kTVMFFITensor` | Non-owning tensor view (added 1ec6236) |
| `is_integeral_enum_v<T>` | variable template | Two-phase constexpr bool: gates `underlying_type_t` behind `is_enum_v` | Safe enum integral check for GCC 8.x (added 5fba9e8) |
| `TypeTraits<ObjectRef subclass>` | specialization | Maps to `kTVMFFIObject`, uses IsInstance for type check, nullable refs accept None | All ObjectRef subclasses via SFINAE |
| `TypeTraits<const TObject*>` | specialization | Maps to `kTVMFFIObject`, non-owning weak pointer conversion | Raw Object pointer (non-owning) |
| `TypeTraits<Optional<T>>` | specialization | Delegates to TypeTraits<T>, accepts kTVMFFINone as nullopt | Optional wrapper |
| `TypeTraits<TypedFunction<FType>>` | specialization | Maps to `kTVMFFIFunction`, delegates to TypeTraits<Function> | Typed function wrapper |
| `StrictBool` | class | `StrictBool(bool)`, `operator bool()` | Wrapper preventing implicit int->bool in FallbackTypes |
| `ObjectRefTypeTraitsBase<TObjRef>` | struct | Full TypeTraits implementation for ObjectRef subclasses | Base for ObjectRef type traits |
| `FallbackOnlyTraitsBase<T, FallbackTypes...>` | struct | `storage_enabled=false`, `TryConvertFromAnyView` tries fallbacks in order | Traits with ordered fallback conversion chain |
| `ObjectRefWithFallbackTraitsBase<TObjRef, FallbackTypes...>` | struct | ObjectRef traits + fallback paths | ObjectRef traits with additional conversion fallbacks |
| `TypeToFieldStaticTypeIndex<T>` | struct | `static constexpr int32_t value` | Maps type to its field_static_type_index for reflection |
| `TypeToRuntimeTypeIndex<T>` | struct | `static int32_t v()` | Maps type to runtime type index (handles ObjectRef specially) |
| `details::STLTypeTrait` | struct | `storage_enabled=false`, `MoveToAnyImpl`, `CopyFromAnyImpl`, `ConstructFromAny` | CRTP base for all STL TypeTraits specializations (c3fc8f7f) |
| `details::STLTypeMismatch` | exception | None | Soft-failure sentinel for nested STL conversion; caught at TryCast boundary (c3fc8f7f) |
| `details::ListTemplate` | tag | `field_static_type_index=kTVMFFIArray` | CRTP base for sequence-like STL types (array, vector, tuple) (c3fc8f7f) |
| `details::MapTemplate` | tag | `field_static_type_index=kTVMFFIMap` | CRTP base for map-like STL types (map, unordered_map) (c3fc8f7f) |
| `TypeTraits<std::array<T,N>>` | specialization | Converts to/from ArrayObj of size N | STL array bridge (c3fc8f7f) |
| `TypeTraits<std::vector<T>>` | specialization | Converts to/from ArrayObj | STL vector bridge (c3fc8f7f) |
| `TypeTraits<std::optional<T>>` | specialization | Delegates to T or kTVMFFINone | STL optional bridge (c3fc8f7f) |
| `TypeTraits<std::variant<Args...>>` | specialization | First-match semantics in variant order | STL variant bridge (c3fc8f7f) |
| `TypeTraits<std::tuple<Args...>>` | specialization | Converts to/from ArrayObj of size sizeof...(Args), uses std::apply (88d5130d fix) | STL tuple bridge (c3fc8f7f) |
| `TypeTraits<std::map<K,V>>` | specialization | Converts to/from MapObj via CreateFromRange | STL map bridge (c3fc8f7f) |
| `TypeTraits<std::unordered_map<K,V>>` | specialization | Same as map, with pre-allocation | STL unordered_map bridge (c3fc8f7f) |
| `TypeTraits<std::function<R(A...)>>` | specialization | Wraps in TypedFunction then delegates | STL function bridge (c3fc8f7f) |
| `tvm_ffi::dtype_trait<T>` | struct template | `static constexpr DLDataType value` | Compile-time C++ numeric type to DLDataType mapping; distinct from TypeTraits (c51e519b) |
