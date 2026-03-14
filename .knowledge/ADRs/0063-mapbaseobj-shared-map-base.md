---
scope:
  - "0005-containers"
---
# Extract MapBaseObj as Shared Base for Map and Dict

**TL;DR**: `MapBaseObj` was extracted from `MapObj` as a shared, type-index-free base class for both immutable `MapObj` and mutable `DictObj`, enabling full code reuse of hash table internals (small/dense layout, MSB tag, probing, rehashing) while allowing the two container types to differ only in type index and mutation semantics.

## Context

Before this change, `MapObj` contained all hash table logic directly: the `SmallMapObj`/`DenseMapObj` subclasses, `InsertMaybeReHash`, layout discrimination via MSB tag, and the `data_`/`slots_`/`data_deleter_` fields. This design worked for a single immutable Map container, but introducing a mutable Dict container (like `List` is to `Array`) required either duplicating all hash table internals or refactoring them into a shared base.

The precedent was `SeqBaseObj` (extracted for `ArrayObj`/`ListObj` code sharing in `9513c2f` #443), which demonstrated that a type-index-free base class can share operations between immutable and mutable sequence containers. The same pattern applies to map-like containers.

Usecases:
- `Dict<K,V>` needs the same hash table layout (small map / dense map), probing, rehashing, and iteration as `Map<K,V>` but with in-place mutation semantics.
- Future container types sharing map internals (e.g., a frozen dict, an ordered map) can extend `MapBaseObj` without duplicating hash table code.

Design Decisions:
- **`MapBaseObj` is type-index-free**: Like `SeqBaseObj` and `BytesObjBase`, `MapBaseObj` does not register a type index. `MapObj` and `DictObj` each register their own index (`kTVMFFIMap`, `kTVMFFIDict`). This avoids polluting the type hierarchy with an intermediate type that users never interact with directly.
- **`map_base.h` absorbs `container_details.h`**: The former `container_details.h` was removed; its contents (hash helpers, `InplaceArrayBase`, `KVRawStorageType`) were moved into `map_base.h`. This reduces header fragmentation.
- **`InsertMaybeReHash` returns `ObjectPtr<Object>`**: Changed from mutating a `ObjectPtr<Object>*` to returning the new container (or `nullptr` if no rehash). This enables Dict's `Set()` to detect rehashing and call `InplaceSwitchTo` to swap storage without changing the `ObjectPtr` identity. Map's `Set()` continues to replace the pointer outright (COW semantics).
- **`ArrayObj` no longer inherits `InplaceArrayBase`**: As part of the cleanup, `ArrayObj` was simplified to inherit only `SeqBaseObj`. Trailing storage is addressed via `reinterpret_cast<char*>(p.get()) + sizeof(ArrayObj)` instead of `AddressOf(0)`. This eliminates the need for `InplaceArrayBase`'s `using` declarations and `static_assert` guards in `ArrayObj`.
- **Concrete subclasses renamed**: `SmallMapObj` -> `SmallMapBaseObj`, `DenseMapObj` -> `DenseMapBaseObj` to reflect that they are internal implementation classes shared between Map and Dict.

**Alternatives considered**:

1. **Duplicate hash table code in DictObj**: Avoids the base class extraction but doubles the maintenance surface for probing, rehashing, MSB tag logic, and iteration. Any bug fix must be applied twice.
2. **Template-based code sharing (CRTP)**: Would avoid a runtime base class but complicates the object hierarchy and interacts poorly with the `Object` type system (which uses single-inheritance chains with `_type_index`).
3. **Single MapObj with a mutability flag**: Would avoid a new type but conflates immutable and mutable semantics, breaking the invariant that `Map` callers can assume no aliased mutations.

**Consequences**:
- **Zero runtime overhead**: `MapBaseObj` adds no new fields or virtual methods. `sizeof(MapObj) == sizeof(DictObj) == sizeof(MapBaseObj)` (verified by static_assert in `dict.h`).
- **Header reorganization**: Code that included `container_details.h` directly must switch to `map_base.h`. `map.h` now includes `map_base.h`.
- **Internal name changes**: `SmallMapObj` -> `SmallMapBaseObj`, `DenseMapObj` -> `DenseMapBaseObj`. External users of `Map<K,V>` and the `MapObj` type key are unaffected.
- **`InplaceSwitchTo` added to `MapBaseObj`**: A new method enabling Dict mutation without pointer identity change. Map does not call this method.

**Rollback**: Inline `MapBaseObj` back into `MapObj`, rename subclasses back, restore `container_details.h`, and revert `InsertMaybeReHash` to pointer-mutation style. Dict would need to be removed or reimplemented.

## Implementation Notes

- `MapBaseObj` is defined in `include/tvm/ffi/container/map_base.h` (created in `5a6b211`, extended in `c1af3b3`).
- `MapObj` in `map.h` is now a thin subclass: `class MapObj : public MapBaseObj { static constexpr int32_t _type_index = kTVMFFIMap; ... }`.
- `DictObj` in `dict.h` is equally thin: `class DictObj : public MapBaseObj { static constexpr int32_t _type_index = kTVMFFIDict; ... }`.
- `SmallMapBaseObj::~SmallMapBaseObj()` was updated to handle the case where `InplaceSwitchTo` has promoted the object to dense layout: it checks `IsSmallMap()` and dispatches to the correct `Reset()`.
- Evidence: `.knowledge/commits/2026-02-18-5a6b211612c4f0360f49a7a17a809d80460f557d.md` + `5a6b211`, `.knowledge/commits/2026-02-19-c1af3b337645bed13f573560910dee2743d7d3b1.md` + `c1af3b3`

## Related Design Docs

- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- Container system with Map/Dict hierarchy
- [`.knowledge/ADRs/0009-container-data-indirection.md`](0009-container-data-indirection.md) -- data_/data_deleter_ pattern (now in MapBaseObj)
- [`.knowledge/ADRs/0017-map-msb-layout-tag.md`](0017-map-msb-layout-tag.md) -- MSB tag (now in MapBaseObj)
- [`.knowledge/ADRs/0059-seqbase-extraction.md`](0059-seqbase-extraction.md) -- Precedent: SeqBaseObj extraction for Array/List
- [`.knowledge/ADRs/0064-mutable-dict-container.md`](0064-mutable-dict-container.md) -- Dict container (motivating use case for this extraction)
