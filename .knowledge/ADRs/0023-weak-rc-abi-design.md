---
scope:
  - "0001-c-abi"
  - "0003-object-system"
---
# Weak Reference Counting ABI Design

**TL;DR**: The decision to add weak reference counting to `TVMFFIObject` by splitting the former 4-byte `ref_counter` into `uint32_t weak_ref_count` + `uint64_t strong_ref_count`, growing the header from 16 to 24 bytes. An implicit weak reference convention and flag-based deleter dispatch avoid overhead for strong-only objects.

## Context

Weak references are needed for future cyclic dependency breaking in the object graph (e.g., parent-child relationships where the child holds a reference back to its parent). The ABI must incorporate weak RC support before the ABI freeze, even though weak references are "not strongly needed yet" at the time of the change.

The core design question is: how to add weak reference counting to the `TVMFFIObject` header while minimizing overhead for the common case (strong-only objects, which are the vast majority).

## Alternatives

### 1. Split `uint32_t weak_ref_count` + `uint64_t strong_ref_count` in header (chosen)

Grow `TVMFFIObject` from 16 to 24 bytes. Strong count is 64-bit (matching the prior `int32_t ref_counter` upgrade path to wider range), weak count is 32-bit (weak references are expected to be rare).

- Pros: No separate control block allocation. Strong-only objects pay only 8 extra bytes per object. The implicit weak reference (`weak_ref_count = 1` at allocation) means strong-only destruction is a single deleter call with both flags set.
- Cons: Every object grows by 8 bytes, even if never weakly referenced. The 24-byte header shifts all cell data offsets from 16 to 24, which is a hard ABI break.

### 2. Single 64-bit ref count with bit-field splitting (torch c10 approach)

Use a single `uint64_t` with the upper 32 bits for weak count and lower 32 bits for strong count. Header stays at 16 bytes.

- Pros: No header size change, no ABI break for cell offsets.
- Cons: Atomic CAS on the combined field is more complex. The strong count is limited to 32 bits. The bit manipulation adds overhead to every IncRef/DecRef.

### 3. Separate control block (std::shared_ptr approach)

Allocate a separate control block containing both ref counts. The object header remains 16 bytes.

- Pros: No change to object header. Weak RC only allocated when needed.
- Cons: Extra heap allocation per object. Two cache lines touched per ref-count operation. Violates the intrusive ref-counting design goal (all lifetime state in the header).

### 4. Defer weak RC to application level

Do not add weak RC to the ABI. Let applications break cycles manually (e.g., via explicit `nullptr` assignment or weak handle tables).

- Pros: No ABI change. Simpler.
- Cons: Once the ABI is frozen, adding weak RC later would require a breaking change. The pre-freeze window is the right time to incorporate it.

## Decision

Alternative 1: split `uint32_t weak_ref_count` + `uint64_t strong_ref_count` in the 24-byte header. Key design choices:

- **Implicit weak reference**: `make_object` initializes `weak_ref_count = 1`. This implicit weak reference is decremented when `strong_ref_count` drops to zero. For strong-only objects, both counts reach zero simultaneously and the deleter is called once with `kTVMFFIObjectDeleterFlagBitMaskBoth`.
- **Flag-based deleter**: The deleter signature changes from `void(*)(TVMFFIObject*)` to `void(*)(TVMFFIObject*, int flags)`. Bit 0 = call destructor, bit 1 = free memory. This avoids adding a second deleter function pointer.
- **`WeakObjectPtr<T>`**: CAS-based `TryPromoteWeakPtr` attempts to increment `strong_ref_count` from a non-zero value. If strong count is zero (object already destroyed), promotion fails.
- **C API rename**: `TVMFFIObjectFree` -> `TVMFFIObjectDecRef` for clarity. `TVMFFIObjectIncRef` added as symmetric counterpart.

## Consequences

- **ABI-breaking**: `sizeof(TVMFFIObject)` changes from 16 to 24. All language bindings (Python/Cython, Rust), shared libraries, and code with `static_assert(sizeof(TVMFFIObject) == 16)` must be updated.
- **Cell offset change**: Object cell data moves from offset 16 to offset 24.
- **8-byte overhead per object**: Universal, even for objects that never use weak references. Mitigated by the fact that objects are heap-allocated and typically larger than 24 bytes.
- **C API rename cascade**: All callers of `TVMFFIObjectFree` must update to `TVMFFIObjectDecRef`.

## Implementation Notes

- Header layout: `{int32_t type_index, uint32_t weak_ref_count, uint64_t strong_ref_count, union{deleter, __ensure_align}}` -- exactly 24 bytes with natural alignment.
- `uint32_t` for weak count (not `uint64_t`) to keep the header at 24 bytes, since weak references are expected to be rare and 4 billion weak refs is sufficient.
- Package version bumped to `0.1.0a6` with this change.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- TVMFFIObject struct layout
- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- Object allocation, ref-counting, WeakObjectPtr
- Commit: `.knowledge/commits/2025-09-01-ca9c3d10bb9640bffb972302f7064e49e592a526.md` + `ca9c3d1`
