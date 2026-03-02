---
design: "0008"
title: "JSON Ecosystem: Parser, Writer, and Object Graph Serialization"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-08-04"
last_updated: "2025-08-22"
scope:
  - "ffi/extra/json"
  - "ffi/extra/serialization"
  - "ffi/reflection/creator"
source_commits:
  - "de541e37ad3820033856cc8a0af55e896af55a3b"
  - "8eaefe04a044292e071263aca309b6991124c566"
  - "7cb92736b2ed95852ac71543937511acc7a3feec"
  - "55edee051c780af1831d7d04a40ddb8960ce01ed"
  - "1a271f00321b8cc16b72e58436716a05e2f62500"
  - "3f4f4f11184fc9862670d929a32ab81beb79286b"
source_ledgers:
  - ".memory/commits/2025-08-04-de541e37ad3820033856cc8a0af55e896af55a3b.md"
  - ".memory/commits/2025-08-05-8eaefe04a044292e071263aca309b6991124c566.md"
  - ".memory/commits/2025-08-05-7cb92736b2ed95852ac71543937511acc7a3feec.md"
  - ".memory/commits/2025-08-06-55edee051c780af1831d7d04a40ddb8960ce01ed.md"
  - ".memory/commits/2025-08-15-1a271f00321b8cc16b72e58436716a05e2f62500.md"
  - ".memory/commits/2025-08-22-3f4f4f11184fc9862670d929a32ab81beb79286b.md"
---

# JSON Ecosystem: Parser, Writer, and Object Graph Serialization

## TL;DR
- A self-contained JSON parser/writer (`json::Parse`/`json::Stringify`) reuses FFI value types (`Any`, `Array<Any>`, `Map<Any,Any>`) as the JSON DOM, avoiding a separate AST while enabling parsed data to be immediately consumed by any FFI function.
- A reflection-based object graph serializer (`ToJSONGraph`/`FromJSONGraph`) preserves object identity through node deduplication and supports custom per-type serialization hooks via `TypeAttrColumn` (`__data_to_json__`/`__data_from_json__`).
- A `reflection::ObjectCreator` factory constructs objects from `Map<String, Any>` field maps using reflection metadata, enabling the deserializer to reconstruct typed objects without compile-time knowledge of concrete types.

## Problem Statement
Cross-language serialization of the FFI object system requires two layers: (1) a general JSON parser/writer for the wire format, and (2) an object-graph-aware serializer that handles reference sharing, type identity, and per-type custom serialization. Without these layers, Python and Rust bindings cannot persist or transport IR objects, and debugging tools cannot inspect object graphs as human-readable text.

## Context and Constraints
- The JSON parser/writer must live in `extra/`, gated by `TVM_FFI_USE_EXTRA_CXX_API`, following [ADR-0009](.memory/ADRs/0009-extra-api-isolation.md).
- Reusing `Any` as the JSON value type avoids a separate DOM layer but conflates JSON `null` with FFI `None`/`nullptr`.
- The object graph serializer must handle shared references (same object referenced from multiple fields) by serializing each object once and using integer indices.
- Forward references during deserialization are required to support arbitrary node ordering in the JSON graph.
- Builds with `-ffast-math` must correctly handle `NaN` and `Infinity` literals, since `std::isnan`/`std::isinf` are unreliable under that flag.

## Goals
- Provide a lightweight JSON parser that handles standard JSON plus `Infinity`/`NaN` and `int64_t` (not just `double`).
- Provide a JSON writer with optional pretty-printing, cycle detection, and `Inf`/`NaN` output.
- Provide object-graph serialization that preserves type identity, object sharing, and supports custom per-type hooks.
- Provide `reflection::ObjectCreator` for constructing objects from `Map<String, Any>` using reflection metadata.
- Provide string-typed convenience wrappers (`ToJSONGraphString`/`FromJSONGraphString`) for cross-language consumers.

## Non-Goals
- Full JSON schema validation or JSON Pointer support.
- Streaming (SAX-style) parsing -- the parser builds the full DOM.
- Thread-safe serialization or parallel object graph traversal.
- Binary serialization formats (e.g., MessagePack, BSON).

## Design
### Components and Responsibilities

- **`json::Parse`** (function, `extra/json.h`): Recursive-descent JSON parser. Uses `JSONParserContext` for character-level scanning and `JSONParser` for grammar rules. Temporary stacks (`array_temp_stack_`, `object_temp_stack_`) accumulate children before batch-constructing immutable containers with exact size. Supports `Infinity`/`-Infinity`/`NaN` literals. Distinguishes `int64_t` from `double` by attempting `strtoimax` first. Reports errors with line/column/char-offset context. Supports error-string-out mode via `String* error_msg` parameter.

- **`json::Stringify`** (function, `extra/json.h`): Serializer that handles `Array`, `List<Any>` (with cycle detection via `unordered_set<const void*>`), and `Map` (with runtime string-key enforcement). Supports optional pretty-printing with configurable indent. Prints integer-valued doubles with `.0` suffix to preserve round-trip fidelity.

- **`json::Value`/`json::Object`/`json::Array`** (type aliases, `extra/json.h`): `json::Value = Any`, `json::Object = Map<Any, Any>`, `json::Array = Array<Any>`. These aliases allow JSON values to flow through the FFI type system without conversion.

- **`ToJSONGraph`** (function, `extra/serialization.h`): Serializes any `ffi::Any` to the JSON object graph format. Uses `ObjectGraphSerializer` internally, which maintains `Map<Any, int64_t>` for node deduplication. For objects with reflection metadata, fields with statically-known primitive types (bool, int, float, DataType) are inlined; all other fields are stored as node indices. Custom serialization via `__data_to_json__` TypeAttrColumn hooks.

- **`FromJSONGraph`** (function, `extra/serialization.h`): Deserializes the JSON object graph back to `ffi::Any`. Uses `ObjectGraphDeserializer` which lazily decodes nodes, allowing forward references. Custom deserialization via `__data_from_json__` TypeAttrColumn hooks. Supports arbitrary node ordering.

- **`ToJSONGraphString`/`FromJSONGraphString`** (functions, `extra/serialization.h`): Convenience wrappers that accept/return `String` instead of `json::Value`, composing `json::Parse`/`json::Stringify` with the graph serialization functions.

- **`reflection::ObjectCreator`** (class, `reflection/creator.h`): Constructs objects from `Map<String, Any>` by: (1) calling `TVMFFITypeMetadata.creator` to allocate via `make_object<T>()`, (2) walking `ForEachFieldInfo` parent-to-child, (3) matching map keys to field names, (4) applying defaults for unset fields, (5) detecting extra/missing fields with diagnostics.

- **`Base64Encode`/`Base64Decode`** (header-only, `extra/base64.h`): Utilities for `Bytes` serialization within the JSON graph format.

- **FastMath-safe IEEE 754 helpers** (static methods in parser/writer): Under `__FAST_MATH__`, use union-based type punning (`union { uint64_t from; double to; } u;`) for `NaN`/`Inf` construction and exponent/mantissa extraction for classification, bypassing `std::isnan`/`std::isinf` which are unreliable under `-ffast-math`. The union approach replaces the earlier `reinterpret_cast` type punning (commit `3f4f4f1`) to avoid `-Werror=strict-aliasing` violations under GCC with `-ffast-math`.

### Data Contracts and Invariants
- **JSON graph format**: `{"root_index": <int>, "nodes": [{"type": "<key>", "data": ...}, ...], "metadata": ...}`. Each node has `type` (type key) and `data` (type-specific payload).
- **Primitive inlining**: Object fields with static type index for `bool`, `int`, `float`, or `DataType` are inlined directly in the node data. All other fields are stored as integer indices into the `nodes` array.
- **Shape serialization**: `Shape` values are encoded as `{"type": "ffi.Shape", "data": [dim0, dim1, ...]}`.
- **Bytes serialization**: `Bytes` values are base64-encoded strings.
- **Node deduplication**: Shared object references produce a single node entry; subsequent references use the same integer index.
- **Forward reference support**: The deserializer lazily decodes nodes, so a node at index N can reference a node at index M > N.
- **Map key type**: `json::Object = Map<Any, Any>` defers string-key checking to access time (writer enforces string keys at serialization time).
- **Integer round-trip**: Integers are parsed as `int64_t` (not `double`). Writer emits `1.0` for `double(1)` to preserve type distinction.
- **`ObjectCreator` field matching**: Required fields without defaults cause `TypeError` on construction. Extra fields in the map that do not match any reflected field cause `TypeError`.

### Control Flow

**JSON Parsing:**
1. `json::Parse(str)` -> `JSONParser::ParseValue()` -> dispatch on first character: `{` (object), `[` (array), `"` (string), `-`/digit (number), `t`/`f` (bool), `n` (null), `I`/`N` (Infinity/NaN).
2. For objects: parse key-value pairs into `object_temp_stack_`, batch-construct `Map<Any, Any>` with exact size.
3. For arrays: parse elements into `array_temp_stack_`, batch-construct `Array<Any>` with exact size.

**Object Graph Serialization:**
1. `ToJSONGraph(value)` -> `ObjectGraphSerializer::Serialize(value)` -> walk the value recursively.
2. For each object: check `Map<Any, int64_t>` dedup map. If already seen, return its index. Otherwise, allocate a new node index, call `CreateObjectData()` to produce the node's data.
3. `CreateObjectData()`: check `__data_to_json__` TypeAttrColumn. If present, call the custom hook. Otherwise, walk `ForEachFieldInfo` and serialize each field (inlining primitives, referencing other objects by index).
4. Result: `{"root_index": N, "nodes": [...], "metadata": ...}`.

**Object Graph Deserialization:**
1. `FromJSONGraph(json)` -> `ObjectGraphDeserializer::Deserialize()` -> read `root_index`, then lazily decode nodes.
2. For each node: look up `type` key, call `ObjectCreator` or `__data_from_json__` hook to reconstruct the object.
3. Integer references in field data are resolved by recursively deserializing the referenced node (lazy, handles forward references).

### Extension Points
- **Custom serialization hooks**: Register `__data_to_json__`/`__data_from_json__` via `TypeAttrDef<T>().def(...)` for types that need special serialization logic.
- **New built-in serializable types**: Add cases to the serializer/deserializer dispatch for new container types (Shape was added in commit `7cb9273`).
- **New JSON literal types**: The parser's dispatch table can be extended to handle additional non-standard literals.

## Alternatives Considered
### Dedicated JSON AST nodes (separate from FFI types)
- Pros: Clean separation of JSON and FFI type systems. JSON null is distinct from FFI None.
- Cons: Requires conversion between JSON AST and FFI types on every use. Adds another object hierarchy. Doubles the memory for parsed JSON that is immediately consumed by FFI functions.

### protobuf/FlatBuffers for object graph serialization
- Pros: Schema-defined. Compact binary format. Cross-language.
- Cons: Requires schema maintenance for every new IR node type. Not human-readable for debugging. Build-time code generation dependency.

### Map<String, Any> for JSON objects (instead of Map<Any, Any>)
- Pros: Type-safe keys at construction time.
- Cons: Requires `as<String>()` checking on every key insertion during parsing, adding overhead. The current approach defers checking to access time.

## Trade-offs
- **Optimized**: Reuse of FFI type system (no conversion layer), compact batch construction (temporary stacks + exact-size containers), human-readable format for debugging, lazy deserialization for forward references.
- **Sacrificed**: JSON null/FFI None conflation, `Map<Any, Any>` defers key-type checking, parser does not support streaming, writer does not support custom formatters.

## Interfaces and Compatibility
- **C++ API**: `json::Parse`, `json::Stringify`, `ToJSONGraph`, `FromJSONGraph`, `ToJSONGraphString`, `FromJSONGraphString`, `reflection::ObjectCreator`.
- **Global functions**: `ffi.json.Parse`, `ffi.json.Stringify`, `ffi.ToJSONGraph`, `ffi.FromJSONGraph`, `ffi.ToJSONGraphString`, `ffi.FromJSONGraphString`.
- **TypeAttrColumn hooks**: `__data_to_json__`, `__data_from_json__` for custom per-type serialization.
- **CMake**: All source files in `src/ffi/extra/`, gated by `TVM_FFI_USE_EXTRA_CXX_API`.

## Failure Modes and Mitigations
- **Malformed JSON**: Parser produces error messages with line/column/char-offset context. Supports error-string-out mode for callers that want to handle errors without exceptions.
- **Missing reflection metadata**: `ObjectCreator` throws `RuntimeError` if the type has no metadata or no creator callback.
- **Missing required field**: `ObjectCreator` throws `TypeError` listing the missing field and type.
- **Cycle in writer input**: `json::Stringify` detects cycles in `List<Any>` via `unordered_set<const void*>` and throws on cycle detection.
- **Non-string map key in writer**: `json::Stringify` enforces string keys at write time and throws if a non-string key is encountered.
- **`-ffast-math` NaN/Inf handling**: FastMath-safe bit-level helpers using union-based type punning ensure correct behavior under `-ffast-math` on GCC/Clang without triggering `-Werror=strict-aliasing`. MSVC's `/fp:fast` does not define `__FAST_MATH__`, so the standard library path is used (correct because MSVC's `/fp:fast` does not eliminate NaN/Inf comparisons as aggressively). The union approach is well-defined in C (C99 6.5.2.3) and accepted by all major C++ compilers as a practical extension.

## Observability and Validation
- `tests/cpp/extra/test_json_parser.cc`: Tests primitives, strings, unicode, escapes, error messages with position context, nesting.
- `tests/cpp/extra/test_json_writer.cc`: Tests all value types, indent, List cycle detection, Inf/NaN, error cases.
- `tests/cpp/extra/test_json_serialization.cc`: Tests primitive types, containers, custom object serialization via hooks, metadata attachment, node order independence (ShuffleNodeOrder test), Shape round-trip.
- `tests/cpp/test_reflection.cc`: Tests `ObjectCreator` construction from `Map<String, Any>`.

## Migration and Rollout
- The JSON parser/writer and object graph serializer are new additions (not replacing existing infrastructure). They are available immediately after enabling `TVM_FFI_USE_EXTRA_CXX_API` (default ON).
- `ObjectCreator` is a higher-level alternative to `MakeObjectFromPackedArgs`. The latter uses packed positional args with alternating key-value pairs; the former uses a typed `Map<String, Any>`. Both are available; `ObjectCreator` is preferred for C++ callers.

## Diagrams
- [.memory/diagrams/0006-json-ecosystem-architecture.md](.memory/diagrams/0006-json-ecosystem-architecture.md)

## Related ADRs
- [.memory/ADRs/0009-extra-api-isolation.md](.memory/ADRs/0009-extra-api-isolation.md) -- all JSON files live in `extra/`, gated by `TVM_FFI_USE_EXTRA_CXX_API`.

## Evidence Matrix
- `json::Value = Any`, `json::Object = Map<Any, Any>`, `json::Array = Array<Any>` type aliases -> `.memory/commits/2025-08-04-de541e37ad3820033856cc8a0af55e896af55a3b.md` + `de541e3` + `include/tvm/ffi/extra/json.h` lines 40-51
- `json::Parse` / `json::Stringify` declarations -> `.memory/commits/2025-08-04-de541e37ad3820033856cc8a0af55e896af55a3b.md` + `de541e3` + `include/tvm/ffi/extra/json.h` lines 68-79
- Recursive-descent parser with temp stacks -> `.memory/commits/2025-08-04-de541e37ad3820033856cc8a0af55e896af55a3b.md` + `de541e3` + `src/ffi/extra/json_parser.cc` (692 LOC)
- Writer with cycle detection and indent -> `.memory/commits/2025-08-04-de541e37ad3820033856cc8a0af55e896af55a3b.md` + `de541e3` + `src/ffi/extra/json_writer.cc` (266 LOC)
- `ToJSONGraph`/`FromJSONGraph` API and JSON graph format -> `.memory/commits/2025-08-05-8eaefe04a044292e071263aca309b6991124c566.md` + `8eaefe0` + `include/tvm/ffi/extra/serialization.h`
- `__data_to_json__`/`__data_from_json__` TypeAttrColumn hooks -> `.memory/commits/2025-08-05-8eaefe04a044292e071263aca309b6991124c566.md` + `8eaefe0` + `src/ffi/extra/serialization.cc`
- `Base64Encode`/`Base64Decode` -> `.memory/commits/2025-08-05-8eaefe04a044292e071263aca309b6991124c566.md` + `8eaefe0` + `include/tvm/ffi/extra/base64.h`
- Node deduplication via `Map<Any, int64_t>` -> `.memory/commits/2025-08-05-8eaefe04a044292e071263aca309b6991124c566.md` + `8eaefe0` + `src/ffi/extra/serialization.cc`
- `reflection::ObjectCreator` from `Map<String, Any>` -> `.memory/commits/2025-08-05-7cb92736b2ed95852ac71543937511acc7a3feec.md` + `7cb9273` + `include/tvm/ffi/reflection/creator.h`
- Shape serialization `{"type": "ffi.Shape", "data": [...]}` -> `.memory/commits/2025-08-05-7cb92736b2ed95852ac71543937511acc7a3feec.md` + `7cb9273` + `src/ffi/extra/serialization.cc`
- `CreateObjectData` return type relaxed from `json::Object` to `json::Value` -> `.memory/commits/2025-08-05-7cb92736b2ed95852ac71543937511acc7a3feec.md` + `7cb9273` + `src/ffi/extra/serialization.cc`
- `ToJSONGraphString`/`FromJSONGraphString` convenience wrappers -> `.memory/commits/2025-08-06-55edee051c780af1831d7d04a40ddb8960ce01ed.md` + `55edee0` + `src/ffi/extra/serialization.cc`
- Global functions `ffi.ToJSONGraphString`/`ffi.FromJSONGraphString` -> `.memory/commits/2025-08-06-55edee051c780af1831d7d04a40ddb8960ce01ed.md` + `55edee0`
- FastMath-safe IEEE 754 helpers (`FastMathSafePosInf`, `FastMathSafeNaN`, `FastMathSafeIsNaN`, `FastMathSafeIsInf`) -> `.memory/commits/2025-08-15-1a271f00321b8cc16b72e58436716a05e2f62500.md` + `1a271f0` + `src/ffi/extra/json_parser.cc`, `src/ffi/extra/json_writer.cc`
- `__FAST_MATH__` guard for parser/writer -> `.memory/commits/2025-08-15-1a271f00321b8cc16b72e58436716a05e2f62500.md` + `1a271f0`
- Union-based type punning replacing `reinterpret_cast` (strict-aliasing fix) -> `.memory/commits/2025-08-22-3f4f4f11184fc9862670d929a32ab81beb79286b.md` + `3f4f4f1` + `src/ffi/extra/json_parser.cc` (3 sites), `src/ffi/extra/json_writer.cc` (2 sites)

## Open Questions
- Should the JSON parser support JSON5 extensions (comments, trailing commas)?
- Should `json::Object` use `Map<String, Any>` to provide compile-time key-type safety at the cost of parsing performance?
- Should the FastMath-safe helpers be extracted to a shared utility header to reduce duplication across parser, writer, and test files? (Note: the helpers now use union-based type punning which is more consistent across sites, but the code is still duplicated.)

## Confidence and Risk
- Confidence: high
- Residual risks: The `Map<Any, Any>` key type means non-string keys are only caught at write/access time, not at parse time. The conflation of JSON `null` and FFI `None` could cause surprises if the serialization format is extended to distinguish them. The FastMath helpers (now using union-based type punning) are duplicated across three files (parser, writer, test).
