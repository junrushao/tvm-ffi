---
scope:
  - "0006-reflection"
  - "0009-structural-equal-hash"
---
# Refactor AccessPath from Flat Array to Parent-Pointing Tree

**TL;DR**: `AccessPath` was changed from a flat type alias `Array<AccessStep>` to a first-class object (`AccessPathObj`) with a parent-pointing linked-list structure (`parent`, `step`, `depth`). This enables compact memory sharing when many paths share a common prefix, as is common during structural comparison.

## Context

During structural comparison (`StructuralEqual::GetFirstMismatch`), the system tracks the access path to the first divergence point. The access path describes navigation from root to a specific field: e.g., `root.body[0].value`. When comparing container elements (e.g., iterating over array items), many sibling paths share a common prefix (e.g., `root.body[0]`, `root.body[1]`, `root.body[2]`).

With the previous design (`AccessPath = Array<AccessStep>`), each sibling path was a full independent array. For `n` sibling paths of depth `d`, this requires `O(n * d)` total allocations.

With the parent-pointing tree, each sibling allocates only one new `AccessPathObj` node pointing to the shared parent. Total allocation for `n` siblings: `O(d + n)`.

Constraints:
- `AccessPath` must remain serializable and usable across FFI boundaries (it is an `Object` subclass).
- The flat `Array<AccessStep>` representation must still be available for display and serialization (via `ToSteps()`).
- The new `AccessPathObj` type key changed from `"tvm.ffi.reflection.AccessStep"` to `"ffi.reflection.AccessStep"` (aligning with the `ffi.*` namespace convention).

Usecases:
- Structural comparison mismatch diagnostics: `GetFirstMismatch` constructs paths incrementally during recursive traversal. The tree structure matches the recursive call pattern naturally -- each level extends the parent.
- AccessPath comparison: `PathEqual` and `IsPrefixOf` can use pointer-equality fast paths on shared parent nodes, short-circuiting deep comparisons.

Design Decisions:
- **Parent-pointing tree** with `Optional<ObjectRef> parent`, `Optional<AccessStep> step`, `int32_t depth`.
- **Builder API**: `AccessPath::Root()`, `->Extend(step)`, `->Attr(name)`, `->ArrayItem(i)`, `->MapItem(key)` and "Missing" variants for asymmetric structures.
- **Conversion**: `ToSteps()` materializes the flat `Array<AccessStep>` representation by reverse-traversing the parent chain. `FromSteps(Array<AccessStep>)` reconstructs from a flat array.
- **Rename**: `AccessKind::kObjectField` became `kAttr`, `AccessStep::ObjectField` became `AccessStep::Attr`, aligning with Python attribute access terminology. New `kAttrMissing` variant added.
- **Reflection registration moved to extra tier**: `AccessPathObj`/`AccessStepObj` reflection metadata registration moved from core `access_path.cc` to `src/ffi/extra/reflection_extra.cc`. The header remains core, but reflection and `MakeObjectFromPackedArgs` require `TVM_FFI_USE_EXTRA_CXX_API=ON`.

Alternatives considered:

1. **Keep flat `Array<AccessStep>`**: Simpler, no linked-list traversal. But `O(n * d)` memory for `n` sibling paths of depth `d`.
2. **Trie structure**: Better deduplication for arbitrary path sets. But more complex, harder to integrate with the Object system, and overkill for the structural comparison use case where paths are constructed incrementally.
3. **Arena-allocated path segments**: Would avoid per-node Object overhead. But incompatible with the FFI Object system and cross-language passing requirements.

Consequences:
- **Breaking API change**: Callers constructing `AccessPath` as `Array<AccessStep>` must use `AccessPath::Root()` / `->Extend()` or `AccessPath::FromSteps()`.
- **Rename breakage**: `kObjectField` -> `kAttr`, `ObjectField(name)` -> `Attr(name)`.
- **Enum renumbering**: `AccessKind` values shifted (`kArrayItemMissing` 3->4, `kMapItemMissing` 4->5) to insert `kAttrMissing = 3`. Binary-incompatible for serialized `AccessStep` values.
- **Extra-tier dependency**: `AccessPath`/`AccessStep` reflection and `MakeObjectFromPackedArgs` require extra tier. When `TVM_FFI_USE_EXTRA_CXX_API=OFF`, the types exist in the type table but field/method metadata is not registered.

## Implementation Notes

- `AccessPathObj` uses `Optional<ObjectRef>` for `parent` (not `Optional<AccessPath>`) to avoid circular header dependency. `GetParent()` performs the downcast.
- `depth` is always `parent->depth + 1` for non-root paths, enabling O(1) prefix-length comparison.
- `PathEqual` walks the parent chain with pointer-equality fast paths at each level.
- `IsPrefixOf` first truncates the longer path to the shorter path's depth using the parent chain, then delegates to `PathEqual`.
- Evidence: commit `f4ede98` (PR #18189).

## Related Design Docs

- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- Reflection system where AccessPath is defined
- [`.knowledge/designs/0009-structural-equal-hash.md`](../designs/0009-structural-equal-hash.md) -- Primary consumer for mismatch diagnostics
- [`.knowledge/designs/0011-extra-api-tier.md`](../designs/0011-extra-api-tier.md) -- Extra tier where reflection registration moved
