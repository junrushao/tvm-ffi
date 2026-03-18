---
scope:
  - "0007-containers.md"
  - "0002-object-system.md"
---
# ADR 0012: Inplace Tail Allocation for Tensor Shape and Strides

**TL;DR**: Decision to store TensorObj's shape and strides as raw `int64_t[]` arrays tail-allocated after the object struct via `make_inplace_array_object`, replacing separate `Optional<Shape>` heap-allocated fields.

## Context
- Prior to this change, `TensorObj` held `shape_data_: Optional<Shape>` and `strides_data_: Optional<Shape>` as protected fields. Each was a ref-counted `Shape` object created lazily when `Tensor::shape()` or `Tensor::strides()` was called, resulting in up to 2 extra heap allocations per tensor.
- `Tensor::shape()` and `Tensor::strides()` returned `Shape` (an `ObjectRef`), which involved ref-count manipulation on every access.
- The `DLTensor.shape` and `DLTensor.strides` pointers pointed into the `Shape` objects, coupling the pointer validity to the Shape's lifetime via the lazy cache.
- A `cached_dl_managed_tensor_versioned_` atomic field was also present for caching `ToDLPackVersioned()` results, adding further complexity and a destructor.

Usecases:
- Tensor creation in hot paths (e.g., per-op dispatch in graph execution engines) where minimizing allocations is critical.
- Shape access in inner loops where ref-counting overhead from `Shape` return type is undesirable.
- Simplifying TensorObj layout by removing mutable cached state.

Design Decisions:
- **Store shape/strides as inplace int64_t arrays** at the tail of the TensorObj memory block via `make_inplace_array_object<TensorObj, int64_t>(2 * ndim)`. The first `ndim` int64s hold shape values; the next `ndim` hold strides. `DLTensor.shape` and `DLTensor.strides` point directly into this tail memory.
- **Return `ShapeView` instead of `Shape`** from `Tensor::shape()` and `Tensor::strides()`. `ShapeView` is a lightweight non-owning view (pointer + size) that avoids heap allocation and ref-counting. Implicit conversion from `Shape` to `ShapeView` (and vice versa) ensures backward compatibility.
- **Remove mutable cached state**: `shape_data_`, `strides_data_`, and `cached_dl_managed_tensor_versioned_` are all eliminated. `TensorObj` no longer has a destructor.
- **Add `FillStridesFromShape`**: A new utility that writes row-major strides in-place without allocating, used during tensor construction.

## Implementation Notes
- `make_inplace_array_object` allocates `sizeof(TensorObj) + 2*ndim*sizeof(int64_t)` bytes (rounded to alignment) in one `AlignedAlloc` call.
- `ShapeView` wraps `TVMFFIShapeCell` (the C ABI struct with `data` pointer and `size`). It provides the same API as `Shape` (indexing, iteration, Product, bounds-checked `at`).
- `Shape::operator[]` is now unchecked (matching `ShapeView::operator[]`); bounds checking moved to `Shape::at()`.
- `Shape::StridesFromShape` signature changed from `(const int64_t*, int64_t)` to `(ShapeView)`.

### Alternative 1: Keep separate Shape objects but allocate from arena
- Pros: No return-type change for `Tensor::shape()`.
- Cons: Still 2 allocations per tensor (even if amortized). Does not eliminate mutable cache fields. Does not reduce TensorObj struct size.

### Alternative 2: Store shape/strides as `std::vector<int64_t>` fields
- Pros: Simpler implementation, no inplace array machinery needed.
- Cons: Extra heap allocation for each vector's internal buffer. Cannot use `make_inplace_array_object` pattern. ABI dependency on `std::vector` layout (non-portable across compilers).

## Addendum: Zero-ndim Exception (4fefeb0)
- Zero-dimensional (scalar) tensors are exempt from the always-non-null strides guarantee. When `ndim == 0`, `strides` may be `nullptr` because there are no dimensions requiring stride values. `ShapeView(nullptr, 0)` is valid and returns an empty view. This aligns with the DLPack specification which allows null strides for scalars. The invariant is now: "strides is non-null for ndim > 0; may be null for ndim == 0."

## Related Design Docs
- [0007-containers.md](../designs/0007-containers.md) -- TensorObj/Tensor/TensorView/ShapeView definitions
- [0002-object-system.md](../designs/0002-object-system.md) -- `make_inplace_array_object` / `InplaceArrayBase`
