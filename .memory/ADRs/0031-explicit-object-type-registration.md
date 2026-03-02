---
adr: "0031"
title: "Remove Static Inline Object Type Registration in Favor of Explicit ObjectDef"
status: "accepted"
date: "2025-10-14"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM FFI contributors"
informed:
  - "C++ API users"
tags:
  - "architecture"
  - "binary-size"
  - "object-system"
source_commits:
  - "9ac31216"
source_ledgers:
  - ".memory/commits/2025-10-14-9ac31216.md"
---

# ADR-0031: Remove Static Inline Object Type Registration in Favor of Explicit ObjectDef

## TL;DR
- Static inline type index registration (`static inline int32_t _register_type_index` / `_type_index`) was removed from `TVM_FFI_DECLARE_OBJECT_INFO*` macros. Object types that need dynamic dispatch must now be explicitly registered via `reflection::ObjectDef<T>()`.
- This eliminates binary size overhead from unused type registrations that occurred in every DSO including the header.

## Status
Accepted

## Context
The `TVM_FFI_DECLARE_OBJECT_INFO` and `TVM_FFI_DECLARE_OBJECT_INFO_MUTABLE` macros previously included a `static inline int32_t _register_type_index` member and a `static inline int32_t _type_index` member that auto-registered the type in the global type table at static initialization time. This meant that every shared library (DSO) that included the header for a type would trigger type registration, even if that DSO never actually used dynamic casting for that type. For large projects with many DSOs and many object types, this caused measurable binary size overhead and startup latency.

The reflection system (`ObjectDef<T>`) already provides a mechanism for registering types with full metadata (fields, methods, documentation). Since any type that needs runtime capabilities (dynamic casting, field access, object construction) already uses `ObjectDef<T>`, the auto-registration in the header macro was redundant for well-structured code.

## Decision Drivers
- Binary size: Each auto-registration adds a static init function and string data to every DSO including the header.
- Startup latency: More static initializers mean slower DSO loading.
- Redundancy: Types using `ObjectDef<T>` for reflection already register themselves; the header-level registration is duplicative.
- Compile-time visibility: Types with static type indices (e.g., `Object`, `Function`, `Tensor`) do not need dynamic registration at all.

## Decision
Remove the `static inline int32_t _register_type_index` and `static inline int32_t _type_index` auto-registration from `TVM_FFI_DECLARE_OBJECT_INFO*` macros. Type index registration now requires one of:
1. Explicit `reflection::ObjectDef<T>()` call in a `TVM_FFI_STATIC_INIT_BLOCK` (preferred).
2. Manual call to `_GetOrAllocRuntimeTypeIndex()`.
3. Static type index (for built-in types like `Object`, `Function`, `Tensor`).

Additionally, `StaticTypeKey::kTVMFFIError` was added for `ffi.Error`, and `[[maybe_unused]]` was added to `tindex` in `_GetOrAllocRuntimeTypeIndex` since the side effect (registration) matters, not the return value.

## Alternatives Considered
### Keep auto-registration but make it lazy
- Pros: No API change. Registration happens on first use.
- Cons: Still adds code to every DSO. Lazy initialization requires thread-safe singleton pattern per type, adding complexity.

### Use weak symbols for auto-registration
- Pros: Linker deduplicates across DSOs.
- Cons: Weak symbols are not portable across all platforms (notably Windows). Does not eliminate the per-DSO static init function.

### Use a code generation step to collect registrations
- Pros: Zero overhead for types not in the generated list.
- Cons: Requires build system integration. Not compatible with header-only usage patterns.

## Why This Option Won
- The explicit `ObjectDef<T>` model is already the standard pattern for any type that needs runtime features. Removing auto-registration simply aligns the macro with the established practice.
- The boilerplate cost is minimal: one `ObjectDef<T>()` call per type, which is already needed for reflection metadata.
- Binary size savings are proportional to the number of object types times the number of DSOs, which grows rapidly in large projects.
- Static-indexed types (built-in types) are completely unaffected.

## Consequences
### Positive
- Reduced binary size in downstream DSOs that include object headers but do not use dynamic dispatch for those types.
- Faster DSO loading due to fewer static initializers.
- Clearer intent: type registration is now explicit, making it obvious which types are runtime-registered.
- Eliminated the subtle "registration in every DSO" behavior that could cause duplicate registration warnings.

### Negative
- C++ users who relied on auto-registration for dynamic casting must add an `ObjectDef<T>()` call. This is a breaking change.
- Types that are only used via `IsInstance<T>()` checks (without reflection) now need explicit registration, which was previously free.

### Risks
- Downstream code that relied on auto-registration will silently fail at runtime (dynamic cast returns false for unregistered types) rather than failing at compile time. Mitigation: the `_GetOrAllocRuntimeTypeIndex()` call still exists for types that need dynamic dispatch without full reflection; they just need to be called explicitly.

## Implementation Notes
- The `TVM_FFI_DECLARE_OBJECT_INFO` macro was modified to remove the `static inline` members.
- `StaticTypeKey::kTVMFFIError = "ffi.Error"` was added to the static type key list.
- `[[maybe_unused]]` attribute was added to `tindex` in `_GetOrAllocRuntimeTypeIndex` to suppress unused-variable warnings.
- All in-tree types already used `ObjectDef<T>` and required no migration.

## Validation
- All existing C++ tests pass (since in-tree types use `ObjectDef<T>`).
- Binary size can be measured before/after in downstream projects.
- `tests/cpp/test_reflection.cc` validates explicit registration.

## Migration and Rollback
- **Migration**: Add `ObjectDef<T>("doc")` in a `TVM_FFI_STATIC_INIT_BLOCK` for any type that uses `IsInstance<T>()` or dynamic casting.
- **Rollback**: Re-add the `static inline int32_t _register_type_index` and `_type_index` members to the macro. Low risk since the macro is in a single header.

## Related Design Docs
- [.memory/designs/0006-reflection-system.md](.memory/designs/0006-reflection-system.md) (ObjectDef is the replacement mechanism)
- [.memory/designs/0002-object-system-and-reference-counting.md](.memory/designs/0002-object-system-and-reference-counting.md) (object type hierarchy)

## Related Diagrams
None

## Evidence Matrix
- Removal of static inline registration from macros -> `.memory/commits/2025-10-14-9ac31216.md` + `9ac31216` + `include/tvm/ffi/object.h`
- `StaticTypeKey::kTVMFFIError` addition -> `9ac31216` + `include/tvm/ffi/object.h`
- `[[maybe_unused]]` on tindex -> `9ac31216` + `include/tvm/ffi/object.h`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Monitor downstream projects for type registration issues after upgrading.
- Document the explicit registration requirement in the C++ API guide.
