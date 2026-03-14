---
scope:
  - "0009-structural-equal-hash"
  - "0011-extra-api-tier"
---
# Frozen StructuralKey Wrapper with Cached Structural Hash

**TL;DR**: `StructuralKey` wraps an arbitrary value together with its precomputed structural hash, enabling efficient use of structurally compared objects as dictionary/map keys without recomputing the expensive deep hash on each lookup.

## Context

Structural hashing (`StructuralHash::Hash`) is a deep, reflection-driven operation that recursively walks all fields of an object graph. For compiler IR objects, this can be expensive (hundreds of fields, nested containers, DAG structures). Using structurally hashed values as dictionary or map keys (e.g., for memoization, common subexpression elimination, or deduplication) requires computing this hash on every lookup, creating a performance bottleneck.

The existing `AnyHash`/`AnyEqual` system (used by `Map`) operates on pointer identity for objects, which is fast but does not support content-based lookup. The structural equal/hash system provides the correct semantics but is too expensive for hot-path use without caching.

Usecases:
- **Memoization tables** in compiler passes: cache the result of transforming an IR subtree, keyed by the subtree's structural identity.
- **Deduplication**: detect structurally identical subexpressions in a DAG-structured IR.
- **Cross-language dict keys**: Python `dict` and `Map` can use `StructuralKey` as keys with structural equality semantics.

Design Decisions:
- **Frozen wrapper pattern**: `StructuralKeyObj` stores `key` (the wrapped value) and `hash_i64` (the cached structural hash). Both fields are read-only (`def_ro`). The hash is computed exactly once in the constructor and never recomputed. This amortizes the expensive structural hash over all subsequent lookups.
- **Three-stage equality**: `StructuralKey::operator==` checks (1) pointer identity (`same_as`) for the fast path, (2) cached hash comparison (`hash_i64 != other->hash_i64`) for cheap rejection, (3) full `StructuralEqual::Equal` only on hash collision. This ordering minimizes the cost of the common "not equal" case.
- **`std::hash` specialization**: A `std::hash<StructuralKey>` specialization is provided, enabling direct use in `std::unordered_map`/`std::unordered_set` in C++.
- **Python hashability**: The Python `StructuralKey` class implements `__hash__` (returning `hash_i64 & 0xFFFFFFFFFFFFFFFF`) and `__eq__` (delegating to `ffi.StructuralKeyEqual`), making it usable as a Python `dict` key.
- **Type key `"ffi.StructuralKey"`**: Registered as a standard FFI object with reflection metadata, so it participates in serialization, repr, and cross-language interop.

**Alternatives considered**:

1. **Recompute structural hash on every lookup**: Correct but O(N) per lookup where N is the number of fields in the object graph. The caching wrapper makes lookups O(1) after the initial O(N) construction.
2. **Hash-consing (intern all structurally identical objects)**: Would make pointer equality equivalent to structural equality, eliminating the need for a wrapper. But hash-consing requires global interning tables, thread-safe deduplication, and prevents mutation of interned objects. The wrapper approach is simpler, local, and does not constrain the object lifecycle.
3. **Register custom `__any_hash__`/`__any_equal__` on every IR type**: Would enable `Map` to use structural equality for those types directly. But this couples every IR type to the structural hash system, adds overhead to all `Map` operations involving those types, and does not compose (a `Map` cannot mix structurally-keyed and identity-keyed types). `StructuralKey` makes the intent explicit at the call site.
4. **Mutable cached hash field on the object itself**: Adding a `cached_hash_` field to every IR object would avoid the wrapper but wastes memory for objects that are never used as keys, and introduces a mutable field on otherwise immutable objects (breaking invariants for `kTVMFFISEqHashKindConstTreeNode` types).

**Consequences**:
- `StructuralKey` adds one new object type to the type registry (`"ffi.StructuralKey"`).
- The wrapper adds 16 bytes of overhead per key (one `Any` field + one `int64_t`), plus the `Object` header (24 bytes). This is acceptable because the number of keys in memoization tables is typically small relative to the total IR size.
- Two `StructuralKey` objects wrapping the same value at different pointers will have equal `hash_i64` values and compare as equal via `operator==`, but will be distinct objects in a `Map` (which uses `AnyEqual` pointer identity). Users must use Python `dict` with `StructuralKey` keys, or register custom `__any_hash__`/`__any_equal__` on `StructuralKeyObj` for `Map` support.

**Rollback**: Remove `include/tvm/ffi/extra/structural_key.h`, the reflection registration in `reflection_extra.cc`, `python/tvm_ffi/structural.py`, and the `StructuralKey` Python class. No other components depend on `StructuralKey`.

## Implementation Notes

- `StructuralKeyObj` is declared in `include/tvm/ffi/extra/structural_key.h` (header-only) with `TVM_FFI_DECLARE_OBJECT_INFO_FINAL`.
- Reflection registration is in `src/ffi/extra/reflection_extra.cc`: `ObjectDef<StructuralKeyObj>().def_ro("key", ...).def_ro("hash_i64", ...).def(init<Any>())`. A `StructuralKeyEqual` global function is also registered.
- Python module `tvm_ffi/structural.py` exports `StructuralKey`, `structural_equal`, `structural_hash`, and `get_first_structural_mismatch`.
- The Python `structural_hash` function masks the result with `& 0xFFFFFFFFFFFFFFFF` to convert the signed `int64_t` from C++ to an unsigned Python integer, matching Python's expectation for `__hash__` return values.
- Evidence: `.knowledge/commits/2026-02-16-6adc8df7d2180ea14e463d3beeaa3d7eecb6f897.md` + `6adc8df`

## Related Design Docs

- [`.knowledge/designs/0009-structural-equal-hash.md`](../designs/0009-structural-equal-hash.md) -- Structural equal/hash system that StructuralKey wraps
- [`.knowledge/designs/0011-extra-api-tier.md`](../designs/0011-extra-api-tier.md) -- Extra tier where structural_key.h lives
- [`.knowledge/ADRs/0060-custom-any-hash-equal.md`](0060-custom-any-hash-equal.md) -- Custom AnyHash/AnyEqual (distinct value-level system)
