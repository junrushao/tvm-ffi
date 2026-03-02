---
adr: "0003"
title: "Inline Small String Optimization in TVMFFIAny"
status: "accepted"
date: "2025-05-06"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "performance"
  - "abi"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
source_ledgers:
  - ".memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md"
---

# ADR-0003: Inline Small String Optimization in TVMFFIAny

## TL;DR
- Strings of 7 bytes or fewer are stored directly inside the 16-byte `TVMFFIAny` value, avoiding heap allocation and reference counting entirely.
- The `small_str_len` field (overlapping `zero_padding` in the union) stores the length, and `v_bytes[0..6]` holds the characters plus a null terminator.

## Status
Accepted

## Context
String values are extremely common in TVM FFI: type keys, error messages, function names, IR node attributes. Many of these are short (e.g., "int32", "float16", "cpu", "bool"). Without optimization, every string requires a heap-allocated `StringObj` with reference counting overhead (allocation + atomic incref/decref).

The `TVMFFIAny` struct is already 16 bytes with an 8-byte value union that is unused for string types beyond the pointer. The question is whether to repurpose this space.

## Decision Drivers
- Performance: avoiding heap allocation for short strings eliminates malloc overhead and cache misses.
- ABI compactness: the optimization must fit within the existing 16-byte layout without growing `TVMFFIAny`.
- Correctness: the representation must be distinguishable from heap-allocated strings at the type-index level.
- Compatibility: foreign language bindings must be able to decode small strings without calling into C++.

## Decision
Reuse the existing `TVMFFIAny` layout for small strings:

| Field | Offset | Usage for small string |
|-------|--------|----------------------|
| `type_index` | 0-3 | `kTVMFFISmallStr` (11) or `kTVMFFISmallBytes` (12) |
| `small_str_len` | 4-7 | Length of the string (0-7), union-overlapping `zero_padding` |
| `v_bytes[0..7]` | 8-15 | Character data (up to 7 chars + implicit null at `v_bytes[small_str_len]`) |

The maximum inline length is 7 because `v_bytes` is 8 bytes and one byte is needed for the null terminator to ensure C string compatibility.

Two distinct type indices are used: `kTVMFFISmallStr` (11) for UTF-8 strings and `kTVMFFISmallBytes` (12) for binary data.

**Key invariant**: `Any::type_index` is never `kTVMFFIRawStr` (non-owning `const char*`). When an `AnyView` holding `kTVMFFIRawStr` is converted to an owning `Any`, short strings are promoted to `kTVMFFISmallStr` and longer strings are promoted to heap-allocated `StringObj` (type index `kTVMFFIStr = 65`).

## Alternatives Considered
### No SSO (always heap-allocate strings)
- Pros: Simpler. One code path for all strings.
- Cons: Significant overhead for the most common string lengths. Every type key lookup would allocate.

### SSO with larger inline buffer (growing TVMFFIAny to 24 or 32 bytes)
- Pros: Can store longer strings inline (up to 15 or 23 bytes).
- Cons: Every `TVMFFIAny` value grows, including non-string values. Function call argument arrays become 50-100% larger. Cache pressure increases.

### External SSO (in StringObj, not TVMFFIAny)
- Pros: Does not affect `TVMFFIAny` layout. Can use larger buffers.
- Cons: Still requires heap allocation for `StringObj`. Misses the main optimization target (avoiding allocation entirely).

## Why This Option Won
- Zero additional space: the optimization is free because it uses already-allocated bytes in the union.
- 7-byte limit covers the vast majority of type keys, attribute names, and short strings in ML workloads.
- The type index distinction (`kTVMFFISmallStr` vs `kTVMFFIStr`) makes dispatch trivial.
- Foreign bindings can read small strings by just accessing `small_str_len` and `v_bytes` -- no function call needed.

## Consequences
### Positive
- No heap allocation for strings <= 7 bytes.
- No reference counting overhead for small strings (they are value types).
- Copy of small strings is a 16-byte memcpy (trivially fast).
- Reduces pressure on the global allocator in hot paths.

### Negative
- Two code paths for string handling everywhere: callers must check `type_index` for `kTVMFFISmallStr` vs `kTVMFFIStr`.
- The 7-byte limit is tight; strings like "float32" (7 chars) just barely fit, but "float128" (8 chars) does not.
- The `small_str_len` field overlapping `zero_padding` means that the padding invariant (`zero_padding == 0`) does not hold for small strings. All code that checks `zero_padding` must be aware of this.

### Risks
- Bugs where code assumes `zero_padding == 0` for all types. Mitigated by having distinct type indices and explicit documentation.
- Future need for longer inline strings (e.g., 15 bytes) would require growing `TVMFFIAny`, which is an ABI break. Mitigated by the current limit being sufficient for common strings.

## Implementation Notes
- `TVMFFIAny` struct in `include/tvm/ffi/c_api.h` defines the union layout.
- `AnyView` constructors in `include/tvm/ffi/any.h` implement the SSO: `std::string_view` input is checked for length <= 7.
- `TVMFFIAnyViewToOwnedAny` in C ABI handles promotion from `kTVMFFIRawStr` to `kTVMFFISmallStr` or `kTVMFFIStr`.

## Validation
- `tests/cpp/test_ffi_any.cc` tests small string creation, comparison, and round-tripping.
- `tests/cpp/test_ffi_string.cc` tests String construction from small and large inputs.

## Migration and Rollback
- This is a foundational ABI design from the root commit. Changing the small string threshold or layout requires an ABI version bump.

## Related Design Docs
- [.memory/designs/0001-type-erased-any-value-system.md](.memory/designs/0001-type-erased-any-value-system.md)
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)

## Related Diagrams
- [.memory/diagrams/0001-any-value-memory-layout.md](.memory/diagrams/0001-any-value-memory-layout.md)

## Evidence Matrix
- Small string fields in TVMFFIAny -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `include/tvm/ffi/c_api.h` lines 287-333
- kTVMFFISmallStr=11, kTVMFFISmallBytes=12 -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 128-129
- Ledger note on SSO -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` Reflection section
- RawStr-to-SmallStr promotion invariant -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 100-103

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Profile whether the 7-byte threshold captures the majority of strings in real workloads.
- Consider adding a metric for SSO hit rate in debug builds.
- **Completed**: [ADR-0010](.memory/ADRs/0010-string-bytes-as-value-types.md) extended this SSO design by rewriting `String`/`Bytes` from `ObjectRef` subclasses to standalone value types backed by `BytesBaseCell`, making SSO the default representation (not just an `Any`-level optimization). The `zero_padding` invariant now requires explicit zeroing in all non-small-string `TypeTraits` specializations.
