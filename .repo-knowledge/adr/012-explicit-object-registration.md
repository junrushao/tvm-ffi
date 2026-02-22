# ADR 012: Explicit Object Type Registration

- Status: Accepted
- Date: 2025-10-14
- Owners: Tianqi Chen

## Context

The `TVM_FFI_DECLARE_OBJECT_INFO` and `TVM_FFI_DECLARE_OBJECT_INFO_STATIC`
macros contained a `static inline int32_t _register_type_index` member that
called `_GetOrAllocRuntimeTypeIndex()` during static initialization. This
auto-registration had two problems:

1. **Binary size overhead**: Every DLL that included the header would
   auto-register the type, even if the type was never used in that library.
   This added unnecessary static initializers and binary bloat.

2. **Unpredictable behavior**: The registration order depended on DLL load
   order, which was fragile and hard to reason about. Types that did not
   need dynamic casting were still being registered.

The reflection system (`ObjectDef<T>`) already provided explicit registration.
The auto-registration was a legacy mechanism.

## Decision

Remove the static `_register_type_index` auto-registration from
`TVM_FFI_DECLARE_OBJECT_INFO` and `TVM_FFI_DECLARE_OBJECT_INFO_STATIC`
(`9ac3121`).

- **Static built-in types** (Str, Bytes, Error, Function, Shape, Tensor,
  Array, Map, Module, OpaquePyObject) are now explicitly reserved at runtime
  startup via `ReserveDepthOneObjectTypeIndex` in `src/ffi/object.cc`.

- **Dynamic types** must be explicitly registered via
  `reflection::ObjectDef<T>()` or `T::_GetOrAllocRuntimeTypeIndex()`.

The `TVM_FFI_DECLARE_OBJECT_INFO_STATIC` macro now uses `[[maybe_unused]]`
on `tindex` and returns the static `_type_index` instead of the dynamically
registered value. `StaticTypeKey::kTVMFFIError` was added as a new constant.

## Consequences

- Positive:
  - Reduced binary size: DLLs no longer contain unnecessary static
    initializers for types they don't use
  - Predictable registration: all registrations are explicit and happen
    in known locations
  - Types that don't need dynamic casting don't need registration
  - Cleaner separation between type declaration and type registration

- Negative:
  - Any downstream code that declares objects without registering through
    `ObjectDef` will lose dynamic casting capability
  - Existing code must be updated to add explicit `ObjectDef<T>()`
    registration for custom objects that need dynamic casting

- Migration/Rollout:
  - Add `reflection::ObjectDef<T>()` registration in a
    `TVM_FFI_STATIC_INIT_BLOCK` for all custom objects that require
    dynamic casting (e.g., `IsInstance<T>()` checks)
  - Objects that are only used via their parent type and never downcast
    do not need explicit registration

## References
- Range summary: `.repo-knowledge/ranges/2025-10-31-FFA2DBF-BC0D225.md`
- Evidence commits: `9ac3121`

## Related Design Docs
- `.repo-knowledge/design/004-reflection-system.md`
- `.repo-knowledge/design/003-c-abi-stability.md`

## Notes
This change was part of a broader pattern of simplifying the object system
ahead of the 0.1.0 release. The `refl::init<Args...>` constructor refactor
(`fc2630f`) and auto-generated `__init__` (`0729193`) happened in the same
week, collectively making object type management more explicit and less
error-prone.
