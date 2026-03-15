---
scope:
  - "0009-reflection"
  - "0018-python-dataclasses"
---
# Auto-Generate `__ffi_init__` from Reflection Metadata

**TL;DR**: When no explicit `refl::init<Args...>` is registered for a reflected type, `ObjectDef` auto-generates a packed `__ffi_init__` constructor from field metadata at C++ static-init time, eliminating the need for Python-side `exec()`-based `__init__` code generation and removing the Python field descriptor infrastructure.

## Context
- Previously, constructor synthesis for reflected types required a two-layer system: C++ registered `refl::init<T, Args...>` for explicit constructors, while Python's `c_class` decorator synthesized `__init__` via `exec()` with `field()` descriptors (`Field`, `KW_ONLY`, `MISSING`) managing defaults and keyword-only semantics.
- This duplication was fragile: Python-side field descriptors could drift from C++ reflection metadata, and the `exec()`-based codegen (~555 lines in `_utils.py`, `field.py`, `c_class.py`) added maintenance burden and complexity.
- The C++ reflection system already has complete field metadata: names, types, offsets, getters/setters, defaults (including factories), and flags.

Usecases:
- Any C++ type with `ObjectDef` registration that does not provide an explicit `refl::init<Args...>` automatically gets a working `__ffi_init__` callable.
- Python `@c_class` (now just `register_object`) and `@register_object` both work with auto-generated init without any Python-side code generation.
- Per-field control via C++ traits: `refl::init(false)` excludes from init, `refl::kw_only(true)` requires keyword argument, `refl::compare(false)` / `refl::hash(false)` excludes from recursive comparison/hashing.

Design Decisions:
- **C++ auto-generates init when none explicitly registered.** The `ObjectDef` destructor checks whether `__ffi_init__` was already registered; if not, calls `RegisterAutoInit(type_index)` which creates a packed `Function` from field metadata.
- **Four new field flag bits control per-field behavior.** `CompareOff` (1<<7), `HashOff` (1<<8), `InitOff` (1<<9), `KwOnly` (1<<10) — set via lowercase trait helpers `compare(bool)`, `hash(bool)`, `init(bool)`, `kw_only(bool)`.
- **Python-side field descriptors removed.** `field()`, `Field`, `KW_ONLY`, `MISSING`, `method_init()`, `method_repr()`, `_utils.py`, and `field.py` deleted. `c_class` simplified to `register_object(type_key)`.
- **KWARGS sentinel protocol for mixed positional+keyword.** The auto-generated init detects a special `ffi.GetKwargsObject()` sentinel in the argument list to switch from positional-only mode to mixed positional+keyword mode. This enables the same packed function to handle both calling conventions.
- **`__c_ffi_init__` always overrides per type.** `_add_class_attrs` in `registry.py` unconditionally sets `__c_ffi_init__` for each type, preventing inherited base-class constructors from masking derived-class constructors.

## Implementation Notes
- `MakeInit(type_index)` in `reflection/init.h` pre-computes field analysis (init/kw_only/has_default), then returns a closure that:
  1. Creates object via `TVMFFIObjectCreator`
  2. Binds positional args to `pos_indices` (sorted: required before optional via `stable_partition`)
  3. If KWARGS sentinel detected: binds keyword args by name lookup
  4. Fills defaults for unbound fields via `SetFieldToDefault`
  5. Throws `TypeError` for missing required fields or unknown keywords
- `RegisterAutoInit(type_index)` calls `MakeInit` and registers with `{"auto_init": true}` metadata
- The `ObjectDef` destructor auto-calls `RegisterAutoInit` when no explicit init was registered
- Lowercase trait classes (`repr`, `compare`, `hash`, `kw_only`) in `reflection/registry.h` provide the ergonomic API: `refl::compare(false)`, `refl::hash(false)`, `refl::init(false)`, `refl::kw_only(true)`

## Related Design Docs
- [0009-reflection.md](../designs/0009-reflection.md) -- Reflection system, auto-init, field flags, lowercase traits
- [0018-python-dataclasses.md](../designs/0018-python-dataclasses.md) -- Simplified c_class = register_object
