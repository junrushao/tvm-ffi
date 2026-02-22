# 015 -- Container System

- Doc ID: 015-container-system
- Status: Approved
- Last Updated: 2026-02-22
- Owners: Junru Shao, Tianqi Chen

## Overview

The TVM FFI container system provides a family of heap-allocated, ref-counted
container types that can be stored in `Any` and passed across the FFI boundary
(C++, Python, Rust). The containers are split into two categories: **immutable**
(copy-on-write) containers (`Array`, `Map`, `Tuple`) for stable snapshots and IR
node children, and **mutable** (shared-reference) containers (`List`, `Dict`) for
incremental accumulation and caches. In addition to these five core containers,
three special-purpose containers are provided: `String` (UTF-8 text with
small-string optimization), `Bytes` (raw binary data), and `Shape` (tensor
dimension tuples). All container objects derive from `Object` and participate in
the standard object system with type indices, ref-counting, and `ObjectRef`
wrappers.

## Key Design

### Container class hierarchy

All containers are heap-allocated `Object` subclasses. Sequences and maps share
transparent base classes that factor out common logic without introducing extra
type indices into the FFI type system:

```text
Object
+-- SeqBaseObj (no type index, transparent base)
|   +-- ArrayObj   (kTVMFFIArray = 71)
|   +-- ListObj    (kTVMFFIList  = 75)
+-- MapBaseObj (no type index, transparent base)
|   +-- SmallMapBaseObj  --+-- dispatched at runtime via MSB tag
|   +-- DenseMapBaseObj  --+
|   +-- MapObj   (kTVMFFIMap  = 72)   [inherits MapBaseObj]
|   +-- DictObj  (kTVMFFIDict = 76)   [inherits MapBaseObj]
+-- ShapeObj  (kTVMFFIShape = 69)
+-- details::BytesObjBase (no type index)
    +-- details::StringObj (kTVMFFIStr   = 65)
    +-- details::BytesObj  (kTVMFFIBytes = 66)
```

### Container comparison table

| Container | C++ Ref Class | C++ Obj Class | Python Class | Mutability | Python ABC | Type Index | Static Type Key |
|-----------|---------------|---------------|--------------|------------|------------|------------|-----------------|
| Array | `Array<T>` | `ArrayObj` | `tvm_ffi.Array` | Immutable (COW) | `Sequence` | 71 (`kTVMFFIArray`) | `ffi.Array` |
| List | `List<T>` | `ListObj` | `tvm_ffi.List` | Mutable | `MutableSequence` | 75 (`kTVMFFIList`) | `ffi.List` |
| Tuple | `Tuple<Ts...>` | `ArrayObj` (shared) | N/A (backed by `tvm_ffi.Array`) | Immutable (COW) | N/A | 71 (`kTVMFFIArray`) | N/A |
| Map | `Map<K,V>` | `MapObj` | `tvm_ffi.Map` | Immutable (COW) | `Mapping` | 72 (`kTVMFFIMap`) | `ffi.Map` |
| Dict | `Dict<K,V>` | `DictObj` | `tvm_ffi.Dict` | Mutable | `MutableMapping` | 76 (`kTVMFFIDict`) | `ffi.Dict` |
| String | `String` | `details::StringObj` | `str` | Immutable | N/A | 65 (`kTVMFFIStr`) / 11 (`kTVMFFISmallStr`) | `ffi.Str` |
| Bytes | `Bytes` | `details::BytesObj` | `bytes` | Immutable | N/A | 66 (`kTVMFFIBytes`) / 12 (`kTVMFFISmallBytes`) | `ffi.Bytes` |
| Shape | `Shape` | `ShapeObj` | `tvm_ffi.Shape` | Immutable | N/A | 69 (`kTVMFFIShape`) | `ffi.Shape` |

Key distinctions:

- `Tuple` reuses `ArrayObj`; it is a C++ compile-time typed wrapper with no
  distinct type index.
- `String` and `Bytes` have a dual type-index system (small inline value vs
  heap-allocated object).
- `Array` and `List` share `SeqBaseObj`; `Map` and `Dict` share `MapBaseObj`.

### Immutable containers (copy-on-write)

**Array<T>** is the primary immutable sequence. It is backed by `ArrayObj`, which
extends `SeqBaseObj`. Elements are stored as contiguous `Any` values inline after
the object header via `make_inplace_array_object`. Copy-on-write semantics mean
that `CopyOnWrite()` checks `data_.unique()`; if the storage is shared, a new
backing `ArrayObj` is allocated (moved from if unique, copied otherwise). The
expansion factor is `kIncFactor = 2` with initial size `kInitSize = 4`.

```cpp
// Copy-on-write semantics
Array<int> a = {1, 2, 3};
Array<int> b = a;       // b shares the same ArrayObj
a.push_back(4);         // copy-on-write: a gets new backing storage
assert(a.size() == 4);
assert(b.size() == 3);  // b is unchanged
```

`Array::Map(fmap)` applies a function to each element with three optimization
paths: (a) mutate-in-place if `data_.unique()` and same output type, (b)
copy-on-write identity if all mapped elements are identical to originals
(checked via `same_as`), and (c) full copy only when elements actually change.

**Map<K,V>** is the immutable associative container. It is backed by `MapObj`
(which extends `MapBaseObj`), using copy-on-write via `CopyOnWrite()` and
`InsertMaybeReHash`. The `operator[]` returns `const V`; mutations go through
`Set()`, which creates a new `MapObj` when the storage is shared.

```cpp
Map<String, int> m = {{"Alice", 100}, {"Bob", 95}};
Map<String, int> m2 = m;  // shares same MapObj
m.Set("Charlie", 88);     // copy-on-write
assert(m.size() == 3);
assert(m2.size() == 2);   // m2 unchanged
```

### Mutable containers (shared reference)

**List<T>** is the mutable sequence. It is backed by `ListObj`, which extends
`SeqBaseObj`. Unlike `Array`, `List` has no copy-on-write: mutations happen
directly on the shared `ListObj`, and all handles see changes immediately. Storage
is a separately heap-allocated `Any*` buffer (via `::operator new`), with a
`RawDataDeleter` as the `data_deleter`. `Reserve(n)` reallocates by moving
elements via the noexcept `Any` move constructor.

```cpp
List<int> a = {1, 2, 3};
List<int> b = a;       // b shares the same ListObj
a.push_back(4);        // in-place mutation
assert(a.size() == 4);
assert(b.size() == 4); // b sees the mutation
```

**Dict<K,V>** is the mutable associative container. It is backed by `DictObj`
(which extends `MapBaseObj`, with `sizeof(DictObj) == sizeof(MapBaseObj)`). Like
`List`, `Dict` has no copy-on-write: `Set()` calls
`InsertMaybeReHash<DictObj>`, and if rehash is needed, uses `InplaceSwitchTo()`
to swap the new storage into the existing `DictObj` so that all handles continue
to point to the same object.

```cpp
Dict<String, int> d = {{"Alice", 100}};
Dict<String, int> d2 = d;  // d2 shares same DictObj
d.Set("Bob", 95);          // in-place mutation
assert(d.size() == 2);
assert(d2.size() == 2);    // d2 sees the mutation
```

### Tuple<Types...>

`Tuple<Types...>` provides compile-time type safety via variadic templates, backed
by `ArrayObj` (the same underlying storage as `Array`). Each position has a
distinct type accessed through `get<I>()`, which returns
`std::tuple_element_t<I, std::tuple<Types...>>`. `Set<I>(value)` performs
copy-on-write via `CopyIfNotUnique()`.

Structured bindings are supported via `std::tuple_size` and `std::tuple_element`
specializations in `namespace std`, plus ADL-friendly `get()` free functions. A
C++17 deduction guide enables `Tuple(1, String("hello"), true)` to deduce
`Tuple<int, String, bool>`.

Tuple has no distinct type index; it reuses `kTVMFFIArray` (71).
`TypeTraits<Tuple<Types...>>` validates both the type index and that the array
has exactly `sizeof...(Types)` elements with matching types.

```cpp
Tuple<int, String, bool> t(42, "hello", true);
int x = t.get<0>();          // 42
String s = t.get<1>();       // "hello"

// Structured bindings (C++17)
auto [a, b, c] = t;

// Copy-on-write Set
t.Set<0>(100);               // copies if not uniquely owned
```

### String and Bytes

**Three-form string representation.** `String` is not an `ObjectRef`; it is a
value type wrapping `details::BytesBaseCell`, which holds a `TVMFFIAny`.
Three forms are discriminated by type index:

1. **RawStr** (`kTVMFFIRawStr = 3`): non-owning `const char*` pointer. Only
   valid in `AnyView`, never stored in containers.
2. **SmallStr** (`kTVMFFISmallStr = 11`): inline string of up to 7 bytes stored
   directly in the `TVMFFIAny::v_bytes` field. No heap allocation.
3. **Str** (`kTVMFFIStr = 65`): heap-allocated `details::StringObj` (extends
   `BytesObjBase` which extends `Object` + `TVMFFIByteArray`). Data is either
   inplace (after object header via `make_inplace_array_object`) or backed by
   `std::string` (via `BytesObjStdImpl<StringObj>`).

Because `String` can be a `SmallStr` (not a heap object) or `Str` (a heap
object), its `field_static_type_index` is `kTVMFFIAny`. `TypeTraits<String>`
checks for `kTVMFFISmallStr || kTVMFFIStr` in `CheckAnyStrict`, and also accepts
`kTVMFFIRawStr` in `TryCastFromAnyView` (converting to an owned `String`).

**Bytes** mirrors `String` but for raw byte data, mapping to Python `bytes`.
Three forms: `kTVMFFISmallBytes = 12` (inline), `kTVMFFIBytes = 66` (heap), and
`kTVMFFIByteArrayPtr` (non-owning). Both share `details::BytesObjBase`.

**Dependency placement.** `String` lives in `tvm/ffi/string.h` (not
`tvm/ffi/container/`) because `any.h` depends on `string.h` (for hash/equality
of string values), and containers depend on `any.h`. The dependency chain is:
`any -> string -> object`.

### Shape

`ShapeObj` extends `Object` and `TVMFFIShapeCell` (C ABI struct with
`int64_t* data` and `size_t size`). `Shape` is the ref wrapper, declared as
non-nullable (`TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE`). Type index:
`kTVMFFIShape = 69`.

Two allocation strategies are provided:

1. **Inplace**: `make_inplace_array_object<ShapeObj, int64_t>(length)` stores
   `int64_t` data immediately after the `ShapeObj` header.
2. **Std-backed**: `ShapeObjStdImpl` stores a `std::vector<int64_t>`, used when
   constructing from `std::vector<int64_t>`.

A lightweight non-owning view, `ShapeView`, holds a `TVMFFIShapeCell` with no
ref counting. `TypeTraits<Shape>` uses
`ObjectRefWithFallbackTraitsBase<Shape, Array<int64_t>>`, allowing automatic
conversion from `Array<int64_t>` to `Shape` (but not the reverse).

### SeqBaseObj: shared sequence infrastructure

`SeqBaseObj` (`include/tvm/ffi/container/seq_base.h`) is the common base for
`ArrayObj` and `ListObj`. It inherits from `Object` (ref counting) and
`TVMFFISeqCell` (C ABI struct: `void* data`, `int64_t size`, `int64_t capacity`,
`void (*data_deleter)(void*)`). It is transparent to the FFI type system -- it
has no type index of its own.

`SeqBaseObj` provides shared operations: `size()`, `capacity()`, `at()`,
`front()`, `back()`, `begin()`/`end()`, `clear()`, `SetItem()`, `pop_back()`,
`erase()`, `insert()`, `Reverse()`, `resize()`. Protected helpers include
`MutableBegin()`, `MutableEnd()`, `EmplaceInit()`, `EnlargeBy()`, `ShrinkBy()`,
`MoveElementsLeft()`, `MoveElementsRight()`.

The CRTP `SeqTypeTraitsBase<Derived, SeqRef, T>` provides shared type-checking
logic. Cross-type acceptance is built in: `Array<T>` has
`kOtherTypeIndex = kTVMFFIList`, and `List<T>` has
`kOtherTypeIndex = kTVMFFIArray`. This means a function taking `Array<T>` can
accept a `List<T>` argument (elements are copied to a new `Array`).

### MapBaseObj and MSB tag dispatch

`MapBaseObj` is the transparent base for `MapObj` and `DictObj`. It holds
`data_`, `size_`, `slots_`, and `data_deleter_`. Two concrete implementations
are dispatched at runtime:

1. **SmallMapBaseObj**: Linear scan over up to `kMaxSize = 4` entries. KV pairs
   are stored inplace after the object header. Initial allocation:
   `kInitSize = 2` slots.
2. **DenseMapBaseObj**: Array-based hash table with Fibonacci hashing
   (`coeff = 11400714819323198485`), power-of-2 table size, 1-byte metadata per
   slot, 16-element data blocks, and a max load factor of 0.99.

The MSB (bit 63) of `MapBaseObj::slots_` discriminates the layout:

- MSB set: SmallMap. `NumSlots()` masks off the tag.
- MSB clear: DenseMap. `NumSlots()` returns `slots_` directly.

```cpp
#define TVM_FFI_DISPATCH_MAP(base, var, body)   \
  {                                             \
    if ((base)->IsSmallMap()) {                 \
      SmallMapBaseObj* var = ...;               \
      body;                                     \
    } else {                                    \
      DenseMapBaseObj* var = ...;               \
      body;                                     \
    }                                           \
  }
```

`DenseMapBaseObj` preserves insertion order via a doubly-linked iteration list
through all entries (`iter_list_head_`, `iter_list_tail_`, and `prev`/`next`
fields per `ItemType`). `SmallMapBaseObj` preserves order via `memmove` on erase.

When `SmallMapBaseObj` is full at `kMaxSize` (4 entries) and a new insert is
needed, `MapBaseObj::InsertMaybeReHash` detects this and transitions to a
`DenseMap` via `CreateFromRange`. For `Dict` (mutable), `InplaceSwitchTo()`
replaces the SmallMap's memory layout in-place with the DenseMap's fields, since
`sizeof(SmallMapBaseObj) + kInitSize * sizeof(KVType) >= sizeof(DenseMapBaseObj)`.
The destructor cross-checks via `IsSmallMap()` to call the correct cleanup.

### Thread safety contracts

- **Immutable containers** (`Array`, `Tuple`, `Map`): Safe for concurrent
  read-only access. COW mutations produce a new backing object when the storage
  is shared (ref count > 1), leaving the original unchanged. However, mutating
  a single handle from multiple threads without synchronization is still unsafe
  (the COW check + copy is not atomic).
- **Mutable containers** (`List`, `Dict`): NOT thread-safe. All mutations go
  directly to the shared backing object. External synchronization (mutex, etc.)
  is required for concurrent access.
- **String/Bytes/Shape**: Immutable once constructed. Safe for concurrent read
  access.

### Python auto-conversion rules

- Python `list` and `tuple` are converted to `Array` when passed to FFI functions.
- Python `dict` is converted to `Map` when passed to FFI functions.
- Return values preserve the actual container type: `Array` returns as
  `tvm_ffi.Array`, `List` as `tvm_ffi.List`, `Map` as `tvm_ffi.Map`, `Dict` as
  `tvm_ffi.Dict`.
- `tvm_ffi.Array` implements `collections.abc.Sequence`.
- `tvm_ffi.List` implements `collections.abc.MutableSequence`.
- `tvm_ffi.Map` implements `collections.abc.Mapping`.
- `tvm_ffi.Dict` implements `collections.abc.MutableMapping`.

### Type index assignments

| Type Index | Value | Name | Category |
|------------|-------|------|----------|
| `kTVMFFISmallStr` | 11 | Inline string (<=7 bytes) | Inline value |
| `kTVMFFISmallBytes` | 12 | Inline bytes (<=7 bytes) | Inline value |
| `kTVMFFIStr` | 65 | Heap-allocated string object | Static object |
| `kTVMFFIBytes` | 66 | Heap-allocated bytes object | Static object |
| `kTVMFFIShape` | 69 | Shape object | Static object |
| `kTVMFFIArray` | 71 | Array object (also Tuple) | Static object |
| `kTVMFFIMap` | 72 | Immutable map object | Static object |
| `kTVMFFIList` | 75 | Mutable list object | Static object |
| `kTVMFFIDict` | 76 | Mutable dict object | Static object |

All container type indices fall in the `[kTVMFFIStaticObjectBegin=64,
kTVMFFIStaticObjectEnd)` range. `SmallStr`/`SmallBytes` are below this range
(they are not heap objects but inline values in `TVMFFIAny`). `Tuple` does not
have its own type index; it reuses `kTVMFFIArray = 71`.

### Decision matrix: when to use each type

| Use Case | Recommended Container | Rationale |
|----------|----------------------|-----------|
| Immutable snapshot of a sequence (e.g., IR node children) | `Array<T>` | COW ensures callers' views are stable |
| Building up a sequence incrementally (loop accumulation) | `List<T>` | Avoids repeated COW copies |
| Fixed heterogeneous collection (multi-typed return value) | `Tuple<T1, T2, ...>` | Compile-time type safety per position |
| Immutable configuration or lookup table | `Map<K, V>` | COW ensures stability |
| Mutable key-value store (caches, accumulating results) | `Dict<K, V>` | In-place mutation, no COW overhead |
| Tensor dimensions | `Shape` | Specialized for int64_t, compact representation |
| Text data (names, keys) | `String` | Maps to Python `str`, small-string optimization |
| Raw binary data | `Bytes` | Maps to Python `bytes`, distinct from String |

Additional guidance:

- Prefer `Array<Any>` over `Array<SomeObjectRef>` when type checking overhead at
  each access is undesirable (deferred checking pattern).
- For function parameters that only need to read a sequence, accept `Array<T>` --
  it will also accept `List<T>` arguments via automatic conversion in TypeTraits.

## APIs

### C++ API

```cpp
// Array: immutable sequence with COW (include/tvm/ffi/container/array.h).
template <typename T>
class Array : public ObjectRef {
  const T operator[](int64_t i) const;
  void push_back(const T& item);        // COW
  void Set(int64_t i, T value);          // COW
  void insert(iterator pos, const T& val);
  void pop_back();
  void erase(iterator pos);
  void clear();
  void reserve(int64_t n);
  void resize(int64_t n);
  size_t size() const;
  template <typename F, typename U = std::invoke_result_t<F, T>>
  Array<U> Map(F fmap) const;
};

// List: mutable sequence (include/tvm/ffi/container/list.h).
template <typename T>
class List : public ObjectRef {
  T operator[](int64_t i) const;
  void push_back(const T& item);        // in-place
  void Set(int64_t i, T value);          // in-place
  void insert(iterator pos, const T& val);
  void pop_back();
  void erase(iterator pos);
  void clear();
  void reserve(int64_t n);
  void resize(int64_t n);
  size_t size() const;
};

// Map: immutable associative container with COW (include/tvm/ffi/container/map.h).
template <typename K, typename V>
class Map : public ObjectRef {
  const V operator[](const K& key) const;
  void Set(const K& key, const V& value);  // COW
  size_t count(const K& key) const;
  size_t size() const;
  iterator begin() const;
  iterator end() const;
  iterator find(const K& key) const;
};

// Dict: mutable associative container (include/tvm/ffi/container/dict.h).
template <typename K, typename V>
class Dict : public ObjectRef {
  V operator[](const K& key) const;
  void Set(const K& key, const V& value);  // in-place
  void erase(const K& key);                // in-place
  void clear();
  size_t count(const K& key) const;
  size_t size() const;
  std::optional<V> Get(const K& key) const;
  iterator begin() const;
  iterator end() const;
};

// Tuple: compile-time typed sequence (include/tvm/ffi/container/tuple.h).
template <typename... Types>
class Tuple : public ObjectRef {
  template <size_t I> auto get() const;
  template <size_t I, typename U> void Set(U&& item);  // COW
};

// Shape: tensor dimension tuple (include/tvm/ffi/container/shape.h).
class Shape : public ObjectRef {
  int64_t operator[](size_t idx) const;
  size_t size() const;
  int64_t Product() const;
  static Shape StridesFromShape(ShapeView shape);
};

// String: UTF-8 text with small-string optimization (include/tvm/ffi/string.h).
class String {
  const char* data() const noexcept;
  size_t size() const noexcept;
  int compare(const String& other) const;
  String substr(size_t pos, size_t count = npos) const;
  size_t find(const char* str, size_t pos = 0) const;
  bool starts_with(const char* prefix) const;
  bool ends_with(const char* suffix) const;
};

// Bytes: raw binary data (include/tvm/ffi/string.h).
class Bytes {
  const char* data() const;
  size_t size() const;
  static bool memequal(const void* lhs, const void* rhs,
                       size_t lhs_count, size_t rhs_count);
};
```

### C ABI type indices

Defined in `include/tvm/ffi/c_api.h`:

- `kTVMFFISmallStr = 11`, `kTVMFFISmallBytes = 12` (inline values)
- `kTVMFFIStr = 65`, `kTVMFFIBytes = 66` (heap objects)
- `kTVMFFIShape = 69`
- `kTVMFFIArray = 71`, `kTVMFFIMap = 72`
- `kTVMFFIList = 75`, `kTVMFFIDict = 76`

### Python API

```python
import tvm_ffi

# Array (Sequence) -- read-only after construction
arr = tvm_ffi.Array([1, 2, 3])
assert arr[0] == 1
assert len(arr) == 3

# List (MutableSequence) -- in-place mutation
lst = tvm_ffi.List([1, 2, 3])
lst.append(4)
lst[0] = 10
del lst[1]

# Map (Mapping) -- read-only after construction
m = tvm_ffi.Map({"key": "value"})
assert m["key"] == "value"

# Dict (MutableMapping) -- in-place mutation
d = tvm_ffi.Dict({"key": "value"})
d["new_key"] = 42
del d["key"]
```

### Global functions (registered in `src/ffi/container.cc`)

| Function name | Description |
|---------------|-------------|
| `ffi.ListAppend` | Append element to List |
| `ffi.ListInsert` | Insert element at index |
| `ffi.ListPop` | Remove and return element |
| `ffi.ListClear` | Clear all elements |
| `ffi.DictSetItem` | Set key-value pair |
| `ffi.DictDelItem` | Delete key |
| `ffi.DictClear` | Clear all entries |
| `ffi.DictPopItem` | Remove and return arbitrary entry |
| `ffi.DictUpdate` | Merge another dict |

## Implementation

### Key source files

| File | Contents |
|------|----------|
| `include/tvm/ffi/container/seq_base.h` | `SeqBaseObj`, `SeqTypeTraitsBase` -- shared sequence infrastructure |
| `include/tvm/ffi/container/array.h` | `ArrayObj`, `Array<T>` -- immutable COW sequence |
| `include/tvm/ffi/container/list.h` | `ListObj`, `List<T>` -- mutable sequence |
| `include/tvm/ffi/container/tuple.h` | `Tuple<Types...>` -- compile-time typed tuple backed by ArrayObj |
| `include/tvm/ffi/container/map_base.h` | `MapBaseObj`, `SmallMapBaseObj`, `DenseMapBaseObj`, `MapTypeTraitsBase` -- shared map infrastructure |
| `include/tvm/ffi/container/map.h` | `MapObj`, `Map<K,V>` -- immutable COW map |
| `include/tvm/ffi/container/dict.h` | `DictObj`, `Dict<K,V>` -- mutable map |
| `include/tvm/ffi/container/shape.h` | `ShapeObj`, `Shape`, `ShapeView` -- tensor shape container |
| `include/tvm/ffi/string.h` | `String`, `Bytes`, `BytesObjBase`, `StringObj`, `BytesObj` -- text and binary data |
| `include/tvm/ffi/c_api.h` | Type index definitions for all container types |
| `python/tvm_ffi/container.py` | Python `Array`, `List`, `Map`, `Dict` classes |
| `src/ffi/container.cc` | Global function registrations for List/Dict mutations |
| `docs/concepts/containers.rst` | Sphinx documentation for containers |

### Performance characteristics

**Typed container access overhead.** `Array<T>` and `Map<K,V>` validate element
types on access. Each `operator[]` or iterator dereference calls
`CopyFromAnyViewAfterCheck<T>`, which includes a type check. For `Array<Any>`
and `Map<Any, Any>`, `CheckAnyStrict` returns true immediately -- no per-element
type check is needed.

**Cross-type acceptance.** When a function takes `Array<T>` but receives a
`List<T>`, `TryCastFromAnyView` creates a new `Array` by copying all elements
from the `List` (O(n) with type checking). Similarly, `Map<K,V>` accepts
`Dict<K,V>` and vice versa.

**Map performance.** SmallMap (up to 4 entries) uses O(n) linear scan per lookup,
optimal for very small maps due to cache locality and no hashing overhead.
DenseMap (5+ entries) provides O(1) amortized lookup with Fibonacci hashing.
Insertion-order iteration adds a `prev`/`next` pointer per entry (16 bytes
overhead per entry in DenseMap).

**Array COW optimization.** `Array::Map(fmap)` avoids unnecessary copying through
three paths: mutate-in-place (if `data_.unique()` and same output type),
copy-on-write identity (if all mapped elements are identical to originals), and
full copy only when elements actually change.

## History

- `7e0a4b3`: Stabilized container ABI -- `ArrayObj` layout finalized with `SeqCell` C struct
- `03e8a6b`: Updated Map ABI with MSB tag dispatch for flexible SmallMap/DenseMap switching
- `5a6b211`: Cleaned up and improved map/array containers; extracted `map_base.h`
- `043d9f6`: Improved String and Bytes C API with `TVMFFIByteArray` handling
- `f9d2bff`: Moved `StringObj`/`BytesObj` into `details` namespace
- `ba0ea87`: Improved string equal/hash handling with `Bytes::memequal`
- `25c25ae`: Introduced `TVMFFIHandleInitOnce` C API for container initialization
- `7786133`: TypeSchema emits distinct container type origins; `docs/concepts/containers.rst` added

## Related

- `.repo-knowledge/design/001-type-erased-value-system.md` -- Any/AnyView and TypeTraits
- `.repo-knowledge/design/003-c-abi-stability.md` -- C ABI constraints on container layouts
- `.repo-knowledge/design/011-mutable-containers.md` -- List/Dict introduction history
- `.repo-knowledge/adr/005-small-string-inline-abi.md` -- Small string inline ABI decision
- `.repo-knowledge/adr/006-msb-tag-map-dispatch.md` -- MSB tag decision for Map dispatch
- `.repo-knowledge/adr/017-mutable-vs-immutable-containers.md` -- Rationale for separate mutable types
- `docs/concepts/containers.rst` -- User-facing container documentation
