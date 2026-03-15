---
scope:
  - "0008-containers"
---
# Insertion-Order-Preserving Map

**TL;DR**: The decision to make `Map<K,V>` preserve insertion order using a dense hashmap, instead of using an unordered or sorted map.

## Context
- TVM's intermediate representation (IR) uses `Map` extensively for storing attributes, configurations, and mappings.
- IR printing and serialization must be deterministic: the same IR should always produce the same textual output, regardless of platform or hash seed.
- The old TVM runtime's Map did not guarantee iteration order, leading to non-deterministic IR dumps and flaky tests.

Usecases:
- Printing IR attributes: `{"target": "llvm", "opt_level": 3}` must always print in the same order the attributes were added.
- Diffing two IR dumps: insertion-order iteration ensures that structurally equivalent IRs produce identical text, enabling `diff`-based comparison.
- Cross-language Map passing: Python `dict` (insertion-ordered since 3.7) naturally maps to an insertion-ordered FFI Map.

Design Decisions:
- **Use a dense hashmap with insertion-order iteration**: Internally, the map stores key-value pairs in an insertion-ordered array and uses a hash table for O(1) lookup. Iteration walks the array linearly.
- **Use `AnyHash`/`AnyEqual` for key hashing**: Keys are stored as `Any` values, using a polymorphic hash that dispatches based on `type_index`. This supports int, string, and object keys uniformly.
- **Immutable (COW) semantics**: Like `Array`, `Map` uses copy-on-write — mutation of a shared map copies the data first.

## Implementation Notes
- `MapObj` uses an open-addressing hash table with a separate insertion-ordered storage array of `(Any key, Any value)` pairs.
- Hash collisions are resolved by linear probing.
- `AnyHash` computes hashes based on the value's type_index: for ints it hashes the int value, for strings it hashes the content, for objects it hashes the pointer.
- `AnyEqual` compares values by type and content: two `Any` values are equal if they have the same type_index and the same value representation.
- Alternative considered: `std::map` (sorted order) — rejected because logarithmic insertion is slower than amortized O(1), and alphabetical order does not match user intent.
- Alternative considered: `std::unordered_map` — rejected because iteration order is non-deterministic.

## Related Design Docs
- [0008-containers.md](.knowledge/designs/0008-containers.md)
- [0002-any-value-system.md](.knowledge/designs/0002-any-value-system.md)
