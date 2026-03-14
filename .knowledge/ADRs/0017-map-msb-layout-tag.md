---
scope:
  - "0005-containers"
---
# Use MSB Tag in MapObj::slots_ for SmallMap/DenseMap Discrimination

**TL;DR**: The MSB (bit 63) of `MapObj::slots_` now distinguishes `SmallMapObj` (MSB set) from `DenseMapObj` (MSB clear), replacing the previous convention of comparing `slots_` against `SmallMapObj::kMaxSize`. This decouples layout discrimination from the slot count value.

## Context

`MapObj` has two concrete subclasses: `SmallMapObj` (inplace array for small maps, `kMaxSize = 4`) and `DenseMapObj` (heap-allocated hash table for large maps). The dispatch macro `TVM_FFI_DISPATCH_MAP` must quickly determine which subclass to cast to.

Previously, the dispatch compared `slots_` against `SmallMapObj::kMaxSize`:
```cpp
if (slots_ <= SmallMapObj::kMaxSize) { /* SmallMapObj */ }
else { /* DenseMapObj */ }
```

This coupled the dispatch logic to the `kMaxSize` constant. Changing `kMaxSize` (e.g., from 4 to 8) would require updating dispatch logic, `InsertMaybeReHash`, and any other code that used `slots_` for layout discrimination. The raw `slots_` value served double duty as both "slot count" and "layout discriminator," creating a subtle coupling.

Usecases:
- Future changes to `kMaxSize` (e.g., tuning for different workloads) can be done by changing only `SmallMapObj::kMaxSize` and the growth logic, without touching dispatch.
- Clearer dispatch logic: `IsSmallMap()` is self-documenting compared to `slots_ <= kMaxSize`.

Design Decisions:
- **`kSmallTagMask = 1ULL << 63`**: The MSB of `slots_` is reserved as a layout tag.
- **`IsSmallMap()` predicate**: `(slots_ & kSmallTagMask) != 0` -- the sole entry point for layout discrimination.
- **`NumSlots()` accessors**: `SmallMapObj::NumSlots()` returns `slots_ & ~kSmallTagMask`. `DenseMapObj::NumSlots()` returns `slots_` directly (MSB is always clear, guarded by assertion).
- **`SetSlotsAndSmallLayoutTag(n)` / `SetSlotsAndDenseLayoutTag(n)`**: The sole write points for `slots_`. The dense setter asserts `(n & kSmallTagMask) == 0`.
- **No code reads `slots_` directly** after this change; all access goes through `IsSmallMap()`, `NumSlots()`, or the setter methods.

Alternatives considered:

1. **Explicit `bool is_small_map_` field**: Unambiguous, but adds 8 bytes per map instance due to alignment padding in the `MapObj` layout. With millions of small maps in compiler IR, this overhead is significant.
2. **Virtual method `IsSmall()`**: Clean OO approach, but adds vtable overhead and breaks the POD-layout-compatible C ABI. The object system does not use virtual dispatch.
3. **Keep value-range convention**: Simpler (no bit manipulation), but couples dispatch to `kMaxSize` and prevents independent changes. The three-way branch in `InsertMaybeReHash` (`slots_ < kMaxSize`, `slots_ == kMaxSize`, else dense) was structurally fragile.

Consequences:
- **Zero-overhead**: MSB tagging has no storage cost (no new fields) and identical branch cost to the previous comparison.
- **ABI change**: `slots_` now has a different bit-level interpretation for `SmallMapObj`. Code reading `slots_` directly (outside the official API) will see incorrect values.
- **Encapsulation**: All `slots_` access is funneled through four methods, making future changes to the encoding localized.
- **Practical limit**: Maximum slot count is `2^63 - 1`, which is never a practical limitation.
- **Assertion-guarded**: `SetSlotsAndDenseLayoutTag` asserts MSB is clear, catching accidental tag corruption.

## Implementation Notes

- `TVM_FFI_DISPATCH_MAP` changed from `if (slots <= SmallMapObj::kMaxSize)` to `if (base->IsSmallMap())`.
- `InsertMaybeReHash` restructured from a three-way branch to a two-level dispatch: first `IsSmallMap()`, then `NumSlots() < kMaxSize` within the small-map branch.
- `DenseMapObj::InsertMaybeReHash` assertion changed from `TVM_FFI_ICHECK_GT(map_node->slots_, SmallMapObj::kMaxSize)` to `TVM_FFI_ICHECK(!map_node->IsSmallMap())`.
- Evidence: commit `03e8a6b` (PR #18211).

## Related Design Docs

- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- Container system with Map dual-layout design
- [`.knowledge/ADRs/0009-container-data-indirection.md`](../ADRs/0009-container-data-indirection.md) -- data_/data_deleter_ pattern in MapObj
