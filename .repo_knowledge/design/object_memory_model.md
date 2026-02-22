# Object System & Memory Model

> Range: `8b46833..ecc7471` (2025-12-12 to 2026-02-21, 100 commits)

## Overview

The Python-side object system was significantly hardened in this range. Key
changes enforce `__slots__=()` on all `tvm_ffi.Object` subclasses (preventing
accidental instance dict creation), add copy/deepcopy/replace semantics via
C++ graph-based deep copy, and introduce a `Function.__init__` constructor.

## Timeline

| Date | SHA | Change |
|------|-----|--------|
| 2026-01-05 | `46ab644` | Add `__bool__` support for Array and Map |
| 2026-02-13 | `c73d61a` | Add `__copy__`, `__deepcopy__`, `__replace__` (#438) |
| 2026-02-15 | `39d9b2b` | Enable customized AnyHash/Equal in Object (#451) |
| 2026-02-15 | `86c4042` | Rename to `ffi.GetInvalidObject`, MISSING singleton (#447) |
| 2026-02-21 | `83daf69` | Enforce `__slots__=()` via CObject/Object split (#27) |
| 2026-02-21 | `ecc7471` | Add `tvm_ffi.Function.__init__` (#28) |

## Key Changes

### 1. `__slots__` Enforcement (`83daf69`)

**Problem**: Python subclasses of `tvm_ffi.Object` could create instance
`__dict__` dictionaries, wasting memory and causing confusion where Python-side
attributes silently diverge from C++-side fields.

**Solution**: Split the Cython `Object` class into:
- `CObject` — internal base holding `chandle` and ref-counting logic
- `Object(CObject)` — public class that enforces `__slots__=()` via
  `_ObjectSlotsMeta` metaclass

All Cython extension types (`ByteArrayArg`, `Device`, `DataType`, `Error`,
`Function`, `Tensor`, `String`, etc.) now declare `__slots__ = ()`.

**Migration**: Downstream subclasses of `tvm_ffi.Object` must add
`__slots__ = ()`.

### 2. Copy / Deep Copy / Replace (`c73d61a`)

**Implementation**: New C++ graph-based deep copy
(`src/ffi/extra/deep_copy.cc`) with DAG memoization and cycle detection.

Python objects gain:
- `__copy__` — returns the same reference (objects are ref-counted)
- `__deepcopy__` — delegates to C++ `ffi.DeepCopy`, which traverses the
  object graph and deep-copies all reachable objects
- `__replace__` — dataclass-style replacement: deep-copies, then sets
  specified fields on the copy

The `__replace__` method enables `copy.replace(obj, field=value)` (PEP 707)
for all `@c_class` dataclasses.

### 3. Custom Hash/Equal (`39d9b2b`)

New type attribute columns `__any_hash__` and `__any_equal__` allow object
types to register custom hash and equality functions. This enables types like
`StructuralKey` (see `6adc8df`) to participate in container key lookups with
custom semantics.

### 4. Function Constructor (`ecc7471`)

`tvm_ffi.Function` now accepts a positional `func` argument:
```python
f = tvm_ffi.Function(my_callable)  # wraps Python callable
g = tvm_ffi.Function(existing_func)  # ref-count increment
```

Three code paths in `__init__`:
1. If `func` is a `Function` — increments ref count (with NULL guard)
2. If `func` is callable — delegates to `_convert_to_ffi_func_handle`
3. Otherwise — raises `TypeError`

## Architecture: CObject / Object Split

```
CObject (Cython extension type)
  ├── chandle: TVMFFIObjectHandle
  ├── __move_handle_from__()
  ├── __init_handle_by_constructor__()
  ├── same_as()
  └── __dealloc__() → TVMFFIObjectDecRef
       │
       └── Object (enforces __slots__)
            ├── __init_subclass__() — validates __slots__
            ├── __copy__()
            ├── __deepcopy__()
            └── __replace__()
                 │
                 ├── Function(Object) — __slots__=(), __init__(func)
                 ├── Tensor(Object) — __slots__=()
                 ├── Error(Object) — __slots__=()
                 └── ... all other types
```

## Design Decisions

1. **Shallow copy = identity**: `copy.copy(obj)` returns the same ref-counted
   handle. This is correct because FFI objects are heap-allocated and
   ref-counted; shallow copy would be misleading if it created a new Python
   wrapper without a new C++ object. (`c73d61a`)

2. **Deep copy traverses the full C++ graph**: Implemented in C++ (not Python)
   to correctly handle cycles, DAGs, and cross-language references. Uses a
   visited-object map keyed by `Object*`. (`c73d61a`)

3. **`__slots__` enforcement at subclass time**: Using `_ObjectSlotsMeta`
   metaclass to validate `__slots__` at class creation time, ensuring
   compatibility with Cython extension types. (`83daf69`)
