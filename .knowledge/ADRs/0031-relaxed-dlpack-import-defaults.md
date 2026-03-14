---
scope:
  - "0005-containers"
  - "0014-python-bindings"
---
# Relaxed DLPack Import Defaults

**TL;DR**: Python `from_dlpack()` defaults changed from `require_alignment=8, require_contiguous=True` to `require_alignment=0, require_contiguous=False`, aligning the Python layer with the C++ layer and improving interop with frameworks that produce non-contiguous or misaligned tensors.

## Context

The Python `from_dlpack()` enforced `required_alignment=8` and `required_contiguous=True` by default, causing `RuntimeError` when importing non-contiguous or misaligned tensors from frameworks like PyTorch (e.g., tensor slices, transposed tensors). The C++ `Tensor::FromDLPack` already defaulted to no checks (`require_alignment=0, require_contiguous=false`), creating an asymmetry between the C++ and Python layers.

## Alternatives

### 1. Relax defaults, provide opt-in validation utilities (chosen)

Change Python defaults to match C++ (`require_alignment=0, require_contiguous=False`). Add `Tensor::IsAligned(size_t)` member method and `IsDirectAddressDevice()` utility for callers who need validation.

- Pros: Maximum interop breadth. Consistent C++/Python defaults. Kernels that need alignment can check explicitly.
- Cons: Removes an early-detection safety net. Alignment issues surface later (at kernel launch) rather than at import time.

### 2. Keep strict defaults, require callers to opt out

Maintain `require_alignment=8, require_contiguous=True`. Callers explicitly pass `require_alignment=0` when needed.

- Pros: Conservative safety. Catches alignment issues early.
- Cons: Breaks common workflows (PyTorch tensor slices fail by default). Forces boilerplate at every `from_dlpack` call for non-contiguous data.

### 3. Global configuration flag

Add a `tvm_ffi.config.dlpack_require_alignment` setting.

- Pros: User-configurable default.
- Cons: Adds global mutable state. Difficult to reason about in multi-library environments.

## Decision

Alternative 1. The parameter names were also corrected from `required_*` to `require_*` for consistency with the C++ API.

## Consequences

- Breaking parameter rename: `required_alignment` -> `require_alignment`, `required_contiguous` -> `require_contiguous`.
- `core.__dlpack_auto_import_required_alignment__` constant removed.
- All auto-conversion paths (convert, make_args for `__dlpack__` and torch.Tensor) now import without restrictions.
- Kernels assuming 8-byte alignment must now explicitly check `tensor.IsAligned(8)`.

## Related Design Docs

- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- Tensor DLPack import defaults
- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- from_dlpack parameters
- Commit: `.knowledge/commits/2025-09-08-1b824e88743a89343ad7493691bbdf5fdf2830c9.md` + `1b824e8`
