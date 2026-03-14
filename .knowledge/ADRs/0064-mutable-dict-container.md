---
scope:
  - "0005-containers"
  - "0001-c-abi"
---
# Introduce Mutable Dict Container

**TL;DR**: `Dict<K,V>` is a new mutable dictionary container that shares `MapBaseObj` internals with `Map<K,V>` but provides in-place mutation semantics (no copy-on-write). It uses `InplaceSwitchTo` to preserve object identity during rehashing, completing the mutable/immutable container pairs (Array/List for sequences, Map/Dict for associative containers).

## Context

The FFI container system had an asymmetry: sequences had both immutable (`Array`) and mutable (`List`) variants, but associative containers only had immutable `Map`. `Map::Set()` uses COW, creating a new `MapObj` when the ref count exceeds 1. This prevents idiomatic in-place dictionary construction patterns and forces Python code to repeatedly rebind the `Map` variable.

The `List` precedent (commit `9513c2f` #443) demonstrated that mutable containers with shared reference semantics are valuable for builder patterns, accumulation loops, and interop with Python's `MutableMapping` protocol. Dict fills the same role for key-value containers.

Usecases:
- **Builder pattern**: Accumulate key-value pairs in a loop without COW overhead. `d.Set("key", val)` modifies `d` in place; all references to `d` see the update.
- **Python MutableMapping**: `Dict` implements `collections.abc.MutableMapping`, enabling `dict[k] = v`, `del dict[k]`, `dict.pop(k)`, and other standard Python dict operations.
- **Future Dict-to-Map freeze**: Because `DictObj` and `MapObj` share the same `MapBaseObj` layout, a future `freeze()` operation could convert a mutable Dict to an immutable Map by changing the type index.

Design Decisions:
- **`DictObj` extends `MapBaseObj`** with type index `kTVMFFIDict = 76`. `sizeof(DictObj) == sizeof(MapBaseObj)` (enforced by `static_assert`). No additional fields.
- **`InplaceSwitchTo` for rehash stability**: When `Dict::Set()` triggers a rehash via `InsertMaybeReHash`, the newly allocated hash table is swapped into the existing `DictObj` via `InplaceSwitchTo`. This preserves the object pointer identity, ensuring all existing references see the updated storage. Map does not use `InplaceSwitchTo`; it replaces the `ObjectPtr` via COW.
- **`InsertMaybeReHash` return-value pattern**: Returns `ObjectPtr<Object>` (new container or nullptr) instead of mutating a pointer. This is necessary because Dict must detect rehashing to call `InplaceSwitchTo`, while Map simply assigns the new pointer.
- **Cycle detection in serialization/structural ops**: Because Dict is mutable, it can form reference cycles. Deep copy, JSON writer, serialization, structural equal, and structural hash all include cycle detection guards for Dict (same pattern as List).
- **TypeTraits cross-acceptance**: `TypeTraits<Dict<K,V>>` has `kPrimaryTypeIndex = kTVMFFIDict` and `kOtherTypeIndex = kTVMFFIMap`, enabling a `Dict<K,V>` parameter to accept both Dict and Map sources. Similarly, `TypeTraits<Map<K,V>>` accepts both Map and Dict.
- **Python Dict class** (`container.py`): Registered as `@register_object("ffi.Dict")`, inherits `MutableMapping[K, V]`. Construction via `_ffi_api.Dict(*list_kvs)`. Views (`keys()`, `values()`, `items()`) use `DictForwardIterFunctor` (separate from `MapForwardIterFunctor`). `KeysView`, `ValuesView`, `ItemsView` were generalized with an `iter_functor_getter` parameter to support both Map and Dict.

**Alternatives considered**:

1. **Add mutability flag to MapObj**: Simpler (no new type), but conflates mutable and immutable semantics. Callers of `Map<K,V>` rely on the invariant that aliased mutations do not occur. A flag would break this invariant for all Map users.
2. **Python-only dict wrapper (no C++ type)**: Would avoid a C ABI change but would not support Dict in C++ or Rust, and would prevent cross-language passing of mutable dictionaries.
3. **Use std::unordered_map behind an Object**: Would lose the dense map probing performance, MSB layout tag, inplace small-map optimization, and cross-DLL safety that `MapBaseObj` provides.

**Consequences**:
- New C ABI type index `kTVMFFIDict = 76`. Older consumers that do not recognize this index will fail gracefully (type mismatch error).
- Python's `tvm_ffi` module exports `Dict` alongside `Array`, `List`, `Map`.
- `KeysView`, `ValuesView`, `ItemsView` in `container.py` now accept an `iter_functor_getter` parameter, changing their constructor signature (backward compatible since the parameter defaults to Map's functor).
- `SmallMapBaseObj` destructor complexity increased: must check `IsSmallMap()` to handle the case where `InplaceSwitchTo` promoted a small map to dense layout.

**Rollback**: Remove `include/tvm/ffi/container/dict.h`, `DictObj` registration, `kTVMFFIDict` from `c_api.h`, Python `Dict` class from `container.py`, and all Dict-related serialization/structural/deep-copy/repr handlers. `MapBaseObj` and `InplaceSwitchTo` can remain (they are independently useful for Map).

## Implementation Notes

- `DictObj` declared in `include/tvm/ffi/container/dict.h`. `Dict<K,V>` is the typed ref wrapper in the same header.
- C ABI: `kTVMFFIDict = 76` added to `TVMFFITypeIndex` enum in `c_api.h`.
- Python FFI functions: `Dict`, `DictGetItem`, `DictSetItem`, `DictErase`, `DictCount`, `DictSize`, `DictGetItemOrMissing`, `DictForwardIterFunctor` registered in `_ffi_api.py` and `container.cc`.
- `InplaceSwitchTo` has two implementations: `DenseMapBaseObj::InplaceSwitchTo` (dense-to-dense swap) and `SmallMapBaseObj::InplaceSwitchTo` (handles both small-to-small and small-to-dense promotion with `InplaceSmallMapDeleterFromData` for ownership transfer).
- Tests: `tests/cpp/test_dict.cc` (229 lines), `tests/python/test_container.py` (219 lines added), `tests/cpp/extra/test_serialization.cc` (72 lines), `tests/cpp/extra/test_structural_equal_hash.cc` (53 lines).
- Evidence: `.knowledge/commits/2026-02-19-c1af3b337645bed13f573560910dee2743d7d3b1.md` + `c1af3b3`

## Related Design Docs

- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- Container system (Dict section)
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI type index registry
- [`.knowledge/ADRs/0063-mapbaseobj-shared-map-base.md`](0063-mapbaseobj-shared-map-base.md) -- MapBaseObj extraction (prerequisite for Dict)
- [`.knowledge/ADRs/0009-container-data-indirection.md`](0009-container-data-indirection.md) -- data_/data_deleter_ pattern shared by Dict
- [`.knowledge/ADRs/0017-map-msb-layout-tag.md`](0017-map-msb-layout-tag.md) -- MSB tag shared by Dict
