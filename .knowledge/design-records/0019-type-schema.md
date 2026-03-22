---
status: "active"
confidence: "high"
---
# Type Schema — Compile-Time Type Annotation and Metadata Pipeline

**TL;DR**
- `TypeSchema<T>` is a C++ compile-time trait that converts any FFI-registered type into a JSON string (e.g., `{"type":"int"}`, `{"type":"ffi.Function","args":[...]}`) — automatically attached as `"type_schema"` in `TVMFFIFieldInfo::metadata` / `TVMFFIMethodInfo::metadata` on every registration.
- `reflection::Metadata{{"key", value}, ...}` is a new `InfoTrait` subclass that lets callers attach arbitrary `int`/`bool`/`String` key-value pairs alongside the auto-generated type schema.
- On the Python side, `TypeSchema` (a frozen-style dataclass) parses JSON schema strings into a structured, printable type annotation with a `repr(ty_map)` extension point for remapping origin names.

## Problem Statement

### Background
Before commit 28fe3cc7, `TVMFFIFieldInfo::metadata` was populated with an empty byte array. Consumers (Python stubs, IDEs, documentation) had no machine-readable type information for registered fields, methods, or global functions.

### Solution
Add `TypeSchemaImpl<T>` — a template specialization chain that maps every FFI-compatible C++ type to a JSON object. The JSON is automatically merged with user-supplied key-value pairs via `reflection::Metadata`, serialized into `TVMFFIFieldInfo.metadata`/`TVMFFIMethodInfo.metadata` at registration time. Python side parses the JSON into `TypeSchema` objects that render as PEP 484 type annotations.

### Goals
- Every registered field, method, and global function carries machine-readable type information with zero user burden.
- User-supplied metadata (doc strings, config flags) co-exists with `"type_schema"` in the same JSON object.
- Python `TypeSchema.repr(ty_map)` enables downstream tools (stub generators, IDEs) to remap concrete types to abstract equivalents.
- Non-goal: runtime type checking or coercion (that is `TypeTraits<T>`'s job).

## Design

### End-to-End Flow

```mermaid
flowchart LR
    A["C++ type T"] -->|"TypeSchemaImpl<T>::v()"| B["JSON string\n{\"type\":\"...\",...}"]
    B -->|merged with user Metadata| C["TVMFFIFieldInfo.metadata\n/ TVMFFIMethodInfo.metadata"]
    C -->|TVMFFIGetGlobalFuncMetadata\n/ field iteration| D["Python: dict[str,Any]"]
    D -->|TypeSchema.from_json_str| E["TypeSchema(origin, args)"]
    E -->|repr(ty_map)| F["'Callable[[int], int]'"]
```

### Key Classes, Fields and Interfaces

```python
# ─── C++ compile-time schema trait ────────────────────────────────────────────

# include/tvm/ffi/base_details.h
# TypeSchema<T> = TypeSchemaImpl<remove_const_t<remove_reference_t<T>>>
template[T]
class TypeSchemaImpl:
    """Forward-declared template; specialized in function_details.h and type_traits.h."""
    @staticmethod
    def v() -> str: ...
    # Returns a JSON object string. Examples:
    #   TypeSchemaImpl<int64_t>::v()  → '{"type":"int"}'
    #   TypeSchemaImpl<bool>::v()     → '{"type":"bool"}'
    #   TypeSchemaImpl<void>::v()     → '{"type":"ffi.None"}'
    #   TypeSchemaImpl<AnyView>::v()  → '{"type":"ffi.AnyView"}'
    #   TypeSchemaImpl<Optional<T>>::v() → '{"type":"Optional","args":[TypeSchema<T>::v()]}'
    #   TypeSchemaImpl<Array<T>>::v() → '{"type":"ffi.Array","args":[TypeSchema<T>::v()]}'
    #   TypeSchemaImpl<FooObj>::v()   → '{"type":"foo.Foo"}'  (uses _type_key)

# include/tvm/ffi/function_details.h
# FuncFunctorImpl<R, Args...>::TypeSchema() composes return + args:
#   '{"type":"ffi.Function","args":[ret_schema, arg0_schema, arg1_schema, ...]}'
# Note: args[0] is the return type; args[1..] are parameter types.
# TypeSchema<void*> → '{"type":"ffi.OpaquePtr"}'
# TypeSchema<DLDataType> → '{"type":"DLDataType"}'

# Every TypeTraits<T> specialization gains a static method (commit 28fe3cc7):
class TypeTraits[T]:
    @staticmethod
    def TypeSchema() -> str:
        return TypeSchemaImpl[T].v()
    # Invariant: always valid JSON; never raises
    # Interacts with: TypeSchemaImpl<T>, FuncFunctorImpl (for function types)


# ─── Metadata InfoTrait subclass ───────────────────────────────────────────────

# include/tvm/ffi/reflection/registry.h
class InfoTrait:
    """Base class for field/method traits (RENAMED from FieldInfoTrait in commit 28fe3cc7).
    # Extension: subclass and implement Apply(FieldInfoBuilder*) / Apply(MethodInfoBuilder*)
    """
    pass

class Metadata(InfoTrait):
    """User-supplied key-value pairs attached to a field, method, or global function.
    Values may be int, bool, or String only. Serialized into the 'metadata' JSON blob
    alongside the auto-generated 'type_schema' key.
    """
    # dict_: list[pair[String, Any]]  (values: int, bool, or String only)
    def __init__(self, dict: InitializerList[pair[String, Any]]): ...
    def Apply(self, info: FieldInfoBuilder | MethodInfoBuilder) -> None: ...
    # Interacts with: FieldInfoBuilder.metadata_, MethodInfoBuilder.metadata_

    @staticmethod
    def ToJSON(metadata: _MetadataType) -> str: ...
    # Invariant: output is a valid JSON object {"key": value, ...}; key order = insertion order
    # Invariant: "type_schema" key is ALWAYS prepended before user keys

class FieldInfoBuilder(TVMFFIFieldInfo):
    """Transient builder. 'metadata_' collects type_schema + user Metadata then serializes."""
    metadata_: list[pair[String, Any]]  # serialized to TVMFFIFieldInfo.metadata at build time
    # Interacts with: InfoTrait.Apply(), FieldInfoTrait (former name of InfoTrait)

class MethodInfoBuilder(TVMFFIMethodInfo):
    """Transient builder. 'metadata_' collects type_schema + user Metadata then serializes."""
    metadata_: list[pair[String, Any]]  # serialized to TVMFFIMethodInfo.metadata at build time


# ─── Python TypeSchema dataclass ───────────────────────────────────────────────

# python/tvm_ffi/cython/type_info.pxi
@dataclasses.dataclass(repr=False)  # NOT frozen=True since commit dd4fb0ae
class TypeSchema:
    """Structured representation of a JSON type schema string."""
    origin: str                          # e.g. "int", "Array", "List", "Map", "Dict", "Callable", "Optional", "ffi.Tensor"
    args: tuple[TypeSchema, ...] = ()
    # Post-init normalisation (commit dd4fb0ae):
    # Invariant: origin in ("list","Array","List") and args==()  is impossible — normalised to (TypeSchema("Any"),)
    # Invariant: origin in ("dict","Map","Dict") and args==()  is impossible — normalised to (TypeSchema("Any"), TypeSchema("Any"))
    # CHANGED (commit 778613316): _TYPE_SCHEMA_ORIGIN_CONVERTER now emits "Array"/"List"/"Map"/"Dict"
    #   instead of collapsing ffi.Array/ffi.List to "list" and ffi.Map/ffi.Dict to "dict".
    #   Backward compat: raw "list"/"dict" origins still accepted in arity checks.
    # TY_MAP_DEFAULTS (stub codegen):
    #   "Array" → "collections.abc.Sequence"
    #   "List"  → "collections.abc.MutableSequence"
    #   "Map"   → "collections.abc.Mapping"
    #   "Dict"  → "collections.abc.MutableMapping"

    @staticmethod
    def from_json_obj(obj: dict[str, Any]) -> TypeSchema: ...
    @staticmethod
    def from_json_str(s: str) -> TypeSchema: ...

    def __repr__(self) -> str:
        """Delegates to self.repr(ty_map=None)."""

    def repr(self, ty_map: Callable[[str], str] | None = None) -> str:
        """Render as Python typing annotation string, optionally remapping origin names.

        Formats:
          Union:    "T1 | T2"
          Optional: "T | None"
          Callable: "Callable[[arg1, arg2], ret]"  (args[0]=ret, args[1:]=params)
          Generic:  "origin[arg1, arg2]"
          Atom:     "origin"
        # Interacts with: TypeField.metadata["type_schema"], TypeMethod.metadata["type_schema"]
        # Extension: pass ty_map to remap any origin name recursively (e.g. "list"→"Sequence")
        """

# _TYPE_SCHEMA_ORIGIN_CONVERTER (Python-side mapping applied when parsing from JSON):
# "DataType" → "DLDataType", "ffi.AnyView" → "Any", "ffi.None" → "None", etc.
# Handles python builtin remapping: "ffi.Int" → "int", "ffi.Float" → "float", etc.
```

### Contracts, Assumptions and Invariants

- `TVMFFIFieldInfo.metadata` / `TVMFFIMethodInfo.metadata` are always a non-empty JSON object string with at least `"type_schema"` key. Before commit 28fe3cc7 they were empty byte arrays — downstream consumers must handle the migration.
- User-supplied `Metadata` key `"type_schema"` would overwrite the auto-generated schema — avoid this key in user metadata.
- `TypeSchema("list").args` is always `(TypeSchema("Any"),)` after construction (post-init normalisation since commit dd4fb0ae). Never `()`.
- `FunctionInfo<R (Class::*)(Args...)>` member-pointer schema includes `Class*` / `const Class*` as first argument (commit 368af824 fix). `FunctionInfo<R (ObjectRef::*)(Args...)>` includes `ObjectRef` by value (commit 7b57a46 SFINAE split).
- `FieldInfoTrait` C++ symbol is renamed to `InfoTrait` (commit 28fe3cc7). Any downstream C++ that subclassed `FieldInfoTrait` must be updated.

### Extension Points
- New container types: add a `TypeSchemaImpl<MyContainer<T>>` specialization in `type_traits.h` returning `{"type":"my.Container","args":[TypeSchema<T>::v()]}`.
- New scalar types: add `TypeSchemaImpl<MyScalar>` returning `{"type":"my.ScalarTypeName"}`.
- Custom Python rendering: pass a `ty_map` function to `TypeSchema.repr()` to remap any origin name to a framework-specific type (e.g. `"list"→"Sequence"`).

### Usage Examples

#### End-to-end: C++ registration → Python metadata retrieval

**Context**: Inspecting type schema for a global function registered with extra metadata.

```python
# C++ side (src/ffi/extra/testing.cc):
# TVM_FFI_STATIC_INIT_BLOCK() {
#     reflection::GlobalDef()
#         .def("testing.schema_id_int", [](int64_t x) { return x; },
#              Metadata{{"bool_attr", true}, {"int_attr", 1}, {"str_attr", "hello"}});
# }

# Python side:
from tvm_ffi import get_global_func_metadata
from tvm_ffi.core import TypeSchema

metadata = get_global_func_metadata("testing.schema_id_int")
# metadata == {"type_schema": '{"type":"ffi.Function","args":[{"type":"int"},{"type":"int"}]}',
#              "bool_attr": True, "int_attr": 1, "str_attr": "hello"}

schema = TypeSchema.from_json_str(metadata["type_schema"])
print(schema)  # Callable[[int], int]
```

#### Field-level schema inspection on a registered object

**Context**: Runtime inspection of field types for IDE/stub integration.

```python
from tvm_ffi.core import TypeInfo, TypeSchema
from tvm_ffi.testing import _SchemaAllTypes

type_info: TypeInfo = _SchemaAllTypes.__tvm_ffi_type_info__
for f in type_info.fields:
    schema = TypeSchema.from_json_str(f.metadata["type_schema"])
    print(f.name, "->", schema)
# v_opt_arr_variant -> list[int | str] | None
# v_map_str_arr_int -> dict[str, list[int]]
```

#### Custom ty_map for abstract type names

**Context**: Stub generation tool that emits abstract typing instead of concrete builtins.

```python
from tvm_ffi.core import TypeSchema

schema = TypeSchema.from_json_str('{"type":"ffi.Function","args":[{"type":"ffi.Array","args":[{"type":"int"}]},{"type":"ffi.Array","args":[{"type":"int"}]}]}')

def _abstract(ty: str) -> str:
    return {"list": "Sequence", "dict": "Mapping"}.get(ty, ty)

assert schema.repr(_abstract) == "Callable[[Sequence[int]], Sequence[int]]"
```

## Implementation Notes
- `TypeSchemaImpl` specializations are spread across `base_details.h` (primitives, void, AnyView), `function_details.h` (functions), and individual container headers (Array, Map, Tuple, Variant). The canonical `TypeSchema<T>` alias strips const/reference before lookup.
- `Metadata::ToJSON` serializes values as: `int` → JSON number, `bool` → JSON `true`/`false`, `String` → JSON double-quoted string (via `EscapeString()`).
- `EscapeString(String) -> String` (added to `string.h` in commit 28fe3cc7) produces a JSON-safe double-quoted string with `\uXXXX` escapes for control characters. Shared with `json_writer.cc`.
- `TypeField.metadata` and `TypeMethod.metadata` on the Python side always contain at minimum `{"type_schema": "..."}`. Empty metadata (before this feature) was not possible — migrating consumers should treat absence of `metadata` as a pre-feature object.

## Alternatives & Trade-offs

### Alternative A: Reflect types via Python `inspect` / `__annotations__`
- Pros: No C++ changes; pure Python.
- Cons: Doesn't capture C++ ABI types; annotations must be manually maintained; drift-prone.

### Alternative B: Separate JSON schema file per registered type
- Pros: Easier tooling (can be parsed without loading the library).
- Cons: Schema can drift from actual registration; requires separate build step; won't capture dynamically registered functions.

## Related Design Docs & ADRs
- `.knowledge/design-records/0006-reflection.md` — `InfoTrait`, `ObjectDef`, `GlobalDef`, `FieldInfoBuilder`/`MethodInfoBuilder`
- `.knowledge/design-records/0008-type-traits.md` — `TypeTraits<T>` gains `TypeSchema()` method
- `.knowledge/design-records/0013-python-package.md` — `TypeField.metadata`, `TypeMethod.metadata`, `get_global_func_metadata`
- `.knowledge/design-records/0020-stub-gen.md` — `tvm-ffi-stubgen` CLI that consumes `TypeSchema` for stub generation

### Python-Side Type Conversion (TypeSchema.convert / CAny)

The TypeSchema system gained a full Python-side conversion pipeline across commits 754f41d3, 2885cf8b, and 5f5ca5ab. This pipeline enforces type annotations at runtime when setting fields or calling typed functions from Python.

```python
# python/tvm_ffi/cython/type_converter.pxi (replaces type_check.pxi)

cdef class _TypeConverter:
    """Pre-built converter returning CAny; C function-pointer dispatch set at build time."""
    cdef _dispatch_fn_t dispatch   # single indirect C call — zero Python overhead
    cdef int32_t type_index        # target Object type index
    cdef tuple subs                # sub-converters for Optional/Union/List/Dict/Tuple
    cdef Function _fn_convert      # lazy __ffi_convert__ TypeAttr lookup
    # Invariant: dispatch never None after build
    # Extension: add new leaf converter functions and wire in _build_converter()

cdef class CAny:
    """Owned TVMFFIAny value container with ref-counting."""
    cdef TVMFFIAny cdata
    # Invariant: type_index >= kTVMFFIStaticObjectBegin -> v_obj is ref-counted
    # Invariant: __dealloc__ decrefs to prevent leaks
    def to_py(self) -> object: ...   # convert back to Python

class TypeSchema:
    def convert(self, value: object) -> CAny: ...    # BREAKING: returns CAny, not object
    def check_value(self, value: object) -> bool: ...
    @staticmethod
    def from_annotation(annotation: object) -> TypeSchema:
        """Build TypeSchema from Python type annotation (bare types, generics, Optional, Union).
        # Interacts with: TYPE_CLS_TO_INFO registry, _TYPE_INDEX_TO_ORIGIN
        # Invariant: unregistered CObject subclasses raise TypeError
        """
        ...
    def to_json(self) -> str: ...  # JSON-serializable type descriptor

# C++ __ffi_convert__ type attribute protocol (commit 5f5ca5ab):
# ObjectDef<Class>.ref<TObjectRef>() auto-registers __ffi_convert__ for every reflected ObjectRef
# type_attr::kConvert = "__ffi_convert__"
# Interacts with: TypeAttrColumn, CastFromAny<TObjectRef>, CastObjectFromAny
```

**Evolution of type conversion**:
1. v1 (754f41d3): `type_check.pxi` with `_TypeConverter` returning Python objects; `_ConvertError` sentinel
2. v2 (2885cf8b): `CAny` wrapper introduced; `convert()` returns `CAny`; `TypeSchema.from_annotation()` added; `try_convert()`/`try_check_value()` removed
3. v3 (5f5ca5ab): `type_check.pxi` replaced by `type_converter.pxi`; Object conversion delegated to C++ `__ffi_convert__` TypeAttr; `__tvm_ffi_value__` precedence changed to before `__tvm_ffi_int__`/`__tvm_ffi_float__`

### FunctionObj-Based Field Setters (commit 4bb487ef)

`TVMFFIFieldInfo::setter` changed from `TVMFFIFieldSetter` (function pointer) to `void*`, enabling Python-defined field setters via `kTVMFFIFieldFlagBitSetterIsFunctionObj = 1 << 11`. When this flag is set, `setter` is a `TVMFFIObjectHandle` (FunctionObj) called with `(field_addr_as_OpaquePtr, value_as_AnyView)`. This enables `@py_class` fields to use FFI Function-based setters with type conversion.

```cpp
// include/tvm/ffi/reflection/accessor.h
inline int CallFieldSetter(const TVMFFIFieldInfo* field_info, void* field_addr,
                           const TVMFFIAny* value) {
    if (!(field_info->flags & kTVMFFIFieldFlagBitSetterIsFunctionObj)) {
        auto setter = reinterpret_cast<TVMFFIFieldSetter>(field_info->setter);
        return setter(field_addr, value);
    } else {
        // FunctionObj path: call with (OpaquePtr, AnyView)
        return TVMFFIFunctionCall(static_cast<TVMFFIObjectHandle>(field_info->setter), args, 2, &result);
    }
}
```

## Evidence Matrix

| Commit | Contribution |
|--------|-------------|
| 28fe3cc7 | Introduces TypeSchemaImpl<T>, Metadata InfoTrait, FieldInfoBuilder/MethodInfoBuilder, EscapeString; Python TypeSchema dataclass + get_global_func_metadata |
| dd4fb0ae | Adds TypeSchema.repr(ty_map), removes frozen=True, adds post-init normalisation for list/dict |
| 368af824 | Fixes FunctionInfo<R (Class::*)(Args...)> to include Class* as first arg in schema |
| 754f41d3 | TypeSchema type converter with C function-pointer dispatch (type_check.pxi) |
| 2885cf8b | CAny owned-value wrapper; TypeSchema.convert returns CAny; TypeSchema.from_annotation |
| 4bb487ef | FunctionObj-based field setter dispatch via kTVMFFIFieldFlagBitSetterIsFunctionObj |
| 5f5ca5ab | __ffi_convert__ TypeAttr; type_converter.pxi replaces type_check.pxi |
| Plus 2 supporting commits (7b57a46, c046b171) |
