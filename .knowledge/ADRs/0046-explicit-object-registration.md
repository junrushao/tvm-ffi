---
scope:
  - "0003-object-system"
  - "0006-reflection"
---
# Remove Static Inline Type Registration in Favor of ObjectDef

**TL;DR**: Removed automatic static-inline type registration from `TVM_FFI_DECLARE_OBJECT_INFO` macros. Object types now require explicit registration via `reflection::ObjectDef<T>()` for dynamic casting to work, trading convenience for reduced binary size and initialization overhead.

## Context

The `TVM_FFI_DECLARE_OBJECT_INFO` macro previously triggered automatic static-inline type registration by including a `static inline` variable whose constructor called type registration functions. This had a significant unintended cost:

1. **Per-DLL binary overhead**: Every shared library that `#include`s a header with `TVM_FFI_DECLARE_OBJECT_INFO` gets a copy of the registration code, even for types the library never uses. For projects with many DLLs linking against FFI headers, this caused measurable binary bloat.

2. **Hidden initialization logic**: Static initialization order is notoriously fragile in C++. Having type registration scattered across many compilation units (one per header inclusion) made the initialization order harder to reason about.

3. **Redundancy**: The `reflection::ObjectDef<T>()` registration (introduced earlier for field/method reflection) already calls `GetOrAllocRuntimeTypeIndex`, which registers the type in the type table. The static-inline registration was entirely redundant for types that use `ObjectDef`.

Usecases:
- Large ML frameworks with dozens of DLLs that include FFI headers but only use a subset of Object types
- Plugin-based architectures where reducing per-plugin binary size matters
- DSL compilers that define many internal types but only expose a few through FFI

Design Decisions:
- Remove the static-inline registration trigger from `TVM_FFI_DECLARE_OBJECT_INFO`.
- Built-in types (`ErrorObj`, `FunctionObj`, etc.) are pre-registered explicitly in `object.cc`.
- Object types not registered via `ObjectDef` will not support `IsInstance` / dynamic downcast. This is intentional: if a type needs dynamic dispatch, it must be reflected.

**Alternatives considered:**

1. **Keep static-inline but use weak symbols**: Use `__attribute__((weak))` to deduplicate across DLLs. Rejected because weak symbols have platform-specific behavior (unreliable on Windows) and do not eliminate the initialization overhead.

2. **Lazy registration on first use**: Register types when `IsInstance` is first called with an unregistered type index. Rejected because it would require a global lock on every `IsInstance` call (hot path), and the "first use" detection adds complexity.

3. **Compile-time registration list (static table)**: Generate a registration table at compile time. Rejected because it requires build system integration and does not work well with header-only usage patterns.

**Consequences:**
- Objects not registered via `ObjectDef` silently lose dynamic casting. If code calls `IsInstance<FooObj>(obj)` and `FooObj` was never registered, the check always returns false. This is acceptable because the expectation is that useful Object types are registered through `ObjectDef` for reflection.
- Binary size reduction for DLLs that include FFI headers but do not use all declared types.
- Simpler initialization: type registration happens in well-defined `TVM_FFI_STATIC_INIT_BLOCK()` blocks, not scattered across header inclusions.

**Migration**: Existing code that relies on `IsInstance` or `Downcast` for a custom Object type must add an `ObjectDef<CustomObj>()` registration block. The compiler will not warn about missing registration; failures manifest as incorrect `IsInstance` results at runtime.

## Implementation Notes
- Commit `9ac3121` (#116) removed the static-inline trigger and updated built-in type registration.
- The change was paired with heap-allocated singletons (commit `4206f16` #133) to avoid static destruction order issues with the global type table.

## Related Design Docs
- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- Object system type table
- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- ObjectDef registration
