---
scope: "json-and-serialization"
---
# API Index: JSON and Object Graph Serialization

**Scope**: JSON parser/writer (`tvm::ffi::json`), object graph serialization (`ToJSONGraph`/`FromJSONGraph`), Base64 utilities, ObjectCreator.
**Design docs**: [0010-json-and-serialization.md](../designs/0010-json-and-serialization.md)
**ADRs**: [0006-json-dialect-and-serialization-strategy.md](../ADRs/0006-json-dialect-and-serialization-strategy.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `json::Value` | using | `= Any` | Type alias: any JSON value stored as ffi::Any |
| `json::Object` | using | `= Map<Any, Any>` | Type alias: JSON object (insertion-ordered) |
| `json::Array` | using | `= Array<Any>` | Type alias: JSON array |
| `json::Parse` | function | `json::Value Parse(const String&, String* error_msg = nullptr)` | Parse JSON string into Any value tree. Extensions: Infinity/NaN, int64 |
| `json::Stringify` | function | `String Stringify(const json::Value&, Optional<int> indent = nullopt)` | Serialize Any value tree to JSON string. Compact or pretty-print |
| `ToJSONGraph` | function | `json::Value ToJSONGraph(const Any& value, const Any& metadata = Any(nullptr))` | Serialize Any to JSON object graph with node deduplication |
| `FromJSONGraph` | function | `Any FromJSONGraph(const json::Value& value)` | Deserialize JSON object graph back to Any |
| `ToJSONGraphString` | function | `String ToJSONGraphString(const Any& value, const Any& metadata)` | Convenience: serialize to JSON string |
| `FromJSONGraphString` | function | `Any FromJSONGraphString(const String& value)` | Convenience: deserialize from JSON string |
| `Base64Encode` | function | `String Base64Encode(const Bytes&)` / `String Base64Encode(const TVMFFIByteArray&)` | RFC 4648 Base64 encoding |
| `Base64Decode` | function | `Bytes Base64Decode(const String&)` / `Bytes Base64Decode(const TVMFFIByteArray&)` | RFC 4648 Base64 decoding |
| `ObjectCreator` | class | `ObjectCreator(type_key)`, `Any operator()(Map<String, Any>)` | Reflection-based object construction from named field map |

## Registered Global Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.json.Parse` | `def Parse(json_str: str) -> Any` | Parse JSON string |
| `ffi.json.Stringify` | `def Stringify(value: Any, indent: Optional[int] = None) -> str` | Serialize to JSON string |
| `ffi.ToJSONGraph` | `def ToJSONGraph(value: Any, metadata: Any = None) -> Any` | Serialize to JSON object graph |
| `ffi.FromJSONGraph` | `def FromJSONGraph(value: Any) -> Any` | Deserialize from JSON object graph |
| `ffi.ToJSONGraphString` | `def ToJSONGraphString(value: Any, metadata: Any) -> str` | Serialize to JSON string (convenience) |
| `ffi.FromJSONGraphString` | `def FromJSONGraphString(value: str) -> Any` | Deserialize from JSON string (convenience) |

## TypeAttrColumn Protocol
| Column Name | Signature | Description |
|------------|-----------|-------------|
| `__data_to_json__` | `def(self: ObjectRef) -> json::Value` | Custom JSON serialization for a type |
| `__data_from_json__` | `def(data: json::Value) -> ObjectRef` | Custom JSON deserialization for a type |
