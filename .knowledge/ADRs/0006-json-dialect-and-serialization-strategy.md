---
scope:
  - "0010-json-and-serialization.md"
---
# ADR: Extended JSON Dialect and Reflection-Based Serialization Strategy

**TL;DR**: Decision to extend JSON with JavaScript-style `Infinity`/`NaN` and `int64` preservation, and to build object graph serialization on top of the existing reflection + TypeAttrColumn infrastructure rather than a separate visitor pattern or external serialization framework.

## Context
- ML workloads produce `NaN` and `Infinity` values that must survive serialization roundtrips. Standard JSON (RFC 8259) has no representation for these.
- The FFI type system distinguishes `int64_t` from `double`. Standard JSON conflates all numbers into IEEE 754 doubles, which would destroy type fidelity for large integers and cause silent precision loss.
- Object graph serialization is needed for persistence, debugging, and cross-process communication. The reflection system already has per-field traversal (`ForEachFieldInfo`) and per-type custom dispatch (`TypeAttrColumn`), making it a natural foundation.

Usecases:
- Serializing compiler IR (which contains NaN sentinels and integer shape dimensions) to JSON for debugging and persistence.
- Cross-language serialization where Python, C++, and Rust callers need consistent type preservation.
- Custom serialization for types with computed fields or external state (e.g., `TIntObj` with custom JSON format).

Design Decisions:
- **Extend JSON with `Infinity`/`NaN` literals**: JavaScript-style literals are recognized by the parser and emitted by the writer. Under `-ffast-math`, union-based IEEE 754 bit manipulation replaces `std::isnan`/`std::isinf` which the compiler may optimize away.
- **Preserve `int64` vs `double` distinction**: Integers without fractional/exponent parts are stored as `int64_t`. The writer appends `.0` to integer-valued doubles (e.g., `42.0`) to disambiguate from int64 values (`42`) on roundtrip.
- **Build serialization on reflection + TypeAttrColumn**: Use `ForEachFieldInfo` for generic field traversal and `__data_to_json__`/`__data_from_json__` TypeAttrColumn entries for custom per-type serialization, paralleling the `__s_equal__`/`__s_hash__` pattern from structural equality.
- **Require default constructors for deserialization**: `FromJSONGraph` uses `TVMFFITypeMetadata.creator` (default constructor) to allocate empty objects before populating fields. This is an intentional trade-off: types that participate in serialization must be default-constructible.

## Implementation Notes
- `json::Parse` and `json::Stringify` are registered as global FFI functions (`ffi.json.Parse`, `ffi.json.Stringify`) for cross-language access.
- `ToJSONGraph`/`FromJSONGraph` are registered as `ffi.ToJSONGraph`/`ffi.FromJSONGraph`, with string convenience wrappers as `ffi.ToJSONGraphString`/`ffi.FromJSONGraphString`.
- The custom serialization protocol uses the same `TypeAttrDef<T>.def("__data_to_json__", ...)` pattern as structural equality's `__s_equal__`.
- `ObjectCreator` provides an alternative to `MakeObjectFromPackedArgs` for map-based construction: it accepts `Map<String, Any>` instead of positional packed args.

## Related Design Docs
- [0010-json-and-serialization.md](../designs/0010-json-and-serialization.md)
- [0008-reflection.md](../designs/0008-reflection.md)
- [0009-structural-equal-hash.md](../designs/0009-structural-equal-hash.md)
