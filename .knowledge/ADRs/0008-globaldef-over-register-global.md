---
scope:
  - "0004-function-system"
  - "0009-reflection"
---
# Replace Function::Registry with reflection::GlobalDef

**TL;DR**: The decision to phase out `Function::Registry` and `TVM_FFI_REGISTER_GLOBAL` in favor of `reflection::GlobalDef`, unifying function registration under the reflection system with metadata support.

## Context
- `Function::Registry` (with its `set_body_typed`, `set_body_packed`, `set_body_method` methods) and the `TVM_FFI_REGISTER_GLOBAL` macro were the original mechanism for registering global functions.
- The reflection system introduced `ObjectDef<T>` for type registration with rich metadata (docstrings, type schemas, flags). Global function registration lacked equivalent metadata support.
- Having two separate registration systems (Function::Registry for functions, ObjectDef for types) created inconsistency and duplicated infrastructure.
- The `TVMFFIFunctionSetGlobalFromMethodInfo` C API was added to support function registration with full `TVMFFIMethodInfo` metadata (name, doc, metadata, flags), which `Function::Registry` did not use.

Usecases:
- Registering global functions with docstrings and type schemas for binding generation: `GlobalDef().def("my.func", func, "does something")`.
- Co-locating type, method, and function registration in a single `TVM_FFI_STATIC_INIT_BLOCK`.
- Fluent builder chaining: `GlobalDef().def("a", fa).def("b", fb).def_packed("c", fc)`.

Design Decisions:
- **`GlobalDef` inherits from `ReflectionDefBase`**, sharing infrastructure with `ObjectDef` (method wrapping, metadata traits, etc.).
- **Three registration methods**: `def(name, func)` (typed), `def_packed(name, func)` (packed args), `def_method(name, func)` (class method with self parameter).
- **`TVM_FFI_STATIC_INIT_BLOCK() { ... }`** replaces `TVM_FFI_REGISTER_GLOBAL` as the init mechanism: a general-purpose static init macro not tied to function registration specifically. On GCC/Clang, emits an `__attribute__((constructor))` function; on MSVC, uses a static-variable-driven function call pattern.
- **`Function::Registry` and `TVM_FFI_REGISTER_GLOBAL` are deleted**: All internal call sites were migrated. This is a breaking change for external C++ code using the old API.

## Implementation Notes
- `GlobalDef::RegisterFunc` calls `TVMFFIFunctionSetGlobalFromMethodInfo` to register functions with full metadata, unlike the old `Function::SetGlobal` which stored only the function object.
- `GetMethod` in `ReflectionDefBase` dispatches with `if constexpr`: ObjectRef-derived classes get by-value self parameter; Object-derived classes get const pointer self parameter.
- Duplicate registration via `GlobalDef` now throws a descriptive `RuntimeError` logged to stderr, with diagnostic guidance.

## Related Design Docs
- [0004-function-system.md](.knowledge/designs/0004-function-system.md)
- [0009-reflection.md](.knowledge/designs/0009-reflection.md)
