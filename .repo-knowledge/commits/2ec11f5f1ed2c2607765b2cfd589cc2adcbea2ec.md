---
sha: "2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec"
date: "2025-07-26T12:20:37-04:00"
author: "Tianqi Chen"
subject: "[FFI][REFACTOR] Enable custom s_hash/equal (#18165)"
nature: ["feat"]
tags: ["test"]
scope: ["include", "src", "tests"]
risk: "medium"
---

# 2ec11f5 — [FFI][REFACTOR] Enable custom s_hash/equal (#18165)

## TL;DR
- Introduces `kTVMFFISEqHashKindCustomTreeNode` (value 6) to allow types to opt in to custom `__s_equal__` and `__s_hash__` functions registered via `TypeAttrDef`.
- Implements the dispatch in `structural_equal.cc` and `structural_hash.cc` to call the registered custom functions when a type uses this kind.
- Adds `TCustomFuncObj` test object demonstrating custom equal/hash.
- Adds `TVM_FFI_USE_EXTRA_CXX_API` CMake option to conditionally compile the extra API sources.

## Why (intent / motivation)
- Types with complex semantic equality (e.g., functions with params as binding sites) need custom traversal logic that cannot be expressed purely through field-by-field comparison.
- The `TypeAttrDef` column mechanism provides a clean way to register these hooks per type.

## What changed (facts from diff)
- `c_api.h`: new enum value `kTVMFFISEqHashKindCustomTreeNode = 6` with documented function signatures.
- `structural_equal.cc`: if `custom_s_equal[type_info->type_index]` is non-null, dispatch to the registered function; handles free-var mapping for `FreeVar` kind after custom call.
- `structural_hash.cc`: analogous dispatch via `custom_s_hash` column.
- `CMakeLists.txt`: new `TVM_FFI_USE_EXTRA_CXX_API` option; structural equal/hash sources conditionally compiled.
- `tests/cpp/CMakeLists.txt`: `extra/` test sources included when `TVM_FFI_USE_EXTRA_CXX_API` is ON.
- `tests/cpp/extra/test_reflection_structural_equal_hash.cc` (moved to `extra/`): adds `StructuralEqualHash::CustomTreeNode` test.
- `tests/cpp/testing_object.h`: adds `TCustomFuncObj` / `TCustomFunc` with `SEqual`/`SHash` methods and `TypeAttrDef` registrations; `TVarObj` name field marked `SEqHashIgnore`.
- `src/ffi/object.cc`: fixes `column_index` bug (iterator value now used after `find`).

## Public surface changes (if any)
- API: new `kTVMFFISEqHashKindCustomTreeNode` enum value; new CMake option `TVM_FFI_USE_EXTRA_CXX_API`.
- Flags/config: `TVM_FFI_USE_EXTRA_CXX_API` CMake option (default ON).
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/cpp/extra/test_reflection_structural_equal_hash.cc` — `CustomTreeNode` test.
- How to verify manually: `cmake -DTVM_FFI_BUILD_TESTS=ON -DTVM_FFI_USE_EXTRA_CXX_API=ON --build build_test && ctest`
- CI impact: none expected

## Risk & rollout notes
- Risk level: medium — new enum value in stable C ABI.
- Rollout/migration: Types wishing to use custom equal/hash must set `_type_s_eq_hash_kind = kTVMFFISEqHashKindCustomTreeNode` and register `__s_equal__`/`__s_hash__` via `TypeAttrDef`.
- Follow-ups: Migrate StructuralEqual/Hash to new reflection (#18166).

## Evidence
### Changed files
- `CMakeLists.txt` +14/-4 (M)
- `include/tvm/ffi/c_api.h` +24/-1 (M)
- `src/ffi/object.cc` +2/-0 (M)
- `src/ffi/reflection/structural_equal.cc` +53/-9 (M)
- `src/ffi/reflection/structural_hash.cc` +39/-13 (M)
- `tests/cpp/CMakeLists.txt` +6/-0 (M)
- `tests/cpp/extra/test_reflection_structural_equal_hash.cc` +27/-1 (R085)
- `tests/cpp/test_reflection_accessor.cc` +1/-0 (M)
- `tests/cpp/testing_object.h` +56/-1 (M)

### Notable symbols / endpoints / configs touched
- `kTVMFFISEqHashKindCustomTreeNode`
- `TVM_FFI_USE_EXTRA_CXX_API` CMake option
- `reflection::TypeAttrColumn` (`__s_equal__`, `__s_hash__`)
- `TCustomFuncObj::SEqual`, `TCustomFuncObj::SHash`

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec.md`
