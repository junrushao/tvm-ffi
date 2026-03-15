# ADR-004: Insertion-Order-Preserving Map

> Status: Accepted
> Decided in: commit 7d34eb8 ("[REFACTOR] Introduce and modernize FFI system")

## Context

The `Map<K,V>` container needs a well-defined iteration order for:
- **Serialization**: IR serialization must produce deterministic output for
  reproducible builds and meaningful diffs
- **Debugging**: Non-deterministic iteration makes debugging difficult when
  map contents appear in error messages or dumps
- **Testing**: Non-deterministic order makes output-based test assertions fragile

Standard `std::unordered_map` has implementation-defined iteration order that
can vary across platforms, compiler versions, and even between runs (with ASLR
affecting hash seeds).

## Decision

Make `MapObj` preserve insertion order. The implementation uses a dense array of
KV pairs (maintaining insertion order) with a separate hash index for O(1) lookup.

The `KVType` is `std::pair<Any, Any>` (32 bytes). Keys use string-aware hashing
and equality (`AnyHash`/`AnyEqual`).

## Consequences

### Positive

- Deterministic iteration order across all platforms and runs
- IR serialization produces identical output given identical input
- Test assertions on map contents are stable
- Better debugging experience: map contents appear in a predictable order

### Negative

- Slightly more memory than a flat hash map (the separate hash index adds overhead)
- Deletion is more complex (needs to maintain order invariant)
- Cannot use simple open-addressing without the auxiliary structures

### Debug Mode

When `TVM_FFI_DEBUG_WITH_ABI_CHANGE` is defined, the map tracks a `state_marker`
that is incremented on every modification. Iterators check this marker to detect
concurrent modification (ABI-incompatible debug check).
