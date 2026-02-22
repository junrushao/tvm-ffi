---
sha: "84c5bdbcd11ae0e5bc921db4f35d3fd1d3ae762c"
date: "2025-12-23"
author: "DarkSharpness"
subject: "[Feature] Support dynamic-style overload for FFI object types (#286)"
nature: ["feat"]
tags: ["design"]
scope: ["cpp", "function", "reflection"]
risk: "medium"
---

# 84c5bdb -- [Feature] Support dynamic-style overload for FFI object types (#286)

## TL;DR
- Adds dynamic-style function overloading support for FFI object methods via a new `overload.h` header.
- Introduces `Function::FromPackedInplace` in `function.h` for constructing packed functions with access to the in-place callable.
- Generalizes `FunctionObjImpl` constructor to use variadic forwarding.
- Adds `OverloadObjectDef<Class>` builder for registering overloaded methods on FFI object types.

## Why (intent / motivation)
- Addresses discussion #265. FFI object methods previously could not have overloaded signatures (e.g., different argument types dispatching to different implementations). This feature enables Python-style dynamic dispatch for C++ FFI methods, selecting the correct overload based on argument types at runtime.

## What changed (facts from diff)
- **`include/tvm/ffi/function.h`**:
  - Added `#include <optional>` and `#include <tuple>`.
  - `FunctionObjImpl` constructor consolidated from two overloads (lvalue/rvalue) to a single variadic forwarding constructor `template <typename... Args> explicit FunctionObjImpl(Args&&...)`.
  - Added `FunctionObjImpl::GetCallable()` method to access the internal callable pointer.
  - Added copy constructor/assignment deletion for `FunctionObjImpl`.
  - New static method `Function::FromPackedInplace<TCallable>(Args&&...)` returning `std::tuple<Function, TCallable*>` -- constructs a function and returns a pointer to the in-place callable for further mutation.

- **`include/tvm/ffi/reflection/overload.h`** (new file, 501 lines):
  - `OverloadBase`: abstract base class for overload dispatch with try-call function pointers and mismatch caching.
  - `TypedOverload<Callable>`: concrete overload for a specific callable signature; performs argument matching via `AnyView::TryAs<T>` and captures matched args in a tuple of optionals.
  - `OverloadSet`: holds a vector of `OverloadBase` instances, dispatches by trying each overload and generating error messages on mismatch.
  - `OverloadObjectDef<Class>`: builder (inheriting from `ObjectDef<Class>`) that exposes `def_overload(name, callables...)` to register multiple method overloads under a single name.

- **`include/tvm/ffi/reflection/registry.h`**:
  - Refactored `ObjectDef<T>::def()` and `ObjectDef<T>::def_rw()` to use `Function::FromPacked` directly instead of intermediate lambda wrappers, making the code more concise and enabling the new variadic constructor path.

- **`tests/cpp/test_overload.cc`** (new file, 95 lines):
  - Tests overloaded methods on a `MyObj` class with `Add(int, int)`, `Add(String, String)`, `Add(int, int, int)`, and `Add(double, double)` overloads. Verifies correct dispatch and error on ambiguous calls.

## Public surface changes (if any)
- API: New `Function::FromPackedInplace<TCallable>()` static method. New `OverloadObjectDef<Class>` builder with `def_overload()`. New `FunctionObjImpl::GetCallable()` accessor.
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/cpp/test_overload.cc` (+95 lines)
- How to verify manually: Build C++ tests with `TVM_FFI_BUILD_TESTS=ON` and run the overload test.
- CI impact: New test will run in the C++ test suite.

## Risk & rollout notes
- Risk level: medium -- changes to `FunctionObjImpl` constructor (variadic forwarding replaces explicit lvalue/rvalue overloads) could subtly affect existing usages if any depend on copy/move semantics, though the new form is strictly more general. The copy deletion is a breaking change if anything tried to copy `FunctionObjImpl`.
- Rollout/migration: Existing code using `Function::FromPacked` is unaffected. New overload features are opt-in.
- Follow-ups: The clang-tidy warning introduced here is fixed in commit 22f22e8.

## Evidence
### Changed files
- `include/tvm/ffi/function.h` (+38/-9) [modified]
- `include/tvm/ffi/reflection/overload.h` (+501) [added]
- `include/tvm/ffi/reflection/registry.h` (+15/-28) [modified]
- `tests/cpp/test_overload.cc` (+95) [added]

### Notable symbols / endpoints / configs touched
- `Function::FromPackedInplace`
- `FunctionObjImpl` (variadic constructor, `GetCallable`, copy deletion)
- `OverloadBase`, `TypedOverload`, `OverloadSet`, `OverloadObjectDef`
- `ObjectDef::def()`, `ObjectDef::def_rw()` (refactored)

### Diff notes
- Diff truncated: yes (reviewed first 200 lines of 700+ line diff; full stat examined)
