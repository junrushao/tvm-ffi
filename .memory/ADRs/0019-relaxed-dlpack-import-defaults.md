---
adr: "0019"
title: "Relaxed DLPack Import Defaults (Alignment=0, Contiguous=False)"
status: "accepted"
date: "2025-09-08"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "Python FFI users"
tags:
  - "architecture"
  - "tensor"
  - "dlpack"
source_commits:
  - "1b824e88743a89343ad7493691bbdf5fdf2830c9"
source_ledgers:
  - ".memory/commits/2025-09-08-1b824e88743a89343ad7493691bbdf5fdf2830c9.md"
---

# ADR-0019: Relaxed DLPack Import Defaults (Alignment=0, Contiguous=False)

## TL;DR
- `from_dlpack()` defaults changed from `require_alignment=8, require_contiguous=True` to `require_alignment=0, require_contiguous=False`, making tensor import permissive by default.
- Callers who need strict alignment or contiguity checks must now explicitly opt in.

## Status
Accepted

## Context
The previous default DLPack import settings required 8-byte alignment and contiguity for all imported tensors. This rejected valid tensors from frameworks like PyTorch that may produce non-contiguous views (e.g., transposed tensors) or tensors with non-standard alignment. Users encountered unexpected `ValueError` exceptions when passing framework tensors to FFI functions, even when the downstream kernel could handle the non-contiguous/non-aligned data.

The global `__dlpack_auto_import_required_alignment__` constant was used by auto-import call sites (`_convert.py`, `function.pxi`), but it was inflexible -- a single global setting for all import paths.

## Decision Drivers
- **Interoperability**: FFI should accept the widest possible set of valid tensors from external frameworks.
- **Least surprise**: Users expect `func(torch_tensor)` to work without needing to know about alignment requirements.
- **Explicit validation**: Kernels that require specific alignment or contiguity should validate their own inputs, not rely on import-time rejection.

## Decision
Change `from_dlpack()` defaults to `require_alignment=0, require_contiguous=False`. Remove the global `__dlpack_auto_import_required_alignment__` constant. All auto-import call sites use the relaxed defaults.

Additionally:
- Rename parameter names from `required_alignment`/`required_contiguous` to `require_alignment`/`require_contiguous` throughout Cython bindings.
- Extract `IsDirectAddressDevice()` as a public C++ utility.
- Add `Tensor::IsAligned()` as a member method.

## Alternatives Considered
### Keep strict defaults with per-function override
- Pros: Safe by default. Catches alignment bugs early.
- Cons: Users constantly encounter import failures with valid tensors. Every FFI function call site needs to override defaults.

### Make alignment configurable via environment variable
- Pros: Non-breaking. Users can opt into relaxed behavior.
- Cons: Global settings are inflexible. Difficult to discover. Environment variables are not composable.

### Remove alignment checking entirely
- Pros: Simplest implementation.
- Cons: No way to validate alignment when needed. Loses useful diagnostic capability.

## Why This Option Won
- Permissive by default matches user expectations from PyTorch, NumPy, and other frameworks.
- Alignment/contiguity validation is better done at the kernel level, not the import level.
- The `require_alignment` and `require_contiguous` parameters remain available for explicit validation when needed.
- New `Tensor::IsAligned()` and `IsDirectAddressDevice()` APIs make it easy for kernels to check alignment at call time.

## Consequences
### Positive
- Tensors from PyTorch, NumPy, CuPy, and other frameworks are accepted without extra configuration.
- No more unexpected `ValueError` on tensor import.
- Cleaner parameter names (`require_*` instead of `required_*`).

### Negative
- Kernels that assume aligned/contiguous input may silently receive non-aligned/non-contiguous data. This shifts the validation burden to kernel authors.

### Risks
- A kernel that previously relied on import-time alignment validation may now receive misaligned data, causing segfaults or incorrect results. Mitigated by providing `Tensor::IsAligned()` for runtime checks.

## Implementation Notes
- Commit `1b824e8` changed defaults in `from_dlpack()`, renamed parameters, extracted `IsDirectAddressDevice()`, and added `Tensor::IsAligned()`.
- All auto-import call sites (`_convert.py`, `function.pxi`) now use relaxed defaults.
- `__dlpack_auto_import_required_alignment__` global constant removed.

## Validation
- Existing tensor import tests pass with relaxed defaults.
- Tests with non-contiguous and non-aligned tensors added.

## Migration and Rollback
- Migration: Code that relied on `required_alignment`/`required_contiguous` keyword names must update to `require_alignment`/`require_contiguous`.
- Kernels that require alignment should add explicit `IsAligned()` checks.
- Rollback: Restore old defaults and re-add the global alignment constant.

## Related Design Docs
- [.memory/designs/0004-container-library.md](.memory/designs/0004-container-library.md) -- Tensor DLPack import path.
- [.memory/designs/0011-cython-binding-layer.md](.memory/designs/0011-cython-binding-layer.md) -- Cython auto-import in `function.pxi`.

## Related Diagrams
None

## Evidence Matrix
- `from_dlpack()` default change -> `.memory/commits/2025-09-08-1b824e88743a89343ad7493691bbdf5fdf2830c9.md` + `1b824e8` + `python/tvm_ffi/cython/ndarray.pxi`
- Parameter rename (`required_*` -> `require_*`) -> `1b824e8` + `python/tvm_ffi/cython/ndarray.pxi`, `python/tvm_ffi/_tensor.py`
- `IsDirectAddressDevice()` extraction -> `1b824e8` + `include/tvm/ffi/container/ndarray.h`
- `Tensor::IsAligned()` member method -> `1b824e8` + `include/tvm/ffi/container/ndarray.h`
- `__dlpack_auto_import_required_alignment__` removal -> `1b824e8` + `python/tvm_ffi/_convert.py`, `python/tvm_ffi/cython/function.pxi`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Downstream kernels should audit their alignment requirements and add explicit `Tensor::IsAligned()` checks where needed.
