---
sha: "0f8bf9fc582fff89e838cadf2aacbfb2a5724ddf"
date: "2025-10-20T21:07:30-07:00"
author: "Tianqi Chen"
subject: "Introduce Device Protocol (#179)"
nature: ["feat"]
tags: ["python", "dlpack", "device"]
scope: ["python", "tests"]
risk: "low"
---

# 0f8bf9f — Introduce Device Protocol (#179)

## TL;DR
- Adds support for `__dlpack_device__` protocol: objects implementing this method (but not `__dlpack__`) are automatically accepted as device arguments in FFI calls.
- Adds new Cython setter `TVMFFIPyArgSetterDLPackDeviceProtocol_` dispatching on the presence of `__dlpack_device__`.
- Adds a test verifying the protocol round-trips through the echo function.

## Why (intent / motivation)
- Symmetric to the dtype protocol added in #178; allows any DLPack-compliant device object to be used directly in FFI calls.

## What changed (facts from diff)
- `python/tvm_ffi/cython/function.pxi`: New `TVMFFIPyArgSetterDLPackDeviceProtocol_` that reads `arg.__dlpack_device__()` and sets `out.v_device`; registered in factory when class has `__dlpack_device__` but not `__dlpack__`.
- `tests/python/test_function.py`: Added `test_function_with_dlpack_device_protocol` with a local `DLPackDeviceProtocol` class.

## Public surface changes (if any)
- API: Objects with `__dlpack_device__()` (and without `__dlpack__`) are now automatically accepted as `Device` arguments in FFI calls.
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/python/test_function.py::test_function_with_dlpack_device_protocol`
- How to verify manually: `uv run pytest tests/python/test_function.py::test_function_with_dlpack_device_protocol -vvs`
- CI impact: none

## Risk & rollout notes
- Risk level: low — purely additive.
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `python/tvm_ffi/cython/function.pxi` +18/-0 (M)
- `tests/python/test_function.py` +16/-0 (M)

### Notable symbols / endpoints / configs touched
- `TVMFFIPyArgSetterDLPackDeviceProtocol_` in `cython/function.pxi`
- `TVMFFIPyArgSetterFactory_` dispatch logic

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/0f8bf9fc582fff89e838cadf2aacbfb2a5724ddf.md`
