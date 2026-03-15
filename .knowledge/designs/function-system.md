---
status: "active"
confidence: "high"
---
# Function System Design

**TL;DR**:
- Every FFI function is a ref-counted `FunctionObj` with a C-compatible `safe_call` entry point and an optional C++ `cpp_call` entry point (for direct invocation without exception translation overhead).
- Global functions are registered via `reflection::GlobalDef` inside `TVM_FFI_STATIC_INIT_BLOCK`, replacing the removed `TVM_FFI_REGISTER_GLOBAL` macro.
- `Function::FromTyped(callable)` wraps typed C++ callables into packed functions; `Function::FromPacked(callable)` wraps packed-signature callables.

## Problem Statement
### Background
- The FFI needs type-erased callables that cross language boundaries through a packed calling convention.
- Functions must be registerable by string name in a global table, accessible from C++, Python, Rust.

### Solution
- `FunctionObj` inherits from both `Object` (ref-counting) and `TVMFFIFunctionCell` (C ABI access).
- The packed calling convention (`TVMFFISafeCallType`) provides a universal C ABI.
- `GlobalDef` provides metadata-rich registration (name, doc, type_schema) via the reflection infrastructure.

### Goals
- Type-erased function calls with zero boxing overhead for POD arguments.
- Automatic argument unpacking from typed C++ functions.
- Non-goals: dynamic dispatch based on argument types (dispatch is caller's responsibility).

## Design

### Packed Calling Convention

```
C++ style:  void(const AnyView* args, int32_t num_args, Any* result)
C style:    int(void* handle, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result)
```

The C++ style throws exceptions. The C style (`TVMFFISafeCallType`) catches exceptions and returns error codes (0 = success, -1 = error in TLS, -2 = frontend error). The first parameter is named `handle` (not `self`), reflecting its role as a generic opaque handle that may be nullptr.

### Class Hierarchy

#### FunctionObj

```cpp
class FunctionObj : public Object, public TVMFFIFunctionCell {
    // TVMFFIFunctionCell provides:
    //   TVMFFISafeCallType safe_call;  // C call entry point (catches exceptions, returns error code)
    //   void* cpp_call;                // Optional direct C++ call (NULL for non-C++ functions)
    typedef void (*FCall)(const FunctionObj*, const AnyView*, int32_t, Any*);

    void CallPacked(const AnyView* args, int32_t num_args, Any* result) const {
        // Branchless select: if cpp_call is set, use it; otherwise redirect through safe_call
        FCall call_ptr = this->cpp_call
            ? reinterpret_cast<FCall>(this->cpp_call)
            : CppCallDedirectToSafeCall;
        (*call_ptr)(this, args, num_args, result);
    }
    static constexpr const char* _type_key = StaticTypeKey::kTVMFFIFunction;  // "ffi.Function"
};
```

Multiple inheritance from both `Object` and `TVMFFIFunctionCell` ensures the `safe_call` and `cpp_call` fields are accessible both as C++ object members and through the C ABI cell accessor. The dual-path design (since 4fe8b2b7) separates concerns: `cpp_call` for direct C++ invocation (fast, exceptions propagate natively), `safe_call` for cross-FFI-boundary calls (exception-safe, returns error code).

#### Implementation Classes (in `details` namespace)

| Class | Purpose |
|-------|---------|
| `FunctionObjImpl<TCallable>` | Stores a C++ callable with perfect forwarding (lvalue/rvalue constructors since 7a355c7); sets `cpp_call` to its static `CppCall` method and `safe_call` to exception-catching wrapper |
| `ExternCFunctionObjImpl` | Wraps a C-style callback (`void* handle` + `safe_call` + `deleter`); `cpp_call=nullptr` |
| `ExternCFunctionObjNullHandleImpl` | For raw C function pointers with null handle/deleter; `cpp_call=nullptr` (added in 4fe8b2b7) |

`ImportedFunctionObjImpl` and the `RedirectCallToSafeCall<Derived>` CRTP base were removed in 4fe8b2b7. External functions now set `cpp_call=nullptr`, and `CallPacked` automatically redirects through `CppCallDedirectToSafeCall` which translates the `safe_call` return code back to C++ exceptions.

#### Function (Reference Wrapper)

Key static factory methods:

- **`FromTyped(callable)`** -- wraps an ordinary C++ function/lambda, auto-generates argument unpacking via `TypeTraits` and index_sequence. (Renamed from `FromUnpacked` in 110b8f9.)
- **`FromTyped(callable, name)`** -- same, with a name for error messages.
- **`FromPacked(callable)`** -- wraps a callable matching packed signature `void(const AnyView*, int32_t, Any*)` or `void(PackedArgs, Any*)`.
- **`FromExternC(handle, safe_call, deleter)`** -- wraps a C-style callback.
- **`ImportFromExternDLL(other)`** -- imports a function from another DLL.

#### TypedFunction<R(Args...)>

Compile-time typed wrapper. Provides `operator()(Args...)` that auto-packs arguments and casts the return value. Implicitly constructible from compatible lambda types.

### Global Function Registry

Functions are registered by string name in a global table (`GlobalFunctionTable` in `src/ffi/function.cc`):

```cpp
Function::SetGlobal("name", func, allow_override);
Function::GetGlobal("name")       -> optional<Function>
Function::GetGlobalRequired("name") -> Function  // throws if not found
Function::ListGlobalNames()        -> vector<String>
Function::RemoveGlobal("name")
```

Internally, `GlobalFunctionTable` stores entries as `Object` subclasses (`GlobalFunctionTable::Entry`) in a `Map<String, Any>`, wrapping `TVMFFIMethodInfo` with metadata (name, doc, type_schema, flags) alongside the function. The table never frees Function pointers (uses `new Function*` without delete) to avoid destruction-order issues with Python callbacks.

#### Registration via GlobalDef (canonical pattern)

```cpp
TVM_FFI_STATIC_INIT_BLOCK() {
  namespace refl = tvm::ffi::reflection;
  refl::GlobalDef()
      .def("my.Add", [](int a, int b) -> int { return a + b; })
      .def_packed("my.ArrayCreate",
                  [](ffi::PackedArgs args, Any* ret) {
                    *ret = Array<Any>(args.data(), args.data() + args.size());
                  })
      .def_method("my.IntGetValue", &TIntObj::GetValue);
}
```

`GlobalDef` methods:
- `def(name, func, extra...)` -- typed function via `Function::FromTyped`
- `def_packed(name, func, extra...)` -- packed function via `Function::FromPacked`
- `def_method(name, method_ptr, extra...)` -- method pointer; dispatches ObjectRef by value, Object by pointer

Each builds a `TVMFFIMethodInfo` and calls `TVMFFIFunctionSetGlobalFromMethodInfo(&info, 0)`.

#### Duplicate Registration

The `TVMFFIMethodInfo*`-based `Update` path uses `TVM_FFI_LOG_AND_THROW` (not `TVM_FFI_THROW`) for duplicate detection, ensuring the error is logged to stderr before throwing -- important during static init where exceptions may be swallowed.

#### TVM_FFI_DLL_EXPORT_TYPED_FUNC

For exporting typed functions from shared libraries as `extern "C"` symbols:

```cpp
// Generates: extern "C" TVM_FFI_DLL_EXPORT int __tvm_ffi_AddOne(void*, TVMFFIAny*, int32_t, TVMFFIAny*)
// Note: symbol is prefixed with __tvm_ffi_ since commit 40e8a51
int AddOne_(int x) { return x + 1; }
TVM_FFI_DLL_EXPORT_TYPED_FUNC(AddOne, AddOne_);
```

Wraps the function body in `TVM_FFI_SAFE_CALL_BEGIN/END`, uses `details::unpack_call` for argument unpacking, and marks the symbol with `TVM_FFI_DLL_EXPORT`.

#### Function Metadata Export (since ac7bf68)

When `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA=1` (build flag, default 0), `TVM_FFI_DLL_EXPORT_TYPED_FUNC` additionally emits a metadata symbol `__tvm_ffi__metadata_<ExportName>` that returns a JSON string containing the function's type schema. A separate macro `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC` emits a documentation symbol `__tvm_ffi__doc_<ExportName>`.

```cpp
#define TVM_FFI_DLL_EXPORT_INCLUDE_METADATA 1

int AddOne_(int x) { return x + 1; }
TVM_FFI_DLL_EXPORT_TYPED_FUNC(AddOne, AddOne_);
// Emits: __tvm_ffi_AddOne (function) + __tvm_ffi__metadata_AddOne (type schema JSON)

TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC(AddOne, "Add one to an integer.");
// Emits: __tvm_ffi__doc_AddOne (docstring getter)
```

Both metadata and doc symbols follow the `TVMFFISafeCallType` convention (returning a `String` via `MoveToAny`). `LibraryModuleObj` resolves these at runtime via `GetFunctionMetadata` and `GetFunctionDoc`, which look up the corresponding symbols in the loaded library. The metadata JSON format is `{"type_schema": "<escaped_schema>"}`.

When `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA=0`, both macros expand to no-ops (the doc macro is completely elided, and the main macro only emits the function symbol).

The `build_inline` / `load_inline` Python API in `tvm_ffi.cpp.extension` automatically sets `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA=1` and emits `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC` for functions with non-empty docstrings.

### PackedArgs

View over `AnyView[]` with helper methods:
- `operator[](i)` -- index into arguments
- `Slice(begin, end)` -- subrange
- `Fill(data, args...)` -- static method to pack variadic args into AnyView array

### Exception/Error Boundary

```cpp
TVM_FFI_SAFE_CALL_BEGIN();
    // C++ code that may throw
TVM_FFI_SAFE_CALL_END();
```

`SAFE_CALL_END` catches: (1) `tvm::ffi::Error` -> TLS + return -1, (2) `EnvErrorAlreadySet` -> return -2, (3) `std::exception` -> wrap as InternalError + return -1.

### Argument Unpacking (`function_details.h`)

`FromTyped` uses `details::unpack_call<RetType>(index_sequence, name, callable, args, num_args, rv)`:
1. Validates argument count against function arity
2. For each parameter, calls `args[i].try_cast<ArgType>()` using `TypeTraits` (note: `try_cast`, not `as`, because function argument dispatch needs type conversion)
3. Calls the underlying function with unpacked arguments
4. Stores return value (if non-void) via `*rv = result`

#### Supported Argument Type Qualifiers (since 583e4b7)

`FromTyped` supports four argument type forms via the `details::ArgTypeSupported<T>` compile-time check:

```cpp
template <typename T>
static constexpr bool ArgTypeSupported =
    (!std::is_reference_v<T>) ||                                    // T or const T
    (std::is_const_v<std::remove_reference_t<T>> && std::is_lvalue_reference_v<T>) ||  // const T&
    (!std::is_const_v<std::remove_reference_t<T>> && std::is_rvalue_reference_v<T>);   // T&&
```

This means `T`, `const T`, `const T&`, and `T&&` are all valid parameter types. Non-const lvalue references (`T&`) are rejected at compile time. The `details::ArgValueWithContext<Type>` template class (previously non-template) provides type-safe argument extraction, fixing interaction with types that have template constructors (e.g., `std::optional<T>`).

### Key Classes, Fields and Interfaces

| Symbol | Signature / Description |
|--------|------------------------|
| `Function::FromTyped(callable)` | `template<F> static Function FromTyped(F callable)` -- wraps typed callable into packed Function |
| `Function::FromPacked(callable)` | `template<F> static Function FromPacked(F callable)` -- wraps packed-signature callable |
| `Function::FromExternC(handle, safe_call, deleter)` | Wraps C callback as Function |
| `Function::InvokeExternC(handle, safe_call, args...)` | `template<Args...> static Any InvokeExternC(void*, TVMFFISafeCallType, Args&&...)` -- direct call without `FunctionObj` allocation (since 9186b44) |
| `Function::SetGlobal(name, func, allow_override)` | Register in global table |
| `Function::GetGlobalRequired(name)` | Lookup or throw |
| `GlobalDef::def(name, func, extra...)` | Register typed global function with metadata |
| `GlobalDef::def_packed(name, func, extra...)` | Register packed global function |
| `GlobalDef::def_method(name, method, extra...)` | Register method pointer as global function |
| `TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, Func)` | Export typed function as extern "C" symbol; also emits `__tvm_ffi__metadata_<ExportName>` when `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA=1` (since ac7bf68) |
| `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC(ExportName, DocStr)` | Export documentation symbol `__tvm_ffi__doc_<ExportName>`; only emitted when `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA=1` (since ac7bf68) |
| `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` | Build flag (0/1, default 0) controlling whether metadata and doc symbols are emitted (since ac7bf68) |
| `TVM_FFI_STATIC_INIT_BLOCK()` | Static initialization block for registration (function-style since 7b813f8) |
| `Function.__from_extern_c__(c_symbol, *, keep_alive_object)` | Python: create Function from `TVMFFISafeCallType` C pointer (since b64b46f) |
| `Function.__from_mlir_packed_safe_call__(mlir_symbol, *, keep_alive_object)` | Python: create Function from MLIR packed `void(void**)` pointer (since f6303b2) |
| `TVMFFIPyMLIRPackedSafeCall` | C++ adapter: translates MLIR packed convention to FFI safe call convention |

### Contracts, Assumptions and Invariants
- **PackedArgs lifetime**: `PackedArgs` is a non-owning view over `AnyView[]`. The caller must ensure the underlying array outlives the `PackedArgs` view.
- **Argument unpacking uses try_cast**: Function argument dispatch uses `try_cast<T>()` (not `as<T>()`), enabling type coercions (e.g., `int` for a `double` parameter).
- **Duplicate registration detection**: The `TVMFFIMethodInfo*` path logs and throws; the `(String, Function, bool)` path throws without logging.
- **Never-free registry**: `GlobalFunctionTable` never frees stored `Function*` pointers to avoid destruction-order issues with cross-language callbacks.

### Extension Points
- New function implementation classes can inherit from `FunctionObj` and set up custom `call`/`safe_call` pairs.
- `GlobalDef` extra args support `const char*` (doc) and `FieldInfoTrait`-like metadata.

### Usage Examples

#### Defining and calling a typed function
**Context**: Creating a typed C++ function and calling it through the FFI.
```cpp
// Define
auto add = Function::FromTyped([](int a, int b) -> int { return a + b; });

// Call via packed convention (how cross-language calls work)
Any result;
AnyView args[] = {AnyView(1), AnyView(2)};
add->call(args, 2, &result);
assert(result.cast<int>() == 3);

// Call via TypedFunction wrapper
TypedFunction<int(int, int)> typed_add = add;
int r = typed_add(1, 2);  // auto-pack and unpack
```

#### Exporting a function with metadata and docstring (C++ -> Python)
**Context**: Exporting a typed function from a shared library with type schema and documentation, then querying them from Python.
```cpp
// In C++ source (compiled with TVM_FFI_DLL_EXPORT_INCLUDE_METADATA=1)
int AddOne_(int x) { return x + 1; }
TVM_FFI_DLL_EXPORT_TYPED_FUNC(AddOne, AddOne_);
TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC(AddOne, "Add one to the input integer.");
```
```python
# In Python
import tvm_ffi
mod = tvm_ffi.load_module("add_one.so")
metadata = mod.get_function_metadata("AddOne")  # {"type_schema": "..."}
doc = mod.get_function_doc("AddOne")  # "Add one to the input integer."
```

### Python Binding: Packed Function Calling (since 2d41a51, refactored in 38d2cda)

The Cython layer in `function.pxi` implements the Python side of the packed calling convention via a C++-based type-dispatch system:

**`Function.__call__(self, *args)`**: `Function` is a `cdef class` with a `release_gil` property (default from `TVM_FFI_RELEASE_GIL_BY_DEFAULT` env var). Initializes `result` to `kTVMFFINone`, calls `TVMFFIPyFuncCall` which dispatches to `TVMFFIPyCallManager.FuncCall`. This packs args via cached type-dispatch setters (each `PyTypeObject*` is mapped to a `TVMFFIPyArgSetter` in a thread-local `unordered_map`), manages stream/device/allocator context, optionally releases the GIL, and calls `TVMFFIFunctionCall`. On return, `make_ret(result, c_dlpack_to_pyobject)` unpacks the result with optional framework tensor conversion.

**Setter factory**: `TVMFFIPyArgSetterFactory_` (Cython) runs the isinstance chain once per Python type and caches the result. POD type setters (`float`, `int`, `bool`, `None`) are C++ functions in `tvm_ffi_python_helpers.h`. Complex setters (Tensor, DLPack, containers, str, bytes) are Cython functions.

**String/Bytes**: `str` uses `TVMFFIStringFromByteArray` (creates owned String with SSO) instead of the old `kTVMFFIRawStr` view. `bytes` uses `TVMFFIBytesFromByteArray` instead of `kTVMFFIByteArrayPtr`.

**Container conversion**: `list`/`tuple`/`dict` are handled by Cython setters (`TVMFFIPyArgSetterTuple_`, `TVMFFIPyArgSetterTupleLike_`, `TVMFFIPyArgSetterMap_`) that call `TVMFFIPyConstructorCall` for recursive conversion, replacing the old `_FUNC_CONVERT_TO_OBJECT` callback.

**DLPack fast path**: When a type has `__c_dlpack_exchange_api__`, the factory installs a setter that calls the `DLPackExchangeAPI` struct's function pointers directly, bypassing Python's `__dlpack__` protocol. See `.knowledge/designs/0018-dlpack-fast-path.md`.

**CUDA stream context**: When tensors with stream context are passed, the setter captures the stream. Before the C call, `TVMFFIEnvSetStream` (renamed from `TVMFFIEnvSetCurrentStream` in f81ab9c) installs it as thread-local context. The previous stream is restored after the call.

See `.knowledge/designs/0014-python-bindings.md` for the full dispatch table and architecture.

### Kwargs Wrapping Utility (since 3115b237)

The `tvm_ffi.utils.kwargs_wrapper` module provides code-generation-based wrappers that add keyword argument support to packed functions (which only accept positional arguments).

**`make_kwargs_wrapper(target_func, arg_names, arg_defaults, kwonly_names, kwonly_defaults, prototype)`**: Generates a Python wrapper function with the specified signature using `exec`-based code generation. The wrapper translates keyword arguments into positional calls to `target_func`.

Key design decisions:
- Default values for `None` and `bool` are embedded directly in generated code. All other defaults use a `MISSING` sentinel to avoid evaluating `__repr__` on arbitrary objects.
- Argument names are validated against Python keywords, identifier rules, and reserved internal names (`__i_target_func`, `__i_MISSING`, `__i_arg_defaults`).
- Supports keyword-only arguments via `*` separator in the generated signature.

**`make_kwargs_wrapper_from_signature(target_func, signature, prototype, exclude_arg_names)`**: Convenience wrapper that extracts parameter information from an `inspect.Signature` object. Rejects `*args` and `**kwargs` parameters.

```python
from tvm_ffi.utils.kwargs_wrapper import make_kwargs_wrapper

packed_fn = tvm_ffi.get_global_func("my.add")
wrapped = make_kwargs_wrapper(
    packed_fn,
    arg_names=["a", "b"],
    arg_defaults=(0,),  # b defaults to 0
    kwonly_names=["debug"],
    kwonly_defaults={"debug": False},
)
result = wrapped(1, b=2, debug=True)
```

### FunctionInfo vs FunctionInfoHelper (member-pointer semantics, fixed in 368af82)

Two template families decompose function signatures differently:

- **`FunctionInfo<R (Class::*)(Args...)>`**: Includes `Class*` as the first parameter in `FuncFunctorImpl<R, Class*, Args...>`. Used for schema generation of methods registered via `def_method`/`def`, where `self` is the first packed argument.
- **`FunctionInfoHelper<R (T::*)(Args...)>`**: Omits the class parameter, using `FuncFunctorImpl<R, Args...>`. Used for decomposing lambda/functor `operator()` where the lambda object is implicit context, not a visible parameter.

This distinction ensures that `TypeSchema()` and `Sig()` correctly report the full signature `(Class*, Args...) -> R` for member function methods.

A third specialization `FunctionInfo<R (&)(Args...), void>` (added in af898a2) handles function lvalue reference types, mapping them to `FuncFunctorImpl<R, Args...>`. This completes the set of function-type decomposition specializations:
- `R(Args...)` -- bare function type
- `R (*)(Args...)` -- function pointer
- `R (&)(Args...)` -- function lvalue reference (fixes compile errors when extra parentheses in `TVM_FFI_DLL_EXPORT_TYPED_FUNC` or `constexpr auto&` bindings produce reference types via `decltype`)

### Python Function Creation from Extern C / MLIR (since b64b46f, f6303b2)

Two static methods on the Cython `Function` class enable creating FFI functions from raw C function pointers:

- **`Function.__from_extern_c__(c_symbol: int, *, keep_alive_object=None) -> Function`** (added in b64b46f): Wraps a `TVMFFISafeCallType`-compatible C function pointer. When `keep_alive_object` is provided, it is `Py_INCREF`'d and stored as the function's closure with `TVMFFIPyObjectDeleter` as deleter. Calls `TVMFFIFunctionCreate` under the hood.

- **`Function.__from_mlir_packed_safe_call__(mlir_packed_symbol: int, *, keep_alive_object=None) -> Function`** (added in f6303b2): Wraps an MLIR packed safe call function pointer (`void(void**)`) via the `TVMFFIPyMLIRPackedSafeCall` adapter class. The adapter translates between the MLIR packed convention (`packed_args = [&handle, &args, &num_args, &rv, &ret_code]`) and the FFI safe call convention.

The `TVMFFIPyMLIRPackedSafeCall` C++ class in `tvm_ffi_python_helpers.h` holds the MLIR function pointer and optional `PyObject*` keep-alive reference, with static `Invoke` and `Deleter` methods.

### Rust Binding (since 09477ce)

The Rust crate `tvm-ffi` provides a complete function system mirror:

**`Function`**: Wraps `ObjectArc<FunctionObj>`. Three construction paths:

1. **`Function::from_typed(f)`**: Wraps a typed `Fn(T0, ..., TN) -> Result<Out>` via the `AsPackedCallable` trait (0-8 args). Internally delegates to `from_packed` with a generated closure.

2. **`Function::from_packed(f)`**: Wraps `Fn(&[AnyView]) -> Result<Any>`. Creates a `CallbackFunctionObjImpl<F>` that stores the closure alongside a `FunctionObj` in the same `#[repr(C)]` allocation, with `safe_call` pointing to a generated `invoke_callback` and `cxx_call = nullptr`.

3. **`Function::from_extern_c(handle, safe_call, deleter)`**: Wraps a C-style callback via `TVMFFIFunctionCreate`.

**Calling**:
- `call_packed(&[AnyView]) -> Result<Any>`: Invokes `safe_call` directly, checks return code, retrieves TLS error on failure.
- `call_tuple(tuple_args) -> Result<Any>`: Small-vector optimization (stack-allocates up to 4 `AnyView`s, heap for more).
- `call_tuple_with_len::<LEN>(tuple_args) -> Result<Any>`: Const-generic stack allocation for known arg count.

**`into_typed_fn!` macro** (Rust equivalent of C++ `TypedFunction<R(Args...)>`):
```rust
let add = Function::from_typed(|x: i32, y: i32| -> Result<i32> { Ok(x + y) });
let typed_add = into_typed_fn!(add, Fn(i32, i32) -> Result<i32>);
assert_eq!(typed_add(1, 2).unwrap(), 3);
```

Supports 0-8 arguments. Uses `IntoArgHolderTuple` to convert arguments to canonical types, then `call_tuple_with_len` for invocation, and `TryInto` for result extraction.

**`tvm_ffi_dll_export_typed_func!` macro** (Rust equivalent of C++ `TVM_FFI_DLL_EXPORT_TYPED_FUNC`):
```rust
fn my_add(x: i32, y: i32) -> Result<i32> { Ok(x + y) }
tvm_ffi_dll_export_typed_func!(my_add, my_add);
// Generates: pub unsafe extern "C" fn __tvm_ffi_my_add(...) -> i32
```

**`AsPackedCallable<I, O>` trait**: Implemented for `Fn(T0, ..., TN) -> Result<Out>` for 0-8 args via macro. Validates argument count, extracts each arg via `ArgTryFromAnyView::try_from_any_view` (which tries strict check then conversion), calls the function, wraps the result in `Any`.

**Global registry**: `Function::get_global(name)` and `Function::register_global(name, func)` wrap the C API `TVMFFIFunctionGetGlobal`/`TVMFFIFunctionSetGlobal`.

See `.knowledge/designs/rust-bindings.md` for the full Rust binding architecture.

### Evolution Timeline
| Version | Commit | Change | Motivation |
|---------|--------|--------|------------|
| v1 | 7d34eb8 | Initial: `FromUnpacked`, `TVM_FFI_REGISTER_GLOBAL`, `Function::Registry` | Establish function system |
| v2 | 110b8f9 | Rename `FromUnpacked` to `FromTyped`; purge `PackedFunc` terminology | Clearer naming |
| v3 | 192f196 | Add `TVM_FFI_DLL_EXPORT`, `TVM_FFI_DLL_EXPORT_TYPED_FUNC` | Shared library export support |
| v4 | b333288 | Introduce `GlobalDef` for metadata-rich function registration | Reflection-aligned registration |
| v5 | 26b68b0 | Remove `TVM_FFI_REGISTER_GLOBAL` and `Function::Registry` | Complete migration to GlobalDef |
| v6 | 5b0cceb | Log-and-throw for duplicate GlobalDef registration | Better diagnostics during static init |
| v7 | 4fe8b2b | Dual-path `safe_call`/`cpp_call`; `ExternCFunctionObjImpl`/`ExternCFunctionObjNullHandleImpl` | Separate exception-safe and direct call paths |
| v8 | 28fe3cc | `TypeSchema()` on `FuncFunctorImpl`; `FunctionInfo` member function `TypeSchema()` | JSON schema for function signatures |
| v9 | 368af82 | Fix `FunctionInfo<R (Class::*)(Args...)>` to include `Class*` as first param | Correct schema arity for member methods |
| v10 | b64b46f | Python `Function.__from_extern_c__`; fix Cython `TVMFFIObject.deleter` field signature | Python-level extern C function creation |
| v11 | f6303b2 | Python `Function.__from_mlir_packed_safe_call__`; `TVMFFIPyMLIRPackedSafeCall` adapter | MLIR JIT integration via packed convention adapter |
| v12 | 9186b44 | `Function::InvokeExternC` static template method | Zero-allocation direct call to extern C symbol |
| v13 | af898a2 | Add `FunctionInfo<R (&)(Args...)>` specialization for function lvalue references | Fix compile error with extra parentheses in `TVM_FFI_DLL_EXPORT_TYPED_FUNC` |
| v14 | 583e4b7 | `ArgTypeSupported<T>` compile-time check; `const T&` and `T&&` support in `FromTyped`; `ArgValueWithContext<Type>` template class | Enable natural C++ parameter style for FFI functions |
| v15 | 7a355c7 | `FunctionObjImpl<TCallable>` uses perfect forwarding (separate lvalue/rvalue constructors); `static_assert` ensuring `TCallable` is not const/reference | Avoid unnecessary copy/move construction when creating Function objects |
| v16 | ac7bf68 | `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` flag; `TVM_FFI_DLL_EXPORT_TYPED_FUNC` emits metadata symbol; `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC` macro for docstrings; `tvm_ffi_doc_prefix` symbol constant | Runtime reflection of exported function signatures and documentation |
| v17 | 3115b237 | `tvm_ffi.utils.kwargs_wrapper` module with `make_kwargs_wrapper` and `make_kwargs_wrapper_from_signature` | Python-style keyword arguments for packed functions |

## Alternatives & Trade-offs
### Keep both TVM_FFI_REGISTER_GLOBAL and GlobalDef
- Pros: Backward compatibility; simpler for one-off registrations
- Cons: Two patterns to maintain; macro-based registration lacks metadata (doc, type_schema); confusing which to use
### Use a decorator/attribute pattern instead of static init blocks
- Pros: More familiar to Python users
- Cons: C++ has no native decorator syntax; `TVM_FFI_STATIC_INIT_BLOCK` achieves the same effect with standard C++ mechanisms

## Related Work
### Design Docs & ADRs
- `.knowledge/designs/reflection.md` -- `GlobalDef` builder, `TVM_FFI_STATIC_INIT_BLOCK`
- `.knowledge/designs/c-abi.md` -- `TVMFFISafeCallType`, `TVMFFIFunctionCell`
- `.knowledge/ADRs/008-globaldef-replaces-register-global.md` -- Decision to migrate to GlobalDef

### Evidence Matrix
- `FromTyped` rename -> `2025-05-07-110b8f9.md` + commit 110b8f9
- `TVM_FFI_DLL_EXPORT_TYPED_FUNC` -> `2025-05-29-192f196.md` + commit 192f196
- `GlobalDef` introduction -> `2025-07-03-b333288.md` + commit b333288
- `Registry` removal -> `2025-07-15-26b68b0.md` + commit 26b68b0
- Log-and-throw for duplicates -> `2025-07-16-5b0cceb.md` + commit 5b0cceb
- FunctionInfo member-pointer fix -> `2025-10-07-368af824845424ea439b9f3d68bf4a710afb38b1.md` + commit 368af82
- Python `__from_extern_c__` -> `2025-10-10-b64b46f32e845b650850d73a5828a2d3f07d3406.md` + commit b64b46f
- Python `__from_mlir_packed_safe_call__` -> `2025-10-11-f6303b23fd97909b59f6ff67b85f2203371f5db1.md` + commit f6303b2
- Plus 2 supporting commits (11a4a02 `handle` rename, 8a00988 `TVM_FFI_WEAK` macro)
- `Function::InvokeExternC` -> `2025-10-14-9186b44d.md` + commit 9186b44
- `FunctionInfo<R(&)(Args...)>` specialization -> `2025-10-24-af898a2c32f053806064ef7b679682f94b5569c1.md` + commit af898a2
- `ArgTypeSupported<T>` + const ref/rvalue ref support -> `2025-11-10-583e4b73.md` + commit 583e4b7
- `FunctionObjImpl` perfect forwarding -> `2025-11-17-7a355c77.md` + commit 7a355c7
- Metadata export pattern (`TVM_FFI_DLL_EXPORT_INCLUDE_METADATA`, `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC`) -> `2025-11-20-ac7bf68058b392c3a8475619016fde48bd08334b.md` + commit ac7bf68
- Kwargs wrapper utility -> `2025-12-04-3115b237d43fa2c7a24157ec88e1a9f9ec403900.md` + commit 3115b237 + `make_kwargs_wrapper`, `make_kwargs_wrapper_from_signature`
- Plus 1 supporting commit (6bc1a8eb robustify kwargs wrapper)
