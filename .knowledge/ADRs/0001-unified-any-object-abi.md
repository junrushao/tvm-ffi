---
scope:
  - "0001-c-abi.md"
  - "0003-any-system.md"
---
# ADR: Unified 16-byte TVMFFIAny Representation

**TL;DR**: Decision to unify all FFI values (POD scalars, object pointers, function arguments, return values) into a single 16-byte `TVMFFIAny` tagged union, replacing the legacy split between `TVMValue` + `type_code` pairs and separate object handles.

## Context
- The legacy TVM FFI used `TVMValue` (8-byte union) + `int type_code` as separate function arguments, requiring two arrays (values and type_codes) for every function call.
- Object handles were managed separately from scalar values, creating two distinct calling conventions depending on whether a value was a POD or an object.
- Different platforms require different alignment and padding, making the separate value+type_code scheme fragile across 32/64-bit platforms.

Usecases:
- Cross-language function calls where both POD values (int, float) and objects (String, Array) flow through the same argument mechanism.
- Container types like `Array<int>` that need to store POD values without boxing them into separate heap objects.
- Stable ABI across compiler versions, platforms (Linux/macOS/Windows/WASM), and shared library boundaries.

Design Decisions:
- **Use a single 16-byte struct** (`TVMFFIAny`) with `int32_t type_index` + `int32_t small_len` + 8-byte value union. Both POD values and object pointers share this representation.
- **Partition the type index space**: `[0, 64)` for POD/on-stack values, `[64, 128)` for static built-in objects, `[128, +inf)` for dynamic user-defined objects. The cutoff at 64 enables O(1) ownership decisions: `type_index < 64` means no ref-counting needed.
- **~~Share layout between stack values and object headers~~**: Originally, `TVMFFIAny` and `TVMFFIObject` shared `int32_t type_index` as their first field. As of commit 13436f0, this is **no longer true**: `TVMFFIObject` now places ref counts first (`strong_ref_count: u32` at offset 0), moving `type_index` to offset 8. The two structs now optimize for different goals -- `TVMFFIAny` optimizes for type dispatch, `TVMFFIObject` optimizes for atomic ref-count operations.
- **Reserve `small_len` for future optimization**: The second `int32_t` slot is reserved for potential small-string optimization but is currently unused, keeping the ABI stable for future extension.

## Implementation Notes
- `TVMFFIAny` is exactly 16 bytes on all platforms: `{int32 type_index, int32 small_len, union{int64/float64/void*/...} value}`.
- The `TVMFFIObject` header is 24 bytes: `{uint32 strong_ref_count, uint32 weak_ref_count, int32 type_index, uint32 __padding, void(*deleter)(self, flags)}`. The header was extended from 16 to 24 bytes (ca9c3d1) for weak counting, then reordered (13436f0) to place ref counts first. `type_index` no longer shares the first-field position with `TVMFFIAny` -- the two structs now diverge in their first 8 bytes.
- All function arguments are passed as `TVMFFIAny*` array. Return values are written to a single `TVMFFIAny*`. This replaces the legacy two-array `(TVMValue*, int*)` convention.
- `AnyView` (non-owning) and `Any` (owning) are C++ wrappers with `sizeof == 16`, layout-compatible with `TVMFFIAny` via `reinterpret_cast`.

## Related Design Docs
- [0001-c-abi.md](../designs/0001-c-abi.md) -- Full C ABI specification
- [0003-any-system.md](../designs/0003-any-system.md) -- C++ Any/AnyView wrappers
- [0006-type-traits.md](../designs/0006-type-traits.md) -- Conversion protocol between C++ types and TVMFFIAny
