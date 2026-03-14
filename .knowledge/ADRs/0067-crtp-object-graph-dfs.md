---
scope:
  - "0027-dataclass-operations"
  - "0011-extra-api-tier"
---
# CRTP-Based Iterative DFS Engine for Object Graph Operations

**TL;DR**: All four object-graph operations (deep copy, repr, recursive hash, recursive compare) share a single `ObjectGraphDFS<Derived, FrameT, ResultT>` CRTP base class that implements iterative DFS with an explicit stack. This eliminates duplicated graph-walking code and provides zero-cost compile-time dispatch.

## Context

Before commit `6b39efb` (#482), `deep_copy.cc` and `repr_print.cc` each contained their own iterative DFS implementation with cycle/DAG detection. Adding `RecursiveHash` and `RecursiveCompare` would have required two more copies. The four operations share a common traversal pattern:

1. Check if the value is immediate (POD, memoized, in-progress)
2. Push a frame with enumerated children (containers via type dispatch, objects via reflection)
3. Process children iteratively
4. Finalize the frame, propagate result to parent

The operations differ only in:
- Frame payload (copy target, string buffer, hash accumulator, comparison state)
- Result type flowing up the stack
- Per-child and per-frame logic (accumulation, early termination)
- Which fields to skip (ReprOff, CompareOff, HashOff)

Usecases:
- Deep copy of arbitrary object graphs with cyclic/DAG structures
- Human-readable repr of any FFI value
- Deterministic recursive hashing for content-addressed storage
- Structural equality and ordering comparison for dataclass objects

Design Decisions:
- **CRTP over virtual dispatch**: The DFS `RunLoop()` calls customization points (e.g., `TryVisitChild`, `FeedChild`) on every child of every frame. For large graphs, this is millions of calls. CRTP enables the compiler to inline these, making the dispatch zero-cost. Virtual dispatch would add function pointer indirection overhead on every call.
- **Iterative over recursive**: An iterative explicit stack avoids C++ stack overflow on deep graphs. `kMaxTraversalStackDepth = 1 << 20` provides approximately 1 million frames, far exceeding typical system stack limits (1-8MB / sizeof(frame)). Iterative also makes custom hook re-entrancy straightforward: save/swap the stack, run the sub-traversal, swap back.
- **Eight customization points**: `GetFieldSkipMask`, `OnEnter`, `OnFrameInit`, `TryVisitChild`, `PushChildFrame`, `FeedChild`, `FinalizeFrame`, `OnFrameComplete`, `OnTerminate`. These cover the full lifecycle (enter, init, per-child, finalize, complete) with enough granularity for all four operations.
- **CompareFrame uses pair-based design**: The comparer's frame stores `vector<pair<Any, Any>>` (LHS/RHS children) instead of the single-value `vector<Any>` in `FrameBase`. This is because comparison operates on two values simultaneously, requiring paired children. The comparer does not inherit `FrameBase`; it defines its own `CompareFrame` struct.
- **Field skip via bitmask**: Each operation returns a `uint32_t` mask from `GetFieldSkipMask()`. `EnumerateChildren` ANDs each field's flags against this mask; if nonzero, the field is skipped. This is a single integer test per field, adding negligible overhead.

## Implementation Notes

- `ObjectGraphDFS` is defined in an anonymous namespace inside `dataclass.cc`. It is not a public API; the CRTP pattern is an implementation detail.
- `FrameBase` is shared by `ObjectDeepCopier`, `ReprPrinter`, and `RecursiveHasher` (which all operate on single values). `RecursiveComparer` uses its own `CompareFrame` (pair-based) and overrides `PushFrame` behavior via `PushPairFrame`.
- `EnumerateChildren` handles Array, List, Map, Dict via type-index switch, and falls through to reflected-object field iteration for all other types.
- Custom hook callbacks (`CreateFnRepr`, `CreateFnHash`, `CreateFnEq`, `CreateFnCompare`) capture `this` and save/restore `stack_` via `std::vector::swap` for re-entrant sub-traversals.
- Evidence: `.knowledge/commits/2026-02-27-6b39efbf381e48a8a42ab3779bc2adf587458fb3.md` + `6b39efb`

## Related Design Docs

- [`.knowledge/designs/0027-dataclass-operations.md`](../designs/0027-dataclass-operations.md) -- Full design of the four operations built on this engine
- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- Reflection metadata consumed by `EnumerateChildren`
- [`.knowledge/designs/0011-extra-api-tier.md`](../designs/0011-extra-api-tier.md) -- Extra tier where `dataclass.cc` lives
