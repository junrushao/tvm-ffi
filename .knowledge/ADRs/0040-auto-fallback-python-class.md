---
scope:
  - "0014-python-bindings"
  - "0003-object-system"
  - "0006-reflection"
---
# Auto-Create Python Fallback Classes for Unregistered C++ Types

**TL;DR**: When a C++ object type has no registered Python class, the system auto-generates a proxy class with reflected fields/methods instead of returning a bare `Object` with a warning. This preserves full reflected API access for C++-only types encountered at runtime.

## Context

When `make_ret_object` encounters a `type_index` with no registered Python class (`TYPE_INDEX_TO_CLS[type_index] is None`), the system must decide how to represent the object in Python. Previously, it logged a warning and returned a bare `Object` instance, losing all reflected fields and methods. This was especially problematic in cross-language workflows where:

- C++ libraries define types that have no explicit Python `@register_object` counterpart.
- Interactive debugging requires inspecting fields and calling methods on C++ objects.
- Downstream Python code receives objects from C++ containers (e.g., `Array` elements) of unknown types.

Usecases:
- A compiler plugin defines custom IR node types in C++. Python tooling iterating over IR graphs encounters these nodes and needs field access for analysis.
- A model checkpoint contains objects whose Python wrappers were not imported. The user can still inspect field values.

Design Decisions:
- Auto-generate a Python proxy class via `make_fallback_cls_for_type_index` in `object.pxi`. The class inherits from the parent type's fallback or registered class, has reflected fields as `property` descriptors and reflected methods as bound methods, and is cached in `TYPE_INDEX_TO_CLS` for future lookups.

## Implementation Notes

- **Recursive parent resolution**: Before creating a fallback class for type index N, the system walks `type_ancestors` from root to leaf and recursively creates fallback classes for any unregistered ancestor. This ensures the Python class hierarchy mirrors C++.
- **Encapsulated attribute builders**: `TypeField.as_property(cls)` and `TypeMethod.as_callable(cls)` centralize property/method creation from reflection metadata, replacing scattered inline logic.
- **Self-resolving parent chain**: `TypeInfo.__post_init__` auto-resolves `parent_type_info` by reading `type_ancestors[-1]` from C and calling `_lookup_or_register_type_info_from_type_key`.
- **One-shot caching**: Each fallback class is created once and registered via `_update_registry`, ensuring the slow path fires only once per type.
- **Docstring policy**: Fallback classes include a warning in `__doc__` indicating they are auto-generated. Field/method docstrings are `None` unless explicitly set in C++ (commit `43ffe57` reverted auto-generated fallback docstrings to avoid Sphinx conflicts).

### Alternatives Considered

**Alternative A: Keep warning + bare Object (status quo)**
- Pros: Simplest implementation.
- Cons: Loses all reflected fields/methods. Users cannot inspect or call methods on unregistered types. Debugging is severely hampered.

**Alternative B: Require explicit `@register_object` for all types**
- Pros: Type-safe, predictable, no auto-generation surprises.
- Cons: Breaks cross-language workflows where Python does not know about all C++ types. Every C++ type addition requires a corresponding Python registration.

**Alternative C: Return a generic `DynamicObject` with `__getattr__` delegation**
- Pros: Simpler than full class generation, avoids polluting class hierarchy.
- Cons: No proper `isinstance` chain, no tab-completion of fields in IDEs, no `property` descriptors for type checking.

### Consequences

- **Behavioral change**: `make_ret_object` no longer returns bare `Object` for unregistered types. All C++ types get a proper Python proxy.
- **Migration**: Existing code that checks `type(obj) is Object` for fallback detection will need updating. The auto-generated class will have a different type.
- **Rollback**: Reverting to bare-Object fallback requires removing `make_fallback_cls_for_type_index` and restoring the warning path in `make_ret_object`.

## Related Design Docs

- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- `make_ret_object` dispatch and `@register_object` flow
- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- `TypeInfo`, `TypeField`, `TypeMethod` consumed by fallback class builder
- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- `type_ancestors` hierarchy used for recursive parent resolution
- Commits: `.knowledge/commits/2025-09-25-98cb8af49ff599c217fce96c3d4f57c0f52b8ec4.md` + `98cb8af`, `.knowledge/commits/2025-09-26-43ffe571bfef2a3f2c2dc254ca3e5dc10e093daa.md` + `43ffe57`
