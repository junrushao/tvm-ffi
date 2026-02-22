# 013 — Function and Calling Convention

- Doc ID: 013-function-calling-convention
- Status: Approved
- Last Updated: 2026-02-22
- Owners: Tianqi Chen

## Overview

Every function call in TVM FFI is represented by a single universal C ABI
signature: `TVMFFISafeCallType`. This "packed function" convention type-erases
all arguments into an `AnyView[]` array and routes them through one of two
function pointers stored in `TVMFFIFunctionCell`: a `safe_call` pointer that
catches C++ exceptions and returns error codes (used at ABI boundaries), and an
optional `cpp_call` pointer that propagates exceptions directly (used within the
same DSO for performance). On top of this C-level protocol, C++ provides
`TypedFunction<R(Args...)>` for compile-time type safety, `PackedArgs` for
lightweight argument access, `Function::FromTyped` for converting arbitrary
callables into packed functions, `Function::InvokeExternC` for zero-allocation
extern C invocation, and `CallExpected<T>` for exception-free error handling.
Python callables are automatically converted to FFI functions via a Cython
bridge, and a thread-local dispatch cache maps `PyTypeObject*` to pre-built
argument setters for fast cross-language calls.

## Key Design

### The canonical calling convention: TVMFFISafeCallType

`TVMFFISafeCallType` (`c_api.h:491-492`) is the single function pointer
typedef that defines the C ABI for all TVM FFI function calls:

```c
typedef int (*TVMFFISafeCallType)(void* handle, const TVMFFIAny* args,
                                  int32_t num_args, TVMFFIAny* result);
```

The four parameters are: `handle` (the function's closure state or `self`
pointer), `args` (type-erased argument array), `num_args` (argument count),
and `result` (output slot). The caller must initialize `result->type_index` to
`kTVMFFINone` or any value less than `kTVMFFIStaticObjectBegin`.

Return value semantics: 0 on success, -1 on error. Errors are not propagated
through the return argument; instead they are stored in thread-local storage
and retrieved via `TVMFFIErrorMoveFromRaised`. As the `c_api.h` comment
(lines 479-484) notes, this TLS-based design "simplifies error propagation in
chains of calls in compiler codegen" since the error does not need to be
threaded through each function argument.

### TVMFFIFunctionCell: dual call pointer layout

`TVMFFIFunctionCell` (`c_api.h:499-516`) sits at a fixed offset after the
`TVMFFIObject` header in every function object:

```c
typedef struct {
  TVMFFISafeCallType safe_call;  // C ABI compatible, catches exceptions
  void* cpp_call;                // C++ direct call, throws (or NULL)
} TVMFFIFunctionCell;
```

`FunctionObj` (`function.h:113`) inherits both `Object` and
`TVMFFIFunctionCell`, making the two function pointers accessible from both
the C and C++ sides:

```cpp
class FunctionObj : public Object, public TVMFFIFunctionCell {
 public:
  using FCall = void (*)(const FunctionObj*, const AnyView*, int32_t, Any*);
};
```

Key invariants:

- `safe_call` is always non-null for valid function objects.
- `cpp_call` is null for functions not originally created in C++ (Python
  callbacks, extern C functions).
- `FCall` has the same parameter layout as `TVMFFISafeCallType` except the
  return type is `void` and errors propagate via C++ exceptions.

### safe_call vs cpp_call: dispatch and fallback

Two function pointers exist to balance cross-DLL safety with same-DSO
performance:

- `safe_call`: used at ABI boundaries (cross-language, cross-DLL). Wraps the
  call in `TVM_FFI_SAFE_CALL_BEGIN/END`, catching C++ exceptions and storing
  them in TLS.
- `cpp_call`: used within the same compilation unit or shared library.
  Propagates exceptions directly via `throw`, avoiding the exception
  catch/rethrow overhead.

`CallPacked` (`function.h:125-131`) dispatches between the two with a
branchless conditional select:

```cpp
TVM_FFI_INLINE void CallPacked(const AnyView* args, int32_t num_args,
                                Any* result) const {
  FCall call_ptr =
      this->cpp_call ? reinterpret_cast<FCall>(this->cpp_call)
                     : CppCallDedirectToSafeCall;
  (*call_ptr)(this, args, num_args, result);
}
```

When `cpp_call` is null, the fallback `CppCallDedirectToSafeCall`
(`function.h:143-148`) calls `safe_call` and re-throws via
`TVM_FFI_CHECK_SAFE_CALL`:

```cpp
static void CppCallDedirectToSafeCall(const FunctionObj* func,
                                      const AnyView* args,
                                      int32_t num_args, Any* rv) {
  FunctionObj* self = const_cast<FunctionObj*>(func);
  TVM_FFI_CHECK_SAFE_CALL(
      self->safe_call(self, reinterpret_cast<const TVMFFIAny*>(args),
                      num_args, reinterpret_cast<TVMFFIAny*>(rv)));
}
```

`FunctionObjImpl<TCallable>` (`function.h:172-174`) sets both pointers when
constructed from a C++ callable:

```cpp
this->safe_call = SafeCall;
this->cpp_call = reinterpret_cast<void*>(CppCall);
```

`ExternCFunctionObjNullHandleImpl` and `ExternCFunctionObjImpl` both set
`cpp_call = nullptr` (`function.h:209, 221`) since their callables are C
functions that cannot participate in C++ exception propagation.

### Safe call macros

`TVM_FFI_SAFE_CALL_BEGIN()` / `TVM_FFI_SAFE_CALL_END()` (`function.h:72-90`)
wrap C++ code in try-catch blocks, converting exceptions to error codes stored
in TLS:

```cpp
#define TVM_FFI_SAFE_CALL_BEGIN() \
  try {                           \
  (void)0

#define TVM_FFI_SAFE_CALL_END()                                      \
  return 0;                                                          \
  }                                                                  \
  catch (const ::tvm::ffi::Error& err) {                             \
    ::tvm::ffi::details::SetSafeCallRaised(err);                     \
    return -1;                                                       \
  }                                                                  \
  catch (const std::exception& ex) {                                 \
    ::tvm::ffi::details::SetSafeCallRaised(                          \
        ::tvm::ffi::Error("InternalError", ex.what(), ""));          \
    return -1;                                                       \
  }
```

`TVM_FFI_CHECK_SAFE_CALL(func)` (`function.h:101-107`) checks the return code
and re-throws the error from TLS:

```cpp
#define TVM_FFI_CHECK_SAFE_CALL(func)                      \
  {                                                        \
    int ret_code = (func);                                 \
    if (ret_code != 0) {                                   \
      throw ::tvm::ffi::details::MoveFromSafeCallRaised(); \
    }                                                      \
  }
```

### TypedFunction: compile-time type-safe wrapper

`TypedFunction<R(Args...)>` (`function.h:757-891`) wraps a `Function`
internally and provides compile-time type checking for C++ callers:

```cpp
template <typename R, typename... Args>
class TypedFunction<R(Args...)> {
 public:
  using TSelf = TypedFunction<R(Args...)>;

  template <typename FLambda, typename = std::enable_if_t<
      std::is_convertible_v<FLambda, std::function<R(Args...)>>>>
  TypedFunction(FLambda&& typed_lambda);

  TVM_FFI_INLINE R operator()(Args... args) const;
  operator Function() const { return packed(); }
  static std::string TypeSchema();

 private:
  Function packed_;
};
```

`operator()` (`function.h:853-864`) calls the underlying `packed_` function,
then casts the `Any` result to `R`. `TypeSchema()` delegates to
`FuncFunctorImpl<R, Args...>::TypeSchema()` (`function_details.h:100-107`)
which produces JSON like `{"type":"ffi.Function","args":[<ret>,<arg1>,...]}`.

`TypeTraits<TypedFunction<FType>>` (`function.h:893-929`) handles
`AnyView`/`Any` conversions so `TypedFunction` can be passed through the FFI
boundary.

### Function::FromTyped: converting callables to packed functions

`Function::FromTyped` (`function.h:536-544`) converts an arbitrary C++
callable into a packed function through a three-stage pipeline:

```cpp
template <typename TCallable>
static Function FromTyped(TCallable&& callable) {
  using FuncInfo = details::FunctionInfo<std::decay_t<TCallable>>;
  auto call_packed = [callable = std::forward<TCallable>(callable)](
                         const AnyView* args, int32_t num_args,
                         Any* rv) mutable -> void {
    details::unpack_call<typename FuncInfo::RetType>(
        std::make_index_sequence<FuncInfo::num_args>{},
        nullptr, callable, args, num_args, rv);
  };
  return FromPackedInternal(std::move(call_packed));
}
```

The `FunctionInfo<T>` trait (`function_details.h:123-145`) extracts `RetType`,
`ArgType`, and `num_args` from function pointers, member function pointers,
and lambdas (via `decltype(&T::operator())`). Supported argument types are
`T`, `const T`, `const T&`, and `T&&` (`function_details.h:61-66`).

`unpack_call<R>` (`function_details.h:205-232`) performs the actual argument
unpacking using `ArgValueWithContext`, which does `try_cast` per argument with
rich error messages including the argument index and function name:

```cpp
template <typename R, std::size_t... Is, typename F>
TVM_FFI_INLINE void unpack_call(std::index_sequence<Is...>,
                                const std::string* optional_name,
                                const F& f, const AnyView* args,
                                int32_t num_args, Any* rv) {
  constexpr size_t nargs = sizeof...(Is);
  if (nargs != num_args) { /* throw TypeError */ }
  if constexpr (std::is_same_v<R, void>) {
    f(ArgValueWithContext<std::tuple_element_t<Is, PackedArgs>>{
        args, Is, optional_name, f_sig}...);
  } else {
    *rv = R(f(ArgValueWithContext<...>{args, Is, optional_name, f_sig}...));
  }
}
```

A two-argument overload of `FromTyped` (`function.h:552-562`) also captures a
`std::string name` for better error messages in type mismatches.

### PackedArgs: variadic argument accessor

`PackedArgs` (`function.h:261-314`) is a lightweight non-owning view over
`const AnyView*` and `int32_t size`:

```cpp
class PackedArgs {
 public:
  PackedArgs(const AnyView* data, int32_t size);
  int size() const;
  const AnyView* data() const;
  PackedArgs Slice(int begin, int end = -1) const;
  AnyView operator[](int i) const;

  template <typename... Args>
  TVM_FFI_INLINE static void Fill(AnyView* data, Args&&... args);
};
```

`PackedArgs::Fill` uses `details::for_each` with `PackedArgsSetter` to write
arguments into the array (`function.h:305-307`). `Function::operator()`
(`function.h:614-622`) creates a stack-allocated `AnyView args_pack[kArraySize]`,
fills it via `PackedArgs::Fill`, then calls `CallPacked`. The
`kArraySize = max(kNumArgs, 1)` pattern avoids zero-length VLA.

### Function::FromExternC and InvokeExternC: static linking patterns

`FromExternC` (`function.h:392-401`) creates a `Function` from raw C function
pointers:

```cpp
static Function FromExternC(void* self, TVMFFISafeCallType safe_call,
                            void (*deleter)(void* self));
```

Two implementation classes handle the two cases:

- `ExternCFunctionObjNullHandleImpl` (`function.h:205-211`): when `self` and
  `deleter` are both null, wraps a simple function pointer.
- `ExternCFunctionObjImpl` (`function.h:216-237`): wraps a C-style closure
  with its own `SafeCall` that delegates to the stored `safe_call_`.

Both set `cpp_call = nullptr` since these are cross-DSO safe only.

`InvokeExternC` (`function.h:586-597`) directly calls an extern C symbol
without creating a `Function` object -- stack-allocated args, no heap
allocation:

```cpp
template <typename... Args>
TVM_FFI_INLINE static Any InvokeExternC(void* handle,
                                        TVMFFISafeCallType safe_call,
                                        Args&&... args) {
  const int kNumArgs = sizeof...(Args);
  const int kArraySize = kNumArgs > 0 ? kNumArgs : 1;
  AnyView args_pack[kArraySize];
  PackedArgs::Fill(args_pack, std::forward<Args>(args)...);
  Any result;
  TVM_FFI_CHECK_SAFE_CALL(
      safe_call(handle, reinterpret_cast<const TVMFFIAny*>(args_pack),
                kNumArgs, reinterpret_cast<TVMFFIAny*>(&result)));
  return result;
}
```

`TVM_FFI_DLL_EXPORT_TYPED_FUNC` (`function.h:946-959`) exports typed functions
as `__tvm_ffi_<ExportName>` symbols following the packed calling convention:

```cpp
extern "C" {
TVM_FFI_DLL_EXPORT int __tvm_ffi_##ExportName(
    void* self, const TVMFFIAny* args, int32_t num_args,
    TVMFFIAny* result) {
  TVM_FFI_SAFE_CALL_BEGIN();
  details::unpack_call<typename FuncInfo::RetType>(
      std::make_index_sequence<FuncInfo::num_args>{},
      &name, Function, args, num_args, result);
  TVM_FFI_SAFE_CALL_END();
}
}
```

### CallExpected: exception-free error handling

`Function::CallExpected<T>` (`function.h:660-692`) returns `Expected<T>`
instead of throwing:

```cpp
template <typename T = Any, typename... Args>
TVM_FFI_INLINE Expected<T> CallExpected(Args&&... args) const {
  // ... pack args ...
  int ret_code = func_obj->safe_call(func_obj, ..., kNumArgs, ...);
  if (ret_code == 0) {
    // try_cast result to T
  } else {
    return Unexpected(details::MoveFromSafeCallRaised());
  }
}
```

On success, the result is `try_cast` to `T`. On failure, the error is moved
from TLS into `Unexpected(Error)`. This is useful for callers that want to
handle errors without try-catch.

### Overload dispatch

The overload system (`overload.h`) supports C++ method overloading at the FFI
boundary, layered on three classes:

- `OverloadBase` (`overload.h:50-80`): abstract base with a `FnPtr` try-call
  interface and a `last_mismatch_index_` cache for fast error reporting.
- `TypedOverload<Callable>` (`overload.h:91-198`): concrete single-signature
  overload that uses `try_cast` per argument:

```cpp
bool TryCall(const AnyView* args, int32_t num_args, Any* rv) {
  if (num_args != kNumArgs) return false;
  CaptureTuple captures{};
  if (!TrySetAux(kSeq, captures, args)) return false;
  if constexpr (std::is_same_v<Ret, void>) {
    CallAux(kSeq, captures);
  } else {
    *rv = CallAux(kSeq, captures);
  }
  return true;
}
```

- `OverloadedFunction<Callable>` (`overload.h:207-259`): extends
  `TypedOverload`, manages additional overloads via a vector. The fast path
  (no overloads registered) calls `unpack_call` directly with zero overhead:

```cpp
void operator()(const AnyView* args, int32_t num_args, Any* rv) {
  if (overloads_.size() == 0) {
    return unpack_call<Ret>(kSeq, name_ptr_, f_, args, num_args, rv);
  }
  if (this->TryCall(args, num_args, rv)) return;
  for (const auto& [overload, fptr] : overloads_) {
    if (overload->num_args_ != num_args) continue;
    if (fptr(overload.get(), args, num_args, rv)) return;
  }
  this->HandleOverloadFailure(args, num_args);
}
```

`OverloadObjectDef` (`overload.h:276-498`) extends `ObjectDef` and manages
registration: on the first call to `RegisterMethod` for a given method name,
it creates an `OverloadedFunction` via `FromPackedInplace` and stores the
`OverloadBase*` in a `std::unordered_map<std::string, OverloadBase*>`. On
subsequent registrations of the same name, it calls `Register()` on the
existing overload.

### Global function registry

`GlobalFunctionTable` (`function.cc:51-142`) is a singleton storing all
registered global functions:

```cpp
class GlobalFunctionTable {
 public:
  class Entry : public Object, public TVMFFIMethodInfo {
    String name_data, doc_data, metadata_data;
    ffi::Function func_data;
  };

  void Update(const String& name, Function func, bool can_override);
  const Entry* Get(const String& name);

  static GlobalFunctionTable* Global() {
    static GlobalFunctionTable* inst = new GlobalFunctionTable();
    return inst;
  }

 private:
  Map<String, Any> table_;
};
```

The table is deliberately allocated via raw `new` and never freed
(`function.cc:131-137`) to avoid destruction-order issues with Python callbacks.
No mutex is used; the assumption is that updates happen during initialization
from the main thread (`function.cc:43-50`).

`TVMFFIFunctionCall` (`function.cc:191-204`) is the idiomatic C-level call
API. On non-MSVC platforms it performs a tail call; on MSVC it avoids tail call
optimization so the function symbol appears in the call frame for FFI boundary
detection:

```cpp
int TVMFFIFunctionCall(TVMFFIObjectHandle func, TVMFFIAny* args,
                       int32_t num_args, TVMFFIAny* result) {
  return reinterpret_cast<FunctionObj*>(func)->safe_call(
      func, args, num_args, result);
}
```

C++ API: `Function::GetGlobal`, `Function::GetGlobalRequired`,
`Function::SetGlobal`. Python API: `tvm_ffi.register_global_func`,
`tvm_ffi.get_global_func`. C++ registration via static init:
`reflection::GlobalDef().def(name, func, ...)` with the
`TVM_FFI_STATIC_INIT_BLOCK()` macro.

### Function metadata export

The compile-time flag `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` (default 0,
`function.h:32-34`) controls export of type schema JSON alongside DLL-exported
functions:

```cpp
#if TVM_FFI_DLL_EXPORT_INCLUDE_METADATA
#define TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, Function)              \
  TVM_FFI_DLL_EXPORT_TYPED_FUNC_IMPL_(ExportName, Function)             \
  extern "C" {                                                           \
  TVM_FFI_DLL_EXPORT int __tvm_ffi__metadata_##ExportName(               \
      void* self, const TVMFFIAny* args, int32_t num_args,               \
      TVMFFIAny* result) {                                               \
    /* returns JSON: {"type_schema": <escaped schema string>} */         \
  }                                                                      \
  }
```

`TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC` (`function.h:1055-1065`) exports a
`__tvm_ffi__doc_<name>` symbol containing docstrings. Both macros use
`TVMFFIStringFromByteArray` to allocate metadata strings in `libtvm_ffi`
rather than the extension module, preventing use-after-unload crashes.

`GlobalFunctionTable::Entry` stores `metadata_data` (JSON string with
`type_schema`), queryable via `ffi.GetGlobalFuncMetadata`.

### Python callable auto-conversion

Any Python `Callable` is automatically converted to `tvm_ffi.Function` when
passed as an FFI argument. The conversion path runs through the Cython layer:

1. `TVMFFIPyArgSetterCallable_` (`function.pxi`) calls
   `_convert_to_ffi_func_handle` which increments the Python function's
   refcount and calls `TVMFFIFunctionCreate` with `tvm_ffi_callback` as
   `safe_call` and `TVMFFIPyObjectDeleter` as the deleter.

2. `tvm_ffi_callback` (`function.pxi`) is the bridge function: it acquires
   the GIL, unpacks `TVMFFIAny[]` to Python objects, calls the Python function,
   converts the result back, and returns 0 on success or -1 on error (with the
   error stored in TLS via `set_last_ffi_error`).

3. `TVMFFIPyObjectDeleter` (`tvm_ffi_python_helpers.h:732-735`) acquires the
   GIL before calling `Py_DecRef`, and handles free-threaded Python via
   `TVMFFIPyWithGILIfNotFreeThreaded`.

`Function.__init__` (`ecc7471`) also accepts any Python callable and wraps it.
GIL release during C++ FFI calls is controlled by the `_RELEASE_GIL_BY_DEFAULT`
environment variable (default: 1).

### Python arg dispatch caching

`TVMFFIPyCallManager` (`tvm_ffi_python_helpers.h:254-484`) is a thread-local
singleton managing argument dispatch:

```cpp
class TVMFFIPyCallManager {
 public:
  static TVMFFIPyCallManager* ThreadLocal() {
    static thread_local TVMFFIPyCallManager inst;
    return &inst;
  }

  TVM_FFI_INLINE int SetArgument(TVMFFIPyArgSetterFactory setter_factory,
                                 TVMFFIPyCallContext* ctx,
                                 PyObject* py_arg, TVMFFIAny* out) {
    PyTypeObject* py_type = Py_TYPE(py_arg);
    out->type_index = kTVMFFINone;
    out->zero_padding = 0;
    out->v_int64 = 0;
    auto it = dispatch_map_.find(py_type);
    if (it != dispatch_map_.end()) {
      return it->second(ctx, py_arg, out);  // cached fast path
    } else {
      TVMFFIPyArgSetter setter;
      if (setter_factory(py_arg, &setter) != 0) return -1;
      dispatch_map_.emplace(py_type, setter);
      return setter(ctx, py_arg, out);
    }
  }

 private:
  std::unordered_map<PyTypeObject*, TVMFFIPyArgSetter> dispatch_map_;
  TVMFFIPyCallStack call_stack_;
};
```

`TVMFFIPyArgSetter` (`tvm_ffi_python_helpers.h:162-189`) is a struct with a
function pointer and optional `DLPackExchangeAPI*`. On first encounter of a
Python type, the factory function checks the type hierarchy in priority order
(None, Tensor, Object types, DLPack, bool, int, float, str, bytes, tuple,
list, dict, callable, etc.). Subsequent calls use the cached setter directly.

Key performance properties:

- Default dispatch capacity: 32 entries (pre-reserved,
  `tvm_ffi_python_helpers.h:476-477`).
- `TVMFFIPyCallStack` uses a 4KB pre-allocated argument stack for cache
  locality, spilling to heap for large argument counts
  (`tvm_ffi_python_helpers.h:66-72`).
- Each `TVMFFIPyCallContext` co-locates `packed_args` and temporary object
  arrays for cache locality with a "one temp per argument" budget
  (`tvm_ffi_python_helpers.h:119-122`).
- `TVMFFIPyFuncCall` optionally releases the GIL around
  `TVMFFIFunctionCall` (`tvm_ffi_python_helpers.h:307-313`).
- Stream context auto-detection: if any tensor arg has a non-CPU device, the
  stream is detected and set via `TVMFFIEnvSetStream`, then restored after
  the call (`tvm_ffi_python_helpers.h:291-323`).

### MLIR bridge: Function.__from_mlir_packed_safe_call__

`TVMFFIPyMLIRPackedSafeCall` (`tvm_ffi_python_helpers.h:644-673`) adapts MLIR
execution engine functions (which use a `void(void**)` signature) to the
`TVMFFISafeCallType` convention:

```cpp
class TVMFFIPyMLIRPackedSafeCall {
 public:
  TVMFFIPyMLIRPackedSafeCall(void (*mlir_packed_safe_call)(void**),
                             PyObject* keep_alive_object);
  static int Invoke(void* func, const TVMFFIAny* args,
                    int32_t num_args, TVMFFIAny* rv) {
    auto* self = reinterpret_cast<TVMFFIPyMLIRPackedSafeCall*>(func);
    int ret_code = 0;
    void* handle = nullptr;
    void* mlir_args[] = {&handle, const_cast<TVMFFIAny**>(&args),
                         &num_args, &rv, &ret_code};
    (*self->mlir_packed_safe_call_)(mlir_args);
    return ret_code;
  }
  static void Deleter(void* self);
};
```

The adapter unpacks the `void**` indirection:
`{&handle, &args, &num_args, &rv, &ret_code}`. The Python API is
`Function.__from_mlir_packed_safe_call__(mlir_packed_symbol, keep_alive_object=...)`.
The `keep_alive_object` (typically the MLIR execution engine) is `Py_IncRef`'d
in the constructor and `Py_DecRef`'d in the destructor
(`tvm_ffi_python_helpers.h:648-657`).

This adapter lives in the Python helper layer, not in the core C++ API. As the
source comments note (`tvm_ffi_python_helpers.h:627-642`), it may become
unnecessary if MLIR execution engines gain native extern C function pointer
support.

### Performance characteristics

- **Python to C++**: microsecond-level overhead, comparable to eager mode
  dispatch. The thread-local dispatch cache and 4KB pre-allocated call stack
  minimize allocation overhead.
- **C++ to C++ (same DSO)**: tens of nanoseconds via the `cpp_call` fast path,
  avoiding exception catching overhead.
- **InvokeExternC**: near-zero overhead -- stack-allocated args, no heap
  allocation, no `Function` object creation.
- **LTO potential**: when both caller and callee are statically linked into a
  single binary, the callee can be inlined and stack args passed in registers.
  The `func_module.rst` documentation describes this as "theoretically
  possible" but "less necessary in practice."
- **Branchless dispatch**: the `cpp_call` vs fallback select uses a conditional
  expression (`function.h:128-129`) for branchless code generation.
- **GIL release**: `_RELEASE_GIL_BY_DEFAULT=1` allows C++ execution without
  holding the GIL.

## APIs

### C API

```c
// Canonical calling convention (include/tvm/ffi/c_api.h)
typedef int (*TVMFFISafeCallType)(void* handle, const TVMFFIAny* args,
                                  int32_t num_args, TVMFFIAny* result);

// Function lifecycle
int TVMFFIFunctionCreate(void* self, TVMFFISafeCallType safe_call,
                         void (*deleter)(void* self),
                         TVMFFIObjectHandle* out);
int TVMFFIFunctionCall(TVMFFIObjectHandle func, TVMFFIAny* args,
                       int32_t num_args, TVMFFIAny* result);

// Global registry
int TVMFFIFunctionSetGlobal(const TVMFFIByteArray* name,
                            TVMFFIObjectHandle f, int override);
int TVMFFIFunctionGetGlobal(const TVMFFIByteArray* name,
                            TVMFFIObjectHandle* out);
int TVMFFIFunctionSetGlobalFromMethodInfo(const TVMFFIMethodInfo* info,
                                          int override);
```

### C++ API

```cpp
// Core classes (include/tvm/ffi/function.h)
class FunctionObj : public Object, public TVMFFIFunctionCell {
  void CallPacked(const AnyView* args, int32_t num_args, Any* result) const;
};

class Function : public ObjectRef {
  // Construction
  static Function FromPacked(TCallable&& packed_call);
  static Function FromTyped(TCallable&& callable);
  static Function FromExternC(void* self, TVMFFISafeCallType safe_call,
                              void (*deleter)(void*));
  template <typename... Args>
  static Any InvokeExternC(void* handle, TVMFFISafeCallType safe_call,
                           Args&&... args);

  // Invocation
  template <typename... Args>
  Any operator()(Args&&... args) const;
  template <typename T = Any, typename... Args>
  Expected<T> CallExpected(Args&&... args) const;

  // Global registry
  static std::optional<Function> GetGlobal(std::string_view name);
  static Function GetGlobalRequired(std::string_view name);
  static void SetGlobal(std::string_view name, Function func,
                        bool override = false);
};

template <typename R, typename... Args>
class TypedFunction<R(Args...)> {
  R operator()(Args... args) const;
  operator Function() const;
  static std::string TypeSchema();
};
```

### Python API

```python
# Function class (tvm_ffi.core.Function)
class Function:
    def __init__(self, handle_or_callable): ...
    def __call__(self, *args) -> Any: ...

    @staticmethod
    def __from_mlir_packed_safe_call__(
        mlir_packed_symbol: int,
        *,
        keep_alive_object: object | None = None,
    ) -> Function: ...

# Global registry (tvm_ffi.registry)
def register_global_func(func_name, f=None, override=False): ...
def get_global_func(name, allow_missing=False): ...
def remove_global_func(name): ...
```

## Implementation

| File | Role |
|------|------|
| `include/tvm/ffi/c_api.h` | C ABI: `TVMFFISafeCallType`, `TVMFFIFunctionCell`, `TVMFFIAny`, all C API functions |
| `include/tvm/ffi/function.h` | C++ API: `FunctionObj`, `Function`, `TypedFunction`, `PackedArgs`, safe call macros, DLL export macros |
| `include/tvm/ffi/function_details.h` | Template internals: `FunctionInfo`, `unpack_call`, `ArgValueWithContext`, `FuncFunctorImpl` |
| `include/tvm/ffi/expected.h` | `Expected<T>` / `Unexpected` for exception-free error handling |
| `include/tvm/ffi/reflection/overload.h` | `OverloadBase`, `TypedOverload`, `OverloadedFunction`, `OverloadObjectDef` |
| `include/tvm/ffi/reflection/registry.h` | `GlobalDef`, `ObjectDef` |
| `src/ffi/function.cc` | `GlobalFunctionTable`, C API implementations (`TVMFFIFunctionCall`, `TVMFFIFunctionCreate`, etc.) |
| `python/tvm_ffi/cython/function.pxi` | Python `Function` class, `tvm_ffi_callback`, arg setters, MLIR bridge |
| `python/tvm_ffi/cython/tvm_ffi_python_helpers.h` | `TVMFFIPyCallManager`, `TVMFFIPyArgSetter`, `TVMFFIPyMLIRPackedSafeCall`, `TVMFFIPyCallStack` |
| `python/tvm_ffi/cython/base.pxi` | Cython C API bindings |
| `python/tvm_ffi/registry.py` | Python `register_global_func`, `get_global_func` |
| `docs/concepts/func_module.rst` | User-facing documentation: calling convention, module system |
| `docs/get_started/stable_c_abi.rst` | Stable C ABI guide with C code examples |

## History

- **38d2cda** 2025-09-11 -- Refactored Python FFI call mechanism, introducing thread-local `TVMFFIPyCallManager` with `PyTypeObject*` dispatch cache and 4KB pre-allocated call stack for performance
- **4fe8b2b** 2025-09-29 -- Clarified Function ABI in C++: formalized the dual `safe_call`/`cpp_call` pointer design in `TVMFFIFunctionCell` and `FunctionObj`
- **9186b44** 2025-10-14 -- Introduced `Function::InvokeExternC` for zero-allocation direct invocation of extern C symbols
- **369ff23** 2025-10-26 -- Added Stable C ABI documentation covering the `TVMFFISafeCallType` convention and error propagation
- **f6303b2** 2025-10-11 -- Enabled FFI function creation from MLIR packed function pointers via `TVMFFIPyMLIRPackedSafeCall` adapter
- **ac7bf68** 2025-11-20 -- Added `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` flag for embedding type schema JSON and docstrings alongside exported functions
- **dcacb98** 2025-12-02 -- Moved metadata string allocation to `libtvm_ffi` via `TVMFFIStringFromByteArray` for cross-module safety
- **84c5bdb** 2025-12-23 -- Added dynamic-style overload dispatch: `OverloadBase`, `TypedOverload`, `OverloadedFunction`, `OverloadObjectDef`
- **f173692** 2026-01-10 -- Added Function, Exception, and Module documentation covering calling convention and performance characteristics
- **ecc7471** 2026-02-21 -- Added `tvm_ffi.Function.__init__` accepting Python callables for direct construction

## Related

- `.repo-knowledge/design/001-type-erased-value-system.md` -- `Any`/`AnyView` are the argument/return types for the packed convention
- `.repo-knowledge/design/003-c-abi-stability.md` -- `TVMFFISafeCallType` is part of the stable C ABI surface
- `.repo-knowledge/design/004-reflection-system.md` -- `ObjectDef` and `GlobalDef` use `Function::FromTyped` for method registration
- `.repo-knowledge/design/007-module-system.md` -- Module function lookup uses the `__tvm_ffi_<name>` symbol convention with the packed calling convention
- `.repo-knowledge/design/009-tensor-and-dlpack.md` -- DLPack tensors are the primary way tensors flow through the packed function interface
- `.repo-knowledge/design/012-error-handling.md` -- Error handling architecture, safe call macros, `Expected<T>`
