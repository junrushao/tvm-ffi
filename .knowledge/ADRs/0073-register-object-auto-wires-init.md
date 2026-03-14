---
scope:
  - "0014-python-bindings"
  - "0006-reflection"
  - "0023-type-schema-and-stubgen"
---
# `register_object` Auto-Wires `__init__` from C++ Reflection

**TL;DR**: `register_object` now automatically wires `__init__` from C++ reflection metadata (`__ffi_init__`), making `__init__` available on all registered objects with C++ init support -- not just `@c_class`-decorated ones. Stubgen is also extended to generate `__init__` signatures from C++ reflection.

## Context

Before commit `6973d22` (#491), `_install_init` (which connects C++ `__ffi_init__` to Python `__init__`) was only called from `_install_dataclass_dunders` (invoked by `@c_class`). This meant that classes registered with bare `@register_object` that had a C++ `refl::init<>()` or auto-init would not get an `__init__` -- users had to either use `@c_class` or call `__ffi_init__` directly.

This caused practical problems: the `examples/python_packaging` example exposed `IntPair` via `@register_object` and `IntPair(1, 2)` failed at runtime because `__init__` was not wired.

Meanwhile, stubgen did not generate `__init__` signatures for objects at all, meaning IDE autocompletion showed no constructor hints.

Usecases:
- `@register_object` classes with C++ `refl::init<Args...>()` should be constructible
- IDE/type-checker users need `__init__` signatures from stubgen
- Downstream packages using `@register_object` (not `@c_class`) for simple types

Design Decisions:
- **Add `_install_init(cls, enabled=True)` call to `register_object._register()`**: After `_add_class_attrs`, `register_object` now calls `_install_init`. This wires `__init__` when `__ffi_init__` is available. Classes without `__ffi_init__` keep `object.__init__` behavior (no TypeError guard installed -- that is reserved for explicit `@c_class(init=False)`).
- **Graceful no-op for classes without `__ffi_init__`**: When `enabled=True` and no `__ffi_init__` exists, `_install_init` returns silently. This preserves backward compatibility for `Object()` and types that intentionally lack constructors.
- **Stubgen `__init__` generation**: New `InitFieldInfo` and `ObjectInfo.gen_init()` in `stub/utils.py` walk the TypeInfo parent chain to collect field flags (`c_init`, `c_kw_only`, `c_has_default`) and emit typed `__init__` stubs. Two code paths: `_gen_auto_init` (KWARGS protocol with proper signature for auto-inits) and `_gen_c_init` (positional pass-through for explicit `refl::init<Args...>()`).
- **`codegen.py` integration**: `generate_object()` calls `gen_init()` and injects the result into the `TYPE_CHECKING` block before method stubs.

## Implementation Notes

- `registry.py` change: single-line addition of `_install_init(cls, enabled=True)` after `_add_class_attrs`.
- `_install_init` behavior when `enabled=True`: if `__ffi_init__` not found in type methods, returns without action (no TypeError guard). This differs from `enabled=False` which installs a TypeError guard.
- `stub/utils.py` adds `InitFieldInfo` dataclass and `ObjectInfo.gen_init()` method. `gen_init()` returns a list of lines for the `__init__` stub.
- `core.pyi` updated with `TypeField.c_init`, `c_kw_only`, `c_has_default` and `TypeInfo.type_ancestors` stubs.
- Testing objects in `testing.py` reorganized/renamed for clarity.
- 30 `ty: ignore` comments removed from tests after stubgen generates proper `__init__` signatures.
- Evidence: `.knowledge/commits/2026-03-01-6973d225eb3c67a7c306e36b20a100c5e9ff46f7.md` + `6973d22`

## Related Design Docs

- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- `register_object` flow
- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- C++ `__ffi_init__` generation
- [`.knowledge/designs/0023-type-schema-and-stubgen.md`](../designs/0023-type-schema-and-stubgen.md) -- Stubgen tool
- [`.knowledge/ADRs/0068-auto-init-from-reflection.md`](0068-auto-init-from-reflection.md) -- Auto-init from C++ reflection
- [`.knowledge/ADRs/0069-c-class-as-register-object-plus-dunders.md`](0069-c-class-as-register-object-plus-dunders.md) -- `@c_class` as register_object + dunders
