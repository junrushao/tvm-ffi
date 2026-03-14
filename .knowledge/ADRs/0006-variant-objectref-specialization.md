---
scope:
  - "0005-containers"
  - "0002-any-system"
---
# Variant ObjectRef Storage Specialization

**TL;DR**: When all types in `Variant<V...>` are `ObjectRef` subclasses, the variant inherits from `ObjectRef` (8 bytes) instead of using `Any` storage (16 bytes). This halves storage and enables participation in `ObjectPtrHash`/`ObjectPtrEqual`.

## Context

`Variant<V...>` was originally always backed by `Any` (16 bytes). When all variant types derive from `ObjectRef`, this wastes 8 bytes -- an `ObjectPtr` (8 bytes) would suffice. Additionally, `Any`-backed variants cannot participate in `ObjectPtrHash`/`ObjectPtrEqual` without extracting the object pointer, which requires knowing the variant is all-ObjectRef at compile time.

Usecases:
- `Variant<String, Array<int>>` (all-ObjectRef) is used as `Map` keys. With ObjectRef storage, it works directly with `ObjectPtrHash`/`ObjectPtrEqual`.
- Reducing memory usage in IR nodes that store many variant fields.

Design Decisions:
- **Dual `VariantBase<bool>` specialization**: `VariantBase<false>` holds `Any data_`; `VariantBase<true>` inherits `ObjectRef`. The selection is determined by `all_object_ref_v<V...>`, a compile-time fold expression `(std::is_base_of_v<ObjectRef, T> && ...)`.
- **Common interface via `ToAnyView()` / `MoveToAny()`**: Both specializations expose the same methods, abstracting over storage. `VariantBase<true>::ToAnyView()` manually constructs a `TVMFFIAny` from the object pointer with proper padding clearing and null handling.

**Alternatives considered**:

1. **Always use `Any`**: Simpler but wastes 8 bytes per all-ObjectRef variant and prevents ObjectRef identity operations.
2. **Union of concrete ObjectRef types**: Type-safe per-type storage but causes combinatorial template explosion.

**Consequences**:
- `sizeof(Variant<String, Array<int>>) == 8` (was 16). `static_assert(std::is_base_of_v<ObjectRef, Variant<String, Array<int>>>)` now passes.
- The `ToAnyView()` implementation in the ObjectRef specialization must manually zero padding and handle null, adding template complexity.
- Existing code using all-ObjectRef variants silently benefits without source changes.

## Implementation Notes

- `details::VariantBase<true>` inherits `ObjectRef` and stores data in `ObjectPtr<Object> data_`.
- `details::all_object_ref_v<T...>` is `(std::is_base_of_v<ObjectRef, T> && ...)`.
- `MoveFromAnyStorageAfterCheck<T>` dispatches to `TypeTraits<T>::MoveFromAnyAfterCheck` for non-`Any` types.
- Evidence: `include/tvm/ffi/container/variant.h:37-94`, commit `296e2f7`.

## Related Design Docs

- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- Container system with Variant
- [`.knowledge/designs/0002-any-system.md`](../designs/0002-any-system.md) -- Any/AnyView used as default Variant storage
