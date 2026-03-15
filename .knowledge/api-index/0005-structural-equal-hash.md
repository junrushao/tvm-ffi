---
scope: "structural-equal-hash"
status: "active"
last_updated_commit: "f4ede982f00257881d9ba7fe82dd8abc07e14690"
related_designs:
  - ".knowledge/designs/0010-structural-equal-hash.md"
related_adrs:
  - ".knowledge/ADRs/009-reflection-structural-eq-hash.md"
---
# API Index: Structural Equal/Hash

**Scope**: Reflection-driven structural equality, hashing, and mismatch diagnostics for IR nodes.
**Design docs**: `.knowledge/designs/0010-structural-equal-hash.md`
**ADRs**: `.knowledge/ADRs/009-reflection-structural-eq-hash.md`

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| (No dedicated C ABI functions; structural eq/hash operates via C++ API and registered global functions) | | |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `StructuralEqual` | class (`tvm::ffi`) | `static bool Equal(const Any&, const Any&, bool map_free_vars=false, bool skip_ndarray_content=false)`; `static Optional<AccessPathPair> GetFirstMismatch(...)`; `bool operator()(const Any&, const Any&) const` | Structural equality with mismatch diagnostics |
| `StructuralHash` | class (`tvm::ffi`) | `static uint64_t Hash(const Any&, bool map_free_vars=false, bool skip_ndarray_content=false)`; `uint64_t operator()(const Any&) const` | Structural hashing |
| `AccessStepObj` | class (`tvm::ffi::reflection`) | `AccessKind kind; Any key; bool StepEqual(const AccessStep&) const` | Single step in a mismatch path |
| `AccessStep` | ObjectRef (`tvm::ffi::reflection`) | `Attr(String)`, `AttrMissing(String)`, `ArrayItem(int64_t)`, `ArrayItemMissing(int64_t)`, `MapItem(Any)`, `MapItemMissing(Any)` | Factory methods for path steps |
| `AccessKind` | enum class (`tvm::ffi::reflection`) | `kAttr=0, kArrayItem=1, kMapItem=2, kAttrMissing=3, kArrayItemMissing=4, kMapItemMissing=5` | Step kind discriminant |
| `AccessPathObj` | class (`tvm::ffi::reflection`) | `Optional<ObjectRef> parent; Optional<AccessStep> step; int32_t depth; PathEqual(other); IsPrefixOf(other); ToSteps()` | Parent-pointing tree node for access paths |
| `AccessPath` | ObjectRef (`tvm::ffi::reflection`) | `Root()`, `FromSteps(Array<AccessStep>)`, `->Extend(step)`, `->Attr(name)`, `->ArrayItem(i)`, `->MapItem(key)` | Linked-list path; shared prefixes share memory |
| `AttachFieldFlag` | class (`tvm::ffi::reflection`) | `SEqHashDef() -> AttachFieldFlag`, `SEqHashIgnore() -> AttachFieldFlag` | Per-field flag attachment for eq/hash control |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `StructuralEqual::Equal` | `static bool Equal(const Any& lhs, const Any& rhs, bool map_free_vars=false, bool skip_ndarray_content=false)` | Top-level structural equality |
| `StructuralEqual::GetFirstMismatch` | `static Optional<AccessPathPair> GetFirstMismatch(const Any& lhs, const Any& rhs, bool map_free_vars=false, bool skip_ndarray_content=false)` | First mismatch with path diagnostics |
| `StructuralHash::Hash` | `static uint64_t Hash(const Any& value, bool map_free_vars=false, bool skip_ndarray_content=false)` | Top-level structural hash |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.GetFirstStructuralMismatch` | `(lhs: Any, rhs: Any, map_free_vars=False, skip_ndarray=False) -> Optional[Tuple[Array[AccessStep], Array[AccessStep]]]` | First mismatch path (registered global) |
| `ffi.StructuralHash` | `(value: Any, map_free_vars=False, skip_ndarray=False) -> int` | Structural hash (registered global) |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `tvm::ffi::reflection::StructuralEqual` | `tvm::ffi::StructuralEqual` | 3fc0391 | Moved out of reflection namespace |
| `tvm::ffi::reflection::StructuralHash` | `tvm::ffi::StructuralHash` | 3fc0391 | Moved out of reflection namespace |
| `reflection/structural_equal.h` | `extra/structural_equal.h` | 3fc0391 | Moved to extra directory |
| `reflection/structural_hash.h` | `extra/structural_hash.h` | 3fc0391 | Moved to extra directory |
| `AccessKind::kArrayIndex` | `AccessKind::kArrayItem` | 3fc0391 | Renamed |
| `AccessKind::kMapKey` | `AccessKind::kMapItem` | 3fc0391 | Renamed |
| `AccessStep::ArrayIndex()` | `AccessStep::ArrayItem()` | 3fc0391 | Renamed |
| `AccessStep::MapKey()` | `AccessStep::MapItem()` | 3fc0391 | Renamed |
| `kTVMFFISEqHashKindCustomTreeNode` | (removed) | 59a837e | Replaced by presence-based custom dispatch |
| `_type_has_method_sequal_reduce` | (removed) | e52aed5 | Replaced by `_type_s_eq_hash_kind` + TypeAttr |
| `_type_has_method_shash_reduce` | (removed) | e52aed5 | Replaced by `_type_s_eq_hash_kind` + TypeAttr |
| `ffi.reflection.GetFirstStructuralMismatch` | `ffi.GetFirstStructuralMismatch` | 3fc0391 | Namespace change |
| `ffi.reflection.StructuralHash` | `ffi.StructuralHash` | 3fc0391 | Namespace change |
| `AccessKind::kObjectField` | `AccessKind::kAttr` | f4ede98 | Renamed |
| `AccessStep::ObjectField(String)` | `AccessStep::Attr(String)` | f4ede98 | Renamed |
| `using AccessPath = Array<AccessStep>` | `AccessPathObj`/`AccessPath` (proper Object/ObjectRef) | f4ede98 | Refactored to parent-pointing tree |
| `tvm.ffi.reflection.AccessStep` (type_key) | `ffi.reflection.AccessStep` | f4ede98 | Type key prefix change |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 9445fe7 | `2025-07-19-9445fe7.md` | Initial reflection-based structural eq/hash, AccessPath, AttachFieldFlag |
| 2ec11f5 | `2025-07-26-2ec11f5.md` | Custom __s_equal__/__s_hash__ via TypeAttr |
| 59a837e | `2025-07-28-59a837e.md` | Presence-based dispatch, NaN canonicalization, accumulator signature |
| e52aed5 | `2025-07-29-e52aed5.md` | Remove legacy boolean flags |
| 3fc0391 | `2025-07-30-3fc0391.md` | Move to tvm::ffi namespace, extra/ directory, AccessKind renames |
| f4ede98 | `2025-08-06-f4ede982f002.md` | AccessPath parent-pointing tree refactor, kObjectField->kAttr, kAttrMissing |
