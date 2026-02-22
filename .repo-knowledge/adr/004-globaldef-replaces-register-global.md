# ADR 004: GlobalDef Replaces TVM_FFI_REGISTER_GLOBAL Macro

- Status: Accepted
- Date: 2025-07-15
- Owners: Tianqi Chen

## Context

The TVM FFI used a `TVM_FFI_REGISTER_GLOBAL` macro (and the underlying
`Function::Registry` class) for registering global functions. This macro
expanded to a static variable that called `set_body_typed`, `set_body_packed`,
or `set_body_method` on a builder object.

Meanwhile, the reflection system introduced `ObjectDef<T>` as a builder-pattern
API for registering object type metadata with `def_ro`, `def_rw`, and
`def_static`. The global function registration mechanism was inconsistent:
object field/method registration used the new `ObjectDef` pattern, while global
function registration used the older macro pattern.

This inconsistency made the API harder to learn and introduced a maintenance
burden: two parallel registration mechanisms needed to be kept in sync.

## Decision

Replace the `TVM_FFI_REGISTER_GLOBAL` macro with a new `reflection::GlobalDef`
class that mirrors the `ObjectDef` API:

```cpp
// Before (legacy):
TVM_FFI_REGISTER_GLOBAL("ffi.FuncName").set_body_typed(some_func);

// After (new):
TVM_FFI_STATIC_INIT_BLOCK(register_funcs) {
  refl::GlobalDef()
      .def("ffi.FuncName", some_func);
}
```

The migration was carried out in two steps:

1. **Introduce GlobalDef and migrate internal sites** (`b333288`): All
   `TVM_FFI_REGISTER_GLOBAL` usages in `container.cc`, `function.cc`,
   `ndarray.cc`, `object.cc`, and `testing.cc` were migrated to
   `GlobalDef().def(...)` inside `TVM_FFI_STATIC_INIT_BLOCK` blocks.

2. **Remove legacy macro and class** (`26b68b0`): The `TVM_FFI_REGISTER_GLOBAL`
   macro, `TVM_FFI_FUNC_REG_VAR_DEF` macro, and `Function::Registry` class
   (144 lines) were deleted from `function.h`.

Additionally, the duplicate registration error message was improved (`5b0cceb`)
to use `TVM_FFI_LOG_AND_THROW` with guidance about likely causes.

## Consequences

- Positive: Unified registration API. Both object metadata and global functions
  now use the same builder pattern, reducing the learning curve for contributors.
- Positive: Reduced public API surface. The `Function::Registry` class and two
  macros were removed (144 lines deleted from `function.h`).
- Positive: Registration happens inside `TVM_FFI_STATIC_INIT_BLOCK`, making the
  initialization timing explicit and consistent.
- Negative: **Breaking change** for all downstream code using
  `TVM_FFI_REGISTER_GLOBAL`. All such call sites must be rewritten.
- Migration/Rollout: Replace
  `TVM_FFI_REGISTER_GLOBAL("name").set_body_typed(f)` with
  `TVM_FFI_STATIC_INIT_BLOCK(label) { refl::GlobalDef().def("name", f); }`.
  The `def_packed` and `def_method` variants are available for packed functions
  and methods respectively.

## References
- Range summary: `.repo-knowledge/ranges/2025-07-31-0966C36-0342D85.md`
- Evidence commits: `b333288162ba3a883dbf6b1ce23672f687d70163`, `26b68b0256fb40baa8aeb55847050d13b064f441`, `5b0cceb05bd21a4c9d1c029b08742cfafedcd023`
- External references: none

## Related Design Docs
- `.repo-knowledge/design/004-reflection-system.md`
- `.repo-knowledge/design/002-namespace-and-api-migration.md`

## Notes
The `GlobalDef` class lives in `include/tvm/ffi/reflection/registry.h` (after
the reflection module split in `e95b43b`). It inherits from
`ReflectionDefBase` and provides `def`, `def_packed`, and `def_method` methods.
The `GetMethod` dispatcher was also improved in `b333288` to correctly handle
both `Object`-derived and `ObjectRef`-derived class types.
