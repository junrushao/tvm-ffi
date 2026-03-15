---
scope:
  - "0008-containers"
---
# Explicit data_ + data_deleter_ in Container Objects

**TL;DR**: The decision to add explicit `void* data_` pointer and `void (*data_deleter_)(void*)` to `ArrayObj` and `MapObj` (now `MapBaseObj`), decoupling element access from `InplaceArrayBase::AddressOf` and enabling future external data buffers. **Note**: `InplaceArrayBase` was subsequently removed entirely in 5a6b211; `ArrayObj` now computes its inplace data pointer directly via `reinterpret_cast<char*>(p.get()) + sizeof(ArrayObj)`. The `data_` and `data_deleter_` fields on the map side are now defined on `MapBaseObj` (the shared base for `MapObj` and `DictObj`).

## Context
- Previously, `ArrayObj` used `begin_`/`end_`/`end_cap_` pointers derived from `InplaceArrayBase::AddressOf()` at every access, tightly coupling element access to the inplace allocation strategy.
- This made it impossible to attach externally-allocated or separately-managed data buffers to container objects.
- Cross-shared-library safety required a way to ensure the allocator and deallocator match; raw `delete[]` could mismatch when allocation and deallocation happened in different shared libraries.
- `DenseMapObj` similarly needed explicit data management for its `Block[]` storage.

Usecases:
- Future support for externally managed memory (mmap'd buffers, device memory) attached to containers.
- Cross-shared-library safety: `data_deleter_` ensures deallocation uses the same allocator as allocation, even across DLL boundaries.
- ABI stability: explicit `data_` pointer decouples the container layout from the inplace array template, making the layout more predictable for language bindings.

Design Decisions:
- **Add `void* data_` and `void (*data_deleter_)(void*)`** to both `ArrayObj` and `MapObj`. For inplace storage, `data_` points to the trailing allocation and `data_deleter_ = nullptr` (object's own deleter handles cleanup). For external storage, `data_deleter_` handles the external buffer.
- **Change `DenseMapObj` slot semantics**: `slots_` now stores the actual count (was `count-1` bitmask). Index wrapping changes from `& slots_` to `% slots_`, removing the power-of-two constraint. **Note**: For `SmallMapObj`, the raw `slots_` value now includes the MSB tag bit (bit 63 set = small layout). Use `NumSlots()` to read the logical count. See [ADR 0012](0012-msb-tag-map-layout.md).
- **`ArrayObj::at()` returns `const Any&`** instead of `const Any` by value, avoiding unnecessary copies.

## Implementation Notes
- `ArrayObj::Empty()` calls `make_inplace_array_object` then sets `data_` to the inplace data address (`reinterpret_cast<char*>(p.get()) + sizeof(ArrayObj)` as of 5a6b211; previously used `InplaceArrayBase::AddressOf(0)` which has been removed).
- `DenseMapObj` uses `data_deleter_ = BlockDeleter` for its `Block[]` allocation, ensuring correct deallocation across shared library boundaries.
- `SmallMapObj` uses `KVRawStorageType` (`TVMFFIAny` pairs) instead of `KVType` (`Any` pairs) for the inplace array template, aligning raw storage with the C ABI struct layout.
- `Array<T>` gains `emplace_back(Args&&...)` for variadic in-place construction.

## Related Design Docs
- [0008-containers.md](.knowledge/designs/0008-containers.md)
- [0007-memory-allocation.md](.knowledge/designs/0007-memory-allocation.md) — make_inplace_array_object for container allocation
