---
adr: "0006"
title: "Add Explicit data_ and data_deleter_ to ArrayObj and MapObj for ABI Stability"
status: "accepted"
date: "2025-06-18"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "abi"
  - "containers"
source_commits:
  - "7e0a4b35df078675af32624b9cd02d1b8da1353e"
source_ledgers:
  - ".memory/commits/2025-06-18-7e0a4b35df078675af32624b9cd02d1b8da1353e.md"
---

# ADR-0006: Add Explicit data_ and data_deleter_ to ArrayObj and MapObj for ABI Stability

## TL;DR
- `ArrayObj` and `MapObj` gain explicit `void* data_` and `void (*data_deleter_)(void*)` fields, decoupling element storage from the inplace-array base class and enabling safe cross-shared-library deallocation.
- This makes the container object layout self-describing: foreign language bindings can read element data at a known offset without relying on C++ template machinery.

## Status
Accepted

## Context
Previously, `ArrayObj` relied on `InplaceArrayBase::AddressOf(0)` to locate element data, with no stored data pointer. This had two problems:
1. **ABI fragility**: Foreign language bindings (Python Cython, Rust) could not determine the data pointer offset without understanding the C++ template layout of `InplaceArrayBase`, which varied by alignment and type.
2. **Cross-library deallocation hazard**: If a container's backing buffer was allocated in one shared library (DSO) and freed in another using a different allocator, memory corruption could result. The C++ allocator mismatch is a real problem when TVM FFI is loaded across multiple DSOs.

The `TVMFFISeqCell` C ABI struct already defined `data`, `size`, `capacity`, and `data_deleter` fields for sequence containers, but `ArrayObj` and `MapObj` did not consistently use them.

## Decision Drivers
- ABI stability: container field offsets must be deterministic and accessible from C.
- Cross-DSO safety: deallocation must use the same allocator as allocation.
- Self-describing layout: foreign bindings should be able to read container data without C++ template knowledge.
- Compatibility with inline storage: containers with inplace-allocated elements (no separate buffer) must have `data_deleter_ == nullptr`.

## Decision
Add to `ArrayObj` and `MapObj`:
- `void* data_`: pointer to the element storage (may point into the same allocation for inplace storage, or to a separately allocated buffer).
- `void (*data_deleter_)(void*)`: if non-null, called to deallocate `data_` when the container is destroyed. If null, the data lives in the inplace allocation and is freed with the object.

For `DenseMapObj` (the hash-table implementation backing `Map`), add a `BlockDeleter` static function that captures the correct `delete[]` in the same translation unit as `new[]`, ensuring cross-DSO safety.

Additionally:
- Rewrite `DenseMapObj` hash table sizing from `slots_ = n - 1` (bitmask) to `slots_ = n` (modulus), fixing probing arithmetic to use `%` instead of `&`.
- Rename dispatch macros from `TVM_DISPATCH_MAP` to `TVM_FFI_DISPATCH_MAP`.
- `ArrayObj::at()` returns `const Any&` instead of `const Any` (avoids unnecessary copy).
- `Array::emplace_back` added for in-place construction.

## Alternatives Considered
### Keep InplaceArrayBase::AddressOf(0) as the only data access path
- Pros: No struct layout change. Minimal code churn.
- Cons: Foreign bindings cannot determine the data pointer offset. Cross-DSO deallocation remains unsafe. The layout depends on C++ template instantiation details that are not ABI-stable.

### Use a separate C API function to get the data pointer
- Pros: No struct layout change. C API provides the accessor.
- Cons: Adds a function call overhead for every data access. Does not solve the cross-DSO deallocation problem. The function implementation would still need to resolve the template layout.

### Store data pointer in TVMFFISeqCell (parent struct) only
- Pros: Data pointer is at a fixed offset in the C ABI struct.
- Cons: `TVMFFISeqCell` is a cell (embedded struct), not a class. `ArrayObj` and `MapObj` derive from `Object` + `TVMFFISeqCell`, so the cell's field offsets depend on the inheritance layout. Explicit fields on the concrete class are more reliable.

## Why This Option Won
- The `data_` + `data_deleter_` pattern directly addresses both problems: ABI stability (known offset) and cross-DSO safety (captured deallocator).
- It matches the `TVMFFISeqCell` contract, making the C++ implementation consistent with the C ABI specification.
- The `data_deleter_` is null for inline storage, so the overhead is zero for the common case (small containers with inplace data).
- The `BlockDeleter` pattern for `DenseMapObj` is a reusable idiom for any container that allocates a separate buffer.

## Consequences
### Positive
- Container element data is accessible at a known struct offset from any language.
- Cross-DSO deallocation is safe by construction (the deleter captures the correct allocator).
- `DenseMapObj` probing is simpler and correct for any slot count (modulus vs bitmask).
- `emplace_back` enables efficient in-place element construction.

### Negative
- **Breaking ABI change**: `ArrayObj` and `MapObj` struct layouts changed (new fields before `size_`/`capacity_`). All compiled bindings must be recompiled.
- Slightly larger object headers (two additional pointer-sized fields per container instance).
- The `data_deleter_` field is unused (null) for most containers that use inplace storage, adding 8 bytes of dead weight per container.

### Risks
- If a container forgets to set `data_deleter_` when using separate allocation, the buffer will leak. Mitigated by the `DenseMapObj::BlockDeleter` pattern and code review.
- The DenseMapObj slot arithmetic change (bitmask to modulus) may have a minor performance impact due to the division instruction. Mitigated by the correctness fix being more important than a micro-benchmark difference.

## Implementation Notes
- `ArrayObj::data_` and `data_deleter_` are placed before `size_` and `capacity_` in the class layout.
- `ArrayObj::Empty()` sets `data_ = AddressOf(0)` for inplace storage with `data_deleter_ = nullptr`.
- `DenseMapObj::BlockDeleter` is a static function that calls `delete[] static_cast<Block*>(ptr)`.
- `SmallMapObj` introduces `KVRawStorageType` (a POD struct of the same size/alignment as `KVType`) to separate raw storage from the C++ type with constructors, preventing implicit construction in inplace storage.
- `Tuple` construction is simplified to delegate to `ArrayObj::Empty()`.
- Macro rename: `TVM_DISPATCH_MAP` -> `TVM_FFI_DISPATCH_MAP`.

## Validation
- `tests/cpp/test_ffi_array.cc`: Tests Array construction, COW, push_back, emplace_back.
- `tests/cpp/test_ffi_map.cc`: Tests Map construction, lookup, insertion, rehashing.
- Cross-DSO safety is validated implicitly through the Python/Rust binding tests that load TVM FFI as a shared library.

## Migration and Rollback
- This is a one-time ABI break to reach a stable target layout. All bindings must be recompiled.
- Rollback would revert to the previous layout, which is not recommended due to the cross-DSO safety improvements.

## Related Design Docs
- [.memory/designs/0004-container-library.md](.memory/designs/0004-container-library.md)
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)

## Related Diagrams
- [.memory/diagrams/0002-object-type-hierarchy.md](.memory/diagrams/0002-object-type-hierarchy.md)

## Evidence Matrix
- `ArrayObj` data_/data_deleter_ fields -> `.memory/commits/2025-06-18-7e0a4b35df078675af32624b9cd02d1b8da1353e.md` + `7e0a4b` + `include/tvm/ffi/container/array.h`
- `MapObj` data_/data_deleter_ fields -> `7e0a4b` + `include/tvm/ffi/container/map.h`
- `DenseMapObj::BlockDeleter` -> `7e0a4b` + `include/tvm/ffi/container/map.h`
- DenseMapObj slot arithmetic fix (bitmask to modulus) -> `7e0a4b` + `include/tvm/ffi/container/map.h`
- Macro rename TVM_DISPATCH_MAP -> TVM_FFI_DISPATCH_MAP -> `7e0a4b`
- Tuple delegation to ArrayObj::Empty() -> `7e0a4b` + `include/tvm/ffi/container/tuple.h`

## Supersedes
None (refines the container design from design 0004)

## Superseded By
None

## Follow-up Actions
- Verify that Python Cython bindings read `data_` at the correct offset after recompilation.
- Consider whether `List` and `Dict` (mutable containers) need the same `data_deleter_` treatment.
