# ADR 006: MSB Tagging for Map Small/Dense Dispatch

- Status: Accepted
- Date: 2025-08-09
- Owners: Tianqi Chen

## Context

The `Map` container uses two internal representations: `SmallMapObj` (for small
maps, linear scan) and `DenseMapObj` (for larger maps, hash table). The
dispatch between these two representations was previously based on comparing
`slots_` against `SmallMapObj::kMaxSize`:

```cpp
if (base->slots_ <= SmallMapObj::kMaxSize) {
  // small map path
} else {
  // dense map path
}
```

This created a tight coupling between the dispatch logic and the size
threshold. Changing `kMaxSize` in the future would require updating all
dispatch sites and could break binary compatibility, since the `slots_` field
is part of the ABI-visible `MapObj` struct.

## Decision

Use the most significant bit (MSB) of `MapObj::slots_` as a tag bit to
distinguish small maps from dense maps:

- MSB set (`kSmallTagMask = 1ULL << 63`): `SmallMapObj`
- MSB clear: `DenseMapObj`

New accessor methods encapsulate the tagging:

| Method | Purpose |
|--------|---------|
| `MapObj::IsSmallMap()` | Check if MSB is set |
| `SmallMapObj::NumSlots()` | Return `slots_ & ~kSmallTagMask` |
| `SmallMapObj::SetSlotsAndSmallLayoutTag()` | Set slots with MSB |
| `DenseMapObj::NumSlots()` | Return `slots_` (MSB guaranteed clear) |
| `DenseMapObj::SetSlotsAndDenseLayoutTag()` | Assert MSB clear |

The `TVM_FFI_DISPATCH_MAP` and `TVM_FFI_DISPATCH_MAP_CONST` macros now use
`base->IsSmallMap()` instead of the size-threshold comparison.

This is an **ABI-level change**: any code that directly inspects
`MapObj::slots_` will observe the MSB tag on small maps.

## Consequences

- Positive: The small/dense boundary (`kMaxSize`) can be changed in the future
  without modifying dispatch logic or breaking the ABI dispatch check.
- Positive: Dispatch is a single bit test, which is marginally faster than a
  comparison.
- Negative: **ABI change** to `MapObj::slots_` semantics. Code that reads
  `slots_` directly must use `NumSlots()` instead.
- Negative: Serialized maps that store raw `slots_` values will differ (MSB
  set for small maps).
- Migration/Rollout: Replace direct `slots_` access with `IsSmallMap()` and
  `NumSlots()`. Recompile all code that touches `MapObj` internals.

## References
- Range summary: `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
- Evidence commits: `03e8a6b8c995259d379358ab50ad81609a99083e`
- External references: none

## Related Design Docs
- `.repo-knowledge/design/003-c-abi-stability.md`

## Notes
The MSB tagging approach is a well-known technique for discriminated unions in
systems programming. By reserving only one bit, the remaining 63 bits of
`slots_` still allow maps with up to 2^63 - 1 slots, which is far beyond any
practical limit.
