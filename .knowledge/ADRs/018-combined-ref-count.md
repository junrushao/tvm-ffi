---
scope:
  - ".knowledge/designs/c-abi.md"
  - ".knowledge/designs/object-system.md"
  - ".knowledge/designs/memory.md"
---
# Combined Reference Count: Packing Strong + Weak into uint64_t

**TL;DR**: The `TVMFFIObject` header packs strong and weak reference counters into a single `uint64_t combined_ref_count` field, enabling a single-atomic fast path for the common case where both counters reach zero simultaneously.

## Context
After introducing weak reference counting (ca9c3d1), the `TVMFFIObject` header had separate `uint32_t strong_ref_count` and `uint32_t weak_ref_count` fields. The common `DecRef` path required:
1. Atomic decrement of `strong_ref_count`
2. Separate atomic read of `weak_ref_count` to check if memory can be freed
3. If weak > 1: separate atomic decrement of `weak_ref_count`

This results in 2-3 atomic operations per object destruction even though >99% of objects have no external weak references (both counters are 1).

Usecases:
- High-frequency object creation/destruction in expression tree building
- Tight loops that allocate temporary FFI objects (e.g., argument packing)

Design Decisions:
- Pack strong (lower 32 bits) and weak (upper 32 bits) into `uint64_t combined_ref_count`. Use `kCombinedRefCountBothOne` sentinel for the common-case single-atomic fast path.

## Alternatives
### A: Keep separate uint32_t counters
- Description: The status quo before 43d13e86. Two separate 32-bit counters at offsets 0 and 4.
- Pros: Simpler code; no bitmask arithmetic; 32-bit atomics may be cheaper on some architectures.
- Cons: Common destruction path requires 2+ atomic ops: one decrement + one conditional read/decrement. The extra atomic read on every strong DecRef is wasted when weak_ref_count == 1 (the overwhelming majority case).
- Why rejected: The single-atomic fast path provides measurable improvement for ML workloads with high object churn.

### B: Use a single atomic with different bit widths (e.g., 48+16)
- Description: Allocate more bits to strong count (which is more frequently used) and fewer to weak.
- Pros: Allows larger strong ref count before overflow.
- Cons: Asymmetric bit widths add complexity to increment/decrement operations; weak ref count of 16 bits is too small for some use cases; no practical benefit since 32-bit strong ref count is already sufficient.
- Why rejected: Uniform 32+32 split is simpler and both counters have identical overflow characteristics.

## Implementation Notes
- `kCombinedRefCountStrongOne = 1` (increment strong by adding 1)
- `kCombinedRefCountWeakOne = 1ULL << 32` (increment weak by adding 2^32)
- `kCombinedRefCountBothOne = kCombinedRefCountWeakOne | kCombinedRefCountStrongOne`
- `kCombinedRefCountMaskUInt32 = (1ULL << 32) - 1` (extract strong count)
- `Object::use_count()` returns `uint64_t` (was `int32_t`), masking to get strong count only
- Allocation: `combined_ref_count = kCombinedRefCountBothOne`, `__padding = 0`

## Related Design Docs
- `.knowledge/designs/c-abi.md` -- TVMFFIObject 24-byte layout
- `.knowledge/designs/object-system.md` -- Object ref-counting internals
- `.knowledge/designs/memory.md` -- Allocator initialization
- `.knowledge/designs/0016-weak-reference-counting.md` -- Weak RC design
- `.knowledge/ADRs/014-weak-ref-24byte-header.md` -- Previous decision on 24-byte header with split counters
