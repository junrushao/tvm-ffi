---
design: "0019"
title: "TypeSchema Metadata System: JSON Type Descriptors for Reflection"
status: "active"
owners:
  - "Junru Shao"
created: "2025-10-03"
last_updated: "2025-10-10"
scope:
  - "ffi/reflection"
  - "ffi/function_details"
  - "ffi/type_traits"
  - "python/tvm_ffi/cython/type_info"
source_commits:
  - "28fe3cc7fc23b725ddefbb3ca1e1899a7dfd530c"
  - "ec422f1a144ac5c544957835d8358bc1238e8b83"
  - "368af824845424ea439b9f3d68bf4a710afb38b1"
  - "c046b17108484780b8b13142e1c1a46e263ec979"
  - "dd4fb0ae92ab69b1cc0280e812a18a58273d4ae6"
source_ledgers:
  - ".memory/commits/2025-10-03-28fe3cc7.md"
  - ".memory/commits/2025-10-04-ec422f1a.md"
  - ".memory/commits/2025-10-07-368af824.md"
  - ".memory/commits/2025-10-07-c046b171.md"
  - ".memory/commits/2025-10-08-dd4fb0ae.md"
---

# TypeSchema Metadata System: JSON Type Descriptors for Reflection

## TL;DR
- `TypeSchema<T>` is a C++ compile-time trait that generates JSON type descriptor strings for all FFI types, enabling cross-language type introspection without C++ header access.
- `Metadata` is a key-value store (String -> Any) attachable to fields, methods, and global functions via the reflection builder API, with `type_schema` automatically attached by `def`/`def_field`/`def_method`.
- On Python, the `TypeSchema` dataclass parses JSON schemas into structured objects with `repr(ty_map=...)` for customizable rendering, supporting stub generation and IDE tooling.

## Problem Statement
The reflection system (Design 0006) provides runtime access to fields and methods, but lacks type information. Without type schemas, Python tooling (stub generators, IDE autocompletion, documentation) cannot determine the types of fields, method arguments, or return values. Manual type annotations in Python stubs duplicate C++ type information and drift over time. The system needs a mechanism to carry compile-time C++ type information into runtime-accessible metadata that any language can consume.

## Context and Constraints
- Type information must be serializable to a language-neutral format (JSON) since it crosses the C ABI boundary.
- The C++ `TypeTraits<T>` system already knows the type index and string name of every FFI type, but this information is scattered across specializations with no unified schema format.
- Fields and methods are registered via `ObjectDef<T>` and `GlobalDef` at static init time; type schema generation must integrate with this builder API without adding manual annotation burden.
- Member function pointers have an implicit `this` parameter that must be reflected in the schema (the FFI calling convention passes `self` explicitly as the first argument).

## Goals
- Generate JSON type descriptors for all FFI types at compile time via `TypeSchema<T>`.
- Attach type schemas automatically to field and method registrations.
- Provide a `Metadata` class for attaching arbitrary key-value metadata to reflection entries.
- Provide a Python `TypeSchema` class that parses JSON schemas into structured objects with customizable rendering.

## Non-Goals
- Runtime type checking based on schemas (schemas are descriptive, not prescriptive).
- Schema validation at field set time.
- Complete Python typing system integration (TypeSchema is a representation, not a mypy plugin).

## Design
### Components and Responsibilities

- **`details::TypeSchema<T>`** (C++ trait, `type_traits.h` / `function_details.h`): Static member `v()` returns a JSON string describing type `T`. Specializations cover: primitives (`int`, `float`, `bool`, `void`), `String`, `Bytes`, `DataType`, `Device`, `DLTensor*`, containers (`Array<T>`, `List<T>`, `Map<K,V>`, `Dict<K,V>`, `Optional<T>`, `Variant<T...>`, `Tuple<T...>`), `Function` and typed functions (`TypedFunction<R(Args...)>`), and `ObjectRef` subclasses (using their type key). Output format: `{"type":"<name>"}` for leaf types, `{"type":"<name>","args":[...]}` for parameterized types.

- **`FunctionInfo<F>` TypeSchema integration** (`function_details.h`): `FunctionInfo<R(Class::*)(Args...)>` specialization now includes `Class*` or `const Class*` as the first argument in the schema (commit `368af824`), matching the actual FFI calling convention where `self` is passed explicitly. The previous version omitted the self type, causing schema/calling-convention mismatch.

- **`reflection::Metadata`** (class, `reflection/registry.h`): Wraps a vector of `(String, Any)` pairs. Applied to `TVMFFIFieldInfo` or `TVMFFIMethodInfo` via the `InfoTrait` mechanism. The pairs are serialized as a JSON object stored in the `metadata` byte array of the C struct. Built via the `Metadata("key", value)` constructor.

- **`FieldInfoBuilder` / `MethodInfoBuilder`** (structs, `reflection/registry.h`): Extend `TVMFFIFieldInfo` / `TVMFFIMethodInfo` with a temporary `Metadata` object during registration. The builder's destructor serializes metadata to JSON and stores it in the C struct's `metadata` field.

- **`InfoTrait: Metadata`** (concrete trait): Applied as an extra argument to `def_ro`, `def_rw`, `def`, `def_method`. Adds key-value pairs to the builder's metadata collection.

- **Automatic `type_schema` attachment**: `GlobalDef::def` and `def_method` automatically call `TypeSchema<F>::v()` for the function type and attach it as `metadata["type_schema"]`. `ObjectDef::def_field` does the same for field types.

- **`EscapeString`** (utility, `string.h`): Proper JSON string escaping for embedding values in JSON metadata. Handles `\`, `"`, control characters.

- **Python `TypeSchema`** (dataclass, `cython/type_info.pxi`): Fields: `origin` (str), `args` (tuple of TypeSchema). Class method `from_json_str(s)` parses the JSON schema. `__repr__()` delegates to `repr(ty_map=None)`. The `repr(ty_map=...)` method (commit `dd4fb0ae`) accepts a callable `(TypeSchema) -> str | None` for overriding type name rendering, enabling stub generators to use different type aliases (e.g., `list` -> `Sequence`).

- **`_TYPE_SCHEMA_ORIGIN_CONVERTER`** (dict, `cython/type_info.pxi`): Maps C++ type names to Python display names. E.g., `"ffi.String"` -> `"str"`, `"DataType"` -> `"dtype"` (commit `c046b171`), `"ffi.Array"` -> `"list"`.

- **`get_global_func_metadata(name)`** (Python function, `registry.py`): Retrieves metadata dict for a global function by name, including its `type_schema`.

### Data Contracts and Invariants
- **JSON schema format**: Always a JSON object with a `"type"` key. Parameterized types add an `"args"` array. No other keys are used in the schema itself (metadata keys like `"type_schema"` are in the outer `Metadata` object).
- **Self-type inclusion for member functions**: The schema for `R (Class::*)(Args...)` includes `Class*` as the first argument type. This matches the packed calling convention where `self` is the first argument.
- **TypeSchema validation**: Python `TypeSchema.__post_init__` validates argument counts: `list`/`Array` allow 0 or 1 args, `dict`/`Map` allow 0 or 2 args, `Union` requires >= 2, `Optional` requires exactly 1.
- **Metadata immutability after registration**: Once serialized to the C struct, metadata is immutable. The `Metadata` object is consumed during registration.

### Control Flow
1. **C++ registration**: `GlobalDef().def("func.name", &Class::method)` -> `TypeSchema<decltype(&Class::method)>::v()` generates JSON -> `Metadata("type_schema", schema_json)` is attached -> `TVMFFIFunctionSetGlobalFromMethodInfo` stores the metadata.
2. **Python consumption**: `get_global_func_metadata("func.name")` -> retrieves `TVMFFIMethodInfo.metadata` -> parses JSON -> returns Python dict including `"type_schema"` key.
3. **Schema rendering**: `TypeSchema.from_json_str('{"type":"ffi.Function","args":[{"type":"int"},{"type":"int"}]}')` -> `TypeSchema(origin="Callable", args=(TypeSchema("int"), TypeSchema("int")))` -> `repr()` -> `"Callable[[int], int]"`.
4. **Custom rendering**: `schema.repr(ty_map=lambda s: "Sequence" if s.origin == "list" else None)` -> uses custom name where `ty_map` returns non-None, falls back to default otherwise.

### Extension Points
- **New type schemas**: Add a `TypeSchema<T>` specialization for any new FFI type. The JSON format is open-ended.
- **New metadata keys**: Attach arbitrary key-value pairs via `Metadata("custom_key", value)` in `def_ro`/`def`/etc.
- **New `ty_map` renderers**: Downstream applications can provide custom `ty_map` callbacks for domain-specific type name rendering.

## Alternatives Considered
### Embed type information in field/method names (e.g., `"x:int"`)
- Pros: Simple, no JSON parsing needed.
- Cons: Cannot represent parameterized types, no structured metadata, fragile parsing.

### Use protobuf/flatbuffer for schema serialization
- Pros: Well-defined schema evolution, binary format.
- Cons: Build-time dependency on protobuf, more complex deserialization, overkill for simple type descriptors.

### Generate Python stubs from C++ headers directly (e.g., via clang AST)
- Pros: No runtime metadata needed.
- Cons: Requires clang toolchain, cannot handle dynamic registration, tightly coupled to C++ build.

## Trade-offs
- **Optimized**: Automatic schema generation (no manual annotation), JSON portability (any language can parse), compile-time type safety (TypeSchema<T> is statically verified), customizable rendering (ty_map).
- **Sacrificed**: JSON parsing overhead on the Python side (mitigated by caching), schema completeness (some C++ types like raw pointers or custom structs may not have TypeSchema specializations), no runtime type enforcement (schemas are hints).

## Interfaces and Compatibility
- **C++ API**: `details::TypeSchema<T>::v()` returning `std::string`, `reflection::Metadata` class, `EscapeString()` utility.
- **C ABI**: `TVMFFIFieldInfo.metadata` and `TVMFFIMethodInfo.metadata` byte arrays carry JSON-serialized metadata.
- **Python API**: `TypeSchema` dataclass with `from_json_str()`, `repr(ty_map=...)`, `__repr__()`. `get_global_func_metadata(name)` function. `TypeField.metadata` and `TypeMethod.metadata` dicts.
- **Breaking change**: `FieldInfoTrait` renamed to `InfoTrait` (commit `28fe3cc7`). Downstream code subclassing `FieldInfoTrait` must update.

## Failure Modes and Mitigations
- **Malformed JSON schema**: If a `TypeSchema<T>` specialization generates invalid JSON, `TypeSchema.from_json_str` raises `ValueError` with the input string. Mitigated by unit tests for all built-in type schema specializations.
- **Missing TypeSchema specialization**: If a C++ type lacks a `TypeSchema<T>` specialization, the compiler will fail with a static assertion or SFINAE failure at registration time. This is a compile-time error, not a runtime error.
- **Self-type omission regression**: The member function self-type fix (commit `368af824`) added tests to prevent regression; C++ and Python tests verify the self argument appears in method schemas.

## Observability and Validation
- `tests/cpp/test_metadata.cc`: Tests TypeSchema generation for all primitive and container types, verifies member function self-type inclusion.
- `tests/python/test_metadata.py`: Tests Python TypeSchema parsing, rendering with default and custom ty_map, dtype display name, metadata retrieval.
- `src/ffi/extra/testing.cc`: Test type `testing.SchemaAllTypes` with fields and methods of every major FFI type.

## Migration and Rollout
- New system: no migration needed for existing code that does not use metadata.
- `FieldInfoTrait` users must rename to `InfoTrait`.
- Type schemas are attached automatically by `GlobalDef::def`/`def_method` and `ObjectDef::def_ro`/`def_rw`; no opt-in needed.

## Diagrams
- [.memory/diagrams/0015-tensorview-typeschema-architecture.md](.memory/diagrams/0015-tensorview-typeschema-architecture.md)

## Related ADRs
None

## Evidence Matrix
- `TypeSchema<T>` trait generating JSON type descriptors -> `.memory/commits/2025-10-03-28fe3cc7.md` + `28fe3cc7` + `include/tvm/ffi/type_traits.h`, `include/tvm/ffi/function_details.h`
- `Metadata` class and `FieldInfoBuilder`/`MethodInfoBuilder` -> `28fe3cc7` + `include/tvm/ffi/reflection/registry.h`
- `EscapeString` utility -> `28fe3cc7` + `include/tvm/ffi/string.h`
- Python `TypeSchema` dataclass with `from_json_str` -> `28fe3cc7` + `python/tvm_ffi/cython/type_info.pxi`
- `get_global_func_metadata()` Python API -> `28fe3cc7` + `python/tvm_ffi/registry.py`
- `_TYPE_SCHEMA_ORIGIN_CONVERTER` mapping table -> `28fe3cc7` + `python/tvm_ffi/cython/type_info.pxi`
- Redundant forward declaration cleanup -> `.memory/commits/2025-10-04-ec422f1a.md` + `ec422f1a` + `include/tvm/ffi/function_details.h`
- Self-type inclusion in member function schemas -> `.memory/commits/2025-10-07-368af824.md` + `368af824` + `include/tvm/ffi/function_details.h`
- `DataType` -> `dtype` display name mapping -> `.memory/commits/2025-10-07-c046b171.md` + `c046b171` + `python/tvm_ffi/cython/type_info.pxi`
- `TypeSchema.repr(ty_map=...)` customizable rendering -> `.memory/commits/2025-10-08-dd4fb0ae.md` + `dd4fb0ae` + `python/tvm_ffi/cython/type_info.pxi`, `python/tvm_ffi/core.pyi`

## Open Questions
- Should TypeSchema support union/intersection types for overloaded functions?
- Should there be a versioning mechanism for schema format changes?
- Should `ty_map` be stored persistently on TypeSchema instances rather than passed per-call?

## Confidence and Risk
- Confidence: high
- Residual risks: The JSON schema format is not formally specified (no JSON Schema or grammar definition). Downstream tools that consume schemas may break if the format evolves. The `_TYPE_SCHEMA_ORIGIN_CONVERTER` mapping is maintained manually; new C++ type names need corresponding Python entries.
