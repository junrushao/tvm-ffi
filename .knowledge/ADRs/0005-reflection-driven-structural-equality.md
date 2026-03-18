---
scope:
  - "0009-structural-equal-hash.md"
  - "0008-reflection.md"
---
# ADR: Reflection-Driven Structural Equality and Hashing

**TL;DR**: Decision to use the reflection metadata system (field info, type attributes, per-type SEqHash kind) for structural equality and hashing, replacing the legacy per-type virtual `SEqualReduce`/`SHashReduce` methods with a generic, declarative approach.

## Context
- Legacy TVM required every object type to implement `SEqualReduce(equal, map_free_vars)` and `SHashReduce(hash_reduce)` virtual methods. This produced hundreds of lines of repetitive boilerplate across the IR type hierarchy.
- The existing reflection system already registers every field of every reflected type with getters, byte offsets, and type information. Structural comparison by iterating registered fields is a natural extension.
- Different types need different comparison semantics: tree nodes (field-by-field), free variables (identity mapping within definition scopes), DAG nodes (sharing-aware), singletons (pointer equality). A single virtual method cannot cleanly express these distinctions.
- Access path reporting (pinpointing the exact field/index/key of a mismatch) requires the comparison framework to be aware of field names, which reflection already provides.

Usecases:
- IR equality checking: `StructuralEqual::Equal(expr1, expr2)` compares two IR expressions field-by-field using registered reflection, with zero handwritten code per type.
- Mismatch diagnosis: `StructuralEqual::GetFirstMismatch(a, b)` returns `AccessPathPair` identifying exactly where two values diverge (e.g., `["body", 0, "value"]`).
- Custom comparison for special types: Types that need non-trivial equality (e.g., functions with variable binding) register `__s_equal__`/`__s_hash__` via `TypeAttrColumn`, receiving a callback for recursive comparison.
- Field exclusion: Fields tagged with `SEqHashIgnore` (e.g., debug names, source locations) are automatically skipped during comparison.

Design Decisions:
- **Use reflection metadata for generic field-by-field comparison**. The `ForEachFieldInfo` traversal with `FieldGetter` provides all information needed to compare any reflected type without type-specific code. The per-type `TVMFFISEqHashKind` enum selects the comparison strategy.
- **Custom dispatch via TypeAttrColumn, not enum values**. Initially a `kTVMFFISEqHashKindCustomTreeNode` enum value was added (commit 2ec11f5), but this was replaced (commit 59a837e) by runtime lookup of `TypeAttrColumn("__s_equal__")`. This unifies custom dispatch with the general type attribute system and avoids enum proliferation.
- **Field flags for declarative control**. `SEqHashIgnore` and `SEqHashDef` flags on `TVMFFIFieldInfo` let type authors control comparison behavior declaratively at registration time, without writing comparison code.
- **TypeError on missing metadata**. Types that lack reflection metadata or have `kTVMFFISEqHashKindUnsupported` throw `TypeError` instead of silently falling back to pointer equality. This prevents subtle bugs where unreflected types appear equal by accident.

## Implementation Notes
- `StructuralEqual` and `StructuralHash` live in the `extra/` module (`tvm::ffi` namespace), compiled when `TVM_FFI_USE_EXTRA_CXX_API=ON`.
- The handler classes (`StructEqualHandler`, `StructuralHashHandler`) maintain internal state: visited DAG node pairs, free variable mappings, and access path stack for mismatch reporting.
- NaN values are canonicalized: all NaN bit patterns compare equal and hash to `quiet_NaN()`.
- The `__s_hash__` callback signature is `(val, init_hash, def_region) -> int64` at the FFI boundary (changed from `uint64` in 86bbddfd to avoid the uint64_t overflow guard in TypeTraits). Bit patterns are preserved via explicit bitcast; Python callers may see negative values.

## Related Design Docs
- [0009-structural-equal-hash.md](../designs/0009-structural-equal-hash.md) -- Full design of the structural equality/hash system
- [0008-reflection.md](../designs/0008-reflection.md) -- ObjectDef, ForEachFieldInfo, TypeAttrDef/TypeAttrColumn
- [0001-c-abi.md](../designs/0001-c-abi.md) -- TVMFFISEqHashKind enum, TVMFFITypeMetadata, field flags
