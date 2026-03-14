---
scope:
  - "0009-structural-equal-hash"
  - "0001-c-abi"
---
# Remove kTVMFFISEqHashKindCustomTreeNode Enum Value

**TL;DR**: The `kTVMFFISEqHashKindCustomTreeNode = 6` enum value was removed from the C ABI. Custom structural equal/hash is now detected at runtime via `TypeAttrColumn` lookup, decoupling the "has custom equal/hash" property from a static enum declaration.

## Context

Commit `2ec11f5` introduced `kTVMFFISEqHashKindCustomTreeNode` as a dedicated dispatch path for types with custom `__s_equal__`/`__s_hash__` functions. This required types to both:
1. Set `_type_s_eq_hash_kind = kTVMFFISEqHashKindCustomTreeNode` in their class declaration.
2. Register `__s_equal__`/`__s_hash__` via `TypeAttrDef<T>`.

This dual requirement was redundant -- the TypeAttrColumn entry already indicates the presence of custom functions.

## Alternatives Considered

1. **Keep the enum value for explicit opt-in**: Provides compile-time documentation of intent (a type declaring `kTVMFFISEqHashKindCustomTreeNode` is clearly signaling custom behavior). But redundant with the runtime check, and prevents types from optionally having custom behavior without a separate enum value. Also prevents combining custom dispatch with other enum semantics (e.g., a DAGNode that also has custom comparison).

2. **Runtime detection via TypeAttrColumn** (chosen): Check `TypeAttrColumn("__s_equal__")[type_index] != nullptr` at the dispatch site, regardless of the `_type_s_eq_hash_kind` value. Custom behavior becomes purely additive -- register the attribute and it works. Any `_type_s_eq_hash_kind` value (TreeNode, DAGNode, etc.) can have custom override.

## Decision

Remove `kTVMFFISEqHashKindCustomTreeNode = 6` from the C ABI. Custom structural equal/hash is detected by checking the TypeAttrColumn at runtime. Types with custom behavior use any appropriate base `_type_s_eq_hash_kind` (typically `kTVMFFISEqHashKindTreeNode`) and register `__s_equal__`/`__s_hash__` attributes.

## Trade-offs

- **Pro**: Simpler dispatch logic (one fewer enum case).
- **Pro**: Custom equal/hash is purely additive (no class declaration change needed).
- **Pro**: Custom behavior can overlay any base `_type_s_eq_hash_kind` semantics.
- **Con**: Loses compile-time signal that a type has custom comparison. This is now a runtime-only property.
- **Con**: ABI-breaking change (enum value 6 removed). Downstream code referencing it fails to compile.

## Consequences

- The `TVMFFISEqHashKind` enum has 6 values (0-5). Value 6 is no longer defined.
- `StructEqualHandler` and `StructuralHashHandler` check TypeAttrColumn before the main dispatch switch.
- Types with `kTVMFFISEqHashKindUnsupported` or missing metadata now throw `TypeError` instead of silently falling back to pointer comparison.
- The `ICHECK` assertion that custom attributes must be registered is removed -- the null check serves as the dispatch condition.

## Implementation Notes

- The same commit (`59a837e`) also added NaN canonicalization and changed the custom hash callback signature to thread `init_hash`.
- Evidence: commits `2ec11f5` (introduction), `59a837e` (removal).

## Related Design Docs

- [`.knowledge/designs/0009-structural-equal-hash.md`](../designs/0009-structural-equal-hash.md) -- Structural equal/hash system
- [`.knowledge/designs/0010-type-attr-columns.md`](../designs/0010-type-attr-columns.md) -- TypeAttr column lookup
