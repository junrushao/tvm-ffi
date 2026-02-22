# Reflection System

- Doc ID: 004-reflection-system
- Status: Approved
- Last Updated: 2025-12-29
- Owners: Tianqi Chen

## Overview

The TVM FFI reflection system provides a mechanism to register and query
structured metadata (fields, methods, static functions) about `Object`
subclasses at runtime. This metadata is defined in C++ using `ObjectDef<T>`
and `ReflectionDefBase` builders, stored in the global type table, and
consumed by Python bindings to automatically generate properties, methods,
and constructors on Python class objects.

The reflection system was introduced and iterated across June 2025 in a series
of commits that progressively enriched the C ABI structs, expanded the C++ API,
and began migrating legacy `VisitAttrs`-style code to the new mechanism.

## Key Design

### ObjectDef builder

The `ObjectDef<T>` class template (inheriting from `ReflectionDefBase`)
provides a builder API for registering field metadata. It is typically invoked
inside a static initialization block:

```cpp
ObjectDef<MyObj>("my_module.MyObj", MyObj_TypeInfo)
    .def_rw("name", &MyObj::name, "The name field")
    .def_ro("count", &MyObj::count, "Read-only count")
    .def_static("create", &MyObj::Create, "Factory method");
```

The class hierarchy evolved during this range:
- At `1a85688`: `ReflectionDef` (single class) with `def_ro`, `def_rw`,
  `def_static`.
- From `e909486` onward: `ReflectionDefBase` (base with registration logic) +
  `ObjectDef` (derived, adds field-pointer-specific methods).

Each `def_*` call registers a `TVMFFIFieldInfo` or `TVMFFIMethodInfo` entry
in the type table. The builder also calls `TVMFFITypeRegisterExtraInfo` to
register type-level metadata (total object size, creator function, doc string).

**Methods on `ObjectDef<T>` at end of range** (`f7311e4`):
- `def_ro(name, field_ptr, ...)` -- register a read-only field.
- `def_rw(name, field_ptr, ...)` -- register a read-write field.
- `def_static(name, func, ...)` -- register a static function.

`def_ro` and `def_rw` were extended in `f7311e4` to accept base-class field
pointers (`T BaseClass::*`) with
`static_assert(std::is_base_of_v<BaseClass, Class>)`, enabling registration
of inherited fields in a derived class's definition.

### C ABI field metadata

The `TVMFFIFieldInfo` struct in `c_api.h` carries per-field metadata at the
end of the range (`f7311e4`):

| Field                     | Type                | Purpose                              |
|---------------------------|---------------------|--------------------------------------|
| `name`                    | `TVMFFIByteArray`   | Field name                           |
| `doc`                     | `TVMFFIByteArray`   | Documentation string                 |
| `metadata`                | `TVMFFIByteArray`   | JSON metadata (renamed from `type_schema` in `935a5a0`) |
| `flags`                   | `int64_t`           | Bitmask of `TVMFFIFieldFlagBitMask`  |
| `size`                    | `int64_t`           | Size of the field                    |
| `alignment`               | `int64_t`           | Alignment of the field               |
| `offset`                  | `int64_t`           | Byte offset within the object        |
| `getter`                  | `TVMFFIFieldGetter` | Getter function                      |
| `setter`                  | `TVMFFIFieldSetter` | Setter function                      |
| `default_value`           | `TVMFFIAny`         | Default value (when flag set)        |
| `field_static_type_index` | `int32_t`           | Static type index hint               |

A separate `TVMFFIMethodInfo` struct carries method metadata:

| Field         | Type              | Purpose                         |
|---------------|-------------------|---------------------------------|
| `name`        | `TVMFFIByteArray` | Method name                     |
| `doc`         | `TVMFFIByteArray` | Documentation string            |
| `metadata`    | `TVMFFIByteArray` | JSON metadata (renamed from `type_schema` in `935a5a0`) |
| `flags`       | `int64_t`         | Bitmask flags                   |
| `method`      | `TVMFFIAny`       | The method as packed Function   |

The `TVMFFIFieldFlagBitMask` enum defines:
- `kTVMFFIFieldFlagBitMaskWritable` (0x1): field is writable
- `kTVMFFIFieldFlagBitMaskHasDefault` (0x2): field has a registered default
- `kTVMFFIFieldFlagBitMaskIsStaticMethod` (0x4): entry is a static method

### Type-level metadata

The `TVMFFITypeMetadata` struct (originally `TVMFFITypeExtraInfo`, `a419ed1`;
renamed in `9445fe7`/`162d600`) provides type-level metadata:

| Field        | Type                   | Purpose                           |
|--------------|------------------------|-----------------------------------|
| `doc`        | `TVMFFIByteArray`      | Type documentation string         |
| `creator`    | `TVMFFIObjectCreator`  | Optional factory function         |
| `total_size` | `int64_t`              | `sizeof(T)` (0 if not registered) |

Registered via the `TVMFFITypeRegisterMetadata` C API function.
Duplicate registration throws `RuntimeError` (`a5a08b2`).

### Pointer-based ancestor arrays

`TVMFFITypeInfo::type_acenstors` was changed from `const int32_t*` (array of
type indices) to `const struct TVMFFITypeInfo**` (array of direct pointers) in
`837800e`. This eliminates a table lookup per ancestor when iterating parent
type fields, enabling O(1) access to ancestor metadata.

### Field iteration

Two iteration functions are provided in `reflection.h`:

- `ForEachFieldInfo(type_info, callback)` -- Iterates all fields of a type and
  its ancestors (parent-to-child order, skipping the root Object), calling
  `callback(const TVMFFIFieldInfo*)` for each. A `static_assert` enforces that
  the callback returns `void` (`69f2484`).

- `ForEachFieldInfoWithEarlyStop(type_info, callback)` -- Same iteration but
  the callback returns `bool`; iteration stops and the function returns `true`
  when the callback returns `true`. Added in `69f2484` as a bridge for migrating
  `VisitAttrs`-style search-and-stop patterns.

### VisitAttrs migration strategy

The legacy `VisitAttrs` pattern required each object class to implement a
virtual `VisitAttrs(AttrVisitor*)` method, with visitors that could stop early.
The new reflection mechanism replaces this with declarative field registration
via `ObjectDef<T>`.

The migration is designed to be gradual:
1. `ForEachFieldInfoWithEarlyStop` (`69f2484`) provides the search-and-stop
   bridge so that code consuming `VisitAttrs` can be ported to consume
   `ForEachFieldInfo` incrementally.
2. `def_ro`/`def_rw` accept base-class pointers (`f7311e4`) so derived classes
   can register inherited fields without refactoring the base class.
3. `TypeTraits<Enum>` specialization (`f7311e4`) ensures enum fields (common in
   TIR nodes) can be stored/retrieved via `Any` as `int64_t`.

### GlobalDef for function registration (July 2025)

`reflection::GlobalDef` (`b333288`) is a builder class that mirrors the
`ObjectDef` API for registering global functions. It provides:

```cpp
GlobalDef()
    .def("func.name", typed_function)        // typed function
    .def_packed("func.name", packed_func)    // packed function
    .def_method<Class>("method.name", &Class::method);  // method
```

All internal function registrations (`container.cc`, `function.cc`, `ndarray.cc`,
`object.cc`, `testing.cc`) were migrated from `TVM_FFI_REGISTER_GLOBAL` to
`GlobalDef` inside `TVM_FFI_STATIC_INIT_BLOCK` blocks (`b333288`). The
`TVM_FFI_REGISTER_GLOBAL` macro and `Function::Registry` class were subsequently
removed (`26b68b0`).

Duplicate global function registration now produces a descriptive error message
via `TVM_FFI_LOG_AND_THROW` (`5b0cceb`).

### ObjectCreator for reflection-based deserialization (August 2025)

`reflection::ObjectCreator` (`7cb9273`) is a helper class that constructs
objects from a type key and a `Map<String, Any>` of field values using the
reflection registry. It is defined in `include/tvm/ffi/reflection/creator.h`.

```cpp
reflection::ObjectCreator creator(type_key);
Any result = creator(fields_map);
```

Internally, `ObjectCreator` calls the type's `metadata->creator`, then iterates
fields via `ForEachFieldInfo` to apply setters, handles defaults for missing
fields, and reports errors for extra/missing fields. This replaced ad-hoc
`getattr`-style attribute setting in the JSONGraph deserializer.

### AccessPath tree refactor (August 2025)

`AccessPath` was refactored (`f4ede98`) from a flat `Array<AccessStep>` typedef
to a first-class `ObjectRef` wrapping `AccessPathObj` with `parent`, `step`,
and `depth` fields. The new parent-pointing tree structure is more compact when
multiple paths share a common prefix (e.g., structural equality mismatch
reporting).

API changes:
- `AccessPath({step1, step2})` replaced by `AccessPath::FromSteps({step1, step2})`
- `AccessKind::kObjectField` renamed to `AccessKind::kAttr`; `kAttrMissing` added
- `AccessStep::ObjectField()` renamed to `AccessStep::Attr()`
- New builder methods: `Root()`, `Attr()`, `AttrMissing()`, `ArrayItem()`,
  `MapItem()`, `Extend()`, `ToSteps()`, `PathEqual()`, `IsPrefixOf()`,
  `GetParent()`, `FromSteps()`

The `src/ffi/reflection/access_path.cc` file was deleted; reflection-related
global registrations (`MakeObjectFromPackedArgs`, AccessStep/AccessPath
reflection) were moved to `src/ffi/extra/reflection_extra.cc`, gated behind
`TVM_FFI_USE_EXTRA_CXX_API` (`f4ede98`).

`ObjectPath` was deprecated in favor of `AccessPath` (`ed56a5e`). The
`tvm::Tuple` namespace alias was also removed in the same commit.

### Reflection module split (July 2025)

The monolithic `include/tvm/ffi/reflection/reflection.h` was split (`e95b43b`)
into two headers:

- **`registry.h`** -- Registration-time APIs: `ObjectDef<T>`, `GlobalDef`,
  `TypeAttrDef<Class>`, `EnsureTypeAttrColumn`.
- **`accessor.h`** -- Runtime accessor utilities: `GetFieldInfo`, `FieldGetter`,
  `FieldSetter`, `GetMethodInfo`, `GetMethod`, `ForEachFieldInfo`,
  `ForEachFieldInfoWithEarlyStop`, `TypeAttrColumn`.

This split reduces compile-time coupling by allowing consumers to include only
the header they need.

### TypeAttrDef: extensible per-type attributes (July 2025)

`TypeAttrDef<Class>` (`9445fe7`, `162d600`) is a builder class for registering
per-type function or constant attributes in a column-store pattern:

```cpp
TypeAttrDef<MyObj>()
    .def("__s_equal__", &MyObj::SEqual)    // function attribute
    .attr("my_constant", some_value);       // constant attribute
```

The values are stored in `TVMFFITypeAttrColumn` arrays indexed by type index
and accessible at runtime via `TypeAttrColumn` (in `accessor.h`):

```cpp
TypeAttrColumn col = TypeAttrColumn::Get("__s_equal__");
auto* func = col.GetOr<Function>(type_index);
```

This mechanism is used to register custom structural equal/hash functions per
type without modifying the fixed `TVMFFITypeMetadata` struct.

### Type-level metadata naming

`TVMFFITypeExtraInfo` was renamed to `TVMFFITypeMetadata` and
`TVMFFITypeRegisterExtraInfo` was renamed to `TVMFFITypeRegisterMetadata`
(`9445fe7`, `162d600`). All internal references to `extra_info` were updated
to `metadata`.

### Static initialization

`TVM_FFI_STATIC_INIT_BLOCK` and `TVM_FFI_STATIC_INIT_BLOCK_VAR_DEF` macros
(`a419ed1`) provide portable static initialization for registration blocks.
These are used to register module info and type metadata at startup.

The `TVM_FFI_STATIC_INIT_BLOCK` syntax was updated from block-style to
function-style `() { ... }` (`7b813f8`). Downstream code using the old
syntax must update to the new form.

### `reflection::init<>` constructor helper (September-October 2025)

`tvm_ffi::reflection::init<ObjectType, Args...>` (`c01dadf`) was originally
a concise free-function helper for registering `__ffi_init__` constructors
via `ObjectDef`, replacing the verbose lambda pattern.

In October 2025, the API was refactored (`fc2630f`) to align with the
pybind11/nanobind `py::init<Args...>()` convention:

- The old free-function `refl::init<T, Args...>` was removed (breaking).
- A new `struct init<Args...>` was introduced with a private
  `execute<Class>(args...)` static method.
- A new `ObjectDef::def(init<Args...>(), Extra...)` overload was added
  that registers the constructor as `__ffi_init__`.

**Before (September 2025):**
```cpp
ObjectDef<MyObj>("my.MyObj", MyObj_TypeInfo)
    .def_static("__ffi_init__", reflection::init<MyObj, int64_t, String>);
```

**After (October 2025, `fc2630f`):**
```cpp
ObjectDef<MyObj>("my.MyObj", MyObj_TypeInfo)
    .def(refl::init<int64_t, String>());
```

The class type `T` is no longer needed as a template parameter since it is
inferred from the `ObjectDef<T>` context. The `kInitMethodName` constant
(`"__ffi_init__"`) was also introduced.

This was introduced alongside the `__ffi_init__` naming convention
(replacing `__create__`), which the Python-side `c_class` decorator
depends on.

### Python-side TypeInfo metadata (September 2025)

`TypeInfo`, `TypeField`, and `TypeMethod` Python dataclasses were introduced
(`53b2e00`), backed by Cython, making C++ type reflection data accessible
as pure Python objects. The `OBJECT_TYPE` list was replaced by
`TYPE_INDEX_TO_INFO` and `TYPE_KEY_TO_INFO` dicts keyed by `TypeInfo`.
`_register_object_by_index` was updated to return a `TypeInfo` instead of
`None`. `_lookup_type_info_from_type_key` was added for introspection
without requiring a Python class.

Class attribute attachment was moved from Cython
(`_add_class_attrs_by_reflection`) to Python-side `_add_class_attrs` in
`registry.py`, using `TypeField.as_property` and `TypeMethod.as_callable`
helpers.

### `@c_class` decorator (September 2025)

`tvm_ffi.dataclasses.c_class` (`e98b94e`) is a Python decorator that allows
classes to mirror C++ FFI types with dataclass-like syntax. Annotated fields
become properties backed by the C++ object, and an `__init__` is
auto-generated from the reflected constructor signature. It supports
inheritance, default values via `field(default=...)` / `field(default_factory=...)`,
`field(init=False)` (`daeb235`), and `__post_init__` hooks.

The decorator depends on:
- The `__ffi_init__` method on `Object` (added to Cython in `e98b94e`)
- The `reflection::init<>` C++ helper (registered constructors)
- The `TypeInfo` Python metadata (for field/method introspection)

The `@c_class` decorator was further enhanced in January 2026:
- `repr=True` parameter and `field(repr=True)` were added (`360648f`) for
  auto-generated `__repr__` methods (format: `ClassName(field=value, ...)`).
  Fields marked `repr=False` are excluded.
- `kw_only` parameter and `KW_ONLY` sentinel were added (`3a5bf5e`), mirroring
  `dataclasses.KW_ONLY` behavior (PEP 557). The `kw_only` parameter can be set
  at class level (`c_class(kw_only=True)`) or per-field (`field(kw_only=True)`).

### Auto-creation of Python classes (September 2025)

When an FFI object type has no registered Python class, a stub class is now
auto-generated on first encounter (`98cb8af`) instead of falling back to
bare `Object`. The generated class inherits from the parent's registered
class (recursively created) and exposes all C++ fields and methods from the
reflection registry. This makes TVM FFI "just work" for C++ types that have
not been manually registered in Python.

`TypeInfo` gained a `type_ancestors` list and `parent_type_info` is now
populated automatically via `__post_init__`. The internal typo
`type_acenstors` was corrected to `type_ancestors` throughout C++ and Cython.

### Metadata rename and docstring separation (October 2025)

`TVMFFIFieldInfo.type_schema` and `TVMFFIMethodInfo.type_schema` were renamed
to `metadata` (`935a5a0`). The rationale is that the field carries arbitrary
JSON, not just type schemas. Simultaneously, `ModuleObj::GetFunctionDoc` was
added as a virtual method to separate unstructured docstrings from structured
metadata. `ffi.ModuleGetFunctionDoc` was registered as a global function.

This is an ABI-breaking change for any C code reading `TVMFFIFieldInfo` or
`TVMFFIMethodInfo` directly.

### TypeSchema template (October 2025)

`TypeSchema<T>` (`28fe3cc`) is a compile-time template that generates a
JSON-based type schema string for any FFI type. Specializations were added
across all container headers (`array.h`, `map.h`, `tuple.h`, `variant.h`,
`tensor.h`, `dtype.h`, `rvalue_ref.h`, `type_traits.h`, `base_details.h`).

The `Metadata{{...}}` builder was added to `ObjectDef` and `GlobalDef`,
allowing arbitrary key-value pairs to be attached to registered fields,
methods, and global functions. The metadata is serialized as JSON in the
`metadata` field of `TVMFFIFieldInfo`/`TVMFFIMethodInfo`.

Python-side: `tvm_ffi.get_global_func_metadata(name)` returns metadata as
`dict[str, Any]`; `TypeField.metadata` and `TypeMethod.metadata` properties
expose field/method metadata; `TypeSchema` Python class parses JSON schemas.

### Explicit object type registration (October 2025)

The static `_register_type_index` auto-registration from
`TVM_FFI_DECLARE_OBJECT_INFO` was removed (`9ac3121`). Previously, every DLL
that included the header would auto-register the type, causing unnecessary
binary size overhead.

Static built-in types are now explicitly reserved at runtime startup via
`ReserveDepthOneObjectTypeIndex` (called in `src/ffi/object.cc` for
`Str`, `Bytes`, `Error`, `Function`, `Shape`, `Tensor`, `Array`, `Map`,
`Module`, `OpaquePyObject`). Dynamic types must be explicitly registered via
`reflection::ObjectDef<T>()` or `T::_GetOrAllocRuntimeTypeIndex()`.

`StaticTypeKey::kTVMFFIError` was added as a new constant.

### Stub generation tooling (October 2025)

`tvm-ffi-stubgen` (`ea02e64`) is a CLI tool and Python module
(`tvm_ffi.stub.stubgen`) that generates in-place, static type stubs inside
specially-marked comment blocks (`# tvm-ffi-stubgen(begin/end)`) in `.py`/`.pyi`
files. It consumes the metadata from the C++ reflection registry to produce
function signatures (`global/<prefix>` blocks) and field/method signatures
(`object/<type_key>` blocks).

The old hand-written `python/tvm_ffi/_ffi_api.pyi` was deleted and replaced
with a generated stub block in `_ffi_api.py`. Stub blocks were also added to
`testing.py`, `access_path.py`, `module.py`, and the packaging example.

Type annotations can be remapped via `# tvm-ffi-stubgen(ty_map): A -> B`
directives, and files can opt out with `# tvm-ffi-stubgen(skip-file)`.

### TypeAttr Python API (November 2025)

A new C API `TVMFFIGetTypeAttrColumn` and Python binding
`tvm_ffi.core._lookup_type_attr(type_index, attr_key)` (`4edf4f3`) were added
to query arbitrary per-type attributes from Python. The `TVMFFITypeAttrColumn`
struct was exposed in the Cython base declarations. This API infrastructure
enables future stubgen and dataclass features to query type attributes
(e.g., `__repr__`, `__metadata__`) registered on C++ types.

### Registered type key enumeration (November 2025)

`tvm_ffi.registry.get_registered_type_keys()` (`8fcd924`) returns all type
keys registered in the C++ TypeTable. Backed by a new global function
`ffi.GetRegisteredTypeKeys` implemented in C++ returning `Array<String>`.
Primarily used by stub generation tooling to enumerate all C++-registered
object types for complete annotation generation.

### Stubgen staged pipeline refactor (November 2025)

The monolithic `tvm_ffi.stub.stubgen` module (528 lines) was deleted and
replaced (`1af6d9f`) with a modular staged pipeline:

- `file_utils.py`: File parsing and marker detection
- `consts.py`: Directive and format constants
- `codegen.py`: Stub code generation
- `analysis.py`: FFI registry analysis
- `utils.py`: Shared utilities
- `cli.py`: CLI entry point with `--dry-run` and `--verbose` modes

A new `import` directive (`# tvm-ffi-stubgen(begin): import`) auto-generates
required import blocks. A new `__all__` directive (`92e150b`) populates
module-level export lists. These directives were adopted across `_ffi_api.py`,
`access_path.py`, `module.py`, and `testing.py`. The `__all__` generation
was the last component needed before whole-package stub generation.

### Cython module naming (November 2025)

The runtime `__module__` patching workaround (`_update_module()`) was replaced
(`4628f06`) with the proper `--module-name tvm_ffi.core` compile-time Cython
flag. The previous workaround introduced in PR #177 did not work on lower
Python/Cython versions.

### Auto-generated `__init__` on registered objects (October 2025)

Previously, calling `SomeObject(...)` when `__init__` was not defined silently
returned an object with `chandle=None`, causing segfaults on field access.
After `0729193`, `_add_class_attrs()` in `registry.py` now:

1. If `__ffi_init__` exists in reflection, sets `__init__` = `__ffi_init__`
2. Otherwise, injects `__init__invalid` that raises `RuntimeError`

This makes construction errors explicit and immediate. Subclasses that manually
define `__init__` are unaffected.

### Dynamic-style overload dispatch (December 2025)

`include/tvm/ffi/reflection/overload.h` (`84c5bdb`, 503 lines) provides
dynamic-style multiple dispatch for FFI object types:

- `OverloadBase`: base class for overload definitions.
- `TypedOverload<Ret, Args...>`: type-dispatched overload with compile-time
  signature matching.
- `OverloadDispatcher`: runtime dispatch table that selects the overload
  based on argument types.
- `OverloadObjectDef<Class>`: builder for registering overloaded methods on
  a class.

`Function::FromPackedInplace<TCallable>(args...)` was added as a static
method returning `std::tuple<Function, TCallable*>`, supporting the overload
machinery by allowing the function object to hold a pointer back to its
captured callable. `FunctionObjImpl` was generalized to use perfect
forwarding (single variadic template constructor, copy deleted).
`FunctionObjImpl::GetCallable()` was added as an accessor.

### DefaultFactory for mutable defaults (February 2026)

`reflection::DefaultFactory` (`5e564cd`) is a callable `() -> Any` alternative
to `DefaultValue` for field defaults. When a field has a `DefaultFactory`
instead of a `DefaultValue`, the factory function is called per instantiation
to produce a fresh value, preventing aliasing bugs for mutable container
defaults (e.g., `Array`, `Map`, `List`, `Dict`).

The `TVMFFIFieldInfo::default_value` field was renamed to
`default_value_or_factory`, and a new flag `kTVMFFIFieldFlagBitMaskDefaultFromFactory
= 1 << 5` distinguishes factory from value at the C ABI level. A centralized
`SetFieldToDefault()` helper in `accessor.h` handles both cases.

### Deep copy infrastructure (February 2026)

A memoized deep copy engine (`c73d61a`) was added for FFI objects:

- `ObjectDeepCopier` (C++, `src/ffi/extra/deep_copy.cc`) uses an iterative
  queue with memoization to preserve shared references and handle cycles across
  `Array`, `List`, `Map`, and general reflected objects.
- `AutoRegisterCopy()` in `ObjectDef` constructor auto-registers
  `__ffi_shallow_copy__` for copy-constructible types.
- Python-side `_setup_copy_methods()` installs `__copy__`, `__deepcopy__`, and
  `__replace__` on all reflected types; non-copyable types get raising stubs.
- `ffi.DeepCopy` is registered as a global function.

### Unified repr system (February 2026)

`ffi.ReprPrint` (`b648c5d`) provides DFS-based repr for all FFI values:

- `ReprPrinter` uses 3-state DFS (NotVisited/InProgress/Done) for cycle
  detection and DAG memoization.
- Per-type customization via `__ffi_repr__` type attribute.
- Per-field exclusion via `Repr(false)` InfoTrait.
- `kTVMFFIFieldFlagBitMaskReprOff = 1 << 6` flag in C ABI.
- All Python `__repr__` methods delegate to this function.
- The `repr` parameter was removed from `field()` and `c_class()`.
- Array repr format changed from `[...]` to `(...)` (tuple-style).

### Slots enforcement on FFI objects (February 2026)

`__slots__ = ()` is now enforced (`83daf69`) on all Cython-defined FFI object
subclasses (`Object`, `Function`, `Tensor`, `Device`, `DType`, `Module`,
`Error`, and derived types). This prevents accidental Python-side attribute
creation on C++-backed objects. See ADR 018 for rationale.

### Function constructor (February 2026)

`Function.__init__` (`ecc7471`) allows creating a `tvm_ffi.Function` directly
from a Python callable or an existing `Function` instance. Previously,
`Function` objects could only be obtained via the global registry or C++ return
values.

### Stubgen package generation (December 2025)

`tvm-ffi-stubgen` gained `--init-pypkg`, `--init-lib`, and `--init-prefix`
flags (`b58c2e3`) for one-command bootstrapping of `_ffi_api.py` and
`__init__.py` for new downstream packages. The CLI was rewritten
(`stub/cli.py`, `stub/codegen.py`, `stub/consts.py`, `stub/file_utils.py`);
`stub/analysis.py` was removed; `stub/lib_state.py` was added to
encapsulate loaded library state. The `tvm_ffi.testing` package was updated
to use the new stub infrastructure.

### Schema support for ObjectRef::MemFn (October 2025)

`TypeSchema` was extended (`7b57a46`) to handle `ObjectRef::MemFn` (member
function pointers), enabling schema generation for method signatures.

## APIs

### C API

```c
// Register type-level metadata (doc, creator, total_size).
TVM_FFI_DLL int TVMFFITypeRegisterMetadata(
    int32_t type_index,
    const TVMFFITypeMetadata* metadata);

// Register a per-type attribute value.
TVM_FFI_DLL int TVMFFITypeRegisterAttr(
    int32_t type_index,
    const TVMFFIByteArray* attr_name,
    const TVMFFIAny* attr_value);

// Get a type attribute column by name. Returns NULL if not registered.
TVM_FFI_DLL const TVMFFITypeAttrColumn* TVMFFIGetTypeAttrColumn(
    const TVMFFIByteArray* attr_name);
```

### C++ API

```cpp
// Builder for registering object type metadata.
template <typename Class>
class ObjectDef : public ReflectionDefBase {
  // Register a read-only field. Accepts base-class field pointers.
  template <typename T, typename BaseClass, typename... Extra>
  ObjectDef& def_ro(const char* name, T BaseClass::*field_ptr, Extra&&... extra);

  // Register a read-write field (requires Class::_type_mutable).
  template <typename T, typename BaseClass, typename... Extra>
  ObjectDef& def_rw(const char* name, T BaseClass::*field_ptr, Extra&&... extra);

  // Register a static function.
  template <typename Func, typename... Extra>
  ObjectDef& def_static(const char* name, Func&& func, Extra&&... extra);
};

// Iterate all fields (void callback, no early stop).
template <typename F>
void ForEachFieldInfo(const TypeInfo* type_info, F callback);

// Iterate all fields (bool callback, stops on true).
template <typename F>
bool ForEachFieldInfoWithEarlyStop(const TypeInfo* type_info, F callback);

// Builder for registering global functions.
class GlobalDef {
  template <typename Func>
  GlobalDef& def(const char* name, Func&& func);
  GlobalDef& def_packed(const char* name, Function func);
  template <typename Class, typename Method>
  GlobalDef& def_method(const char* name, Method method);
};

// Builder for registering per-type attributes.
template <typename Class>
class TypeAttrDef {
  template <typename Func>
  TypeAttrDef& def(const char* attr_key, Func&& func);
  template <typename T>
  TypeAttrDef& attr(const char* attr_key, T value);
};

// Runtime accessor for per-type attribute columns.
class TypeAttrColumn {
  static TypeAttrColumn Get(const char* attr_key);
  template <typename T>
  const T* GetOr(int32_t type_index) const;
};
```

### Overload dispatch (December 2025)

```cpp
// Dynamic-style overload dispatch (include/tvm/ffi/reflection/overload.h).
template <typename Class>
class OverloadObjectDef {
  // Register an overloaded method on Class.
  template <typename Ret, typename... Args>
  OverloadObjectDef& def(const char* name, Ret (*func)(Args...));
};

// Construct a Function that owns its callable, returning a pointer to it.
template <typename TCallable, typename... Args>
static std::tuple<Function, TCallable*> Function::FromPackedInplace(Args&&... args);
```

### Constructor registration helper

```cpp
// Concise constructor registration (October 2025, fc2630f).
template <typename... Args>
struct init {
  // Privately calls make_object<Class>(args...) when used with ObjectDef::def().
};

// Usage:
ObjectDef<MyObj>("my.MyObj", MyObj_TypeInfo)
    .def(refl::init<int64_t, String>());
```

### Python API (September 2025)

```python
from tvm_ffi.dataclasses import c_class, field

@c_class("my.MyObj")
class MyObj(tvm_ffi.Object):
    name: str
    count: int = field(default=0)
```

### Macros

```cpp
TVM_FFI_STATIC_INIT_BLOCK(name) () { /* init code */ }
TVM_FFI_STATIC_INIT_BLOCK_VAR_DEF(name)
```

## Implementation

Key files:
- `include/tvm/ffi/c_api.h` -- `TVMFFIFieldInfo`, `TVMFFIMethodInfo`, `TVMFFITypeMetadata`, `TVMFFITypeAttrColumn`, `TVMFFIFieldFlagBitMask`, `TVMFFITypeRegisterMetadata`, `TVMFFITypeRegisterAttr`, `TVMFFIGetTypeAttrColumn`
- `include/tvm/ffi/reflection/registry.h` -- `ReflectionDefBase`, `ObjectDef<T>`, `GlobalDef`, `TypeAttrDef<Class>`, `EnsureTypeAttrColumn`
- `include/tvm/ffi/reflection/accessor.h` -- `GetFieldInfo`, `FieldGetter`, `FieldSetter`, `GetMethod`, `ForEachFieldInfo`, `ForEachFieldInfoWithEarlyStop`, `TypeAttrColumn`
- `include/tvm/ffi/reflection/access_path.h` -- `AccessPathObj`, `AccessPath`, `AccessStep`, `AccessPathPair`
- `include/tvm/ffi/reflection/creator.h` -- `reflection::ObjectCreator`
- `include/tvm/ffi/base_details.h` -- `TVM_FFI_STATIC_INIT_BLOCK` macros
- `src/ffi/object.cc` -- `TypeTable::RegisterTypeMetadata`, `RegisterTypeAttr`, `GetTypeAttrColumn`, Python reflection helpers
- `src/ffi/extra/reflection_extra.cc` -- `MakeObjectFromPackedArgs`, AccessStep/AccessPath reflection registrations (moved from `src/ffi/reflection/access_path.cc` and `src/ffi/object.cc` in `f4ede98`)
- `src/ffi/function.cc` -- Module info registration via static init
- `src/ffi/extra/testing.cc` -- Test objects for reflection scenarios (moved from `src/ffi/testing.cc` in `023ea44`)

Tests:
- `tests/cpp/test_reflection_accessor.cc` -- Field access, TypeAttrColumn tests
- `tests/cpp/testing_object.h` -- Test object definitions with reflection and TypeAttrDef registrations

## History
- 2025-06-15: `TVMFFIFieldInfo` expanded with metadata; `ReflectionDef` gained `def_static` (`1a85688`)
- 2025-06-16: `TVMFFITypeExtraInfo`/`TVMFFITypeRegisterExtraInfo` added; `TVM_FFI_BUILD_REGISTRY` removed; static init macros added (`a419ed1`)
- 2025-06-17: `ReflectionDef` refactored into `ReflectionDefBase` + `ObjectDef`; Python reflection registration implemented (`e909486`)
- 2025-06-19: `type_acenstors` changed to pointer-based; `ForEachFieldInfo` parent iteration overloads added (`837800e`)
- 2025-06-25: `ForEachFieldInfoWithEarlyStop` added as VisitAttrs migration bridge (`69f2484`)
- 2025-06-27: Duplicate registration guard added; `DLDataType` padding fix (`a5a08b2`)
- 2025-06-27: `def_ro`/`def_rw` extended for base-class fields; `TypeTraits<Enum>` added (`f7311e4`)
- 2025-07-03: `reflection::GlobalDef` introduced for function registration (`b333288`)
- 2025-07-14: `reflection.h` split into `registry.h` + `accessor.h` (`e95b43b`)
- 2025-07-15: `TVM_FFI_REGISTER_GLOBAL` macro and `Function::Registry` removed (`26b68b0`)
- 2025-07-19: `TypeAttrDef`, `TypeAttrColumn`, `AccessPath` introduced; `TVMFFITypeExtraInfo` renamed to `TVMFFITypeMetadata`; `StructuralEqual`/`StructuralHash` added to reflection (`9445fe7`)
- 2025-07-22: `TVMFFITypeRegisterExtraInfo` renamed to `TVMFFITypeRegisterMetadata`; `TypeAttrDef`/`TypeAttrColumn` C++ APIs formalized (`162d600`)
- 2025-07-26: Custom `__s_equal__`/`__s_hash__` via `TypeAttrDef` enabled (`2ec11f5`)
- 2025-07-30: `StructuralEqual`/`StructuralHash` moved to `ffi/extra/` namespace and directory (`3fc0391`)
- 2025-08-05: `reflection::ObjectCreator` added for reflection-based object construction (`7cb9273`)
- 2025-08-06: `AccessPath` refactored to parent-pointing tree; `kObjectField` renamed to `kAttr`; reflection extras moved to `src/ffi/extra/` (`f4ede98`)
- 2025-08-06: `ObjectPath` deprecated in favor of `AccessPath`; `tvm::Tuple` alias removed (`ed56a5e`)
- 2025-08-20: `testing.cc` moved to extra layer; env API symbols renamed (`023ea44`)
- 2025-09-13: `TVM_FFI_STATIC_INIT_BLOCK` syntax updated to function style (`7b813f8`)
- 2025-09-19: Python-side `TypeInfo`, `TypeField`, `TypeMethod` dataclasses introduced (`53b2e00`)
- 2025-09-21: `reflection::init<T, Args...>` constructor helper added; `__ffi_init__` convention established (`c01dadf`)
- 2025-09-21: `@c_class` decorator introduced for dataclass-like Python/C++ class mirroring (`e98b94e`)
- 2025-09-24: `field(init=...)` support added to `@c_class` (`daeb235`)
- 2025-09-25: Auto-creation of Python classes for unregistered FFI types (`98cb8af`)
- 2025-09-25: `type_acenstors` typo corrected to `type_ancestors` (`98cb8af`)
- 2025-10-01: `TVMFFIFieldInfo.type_schema` and `TVMFFIMethodInfo.type_schema` renamed to `metadata`; `ModuleObj::GetFunctionDoc` added (`935a5a0`)
- 2025-10-03: `TypeSchema<T>` template and `Metadata{{...}}` builder for JSON-based type schemas; `tvm_ffi.get_global_func_metadata()` Python API (`28fe3cc`)
- 2025-10-07: `self` parameter fix in member function schemas (`368af82`)
- 2025-10-07: `tvm_ffi.dtype` used instead of `DataType` in schemas (`c046b17`)
- 2025-10-08: `TypeSchema.repr(ty_map)` for flexible type representation (`dd4fb0a`)
- 2025-10-12: `tvm-ffi-stubgen` CLI tool and `tvm_ffi.stub.stubgen` module for inline stub generation (`ea02e64`)
- 2025-10-13: Auto-extraction of type annotations from function definitions in docs (`17ff30b`)
- 2025-10-14: `ObjectRef::MemFn` schema support added (`7b57a46`)
- 2025-10-14: Static `_register_type_index` auto-registration removed; explicit `ReserveDepthOneObjectTypeIndex` for built-in types (`9ac3121`)
- 2025-10-15: `refl::init<Args...>` struct replaces `refl::init<T, Args...>` free function; `ObjectDef::def(init<Args...>())` pattern (`fc2630f`)
- 2025-10-19: Auto-generated `__init__` on registered objects prevents silent segfaults (`0729193`)
- 2025-11-08: `_lookup_type_attr` Python API for querying per-type attributes (`4edf4f3`)
- 2025-11-09: Cython module naming fixed with `--module-name` compile-time flag (`4628f06`)
- 2025-11-09: `get_registered_type_keys()` API for type key enumeration (`8fcd924`)
- 2025-11-15: Stubgen refactored into staged pipeline with `import` directive (`1af6d9f`)
- 2025-11-16: Stubgen `__all__` generation for proper exporting (`92e150b`)
- 2025-12-18: Stubgen `--init-pypkg`, `--init-lib`, `--init-prefix` flags for package scaffolding; `stub/analysis.py` removed, `stub/lib_state.py` added (`b58c2e3`)
- 2025-12-23: Dynamic-style overload dispatch: `overload.h`, `OverloadObjectDef`, `TypedOverload`, `OverloadDispatcher`; `Function::FromPackedInplace`; `FunctionObjImpl` made non-copyable (`84c5bdb`)
- 2026-01-10: `Type2Str<Any&&>` and `Type2Str<AnyView&&>` specializations added so `refl::init<Any>()` / `refl::init<AnyView>()` compile correctly (`38914fa`)
- 2026-01-18: `c_class(repr=True)` and `field(repr=True)` added; auto-generated `__repr__` for `@c_class` dataclasses (`360648f`)
- 2026-01-18: `c_class(kw_only=True)`, `field(kw_only=True)`, and `KW_ONLY` sentinel added for keyword-only field support (`3a5bf5e`)
- 2026-02-13: `__copy__`, `__deepcopy__`, `__replace__` added to all reflected FFI objects; `AutoRegisterCopy()` in `ObjectDef`; `DeepCopy` C++ engine with memoized graph copy (`c73d61a`)
- 2026-02-14: `DefaultFactory` reflection trait added for mutable default avoidance; `TVMFFIFieldInfo::default_value` renamed to `default_value_or_factory`; `kTVMFFIFieldFlagBitMaskDefaultFromFactory = 1 << 5` (`5e564cd`)
- 2026-02-15: `MISSING` singleton moved from `container.py` to `core.pyx`; `ffi.MapGetMissingObject` renamed to `ffi.GetInvalidObject` (`86c4042`)
- 2026-02-18: DFS-based `ffi.ReprPrint` introduced for unified object repr; `Repr` InfoTrait and `kTVMFFIFieldFlagBitMaskReprOff = 1 << 6` added; Python repr code-gen removed from dataclasses; Array repr format changed from `[...]` to `(...)` (`b648c5d`)
- 2026-02-21: `__slots__ = ()` enforced on all Cython-defined FFI object subclasses (`83daf69`)
- 2026-02-21: `Function.__init__` constructor added, accepting Python callables or existing `Function` objects (`ecc7471`)
- 2026-02-21: TypeSchema emits distinct container origins (`Array`, `List`, `Map`, `Dict`) for accurate stub generation (`7786133`)

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-06-27-1C9B17A-F7311E4.md`
  - `.repo-knowledge/ranges/2025-07-31-0966C36-0342D85.md`
  - `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
  - `.repo-knowledge/ranges/2025-09-30-CA9C3D1-F9179EC.md`
  - `.repo-knowledge/ranges/2025-10-31-FFA2DBF-BC0D225.md`
  - `.repo-knowledge/ranges/2025-11-30-0EE6444-4076EF5.md`
  - `.repo-knowledge/ranges/2025-12-29-5A82940-6E7CAFA.md`
  - `.repo-knowledge/ranges/2026-01-30-C51E519-B508698.md`
  - `.repo-knowledge/ranges/2026-02-21-B1611E0-ECC7471.md`
- Related ADRs:
  - `.repo-knowledge/adr/003-visitattrs-to-reflection-migration.md`
  - `.repo-knowledge/adr/004-globaldef-replaces-register-global.md`
  - `.repo-knowledge/adr/010-c-class-decorator.md`
  - `.repo-knowledge/adr/018-slots-enforcement-ffi-objects.md`
- Related design docs: `.repo-knowledge/design/005-structural-equal-hash.md`, `.repo-knowledge/design/006-serialization-system.md`, `.repo-knowledge/design/011-mutable-containers.md`
