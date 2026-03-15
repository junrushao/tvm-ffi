---
scope:
  - "0001-c-abi-layer"
  - "0003-object-system"
---
# Type Index Range Partitioning

**TL;DR**: The decision to partition `TVMFFITypeIndex` into three ranges — POD `[0,64)`, static objects `[64,128)`, dynamic objects `[128,+inf)` — to enable fast type dispatch and extensibility.

## Context
- Every `TVMFFIAny` and `TVMFFIObject` carries a `type_index` discriminator. The runtime must quickly determine: is this a POD value? Is it a known object type? Is it a user-defined type?
- Some object types (Object, String, Error, Function, Array, Map, Shape, Tensor, Module) are fundamental and should have compile-time-known indices for fast dispatch (no table lookup needed).
- User-defined types must be accommodated without modifying the core code.

Usecases:
- `Any::reset()` checks `type_index >= kTVMFFIStaticObjectBegin` to decide if DecRef is needed. This single comparison replaces a table lookup.
- Language bindings can switch on known static type indices (65=String, 67=Error, 68=Function) for fast-path handling.
- Plugin libraries register new types at runtime, getting indices >= 128.

Design Decisions:
- **Three-range partition**:
  - `[-1]`: `kTVMFFIAny` — sentinel for reflection (field annotated as "any type"), never appears at runtime.
  - `[0, 64)`: POD and special types. These are **never** reference-counted. The value lives entirely within the 8-byte union of `TVMFFIAny`. Includes small string/bytes inline storage: `kTVMFFISmallStr=11`, `kTVMFFISmallBytes=12`.
  - `[64, 128)`: Static object types with compile-time-known indices. These are reference-counted. Core types like String, Function, Array get permanent indices.
  - `[128, +inf)`: Dynamic object types allocated at runtime via `TVMFFIGetOrAllocTypeIndex`. Each new type gets a unique index.
- **Gap between 64 and 128**: Allows up to 64 static object types without colliding with dynamic indices. Currently 11 are used (64-74, with `kTVMFFIOpaquePyObject = 74` as the last static object type), leaving room for 53 more.
- **Complexity-ordered sub-grouping**: Within the static object range, indices are grouped by ABI complexity. Indices 64-70 are "simple" types with pure C ABI layouts (Object, String, Bytes, Error, Function, Shape, Tensor), while indices 71+ are "complex" types that may require C++ (Array, Map, Module, OpaquePyObject). This ordering was introduced in commit 777cf8d to prepare for ABI freeze.
- **Child slot optimization**: Within the dynamic range, a base type can reserve N child slots. Its children get consecutive indices `[base, base+N+1)`, enabling O(1) `IsInstance` via range check.

## Implementation Notes
- `kTVMFFIStaticObjectBegin = 64` is the dividing line for ownership: `type_index >= 64` means the `TVMFFIAny.v_obj` field holds a refcounted pointer.
- `kTVMFFIStaticObjectEnd = 75` (after `kTVMFFIOpaquePyObject = 74`).
- `kTVMFFIDynObjectBegin = 128` is where runtime allocation starts. The gap between 75 and 128 is intentional padding for future static types.
- `TVMFFIGetOrAllocTypeIndex` handles both static registration (when `static_type_index >= 0`, it populates the type table at that index) and dynamic allocation (when `static_type_index == -1`, it allocates the next available index >= 128).
- `IsObjectInstance<T>` exploits the partitioning: for final types, a single equality check; for non-final types with child slots, a range check; for the general case, an ancestor table lookup.
- Alternative considered: flat enumeration (all types get sequential indices) — rejected because it prevents the efficient `>= kTVMFFIStaticObjectBegin` ownership check and would require a lookup table for every type discrimination.
- Alternative considered: string-based type keys only — rejected because string comparison is too slow for hot-path type dispatch. Type indices enable integer comparison.

## Related Design Docs
- [0001-c-abi-layer.md](.knowledge/designs/0001-c-abi-layer.md)
- [0003-object-system.md](.knowledge/designs/0003-object-system.md)
- [0002-any-value-system.md](.knowledge/designs/0002-any-value-system.md)
