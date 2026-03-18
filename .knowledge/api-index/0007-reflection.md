---
scope: "reflection"
---
# API Index: Reflection System

**Scope**: C++ reflection registration API (ObjectDef, GlobalDef, TypeAttrDef) and runtime accessors (FieldGetter, FieldSetter, ForEachFieldInfo).
**Design docs**: [0008-reflection.md](../designs/0008-reflection.md)
**ADRs**: [0005-reflection-driven-structural-equality.md](../ADRs/0005-reflection-driven-structural-equality.md)

## C++ API: Types, Methods, Functions, Macros

### Registration (reflection/registry.h)
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `ReflectionDefBase` | class | `FieldGetter<T>()`, `FieldSetter<T>()`, `GetMethod()`, `ObjectCreatorDefault<T>()`, `ApplyFieldInfoTrait()`, `ApplyMethodInfoTrait()` | Base class with shared field/method registration utilities. Note: `GetMethod` no longer has `<Class>` template parameter |
| `ObjectCreator` | class | `ObjectCreator(type_key)`, `ObjectCreator(type_info)`, `Any operator()(Map<String, Any>)` | Reflection-based object construction from named field map (in `reflection/creator.h`) |
| `ObjectDef<Class>` | class | `def_ro(name, field_ptr, extra...)`, `def_rw(name, field_ptr, extra...)`, `def_(name, func, extra...)`, `def_static(name, func, extra...)`, `def(init<Args...>(), extra...)` | Builder for registering object reflection (fields, methods, metadata). `def(init<>())` registers `__ffi_init__` (fc2630f). Auto-derives type_index/key from Class |
| `refl::init<Args...>` | tag struct | `init<int64_t, int64_t>()` | Tag type for constructor registration on ObjectDef. Object type T deduced from ObjectDef<T>. Replaces old free-function `refl::init<T, Args...>` (fc2630f) |
| `GlobalDef` | class | `def_(name, func, extra...)`, `def_packed(name, func, extra...)`, `def_method(name, func, extra...)` | Builder for registering global functions (replaces TVM_FFI_REGISTER_GLOBAL) |
| `TypeAttrDef<Class>` | class | `def_(name, func) -> TypeAttrDef&`, `attr(name, value) -> TypeAttrDef&` | Builder for registering per-type attributes in named columns |
| `InfoTrait` | class | `Apply(FieldInfoBuilder*)`, `Apply(MethodInfoBuilder*)` | Base trait for custom field/method metadata (renamed from `FieldInfoTrait` in 28fe3cc) |
| `Metadata` | class | `Metadata(initializer_list<pair<String, Any>>)`, `Apply(FieldInfoBuilder*)`, `Apply(MethodInfoBuilder*)`, `ToJSON(vector)` | User-supplied key-value metadata for fields, methods, global funcs. Values: int, bool, String |
| `FieldInfoBuilder` | struct | extends `TVMFFIFieldInfo` + `metadata_: vector<pair<String, Any>>` | Builder intermediary for field registration with metadata |
| `MethodInfoBuilder` | struct | extends `TVMFFIMethodInfo` + `metadata_: vector<pair<String, Any>>` | Builder intermediary for method/global func registration with metadata |
| `DefaultValue` | class | `Apply(FieldInfoBuilder*)` | Trait to set a field's static default value during registration |
| `DefaultFactory` | class | `DefaultFactory(Function factory)`, `Apply(FieldInfoBuilder*)` | Trait for mutable defaults; factory called per object creation (5e564cd) |
| `SetFieldToDefault` | function | `void SetFieldToDefault(const TVMFFIFieldInfo*, void*)` | Centralized helper: calls factory or copies static default (5e564cd) |
| `AttachFieldFlag` | class | `SEqHashDef() -> AttachFieldFlag`, `SEqHashIgnore() -> AttachFieldFlag` | Trait to attach field-level flags |
| `ffi.DeepCopy` | FFI function | `Any DeepCopy(const Any&)` | Memoized deep copy of FFI object graph; shared refs preserved, cycles handled (c73d61a) |
| `AutoRegisterCopy` | (internal) | called in `ObjectDef<T>()` constructor | Auto-registers `__ffi_shallow_copy__` for copy-constructible types (c73d61a) |
| `GetFieldByteOffsetToObject<Class, T>(field_ptr)` | function | `int64_t GetFieldByteOffsetToObject(T Class::*field_ptr)` | Compute byte offset from Object header to a class field |
| `OverloadObjectDef<Class>` | class | `def_ro(name, field_ptr, extra...)`, `def_rw(name, field_ptr, extra...)`, `def_(name, func, extra...)`, `def_static(name, func, extra...)`, `def(init<Args...>(), extra...)` | Overload-aware reflection builder. Same method name can be registered multiple times with different signatures; runtime dispatch by arg count/type (84c5bdbc) |
| `OverloadBase` | class | `Register(UniquePtr<OverloadBase>)`, `GetTryCallPtr()`, `GetMismatchMessage(os, args, num_args)` | Abstract base for one overload entry in a dispatch chain (84c5bdbc) |
| `TypedOverload<Callable>` | class | `TryCall(args, num_args, rv) -> bool` | Concrete overload entry using optional-based argument capture (84c5bdbc) |
| `OverloadedFunction<Callable>` | class | `operator()(args, num_args, rv)`, `Register(UniquePtr<OverloadBase>)` | Primary overload that owns additional overload entries; linear-scan dispatch (84c5bdbc) |
| `EnsureTypeAttrColumn(name)` | function | `void EnsureTypeAttrColumn(std::string_view name)` | Pre-create a TypeAttr column (idempotent) |
| `EscapeString(value)` | function (string.h) | `String EscapeString(const String& value)` | JSON-escape a string (double-quoted). Used by `Metadata::ToJSON` (28fe3cc) |
| `TVM_FFI_STATIC_INIT_BLOCK()` | macro | GCC/Clang: `__attribute__((constructor)) static void f() { Body }`. Others: static-variable + lambda fallback. | General-purpose static initialization. New function-body syntax: `TVM_FFI_STATIC_INIT_BLOCK() { Body }` (7b813f8) |

### Runtime Access (reflection/accessor.h)
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `GetFieldInfo(type_key, field_name)` | function | `const TVMFFIFieldInfo* GetFieldInfo(std::string_view, const char*)` | Look up a field by type key and name |
| `GetMethodInfo(type_key, method_name)` | function | `const TVMFFIMethodInfo* GetMethodInfo(std::string_view, const char*)` | Look up a method by type key and name |
| `GetMethod(type_key, method_name)` | function | `Function GetMethod(std::string_view, const char*)` | Get a method's Function handle |
| `FieldGetter` | class | `Any operator()(const Object*) const`, `Any operator()(const ObjectRef&) const` | Wrapper to invoke a field getter |
| `FieldSetter` | class | `void operator()(Object*, AnyView) const` | Wrapper to invoke a field setter |
| `ForEachFieldInfo(type_info, callback)` | function | `void ForEachFieldInfo(const TVMFFITypeInfo*, Callback)` | Iterate all fields including inherited (callback must return void) |
| `ForEachFieldInfoWithEarlyStop(type_info, callback)` | function | `bool ForEachFieldInfoWithEarlyStop(const TVMFFITypeInfo*, Callback)` | Iterate fields with early termination (callback returns bool) |
| `TypeAttrColumn` | class | `AnyView operator[](int32_t type_index)` | Read accessor for a named type attribute column |

### Removed
| Name | Kind | Description |
|------|------|-------------|
| ~~`TVM_FFI_REFLECTION_DEF(TypeName)`~~ | macro | Removed: replaced by `TVM_FFI_STATIC_INIT_BLOCK({ ObjectDef<T>()... })` |
| ~~`TVM_FFI_REGISTER_GLOBAL(name)`~~ | macro | Removed: replaced by `GlobalDef().def(...)` (commit 26b68b0) |
| ~~`ReflectionDef`~~ | class | Removed: replaced by `ObjectDef<T>` (commit a419ed1) |
| ~~`ReflectionFieldGetter`~~ | class | Renamed to `FieldGetter` |
| ~~`GetReflectionFieldInfo`~~ | function | Renamed to `GetFieldInfo` |
| ~~`FieldInfoTrait`~~ | class | Renamed to `InfoTrait` (28fe3cc) |
