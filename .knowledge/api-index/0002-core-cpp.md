---
scope: "core-cpp"
---
# API Index: Core C++ API

**Scope**: C++ types, classes, functions, and macros in `tvm::ffi` namespace (excluding containers, which have their own index).
**Design docs**: [0002-any-value-system.md](../designs/0002-any-value-system.md), [0003-object-system.md](../designs/0003-object-system.md), [0004-function-system.md](../designs/0004-function-system.md), [0005-type-traits.md](../designs/0005-type-traits.md), [0006-error-handling.md](../designs/0006-error-handling.md), [0007-memory-allocation.md](../designs/0007-memory-allocation.md)
**ADRs**: [0001-unified-any-value.md](../ADRs/0001-unified-any-value.md), [0002-tls-error-propagation.md](../ADRs/0002-tls-error-propagation.md), [0004-type-index-layout.md](../ADRs/0004-type-index-layout.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `AnyView` | class | `TVMFFIAny data_`; `reset()`, `swap(AnyView&)`, `type_index() -> int32_t`, `as<T>() -> optional<T>` (strict), `try_cast<T>() -> optional<T>` (coercing), `cast<T>() -> T` (coercing+throw), `GetTypeKey() -> string` | Non-owning type-erased view of a value |
| `Any` | class | `TVMFFIAny data_`; `reset()`, `swap(Any&)`, `type_index() -> int32_t`, `as<T>() -> optional<T>` (strict), `as<T>() &&` (strict rvalue), `try_cast<T>() -> optional<T>` (coercing), `cast<T>() -> T`, `operator AnyView()` | Owning type-erased value (IncRef/DecRef for objects) |
| `Object` | class | `TVMFFIObject header_`; `IsInstance<T>() -> bool`, `type_index() -> int32_t`, `GetTypeKey() -> string`, `use_count() -> int32_t`, `unique() -> bool` | Base class for all heap-allocated FFI objects |
| `ObjectPtr<T>` | class template | `Object* data_`; `get() -> T*`, `reset()`, `use_count() -> int`, `unique() -> bool`, `swap(ObjectPtr&)` | Intrusive smart pointer with atomic refcounting |
| `ObjectRef` | class | `ObjectPtr<Object> data_`; `defined() -> bool`, `get() -> const Object*`, `same_as(ObjectRef) -> bool`, `as<ObjectType>() -> const ObjectType*`, `as<ObjectRefType>() -> optional<ObjectRefType>`, `type_index() -> int32_t` | Handle wrapper for objects |
| `WeakObjectPtr<T>` | class template | `Object* data_`; `lock() -> ObjectPtr<T>` (CAS-based promotion), `expired() -> bool`, `reset()`, `use_count() -> int`, `swap(WeakObjectPtr&)` | Weak intrusive smart pointer (mirrors std::weak_ptr) |
| `FunctionObj` | class | `void* cpp_call` (via TVMFFIFunctionCell), `TVMFFISafeCallType safe_call` (via TVMFFIFunctionCell); `CallPacked(const AnyView*, int32_t, Any*)`; `static _type_index = 68`, `static _type_key = "ffi.Function"` | Callable object with dual C++/C ABI call paths; `cpp_call` may be NULL |
| `Function` | class | inherits `ObjectRef`; `operator()(Args...) -> Any`, `CallPacked(...)`, `CallExpected<T>(Args...) -> Expected<T>` (0a9d4b6), `FromPacked(callable)$`, `FromTyped(callable)$`, `FromExternC(...)$`, `InvokeExternC(handle, safe_call, args...)$ -> Any` (9186b44), `GetGlobal(name)$`, `GetGlobalRequired(name)$`, `SetGlobal(name, func)$`, `ListGlobalNames()$`, `RemoveGlobal(name)$` | Type-erased function handle with global registry |
| `TypedFunction<R(Args...)>` | class template | `Function packed_`; `operator()(Args...) -> R`, `packed() -> const Function&` | Compile-time typed function wrapper |
| `PackedArgs` | class | `const AnyView* data_; int32_t size_`; `operator[](int) -> AnyView`, `Slice(begin, end) -> PackedArgs`, `Fill<Args>(AnyView*, Args&&...)$` | View of packed function arguments |
| `ErrorObj` | class | inherits `Object + TVMFFIErrorCell`; `static _type_index = 67`; destructor DecRefs `cause_chain`/`extra_context` | Error data object; TVMFFIErrorCell extended with `cause_chain`, `extra_context` fields (0d157dc) |
| `Error` | class | inherits `ObjectRef + std::exception`; `kind() -> string`, `message() -> string`, `traceback() -> string`, `cause_chain() -> optional<Error>` (0d157dc), `extra_context() -> optional<ObjectRef>` (0d157dc), `UpdateTraceback(bytearray*)`, `what() -> const char*`; constructor overload: `Error(kind, message, backtrace, optional<Error> cause_chain, optional<ObjectRef> extra_context)` | Error handle with std::exception and optional cause chaining |
| `EnvErrorAlreadySet` | function (was struct, removed in b1611e0) | `inline Error EnvErrorAlreadySet()` returns `Error("EnvErrorAlreadySet", "", "")` | Factory for frontend-error-already-set signal; no longer a separate exception type |
| `Expected<T>` | class template (0a9d4b6) | `Any data_`; `is_ok() -> bool`, `is_err() -> bool`, `has_value() -> bool`, `value() -> T`, `error() -> Error`, `value_or(U) -> T`; `static_assert(!is_same_v<T, Error>)` | Exception-free result type holding either T or Error in an Any. See [0006-error-handling](../designs/0006-error-handling.md) |
| `Unexpected<E>` | class template (0a9d4b6) | `explicit Unexpected(E error)`; `error() -> E`; CTAD guide `Unexpected(E) -> Unexpected<E>` | Explicit error wrapper for Expected construction |
| `String` | class | standalone value type (not ObjectRef); `details::BytesBaseCell data_`; `data()`, `c_str()`, `size()`, `compare()`; stores inline (kTVMFFISmallStr) or heap (kTVMFFIStr) | Immutable string with small string optimization |
| `details::StringObj` | class | inherits `Object + TVMFFIByteArray (via details::BytesObjBase)`; in `details` namespace | String data object (heap-allocated, for strings > 7 bytes) |
| `Bytes` | class | standalone value type (not ObjectRef); `details::BytesBaseCell data_`; `data()`, `size()`, `memequal()$`, `memncmp()$`; stores inline (kTVMFFISmallBytes) or heap (kTVMFFIBytes) | Raw byte container with small buffer optimization |
| `details::BytesObj` | class | inherits `Object + TVMFFIByteArray (via details::BytesObjBase)`; in `details` namespace | Bytes data object (heap-allocated, for bytes > 7 bytes) |
| `details::BytesBaseCell` | class | `TVMFFIAny data_`; `data() -> const char*`, `size() -> size_t`, `MoveToAny(TVMFFIAny*)`, `CopyToTVMFFIAny() -> TVMFFIAny`, `CopyFromAnyView(TVMFFIAny*)$`, `MoveFromAny(TVMFFIAny*)$` | Internal dual-storage cell dispatching between inline and heap string representations |
| `Optional<T>` | class template | `ObjectPtr<Object> data_` or `std::optional<T>`; `value() -> T`, `value_or(T) -> T` | FFI-compatible optional |
| `Variant<V...>` | class template | inherits `ObjectRef`; `is<T>() -> bool`, `get<T>() -> T` | Compile-time union of ObjectRef types |
| `TypeTraits<T>` | struct template | `CopyToAnyView`, `MoveToAny`, `CheckAnyStrict`, `CopyFromAnyViewAfterCheck`, `MoveFromAnyAfterCheck`, `TryCastFromAnyView`, `TypeStr` | Type conversion protocol for Any/AnyView |
| `TypeTraitsBase` | struct | `convert_enabled = true`, `storage_enabled = true`, `GetMismatchTypeInfo(TVMFFIAny*) -> string` | Default base for TypeTraits specializations |
| `TypeTraits<Expected<T>>` | struct template specialization (0a9d4b6) | `CheckAnyStrict`: true if T or Error; `TypeSchema`: `{"type":"Expected","args":[<T>,{"type":"ffi.Error"}]}` | Enables Expected<T> to participate in Any type system |
| `ObjectRefTypeTraitsBase<T>` | struct template | Implements all 7 TypeTraits methods for ObjectRef subtypes | Reusable base for object type traits |
| `FallbackOnlyTraitsBase<T, FBs...>` | struct template | `TryConvertFromAnyView` tries fallback chain | Base for types with coercion chains |
| `ObjectRefWithFallbackTraitsBase<T, FBs...>` | struct template | Combines ObjectRef check + fallback chain | Base for ObjectRef types with fallbacks (note: String/Bytes no longer use this) |
| `StaticTypeKey` | struct | `kTVMFFIAny`, `kTVMFFINone`, `kTVMFFIBool`, `kTVMFFIInt`, `kTVMFFIFloat`, `kTVMFFIDLTensorPtr = "DLTensor*"`, etc. | String constants for static type keys |
| `is_integeral_enum_v<T>` | variable template | `template<typename T, bool = std::is_enum_v<T>> constexpr bool is_integeral_enum_v = false;` | Two-phase SFINAE guard for enum TypeTraits (GCC 8.x fix) |
| `FunctionInfo<F>` | struct template | Primary: dispatches to `FunctionInfoHelper<decltype(&T::operator())>`; Specializations: `R(Args...)`, `R(*)(Args...)`, `R(&)(Args...)` (a23c5a0), `R(Class::*)(Args...)` for Object/ObjectRef classes | Compile-time callable introspection for typed-to-packed conversion |
| `details::TypeSchemaImpl<T>` | struct template | `static std::string v()` | JSON type schema generation; primary delegates to `TypeTraits<U>::TypeSchema()` |
| `details::TypeSchema<T>` | using alias | `= TypeSchemaImpl<remove_const_t<remove_reference_t<T>>>` | Convenience alias for TypeSchemaImpl |
| `EscapeString` | function | `(const String& value) -> String` | JSON-escape and double-quote a string |
| `UnsafeInit` | struct | (empty tag type) | Tag for null-initializing ObjectRef subtypes; every ObjectRef must provide a constructor taking `UnsafeInit` |
| `ObjectUnsafe::ObjectRefFromObjectPtr<T>` | static template function | `(const ObjectPtr<Object>&) -> T` and `(ObjectPtr<Object>&&) -> T` | Canonical factory for constructing ObjectRef from raw ObjectPtr via UnsafeInit |
| `make_object<T>(args...)` | function template | `-> ObjectPtr<T>` | Allocate object via details::SimpleObjAllocator |
| `make_inplace_array_object<A, E>(n, args...)` | function template | `-> ObjectPtr<A>` | Allocate object + trailing array |
| `details::SimpleObjAllocator` | class | `Handler<T>`, `ArrayHandler<A, E>` | Default allocator using new/delete (moved to `tvm::ffi::details` namespace) |
| `ObjAllocatorBase<Derived>` | class template (CRTP) | `make_object<T>(args...)`, `make_inplace_array<A, E>(n, args...)` | Allocator base with header init |
| `details::AlignedAlloc<align>(size)` | function template | `-> void*` | Platform-aware aligned allocation (replaces StorageType new/delete) |
| `details::AlignedFree(data)` | function | `(void*) -> void` | Platform-aware aligned free |
| `details::IsObjectInstance<TargetType>` | function template | `(int32_t object_type_index) -> bool` | Three-tier IsInstance check |
| `details::ObjectUnsafe` | struct | `GetHeader(Object*)`, `ObjectPtrFromOwned<T>`, `IncRefObjectHandle`, `DecRefObjectHandle`, etc. | Low-level object manipulation helpers |
| `details::ErrorBuilder` | class | `stream() -> ostringstream&`, `~ErrorBuilder() [[noreturn]]` | Stream-style error construction |
| `TypeKeyToIndex` | function | `(string_view type_key) -> int32_t` | Helper wrapping TVMFFITypeKeyToIndex |
| `TypeIndexToTypeKey` | function | `(int32_t type_index) -> string` | Helper wrapping TVMFFIGetTypeInfo |
| `Function::FromPackedInplace<TCallable>` | static method (84c5bdb) | `(Args&&...) -> tuple<Function, TCallable*>` | In-place construct callable inside FunctionObj, return (Function, pointer-to-embedded-callable). Enables post-construction mutation for overload dispatch. |
| `<tvm/ffi/tvm_ffi.h>` | umbrella header (8caa0cb) | Includes all core TVM-FFI C++ headers (excluding `tvm/ffi/extra/`) | Single-include entry point for extension writers |

## C++ API: Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `TVM_FFI_DECLARE_OBJECT_INFO(Key, T, Parent)` | macro | Sets `_type_key = Key`, generates `_type_depth`, `_GetOrAllocRuntimeTypeIndex()`, `RuntimeTypeIndex()`, `_type_index` | Declare non-final object type (was `DECLARE_BASE_OBJECT_INFO`) |
| `TVM_FFI_DECLARE_OBJECT_INFO_FINAL(Key, T, Parent)` | macro | Sets `_type_child_slots=0`, `_type_final=true`, `_type_key = Key`, then includes OBJECT_INFO logic | Declare final (leaf) object type (was `DECLARE_FINAL_OBJECT_INFO`) |
| `TVM_FFI_DECLARE_OBJECT_INFO_STATIC(Key, T, Parent)` | macro | Sets `_type_key = Key`, uses compile-time `_type_index` for RuntimeTypeIndex | Declare object with static type index (was `DECLARE_STATIC_OBJECT_INFO`) |
| `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(T, Parent, Obj)` | macro | `ObjectPtr<Obj>` constructor + `UnsafeInit` constructor, `__PtrType = conditional_t<Obj::_type_mutable, ...>`, `_type_is_nullable=true` | Define nullable ObjectRef (was `DEFINE_OBJECT_REF_METHODS`) |
| `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(T, Parent, Obj)` | macro | `UnsafeInit` constructor only, `__PtrType = conditional_t<Obj::_type_mutable, ...>`, `_type_is_nullable=false` | Define non-nullable ObjectRef (was `DEFINE_NOTNULLABLE_OBJECT_REF_METHODS`; mutable variants absorbed via `_type_mutable`) |
| `TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, Function)` | macro | Creates `extern "C"` symbol `__tvm_ffi_##ExportName` with `TVMFFISafeCallType` signature | Export typed function from shared library with `__tvm_ffi_` prefix |
| `TVM_FFI_DLL_EXPORT` | macro | Always-export visibility annotation | DLL export (unlike `TVM_FFI_DLL` which is dllimport on consumer) |
| `TVM_FFI_THROW(ErrorKind)` | macro | Creates `ErrorBuilder` with traceback | Stream-style error throw |
| `TVM_FFI_LOG_AND_THROW(ErrorKind)` | macro | Like THROW but logs to stderr first | Error throw with logging |
| `TVM_FFI_SAFE_CALL_BEGIN()` | macro | Opens try block | Begin C ABI exception boundary |
| `TVM_FFI_SAFE_CALL_END()` | macro | Catch hierarchy: Error, std::exception (b1611e0: EnvErrorAlreadySet catch removed) | End C ABI exception boundary |
| `TVM_FFI_CHECK_SAFE_CALL(func)` | macro | Checks `ret_code != 0`, throws `MoveFromSafeCallRaised()` (b1611e0: -2 check removed) | Error-code-to-exception conversion |
| `TVM_FFI_CHECK(cond, ErrorKind)` | macro (35cbc32) | `if (!(cond)) TVM_FFI_THROW(ErrorKind) << "Check failed: ..."` | Tier 1: condition check with user-specified error kind |
| `TVM_FFI_CHECK_LT/GT/LE/GE/EQ/NE(x, y, ErrorKind)` | macros (35cbc32) | `TVM_FFI_CHECK_BINARY_OP(name, op, x, y, ErrorKind)` | Tier 1: binary comparison checks with custom error kind |
| `TVM_FFI_CHECK_NOTNULL(x, ErrorKind)` | macro (35cbc32) | Asserts non-null, returns `x` | Tier 1: null-pointer check with custom error kind |
| `TVM_FFI_ICHECK(x)` | macro | `TVM_FFI_CHECK(x, InternalError)` | Tier 2: thin wrapper, always InternalError |
| `TVM_FFI_ICHECK_LT/GT/LE/GE/EQ/NE(x, y)` | macros | `TVM_FFI_CHECK_*(x, y, InternalError)` | Tier 2: binary comparison with InternalError |
| `TVM_FFI_ICHECK_NOTNULL(ptr)` | macro | `TVM_FFI_CHECK_NOTNULL(ptr, InternalError)` | Tier 2: null check with InternalError |
| `TVM_FFI_DCHECK(x)` | macro (35cbc32) | `TVM_FFI_ICHECK(x)` (debug) / `while (false) ...` (NDEBUG) | Tier 3: debug-only condition check |
| `TVM_FFI_DCHECK_LT/GT/LE/GE/EQ/NE(x, y)` | macros (35cbc32) | `TVM_FFI_ICHECK_*(x, y)` (debug) / dead code (NDEBUG) | Tier 3: debug-only binary comparisons |
| `TVM_FFI_DCHECK_NOTNULL(x)` | macro (35cbc32) | `TVM_FFI_ICHECK_NOTNULL(x)` (debug) / `(x)` (NDEBUG) | Tier 3: debug-only null check; returns x in all modes |
| `TVM_FFI_CHECK_BINARY_OP(name, op, x, y, ErrorKind)` | internal macro (35cbc32) | Formats "Check failed: (x op y) ..." | Internal helper for binary CHECK macros |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | — | Python bindings not in scope for this commit |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | — | Rust bindings not in scope for this commit |
