# ADR-001: Unified Any and Object Type Index Layout

> Status: Accepted
> Decided in: commit 7d34eb8 ("[REFACTOR] Introduce and modernize FFI system")

## Context

The FFI needs a type-erased value representation for function arguments and return
values. Previous designs used separate representations for packed function argument
types (integer codes) and object types (separate type system). This led to:

- Inability to store POD values directly in typed containers (e.g., `Array<int>`
  required boxing int into an object)
- Dual-path conversion logic everywhere arguments are processed
- Separate serialization and type-checking paths for POD and object values

## Decision

Use a single 16-byte `TVMFFIAny` structure where `type_index` at offset 0 is shared
with `TVMFFIObject`, unifying POD values and object references under one type tag
system:

```
TVMFFIAny  = { int32_t type_index, int32_t small_len, 8-byte union }  -- 16 bytes
TVMFFIObject = { int32_t type_index, int32_t ref_counter, 8-byte deleter } -- 16 bytes (at decision time)
```

**Note**: `TVMFFIObject` was later expanded to 24 bytes in commit ca9c3d1 to add weak reference counting (`weak_ref_count` + `strong_ref_count`). `TVMFFIAny` remains 16 bytes. See `.knowledge/ADRs/014-weak-ref-24byte-header.md`.

```text
Current (ca9c3d1+):
TVMFFIObject = { type_index, weak_ref_count, strong_ref_count, deleter(obj, flags) } -- 24 bytes
```

POD values (int, float, bool, etc.) use type indices in `[0, 64)`. Object references
use indices `>= 64`. A single integer comparison (`type_index >= kTVMFFIStaticObjectBegin`)
distinguishes POD from object values.

## Consequences

### Positive

- `Array<int>` works natively: the Any elements hold `type_index=kTVMFFIInt` with
  the int64 value inline. No boxing to heap objects required.
- Single `TypeTraits<T>` protocol handles all types uniformly
- Function call arguments are a flat `AnyView[]` array -- no polymorphism, no
  variant types, no virtual calls in the hot path
- Containers (Array, Map) store `Any` elements that can hold both POD and objects

### Negative

- The 16-byte fixed size means large POD values (e.g., 128-bit integers) cannot
  be stored inline (would need to be boxed as objects)
- The `small_len` field is currently unused (reserved for future small-string
  optimization), consuming 4 bytes in every value

### Neutral

- The shared type_index space means POD type indices and object type indices must
  not conflict, requiring careful range partitioning (see ADR-003)
