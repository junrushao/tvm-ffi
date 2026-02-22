# ADR 021: Map Insertion-Order Guarantee

- Status: Accepted
- Date: 2025-08-09
- Owners: Tianqi Chen

## Context

Hash maps traditionally have unspecified iteration order. TVM FFI's `Map<K,V>`
is exposed to Python where dictionaries preserve insertion order (guaranteed
since Python 3.7). Having deterministic iteration also benefits serialization
reproducibility and structural hashing: the same logical map always produces the
same byte stream and the same hash, regardless of internal table layout or
rehash events.

## Decision

Guarantee that `Map<K,V>` (and `Dict<K,V>`) preserve insertion order. Iteration
over a map yields key-value pairs in the order they were first inserted, matching
Python dictionary semantics.

The implementation achieves this through two complementary mechanisms:

1. **`DenseMapBaseObj`** threads a doubly-linked iteration list through the hash
   table entries. Each `ItemType` carries `prev` and `next` index fields
   (`uint64_t`), and the map object maintains `iter_list_head_` and
   `iter_list_tail_` pointers. New entries are appended to the tail via
   `IterListPushBack`. Erasure unlinks the node via `IterListUnlink`. Rehashing
   replays insertions in list order (`iter_list_head_` walk in
   `InsertMaybeReHash`) so the order is preserved across table growth.

2. **`SmallMapBaseObj`** stores entries in a contiguous array and iterates by
   simple index increment (`0, 1, 2, ...`). New entries are appended at
   `data_[size_]`. Erasure uses `memmove` to shift later elements down,
   preserving insertion order trivially.

## Consequences

- Positive: Deterministic iteration matches Python `dict` semantics, eliminating
  a class of cross-language behavioral mismatches.
- Positive: Serialization output is reproducible -- the same map always
  serializes to the same byte sequence.
- Positive: Structural hashing over map contents is stable and deterministic.
- Negative: Two extra `uint64_t` fields (`prev`, `next`) per `DenseMapBaseObj`
  entry, increasing per-entry overhead by 16 bytes.
- Negative: Insertion, erasure, and rehash must maintain the linked list, adding
  a small constant-time cost to each operation.
- Migration/Rollout: No migration needed for users. The guarantee is inherent in
  the data structure and applies to all existing `Map`/`Dict` usage.

## References
- Range summary: `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
- Evidence commits: `5a6b211` (map_base.h reorganization), `03e8a6b` (MSB tag dispatch)
- External references: none

## Related Design Docs
- `.repo-knowledge/adr/006-msb-tag-map-dispatch.md`
- `.repo-knowledge/adr/017-mutable-vs-immutable-containers.md`

## Notes
The doubly-linked iteration list approach is analogous to the technique used by
CPython's `dict` implementation (compact dict, PEP 468/PEP 520) and by Java's
`LinkedHashMap`. By embedding the prev/next pointers directly in the hash table
entry (`ItemType`), the implementation avoids separate node allocations and
maintains good cache locality during iteration.
