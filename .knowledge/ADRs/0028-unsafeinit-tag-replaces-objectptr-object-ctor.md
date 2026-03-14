---
scope:
  - "0003-object-system"
  - "0005-containers"
  - "0006-reflection"
---
# UnsafeInit Tag Replaces ObjectPtr<Object> Constructor

**TL;DR**: The `UnsafeInit{}` tag struct replaces the implicit `ObjectPtr<Object>` constructors on `ObjectRef` subclasses, making unsafe nullptr initialization explicit and auditable. All internal code routes through `ObjectUnsafe::ObjectRefFromObjectPtr<T>()`.

## Context

`ObjectRef` subclasses previously accepted `ObjectPtr<Object>` (untyped, non-narrowing) as a constructor argument. This had two problems:

1. **No static type narrowing**: Arbitrary `ObjectPtr<Object>` could bypass the compile-time type check, allowing an `ArrayObj` pointer to be stored in a `Map` ref without error.
2. **Implicit null construction of non-nullable types**: Types with `_type_is_nullable = false` could still be constructed from a null `ObjectPtr<Object>`, violating their non-null invariant.

These constructors were used extensively in internal code for two legitimate patterns: (a) constructing refs from C API handles (which are untyped `void*`), and (b) temporarily constructing null refs during reflection-based object creation.

## Alternatives

### 1. UnsafeInit tag with centralized unsafe helper (chosen)

Introduce `ffi::UnsafeInit{}` tag struct. Remove `RefType(ObjectPtr<Object>)` from all macro-generated constructors. Add `ObjectUnsafe::ObjectRefFromObjectPtr<T>()` as the single bottleneck for untyped construction.

- Pros: Unsafety is explicit (`UnsafeInit{}` at every call site), auditable (grep for `UnsafeInit`), and centralized (one helper function). Non-nullable types can only be constructed via the tag, making null construction impossible without explicit opt-in.
- Cons: All internal code must be migrated to use the helper. Slight verbosity increase at call sites.

### 2. Keep ObjectPtr<Object> constructor with runtime checks

Add runtime `IsInstance<ContainerType>` checks inside the constructor.

- Pros: No API change for internal code.
- Cons: Runtime cost on every construction. Still allows mistyped pointers (error is deferred to runtime, not compile time). Does not solve the null construction problem for non-nullable types.

### 3. Require ObjectPtr<ContainerType> everywhere

Remove `ObjectPtr<Object>` constructor entirely; require all construction to go through `ObjectPtr<ConcreteType>`.

- Pros: Full static type safety.
- Cons: Some internal paths (C API handle wrapping, reflection-based creation) genuinely need untyped construction. Would require unsafe casts scattered throughout the codebase instead of being centralized.

## Decision

Alternative 1. The migration pattern is:
- `T(ObjectPtr<Object> ptr)` -> `ObjectUnsafe::ObjectRefFromObjectPtr<T>(ptr)`
- `T(ObjectPtr<Object>(nullptr))` -> `ObjectUnsafe::ObjectRefFromObjectPtr<T>(nullptr)`

The constructor signatures after migration:
- **Nullable types**: `T(ObjectPtr<ContainerType>)` + `explicit T(UnsafeInit)`
- **Non-nullable types**: `explicit T(UnsafeInit)` only

For reflection, `ObjectCreatorUnsafeInit<T>` provides a fallback creator for types with `T(UnsafeInit)` but no default constructor.

## Consequences

- Breaking change for downstream C++ code that constructs `ObjectRef` subclasses via `RefType(ObjectPtr<Object>)`. Migration is mechanical.
- All unsafe construction is now auditable via `grep -r "UnsafeInit\|ObjectRefFromObjectPtr"`.
- `Shape::StridesFromShape` static factory replaces `details::MakeStridesFromShape` free function with improved const-correctness.
- `Module` gains an explicit constructor from `ObjectPtr<ModuleObj>` with a null check.

## Related Design Docs

- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- UnsafeInit tag, ObjectUnsafe helper
- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- ObjectCreatorUnsafeInit fallback
- Commit: `.knowledge/commits/2025-09-08-472e10c4086e91fb788ffe1f0eee10df4bcf5db2.md` + `472e10c`
