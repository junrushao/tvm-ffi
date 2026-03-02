---
design: "0004"
title: "Container Library: Array, Map, String, Shape, Tuple, Variant, Tensor"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-05-06"
last_updated: "2025-10-01"
scope:
  - "ffi/containers"
  - "ffi/string"
  - "ffi/container/tensor"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
  - "296e2f7e6cce7c477e7bd3a124e1a6bb0983bd71"
  - "7e0a4b35df078675af32624b9cd02d1b8da1353e"
  - "024e45cdc9f630df739d82d63d29eb9791ccd707"
  - "0342d85f15fa2563ce502c6adb20497e0bf02c5e"
  - "ba0ea87da5f51890b8801ceaad2f583d17265bc1"
  - "f9d2bff8444250bdac336eeb1eee9cfba063008d"
  - "49e2ed4a169918d346fe8f96c208a4cec56cf3e8"
  - "03e8a6b8c995259d379358ab50ad81609a99083e"
  - "ed56a5e768b417c0d44332f5dda08a0971193677"
  - "ca95b412d75c80466390fbd5e6b5ba77673d93cc"
  - "3a551d83f7c05106fa8033a61970a5ce34aa8aef"
  - "6fa40b5829636d6f543ebe5dd67f623681eec880"
  - "1b824e88743a89343ad7493691bbdf5fdf2830c9"
  - "8ca0719f74bef289d80c8704343ed7c1607db8f3"
  - "1ec623678adea0ddba482d8d56d4ab2be440e694"
  - "4fefeb0f5913fc41cf860f517b9320f1bf1d0e98"
source_ledgers:
  - ".memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md"
  - ".memory/commits/2025-05-10-296e2f7e6cce7c477e7bd3a124e1a6bb0983bd71.md"
  - ".memory/commits/2025-06-18-7e0a4b35df078675af32624b9cd02d1b8da1353e.md"
  - ".memory/commits/2025-05-29-024e45cdc9f630df739d82d63d29eb9791ccd707.md"
  - ".memory/commits/2025-07-31-0342d85f15fa2563ce502c6adb20497e0bf02c5e.md"
  - ".memory/commits/2025-07-30-ba0ea87da5f51890b8801ceaad2f583d17265bc1.md"
  - ".memory/commits/2025-08-01-f9d2bff8444250bdac336eeb1eee9cfba063008d.md"
  - ".memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md"
  - ".memory/commits/2025-08-09-03e8a6b8c995259d379358ab50ad81609a99083e.md"
  - ".memory/commits/2025-08-06-ed56a5e768b417c0d44332f5dda08a0971193677.md"
  - ".memory/commits/2025-09-06-ca95b412d75c80466390fbd5e6b5ba77673d93cc.md"
  - ".memory/commits/2025-09-06-3a551d83f7c05106fa8033a61970a5ce34aa8aef.md"
  - ".memory/commits/2025-09-06-6fa40b5829636d6f543ebe5dd67f623681eec880.md"
  - ".memory/commits/2025-09-08-1b824e88743a89343ad7493691bbdf5fdf2830c9.md"
  - ".memory/commits/2025-09-27-8ca0719f.md"
  - ".memory/commits/2025-10-01-1ec62367.md"
  - ".memory/commits/2025-10-01-4fefeb0f.md"
---

# Container Library: Array, Map, String, Shape, Tuple, Variant, Tensor

## TL;DR
- TVM FFI provides a rich set of containers that are all Objects (ref-counted, type-indexed, passable via Any): `Array<T>` (immutable with COW), `Map<K,V>` (immutable ordered), `String`, `Bytes`, `Shape`, `Tuple`, `Variant<T...>`, `Optional<T>`, and `Tensor`/`NDArray`.
- All sequence-like containers (`Array`, `Map`, `List`, `Dict`) share a common `SeqBaseObj` / `TVMFFISeqCell` base with `data`, `size`, `capacity`, and `data_deleter` fields.
- Containers use inline storage via `make_inplace_array_object` to co-locate element data with the object header in a single allocation.

## Problem Statement
A cross-language FFI system needs standard container types that can be passed between languages without serialization. Without shared containers, each language would need to copy data into its native collections on every FFI boundary crossing, losing both performance and object identity.

## Context and Constraints
- Containers must be Objects (derive from `Object`) to participate in the type-erased value system.
- Elements are stored as `Any` values to support heterogeneous content (e.g., `Array<Any>`).
- Immutability is preferred for safety in concurrent and cross-language scenarios.
- Inline storage is important: ML workloads frequently create small, short-lived arrays (e.g., shapes, tuples of attributes).
- `String` is the most used container type and needs special optimization (SSO in `Any`, inline storage in `StringObj`).

## Goals
- Provide immutable containers (`Array`, `Map`) with copy-on-write (COW) mutation APIs.
- Provide mutable containers (`List`, `Dict`) for accumulation patterns.
- Provide `String` with zero-copy `string_view`-like access and inline storage.
- Provide `Shape` for tensor dimension tuples with inline `int64_t` storage.
- Provide `Tuple` for fixed-size heterogeneous value collections.
- Provide `Variant<T...>` for tagged-union-style type alternatives.
- Provide `Tensor`/`NDArray` for DLPack-compatible tensor exchange.

## Non-Goals
- Thread-safe mutation of mutable containers (`List`, `Dict` are single-threaded).
- Sorted maps or hash maps with custom comparators.
- Tensor computation (TVM FFI Tensors are data containers, not compute primitives).

## Design
### Components and Responsibilities

- **`SeqBaseObj`** (base class): Inherits `Object` + `TVMFFISeqCell`. Provides `data`, `size`, `capacity`, `data_deleter`. All sequence containers derive from this.

- **`ArrayObj` / `Array<T>`** (`array.h`): Immutable typed sequence. Elements are `Any` values. Supports COW: `push_back`, `emplace_back`, `Set`, and `erase` produce a new copy if there are multiple references. Uses `make_inplace_array_object` for inline element storage. Contains explicit `data_` pointer and `data_deleter_` for ABI stability and cross-DSO safety (see [ADR-0006](.memory/ADRs/0006-container-abi-data-deleter.md)). `CopyFrom`/`MoveFrom` static methods for construction. `at()` returns `const Any&` (avoids copy).

- **`MapObj` / `Map<K,V>`** (`map.h`): Immutable ordered map preserving insertion order. Internally uses a dense array of key-value pairs. Lookup is O(n) for small maps (common case) and O(1) via hash index for larger maps. COW semantics like Array. Contains explicit `data_` pointer and `data_deleter_` for ABI stability. `DenseMapObj` hash table sizing uses modulus (`%`) instead of bitmask (`&`) for correct probing with any slot count, with `BlockDeleter` for cross-DSO safety. The MSB (bit 63) of `MapObj::slots_` serves as a layout tag: set = SmallMap, clear = DenseMap (see [ADR-0011](.memory/ADRs/0011-map-msb-layout-tag.md)). The `IsSmallMap()` accessor checks this tag; `NumSlots()` masks it off for SmallMap or returns raw value for DenseMap.

- **`String`** (`string.h`): A value type backed by `details::BytesBaseCell`, a 16-byte wrapper around `TVMFFIAny`. Short strings (<=7 bytes) are stored inline via SSO (`kTVMFFISmallStr`); longer strings heap-allocate a `details::StringObj` using `InplaceArrayBase` for inline character storage. No longer inherits from `ObjectRef`. Default constructor creates an empty small string. `String(nullptr_t) = delete` enforces non-null. Provides `data()`/`size()`, comparison, hashing, concatenation, `std::ostream` integration. Includes a dedicated `Bytes::memequal` fast path for equality checks. See [ADR-0010](.memory/ADRs/0010-string-bytes-as-value-types.md).

- **`Bytes`** (`string.h`): Same value-type design as `String` but with type indices `kTVMFFISmallBytes`/`kTVMFFIBytes`. For binary data without UTF-8 assumptions.

- **`ShapeObj` / `Shape`** (`shape.h`, 219 LOC): Inline `int64_t` array for tensor dimensions. Uses `InplaceArrayBase` with `TVMFFIShapeCell`. Immutable.

- **`TupleObj` / `Tuple`** (`tuple.h`, 279 LOC): Fixed-size heterogeneous collection. Elements are `Any`. Uses `SeqBaseObj` with inline storage. Provides `operator[]` and structured binding support. Note: the `using ffi::Tuple;` re-export from `namespace tvm` has been removed (commit `ed56a5e`); callers must use `tvm::ffi::Tuple` explicitly.

- **`Variant<T...>`** (`variant.h`): Tagged union over type alternatives. Uses the object's `type_index` as the discriminant. **ObjectRef specialization**: When all `T...` derive from `ObjectRef`, `Variant` inherits from `ObjectRef` directly (8 bytes, single pointer) instead of wrapping `Any` (16 bytes). This is enabled by `VariantBase<true>` specialization and the `all_object_ref_v<T...>` compile-time trait. Non-ObjectRef variants use `VariantBase<false>` backed by `Any`. See commit `296e2f`.

- **`Optional<T>`** (`optional.h`, 299 LOC): Either a `T` value or `None`. For `ObjectRef` types, uses null pointer. For POD types, wraps in `std::optional` semantics at the Any level.

- **`ShapeView`** (`shape.h`): Lightweight non-owning view over shape data (pointer + size), avoiding the need for managed `Shape` allocations in hot paths. Provides `operator[]`, `begin()`/`end()`, `size()`, `empty()`. Default constructor creates an empty view. Implicit conversion to/from `Shape`. Added in commit `8ca0719`.

- **`TensorView`** (`tensor.h`): Non-owning lightweight view over a `DLTensor`, designed for FFI kernel function signatures where callers may provide either a `DLTensor*` or an owned `Tensor`. Copies the `DLTensor` metadata struct (not data). Registers `TypeTraits<TensorView>` mapping to `kTVMFFIDLTensorPtr`. Deliberately does NOT support `MoveToAny`/`MoveFromAny` to prevent ownership promotion. `TensorView(Tensor&&) = delete` prevents binding to temporaries. Added in commit `1ec62367`. See [Design 0018](.memory/designs/0018-tensorview-non-owning-tensor-view.md) for full details.

- **`TensorObj` / `Tensor`** (`tensor.h`, renamed from `ndarray.h` in commit `3a551d8`): DLPack-compatible tensor. Canonical name changed from `NDArray` to `Tensor` (type key `"ffi.Tensor"`, was `"ffi.NDArray"`; type index `kTVMFFITensor`, was `kTVMFFINDArray`). Contains a `DLTensor` struct (data pointer, device, dtype, shape, strides). `TensorObj` ABI surface was minimized in commit `8ca0719`: `shape_data_`, `strides_data_`, and `cached_dl_managed_tensor_versioned_` fields removed; shape and strides are now stored inline as trailing data via `make_inplace_array_object`. `Tensor::shape()` and `Tensor::strides()` return `ShapeView` instead of `Shape`. Helper methods `data_ptr()`, `ndim()`, `numel()` added. `ToDLPackVersioned()` simplified (no atomic caching, always allocates). Strides are always populated with contiguous (row-major) values (changed from nullable in commit `ca95b41`). DLPack import defaults relaxed: `require_alignment=0, require_contiguous=False` (commit `1b824e8`; see [ADR-0019](.memory/ADRs/0019-relaxed-dlpack-import-defaults.md)). New utilities: `IsDirectAddressDevice()` and `Tensor::IsAligned()` for callers that need explicit alignment checks.

### Data Contracts and Invariants
- **Array element type invariant**: `Array<T>` guarantees `TypeTraits<T>::CheckAnyStrict(elem)` for every element. This is checked at construction and maintained by COW mutations.
- **Map ordering invariant**: `Map<K,V>` preserves insertion order. Iteration yields entries in the order they were inserted.
- **String non-null invariant**: `String(nullptr_t)` is deleted. A default-constructed `String` is an empty small string (`kTVMFFISmallStr`), never null. Use `Optional<String>` for nullable strings (zero overhead, same 16-byte size).
- **Map unique key invariant**: `MapObj::CreateFromRange` guarantees unique keys for both small and dense map branches. Duplicate input keys use last-writer-wins semantics. Fixed in commit `0342d85`.
- **String cross-type equality**: `AnyHash`/`AnyEqual` treat `kTVMFFISmallStr` and `kTVMFFIStr` (heap) as equivalent types for equality and hashing. Likewise for `kTVMFFISmallBytes` and `kTVMFFIBytes`.
- **Inline storage invariant**: For containers using `make_inplace_array_object`, `data_deleter_ == nullptr` and `data_` points into the same allocation (data lives in the object allocation). For containers with separately allocated buffers (e.g., `ListObj` after growth, `DenseMapObj` hash blocks), `data_deleter_ != nullptr` and captures the correct deallocator from the allocating translation unit.
- **Variant size invariant**: `sizeof(Variant<ObjectRef types...>)` = `sizeof(ObjectRef)` (8 bytes). `sizeof(Variant<non-ObjectRef types...>)` = `sizeof(Any)` (16 bytes).
- **TensorView non-ownership invariant**: `TensorView` does NOT extend data lifetime. The caller must ensure data outlives the view. `strides()` permits null strides when `ndim == 0` (zero-dimensional scalar tensors; fix in commit `4fefeb0f`).
- **Tensor DLPack compatibility**: `Tensor` stores a `DLTensor` that is compatible with the DLPack specification. `device`, `dtype`, `shape`, and `strides` are always valid (strides are always non-null, populated with contiguous row-major values by default per commit `ca95b41`). Code that previously checked `strides == nullptr` as a proxy for contiguity must be updated. DLPack import is permissive by default (`require_alignment=0, require_contiguous=False` per commit `1b824e8`); callers that need strict validation should use `Tensor::IsAligned()` or pass explicit parameters to `from_dlpack()`.

### Control Flow
1. **Array creation**: `Array<T>{elem1, elem2, ...}` -> `make_inplace_array_object<ArrayObj, Any>(n)` -> copy elements as `Any` values -> return `Array<T>`.
2. **Array COW mutation**: `arr.push_back(val)` -> if `use_count() == 1`, mutate in place (if capacity allows) -> else `CopyFrom` to new allocation with +1 capacity -> append val -> return new `Array<T>`.
3. **String creation**: `String("hello")` -> `BytesBaseCell::InitSpaceForSize(len)` -> if len <= 7, store inline in `TVMFFIAny.v_bytes` with `kTVMFFISmallStr` type index -> else heap-allocate `details::StringObj` via `make_inplace_array_object` -> memcpy -> return `String` (value type, 16 bytes).
4. **Map lookup**: `map[key]` -> linear scan of key-value pairs (for small maps) or hash-indexed lookup.
5. **Tensor exchange**: `Tensor::FromDLPack(managed)` -> wrap `DLManagedTensor*` -> `Tensor::ToDLPack()` -> produce `DLManagedTensor*` with ref-count-aware deleter.

### Extension Points
- **New container types**: Derive from `SeqBaseObj` for sequence-like containers or from `Object` directly for other patterns.
- **Custom element types**: Any type with a `TypeTraits` specialization can be stored in containers.
- **Container interop**: `Array<T>` and `Map<K,V>` provide constructors from `std::vector` and `std::unordered_map`.

## Alternatives Considered
### Use std::vector / std::unordered_map directly
- Pros: Standard C++. Familiar API.
- Cons: Not Objects (cannot be passed via Any). Not C ABI compatible. Cannot be shared across language boundaries. No COW semantics.

### Protobuf repeated fields
- Pros: Cross-language. Schema-defined.
- Cons: Serialization overhead. Not in-process zero-copy. Not Objects.

## Trade-offs
- **Optimized**: Cross-language interoperability (all containers are Objects), inline storage for small collections, COW for safe mutation APIs, DLPack compatibility for tensors.
- **Sacrificed**: Mutable container performance (COW adds allocation on multi-reference mutation), Map lookup performance for large maps (O(n) linear scan for small maps, hash for large), compile-time type safety (elements are stored as `Any`).

## Interfaces and Compatibility
- **C ABI**: `TVMFFISeqCell`, `TVMFFIByteArray`, `TVMFFIShapeCell` structs define the data layout visible to foreign languages.
- **C++ API**: `Array<T>`, `Map<K,V>`, `String`, `Bytes`, `Shape`, `Tuple`, `Variant<T...>`, `Optional<T>`, `Tensor` (renamed from `NDArray` in commit `3a551d8`), `IsDirectAddressDevice()`, `Tensor::IsAligned()`. All accessible via `tvm::ffi::` only (namespace isolation per [ADR-0018](.memory/ADRs/0018-ffi-namespace-isolation.md)).
- **DLPack**: `TVMFFITensorFromDLPack`, `TVMFFITensorToDLPack` C ABI functions (renamed from `TVMFFINDArray*` in commit `3a551d8`).

## Failure Modes and Mitigations
- **Element type mismatch**: Inserting an element that fails `TypeTraits<T>::CheckAnyStrict` into a typed `Array<T>` throws `TypeError`. Mitigated by construction-time validation.
- **Map key not found**: `map[missing_key]` throws `KeyError`. The `count()` and `find()` methods provide safe lookup alternatives.
- **Tensor device mismatch**: Accessing `Tensor` data on the wrong device causes undefined behavior. Mitigated by exposing `device` for caller checks.
- **String encoding errors**: `String` does not validate UTF-8. Malformed UTF-8 is passed through without error. Foreign bindings are responsible for validation.

## Observability and Validation
- `tests/cpp/test_ffi_array.cc`: Tests Array construction, COW, push_back, iteration, and type checking.
- `tests/cpp/test_ffi_map.cc`: Tests Map construction, lookup, insertion order, and COW.
- `tests/cpp/test_ffi_string.cc`: Tests String construction, comparison, hashing, and inline storage.
- `tests/cpp/test_ffi_ndarray.cc`: Tests Tensor/NDArray creation and DLPack round-tripping.
- `tests/cpp/test_ffi_tuple.cc`: Tests Tuple construction and element access.

## Migration and Rollout
- Foundational containers from the root commit. Used throughout the codebase for type metadata, function arguments, and data exchange.

## Diagrams
- [.memory/diagrams/0002-object-type-hierarchy.md](.memory/diagrams/0002-object-type-hierarchy.md) (shows SeqBaseObj inheritance)

## Related ADRs
- [.memory/ADRs/0003-small-string-optimization-in-any.md](.memory/ADRs/0003-small-string-optimization-in-any.md) (String SSO)
- [.memory/ADRs/0006-container-abi-data-deleter.md](.memory/ADRs/0006-container-abi-data-deleter.md) (data_/data_deleter_ for Array/Map)
- [.memory/ADRs/0010-string-bytes-as-value-types.md](.memory/ADRs/0010-string-bytes-as-value-types.md) (String/Bytes rewritten from ObjectRef to value types)
- [.memory/ADRs/0011-map-msb-layout-tag.md](.memory/ADRs/0011-map-msb-layout-tag.md) (MSB tag in MapObj::slots_ for SmallMap/DenseMap dispatch)
- [.memory/ADRs/0018-ffi-namespace-isolation.md](.memory/ADRs/0018-ffi-namespace-isolation.md) (namespace isolation: `using ffi::*` removed)
- [.memory/ADRs/0019-relaxed-dlpack-import-defaults.md](.memory/ADRs/0019-relaxed-dlpack-import-defaults.md) (relaxed DLPack import defaults)

## Evidence Matrix
- Array<T> (COW, data_/data_deleter_) -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `include/tvm/ffi/container/array.h`; `.memory/commits/2025-06-18-7e0a4b35df078675af32624b9cd02d1b8da1353e.md` + `7e0a4b`
- Map<K,V> (insertion-order, data_/data_deleter_) -> ledger + `7d34eb8` + `include/tvm/ffi/container/map.h`; `7e0a4b`
- StringObj inline storage -> ledger + `7d34eb8` + `include/tvm/ffi/string.h`
- Shape (inline int64) -> ledger + `7d34eb8` + `include/tvm/ffi/container/shape.h`
- Tuple (SFINAE fix, delegation to ArrayObj::Empty) -> ledger + `7d34eb8` + `include/tvm/ffi/container/tuple.h`; `.memory/commits/2025-05-29-024e45cdc9f630df739d82d63d29eb9791ccd707.md` + `024e45`; `7e0a4b`
- Variant ObjectRef specialization (VariantBase<true>) -> `.memory/commits/2025-05-10-296e2f7e6cce7c477e7bd3a124e1a6bb0983bd71.md` + `296e2f` + `include/tvm/ffi/container/variant.h`
- NDArray/Tensor (DLPack) -> ledger + `7d34eb8` + `include/tvm/ffi/container/ndarray.h`
- SeqBaseObj / TVMFFISeqCell -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 365-398
- make_inplace_array_object -> `7d34eb8` + `include/tvm/ffi/memory.h`
- DenseMapObj slot arithmetic fix (bitmask to modulus) -> `7e0a4b` + `include/tvm/ffi/container/map.h`
- SmallMapObj duplicate key fix -> `.memory/commits/2025-07-31-0342d85f15fa2563ce502c6adb20497e0bf02c5e.md` + `0342d85` + `include/tvm/ffi/container/map.h`
- `Bytes::memequal` and `StableHashBytes` aligned optimization -> `.memory/commits/2025-07-30-ba0ea87da5f51890b8801ceaad2f583d17265bc1.md` + `ba0ea87` + `include/tvm/ffi/string.h`, `include/tvm/ffi/base_details.h`
- `StringObj`/`BytesObj` moved to `namespace details` -> `.memory/commits/2025-08-01-f9d2bff8444250bdac336eeb1eee9cfba063008d.md` + `f9d2bff`
- String/Bytes rewritten as value types (BytesBaseCell) -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/string.h`
- `Optional<String>`/`Optional<Bytes>` zero-overhead specialization -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/optional.h`
- MapObj MSB layout tag (`kSmallTagMask`, `IsSmallMap()`, `NumSlots()`) -> `.memory/commits/2025-08-09-03e8a6b8c995259d379358ab50ad81609a99083e.md` + `03e8a6b` + `include/tvm/ffi/container/map.h`
- `using ffi::Tuple` removed from `namespace tvm` -> `.memory/commits/2025-08-06-ed56a5e768b417c0d44332f5dda08a0971193677.md` + `ed56a5e` + `include/tvm/ffi/container/tuple.h`
- NDArray strides always populated (MakeStridesFromShape, stride_data_ field) -> `.memory/commits/2025-09-06-ca95b412d75c80466390fbd5e6b5ba77673d93cc.md` + `ca95b41` + `include/tvm/ffi/container/ndarray.h`, `include/tvm/ffi/container/shape.h`
- NDArray->Tensor rename (type key, C API, Python, Cython) -> `.memory/commits/2025-09-06-3a551d83f7c05106fa8033a61970a5ce34aa8aef.md` + `3a551d8` + `include/tvm/ffi/container/ndarray.h`, `python/tvm_ffi/`
- Tensor::strides() accessor with lazy caching -> `.memory/commits/2025-09-06-6fa40b5829636d6f543ebe5dd67f623681eec880.md` + `6fa40b5` + `include/tvm/ffi/container/ndarray.h`
- Relaxed DLPack import defaults (require_alignment=0, require_contiguous=False) -> `.memory/commits/2025-09-08-1b824e88743a89343ad7493691bbdf5fdf2830c9.md` + `1b824e8` + `python/tvm_ffi/cython/ndarray.pxi`, `include/tvm/ffi/container/ndarray.h`
- IsDirectAddressDevice() and Tensor::IsAligned() -> `1b824e8` + `include/tvm/ffi/container/ndarray.h`
- ShapeView non-owning view class, TensorObj ABI minimization (fields removed, inline shape/strides), data_ptr()/ndim()/numel() helpers -> `.memory/commits/2025-09-27-8ca0719f.md` + `8ca0719` + `include/tvm/ffi/container/shape.h`, `include/tvm/ffi/container/tensor.h`
- TensorView non-owning view with `kTVMFFIDLTensorPtr` type index -> `.memory/commits/2025-10-01-1ec62367.md` + `1ec62367` + `include/tvm/ffi/container/tensor.h`, `include/tvm/ffi/object.h`
- Null strides fix for zero-dim tensors -> `.memory/commits/2025-10-01-4fefeb0f.md` + `4fefeb0f` + `include/tvm/ffi/container/tensor.h`

## Open Questions
- Should `Map<K,V>` switch to a hash-based implementation for all sizes, or is the current linear-for-small/hash-for-large strategy optimal?
- Should `String` enforce UTF-8 validation?
- Should the `zero_padding` zeroing discipline (required by the String value type change) have a centralized helper or compile-time check to prevent regressions in new `TypeTraits` specializations?

## Confidence and Risk
- Confidence: high
- Residual risks: COW mutation performance under high contention (many references). Map lookup performance for medium-sized maps (too large for linear scan, too small for hash table overhead to amortize).
