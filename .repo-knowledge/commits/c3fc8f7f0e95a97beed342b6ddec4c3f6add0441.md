---
sha: "c3fc8f7f0e95a97beed342b6ddec4c3f6add0441"
date: "2025-11-30T08:14:44+08:00"
author: "DarkSharpness"
subject: "[Feature] Support vanilla C++ STL in FFI. (#228)"
nature: ["feat"]
tags: ["test"]
scope: ["include", "tests"]
risk: "medium"
---

# c3fc8f7 — [Feature] Support vanilla C++ STL in FFI. (#228)

## TL;DR
- Adds `include/tvm/ffi/extra/stl.h` providing `TypeTraits` specializations for C++ STL containers: `std::array`, `std::vector`, `std::optional`, `std::variant`, `std::tuple`, `std::map`, `std::unordered_map`, and `std::function`
- Allows C++ exported functions to use STL types directly as argument and return types
- Adds `MapObj` friendship to `TypeTraits` for internal access

## Why (intent / motivation)
- Reduces boilerplate when building kernel libraries; users familiar with STL containers can use them directly without converting to `tvm::ffi::Array`, `Tuple`, `Map`, etc.

## What changed (facts from diff)
- New `include/tvm/ffi/extra/stl.h` (649 lines): full `TypeTraits` specializations for STL containers using the shared `STLTypeTrait` base
- `include/tvm/ffi/container/map.h`: Added `friend struct TypeTraits` to `MapObj`
- New test file `tests/python/cpp_src/test_stl.cc` with `test_tuple`, `test_vector`, `test_variant`, `test_map`, `test_map_2`, `test_function` exported functions
- New `tests/python/test_stl.py` with assertions covering all STL types

## Public surface changes (if any)
- API: New `include/tvm/ffi/extra/stl.h` header; STL types now usable in `TVM_FFI_DLL_EXPORT_TYPED_FUNC`
- Flags/config: none
- Data formats/schemas: New JSON type schema strings for STL types (e.g., `{"type":"std::vector","args":[...]}`)

## Tests & verification
- Added/updated tests: `tests/python/cpp_src/test_stl.cc`, `tests/python/test_stl.py`
- How to verify manually: `uv run pytest -vvs tests/python/test_stl.py`
- CI impact: New test file added to Python test suite

## Risk & rollout notes
- Risk level: medium — large new header; introduces new type dispatch paths. Note: follow-up PRs were needed to fix segfaults
- Rollout/migration: Opt-in via `#include <tvm/ffi/extra/stl.h>`; native tvm containers remain preferred for performance
- Follow-ups: Use-after-move fix (#293), segfault workarounds (#297, #298)

## Evidence
### Changed files
- `include/tvm/ffi/container/map.h` +3/-0 (modified)
- `include/tvm/ffi/extra/stl.h` +649/-0 (added)
- `tests/python/cpp_src/test_stl.cc` +99/-0 (added)
- `tests/python/test_stl.py` +51/-0 (added)

### Notable symbols / endpoints / configs touched
- `TypeTraits<std::vector<T>>`, `TypeTraits<std::tuple<...>>`, `TypeTraits<std::variant<...>>`, etc. — new specializations
- `STLTypeTrait` / `ListTemplate` / `MapTemplate` — internal base structs
- `MapObj` — added TypeTraits friend

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/c3fc8f7f0e95a97beed342b6ddec4c3f6add0441.md`
