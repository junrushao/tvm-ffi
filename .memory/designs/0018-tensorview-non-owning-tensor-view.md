---
design: "0018"
title: "TensorView: Non-Owning Tensor View for FFI Kernel Signatures"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-10-01"
last_updated: "2025-10-17"
scope:
  - "ffi/container/tensor"
  - "ffi/type_traits"
  - "ffi/object"
source_commits:
  - "1ec623678adea0ddba482d8d56d4ab2be440e694"
  - "4fefeb0f5913fc41cf860f517b9320f1bf1d0e98"
  - "0dcd4d2b"
  - "573d76f2"
source_ledgers:
  - ".memory/commits/2025-10-01-1ec62367.md"
  - ".memory/commits/2025-10-01-4fefeb0f.md"
  - ".memory/commits/2025-10-14-0dcd4d2b.md"
  - ".memory/commits/2025-10-17-573d76f2.md"
---

# TensorView: Non-Owning Tensor View for FFI Kernel Signatures

## TL;DR
- `ffi::TensorView` is a lightweight non-owning view over a `DLTensor` struct, designed for FFI kernel function signatures where callers may pass either a DLPack `DLTensor*` pointer or an owned `Tensor` reference.
- TensorView copies the `DLTensor` metadata struct (not the data), providing shape/strides/dtype accessors while the underlying data lifetime is managed by the caller.
- The class deliberately does NOT support `MoveToAny`/`MoveFromAny` to prevent accidental ownership promotion; it is a "borrow" type in the FFI type system.

## Problem Statement
FFI kernel functions need to accept tensor inputs from diverse sources: owned `Tensor` objects from the FFI, raw `DLTensor*` from DLPack exchange, or tensors from frameworks like PyTorch that pass `DLTensor*` pointers. Requiring an owning `Tensor` (which involves ref-counting and heap allocation) is too restrictive: some callers only have a `DLTensor*` from a DLPack capsule and cannot produce an owning `Tensor` without a copy or import operation. Without a non-owning view, kernel signatures are forced into one of two bad patterns: accept `DLTensor*` raw pointers (losing type safety) or require `Tensor` (forcing unnecessary ownership).

## Context and Constraints
- The DLPack specification defines `DLTensor` as a non-owning descriptor (pointer, shape, strides, dtype, device).
- `Tensor` (formerly `NDArray`) is a ref-counted `Object` that wraps a `DLTensor` with ownership semantics.
- FFI functions use `TypeTraits<T>` to marshal arguments from `AnyView`. A non-owning view type needs its own `TypeTraits` specialization.
- The view must work in packed function signatures: `void kernel(TensorView input, TensorView output)`.
- Zero-dimensional (scalar) tensors are a common edge case; `DLTensor::strides` may be null when `ndim == 0`.

## Goals
- Provide a non-owning tensor view usable in FFI function signatures.
- Accept both `DLTensor*` and `Tensor` as sources.
- Prevent accidental ownership promotion (no move-to-Any).
- Support all tensor metadata accessors: `shape()`, `strides()`, `data_ptr()`, `ndim()`, `numel()`, `dtype()`, `IsContiguous()`.

## Non-Goals
- Tensor data lifetime management (TensorView does not participate in ref counting).
- Tensor computation or arithmetic operations.
- Replacing `Tensor` for storage or container use cases.

## Design
### Components and Responsibilities

- **`ffi::TensorView`** (class, `container/tensor.h`): Stores a copy of the `DLTensor` struct. Constructors accept `const Tensor&`, `const DLTensor*`, copy/move. The `TensorView(Tensor&&) = delete` constructor prevents binding to temporaries that could dangle. Provides method-based accessors (commit `0dcd4d2b`): `shape()` returns `ShapeView`, `strides()` returns `ShapeView`, `data_ptr()` returns `void*`, `ndim()` returns `int32_t`, `numel()` returns `int64_t`, `dtype()` returns `DLDataType`, `IsContiguous()` returns `bool`, `device()` returns `DLDevice`, `size(idx)` returns `int64_t`, `stride(idx)` returns `int64_t`, `byte_offset()` returns `uint64_t`, `GetDLTensorPtr()` returns `const DLTensor*`. The `operator->()` pattern was removed; see [ADR-0032](.memory/ADRs/0032-method-based-tensor-api.md). ATen-style aliases (commit `573d76f2`): `dim()` -> `ndim()`, `sizes()` -> `shape()`, `is_contiguous()` -> `IsContiguous()`. The `size(idx)` and `stride(idx)` methods accept `int64_t` (changed from `size_t`) and support negative indexing: `size(-1)` returns the last dimension size (PyTorch semantics).

- **`TypeTraits<TensorView>`** (specialization, `container/tensor.h`): Maps to `kTVMFFIDLTensorPtr` type index. `TryCastFromAnyView` accepts both `kTVMFFIDLTensorPtr` (raw `DLTensor*` from C API) and object-typed `Tensor` (by extracting the `DLTensor` pointer). Does NOT provide `MoveToAny` or `MoveFromAny`.

- **`StaticTypeKey::kTVMFFIDLTensorPtr`** (constant, `object.h`): String literal `"DLTensor*"` added to the static type key registry. Represents the `DLTensor*` pointer type index in the type-erased value system.

### Data Contracts and Invariants
- **No ownership invariant**: `TensorView` does NOT extend the lifetime of the underlying tensor data. The caller must ensure the data outlives the view. This is enforced by the absence of `MoveToAny`/`MoveFromAny` in the `TypeTraits` specialization.
- **Null strides for zero-dim tensors**: `strides()` returns an empty `ShapeView` when `ndim == 0` and `strides` is null. The check is `strides != nullptr || ndim == 0`, not just `strides != nullptr`. This was fixed in commit `4fefeb0f` across 5 locations.
- **Move-from-owned deletion**: `TensorView(Tensor&&) = delete` prevents binding to rvalue `Tensor` objects, which would dangle after the temporary is destroyed.
- **DLTensor struct copy**: The constructor copies the entire `DLTensor` struct (40 bytes: data, device, ndim, dtype, shape, strides, byte_offset). The `shape` and `strides` pointers still reference the original tensor's memory.

### Control Flow
1. C++ kernel declares `void kernel(TensorView input, TensorView output)`.
2. FFI caller passes arguments as `AnyView` (either `DLTensor*` with `kTVMFFIDLTensorPtr` type index, or an object-typed `Tensor`).
3. `TypeTraits<TensorView>::TryCastFromAnyView` dispatches: if `kTVMFFIDLTensorPtr`, constructs TensorView from the `DLTensor*`; if object-typed, checks for `Tensor` and extracts the `DLTensor` pointer.
4. Kernel receives a `TensorView` with all metadata accessors available.

### Extension Points
- Future non-owning view types (e.g., `ShapeView`, `StringView`) can follow the same pattern: `TypeTraits` specialization without `MoveToAny`, constructors from both owned and borrowed sources.
- Additional `DLTensor*` sources (e.g., custom memory pools) can participate by providing a valid `DLTensor*` at the C API level.

## Alternatives Considered
### Accept raw `DLTensor*` in kernel signatures
- Pros: Direct, no wrapper class needed.
- Cons: No type-safety in `TypeTraits`. Cannot provide convenience accessors. Raw pointers in signatures are error-prone.

### Require `Tensor` (owned) in all kernel signatures
- Pros: Simple ownership model. Full type safety.
- Cons: Forces callers to import/wrap `DLTensor*` into an owning `Tensor`, which requires ref-count allocation. Not possible when the caller only has a borrowed `DLTensor*`.

## Trade-offs
- **Optimized**: Flexibility (kernels accept both owned and borrowed tensors), zero allocation overhead (no ref counting, just struct copy), familiar DLPack compatibility.
- **Sacrificed**: Safety (no lifetime tracking; dangling views are possible if the caller does not manage lifetimes), no ability to store TensorView in containers or return it from FFI functions (no `MoveToAny`).

## Interfaces and Compatibility
- **C++ API**: `ffi::TensorView` class with constructors from `const Tensor&`, `const DLTensor*`, copy/move. Accessors: `shape()`, `strides()`, `data_ptr()`, `ndim()`, `numel()`, `dtype()`, `device()`, `IsContiguous()`, `size(idx)`, `stride(idx)`, `byte_offset()`, `GetDLTensorPtr()`. ATen-style aliases: `dim()`, `sizes()`, `is_contiguous()`. `operator->()` removed (commit `0dcd4d2b`). `Tensor` has the same method-based API and ATen aliases. `size(idx)` and `stride(idx)` accept `int64_t` with negative indexing support (commit `573d76f2`).
- **Type system**: `kTVMFFIDLTensorPtr` type index, `StaticTypeKey::kTVMFFIDLTensorPtr = "DLTensor*"`.
- **TypeTraits**: `TypeTraits<TensorView>` with `TryCastFromAnyView` only (no `MoveToAny`/`MoveFromAny`).

## Failure Modes and Mitigations
- **Dangling view**: If the underlying `DLTensor` data is freed while a `TensorView` still references it, accessing `data_ptr()` is undefined behavior. Mitigation: `TensorView(Tensor&&) = delete` prevents the most common dangling pattern (binding to a temporary). Documentation emphasizes caller lifetime responsibility.
- **Null strides on non-zero-dim tensor**: If a malformed `DLTensor` has null strides with `ndim > 0`, `strides()` will return an empty `ShapeView`. Mitigation: `IsContiguous()` handles this case by treating null strides as contiguous (per DLPack convention).
- **Type mismatch**: If `AnyView` contains a non-Tensor object, `TryCastFromAnyView` returns an error. No silent miscast.

## Observability and Validation
- Examples updated to use `TensorView` in kernel signatures (e.g., `add_one` kernel).
- Tests in `tests/cpp/` and `tests/python/test_load_inline.py` exercise `TensorView` construction from both `DLTensor*` and `Tensor`.
- The zero-dim strides fix is tested via scalar tensor edge cases.

## Migration and Rollout
- New class: no migration needed for existing code.
- Kernel ops are recommended (not required) to switch from `Tensor` to `TensorView` for broader input compatibility.
- Existing `Tensor` signatures continue to work unchanged.

## Diagrams
- [.memory/diagrams/0015-tensorview-typeschema-architecture.md](.memory/diagrams/0015-tensorview-typeschema-architecture.md)

## Related ADRs
- [.memory/ADRs/0032-method-based-tensor-api.md](.memory/ADRs/0032-method-based-tensor-api.md) (decision to replace operator->() with method-based accessors)

## Evidence Matrix
- `ffi::TensorView` class with constructors and accessors -> `.memory/commits/2025-10-01-1ec62367.md` + `1ec62367` + `include/tvm/ffi/container/tensor.h`
- `TypeTraits<TensorView>` mapping to `kTVMFFIDLTensorPtr` -> `1ec62367` + `include/tvm/ffi/container/tensor.h`
- `StaticTypeKey::kTVMFFIDLTensorPtr = "DLTensor*"` -> `1ec62367` + `include/tvm/ffi/object.h`
- `TensorView(Tensor&&) = delete` safety pattern -> `1ec62367` + `include/tvm/ffi/container/tensor.h`
- Null strides fix for zero-dim tensors (5 locations) -> `.memory/commits/2025-10-01-4fefeb0f.md` + `4fefeb0f` + `include/tvm/ffi/container/tensor.h`
- Method-based API replacing `operator->()` on both Tensor and TensorView -> `.memory/commits/2025-10-14-0dcd4d2b.md` + `0dcd4d2b` + `include/tvm/ffi/container/tensor.h`
- ATen-style aliases (`dim()`, `sizes()`, `is_contiguous()`), negative indexing on `size()`/`stride()`, parameter type `size_t` -> `int64_t` -> `.memory/commits/2025-10-17-573d76f2.md` + `573d76f2` + `include/tvm/ffi/container/tensor.h`, `tests/cpp/test_tensor.cc`

## Open Questions
- Should `TensorView` also provide a device-side data accessor with type checking (e.g., `typed_data_ptr<float>()`)?
- Should there be a mechanism to create a `Tensor` from a `TensorView` (explicit ownership promotion)?

## Confidence and Risk
- Confidence: high
- Residual risks: Dangling views are not detectable at runtime. The struct copy means `TensorView::shape()` and `TensorView::strides()` return pointers into the original tensor's memory, creating a hidden dependency. If the original tensor reallocates its shape array (unlikely in practice), the view's shape pointer would dangle.
