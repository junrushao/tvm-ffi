---
scope: "structural-equal-hash"
---
# API Index: Structural Equality and Hash

**Scope**: Structural equality/hash comparison classes, access path diagnostics, and related C ABI types.
**Design docs**: [0010-structural-equal-hash.md](../designs/0010-structural-equal-hash.md)
**ADRs**: [0009-custom-seqhash-via-typeattr.md](../ADRs/0009-custom-seqhash-via-typeattr.md), [0010-extra-api-isolation.md](../ADRs/0010-extra-api-isolation.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `StructuralEqual` | class (`extra/structural_equal.h`) | `Equal(const Any&, const Any&, bool map_free_vars=false, bool skip_ndarray_content=false)$ -> bool`, `GetFirstMismatch(const Any&, const Any&, bool, bool)$ -> Optional<AccessPathPair>`, `operator()(const Any&, const Any&) -> bool` | Reflection-based deep structural equality comparator |
| `StructuralHash` | class (`extra/structural_hash.h`) | `Hash(const Any&, bool map_free_vars=false, bool skip_ndarray_content=false)$ -> uint64_t`, `operator()(const Any&) -> uint64_t` | Reflection-based deep structural hasher |
| `AccessKind` | enum class (int32_t) | `kAttr=0`, `kArrayItem=1`, `kMapItem=2`, `kAttrMissing=3`, `kArrayItemMissing=4`, `kMapItemMissing=5` | Access step kind for mismatch diagnostics (kObjectField renamed to kAttr; kAttrMissing added) |
| `AccessStepObj` | class (`reflection/access_path.h`) | `AccessKind kind; Any key;`; `StepEqual(const AccessStep&) -> bool`; `_type_s_eq_hash_kind = kTVMFFISEqHashKindConstTreeNode`; `_type_key = "ffi.reflection.AccessStep"` | Access step data object (type_key changed from "tvm.ffi.reflection.AccessStep") |
| `AccessStep` | class | `Attr(String)$`, `AttrMissing(String)$`, `ArrayItem(int64_t)$`, `ArrayItemMissing(int64_t)$`, `MapItem(Any)$`, `MapItemMissing(Any)$` | Access step ref wrapper with factory methods (ObjectField renamed to Attr; AttrMissing added) |
| `AccessPathObj` | class (`reflection/access_path.h`) | `Optional<ObjectRef> parent; Optional<AccessStep> step; int32_t depth;`; `GetParent()`, `Extend(AccessStep)`, `Attr(String)`, `AttrMissing(String)`, `ArrayItem(int64_t)`, `ArrayItemMissing(int64_t)`, `MapItem(Any)`, `MapItemMissing(Any)`, `ToSteps() -> Array<AccessStep>`, `PathEqual(AccessPath) -> bool`, `IsPrefixOf(AccessPath) -> bool`; `_type_key = "ffi.reflection.AccessPath"` | Parent-pointing tree node for access paths (replaced `Array<AccessStep>` alias) |
| `AccessPath` | class | `Root()$`, `FromSteps(Array<AccessStep>)$`, `FromSteps(Iter, Iter)$` | Access path ref wrapper with factories; extends ObjectRef (no longer a type alias) |
| `AccessPathPair` | using | `= Tuple<AccessPath, AccessPath>` | Pair of access paths (lhs, rhs) for mismatch reporting |
| `TVMFFISEqHashKind` | enum (int32_t, C ABI) | `Unsupported=0`, `TreeNode=1`, `FreeVar=2`, `DAGNode=3`, `ConstTreeNode=4`, `UniqueInstance=5` | Per-type structural equality dispatch kind |
| `TVM_FFI_EXTRA_CXX_API` | macro (`extra/base.h`) | defaults to `TVM_FFI_DLL` | Visibility annotation for non-core C++ APIs implemented in .cc files |
| `details::StableHashCombine` | function | `(uint64_t a, uint64_t b) -> uint64_t` | Deterministic hash combiner |
| `details::StableHashBytes` | function | `(const char* data, size_t size) -> uint64_t` | Byte-content hasher with alignment fast-path |
| `StableHashSmallStrBytes` | function | `(const TVMFFIAny* data) -> uint64_t` | Hash function optimized for inline small strings |
| `StructuralKeyObj` | class (`extra/structural_key.h`, 6adc8df) | `Any key; int64_t hash_i64;`; `StructuralKeyObj(Any key)`; `_type_key = "ffi.StructuralKey"` | Object wrapping a value with its cached structural hash |
| `StructuralKey` | class (`extra/structural_key.h`, 6adc8df) | `StructuralKey(Any key)`, `operator==(const StructuralKey&) -> bool` (identity+hash+StructuralEqual), `operator!=(const StructuralKey&) -> bool` | Ref wrapper for structural-equality-based map keys |
| `std::hash<StructuralKey>` | specialization (6adc8df) | `operator()(const StructuralKey&) -> size_t` (returns `hash_i64`) | Enables `std::unordered_map<StructuralKey, V>` |
| `RecursiveHash` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& value) -> int64_t` | Deterministic recursive hash via reflection; honors `HashOff` field flag |
| `RecursiveEq` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& lhs, const Any& rhs) -> bool` | Recursive structural equality; honors `CompareOff` field flag |
| `RecursiveLt` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& lhs, const Any& rhs) -> bool` | Recursive less-than; honors `CompareOff` |
| `RecursiveLe` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& lhs, const Any& rhs) -> bool` | Recursive less-than-or-equal; honors `CompareOff` |
| `RecursiveGt` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& lhs, const Any& rhs) -> bool` | Recursive greater-than; honors `CompareOff` |
| `RecursiveGe` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& lhs, const Any& rhs) -> bool` | Recursive greater-than-or-equal; honors `CompareOff` |

## C++ API: Global Registered Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.GetFirstStructuralMismatch` | `(Any lhs, Any rhs, bool map_free_vars, bool skip_ndarray) -> Optional<AccessPathPair>` | Get first structural mismatch path |
| `ffi.StructuralHash` | `(Any value, bool map_free_vars, bool skip_ndarray) -> uint64_t` | Compute structural hash |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `StructuralKey` (6adc8df) | `class StructuralKey(Object): def __init__(self, key: Any) -> None; def __hash__(self) -> int; def __eq__(self, other) -> bool` | Hash-cached structural key wrapper (`tvm_ffi.structural`) |
| `structural_hash` (6adc8df) | `(value: Any, map_free_vars: bool = False, skip_tensor_content: bool = False) -> int` | Compute structural hash (`tvm_ffi.structural`) |
| `structural_equal` (6adc8df) | `(lhs: Any, rhs: Any, map_free_vars: bool = False, skip_tensor_content: bool = False) -> bool` | Structural equality check (`tvm_ffi.structural`) |
| `get_first_structural_mismatch` (6adc8df) | `(lhs, rhs, map_free_vars=False, skip_tensor_content=False) -> tuple[AccessPath, AccessPath] \| None` | Mismatch diagnostics (`tvm_ffi.structural`) |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | -- | Not yet bound |
