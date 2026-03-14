---
status: "active"
confidence: "medium"
---
# Module Export System

**TL;DR**
- `TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, CppFunction)` generates an `extern "C"` symbol with `TVMFFISafeCallType` signature, enabling typed C++ functions to be exported from shared library modules for discovery via `load_module`.
- `TVM_FFI_DLL_EXPORT` provides always-export visibility (unlike `TVM_FFI_DLL` which may be `dllimport` on MSVC), ensuring module-exported symbols are visible regardless of build context.
- The export macro leverages the function system's `FunctionInfo<TCallable>` for arity/return type deduction and `unpack_call` for argument unpacking within a `TVM_FFI_SAFE_CALL_BEGIN/END` boundary.
- When `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` is defined, companion `__tvm_ffi__metadata_<name>` and `__tvm_ffi__doc_<name>` symbols are additionally exported for cross-language introspection. See [ADR 0047](../ADRs/0047-embedded-function-metadata.md).

## Problem Statement

### Background

TVM kernel libraries and addons are compiled as shared libraries (`.so` / `.dll`) that are loaded at runtime. These libraries need to expose typed C++ functions via C-ABI-compatible symbols that the module loader can discover and wrap.

### Solution

A macro that generates `extern "C"` wrapper functions with `TVMFFISafeCallType` signature. The wrapper unpacks `AnyView*` arguments into typed C++ parameters, calls the original function, and packs the return value back into `Any*`, all within a safe-call exception boundary.

### Goals

- **Goal**: Export typed C++ functions from shared libraries with zero manual C wrapper code.
- **Goal**: Cross-DLL-safe error handling via `TVM_FFI_SAFE_CALL_BEGIN/END`.
- **Goal**: Consistent visibility across Emscripten, MSVC, and GCC/Clang via `TVM_FFI_DLL_EXPORT`.
- **Non-goal**: Automatic function discovery by convention (the caller must know the symbol name).

## Design

### Export Macro

```cpp
#define TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, Function)
// Generates:
extern "C" TVM_FFI_DLL_EXPORT int __tvm_ffi_##ExportName(
    void* handle, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result) {
  TVM_FFI_SAFE_CALL_BEGIN();
  using FInfo = FunctionInfo<decltype(Function)>;
  using RetType = typename FInfo::RetType;
  // Check arity
  // unpack_call<RetType>(Function, args, num_args, result)
  TVM_FFI_SAFE_CALL_END();
}
```

**Symbol prefix convention** (commit `40e8a51` #18273): The generated `extern "C"` symbol is `__tvm_ffi_##ExportName` (not the raw `ExportName`). The constant `symbol::tvm_ffi_symbol_prefix = "__tvm_ffi_"` defines the canonical prefix for all FFI-exported function symbols in shared libraries. This prevents symbol collisions between FFI-exported functions and non-FFI symbols in the same library.

The generated function:
1. Checks `num_args` against `FInfo::kNumArgs`.
2. Uses `unpack_call<RetType>` to convert packed `AnyView` arguments to typed parameters.
3. Calls the original C++ function.
4. Packs the return value into `result`.
5. Catches exceptions via `TVM_FFI_SAFE_CALL_END` and returns error codes.

### Companion Metadata Symbols

When `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` is set to 1 (default 0), the export macro additionally emits:

- **`__tvm_ffi__metadata_<ExportName>`**: Returns a JSON string `{"type_schema": "<schema>"}` containing the function's type schema (generated from `FunctionInfo::TypeSchema()`).
- **`__tvm_ffi__doc_<ExportName>`** (via `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC`): Returns a documentation string.

Both symbols use `TVMFFISafeCallType` signature and allocate return strings via `TVMFFIStringFromByteArray` to ensure the string lives in the main library's heap (preventing use-after-unload when the module is garbage-collected).

The Python `Module.get_function_metadata(name)` and `Module.get_function_doc(name)` query these symbols.

### Module Lifetime Management

`load_module(path, keep_module_alive=True)` registers loaded modules in a C++-side `ModuleGlobals` registry via `ModuleGlobalsAdd`, preventing Python GC from prematurely unloading shared libraries whose functions are still referenced. The `load_lib_module(package, target)` convenience API in `tvm_ffi.libinfo` wraps this for downstream packages.

### Key Classes, Fields and Interfaces

- **`TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, Func)`** (`include/tvm/ffi/function.h`): Generates an `extern "C"` export; conditionally emits metadata symbol.
- **`TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC(ExportName, DocString)`** (`include/tvm/ffi/function.h`): Emits a documentation symbol (only when metadata enabled).
- **`TVM_FFI_DLL_EXPORT_INCLUDE_METADATA`** (compile flag): Gates metadata/doc symbol emission. Default 0.
- **`TVM_FFI_DLL_EXPORT`** (`include/tvm/ffi/c_api.h`): Always-export visibility macro.
- **`FunctionInfo<TCallable>`**: Extracts `RetType`, `kNumArgs`, and parameter types from the callable.
- **`unpack_call<RetType>`**: Template that unpacks `AnyView*` arguments into typed parameters.
- **`tvm_ffi.libinfo.load_lib_module(package, target)`** (Python): Convenience API for downstream library loading.

### Contracts, Assumptions and Invariants

- **SafeCallType signature**: The generated function matches `TVMFFISafeCallType` exactly.
- **Exception safety**: All exceptions are caught by `TVM_FFI_SAFE_CALL_END`.
- **Arity check**: Mismatched argument count throws `RuntimeError` with a diagnostic message.
- **Always-export**: `TVM_FFI_DLL_EXPORT` ensures the symbol is never `dllimport` even when the library is consumed externally.

### ModuleObj::GetFunctionDoc

`ModuleObj` (defined in `include/tvm/ffi/extra/module.h`) now exposes per-function documentation via:
- **`GetFunctionDoc(name)`**: Virtual method returning `Optional<String>`. Default returns `std::nullopt`. Subclasses (e.g., `LibraryModuleObj`) can override to provide function-specific docstrings.
- **`GetFunctionDoc(name, query_imports)`**: Non-virtual method that searches the module's import chain when `query_imports=true`.
- **`ffi.ModuleGetFunctionDoc`**: Global function registered for cross-language access.

This separates unstructured docstrings from structured metadata (the `metadata` field in `TVMFFIMethodInfo`), enabling efficient metadata queries without loading full docstrings.

### Extension Points

- **Custom export wrappers**: New macros can be built on the same pattern for packed functions or functions with custom error handling.
- **Module metadata export**: The `GetFunctionDoc` virtual method enables per-function documentation in loaded modules. The `metadata` field in `TVMFFIMethodInfo` provides structured JSON metadata alongside the function symbol.

## Alternatives & Trade-offs

### Alternative: Manual extern "C" wrappers

- Pros: Full control over the generated code
- Cons: Boilerplate-heavy, error-prone (forgetting safe_call boundary, wrong arity check). The macro eliminates all boilerplate.

### Alternative: Use TVM_FFI_DLL instead of TVM_FFI_DLL_EXPORT

- Pros: One fewer macro to maintain
- Cons: On MSVC, `TVM_FFI_DLL` resolves to `dllimport` when `TVM_FFI_EXPORTS` is not defined (i.e., when building a module that links against the FFI). Module-exported symbols must always be `dllexport`, which `TVM_FFI_DLL_EXPORT` guarantees.

## Related Work

### Design Docs & ADRs

- [`.knowledge/designs/0001-c-abi.md`](0001-c-abi.md) -- `TVMFFISafeCallType` and visibility macros
- [`.knowledge/designs/0004-function-system.md`](0004-function-system.md) -- `FunctionInfo`, `unpack_call`, packed calling convention
- [`.knowledge/designs/0013-module-system.md`](0013-module-system.md) -- Module system (consumer of exported symbols via LibraryModuleObj)
- [`.knowledge/ADRs/0005-safe-call-abi-boundary.md`](../ADRs/0005-safe-call-abi-boundary.md) -- Dual call/safe_call
- [`.knowledge/ADRs/0047-embedded-function-metadata.md`](../ADRs/0047-embedded-function-metadata.md) -- Metadata/doc companion symbol decision

### Evidence Matrix

- TVM_FFI_DLL_EXPORT_TYPED_FUNC introduction -> `.knowledge/commits/2025-05-29-192f196ec7b342677217e854fae7e7970fa100c5.md` + `192f196`
- TVM_FFI_DLL_EXPORT macro -> `.knowledge/commits/2025-05-29-192f196ec7b342677217e854fae7e7970fa100c5.md` + `192f196`
- __tvm_ffi_ symbol prefix for exported functions -> `.knowledge/commits/2025-09-06-40e8a519f5270dfb18436b2f26c2d691cf24c9c1.md` + `40e8a51`
- ModuleObj::GetFunctionDoc + type_schema -> metadata rename -> `.knowledge/commits/2025-10-01-ffa2dbf8bc18edb3114f18f619da08c4e3289de6.md` + `ffa2dbf`
- Embedded metadata/doc companion symbols -> `.knowledge/commits/2025-11-20-ac7bf68058b392c3a8475619016fde48bd08334b.md` + `ac7bf68`
- Main-lib allocation fix for metadata strings -> `.knowledge/commits/2025-12-02-dcacb98d189241d52ef51c1d63fb0e9f6c98a4b0.md` + `dcacb98`
- keep_module_alive flag for load_module -> `.knowledge/commits/2025-12-11-8dcaec1fb47bf7873b105385b7d2808d51f6b342.md` + `8dcaec1`
- load_lib_module convenience API -> `.knowledge/commits/2025-12-12-f255650b8e5121452dd60805b206a0cb5bcb6525.md` + `f255650`
