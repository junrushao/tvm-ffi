---
scope: "json-serialization"
status: "active"
last_updated_commit: "1a271f00321b8cc16b72e58436716a05e2f62500"
related_designs:
  - ".knowledge/designs/0012-json-serialization.md"
related_adrs: []
---
# API Index: JSON & Object Graph Serialization

**Scope**: JSON parsing/writing, Base64 encoding, reflection-based object graph serialization/deserialization, and ObjectCreator.
**Design docs**: `.knowledge/designs/0012-json-serialization.md`
**ADRs**: None

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| (No dedicated C ABI functions; all serialization operates via C++ API and registered global functions) | | |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `json::Value` | using | `using Value = Any` | Type alias for JSON value |
| `json::Object` | using | `using Object = Map<Any, Any>` | Type alias for JSON object |
| `json::Array` | using | `using Array = Array<Any>` | Type alias for JSON array |
| `reflection::ObjectCreator` | class | `ObjectCreator(string_view type_key)`, `Any operator()(const Map<String, Any>& fields) const` | Create object from type key + field map via reflection |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `json::Parse` | `TVM_FFI_EXTRA_CXX_API json::Value Parse(const String& json_str, String* error_msg = nullptr)` | Parse JSON string; optional error output param |
| `json::Stringify` | `TVM_FFI_EXTRA_CXX_API String Stringify(const json::Value& value, Optional<int> indent = std::nullopt)` | Serialize value to JSON string |
| `ToJSONGraph` | `TVM_FFI_EXTRA_CXX_API json::Value ToJSONGraph(const Any& value, const Any& metadata = Any(nullptr))` | Serialize any value to JSON object graph with DAG dedup |
| `FromJSONGraph` | `TVM_FFI_EXTRA_CXX_API Any FromJSONGraph(const json::Value& value)` | Deserialize JSON object graph to Any value |
| `Base64Encode` | `inline String Base64Encode(TVMFFIByteArray bytes)` | Encode bytes to base64 string |
| `Base64Encode` | `inline String Base64Encode(const Bytes& data)` | Convenience overload for Bytes |
| `Base64Decode` | `inline Bytes Base64Decode(TVMFFIByteArray bytes)` | Decode base64 string to Bytes |
| `Base64Decode` | `inline Bytes Base64Decode(const String& data)` | Convenience overload for String |

## Global Functions (registered via GlobalDef)
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.json.Parse` | `(String json_str) -> json::Value` | Parse JSON string (throws on error) |
| `ffi.json.Stringify` | `(json::Value value, Optional<int> indent) -> String` | Serialize to JSON string |
| `ffi.ToJSONGraph` | `(Any value, Any metadata) -> json::Value` | Serialize to JSON object graph (C++ callers) |
| `ffi.FromJSONGraph` | `(json::Value value) -> Any` | Deserialize JSON object graph (C++ callers) |
| `ffi.ToJSONGraphString` | `(Any value, Any metadata) -> String` | Serialize to JSON graph string (cross-language) |
| `ffi.FromJSONGraphString` | `(String value) -> Any` | Deserialize from JSON graph string (cross-language) |

## TypeAttr Columns
| Name | Callback Signature | Description |
|------|-------------------|-------------|
| `__data_to_json__` | `(const TObj*) -> json::Value` | Custom per-type serialization to JSON |
| `__data_from_json__` | `(json::Value) -> Any` | Custom per-type deserialization from JSON |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `ffi.ToJSONGraphString` | `(value: Any, metadata: Any) -> str` | Serialize object graph to JSON string |
| `ffi.FromJSONGraphString` | `(json_str: str) -> Any` | Deserialize object graph from JSON string |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| (Accessible via global function registry: `get_global_func("ffi.ToJSONGraphString")`) | | |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| (None) | | | |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| de541e3 | `2025-08-04-de541e37ad38.md` | JSON parser/writer with int64/double distinction |
| 8eaefe0 | `2025-08-05-8eaefe04a044.md` | ToJSONGraph/FromJSONGraph, __data_to_json__/__data_from_json__, Base64 |
| 7cb9273 | `2025-08-05-7cb92736b2ed.md` | ObjectCreator, Shape serialization |
| 55edee0 | `2025-08-06-55edee051c78.md` | String-based FFI wrappers (ToJSONGraphString/FromJSONGraphString) |
| 1a271f0 | `2025-08-15-1a271f00321b.md` | Fastmath-safe IEEE 754 helpers |
