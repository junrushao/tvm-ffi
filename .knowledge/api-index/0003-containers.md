---
scope: "containers"
---
# API Index: Containers

**Scope**: Container types in `tvm::ffi` — Array, List, Map, Dict, Shape, Tensor, Tuple, Variant.
**Design docs**: [0008-containers.md](../designs/0008-containers.md)
**ADRs**: [0003-insertion-order-map.md](../ADRs/0003-insertion-order-map.md), [0012-msb-tag-map-layout.md](../ADRs/0012-msb-tag-map-layout.md), [0027-dict-mutable-map.md](../ADRs/0027-dict-mutable-map.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `TVMFFISeqCell` | C struct (9513c2f) | `void* data`, `int64_t size`, `int64_t capacity`, `void (*data_deleter)(void*)` | C ABI struct defining shared memory layout for sequence containers |
| `SeqBaseObj` | class (9513c2f) | inherits `Object + TVMFFISeqCell (protected)`; `size() -> size_t`, `capacity() -> size_t`, `empty() -> bool`, `at(int64_t) -> const Any&`, `operator[](int64_t) -> const Any&`, `front() -> const Any&`, `back() -> const Any&`; iterators, find, contains, count | Shared base for ArrayObj and ListObj; consolidates element access and iteration |
| `ArrayObj` | class | inherits `SeqBaseObj`; fields inherited from TVMFFISeqCell; `static _type_index = 71`, `static _type_key = "ffi.Array"` | Inplace array of Any values (was directly inheriting Object, now via SeqBaseObj) |
| `Array<T>` | class template | inherits `ObjectRef`; `size() -> size_t`, `operator[](int64_t) -> T`, `push_back(T)`, `emplace_back(Args&&...)`, `Set(int64_t, T)`, `FromRange(begin, end)$`; `ContainerType = ArrayObj` | Immutable (COW) typed array |
| `ListObj` | class (9513c2f) | inherits `SeqBaseObj`; `CreateRepeated(n, val)$ -> ObjectPtr<ListObj>`; `static _type_index = kTVMFFIList = 75`, `static _type_key = "ffi.List"` | Mutable sequence container data |
| `List<T>` | class template (9513c2f) | inherits `ObjectRef`; `size() -> size_t`, `empty() -> bool`, `operator[](int64_t) -> T`, `push_back(T)`, `pop_back()`, `insert(int64_t, T)`, `erase(int64_t)`, `resize(int64_t)`, `Set(int64_t, T)`, `clear()`, `reserve(int64_t)`, `reverse()`; `ContainerType = ListObj` | Mutable typed sequence (no COW, not thread-safe, can form reference cycles) |
| `MapBaseObj` | class (5a6b211) | inherits `Object`; `void* data_`, `uint64_t size_`, `uint64_t slots_` (bit 63 = layout tag), `void (*data_deleter_)(void*)`; `size() -> size_t`, `count(key) -> size_t`, `at(key) -> const Any&` / `Any&`, `begin() -> iterator`, `end() -> iterator`, `find(key) -> iterator`, `erase(key/iter)`, `clear()`, `IsSmallMap() -> bool`; `static kSmallTagMask = 1ULL << 63`; protected: `InplaceSwitchTo(ObjectPtr<Object>&&)`, `Empty<MapObjType>()$`, `InsertMaybeReHash<MapObjType>(KVType&&, map)$ -> ObjectPtr<Object>`, `CreateFromRange<MapObjType, IterType>(first, last)$`, `CopyFrom<MapObjType>(MapBaseObj*)$` | Shared base for MapObj and DictObj; transparent to FFI type system (no type index) |
| `SmallMapBaseObj` | class (5a6b211) | inherits `MapBaseObj`; `NumSlots() -> uint64_t` (masks off MSB tag); `clear()`; `static kMaxSize` | Linear-scan small map layout (MSB of slots_ is set) |
| `DenseMapBaseObj` | class (5a6b211) | inherits `MapBaseObj`; `NumSlots() -> uint64_t` (identity; MSB always clear); `clear()` | Open-addressing dense hash map layout (MSB of slots_ is clear) |
| `MapObj` | class | inherits `MapBaseObj`; `static _type_index = 72`, `static _type_key = "ffi.Map"` | Thin subclass defining FFI type index for immutable Map (body nearly empty after 5a6b211) |
| `Map<K,V>` | class template | inherits `ObjectRef`; `size() -> size_t`, `at(K) -> V`, `count(K) -> bool`, `Set(K, V)`, `begin() -> iterator`, `end() -> iterator`; `ContainerType = MapObj` | Immutable (COW) typed map |
| `DictObj` | class (c1af3b3) | inherits `MapBaseObj`; `static _type_index = kTVMFFIDict = 76`, `static _type_key = "ffi.Dict"`; `sizeof(DictObj) == sizeof(MapBaseObj)` | Mutable dictionary data; shares MapBaseObj storage with MapObj |
| `Dict<K,V>` | class template (c1af3b3) | inherits `ObjectRef`; `Dict()`, `at(K) -> V`, `operator[](K) -> V`, `size() -> size_t`, `count(K) -> size_t`, `empty() -> bool`, `clear()`, `Set(K, V)`, `erase(K)`, `Get(K) -> optional<V>`, `begin() -> iterator`, `end() -> iterator`, `find(K) -> iterator`; `ContainerType = DictObj` | Mutable typed map with shared-reference semantics (no COW) |
| `MapTypeTraitsBase<Derived, MapRef, K, V>` | CRTP template (c1af3b3) | `CheckAnyStrict`, `GetMismatchTypeInfo`, `TryCastFromAnyView`, `TypeStr`; Derived must expose `kPrimaryTypeIndex`, `kOtherTypeIndex`, `kTypeName` | Shared type-traits logic enabling Map<->Dict cross-conversion |
| `ShapeObj` | class | inherits `Object + TVMFFIShapeCell`; `size() -> size_t`, `at(size_t) -> int64_t`; `static _type_index = 69` | Immutable int64 tuple data |
| `Shape` | class | inherits `ObjectRef`; `size() -> size_t`, `operator[](size_t) -> int64_t`; `ContainerType = ShapeObj` | Immutable dimension shape |
| `TensorObj` | class | inherits `Object + DLTensor`; `Optional<Shape> strides_data_` (protected, owns strides buffer); `static _type_index = 70`, `_type_key = "ffi.Tensor"` | DLPack tensor wrapper data; strides always non-null for ndim>0, may be null for zero-dim (renamed from `NDArrayObj`) |
| `Shape::StridesFromShape` | static method | `(const int64_t* data, int64_t ndim) -> Shape` | Compute row-major contiguous strides: strides[i] = product(shape[i+1:]) |
| `Tensor` | class | inherits `ObjectRef`; `data_ptr() -> void*`, `device() -> DLDevice`, `ndim() -> int32_t`, `dtype() -> DLDataType`, `size(int64_t idx) -> int64_t` (negative index wraps, 573d76f), `stride(int64_t idx) -> int64_t` (negative index wraps, 573d76f), `byte_offset() -> uint64_t`, `numel() -> int64_t`, `shape() -> ShapeView`, `strides() -> ShapeView`, `GetDLTensorPtr() -> const DLTensor*`, `IsContiguous() -> bool`, `IsAligned(size_t) -> bool`, `dim() -> int32_t` (alias for ndim, 573d76f), `sizes() -> ShapeView` (alias for shape, 573d76f), `is_contiguous() -> bool` (alias for IsContiguous, 573d76f), `FromDLPack(...)$`, `ToDLPack()`, `FromDLPackVersioned(...)$`, `ToDLPackVersioned()`, `FromEnvAlloc(env_alloc, shape, dtype, device)$` (f679fe5), `as_strided(shape, strides, element_offset) -> Tensor` (8888eb4), `FromNDAllocStrided<TNDAlloc>(alloc, shape, strides, dtype, device) -> Tensor` (8888eb4); `operator->()` removed (0dcd4d2); `ContainerType = TensorObj` | Tensor with method-based API, ATen-style aliases, strided views, and DLPack interop |
| `IsDirectAddressDevice` | inline function | `(const DLDevice&) -> bool` | Returns true for devices with direct memory addressing (CPU, CUDA, ROCm) |
| `TupleObj` | class | `void* data_; int32_t size_` | Heterogeneous fixed-size tuple data |
| `Tuple<Types...>` | class template | inherits `ObjectRef`; `size() -> size_t`, `operator[](size_t) -> Any`, `get<I>() const& -> auto`, `get<I>() && -> auto` (move if unique, 227bdd0); `ContainerType = TupleObj`; CTAD: `Tuple(UTypes&&...) -> Tuple<decay_t<UTypes>...>` | Fixed-size heterogeneous tuple with C++17 structured binding support |
| `get<I>(const Tuple<Types...>&)` | free function (ADL) | `-> tuple_element_t<I, tuple<Types...>>` | ADL-friendly get for structured bindings (227bdd0) |
| `get<I>(Tuple<Types...>&&)` | free function (ADL) | `-> tuple_element_t<I, tuple<Types...>>` | Move-out get for structured bindings (227bdd0) |
| `std::tuple_size<Tuple<Types...>>` | specialization | `integral_constant<size_t, sizeof...(Types)>` | Structured binding support (227bdd0) |
| `std::tuple_element<I, Tuple<Types...>>` | specialization | `tuple_element<I, tuple<Types...>>` | Structured binding support (227bdd0) |
| `Variant<V...>` | class template | inherits `VariantBase<all_object_ref_v<V...>>`; `is<T>() -> bool`, `get<T>() -> T`, `same_as(Variant) -> bool`. Inherits `ObjectRef` when all V are ObjectRef subtypes, otherwise backed by `Any` | Compile-time union with conditional ObjectRef inheritance |
| `TensorView` | class | `DLTensor tensor_` (shallow copy); `data_ptr() -> void*`, `device() -> DLDevice`, `ndim() -> int32_t`, `dtype() -> DLDataType`, `size(int64_t idx) -> int64_t` (negative index wraps, 573d76f), `stride(int64_t idx) -> int64_t` (negative index wraps, 573d76f), `byte_offset() -> uint64_t`, `numel() -> int64_t`, `shape() -> ShapeView`, `strides() -> ShapeView`, `IsContiguous() -> bool`, `dim() -> int32_t` (alias for ndim, 573d76f), `sizes() -> ShapeView` (alias for shape, 573d76f), `is_contiguous() -> bool` (alias for IsContiguous, 573d76f), `as_strided(shape, strides, element_offset) -> TensorView` (8888eb4; caller manages lifetime); `TypeTraits: storage_enabled=false, field_static_type_index=kTVMFFIDLTensorPtr`; `operator->()` removed (0dcd4d2) | Non-owning tensor view with ATen-style aliases; recommended parameter type for FFI kernel functions |
| `String::starts_with` | method (02d1a96) | `starts_with(const String&) -> bool`, `starts_with(string_view) -> bool`, `starts_with(const char*) -> bool`, `starts_with(const char*, size_t) -> bool` | Prefix check; core uses `memcmp`. Mirrors C++20 `std::string::starts_with` |
| `String::ends_with` | method (02d1a96) | `ends_with(const String&) -> bool`, `ends_with(string_view) -> bool`, `ends_with(const char*) -> bool`, `ends_with(const char*, size_t) -> bool` | Suffix check; core uses `memcmp` at `data() + size() - count`. Mirrors C++20 `std::string::ends_with` |
| `String::npos` | static constexpr (bd12b26) | `static constexpr size_t npos = static_cast<size_t>(-1)` | Sentinel for find() not-found result |
| `String::find` | method (bd12b26) | `find(const String&, size_t pos=0) -> size_t`, `find(const char*, size_t pos=0) -> size_t`, `find(const char*, size_t pos, size_t count) -> size_t` | Delegates to `std::string_view::find` |
| `String::substr` | method (bd12b26) | `substr(size_t pos=0, size_t count=npos) -> String` | Throws `std::out_of_range` if `pos > size()` |
| `ffi.ArrayContains` | registered function (5bc7fcd) | `(const ArrayObj*, const Any&) -> bool` | Linear search with AnyEqual. Enables Python `Array.__contains__` |
| `ffi.MapGetItemOrMissing` | registered function | `(MapObj*, Any key) -> Any` | Returns value if key exists, otherwise returns singleton missing object (438f643) |
| `ffi.GetInvalidObject` | registered function (86c4042) | `() -> ObjectRef` | Returns the singleton sentinel object (renamed from `ffi.MapGetMissingObject`; now general-purpose, not Map-specific) |
| `ffi.Dict` | registered function (c1af3b3) | `(args...) -> DictObj*` | Packed constructor (alternating key/value args) |
| `ffi.DictSize` | registered function (c1af3b3) | `(DictObj*) -> int64_t` | Dict size |
| `ffi.DictGetItem` | registered function (c1af3b3) | `(DictObj*, Any) -> Any` | Get item by key |
| `ffi.DictSetItem` | registered function (c1af3b3) | `(Dict<Any,Any>, Any, Any) -> void` | Set item by key |
| `ffi.DictCount` | registered function (c1af3b3) | `(DictObj*, Any) -> int64_t` | Count key occurrences (0 or 1) |
| `ffi.DictErase` | registered function (c1af3b3) | `(Dict<Any,Any>, Any) -> void` | Erase by key |
| `ffi.DictClear` | registered function (c1af3b3) | `(Dict<Any,Any>) -> void` | Clear all entries |
| `ffi.DictForwardIterFunctor` | registered function (c1af3b3) | `(DictObj*) -> Function` | Returns forward iteration functor |
| `ffi.DictGetItemOrMissing` | registered function (c1af3b3) | `(DictObj*, Any) -> Any` | Returns value or singleton missing sentinel |
| `GetDataSize(const Tensor&)` | function | `-> size_t` | Compute data buffer size from numel and dtype (0dcd4d2) |
| `GetDataSize(const TensorView&)` | function | `-> size_t` | Same for TensorView (0dcd4d2) |
| `AnyHash` | struct | `operator()(const Any&) -> size_t`; private: `GetAnyHashTypeAttrColumn()$`, `CallCustomAnyHash(TVMFFIAny, Any)$` | Hash functor for Any keys in Map; normalizes small/large strings; dispatches to `__any_hash__` type attr for Object types (39d9b2b) |
| `AnyEqual` | struct | `operator()(const Any&, const Any&) -> bool`; private: `GetAnyEqualTypeAttrColumn()$`, `CallCustomAnyEqual(TVMFFIAny, Any, Any)$` | Equality functor for Any keys in Map; uses Bytes::memequal for strings; dispatches to `__any_equal__` type attr for Object types (39d9b2b) |
| `Bytes::memequal` | static function | `(const void* lhs, const void* rhs, size_t lhs_count, size_t rhs_count) -> bool` | Fast equality: size-mismatch rejection + pointer check + memcmp |
| `Bytes::memncmp` | static function | `(const char* lhs, const char* rhs, size_t lhs_count, size_t rhs_count) -> int` | Lexicographic comparison for ordering |
| `IterAdapter<Converter, TIter>` | class template | `value_type = ResultType`; `reference = const ResultType`; `pointer = const ResultType*`; `operator*() const -> reference` (14f3c82: fixed to match InputIterator requirement) | Iterator adapter wrapping TIter with Converter |
| `ReverseIterAdapter<Converter, TIter>` | class template | Same type aliases as IterAdapter; identical InputIterator fix (14f3c82) | Reverse iterator adapter |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `Array.__contains__` (5bc7fcd) | `(self, value: object) -> bool` | Linear search via `ffi.ArrayContains` |
| `Array.__bool__` (46ab644) | `(self) -> bool` | Returns `len(self) > 0`. Previously `True` for empty arrays. |
| `Map.__bool__` (46ab644) | `(self) -> bool` | Returns `len(self) > 0`. Previously `True` for empty maps. |
| `List` (9513c2f) | `@register_object("ffi.List") class List(core.Object, MutableSequence[T])` | Mutable sequence container |
| `List.__init__` (9513c2f) | `(self, input_list: Iterable[T]) -> None` | Create from iterable |
| `List.__setitem__` (9513c2f) | `(self, idx, val) -> None` | Set element by index |
| `List.__delitem__` (9513c2f) | `(self, idx) -> None` | Delete element by index |
| `List.append` (9513c2f) | `(self, val: T) -> None` | Append element |
| `List.insert` (9513c2f) | `(self, idx: int, val: T) -> None` | Insert element at index |
| `List.pop` (9513c2f) | `(self, idx: int = -1) -> T` | Remove and return element |
| `List.reverse` (9513c2f) | `(self) -> None` | Reverse in place |
| `MISSING` (86c4042) | `MISSING: Object` (in `tvm_ffi.core` and `tvm_ffi.container`) | Singleton sentinel for missing map lookups; initialized via `ffi.GetInvalidObject` |
| `Dict` (c1af3b3) | `@register_object("ffi.Dict") class Dict(core.Object, MutableMapping[K, V])` | Mutable map container |
| `Dict.__init__` (c1af3b3) | `(self, input_dict: Mapping[K, V] \| None = None) -> None` | Create from mapping or empty |
| `Dict.__setitem__` (c1af3b3) | `(self, k: K, v: V) -> None` | Set entry |
| `Dict.__delitem__` (c1af3b3) | `(self, k: K) -> None` | Delete entry |
| `Dict.get` (c1af3b3) | `(self, key: K, default=None) -> V \| None` | Sentinel-based get |
| `Dict.pop` (c1af3b3) | `(self, key: K, *args) -> V` | Remove and return value |
| `Dict.clear` (c1af3b3) | `(self) -> None` | Clear all entries |
| `Dict.update` (c1af3b3) | `(self, other: Mapping[K, V]) -> None` | Merge entries from other mapping |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | — | Rust bindings not in scope for this commit |
