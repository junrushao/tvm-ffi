# Reflection-Based Structural Equal and Hash

- Doc ID: 005-structural-equal-hash
- Status: Approved
- Last Updated: 2026-02-21
- Owners: Tianqi Chen

## Overview

The TVM FFI provides `StructuralEqual` and `StructuralHash` implementations
that compare and hash objects by recursively traversing their fields using the
reflection system. These replace the legacy `SEqualReduce`/`SHashReduce`
virtual method mechanism. The system supports field-by-field comparison for
standard registered types, custom comparison functions for types with complex
semantic equality, and structured mismatch reporting via access paths.

This functionality lives in the `ffi::` namespace under the `include/tvm/ffi/extra/`
header directory, establishing it as "extra" functionality outside the core FFI
reflection API.

## Key Design

### Reflection-driven field traversal

For types with `kTVMFFISEqHashKindTreeNode` (the standard registered kind),
`StructuralEqual` and `StructuralHash` iterate over all fields registered via
`ObjectDef<T>` using the reflection system's field metadata. For each field:

- **Equality**: Recursively compares the field values. Handles `Object`
  subtypes by dispatching to their own structural equality, and primitive types
  (int, float, string) by direct comparison.
- **Hashing**: Recursively hashes field values, combining them into a single
  hash using a stable hash combiner (`StableHashCombine`).

If a type's `TVMFFITypeMetadata` is missing or its `s_eq_hash_kind` is
`kTVMFFISEqHashKindUnsupported`, equality/hashing throws `TypeError` (`59a837e`).

### Custom __s_equal__ / __s_hash__ via TypeAttrDef

Types that need semantic equality beyond field-by-field comparison (e.g.,
functions where parameters are binding sites) can register custom comparison
functions via `TypeAttrDef` (`2ec11f5`, `59a837e`):

```cpp
TypeAttrDef<MyObj>()
    .def("__s_equal__", &MyObj::SEqual)
    .def("__s_hash__", &MyObj::SHash);
```

The dispatch logic checks the `TypeAttrColumn` for `__s_equal__` /
`__s_hash__` first. If a custom function exists, it is called; otherwise,
the default field-iteration logic runs. This approach was chosen over a
dedicated `kTVMFFISEqHashKindCustomTreeNode` enum value, which was introduced
temporarily (`2ec11f5`) and removed two days later (`59a837e`) in favor of
the simpler column-lookup approach.

### Free variable binding support

Types with `kTVMFFISEqHashKindFreeVar` support variable-binding semantics in
structural equality. When two free variables are compared, they are recorded
in a mapping table; subsequent references must be consistent. This enables
alpha-equivalence checks for IR expressions with binders.

### AccessPath mismatch reporting

When structural equality fails, the `GetFirstMismatch` method returns an
`AccessPathPair` that describes the exact access path to the first differing
field. The path is composed of `AccessStep` elements (`9445fe7`):

| AccessKind         | Meaning                            |
|--------------------|------------------------------------|
| `kAttr`            | Object attribute access             |
| `kArrayItem`       | Array element by index              |
| `kMapItem`         | Map entry by key                    |
| `kAttrMissing`     | Object attribute missing (error)    |
| `kArrayItemMissing`| Array item missing (error)          |
| `kMapItemMissing`  | Map item missing (error)            |

(Note: the `kArrayItem`/`kMapItem` names were established in `3fc0391`,
replacing earlier `kArrayIndex`/`kMapKey` names. The `kObjectField` name was
renamed to `kAttr` in `f4ede98`.)

In August 2025 (`f4ede98`), `AccessPath` was refactored from a flat
`Array<AccessStep>` alias to a parent-pointing tree structure
(`AccessPathObj`/`AccessPath`) with `parent`, `step`, and `depth` fields.
This is more compact when multiple paths share a common prefix, which is the
typical case in structural equality mismatch reporting. The fluent builder
API (`Root()->Attr("body")->ArrayItem(1)`) replaces array initializer lists.
See design doc `004-reflection-system.md` for the full AccessPath API.

The global function `ffi.GetFirstStructuralMismatch` exposes this to Python.

### NaN handling

Float comparison handles NaN correctly (`59a837e`): two NaN values are
considered structurally equal (since they represent the same "not a number"
sentinel). For hashing, NaN values are normalized to a quiet NaN bit pattern
before hashing to ensure consistent hash values.

### String and byte comparison optimization

String equality and hashing were optimized (`ba0ea87`):

- `Bytes::memequal` uses `std::memcmp` for fast byte-level equality,
  replacing character-by-character comparison.
- `StableHashBytes` uses aligned 64-bit loads when data alignment permits,
  with a separate unaligned path for misaligned data.
- `String::compare(const char*)` avoids calling `strlen` by comparing
  inline.

These optimizations affect the hot path for map lookups and structural
equality of string-typed fields.

### Core/extra boundary

`StructuralEqual` and `StructuralHash` were initially placed in
`include/tvm/ffi/reflection/` and the `reflection` namespace. In `3fc0391`,
they were moved to `include/tvm/ffi/extra/` and the `ffi` namespace. This
establishes a clear boundary:

- **Core** (`include/tvm/ffi/reflection/`): Registration and field access APIs
  (`ObjectDef`, `GlobalDef`, `TypeAttrDef`, `ForEachFieldInfo`).
- **Extra** (`include/tvm/ffi/extra/`): Optional higher-level functionality
  that builds on the core reflection API (`StructuralEqual`, `StructuralHash`).

The `TVM_FFI_USE_EXTRA_CXX_API` CMake option (`2ec11f5`) controls whether the
extra sources are compiled.

### StructuralKey wrapper (February 2026)

`StructuralKey` (`6adc8df`, `include/tvm/ffi/extra/structural_key.h`) is a
wrapper object that caches a structural hash and registers `__any_hash__` and
`__any_equal__` type attributes on `StructuralKeyObj`. This enables using
structural equality semantics as a key in `Map<Any, Any>` or C++
`std::unordered_map<StructuralKey, T>` without manual hash caching.

Python-side, `tvm_ffi.StructuralKey` provides `__hash__` and `__eq__` delegates,
and `tvm_ffi.structural_equal`, `tvm_ffi.structural_hash`,
`tvm_ffi.get_first_structural_mismatch` are promoted to top-level API functions.

### Cycle detection for mutable containers (February 2026)

With the introduction of `List` and `Dict` (mutable containers that can form
reference cycles), the structural hash and equality implementations were
updated (`9513c2f`, `c1af3b3`) to detect cycles during traversal. The
implementations track visited objects and correctly handle back-references
without infinite recursion.

## APIs

### C++ API

```cpp
// Structural equality comparator (in ffi:: namespace, include/tvm/ffi/extra/structural_equal.h).
class StructuralEqual {
  // Static method with full control over free-variable mapping and tensor content.
  static bool Equal(const Any& lhs, const Any& rhs,
                    bool map_free_vars = false,
                    bool skip_tensor_content = false);

  // Static method returning the first mismatch path, or nullopt if equal.
  static Optional<reflection::AccessPathPair> GetFirstMismatch(
      const Any& lhs, const Any& rhs,
      bool map_free_vars = false,
      bool skip_tensor_content = false);

  // Functor shortcut: Equal(lhs, rhs, false, true).
  bool operator()(const Any& lhs, const Any& rhs) const;
};

// Structural hash (in ffi:: namespace, include/tvm/ffi/extra/structural_hash.h).
class StructuralHash {
  // Static method with full control.
  static uint64_t Hash(const Any& value,
                       bool map_free_vars = false,
                       bool skip_tensor_content = false);

  // Functor shortcut: Hash(value).
  uint64_t operator()(const Any& value) const;
};
```

### Global functions

| Function name                    | Description                          |
|----------------------------------|--------------------------------------|
| `ffi.GetFirstStructuralMismatch` | Returns mismatch path or null        |
| `ffi.StructuralHash`            | Returns structural hash as int       |

### Custom function signatures

Custom `__s_equal__` functions are called as packed functions with signature:
`(ObjectRef lhs, ObjectRef rhs, Function callback) -> bool`

where `callback` is a `Function` wrapping
`(AnyView lhs, AnyView rhs, bool def_region, AnyView field_name) -> bool`.

Custom `__s_hash__` functions are called as packed functions with signature:
`(ObjectRef obj, int64_t init_hash, Function callback) -> uint64_t`

where `callback` is a `Function` wrapping
`(AnyView val, uint64_t init_hash, bool def_region) -> uint64_t`.

## Implementation

Key files:
- `include/tvm/ffi/extra/base.h` -- `TVM_FFI_EXTRA_CXX_API` macro
- `include/tvm/ffi/extra/structural_equal.h` -- `StructuralEqual` class
- `include/tvm/ffi/extra/structural_hash.h` -- `StructuralHash` class
- `include/tvm/ffi/reflection/access_path.h` -- `AccessPathObj`, `AccessPath`, `AccessStep`, `AccessPathPair`
- `src/ffi/extra/structural_equal.cc` -- Equality implementation with custom dispatch
- `src/ffi/extra/structural_hash.cc` -- Hash implementation with custom dispatch
- `src/ffi/extra/reflection_extra.cc` -- `AccessPath` reflection registrations (moved from `src/ffi/reflection/access_path.cc` in `f4ede98`)
- `include/tvm/ffi/string.h` -- `Bytes::memequal`, `Bytes::memncmp`
- `include/tvm/ffi/base_details.h` -- `StableHashBytes` (aligned/unaligned)

Tests:
- `tests/cpp/extra/test_structural_equal_hash.cc` -- Array, Map, nested container, FreeVar, CustomTreeNode tests
- `tests/cpp/test_string.cc` -- `String::Compare`, `String::BytesHash` tests

## History
- 2025-07-19: `StructuralEqual`, `StructuralHash`, `AccessPath` introduced in `reflection/` (`9445fe7`)
- 2025-07-22: `TypeAttrDef`/`TypeAttrColumn` formalized for custom dispatch (`162d600`)
- 2025-07-26: `kTVMFFISEqHashKindCustomTreeNode` added; `TVM_FFI_USE_EXTRA_CXX_API` CMake option added (`2ec11f5`)
- 2025-07-28: `kTVMFFISEqHashKindCustomTreeNode` removed; dispatch unified via `TypeAttrColumn` lookup; NaN handling added (`59a837e`)
- 2025-07-29: Legacy `_type_has_method_sequal_reduce`/`_type_has_method_shash_reduce` removed from `Object` (`e52aed5`)
- 2025-07-30: String equality/hash optimized with `memequal` and aligned loads (`ba0ea87`)
- 2025-07-30: `StructuralEqual`/`StructuralHash` moved to `ffi/extra/`; `AccessKind` enum values renamed (`3fc0391`)
- 2025-07-31: `SmallMapObj::CreateFromRange` fixed for duplicate keys (`0342d85`)
- 2025-08-06: `AccessPath` refactored to parent-pointing tree structure; `kObjectField` renamed to `kAttr` (`f4ede98`)
- 2026-02-13: Cycle detection added for `List` traversal in structural hash/equal (`9513c2f`)
- 2026-02-16: `StructuralKey` introduced for structural-equality-based container keys; `ffi.StructuralEqual` global function registered (`6adc8df`)
- 2026-02-19: Cycle detection extended for `Dict` traversal (`c1af3b3`)

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-07-31-0966C36-0342D85.md`
  - `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
  - `.repo-knowledge/ranges/2026-02-21-B1611E0-ECC7471.md`
- Related ADRs: `.repo-knowledge/adr/003-visitattrs-to-reflection-migration.md`
- Related design docs:
  - `.repo-knowledge/design/004-reflection-system.md`
  - `.repo-knowledge/design/003-c-abi-stability.md`
