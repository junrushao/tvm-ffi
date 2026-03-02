---
adr: "0032"
title: "Method-Based Tensor/TensorView API Replacing operator->()"
status: "accepted"
date: "2025-10-14"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM FFI contributors"
informed:
  - "C++ API users"
  - "Example and documentation authors"
tags:
  - "api-design"
  - "tensor"
  - "safety"
source_commits:
  - "0dcd4d2b"
source_ledgers:
  - ".memory/commits/2025-10-14-0dcd4d2b.md"
---

# ADR-0032: Method-Based Tensor/TensorView API Replacing operator->()

## TL;DR
- `Tensor::operator->()` (returning `DLTensor*`) and `TensorView::operator->()` were removed in favor of explicit method-based accessors: `data_ptr()`, `ndim()`, `dtype()`, `device()`, `size(idx)`, `stride(idx)`, `byte_offset()`, `GetDLTensorPtr()`.
- This eliminates accidental exposure of raw `DLTensor` internals and provides a safer, more discoverable API surface.

## Status
Accepted

## Context
The `Tensor` class (an `ObjectRef` wrapper around `TensorObj`) previously provided `operator->()` returning a `DLTensor*`, which allowed direct member access via `tensor->data`, `tensor->ndim`, `tensor->dtype`, `tensor->device`, etc. While convenient, this pattern had several problems:

1. **Unsafe internal exposure**: Users could access `tensor->shape`, `tensor->strides` as raw `int64_t*` pointers without bounds checking.
2. **API discoverability**: `operator->()` does not appear in code completion or documentation. Users had to know that `Tensor` wraps `DLTensor`.
3. **Encapsulation violation**: The `DLTensor` struct is a DLPack implementation detail. Exposing it directly prevents the `Tensor` class from adding bounds checks, lazy allocation, or other safety features.
4. **TensorView consistency**: `TensorView` also had `operator->()`, creating the same problems for the non-owning view type.

## Decision Drivers
- API safety: prevent raw pointer access to shape/strides arrays.
- Discoverability: methods appear in IDE autocompletion and documentation.
- Consistency: `Tensor` and `TensorView` should have identical accessor APIs.
- DLPack encapsulation: isolate internal struct from public API.

## Decision
Replace `operator->()` with named method accessors on both `Tensor` and `TensorView`:

| Old (`operator->()`)       | New (method-based)      |
|----------------------------|-------------------------|
| `tensor->data`             | `tensor.data_ptr()`     |
| `tensor->ndim`             | `tensor.ndim()`         |
| `tensor->dtype`            | `tensor.dtype()`        |
| `tensor->device`           | `tensor.device()`       |
| `tensor->shape[i]`         | `tensor.size(i)`        |
| `tensor->strides[i]`       | `tensor.stride(i)`      |
| `tensor->byte_offset`      | `tensor.byte_offset()`  |
| (no equivalent)            | `tensor.GetDLTensorPtr()` |

`GetDLTensorPtr()` provides escape-hatch access to the raw `DLTensor*` for interop code that needs it, making the intent explicit.

## Alternatives Considered
### Keep operator->() alongside new methods
- Pros: Backward-compatible. Users can migrate gradually.
- Cons: Defeats the purpose. Users continue using the raw accessor by habit. Two ways to do the same thing.

### Deprecate operator->() with [[deprecated]] attribute
- Pros: Gentle migration path. Compiler warnings guide users.
- Cons: Deprecation warnings are often ignored. Adds a long transition period with both APIs coexisting.

### Use a proxy object pattern (operator->() returns a proxy with safe accessors)
- Pros: Keeps arrow syntax. Can add bounds checking in proxy.
- Cons: Confusing that `->` returns a different type than expected. Does not help with API discoverability.

## Why This Option Won
- Clean break: removing `operator->()` forces all call sites to update, eliminating the unsafe pattern completely.
- The new method names (`data_ptr()`, `size()`, `stride()`) align with PyTorch's tensor API, making them familiar to ML developers.
- `GetDLTensorPtr()` provides an explicit escape hatch for interop code, making the intent clear.
- The change was mechanical (16 files updated) with no ambiguity in the mapping.

## Consequences
### Positive
- No accidental exposure of raw `DLTensor` internals.
- Methods appear in IDE autocompletion and Doxygen docs.
- `Tensor` and `TensorView` now have identical accessor APIs.
- `size(i)` and `stride(i)` can add bounds checking in the future without breaking callers.

### Negative
- Breaking change for all C++ code using `tensor->` syntax (16 files updated in-tree).
- Slightly more verbose: `tensor.data_ptr()` instead of `tensor->data`.

### Risks
- Downstream C++ code will fail to compile until updated. Mitigation: the compiler error is clear (no `operator->()` member), and the fix is a mechanical rename.

## Implementation Notes
- `operator->()` was removed from both `Tensor` (in `ObjectRef` wrapper) and `TensorView`.
- New methods are defined directly on the classes (not inherited from a base).
- All examples, docs, and tests were updated in the same commit.
- `GetDLTensorPtr()` returns `const DLTensor*` (not mutable), preserving const-correctness.

## Validation
- All C++ tests compile and pass with the new API.
- All examples updated and verified.
- Documentation updated to use method-based syntax.

## Migration and Rollback
- **Migration**: Search-and-replace `tensor->data` -> `tensor.data_ptr()`, `tensor->ndim` -> `tensor.ndim()`, etc. The mapping is 1:1.
- **Rollback**: Re-add `operator->()` to `Tensor` and `TensorView`. Low risk since the operator is a one-line method.

## Related Design Docs
- [.memory/designs/0018-tensorview-non-owning-tensor-view.md](.memory/designs/0018-tensorview-non-owning-tensor-view.md) (TensorView API surface)

## Related Diagrams
None

## Evidence Matrix
- Removal of `operator->()` and addition of method-based accessors -> `.memory/commits/2025-10-14-0dcd4d2b.md` + `0dcd4d2b` + `include/tvm/ffi/container/tensor.h`
- 16-file update across examples, docs, tests -> `0dcd4d2b` + `examples/`, `docs/`, `tests/`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Add bounds checking to `size(idx)` and `stride(idx)` in a future commit.
- Update Rust bindings if they mirror the C++ Tensor API.
