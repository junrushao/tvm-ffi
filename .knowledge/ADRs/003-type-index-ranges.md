# ADR-003: Type Index Range Partitioning

> Status: Accepted
> Decided in: commit 7d34eb8 ("[REFACTOR] Introduce and modernize FFI system")

## Context

The unified type index system (ADR-001) requires partitioning the integer type index
space to accommodate:
- POD types with fixed compile-time indices
- Built-in object types with fixed compile-time indices
- User-defined object types with runtime-allocated indices
- Fast IsInstance checks without hash table lookups

## Decision

Partition the `int32_t` type index space into three ranges:

```
[-1]           kTVMFFIAny         -- Sentinel for reflection annotations
[0, 64)        POD/special types  -- None=0, Int=1, Bool=2, Float=3, OpaquePtr=4,
                                     DataType=5, Device=6, DLTensorPtr=7, RawStr=8,
                                     ByteArrayPtr=9, ObjectRValueRef=10,
                                     SmallStr=11, SmallBytes=12, ...
[64, 128)      Static objects     -- Object, String, Bytes, Error, Function, Array, Map, ...
[128, +inf)    Dynamic objects    -- Allocated at runtime by TVMFFITypeGetOrAllocIndex
```

Note: `kTVMFFISmallStr = 11` and `kTVMFFISmallBytes = 12` were added in commit 49e2ed4 for the small-string optimization. The POD range now has 13 allocated entries out of 64 slots.

Within the static object range, each built-in type gets a fixed index. As of commit 91d69f0, the ordering is:
`kTVMFFIObject=64`, `kTVMFFIStr=65`, `kTVMFFIBytes=66`, `kTVMFFIError=67`, `kTVMFFIFunction=68`, `kTVMFFIShape=69`, `kTVMFFITensor=70` (renamed from `kTVMFFINDArray` in 3a551d8), `kTVMFFIArray=71`, `kTVMFFIMap=72`, `kTVMFFIModule=73`, `kTVMFFIOpaquePyObject=74`.

Note: Indices 69-72 were reordered in commit 777cf8d to group "simple C ABI" objects (Shape=69, NDArray=70) before "more complex" objects (Array=71, Map=72). See `.knowledge/ADRs/015-type-index-simplicity-ordering.md`. Index 74 was allocated for `kTVMFFIOpaquePyObject` in commit 91d69f0.

The range `[75, 128)` is reserved for future static types.

For dynamic types, a child-slot optimization is used: a parent type can reserve
`_type_child_slots` contiguous indices after its own index. If a child's index falls
in `[parent_index, parent_index + child_slots + 1)`, the `IsInstance` check is a
simple range comparison (no table lookup needed).

## Consequences

### Positive

- `IsInstance<T>()` for final types reduces to a single integer comparison
- `IsInstance<T>()` for base types with child slots is a range check (two comparisons)
- POD values are easily distinguished from object references by
  `type_index < kTVMFFIStaticObjectBegin` (single comparison)
- Static types have predictable indices that language bindings can hardcode
- The ancestor table fallback handles arbitrary type hierarchies when child
  slots overflow

### Negative

- The 64-slot POD range and 64-slot static object range are fixed at compile time.
  If more static types are needed, the `kTVMFFIDynObjectBegin=128` boundary would
  need to change (ABI break).
- Child slot allocation is first-come-first-served; if a parent's child slots are
  exhausted, new children fall into the overflow range and require table lookups

### Allocation Algorithm (TypeTable via TVMFFITypeGetOrAllocIndex, renamed from TVMFFIGetOrAllocTypeIndex in 1a85688)

1. If `static_type_index >= 0`: place at the given index (compile-time assignment)
2. Else try to allocate from parent's reserved child slots:
   `parent.type_index + parent.allocated_slots` (contiguous with parent)
3. If parent's slots are full and overflow is allowed: allocate from global counter
   (starts at 128, grows monotonically)
4. If overflow is not allowed: error (capacity exceeded)
