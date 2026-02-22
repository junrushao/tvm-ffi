# Namespace and API Migration

- Doc ID: 002-namespace-and-api-migration
- Status: Approved
- Last Updated: 2025-08-31
- Owners: Tianqi Chen

## Overview

The TVM FFI codebase migrated from legacy `tvm::runtime` names (e.g.,
`PackedFunc`, `TVMArgs`) to a new `tvm::ffi` namespace (e.g., `ffi::Function`,
`ffi::Any`). This document describes the migration strategy, the namespace
redirect layer, and the DLL export conventions that evolved during May 2025.

## Key Design

### Namespace redirect strategy

To avoid breaking downstream code that references `tvm::Array`, `tvm::Map`,
etc., the migration uses `using` declarations at the bottom of each public
header to re-export `tvm::ffi::*` types into the `tvm::` namespace.

This was applied in two waves:
1. **Containers and utilities** (`16e9f0a`): `Array`, `Map`, `Tuple`, `Variant`,
   `String`, `Bytes`, `Optional`, `Function`, `Downcast`, `GetRef`, `make_object`.
2. **Core value types** (`192f196`): `Any`, `AnyView`.

The pattern is:
```cpp
namespace tvm {
using ffi::Array;  // expose tvm::ffi::Array as tvm::Array
}  // namespace tvm
```

### Naming renames

| Old name                    | New name                     | Commit   |
|-----------------------------|------------------------------|----------|
| `Function::FromUnpacked`    | `Function::FromTyped`        | `110b8f9`|
| `TVM_REGISTER_GLOBAL`       | `TVM_FFI_REGISTER_GLOBAL`    | `8a00988`|
| "PackedFunc" (doc comments) | "ffi::Function"              | `110b8f9`|
| "NullOpt" (Map::Get doc)    | "std::nullopt"               | `16e9f0a`|
| `TVM_FFI_REGISTER_GLOBAL`   | `GlobalDef().def(...)` pattern| `b333288`, `26b68b0`|
| `Downcast<T>(ref)`          | `ref.cast<T>()` / `GetRef<T>(ptr)` | `4be1af7`|
| `tvm::Tuple`                | `tvm::ffi::Tuple`            | `ed56a5e`|
| `TVMFFIEnvLookupFromImports`| `TVMFFIEnvModLookupFromImports`| `023ea44`|
| `TVMFFIEnvRegisterContextSymbol`| `TVMFFIEnvModRegisterContextSymbol`| `023ea44`|
| `TVMFFIEnvRegisterSystemLibSymbol`| `TVMFFIEnvModRegisterSystemLibSymbol`| `023ea44`|
| `AccessKind::kObjectField`  | `AccessKind::kAttr`          | `f4ede98`|
| `AccessStep::ObjectField()` | `AccessStep::Attr()`         | `f4ede98`|

`Function::FromTyped` more clearly conveys that the method wraps a typed
(non-packed) C++ callable into the packed calling convention.

### DLL export macros

Three macros handle symbol visibility across platforms (Emscripten, MSVC,
GCC/Clang):

| Macro                       | Semantics                                       | Commit   |
|-----------------------------|-------------------------------------------------|----------|
| `TVM_FFI_DLL`               | Context-dependent: export when building the DLL, import when consuming it. | pre-range |
| `TVM_FFI_DLL_EXPORT`        | Always export (never import). For symbols that module libraries expose.    | `192f196` |
| `TVM_FFI_WEAK`              | Weak linkage (`__attribute__((weak))` / `__declspec(selectany)`). For optional overrides. | `8a00988` |

`TVM_FFI_DLL_EXPORT_TYPED_FUNC(name, func)` wraps a typed C++ function into a
`TVMFFISafeCallType` exported symbol, allowing shared libraries to expose typed
functions through the standard C ABI entry point (`192f196`).

## APIs

### Changed C++ APIs

- `Function::FromTyped(callable)` -- Creates a `Function` from a typed callable.
  Replaces `Function::FromUnpacked`.

### New macros

```cpp
TVM_FFI_DLL_EXPORT       // Always-export visibility attribute
TVM_FFI_WEAK             // Weak symbol linkage
TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, typed_function)
```

Note: `TVM_FFI_REGISTER_GLOBAL` was introduced as the preferred replacement for
`TVM_REGISTER_GLOBAL`, but was itself removed in July 2025 (`26b68b0`) in favor
of `reflection::GlobalDef`. See design doc 004 for details.

### Namespace aliases

After `16e9f0a` and `192f196`, the following are available in `tvm::`:
`Array`, `Map`, `Variant`, `String`, `Bytes`, `Optional`, `Function`,
`Any`, `AnyView`, `GetRef`, `make_object`.

Note: `tvm::Tuple` was removed in `ed56a5e` (August 2025); use
`tvm::ffi::Tuple`. `tvm::Downcast` was removed in `4be1af7` (August 2025);
use `.cast<T>()` on `Any`/`AnyView` or `GetRef<T>(ptr)` for raw pointers.

## Implementation

Key files:
- `include/tvm/ffi/c_api.h` -- `TVM_FFI_DLL_EXPORT`, `TVM_FFI_WEAK`, `TVM_FFI_DLL`
- `include/tvm/ffi/function.h` -- `Function::FromTyped`, `TVM_FFI_DLL_EXPORT_TYPED_FUNC`
- `include/tvm/ffi/any.h` -- `tvm::Any`, `tvm::AnyView` using declarations
- `include/tvm/ffi/container/*.h` -- per-container `using` declarations

Migration checklist for downstream code:
1. Replace `Function::FromUnpacked(...)` with `Function::FromTyped(...)`.
2. Replace `TVM_REGISTER_GLOBAL` / `TVM_FFI_REGISTER_GLOBAL` with
   `TVM_FFI_STATIC_INIT_BLOCK({ refl::GlobalDef().def("name", func); })`.
   The `TVM_FFI_REGISTER_GLOBAL` macro and `Function::Registry` class were
   removed in `26b68b0`.
3. No need to change `tvm::Array`, `tvm::Map`, etc. -- redirects handle it.

## History
- 2025-05-07: `FromUnpacked` renamed to `FromTyped` (`110b8f9`)
- 2025-05-08: Container namespace redirects added (`16e9f0a`)
- 2025-05-24: `TVM_FFI_WEAK` macro, doc migration to `TVM_FFI_REGISTER_GLOBAL` (`8a00988`)
- 2025-05-29: `Any`/`AnyView` redirects, `TVM_FFI_DLL_EXPORT` and `TVM_FFI_DLL_EXPORT_TYPED_FUNC` (`192f196`)
- 2025-07-03: `reflection::GlobalDef` introduced for function registration (`b333288`)
- 2025-07-15: `TVM_FFI_REGISTER_GLOBAL` macro and `Function::Registry` class removed (`26b68b0`)
- 2025-08-06: `tvm::Tuple` alias removed; use `tvm::ffi::Tuple` (`ed56a5e`)
- 2025-08-08: `Downcast` family removed from FFI; use `.cast<T>()` or `GetRef<T>()` (`4be1af7`)
- 2025-08-20: Env API symbols renamed with `Mod` infix (`023ea44`)

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-05-29-7D34EB8-024E45C.md`
  - `.repo-knowledge/ranges/2025-07-31-0966C36-0342D85.md`
  - `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
- Related ADRs:
  - `.repo-knowledge/adr/004-globaldef-replaces-register-global.md`
  - `.repo-knowledge/adr/007-downcast-removal.md`
