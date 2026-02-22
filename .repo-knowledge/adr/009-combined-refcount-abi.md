# ADR 009: Combined Reference Count in TVMFFIObject

- Status: Accepted
- Date: 2025-09-26
- Owners: Tianqi Chen

## Context

The `TVMFFIObject` struct had separate `uint32_t strong_ref_count` and
`uint32_t weak_ref_count` fields. In the `DecRef` hot path (the most common
refcount operation), detecting the common case of both counters going to zero
required two atomic operations: one to decrement the strong count, and a
separate read of the weak count to decide whether to deallocate.

PyTorch's `intrusive_ptr` had recently adopted a combined counter optimization
that merges both counts into a single `uint64_t` atomic, enabling single-atomic
detection of the common case.

## Decision

The change was implemented in two steps:

**Step 1: Header reorder** (`13436f0`): `TVMFFIObject` fields were reordered
to place `strong_ref_count` and `weak_ref_count` (both `uint32_t`) before
`type_index` and `__padding`. This aligned with PyTorch's `intrusive_ptr`
layout where reference counters come first for better cache performance. The
previously shared `type_index` position between `TVMFFIObject` and
`TVMFFIAny` was intentionally broken. Windows atomic operations were updated
from 64-bit to 32-bit intrinsics to match the 32-bit counters.

**Step 2: Combined counter** (`43d13e8`): The two separate `uint32_t` fields
were merged into a single `uint64_t combined_ref_count`. Strong occupies the
lower 32 bits, weak occupies the upper 32 bits. Constants
`kCombinedRefCountStrongOne`, `kCombinedRefCountWeakOne`, and
`kCombinedRefCountBothOne` were introduced. `DecRef` gains a fast path:
if the value before subtraction equals `kCombinedRefCountBothOne`, both
counts are going to zero and the object can be deallocated with a single
atomic fetch-subtract.

Both changes are ABI-breaking and require recompilation of all compiled
binaries.

## Consequences

- Positive: Eliminates a separate weak-counter read in the `DecRef` hot path,
  reducing the common case from two atomic operations to one.
- Positive: Layout aligns with PyTorch's `intrusive_ptr`, potentially enabling
  future interop optimizations.
- Negative: ABI-breaking change to the `TVMFFIObject` struct layout; all
  consuming code must be rebuilt.
- Negative: The shared `type_index` position between `TVMFFIObject` and
  `TVMFFIAny` (tested in `test_c_ffi_abi.cc`) was broken. The test file was
  deleted.
- Migration/Rollout: All pre-compiled extensions or libraries using
  `TVMFFIObject` directly must be rebuilt against the new headers. Version
  was bumped to `0.1.0b8`.

## References
- Range summary: `.repo-knowledge/ranges/2025-09-30-CA9C3D1-F9179EC.md`
- Evidence commits: `13436f01111bc4218feb440a29a2e421bc148cc4`, `43d13e86ee24d1558f929e3b0faa3182ca1af872`
- External references: PyTorch `intrusive_ptr` combined refcount optimization

## Related Design Docs
- `.repo-knowledge/design/003-c-abi-stability.md`

## Notes
`Object::use_count()` return type changed from `int32_t` to `uint64_t`
(returning only the lower 32 bits via mask). The Cython struct declaration
in `base.pxi` was updated to match the new `uint64_t combined_ref_count`
field.
