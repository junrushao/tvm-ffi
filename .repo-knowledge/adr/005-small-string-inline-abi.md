# ADR 005: Inline Small Strings in TVMFFIAny

- Status: Accepted
- Date: 2025-08-04
- Owners: Tianqi Chen

## Context

Short strings (field names, type keys, small identifiers) are among the most
frequently created values in the TVM FFI. Every such string previously required
a heap-allocated `StringObj` with reference counting, even for strings of just
a few bytes. This creates memory pressure, reduces cache locality, and adds
allocation/deallocation overhead on hot paths such as field lookup and type
dispatch.

The `TVMFFIAny` union has 8 bytes available in its value slot
(`v_handle`/`v_int64`/`v_float64`). Strings that fit within this slot can be
stored inline without heap allocation.

## Decision

Add two new type indices to the C ABI:

- `kTVMFFISmallStr`: Inline string stored directly in the `TVMFFIAny` value slot.
- `kTVMFFISmallBytes`: Inline byte sequence stored in the same slot.

A `zero_padding` field was added to the `TVMFFIAny` union to ensure unused
bytes are zeroed. This is required for correct equality comparison via the
`v_uint64` field, since two logically equal small strings must produce the same
bit pattern.

All code that previously checked `type_index == kTVMFFIStr` must now check
`type_index == kTVMFFIStr || type_index == kTVMFFISmallStr` (and analogously
for bytes). The `AnyView`, `Any`, `TypeTraits`, cast machinery, `Optional`,
`RValueRef`, `Variant`, `DType`, reflection accessor, structural equal/hash,
and `String`/`Bytes` classes were all updated.

This is an **ABI-breaking change**: the `TVMFFIAny` union layout changed, and
all pre-compiled binaries must be recompiled.

## Consequences

- Positive: Short strings avoid heap allocation entirely, reducing memory
  pressure and improving cache locality on hot paths (field lookup, type
  dispatch, JSON key processing).
- Positive: The `zero_padding` field ensures correctness of bitwise equality
  for all `TVMFFIAny` values, not just small strings.
- Negative: **Breaking C ABI change**. All shared libraries and bindings must
  be recompiled. Type-checking code must handle both inline and heap variants.
- Negative: Increased complexity in `string.h` (+422/-145 lines) to handle
  dual representations.
- Migration/Rollout: Recompile all code using `TVMFFIAny`. Update type index
  checks to handle `kTVMFFISmallStr`/`kTVMFFISmallBytes`. The dual-check
  pattern is encapsulated in helper functions in `string.h`.

## References
- Range summary: `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
- Evidence commits: `49e2ed4a169918d346fe8f96c208a4cec56cf3e8`
- External references: none

## Related Design Docs
- `.repo-knowledge/design/001-type-erased-value-system.md`
- `.repo-knowledge/design/003-c-abi-stability.md`

## Notes
The small string optimization is transparent to most callers via the `String`
and `Bytes` C++ classes, which automatically choose between inline and heap
storage based on length. The threshold for inline storage is determined by the
available bytes in the `TVMFFIAny` union value slot (typically 7 bytes for
null-terminated strings).
