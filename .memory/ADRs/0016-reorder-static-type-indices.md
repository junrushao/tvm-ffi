---
adr: "0016"
title: "Reorder Static Type Indices to Group Simple C-ABI Objects Before Complex C++ Objects"
status: "accepted"
date: "2025-08-30"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "abi"
  - "type-system"
source_commits:
  - "777cf8d51f2054d96e0413b7406ed38ef43a7b39"
source_ledgers:
  - ".memory/commits/2025-08-30-777cf8d51f2054d96e0413b7406ed38ef43a7b39.md"
---

# ADR-0016: Reorder Static Type Indices to Group Simple C-ABI Objects Before Complex C++ Objects

## TL;DR
- Static object type indices in `c_api.h` were reordered so that simple C-ABI-only types (String, Bytes, Error, Function, Shape, NDArray) occupy lower indices, and complex C++-dependent types (Array, Map, Module) follow.
- This is a deliberate pre-ABI-freeze breaking change enabling future C-only consumers to handle the simple subset without C++ dependencies.

## Status
Accepted

## Context
The static type index range [64, 128) in `TVMFFITypeIndex` assigns fixed indices to builtin object types. Before this change, the ordering was: Object=64, String=65, Bytes=66, Error=67, Function=68, Array=69, Map=70, Shape=71, NDArray=72, Module=73. This mixed simple C-ABI types (whose struct layouts are fully defined in `c_api.h`) with complex C++ types (Array, Map) whose internals require C++ to manipulate.

A future design goal is to allow lightweight C-only consumers (e.g., embedded runtimes, WASM toolchains) to handle a subset of FFI types without linking against C++ code. Grouping simple types first in the index space makes range checks trivial: `type_index < kTVMFFIFirstComplexType` identifies types that can be handled with pure C.

## Decision Drivers
- Enable C-only consumers to identify and handle simple types via a single range check.
- Align the index ordering with conceptual complexity: POD-like C-ABI types first, then complex container types.
- Must be done before the ABI freeze (during the 0.1.x pre-release window).

## Decision
Reorder the static type indices as follows:

| Old Index | New Index | Type |
|-----------|-----------|------|
| 64 | 64 | Object (unchanged) |
| 65 | 65 | String (unchanged) |
| 66 | 66 | Bytes (unchanged) |
| 67 | 67 | Error (unchanged) |
| 68 | 68 | Function (unchanged) |
| 71 | 69 | Shape (moved up) |
| 72 | 70 | NDArray (moved up) |
| 69 | 71 | Array (moved down) |
| 70 | 72 | Map (moved down) |
| 73 | 73 | Module (unchanged) |

The reordering groups types as:
1. **Simple C-ABI types** [64-70]: Object, String, Bytes, Error, Function, Shape, NDArray -- all have struct layouts fully defined in `c_api.h`.
2. **Complex C++ types** [71-73]: Array, Map, Module -- require C++ internals (templates, virtual dispatch) for manipulation.

## Alternatives Considered
### Keep existing ordering
- Pros: No ABI break. No code changes needed.
- Cons: Future C-only consumer would need a bitmask or set of indices instead of a simple range check. Misses the pre-freeze window.

### Use a separate flag in TypeInfo instead of index ordering
- Pros: No reordering needed. Extensible.
- Cons: Requires an additional field in `TVMFFITypeInfo`. A range check is faster and simpler than a flag lookup.

## Why This Option Won
- The reordering is a one-time ABI break in the pre-release window (version `0.1.0a3`), when downstream consumers are still adapting.
- Range checks (`index <= kTVMFFINDArray`) are the simplest and fastest mechanism for C-only consumers.
- The conceptual ordering (simple before complex) makes the API more intuitive.

## Consequences
### Positive
- C-only consumers can identify simple types with a single comparison.
- The index ordering now reflects conceptual complexity, aiding documentation and understanding.

### Negative
- **ABI-breaking**: Any code that hardcodes type index values for Array (69), Map (70), Shape (71), or NDArray (72) must be updated.
- Cython `base.pxi` enum values must be synchronized.

### Risks
- Downstream code that hardcodes old type index values will silently misidentify types. Mitigated by the fact that this is a pre-release version and the Cython layer was updated in the same commit.

## Implementation Notes
- `include/tvm/ffi/c_api.h`: `kTVMFFIShape` changed from 71 to 69, `kTVMFFINDArray` from 72 to 70, `kTVMFFIArray` from 69 to 71, `kTVMFFIMap` from 70 to 72.
- `python/tvm_ffi/cython/base.pxi`: Enum constants updated to match.
- Version bumped to `0.1.0a3`.

## Validation
- All existing tests pass with the new index values (C++, Python, Rust).
- The Cython binding layer's `make_ret()` switch uses symbolic constants, so the reordering is transparent there.

## Migration and Rollback
- All bindings must update their hardcoded type index values to match the new `c_api.h`.
- Rollback would require another index reorder (another ABI break), which is only possible in the pre-release window.

## Related Design Docs
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)

## Related Diagrams
- None

## Evidence Matrix
- Index reorder in c_api.h -> `.memory/commits/2025-08-30-777cf8d51f2054d96e0413b7406ed38ef43a7b39.md` + `777cf8d` + `include/tvm/ffi/c_api.h`
- Cython base.pxi enum update -> `777cf8d` + `python/tvm_ffi/cython/base.pxi`
- Version bump to 0.1.0a3 -> `777cf8d`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Document the simple/complex type boundary in the ABI overview docs.
- Ensure Rust bindings are updated to reflect the new index values.
