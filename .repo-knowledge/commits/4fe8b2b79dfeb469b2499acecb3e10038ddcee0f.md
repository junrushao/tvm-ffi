---
sha: "4fe8b2b79dfeb469b2499acecb3e10038ddcee0f"
date: "2025-09-29T14:32:11-04:00"
author: "Tianqi Chen"
subject: "[ABI] Further clarify Function ABI in cpp (#71)"
nature: ["refactor"]
tags: ["cpp", "abi"]
scope: ["include", "tests"]
risk: "medium"
---

# 4fe8b2b — [ABI] Further clarify Function ABI in cpp (#71)

## TL;DR
- Adds `cpp_call` field to `TVMFFIFunctionCell` (C ABI struct) alongside the existing `safe_call`; `cpp_call` is the raw C++ throwing call path, `safe_call` is the exception-catching path.
- Removes the private `FunctionObj::call` field; `CallPacked` now checks `cpp_call` first, falling back to `CppCallRedirectToSafeCall`.
- Removes `ImportedFunctionObjImpl` and `RedirectCallToSafeCall<>` CRTP helper; simplifies `ExternCFunctionObjImpl`.
- Adds `Function::FromExternC(nullptr, fn, nullptr)` fast path via `ExternCFunctionObjNullHandleImpl`.

## Why (intent / motivation)
- Clarify the function ABI so it is clear which call path is C++ (throwing) vs C-safe; allows cross-DLL calls to always go through `safe_call` while same-DLL calls can use the fast `cpp_call` path.

## What changed (facts from diff)
- `include/tvm/ffi/c_api.h`: `TVMFFIFunctionCell` gains `void* cpp_call` field.
- `include/tvm/ffi/function.h`: `FunctionObj::call` removed; `CallPacked` uses `cpp_call ? reinterpret_cast<FCall>(cpp_call) : CppCallRedirectToSafeCall`.
- `FunctionObjImpl` renamed internal call from `Call` to `CppCall`; sets `cpp_call` instead of `call`.
- `ExternCFunctionObjImpl` simplified; no longer inherits from CRTP; `cpp_call = nullptr`.
- `ExternCFunctionObjNullHandleImpl` added for null-handle raw function pointers.
- `ImportedFunctionObjImpl` removed entirely; `Function::ImportFromExternDLL` removed.
- `TVM_FFI_DLL_EXPORT_TYPED_FUNC` updated: `args` parameter now `const TVMFFIAny*`.
- Version bumped to `0.1.0b12`.

## Public surface changes (if any)
- API: `TVMFFIFunctionCell` ABI gains `cpp_call` field (ABI-breaking for existing compiled objects). `Function::ImportFromExternDLL` removed. `TVM_FFI_DLL_EXPORT_TYPED_FUNC` `args` signature changed to `const TVMFFIAny*`.
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/cpp/test_function.cc` (+10, `TEST(Func, FromExternC)`).
- How to verify manually: `ctest --test-dir build_test -R Func`
- CI impact: none

## Risk & rollout notes
- Risk level: medium — `TVMFFIFunctionCell` struct layout changed; any pre-compiled objects using the old layout are ABI-incompatible.
- Rollout/migration: Recompile all code using `TVMFFIFunctionCell`; update any usage of `Function::ImportFromExternDLL` (removed).
- Follow-ups: none

## Evidence
### Changed files
- `include/tvm/ffi/c_api.h` +13/-0 (M)
- `include/tvm/ffi/function.h` +65/-100 (M)
- `pyproject.toml` +1/-1 (M) — version bump
- `python/tvm_ffi/__init__.py` +1/-1 (M) — version bump
- `tests/cpp/test_function.cc` +10/-0 (M)

### Notable symbols / endpoints / configs touched
- `TVMFFIFunctionCell::cpp_call`
- `FunctionObj::CallPacked`
- `ExternCFunctionObjNullHandleImpl`
- `ExternCFunctionObjImpl`
- `TVM_FFI_DLL_EXPORT_TYPED_FUNC`
- `Function::FromExternC`

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/4fe8b2b79dfeb469b2499acecb3e10038ddcee0f.md`
