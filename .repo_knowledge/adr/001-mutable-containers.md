# ADR-001: Introduce Mutable Containers (List, Dict)

- **Status**: Accepted
- **Date**: 2026-02-19
- **Commits**: `9513c2f` (List), `c1af3b3` (Dict), `5a6b211` (refactor)

## Context

TVM-FFI originally provided only immutable (copy-on-write) containers:
`Array<T>` and `Map<K,V>`. While COW semantics are safe and efficient for
read-heavy workloads, they are unsuitable for use cases requiring in-place
mutation where multiple handles should observe changes (e.g., building up
state progressively, accumulating results).

## Decision

Introduce two new mutable containers alongside the existing immutable ones:

| | Immutable (COW) | Mutable (Shared-ref) |
|---|---|---|
| **Sequence** | `Array<T>` | `List<T>` |
| **Mapping** | `Map<K,V>` | `Dict<K,V>` |

Key design choices:
1. **Shared base classes**: `SeqBaseObj` (Array + List) and `MapBaseObj`
   (Map + Dict) to consolidate iteration and internal data structure logic.
2. **New ABI type codes**: `kTVMFFIList = 75`, `kTVMFFIDict = 76`.
3. **Cycle-aware infrastructure**: Serialization, structural hash/equal,
   JSON writer, and repr all handle reference cycles in mutable containers.
4. **Python protocols**: `List` implements `MutableSequence`, `Dict`
   implements `MutableMapping`.

## Consequences

- **Positive**: Natural Python-like semantics for mutable state; shared
  base classes reduce code duplication; full integration across all subsystems.
- **Negative**: New ABI type codes are permanent commitments; cycle detection
  adds complexity to serialization/traversal; `InplaceArrayBase` CRTP was
  removed during refactoring.
- **Risks**: The ABI type indices (`75`, `76`) must remain stable across all
  future versions.

## Alternatives Considered

1. **Mutation via COW containers**: Rejected — COW semantics mean mutations
   create new copies, which is confusing when multiple handles exist.
2. **Python-only wrappers**: Rejected — would not work cross-language and
   would bypass the C++ container infrastructure.
