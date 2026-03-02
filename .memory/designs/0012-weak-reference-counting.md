---
design: "0012"
title: "Weak Reference Counting (WeakObjectPtr)"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-09-01"
last_updated: "2025-10-01"
scope:
  - "ffi/c_api"
  - "ffi/object"
  - "ffi/memory"
source_commits:
  - "ca9c3d10bb9640bffb972302f7064e49e592a526"
  - "13436f01111bc4218feb440a29a2e421bc148cc4"
  - "43d13e86ee24d1558f929e3b0faa3182ca1af872"
source_ledgers:
  - ".memory/commits/2025-09-01-ca9c3d10bb9640bffb972302f7064e49e592a526.md"
  - ".memory/commits/2025-09-25-13436f01.md"
  - ".memory/commits/2025-09-26-43d13e86.md"
---

# Weak Reference Counting (WeakObjectPtr)

## TL;DR
- `WeakObjectPtr<T>` provides `std::weak_ptr`-like semantics for FFI objects: it observes an object without preventing its destruction, and can be promoted to a strong `ObjectPtr<T>` via `lock()` if the object is still alive.
- The object header layout initially changed from `combined_ref_count` (uint64_t) to separate fields in commit `ca9c3d1`, then was reordered (refcounts first) in commit `13436f0` and re-combined into a single `uint64_t combined_ref_count` (strong in lower 32 bits, weak in upper 32 bits) in commit `43d13e8`, keeping the total header size at 24 bytes.
- The deleter function signature changes from `void(*)(TVMFFIObject*)` to `void(*)(TVMFFIObject*, int flags)`, using bitmask flags to separate object destruction from memory deallocation.

## Problem Statement
The object system previously had no way to observe an object without extending its lifetime. This prevented caching patterns (where a cache should not keep objects alive), parent-child back-references (where children should not prevent parent destruction), and interning tables (where the table should not prevent interned objects from being collected). The combined refcount design (ADR-0002) reserved space for weak references but did not expose weak pointer semantics in the C++ API.

## Context and Constraints
- The object header (`TVMFFIObject`) must remain exactly 24 bytes for ABI compatibility.
- Reference counting operations must remain lock-free (CAS-based) for performance.
- Existing code using `ObjectPtr<T>` and `ObjectRef` must continue to work unchanged.
- The deleter must distinguish between "destroy the object" (strong count -> 0) and "free the memory" (weak count -> 0), because weak references need the memory block to remain valid after the object is logically destroyed.
- The common case (no weak references) must not incur measurable overhead.

## Goals
- Provide `WeakObjectPtr<T>` with `lock()` / `TryPromoteWeakPtr()` for safe promotion.
- Support the split destruction protocol: separate object destruction from memory deallocation.
- Maintain the 24-byte header size.
- Optimize the common case (no weak references) with a single deleter call.

## Non-Goals
- Thread-safe weak reference creation from a strong reference that is concurrently being destroyed. The caller must hold a valid strong reference when creating a weak reference.
- Exposing weak references in the C API or to Python/Rust bindings (this is a C++-only feature for now).
- Automatic cycle breaking using weak references.

## Design
### Components and Responsibilities

- **`TVMFFIObject` header** (C struct, `c_api.h`): Layout is `{ uint64_t combined_ref_count; int32_t type_index; uint32_t __padding; void(*deleter)(void*, int); }`. Strong count is in the lower 32 bits, weak count in the upper 32 bits of `combined_ref_count`. Initially split into separate fields (commit `ca9c3d1`), then header reordered to refcounts-first (commit `13436f0`), then re-combined into single u64 (commit `43d13e8`). The `__padding` field is zero-initialized (commit `ffa2dbf`).

- **`TVMFFIObjectDeleterFlagBitMask`** (C enum, `c_api.h`): Defines flags for the deleter:
  - `kTVMFFIObjectDeleterFlagBitMaskStrong = 1` -- Destroy the object (run destructor).
  - `kTVMFFIObjectDeleterFlagBitMaskWeak = 2` -- Free the memory block.
  - `kTVMFFIObjectDeleterFlagBitMaskBoth = 3` -- Destroy and free (common case).

- **`WeakObjectPtr<T>`** (template, `object.h`): Weak reference smart pointer. Holds a raw `T*` pointer and increments/decrements the weak reference count. Key methods:
  - `lock()` -> `ObjectPtr<T>`: Attempts to promote weak to strong via CAS. Returns null `ObjectPtr` if the object is already destroyed (strong count == 0).
  - `use_count()`: Returns the current strong reference count (for diagnostics).
  - Copy/move semantics increment/decrement weak count atomically.

- **`Object::IncWeakRef()` / `Object::DecWeakRef()`** (methods, `object.h`): Atomic weak count management. `DecWeakRef()` calls the deleter with `kTVMFFIObjectDeleterFlagBitMaskWeak` when weak count reaches 0.

- **`Object::TryPromoteWeakPtr()`** (static method, `object.h`): CAS loop that attempts to increment strong count from a non-zero value. Returns true on success (and the caller gets a strong reference), false if strong count was already 0.

- **`SimpleObjAllocator`** (updated, `memory.h`): The deleter now accepts flags and handles three cases:
  - `Both`: Run destructor and free memory (common case when no weak refs exist).
  - `Strong` only: Run destructor but do not free memory (weak refs still hold the block).
  - `Weak` only: Free memory (last weak ref released after object was destroyed).

- **`TVMFFIObjectIncRef` / `TVMFFIObjectDecRef`** (C API, renamed): `TVMFFIObjectFree` is renamed to `TVMFFIObjectDecRef`. A new `TVMFFIObjectIncRef` is added for symmetry.

### Data Contracts and Invariants

- **Header layout**: `combined_ref_count` (8 bytes, strong lower 32 + weak upper 32) + `type_index` (4 bytes) + `__padding` (4 bytes) + `deleter` (8 bytes) = 24 bytes. The `deleter` is 8-byte aligned via the `__ensure_align` union trick.
- **Strong count invariant**: The object is alive as long as the strong count (lower 32 bits of `combined_ref_count`) > 0. When it reaches 0, the destructor runs.
- **Weak count invariant**: The memory block is valid as long as the weak count (upper 32 bits) > 0 OR strong count > 0. The weak count starts at 1 (representing the "strong reference group"), incremented for each `WeakObjectPtr`, and decremented when the last strong reference is released.
- **Promotion invariant**: `TryPromoteWeakPtr` succeeds only if the strong count > 0 at the time of the CAS on `combined_ref_count`. The CAS adds `kCombinedRefCountStrongOne` only if the strong bits are non-zero.
- **Common-case optimization**: When strong count reaches 0 after `fetch_sub`, a single atomic read of `combined_ref_count` reveals both counters. If `prev == kCombinedRefCountBothOne` (both counters were 1), the deleter is called with `kTVMFFIObjectDeleterFlagBitMaskBoth`, requiring only one atomic operation total instead of two separate atomic reads.

### Control Flow

1. **Object construction**: `make_object<T>(args...)` -> `AlignedAlloc` -> set `combined_ref_count = kCombinedRefCountBothOne` (strong=1, weak=1), `type_index`, `__padding = 0`, `deleter` -> return `ObjectPtr<T>`.

2. **Creating a weak reference**: `WeakObjectPtr<T> weak(strong_ptr)` -> `Object::IncWeakRef()` -> `atomic_fetch_add(&combined_ref_count, kCombinedRefCountWeakOne)` (adds 1 << 32).

3. **Promoting weak to strong**: `weak.lock()` -> `TryPromoteWeakPtr()`:
   ```
   loop:
     old = atomic_load(combined_ref_count)
     if (old & kCombinedRefCountMaskUInt32) == 0: return false  // strong == 0
     new = old + kCombinedRefCountStrongOne
     if CAS(combined_ref_count, old, new): return true
   ```

4. **Strong ref destruction** (`ObjectPtr` destructor): `Object::DecRef()`:
   ```
   old = atomic_fetch_sub(combined_ref_count, 1, RELEASE)  // dec strong by 1
   if (old & kCombinedRefCountMaskUInt32) == 1:  // was the last strong ref
     acquire_fence()
     if old == kCombinedRefCountBothOne:
       // No weak refs (both counters were 1): single-call fast path
       deleter(self, Both)
     else:
       // Weak refs exist: destroy only, then dec weak
       deleter(self, Strong)
       DecWeakRef()
   ```

5. **Weak ref destruction** (`WeakObjectPtr` destructor): `Object::DecWeakRef()`:
   ```
   old = atomic_fetch_sub(combined_ref_count, kCombinedRefCountWeakOne, RELEASE)
   if (old >> 32) == 1:  // was the last weak ref
     acquire_fence()
     deleter(self, Weak)  // free memory only
   ```

### Extension Points
- **Custom deleters with weak ref support**: Any custom deleter must handle the `flags` parameter correctly, distinguishing destruction from deallocation.
- **Weak ref observation**: `WeakObjectPtr::use_count()` provides diagnostic access to the strong count without promotion.

## Alternatives Considered
### Keep combined_ref_count and extract weak count via bit manipulation
- Pros: No header layout change. Backward compatible.
- Cons: The combined layout (strong in low 32 bits, weak in high 32 bits) limits strong count to 2^32. Separate fields allow `strong_ref_count` to use the full 64-bit range while `weak_ref_count` uses 32 bits (weak refs are rare, so 2^32 is sufficient).

### Use std::weak_ptr / std::shared_ptr instead
- Pros: Standard, well-tested.
- Cons: Non-intrusive (separate control block), not C ABI compatible, cannot participate in the FFI object header.

### External weak reference table (map from pointer to weak count)
- Pros: No header changes at all. Only objects with weak refs pay the cost.
- Cons: Requires a global lock or concurrent hash map. Much slower promotion (hash lookup + CAS). Memory fragmentation from the table.

## Trade-offs
- **Optimized**: Common case (no weak references) incurs zero measurable overhead -- the deleter is called once with `Both` flag. Strong incref/decref is the same single atomic operation as before.
- **Sacrificed**: The `strong_ref_count` is now a separate field (not packed with weak count), so "read both counts atomically" requires two atomic loads. This only matters during the last strong decref (rare path). The header layout change is an ABI break.

## Interfaces and Compatibility
- **C ABI**: `TVMFFIObject` header layout changed (ABI break). `TVMFFIObjectFree` renamed to `TVMFFIObjectDecRef`. `TVMFFIObjectIncRef` added. Deleter signature gains `int flags` parameter.
- **C++ API**: `WeakObjectPtr<T>` (new), `Object::IncWeakRef()` / `DecWeakRef()` / `TryPromoteWeakPtr()` (new). `ObjectPtr<T>` unchanged in API but updated internally.
- **Python/Rust**: Not exposed. These bindings use `TVMFFIObjectIncRef`/`TVMFFIObjectDecRef` only.

## Failure Modes and Mitigations
- **Promotion after destruction**: `lock()` returns null `ObjectPtr`. Caller must check `defined()`.
- **Weak count overflow**: If `weak_ref_count` exceeds 2^32, behavior is undefined. Mitigated by practical impossibility (~4 billion weak references to a single object).
- **Deleter flag mismatch**: A custom deleter that ignores flags could double-free or leak memory. Mitigated by `SimpleObjAllocator` providing a correct reference implementation.

## Observability and Validation
- `WeakObjectPtr::use_count()` returns the strong count for diagnostics.
- Unit tests verify: creation, promotion, failed promotion after destruction, lifecycle (destructor timing vs memory deallocation), common-case optimization (single deleter call).

## Migration and Rollout
- **ABI break**: All bindings must be recompiled against the new `TVMFFIObject` header.
- The `TVMFFIObjectFree` -> `TVMFFIObjectDecRef` rename requires updating C ABI consumers.
- Custom deleters must be updated to accept and handle the `int flags` parameter.

## Diagrams
- [.memory/diagrams/0010-weak-ref-lifecycle.md](.memory/diagrams/0010-weak-ref-lifecycle.md)

## Related ADRs
- [.memory/ADRs/0002-combined-refcount-in-single-u64.md](.memory/ADRs/0002-combined-refcount-in-single-u64.md) -- Superseded by the split refcount layout.
- [.memory/ADRs/0008-release-acquire-refcount-split.md](.memory/ADRs/0008-release-acquire-refcount-split.md) -- The release/acquire pattern is preserved in the new design.

## Evidence Matrix
- TVMFFIObject header layout change (split refcounts) -> `.memory/commits/2025-09-01-ca9c3d10bb9640bffb972302f7064e49e592a526.md` + `ca9c3d1` + `include/tvm/ffi/c_api.h`
- `WeakObjectPtr<T>` template -> `ca9c3d1` + `include/tvm/ffi/object.h`
- `TryPromoteWeakPtr` CAS loop -> `ca9c3d1` + `include/tvm/ffi/object.h`
- `TVMFFIObjectDeleterFlagBitMask` enum -> `ca9c3d1` + `include/tvm/ffi/c_api.h`
- `SimpleObjAllocator` deleter update -> `ca9c3d1` + `include/tvm/ffi/memory.h`
- `TVMFFIObjectFree` -> `TVMFFIObjectDecRef` rename -> `ca9c3d1` + `include/tvm/ffi/c_api.h`
- Common-case optimization (check weak==1) -> `ca9c3d1` + `include/tvm/ffi/object.h` DecRef method

## Open Questions
- Should weak references be exposed in the Python binding for caching patterns?
- Should there be a `WeakObjectRef` (like `ObjectRef` but weak) for ergonomic C++ usage?

## Confidence and Risk
- Confidence: high
- Residual risks: The ABI break affects all existing bindings. Custom deleters that do not handle flags correctly will malfunction. The split refcount layout means the "read both counts atomically" property from ADR-0002 is lost (but this property was only useful in the deletion path, which now uses the flag-based protocol instead).
