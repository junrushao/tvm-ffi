---
adr: "0010"
title: "Rewrite String/Bytes as Value Types Backed by BytesBaseCell"
status: "accepted"
date: "2025-08-04"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "abi"
  - "breaking-change"
source_commits:
  - "f9d2bff8444250bdac336eeb1eee9cfba063008d"
  - "49e2ed4a169918d346fe8f96c208a4cec56cf3e8"
  - "ba0ea87da5f51890b8801ceaad2f583d17265bc1"
  - "0342d85f15fa2563ce502c6adb20497e0bf02c5e"
source_ledgers:
  - ".memory/commits/2025-08-01-f9d2bff8444250bdac336eeb1eee9cfba063008d.md"
  - ".memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md"
  - ".memory/commits/2025-07-30-ba0ea87da5f51890b8801ceaad2f583d17265bc1.md"
  - ".memory/commits/2025-07-31-0342d85f15fa2563ce502c6adb20497e0bf02c5e.md"
---

# ADR-0010: Rewrite String/Bytes as Value Types Backed by BytesBaseCell

## TL;DR
- `String` and `Bytes` are rewritten from `ObjectRef` subclasses to standalone value types backed by `details::BytesBaseCell`, a 16-byte wrapper around `TVMFFIAny`. Short strings (<=7 bytes) are stored inline via SSO; longer strings heap-allocate `StringObj`/`BytesObj`.
- This eliminates ObjectRef indirection for short strings, removes reference counting overhead for the most common string lengths, and unifies the SSO path with the String/Bytes type itself.

## Status
Accepted

## Context
ADR-0003 introduced small string optimization (SSO) in `TVMFFIAny` but kept `String` and `Bytes` as `ObjectRef` wrappers. This meant SSO only applied at the `Any`/`AnyView` level -- when a `String` was stored in an `Any`, a short string could be inline, but the `String` class itself always held a pointer to a heap-allocated `StringObj`. Converting between `String` and `Any` required promotion/demotion logic.

Commit `f9d2bff` prepared the ground by moving `StringObj`/`BytesObj` into `namespace details`, signaling these are implementation details. Commit `49e2ed4` completed the rewrite, making `String`/`Bytes` directly wrap a `TVMFFIAny` cell.

## Decision Drivers
- Performance: short strings are extremely common (type keys, attribute names, DLDataType strings). Eliminating heap allocation and atomic refcounting for <=7-byte strings is a significant win.
- Simplicity: a single representation for strings eliminates the dual-path (ObjectRef vs. inline) that callers had to navigate.
- Value semantics: strings are conceptually values, not identity-bearing objects. Value type semantics (`==` compares content, not pointers) are more natural.
- Zero-overhead Optional: `Optional<String>` should have the same size as `String` (16 bytes), using `kTVMFFINone` as the null sentinel.

## Decision
Rewrite `String` and `Bytes` as value types:

1. **`details::BytesBaseCell`**: A 16-byte cell wrapping `TVMFFIAny`. Manages refcounting for heap strings, provides `data()`/`size()` that dispatch on type index (small vs. heap), and implements `InitSpaceForSize` for allocating inline or heap backing.

2. **`String`/`Bytes`**: No longer inherit from `ObjectRef`. Hold a `BytesBaseCell data_` member. Default constructor creates an empty small string (`kTVMFFISmallStr`/`kTVMFFISmallBytes`). Methods like `get()`, `use_count()`, `defined()` are removed.

3. **`TypeTraits<String>`/`TypeTraits<Bytes>`**: `field_static_type_index = kTVMFFIAny` (since the runtime representation can be either `kTVMFFISmallStr` or `kTVMFFIStr`). `CheckAnyStrict` checks both type indices. Fallback conversions from `kTVMFFIRawStr` and `kTVMFFIByteArrayPtr` are preserved.

4. **`Optional<String>`/`Optional<Bytes>`**: Zero-overhead specialization using `BytesBaseCell` with `kTVMFFINone` as the null sentinel. `sizeof(Optional<String>) == sizeof(String) == 16`.

5. **`zero_padding` invariant**: All non-small-string `TVMFFIAny` values must have `zero_padding == 0`. Every `TypeTraits::CopyToAnyView`/`MoveToAny` specialization explicitly zeroes this field.

6. **Cross-type equality**: `AnyHash`/`AnyEqual` treat `kTVMFFISmallStr`/`kTVMFFIStr` as equivalent (and likewise for bytes). Structural hash/equal also handle cross-type comparison.

## Alternatives Considered
### Keep String/Bytes as ObjectRef with SSO only in Any
- Pros: No breaking API change. Simpler migration.
- Cons: Perpetuates dual-path logic. ObjectRef overhead for short strings. `Optional<String>` requires wrapper.

### Use a discriminated union in String (SSO + heap in one class, without TVMFFIAny)
- Pros: Could support longer inline strings (up to 15 bytes in a 16-byte union).
- Cons: Requires a separate discriminator from `TVMFFIAny.type_index`, creating inconsistency between `String` internal state and `Any` representation. More complex FFI boundary transitions.

### Use std::string internally with SSO
- Pros: Leverage std::string's proven SSO implementation.
- Cons: Not C ABI compatible. `std::string` layout varies by compiler. Cannot be stored directly in `TVMFFIAny`.

## Why This Option Won
- The `BytesBaseCell` approach reuses the existing `TVMFFIAny` layout that is already designed for SSO, achieving full consistency between the `String` type and its `Any` representation.
- The 16-byte size matches `TVMFFIAny` exactly, so `String`/`Bytes` can be bitwise-moved to/from `Any` without conversion.
- Zero-overhead `Optional` is a strong practical benefit: every optional string field in IR nodes saves 8 bytes compared to a wrapped `Optional<ObjectRef>`.

## Consequences
### Positive
- No heap allocation for strings <=7 bytes (zero refcounting overhead).
- `String`/`Bytes` are now true value types with content-based `==`.
- `Optional<String>`/`Optional<Bytes>` have zero overhead (same 16-byte size).
- `Any` <-> `String` transitions are trivial (same backing representation).
- Default `String` is empty (not null), eliminating null-string bugs.

### Negative
- **Breaking API**: `String`/`Bytes` no longer inherit from `ObjectRef`. Methods like `get()`, `use_count()`, `defined()`, and implicit `ObjectRef` conversion are removed. All downstream code using these APIs must update.
- **`zero_padding` discipline**: Every `TypeTraits` specialization must explicitly zero `zero_padding`. A forgotten zeroing breaks `same_as` and hash consistency. This is fragile and pervasive.
- **Two `test_rvalue_ref.cc` cases commented out**: RValueRef + String interaction needs follow-up work.
- **`std::hash<String>` changed**: Now uses `std::hash<std::string_view>` instead of `StableHashBytes`. The std hash and stable hash now differ (intentionally: std::hash for C++ containers, StableHash for cross-platform determinism).

### Risks
- New `TypeTraits` specializations that forget to zero `zero_padding` will cause subtle hash/equality bugs. Mitigated by pervasive code review and the `AnyEqualHash` test that verifies cross-type consistency.
- `TVMFFIDataTypeToString` C API signature changed from `TVMFFIObjectHandle*` to `TVMFFIAny*` output. Downstream C callers must update.

## Implementation Notes
- The preparatory commit `f9d2bff` moved `StringObj`/`BytesObj` into `namespace details`, establishing that Obj types are implementation details.
- String `Concat` was rewritten to use `InitSpaceForSize` directly, avoiding intermediate `std::string` allocation.
- `AnyEqual::operator()` adds a 16-byte fast path (`memcmp` via `int64_t` reinterpret) for same-type comparisons.
- New type indices `kTVMFFISmallStr=11`, `kTVMFFISmallBytes=12` are registered in the type table.
- `TypeTable::CopyString` uses a new `MakeInplaceString` helper since `String` is no longer an `ObjectRef`.

## Validation
- `tests/cpp/test_any.cc`: `AnyEqualHash` test verifying small-str/heap-str cross-type equality and hash.
- `tests/cpp/test_optional.cc`: `Optional<String>`/`Optional<Bytes>` with `sizeof` static assertions.
- `tests/cpp/test_string.cc`: Updated type index expectations, new `StdHash` test, empty `Bytes` test.
- `tests/cpp/extra/test_reflection_structural_equal_hash.cc`: Cross-type string comparison.

## Migration and Rollback
- **From ObjectRef-based String**: Remove `get()`, `use_count()`, `defined()` calls. Replace `String` -> `ObjectRef` implicit conversions with explicit `Any(str)`. Replace `r.defined()` checks with `opt_str.has_value()` using `Optional<String>`.
- **Rollback**: Revert the commit and restore ObjectRef-based String/Bytes. The `namespace details` move can remain.

## Related Design Docs
- [.memory/designs/0001-type-erased-any-value-system.md](.memory/designs/0001-type-erased-any-value-system.md)
- [.memory/designs/0004-container-library.md](.memory/designs/0004-container-library.md)

## Related Diagrams
- [.memory/diagrams/0001-any-value-memory-layout.md](.memory/diagrams/0001-any-value-memory-layout.md)

## Evidence Matrix
- `BytesBaseCell` class definition -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/string.h`
- `StringObj`/`BytesObj` moved to `namespace details` -> `.memory/commits/2025-08-01-f9d2bff8444250bdac336eeb1eee9cfba063008d.md` + `f9d2bff` + `include/tvm/ffi/string.h`
- `zero_padding` zeroing in all TypeTraits -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/type_traits.h`
- `Optional<String>`/`Optional<Bytes>` zero-overhead -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/optional.h`
- `AnyHash`/`AnyEqual` cross-type small-str/heap-str -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/any.h`
- `Bytes::memequal` fast path -> `.memory/commits/2025-07-30-ba0ea87da5f51890b8801ceaad2f583d17265bc1.md` + `ba0ea87` + `include/tvm/ffi/string.h`
- `TVMFFIDataTypeToString` signature change -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `src/ffi/dtype.cc`
- `kTVMFFISmallStr=11`, `kTVMFFISmallBytes=12` registration -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/c_api.h`

## Supersedes
None (but significantly extends [ADR-0003: Inline Small String Optimization in TVMFFIAny](.memory/ADRs/0003-small-string-optimization-in-any.md))

## Superseded By
None

## Follow-up Actions
- Resolve the two commented-out `test_rvalue_ref.cc` test cases for RValueRef + String interaction.
- Consider a compile-time check or centralized helper for `zero_padding` zeroing to prevent regressions.
- Update Python Cython bindings to handle the `String` type change (no longer ObjectRef).
