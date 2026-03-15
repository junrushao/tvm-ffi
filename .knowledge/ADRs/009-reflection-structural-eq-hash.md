---
scope:
  - ".knowledge/designs/0010-structural-equal-hash.md"
  - ".knowledge/designs/reflection.md"
---
# ADR-009: Reflection-Based Structural Equality and Hash

**TL;DR**:
- Structural equality and hashing for IR nodes are implemented by automatically walking reflection-registered fields, replacing the legacy per-type virtual method pattern (`SEqualReduce`/`SHashReduce`).
- Types opt in via a `_type_s_eq_hash_kind` enum and optionally override the default with custom `__s_equal__`/`__s_hash__` TypeAttr callbacks.

## Context

IR compilers (e.g., TVM Relax) need to compare and deduplicate AST nodes structurally. The legacy approach required every type to:
1. Declare `static constexpr bool _type_has_method_sequal_reduce = true` and `_type_has_method_shash_reduce = true`
2. Implement `SEqualReduce(other, equal_fn)` and `SHashReduce(hash_fn)` methods

This was error-prone (forgetting a field silently produces wrong comparisons), verbose (every type reimplements the same field-walking logic), and fragile (adding a new field requires updating comparison methods).

Meanwhile, the reflection system already knows every field's name, type, and offset via `ObjectDef<T>` registration. Structural comparison can be derived automatically.

Usecases:
- Comparing two IR functions for semantic equivalence (ignoring comments, mapping free variables)
- Hashing IR nodes for memoization and deduplication in compiler passes
- Debugging structural mismatches with precise field-path diagnostics

Design Decisions:
- Structural equality and hash are derived from reflection field metadata by default, with a per-type enum (`TVMFFISEqHashKind`) controlling the semantic mode (tree, DAG, free-var, etc.).
- Custom `__s_equal__`/`__s_hash__` callbacks via TypeAttr provide escape hatches when the default field walk is insufficient.
- The dispatch is presence-based: if `__s_equal__` exists in the TypeAttrColumn for a type, it takes priority regardless of the enum kind.
- FreeVar/DAG bookkeeping runs unconditionally after content comparison, whether field-based or custom.

## Alternatives

### Per-type virtual methods (SEqualReduce/SHashReduce)
- Description: Each type implements `SEqualReduce` and `SHashReduce` methods that manually compare/hash their fields. Detected via compile-time boolean flags on the Object class.
- Pros: Full control per type; no reflection dependency; familiar OOP pattern
- Cons: Every type must manually implement; easy to forget a field (silent correctness bug); no automatic coverage for new fields; duplication of FreeVar/DAG bookkeeping across types; compile-time boolean flags (`_type_has_method_sequal_reduce`) are fragile and were already being phased out
- Why rejected: The reflection system already captures all fields. Forcing manual reimplementation is both redundant and error-prone. The FreeVar/DAG bookkeeping was being duplicated in every custom implementation, violating DRY.

### Visitor-based approach (VisitAttrs + comparison)
- Description: Reuse the `VisitAttrs` visitor pattern (already present in legacy TVM) to both enumerate fields and compare them.
- Pros: Single visitor method handles reflection and comparison; existing infrastructure
- Cons: `VisitAttrs` was already removed (commit da47623) because it conflated field enumeration with field mutation; it cannot express per-field comparison semantics (ignore, def-region); adding comparison-specific flags to a general visitor clutters its API
- Why rejected: `VisitAttrs` conflates too many concerns. The reflection system with `TVMFFIFieldInfo::flags` provides a cleaner separation of concerns.

### Dedicated enum kind for custom dispatch (kTVMFFISEqHashKindCustomTreeNode = 6)
- Description: Add a separate enum value to indicate "use custom callbacks" (implemented in v2, removed in v3).
- Pros: Explicit: the enum value signals that reflection-based field walk should be skipped
- Cons: Inflexible -- a type must choose between reflection-based OR custom, cannot have both; a type with custom callbacks still needs fields registered for serialization, creating a redundant enum value; removed in commit 59a837e in favor of presence-based dispatch
- Why rejected: Presence-based dispatch (checking `TypeAttrColumn["__s_equal__"][type_index] != nullptr`) is simpler and more flexible. Any type can have both reflection fields and custom callbacks without a special enum value.

## Implementation Notes
- Types opt in by setting `static constexpr TVMFFISEqHashKind _type_s_eq_hash_kind = kTVMFFISEqHashKindTreeNode` (or DAGNode, FreeVar, etc.). This is read by `ObjectDef::RegisterExtraInfo` and stored in `TVMFFITypeMetadata.structural_eq_hash_kind`.
- Per-field flags `AttachFieldFlag::SEqHashIgnore()` and `AttachFieldFlag::SEqHashDef()` control skip/def-region semantics.
- Custom callbacks are registered via `TypeAttrDef<T>().def("__s_equal__", &T::SEqual).def("__s_hash__", &T::SHash)`.
- The `__s_hash__` callback takes `(uint64_t init_hash, TypedFunction<uint64_t(AnyView, uint64_t, bool)> hash)` -- an accumulator-threaded signature where the callback returns the combined hash.
- `AccessPath`/`AccessStep` provide first-mismatch diagnostics via `StructuralEqual::GetFirstMismatch`.
- NaN float values are canonicalized: all NaN representations compare as equal and hash to the same bucket.
- The legacy `_type_has_method_sequal_reduce` and `_type_has_method_shash_reduce` boolean fields were removed from `Object` in commit e52aed5, completing the migration.

## Related Design Docs
- `.knowledge/designs/0010-structural-equal-hash.md` -- Full design doc for the structural equal/hash system
- `.knowledge/designs/reflection.md` -- TypeAttr system, AttachFieldFlag, ForEachFieldInfo
- `.knowledge/designs/c-abi.md` -- TVMFFISEqHashKind enum, TVMFFITypeMetadata struct
