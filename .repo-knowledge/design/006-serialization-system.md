# Serialization System (JSON + JSONGraph)

- Doc ID: 006-serialization-system
- Status: Approved
- Last Updated: 2026-02-21
- Owners: Tianqi Chen

## Overview

The TVM FFI provides a three-layer serialization stack for persisting and
restoring object graphs:

1. **JSON parser/writer**: A lightweight, dependency-free JSON layer that
   operates on `Any`/`Map`/`Array` values directly.
2. **JSONGraph serialization**: A graph-aware format that preserves shared
   object references across the object graph.
3. **ObjectCreator**: A reflection-based helper for type-safe deserialization
   using the reflection registry.

All three layers live in `include/tvm/ffi/extra/` and `src/ffi/extra/`, gated
behind `TVM_FFI_USE_EXTRA_CXX_API=ON`.

## Key Design

### JSON parser and writer

The JSON parser (`src/ffi/extra/json_parser.cc`, `de541e3`) is a recursive
descent parser that produces `Any` values directly. The type mapping is:

| JSON type | FFI type |
|-----------|----------|
| `null`    | `nullptr` (kTVMFFINone) |
| `true`/`false` | `bool` (kTVMFFIBool) |
| integer   | `int64_t` (kTVMFFIInt) |
| float     | `double` (kTVMFFIFloat) |
| string    | `String` |
| array     | `Array<Any>` |
| object    | `Map<Any, Any>` |

The parser supports JavaScript-style `Infinity`, `-Infinity`, and `NaN`
literals for special floating-point values. These are not standard JSON but
are required for round-tripping TVM IR that contains such values.

The writer (`src/ffi/extra/json_writer.cc`) serializes `Any` back to JSON
strings with optional indentation.

Type aliases in `include/tvm/ffi/extra/json.h`:
```cpp
namespace json {
using Value = Any;
using Object = Map<Any, Any>;
using Array = ffi::Array<Any>;
}  // namespace json
```

### Fast-math safety

The parser and writer include bit-level implementations for NaN and Infinity
creation and detection (`1a271f0`, `3f4f4f1`) that work correctly under
`-ffast-math`. Under this flag, `std::isnan()`, `std::isinf()`, and
`std::numeric_limits<double>::infinity()` may be optimized away by the
compiler. The fallback implementations use pointer-cast or bitwise IEEE 754
checks guarded by `#ifdef __FAST_MATH__`.

### JSONGraph format

The JSONGraph serializer (`src/ffi/extra/serialization.cc`, `8eaefe0`)
converts an arbitrary `Any` value into a JSON structure that preserves shared
object references:

```json
{
  "root_index": 0,
  "nodes": [
    {"type": "tvm.ffi.Array", "data": [1, 2]},
    {"type": "my.Type", "data": {"field1": "value", "field2": 42}}
  ],
  "metadata": null
}
```

Each node in the `nodes` array represents a distinct object, identified by its
type key. Object references within node data are replaced by integer indices
into the `nodes` array, enabling shared references to be serialized without
duplication.

The serializer (`ObjectGraphSerializer`) walks the object graph depth-first,
assigning indices to each unique object. The deserializer
(`ObjectGraphDeserializer`) reconstructs the graph by creating objects in
topological order.

### Custom serialization hooks

Types that need custom serialization logic register `__data_to_json__` and
`__data_from_json__` type attributes via `TypeAttrDef`:

```cpp
TypeAttrDef<MyObj>()
    .def("__data_to_json__", &MyObj::DataToJSON)
    .def("__data_from_json__", &MyObj::DataFromJSON);
```

The serializer calls these hooks instead of the default field-by-field
serialization when they are registered for a type. `Bytes` fields are
automatically encoded/decoded using base64.

The `EnsureTypeAttrColumn` calls for `__data_to_json__` and
`__data_from_json__` are registered at static init time (`55edee0`) to prevent
late-registration races.

### ObjectCreator for deserialization

`reflection::ObjectCreator` (`7cb9273`) constructs objects from a type key and
a `Map<String, Any>` of field values using the reflection registry. It
replaced ad-hoc `getattr`-style attribute setting in the deserializer:

```cpp
reflection::ObjectCreator creator(type_key);
Any result = creator(fields_map);
```

Internally, `ObjectCreator` calls the type's registered `creator` function,
then iterates fields via `ForEachFieldInfo`, applying setters for each provided
field. It handles defaults for missing fields and reports errors for
extra/missing fields.

`Shape` fields are stored as primitives in the JSONGraph format rather than as
separate object nodes (`7cb9273`).

### String-based convenience API

String-based wrappers (`55edee0`) provide a simpler interface for Python and
other language bindings:

- `ffi.ToJSONGraphString(Any value, Any metadata) -> String`
- `ffi.FromJSONGraphString(String json) -> Any`

These combine `json::Stringify`/`json::Parse` with `ToJSONGraph`/`FromJSONGraph`.

### List and Dict serialization with cycle detection (February 2026)

The JSONGraph serializer and deserializer were extended (`9513c2f`, `c1af3b3`)
to handle `List` and `Dict` container types. Since mutable containers can form
reference cycles (unlike immutable `Array` and `Map`), the serializer tracks
visited objects and correctly handles back-references using the existing
node-index mechanism.

The JSON writer (`json_writer.cc`) was also updated with cycle detection for
`List` objects, preventing infinite recursion when writing mutable graphs.

Python serialization tests were added (`tests/python/test_serialization.py`,
573 lines) and C++ serialization tests expanded (`tests/cpp/extra/test_serialization.cc`,
+477 lines) to cover cycle detection and List/Dict round-trip scenarios.

### JSON parser UTF-8 fix (February 2026)

The JSON parser (`d3b5532`) was fixed to correctly handle UTF-8 bytes in the
control character check. Previously, multi-byte UTF-8 sequences could be
incorrectly flagged as control characters due to signed byte comparison.

## APIs

### C++ API

```cpp
// JSON parsing and writing (include/tvm/ffi/extra/json.h).
namespace json {
using Value = Any;
using Object = Map<Any, Any>;
using Array = ffi::Array<Any>;

// Parse JSON string. Optional error_msg pointer for parse errors.
Value Parse(String json_str, String* error_msg = nullptr);

// Serialize to JSON string. Optional indent for pretty-printing.
String Stringify(Value value, Optional<int> indent = NullOpt);
}  // namespace json

// JSONGraph serialization (include/tvm/ffi/extra/serialization.h).
json::Value ToJSONGraph(Any value, Any metadata);
Any FromJSONGraph(json::Value json);

// Base64 encoding/decoding (include/tvm/ffi/extra/base64.h).
String Base64Encode(TVMFFIByteArray data);
Bytes Base64Decode(TVMFFIByteArray data);

// Object construction from reflection (include/tvm/ffi/reflection/creator.h).
class ObjectCreator {
  ObjectCreator(const char* type_key);
  ObjectCreator(const TVMFFITypeInfo* type_info);
  Any operator()(Map<String, Any> fields);
};
```

### Global functions

| Function name | Signature | Description |
|---------------|-----------|-------------|
| `ffi.json.Parse` | `(String) -> Any` | Parse JSON string |
| `ffi.json.Stringify` | `(Any, Optional<int>) -> String` | Serialize to JSON |
| `ffi.ToJSONGraph` | `(Any, Any) -> json::Value` | Serialize to JSONGraph |
| `ffi.FromJSONGraph` | `(json::Value) -> Any` | Deserialize from JSONGraph |
| `ffi.ToJSONGraphString` | `(Any, Any) -> String` | Serialize to JSON string |
| `ffi.FromJSONGraphString` | `(String) -> Any` | Deserialize from JSON string |

### Build configuration

All serialization sources require `TVM_FFI_USE_EXTRA_CXX_API=ON` in CMake.

## Implementation

Key files:
- `include/tvm/ffi/extra/json.h` -- `json::Value`, `json::Parse`, `json::Stringify`
- `include/tvm/ffi/extra/serialization.h` -- `ToJSONGraph`, `FromJSONGraph`, JSONGraph schema documentation
- `include/tvm/ffi/extra/base64.h` -- `Base64Encode`, `Base64Decode`
- `include/tvm/ffi/reflection/creator.h` -- `reflection::ObjectCreator`
- `src/ffi/extra/json_parser.cc` -- `JSONParserContext`, fast-math-safe helpers
- `src/ffi/extra/json_writer.cc` -- JSON writer, fast-math-safe NaN/Inf detection
- `src/ffi/extra/serialization.cc` -- `ObjectGraphSerializer`, `ObjectGraphDeserializer`, string-based wrappers

Tests:
- `tests/cpp/extra/test_json_parser.cc` -- Parser tests for all JSON types, error paths, int64 precision, Infinity/NaN
- `tests/cpp/extra/test_json_writer.cc` -- Writer tests for roundtrip and indent formatting
- `tests/cpp/extra/test_serialization.cc` -- Roundtrip tests for primitives, strings, bytes, objects, nested objects, shared references

## History
- 2025-08-04: JSON parser and writer introduced (`de541e3`)
- 2025-08-05: JSONGraph serialization added with base64 support (`8eaefe0`)
- 2025-08-05: `ObjectCreator` added; serialization migrated to reflection-based construction (`7cb9273`)
- 2025-08-06: String-based convenience wrappers added; `EnsureTypeAttrColumn` for hooks (`55edee0`)
- 2025-08-15: Fast-math-safe NaN/Infinity handling in parser and writer (`1a271f0`)
- 2025-08-22: Additional fast-math fix for JSON parser/writer (`3f4f4f1`)
- 2026-02-11: JSON parser UTF-8 bytes fix for control character check (`d3b5532`)
- 2026-02-13: `List` serialization with cycle detection added (`9513c2f`)
- 2026-02-19: `Dict` serialization with cycle detection added (`c1af3b3`)

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
  - `.repo-knowledge/ranges/2026-02-21-B1611E0-ECC7471.md`
- Related design docs:
  - `.repo-knowledge/design/004-reflection-system.md`
  - `.repo-knowledge/design/001-type-erased-value-system.md`
