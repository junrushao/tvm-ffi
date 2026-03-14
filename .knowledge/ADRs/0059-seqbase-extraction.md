---
scope:
  - "0005-containers"
  - "0001-c-abi"
---
# Extract SeqBaseObj as Shared Base for Array and List

**TL;DR**: `SeqBaseObj` is extracted from `ArrayObj` as a shared base class for all sequence containers (`ArrayObj`, `ListObj`), consolidating element access, iteration, bounds checking, and destruction into a single implementation backed by the new `TVMFFISeqCell` C ABI struct.

## Context

Before commit `9513c2f` (#443), `ArrayObj` was the only sequence container. All sequence logic (element access, bounds checking, iteration, destruction, `clear()`) was implemented directly in `ArrayObj`. Adding `List<T>` as a mutable sequence required duplicating this logic, creating a maintenance burden and a risk of behavioral divergence between the two containers.

The core insight is that both `Array` and `List` share the same fundamental storage model: a contiguous buffer of `Any` elements accessed via a `void* data` pointer with `size` and `capacity` metadata. The difference lies in ownership and mutation semantics: `Array` is immutable (COW) with optional inplace trailing storage, while `List` is mutable with heap-only storage.

Usecases:
- `List<T>` mutable sequence container needed shared element-access logic with `Array<T>` without code duplication.
- Serialization, structural hash/equal, and JSON writer need a unified interface for "iterate elements of a sequence" regardless of whether it is an Array or List.
- Future sequence containers (e.g., `Deque<T>`) can extend `SeqBaseObj` to reuse the same operations.

Design Decisions:
- **Extract `SeqBaseObj`** (`include/tvm/ffi/container/seq_base.h`) as an intermediate base class between `Object` and `ArrayObj`/`ListObj`.
- **No type index for `SeqBaseObj`**: It is transparent to the FFI type system, following the same pattern as `details::BytesObjBase`. `ArrayObj` and `ListObj` each have their own type indices (`kTVMFFIArray = 66`, `kTVMFFIList = 75`).
- **New C ABI struct `TVMFFISeqCell`**: Standardizes the sequence storage layout (`data`, `size`, `capacity`, `data_deleter`) at the ABI level. `SeqBaseObj` inherits from `TVMFFISeqCell` via protected inheritance.
- **`ArrayObj` refactored to extend `SeqBaseObj`**: The `data_`, `size_`, `capacity_`, `data_deleter_` fields move from `ArrayObj` into `TVMFFISeqCell`/`SeqBaseObj`. Array-specific logic (inplace storage, COW) remains in `ArrayObj`.
- **`ListObj` extends `SeqBaseObj`**: Heap-only storage with `RawDataDeleter`. Mutable mutation methods on `ListObj` use `SeqBaseObj::MutableBegin()` for direct element access.

**Alternatives considered**:

1. **Duplicate sequence logic in ListObj**: Simpler (no refactoring of ArrayObj), but doubles the code for bounds checking, iteration, and destruction. Behavioral divergence risk is high.
2. **Template-based CRTP mixin instead of inheritance**: Avoids virtual inheritance issues but adds template complexity. Since `SeqBaseObj` has no virtual methods and no type index, direct inheritance is simpler and has zero runtime overhead.
3. **Shared free functions instead of a base class**: Functions like `SeqAccess(data, size, i)` avoid inheritance but scatter the implementation and cannot share the destructor logic cleanly.

**Consequences**:
- ABI-compatible change: `TVMFFISeqCell` is a new addition, and `ArrayObj`'s field layout at the C ABI level is preserved (same offsets for `data`, `size`, `capacity`, `data_deleter`).
- Code reduction: ~300 lines removed from `array.h`, consolidated into `seq_base.h`.
- `TypeTraits<std::vector<T>>::TryCastFromAnyView` now accepts both `kTVMFFIArray` and `kTVMFFIList`.
- Serialization, structural hash/equal, and JSON writer gain List support with cycle detection (List is mutable, so cycles are possible; Array is immutable and cannot form cycles).

**Migration**: No migration needed. `ArrayObj` field access is source-compatible. `SeqBaseObj` is an internal implementation detail not exposed to users.

## Implementation Notes

- `SeqBaseObj` is defined in `include/tvm/ffi/container/seq_base.h`.
- `ListObj` is defined in `include/tvm/ffi/container/list.h` with type index `kTVMFFIList = 75`.
- `TVMFFISeqCell` is defined in `include/tvm/ffi/c_api.h` between `[TVMFFISeqCell.begin]` and `[TVMFFISeqCell.end]` markers.
- The Python `List` class is in `python/tvm_ffi/container.py`, registered as `@register_object("ffi.List")`, implementing `collections.abc.MutableSequence`.
- Evidence: `.knowledge/commits/2026-02-13-9513c2f8a57f64ad7473d7cd06084719f6d5e70e.md` + `9513c2f`

## Related Design Docs

- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- Container system design
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI struct definitions
- [`.knowledge/ADRs/0009-container-data-indirection.md`](0009-container-data-indirection.md) -- data_/data_deleter_ indirection pattern (now in TVMFFISeqCell)
