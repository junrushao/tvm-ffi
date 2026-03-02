---
adr: "0011"
title: "Use MSB Tag in MapObj::slots_ to Distinguish SmallMap from DenseMap"
status: "accepted"
date: "2025-08-09"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "abi"
  - "containers"
source_commits:
  - "03e8a6b8c995259d379358ab50ad81609a99083e"
source_ledgers:
  - ".memory/commits/2025-08-09-03e8a6b8c995259d379358ab50ad81609a99083e.md"
---

# ADR-0011: Use MSB Tag in MapObj::slots_ to Distinguish SmallMap from DenseMap

## TL;DR
- The MSB (bit 63) of `MapObj::slots_` now serves as a layout tag: set = SmallMap, clear = DenseMap. This replaces the previous heuristic of comparing `slots_ <= SmallMapObj::kMaxSize`.
- This decouples the SmallMap/DenseMap boundary from a fixed capacity constant, enabling future changes to `kMaxSize` without breaking dispatch logic.

## Status
Accepted

## Context
`MapObj` has two internal layouts: `SmallMapObj` (linear scan for small N) and `DenseMapObj` (robin-hood hash table). Both share the same `MapObj` base class with `slots_`, `size_`, and `data_` fields. Previously, the dispatch macro `TVM_FFI_DISPATCH_MAP` compared `slots_ <= SmallMapObj::kMaxSize` to determine the layout. This approach conflated capacity with type identity: changing `kMaxSize` would break the dispatch logic because the boundary between "small" and "dense" was encoded in the value of `slots_` rather than in an explicit tag.

## Decision Drivers
- Decoupling: The small/dense boundary should be an explicit type tag, not an implicit range check on capacity.
- Future flexibility: `kMaxSize` should be changeable without ABI breakage.
- Runtime safety: The tag should be cheap to check and hard to misuse.

## Decision
Use the MSB (bit 63) of `MapObj::slots_` as a layout discriminator:
- `kSmallTagMask = 1ULL << 63`: When set, the map is a `SmallMapObj`. When clear, it is a `DenseMapObj`.
- `MapObj::IsSmallMap()`: Returns `(slots_ & kSmallTagMask) != 0`.
- `SmallMapObj::NumSlots()`: Returns `slots_ & ~kSmallTagMask` (masks off the tag).
- `DenseMapObj::NumSlots()`: Returns `slots_` directly (MSB is guaranteed clear).
- `SetSlotsAndSmallLayoutTag(n)`: Sets `slots_ = (n & ~kSmallTagMask) | kSmallTagMask`.
- `SetSlotsAndDenseLayoutTag(n)`: Sets `slots_ = n` with `TVM_FFI_ICHECK` that MSB is clear.

The `TVM_FFI_DISPATCH_MAP` and `TVM_FFI_DISPATCH_MAP_CONST` macros and `InsertMaybeReHash` are rewritten to use `IsSmallMap()` instead of the slot-count comparison.

## Alternatives Considered
### Keep the slot-count comparison heuristic
- Pros: No ABI change. Simple to understand.
- Cons: `kMaxSize` cannot change without breaking dispatch. Conflates capacity with type identity. The three-way comparison in `InsertMaybeReHash` was logically fragile.

### Use a separate `layout_tag` field in MapObj
- Pros: No bit stealing. Clear intent.
- Cons: Increases `MapObj` size. ABI change (new field). Wastes space since `slots_` already has 63 unused bits for SmallMap (which never exceeds ~16 slots).

### Use the lowest bit instead of MSB
- Pros: Same technique, different bit.
- Cons: Lowest bit conflicts with even/odd slot counts in DenseMapObj. MSB is naturally unused since DenseMapObj slot counts are bounded well below 2^63.

## Why This Option Won
- MSB is naturally free: DenseMap slot counts are bounded by available memory (far below 2^63). SmallMap slot counts are bounded by `kMaxSize` (currently ~16).
- The tag is self-documenting: `IsSmallMap()` reads the tag bit, `NumSlots()` masks it off. The invariant is enforced by `SetSlotsAndDenseLayoutTag` asserting MSB clear.
- No ABI field change: `slots_` retains its position and size in `MapObj`. Only its interpretation changes.
- Future-proof: `kMaxSize` can change freely; the dispatch logic checks the tag, not the capacity.

## Consequences
### Positive
- SmallMap/DenseMap dispatch is now based on an explicit type tag, not a capacity heuristic.
- `InsertMaybeReHash` is cleaner: the `NumSlots() == kMaxSize` check is nested inside the `IsSmallMap()` branch.
- Future `kMaxSize` changes do not affect dispatch correctness.

### Negative
- ABI-level change: any code that reads `slots_` directly to determine map type or capacity must use the new accessors. All such call sites are within `map.h` and were updated in this commit.
- The MSB trick is a bit-level convention that requires documentation to prevent misuse.

### Risks
- Off-by-one in tag masking could corrupt slot counts. Mitigated by `TVM_FFI_ICHECK` in `SetSlotsAndDenseLayoutTag` and by encapsulating all access through the accessors.
- Serialized maps are unaffected (serialization goes through iterators, not raw field access).

## Implementation Notes
- All changes are confined to `include/tvm/ffi/container/map.h`.
- `kSmallTagMask` is `static constexpr` in `MapObj`.
- `IsSmallMap()` is on the `MapObj` base class.
- `NumSlots()` is defined separately on `SmallMapObj` (masks off tag) and `DenseMapObj` (returns raw value).
- `SetSlotsAndSmallLayoutTag` and `SetSlotsAndDenseLayoutTag` are private on the respective subclasses.

## Validation
- Existing `tests/cpp/test_ffi_map.cc` tests continue to pass, covering construction, lookup, insertion order, COW, and small-to-dense transition.
- The `TVM_FFI_ICHECK` in `SetSlotsAndDenseLayoutTag` provides runtime detection of accidental MSB-set values in DenseMap.

## Migration and Rollback
- In-tree: all callers use the accessor methods; no raw `slots_` reads remain. No migration needed.
- Rollback: revert the commit. The previous `slots_ <= kMaxSize` heuristic is restored.

## Related Design Docs
- [.memory/designs/0004-container-library.md](.memory/designs/0004-container-library.md) -- Map dual-layout architecture.

## Related Diagrams
- None

## Evidence Matrix
- `kSmallTagMask = 1ULL << 63` definition -> `.memory/commits/2025-08-09-03e8a6b8c995259d379358ab50ad81609a99083e.md` + `03e8a6b` + `include/tvm/ffi/container/map.h` line 228
- `IsSmallMap()` accessor on MapObj -> `.memory/commits/2025-08-09-03e8a6b8c995259d379358ab50ad81609a99083e.md` + `03e8a6b` + `include/tvm/ffi/container/map.h` line 233
- `SmallMapObj::NumSlots()` with mask -> `.memory/commits/2025-08-09-03e8a6b8c995259d379358ab50ad81609a99083e.md` + `03e8a6b` + `include/tvm/ffi/container/map.h` line 260
- `DenseMapObj::NumSlots()` (raw value) -> `.memory/commits/2025-08-09-03e8a6b8c995259d379358ab50ad81609a99083e.md` + `03e8a6b` + `include/tvm/ffi/container/map.h` line 554
- `SetSlotsAndSmallLayoutTag` with `kSmallTagMask` OR -> `.memory/commits/2025-08-09-03e8a6b8c995259d379358ab50ad81609a99083e.md` + `03e8a6b` + `include/tvm/ffi/container/map.h` line 334
- `SetSlotsAndDenseLayoutTag` with `TVM_FFI_ICHECK` MSB clear -> `.memory/commits/2025-08-09-03e8a6b8c995259d379358ab50ad81609a99083e.md` + `03e8a6b` + `include/tvm/ffi/container/map.h` line 1203
- `InsertMaybeReHash` rewrite with `IsSmallMap()` branch -> `.memory/commits/2025-08-09-03e8a6b8c995259d379358ab50ad81609a99083e.md` + `03e8a6b` + `include/tvm/ffi/container/map.h` lines 411-419

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Monitor whether `kMaxSize` changes are needed and verify dispatch correctness after any such change.
