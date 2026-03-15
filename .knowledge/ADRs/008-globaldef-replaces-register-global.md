---
scope:
  - ".knowledge/designs/function-system.md"
  - ".knowledge/designs/reflection.md"
---
# ADR-008: GlobalDef Replaces TVM_FFI_REGISTER_GLOBAL

**TL;DR**: Replace the `TVM_FFI_REGISTER_GLOBAL` macro and `Function::Registry` class with `reflection::GlobalDef` inside `TVM_FFI_STATIC_INIT_BLOCK`, unifying function registration under the reflection infrastructure with metadata support (doc, type_schema).

## Context
The initial design used `TVM_FFI_REGISTER_GLOBAL("name").set_body_typed(f)` for global function registration. This macro expanded to a static `Function::Registry` object with chaining methods (`set_body_typed`, `set_body_packed`, `set_body_method`). The approach had limitations:

Usecases:
- Metadata-rich registration: global functions need documentation strings and type schemas for Python stub generation and IDE support. The old macro-based path had no metadata support.
- Consistent registration API: object types use `ObjectDef` with `def`/`def_ro`/`def_rw`; using a completely different pattern (`TVM_FFI_REGISTER_GLOBAL`) for functions created unnecessary cognitive load.
- Internal registry migration: `GlobalFunctionTable` migrated from `std::unordered_map<string, Function*>` to `Map<String, Any>` storing `GlobalFunctionTable::Entry` objects with metadata. The old `Function::Registry` was not designed to populate this metadata.

Design Decisions:
- Introduce `reflection::GlobalDef` with `def(name, func, extra...)`, `def_packed(name, func, extra...)`, and `def_method(name, method, extra...)`.
- Each method builds a `TVMFFIMethodInfo` (name, doc, type_schema, flags, function) and calls `TVMFFIFunctionSetGlobalFromMethodInfo`.
- Use `TVM_FFI_STATIC_INIT_BLOCK` as the universal static-init block, replacing both `TVM_FFI_REGISTER_GLOBAL` and `TVM_FFI_REFLECTION_DEF`.
- Remove `Function::Registry` class and `TVM_FFI_REGISTER_GLOBAL` macro entirely (not deprecated -- removed).

## Alternatives

### A: Keep TVM_FFI_REGISTER_GLOBAL alongside GlobalDef
- Description: Maintain backward compatibility by keeping both registration paths.
- Pros: No migration needed for downstream code; gradual transition possible.
- Cons: Two ways to do the same thing creates confusion about which to use; `Function::Registry` cannot carry metadata (doc, type_schema), so it will always be the "lesser" option; maintaining two code paths doubles the testing and documentation burden.
- Why rejected: Having two registration mechanisms with different capabilities and no clear guidance on which to use is worse than a clean migration. All internal call sites were migrated before removal.

### B: Add metadata to Function::Registry instead of creating GlobalDef
- Description: Extend `Registry` with `set_doc(...)`, `set_type_schema(...)` methods.
- Pros: Minimal API change; familiar pattern preserved.
- Cons: `Function::Registry` is a standalone class in `function.h`, not part of the reflection system; it would need to independently build `TVMFFIMethodInfo` and call `TVMFFIFunctionSetGlobalFromMethodInfo`, duplicating logic already in `ReflectionDefBase`; the macro-based registration pattern (`TVM_FFI_REGISTER_GLOBAL`) is inherently limited (one function per macro invocation, no chaining of multiple registrations).
- Why rejected: Duplicating the `TVMFFIMethodInfo` construction logic in two places (Registry and reflection) violates DRY. `GlobalDef` inherits from `ReflectionDefBase` and reuses all the trait-application and method-wrapping machinery.

## Implementation Notes
- Migration pattern:
  ```cpp
  // Old:
  TVM_FFI_REGISTER_GLOBAL("my.Add").set_body_typed([](int a, int b) { return a + b; });

  // New:
  TVM_FFI_STATIC_INIT_BLOCK() {
    tvm::ffi::reflection::GlobalDef().def("my.Add", [](int a, int b) { return a + b; });
  }
  ```
- `GlobalDef::def_method` dispatches ObjectRef-derived classes by value and Object-derived classes by const pointer, using `if constexpr` in `ReflectionDefBase::GetMethod`.
- Duplicate registration via the `TVMFFIMethodInfo*` path uses `TVM_FFI_LOG_AND_THROW` (logs to stderr before throwing) because duplicate registration typically occurs at static init time where thrown exceptions may be silently lost.

## Related Design Docs
- `.knowledge/designs/function-system.md` -- GlobalDef usage and registration flow
- `.knowledge/designs/reflection.md` -- ReflectionDefBase, ObjectDef, GlobalDef hierarchy
