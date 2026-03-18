---
scope: "function-system"
---
# API Index: Function System

**Scope**: C++ Function, FunctionObj, typed functions, global registry, and related macros.
**Design docs**: [0004-function-system.md](../designs/0004-function-system.md)
**ADRs**: [0002-tls-error-propagation.md](../ADRs/0002-tls-error-propagation.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `FunctionObj` | class | `TVMFFISafeCallType safe_call`, `void* cpp_call`, `CallPacked(args, num_args, result)` | Object container backing Function with dual call paths: cpp_call (C++ direct) or safe_call fallback (4fe8b2b) |
| `Function` | class | `operator()(args...) -> Any`, `CallPacked(args, num_args, result)`, `CallExpected<T>(args...) -> Expected<T>` (0a9d4b6), `FromPacked(callable) -> Function`, `FromTyped(callable) -> Function` (renamed from FromUnpacked), `FromExternC(self, safe_call, deleter) -> Function`, `InvokeExternC(handle, safe_call, args...) -> Any` (9186b44), `GetGlobal(name) -> Optional<Function>`, `GetGlobalRequired(name) -> Function`, `SetGlobal(name, func, override)`, `ListGlobalNames() -> vector<String>`, `RemoveGlobal(name)` | Type-erased callable ref with global registry. ~~ImportFromExternDLL~~ removed (4fe8b2b) |
| `TypedFunction<R(Args...)>` | class | `R operator()(Args...)`, `Function packed()`, `static TypeSchema() -> string` (28fe3cc), implicit conversion to/from Function | Compile-time typed wrapper around Function |
| `details::FunctionInfo<T>` | struct template | `Sig() -> string`, `TypeSchema() -> string` | Extracts function signature and schema. SFINAE specializations for Object (Class*) vs ObjectRef (Class by-value) member function pointers (7b57a46) |
| `reflection::GlobalDef` | class | `def(name, func) -> GlobalDef&`, `def_packed(name, func) -> GlobalDef&`, `def_method(name, func) -> GlobalDef&` | Register global functions with type schema metadata (in `reflection/registry.h`) |
| `Function::FromPackedInplace<TCallable>(Args...)` | static method | `auto FromPackedInplace(Args&&...) -> tuple<Function, TCallable*>` | Create Function with mutable callable access; used by OverloadObjectDef (84c5bdbc) |
| `FunctionObjImpl<TCallable>` | class | `TCallable callable_`, variadic forwarding ctor (84c5bdbc, was dual ctor), `GetCallable() -> TCallable*` (84c5bdbc), `static_assert(TCallable == decay_t<TCallable>)` | Internal: stores a packed callable inside FunctionObj |
| `ExternCFunctionObjImpl` | class | `void* self_`, `TVMFFISafeCallType safe_call_`, `void(*deleter_)(void*)` | Internal: wraps C-style callback as FunctionObj (cpp_call=nullptr) |
| `ExternCFunctionObjNullHandleImpl` | class | `safe_call` only | Internal: lightweight FunctionObj for raw C function pointers (null self, null deleter) (4fe8b2b) |
| ~~`ImportedFunctionObjImpl`~~ | class | _(removed in 4fe8b2b)_ | Removed: cross-DLL safety now via cpp_call==nullptr convention |
| `PackedArgsSetter` | class | `void operator()(size_t i, T&& value)` | Internal: helper to fill AnyView array from variadic args |
| `TVM_FFI_SAFE_CALL_BEGIN()` | macro | `try {` | Begin safe-call exception boundary |
| `TVM_FFI_SAFE_CALL_END()` | macro | Catches Error (-1), std::exception (-1). EnvErrorAlreadySet now caught as regular Error (b1611e0). | End safe-call exception boundary |
| `TVM_FFI_CHECK_SAFE_CALL(func)` | macro | Checks return code, rethrows from TLS if needed | Caller-side safe-call return code checker |
| ~~`TVM_FFI_REGISTER_GLOBAL(name)`~~ | macro | _(removed in commit 26b68b0)_ | Removed: replaced by `reflection::GlobalDef().def(...)` |
| `TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, Function)` | macro | emits `extern "C" __tvm_ffi_ExportName(...)`, plus `__tvm_ffi__metadata_ExportName` when `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA=1` | Export typed C++ function as FFI DLL symbol |
| `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC(ExportName, DocString)` | macro | emits `extern "C" __tvm_ffi__doc_ExportName(...)` when metadata flag is 1 | Export docstring for a DLL-exported function (ac7bf68) |
| `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` | compile-time flag | default 0; set to 1 via `-D` to enable metadata/doc symbol emission | Governs metadata embedding in DLL export macros (ac7bf68) |
| `TypeKeyToIndex(type_key) -> int32` | function | `int32_t TypeKeyToIndex(std::string_view type_key)` | Convert type key string to runtime type index |
