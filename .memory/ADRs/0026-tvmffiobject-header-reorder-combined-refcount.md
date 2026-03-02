---
adr: "0026"
title: "Reorder TVMFFIObject Header and Re-adopt Combined u64 Reference Count"
status: "accepted"
date: "2025-09-26"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "abi"
  - "memory-management"
  - "performance"
source_commits:
  - "13436f01111bc4218feb440a29a2e421bc148cc4"
  - "43d13e86ee24d1558f929e3b0faa3182ca1af872"
  - "ffa2dbf8bc18edb3114f18f619da08c4e3289de6"
source_ledgers:
  - ".memory/commits/2025-09-25-13436f01.md"
  - ".memory/commits/2025-09-26-43d13e86.md"
  - ".memory/commits/2025-10-01-ffa2dbf8.md"
---

# ADR-0026: Reorder TVMFFIObject Header and Re-adopt Combined u64 Reference Count

## TL;DR
- The `TVMFFIObject` header was reordered to place `combined_ref_count` first (bytes 0-7), followed by `type_index` (bytes 8-11) and `__padding` (bytes 12-15), aligning with PyTorch's `intrusive_ptr` ABI layout.
- The previously split `strong_ref_count` (uint64_t) + `weak_ref_count` (uint32_t) fields are re-combined into a single `uint64_t combined_ref_count` (strong in lower 32 bits, weak in upper 32 bits), enabling a single-atomic fast-path deletion when both counters reach zero simultaneously.

## Status
Accepted

## Context
After the weak reference counting design (commit `ca9c3d1`) split the original `combined_ref_count` into separate `strong_ref_count` (uint64_t) and `weak_ref_count` (uint32_t) fields, the DecRef path required two separate atomic operations: one to decrement the strong count and a second to read the weak count to decide whether to call the deleter with `Both` or just `Strong`. This two-read pattern was correct but left performance on the table.

Meanwhile, PyTorch's `c10::intrusive_ptr` places the refcount fields at offset 0 of its control block. Aligning TVM FFI's object header with this layout creates opportunities for future interop (e.g., shared reference counting between TVM and torch objects in the same address space).

The original combined refcount design (ADR-0002) was superseded in `ca9c3d1` because weak references needed 32 bits and the original layout placed `type_index` first. With the header reorder moving refcounts to the front, the combined approach becomes viable again with the full weak reference semantics.

## Decision Drivers
- Performance: the DecRef fast path (both strong and weak at 1) should require only one atomic fetch-sub, not a fetch-sub followed by a separate atomic load.
- ABI alignment with PyTorch `intrusive_ptr`: placing refcounts at offset 0 enables potential future interop.
- Cache friendliness: refcount operations are the most frequent operations on objects, so placing them first maximizes L1 cache efficiency.
- Correctness: the combined u64 approach must preserve all weak reference semantics established in the split design.

## Decision
**Step 1** (commit `13436f0`): Reorder `TVMFFIObject` so that `strong_ref_count` (uint32_t) and `weak_ref_count` (uint32_t) occupy bytes 0-7, followed by `type_index` (int32_t) at bytes 8-11 and `__padding` at bytes 12-15. This breaks the previous invariant that `TVMFFIObject.type_index` shares offset 0 with `TVMFFIAny.type_index` (the test asserting this was correctly removed).

**Step 2** (commit `43d13e8`): Merge the two uint32_t fields into a single `uint64_t combined_ref_count`. Strong count occupies bits [0,31], weak count occupies bits [32,63]. Constants: `kCombinedRefCountStrongOne = 1`, `kCombinedRefCountWeakOne = 1 << 32`, `kCombinedRefCountBothOne = kCombinedRefCountWeakOne | kCombinedRefCountStrongOne`, `kCombinedRefCountMaskUInt32 = (1 << 32) - 1`.

**Step 3** (commit `ffa2dbf`): Zero-initialize `__padding` in the allocator to ensure deterministic memory.

## Alternatives Considered
### Keep separate strong/weak fields at new positions
- Pros: Simpler code (no bit manipulation). Each counter gets full 32 or 64 bits.
- Cons: DecRef fast path requires two atomic operations. Does not exploit the "read both at once" property.

### Keep original header order (type_index first)
- Pros: Maintains the `TVMFFIObject.type_index` == `TVMFFIAny.type_index` offset invariant, allowing shared type dispatch code.
- Cons: Not aligned with PyTorch. Refcount not at offset 0 wastes cache potential on the hottest path. The shared-offset invariant was not actually exploited in practice (confirmed by removing the test without fallout).

### Use 64-bit strong + 64-bit weak (expand header to 32 bytes)
- Pros: No risk of 32-bit overflow in either counter. Simpler than combined.
- Cons: Increases every object allocation by 8 bytes. The 24-byte header is a hard ABI constraint.

## Why This Option Won
- The combined u64 approach provides a single-instruction fast path for the most common deletion scenario (no weak refs): `fetch_sub(combined_ref_count, 1)` returns `kCombinedRefCountBothOne`, immediately confirming both counters reached zero without any additional atomic reads.
- Placing refcounts at offset 0 maximizes cache locality for the hottest operation (IncRef/DecRef) and aligns with PyTorch's layout for potential future interop.
- The technique was recently validated by PyTorch's adoption of the same pattern.
- The 32-bit limit for each counter (4 billion) is impractical to reach for either strong or weak references.

## Consequences
### Positive
- DecRef fast path (no weak refs) is now a single atomic operation instead of two.
- Header layout is aligned with PyTorch `intrusive_ptr`, opening interop opportunities.
- Cache-friendly: offset 0 refcounts benefit from L1 prefetch patterns for sequential object access.

### Negative
- The `type_index` is no longer at offset 0, breaking the historical invariant shared with `TVMFFIAny`. All compiled C++/Cython code must be recompiled (ABI break).
- Both strong and weak counts are limited to uint32 (~4 billion). Overflow of either silently corrupts the other.
- The bit manipulation adds slight complexity to the refcount paths (shift/mask for use_count, constants for IncWeakRef).

### Risks
- Endianness: the "strong = lower 32 bits" assumption works on little-endian (x86, ARM64) but would need adjustment on big-endian platforms. The project does not officially support big-endian. Mitigation: no big-endian targets in CI.
- Silent corruption on overflow: if either counter exceeds 2^32, the other is silently corrupted. Mitigation: practical impossibility of 4 billion concurrent references.

## Implementation Notes
- `Object::IncRef()`: `atomic_fetch_add(&combined_ref_count, 1, RELAXED)`
- `Object::DecRef()`: `atomic_fetch_sub(&combined_ref_count, 1, RELEASE)` -> check `(prev & mask) == 1` for last strong ref -> if `prev == kCombinedRefCountBothOne`, call `deleter(self, Both)` (fast path).
- `Object::IncWeakRef()`: `atomic_fetch_add(&combined_ref_count, kCombinedRefCountWeakOne, RELAXED)`
- `Object::DecWeakRef()`: `atomic_fetch_sub(&combined_ref_count, kCombinedRefCountWeakOne, RELEASE)` -> check upper 32 bits.
- `Object::TryPromoteWeakPtr()`: CAS loop on `combined_ref_count`, adding `kCombinedRefCountStrongOne` only if lower 32 bits are non-zero.
- `Object::use_count()`: `atomic_load(&combined_ref_count, RELAXED) & kCombinedRefCountMaskUInt32`
- `__padding` is explicitly set to 0 in `ObjAllocatorBase::make` and `make_inplace_array` (commit `ffa2dbf`).

## Validation
- `tests/cpp/test_ffi_object.cc`: Existing reference counting tests validate correctness of the combined approach.
- `test_c_ffi_abi.cc` (which asserted the old type_index-first layout) was removed in commit `13436f0`.
- Version bumped to 0.1.0b8 after the combined refcount change.

## Migration and Rollback
- ABI-breaking change: all compiled C++/Cython/Rust code must be recompiled after either commit.
- Rollback: revert to split fields. Straightforward but requires another ABI bump.
- Foreign bindings that read `TVMFFIObject` fields directly must update their struct definitions.

## Related Design Docs
- [.memory/designs/0002-object-system-and-reference-counting.md](.memory/designs/0002-object-system-and-reference-counting.md)
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)
- [.memory/designs/0012-weak-reference-counting.md](.memory/designs/0012-weak-reference-counting.md)

## Related Diagrams
- [.memory/diagrams/0002-object-type-hierarchy.md](.memory/diagrams/0002-object-type-hierarchy.md)
- [.memory/diagrams/0013-tvmffiobject-header-layout.md](.memory/diagrams/0013-tvmffiobject-header-layout.md)

## Evidence Matrix
- Header reorder (refcounts first) -> `.memory/commits/2025-09-25-13436f01.md` + `13436f0` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/object.h`
- Combined u64 refcount constants and atomic operations -> `.memory/commits/2025-09-26-43d13e86.md` + `43d13e8` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/object.h`
- Zero-init __padding -> `.memory/commits/2025-10-01-ffa2dbf8.md` + `ffa2dbf` + `include/tvm/ffi/memory.h`
- Removal of test_c_ffi_abi.cc -> `13436f0` + `tests/cpp/test_c_ffi_abi.cc`
- Version bump to 0.1.0b8 -> `43d13e8` + `pyproject.toml`

## Supersedes
[.memory/ADRs/0002-combined-refcount-in-single-u64.md](.memory/ADRs/0002-combined-refcount-in-single-u64.md) (re-adopts the same approach with a different header layout, now with full weak reference semantics)

## Superseded By
None

## Follow-up Actions
- Update Rust binding struct definitions for the new header layout.
- Consider adding a compile-time static_assert that `offsetof(TVMFFIObject, combined_ref_count) == 0` to catch future accidental reorderings.
