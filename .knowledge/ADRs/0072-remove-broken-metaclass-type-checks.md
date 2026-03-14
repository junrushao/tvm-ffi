---
scope:
  - "0014-python-bindings"
---
# Remove Broken `_ObjectSlotsMeta.__instancecheck__`/`__subclasscheck__`

**TL;DR**: The `__instancecheck__` and `__subclasscheck__` overrides on `_ObjectSlotsMeta` were removed because they unconditionally returned `True` for any `CObject` instance/subclass regardless of which class was being checked, causing incorrect cross-hierarchy type checks (e.g., `isinstance(Map(...), Array)` returning `True`).

## Context

When `_ObjectSlotsMeta` was introduced (commit `49a5d71` #480, [ADR 0066](0066-slots-enforcement-via-metaclass.md)), it included `__instancecheck__` and `__subclasscheck__` overrides that checked `isinstance(instance, CObject)` / `issubclass(subclass, CObject)` before delegating to `ABCMeta`. The intent was to ensure `isinstance(x, Object)` returned `True` for `CObject` instances that were not created through the metaclass.

However, the implementation was overly broad: these metaclass methods are called with `cls` as the class being checked against (e.g., `isinstance(x, Array)` calls `Array.__instancecheck__(x)`), but the overrides ignored `cls` entirely. Any `CObject` instance passed the check against any `_ObjectSlotsMeta`-controlled class, producing wrong results:

```python
isinstance(Map(), Array)    # True (wrong)
isinstance(String(), Error) # True (wrong)
issubclass(Map, Array)      # True (wrong)
```

Usecases:
- Type guards in user code: `if isinstance(obj, Array):` would incorrectly match `Map` objects
- Generic dispatch logic relying on `isinstance` for FFI container type discrimination

Design Decisions:
- **Remove the overrides entirely**: All objects returned from C++ are always constructed as proper `Object` subclasses (via `make_ret_object` which creates instances of the registered Python class). Standard Python MRO-based `isinstance`/`issubclass` checks work correctly for all FFI objects because the class hierarchy mirrors the C++ type hierarchy.
- **No replacement logic needed**: The original concern (that `CObject` instances might not pass `isinstance(x, Object)`) is moot because `Object` inherits from `CObject`, so `CObject` instances are always `Object` instances by standard MRO.
- **Regression tests added**: 22 new tests in `TestIsinstanceIssubclass` cover containers (Array, List, Map, Dict), inheritance hierarchies, and cross-hierarchy checks.

## Implementation Notes

- Removed `__instancecheck__` and `__subclasscheck__` from `_ObjectSlotsMeta` in `object.pxi` (13 lines deleted).
- Updated `test_dataclass_init.py` to assert correct behavior (parent instance is not an instance of child class).
- Added 22 new regression tests verifying isinstance/issubclass correctness.
- The `_ObjectSlotsMeta.__new__` (slots injection) and `__init__` methods are preserved -- only the type-check overrides were broken.
- Evidence: `.knowledge/commits/2026-03-06-721d87816152e4a1cdc5c7906b116d46007699f8.md` + `721d878`

## Related Design Docs

- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Python bindings where `_ObjectSlotsMeta` resides
- [`.knowledge/ADRs/0066-slots-enforcement-via-metaclass.md`](0066-slots-enforcement-via-metaclass.md) -- Original decision to introduce `_ObjectSlotsMeta`
