---
scope:
  - "0001-c-abi"
  - "0002-any-system"
  - "0003-object-system"
---
# Type Index Partitioning: POD / Static Object / Dynamic Object

**TL;DR**: `TVMFFITypeIndex` is partitioned into three contiguous ranges -- POD `[0, 64)`, static objects `[64, 128)`, dynamic objects `[128, +inf)` -- to enable O(1) discrimination between POD values and heap objects, and to provide fixed indices for built-in types while allowing unlimited runtime-allocated types.

## Context

The FFI stores values of different types in a single 16-byte `TVMFFIAny` container. The runtime must frequently answer two questions:

1. **Is this value a heap object?** (needed for `IncRef`/`DecRef` decisions in `Any` copy/destroy)
2. **Is this value an instance of type T?** (needed for `IsInstance` and `cast<T>`)

A flat, fully dynamic type index would require a table lookup for question 1, adding overhead to every `Any` copy/destroy operation. A fixed enumeration would limit extensibility.

Usecases:
- `Any::reset()` must decide whether to call `DecRef`. With partitioning, this is a single comparison: `if (type_index >= 64) DecRef(v_obj)`.
- `IsInstance<T>` can use range checks within the static object partition for built-in types (e.g., `kTVMFFIStr = 65` is known at compile time).
- User-defined types get indices from `[128, +inf)` without conflicting with built-in types.

Design Decisions:
- **Three-range partition**: POD `[0, 64)` for on-stack values (int, float, bool, DLDevice, etc.), static objects `[64, 128)` for built-in object types (String, Error, Function, Array, Map, Shape, NDArray, Module), dynamic objects `[128, +inf)` for user-defined types allocated at runtime.
- **64-slot ranges**: 64 slots for POD and 64 for static objects. Currently 11 POD indices and 10 static object indices are used, leaving room for growth without ABI breaks.
- **Single comparison for object detection**: The hot path `type_index >= kTVMFFIStaticObjectBegin` (i.e., `>= 64`) is a single branch. This is executed on every `Any` copy, move, and destroy.

**Alternatives considered**:

1. **Single flat namespace** (all types start at 0, dynamically allocated):
   - Pros: No artificial range limits, simpler allocation.
   - Cons: Cannot distinguish POD from object at O(1). Would need a bitmap or table lookup in every `Any` destructor. Rejected for performance.

2. **Fully dynamic allocation** (even built-in types get runtime indices):
   - Pros: Maximum flexibility.
   - Cons: Built-in type indices would not be compile-time constants, preventing `if constexpr` optimizations in `IsInstance` and `TypeTraits`. Rejected because compile-time dispatch is important for hot paths.

3. **Bit-flag encoding** (use high bits to encode POD/object):
   - Pros: More encoding space.
   - Cons: Complicates type index arithmetic (range checks for `IsInstance`). The linear partitioning is simpler and sufficient given the 2^31 dynamic range.

**Consequences**:
- Built-in types have stable, well-known indices that language bindings can hard-code.
- The POD range limit of 64 is unlikely to be hit (11 used), but if it is, adding a new POD type in the `[11, 63)` range requires updating all bindings that switch on type indices.
- The static object range limit of 64 (`[64, 127)`) accommodates 10 built-in object types with 54 remaining. Overflow into the dynamic range would work but lose the compile-time index advantage.

## Implementation Notes

- `TVMFFITypeIndex` is an `int32_t`-based enum (not `uint32_t`) to accommodate the sentinel `kTVMFFIAny = -1`.
- `kTVMFFIStaticObjectEnd` is a marker, not a usable index. The next available static index is `kTVMFFIStaticObjectEnd`.
- `TypeTable` constructor pre-allocates `kTVMFFIDynObjectBegin = 128` null entries, then initializes built-in type entries.
- Evidence: `include/tvm/ffi/c_api.h:49-131` (TVMFFITypeIndex enum), `src/ffi/object.cc:237-258` (TypeTable constructor), commit `7d34eb8`.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- Full type index layout diagram
- [`.knowledge/designs/0002-any-system.md`](../designs/0002-any-system.md) -- How partitioning enables O(1) POD/object discrimination in Any
- [`.knowledge/ADRs/0003-slot-based-type-allocation.md`](0003-slot-based-type-allocation.md) -- How dynamic indices are allocated within the `[128, +inf)` range
