---
adr: "0001"
title: "Partition Type Index Space into POD, Static, and Dynamic Ranges"
status: "accepted"
date: "2025-05-06"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "type-system"
  - "abi"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
source_ledgers:
  - ".memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md"
---

# ADR-0001: Partition Type Index Space into POD, Static, and Dynamic Ranges

## TL;DR
- The `int32_t type_index` field in `TVMFFIAny` and `TVMFFIObject` is partitioned into three contiguous ranges: POD/special types [0, 64), static builtin objects [64, 128), and dynamically registered objects [128, +inf).
- This partitioning enables O(1) dispatch for common types, guarantees ABI stability for builtins, and provides unbounded extensibility for user-defined types.

## Status
Accepted

## Context
A type-erased value system needs a way to tag every value with its runtime type. The tag must be:
1. Fast to compare (used on every function call argument).
2. Stable across shared library boundaries (C ABI compatibility).
3. Extensible for user-defined types without recompilation of the core library.

Packing all type tags into a single `int32_t` field keeps `TVMFFIAny` at 16 bytes. The question is how to allocate values within that 32-bit space.

## Decision Drivers
- ABI stability: builtin type indices must never change across versions.
- Performance: common type checks should be a single integer comparison, not a string lookup.
- Extensibility: user-defined types must be registrable at runtime without reserving the entire index space upfront.
- IsInstance fast path: subtype checks should be possible via range comparison when types are allocated in contiguous child slots.

## Decision
Partition the `int32_t` type index into three ranges:

| Range | Purpose | Allocation |
|-------|---------|------------|
| [0, 64) | POD and special types (None, int, float, bool, DataType, Device, RawStr, SmallStr, etc.) | Compile-time constants in `TVMFFITypeIndex` enum |
| [64, 128) | Static builtin object types (Object, String, Bytes, Error, Function, Shape, Tensor, Array, Map, Module, List, Dict, etc.) | Compile-time constants in `TVMFFITypeIndex` enum |
| [128, +inf) | Dynamic user-defined object types | Allocated at runtime by `TypeTable::GetOrAllocTypeIndex` |

The boundary constants are:
- `kTVMFFIStaticObjectBegin = 64`
- `kTVMFFIDynObjectBegin = 128`

Within the dynamic range, `TypeTable` uses a child-slot reservation scheme: when a type is registered, it reserves `num_child_slots + 1` contiguous indices. Child types are first allocated from the parent's reserved pool, enabling `IsInstance` via a single range check. If the pool is exhausted, indices overflow into the tail of the index space, and `IsInstance` falls back to ancestor-table lookup.

## Alternatives Considered
### Flat sequential allocation
- Pros: Simple. No wasted indices.
- Cons: No fast subtype check. ABI unstable (indices depend on registration order). No guaranteed ranges for POD vs object.

### String-based type tags
- Pros: Completely extensible. Human-readable.
- Cons: Slow comparison (string hash + equality). Larger tag (pointer vs. int32). Cannot be used as array index.

### Larger partitions (e.g., [0, 256) for static)
- Pros: More room for future builtins.
- Cons: Wastes the child-slot contiguous range, pushing dynamic types further out and reducing slot-range IsInstance effectiveness.

## Why This Option Won
- 64 slots for POD is generous (only 13 used so far) and keeps the boundary at a power of two, enabling bitmask checks.
- 64 slots for static objects (15 used, including `kTVMFFIOpaquePyObject=74` added in `91d69f0`) leaves headroom for future builtins without breaking the boundary. The static indices were reordered in commit `777cf8d` to group simple C-ABI types before complex C++ types (see [ADR-0016](.memory/ADRs/0016-reorder-static-type-indices.md)).
- Dynamic types starting at 128 means the entire [0, 128) range is known at compile time and can be hardcoded in foreign language bindings.
- The child-slot reservation within the dynamic range gives O(1) IsInstance for the common case while handling overflow gracefully.

## Consequences
### Positive
- O(1) type dispatch for all POD types (single comparison against range boundary).
- ABI-stable: adding a new builtin at index 77 does not shift any dynamic type.
- IsInstance fast path via slot-range check avoids ancestor table lookup for most types.

### Negative
- The static ranges [0, 64) and [64, 128) can eventually run out if many new builtins are added. This would require a breaking ABI change.
- Child-slot reservation can waste indices if a type reserves N slots but fewer than N subtypes are ever registered.

### Risks
- If the 64-slot static range fills up, a new ABI version is required. Mitigated by the current low occupancy (13/64 for objects).
- Overflow from child slots to tail allocation breaks the contiguous property, degrading IsInstance to O(depth) ancestor walk. Mitigated by generous initial slot allocation.

## Implementation Notes
- `TVMFFITypeIndex` enum in `include/tvm/ffi/c_api.h` defines all compile-time constants.
- `TypeTable` in `src/ffi/object.cc` manages runtime allocation with `GetOrAllocTypeIndex`.
- Child slot reservation: `num_slots = num_child_slots + 1` (1 for the type itself).
- When `parent->allocated_slots + num_slots > parent->num_slots`, overflow appends to `type_counter_`.

## Validation
- `tests/cpp/test_ffi_object.cc` exercises type registration and IsInstance checks.
- Static type indices are validated by compile-time enum values that must match across all bindings.

## Migration and Rollback
- This is a foundational design established at the root commit. Changing the partition boundaries requires a major ABI version bump.

## Related Design Docs
- [.memory/designs/0001-type-erased-any-value-system.md](.memory/designs/0001-type-erased-any-value-system.md)
- [.memory/designs/0002-object-system-and-reference-counting.md](.memory/designs/0002-object-system-and-reference-counting.md)
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)

## Related Diagrams
- [.memory/diagrams/0001-any-value-memory-layout.md](.memory/diagrams/0001-any-value-memory-layout.md)

## Evidence Matrix
- Type index enum definition -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `include/tvm/ffi/c_api.h` lines 84-192
- TypeTable child-slot allocation -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `src/ffi/object.cc` lines 121-188
- kTVMFFIStaticObjectBegin=64, kTVMFFIDynObjectBegin=128 -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 132, 186

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Monitor static range occupancy as new builtin types are added (15/64 used as of `91d69f0`).
- Consider increasing the static range boundary if occupancy exceeds 75%.
- See [ADR-0016](.memory/ADRs/0016-reorder-static-type-indices.md) for the pre-ABI-freeze reordering of static object indices.
