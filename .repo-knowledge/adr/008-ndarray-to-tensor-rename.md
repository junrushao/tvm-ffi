# ADR 008: Rename NDArray to Tensor

- Status: Accepted
- Date: 2025-09-06
- Owners: Tianqi Chen

## Context

The TVM FFI used `NDArray` (N-dimensional array) as its tensor abstraction
name, inherited from DLPack's `DLTensor` naming. However, the broader ML
ecosystem (PyTorch, JAX, TensorFlow) universally uses "Tensor" as the standard
name. The pre-1.0 phase of the standalone `tvm-ffi` repository provided an
opportunity for a global rename before the ABI freeze.

## Decision

Rename `NDArray`/`NDArrayObj` to `Tensor`/`TensorObj` across the entire
codebase in a single coordinated commit (`3a551d8`). This includes:

- C++ class names: `NDArray` -> `Tensor`, `NDArrayObj` -> `TensorObj`
- Header path: `ndarray.h` -> `tensor.h`
- Cython file: `ndarray.pxi` -> `tensor.pxi`
- Python module: `ndarray.py` -> `_tensor.py`
- Python class: `tvm_ffi.NDArray` -> `tvm_ffi.Tensor`
- Test files: `test_ndarray.cc` -> `test_tensor.cc`
- All include paths, type aliases, forward declarations, and docstring
  references across `include/`, `src/`, `python/`, `tests/`, `docs/`,
  and `examples/`.

The rename was performed as an ABI-breaking change, acceptable during the
pre-1.0 beta phase.

## Consequences

- Positive: Aligns with ML ecosystem naming conventions, reducing cognitive
  load for users coming from PyTorch, JAX, or other frameworks.
- Positive: Performed early in the standalone repo lifecycle, minimizing the
  number of downstream consumers that need updating.
- Negative: ABI-breaking change requiring all compiled binaries to be rebuilt.
- Negative: Any external code referencing `NDArray` must be updated.
- Migration/Rollout: All approximately 30 affected files were updated in a
  single commit. Downstream consumers must update their code to use
  `Tensor`/`TensorObj` and include `tensor.h` instead of `ndarray.h`.

## References
- Range summary: `.repo-knowledge/ranges/2025-09-30-CA9C3D1-F9179EC.md`
- Evidence commits: `3a551d83f7c05106fa8033a61970a5ce34aa8aef`
- External references: DLPack specification (dlpack.org)

## Related Design Docs
- `.repo-knowledge/design/009-tensor-and-dlpack.md`
- `.repo-knowledge/design/003-c-abi-stability.md`

## Notes
The Python-side API cleanup (`40f4d9d`) immediately followed, renaming
internal modules (`convert.py` -> `_convert.py`, `dtype.py` -> `_dtype.py`)
and adding `DLDeviceType` enum.
