---
scope:
  - "0022-rust-bindings"
  - "0005-containers"
---
# Recursive Element-Level Type Checking for Rust Array<T>

**TL;DR**: The Rust `Array<T>` binding implements element-level type checking in its `AnyCompatible` trait, recursively validating each element against `T` during `check_any_strict` and supporting a fallback element-by-element conversion in `try_cast_from_any_view`.

## Context

The C++ `Array<T>` is a homogeneous container, but at the C ABI level it is type-erased: `ArrayObj` has type index `kTVMFFIArray` regardless of element type. When converting an `Any` containing an `Array` back to `Array<T>` in Rust, the element types must be validated at runtime since the type parameter `T` is erased at the ABI boundary.

## Decision

Implement two-path type validation in `Array<T>`'s `AnyCompatible`:

1. **Fast path (`check_any_strict`)**: Check that `type_index == kTVMFFIArray`, then iterate all elements calling `T::check_any_strict`. Short-circuit optimization: if `T` is `Any` (via `TypeId` comparison), skip element checking entirely since `Any` accepts all types.

2. **Slow path (`try_cast_from_any_view`)**: If strict check fails but the outer type matches, attempt element-by-element conversion via `T::try_cast_from_any_view`. This supports coercion scenarios (e.g., an array of `int64` values being read as `Array<f64>`).

3. **`TryFrom<Any>`** and **`TryFrom<AnyView>`**: Delegate to `TryFromTemp` which uses `try_cast_from_any_view` internally.

## Rationale

1. **Type safety**: Prevents runtime errors from type mismatches (e.g., reading `Array<Shape>` as `Array<Tensor>`).
2. **Performance**: The fast path avoids element iteration when types match exactly. The `Any` bypass avoids unnecessary per-element checks for untyped arrays.
3. **Compatibility**: Matches C++ behavior where `Array<T>` is type-checked lazily on element access.

## Implementation Notes

- `rust/tvm-ffi/src/collections/array.rs`: `ArrayObj` with `#[repr(C)]` layout matching C++ (`data`, `size`, `capacity`, `data_deleter`). `ObjectCoreWithExtraItems` with `ExtraItem = TVMFFIAny`. Full `AnyCompatible` implementation with recursive checking.
- Tests in `test_array.rs` verify: recursive type checking (Shape array cannot be cast to Tensor array), parametric support (Shape, Tensor, Function arrays), and Any/AnyView roundtrip.

## Related Design Docs

- [`.knowledge/designs/0022-rust-bindings.md`](../designs/0022-rust-bindings.md)
- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md)
- Commit: `.knowledge/commits/2026-01-30-d0d0e2f935cda443bd85e097a3cfb18de2a96f4d.md`
