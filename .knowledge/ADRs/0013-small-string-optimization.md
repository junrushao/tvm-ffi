---
scope:
  - "0002-any-system"
  - "0005-containers"
  - "0001-c-abi"
---
# Small String Optimization (SSO) for String/Bytes

**TL;DR**: Strings up to 7 bytes are stored inline in `TVMFFIAny.v_bytes` as POD values, avoiding heap allocation and ref-counting. This changes `String` and `Bytes` from `ObjectRef` subclasses to value types backed by `details::BytesBaseCell`.

## Context

Short strings (type keys, field names, dtype strings like "float32", error kinds) are the most common string values in the FFI. Every such string previously required a heap allocation via `make_inplace_array_object`, an atomic ref-count increment on copy, and a decrement on destruction. Given the 16-byte `TVMFFIAny` has an 8-byte value union, 7 bytes of string content (plus implicit null terminator) can fit inline.

The `small_len` field (offset 4 in `TVMFFIAny`) was reserved since the initial ABI design but not activated. The `StringObj`/`BytesObj` types were moved to `tvm::ffi::details` namespace (commit `0342d85`) as a preparatory step to decouple the public API from the implementation.

## Alternatives Considered

1. **Keep all strings heap-allocated**: Simpler, no dual-representation complexity. But every short string incurs allocation + ref-counting overhead. The majority of FFI string values are short.

2. **Separate `SmallString` type**: Avoids breaking the `ObjectRef` hierarchy for `String`/`Bytes`. But doubles the API surface (two string types), requires conversion at every FFI boundary, and does not enable transparent optimization for existing code.

3. **Store SSO inline in `BytesObjBase`** (object-level SSO): Keep `String` as `ObjectRef` but store short strings inline in the object itself. Still requires heap allocation for the object header, just saves the inplace-array overhead. Does not eliminate allocation for the common case.

## Decision

Implement SSO at the `TVMFFIAny` level using new POD type indices `kTVMFFISmallStr = 11` and `kTVMFFISmallBytes = 12`. `String` and `Bytes` become value types (not `ObjectRef` subclasses) backed by `details::BytesBaseCell`, which holds a `TVMFFIAny data_` and branches on `type_index` to provide a uniform interface.

The SSO threshold is `kMaxSmallBytesLen = sizeof(int64_t) - 1 = 7`, derived from the 8-byte `v_bytes` union member minus one byte for the null terminator.

## Trade-offs

- **Pro**: Short strings (up to 7 bytes) avoid heap allocation entirely. This covers most type keys, field names, and common strings.
- **Pro**: Unified representation -- callers use `String`/`Bytes` without knowing whether content is inline or heap-allocated.
- **Pro**: `sizeof(String) == sizeof(Bytes) == 16`, same as before.
- **Pro**: `Optional<String>` is 16 bytes (no `std::optional` wrapper) using `kTVMFFINone` sentinel.

- **Con**: Breaking API change -- `String` and `Bytes` are no longer `ObjectRef` subclasses. Code using `String::use_count()`, `String::get()`, `Downcast<String>(ObjectRef)`, or assigning `String` to `ObjectRef` breaks.
- **Con**: `RValueRef<String>` no longer works (requires `ObjectRef`). Two tests were commented out.
- **Con**: Cross-representation equality/hash adds complexity (~8 comparison combinations in `AnyEqual`).
- **Con**: The `zero_padding` invariant must be maintained at ~25 write sites across 7 headers. Missing a site causes hash/equality bugs.
- **Con**: `TVMFFIDataTypeToString` C API signature changed from `TVMFFIObjectHandle*` to `TVMFFIAny*` out-param.

## Consequences

- `String` and `Bytes` are value types with dual representation (inline POD or heap object).
- All `TypeTraits<String>` and `TypeTraits<Bytes>` specializations are fully custom (not using `ObjectRefTypeTraitsBase`).
- `AnyHash` and `AnyEqual` handle cross-representation comparisons, using canonical heap type indices for hash consistency.
- The `zero_padding` field must be zeroed at every `CopyToAnyView`/`MoveToAny` site for all non-small-string types.
- `kTVMFFISmallStr = 11` and `kTVMFFISmallBytes = 12` consume two POD type index slots from the `[11, 63)` reserved range.

## Implementation Notes

- `details::BytesBaseCell` is the dual-storage engine. `InitSpaceForSize` decides inline vs heap. Copy/move constructors handle ref-counting for heap objects only.
- `TypeTable` constructor registers `kTVMFFISmallStr` and `kTVMFFISmallBytes` via `ReserveBuiltinTypeIndex`.
- Evidence: commits `0342d85` (namespace preparation), `f9d2bff` (SSO implementation).

## Related Design Docs

- [`.knowledge/designs/0002-any-system.md`](../designs/0002-any-system.md) -- zero_padding invariant, AnyHash/AnyEqual
- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- String/Bytes design
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- TVMFFIAny layout, new POD type indices
