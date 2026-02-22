# ADR 020: Back Tuple by ArrayObj Storage

- Status: Accepted
- Date: 2025-08-04
- Owners: Tianqi Chen

## Context

TVM FFI needed a heterogeneous, fixed-size container for function return values
and structured data. Two options were considered: (a) introduce a distinct
`TupleObj` with per-element type metadata and its own type index, or (b) reuse
the existing `ArrayObj` storage and enforce type safety purely at compile time.

A distinct `TupleObj` would have required a new type index, new ABI surface, and
separate conversion rules in every language binding (Python, Rust). Meanwhile,
`ArrayObj` was already stabilized in the C ABI, and Python `list`/`tuple` both
convert to `Array` through the same path.

## Decision

Back `Tuple<T1, T2, ...>` by the same `ArrayObj` storage as `Array<T>`, with no
distinct type index.

`Tuple<Types...>` is a C++ class template that inherits from `ObjectRef` and
stores its elements in an `ArrayObj`. The container type alias confirms this:

```cpp
using ContainerType = ArrayObj;
```

Construction allocates an `ArrayObj` via `ArrayObj::Empty(sizeof...(Types))` and
placement-new initializes each element. Element access (`get<I>()`) indexes
directly into the `ArrayObj` data. Copy-on-write semantics mirror `Array`.

Compile-time type safety is enforced entirely via C++ template parameters
(`Tuple<int, String>`) and `std::tuple_size`/`std::tuple_element`
specializations for structured bindings. The `TypeTraits<Tuple<Types...>>`
specialization checks `type_index == kTVMFFIArray` and validates per-element
types, but does not introduce a separate runtime type.

ADL-friendly free `get<I>()` functions and a C++17 deduction guide are provided
for ergonomic usage.

## Consequences

- Positive: Zero-cost exchange with `Array` at the ABI boundary. No additional
  type index needed, keeping the C ABI surface minimal.
- Positive: Python `list`/`tuple` both convert to `Array`, so `Tuple` and
  `Array` share the same runtime representation. This unifies conversion rules
  from Python and avoids a separate code path in Cython bindings.
- Positive: Structured bindings work via `std::tuple_size` and
  `std::tuple_element` specializations, giving `Tuple` the same ergonomics as
  `std::tuple` in C++17.
- Negative: Cannot distinguish `Tuple` from `Array` at runtime. Both have
  `type_index == kTVMFFIArray`. Tuple is a compile-time-only type overlay on
  `ArrayObj`.
- Negative: Runtime type checking in `TypeTraits<Tuple<Types...>>` must verify
  both the array size and per-element types on every cast, which is more
  expensive than a single type-index check would be.
- Migration/Rollout: No migration needed. `Tuple` is a new addition that
  composes with existing `ArrayObj` infrastructure without modifying the ABI.

## References
- Evidence commits: `7e0a4b3` (ArrayObj ABI stabilization)
- Source: `include/tvm/ffi/container/tuple.h`, `include/tvm/ffi/container/array.h`
- External references: none

## Related Design Docs
- `.repo-knowledge/design/001-type-erased-value-system.md`
- `.repo-knowledge/design/003-c-abi-stability.md`

## Notes
The `Tuple` template enforces `details::all_storage_enabled_v<Types...>` at
compile time, ensuring every element type is compatible with `Any`. The
`TryCastFromAnyView` slow path in `TypeTraits` will attempt per-element
conversion when strict type checking fails, allowing flexible interop with
loosely-typed arrays received from Python or other FFI boundaries.
