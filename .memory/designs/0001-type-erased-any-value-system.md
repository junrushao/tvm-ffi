---
design: "0001"
title: "Type-Erased Any/AnyView Value System"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-05-06"
last_updated: "2025-10-07"
scope:
  - "ffi/any"
  - "ffi/type_traits"
  - "ffi/c_api"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
  - "37a2e7c521435cbe2bd772480f0389c18bd9ce2c"
  - "a5a08b2553a8327cb821b17aa4028ff5ba52e8f0"
  - "49e2ed4a169918d346fe8f96c208a4cec56cf3e8"
  - "ba0ea87da5f51890b8801ceaad2f583d17265bc1"
  - "0d8fec88eca5acaeaa7e771003d183c31711574a"
  - "5fba9e8ff31940855b4abfa664c3369513814aa4"
source_ledgers:
  - ".memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md"
  - ".memory/commits/2025-05-14-37a2e7c521435cbe2bd772480f0389c18bd9ce2c.md"
  - ".memory/commits/2025-06-27-a5a08b2553a8327cb821b17aa4028ff5ba52e8f0.md"
  - ".memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md"
  - ".memory/commits/2025-07-30-ba0ea87da5f51890b8801ceaad2f583d17265bc1.md"
  - ".memory/commits/2025-10-07-0d8fec88.md"
  - ".memory/commits/2025-10-04-5fba9e8f.md"
---

# Type-Erased Any/AnyView Value System

## TL;DR
- `TVMFFIAny` is the 16-byte tagged union that forms the universal value representation across all FFI boundaries. Every function argument and return value is transported as a `TVMFFIAny`.
- `AnyView` (non-owning) and `Any` (owning, ref-counting) are the C++ wrappers. `AnyView` can hold non-owning references like raw C strings; `Any` never holds non-owning types.
- The `TypeTraits<T>` template framework governs bidirectional conversion between concrete C++ types and `Any`/`AnyView`, providing compile-time dispatch and runtime type checking.

## Problem Statement
A cross-language FFI system needs to pass values of diverse types (integers, floats, strings, objects, tensors) through a single uniform calling convention. Without type erasure, every function signature would need to be specialized per argument type, which is incompatible with a C ABI and impractical for dynamic dispatch. If the value representation is wrong (too large, too slow, or lossy), every function call in the system suffers.

## Context and Constraints
- The value must fit in a fixed-size struct for stack allocation and array packing (function arguments are passed as `const TVMFFIAny* args`).
- 16 bytes is the chosen size: 4 bytes type tag + 4 bytes padding/metadata + 8 bytes value union. This matches two machine words on 64-bit platforms.
- POD types (int, float, bool, DLDataType, DLDevice) must be stored inline without heap allocation.
- Object types must interoperate with the reference-counted object system.
- Strings need special optimization because they are the most frequent non-POD type in the FFI.

## Goals
- Provide a single, universal value type for the packed function calling convention.
- Enable zero-copy passing of POD values across FFI boundaries.
- Support ownership semantics: `AnyView` for borrows, `Any` for ownership.
- Enable small-string optimization to avoid heap allocation for short strings.
- Provide a compile-time dispatch framework (`TypeTraits`) for type-safe conversions.

## Non-Goals
- Supporting non-standard-layout types directly (e.g., `std::vector`). These are wrapped as objects.
- Providing implicit conversion between all types. Conversions are explicit and governed by `TypeTraits`.
- Supporting big-endian platforms in this initial design.

## Design
### Components and Responsibilities
- **`TVMFFIAny`** (C struct, `c_api.h`): The on-wire ABI representation. A tagged union with `type_index` discriminator, `zero_padding`/`small_str_len` metadata, and an 8-byte value union.
- **`AnyView`** (C++ class, `any.h`): Non-owning view wrapper around `TVMFFIAny`. Can hold `kTVMFFIRawStr` (non-owning `const char*`). Provides constructors from all supported types and three access methods: `as<T>()` (strict check, no conversion), `cast<T>()` (converting, throws on failure), `try_cast<T>()` (converting, returns `std::optional`). See [ADR-0005](.memory/ADRs/0005-as-vs-cast-semantic-split.md).
- **`Any`** (C++ class, `any.h`): Owning wrapper. Manages reference counts for object types. Invariant: `Any::type_index` is never `kTVMFFIRawStr`. When constructed from a raw string, it is promoted to `kTVMFFISmallStr` or `kTVMFFIStr`. Provides the same `as`/`cast`/`try_cast` methods as `AnyView`, plus rvalue `as<T>() &&` for move-out.
- **`TypeTraits<T>`** (template, `type_traits.h`): Per-type conversion policy. Key operations: `CopyToAnyView`, `MoveToAny`, `CheckAnyStrict` (strict type match), `CopyFromAnyViewAfterCheck` (copy after strict check), `MoveFromAnyAfterCheck` (move after strict check), `TryCastFromAnyView` (converting extraction), `TypeStr`. Enum types backed by integral types are supported via a SFINAE specialization that stores enums as `kTVMFFIInt`.
- **`TypeTraitsNoCR<T>`** (template, `type_traits.h`): Convenience alias that strips `const` and reference qualifiers before dispatching to `TypeTraits`.

### Data Contracts and Invariants
- **16-byte invariant**: `sizeof(TVMFFIAny) == 16` on all supported platforms.
- **Ownership invariant**: `Any::type_index` is never `kTVMFFIRawStr` (8) or `kTVMFFIObjectRValueRef` (10). These are view-only types.
- **Padding invariant**: For all types except small strings/bytes, `zero_padding == 0`.
- **Null termination**: Small strings stored in `v_bytes` are null-terminated at `v_bytes[small_str_len]`.
- **Reference counting**: When `type_index >= kTVMFFIStaticObjectBegin` (64), the value is an object pointer (`v_obj`). `Any` manages refcount; `AnyView` does not.
- **`Any::same_as` completeness**: `same_as` compares `type_index`, `v_int64`, and `zero_padding` (the latter is needed because small strings store their length in `zero_padding`/`small_str_len`).
- **Cross-type string equality**: `AnyHash` and `AnyEqual` treat `kTVMFFISmallStr`/`kTVMFFIStr` (and `kTVMFFISmallBytes`/`kTVMFFIBytes`) as equivalent, hashing them with the same type key so small and heap strings hash identically. A 16-byte fast path (`memcmp` via `int64_t` reinterpret) handles same-type comparisons.
- **Container element invariant**: `Array<T>` elements satisfy `TypeTraits<T>::CheckAnyStrict(elem)` for all elements.

### Control Flow
1. **C++ to AnyView**: `TypeTraits<T>::CopyToAnyView(value)` sets `type_index` and the appropriate union field. POD types are stored inline. Objects store `v_obj` pointer (no incref for view). Small strings use SSO.
2. **AnyView to Any (ownership transfer)**: For POD/SSO types, bitwise copy. For objects, `Any` increments the reference count. For `kTVMFFIRawStr`, the string is promoted to `kTVMFFISmallStr` (if <= 7 bytes) or heap-allocated `StringObj` (`kTVMFFIStr`).
3. **Any/AnyView to T** (three paths): `any.as<T>()` calls `CheckAnyStrict` + `CopyFromAnyViewAfterCheck` (strict, no conversion, returns `optional`). `any.try_cast<T>()` calls `TryCastFromAnyView` (converting, returns `optional`). `any.cast<T>()` calls `TryCastFromAnyView` and throws `TypeError` on failure.
4. **Any destruction**: If `type_index >= kTVMFFIStaticObjectBegin`, decrement `v_obj` refcount. Otherwise, no-op (POD/SSO).

### Extension Points
- **New POD types**: Add a new `kTVMFFI*` constant in the [0, 64) range and specialize `TypeTraits<NewType>`.
- **New object types**: Register via `TVM_FFI_DECLARE_OBJECT_INFO`. TypeTraits for `ObjectRef` subclasses are automatically enabled.
- **Custom conversions**: Specialize `TypeTraits<T>` with custom `TryCastFromAnyView` to support implicit conversions (e.g., integer to enum).

## Alternatives Considered
### std::any / std::variant
- Pros: Standard C++. Type-safe.
- Cons: Not C ABI compatible. `std::any` uses heap allocation for large types. `std::variant` requires all types to be enumerated at compile time. Neither supports cross-language use.

### Protocol Buffers / FlatBuffers value type
- Pros: Cross-language. Schema-defined.
- Cons: Serialization overhead for every function call. Not suitable for in-process FFI where zero-copy is required.

## Trade-offs
- **Optimized**: Speed of value passing (16-byte stack values, no allocation for POD), ABI stability (fixed layout), SSO for short strings.
- **Sacrificed**: Type safety at compile time (type index is a runtime tag), big-endian support, inline storage for larger types (anything > 8 bytes goes to the heap).

## Interfaces and Compatibility
- **Public C ABI**: `TVMFFIAny` struct, `TVMFFIAnyViewToOwnedAny` function.
- **Public C++ API**: `Any`, `AnyView` classes, `TypeTraits<T>` framework.
- **Compatibility boundary**: The `TVMFFIAny` layout is versioned (`TVM_FFI_VERSION_*`). Changing it requires a major version bump.

## Failure Modes and Mitigations
- **Type mismatch at cast time**: `cast<T>()` throws `TypeError` with a message indicating expected vs. actual type. The error includes both type keys for debugging.
- **Overflow of type index range**: If more than 64 POD types are needed, the static object range must be shifted. Mitigated by current low occupancy (13/64).
- **Dangling AnyView**: An `AnyView` outliving the data it references (e.g., a raw string that is freed) causes undefined behavior. Mitigated by documentation and the convention that `AnyView` is only used within a single function call scope.

## Observability and Validation
- `tests/cpp/test_ffi_any.cc`: Tests construction, casting, SSO, ownership semantics, and type checking for all supported types.
- Runtime `type_index()` inspection is available on both `Any` and `AnyView`.
- Debug builds can enable `TVM_FFI_ALWAYS_LOG_BEFORE_THROW` for logging all type errors.

## Migration and Rollout
- This is the foundational value type from the root commit. All function calls, container elements, and object fields use `Any`/`AnyView`.

## Diagrams
- [.memory/diagrams/0001-any-value-memory-layout.md](.memory/diagrams/0001-any-value-memory-layout.md)

## Related ADRs
- [.memory/ADRs/0001-type-index-partitioning.md](.memory/ADRs/0001-type-index-partitioning.md)
- [.memory/ADRs/0003-small-string-optimization-in-any.md](.memory/ADRs/0003-small-string-optimization-in-any.md)
- [.memory/ADRs/0005-as-vs-cast-semantic-split.md](.memory/ADRs/0005-as-vs-cast-semantic-split.md)
- [.memory/ADRs/0010-string-bytes-as-value-types.md](.memory/ADRs/0010-string-bytes-as-value-types.md)
- [.memory/ADRs/0012-remove-downcast-favor-any-cast.md](.memory/ADRs/0012-remove-downcast-favor-any-cast.md)

## Evidence Matrix
- TVMFFIAny struct definition -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `include/tvm/ffi/c_api.h` lines 280-333
- AnyView class (492 LOC) -> ledger + `7d34eb8` + `include/tvm/ffi/any.h`
- TypeTraits framework (683 LOC) -> ledger + `7d34eb8` + `include/tvm/ffi/type_traits.h`
- Ownership invariant (Any never holds kTVMFFIRawStr) -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 100-103
- SSO (small_str_len, v_bytes) -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 297-327
- Container element invariant -> `7d34eb8` + `include/tvm/ffi/type_traits.h` lines 63-67
- as/cast/try_cast semantic split -> `.memory/commits/2025-05-14-37a2e7c521435cbe2bd772480f0389c18bd9ce2c.md` + `37a2e7` + `include/tvm/ffi/any.h`, `type_traits.h`
- Enum TypeTraits specialization -> `.memory/commits/2025-06-27-a5a08b2553a8327cb821b17aa4028ff5ba52e8f0.md` + `a5a08b` + `include/tvm/ffi/type_traits.h`
- `zero_padding` zeroing in all TypeTraits specializations -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/type_traits.h`
- `Any::same_as` includes `zero_padding` comparison -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/any.h`
- `AnyHash`/`AnyEqual` cross-type small-str/heap-str branches -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/any.h`
- `StableHashBytes` aligned-load optimization -> `.memory/commits/2025-07-30-ba0ea87da5f51890b8801ceaad2f583d17265bc1.md` + `ba0ea87` + `include/tvm/ffi/base_details.h`
- `StableHashSmallStrBytes` for fast small-string hashing -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4` + `include/tvm/ffi/base_details.h`
- `noexcept` on `Any`/`AnyView` move constructors/assignment, `MoveTVMFFIAnyToAny` pointer parameter fix -> `.memory/commits/2025-10-07-0d8fec88.md` + `0d8fec88` + `include/tvm/ffi/any.h`
- `is_integeral_enum_v<T>` two-phase SFINAE trait for GCC 8.x compatibility -> `.memory/commits/2025-10-04-5fba9e8f.md` + `5fba9e8f` + `include/tvm/ffi/type_traits.h`

## Open Questions
- Should `AnyView` have a debug mode that tracks the lifetime of referenced data?
- Is the 7-byte SSO limit sufficient for all common type keys?

## Confidence and Risk
- Confidence: high
- Residual risks: Dangling `AnyView` references in incorrect usage patterns. The 16-byte size is optimal now but may be reconsidered if DLPack evolves to require larger inline data.
