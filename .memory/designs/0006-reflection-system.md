---
design: "0006"
title: "Reflection System: ObjectDef, GlobalDef, and Runtime Type Metadata"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-06-15"
last_updated: "2025-10-19"
scope:
  - "ffi/reflection"
  - "ffi/c_api"
  - "ffi/object"
  - "ffi/function"
source_commits:
  - "1a856886c8c14c6271e156d1ce4d76335d42f0ff"
  - "a419ed175aac752a3df2ee73faad360a2824ecd8"
  - "e9094866e1e58535f2456b92c1072449f6a2716a"
  - "7e0a4b35df078675af32624b9cd02d1b8da1353e"
  - "837800e772d8c1dfa3a00a9f23f096487c96bd37"
  - "69f2484f915d95886502a1f620ea69aeed623c49"
  - "a5a08b2553a8327cb821b17aa4028ff5ba52e8f0"
  - "0966c368b097ec1b89e459a550716674198ac1d4"
  - "b333288162ba3a883dbf6b1ce23672f687d70163"
  - "da47623098927c5b7e6380b1481b4002facdd6cd"
  - "e95b43b0a36325fc17ad3918e3572cf11fabae13"
  - "26b68b0256fb40baa8aeb55847050d13b064f441"
  - "9445fe734839cffc8bdf881788528b7763f7be03"
  - "162d6009252dd44950a9aa9b890cbbce6b8e5155"
  - "7cb92736b2ed95852ac71543937511acc7a3feec"
  - "f4ede982f00257881d9ba7fe82dd8abc07e14690"
  - "935a5a074686839ae42a9bc52581232beeb5b1fc"
  - "28fe3cc7fc23b725ddefbb3ca1e1899a7dfd530c"
  - "368af824845424ea439b9f3d68bf4a710afb38b1"
  - "dd4fb0ae92ab69b1cc0280e812a18a58273d4ae6"
  - "9ac31216"
  - "fc2630fa"
  - "7b57a466"
  - "f0145b4"
  - "0729193f"
source_ledgers:
  - ".memory/commits/2025-06-15-1a856886c8c14c6271e156d1ce4d76335d42f0ff.md"
  - ".memory/commits/2025-06-16-a419ed175aac752a3df2ee73faad360a2824ecd8.md"
  - ".memory/commits/2025-06-17-e9094866e1e58535f2456b92c1072449f6a2716a.md"
  - ".memory/commits/2025-06-18-7e0a4b35df078675af32624b9cd02d1b8da1353e.md"
  - ".memory/commits/2025-06-19-837800e772d8c1dfa3a00a9f23f096487c96bd37.md"
  - ".memory/commits/2025-06-25-69f2484f915d95886502a1f620ea69aeed623c49.md"
  - ".memory/commits/2025-06-27-a5a08b2553a8327cb821b17aa4028ff5ba52e8f0.md"
  - ".memory/commits/2025-07-01-0966c368b097ec1b89e459a550716674198ac1d4.md"
  - ".memory/commits/2025-07-03-b333288162ba3a883dbf6b1ce23672f687d70163.md"
  - ".memory/commits/2025-07-03-da47623098927c5b7e6380b1481b4002facdd6cd.md"
  - ".memory/commits/2025-07-14-e95b43b0a36325fc17ad3918e3572cf11fabae13.md"
  - ".memory/commits/2025-07-15-26b68b0256fb40baa8aeb55847050d13b064f441.md"
  - ".memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md"
  - ".memory/commits/2025-07-22-162d6009252dd44950a9aa9b890cbbce6b8e5155.md"
  - ".memory/commits/2025-08-05-7cb92736b2ed95852ac71543937511acc7a3feec.md"
  - ".memory/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md"
  - ".memory/commits/2025-10-01-935a5a07.md"
  - ".memory/commits/2025-10-03-28fe3cc7.md"
  - ".memory/commits/2025-10-07-368af824.md"
  - ".memory/commits/2025-10-08-dd4fb0ae.md"
  - ".memory/commits/2025-10-14-9ac31216.md"
  - ".memory/commits/2025-10-15-fc2630fa.md"
  - ".memory/commits/2025-10-14-7b57a466.md"
  - ".memory/commits/2025-10-15-f0145b4.md"
  - ".memory/commits/2025-10-19-0729193f.md"
---

# Reflection System: ObjectDef, GlobalDef, and Runtime Type Metadata

## TL;DR
- The reflection system provides a pybind/nanobind-inspired builder API (`ObjectDef<T>`, `GlobalDef`) for registering object fields, methods, and global functions with rich metadata (docstrings, default values, type schemas, flags). It replaces the legacy `VisitAttrs` pattern and `TVM_FFI_REGISTER_GLOBAL` macro.
- All reflection metadata is stored in the C ABI via `TVMFFIFieldInfo`, `TVMFFIMethodInfo`, and `TVMFFITypeMetadata` structs, accessible from any language through the C API. This enables cross-language object construction (`MakeObjectFromPackedArgs`), field access, and method dispatch without compile-time knowledge of concrete types.
- The system is split into two header layers: `registry.h` (write path: type/field/method registration at static-init time) and `accessor.h` (read path: runtime field/method access), minimizing compile-time cost for translation units that only define types.

## Problem Statement
Cross-language object systems need a way to introspect object fields, methods, and construction parameters at runtime. Without reflection, each Python/Rust binding must manually wrap every C++ type with bespoke glue code. The legacy `VisitAttrs` pattern required visitor callbacks and did not provide field metadata (types, defaults, docs) needed for automatic Python `__init__` generation, property binding, or documentation.

## Context and Constraints
- Reflection metadata must be accessible from C (via `TVMFFITypeInfo`) so Python Cython and Rust bindings can read it without C++ headers.
- Registration must happen at static initialization time (before `main()`), compatible with shared library loading order.
- The API should follow the pybind/nanobind convention (`def_ro`, `def_rw`, `def`, `def_static`) to be familiar to the ML ecosystem.
- Mutable fields require compile-time gating via `_type_mutable` to prevent accidental writes to immutable objects.
- The `ObjectDef<T>` builder must work with base-class member pointers for inherited fields.
- The global function registry must carry metadata (doc, type schema) alongside the function itself.

## Goals
- Provide `ObjectDef<T>` for registering object type metadata: fields (read-only/writable), methods, default values, docstrings, type schemas, and an object creator callback.
- Provide `GlobalDef` for registering global functions with metadata, replacing `TVM_FFI_REGISTER_GLOBAL`.
- Enable runtime object construction from type key + field arguments via `MakeObjectFromPackedArgs`.
- Enable runtime field traversal (including inherited fields) via `ForEachFieldInfo`.
- Keep the C ABI structs self-describing so foreign language bindings need only `c_api.h`.

## Non-Goals
- Full serialization/deserialization framework (reflection provides metadata; serializers are built on top).
- Runtime method dispatch with virtual table semantics (methods are stored as `Function` objects, not vtable slots).
- Automatic Python class generation (that is the Python `c_class` layer, built on top of this C++ reflection).

## Design
### Components and Responsibilities

- **`ObjectDef<T>`** (template, `reflection/registry.h`): Builder for registering a single object type's reflection metadata. Constructor registers `TVMFFITypeMetadata` (creator, total_size, doc). Methods: `def_ro(name, member_ptr, extras...)` for read-only fields, `def_rw(name, member_ptr, extras...)` for writable fields (requires `T::_type_mutable`), `def(name, callable, extras...)` for methods, `def_static(name, callable, extras...)` for static methods, `def(refl::init<Args...>())` for constructors (replaces the previous `def_static("__ffi_init__", refl::init<T, Args...>)` pattern, commit `fc2630fa`).

- **`refl::init<Args...>`** (struct, `reflection/registry.h`): Constructor registration tag type. When passed to `ObjectDef<T>::def()`, it registers an `__ffi_init__` method whose `Class` type is deduced from the `ObjectDef<T>` context (commit `fc2630fa`). This aligns with the pybind11/nanobind convention where the class type is not redundantly specified. The struct has a private `execute<Class>` static method that creates the object. Replaces the previous `refl::init<T, Args...>` free function template. The internal constant `INIT_METHOD_NAME` was renamed to `kInitMethodName` (commit `f0145b4`) to follow Google C++ naming conventions.

- **`GlobalDef`** (class, `reflection/registry.h`): Builder for registering global functions with metadata. Methods: `def(name, func, extras...)` for typed functions, `def_packed(name, func, extras...)` for packed-args functions, `def_method(name, member_ptr, extras...)` for class member functions exposed as globals.

- **`ReflectionDefBase`** (base class, `reflection/registry.h`): Shared infrastructure for `ObjectDef` and `GlobalDef`. Provides `FieldGetter`/`FieldSetter` lambda factories, `ObjectCreatorDefault<T>`, `GetMethod` dispatch (handles `ObjectRef` by-value vs `Object` by-pointer), and `InfoTrait` application helpers. The `GetMethod` was simplified in commit `f4ede98` to a single non-class-templated overload (removing the `Class` template parameter and redundant `GlobalDef::GetMethod_` overloads), since `Function::FromTyped` already handles member function pointers.

- **`TVMFFIFieldInfo`** (C struct, `c_api.h`): Per-field metadata. Fields: `name` (TVMFFIByteArray), `offset` (int64), `size` (int64), `alignment` (int64), `type_schema` (TVMFFIByteArray), `field_static_type_index` (int32), `flags` (int64, bitmask from `TVMFFIFieldFlagBitMask`), `doc` (TVMFFIByteArray), `default_value` (TVMFFIAny), `getter` (TVMFFIAny), `setter` (TVMFFIAny), `metadata` (TVMFFIObjectHandle).

- **`TVMFFIMethodInfo`** (C struct, `c_api.h`): Per-method metadata. Fields: `name` (TVMFFIByteArray), `metadata` (TVMFFIByteArray, renamed from `type_schema` in commit `935a5a0`), `method` (TVMFFIAny), `flags` (int64), `doc` (TVMFFIByteArray), `metadata_handle` (TVMFFIObjectHandle).

- **`TVMFFITypeMetadata`** (C struct, `c_api.h`): Per-type metadata. Fields: `creator` (TVMFFIObjectCreator callback), `total_size` (int32), `doc` (TVMFFIByteArray), `structural_eq_hash_kind` (TVMFFISEqHashKind). Renamed from `TVMFFITypeExtraInfo` in commit `162d600`.

- **`InfoTrait`** (base struct, `reflection/registry.h`): Extensible trait applied to field/method info via variadic extra arguments. Concrete traits: `DefaultValue` (sets `default_value` + `HasDefault` flag), `Metadata` (attaches key-value pairs). Renamed from `FieldInfoTrait` in commit `28fe3cc7`.

- **`details::TypeSchema<T>`** (C++ trait, `type_traits.h`, `function_details.h`): Generates JSON type descriptor strings for all FFI types. Automatically attached as `metadata["type_schema"]` by `GlobalDef::def`, `def_method`, `ObjectDef::def_ro`/`def_rw`. Member function schemas include the `self` type as the first argument (fix in commit `368af824`). See [Design 0019](.memory/designs/0019-typeschema-metadata-system.md) for full details.

- **`reflection::Metadata`** (class, `reflection/registry.h`): Key-value store (String -> Any) attachable to fields, methods, and global functions. Applied via the `InfoTrait` mechanism. Serialized as JSON in the C struct's `metadata` byte array. Added in commit `28fe3cc7`.

- **`ForEachFieldInfo` / `ForEachFieldInfoWithEarlyStop`** (templates, `reflection/accessor.h`): Walk all fields of a type including inherited parent fields, traversing the ancestor chain from root to leaf.

- **`FieldGetter` / `FieldSetter`** (classes, `reflection/accessor.h`): Runtime field access helpers that read/write fields by offset from `TVMFFIFieldInfo`.

- **`MakeObjectFromPackedArgs`** (global function, `src/ffi/extra/reflection_extra.cc`): Creates an object by type key (or type index), iterating ancestor fields parent-to-child, matching keyword arguments to field names, and applying defaults for unset fields. Relocated from core `src/ffi/object.cc` to `extra/` in commit `f4ede98`, gated behind `TVM_FFI_USE_EXTRA_CXX_API`.

- **`reflection::ObjectCreator`** (class, `reflection/creator.h`): Higher-level alternative to `MakeObjectFromPackedArgs` that constructs objects from `Map<String, Any>`. Calls `TVMFFITypeMetadata.creator` to allocate, walks `ForEachFieldInfo` parent-to-child matching map keys to field names, applies defaults for unset fields, and detects extra/missing fields with diagnostics. Preferred for C++ callers. See [Design 0008](.memory/designs/0008-json-ecosystem.md).

- **`TypeAttrDef<T>`** (template, `reflection/registry.h`): Builder for registering per-type attributes via the TypeAttr column store. Methods: `def(name, func)` for function-valued attrs, `attr(name, value)` for constant-valued attrs. Inherits from `ReflectionDefBase` for method wrapping. Attributes are stored in a column-oriented store in `TypeTable`, indexed by `(attr_name, type_index)`.

- **`TypeAttrColumn`** (class, `reflection/accessor.h`): Read-side accessor wrapping `TVMFFIGetTypeAttrColumn`. Provides `operator[](type_index)` returning `AnyView`. Used for runtime lookup of per-type attributes like `__s_equal__` and `__s_hash__`.

- **`EnsureTypeAttrColumn`** (function, `reflection/registry.h`): Registers a column slot (with `type_index = kTVMFFINone`) without storing a value. Ensures the column exists for later reads, avoiding null-pointer checks.

- **`TVMFFITypeAttrColumn`** (C struct, `c_api.h`): Column-array of `TVMFFIAny` values indexed by `type_index`, with `data` pointer and `size`. Returned by `TVMFFIGetTypeAttrColumn`.

- **`AttachFieldFlag`** (reflection trait, `reflection/registry.h`): Annotates fields with semantic flags via `TVMFFIFieldFlagBitMask`. Concrete flags include `kTVMFFIFieldFlagBitMaskSEqHashIgnore` and `kTVMFFIFieldFlagBitMaskSEqHashDef` for structural equal/hash semantics.

- **`TVM_FFI_STATIC_INIT_BLOCK`** (macro, `base_details.h`): General-purpose static initialization macro. Generates a static function with `[[maybe_unused]]` attribute that runs its body at program startup. Used for both `ObjectDef<T>`, `GlobalDef`, and `TypeAttrDef` registration blocks.

### Data Contracts and Invariants
- **Single registration invariant**: Each type index may have `TVMFFITypeMetadata` registered at most once. Duplicate registration throws `RuntimeError` with diagnostic hints.
- **Mutability gate**: `def_rw` requires `T::_type_mutable == true` at compile time. A `static_assert` enforces this.
- **Base-class member pointer**: `def_ro`/`def_rw` accept `T BaseClass::*` member pointers where `std::is_base_of_v<BaseClass, Class>`. This is enforced by `static_assert`.
- **Ancestor field order**: `ForEachFieldInfo` visits fields in parent-to-child order by walking `type_ancestors[0..type_depth-1]`, then the leaf type's own fields.
- **Ancestor pointer invariant**: `TVMFFITypeInfo::type_ancestors` stores `const TVMFFITypeInfo**` (pointers to parent TypeInfo structs), enabling O(1) field/method access on ancestors without index lookups.
- **Root type participation**: `Object` itself has a registered `TVMFFITypeMetadata` (with `creator = nullptr`), ensuring reflection queries are uniform across the hierarchy.

### Control Flow
1. **Type registration**: `TVM_FFI_STATIC_INIT_BLOCK({ ObjectDef<FooObj>("doc").def_ro("x", &FooObj::x).def("method", &Foo::Method); })` at static init -> `ObjectDef` constructor calls `TVMFFITypeRegisterMetadata` with creator, total_size, doc -> each `def_ro`/`def_rw` calls `TVMFFITypeRegisterField` with populated `TVMFFIFieldInfo` -> each `def`/`def_static` calls `TVMFFITypeRegisterMethod` with populated `TVMFFIMethodInfo`.
2. **Global function registration**: `TVM_FFI_STATIC_INIT_BLOCK({ GlobalDef().def("func.name", my_func, "doc"); })` -> `GlobalDef::RegisterFunc` calls `TVMFFIFunctionSetGlobalFromMethodInfo` with function + metadata.
3. **Object construction from reflection**: `MakeObjectFromPackedArgs("ffi.FooObj", "x", 42)` -> look up type index -> get `TVMFFITypeMetadata.creator` -> call creator to allocate -> walk ancestors parent-to-child, matching field names to keyword args -> set defaults for unset fields -> return constructed object.
3b. **Python auto-init safety** (commit `0729193f`): When a registered Python object class has no `__init__`, `_add_class_attrs` in `registry.py` auto-generates one: if `__ffi_init__` method is defined (from reflection), it becomes `__init__`; otherwise, `__init__` raises `RuntimeError`. This prevents silent creation of objects with `chandle=None` that would segfault on field access. The fix also changed `dict(cls.__dict__)` to `cls.__dict__.copy()` in `object.pxi` for correctness.
4. **Field traversal**: `ForEachFieldInfo(type_info, [](const TVMFFIFieldInfo& f) { ... })` -> iterate `type_ancestors[0..depth-1]` visiting each ancestor's fields -> then visit the leaf type's own fields.
5. **Field access**: `FieldGetter(field_info)(obj_ptr)` -> read `AnyView` at `(char*)obj + field_info->offset` -> convert to `Any` and return.

### Extension Points
- **New InfoTraits**: Implement a struct inheriting `InfoTrait` with an `Apply(TVMFFIFieldInfo*)` or `Apply(TVMFFIMethodInfo*)` method. Pass as extra argument to `def_ro`/`def`/etc.
- **Custom creators**: Override the default `make_object<T>` creator by passing a custom `TVMFFIObjectCreator` in `TVMFFITypeMetadata`.
- **New reflection builders**: Inherit from `ReflectionDefBase` for domain-specific registration patterns. `TypeAttrDef<T>` is the first such builder, used for per-type attribute registration.
- **TypeAttr columns**: Register new per-type attributes via `TypeAttrDef<T>().def(name, method)` or `.attr(name, value)`. The column store supports open-ended, user-defined per-type metadata without modifying core structs.
- **Accessor extensions**: Build serializers, debuggers, structural comparators, or Python property generators on top of `ForEachFieldInfo`, `FieldGetter`/`FieldSetter`, and `TypeAttrColumn`.

## Alternatives Considered
### Keep VisitAttrs pattern
- Pros: Already existed in upstream TVM. No migration needed.
- Cons: Visitor-based (no random-access to fields by name). No metadata (types, defaults, docs). Cannot construct objects from reflection. Tightly coupled to C++ (no C ABI exposure).

### Generate reflection from a schema file (IDL/protobuf)
- Pros: Language-neutral. Schema-first design.
- Cons: Requires a build-time code generation step. Cannot reflect types defined at runtime (dynamic registration). Adds build system complexity. Not compatible with existing C++ class definitions.

### Expose C++ RTTI (typeid/typeinfo)
- Pros: Zero annotation cost.
- Cons: Not portable across compilers/DSOs. Cannot provide field-level metadata. No C ABI support. Disabled by default on many builds (`-fno-rtti`).

## Trade-offs
- **Optimized**: Cross-language metadata access (C ABI structs readable by any binding), familiar API (pybind-style), compile-time safety (`_type_mutable` gate, base-class `static_assert`), runtime object construction from reflection.
- **Sacrificed**: Compile-time cost of `ObjectDef` template instantiation, unbounded growth of the `any_pool_` in TypeTable (strings, defaults, metadata owned for process lifetime), no field-level type erasure validation at registration time (only the `field_static_type_index` is a hint, not enforced).

## Interfaces and Compatibility
- **C ABI**: `TVMFFITypeRegisterField`, `TVMFFITypeRegisterMethod`, `TVMFFITypeRegisterMetadata`, `TVMFFITypeRegisterAttr`, `TVMFFIGetTypeAttrColumn`, `TVMFFIFunctionSetGlobalFromMethodInfo`. Structs: `TVMFFIFieldInfo`, `TVMFFIMethodInfo`, `TVMFFITypeMetadata`, `TVMFFITypeAttrColumn`. Enums: `TVMFFIFieldFlagBitMask` (Writable, HasDefault, IsStaticMethod, SEqHashIgnore, SEqHashDef), `TVMFFISEqHashKind`.
- **C++ API**: `reflection::ObjectDef<T>`, `reflection::GlobalDef`, `reflection::TypeAttrDef<T>`, `reflection::TypeAttrColumn`, `reflection::EnsureTypeAttrColumn`, `reflection::AttachFieldFlag`, `reflection::ForEachFieldInfo`, `reflection::FieldGetter`, `reflection::FieldSetter`, `TVM_FFI_STATIC_INIT_BLOCK`.
- **Compatibility**: The `TVMFFIFieldInfo` and `TVMFFIMethodInfo` struct layouts evolved through multiple commits and are now stable. Adding new fields at the end is a minor version change; reordering is a major version change.

## Failure Modes and Mitigations
- **Duplicate type metadata registration**: Throws `RuntimeError` with hints (duplicate `ObjectDef<T>`, missing `_type_key` override, key collision). Fail-fast prevents silent data corruption.
- **Duplicate TypeAttr registration**: Registering the same `(attr_name, type_index)` pair twice throws `RuntimeError`.
- **Missing required field in MakeObjectFromPackedArgs**: Throws `TypeError` listing the missing field name and type.
- **def_rw on immutable type**: Compile-time `static_assert` failure with message about `_type_mutable`.
- **Base-class member pointer type mismatch**: Compile-time `static_assert` failure with `is_base_of` diagnostic.
- **Field offset overflow**: `offset`, `size`, `alignment` are `int64_t`, supporting objects up to 2^63 bytes. Practically impossible to overflow.

## Observability and Validation
- `tests/cpp/test_reflection.cc`: Tests `ObjectDef`, `GlobalDef`, `ForEachFieldInfo`, `FieldGetter`, `FieldSetter`, `MakeObjectFromPackedArgs`, default values, method registration, base-class member pointers.
- `TVMFFITypeIndexToInfo` C API provides runtime introspection of all registered type metadata.
- `TVMFFIFunctionListGlobal` lists all registered global functions with their metadata.
- Duplicate registration is detected at static init time and fails loudly.

## Migration and Rollout
- **From VisitAttrs**: Replace `void VisitAttrs(AttrVisitor* v) { v->Visit("field", &field); }` with `ObjectDef<T>().def_ro("field", &T::field)` in a `TVM_FFI_STATIC_INIT_BLOCK`.
- **From TVM_FFI_REGISTER_GLOBAL**: Replace `TVM_FFI_REGISTER_GLOBAL("name").set_body_typed(f)` with `GlobalDef().def("name", f)` in a `TVM_FFI_STATIC_INIT_BLOCK`.
- The `_type_has_method_visit_attrs` flag on `Object` has been removed; new code should use only `ObjectDef`.
- `TVM_FFI_REGISTER_GLOBAL` and `Function::Registry` have been deleted; all in-tree code uses `GlobalDef`.

## Diagrams
- [.memory/diagrams/0004-reflection-system-architecture.md](.memory/diagrams/0004-reflection-system-architecture.md)

## Related ADRs
- [.memory/ADRs/0009-extra-api-isolation.md](.memory/ADRs/0009-extra-api-isolation.md) (structural equal/hash, built on reflection, isolated to extra/ directory)
- [.memory/ADRs/0031-explicit-object-type-registration.md](.memory/ADRs/0031-explicit-object-type-registration.md) (removal of static inline registration in favor of ObjectDef)

## Related Design Docs
- [.memory/designs/0019-typeschema-metadata-system.md](.memory/designs/0019-typeschema-metadata-system.md) (TypeSchema and Metadata system built on top of reflection)

## Evidence Matrix
- `ObjectDef<T>` template with `def_ro`/`def_rw`/`def`/`def_static` -> `.memory/commits/2025-06-15-1a856886c8c14c6271e156d1ce4d76335d42f0ff.md` + `1a8568` + `include/tvm/ffi/reflection/registry.h`
- `TVMFFIFieldInfo` with offset/size/alignment/type_schema/flags/default_value -> `.memory/commits/2025-06-16-a419ed175aac752a3df2ee73faad360a2824ecd8.md` + `a419ed` + `include/tvm/ffi/c_api.h`
- `TVMFFITypeMetadata` (creator, total_size, doc) -> `.memory/commits/2025-06-16-a419ed175aac752a3df2ee73faad360a2824ecd8.md` + `a419ed` + `include/tvm/ffi/c_api.h`
- `MakeObjectFromPackedArgs` global function -> `.memory/commits/2025-06-17-e9094866e1e58535f2456b92c1072449f6a2716a.md` + `e90948` + `src/ffi/object.cc`
- `ReflectionDefBase` base class with `GetMethod` dispatch -> `.memory/commits/2025-06-17-e9094866e1e58535f2456b92c1072449f6a2716a.md` + `e90948`
- Ancestor pointer change (`type_ancestors` from int32* to TypeInfo**) -> `.memory/commits/2025-06-19-837800e772d8c1dfa3a00a9f23f096487c96bd37.md` + `837800`
- `ForEachFieldInfo` and `ForEachFieldInfoWithEarlyStop` -> `.memory/commits/2025-06-19-837800e772d8c1dfa3a00a9f23f096487c96bd37.md` + `837800` + `.memory/commits/2025-06-25-69f2484f915d95886502a1f620ea69aeed623c49.md` + `69f248`
- Enum TypeTraits and base-class member pointer support -> `.memory/commits/2025-06-27-a5a08b2553a8327cb821b17aa4028ff5ba52e8f0.md` + `a5a08b`
- `GlobalDef` class with `def`/`def_packed`/`def_method` -> `.memory/commits/2025-07-03-b333288162ba3a883dbf6b1ce23672f687d70163.md` + `b33328`
- Removal of `_type_has_method_visit_attrs` -> `.memory/commits/2025-07-03-da47623098927c5b7e6380b1481b4002facdd6cd.md` + `da4762`
- Split into `registry.h` and `accessor.h` -> `.memory/commits/2025-07-14-e95b43b0a36325fc17ad3918e3572cf11fabae13.md` + `e95b43`
- Removal of `TVM_FFI_REGISTER_GLOBAL` and `Function::Registry` -> `.memory/commits/2025-07-15-26b68b0256fb40baa8aeb55847050d13b064f441.md` + `26b68b`
- Duplicate registration guard -> `.memory/commits/2025-07-01-0966c368b097ec1b89e459a550716674198ac1d4.md` + `0966c3`
- `TVM_FFI_STATIC_INIT_BLOCK` macro -> `.memory/commits/2025-06-16-a419ed175aac752a3df2ee73faad360a2824ecd8.md` + `a419ed` + `include/tvm/ffi/base_details.h`
- `AttachFieldFlag` for SEqHash field annotations -> `.memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md` + `9445fe7` + `include/tvm/ffi/reflection/registry.h`
- `TypeAttrDef<T>` and `TypeAttrColumn` -> `.memory/commits/2025-07-22-162d6009252dd44950a9aa9b890cbbce6b8e5155.md` + `162d600` + `include/tvm/ffi/reflection/registry.h`, `include/tvm/ffi/reflection/accessor.h`
- Rename `TVMFFITypeExtraInfo` -> `TVMFFITypeMetadata` -> `.memory/commits/2025-07-22-162d6009252dd44950a9aa9b890cbbce6b8e5155.md` + `162d600` + `include/tvm/ffi/c_api.h`
- `TVMFFITypeAttrColumn` C struct and `TVMFFITypeRegisterAttr`/`TVMFFIGetTypeAttrColumn` C APIs -> `.memory/commits/2025-07-22-162d6009252dd44950a9aa9b890cbbce6b8e5155.md` + `162d600` + `include/tvm/ffi/c_api.h`
- `reflection::ObjectCreator` from `Map<String, Any>` -> `.memory/commits/2025-08-05-7cb92736b2ed95852ac71543937511acc7a3feec.md` + `7cb9273` + `include/tvm/ffi/reflection/creator.h`
- `MakeObjectFromPackedArgs` moved to `extra/reflection_extra.cc` -> `.memory/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md` + `f4ede98` + `src/ffi/extra/reflection_extra.cc`
- `GetMethod` simplified to single non-class-templated overload -> `.memory/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md` + `f4ede98` + `include/tvm/ffi/reflection/registry.h`
- `TVMFFIFieldInfo.type_schema` and `TVMFFIMethodInfo.type_schema` renamed to `metadata`, `ModuleObj::GetFunctionDoc` added -> `.memory/commits/2025-10-01-935a5a07.md` + `935a5a0` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/extra/module.h`
- `TypeSchema<T>` trait, `Metadata` class, `FieldInfoBuilder`/`MethodInfoBuilder`, `EscapeString`, `FieldInfoTrait` -> `InfoTrait` rename -> `.memory/commits/2025-10-03-28fe3cc7.md` + `28fe3cc7` + `include/tvm/ffi/type_traits.h`, `include/tvm/ffi/reflection/registry.h`, `include/tvm/ffi/string.h`
- Member function self-type inclusion in TypeSchema -> `.memory/commits/2025-10-07-368af824.md` + `368af824` + `include/tvm/ffi/function_details.h`
- `TypeSchema.repr(ty_map=...)` customizable rendering -> `.memory/commits/2025-10-08-dd4fb0ae.md` + `dd4fb0ae` + `python/tvm_ffi/cython/type_info.pxi`
- Removed static inline auto-registration from `TVM_FFI_DECLARE_OBJECT_INFO*` macros -> `.memory/commits/2025-10-14-9ac31216.md` + `9ac31216` + `include/tvm/ffi/object.h`
- `refl::init<Args...>` struct and `ObjectDef::def(init<Args...>)` constructor registration -> `.memory/commits/2025-10-15-fc2630fa.md` + `fc2630fa` + `include/tvm/ffi/reflection/registry.h`
- `FunctionInfo` specialization for `ObjectRef::MemFn` (pass ObjectRef by value) -> `.memory/commits/2025-10-14-7b57a466.md` + `7b57a466` + `include/tvm/ffi/function_details.h`
- `INIT_METHOD_NAME` -> `kInitMethodName` naming convention fix -> `.memory/commits/2025-10-15-f0145b4.md` + `f0145b4` + `include/tvm/ffi/reflection/registry.h`
- Auto-generate `__init__` from `__ffi_init__` or raise `RuntimeError` -> `.memory/commits/2025-10-19-0729193f.md` + `0729193f` + `python/tvm_ffi/registry.py`, `python/tvm_ffi/cython/object.pxi`

## Open Questions
- Should the `any_pool_` in TypeTable have a bounded size or garbage collection for rarely-used type metadata?
- Should `TVMFFIFieldInfo` include a `type_schema` validator that checks field values at set time (currently the schema is a hint, not enforced)?
- Should `MakeObjectFromPackedArgs` support positional arguments in addition to keyword-style field matching?

## Confidence and Risk
- Confidence: high
- Residual risks: The `any_pool_` grows unboundedly for the process lifetime, which could be a concern for long-running applications that dynamically register and unregister types (though unregistration is not currently supported). The `const_cast` in non-const `GetMethod` overload is safe only when `_type_mutable` is set, but this invariant is enforced at the `Any` extraction site, not at the reflection registration site.
