---
scope:
  - "0001-c-abi.md"
  - "0002-object-system.md"
---
# ADR: Weak Reference Counting in Object ABI

**TL;DR**: Decision to extend the `TVMFFIObject` header from 16 to 24 bytes with weak reference support. The implementation evolved from split `strong_ref_count: uint32` + `weak_ref_count: uint32` (ca9c3d1) to a single packed `combined_ref_count: uint64` (43d13e8) that enables single-atomic DecRef fast path for the common case.

## Context
- The original `TVMFFIObject` header used a single `int32_t ref_counter` for lifetime management. When the counter reached zero, both the destructor and memory deallocation happened atomically.
- Graph-structured data (e.g., IR nodes with parent/child references) can create reference cycles. Without weak references, breaking cycles requires manual care (raw pointers, separate handle types).
- Caching patterns (e.g., module import caches, compile result caches) benefit from weak references that observe an object without preventing its destruction.
- The `int32_t` counter limited maximum reference count to ~2 billion. Hot objects in multithreaded workloads occasionally saturated this (though rare in practice).

Usecases:
- Breaking reference cycles in IR graph structures without manual raw pointer management.
- Implementing caches (e.g., module function lookup caches) that do not prevent object destruction.
- Enabling parent-pointer patterns where children observe parents without preventing parent destruction.

Design Decisions:
- **Packed combined ref count** in the object header. A single `combined_ref_count: uint64` replaces the old `int32 ref_counter`. Strong count is stored in the lower 32 bits, weak count in the upper 32 bits. Header grows from 16 to 24 bytes. The packing enables a single-atomic DecRef fast path (43d13e8): when `combined_ref_count` equals `kCombinedRefCountBothOne` (both=1), one atomic subtract detects both-counts-reaching-zero without a separate weak-count read.
- **Two-phase deletion protocol**: When `strong_ref_count` reaches 0, the deleter is called with `kStrong` flag (runs destructor, does NOT free memory). When `weak_ref_count` reaches 0, the deleter is called with `kWeak` flag (frees memory block). When both reach 0 simultaneously (the common case with no weak refs), `kBoth` flag triggers both in one call.
- **Implicit weak ref**: `make_object` initializes `weak_ref_count=1`. This implicit weak ref is owned by the strong count and decremented when `strong_ref_count` reaches 0. This means the common case (no WeakObjectPtr exists) has zero overhead: both counts reach 0 together, `kBoth` path runs.
- **CAS-based promotion**: `WeakObjectPtr::lock()` uses a compare-and-swap loop to atomically increment `strong_ref_count` only if it is currently > 0. This is thread-safe and lock-free.
- **Deleter signature change**: `void(*deleter)(TVMFFIObject*)` becomes `void(*deleter)(TVMFFIObject*, int flags)`. This is an ABI break.
- **API rename**: `TVMFFIObjectFree` renamed to `TVMFFIObjectDecRef`; new `TVMFFIObjectIncRef` added for symmetry.

## Implementation Notes
- Both counts are 32 bits (strong=lower, weak=upper) packed in one `uint64` field. ~4 billion max refs per count is sufficient in practice.
- The combined packing was initially enabled by narrowing `strong_ref_count` from `uint64` to `uint32` (13436f0). The follow-up commit (43d13e8) replaced the separate fields with `combined_ref_count: uint64`, realizing the single-atomic CAS optimization. `DecRef` now uses one fewer atomic operation in the common case: previously `atomic_sub(strong) + atomic_load(weak) + conditional atomic_sub(weak)`, now `atomic_sub(combined) + branch on pre-sub value`.
- The `TVMFFIObjectDeleterFlagBitMask` enum is an `int32_t` with upper bits reserved for future extension.
- `details::SimpleObjAllocator::Handler<T>::Deleter_` implements the three-way dispatch (strong-only, weak-only, both). (Allocators moved to `details` namespace in `24125d0`.)

### Alternative 1: External weak reference table (like Python's `weakref`)
- Pros: No header size increase. No ABI break for deleter signature.
- Cons: Requires global hash table lookup for every weak ref creation/promotion. Significant per-operation overhead. Cannot be lock-free.

### Alternative 2: Separate control block (like `std::shared_ptr`)
- Pros: No change to object header size. More flexible control block layout.
- Cons: Extra heap allocation per object (control block + object). Extra indirection for ref-count access. Cannot reuse the intrusive counting pattern that is fundamental to the TVM FFI ABI.

## Related Design Docs
- [0001-c-abi.md](../designs/0001-c-abi.md) -- TVMFFIObject header layout, TVMFFIObjectDeleterFlagBitMask enum
- [0002-object-system.md](../designs/0002-object-system.md) -- WeakObjectPtr<T>, two-phase deletion protocol
