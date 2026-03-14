---
scope:
  - "0001-c-abi"
  - "0003-object-system"
---
# Pack Strong/Weak Ref Counters into Single u64 Atomic

**TL;DR**: The `TVMFFIObject` header replaces separate `strong_ref_count` (u32) and `weak_ref_count` (u32) with a single `uint64_t combined_ref_count`, enabling single-atomic detection of the common "both counters are one" state during deallocation.

## Context

The ref-counting system uses two-phase destruction: strong count reaching zero triggers the destructor, weak count reaching zero frees memory. In the common case (no external weak references), both counters go to zero simultaneously. The previous two-field design required `DecRef` to:
1. Atomically decrement `strong_ref_count` (u32).
2. If strong hits zero, atomically read `weak_ref_count` to decide between `Both` (single-call) and `Strong`-then-`Weak` (two-call) deletion.

This second atomic read, while seemingly cheap, adds a data dependency and potential cache-line ping-pong on the same object header in concurrent scenarios. It also misaligns with established intrusive pointer designs (e.g., PyTorch `intrusive_ptr`) that use packed counters.

The change happened in two stages:
1. Commit `13436f0`: Reordered `TVMFFIObject` header to place ref counters at offset 0 and narrowed `strong_ref_count` from u64 to u32, preparing for the packed layout.
2. Commit `43d13e8`: Replaced the two u32 fields with a single `uint64_t combined_ref_count` where lower 32 bits = strong, upper 32 bits = weak.

Usecases:
- High-throughput FFI call paths that create/destroy many temporary objects (e.g., argument packing, container iteration) benefit from the reduced atomic operation count.
- Concurrent reference counting across threads, where eliminating the second atomic load reduces contention.

Design Decisions:
- Pack strong (lower 32 bits) and weak (upper 32 bits) into `combined_ref_count` at offset 0.
- `DecRef` checks if `count_before_sub == kCombinedRefCountBothOne` to detect the common single-owner case in one atomic decrement, calling `deleter(kTVMFFIObjectDeleterFlagBitMaskBoth)` without any additional atomics.
- Constants: `kCombinedRefCountBothOne = (1ULL << 32) | 1`, `kCombinedRefCountStrongOne = 1`, `kCombinedRefCountWeakOne = 1ULL << 32`, `kCombinedRefCountMaskUInt32 = 0xFFFFFFFF`.
- `Object::use_count()` return type changed from `int32_t` to `uint64_t` (reports strong count only by masking).

## Implementation Notes

- The `TVMFFIObject` header is now 24 bytes: `{combined_ref_count (u64), type_index (i32), __padding (u32), deleter (8B)}`.
- `type_index` moved from offset 0 to offset 8. The former invariant that `TVMFFIObject` and `TVMFFIAny` share `type_index` at offset 0 no longer holds.
- All MSVC intrinsics updated from 64-bit to 32-bit equivalents in the intermediate stage, then back to 64-bit for the combined counter.
- The `__padding` field is explicitly zeroed in the allocator (`d72019c`) for deterministic memory.

### Alternatives Considered

**Alternative A: Keep separate u32 counters with two atomics**
- Pros: Simpler, no bit manipulation. Each counter is independently readable.
- Cons: Requires an extra atomic read during common-case destruction. Does not align with PyTorch `intrusive_ptr` ABI convention.

**Alternative B: Use a single u32 counter (no weak references)**
- Pros: Simplest possible design. 4 bytes for ref count.
- Cons: Eliminates weak reference support entirely. `WeakObjectPtr<T>` would be impossible.

### Consequences

- **ABI-breaking**: All compiled C/C++ code must be recompiled. `TVMFFIObject` field layout changed.
- **Behavioral**: Common-case `DecRef` is now a single atomic operation + branch, eliminating the second atomic load for the no-weak-ref case.
- **Rollback**: Reverting requires splitting `combined_ref_count` back into two u32 fields and updating all atomic operations.

## Related Design Docs

- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- Object header layout and ref-counting protocol
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- `TVMFFIObject` C struct definition
- Commits: `.knowledge/commits/2025-09-25-13436f01111bc4218feb440a29a2e421bc148cc4.md` + `13436f0`, `.knowledge/commits/2025-09-26-43d13e86ee24d1558f929e3b0faa3182ca1af872.md` + `43d13e8`
