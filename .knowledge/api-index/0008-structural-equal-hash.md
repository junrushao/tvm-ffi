---
scope: "structural-equal-hash"
---
# API Index: Structural Equality and Hashing

**Scope**: C++ StructuralEqual, StructuralHash, AccessPath, and related types in the `extra/` module.
**Design docs**: [0009-structural-equal-hash.md](../designs/0009-structural-equal-hash.md)
**ADRs**: [0005-reflection-driven-structural-equality.md](../ADRs/0005-reflection-driven-structural-equality.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `StructuralEqual` | class | `static bool Equal(Any, Any, bool map_free_vars=false, bool skip_tensor_content=false)`, `static Optional<AccessPathPair> GetFirstMismatch(Any, Any, ...)`, `bool operator()(Any, Any)` | Recursive structural equality using reflection metadata (in `tvm::ffi`) |
| `StructuralHash` | class | `static uint64_t Hash(Any, bool map_free_vars=false, bool skip_tensor_content=false)`, `uint64_t operator()(Any)` | Recursive structural hashing using reflection metadata (in `tvm::ffi`) |
| `AccessStepObj` | class | `AccessKind kind`, `Any key` | Single step in a mismatch access path |
| `AccessStep` | using | `ObjectRef` wrapper for `AccessStepObj` | Access step ref |
| `AccessPathObj` | class | `parent: Optional<ObjectRef>`, `step: Optional<AccessStep>`, `depth: int`, `Extend()`, `Attr()`, `ToSteps()`, `PathEqual()`, `IsPrefixOf()` | Parent-pointer tree node for access paths (replaced Array alias) |
| `AccessPath` | class | `static Root()`, `static FromSteps(Array<AccessStep>)` | ObjectRef wrapper for AccessPathObj |
| `AccessPathPair` | using | `Tuple<AccessPath, AccessPath>` | Pair of paths (lhs, rhs) for mismatch |
| `AccessKind` | enum | `kAttr=0`, `kArrayItem=1`, `kMapItem=2`, `kAttrMissing=3`, `kArrayItemMissing=4`, `kMapItemMissing=5` | Kind of access step (kObjectField renamed to kAttr, kAttrMissing added) |
| `TVMFFISEqHashKind` | enum (C ABI) | `Unsupported=0`, `TreeNode=1`, `FreeVar=2`, `DAGNode=3`, `ConstTreeNode=4`, `UniqueInstance=5` | Per-type comparison semantics |
| `TVM_FFI_EXTRA_CXX_API` | macro | Visibility attribute for extra API symbols | Marks non-core C++ APIs (in `extra/base.h`) |

| `StructuralKeyObj` | class | `key: Any`, `hash_i64: int` | Caches structural hash alongside a key value for efficient map lookups (6adc8df) |
| `StructuralKey` | class | `__init__(key)`, `__hash__()`, `__eq__(other)` | Python-side wrapper with `__any_hash__`/`__any_equal__` type attrs for native container integration (6adc8df) |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.reflection.GetFirstStructuralMismatch` | `def GetFirstStructuralMismatch(lhs, rhs, ...) -> Optional[Tuple]` | Global function for mismatch detection |
| `ffi.reflection.StructuralHash` | `def StructuralHash(value, ...) -> int` | Global function for structural hashing |
| `tvm_ffi.structural_equal` | `def structural_equal(lhs, rhs, map_free_vars=False, skip_tensor_content=False) -> bool` | Top-level structural equality (6adc8df) |
| `tvm_ffi.structural_hash` | `def structural_hash(value, map_free_vars=False, skip_tensor_content=False) -> int` | Top-level structural hash (6adc8df) |
| `tvm_ffi.get_first_structural_mismatch` | `def get_first_structural_mismatch(lhs, rhs, ...) -> Optional[tuple]` | Returns (lhs_path, rhs_path) or None (6adc8df) |
| `tvm_ffi.StructuralKey` | `class StructuralKey: __init__(key), __hash__(), __eq__(other)` | Structural-hash-keyed wrapper for dict/map use (6adc8df) |
