---
adr: "0002"
title: "Pack Strong and Weak Reference Counts into a Single uint64_t"
status: "superseded"
date: "2025-05-06"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "memory-management"
  - "abi"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
source_ledgers:
  - ".memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md"
---

# ADR-0002: Pack Strong and Weak Reference Counts into a Single uint64_t

## TL;DR
- `TVMFFIObject::combined_ref_count` stores the strong reference count in the lower 32 bits and the weak reference count in the upper 32 bits of a single `uint64_t`.
- This allows atomic increment/decrement of the strong count with plain +1/-1 operations and a single atomic read to check both counters during deletion.

## Status
Superseded (by split refcount layout in commit `ca9c3d1`)

## Context
Every heap-allocated object in TVM FFI (`TVMFFIObject`) needs reference counting for lifetime management. The system uses intrusive reference counting (the count is embedded in the object header). Two reference kinds are needed:
1. **Strong references** (`ObjectPtr<T>`): keep the object alive and prevent destructor execution.
2. **Weak references**: allow the memory block to be reclaimed only after both strong and weak counts reach zero.

The deleter callback receives flags (`TVMFFIObjectDeleterFlagBitMask`) indicating whether to run the destructor (strong -> 0), free the memory block (weak -> 0), or both.

The object header must be compact: it is prepended to every heap object, and padding bloats all allocations.

## Decision Drivers
- Performance: reference counting is the hottest operation in the system (every function call argument may involve incref/decref).
- Atomicity: strong incref/decref should be a single atomic operation, not a CAS loop.
- Space efficiency: the object header should be minimal (currently 24 bytes: 8 refcount + 4 type_index + 4 padding + 8 deleter).
- Correctness during deletion: when strong count reaches zero, the runtime must atomically check whether weak count is also zero to decide whether to free the memory block.

## Decision
Use a single `uint64_t combined_ref_count` with the layout:

```
Bits [0, 31]  : strong_ref_count (uint32_t)
Bits [32, 63] : weak_ref_count   (uint32_t)
```

**Rationale for bit ordering**: Placing the strong count in the lower 32 bits means that `atomic_fetch_add(combined_ref_count, 1)` and `atomic_fetch_sub(combined_ref_count, 1)` increment/decrement the strong count without touching the weak count (no carry occurs as long as strong_ref_count < 2^32, which is always true in practice). This avoids needing a CAS loop for the common strong incref/decref path.

When the strong count reaches zero after a decrement, a single atomic load of `combined_ref_count` reveals the weak count in the upper 32 bits, enabling the runtime to decide deletion behavior (destroy only vs. destroy + free) without a separate atomic read.

## Alternatives Considered
### Two separate uint32_t fields
- Pros: Simpler to understand. Each counter is independently atomic.
- Cons: Checking both counters during deletion requires two atomic loads (or a lock). Header size is the same (8 bytes either way due to alignment), but the combined approach provides a "read both at once" primitive for free.

### Single uint32_t strong count only (no weak refs)
- Pros: Simplest. 4 bytes saved.
- Cons: Cannot support weak references. Some patterns (e.g., preventing cyclic leaks, caching) require weak references. Future extensibility is lost.

### std::shared_ptr control block
- Pros: Standard, well-tested.
- Cons: Non-intrusive (separate allocation for control block). Not compatible with C ABI. Prevents inline storage optimizations. Cannot expose refcount layout to foreign languages.

## Why This Option Won
- The combined layout is ABI-compatible with a struct `{ uint32_t strong, uint32_t weak }` on little-endian platforms, so foreign language bindings can read individual counts.
- Strong incref/decref is a single `fetch_add`/`fetch_sub` with no CAS, which is optimal on x86 (`lock xadd`) and ARM (`ldxr`/`stxr` loop but single instruction pair).
- The "read both counts atomically" property during deletion is a natural consequence of the packing, not an additional cost.

## Consequences
### Positive
- Minimal overhead for the most common operation (strong incref/decref).
- Atomic check of both counters during deletion prevents a race between the last strong decref and a concurrent weak decref.
- ABI-stable: the field position and semantics are fixed in `TVMFFIObject`.

### Negative
- Maximum strong or weak reference count is 2^32 - 1 (~4 billion). Overflow would corrupt the other counter. In practice this is not a concern.
- The bit layout assumes little-endian for struct equivalence. On big-endian platforms, the struct layout `{ uint32_t strong, uint32_t weak }` would need byte-swapping or different field order. The current codebase does not officially support big-endian.

### Risks
- A bug that overflows the strong count past 2^32 would silently corrupt the weak count. Mitigated by the practical impossibility of 4 billion concurrent references.
- Big-endian platforms may need adaptation. Mitigated by the project's focus on x86-64, ARM64 (all little-endian).

## Implementation Notes
- `TVMFFIObject::combined_ref_count` is defined in `include/tvm/ffi/c_api.h`.
- `TVMFFIObjectIncRef` / `TVMFFIObjectDecRef` are the C ABI functions that perform atomic operations.
- The deleter function signature is `void (*deleter)(void* self, int flags)` where flags come from `TVMFFIObjectDeleterFlagBitMask`: `kTVMFFIObjectDeleterFlagBitMaskStrong` (destroy object), `kTVMFFIObjectDeleterFlagBitMaskWeak` (free memory), `kTVMFFIObjectDeleterFlagBitMaskBoth` (both).

## Validation
- `tests/cpp/test_ffi_object.cc` tests reference counting semantics.
- The C ABI functions are tested via integration with Python and Rust bindings (in later commits).

## Migration and Rollback
- This is a foundational ABI decision from the root commit. Changing it requires a major ABI version bump and recompilation of all bindings.

## Related Design Docs
- [.memory/designs/0002-object-system-and-reference-counting.md](.memory/designs/0002-object-system-and-reference-counting.md)
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)

## Related Diagrams
- [.memory/diagrams/0002-object-type-hierarchy.md](.memory/diagrams/0002-object-type-hierarchy.md)

## Evidence Matrix
- combined_ref_count definition -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `include/tvm/ffi/c_api.h` lines 231-251
- Deleter flag bitmask enum -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 200-225
- Ledger reflection on combined refcount design -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` Reflection section

## Supersedes
None

## Superseded By
[.memory/ADRs/0026-tvmffiobject-header-reorder-combined-refcount.md](.memory/ADRs/0026-tvmffiobject-header-reorder-combined-refcount.md) -- The combined `uint64_t` layout was temporarily replaced by separate fields in commit `ca9c3d1`, then re-adopted with a reordered header (refcounts at offset 0) and full weak reference semantics in commits `13436f0` / `43d13e8`. The current layout uses `combined_ref_count` with strong in lower 32 bits and weak in upper 32 bits.

## Follow-up Actions
- Document big-endian considerations if cross-platform support is ever added.
