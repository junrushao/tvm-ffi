---
scope:
  - ".knowledge/designs/c-abi.md"
  - ".knowledge/designs/object-system.md"
  - ".knowledge/ADRs/003-type-index-ranges.md"
---
# ADR-015: Type Index Simplicity Ordering within Static Object Range

**TL;DR**:
- Reordered the static object type indices `[69-72]` to group "simple C ABI" objects (Shape=69, Tensor=70) before "more complex" objects (Array=71, Map=72), establishing a deliberate ordering convention within the static object range. (NDArray was renamed to Tensor in 3a551d8.)
- This reordering is ABI-breaking but was done pre-freeze to simplify C ABI reasoning: indices 69-70 represent objects whose layouts can be fully described by C structs (`TVMFFIShapeCell`, `DLTensor`), while 71-72 are C++ container objects requiring more complex handling.

## Context
The static object type indices in the `[64, 128)` range were originally assigned in order of implementation: Array=69, Map=70, Shape=71, NDArray=72. This ordering did not reflect any semantic property of the types.

As the C ABI stabilized, a natural grouping emerged: some objects (Shape, NDArray) have layouts fully describable by C structs and can be handled by pure-C code, while others (Array, Map) are C++ container objects with internal pointer structures that are opaque to C consumers.

Usecases:
- **C-only consumers**: Embedded systems or non-C++ language bindings that want to handle a subset of FFI types using only C struct access. They can now check `type_index <= 70` to identify "simple" types.
- **ABI documentation clarity**: Grouping by complexity makes the type index table self-documenting.

Design Decisions:
- Reorder: Shape=69, NDArray=70 (simple C ABI), then Array=71, Map=72 (more complex). Module stays at 73.
- Mark the boundary with a `// more complex objects` comment divider in the enum.
- This is a one-time ABI break done before the ABI freeze.

## Alternatives

### Alternative A: Keep original ordering (Array=69, Map=70, Shape=71, NDArray=72)
- Description: No reordering; keep the implementation-order assignment.
- Pros: No ABI break; no code changes needed; existing hardcoded indices in Cython/Rust bindings remain valid.
- Cons: The ordering has no semantic meaning, making it harder to reason about which types have pure-C layouts. Future C-only consumers cannot use a simple range check to identify C-friendly types.
- Why rejected: The ABI is not yet frozen, so this is the optimal time to establish a meaningful ordering convention. The cost of updating hardcoded indices in Cython and Rust bindings is a one-time effort.

### Alternative B: Use a separate flag/attribute instead of ordering
- Description: Add a `is_c_abi_simple` flag to `TVMFFITypeInfo` rather than relying on index ordering.
- Pros: Decouples the property from the index value; no ABI break; extensible to future types.
- Cons: Adds complexity to `TVMFFITypeInfo`; every consumer must query the flag instead of doing a simple range check; the flag itself would be a new ABI addition.
- Why rejected: The ordering convention is simpler and has zero runtime cost. A flag would add a per-type metadata field that is redundant with information already encoded in the index position.

## Implementation Notes
- Updated enum values in `c_api.h`: `kTVMFFIShape=69, kTVMFFITensor=70` (renamed from `kTVMFFINDArray` in 3a551d8)`, kTVMFFIArray=71, kTVMFFIMap=72`.
- Updated Cython `base.pxi` to match new index values.
- Same commit also renamed `override` -> `allow_override` in `TVMFFIFunctionSetGlobal` and `TVMFFIFunctionSetGlobalFromMethodInfo` parameter names (source-level only, no ABI impact since the parameter is `int`).
- Same commit added `ModuleObj::GetFunctionMetadata` virtual method and `ffi.ModuleGetFunctionMetadata` global function.
- Version bump from 0.1.0a2 to 0.1.0a3.

## Related Design Docs
- `.knowledge/designs/c-abi.md` -- Type index ranges, TVMFFIObject layout
- `.knowledge/designs/object-system.md` -- Type index hierarchy
- `.knowledge/ADRs/003-type-index-ranges.md` -- Type index partitioning
