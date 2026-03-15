---
scope: "reflection"
---
# API Index: Reflection System

**Scope**: Reflection registration builders and runtime accessors in `tvm::ffi::reflection` namespace.
**Design docs**: [0009-reflection.md](../designs/0009-reflection.md), [0010-structural-equal-hash.md](../designs/0010-structural-equal-hash.md)
**ADRs**: [0008-globaldef-over-register-global.md](../ADRs/0008-globaldef-over-register-global.md), [0009-custom-seqhash-via-typeattr.md](../ADRs/0009-custom-seqhash-via-typeattr.md), [0027-auto-init-from-reflection.md](../ADRs/0027-auto-init-from-reflection.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `ReflectionDefBase` | class | `FieldGetter<T>()$`, `FieldSetter<T>()$`, `ObjectCreatorDefault<T>()$`, `GetMethod(name, func)$`, `ApplyFieldInfoTrait()$`, `ApplyMethodInfoTrait()$`, `ApplyExtraInfoTrait()$` | Base class with shared reflection helpers |
| `InfoTrait` | struct | (empty base class, renamed from `FieldInfoTrait`) | Extension point for field/method metadata customization |
| `Metadata` | class | `Metadata(initializer_list<pair<String, Any>>)`, `Apply(FieldInfoBuilder*)`, `Apply(MethodInfoBuilder*)` | Attach key-value metadata to fields, methods, global functions |
| `FieldInfoBuilder` | struct | inherits `TVMFFIFieldInfo`; `_MetadataType metadata_` | Extended field info with builder-time metadata |
| `MethodInfoBuilder` | struct | inherits `TVMFFIMethodInfo`; `_MetadataType metadata_` | Extended method info with builder-time metadata |
| `ObjectDef<Class>` | class template | `ObjectDef(ExtraArgs...)`, `def_ro(name, field_ptr, extra...) -> ObjectDef&`, `def_rw(name, field_ptr, extra...) -> ObjectDef&`, `def(name, func, extra...) -> ObjectDef&`, `def(init<Args...>, extra...) -> ObjectDef&` (fc2630f), `def_static(name, func, extra...) -> ObjectDef&`; `INIT_METHOD_NAME = "__ffi_init__"` | Registration builder for object types |
| `init<Args...>` | struct template (fc2630f) | `init()` default ctor; `execute<Class>(Args&&...) -> ObjectRef` (private, deduced from ObjectDef context) | Constructor registration tag; replaces old `init<T, Args...>` free function |
| `GlobalDef` | class | `def(name, func, extra...) -> GlobalDef&`, `def_packed(name, func, extra...) -> GlobalDef&`, `def_method(name, func, extra...) -> GlobalDef&` | Registration builder for global functions |
| `FieldInfoTrait` | struct | **deprecated, renamed to `InfoTrait`** | Legacy name for field metadata extension point |
| `DefaultValue` | class | `DefaultValue(Any value)`, `Apply(TVMFFIFieldInfo*)` | Sets direct default value on field info |
| `DefaultFactory` | class (5e564cd) | `DefaultFactory(Function factory)`, `Apply(TVMFFIFieldInfo*)` | Factory-based default: stores `() -> Any` callable in `default_value_or_factory`; sets `kTVMFFIFieldFlagBitMaskDefaultFromFactory` flag |
| `SetFieldToDefault` | inline function (5e564cd) | `(const TVMFFIFieldInfo*, void* field_addr) -> void` | Centralized default resolution: calls factory or passes direct value to setter |
| `type_attr::kInit` | constant (c73d61a) | `= "__ffi_init__"` | Well-known attribute name for constructor method |
| `type_attr::kShallowCopy` | constant (c73d61a) | `= "__ffi_shallow_copy__"` | Well-known attribute name for shallow copy method |
| `GetFieldByteOffsetToObject` | function template | `(T BaseClass::*field_ptr) -> int64_t` | Compute byte offset from Object* to field |
| `FieldGetter` | class | `FieldGetter(TVMFFIFieldInfo*)`, `FieldGetter(type_key, field_name)`, `operator()(const Object*) -> Any`, `operator()(const ObjectRef&) -> Any` | Callable field read accessor |
| `FieldSetter` | class | `FieldSetter(TVMFFIFieldInfo*)`, `FieldSetter(type_key, field_name)`, `operator()(const Object*, AnyView)`, `operator()(const ObjectRef&, AnyView)` | Callable field write accessor |
| `GetFieldInfo` | function | `(string_view type_key, const char* field_name) -> const TVMFFIFieldInfo*` | Look up field info by name |
| `GetMethodInfo` | function | `(string_view type_key, const char* method_name) -> const TVMFFIMethodInfo*` | Look up method info by name |
| `GetMethod` | function | `(string_view type_key, const char* method_name) -> Function` | Get method as callable Function |
| `ForEachFieldInfo` | function template | `(const TypeInfo*, Callback) -> void` (Callback: `(const TVMFFIFieldInfo*) -> void`) | Iterate all fields (inherited + own), parent-to-child |
| `ForEachFieldInfoWithEarlyStop` | function template | `(const TypeInfo*, Callback) -> bool` (Callback: `(const TVMFFIFieldInfo*) -> bool`) | Same with early termination |
| `TVMFFIFieldFlagBitMask` | enum | `Writable=1`, `HasDefault=2`, `IsStaticMethod=4`, `SEqHashIgnore=8`, `SEqHashDef=16`, `DefaultFromFactory=32` (5e564cd), `ReprOff=64` (b648c5d), `CompareOff=128` (6b39efb), `HashOff=256` (6b39efb), `InitOff=512` (6b39efb), `KwOnly=1024` (6b39efb), `SetterIsFunctionObj=2048` (10dc59d) | Bitmask for field/method flags |
| `TVMFFITypeMetadata` | struct | `TVMFFIByteArray doc; TVMFFIObjectCreator creator; int32_t total_size; TVMFFISEqHashKind structural_eq_hash_kind` | Type metadata (renamed from TVMFFITypeExtraInfo) |
| `TVMFFITypeAttrColumn` | struct | `const TVMFFIAny* data; int32_t size; int32_t begin_index` (c85fd42) | Column-oriented per-type attribute storage; sparse range `[begin_index, begin_index + size)` |
| `TypeAttrDef<Class>` | class template | `TypeAttrDef(ExtraArgs...)`, `def(name, func) -> TypeAttrDef&`, `attr(name, value) -> TypeAttrDef&` | Registration builder for per-type attributes |
| `TypeAttrColumn` | class | `TypeAttrColumn(string_view attr_name)`, `operator[](int32_t type_index) -> AnyView` | Runtime accessor for per-type attribute columns |
| `EnsureTypeAttrColumn` | function | `(string_view name) -> void` | Pre-create attribute column without registering values |
| `OverloadObjectDef<Class>` | class template (`reflection/overload.h`, 84c5bdb) | `def_ro(name, field_ptr, extra...) -> OverloadObjectDef&`, `def_rw(name, field_ptr, extra...) -> OverloadObjectDef&`, `def(name, func, extra...) -> OverloadObjectDef&` (overloadable), `def_static(name, func, extra...) -> OverloadObjectDef&` (overloadable), `def(init<Args...>, extra...) -> OverloadObjectDef&` (overloadable ctor) | Overload-aware registration builder. Private-inherits ObjectDef. First def() for a name creates OverloadedFunction via FromPackedInplace; subsequent calls register additional overloads |
| `details::OverloadBase` | struct (`reflection/overload.h`, 84c5bdb) | `FnPtr = bool(*)(OverloadBase*, const AnyView*, int32_t, Any*)`, `Register(unique_ptr<OverloadBase>)`, `GetTryCallPtr() -> FnPtr`, `GetMismatchMessage(ostringstream&, const AnyView*, int32_t)` | Base for overload dispatch entries. Tracks num_args and optional name |
| `details::TypedOverload<Callable>` | struct template (`reflection/overload.h`, 84c5bdb) | inherits `OverloadBase`; `TryCall(const AnyView*, int32_t, Any*) -> bool` | Concrete overload entry using try_cast per argument |
| `details::OverloadedFunction<Callable>` | struct template (`reflection/overload.h`, 84c5bdb) | inherits `TypedOverload<Callable>`; `Register(unique_ptr<OverloadBase>)`, `operator()(const AnyView*, int32_t, Any*)` | Runtime overload dispatch callable. Zero overhead when no overloads (direct unpack_call). Slow path iterates overloads by arity then try_call |
| `ReflectionDefBase::WrapFunction` | static method (84c5bdb) | `WrapFunction(Func&&) -> Func&&` (passthrough), `WrapFunction(R (Class::*)(Args...)) -> lambda`, `WrapFunction(R (Class::*)(Args...) const) -> lambda` | Factored-out member-pointer-to-lambda conversion, reusable by ObjectDef and OverloadObjectDef |
| `AttachFieldFlag` | class | `AttachFieldFlag(int32_t flag)`, `SEqHashDef()$`, `SEqHashIgnore()$`, `Apply(TVMFFIFieldInfo*)` | Field trait for attaching flag bits (e.g., SEqHash annotations) |
| `repr` | class (`reflection/registry.h`, b648c5d, renamed from `Repr` in 6b39efb) | `repr(bool show)`, `Apply(TVMFFIFieldInfo*)` | Field trait to exclude fields from repr output. `repr(false)` sets `kTVMFFIFieldFlagBitMaskReprOff` |
| `compare` | class (`reflection/registry.h`, 6b39efb) | `compare(bool include)`, `Apply(TVMFFIFieldInfo*)` | Field trait to exclude from recursive comparison. `compare(false)` sets `CompareOff` |
| `hash` | class (`reflection/registry.h`, 6b39efb) | `hash(bool include)`, `Apply(TVMFFIFieldInfo*)` | Field trait to exclude from recursive hashing. `hash(false)` sets `HashOff` |
| `kw_only` | class (`reflection/registry.h`, 6b39efb) | `kw_only(bool is_kw_only)`, `Apply(TVMFFIFieldInfo*)` | Field trait for keyword-only auto-init parameter. `kw_only(true)` sets `KwOnly` |
| `type_attr::kRepr` | constant (b648c5d) | `= "__ffi_repr__"` | Type attribute key for custom repr functions |
| `MakeInit` | inline function (`reflection/init.h`, 6b39efb) | `(int32_t type_index) -> Function` | Create packed `__ffi_init__` from reflection field metadata; supports positional+KWARGS calling |
| `RegisterAutoInit` | inline function (`reflection/init.h`, 6b39efb) | `(int32_t type_index) -> void` | Call `MakeInit` and register as `__ffi_init__` static method with `auto_init:true` metadata |
| `DeepCopy` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& value) -> Any` | Graph-preserving deep copy (relocated from `extra/deep_copy.h`) |
| `ReprPrint` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& value) -> String` | DFS-based unified repr (relocated from `extra/repr_print.cc`) |
| `RecursiveHash` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& value) -> int64_t` | Deterministic recursive hash using reflection field metadata |
| `RecursiveEq` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& lhs, const Any& rhs) -> bool` | Recursive structural equality |
| `RecursiveLt` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& lhs, const Any& rhs) -> bool` | Recursive structural less-than |
| `RecursiveLe` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& lhs, const Any& rhs) -> bool` | Recursive structural less-than-or-equal |
| `RecursiveGt` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& lhs, const Any& rhs) -> bool` | Recursive structural greater-than |
| `RecursiveGe` | function (`extra/dataclass.h`, 6b39efb) | `(const Any& lhs, const Any& rhs) -> bool` | Recursive structural greater-than-or-equal |
| `TVMFFIObjectCreator` | typedef | `int (*)(TVMFFIObjectHandle* result)` | Object creation function pointer |
| `TVM_FFI_STATIC_INIT_BLOCK()` | macro | `TVM_FFI_STATIC_INIT_BLOCK() { ... }` -- defines a function that runs once at static init. GCC/Clang: `__attribute__((constructor))`; MSVC: static-variable-driven fn call. | General-purpose static initialization |
| `reflection::ObjectCreator` | class (`reflection/creator.h`) | `ObjectCreator(string_view type_key)`, `ObjectCreator(const TVMFFITypeInfo*)`, `operator()(const Map<String, Any>&) -> Any` | Create objects from type key + field map via reflection; validates metadata/creator, applies defaults |
| `DeepCopy` | function (c73d61a, `extra/deep_copy.h`) | `(const Any& value) -> Any` | Graph-preserving deep copy with memoization; handles shared refs and cycles |
| `ObjectDef::AutoRegisterCopy` | private method (c73d61a) | auto-called in ObjectDef constructor | Auto-registers `__ffi_shallow_copy__` for `is_copy_constructible_v<Class>` types as both instance method and type attribute |
| `CreateEmptyObject` | inline function (`reflection/creator.h`, e268eb1d) | `(const TVMFFITypeInfo*) -> ObjectPtr<Object>` | Create empty object: tries `metadata->creator` fast path, falls back to `__ffi_new__` type attr; throws RuntimeError if neither available |
| `HasCreator` | inline function (`reflection/creator.h`, e268eb1d) | `(const TVMFFITypeInfo*) -> bool` | Check if type supports reflection creation (native creator or `__ffi_new__` type attr) |

## C++ API: C ABI Functions for Reflection
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `TVMFFITypeRegisterField` | function | `(int32_t type_index, const TVMFFIFieldInfo*) -> int` | Register a reflection field |
| `TVMFFITypeRegisterMethod` | function | `(int32_t type_index, const TVMFFIMethodInfo*) -> int` | Register a reflection method |
| `TVMFFITypeRegisterMetadata` | function | `(int32_t type_index, const TVMFFITypeMetadata*) -> int` | Register type metadata (renamed from TVMFFITypeRegisterExtraInfo) |
| `TVMFFITypeRegisterAttr` | function | `(int32_t type_index, const TVMFFIByteArray*, const TVMFFIAny*) -> int` | Register per-type attribute |
| `TVMFFIGetTypeAttrColumn` | function | `(const TVMFFIByteArray*) -> const TVMFFITypeAttrColumn*` | Look up per-type attribute column |
| `TVMFFIFunctionSetGlobalFromMethodInfo` | function | `(const TVMFFIMethodInfo*, int allow_override) -> int` | Register global function with metadata |
| `ffi.GetGlobalFuncMetadata` | global function | `(String name) -> String` (JSON metadata) | Retrieve metadata for a registered global function |
| `ffi.ReprPrint` (b648c5d) | global function | `(Any value) -> String` | DFS-based unified repr with cycle detection and DAG memoization. Uses `__ffi_repr__` type attr for custom formatting, generic reflection fallback for others. Controlled by `TVM_FFI_REPR_WITH_ADDR` env var. |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.MakeObjectFromPackedArgs` | `(type_key_or_index, *field_name_value_pairs) -> Object` | Create object by type key + keyword fields |
| `Object.__copy__` (c73d61a) | `(self) -> Object` | Shallow copy via `__ffi_shallow_copy__` type attribute; raises TypeError for non-copyable types |
| `Object.__deepcopy__` (c73d61a) | `(self, memo: dict) -> Object` | Deep copy via `ffi.DeepCopy`; graph-preserving with memoization |
| `Object.__replace__` (c73d61a) | `(self, **kwargs) -> Object` | Dataclass-style replace: shallow copy + field overrides |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | — | Rust reflection bindings not yet in scope |
