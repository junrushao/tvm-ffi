---
scope:
  - "0003-object-system"
---
# Rename Core Object Type Keys from object.* to ffi.*

**TL;DR**: The decision to migrate all core FFI object `_type_key` strings from the `"object.*"` prefix to `"ffi.*"` (e.g., `"object.Object"` -> `"ffi.Object"`, `"object.Array"` -> `"ffi.Array"`), and centralize type key constants in `StaticTypeKey`.

## Context
- Core FFI types previously used `"object.*"` as their type key prefix (e.g., `"object.Object"`, `"object.Function"`, `"object.Array"`).
- This prefix could conflict with user-defined types that also use `"object.*"`, creating ambiguity.
- The `"object.*"` prefix did not align with the C++ namespace `tvm::ffi`, making the relationship between type keys and namespaces unclear.
- Type key strings were scattered as inline literals across individual class definitions, making renames error-prone.

Usecases:
- Python's `@register_object("ffi.Array")` now uses a prefix that unambiguously identifies core FFI types.
- Serialization formats storing type keys can distinguish FFI core types from user types by prefix.
- The `StaticTypeKey` struct provides a single source of truth for all core type key strings.

Design Decisions:
- **Use `ffi.*` prefix** for all core FFI object type keys: `ffi.Object`, `ffi.String`, `ffi.Bytes`, `ffi.Error`, `ffi.Function`, `ffi.Array`, `ffi.Map`, `ffi.Shape`, `ffi.Tensor` (renamed from `ffi.NDArray` in commit 3a551d8).
- **Centralize in `StaticTypeKey`**: New constants `kTVMFFIObject`, `kTVMFFIFunction`, `kTVMFFIArray`, `kTVMFFIMap` are added. Classes now reference these constants instead of inline string literals.
- **Breaking change**: Any code matching on `_type_key` strings (Python `@register_object`, serialization, Rust bindings) must update to the new prefix.

## Implementation Notes
- `IsInstance` checks are unaffected since they use integer type indices, not string keys.
- `GetTypeKey()` now returns `"ffi.*"` strings for all core types.
- Serialized data containing old `"object.*"` type keys requires migration.

## Related Design Docs
- [0003-object-system.md](.knowledge/designs/0003-object-system.md)
