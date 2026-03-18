---
scope:
  - "0015-python-dataclasses"
---
# Support Python-Defined FFI Classes via @py_class

**TL;DR**: Introduces `@py_class` to allow defining FFI-compatible dataclasses entirely in Python, removing the requirement for a C++ counterpart. Uses a two-phase registration pattern that handles forward references gracefully.

## Context
- Before `@py_class`, every FFI object type required a C++ class definition with `ObjectDef<T>` reflection registration, even for simple data-holder types used only from Python.
- This forced a C++ rebuild cycle for every new type, slowed iteration, and created a barrier for Python-first users.
- The C++ reflection infrastructure (field registration, TypeSchema, structural eq/hash) was mature enough to support types registered from Python.

Usecases:
- Rapid prototyping of IR node types without touching C++.
- Python-only applications that need serializable, structurally-comparable data types compatible with the FFI ecosystem.
- Gradual migration: start with `@py_class`, move to C++ only when performance requires it.

Design Decisions:
- **Two-phase registration**: Phase 1 allocates a permanent C-level type index and registers the class in the type table. Phase 2 resolves annotations and registers fields. If forward references prevent phase 2 at decoration time, a deferred `__init__` retries on first use.
- **Reuse existing infrastructure**: `@py_class` delegates to `register_object`, `_install_init`, `_install_dataclass_dunders`, `_add_class_attrs` -- the same infrastructure as `@c_class` and `register_object`. No new C++ runtime machinery was required beyond `_register_py_class` and `_register_fields`.
- **`__ffi_*` dunder auto-registration**: Methods matching `_FFI_RECOGNIZED_METHODS` (e.g. `__ffi_repr__`, `__s_equal__`) are auto-detected and registered as both TypeMethod and TypeAttr, bridging Python methods into the C++ dispatch system.
- **Structural eq/hash opt-in**: `structure` parameter (None/"tree"/"var"/"dag"/"const-tree"/"singleton") maps to `TVMFFISEqHashKind`. Per-field `field(structure="ignore"/"def")` maps to SEqHash field flags. Disabled by default (structure=None) for safety.

## Implementation Notes
- `py_class.py` (552 lines) implements the full decorator with `_phase1_register_type`, `_phase2_register_fields`, `_collect_own_fields`, `_collect_py_methods`, deferred init, and rollback.
- `field.py` (242 lines) provides the `Field` descriptor with `compare`, `hash`, `structure`, `kw_only`, `default`, `default_factory` parameters.
- Forward-reference handling: `_PY_CLASS_BY_MODULE` maintains per-module class lookups so mutually-referential types in the same module resolve correctly. `_PENDING_CLASSES` tracks deferred registrations, flushed after each successful phase 2.
- Rollback: if phase 2 raises (bad annotation, field ordering error), `_rollback_registration` removes the class from Python-level registries. The C-level type index is permanently consumed (cannot be reclaimed), but the Python-side state is clean for retry.

## Related Design Docs
- [0015-python-dataclasses.md](../designs/0015-python-dataclasses.md)
- [0008-reflection.md](../designs/0008-reflection.md)
- [0009-structural-equal-hash.md](../designs/0009-structural-equal-hash.md)
