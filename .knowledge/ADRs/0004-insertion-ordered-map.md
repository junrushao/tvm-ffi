---
scope:
  - "0007-containers.md"
---
# ADR: Insertion-Ordered Map

**TL;DR**: Decision to make `Map<K,V>` preserve insertion order, breaking compatibility with the legacy unordered Map, to match Python dict semantics and enable deterministic iteration.

## Context
- The legacy TVM Map used an unordered hash map, causing non-deterministic iteration order that varied across runs and platforms.
- Non-deterministic iteration causes reproducibility issues: two identical compilations could produce different output due to different Map iteration order.
- Python dicts (since 3.7) guarantee insertion order. Having the C++ Map match this behavior eliminates a category of cross-language behavioral mismatches.
- The main cost of insertion-ordered maps is slightly more memory per entry (need to maintain both the hash table and a dense insertion-order array).

Usecases:
- Deterministic IR printing: iterating over a Map of attributes always produces the same output, regardless of platform or hash seed.
- Cross-language consistency: a Map created in C++ and iterated in Python produces the same order.
- Serialization/deserialization: insertion-ordered maps enable round-trip stability (serialize -> deserialize -> serialize produces identical output).

Design Decisions:
- **Open-addressing hash table with dense arrays**: The Map implementation uses separate dense arrays for keys and values (maintaining insertion order) with an index hash table for O(1) lookup. This trades ~25% more memory for deterministic O(n) iteration in insertion order.
- **Breaking change from legacy**: Legacy code that depended on unordered iteration may observe different ordering. This is intentional and considered a correctness improvement, not a regression.
- **Immutability preserved**: Map remains immutable. To "modify" a Map, create a new one with the desired changes. This simplifies the hash table implementation (no tombstones needed).

## Implementation Notes
- The Map uses three arrays: `keys[]` (dense, insertion order), `values[]` (dense, parallel to keys), and `indices[]` (sparse hash table mapping hash -> dense index).
- Lookup: hash the key, probe `indices[]` for the dense index, then check `keys[dense_index]` for equality.
- Iteration: simply iterate `keys[]` and `values[]` in order (0, 1, 2, ...).
- Memory overhead vs unordered: one extra `int32_t` index per entry in the sparse table. For typical FFI usage (small maps of attributes), this is negligible.

## Related Design Docs
- [0007-containers.md](../designs/0007-containers.md) -- Container suite overview
