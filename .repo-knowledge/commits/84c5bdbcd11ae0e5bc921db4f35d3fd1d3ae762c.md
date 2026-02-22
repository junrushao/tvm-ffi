---
sha: "84c5bdbcd11ae0e5bc921db4f35d3fd1d3ae762c"
date: "2025-12-23T14:45:32+08:00"
author: "DarkSharpness"
subject: "[Feature] Support dynamic-style overload for FFI object types (#286)"
nature: ["feat"]
tags: ["test"]
scope: ["include", "tests"]
risk: "medium"
---

# 84c5bdb — [Feature] Support dynamic-style overload for FFI object types (#286)

## TL;DR
- Added new header `include/tvm/ffi/reflection/overload.h` (501 lines) providing dynamic-style multiple dispatch for FFI object types
- Added `Function::FromPackedInplace` static method to construct a `Function` owning its callable while exposing a raw pointer to it
- Generalized `FunctionObjImpl` constructor to use perfect forwarding; made it non-copyable; exposed `GetCallable()`
- Added test suite `tests/cpp/test_overload.cc` (95 lines)

## Why (intent / motivation)
- Users building DSLs or dispatching systems on top of TVM FFI need to overload functions on argument types without writing manual type-checking boilerplate
- `Function::FromPackedInplace` supports the overload machinery by allowing the function object to hold a pointer back to its captured callable

## What changed (facts from diff)
- `include/tvm/ffi/function.h`: `FunctionObjImpl` constructor changed from lvalue/rvalue overloads to single variadic perfect-forwarding template; copy constructor and assignment deleted; `GetCallable()` method added; `Function::FromPackedInplace<TCallable>(args...)` static method added returning `std::tuple<Function, TCallable*>`
- `include/tvm/ffi/reflection/overload.h`: new header defining `OverloadBase`, `TypedOverload<Ret,Args...>`, `OverloadDispatcher`, `OverloadObjectDef<Class>` for building type-dispatched method tables; uses `std::optional`-based capture tuples
- `include/tvm/ffi/reflection/registry.h`: minor refactors to generalize helper methods used by the overload system (+25/-18)
- `tests/cpp/test_overload.cc`: 95-line test covering dispatch on integer and float arguments

## Public surface changes (if any)
- API: `Function::FromPackedInplace<TCallable>(args...)` — new static method; `FunctionObjImpl::GetCallable()` exposed; `FunctionObjImpl` no longer copyable
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/cpp/test_overload.cc` (new, 95 lines)
- How to verify manually: `cmake . -B build_test -DTVM_FFI_BUILD_TESTS=ON && cmake --build build_test && ctest -V --test-dir build_test -R overload`
- CI impact: new C++ test binary; added to ctest suite

## Risk & rollout notes
- Risk level: medium — `FunctionObjImpl` is now non-copyable and its constructor changed; any code that copied `FunctionObjImpl` directly will fail to compile
- Rollout/migration: `FunctionObjImpl` is an implementation detail; direct users should not be affected
- Follow-ups: clang-tidy lint fix needed (see commit 22f22e8)

## Evidence
### Changed files
- M `include/tvm/ffi/function.h` +37/-10
- A `include/tvm/ffi/reflection/overload.h` +501/-0
- M `include/tvm/ffi/reflection/registry.h` +25/-18
- A `tests/cpp/test_overload.cc` +95/-0

### Notable symbols / endpoints / configs touched
- `Function::FromPackedInplace<TCallable>` — new static factory method
- `FunctionObjImpl::GetCallable()` — new accessor
- `OverloadObjectDef<Class>` — new class in `overload.h`
- `TypedOverload<Ret, Args...>` — new dispatch template
- `CaptureTuple` / `CaptureTupleAux` — internal optional-based capture tuple types

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/84c5bdbcd11ae0e5bc921db4f35d3fd1d3ae762c.md`
