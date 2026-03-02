---
adr: "0020"
title: "Object Declaration Macro Consolidation (6->4 Declare, 4->2 Ref)"
status: "accepted"
date: "2025-09-08"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "All C++ FFI users"
tags:
  - "architecture"
  - "object-system"
  - "macro"
source_commits:
  - "4ffbc88b60f659a74619035e699986792c071e8d"
source_ledgers:
  - ".memory/commits/2025-09-08-4ffbc88b60f659a74619035e699986792c071e8d.md"
---

# ADR-0020: Object Declaration Macro Consolidation (6->4 Declare, 4->2 Ref)

## TL;DR
- Object declaration macros consolidated from 6 variants to 4 (`TVM_FFI_DECLARE_OBJECT_INFO`, `TVM_FFI_DECLARE_OBJECT_INFO_FINAL`, `TVM_FFI_DECLARE_OBJECT_INFO_STATIC`, `TVM_FFI_DECLARE_OBJECT_INFO_PREDEFINED_TYPE_KEY`).
- ObjectRef method macros consolidated from 4 variants to 2 (`TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE`, `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE`).
- Type key is now embedded in the declaration macro, and mutability is auto-detected via `_type_mutable`.

## Status
Accepted

## Context
The Object system used 6 declaration macros (`TVM_FFI_DECLARE_BASE_OBJECT_INFO`, `TVM_FFI_DECLARE_FINAL_OBJECT_INFO`, `TVM_FFI_DECLARE_STATIC_OBJECT_INFO`, and predefined variants) and 4 ref method macros (`TVM_FFI_DEFINE_OBJECT_REF_METHODS`, `TVM_FFI_DEFINE_MUTABLE_OBJECT_REF_METHODS`, `TVM_FFI_DEFINE_NOTNULLABLE_OBJECT_REF_METHODS`, `TVM_FFI_DEFINE_MUTABLE_NOTNULLABLE_OBJECT_REF_METHODS`). The mutable/immutable distinction in ref macros required separate macros despite differing only in whether `operator->` returns `const T*` or `T*`. The type key required a separate `static constexpr const char* _type_key = "..."` line before the macro call.

## Decision Drivers
- **Reduced macro proliferation**: 10 macros for a single pattern is excessive and error-prone.
- **Consistency**: The type key should be part of the declaration, not a separate line.
- **Auto-detection**: Mutability should be derived from the `_type_mutable` field, not from choosing a different macro.
- **Name clarity**: Macro names should follow a consistent suffix pattern.

## Decision
### Declaration macros (6 -> 4):
| Old | New |
|-----|-----|
| `TVM_FFI_DECLARE_BASE_OBJECT_INFO(Self, Parent)` + separate `_type_key` | `TVM_FFI_DECLARE_OBJECT_INFO("key", Self, Parent)` |
| `TVM_FFI_DECLARE_FINAL_OBJECT_INFO(Self, Parent)` + separate `_type_key` | `TVM_FFI_DECLARE_OBJECT_INFO_FINAL("key", Self, Parent)` |
| `TVM_FFI_DECLARE_STATIC_OBJECT_INFO(Self, Parent)` + separate `_type_key` | `TVM_FFI_DECLARE_OBJECT_INFO_STATIC("key", Self, Parent)` |
| (classes needing `_type_key` defined separately) | `TVM_FFI_DECLARE_OBJECT_INFO_PREDEFINED_TYPE_KEY(Self, Parent)` |

### Ref method macros (4 -> 2):
| Old | New |
|-----|-----|
| `TVM_FFI_DEFINE_OBJECT_REF_METHODS` | `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE` |
| `TVM_FFI_DEFINE_MUTABLE_OBJECT_REF_METHODS` | (merged into `_NULLABLE`, auto-detects mutability) |
| `TVM_FFI_DEFINE_NOTNULLABLE_OBJECT_REF_METHODS` | `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE` |
| `TVM_FFI_DEFINE_MUTABLE_NOTNULLABLE_OBJECT_REF_METHODS` | (merged into `_NOTNULLABLE`, auto-detects mutability) |

The `__PtrType` alias in ref macros uses `std::conditional_t<ObjectName::_type_mutable, ObjectName*, const ObjectName*>` to automatically select mutable vs const pointer.

## Alternatives Considered
### Keep existing macros, add aliases
- Pros: Non-breaking.
- Cons: More macros, not fewer. Confusion about which to use.

### Use template-based CRTP instead of macros
- Pros: Eliminates macros entirely.
- Cons: Complex template errors. C++ CRTP patterns are less readable than macro patterns for this use case. Large migration.

### Consolidate to just 2 macros (one declare, one ref)
- Pros: Maximum simplification.
- Cons: Overloaded behavior (base vs. final vs. static) makes a single macro too complex.

## Why This Option Won
- Significant reduction in macro count (10 -> 6) without losing any expressiveness.
- Type key embedding eliminates the most common boilerplate line.
- Auto-mutable detection via `_type_mutable` eliminates the mutable/immutable macro split cleanly using `std::conditional_t`.
- Consistent `VERB_ADJECTIVE` suffix naming (`_FINAL`, `_STATIC`, `_NULLABLE`, `_NOTNULLABLE`).

## Consequences
### Positive
- Fewer macros to remember and document.
- Type key always defined inside the declaration (guaranteed by macro).
- No more accidentally using the wrong mutable/immutable ref macro.
- Clear naming pattern for future macro additions.

### Negative
- **Breaking change** for all C++ code using the old macro names.
- All Object/ObjectRef declarations must be updated.

### Risks
- Large downstream migration. Mitigated by mechanical search-and-replace: the old macro names are unique strings.

## Implementation Notes
- Commit `4ffbc88` renames all macros across all headers and source files.
- `_type_is_nullable` is now explicitly set: `true` in `_NULLABLE`, `false` in `_NOTNULLABLE`.
- The `TVM_FFI_DECLARE_OBJECT_INFO_PREDEFINED_TYPE_KEY` variant exists for the rare case where `_type_key` must be defined separately (e.g., when the key is computed).

## Validation
- All in-tree types updated to new macros.
- All C++ tests pass.
- Python tests pass (macros are C++ only; Python bindings unaffected).

## Migration and Rollback
- Migration: Find-and-replace old macro names to new names across all C++ files. For declaration macros, move the `_type_key = "..."` line into the macro argument.
- Rollback: Revert macro renames and restore old macro definitions.

## Related Design Docs
- [.memory/designs/0002-object-system-and-reference-counting.md](.memory/designs/0002-object-system-and-reference-counting.md)

## Related Diagrams
None

## Evidence Matrix
- Declaration macro renames -> `.memory/commits/2025-09-08-4ffbc88b60f659a74619035e699986792c071e8d.md` + `4ffbc88` + `include/tvm/ffi/object.h`
- Ref method macro consolidation -> `4ffbc88` + `include/tvm/ffi/object.h`
- Auto-mutable `__PtrType` via `std::conditional_t` -> `4ffbc88` + `include/tvm/ffi/object.h`
- TypeKey-in-macro pattern -> `4ffbc88` + `include/tvm/ffi/object.h` (all `TVM_FFI_DECLARE_OBJECT_INFO*` macros)

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Downstream projects must update all macro invocations to the new names.
- Documentation (guides, tutorials) must be updated to reference the new macro names.
