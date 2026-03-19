---
status: "active"
confidence: "high"
---
# Reflection System

**TL;DR**.
- The reflection system enables runtime access to object fields, methods, and per-type attributes via string names. It powers Python property access, serialization, generic object construction, and structural equality/hashing.
- `reflection::ObjectDef<T>` is the fluent builder for registering field/method accessors on Object types. `reflection::GlobalDef` is its counterpart for global function registration. Both inherit from `ReflectionDefBase` and register at static init time via `TVM_FFI_STATIC_INIT_BLOCK`.
- `reflection::TypeAttrDef<T>` registers per-type named attributes (functions or constants) in column-oriented storage, enabling extensible per-type metadata (e.g., custom structural equal/hash functions via `__s_equal__`/`__s_hash__`).
- Field access at runtime: type_key -> type_index -> TVMFFITypeInfo -> field_info -> offset + getter/setter. Headers split: `reflection/registry.h` (registration) and `reflection/accessor.h` (runtime access).

## Problem Statement

### Background
- Python and other dynamic languages need to access C++-defined object fields by name.
- Serialization and generic object construction need field enumeration without compile-time knowledge.
- Global function registration needs metadata beyond just the function pointer (docstrings, type schemas).
- C++ has no built-in runtime reflection. Metadata must be explicitly registered.

### Solution
- `TVMFFIFieldInfo` stores field access metadata: name, docstring, flags bitmask, offset from Object pointer, getter/setter function pointers, default value, size, alignment, and type_schema.
- `ObjectDef<T>` computes byte offsets from C++ member pointers and generates type-safe getter/setter functions. Also auto-registers type metadata (size, creator, doc) via `TVMFFITypeRegisterMetadata`.
- `GlobalDef` registers global functions with full metadata via `TVMFFIFunctionSetGlobalFromMethodInfo`, replacing the removed `TVM_FFI_REGISTER_GLOBAL` macro.
- `TypeAttrDef<T>` registers per-type named attributes in column storage for extensible metadata.

### Goals
- Runtime field and method access by string name with type-safe conversion.
- Byte-offset-based field location for efficient access.
- Read-only/read-write fields with `_type_mutable` enforcement.
- Generic object construction from packed arguments (`ffi.MakeObjectFromPackedArgs`).
- Per-type extensible attributes via TypeAttr column storage.
- Non-goal: schema generation. (Serialization is now supported via `ToJSONGraph`/`FromJSONGraph` in `ffi/extra/serialization.h`, which uses reflection to walk object fields automatically -- see design record 0010.)

## Design

```mermaid
sequenceDiagram
    participant Init as TVM_FFI_STATIC_INIT_BLOCK
    participant ODef as ObjectDef&lt;T&gt;
    participant CAPI as TVMFFITypeRegisterField
    participant Meta as TVMFFITypeRegisterMetadata
    participant TypeTable as Global Type Table
    participant Python as Python Binding
    participant Getter as FieldGetter

    Init->>ODef: ObjectDef&lt;T&gt;() (registers metadata)
    ODef->>Meta: TVMFFITypeRegisterMetadata(type_index, size, creator, doc)
    ODef->>ODef: .def_rw("name", &T::name, ...)
    ODef->>ODef: compute offset, create getter/setter
    ODef->>CAPI: TVMFFITypeRegisterField(type_index, &info)
    CAPI->>TypeTable: store TVMFFIFieldInfo in TVMFFITypeInfo

    Python->>TypeTable: TVMFFIGetTypeInfo(type_index)
    TypeTable-->>Python: TVMFFITypeInfo with fields[], methods[], metadata
    Python->>Python: find field by name, get offset
    Python->>Getter: getter(obj_ptr + offset, &result)
    Getter-->>Python: result (as TVMFFIAny)
```

### Key Classes, Fields and Interfaces

```python
class ReflectionDefBase:
    """Base class with shared getter/setter/method helpers."""
    # Provides: FieldGetter<T>, FieldSetter<T>, ObjectCreatorDefault<T>,
    #   GetMethod (dispatches ObjectRef by-value vs Object by-const-ptr)
    # Interacts with: ObjectDef, GlobalDef, TypeAttrDef, Function.FromTyped

class ObjectDef(ReflectionDefBase, Generic[Class]):
    """Templatized fluent builder for registering type reflection metadata.
    Since 9ac3121, this is also the mandatory registration path for dynamic object types --
    the macro declarations no longer trigger registration via static inline variables."""
    type_index_: int32  # from Class::_GetOrAllocRuntimeTypeIndex()
    type_key_: str      # from Class::_type_key

    def __init__(self, *extra_args: str) -> None:
        """Register type index, type key, AND metadata (size, creator, doc)."""
        # Calls TVMFFITypeRegisterMetadata with total_size, creator, doc
        # Invariant: Class must have _GetOrAllocRuntimeTypeIndex() and _type_key
        # Invariant: without ObjectDef (or explicit _GetOrAllocRuntimeTypeIndex()), IsInstance fails (9ac3121)
        # Interacts with: TVMFFITypeRegisterMetadata

    def def_ro(self, name: str, field_ptr: MemberPointer[BaseClass, T], *extra) -> ObjectDef:
        """Register a read-only field. BaseClass must be base of Class."""
        # Invariant: static_assert(is_base_of_v<BaseClass, Class>)
        # Extra args: docstring, DefaultValue, AttachFieldFlag
        # Interacts with: TVMFFITypeRegisterField

    def def_rw(self, name: str, field_ptr: MemberPointer[BaseClass, T], *extra) -> ObjectDef:
        """Register a read-write field."""
        # Invariant: static_assert(Class._type_mutable) -- compile error if immutable
        # Interacts with: TVMFFITypeRegisterField

    def def_(self, name: str, func: Callable, *extra) -> ObjectDef:
        """Register an instance method (self is first arg)."""
        # Interacts with: TVMFFITypeRegisterMethod, Function.FromTyped

    def def_(self, init_func: "init[*Args]", *extra) -> ObjectDef:
        """Register a constructor method (__ffi_init__) for this object type. (fc2630f)
        The object type is automatically deduced from the ObjectDef<Class> context,
        eliminating the need to repeat the Class type as a template parameter.
        # Interacts with: init<Args...>::execute<Class>, make_object<Class>, TVMFFITypeRegisterMethod
        # Invariant: registers as static method named kInitMethodName ("__ffi_init__")
        # Replaces: old pattern `.def_static("__ffi_init__", refl::init<T, Args...>)`
        """
        ...

    def def_static(self, name: str, func: Callable, *extra) -> ObjectDef:
        """Register a static method."""
        # Interacts with: TVMFFITypeRegisterMethod

class init(Generic[*Args]):
    """Struct template helper for constructor registration via ObjectDef::def(). (fc2630f)
    The object type is automatically deduced from the ObjectDef<Class> context.
    Replaces the old free function `reflection::init<T, Args...>` (which required
    the Class type as an explicit template parameter).
    # Interacts with: ObjectDef.def(), make_object<Class>
    # Invariant: Args must match a valid constructor of the Class type
    """
    kInitMethodName: ClassVar[str] = "__ffi_init__"

class refl_compare:    # refl::compare(bool include)
    """Controls field participation in RecursiveEq/Lt/etc. Sets CompareOff flag (bit 7)."""
    # Interacts with: TVMFFIFieldInfo.flags, RecursiveComparer dispatch (0009)

class refl_hash:       # refl::hash(bool include)
    """Controls field participation in RecursiveHash. Sets HashOff flag (bit 8)."""
    # Interacts with: TVMFFIFieldInfo.flags, RecursiveHasher dispatch (0009)

class refl_init_field:  # refl::init(false) as field trait
    """Excludes field from auto-generated __ffi_init__. Sets InitOff flag (bit 9)."""
    # Interacts with: MakeInit, _make_init_signature (Python)

class refl_kw_only:    # refl::kw_only(bool)
    """Marks field as keyword-only in auto-generated __ffi_init__. Sets KwOnly flag (bit 10)."""
    # Interacts with: MakeInit, _make_init_signature (Python)

class refl_repr:       # refl::repr(bool show)
    """Controls field visibility in ReprPrint. Renamed from refl::Repr in 6b39efb."""
    # Interacts with: ReprPrinter, ObjectGraphDFS

def MakeInit(type_index: int32) -> Function:
    """Build a packed __ffi_init__ from reflection field metadata."""
    # Walks field chain parent-to-child; collects fields where InitOff is not set
    # Positional ordering: required fields first, then fields with HasDefault
    # KwOnly fields placed after KWARGS sentinel
    # Interacts with: TVMFFITypeInfo.metadata.creator, field reflection, KWARGS sentinel
    # Invariant: positional required before positional default before kw-only required before kw-only default

# Python-side auto-init pipeline (b1abaeac):
def _make_init(type_cls: type, type_info: TypeInfo) -> Callable:
    """Build Python __init__ delegating to C++ __ffi_init__ via KWARGS protocol."""
    # Interacts with: core.KWARGS, _make_init_signature

def _make_init_signature(type_info: TypeInfo) -> inspect.Signature:
    """Build inspect.Signature from TypeField.c_init/c_kw_only/c_has_default."""
    # Walks parent chain parent-first; collects fields where c_init=True
    # Interacts with: TypeInfo.parent_type_info, TypeField attributes

def _install_init(cls: type, *, enabled: bool) -> None:
    """Install __init__ from C++ reflection or a TypeError guard."""
    # Checks __ffi_init__ method metadata for auto_init: true
    # If auto_init: uses _make_init; else: wires __ffi_init__ directly
    # Interacts with: TypeInfo.methods, _make_init

class GlobalDef(ReflectionDefBase):
    """Fluent builder for registering global functions with metadata."""

    def def_(self, name: str, func: Callable, *extra) -> GlobalDef:
        """Register a typed global function."""
        # Interacts with: Function.FromTyped, TVMFFIFunctionSetGlobalFromMethodInfo

    def def_packed(self, name: str, func: Callable, *extra) -> GlobalDef:
        """Register in raw packed-args format."""
        # Interacts with: Function.FromPacked

    def def_method(self, name: str, func: MemberPointer, *extra) -> GlobalDef:
        """Expose a class method as a global function."""

class InfoTrait:
    """Base class for traits applied to fields AND methods. (Renamed from FieldInfoTrait in 28fe3cc)"""
    # Subclasses: DefaultValue, AttachFieldFlag, Metadata

class Metadata(InfoTrait):
    """User-supplied metadata (int/bool/string key-value pairs) for fields/methods/global functions. (28fe3cc)"""
    def __init__(self, dict: list[tuple[str, Any]]) -> None: ...
    def Apply(self, info: FieldInfoBuilder) -> None: ...
    def Apply(self, info: MethodInfoBuilder) -> None: ...
    # Interacts with: FieldInfoBuilder.metadata_, MethodInfoBuilder.metadata_
    # Invariant: ObjectDef/GlobalDef automatically includes "type_schema" in metadata

class FieldInfoBuilder(TVMFFIFieldInfo):
    """Extends TVMFFIFieldInfo with temporary metadata vector during registration. (28fe3cc)"""
    metadata_: list[tuple[String, Any]]

class MethodInfoBuilder(TVMFFIMethodInfo):
    """Extends TVMFFIMethodInfo with temporary metadata vector during registration. (28fe3cc)"""
    metadata_: list[tuple[String, Any]]

class TypeAttrDef(Generic[Class]):
    """Builder for registering per-type named attributes in column storage."""
    def def_(self, name: str, func: Callable) -> TypeAttrDef: ...
        # Interacts with: TVMFFITypeRegisterAttr
    def attr(self, name: str, value: T) -> TypeAttrDef: ...
        # Extension: any type T convertible to AnyView

class TypeAttrColumn:
    """Read-only accessor for a named type attribute column."""
    def __init__(self, attr_name: str) -> None: ...
        # Interacts with: TVMFFIGetTypeAttrColumn
    def __getitem__(self, type_index: int32) -> AnyView: ...
        # Invariant: returns null AnyView for unregistered types

# --- Runtime access helpers (reflection/accessor.h) ---

def GetFieldInfo(type_key: str, field_name: str) -> TVMFFIFieldInfo_ptr: ...
def GetMethodInfo(type_key: str, method_name: str) -> TVMFFIMethodInfo_ptr: ...
def GetMethod(type_key: str, method_name: str) -> Function: ...

class FieldGetter:
    """Resolved field getter for repeated access."""
    def __init__(self, type_key: str, field_name: str): ...
    def __call__(self, obj: Object_ptr) -> Any:
        # addr = (char*)obj + field_info_.offset
        # Interacts with: TVMFFIFieldInfo.getter, TVMFFIFieldInfo.offset

class FieldSetter:
    """Resolved field setter for repeated access."""
    def __init__(self, type_key: str, field_name: str): ...
    def __call__(self, obj: Object_ptr, value: AnyView) -> None: ...

def ForEachFieldInfo(type_info: TVMFFITypeInfo_ptr,
                     callback: Callable[[TVMFFIFieldInfo_ptr], None]) -> None:
    """Visit every field including inherited parent fields, parent-to-child order."""
    # Uses pointer-based type_ancestors for direct traversal
    # Invariant: callback must return void (static_assert enforced)

def ForEachFieldInfoWithEarlyStop(type_info: TVMFFITypeInfo_ptr,
                                  callback: Callable[[TVMFFIFieldInfo_ptr], bool]) -> bool:
    """Visit fields with early termination."""

class ObjectCreator:
    """Reflection-based constructor: creates any Object type from a field map."""
    # Lives in: include/tvm/ffi/reflection/creator.h
    # Invariant: type must have reflection registered (TVMFFITypeMetadata.creator != nullptr)
    # Interacts with: TVMFFIGetTypeInfo, ForEachFieldInfo, TVMFFIFieldInfo.setter, ObjectUnsafe

    def __init__(self, type_key: str) -> None:
        """Look up type by key; throws RuntimeError if no reflection or no creator."""
    def __init__(self, type_info: TVMFFITypeInfo_ptr) -> None:
        """Direct init from type_info pointer."""
    def __call__(self, fields: Map[String, Any]) -> Any:
        """Create object, set required fields, apply defaults for optional fields."""
        # Invariant: all fields without kTVMFFIFieldFlagBitMaskHasDefault must be in `fields`
        # Throws TypeError for missing required fields or unknown field names

def MakeObjectFromPackedArgs(args: PackedArgs, ret: Any) -> None:
    """Create object from type_key (str) or type_index (int32) + keyword field args."""
    # Walks ancestor chain parent-to-child setting fields via reflection setters
    # Invariant: all registered fields must be set or have defaults
    # Registered as: "ffi.MakeObjectFromPackedArgs"
    # Note: relocated to src/ffi/extra/reflection_extra.cc (behind TVM_FFI_USE_EXTRA_CXX_API)

# Macro: TVM_FFI_STATIC_INIT_BLOCK() { body }
#   GCC/Clang: __attribute__((constructor)) static void __TVMFFIStaticInitFunc<N>()
#   Non-GCC: static function + [[maybe_unused]] static inline int variable IIFE
#   General-purpose static init block; replaces the removed TVM_FFI_REFLECTION_DEF (7b813f8)
```

### Contracts, Assumptions and Invariants
- **Offset stability**: Byte offsets are computed from C++ class layout at static init time. Changing field order or adding fields to parent classes changes offsets and requires recompilation.
- **Getter/setter exception safety**: Both are wrapped in `TVM_FFI_SAFE_CALL_BEGIN`/`END`, so type conversion errors produce structured Error objects rather than crashes.
- **Mutability enforcement**: `def_rw` enforces `static_assert(Class::_type_mutable)` at compile time. Immutable types can only use `def_ro`.
- **Registration at static init time**: `TVM_FFI_STATIC_INIT_BLOCK` creates a `static inline` variable ensuring registration when the shared library loads. Order between types is unspecified.
- **Flags bitmask**: `TVMFFIFieldInfo.flags` uses `TVMFFIFieldFlagBitMask` bits: Writable (bit 0), HasDefault (bit 1), IsStaticMethod (bit 2), SEqHashIgnore (bit 3), SEqHashDef (bit 4), DefaultFromFactory (bit 5), CompareOff (bit 7), HashOff (bit 8), InitOff (bit 9), KwOnly (bit 10). Bits 7-10 added in `6b39efb`.
- **TypeAttr column uniqueness**: Each (type_index, attr_name) pair can only be registered once. Duplicates throw RuntimeError.
- **Metadata uniqueness**: Each type_index can only have `TVMFFITypeMetadata` registered once.
- **Auto-init generation** (`6b39efb`, `b1abaea`): `ObjectDef<T>` destructor auto-registers `__ffi_init__` when: (1) no explicit `refl::init<Args...>()` was registered, (2) type has a default creator, (3) `init(false)` was NOT passed to ObjectDef constructor. The generated `__ffi_init__` method's metadata includes `auto_init: true`. On the Python side, `_install_init` checks this metadata to decide whether to generate a signature-aware `__init__` (via `_make_init`) or wire `__ffi_init__` directly.
- **KWARGS protocol**: Auto-generated `__ffi_init__` uses a KWARGS sentinel object (obtained via `ffi.GetKwargsObject`) to separate positional from keyword arguments in the packed calling convention. Python `_make_init` appends `core.KWARGS` followed by `key, value, key, value, ...` pairs.
- **FunctionObj setter dispatch** (`4bb487e`): `TVMFFIFieldInfo.setter` is `void*` (was `TVMFFIFieldSetter`). When `kTVMFFIFieldFlagBitSetterIsFunctionObj` (bit 11) is set, `CallFieldSetter` dispatches via `TVMFFIFunctionCall` instead of raw C function pointer, enabling Python-defined field setters.
- **__ffi_new__ fallback** (`e3333e2`): `CreateEmptyObject(type_index)` tries `metadata->creator` first, falls back to `__ffi_new__` TypeAttr. This enables reflection-based creation/serialization/init for Python-defined types that have no C++ creator.
- **__ffi_convert__ dispatch** (`5f5ca5a`): `ObjectDef<T>` auto-registers a `__ffi_convert__` TypeAttr that performs `AnyView -> T` conversion via `CastFromAny`/`CastObjectFromAny`. Used by the Python type converter to dispatch object conversion to C++ instead of reimplementing marshal heuristics in Python.

### Extension Points
- **Method registration**: `ObjectDef.def()` / `def_static()` register methods as Function objects accessible via `GetMethod(type_key, name)`.
- **Custom field types**: Any type with a `TypeTraits` specialization can be a field type.
- **TypeAttr extensibility**: Any subsystem can register per-type attributes without modifying core reflection. Used by structural equal/hash for `__s_equal__`/`__s_hash__` dispatch (see 0009-structural-eq-hash).
- **Generic construction**: `MakeObjectFromPackedArgs` enables Python/Rust to construct any reflected Object type by type key + field name-value pairs.
- **Auto-init customization**: Per-field traits `refl::init(false)`, `refl::kw_only(true)`, `refl::default_value(v)`, `refl::default_factory(fn)` control which fields appear in auto-generated `__ffi_init__` and how. Pass `init(false)` to the `ObjectDef` constructor to suppress auto-init entirely for a type.

### Usage Examples

#### Registering fields, methods, and defaults with ObjectDef
**Context**: The standard pattern for reflecting a mutable C++ object type.
```cpp
class MyNodeObj : public Object {
 public:
  String name;
  int64_t value;
  double Add(double other) const { return value + other; }
  static constexpr bool _type_mutable = true;
  static constexpr const char* _type_key = "test.MyNode";
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("test.MyNode", MyNodeObj, Object);
};

// Registration at static init time
TVM_FFI_STATIC_INIT_BLOCK() {
  namespace refl = tvm::ffi::reflection;
  refl::ObjectDef<MyNodeObj>()
      .def_rw("name", &MyNodeObj::name, "node name", refl::DefaultValue(""))
      .def_rw("value", &MyNodeObj::value, refl::DefaultValue(0))
      .def("Add", &MyNodeObj::Add, "add method");
}

// Runtime field access (as Python binding would do)
refl::FieldGetter getter("test.MyNode", "name");
Any result = getter(node_ptr);  // String("hello")

// Runtime method call
Function add_fn = refl::GetMethod("test.MyNode", "Add");
double sum = add_fn(node_ref, 3.14).cast<double>();

// Generic object construction from packed args
Function make = Function::GetGlobalRequired("ffi.MakeObjectFromPackedArgs");
Any obj = make("test.MyNode", "name", "world", "value", 42);
```

#### Registering global functions with GlobalDef
**Context**: Replacing the removed `TVM_FFI_REGISTER_GLOBAL` macro.
```cpp
TVM_FFI_STATIC_INIT_BLOCK() {
  namespace refl = tvm::ffi::reflection;
  refl::GlobalDef()
      .def("ffi.ArrayGetItem",
           [](const ArrayObj* n, int64_t i) -> Any { return n->at(i); })
      .def_packed("ffi.Array",
                  [](PackedArgs args, Any* ret) {
                    *ret = Array<Any>(args.data(), args.data() + args.size());
                  })
      .def_method("testing.Int_GetValue", &TIntObj::GetValue);
}
```

### Evolution Timeline

| Date | Commit | Change |
|------|--------|--------|
| 2025-05-06 | `7d34eb8` | Initial ReflectionDef with def_readonly/def_readwrite, FieldGetter, byte offset |
| 2025-06-15 | `1a85688` | Rename to pybind-style (def_ro/def_rw), add method registration, flags bitmask, DefaultValue |
| 2025-06-16 | `a419ed1` | Enrich TVMFFIFieldInfo (size, alignment, type_schema), rename to ObjectDef<T> |
| 2025-06-17 | `e909486` | Add ReflectionDefBase, MakeObjectFromPackedArgs, mutability enforcement |
| 2025-06-19 | `837800e` | Pointer-based type_ancestors, ForEachFieldInfo utility |
| 2025-06-25 | `69f2484` | ForEachFieldInfoWithEarlyStop |
| 2025-07-03 | `b333288` | GlobalDef introduced for global function registration |
| 2025-07-14 | `e95b43b` | Split into registry.h (registration) and accessor.h (access) |
| 2025-07-15 | `26b68b0` | Remove Function::Registry and TVM_FFI_REGISTER_GLOBAL |
| 2025-07-19 | `9445fe7` | Structural eq/hash fields and types (SEqHash flags, TVMFFISEqHashKind) |
| 2025-07-22 | `162d600` | TypeAttr column system, rename TVMFFITypeExtraInfo to TVMFFITypeMetadata |
| 2025-08-05 | `7cb9273` | ObjectCreator: reflection-based object construction from Map<String, Any> |
| 2025-08-06 | `f4ede98` | AccessPathObj/AccessStepObj reflection registration; MakeObjectFromPackedArgs relocated to extra |
| 2025-10-03 | `28fe3cc` | InfoTrait rename (was FieldInfoTrait), Metadata class, FieldInfoBuilder/MethodInfoBuilder, auto type_schema in metadata |
| 2025-10-07 | `368af82` | Method schemas now include self (FunctionInfo member pointer fix) |
| 2025-10-08 | `dd4fb0a` | TypeSchema.repr(ty_map) for configurable field/method type display |
| 2025-10-14 | `9ac3121` | ObjectDef mandatory for type index registration (static inline auto-registration removed) |
| 2025-10-15 | `fc2630f` | Struct-based `init<Args...>` via `ObjectDef::def()`, replacing `init<T, Args...>` free function |
| 2026-02-27 | `6b39efb` | Auto-generated `__ffi_init__` from ObjectDef destructor; field traits: refl::compare/hash/init(false), refl::kw_only; field flag bits CompareOff(7)/HashOff(8)/InitOff(9)/KwOnly(10); MakeInit; refl::Repr -> refl::repr rename |
| 2026-02-28 | `b1abaea` | Python auto-init pipeline: `_make_init`, `_make_init_signature`, `_install_init`; TypeField.c_init/c_kw_only/c_has_default; core.KWARGS sentinel; auto_init method metadata |
| 2026-03-04 | `4bb487e` | TVMFFIFieldInfo.setter changed to `void*`; `CallFieldSetter` dispatch; `kTVMFFIFieldFlagBitSetterIsFunctionObj` (bit 11) |
| 2026-03-05 | `e3333e2` | `CreateEmptyObject`/`HasCreator` utilities; `__ffi_new__` TypeAttr fallback; Python `Field` descriptor; TVMFFITypeMetadata layout change |
| 2026-03-08 | `5f5ca5a` | `__ffi_convert__` TypeAttr auto-registered by ObjectDef; `ObjectDef.ref<T>()` for ObjectRef wrappers; `ffi.MakeNew`/`ffi.FunctionFromExternC` |

## Alternatives & Trade-offs
### C++ RTTI / dynamic_cast (rejected)
- Pros: Built-in; no manual registration needed.
- Cons: Only provides type information, not field access; varies across compilers; disabled in many embedded/ML builds.

### Code generation for reflection (e.g., protobuf-style .proto files)
- Pros: Zero runtime overhead; can generate optimized accessors.
- Cons: Requires separate build step; hard to keep in sync with C++ class definitions; breaks single-source-of-truth principle.

## Related Work
### Design Records
- `0002-object-system.md` -- Object is the base class; `_type_mutable` gates writable fields; TVMFFITypeInfo stores metadata
- `0003-function-system.md` -- Function.FromTyped used by method/global registration; GlobalDef replaces TVM_FFI_REGISTER_GLOBAL
- `0005-type-traits-protocol.md` -- TypeTraits powers getter/setter type conversion
- `0007-c-abi.md` -- TVMFFIFieldInfo, TVMFFIMethodInfo, TVMFFITypeMetadata, TVMFFITypeAttrColumn are C ABI definitions
- `0009-structural-eq-hash.md` -- Uses TypeAttrDef for `__s_equal__`/`__s_hash__` custom dispatch

### Evidence Matrix
- ObjectDef builder and method registration -> `commits/2025-06-15-1a856886...md` + `1a85688` + `ObjectDef`, `def_ro`, `def_rw`, `def`
- GlobalDef for global function registration -> `commits/2025-07-03-b333288...md` + `b333288` + `GlobalDef`, `def_packed`, `def_method`
- TypeAttr column system -> `commits/2025-07-22-162d600...md` + `162d600` + `TypeAttrDef`, `TypeAttrColumn`, `TVMFFITypeRegisterAttr`
- MakeObjectFromPackedArgs -> `commits/2025-06-17-e909486...md` + `e909486` + `MakeObjectFromPackedArgs`, `TVMFFITypeMetadata`
- ForEachFieldInfo traversal -> `commits/2025-06-19-837800e...md` + `837800e` + `ForEachFieldInfo`, pointer-based ancestors
- Header split -> `commits/2025-07-14-e95b43b...md` + `e95b43b` + `registry.h`, `accessor.h`
- ObjectCreator -> `commits/2025-08-05-7cb92736...md` + `7cb9273` + `ObjectCreator`, `creator.h`
- Plus 5 supporting commits: `a419ed1` (enrich metadata), `69f2484` (early stop), `26b68b0` (remove Registry), `9445fe7` (SEqHash), `f7311e4` (base-class member ptrs)
- InfoTrait rename, Metadata class, type_schema auto-injection -> `commits/2025-10-03-28fe3cc7...md` + `28fe3cc` + `InfoTrait`, `Metadata`, `FieldInfoBuilder`, `MethodInfoBuilder`
- Method schemas include self, member pointer fix -> `commits/2025-10-07-368af824...md` + `368af82` + `FunctionInfo`, method schema `self`
- TypeSchema.repr(ty_map) for field/method display -> `commits/2025-10-08-dd4fb0ae...md` + `dd4fb0a` + `TypeSchema.repr`, `ty_map`
- ObjectDef now required for type index registration (not just reflection) -> `commits/2025-10-14-9ac31216...md` + `9ac3121` + `ObjectDef`, `ReserveDepthOneObjectTypeIndex`
- Struct-based init<Args...> via ObjectDef::def(), replaces init<T, Args...> free function -> `commits/2025-10-15-fc2630fa...md` + `fc2630f` + `init<Args...>`, `ObjectDef::def(init<...>())`
- Auto-generated __ffi_init__, field traits, flag bits -> `commits/2026-02-27-6b39efbf...md` + `6b39efb` + `MakeInit`, `refl::compare`, `refl::hash`, `refl::init`, `refl::kw_only`
- Python auto-init pipeline (_make_init, _install_init, KWARGS) -> `commits/2026-02-28-b1abaeac...md` + `b1abaea` + `_make_init`, `_install_init`, `core.KWARGS`, `TypeField.c_init`
