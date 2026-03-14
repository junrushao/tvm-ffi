---
scope:
  - "0001-c-abi"
  - "0002-type-index-partitioning"
---
# Static Type Index Complexity-Based Ordering

**TL;DR**: The decision to reorder static type indices within the `[64, 128)` range by ABI complexity -- simple C-ABI-only types first, complex C++-dependent types second -- before freezing the ABI.

## Context

The original static type index assignments were chronological: types received indices in the order they were added to the codebase. This produced an ordering where `Array` (69) and `Map` (70) preceded `Shape` (71) and `NDArray` (72), despite `Array` and `Map` requiring C++ runtime support (templates, vtables) while `Shape` and `NDArray` have fully C-described cell layouts in `c_api.h`.

Before the ABI freeze, there is a one-time opportunity to establish a semantically meaningful ordering that aids future decisions about which types can be used in pure-C contexts (e.g., lightweight C-only FFI consumers, WebAssembly minimal builds).

## Alternatives

### 1. Complexity-based ordering (chosen)

Reorder so that "simple" types with pure C ABI cell layouts precede "complex" types:
- Simple C ABI: Object=64, Str=65, Bytes=66, Error=67, Function=68, Shape=69, NDArray=70
- Complex C++: Array=71, Map=72, Module=73, OpaquePyObject=74

### 2. Keep chronological ordering

- Pros: No ABI break, simpler.
- Cons: No semantic grouping. Future decisions about pure-C subsets would need ad-hoc rules.

### 3. Use sub-ranges with gaps

Reserve indices `[64, 80)` for simple types and `[80, 128)` for complex types, leaving gaps for future additions.

- Pros: More room for future simple types.
- Cons: Wastes index space in the already-limited 64-slot static range. The current approach uses contiguous allocation which is more space-efficient.

## Decision

Alternative 1: reorder to complexity-based grouping. Specific index reassignments:
- `kTVMFFIShape`: 71 -> 69
- `kTVMFFINDArray`: 72 -> 70
- `kTVMFFIArray`: 69 -> 71
- `kTVMFFIMap`: 70 -> 72

A comment block `// more complex objects` marks the dividing line in the `TVMFFITypeIndex` enum.

## Consequences

- **ABI-breaking**: Any compiled code or language binding that hard-codes the integer values of `kTVMFFIArray`, `kTVMFFIMap`, `kTVMFFIShape`, or `kTVMFFINDArray` must be updated.
- **Python/Cython sync**: The Cython `base.pxi` must reflect the new values.
- This change is acceptable only before the ABI freeze. After freeze, static type index assignments are permanent.
- Package version bumped to `0.1.0a3` with this change.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- Type Index Layout
- [`.knowledge/ADRs/0002-type-index-partitioning.md`](0002-type-index-partitioning.md) -- Type index ranges
- Commit: `.knowledge/commits/2025-08-30-777cf8d51f2054d96e0413b7406ed38ef43a7b39.md` + `777cf8d`
