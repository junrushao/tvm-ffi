---
design: "0003"
title: "Packed Function System and Global Registry"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-05-06"
last_updated: "2025-10-22"
scope:
  - "ffi/function"
  - "ffi/c_api"
  - "ffi/reflection"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
  - "110b8f91ea89c08254219e82d0b2ac67bf2dd2c0"
  - "192f196ec7b342677217e854fae7e7970fa100c5"
  - "a419ed175aac752a3df2ee73faad360a2824ecd8"
  - "b333288162ba3a883dbf6b1ce23672f687d70163"
  - "26b68b0256fb40baa8aeb55847050d13b064f441"
  - "5b0cceb05bd21a4c9d1c029b08742cfafedcd023"
  - "7b813f8bc6a548d9aebb24ec5d19c0aa8b89c6a7"
  - "4fe8b2b79dfeb469b2499acecb3e10038ddcee0f"
  - "a15364746d60766bfaf6e0a6ccdb2353ceee7d7d"
  - "f6303b23fd97909b59f6ff67b85f2203371f5db1"
  - "a23c5a03"
source_ledgers:
  - ".memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md"
  - ".memory/commits/2025-05-07-110b8f91ea89c08254219e82d0b2ac67bf2dd2c0.md"
  - ".memory/commits/2025-05-29-192f196ec7b342677217e854fae7e7970fa100c5.md"
  - ".memory/commits/2025-06-16-a419ed175aac752a3df2ee73faad360a2824ecd8.md"
  - ".memory/commits/2025-07-03-b333288162ba3a883dbf6b1ce23672f687d70163.md"
  - ".memory/commits/2025-07-15-26b68b0256fb40baa8aeb55847050d13b064f441.md"
  - ".memory/commits/2025-07-16-5b0cceb05bd21a4c9d1c029b08742cfafedcd023.md"
  - ".memory/commits/2025-09-13-7b813f8b.md"
  - ".memory/commits/2025-09-29-4fe8b2b7.md"
  - ".memory/commits/2025-10-10-a1536474.md"
  - ".memory/commits/2025-10-11-f6303b23.md"
  - ".memory/commits/2025-10-22-a23c5a03.md"
---

# Packed Function System and Global Registry

## TL;DR
- `FunctionObj` is a type-erased callable with a dual-dispatch mechanism: `cpp_call` for direct C++ invocation with exception propagation, and `safe_call` for C ABI invocation with error-code return and TLS error propagation.
- The global function registry (`GlobalFunctionTable`) maps string names to `Function` objects, enabling cross-language function lookup via `TVMFFIFunctionGetGlobal`.
- `TypedFunction<R(Args...)>` provides type-safe wrappers over the untyped packed calling convention.

## Problem Statement
Cross-language function invocation requires a universal calling convention. Each language has its own function call mechanism (C++ templates, Python dynamic dispatch, Rust traits). The FFI must provide a single, type-erased function representation that all languages can call and implement, while preserving performance for same-language calls and correctness across language boundaries.

## Context and Constraints
- The calling convention is packed: arguments are passed as `const TVMFFIAny* args, int32_t num_args` and the result is returned via `TVMFFIAny* rv`.
- Functions must be callable from C, C++, Python, and Rust.
- C++ exceptions must not escape C ABI boundaries.
- The global registry must support static initialization (functions registered before `main()`).
- Functions must be first-class objects (passable as arguments, storable in containers).

## Goals
- Provide a single function type (`Function`) usable from all languages.
- Enable zero-overhead C++ calls via `cpp_call` when caller and callee are in the same DSO.
- Enable safe cross-language calls via `safe_call` with error propagation.
- Provide a global name-based registry for function discovery.
- Support both C++ callables (lambdas, function pointers) and C-style extern callbacks.

## Non-Goals
- Async/coroutine function support (all calls are synchronous).
- Overload resolution (each name maps to exactly one function).
- Automatic type coercion at call boundaries (explicit `TypeTraits` conversions apply).

## Design
### Components and Responsibilities
- **`FunctionObj`** (class, `function.h`): Inherits `Object` + `TVMFFIFunctionCell`. Contains two dispatch pointers: `cpp_call` and `safe_call`. `cpp_call` throws exceptions directly; `safe_call` catches them and returns error codes.
- **`FunctionObjImpl<TCallable>`** (template, `function_details.h`): Wraps an arbitrary C++ callable. Unpacks `TVMFFIAny` arguments into typed parameters via `TypeTraits`, calls the underlying callable, and packs the result back.
- **`ExternCFunctionObjImpl`** (class, `function.h`): Wraps a C-style callback (`TVMFFISafeCallType`) with a handle. The `cpp_call` path invokes the safe_call and rethrows any TLS error as a C++ exception.
- **`ExternCFunctionObjNullHandleImpl`** (class, `function.h`): Wraps a raw C function pointer without closure handle. Added in commit `4fe8b2b` when `ImportedFunctionObjImpl` and `RedirectCallToSafeCall` CRTP base were removed.
- **`CppCallDedirectToSafeCall`** (function, `function.h`): Fallback `cpp_call` path for `FunctionObj` instances where `cpp_call` is null. Invokes `safe_call` and rethrows any TLS error as a C++ exception.
- **`Function`** (ref class, `function.h`): `ObjectRef` wrapper. Provides `operator()(Args...)` with variadic template expansion. Each argument is converted to `AnyView` via `TypeTraits`, passed to `cpp_call`, and the result is returned as `Any`.
- **`TypedFunction<R(Args...)>`** (template, `function.h`): Wraps a `Function` with compile-time type-safe signatures. Converts arguments and checks the return type.
- **`GlobalFunctionTable`** (singleton, `src/ffi/function.cc`): A `Map<String, Any>` that stores registered functions with metadata. Each entry is a `GlobalFunctionTable::Entry` object (extends `Object` + `TVMFFIMethodInfo`) carrying the function and its metadata (doc, type schema, flags). Registration via `TVMFFIFunctionSetGlobal` or `TVMFFIFunctionSetGlobalFromMethodInfo`, lookup via `TVMFFIFunctionGetGlobal`. The underlying storage was migrated from `std::unordered_map` to `Map<String, Any>` to dogfood TVM FFI containers.
- **`reflection::GlobalDef`** (class, `reflection/registry.h`): The current preferred way to register global functions. Provides a fluent builder API: `GlobalDef().def("name", func, "doc")`, `def_packed("name", func)`, `def_method("name", member_ptr)`. Used inside `TVM_FFI_STATIC_INIT_BLOCK`. Replaces the deleted `TVM_FFI_REGISTER_GLOBAL` macro and `Function::Registry` class. See [design 0006](.memory/designs/0006-reflection-system.md).
- **`TVM_FFI_REGISTER_GLOBAL("name")`** (**DELETED**): The legacy macro and `Function::Registry` class have been removed. All in-tree code uses `GlobalDef` instead.

### Data Contracts and Invariants
- **Packed calling convention**: All functions accept `(const TVMFFIAny* args, int32_t num_args, TVMFFIAny* rv)`. The caller must initialize `rv->type_index = kTVMFFINone` before the call.
- **Safe-call return code**: 0 = success, -1 = error (retrieve via `TVMFFIErrorMoveFromRaised`).
- **Dual dispatch invariant**: `cpp_call` and `safe_call` are semantically equivalent -- they produce the same result for the same inputs. `safe_call` wraps `cpp_call` in a try/catch.
- **Registry uniqueness**: Each name maps to at most one function. Attempting to register a duplicate without `can_override=true` raises `RuntimeError`.
- **Lifetime**: Registered functions are owned by the global table and live for the process lifetime.

### Control Flow
1. **C++ caller (same DSO)**: `func(arg1, arg2)` -> `TypeTraits<Arg>::CopyToAnyView` for each arg -> `FunctionObj::cpp_call(args, n, &rv)` -> unpack rv as `Any`.
2. **Foreign caller (across ABI)**: `safe_call(handle, args, n, rv)` -> try { `cpp_call(args, n, rv)` } catch (Error& e) { `TVMFFIErrorSetRaised(e)` ; return -1 } -> return 0.
3. **Function registration (current)**: `TVM_FFI_STATIC_INIT_BLOCK() { GlobalDef().def("name", callable, "doc"); }` -> construct `FunctionObjImpl<TCallable>` -> build `TVMFFIMethodInfo` with metadata -> `TVMFFIFunctionSetGlobalFromMethodInfo(info)` -> `GlobalFunctionTable::Register(name, Entry)`. The `TVM_FFI_STATIC_INIT_BLOCK` macro was refactored in commit `7b813f8` from lambda-based `TVM_FFI_STATIC_INIT_BLOCK(Body)` to function-style `TVM_FFI_STATIC_INIT_BLOCK() { ... }` syntax, using `__attribute__((constructor))` on GCC/Clang for reliable static initialization ordering.
4. **Function lookup**: `get_global_func("name")` -> `TVMFFIFunctionGetGlobal("name", &out)` -> returns `Function` or throws if not found.

### Extension Points
- **New callable types**: Specialize `FunctionObjImpl<T>` or implement `TVMFFISafeCallType` for C-style callbacks.
- **Metadata**: Functions can carry metadata strings (doc, schema) via `TVMFFIMethodInfo`. TypeSchema is automatically attached by `GlobalDef::def` (see [Design 0019](.memory/designs/0019-typeschema-metadata-system.md)).
- **Module system**: `load_module("path.so")` discovers functions via `__tvm_ffi_<name>` symbol prefix and registers them in the global table.
- **External function construction**: `Function.__from_extern_c__` and `Function.__from_mlir_packed_safe_call__` enable constructing FFI Functions from JIT-compiled function pointers. See [Design 0020](.memory/designs/0020-external-function-construction.md).

## Alternatives Considered
### Vtable-based function objects (like std::function)
- Pros: Standard C++ pattern. Type-safe.
- Cons: Not C ABI compatible. Cannot be shared across DSO boundaries safely. No packed calling convention.

### Individual C function per FFI function
- Pros: Direct C ABI compatibility. No indirection.
- Cons: Cannot discover functions dynamically. Cannot pass functions as values. Explosion of C symbols.

## Trade-offs
- **Optimized**: Cross-language interoperability (single calling convention), dynamic function discovery (registry), zero-overhead same-language calls (cpp_call).
- **Sacrificed**: Compile-time type safety at call boundaries (packed convention is untyped), function overloading (names are unique).

## Interfaces and Compatibility
- **C ABI**: `TVMFFIFunctionCreate`, `TVMFFIFunctionCall`, `TVMFFIFunctionGetGlobal`, `TVMFFIFunctionSetGlobal`, `TVMFFISafeCallType`.
- **C++ API**: `Function`, `TypedFunction<R(Args...)>`, `reflection::GlobalDef`, `get_global_func`, `Function::FromTyped` (renamed from `FromUnpacked`), `TVM_FFI_DLL_EXPORT_TYPED_FUNC` (for DSO export of typed functions). The `FunctionInfo<F>` type traits system provides compile-time function signature introspection, supporting function pointers (`R(*)(Args...)`), function references (`R(&)(Args...)`, added in commit `a23c5a03`), member function pointers, and lambda types.
- **Registry protocol**: Functions are registered by name with optional metadata (doc, type_schema, flags). The name is the only identifier; there is no numeric function ID. Duplicate registration without override throws `RuntimeError` with diagnostic hints.

## Failure Modes and Mitigations
- **Function not found**: `get_global_func("unknown")` throws `RuntimeError` with the name. Mitigated by providing `get_global_func` overloads that return `Optional<Function>`.
- **Argument type mismatch**: `TypeTraits` check fails during argument unpacking, throwing `TypeError` with expected vs. actual type. The error propagates via the safe-call mechanism.
- **Duplicate registration**: `TVM_FFI_REGISTER_GLOBAL` with an already-registered name fails loudly with a diagnostic message.
- **Exception escape from safe_call**: Impossible by construction -- `TVM_FFI_SAFE_CALL_END()` catches all exceptions including `std::exception` and unknown exceptions.

## Observability and Validation
- `tests/cpp/test_ffi_function.cc`: Tests function creation, packed calls, global registration, and TypedFunction wrappers.
- `TVMFFIFunctionListGlobal` lists all registered function names.
- Metadata strings on registered functions can carry schema information for documentation tools.

## Migration and Rollout
- Foundational design from the root commit. The packed calling convention is the universal FFI mechanism.

## Diagrams
- [.memory/diagrams/0003-function-call-flow.md](.memory/diagrams/0003-function-call-flow.md)

## Related ADRs
- [.memory/ADRs/0004-tls-error-propagation.md](.memory/ADRs/0004-tls-error-propagation.md)

## Evidence Matrix
- FunctionObj dual dispatch (914 LOC) -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `include/tvm/ffi/function.h`
- GlobalFunctionTable (migrated to Map<String, Any>) -> `.memory/commits/2025-06-16-a419ed175aac752a3df2ee73faad360a2824ecd8.md` + `a419ed` + `src/ffi/function.cc`
- TVMFFISafeCallType -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 458-480
- FromUnpacked renamed to FromTyped -> `.memory/commits/2025-05-07-110b8f91ea89c08254219e82d0b2ac67bf2dd2c0.md` + `110b8f`
- TVM_FFI_DLL_EXPORT_TYPED_FUNC macro -> `.memory/commits/2025-05-29-192f196ec7b342677217e854fae7e7970fa100c5.md` + `192f19`
- GlobalDef class introduction -> `.memory/commits/2025-07-03-b333288162ba3a883dbf6b1ce23672f687d70163.md` + `b33328`
- TVM_FFI_REGISTER_GLOBAL and Function::Registry removal -> `.memory/commits/2025-07-15-26b68b0256fb40baa8aeb55847050d13b064f441.md` + `26b68b`
- Duplicate registration error improvement -> `.memory/commits/2025-07-16-5b0cceb05bd21a4c9d1c029b08742cfafedcd023.md` + `5b0cce`
- TVMFFIFunctionSetGlobalFromMethodInfo C API -> `a419ed` + `include/tvm/ffi/c_api.h`
- Safe-call begin/end macros -> `7d34eb8` + `include/tvm/ffi/function.h` lines 72-80
- `TVM_FFI_STATIC_INIT_BLOCK` refactor to function-style with `__attribute__((constructor))` -> `.memory/commits/2025-09-13-7b813f8b.md` + `7b813f8` + `include/tvm/ffi/base_details.h`
- `TVMFFIFunctionCell.cpp_call` field, removal of `ImportedFunctionObjImpl`, `Function::ImportFromExternDLL`, `ExternCFunctionObjNullHandleImpl` added -> `.memory/commits/2025-09-29-4fe8b2b7.md` + `4fe8b2b` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/function.h`
- `Function.__from_extern_c__` for constructing Functions from extern C function pointers -> `.memory/commits/2025-10-10-a1536474.md` + `a1536474` + `python/tvm_ffi/cython/function.pxi`
- `Function.__from_mlir_packed_safe_call__` with `TVMFFIPyMLIRPackedSafeCall` adapter -> `.memory/commits/2025-10-11-f6303b23.md` + `f6303b23` + `python/tvm_ffi/cython/function.pxi`, `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- `FunctionInfo<R(&)(Args...), void>` specialization for function reference types -> `.memory/commits/2025-10-22-a23c5a03.md` + `a23c5a03` + `include/tvm/ffi/function_details.h`

## Open Questions
- Should there be a mechanism for unregistering functions (currently not supported)?

## Confidence and Risk
- Confidence: high
- Residual risks: Static initialization order dependencies between `TVM_FFI_STATIC_INIT_BLOCK` calls across translation units. On GCC/Clang, `__attribute__((constructor))` provides more reliable ordering than the variable-initializer pattern (commit `7b813f8`), but cross-TU ordering is still compiler-defined. The global registry is not thread-safe during registration (assumed to happen in the main thread during init).
