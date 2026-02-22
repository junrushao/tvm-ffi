---
sha: "6adc8df7d2180ea14e463d3beeaa3d7eecb6f897"
date: "2026-02-16T21:08:20-05:00"
author: "Tianqi Chen"
subject: "[EXTRA] Introduce StructuralKey (#453)"
nature: ["feat"]
tags: ["test"]
scope: ["include/tvm/ffi/extra", "src/ffi/extra", "python/tvm_ffi", "tests"]
risk: "low"
---

# 6adc8df — [EXTRA] Introduce StructuralKey (#453)

## TL;DR
- Introduces `StructuralKey`, a wrapper object that caches a structural hash and uses structural equality/hash for map lookups and comparisons.
- Registers `__any_hash__` and `__any_equal__` type attributes on `StructuralKeyObj` so it can be used as a key in `Map<Any, Any>` with structural semantics.
- Exposes `tvm_ffi.StructuralKey` in Python with `__hash__` and `__eq__` delegates, and the `ffi.StructuralEqual` global function.

## Why (intent / motivation)
- Provides a convenient wrapper to use structural equality and hash in containers (both C++ `std::unordered_map<StructuralKey, T>` and `tvm_ffi.Map`) without manual hash caching.

## What changed (facts from diff)
- New header `include/tvm/ffi/extra/structural_key.h` (+103 lines): `StructuralKeyObj` (with `key` and `hash_i64` fields) and `StructuralKey` ref wrapper with `operator==`/`!=`; `std::hash<StructuralKey>` specialization.
- `src/ffi/extra/reflection_extra.cc`: registers `StructuralKeyObj` fields and `__any_hash__`/`__any_equal__` type attributes; exposes `ffi.StructuralKey` and `ffi.StructuralKeyEqual` globals.
- `src/ffi/extra/structural_equal.cc`: registers new `ffi.StructuralEqual` global function.
- New Python file `python/tvm_ffi/structural.py` (+230 lines): `structural_equal`, `structural_hash`, `get_first_structural_mismatch` functions with docstrings; `StructuralKey` class with `__hash__`/`__eq__`.
- `python/tvm_ffi/__init__.py`: exports `StructuralKey`, `structural_equal`, `structural_hash`, `get_first_structural_mismatch`.
- New C++ test `tests/cpp/extra/test_structural_key.cc` (+79 lines).
- New Python test `tests/python/test_structural.py` (+92 lines).

## Public surface changes (if any)
- API: `tvm_ffi.StructuralKey`, `tvm_ffi.structural_equal`, `tvm_ffi.structural_hash`, `tvm_ffi.get_first_structural_mismatch`; C++ `StructuralKey`, `StructuralKeyObj`; `ffi.StructuralEqual` global
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/cpp/extra/test_structural_key.cc`, `tests/python/test_structural.py`
- How to verify manually: `uv run pytest -vvs tests/python/test_structural.py`
- CI impact: none

## Risk & rollout notes
- Risk level: low — additive new type and utilities; no existing code modified
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `include/tvm/ffi/extra/structural_key.h` +103/-0 (A)
- `python/tvm_ffi/__init__.py` +12/-0 (M)
- `python/tvm_ffi/_ffi_api.py` +6/-0 (M)
- `python/tvm_ffi/structural.py` +230/-0 (A)
- `src/ffi/extra/reflection_extra.cc` +37/-1 (M)
- `src/ffi/extra/structural_equal.cc` +3/-1 (M)
- `tests/cpp/extra/test_structural_key.cc` +79/-0 (A)
- `tests/python/test_structural.py` +92/-0 (A)

### Notable symbols / endpoints / configs touched
- `StructuralKey`, `StructuralKeyObj` — new C++ types
- `ffi.StructuralKey`, `ffi.StructuralKeyEqual`, `ffi.StructuralEqual` — new global functions
- `tvm_ffi.structural_equal`, `tvm_ffi.structural_hash` — promoted to top-level Python API
- `__any_hash__`, `__any_equal__` type attrs on `StructuralKeyObj`

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/6adc8df7d2180ea14e463d3beeaa3d7eecb6f897.md`
