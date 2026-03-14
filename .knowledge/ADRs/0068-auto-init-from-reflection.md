---
scope:
  - "0006-reflection"
  - "0027-dataclass-operations"
---
# Auto-Generated `__ffi_init__` from Reflection Metadata

**TL;DR**: `ObjectDef<T>` now auto-generates a packed `__ffi_init__` constructor in its destructor when no explicit `refl::init<Args...>` was registered. This eliminates manual constructor boilerplate for reflected types while preserving opt-out via `refl::init(false)`.

## Context

Before commit `6b39efb` (#482), every reflected type that wanted a Python-accessible constructor had to explicitly register one via `refl::init<Args...>()`. Types without an explicit init would either get no constructor (causing `RuntimeError` in Python) or rely on `MakeObjectFromPackedArgs` (which requires packed key-value arguments, not positional).

This was error-prone: developers would register fields but forget the init, and users would get confusing runtime errors. It was also boilerplate-heavy: the init signature had to mirror the field types exactly.

Usecases:
- `@c_class`-decorated Python types need constructors without C++ boilerplate
- Field-based construction matching Python `dataclasses` conventions (positional args, keyword-only, defaults)
- KWARGS calling convention for Python `**kwargs` support in constructors

Design Decisions:
- **Auto-generate in `ObjectDef` destructor**: The destructor runs after all `def_ro`/`def_rw`/`def` calls, so all field metadata is available. If no `refl::init<Args...>` was registered (`has_explicit_init_ == false`) and the type has a creator, the destructor calls `RegisterAutoInit(type_index_)`. This is a zero-boilerplate default.
- **Opt-out via `refl::init(false)`**: Passed to `ObjectDef` constructor or as a field trait. At class level, it sets `has_explicit_init_ = true`, suppressing auto-init. At field level, it sets `kTVMFFIFieldFlagBitMaskInitOff`, excluding the field from the auto-generated init. Types with non-standard construction (e.g., AccessStepObj, AccessPathObj) use `ObjectDef<T>(refl::init(false))`.
- **KWARGS sentinel object**: The auto-generated init supports both positional-only and KWARGS calling conventions. A singleton `ffi.GetKwargsObject()` acts as a sentinel marker in the packed argument list. Arguments before the sentinel are positional; key-value pairs after are keyword arguments.
- **Separate `init.h` header**: `MakeInit` and `RegisterAutoInit` live in `include/tvm/ffi/reflection/init.h`, keeping `registry.h` focused on registration primitives. `registry.h` includes `init.h`.
- **Positional ordering**: Required (non-default) positional fields come before optional (defaulted) positional fields, matching Python signature conventions. This is achieved via `std::stable_partition` on `pos_indices`.
- **`init<>` zero-argument specialization**: Doubles as both a zero-arg constructor registration and an `InfoTrait` for init control. CTAD deduction guide `init(bool) -> init<>` enables `refl::init(false)` without explicit template arguments.
- **`kw_only` trait**: `refl::kw_only(true)` sets `kTVMFFIFieldFlagBitMaskKwOnly`, making a field keyword-only in the auto-generated init. Such fields are excluded from positional indices.
- **Lowercase trait aliases**: `default_value`, `default_factory` (aliases for `DefaultValue`, `DefaultFactory`) provide a consistent lowercase API alongside `repr`, `compare`, `hash`, `kw_only`, `init`.

## Implementation Notes

- `MakeInit(type_index)` pre-computes an `AutoInitInfo` struct: all fields, init indices, positional indices (partitioned required-first), name-to-index map. The returned `Function` is a closure over this shared info.
- The KWARGS sentinel is resolved eagerly via `Function::GetGlobalRequired("ffi.GetKwargsObject")()` during `MakeInit`, not at call time. The sentinel is compared by object identity (`same_as`).
- Field binding in KWARGS mode: positional args fill `pos_indices` left-to-right up to the sentinel position, then key-value pairs are matched by name. Duplicate argument detection is via `field_set` vector. Missing required fields throw `TypeError`.
- `RegisterAutoInit` wraps `MakeInit` and registers the result as `__ffi_init__` with `auto_init:true` in JSON metadata.
- New C ABI field flags: `kTVMFFIFieldFlagBitMaskInitOff` (bit 9) and `kTVMFFIFieldFlagBitMaskKwOnly` (bit 10).
- `ObjectDef` destructor is `noexcept(false)` to allow `RegisterAutoInit` to throw on error (e.g., missing creator).
- Evidence: `.knowledge/commits/2026-02-27-6b39efbf381e48a8a42ab3779bc2adf587458fb3.md` + `6b39efb`

## Related Design Docs

- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- Reflection system where ObjectDef, init, and field metadata live
- [`.knowledge/designs/0027-dataclass-operations.md`](../designs/0027-dataclass-operations.md) -- Dataclass operations that depend on reflected types having init
- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Python `@c_class` that consumes `__ffi_init__`
