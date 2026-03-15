---
scope:
  - ".knowledge/designs/containers.md"
---
# ADR-006: Variant ObjectRef Storage Specialization

**TL;DR**: When all types in `Variant<V...>` are `ObjectRef` subtypes, the variant is backed by `ObjectRef` (8 bytes) instead of `Any` (16 bytes), halving memory footprint and enabling direct participation in the `ObjectRef` type hierarchy.

## Context
`Variant<V...>` needs to store one of several alternative types. The original implementation used `Any` (16 bytes) as the universal backing store. However, a common pattern is `Variant<TypeA, TypeB>` where both `TypeA` and `TypeB` derive from `ObjectRef` -- in this case, a single `ObjectRef` (8 bytes) suffices because the runtime `type_index` already discriminates the held type.

Usecases:
- IR expression types like `Variant<IntImm, FloatImm>` where all alternatives are objects. Halving the variant size from 16 to 8 bytes reduces memory consumption in AST nodes.
- Passing an all-ObjectRef variant where an `ObjectRef` is expected, without boxing or manual extraction.

Design Decisions:
- Introduce `all_object_ref_v<T...> = (std::is_base_of_v<ObjectRef, T> && ...)` compile-time predicate.
- Create `VariantBase<bool all_storage_object>` with two specializations:
  - `VariantBase<false>`: backed by `Any data_` (default, 16 bytes).
  - `VariantBase<true>`: inherits from `ObjectRef` (8 bytes), stores the held object directly.
- `Variant<V...>` inherits from `VariantBase<all_object_ref_v<V...>>`.

## Alternatives

### A: Always use Any backing
- Description: Keep the original design where all variants are 16 bytes.
- Pros: Uniform implementation; no template specialization complexity; no CRTP-like base class.
- Cons: Wastes 8 bytes per all-ObjectRef variant; variants cannot be used where `ObjectRef` is expected without explicit conversion; prevents storing variants in ObjectRef-typed containers without boxing.
- Why rejected: The 2x memory overhead is significant for AST-heavy workloads where variants appear in every node.

### B: Use std::variant<V...>
- Description: Delegate to the standard library `std::variant`.
- Pros: Standard C++17; compiler-managed discriminant and visitors.
- Cons: Fixed size based on largest alternative (potentially larger than 16 bytes); does not participate in the Object type hierarchy; not ABI-stable across compilers; discriminant is redundant when the object's `type_index` already identifies the held type.
- Why rejected: The TVM type system already provides a discriminant (`type_index`); duplicating it via `std::variant`'s index is wasteful. The inability to participate in `ObjectRef` hierarchy would require wrapping every variant in a box.

## Implementation Notes
- `VariantBase<true>::ToAnyView()` must manually construct a `TVMFFIAny` from the held `ObjectPtr`, since `ObjectRef` does not natively produce one. It uses `ObjectUnsafe::TVMFFIObjectPtrFromObjectPtr` to fill the AnyView fields.
- `VariantBase<true>::MoveToAny()` uses `AnyUnsafe::MoveFromAnyStorageAfterCheck<ObjectRef>` to move the held object into an `Any` value.
- `AnyUnsafe::MoveFromAnyStorageAfterCheck<T>` was added alongside this decision as the move counterpart to the existing `CopyFromAnyStorageAfterCheck<T>`.

## Related Design Docs
- `.knowledge/designs/containers.md` -- Variant dual-storage design
