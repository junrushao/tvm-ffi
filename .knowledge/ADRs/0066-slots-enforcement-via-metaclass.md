---
scope:
  - "0014-python-bindings"
  - "0003-object-system"
---
# Enforce `__slots__=()` for Object Subclasses via `_ObjectSlotsMeta`

**TL;DR**: All Python `Object` subclasses now enforce `__slots__ = ()` by default through a metaclass (`_ObjectSlotsMeta`), preventing accidental per-instance `__dict__` creation. The Cython `Object` class is split into `CObject` (extension type) + `Object` (Python class with metaclass).

## Context

FFI `Object` instances are lightweight handles wrapping a single `void*` pointer to a C++ runtime object. In standard Python, classes without `__slots__` automatically get a per-instance `__dict__` (56+ bytes on CPython), which:
- Wastes memory on objects that should be purely handle-based
- Allows accidental attribute creation (e.g., `obj.typo = 42`) that shadows reflected properties or silently stores state Python-side when it should be on the C++ side
- Creates confusion between Python-side attributes and C++ reflected fields

Several existing subclasses (e.g., `Function`, `Error`, `Tensor`) already declared `__slots__ = ()` individually, but the enforcement was inconsistent -- forgetting `__slots__` in a new subclass silently re-enabled `__dict__`.

Usecases:
- A user creates a custom `Object` subclass for testing and accidentally stores state in Python attributes that is invisible to C++ serialization/copy.
- Container types (`Array`, `Map`) hold many `Object` instances; per-instance `__dict__` overhead is multiplied.
- `Module.__getattr__` needs to cache looked-up functions; it explicitly opts into `__dict__` via `__slots__ = ("__dict__",)`.

Design Decisions:
- **Split `Object` into `CObject` (Cython `cdef class`) + `Object` (Python class with metaclass).** The `cdef class` cannot have a metaclass in Cython, so the split is architecturally necessary. `CObject` owns the `chandle` and ref-counting; `Object` inherits from `CObject` and uses `_ObjectSlotsMeta`.
- **`_ObjectSlotsMeta` extends `ABCMeta`** (not `type`) to support abstract method registration in Object subclasses. It auto-injects `__slots__ = ()` into any subclass that does not explicitly declare `__slots__`.
- **Override `__instancecheck__` and `__subclasscheck__`** on the metaclass so that `isinstance(x, Object)` returns `True` for `CObject` instances (which are not created through the metaclass). This maintains backward compatibility for code that checks `isinstance(x, Object)`. **Update (commit `721d878` #498)**: These overrides were removed because they were overly broad -- they unconditionally returned `True` for any `CObject` instance regardless of the target class, causing `isinstance(Map(), Array)` to incorrectly return `True`. Standard MRO-based checks work correctly because all FFI objects are proper `Object` subclasses. See [ADR 0072](0072-remove-broken-metaclass-type-checks.md).
- **Subclasses that need `__dict__` opt in explicitly** with `__slots__ = ("__dict__",)`. This is a clear, auditable signal that the class intentionally needs per-instance dynamic attributes.

### Alternatives Considered

**Alternative A: Per-class `__slots__ = ()` convention (status quo)**
- Pros: No metaclass overhead. No Cython refactoring.
- Cons: Enforcement by convention is unreliable. Every new subclass author must remember to add `__slots__`. Forgetting it silently adds 56+ bytes per instance and enables accidental attributes.

**Alternative B: `__init_subclass__` hook instead of metaclass**
- Pros: Lighter-weight than a metaclass. No `ABCMeta` dependency.
- Cons: `__init_subclass__` runs after class creation, so `__slots__` would already be computed by the time the hook fires. Cannot inject `__slots__` retroactively without recreating the class.

**Alternative C: Use `__slots__` keyword in `class` statement (Python 3.13+ `type.__new__` `__slots__` kwarg)**
- Pros: Clean syntax. No metaclass needed.
- Cons: Requires Python 3.13+. The project targets Python 3.9+.

### Consequences

- **Breaking change**: All `Object` subclasses that set arbitrary instance attributes will raise `AttributeError`. Migration: declare `__slots__ = ("__dict__",)` or use reflected properties.
- **Memory savings**: Each `Object` instance saves 56+ bytes (the cost of an empty `__dict__`).
- **Repr change**: `object_repr()` now uses a local `from tvm_ffi._ffi_api import ReprPrint` instead of a module-level `_REPR_PRINT` cache (the module-level cache was on an attribute of `Object`, which is now slots-enforced).
- **`Module` caching**: `Module.__getattr__` stores looked-up functions via `setattr(self, name, func)` into its explicit `__dict__` slot, eliminating the need for a separate caching dict.

## Implementation Notes

- `object.pxi`: `CObject` is the new `cdef class` (was `Object`). `Object` is now a pure-Python class inheriting from `CObject` with `metaclass=_ObjectSlotsMeta`.
- `_ObjectSlotsMeta.__new__`: If `__slots__` not in `ns`, injects `ns["__slots__"] = ()`.
- `_ObjectSlotsMeta.__instancecheck__`/`__subclasscheck__`: **Removed** in commit `721d878` (#498). The original implementation checked `isinstance(instance, CObject)` / `issubclass(subclass, CObject)` first, but this was overly broad. See [ADR 0072](0072-remove-broken-metaclass-type-checks.md).
- `function.pxi`, `error.pxi`, `tensor.pxi`, `string.pxi`, `dtype.pxi`: Updated to reference `CObject` instead of `Object` for Cython-level operations.
- `module.py`: `Module` declares `__slots__ = ("__dict__",)` for function caching.
- `container.py`: Removed redundant `__slots__ = ()` declarations (now auto-injected by metaclass).
- `device.pxi`: `kDLMAIA = 17` added, `kDLTrn` renumbered from 17 to 18.

## Related Design Docs

- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Python bindings where the Object hierarchy resides
- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- Object system that Python Object wraps
- Evidence: `.knowledge/commits/2026-02-27-49a5d71a3145aee20b6cfbcb7a2f7d9feb25f2f7.md` + `49a5d71`
