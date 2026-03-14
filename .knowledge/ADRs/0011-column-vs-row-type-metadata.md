---
scope:
  - "0006-reflection"
  - "0001-c-abi"
  - "0010-type-attr-columns"
---
# Column-Oriented vs Row-Oriented Type Metadata

**TL;DR**: Extensible per-type attributes use column-oriented storage (`TypeAttrColumn`) alongside the existing row-oriented `TVMFFITypeMetadata` struct. Each named attribute occupies its own `std::vector<Any>` indexed by `type_index` for O(1) lookup, enabling unbounded extensibility without ABI changes.

## Context

The system needs to store per-type metadata. Fixed metadata fields (creator, total_size, doc, structural_eq_hash_kind) work well as a struct per type (`TVMFFITypeMetadata`), but extensible attributes (custom equality functions, serialization hints, code generation metadata) need a different model. Each addition to the fixed struct is an ABI-breaking change requiring all downstream bindings to recompile.

The immediate motivating use case was registering `__s_equal__` and `__s_hash__` custom functions per type for the structural equality/hash system, but the mechanism is designed to be general-purpose.

## Alternatives Considered

1. **Keep adding fields to TVMFFITypeMetadata**: Simple, all metadata in one struct. But breaks ABI for each new field. The `total_size` narrowing (int64_t to int32_t) in the same commit group illustrates the pressure on the fixed struct layout.

2. **Per-type `Map<String, Any>`**: Fully dynamic, one map per type. But O(log n) lookup per access, which is too slow for hot paths like structural equality dispatch that check every object encountered during comparison.

3. **Column arrays indexed by type_index** (chosen): Each named attribute has its own `std::vector<Any>`. Lookup is `column_data[type_index]` -- O(1). Sparse (unregistered types return null). ABI-stable (adding new attributes does not change any C struct).

## Decision

Use column-oriented storage for extensible per-type attributes, exposed through two new C API functions (`TVMFFITypeRegisterAttr`, `TVMFFIGetTypeAttrColumn`) and the `TVMFFITypeAttrColumn` struct. Keep `TVMFFITypeMetadata` for the fixed, frequently-accessed fields (creator, total_size, structural_eq_hash_kind).

## Trade-offs

- **Pro**: O(1) per-type lookup via array indexing.
- **Pro**: ABI-stable -- new attributes are added without changing any C struct.
- **Pro**: Sparse storage -- unregistered types do not consume memory (vector is only as large as the highest registered type_index).
- **Pro**: Cache-friendly when iterating all types for a given attribute (sequential memory access).
- **Con**: Wastes some space when columns are sparse (vectors sized to max registered type_index).
- **Con**: Column `data` pointer may change on registration (vector reallocation), though this is safe because registration is single-threaded during static init.
- **Con**: Two lookup mechanisms (fixed struct for core metadata, column for extensible attributes) add conceptual complexity.

## Consequences

- Structural equal/hash custom functions (`__s_equal__`, `__s_hash__`) are registered and looked up via TypeAttrColumn.
- Future per-type metadata (serialization hints, code generation metadata) can be added without any ABI changes.
- The `TVMFFITypeMetadata` struct remains small and stable.
- Column name-to-index mapping uses `Map<String, int64_t>` in TypeTable, consistent with the `type_key2index_` pattern.

## Implementation Notes

- `TypeAttrColumnData` struct in `src/ffi/object.cc` extends `TVMFFITypeAttrColumn` and owns `std::vector<Any> data_`.
- `TVMFFITypeRegisterAttr` with `type_index == kTVMFFINone` creates the column without inserting a value (`EnsureTypeAttrColumn` mechanism).
- A bug in `TypeTable::RegisterTypeAttr` where `column_index` was not assigned for existing columns was fixed in `2ec11f5`.
- Evidence: commits `162d600`, `2ec11f5`, `59a837e`.

## Related Design Docs

- [`.knowledge/designs/0010-type-attr-columns.md`](../designs/0010-type-attr-columns.md) -- Full TypeAttr design
- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- Reflection system overview
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI structs
