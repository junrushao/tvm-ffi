# ADR-002: Enforce `__slots__=()` on Object Subclasses

- **Status**: Accepted
- **Date**: 2026-02-21
- **Commits**: `83daf69`

## Context

TVM-FFI objects store their state in C++ heap-allocated objects, accessed
through a `chandle` (C pointer). Python subclasses of `tvm_ffi.Object` were
free to create instance dictionaries, leading to:

1. **Memory waste**: Each Python instance would allocate an unnecessary
   `__dict__` dictionary.
2. **Confusing behavior**: Python-side attributes would silently diverge from
   C++-side fields, since assignments to `obj.field` would go to the Python
   dict rather than the C++ object.

## Decision

Split the Cython `Object` class into:
- `CObject` — internal base with `chandle`, ref-counting, and handle
  manipulation methods.
- `Object(CObject)` — public class that enforces `__slots__ = ()` via
  `__init_subclass__`.

All Cython extension types declare `__slots__ = ()`. Any pure-Python subclass
of `tvm_ffi.Object` that does not declare `__slots__ = ()` will raise an error
at class definition time.

## Consequences

- **Positive**: Consistent memory model; no silent attribute divergence;
  reduced per-instance memory overhead.
- **Negative**: Breaking change for any downstream code that subclasses
  `tvm_ffi.Object` without `__slots__`.
- **Migration**: Downstream subclasses must add `__slots__ = ()`.

## Alternatives Considered

1. **Metaclass-based enforcement**: Rejected — not compatible with Cython
   extension types.
2. **Runtime warning instead of error**: Rejected — a warning would be too
   easy to ignore, and the consequences of instance dicts are subtle.
3. **Do nothing**: Rejected — the memory waste and attribute divergence
   are real problems observed in practice.
