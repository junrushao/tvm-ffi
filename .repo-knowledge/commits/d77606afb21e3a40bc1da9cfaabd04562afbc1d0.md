---
sha: "d77606afb21e3a40bc1da9cfaabd04562afbc1d0"
date: "2025-09-19T13:09:27-07:00"
author: "Yaxing Cai"
subject: "feat: Enable torch/numpy/ml_dtypes dtype as ffi input (#25)"
nature: ["feat"]
tags: ["test"]
scope: ["python", "include", "tests"]
risk: "medium"
---

# d77606a — feat: Enable torch/numpy/ml_dtypes dtype as ffi input (#25)

## TL;DR
- Allows `torch.dtype`, `numpy.dtype`, and `ml_dtypes` dtype objects to be passed directly as FFI function arguments.
- Adds Cython argument setter dispatch for these types, mapping them to `DLDataType` at call time.
- Adds `_convert_torch_dtype_to_ffi_dtype` and `_convert_numpy_dtype_to_ffi_dtype` conversion functions.
- Fixes missing `"bool"` case in `DLDataTypeCodeAsCStr` in the C++ header.
- Adds comprehensive tests covering all supported dtypes from all three libraries.

## Why (intent / motivation)
- Users often have dtype objects from PyTorch or NumPy and want to pass them to TVM FFI functions that expect `DLDataType`. Without this, users had to manually convert before every call.

## What changed (facts from diff)
- `include/tvm/ffi/dtype.h`: Added `kDLBool` case to `DLDataTypeCodeAsCStr`.
- `python/tvm_ffi/cython/dtype.pxi`: Added import guards for torch/numpy/ml_dtypes; added `TORCH_DTYPE_TO_DTYPE`, `NUMPY_DTYPE_TO_DTYPE`, `MLDTYPES_DTYPE_TO_DTYPE` mapping dicts; added `_convert_torch_dtype_to_ffi_dtype` and `_convert_numpy_dtype_to_ffi_dtype` functions.
- `python/tvm_ffi/cython/function.pxi`: Added `TVMFFIPyArgSetterDTypeFromTorch_` and `TVMFFIPyArgSetterDTypeFromNumpy_` Cython setters; wired them into `TVMFFIPyArgSetterFactory_`.
- `python/tvm_ffi/_convert.py`: Added `torch.dtype` and `numpy.dtype` branches in `convert()`.
- `tests/python/test_dtype.py`: Added `test_torch_dtype_conversion`, `test_numpy_dtype_conversion`, `test_ml_dtypes_dtype_conversion`.

## Public surface changes (if any)
- API: `tvm_ffi.convert(torch_dtype)` and `tvm_ffi.convert(numpy_dtype)` now return a `DataType` object; torch/numpy dtypes are now accepted as direct FFI call arguments.
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/python/test_dtype.py` (three new test functions)
- How to verify manually: `uv run pytest -vvs tests/python/test_dtype.py`
- CI impact: New test coverage; torch/numpy/ml_dtypes are optional (tests use `pytest.importorskip`).

## Risk & rollout notes
- Risk level: medium — new argument dispatch paths; incorrect mapping would silently pass wrong dtypes
- Rollout/migration: none, additive
- Follow-ups: none

## Evidence
### Changed files
- `include/tvm/ffi/dtype.h` +3/-0 (modified)
- `python/tvm_ffi/_convert.py` +15/-1 (modified)
- `python/tvm_ffi/cython/dtype.pxi` +113/-0 (modified)
- `python/tvm_ffi/cython/function.pxi` +37/-0 (modified)
- `tests/python/test_dtype.py` +79/-0 (modified)

### Notable symbols / endpoints / configs touched
- `TORCH_DTYPE_TO_DTYPE`, `NUMPY_DTYPE_TO_DTYPE`, `MLDTYPES_DTYPE_TO_DTYPE` (lookup tables)
- `_convert_torch_dtype_to_ffi_dtype`, `_convert_numpy_dtype_to_ffi_dtype`
- `TVMFFIPyArgSetterDTypeFromTorch_`, `TVMFFIPyArgSetterDTypeFromNumpy_`
- `DLDataTypeCodeAsCStr` (`kDLBool` case)

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/d77606afb21e3a40bc1da9cfaabd04562afbc1d0.md`
