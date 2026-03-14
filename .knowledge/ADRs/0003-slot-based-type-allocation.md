---
scope:
  - "0003-object-system"
  - "0001-c-abi"
---
# Slot-Based Type Index Allocation for O(1) IsInstance

**TL;DR**: Parent types reserve contiguous index ranges for their children in the `TypeTable`. This enables O(1) `IsInstance` checks via a simple range comparison (`target_index <= object_index < target_index + slots`), with a fallback ancestor table lookup for overflow cases.

## Context

Deep type hierarchies require frequent `IsInstance` checks (e.g., "is this object a subclass of `ExprNode`?"). The naive approach -- walking the ancestor chain -- is O(depth). Hash-set-based approaches have poor cache behavior. The system needs a mechanism that works for the common case in O(1) while handling edge cases correctly.

Usecases:
- `Any::cast<Array<Expr>>()` must check that every element `IsInstance<ExprNode>` -- this is called millions of times during compilation.
- `TypeTraits<T>::CheckAnyStorage` uses `IsInstance` to validate container elements.
- Python `isinstance(obj, ExprNode)` dispatches through the same mechanism.

Design Decisions:
- **Contiguous slot reservation**: Each type declares `_type_child_slots` (number of children it expects). The `TypeTable` allocates that many contiguous indices starting from the parent's index. Children are allocated within this range sequentially.
- **Range check fast path**: `IsInstance<T>` checks `object_type_index >= T::RuntimeTypeIndex() && object_type_index < T::RuntimeTypeIndex() + T::_type_child_slots + 1`. This is a single comparison pair, branch-predictor friendly, and cache-line local (no pointer chasing).
- **Overflow fallback**: If children exceed the reserved slots, `_type_child_slots_can_overflow = true` enables allocation from a global counter (`type_counter_`). `IsInstance` falls back to `type_ancestors[TargetType::_type_depth] == target_type_index` -- an O(1) table lookup (not O(depth) chain walking).
- **Compile-time specialization**: `IsInstance` uses `if constexpr` to select the optimal path: exact match for final types, range check for types with known child slots, and fallback for overflow-capable types.

**Alternatives considered**:

1. **Linear ancestor scan**: Walk `type_ancestors[0..depth]` looking for the target.
   - Pros: No slot reservation complexity.
   - Cons: O(depth) per check. For hierarchies of depth 5-10, this is 5-10x slower than a single range check.

2. **Hash-set of ancestors per type**: Store all ancestors in a hash set, check membership.
   - Pros: O(1) amortized lookup.
   - Cons: Hash set per type consumes more memory and has poor cache locality (pointer chasing into heap-allocated buckets). The contiguous range check reads only two integers.

3. **Bitmap per type**: Store a bit vector where bit i is set if type i is an ancestor.
   - Pros: O(1) lookup.
   - Cons: Bitmap size grows with the total number of types. With dynamic allocation potentially producing thousands of types, bitmaps become prohibitively large.

**Consequences**:
- Types with under-estimated `_type_child_slots` waste index space (reserved but unused slots).
- Types with over-estimated slots work correctly but miss the fast path for overflow children (fall back to ancestor table).
- Reordering or removing types from the hierarchy can cause slot fragmentation, but this is mitigated by the overflow mechanism.
- The `TypeTable::Dump()` method helps diagnose slot utilization: it prints `num_child_slots`, `num_children`, and `expected_child_slots` for each type.

## Implementation Notes

- `TypeTable::GetOrAllocTypeIndex` implements the three-tier allocation: static index -> parent's reserved pool -> overflow counter.
- The ancestor table `type_ancestors[depth]` stores the type_index of the ancestor at each depth level. This is copied from the parent's ancestor table plus the parent itself.
- `IsInstance` compiled code for a final type reduces to a single `cmp` + `je` instruction. For a non-final type with child slots, it reduces to two `cmp` instructions (range check).
- Evidence: `src/ffi/object.cc:100-167` (GetOrAllocTypeIndex), `include/tvm/ffi/object.h:661-693` (IsObjectInstance), commit `7d34eb8`.

## Related Design Docs

- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- TypeTable and IsInstance implementation
- [`.knowledge/ADRs/0002-type-index-partitioning.md`](0002-type-index-partitioning.md) -- The three-range partition that this allocation operates within
