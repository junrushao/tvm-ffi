---
scope:
  - "0004-function-system"
  - "0006-reflection"
---
# GlobalDef Replaces TVM_FFI_REGISTER_GLOBAL

**TL;DR**: `reflection::GlobalDef` replaces the `TVM_FFI_REGISTER_GLOBAL` macro and `Function::Registry` class as the standard mechanism for registering global functions. `GlobalDef` attaches rich metadata (type schemas, docstrings, flags) via `TVMFFIMethodInfo`, enabling Python stub generation and IDE tooling.

## Context

`TVM_FFI_REGISTER_GLOBAL("name").set_body_typed(fn)` used a `static inline Registry&` pattern that stored only a function name and function pointer. The reflection system needed richer metadata per function for:
- Python stub generation (`tvm-ffi-stubgen`) that can emit type-annotated function signatures.
- IDE tooling that can display function documentation.
- Consistent registration via `TVM_FFI_STATIC_INIT_BLOCK` (the universal init mechanism).

Usecases:
- `GlobalDef().def("ffi.MakeObjectFromPackedArgs", MakeObjectFromPackedArgs)` registers a function with auto-derived type schema.
- `GlobalDef().def("testing.nop", [](PackedArgs, Any*) {}, "A no-op function for benchmarking")` attaches a docstring.

Design Decisions:
- **New `GlobalDef` builder class**: Inherits `ReflectionDefBase`, providing `def`, `def_packed`, `def_method` with variadic extra args for metadata traits.
- **Uses `TVMFFIFunctionSetGlobalFromMethodInfo`**: The C API entry point that stores full `TVMFFIMethodInfo` (name, doc, type_schema, flags, function) in the `GlobalFunctionTable::Entry`.
- **Complete removal of `Function::Registry` and `TVM_FFI_REGISTER_GLOBAL`**: The old macro and builder class are deleted (~144 lines removed from `function.h`).

**Alternatives considered**:

1. **Extend `TVM_FFI_REGISTER_GLOBAL` to carry metadata**: Adds complexity to the existing macro and `Registry` class. The macro pattern (`static inline Registry&`) is harder to extend with variadic args than a builder class.
2. **Keep both mechanisms**: Maintenance burden of two divergent registration APIs with different metadata capabilities.

**Consequences**:
- Breaking change: all downstream C++ code using `TVM_FFI_REGISTER_GLOBAL` must migrate to `GlobalDef`.
- Functions registered via `GlobalDef` carry richer metadata than the old path.
- The `GlobalFunctionTable` now stores `Entry` objects (embedding `TVMFFIMethodInfo`) in `Map<String, Any>`, not raw `Function*` pointers.
- Rollback: The old macro could be re-introduced as a thin wrapper around `GlobalDef` if migration proves too disruptive.

## Implementation Notes

- `GlobalDef::RegisterFunc` constructs a `TVMFFIMethodInfo` and calls `TVMFFIFunctionSetGlobalFromMethodInfo`.
- `GlobalDef` inherits `ReflectionDefBase::GetMethod` for member-function-pointer wrapping, supporting both `ObjectRef`-derived (pass by value) and `Object`-derived (pass by const pointer) class methods.
- All core FFI registrations in `src/ffi/*.cc` migrated to `GlobalDef` within `TVM_FFI_STATIC_INIT_BLOCK` blocks.
- Evidence: `include/tvm/ffi/reflection/registry.h` (GlobalDef), `include/tvm/ffi/function.h` (deletion), commits `b333288`, `26b68b0`.

## Related Design Docs

- [`.knowledge/designs/0004-function-system.md`](../designs/0004-function-system.md) -- GlobalFunctionTable
- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- GlobalDef and ReflectionDefBase
- [`.knowledge/ADRs/0004-global-function-table-leak.md`](0004-global-function-table-leak.md) -- Intentional leak (still applies)
