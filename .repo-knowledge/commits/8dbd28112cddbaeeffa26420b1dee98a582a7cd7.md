---
sha: "8dbd28112cddbaeeffa26420b1dee98a582a7cd7"
date: "2025-11-21T20:01:22-05:00"
author: "Tianqi Chen"
subject: "[TORCH] Fix precise version of f8e8m0 support (#282)"
nature: ["fix"]
tags: []
scope: ["include", "python"]
risk: "low"
---

# 8dbd281 — [TORCH] Fix precise version of f8e8m0 support (#282)

## TL;DR
- Fixes version guard for `Float8_e8m0fnu` (f8e8m0) dtype to be available in PyTorch 2.7+, not only 2.8+
- Keeps `Float4_e2m1fn_x2` gated at 2.8+
- Bumps `TVM_FFI_VERSION_PATCH` from 3 to 4

## Why (intent / motivation)
- The f8e8m0 float type was introduced in PyTorch 2.7, not 2.8; the original version guard was too restrictive

## What changed (facts from diff)
- `python/tvm_ffi/utils/_build_optional_torch_c_dlpack.py`: Changed `#if TORCH_VERSION_MAJOR >= 2 && TORCH_VERSION_MINOR >= 8` to `#if (TORCH_VERSION_MAJOR > 2) || (TORCH_VERSION_MAJOR == 2 && TORCH_VERSION_MINOR >= 7)` for `Float8_e8m0fnu` in both `getDLDataTypeForDLPackv1` and `toScalarTypeForDLPackv1`; added a separate guard for `Float4_e2m1fn_x2` at `>= 2.8`
- `include/tvm/ffi/c_api.h`: `TVM_FFI_VERSION_PATCH` bumped 3 → 4

## Public surface changes (if any)
- API: none
- Flags/config: none
- Data formats/schemas: `Float8_e8m0fnu` DLPack dtype now accessible on PyTorch 2.7+

## Tests & verification
- Added/updated tests: none
- How to verify manually: Build the torch-c-dlpack extension with PyTorch 2.7 and verify f8e8m0 dtype round-trips
- CI impact: none

## Risk & rollout notes
- Risk level: low — expands supported dtype range for an existing feature; no breaking change
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `include/tvm/ffi/c_api.h` +1/-1 (modified)
- `python/tvm_ffi/utils/_build_optional_torch_c_dlpack.py` +6/-2 (modified)

### Notable symbols / endpoints / configs touched
- `getDLDataTypeForDLPackv1` — Float8_e8m0fnu version guard fixed
- `toScalarTypeForDLPackv1` — Float8_e8m0fnu version guard fixed
- `TVM_FFI_VERSION_PATCH` — bumped to 4

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/8dbd28112cddbaeeffa26420b1dee98a582a7cd7.md`
