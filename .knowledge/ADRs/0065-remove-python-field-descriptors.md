---
scope:
  - "0006-reflection"
  - "0014-python-bindings"
---
# Remove Python-Side Field Descriptor Infrastructure

**TL;DR**: The Python-side `field()`, `Field`, `KW_ONLY`, and exec-based `__init__` codegen in `tvm_ffi.dataclasses` were removed. The `c_class` decorator is now a thin pass-through to `register_object`, relying entirely on C++ reflection for field metadata and constructor generation.

## Context

The `c_class` decorator (introduced for dataclass-style Python authoring of C++ FFI-backed types) maintained a parallel Python-side field descriptor system that duplicated metadata already available through C++ reflection:

- `field.py` (169 lines): `Field` class, `KW_ONLY` sentinel, `default_factory` wiring, `_FieldValue` TypeVar
- `_utils.py` (210 lines): `type_info_to_cls`, `fill_dataclass_field`, `method_init` (exec-based code generation producing Python functions with explicit parameters)
- `c_class.py` (190 lines): `_inspect_c_class_fields` matching Python annotations against C++ fields, `kw_only` resolution order, `KW_ONLY` sentinel detection

This duplication created several problems:

Usecases:
- A user changes a C++ field default and expects the Python side to reflect it automatically -- the parallel Python descriptor could diverge.
- A derived class inherits from a base that uses `c_class` -- the exec-based `__init__` could inherit the base's constructor with the wrong field count.
- Python-side `field(kw_only=...)` and `KW_ONLY` sentinel add complexity that C++ already handles via `kTVMFFIFieldFlagBitMaskKwOnly`.

Design Decisions:
- **Remove all Python-side field descriptor infrastructure.** Delete `_utils.py` and `field.py` entirely. Reduce `c_class.py` from 190 lines to 36 lines, making it a one-line delegation to `register_object`.
- **Fix `_add_class_attrs` to always override `__c_ffi_init__` per type.** This prevents a derived class from inheriting a base class constructor with the wrong field count, resolving a latent bug where the Python init for a child class could call the parent's constructor.
- **Remove the `init`, `kw_only`, and `repr` parameters from `c_class()`**, since all these behaviors are now controlled by C++ reflection flags (`kTVMFFIFieldFlagBitMaskKwOnly`, `kTVMFFIFieldFlagBitMaskInitOff`, `kTVMFFIFieldFlagBitMaskReprOff`).

### Alternatives Considered

**Alternative A: Keep Python field descriptors for backward compatibility**
- Pros: No breaking change for existing `field()` users.
- Cons: Perpetuates duplication between Python and C++ metadata. The C++ reflection system now provides `DefaultFactory`, `kw_only`, `init(false)`, and `Repr(false)` -- every feature the Python side duplicated.

**Alternative B: Merge Python descriptors into C++ reflection**
- Pros: Single source of truth from the start.
- Cons: Already achieved by the C++ reflection system; the Python side was the duplicate.

### Consequences

- **Breaking change**: `field()`, `Field`, `KW_ONLY`, and `MISSING` are no longer exported from `tvm_ffi.dataclasses`. Code using `from tvm_ffi.dataclasses import field` must be updated.
- **Breaking change**: `c_class`-decorated classes must now explicitly inherit from `Object` (previously `type_info_to_cls` injected it).
- **Breaking change**: `__init__` on decorated types uses the C++ FFI constructor directly (positional args in field order) instead of the Python codegen'd init with keyword-only and default factory support.
- **Simplification**: 550+ lines of Python code removed. The `c_class` -> `register_object` path is now trivially auditable.
- **Rollback**: Re-introduce `_utils.py` and `field.py` if downstream packages rely on `field()` API. The C++ reflection flags provide a superset of the removed functionality.

## Implementation Notes

- `c_class.py`: Reduced to a 36-line module that delegates `c_class(type_key)` -> `register_object(type_key)`.
- `registry.py`: `_add_class_attrs` now always overrides `__c_ffi_init__` (matching the existing `__ffi_shallow_copy__` override pattern).
- `test_dataclasses_c_class.py`: Deleted (151 lines, tested removed infrastructure).
- `test_repr.py`: Updated to use positional args for derived constructors.

## Related Design Docs

- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- Reflection system that now solely owns field metadata
- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Python bindings where `c_class` and `_add_class_attrs` reside
- Evidence: `.knowledge/commits/2026-02-27-b97ff1ae2abd21f5b8a368d5e04f34b53e3985bf.md` + `b97ff1a`
