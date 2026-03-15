---
scope:
  - "0012-json-and-serialization"
  - "0002-any-value-system"
  - "0008-containers"
---
# Represent JSON Values Using Existing FFI Types Rather Than New Object Subclasses

**TL;DR**: The decision to represent JSON values as `Any` (scalars/null), `Array<Any>` (arrays), and `Map<Any, Any>` (objects) via type aliases, rather than introducing dedicated `JsonValue`/`JsonObject`/`JsonArray` object types.

## Context
- The JSON parser/writer needed a value representation for parsed JSON data.
- Two options: (a) define new object types (`JsonValueObj`, `JsonObjectObj`, `JsonArrayObj`) with dedicated type indices, or (b) reuse existing FFI types through lightweight aliases.
- The JSON subsystem lives in `extra/` (non-core), so adding new core type indices for JSON would break the isolation boundary.
- The existing type system already supports all JSON value types: `nullptr_t` (null), `bool`, `int64_t`, `double`, `String`, `Array<Any>`, `Map<Any, Any>`.

Usecases:
- Parsing configuration JSON and passing results through the FFI as `Any` values without special handling.
- Serializing FFI objects to JSON using the same container types used elsewhere in the system.
- Storing parsed JSON values in `Any`-typed containers without boxing or conversion.

Design Decisions:
- **`json::Value = Any`**: Any JSON value is a type-erased `Any`. Scalars (`int64_t`, `double`, `bool`, `nullptr_t`, `String`) are stored directly. Compound types (`Array<Any>`, `Map<Any, Any>`) are stored as object references inside `Any`.
- **`json::Object = Map<Any, Any>`** rather than `Map<String, Any>`: Avoids the overhead of `TypeTraits<String>::CheckAnyStrict` key checking at insertion time for the map. JSON keys are always strings, but the type check happens at read time when extracting keys, not at write time. This trades compile-time key-type safety for insertion performance.
- **`json::Array = Array<Any>`**: Standard FFI array with `Any` element type, allowing heterogeneous JSON arrays.
- **No new type indices, no new TypeTraits, no new Object subclasses**: The entire JSON value model is expressed in 3 lines of `using` declarations.

## Implementation Notes
- The type aliases are defined in `include/tvm/ffi/extra/json.h`.
- The JSON parser writes directly into `Any` output slots, and the writer dispatches on `TypeIndex` to determine the serialization format.
- `Map<Any, Any>` preserves insertion order (via the insertion-order-preserving dense hashmap), ensuring deterministic key ordering in serialized JSON.
- The trade-off of losing compile-time key-type checking on `Map<Any, Any>` is acceptable because the JSON parser always inserts `String` keys, and any incorrect usage (non-string key) will surface at runtime when the consumer tries to cast the key to `String`.

## Related Design Docs
- [0012-json-and-serialization.md](../designs/0012-json-and-serialization.md)
- [0002-any-value-system.md](../designs/0002-any-value-system.md)
- [0008-containers.md](../designs/0008-containers.md) -- Map insertion-order preservation
