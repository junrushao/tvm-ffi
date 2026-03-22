---
status: "active"
confidence: "high"
---
# Structural Equality and Hash — Reflection-Driven Value Comparison

**TL;DR**
- `StructuralEqual` and `StructuralHash` recursively compare/hash any `Any` value by walking reflection-registered fields, handling tree, DAG, free-variable, and unique-instance node semantics via a per-type kind flag (`TVMFFISEqHashKind`) stored in `TVMFFITypeMetadata`.
- Custom comparison/hash behavior is injected via `TypeAttrColumn("__s_equal__"/"__s_hash__")` entries registered through `TypeAttrDef<T>`. Types set `_type_s_eq_hash_kind = kTVMFFISEqHashKindTreeNode` and register these attrs to opt in to custom dispatch without needing a new enum value.
- `AccessStep`/`AccessPath`/`AccessPathPair` record the path to the first mismatch for rich error reporting. `AccessPath` is a proper `ObjectRef` (parent-pointer tree) since commit f4ede98 — it is no longer an alias for `Array<AccessStep>`. `AccessPath` reflection registrations live in `src/ffi/extra/reflection_extra.cc` (extra-gated). The always-compiled core still provides the `access_path.h` header with the type definitions.

## Problem Statement

### Background
IR compiler frameworks need to compare and hash complex graph structures (ASTs, relay expressions, etc.) where node identity differs but structural content may match. Standard `operator==` and `std::hash` use pointer identity; deep equality requires recursive traversal that understands shared sub-graphs (DAGs), free variables (alpha-equivalence), and which fields to skip (e.g., comments, metadata).

### Solution
`StructuralEqual` and `StructuralHash` are handler objects that dispatch on `TVMFFISEqHashKind` stored per type. For each object encountered, they look up the kind and either: (1) compare/hash field-by-field via reflection, (2) use map-based equality for free vars, (3) memoize results for DAG nodes, or (4) delegate to a custom `__s_equal__`/`__s_hash__` function registered in a `TypeAttrColumn`. All non-object scalar types are handled by specialized branches.

### Goals
- Reflection-driven: types opt in by setting one static field and calling `ObjectDef`.
- Alpha-equivalence for free variables: variables with different names but bound at structurally equivalent positions compare equal.
- DAG memoization: avoid exponential blowup for shared subgraph structures.
- Rich mismatch reporting: `GetFirstMismatch` returns the exact path to the first diverging field/element.
- Non-goal: runtime pluggable comparison (type kinds are registered at static init time).

## Design

### TVMFFISEqHashKind Dispatch

```mermaid
flowchart TD
    A["StructuralEqual::Equal(lhs, rhs)"]
    B{"TVMFFIGetTypeInfo(type_index) returns metadata?"}
    C["TypeError: type has no metadata"]
    D{"TVMFFISEqHashKind?"}
    E["TypeError: kUnsupported"]
    F["pointer identity (lhs.same_as(rhs))"]
    G{"TypeAttrColumn('__s_equal__')[type_index] non-null?"}
    H["Call __s_equal__(self, other, cmp_cb)"]
    I["ForEachFieldInfoWithEarlyStop: compare each field"]
    J["record in equal_map (DAG/FreeVar only)"]

    A --> B
    B -- "null" --> C
    B -- "non-null" --> D
    D -- "kUnsupported" --> E
    D -- "kUniqueInstance" --> F
    D -- "kConstTree: ptr match?" --> |"same ptr → true"| F
    D -- "kDAGNode / kFreeVar: cached?" --> |"in map → use cached"| J
    D -- "kTreeNode / kDAGNode / kFreeVar / kConstTree" --> G
    G -- "non-null" --> H
    G -- "null" --> I
    I --> J
```

### Key Classes, Fields and Interfaces

```python
class TVMFFISEqHashKind(IntEnum):
    """Per-type structural comparison/hash strategy. Stored in TVMFFITypeMetadata."""
    kTVMFFISEqHashKindUnsupported    = 0  # throws TypeError if encountered
    kTVMFFISEqHashKindTreeNode       = 1  # recurse over reflected fields; custom attrs may override
    kTVMFFISEqHashKindFreeVar        = 2  # symbolic variable: map-or-pointer equality
    kTVMFFISEqHashKindDAGNode        = 3  # recurse fields; record mapping to detect sharing
    kTVMFFISEqHashKindConstTreeNode  = 4  # tree with no free-var children; pointer equality as fast path
    kTVMFFISEqHashKindUniqueInstance = 5  # singleton; always pointer equality
    # Note: kTVMFFISEqHashKindCustomTreeNode=6 was briefly introduced (commit 2ec11f5f)
    # then removed (commit 59a837eb). Custom dispatch is now via TypeAttrColumn only.


class StructuralEqual:
    """Reflection-driven structural equality comparator.
    Header: include/tvm/ffi/extra/structural_equal.h (moved from reflection/ in commit 3fc0391e)
    """
    @staticmethod
    def Equal(lhs: Any, rhs: Any,
              map_free_vars: bool = False,
              skip_ndarray_content: bool = False) -> bool: ...
    # Interacts with: TVMFFITypeInfo.metadata.structural_eq_hash_kind (dispatch)
    # Interacts with: TVMFFIFieldInfo.flags (SEqHashIgnore / SEqHashDef)
    # Interacts with: TypeAttrColumn("__s_equal__") for custom dispatch
    # Invariant: NaN float values compare as equal to each other (commit 59a837eb)
    # Invariant: missing metadata or kUnsupported throws TypeError (not silent fallback)

    @staticmethod
    def GetFirstMismatch(lhs: Any, rhs: Any,
                         map_free_vars: bool = False,
                         skip_ndarray_content: bool = False
                         ) -> Optional[AccessPathPair]: ...
    # Returns None on equality; else (lhs_path, rhs_path) to first diverging element
    # Registered as global func: "ffi.reflection.GetFirstStructuralMismatch"
    # Interacts with: AccessPath (records mismatch_lhs_reverse_path_, mismatch_rhs_reverse_path_)

    def __call__(self, lhs: Any, rhs: Any) -> bool:
        return StructuralEqual.Equal(lhs, rhs, map_free_vars=False, skip_ndarray_content=True)
    # Default operator() skips NDArray content (typically want structure comparison, not data)


class StructuralHash:
    """Reflection-driven structural hash functor.
    Header: include/tvm/ffi/extra/structural_hash.h
    """
    @staticmethod
    def Hash(value: Any,
             map_free_vars: bool = False,
             skip_ndarray_content: bool = False) -> uint64_t: ...
    # Registered as global func: "ffi.reflection.StructuralHash"
    # Interacts with: StructuralHashHandler.hash_memo_ (memoisation for DAG/ConstTree)
    # Interacts with: StructuralHashHandler.free_var_counter_ (lexical order for FreeVar)
    # Invariant: consistent with StructuralEqual — equal objects produce equal hashes
    # Invariant: NaN float values all hash to the same canonical value

    def __call__(self, value: Any) -> uint64_t:
        return StructuralHash.Hash(value)


# FFIStructuralHash — C++ global function wrapper (commit 86bbddfd):
def FFIStructuralHash(value: Any, map_free_vars: bool, skip_tensor_content: bool) -> int64_t:
    """Registered as global func "ffi.StructuralHash". Returns int64_t (bitcast of uint64_t hash).
    Internally calls StructuralHash::Hash() which returns uint64_t, then does:
        return static_cast<int64_t>(hash_result);  # bitcast preserving all bits
    This avoids the TypeTraits<uint64_t>::CopyToAnyView overflow check (commit 86bbddfd):
    large hash values that exceed INT64_MAX would otherwise throw OverflowError when
    returned through the FFI boundary.
    # Invariant: the bit pattern is preserved; callers who need uint64_t must reinterpret:
    #   uint64_t h = static_cast<uint64_t>(result.cast<int64_t>());
    # Interacts with: TypeTraits<uint64_t>::CopyToAnyView overflow guard (0008-type-traits)
    """


class AccessKind(IntEnum):
    """Discriminator for one step in an AccessPath.
    Header: include/tvm/ffi/reflection/access_path.h
    """
    kAttr             = 0   # was: kObjectField (renamed in commit f4ede98)
    kArrayItem        = 1   # was: kArrayIndex (renamed in commit 3fc0391e)
    kMapItem          = 2   # was: kMapKey
    kAttrMissing      = 3   # NEW (commit f4ede98) — missing object attribute
    kArrayItemMissing = 4   # was: 3 (shifted by 1 in commit f4ede98)
    kMapItemMissing   = 5   # was: 4 (shifted by 1 in commit f4ede98)
    # Invariant: numeric values are ABI-significant (stored in AccessStepObj::kind as int32_t)
    # BREAKING: any serialized integer values of kArrayItemMissing/kMapItemMissing are stale


class AccessStep(ObjectRef):
    """One step along an object traversal path, used in mismatch reporting.
    AccessStep itself has kTVMFFISEqHashKindConstTreeNode so paths are structurally comparable.
    """
    kind: AccessKind
    key: Any   # str for kAttr/kAttrMissing, int64 for kArrayItem/kArrayItemMissing, Any for kMap*

    @staticmethod
    def Attr(name: str) -> AccessStep: ...          # was: ObjectField() (renamed commit f4ede98)
    @staticmethod
    def AttrMissing(name: str) -> AccessStep: ...   # NEW (commit f4ede98)
    @staticmethod
    def ArrayItem(index: int64) -> AccessStep: ...
    @staticmethod
    def ArrayItemMissing(index: int64) -> AccessStep: ...
    @staticmethod
    def MapItem(key: Any) -> AccessStep: ...
    @staticmethod
    def MapItemMissing(key: Any = None) -> AccessStep: ...
    # Interacts with: AccessPathObj.StepEqual() for PathEqual traversal
    # REMOVED: ObjectField() — use Attr() instead


class AccessPathObj(Object):
    """Parent-pointer tree node for an access path (since commit f4ede98).
    REPLACES the old alias: AccessPath = Array[AccessStep]
    _type_key = "ffi.reflection.AccessPath"
    _type_s_eq_hash_kind = kTVMFFISEqHashKindConstTreeNode
    """
    parent: Optional[ObjectRef]   # None at root; cast to AccessPath to traverse
    step:   Optional[AccessStep]  # None at root
    depth:  int32_t               # 0 at root; = parent.depth + 1
    # Invariant: empty parent ⟺ root (depth == 0)
    # Interacts with: StructuralEqual.GetFirstMismatch (builds paths via Attr/ArrayItem/MapItem)

    def Extend(self, step: AccessStep) -> AccessPath: ...
    def Attr(self, name: str) -> AccessPath: ...
    def AttrMissing(self, name: str) -> AccessPath: ...
    def ArrayItem(self, index: int64) -> AccessPath: ...
    def ArrayItemMissing(self, index: int64) -> AccessPath: ...
    def MapItem(self, key: Any) -> AccessPath: ...
    def MapItemMissing(self, key: Any) -> AccessPath: ...
    def ToSteps(self) -> Array[AccessStep]: ...
    # Walks parent chain, collects into vector, reverses → O(depth)
    def PathEqual(self, other: AccessPath) -> bool: ...
    # Fast path: pointer equality; depth guard; then step-by-step up parent chain
    def IsPrefixOf(self, other: AccessPath) -> bool: ...


class AccessPath(ObjectRef):
    """Ref wrapper for AccessPathObj. REPLACES old alias: AccessPath = Array[AccessStep]."""
    @staticmethod
    def Root() -> AccessPath: ...          # creates root node: parent=None, step=None, depth=0
    @staticmethod
    def FromSteps(steps: Array[AccessStep]) -> AccessPath: ...
    # Builds by repeatedly calling Root()->Extend() for each step
    # Invariant: round-trip: FromSteps(path->ToSteps()) produces PathEqual path

AccessPathPair = Tuple[AccessPath, AccessPath]  # (lhs_path, rhs_path) — unchanged type


# Custom equal/hash attribute protocol (registered via TypeAttrDef):

def __s_equal__(
    self: ObjectRefType,
    other: ObjectRefType,
    cmp: TypedFunction[bool(AnyView lhs, AnyView rhs, bool def_region, AnyView field_name)]
) -> bool:
    """Custom structural equality for a type.
    cmp(lhs, rhs, def_region, field_name) compares sub-values recursively.
    def_region=True: enables map_free_vars_ in the handler (for binding sites like params).
    def_region=False: standard comparison (for body, expressions).
    """
    ...
# Interacts with: TypeAttrColumn("__s_equal__"), StructEqualHandler.s_equal_callback_


def __s_hash__(
    self: ObjectRefType,
    init_hash: uint64_t,
    hash: TypedFunction[uint64_t(AnyView val, uint64_t init_hash, bool def_region)]
) -> uint64_t:
    """Custom structural hash for a type.
    hash callback calls StableHashCombine(init_hash, HashAny(val)) internally.
    def_region=True: enables map_free_vars_ in the handler.
    """
    ...
# Interacts with: TypeAttrColumn("__s_hash__"), StructuralHashHandler.s_hash_callback_
```

### Field-Level Flags for SEqHash

```python
# TVMFFIFieldInfo.flags bits used by StructuralEqual/Hash (registered via AttachFieldFlag):
# kTVMFFIFieldFlagBitMaskSEqHashIgnore = 1 << 3
#   → StructuralEqual/Hash skips this field entirely
#   → Use for: comments, debugging annotations, metadata that doesn't affect semantics

# kTVMFFIFieldFlagBitMaskSEqHashDef    = 1 << 4
#   → The field contains "binding sites" for free variables (e.g., function params)
#   → StructuralEqual uses cmp(lhs, rhs, def_region=True, name) for these fields
#   → Enables alpha-equivalence: two lambdas with same body but different param names compare equal

# Registration via ObjectDef:
# ObjectDef<TFuncObj>()
#     .def_ro("params", &TFuncObj::params, AttachFieldFlag::SEqHashDef())
#     .def_ro("body",   &TFuncObj::body)
#     .def_ro("comment",&TFuncObj::comment, AttachFieldFlag::SEqHashIgnore())
```

## Contracts, Assumptions and Invariants

- All NaN float values compare as equal to each other in `StructuralEqual`, and all hash to the same canonical bit pattern (commit 59a837eb). This ensures NaN in IR nodes doesn't prevent structural matching.
- `kTVMFFISEqHashKindUnsupported` and missing metadata both raise `TypeError` — there is no silent fallback to pointer identity (changed in commit 59a837eb). Callers must set `_type_s_eq_hash_kind` on all types they intend to compare structurally.
- `StructuralEqual.Equal` with `map_free_vars=True` builds a bijection between free variables as it traverses; two structurally equivalent expressions with different variable names are equal.
- `AccessPath` is now a proper `ObjectRef` backed by a parent-pointer tree (`AccessPathObj`), not an alias for `Array<AccessStep>`. Migration: replace `AccessPath({step1, step2})` with `AccessPath::Root()->Attr("x")->ArrayItem(0)` or `AccessPath::FromSteps({...})`.
- `AccessPathObj` builds paths incrementally; `ToSteps()` linearizes on demand in O(depth).
- `AccessStep` itself has `kTVMFFISEqHashKindConstTreeNode` so paths can be structurally compared in tests.
- `AccessStep::ObjectField()` is **removed** since commit f4ede98. Use `AccessStep::Attr()` instead.
- `kArrayItemMissing` shifted from 3→4 and `kMapItemMissing` from 4→5 in commit f4ede98 (new `kAttrMissing=3` inserted). Any serialized integer values of these enum members are stale after that commit.
- AccessPath/AccessStep reflection registrations live in `src/ffi/extra/reflection_extra.cc` (extra-gated) since commit f4ede98. The header file `access_path.h` with type definitions is still always compiled.
- `MakeObjectFromPackedArgs` moved from the always-compiled core to `src/ffi/extra/reflection_extra.cc` (also commit f4ede98) — now extra-only.
- `StructuralEqual.cc` and `StructuralHash.cc` are compiled under `TVM_FFI_USE_EXTRA_CXX_API` (CMake option, default ON). The `TVM_FFI_EXTRA_CXX_API` macro marks their exported symbols.
- For DAG node types (`kTVMFFISEqHashKindDAGNode`), the handler maintains `equal_map_lhs_` and `equal_map_rhs_` — maps from object pointer to partner pointer. Revisiting an already-mapped pair succeeds immediately.
- For `kTVMFFISEqHashKindFreeVar`, the first visit records the pairing in `equal_map_*`. Subsequent visits check that the same pairing holds.

### Failure Modes
- Registering `__s_equal__` without `__s_hash__` (or vice versa) for a type: `StructuralHash` will try `TypeAttrColumn("__s_hash__")` and fall through to field reflection, while `StructuralEqual` calls `__s_equal__`. The two may become inconsistent. Always register both.
- A type with `kTVMFFISEqHashKindDAGNode` used in a recursive cycle (circular graph): the handler will loop indefinitely. The design assumes acyclic object graphs.
- `GetFirstMismatch` on very deep nested structures: the mismatch path grows linearly with depth — no depth limit is enforced.

### Extension Points
- Add custom structural comparison for a type: set `_type_s_eq_hash_kind = kTVMFFISEqHashKindTreeNode` and register `__s_equal__`/`__s_hash__` via `TypeAttrDef<T>()`.
- Opt out specific fields: use `AttachFieldFlag::SEqHashIgnore()` in `ObjectDef`.
- Mark binding sites: use `AttachFieldFlag::SEqHashDef()` to enable alpha-equivalence in those fields.
- The `extra/` subsystem allows downstream code to add new structural-comparison-like passes (e.g., a structural printer) using the same `TypeAttrColumn` mechanism.

### Usage Examples

#### Define a type with alpha-equivalence (function with params + body)
**Context**: a function IR node where variable names should not affect equality.

```cpp
class TFuncObj : public Object {
 public:
  Array<TVar> params;
  Array<ObjectRef> body;
  String comment;  // should be ignored

  static constexpr TVMFFISEqHashKind _type_s_eq_hash_kind = kTVMFFISEqHashKindTreeNode;
  static constexpr const char* _type_key = "test.Func";
  TVM_FFI_DECLARE_FINAL_OBJECT_INFO(TFuncObj, Object);

  bool SEqual(const TFuncObj* other,
              ffi::TypedFunction<bool(AnyView, AnyView, bool, AnyView)> cmp) const {
    if (!cmp(params, other->params, /*def_region=*/true, "params")) return false;
    return cmp(body, other->body, /*def_region=*/false, "body");
  }
  uint64_t SHash(uint64_t init_hash,
                 ffi::TypedFunction<uint64_t(AnyView, uint64_t, bool)> hash) const {
    uint64_t h = hash(params, init_hash, /*def_region=*/true);
    return hash(body, h, /*def_region=*/false);
  }
};

TVM_FFI_STATIC_INIT_BLOCK({
  namespace refl = tvm::ffi::reflection;
  refl::ObjectDef<TFuncObj>()
      .def_ro("params",  &TFuncObj::params,  refl::AttachFieldFlag::SEqHashDef())
      .def_ro("body",    &TFuncObj::body)
      .def_ro("comment", &TFuncObj::comment, refl::AttachFieldFlag::SEqHashIgnore());
  refl::TypeAttrDef<TFuncObj>()
      .def("__s_equal__", &TFuncObj::SEqual)
      .def("__s_hash__",  &TFuncObj::SHash);
});

// Usage:
TVar x("x"), y("y");
TFunc fa({x}, {x}), fb({y}, {y});
assert(refl::StructuralEqual()(fa, fb));  // true — alpha-equivalent
```

#### Getting the first mismatch path
**Context**: debug output showing exactly where two IR expressions differ.

```cpp
Array<int> a = {1, 2, 3};
Array<int> d = {1, 2};
auto diff = refl::StructuralEqual::GetFirstMismatch(a, d);
// diff is Optional<AccessPathPair>
// d is missing the element at index 2

if (diff) {
    // Since commit f4ede98, diff elements are AccessPath objects (parent-pointer tree)
    // not Array<AccessStep> aliases
    auto lhs_path = diff->get<0>();  // AccessPath
    auto lhs_steps = lhs_path->ToSteps();  // linearize to Array<AccessStep>
    assert(lhs_steps[0]->kind == refl::AccessKind::kArrayItem);
    assert(lhs_steps[0]->key.cast<int64_t>() == 2);

    // Fluent builder style (new):
    refl::AccessPath path = refl::AccessPath::Root()->Attr("body")->ArrayItem(1);
    assert(path->depth == 2);

    // Prefix check:
    refl::AccessPath prefix = refl::AccessPath::Root()->Attr("body");
    assert(prefix->IsPrefixOf(path));
}
```

## Implementation Notes
- `StructEqualHandler` and `StructuralHashHandler` are internal handler classes (not part of the public API). They carry all traversal state: `equal_map_lhs_`, `equal_map_rhs_`, `hash_memo_`, `free_var_counter_`, mismatch path accumulators.
- Callback closures (`s_equal_callback_`, `s_hash_callback_`) are lazily built inside the handler the first time custom dispatch is invoked. They capture handler state by raw pointer (not reference) for performance.
- The `def_region` flag in callbacks temporarily flips `map_free_vars_` in the handler to record free-variable pairings. It's reset after the call returns.
- `StableHashBytes` uses an aligned 8-byte fast path (commit ba0ea87d) for `String` and `Bytes` hashing. All NaN values hash to `std::numeric_limits<double>::quiet_NaN()`.
- `ForEachFieldInfoWithEarlyStop` (commit 69f2484f) is used by `StructEqualHandler` to abort field traversal on the first mismatch, returning early without visiting the remaining fields.

## Alternatives & Trade-offs

### Alternative A: Virtual methods on Object (VisitAttrs pattern)
- Pros: No registration overhead; natural OOP design; each node knows how to compare itself.
- Cons: Requires all node classes to implement `VisitAttrs`/`SEqualReduce`/`SHashReduce`; adds virtual methods to every Object subclass; changes are scattered across many files; not C-ABI compatible.

### Alternative B: Per-type comparator registered as a function table (not TypeAttr column)
- Pros: Simpler; function table indexed by type_index.
- Cons: Requires modifying `TVMFFITypeInfo` to add a comparator slot — binary ABI break per new dispatch type; TypeAttrColumn approach adds new dispatch without changing `TVMFFITypeInfo`.

### Decision Record: TypeAttrColumn for Custom Dispatch vs. Dedicated Enum Value

**Decision**: Use `TypeAttrColumn("__s_equal__"/"__s_hash__")` for custom dispatch rather than a dedicated `kTVMFFISEqHashKindCustomTreeNode = 6` enum value.

**Drivers**: The custom enum value was briefly introduced (commit 2ec11f5f) then removed (commit 59a837eb). The key insight: custom dispatch can be detected by a non-null TypeAttrColumn entry regardless of the SEqHashKind value. This means a type can be `kTVMFFISEqHashKindTreeNode` (standard field traversal) but also have `__s_equal__` registered — the custom attr takes precedence. This orthogonality allows future types to combine both, e.g., use custom comparison for selective fields while still having the standard kind for hash memoization behavior.

**Rejected alternative**: A distinct `kTVMFFISEqHashKindCustomTreeNode` value that mandates TypeAttrDef registration. This was more prescriptive but required all custom types to declare a new kind even when their memoization behavior (tree vs DAG) matched an existing kind.

### StructuralKey — Hash-Caching Wrapper for Map Keys (commit 6adc8df7)

`StructuralKey` wraps any `Any` value and pre-computes its structural hash at construction time. This enables `std::unordered_map<StructuralKey, V>` and `Map<Any, Any>` with structural key semantics.

```python
class StructuralKeyObj(Object):
    """type_key = 'ffi.StructuralKey'"""
    key: Any          # Invariant: immutable after construction
    hash_i64: int     # Cached StructuralHash::Hash(key) as int64_t
    # Invariant: hash_i64 == static_cast<int64_t>(StructuralHash::Hash(key)) always

class StructuralKey(ObjectRef):
    def __hash__(self) -> int:
        return self.hash_i64 & 0xFFFFFFFFFFFFFFFF
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, StructuralKey) and ffi.StructuralKeyEqual(self, other)
    # Interacts with: StructuralEqual::Equal for hash-matched pairs

# TypeAttr registration (enables Map<Any,Any> structural key dispatch):
# TypeAttrDef<StructuralKeyObj>()
#   .attr("__any_hash__",  &StructuralKeyHash)
#   .attr("__any_equal__", &StructuralKeyEqual)
# Interacts with: Map<Any, Any> key dispatch via TypeAttrColumn

# Python API:
def structural_equal(lhs, rhs, map_free_vars=False, skip_tensor_content=False) -> bool: ...
def structural_hash(value, map_free_vars=False, skip_tensor_content=False) -> int: ...
def get_first_structural_mismatch(lhs, rhs, ...) -> tuple[AccessPath, AccessPath] | None: ...

# Also registered in this commit: ffi.StructuralEqual global function (was previously missing)
```

## Note: Distinct from RecursiveEq/RecursiveHash

`StructuralEqual`/`StructuralHash` is the **IR-oriented** comparison system with alpha-equivalence, free-variable binding, DAG memoization, and `TVMFFISEqHashKind` dispatch (registered at static-init time). It is intentionally separate from:
- **`RecursiveEq`/`RecursiveHash`** (see `0031-dataclass-ops.md`, commit 6b39efbf): simpler field-by-field comparison for data containers — no alpha-equivalence, no DAG memo, no `TVMFFISEqHashKind`. Uses `ObjectGraphDFS<CompareTraversal>` with `kTVMFFIFieldFlagBitMaskCompareOff`/`HashOff` per-field opt-outs.
- **`AnyHash`/`AnyEqual`** (see `0003-any-anyview.md`, commit 39d9b2b4): controls `std::hash<Any>` and `operator==` for `Any` values — a lower-level primitive with per-type `__any_hash__`/`__any_equal__` TypeAttr columns, not recursive graph traversal.

## Related Design Docs & ADRs
- `.knowledge/design-records/0001-c-abi.md` — `TVMFFISEqHashKind` enum, `TVMFFITypeMetadata`, `TVMFFITypeAttrColumn`, `TVMFFIFieldInfo` flag bits 3 and 4
- `.knowledge/design-records/0006-reflection.md` — `ObjectDef`, `TypeAttrDef`, `AttachFieldFlag`, `ForEachFieldInfoWithEarlyStop`
- `.knowledge/design-records/0002-object-system.md` — `_type_s_eq_hash_kind` static member, `Object` inheritance, `IsInstance`
- `.knowledge/design-records/0007-containers.md` — `Array`, `Map`, `Shape`, `NDArray`, `Bytes` all have specialized comparison branches
- `.knowledge/design-records/0003-any-anyview.md` — `AnyView` type_index dispatch used in `CompareAny`; `__any_hash__`/`__any_equal__` TypeAttr columns
- `.knowledge/design-records/0029-py-class.md` — `@py_class(structure=...)` surfaces SEqHash kinds to Python-defined types
- `.knowledge/design-records/0031-dataclass-ops.md` — `RecursiveEq`/`RecursiveHash` — simpler field-by-field system for data containers
