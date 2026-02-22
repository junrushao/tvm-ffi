# ADR 017: Mutable vs Immutable Container Split

- Status: Accepted
- Date: 2026-02-13
- Owners: Junru Shao, Tianqi Chen

## Context

`Array<T>` and `Map<K,V>` are immutable containers with copy-on-write (COW)
semantics. Mutations produce a new object; the old object is unchanged. This is
the correct semantic for IR nodes and value types where transparent sharing is
expected.

However, constructing data structures incrementally (e.g., populating a list in
a loop, building a cache map) requires repeatedly copying the entire container,
which is both inefficient and semantically incorrect when multiple references
should observe mutations.

Two options were considered:
1. Add mutation methods to `Array` and `Map` with "unique ownership" checks.
2. Introduce separate `List` and `Dict` mutable types.

## Decision

Separate `List<T>` and `Dict<K,V>` mutable container types were introduced
alongside the existing `Array<T>` and `Map<K,V>`.

Shared base classes (`SeqBaseObj` for sequences, `MapObj` for maps) extract
common infrastructure. Mutable containers share storage and iteration code with
their immutable counterparts but have distinct type indices (`kTVMFFIList`,
`kTVMFFIDict`) and do not enforce COW semantics.

The decision to use separate types rather than mutation on existing containers
was driven by:
- **Type safety**: The type system distinguishes mutable from immutable at
  compile time. Functions accepting `Array<T>` cannot accidentally mutate it.
- **Backward compatibility**: All existing code using `Array` and `Map`
  continues to work without changes.
- **Thread safety clarity**: `Array`/`Map` are safe to share across threads
  (immutable). `List`/`Dict` require external synchronization (mutable).

## Consequences

- Positive: Clean separation of mutable/immutable semantics; no behavioral
  changes to existing `Array`/`Map` types; type-checker support via distinct
  stub annotations (`Sequence` vs `MutableSequence`, `Mapping` vs
  `MutableMapping`).
- Negative: Code duplication potential between mutable and immutable variants
  (mitigated by shared base classes); users must choose between `Array` and
  `List`, `Map` and `Dict`.
- Migration/Rollout: Purely additive. Existing code is unaffected. New code can
  opt into `List`/`Dict` where mutable semantics are needed.

## References
- Range summary: `.repo-knowledge/ranges/2026-02-21-B1611E0-ECC7471.md`
- Evidence commits: `9513c2f`, `5a6b211`, `c1af3b3`, `7786133`
- External references: none

## Related Design Docs
- `.repo-knowledge/design/011-mutable-containers.md`
- `.repo-knowledge/design/001-type-erased-value-system.md`

## Notes
- Cycle detection was added to serialization, structural hash/equal, and JSON
  writer specifically for mutable containers, since they (unlike immutable ones)
  can form reference cycles.
- The `docs/concepts/containers.rst` page provides unified documentation for
  all container types including guidance on when to use mutable vs immutable.
