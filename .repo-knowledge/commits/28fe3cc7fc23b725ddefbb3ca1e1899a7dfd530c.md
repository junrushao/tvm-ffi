---
sha: "28fe3cc7fc23b725ddefbb3ca1e1899a7dfd530c"
date: "2025-10-03T16:07:06-07:00"
author: "Junru Shao"
subject: "feat: Metadata and JSON-based type schemas for fields, methods and global funcs (#36)"
nature: ["feat"]
tags: ["cpp", "python", "reflection"]
scope: ["include", "src", "python", "tests"]
risk: "medium"
---

# 28fe3cc — feat: Metadata and JSON-based type schemas for fields, methods and global funcs (#36)

## TL;DR
- Introduces JSON-based type schema generation (`TypeSchema<T>`) for all FFI types (primitives, containers, callables).
- Adds a `Metadata` trait/builder allowing arbitrary key-value pairs to be attached to registered fields, methods, and global functions.
- Exposes metadata as `dict[str, Any]` in Python via `tvm_ffi.get_global_func_metadata(name)` and as `TypeField.metadata` / `TypeMethod.metadata`.
- Adds `TypeSchema` Python class for parsing JSON schema strings into structured objects.

## Why (intent / motivation)
- Richer machine-readable type information enables tooling, static analysis, stub generation, and dynamic dispatch mechanisms built on top of TVM FFI without requiring recompilation.

## What changed (facts from diff)
- `include/tvm/ffi/reflection/registry.h`: `FieldInfoBuilder`/`MethodInfoBuilder` added; `Metadata{{...}}` attachment support added to `GlobalDef` and `ObjectDef`; schema serialized into the `metadata` JSON field.
- `include/tvm/ffi/function_details.h`: `TypeSchema<T>` template added for all supported FFI types.
- `include/tvm/ffi/string.h`: `EscapeString` utility added.
- Multiple container headers (`array.h`, `map.h`, `tuple.h`, `variant.h`, `tensor.h`, `dtype.h`, `rvalue_ref.h`, `type_traits.h`, `base_details.h`): `TypeSchema<T>` specializations added.
- `src/ffi/extra/testing.cc`: test registrations with metadata and type schema examples added.
- `src/ffi/extra/json_writer.cc`: refactored (-47 lines).
- `src/ffi/function.cc`: `get_global_func_metadata` global function registered.
- `python/tvm_ffi/cython/type_info.pxi`: `TypeSchema` and `metadata` parsing added (+82 lines).
- `python/tvm_ffi/cython/object.pxi`: metadata exposed in field/method info (+7/-1).
- `python/tvm_ffi/registry.py`: `get_global_func_metadata` function added.
- `python/tvm_ffi/__init__.py`: `get_global_func_metadata` exported.
- `python/tvm_ffi/core.pyi`: `TypeSchema`, `TypeField.metadata`, `TypeMethod.metadata` stubs added.
- `python/tvm_ffi/testing.py`: test helpers added.
- `tests/cpp/test_metadata.cc` and `tests/python/test_metadata.py` added.

## Public surface changes (if any)
- API: `tvm_ffi.get_global_func_metadata(name: str) -> dict[str, Any]`; `TypeField.metadata`, `TypeMethod.metadata`; `TypeSchema` class; C++ `Metadata{{...}}` attachment in registration DSL; `TypeSchema<T>` template.
- Flags/config: none
- Data formats/schemas: JSON schema format in `metadata["type_schema"]` field.

## Tests & verification
- Added/updated tests: `tests/cpp/test_metadata.cc` (new), `tests/python/test_metadata.py` (new).
- How to verify manually: `uv run pytest -vvs tests/python/test_metadata.py`; `ctest --test-dir build_test -R Metadata`
- CI impact: none

## Risk & rollout notes
- Risk level: medium — large feature addition touching many headers; no breaking changes to existing APIs but adds new type constraints in templates.
- Rollout/migration: none
- Follow-ups: stub generation tooling (`tvm-ffi-stubgen`) can now consume `type_schema` from metadata.

## Evidence
### Changed files
- `include/tvm/ffi/base_details.h` +16/-0 (M)
- `include/tvm/ffi/container/array.h` +7/-0 (M)
- `include/tvm/ffi/container/map.h` +8/-0 (M)
- `include/tvm/ffi/container/tensor.h` +3/-0 (M)
- `include/tvm/ffi/container/tuple.h` +9/-2 (M)
- `include/tvm/ffi/container/variant.h` +8/-0 (M)
- `include/tvm/ffi/dtype.h` +3/-0 (M)
- `include/tvm/ffi/function.h` +6/-0 (M)
- `include/tvm/ffi/function_details.h` +41/-2 (M)
- `include/tvm/ffi/reflection/registry.h` +122/-21 (M)
- `include/tvm/ffi/rvalue_ref.h` +8/-0 (M)
- `include/tvm/ffi/string.h` +70/-2 (M)
- `include/tvm/ffi/type_traits.h` +34/-0 (M)
- `python/tvm_ffi/__init__.py` +2/-0 (M)
- `python/tvm_ffi/core.pyi` +13/-0 (M)
- `python/tvm_ffi/cython/object.pxi` +7/-1 (M)
- `python/tvm_ffi/cython/type_info.pxi` +82/-0 (M)
- `python/tvm_ffi/registry.py` +20/-0 (M)
- `python/tvm_ffi/testing.py` +4/-0 (M)
- `src/ffi/extra/json_writer.cc` +2/-47 (M)
- `src/ffi/extra/testing.cc` +174/-0 (M)
- `src/ffi/function.cc` +8/-? (M)
- `tests/cpp/test_metadata.cc` (A)
- `tests/python/test_metadata.py` (A)

### Notable symbols / endpoints / configs touched
- `TypeSchema<T>` template in `function_details.h`
- `Metadata` builder in `reflection/registry.h`
- `EscapeString` in `string.h`
- `tvm_ffi.get_global_func_metadata`
- `TypeSchema` Python class
- `TypeField.metadata`, `TypeMethod.metadata`

### Diff notes
- Diff truncated: yes (bundle exceeds token limit)

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/28fe3cc7fc23b725ddefbb3ca1e1899a7dfd530c.md`
