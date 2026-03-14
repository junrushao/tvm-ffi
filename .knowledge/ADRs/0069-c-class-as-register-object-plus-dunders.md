---
scope:
  - "0014-python-bindings"
  - "0027-dataclass-operations"
---
# `@c_class` Reimplemented as `register_object` + Structural Dunders

**TL;DR**: The `@c_class` decorator is reimplemented from a thin `register_object` pass-through into a two-phase decorator that first registers the FFI type, then installs structural dunder methods (`__init__`, `__repr__`, `__eq__`/`__ne__`, `__hash__`, `__lt__`/`__le__`/`__gt__`/`__ge__`) derived from C++ recursive operations.

## Context

Before commit `e5f3af7` (#488), `@c_class` was a thin wrapper around `@register_object` that accepted and ignored keyword arguments for forward compatibility (simplified from a full dataclass-style decorator in commit `b97ff1a` #478). Users who wanted structural comparison, hashing, or ordering on FFI objects had to manually define dunders or use the internal `_ffi_api.RecursiveEq` etc. directly.

The C++ side already provided all the necessary operations -- `RecursiveEq`, `RecursiveHash`, `RecursiveLt/Le/Gt/Ge`, `RecursiveCompare` -- via the `ObjectGraphDFS` CRTP engine in `dataclass.cc`. The Python side had newly exposed these via `_ffi_api` typed stubs (commits `b87196f`, `5796ff4`). The `__ffi_init__` -> Python `__init__` wiring was also in place (commit `b1abaea`). What was missing was a clean decorator API to install all these dunders consistently.

## Decision

Reimplement `@c_class` as a two-phase decorator:

1. **Phase 1**: Call `register_object(type_key)(cls)` to perform FFI type registration (type index lookup, reflection metadata attachment, field/method properties).
2. **Phase 2**: Call `_install_dataclass_dunders(cls, init=..., repr=..., eq=..., order=..., unsafe_hash=...)` to install structural dunders.

Each dunder delegates to the corresponding C++ recursive operation via `_ffi_api`. User-defined dunders in `cls.__dict__` are never overwritten.

The decorator signature follows Python's `dataclasses.dataclass` conventions:

```python
@c_class(
    type_key: str,
    *,
    init: bool = True,        # synthesize __init__ from C++ reflection
    repr: bool = True,        # __repr__ via C++ ReprPrint
    eq: bool = False,         # __eq__/__ne__ via RecursiveEq
    order: bool = False,      # __lt__/__le__/__gt__/__ge__ via RecursiveLt/Le/Gt/Ge
    unsafe_hash: bool = False # __hash__ via RecursiveHash
)
```

The `eq`, `order`, and `unsafe_hash` parameters default to `False` for backward compatibility. `init` and `repr` default to `True` since these are non-breaking (init was already auto-installed, repr was already delegated to C++).

## Alternatives Considered

### Alternative 1: Full Python dataclass integration

Make `@c_class` actually generate a Python `dataclasses.dataclass`-compatible class, using `dataclasses.field()` for each reflected field.

- Pros: Full interop with Python dataclass ecosystem (e.g., `dataclasses.asdict`, `dataclasses.fields`).
- Cons: Fundamental mismatch -- FFI objects are C++ heap-allocated with ref-counting, not Python-native data holders. The `dataclass` protocol assumes direct field access via `__dict__` or `__slots__`, but FFI fields go through C function pointer getters/setters. The impedance mismatch would require extensive adapter code.

### Alternative 2: Single combined decorator (no separate register_object)

Merge registration and dunder installation into a single monolithic decorator, eliminating the two-phase approach.

- Pros: Simpler implementation, no need for the `register_object` + `_install_dataclass_dunders` split.
- Cons: `@register_object` remains useful on its own for types that do not want the dataclass-style dunders (e.g., built-in container types like `Array`, `Map` which have their own protocol implementations). The split keeps the two concerns orthogonal.

### Alternative 3: Install dunders in `register_object` always

Have `@register_object` always install structural dunders (making `@c_class` unnecessary).

- Pros: All registered objects get consistent dunder behavior.
- Cons: Breaking change -- existing `@register_object` classes may have incompatible `__eq__`/`__hash__` behavior. Container types (`Array`, `Map`, `Dict`) implement their own protocols. The opt-in approach via `@c_class` is safer and more explicit.

## Consequences

- **`@c_class` is now the recommended decorator** for user-facing reflected types. `@register_object` remains for lower-level registration without structural dunders.
- **`__init__` is no longer auto-installed by `@register_object`**: The `_install_init` call was moved from `_add_class_attrs` (called by `register_object`) to `_install_dataclass_dunders` (called by `c_class`). Bare `@register_object` classes must either switch to `@c_class` or define their own `__init__`.
- **All `tvm_ffi.testing` classes migrated** from `@register_object` to `@c_class`, serving as reference examples.
- **`@dataclass_transform`** enables IDE support: pyright and mypy understand `@c_class`-decorated classes and can infer `__init__` signatures from field annotations.
- **NotImplemented return**: All installed `__eq__`/`__ne__`/ordering dunders return `NotImplemented` (not `False` or `TypeError`) for unrelated types, following Python data model conventions. This allows Python's comparison fallback chain to work correctly.

## Implementation Notes

- `_is_comparable(self, other)` checks `isinstance(other, type(self)) or isinstance(self, type(other))` -- bidirectional check for subclass compatibility. Returns `True` if either is a subclass of the other.
- `_install_dataclass_dunders` closes over `_ffi_api.RecursiveEq`, `_ffi_api.RecursiveHash`, etc. at install time (not call time), avoiding repeated module lookups.
- The `unsafe_hash` name (matching `dataclasses.dataclass`) signals that hashing mutable objects is caller's responsibility -- mutating an object while it is a dict key or set member breaks invariants.
- Evidence: `.knowledge/commits/2026-02-28-e5f3af7bb83e6461c45d08117e4eaabe51add3b1.md` + `e5f3af7`

## Related Design Docs

- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Python bindings where `@c_class` lives
- [`.knowledge/designs/0027-dataclass-operations.md`](../designs/0027-dataclass-operations.md) -- C++ recursive operations consumed by the dunders
- [`.knowledge/ADRs/0068-auto-init-from-reflection.md`](0068-auto-init-from-reflection.md) -- `__ffi_init__` auto-generation that `_install_init` consumes
