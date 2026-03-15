---
scope: "json-and-serialization"
---
# API Index: JSON and Object Graph Serialization

**Scope**: JSON parser/writer, object graph serialization/deserialization, base64 utilities, and the reflection-based ObjectCreator.
**Design docs**: [0012-json-and-serialization.md](../designs/0012-json-and-serialization.md)
**ADRs**: [0011-json-reuses-any-no-new-objects.md](../ADRs/0011-json-reuses-any-no-new-objects.md), [0010-extra-api-isolation.md](../ADRs/0010-extra-api-isolation.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `json::Value` | using (`extra/json.h`) | `= Any` | Type alias for any JSON value |
| `json::Object` | using (`extra/json.h`) | `= ffi::Map<Any, Any>` | Type alias for JSON objects (insertion-order-preserving) |
| `json::Array` | using (`extra/json.h`) | `= ffi::Array<Any>` | Type alias for JSON arrays |
| `json::Parse` | function (`extra/json.h`) | `(const String& json_str, String* error_msg = nullptr) -> json::Value` | Parse JSON string to Any; optional error-safe mode |
| `json::Stringify` | function (`extra/json.h`) | `(const json::Value& value, Optional<int> indent = nullopt) -> String` | Serialize Any to JSON string; optional pretty-printing |
| `ToJSONGraph` | function (`extra/serialization.h`) | `(const Any& value, const Any& metadata = Any(nullptr)) -> json::Value` | Serialize Any to JSON object graph preserving types and shared refs |
| `FromJSONGraph` | function (`extra/serialization.h`) | `(const json::Value& value) -> Any` | Deserialize JSON object graph to Any |
| `FromJSONGraphString` | function (internal) | `(const String& value) -> Any` | Convenience: Parse + FromJSONGraph |
| `ToJSONGraphString` | function (internal) | `(const Any& value, const Any& metadata) -> String` | Convenience: ToJSONGraph + Stringify |
| `Base64Encode` | function (`extra/base64.h`) | `(TVMFFIByteArray bytes) -> String`, `(const Bytes& data) -> String` | Encode bytes to base64 string |
| `Base64Decode` | function (`extra/base64.h`) | `(TVMFFIByteArray bytes) -> Bytes`, `(const String& data) -> Bytes` | Decode base64 string to bytes |
| `reflection::ObjectCreator` | class (`reflection/creator.h`) | `ObjectCreator(string_view type_key)`, `ObjectCreator(const TVMFFITypeInfo*)`, `operator()(const Map<String, Any>&) -> Any` | Create objects from type key + field map using reflection |

## C++ API: Global Registered Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.json.Parse` | `(String) -> Any` | Parse JSON string |
| `ffi.json.Stringify` | `(Any, Optional<int>) -> String` | Serialize to JSON string |
| `ffi.ToJSONGraph` | `(Any, Any) -> json::Value` | Serialize to JSON object graph |
| `ffi.FromJSONGraph` | `(json::Value) -> Any` | Deserialize from JSON object graph |
| `ffi.ToJSONGraphString` | `(Any, Any) -> String` | Serialize to JSON graph string |
| `ffi.FromJSONGraphString` | `(String) -> Any` | Deserialize from JSON graph string |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `tvm_ffi.get_global_func("ffi.ToJSONGraphString")` | `(Any, Any) -> String` | Cross-language object graph serialization |
| `tvm_ffi.get_global_func("ffi.FromJSONGraphString")` | `(String) -> Any` | Cross-language object graph deserialization |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | -- | Not yet bound |
