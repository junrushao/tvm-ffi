---
scope: "function-system"
status: "active"
last_updated_commit: "3115b237d43fa2c7a24157ec88e1a9f9ec403900"
related_designs:
  - ".knowledge/designs/function-system.md"
related_adrs:
  - ".knowledge/ADRs/008-globaldef-replaces-register-global.md"
---
# API Index: Function System

**Scope**: Type-erased callable objects, global function registry, and function export utilities.
**Design docs**: `.knowledge/designs/function-system.md`
**ADRs**: `.knowledge/ADRs/008-globaldef-replaces-register-global.md`

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFIFunctionCreate` | `int TVMFFIFunctionCreate(void* handle, TVMFFISafeCallType call, void(*deleter)(void*), TVMFFIObjectHandle* out)` | Create Function from C callback |
| `TVMFFIFunctionCall` | `int TVMFFIFunctionCall(TVMFFIObjectHandle func, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result)` | Invoke function via safe_call |
| `TVMFFIFunctionSetGlobal` | `int TVMFFIFunctionSetGlobal(const char* name, TVMFFIObjectHandle func, int allow_override)` | Register a global function |
| `TVMFFIFunctionGetGlobal` | `int TVMFFIFunctionGetGlobal(const char* name, TVMFFIObjectHandle* out)` | Retrieve a global function |
| `TVMFFIFunctionSetGlobalFromMethodInfo` | `int TVMFFIFunctionSetGlobalFromMethodInfo(const TVMFFIMethodInfo* info, int allow_override)` | Register global function with metadata |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `FunctionObj` | class | `FCall call`, `TVMFFISafeCallType safe_call`; `_type_key = "ffi.Function"` | Base function object with dual call entry points |
| `Function` | class (ObjectRef) | `FromTyped(callable)`, `FromPacked(callable)`, `FromExternC(...)`, `SetGlobal(...)`, `GetGlobal(...)`, `GetGlobalRequired(...)` | Reference wrapper with factory methods |
| `TypedFunction<R(Args...)>` | class template | `R operator()(Args...)` | Compile-time typed wrapper around Function |
| `PackedArgs` | class | `operator[](i)`, `Slice(begin, end)`, `data()`, `size()` | Non-owning view over AnyView[] argument array |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `details::ArgTypeSupported<T>` | `template<T> static constexpr bool ArgTypeSupported` | Compile-time check: accepts `T`, `const T`, `const T&`, `T&&`; rejects `T&` (since 583e4b7) |
| `details::ArgValueWithContext<Type>` | `template<typename Type> class ArgValueWithContext` | Type-safe argument extraction wrapper; parameterized on expected type (since 583e4b7) |
| `Function::FromTyped(callable)` | `template<F> static Function FromTyped(F callable)` | Wrap typed callable into packed Function |
| `Function::FromTyped(callable, name)` | `template<F> static Function FromTyped(F callable, std::string name)` | Same, with name for error messages |
| `Function::FromPacked(callable)` | `template<F> static Function FromPacked(F callable)` | Wrap packed-signature callable |
| `Function::FromExternC(handle, safe_call, deleter)` | `static Function FromExternC(void*, TVMFFISafeCallType, void(*)(void*))` | Wrap C callback |
| `Function::ImportFromExternDLL(other)` | `static Function ImportFromExternDLL(Function other)` | Import function from another DLL |
| `TVM_FFI_DLL_EXPORT_TYPED_FUNC(Export, Func)` | Generates `extern "C" TVM_FFI_DLL_EXPORT int __tvm_ffi_##Export(void*, TVMFFIAny*, int32_t, TVMFFIAny*)`; also emits `__tvm_ffi__metadata_##Export` when `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA=1` | Export typed function as C symbol with `__tvm_ffi_` prefix (prefixed since 40e8a51; metadata since ac7bf68) |
| `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC(Export, DocStr)` | Generates `extern "C" TVM_FFI_DLL_EXPORT int __tvm_ffi__doc_##Export(...)` returning docstring; no-op when `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA=0` | Export docstring symbol for a typed function (since ac7bf68) |
| `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` | `#define TVM_FFI_DLL_EXPORT_INCLUDE_METADATA 0` (default) | Build flag controlling metadata/doc symbol emission (since ac7bf68) |
| `TVM_FFI_SAFE_CALL_BEGIN()` / `TVM_FFI_SAFE_CALL_END()` | Exception boundary macros | Catch C++ exceptions, store in TLS, return error code |
| `TVM_FFI_CHECK_SAFE_CALL(expr)` | Check C ABI return code, rethrow on error | Error code to exception conversion |
| `TVMFFIPyMLIRPackedSafeCall` | C++ adapter class with `Invoke`/`Deleter` static methods | MLIR packed `void(void**)` -> FFI safe call convention (since f6303b2) |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `Function.__from_extern_c__` | `(c_symbol: int, *, keep_alive_object=None) -> Function` | Create Function from TVMFFISafeCallType C pointer (since b64b46f) |
| `Function.__from_mlir_packed_safe_call__` | `(mlir_symbol: int, *, keep_alive_object=None) -> Function` | Create Function from MLIR packed pointer (since f6303b2) |
| `make_kwargs_wrapper` | `(target_func, arg_names, arg_defaults, kwonly_names, kwonly_defaults, prototype) -> Callable` | Code-gen kwargs wrapper for positional-only functions (since 3115b237) |
| `make_kwargs_wrapper_from_signature` | `(target_func, signature, prototype, exclude_arg_names) -> Callable` | Convenience wrapper extracting params from `inspect.Signature` (since 3115b237) |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `Function::FromUnpacked(callable)` | `Function::FromTyped(callable)` | 110b8f9 | Clearer naming |
| `TVM_FFI_REGISTER_GLOBAL(name)` | `GlobalDef().def(name, ...)` in `TVM_FFI_STATIC_INIT_BLOCK` | 26b68b0 | Macro removed |
| `Function::Registry` | `reflection::GlobalDef` | 26b68b0 | Class removed |
| `set_body_typed(f)` | `GlobalDef().def(name, f)` | 26b68b0 | Method on removed class |
| `set_body_packed(f)` | `GlobalDef().def_packed(name, f)` | 26b68b0 | Method on removed class |
| `set_body_method(f)` | `GlobalDef().def_method(name, f)` | 26b68b0 | Method on removed class |
| `TVMFFISafeCallType` param `self` | `handle` | 11a4a02 | Documentation naming clarification |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 110b8f9 | `2025-05-07-110b8f9.md` | Rename FromUnpacked to FromTyped |
| 192f196 | `2025-05-29-192f196.md` | Add TVM_FFI_DLL_EXPORT, TVM_FFI_DLL_EXPORT_TYPED_FUNC |
| b333288 | `2025-07-03-b333288.md` | Introduce GlobalDef |
| 26b68b0 | `2025-07-15-26b68b0.md` | Remove TVM_FFI_REGISTER_GLOBAL and Function::Registry |
| 5b0cceb | `2025-07-16-5b0cceb.md` | Log-and-throw for duplicate GlobalDef registration |
| b64b46f | `2025-10-10-b64b46f.md` | Python Function.__from_extern_c__ |
| f6303b2 | `2025-10-11-f6303b2.md` | Python Function.__from_mlir_packed_safe_call__ + TVMFFIPyMLIRPackedSafeCall adapter |
| 583e4b7 | `2025-11-10-583e4b73.md` | ArgTypeSupported<T>, ArgValueWithContext<Type>, const T&/T&& support |
| 7a355c7 | `2025-11-17-7a355c77.md` | FunctionObjImpl perfect forwarding (lvalue/rvalue constructors) |
| ac7bf68 | `2025-11-20-ac7bf68058b392c3a8475619016fde48bd08334b.md` | TVM_FFI_DLL_EXPORT_INCLUDE_METADATA, TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC |
| 3115b237 | `2025-12-04-3115b237d43fa2c7a24157ec88e1a9f9ec403900.md` | kwargs_wrapper module: make_kwargs_wrapper, make_kwargs_wrapper_from_signature |
