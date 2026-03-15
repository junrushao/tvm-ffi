---
scope:
  - "0018-python-dataclasses"
  - "0014-python-package"
---
# `@c_class` vs `@register_object` for Python FFI Type Proxies

**TL;DR**: `@c_class` is the preferred decorator for C++ types that have reflection metadata (fields, methods, `__ffi_init__` constructor), providing dataclass-style ergonomics. `@register_object` remains for types without reflection metadata or legacy types that predate the reflection system.

## Context
- The TVM FFI Python package provides two ways to create Python proxy classes for C++ object types.
- `@register_object` (original) requires manual `__init__` that calls `self.__init_handle_by_constructor__` and manual field property definitions.
- `@c_class` (new, experimental) reads C++ reflection metadata and auto-generates `__init__`, field properties, and method bindings.

Usecases:
- **New types with reflection**: Use `@c_class`. The C++ side registers fields via `ObjectDef<T>.def_ro/def_rw` and a constructor via `.def(refl::init<Args...>())` (type deduced from ObjectDef context). The Python side annotates fields and gets a synthesized `__init__` with defaults.
- **Legacy types without reflection**: Use `@register_object`. Types that predate the reflection system or that have complex construction logic not expressible through reflection.
- **Types with custom `__init__` logic**: Use `@c_class` with a manually defined `__init__` that calls `self.__ffi_init__(...)`. The decorator still provides field properties and method bindings but skips `__init__` synthesis.

Design Decisions:
- `@c_class` requires the C++ type to have reflection metadata registered via `ObjectDef<T>`. Without it, the decorator raises an error.
- The `__ffi_init__` protocol standardizes constructor dispatch: C++ registers the constructor as `__ffi_init__`, Python renames it to `__c_ffi_init__` to avoid collision with `Object.__ffi_init__` (the dispatch method).
- `@c_class` uses `@dataclass_transform` from `typing_extensions` to enable type checker integration (mypy, pyright treat the class as a dataclass).
- The `field(init=False)` parameter allows fields to be excluded from the synthesized `__init__` while still being managed by the C++ constructor.

## Implementation Notes
- `@c_class` calls `_lookup_or_register_type_info_from_type_key(type_key)` to get `TypeInfo` from the reflection registry (renamed from `_lookup_type_info_from_type_key` in 98cb8af).
- `fill_dataclass_field()` resolves each Python annotation's RHS (bare value, `field()`, or `MISSING`) into a `Field` descriptor.
- `method_init()` uses `exec()`-based code generation (following stdlib `dataclasses` pattern) to synthesize `__init__`.
- `type_info_to_cls()` creates the final class with `Object` as base, field properties from `TypeField.as_property()`, and reflected methods.

## Related Design Docs
- [0018-python-dataclasses.md](../designs/0018-python-dataclasses.md) -- Full design of the `c_class` system
- [0009-reflection.md](../designs/0009-reflection.md) -- C++ reflection system that `c_class` consumes
- [0014-python-package.md](../designs/0014-python-package.md) -- `register_object`, `Object` base class
