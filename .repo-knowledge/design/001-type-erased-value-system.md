# Type-Erased Value System (Any/AnyView)

- Doc ID: 001-type-erased-value-system
- Status: Approved
- Last Updated: 2025-12-29
- Owners: Tianqi Chen

## Overview

The FFI layer provides two type-erased value containers: `Any` (owning) and
`AnyView` (non-owning). These containers are the fundamental data transport
for the packed calling convention, where every function receives arguments as
`const AnyView* args` and writes its return value into `Any* rv`.

This document covers the type-erased value system, the `as`/`cast` semantic
split, and the `TypeTraits` machinery that underpins both.

## Key Design

### Any and AnyView

`AnyView` is a lightweight, non-owning view over a type-erased value stored in
the `TVMFFIAny` C struct. `Any` is the owning counterpart that manages the
lifetime of its held value (including ref-counted `Object` pointers).

Both expose extraction methods parameterized by the target type `T`.

### as vs cast: strict check vs conversion

A key semantic decision (introduced in `37a2e7c`) separates type extraction
into two distinct operations:

- **`as<T>()`** -- Strict type check with no conversion. Returns
  `std::optional<T>`: the value if the stored type already matches `T` exactly
  (or is a subtype, for Object pointers), or `std::nullopt` otherwise. Calls
  `TypeTraits<T>::CheckAnyStrict` internally. Does not throw.

- **`cast<T>()`** -- Full type conversion. May perform coercion (e.g., integer
  widening, `int` to `double`). Calls `TypeTraits<T>::TryCastFromAnyView`
  internally. Throws on failure.

- **`try_cast<T>()`** -- Same as `cast<T>()` but returns `std::optional<T>`
  instead of throwing.

The `as<T>()` overload where `T` is an Object subclass is a shortcut that
returns `const T*` (a raw pointer to the held Object if it matches `T`, or
`nullptr` otherwise), implemented as `as<const T*>().value_or(nullptr)`.

### TypeTraits split

The `TypeTraits<T>` specialization protocol was refactored (in `37a2e7c`) from
a single `TryConvertFromAnyView` into three distinct hooks:

| Hook                       | Purpose                                         |
|----------------------------|--------------------------------------------------|
| `CheckAnyStrict`           | Returns `true` if the value is already type `T`. |
| `CopyFromAnyViewAfterCheck`| Extracts the value assuming check already passed. |
| `TryCastFromAnyView`       | Full conversion attempt (may coerce types).       |

Containers (`Array`, `Map`, `Tuple`, `Variant`) implement these hooks to
propagate type-checking or conversion to their elements.

### Enum TypeTraits specialization

A `TypeTraits<Enum>` specialization was added (`f7311e4`) for C++ enum types.
Enums are stored as `int64_t` in `Any`/`AnyView` via `static_cast`. This
enables enum-typed fields (common in TIR node definitions) to be registered
with the reflection system and round-tripped through the packed calling
convention without manual conversion wrappers.

### Small string/bytes inline storage (August 2025)

Short strings and byte sequences (e.g., field names, type keys) are stored
inline in the `TVMFFIAny` union rather than as heap-allocated `StringObj`
instances (`49e2ed4`). Two new type indices were added to the C ABI:

- `kTVMFFISmallStr`: Inline string stored in the `v_handle`/`v_int64` slot.
- `kTVMFFISmallBytes`: Inline byte sequence stored in the same slot.

A `zero_padding` field was added to the `TVMFFIAny` union to ensure unused
bytes are zeroed, which is required for correct equality comparison via
`v_uint64`.

All type-checking code that previously compared `== kTVMFFIStr` must now check
`== kTVMFFIStr || == kTVMFFISmallStr` (and analogously for bytes). The
`AnyView`, `Any`, type traits, cast machinery, `Optional`, `RValueRef`,
`Variant`, `DType`, reflection accessor, and structural equal/hash
implementations were all updated.

This is an **ABI-breaking change**: pre-compiled binaries must be recompiled.

### DLDataType padding correctness

The `TypeTraits<DLDataType>` specialization was updated (`a5a08b2`) to zero the
padding portion of the `TVMFFIAny` union before writing the `v_dtype` field.
`DLDataType` occupies fewer bytes than the full union; without zeroing, two
logically equal `DLDataType` values could compare unequal via `v_uint64`.
Both `CopyToAnyView` and `MoveToAny` now set `result->v_uint64 = 0` before
writing `result->v_dtype`.

### Variant generalization

`Variant<T...>` was extended (in `296e2f7`) to accept any `ObjectRef` subtype as
a member type. The `TypeTraits<Variant<T...>>` specialization iterates over all
member types, attempting `CheckAnyStrict` for `as` and `TryCastFromAnyView` for
`cast`, returning the first successful match.

The helper `AnyUnsafe::MoveFromAnyStorageAfterCheck<T>` enables zero-copy
extraction from `Any` storage after a strict check succeeds.

### STL TypeTraits specializations (November 2025)

`include/tvm/ffi/extra/stl.h` (`c3fc8f7`) provides `TypeTraits`
specializations for C++ STL containers: `std::vector<T>`, `std::array<T,N>`,
`std::optional<T>`, `std::variant<T...>`, `std::tuple<T...>`,
`std::map<K,V>`, `std::unordered_map<K,V>`, and `std::function<R(Args...)>`.
This allows C++ exported functions to accept and return STL containers
directly without converting to native TVM containers.

The specializations are implemented using a shared `STLTypeTrait` base and
bridge to the corresponding native containers (e.g., `std::vector<T>` maps
through `Array<T>`, `std::map<K,V>` maps through `Map<K,V>`). This is an
opt-in header: native TVM containers remain preferred for performance.

`MapObj` added `friend struct TypeTraits` for internal access. Follow-up
fixes addressed use-after-move in `std::tuple` handling (`88d5130`) and
segfaults (`4076ef5`).

### Tuple structured binding support (November 2025)

C++17 structured binding support was added to `Tuple<Types...>` (`5569e44`):

- `std::tuple_size` and `std::tuple_element` specializations in namespace `std`
- ADL-friendly free functions `get<I>(const Tuple<...>&)` and
  `get<I>(Tuple<...>&&)`
- Rvalue `Tuple::get<I>() &&` overload that moves out the element when the
  tuple has unique ownership (calls `AnyUnsafe::MoveFromAnyAfterCheck`)
- C++17 deduction guide: `Tuple{1, 2.0f, String{"hello"}}` works without
  explicit template arguments

This enables `auto [a, b, c] = tuple;` syntax in C++ code.

### IterAdapter reference type fix (November 2025)

`IterAdapter::reference` was changed from `value_type&` to `value_type`
(`14f3c82`). The previous implementation returned `const value_type` (a
prvalue) but declared `reference = value_type&`, creating a type mismatch
that caused undefined behavior with STL components like
`std::make_move_iterator`.

### Generic value protocol (December 2025)

The `__tvm_ffi_value__()` protocol (`3dd7a81`) enables Python objects to
declare how they convert to TVM FFI values without requiring explicit
converter registration. Any Python object that defines `__tvm_ffi_value__()`
is automatically converted by calling this method to obtain the actual FFI
value. The protocol is dispatched in the Cython call path via
`TVMFFIPyArgSetterFFIValueProtocol_`.

The implementation required refactoring `TVMFFIPyCallContext` from a nested
inner class of `TVMFFIPyCallManager` into a standalone RAII class, and
separating call stack state into `TVMFFIPyCallStack` with an
`extra_temp_py_objects_stack` vector to keep alive temporary objects created
by the value protocol.

### Customizable AnyHash/AnyEqual via type attributes (February 2026)

`AnyHash` and `AnyEqual` functors were extended (`39d9b2b`) to consult per-type
attribute columns (`__any_hash__`, `__any_equal__`) when hashing or comparing
object-typed `Any` values. This enables objects to override the default
pointer-based hash and equality with structural or value-based logic.

The dispatch supports both raw function pointer (fast path) and `ffi::Function`
object invocation. Types without registered `__any_hash__`/`__any_equal__`
attributes continue to use pointer-based defaults. This mechanism is used by
`StructuralKey` (`6adc8df`) to make structural hash/equality available as a
container key without manual conversion.

Implementation moved `MoveFromSafeCallRaised` and `SetSafeCallRaised` from
`function_details.h` to `error.h` so they are accessible without depending on
`function.h`.

### Tuple constructor strictness

`Tuple<Types...>` constructor SFINAE was tightened (in `024e45c`) to prevent
the variadic `UTypes&&...` forwarding constructor from hijacking same-type move
construction. A guard excludes the variadic path when the single argument is
exactly `Tuple<Types...>`, forcing the correct move-constructor overload.

## APIs

### Public extraction methods on AnyView/Any

```cpp
// Strict check (no conversion). Returns nullopt if type does not match.
template <typename T> std::optional<T> AnyView::as() const;
template <typename T> std::optional<T> Any::as() const;

// Object pointer shortcut. Returns nullptr if type does not match.
template <typename T> const T* AnyView::as() const;  // T : Object

// Full conversion. Throws TypeError if conversion fails.
template <typename T> T AnyView::cast() const;
template <typename T> T Any::cast() const;

// Optional conversion. Returns std::nullopt if conversion fails.
template <typename T> std::optional<T> AnyView::try_cast() const;
```

### TypeTraits protocol

Each type `T` that can be stored in `Any`/`AnyView` must specialize:

```cpp
template <> struct TypeTraits<T> {
  static bool CheckAnyStrict(const TVMFFIAny* src);
  static T CopyFromAnyViewAfterCheck(const TVMFFIAny* src);
  static std::optional<T> TryCastFromAnyView(const TVMFFIAny* src);
};
```

### Compile-time helpers

- `all_object_ref_v<T...>`: Checks that every type in a parameter pack is a
  subclass of `ObjectRef` (added in `296e2f7`). Used by `Variant` to validate
  member types at compile time.

## Implementation

Key files:
- `include/tvm/ffi/any.h` -- `AnyView`, `Any`, `AnyUnsafe`
- `include/tvm/ffi/type_traits.h` -- `TypeTraits` protocol and built-in specializations
- `include/tvm/ffi/container/variant.h` -- `Variant<T...>` type traits
- `include/tvm/ffi/container/tuple.h` -- `Tuple<Types...>` constructor guards
- `include/tvm/ffi/container/container_details.h` -- `all_object_ref_v`, `IterAdapter`

Tests:
- `tests/cpp/test_any.cc` -- as/cast/try_cast behavior
- `tests/cpp/test_variant.cc` -- Variant with ObjectRef members
- `tests/cpp/test_tuple.cc` -- Constructor routing correctness
- `tests/cpp/test_string.cc` -- String as/cast semantics

## History
- 2025-05-14: `as<T>()` / `cast<T>()` semantic split introduced (`37a2e7c`)
- 2025-05-10: `Variant<T...>` generalized to all ObjectRef types (`296e2f7`)
- 2025-05-29: Tuple constructor SFINAE tightened (`024e45c`)
- 2025-06-27: `TypeTraits<Enum>` specialization added for enum types (`f7311e4`)
- 2025-06-27: `DLDataType` `Any` representation padding zeroed for correct equality (`a5a08b2`)
- 2025-08-04: Small string/bytes inline storage added (`kTVMFFISmallStr`, `kTVMFFISmallBytes`); `zero_padding` field in `TVMFFIAny` (`49e2ed4`)
- 2025-11-04: `IterAdapter::reference` type fixed from `value_type&` to `value_type` (`14f3c82`)
- 2025-11-05: Tuple C++17 structured binding support, rvalue `get()`, deduction guide (`5569e44`)
- 2025-11-30: STL `TypeTraits` specializations added in `include/tvm/ffi/extra/stl.h` (`c3fc8f7`)
- 2025-11-30: Use-after-move fix for `std::tuple` handling in STL bridge (`88d5130`)
- 2025-12-04: `__tvm_ffi_value__()` generic value protocol introduced; `TVMFFIPyCallContext` refactored to standalone RAII class; `TVMFFIPyCallStack` added (`3dd7a81`)
- 2026-01-08: `TypeTraits<Int>::CopyToAnyView` overflow guard added for `uint64_t`/`size_t` values exceeding `INT64_MAX`; throws `OverflowError` (`86bbddf`)
- 2026-01-10: `Type2Str<Any&&>` and `Type2Str<AnyView&&>` template specializations added to fix `refl::init<Any>()`/`refl::init<AnyView>()` compile errors; `class Any` forward declaration added to `type_traits.h` (`38914fa`)
- 2026-02-15: `AnyHash`/`AnyEqual` extended to consult per-type `__any_hash__`/`__any_equal__` type attribute columns; `MoveFromSafeCallRaised`/`SetSafeCallRaised` moved to `error.h` (`39d9b2b`)

### uint64_t overflow guard (January 2026)

A compile-time-selected runtime overflow guard was added (`86bbddf`) to
`TypeTraits<Int>::CopyToAnyView`. When converting `uint64_t` or `size_t` values
into the `int64_t` representation used by `TVMFFIAny`, a `constexpr if` block
checks `std::is_unsigned_v<Int> && sizeof(Int) >= sizeof(int64_t)` and throws
`OverflowError` if the value exceeds `INT64_MAX`. The `StructuralHash` global
function and internal call sites were updated to use explicit
`static_cast<int64_t>` for intentional bit-casts.

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-05-29-7D34EB8-024E45C.md`
  - `.repo-knowledge/ranges/2025-06-27-1C9B17A-F7311E4.md`
  - `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
  - `.repo-knowledge/ranges/2025-11-30-0EE6444-4076EF5.md`
  - `.repo-knowledge/ranges/2025-12-29-5A82940-6E7CAFA.md`
  - `.repo-knowledge/ranges/2026-01-30-C51E519-B508698.md`
  - `.repo-knowledge/ranges/2026-02-21-B1611E0-ECC7471.md`
- Related ADRs:
  - `.repo-knowledge/adr/001-as-vs-cast-semantics.md`
  - `.repo-knowledge/adr/005-small-string-inline-abi.md`
