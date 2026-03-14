---
scope:
  - "0012-json-and-serialization"
  - "0002-any-system"
---
# Reuse Any as JSON Value Type

**TL;DR**: The JSON module aliases `json::Value = Any`, `json::Object = Map<Any, Any>`, `json::Array = Array<Any>` rather than introducing JSON-specific value types. This keeps the module minimal (zero new type indices) at the cost of losing compile-time JSON type safety.

## Context

When adding a JSON module to the FFI, the fundamental question was how to represent parsed JSON values in C++. Two approaches were possible:

1. Define new JSON-specific types (e.g., `JsonNull`, `JsonNumber`, `JsonObject`) with dedicated type indices and registration.
2. Reuse the existing `Any`/`Array<Any>`/`Map<Any, Any>` type system as-is.

Constraints:
- The JSON module should be lightweight -- a utility, not a new subsystem.
- JSON values must be usable in all existing FFI infrastructure (containers, function calls, serialization).
- The extra API tier discourages new type indices for non-core features.

Usecases:
- Configuration parsing: JSON config files parsed into `Any` values for direct use in FFI function calls.
- Serialization interchange: JSON graph serialization (`ToJSONGraph`/`FromJSONGraph`) uses `json::Value` as the intermediate representation. Reusing `Any` means the serialized form is directly usable without conversion.
- Python integration: `json::Value` values can be passed to/from Python via the packed calling convention with zero conversion.

Design Decisions:
- **`json::Value = Any`**: The JSON value type is a direct alias for `Any`. No new type index, no new Object subclass, no registration.
- **`json::Object = Map<Any, Any>`**: JSON objects use the existing `Map` with `Any` keys rather than `Map<String, Any>`. This avoids the overhead of key-type checking during `as` conversion; string validation happens at runtime when keys are read or written by `JSONWriter`.
- **`json::Array = Array<Any>`**: JSON arrays use the existing typed array container.
- **JSON null = `nullptr` (`kTVMFFINone`)**: No separate JSON null type. This means JSON null is indistinguishable from FFI null.

## Implementation Notes

- The entire `json.h` header is 84 lines, consisting entirely of three type aliases and two function declarations.
- The JSON parser constructs `Any` values using existing type indices: `kTVMFFINone` (null), `kTVMFFIBool` (true/false), `kTVMFFIInt` (integers), `kTVMFFIFloat` (floats), `kTVMFFIStr`/`kTVMFFISmallStr` (strings), `kTVMFFIArray` (arrays), `kTVMFFIMap` (objects).
- The JSON writer dispatches on `value.type_index()` against these same type indices. Unrecognized types throw `ValueError`.
- Evidence: `de541e3` introduced the module; `8eaefe0` built JSON graph serialization on top of these aliases.

## Related Design Docs

- [`.knowledge/designs/0012-json-and-serialization.md`](../designs/0012-json-and-serialization.md) -- JSON module and graph serialization design
- [`.knowledge/designs/0002-any-system.md`](../designs/0002-any-system.md) -- The Any type erasure system reused as JSON value
- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- Array and Map containers used for JSON arrays and objects
