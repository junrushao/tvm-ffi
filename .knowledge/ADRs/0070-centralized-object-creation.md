---
scope:
  - "0006-reflection"
  - "0003-object-system"
---
# Centralized Object Creation via `CreateEmptyObject`/`HasCreator`

**TL;DR**: All reflection-based object creation is centralized into two inline helpers -- `CreateEmptyObject` and `HasCreator` -- that unify the two-step "check creator, call creator" pattern and add a `__ffi_new__` type-attribute fallback for Python-defined types.

## Context

Before commit `e268eb1` (#501), four separate call sites in the codebase duplicated the same pattern: check `type_info->metadata != nullptr`, check `metadata->creator != nullptr`, call the creator, and wrap the result in an `ObjectPtr`. These sites were:
- `reflection::ObjectCreator` (`creator.h`)
- `MakeInit` auto-init generator (`init.h`)
- `MakeObjectFromPackedArgs` (`reflection_extra.cc`)
- JSON deserialization (`serialization.cc`)

Each duplicated the validation logic slightly differently, and none supported Python-defined types that lack a C++ creator but register a `__ffi_new__` type attribute.

Usecases:
- C++ reflected types with `ObjectCreatorDefault<T>` or `ObjectCreatorUnsafeInit<T>` -- fast path via `metadata->creator`
- Python-defined types using `@py_class` that register a `__ffi_new__` type attribute instead of a native creator
- Serialization round-trips that reconstruct objects from type keys

Design Decisions:
- **Two-path resolution**: `CreateEmptyObject` tries the native `metadata->creator` first (fast path), then falls back to `__ffi_new__` type attribute lookup via `TVMFFIGetTypeAttrColumn`. This preserves zero-overhead for C++ types while enabling Python-defined types.
- **`HasCreator` predicate**: Separate from `CreateEmptyObject` so callers can check creatability without side effects (e.g., `ObjectDef` destructor deciding whether to register auto-init).
- **Placed in `creator.h`**: Both helpers live alongside `ObjectCreator` in `include/tvm/ffi/reflection/creator.h`, keeping all creation logic in one header. `creator.h` now includes `function.h` (for `Function` type needed by `__ffi_new__` invocation).
- **Fully qualified `details::` references**: The same commit qualifies bare `details::` references to `::tvm::ffi::details::` in `overload.h`, `registry.h`, and `init.h` to prevent ADL/lookup ambiguity when these headers are included from other namespaces.

## Implementation Notes

- `CreateEmptyObject(type_info)`:
  1. If `type_info->metadata->creator != nullptr`, calls it via `TVM_FFI_CHECK_SAFE_CALL`, wraps result in `ObjectPtr<Object>`.
  2. Otherwise, looks up `__ffi_new__` column via `TVMFFIGetTypeAttrColumn`. If found and the value at the type's index is a `Function`, invokes it and casts result to `ObjectRef`.
  3. Throws `RuntimeError` if neither path succeeds.
- `HasCreator(type_info)`: Same two-path check but returns `bool` without side effects.
- `ObjectCreator` constructor now calls `HasCreator` instead of duplicating the check.
- `ObjectCreator::operator()` calls `CreateEmptyObject` instead of `metadata->creator` directly.
- The four deduplicated sites in `init.h`, `overload.h`, `reflection_extra.cc`, and `serialization.cc` now call `CreateEmptyObject`.
- Evidence: `.knowledge/commits/2026-03-10-e268eb1d2d55ae97bdaab7ab52f381f436fd0c82.md` + `e268eb1`

## Related Design Docs

- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- Reflection system where ObjectCreator and creation logic live
- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- Object lifecycle and type registration
- [`.knowledge/ADRs/0068-auto-init-from-reflection.md`](0068-auto-init-from-reflection.md) -- Auto-init generation that consumes HasCreator
