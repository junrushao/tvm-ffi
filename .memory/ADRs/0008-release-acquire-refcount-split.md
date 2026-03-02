---
adr: "0008"
title: "Split Release/Acquire Barriers in Object Reference Count Decrement"
status: "accepted"
date: "2025-06-18"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "performance"
  - "memory-management"
source_commits:
  - "d5209f0ce34d1f7c20c6cdc10cbc8445facb85e5"
source_ledgers:
  - ".memory/commits/2025-06-18-d5209f0ce34d1f7c20c6cdc10cbc8445facb85e5.md"
---

# ADR-0008: Split Release/Acquire Barriers in Object Reference Count Decrement

## TL;DR
- The atomic decrement in `Object::DecRef` is changed from `ACQ_REL` on every decrement to `RELEASE`-only, with an `ACQUIRE` fence added only when the refcount drops to zero and the deleter must run. This reduces memory-ordering overhead on weakly-ordered architectures (ARM, RISC-V) while maintaining correctness.
- All atomic operations (`IncRef`, `DecRef`, `use_count`) are inlined directly into `Object` methods, removing the helper functions from `base_details.h`.

## Status
Accepted

## Context
Reference counting is the hottest operation in TVM FFI -- every function call argument may involve `IncRef`/`DecRef`. The previous implementation used `ACQ_REL` (acquire-release) ordering on every `fetch_sub` in `DecRef`, which on ARM/RISC-V translates to a full memory barrier (`dmb`) on every decrement, even when the object is not being freed.

The standard pattern for reference-counted smart pointers (used by `std::shared_ptr` in libstdc++ and libc++, and documented by Boost.Atomic) splits the ordering:
1. **Release** on the `fetch_sub`: ensures all prior writes by this thread are visible to other threads before the refcount change.
2. **Acquire** fence only when refcount reaches zero: ensures all writes from other threads (that also decremented the refcount) are visible before the deleter runs.

The acquire fence is needed only once per object lifetime (at destruction), not on every decrement. The common case (refcount > 1 after decrement) pays only the release cost.

## Decision Drivers
- Performance: reduce barrier cost on the hot `DecRef` path, especially on ARM/RISC-V.
- Correctness: the deleter must see all writes from all threads that held references.
- Alignment with industry practice: match the `std::shared_ptr` implementation pattern.
- Simplicity: inline the atomics directly in `Object` methods rather than delegating to helpers.

## Decision
Replace the single `ACQ_REL` `fetch_sub` with:

```cpp
// Non-MSVC path:
uint64_t prev = __atomic_fetch_sub(&combined_ref_count, 1, __ATOMIC_RELEASE);
if (prev == 1) {  // was 1, now 0 -> last reference
  __atomic_thread_fence(__ATOMIC_ACQUIRE);
  // call deleter
}
```

For MSVC, use `_InterlockedDecrement64` which implies a full barrier, and check `== 0` (new value) matching `_InterlockedDecrement` semantics.

Inline all atomic operations into `Object::IncRef`, `Object::DecRef`, and `Object::use_count`, removing `details::AtomicIncrementRelaxed`, `details::AtomicDecrementRelAcq`, and `details::AtomicLoadRelaxed` from `base_details.h`.

## Alternatives Considered
### Keep ACQ_REL on every decrement
- Pros: Simpler code. No conditional fence. Proven correct.
- Cons: Unnecessary acquire barrier on every non-final decrement. Measurable overhead on ARM.

### Use relaxed ordering everywhere with a separate synchronization mechanism
- Pros: Minimal barrier cost.
- Cons: Incorrect. Without release ordering on decrements, the deleter could run before all writes from other threads are visible.

### Use seq_cst (sequential consistency) for maximum safety
- Pros: Strongest ordering guarantee. Easiest to reason about.
- Cons: Significantly more expensive than release/acquire on all platforms. Over-orders operations that do not need sequential consistency.

## Why This Option Won
- It is the standard pattern used by `std::shared_ptr` in both libstdc++ and libc++, and recommended by Boost.Atomic documentation.
- On x86, the practical difference is negligible (store-load already has acquire semantics from the hardware), so this is a zero-cost improvement on x86 and a real improvement on ARM/RISC-V.
- The acquire fence is paid only once per object lifetime (at the final decrement), making the common case (refcount > 1) faster.
- Inlining the atomics improves readability and eliminates a layer of indirection.

## Consequences
### Positive
- Reduced memory barrier cost on the hot decref path on ARM/RISC-V.
- `IncRef`/`DecRef`/`use_count` are now self-contained in `object.h` -- no separate helper file needed.
- MSVC path is simplified (direct `_InterlockedDecrement64` without the `+1` fixup from the removed helper).

### Negative
- Slightly more complex `DecRef` code (conditional fence after the fetch_sub).
- The MSVC path remains a full barrier (cannot be split with MSVC intrinsics), so the optimization only benefits GCC/Clang.

### Risks
- If the `fetch_sub` and fence are not correctly paired, the deleter could see stale data. Mitigated by the pattern being well-established (Boost.Atomic, libstdc++, libc++).
- On x86, the change is a no-op in practice, so any regression would only appear on ARM test infrastructure.

## Implementation Notes
- `Object::IncRef()`: `__atomic_fetch_add(&combined_ref_count, 1, __ATOMIC_RELAXED)` (relaxed is sufficient for increment).
- `Object::DecRef()`: `__atomic_fetch_sub(&combined_ref_count, 1, __ATOMIC_RELEASE)` + conditional `__atomic_thread_fence(__ATOMIC_ACQUIRE)` when prev == 1.
- `Object::use_count()`: `__atomic_load(&combined_ref_count, __ATOMIC_RELAXED) & 0xFFFFFFFF` (lower 32 bits = strong count).
- `details::AtomicIncrementRelaxed`, `details::AtomicDecrementRelAcq`, `details::AtomicLoadRelaxed` are deleted from `base_details.h`.

## Validation
- `tests/cpp/test_ffi_object.cc`: Existing reference counting tests validate correctness.
- The change does not alter observable behavior -- only memory ordering guarantees, which are not directly testable in unit tests but are validated by the well-established pattern.

## Migration and Rollback
- No migration needed. The change is internal to `Object` methods.
- Rollback: revert to `ACQ_REL` on every decrement. Simple and low-risk.

## Related Design Docs
- [.memory/designs/0002-object-system-and-reference-counting.md](.memory/designs/0002-object-system-and-reference-counting.md)

## Related Diagrams
- None

## Evidence Matrix
- Release/acquire split in DecRef -> `.memory/commits/2025-06-18-d5209f0ce34d1f7c20c6cdc10cbc8445facb85e5.md` + `d5209f` + `include/tvm/ffi/object.h`
- Inlined atomics (removed helpers from base_details.h) -> `d5209f` + `include/tvm/ffi/object.h`, `include/tvm/ffi/base_details.h`
- MSVC path adjustment -> `d5209f` + `include/tvm/ffi/object.h`

## Supersedes
None (refines the refcount implementation from ADR-0002)

## Superseded By
None

## Follow-up Actions
- Benchmark on ARM hardware to quantify the improvement.
- Consider whether `IncRef` should use `relaxed` ordering (current) or `acquire` for additional safety in edge cases.
- Note: the release/acquire split pattern continues to apply with the combined u64 refcount (ADR-0026). The `fetch_sub` on `combined_ref_count` uses `RELEASE`, with an `ACQUIRE` fence only when the strong count reaches zero.
