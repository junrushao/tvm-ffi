# ADR 018: __slots__ Enforcement on FFI Object Subclasses

- Status: Accepted
- Date: 2026-02-21
- Owners: Junru Shao

## Context

Python FFI objects (subclasses of `tvm_ffi.Object`) are backed by C++ structs.
Field access is mediated by Cython-generated getters/setters that read/write
the underlying C++ memory. However, Python allows arbitrary attribute
assignment on any object that has a `__dict__`:

```python
obj = SomeCppBackedObject()
obj.my_custom_attr = 42  # Stored in Python __dict__, invisible to C++
```

These Python-only attributes are invisible to C++ field accessors, serialization,
structural equality, and `repr`. This is a footgun: users expect that setting
an attribute on an FFI object modifies the underlying C++ data, but instead it
silently creates a Python-side shadow attribute.

## Decision

Enforce `__slots__ = ()` on all Cython-defined FFI object subclasses by
default. This prevents Python-side `__dict__` creation and makes arbitrary
attribute assignment raise `AttributeError`.

The enforcement applies to: `Object`, `Function`, `Tensor`, `Device`, `DType`,
`Module`, `Error`, and all derived types defined in Cython `.pxi` files.

Python-side subclasses (e.g., `@c_class` decorated classes) that need Python
attributes can opt in by explicitly declaring `__slots__` with the desired
attribute names.

## Consequences

- Positive: Eliminates silent Python-side shadow attributes on C++-backed
  objects. Reduces memory usage (no per-instance `__dict__`). Makes attribute
  errors explicit and immediate.
- Negative: Any existing code that sets arbitrary Python attributes on FFI
  objects (e.g., `obj.tag = "debug"`) will now raise `AttributeError`. This is
  a behavioral breaking change.
- Migration/Rollout: Remove or replace `obj.custom_attr = value` patterns with
  either C++ field registration or a separate Python wrapper object. The change
  was applied in a single commit across all Cython `.pxi` files.

## References
- Range summary: `.repo-knowledge/ranges/2026-02-21-B1611E0-ECC7471.md`
- Evidence commits: `83daf69`
- External references: Python data model documentation on `__slots__`

## Related Design Docs
- `.repo-knowledge/design/004-reflection-system.md`

## Notes
- Sphinx autodoc configuration was updated to handle slotted classes
  (`docs/conf.py`, `83daf69`).
- The `Function.__init__` constructor (`ecc7471`) was added in the same
  batch, providing a clean way to create `Function` objects from Python
  callables without relying on arbitrary attribute assignment.
