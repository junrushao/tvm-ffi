---
sha: "6adc8df7d2180ea14e463d3beeaa3d7eecb6f897"
date: "2026-02-16"
author: "Tianqi Chen"
subject: "[EXTRA] Introduce StructuralKey (#453)"
nature: ["feat"]
tags: ["design"]
scope: ["extra", "python", "structural"]
risk: "low"
---

# 6adc8df -- [EXTRA] Introduce StructuralKey (#453)

## TL;DR
- Introduces `StructuralKey` as a wrapper class that caches structural hash and uses structural equality for comparisons.
- Adds new C++ header `structural_key.h`, Python module `structural.py`, and Python class `StructuralKey`.
- Registers `ffi.StructuralKey`, `ffi.StructuralKeyEqual`, and `ffi.StructuralEqual` global functions.
- Re-exports `structural_equal`, `structural_hash`, `get_first_structural_mismatch`, and `StructuralKey` from `tvm_ffi`.

## Why (intent / motivation)
- Provides a convenient wrapper class to indicate use of structural equal/hash in comparisons, useful as a key type in hash maps where structural equality semantics are desired (e.g., Python dicts or `tvm_ffi.Map`).

## What changed (facts from diff)
- `include/tvm/ffi/extra/structural_key.h`: New C++ header defining `StructuralKeyObj` (stores `key` + cached `hash_i64`) and `StructuralKey` ref wrapper with `operator==`/`!=` and `std::hash` specialization.
- `python/tvm_ffi/__init__.py`: Imports and re-exports `StructuralKey`, `structural_equal`, `structural_hash`, `get_first_structural_mismatch` from new `structural` module.
- `python/tvm_ffi/_ffi_api.py`: Adds stubs for `StructuralKey`, `StructuralKeyEqual`, `StructuralEqual`.
- `python/tvm_ffi/structural.py`: New 230-line module with `structural_equal()`, `structural_hash()`, `get_first_structural_mismatch()` convenience functions and `StructuralKey` Python class with `__hash__`/`__eq__`.
- `src/ffi/extra/reflection_extra.cc`: Registers `StructuralKeyObj` reflection, `__any_hash__`/`__any_equal__` type attributes, and `ffi.StructuralKey`/`ffi.StructuralKeyEqual` global functions.
- `src/ffi/extra/structural_equal.cc`: Registers `ffi.StructuralEqual` global function.
- `tests/cpp/extra/test_structural_key.cc`: New C++ tests for equality, std::hash, unordered_map usage, and Map integration.
- `tests/python/test_structural.py`: New Python tests for StructuralKey, helpers, Map/dict usage, and tensor content policy.

## Public surface changes (if any)
- API: New `tvm_ffi.StructuralKey` class, new `tvm_ffi.structural_equal()`, `tvm_ffi.structural_hash()`, `tvm_ffi.get_first_structural_mismatch()` functions. New C++ `tvm::ffi::StructuralKey` class.
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/cpp/extra/test_structural_key.cc`, `tests/python/test_structural.py`
- How to verify manually: `uv run pytest -vvs tests/python/test_structural.py` and run C++ tests
- CI impact: Adds new test files.

## Risk & rollout notes
- Risk level: low -- Purely additive new feature. No existing behavior changed.
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `include/tvm/ffi/extra/structural_key.h` (+103/-0, added)
- `python/tvm_ffi/__init__.py` (+12/-0, modified)
- `python/tvm_ffi/_ffi_api.py` (+6/-0, modified)
- `python/tvm_ffi/structural.py` (+230/-0, added)
- `src/ffi/extra/reflection_extra.cc` (+38/-1, modified)
- `src/ffi/extra/structural_equal.cc` (+4/-1, modified)
- `tests/cpp/extra/test_structural_key.cc` (+79/-0, added)
- `tests/python/test_structural.py` (+92/-0, added)

### Notable symbols / endpoints / configs touched
- `StructuralKeyObj`, `StructuralKey` (new C++ types)
- `ffi.StructuralKey`, `ffi.StructuralKeyEqual`, `ffi.StructuralEqual` (new global functions)
- `__any_hash__`, `__any_equal__` type attributes for `StructuralKeyObj`

### Diff notes
- Diff truncated: no
