---
design: "0007"
title: "Reflection-Based Structural Equal and Hash System"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-07-19"
last_updated: "2025-08-06"
scope:
  - "ffi/extra"
  - "ffi/reflection"
  - "ffi/c_api"
source_commits:
  - "9445fe734839cffc8bdf881788528b7763f7be03"
  - "162d6009252dd44950a9aa9b890cbbce6b8e5155"
  - "2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec"
  - "59a837eb4040843051706cbf5c7b71725fd65364"
  - "e52aed53526d3a6207feb940303a6cd584fdf9d1"
  - "3fc0391e29dac100ad37db45348090438e1db739"
  - "ba0ea87da5f51890b8801ceaad2f583d17265bc1"
  - "f4ede982f00257881d9ba7fe82dd8abc07e14690"
source_ledgers:
  - ".memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md"
  - ".memory/commits/2025-07-22-162d6009252dd44950a9aa9b890cbbce6b8e5155.md"
  - ".memory/commits/2025-07-26-2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec.md"
  - ".memory/commits/2025-07-28-59a837eb4040843051706cbf5c7b71725fd65364.md"
  - ".memory/commits/2025-07-29-e52aed53526d3a6207feb940303a6cd584fdf9d1.md"
  - ".memory/commits/2025-07-30-3fc0391e29dac100ad37db45348090438e1db739.md"
  - ".memory/commits/2025-07-30-ba0ea87da5f51890b8801ceaad2f583d17265bc1.md"
  - ".memory/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md"
---

# Reflection-Based Structural Equal and Hash System

## TL;DR
- `StructuralEqual` and `StructuralHash` classes traverse object fields via reflection metadata, replacing per-type manual `SEqualReduce`/`SHashReduce` registrations. The system is driven by the same `ForEachFieldInfo` infrastructure used for object construction and serialization.
- Each object type declares a `TVMFFISEqHashKind` enum value (`TreeNode`, `FreeVar`, `DAGNode`, `ConstTreeNode`, `UniqueInstance`) that controls traversal semantics. Types can also register custom `__s_equal__`/`__s_hash__` callbacks via `TypeAttrColumn` for comparison logic that cannot be expressed by field flags alone.
- `AccessPath`/`AccessStep` objects provide precise mismatch diagnostics, allowing callers to determine the exact field/index/key where two values diverge.

## Problem Statement
Compiler IR objects need deep structural comparison and hashing for optimization passes (CSE, deduplication, pattern matching). Without a generic mechanism, each IR node type must manually implement `SEqualReduce`/`SHashReduce`, leading to hundreds of boilerplate registrations that are error-prone and hard to keep in sync with field changes. If the comparison is wrong, optimization passes silently produce incorrect results.

## Context and Constraints
- Structural comparison must respect IR-specific semantics: free variables (matched by identity), DAG nodes (shared subexpressions), define regions (where variables are introduced), and constant trees (compared by content always).
- The comparison must traverse inherited fields in parent-to-child order, consistent with the reflection system's `ForEachFieldInfo`.
- Custom comparison logic is needed for types where field-by-field traversal is insufficient (e.g., types that reorder comparisons or apply normalization).
- The system must be optional: minimal builds should be able to exclude structural comparison without affecting core FFI functionality.
- NaN values in floating-point fields must compare as equal and hash consistently (canonicalization requirement).

## Goals
- Eliminate per-type manual `SEqualReduce`/`SHashReduce` implementations via reflection-driven field traversal.
- Support five comparison semantics via `TVMFFISEqHashKind` enum: `TreeNode`, `FreeVar`, `DAGNode`, `ConstTreeNode`, `UniqueInstance`.
- Support custom comparison via `__s_equal__`/`__s_hash__` callbacks registered in `TypeAttrColumn`.
- Provide `AccessPath`-based mismatch diagnostics for debugging comparison failures.
- Isolate the system behind `TVM_FFI_USE_EXTRA_CXX_API` CMake flag for minimal builds.

## Non-Goals
- Thread-safe concurrent comparison (single-threaded traversal assumed).
- Serialization or canonical forms (structural hash/equal is a query, not a transformation).
- Comparison of non-Object values beyond POD equality (the system dispatches on Object types).

## Design
### Components and Responsibilities

- **`TVMFFISEqHashKind`** (C ABI enum, `c_api.h`): Per-type metadata controlling structural comparison semantics. Values: `kTVMFFISEqHashKindUnsupported` (0, default -- throws `TypeError` if compared), `kTVMFFISEqHashKindTreeNode` (1, field-by-field tree comparison), `kTVMFFISEqHashKindFreeVar` (2, identity-mapped variables), `kTVMFFISEqHashKindDAGNode` (3, shared subexpressions with deduplication), `kTVMFFISEqHashKindConstTreeNode` (4, always compared by content regardless of define-region), `kTVMFFISEqHashKindUniqueInstance` (5, pointer equality only). Stored in `TVMFFITypeMetadata.structural_eq_hash_kind`.

- **`StructuralEqual`** (class, `extra/structural_equal.h`): Static `Equal(lhs, rhs, map_free_vars, skip_tensor_content)` method and `GetFirstMismatch` method. Internally uses `StructEqualHandler` which maintains a `map_free_vars_` flag, an `equal_map_` for FreeVar/DAG bookkeeping, and per-comparison `AccessPath` tracking.

- **`StructuralHash`** (class, `extra/structural_hash.h`): Static `Hash(value, map_free_vars, skip_tensor_content)` method. Internally uses `StructuralHashHandler` which maintains a `hash_combine_` accumulator and FreeVar/DAG counters.

- **`AccessPath` / `AccessStep`** (classes, `reflection/access_path.h`): `AccessPath` was redesigned from a flat `Array<AccessStep>` alias to a dedicated `AccessPathObj` using a parent-pointing tree structure (commit `f4ede98`). Each `AccessPathObj` has `parent` (Optional<ObjectRef>), `step` (Optional<AccessStep>), `depth` (int32_t). Methods: `Root()`, `Extend()`, `Attr()`, `AttrMissing()`, `ArrayItem()`, `ArrayItemMissing()`, `MapItem()`, `MapItemMissing()`, `ToSteps()`, `PathEqual()`, `IsPrefixOf()`, `GetParent()`. Factory: `AccessPath::FromSteps(iter, iter)` and `AccessPath::FromSteps(Array<AccessStep>)`. `AccessKind` enum: `kAttr` (renamed from `kObjectField`), `kArrayItem`, `kMapItem`, plus `kAttrMissing`, `kArrayItemMissing`, `kMapItemMissing`. The parent-pointing structure is space-efficient when many paths share a common prefix during tree comparisons. `AccessStep::_type_key` changed from `"tvm.ffi.reflection.AccessStep"` to `"ffi.reflection.AccessStep"`.

- **`AttachFieldFlag`** (reflection trait, `reflection/registry.h`): Annotates fields with semantic flags via `TVMFFIFieldFlagBitMask`. Two SEqHash-specific flags: `kTVMFFIFieldFlagBitMaskSEqHashIgnore` (skip field during comparison) and `kTVMFFIFieldFlagBitMaskSEqHashDef` (mark field as part of a define region where `map_free_vars` is temporarily enabled).

- **`TypeAttrColumn` custom dispatch**: When a type has `kTVMFFISEqHashKindTreeNode` and registers `__s_equal__`/`__s_hash__` callbacks via `TypeAttrDef<T>`, the handlers dispatch through these callbacks instead of field-by-field traversal. The callbacks receive `cmp`/`hash` functions that recurse back into the structural comparison infrastructure, with `def_region` control for binding-site parameters.

- **`TVM_FFI_EXTRA_CXX_API`** (macro, `extra/base.h`): Visibility annotation for non-core C++ APIs. Defined as `TVM_FFI_DLL`. Structural equal/hash source files are gated behind `TVM_FFI_USE_EXTRA_CXX_API` CMake option (default ON).

### Data Contracts and Invariants
- **Kind completeness**: Every object type participating in structural comparison must have `_type_s_eq_hash_kind != kTVMFFISEqHashKindUnsupported`, or a `TypeError` is thrown.
- **NaN canonicalization**: `StructuralHash(NaN) == StructuralHash(NaN)` and `StructuralEqual(NaN, NaN) == true` regardless of NaN bit pattern. Float values are canonicalized to `quiet_NaN` before comparison/hashing.
- **Field order**: Structural comparison traverses fields in ancestor-first order via `ForEachFieldInfo`, matching the order used by `MakeObjectFromPackedArgs`.
- **FreeVar mapping**: Two FreeVar objects are structurally equal if and only if they appear at the same position in the traversal order. The `equal_map_` maintains the bijective mapping.
- **DAG sharing**: For `DAGNode` types, if two objects have been compared equal previously, subsequent comparisons short-circuit to `true`.
- **Custom callback protocol**: `__s_equal__(self, other, cmp)` where `cmp(lhs, rhs, def_region, field_name) -> bool`. `__s_hash__(self, init_hash, hash)` where `hash(value, def_region) -> uint64_t` and the callback returns the combined hash directly.

### Control Flow
1. **Structural Equal**: `StructuralEqual::Equal(lhs, rhs)` -> create `StructEqualHandler` -> `CompareAny(lhs, rhs)` -> if both are objects with same type: check `UniqueInstance` (pointer fast path) -> check FreeVar/DAG maps -> check `TypeAttrColumn("__s_equal__")` for custom dispatch -> else `ForEachFieldInfoWithEarlyStop` for field-by-field comparison -> apply FreeVar/DAG post-processing on success -> return result.
2. **Structural Hash**: `StructuralHash::Hash(value)` -> create `StructuralHashHandler` -> `HashAny(value)` -> type index dispatch: POD types hash directly; object types: check `UniqueInstance` (pointer hash) -> check `TypeAttrColumn("__s_hash__")` for custom dispatch -> else `ForEachFieldInfo` field-by-field hashing -> apply FreeVar/DAG counter logic -> return combined hash.
3. **Mismatch diagnostics**: `GetFirstMismatch(lhs, rhs)` -> run comparison with `AccessPath` tracking enabled -> on first mismatch, capture `(lhs_path, rhs_path)` as `AccessPathPair` -> return to caller for diagnostic display.

### Extension Points
- **New SEqHash kinds**: Add new values to `TVMFFISEqHashKind` enum for new traversal semantics (requires ABI version bump).
- **Custom comparison**: Register `__s_equal__`/`__s_hash__` via `TypeAttrDef<T>().def(...)` for any `TreeNode` type.
- **New field flags**: Extend `TVMFFIFieldFlagBitMask` to add new semantic annotations (e.g., "normalize before compare").
- **Container-specific comparison**: The handler has special-case logic for `Array`, `Map`, `Shape`, and `NDArray`. New container types can be added by extending the dispatch in `structural_equal.cc`/`structural_hash.cc`.

## Alternatives Considered
### Keep per-type SEqualReduce/SHashReduce visitor pattern
- Pros: Already existed in upstream TVM. Full control per type.
- Cons: Hundreds of manual registrations. Error-prone when fields change. No cross-language access to comparison logic.

### Template metaprogramming (compile-time reflection)
- Pros: Zero runtime cost. Type-safe.
- Cons: Not available in C++17 (requires C++23 or later). Cannot support dynamic types or cross-language dispatch.

### Separate custom kind (`kTVMFFISEqHashKindCustomTreeNode = 6`)
- Pros: Explicit dispatch via enum value.
- Cons: Adds complexity to dispatch logic. Redundant with `TypeAttrColumn` presence check. Was introduced in commit `2ec11f5` and removed in `59a837e` after one week.

## Trade-offs
- **Optimized**: Elimination of boilerplate (one `_type_s_eq_hash_kind` declaration replaces `SEqualReduce`/`SHashReduce`), cross-language access via global functions, rich mismatch diagnostics via `AccessPath`.
- **Sacrificed**: Potential performance overhead from runtime reflection dispatch vs. hand-tuned per-type comparison. The `TypeAttrColumn` lookup adds a level of indirection for custom dispatch. The `AccessPath` parent-pointing tree allocates objects on each step extension.

## Interfaces and Compatibility
- **C ABI**: `TVMFFISEqHashKind` enum, `TVMFFITypeMetadata.structural_eq_hash_kind` field, `TVMFFIFieldFlagBitMask` with SEqHash flags (`kTVMFFIFieldFlagBitMaskSEqHashIgnore`, `kTVMFFIFieldFlagBitMaskSEqHashDef`).
- **C++ API**: `StructuralEqual`, `StructuralHash`, `AccessPath`, `AccessStep`, `AccessPathPair`, `AttachFieldFlag::SEqHashIgnore()`, `AttachFieldFlag::SEqHashDef()`.
- **Global functions**: `ffi.reflection.GetFirstStructuralMismatch`, `ffi.reflection.StructuralHash` (registered via `GlobalDef`).
- **CMake**: `TVM_FFI_USE_EXTRA_CXX_API` (default ON) gates compilation of `structural_equal.cc`, `structural_hash.cc`.

## Failure Modes and Mitigations
- **Missing metadata**: Types without `TVMFFITypeMetadata` or with `kTVMFFISEqHashKindUnsupported` throw `TypeError` instead of silently falling back to pointer comparison. This strict error semantics was introduced in commit `59a837e`.
- **Custom callback error**: If `__s_equal__`/`__s_hash__` callbacks throw, the exception propagates through the handler and terminates the comparison.
- **Infinite recursion**: Circular object graphs would cause stack overflow. Mitigated by the DAG bookkeeping which short-circuits on previously-compared pairs (for `DAGNode` types). Tree and FreeVar types are assumed to be acyclic by the IR's structural invariants.
- **NaN inconsistency**: Without canonicalization, different NaN bit patterns would hash differently and compare unequal. The canonicalization to `quiet_NaN` (commit `59a837e`) ensures consistency.

## Observability and Validation
- `tests/cpp/extra/test_reflection_structural_equal_hash.cc`: Tests all SEqHash kinds (TreeNode, FreeVar, DAGNode, ConstTreeNode, UniqueInstance), field flag annotations (SEqHashIgnore, SEqHashDef), custom dispatch via TypeAttrDef, NaN handling, and AccessPath diagnostics.
- `ffi.reflection.GetFirstStructuralMismatch` global function provides runtime mismatch diagnosis accessible from Python.
- `ffi.reflection.StructuralHash` global function provides cross-language hash access.

## Migration and Rollout
- **From legacy SEqualReduce/SHashReduce**: Declare `_type_s_eq_hash_kind` static constexpr in the Obj class. Register fields with `AttachFieldFlag::SEqHashDef()`/`SEqHashIgnore()` where needed. Remove `SEqualReduce`/`SHashReduce` methods. The legacy `_type_has_method_sequal_reduce`/`_type_has_method_shash_reduce` bools were removed from `Object` in commit `e52aed5`.
- **For custom comparison**: Set `_type_s_eq_hash_kind = kTVMFFISEqHashKindTreeNode` and register `__s_equal__`/`__s_hash__` via `TypeAttrDef<T>().def(...)`.

## Diagrams
- [.memory/diagrams/0005-structural-equal-hash-flow.md](.memory/diagrams/0005-structural-equal-hash-flow.md)

## Related ADRs
- [.memory/ADRs/0009-extra-api-isolation.md](.memory/ADRs/0009-extra-api-isolation.md)

## Evidence Matrix
- `TVMFFISEqHashKind` enum with 6 values (0-5) -> `.memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md` + `9445fe7` + `include/tvm/ffi/c_api.h`
- `StructuralEqual` / `StructuralHash` classes -> `.memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md` + `9445fe7` + `include/tvm/ffi/extra/structural_equal.h`, `include/tvm/ffi/extra/structural_hash.h`
- `AccessPath`/`AccessStep` with `kArrayItem`/`kMapItem` naming -> `.memory/commits/2025-07-30-3fc0391e29dac100ad37db45348090438e1db739.md` + `3fc0391` + `include/tvm/ffi/reflection/access_path.h`
- `AccessPathObj` parent-pointing tree redesign (parent, step, depth fields) -> `.memory/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md` + `f4ede98` + `include/tvm/ffi/reflection/access_path.h`
- `AccessKind::kObjectField` renamed to `kAttr`, `kAttrMissing` added -> `.memory/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md` + `f4ede98` + `include/tvm/ffi/reflection/access_path.h`
- `AccessStep::_type_key` changed to `"ffi.reflection.AccessStep"` -> `.memory/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md` + `f4ede98`
- AccessPath/AccessStep reflection moved to `src/ffi/extra/reflection_extra.cc` -> `.memory/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md` + `f4ede98`
- `AttachFieldFlag` for SEqHash Def/Ignore -> `.memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md` + `9445fe7` + `include/tvm/ffi/reflection/registry.h`
- `TypeAttrColumn` custom dispatch (replaces `kTVMFFISEqHashKindCustomTreeNode`) -> `.memory/commits/2025-07-28-59a837eb4040843051706cbf5c7b71725fd65364.md` + `59a837e` + `src/ffi/extra/structural_equal.cc`, `src/ffi/extra/structural_hash.cc`
- `kTVMFFISEqHashKindCustomTreeNode` introduced then removed -> `.memory/commits/2025-07-26-2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec.md` + `2ec11f5` (introduced); `.memory/commits/2025-07-28-59a837eb4040843051706cbf5c7b71725fd65364.md` + `59a837e` (removed)
- NaN canonicalization invariant -> `.memory/commits/2025-07-28-59a837eb4040843051706cbf5c7b71725fd65364.md` + `59a837e`
- Legacy `_type_has_method_sequal_reduce`/`_type_has_method_shash_reduce` removed from Object -> `.memory/commits/2025-07-29-e52aed53526d3a6207feb940303a6cd584fdf9d1.md` + `e52aed5` + `include/tvm/ffi/object.h`
- `TVM_FFI_EXTRA_CXX_API` macro and `extra/` directory -> `.memory/commits/2025-07-30-3fc0391e29dac100ad37db45348090438e1db739.md` + `3fc0391` + `include/tvm/ffi/extra/base.h`
- `TVM_FFI_USE_EXTRA_CXX_API` CMake option -> `.memory/commits/2025-07-26-2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec.md` + `2ec11f5` + `CMakeLists.txt`
- String `memequal` and `StableHashBytes` aligned optimization used in structural equal -> `.memory/commits/2025-07-30-ba0ea87da5f51890b8801ceaad2f583d17265bc1.md` + `ba0ea87`

## Open Questions
- ~~Should the `AccessPath` tree use arena allocation to reduce per-step heap allocation overhead during large comparisons?~~ Partially addressed: the parent-pointing tree structure (commit `f4ede98`) avoids duplicating shared prefixes, which is the dominant cost pattern during tree comparisons. Full arena allocation remains a future optimization.
- Should `DAGNode` comparison track and report the point where two previously-equal subgraphs diverge?
- Should the system support parallel structural comparison for independent subtrees?

## Confidence and Risk
- Confidence: high
- Residual risks: The `TypeAttrColumn` lookup for custom dispatch is not cached per-handler invocation (it uses a static local, which is initialized once per process). If the column is modified after the handler is created, the static reference may become stale (unlikely in practice since columns are registered at static init). The `AccessPath` allocation overhead may be significant for deeply nested IR trees when `GetFirstMismatch` is called frequently.
