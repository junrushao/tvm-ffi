---
scope:
  - "0010-structural-equal-hash"
  - "0009-reflection"
---
# Custom Structural Equal/Hash via TypeAttrColumn Instead of Dedicated Enum

**TL;DR**: The decision to remove `kTVMFFISEqHashKindCustomTreeNode` (enum value 6) and instead discover custom `__s_equal__`/`__s_hash__` implementations via `TypeAttrColumn` null-check at runtime, unifying custom dispatch with the existing reflection attribute system.

## Context
- The structural equality/hash system initially used `TVMFFISEqHashKind` to control dispatch per type. A dedicated value `kTVMFFISEqHashKindCustomTreeNode=6` was added for types needing user-defined comparison logic.
- This created a hard coupling: types wanting custom behavior had to set a specific enum value AND register type attributes, with the enum value being the sole signal for custom dispatch.
- The `TypeAttrColumn` system (introduced for extensible per-type attributes) already provided a natural discovery mechanism: if a column entry is non-null for a given type index, the attribute is registered.
- Having a dedicated enum value meant the C ABI had to grow for every new dispatch strategy.

Usecases:
- IR node types that need to skip certain fields during comparison (e.g., debug info, source locations).
- Types with partial ordering or non-trivial free-variable scoping where automatic field traversal is insufficient.
- Cross-language extensibility: Python/Rust code registering custom comparison functions via the type attribute system.

Design Decisions:
- **Remove `kTVMFFISEqHashKindCustomTreeNode`**: Types use `kTVMFFISEqHashKindTreeNode` (value 1) and optionally register `__s_equal__`/`__s_hash__` via `TypeAttrDef`.
- **Discovery via null-check**: The structural equal/hash handler checks `TypeAttrColumn("__s_equal__")[type_index]` at runtime. If non-null, use the custom function. If null, use automatic field traversal. This is O(1) with no additional enum values needed.
- **Attribute names are conventions**: `__s_equal__` and `__s_hash__` are string-named conventions, not hardcoded symbols. Any type can register them independently.
- **`__s_hash__` callback signature change**: The callback now takes `(AnyView val, uint64_t init_hash, bool def_region) -> uint64_t`, incorporating `StableHashCombine` internally rather than requiring callers to combine. This simplifies custom implementations.

## Implementation Notes
- `EnsureTypeAttrColumn("__s_equal__")` and `EnsureTypeAttrColumn("__s_hash__")` are called at static init to pre-create the columns, ensuring the `TypeAttrColumn` accessor never throws "column not found".
- The handler uses `static` local `TypeAttrColumn` instances for lookup, cached after first construction. Column lookup is a single array index by `type_index`.
- FreeVar mapping and DAGNode post-processing are applied after the custom function returns, ensuring custom handlers coexist with graph-level semantics.

## Related Design Docs
- [0010-structural-equal-hash.md](../designs/0010-structural-equal-hash.md)
- [0009-reflection.md](../designs/0009-reflection.md)
