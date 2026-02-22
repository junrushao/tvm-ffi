# Reflection System Extensions

> Range: `8b46833..ecc7471` (2025-12-12 to 2026-02-21, 100 commits)

## Overview

The reflection system (used by `ObjectDef<T>` in C++ and `@c_class` in Python)
gained several extensions: function overloading, default factories for mutable
defaults, `kw_only` init parameters, unified repr printing, and `__repr__`
code generation for dataclasses.

## Timeline

| Date | SHA | Change |
|------|-----|--------|
| 2025-12-23 | `84c5bdb` | Dynamic-style overload for FFI object types (#286) |
| 2026-01-10 | `38914fa` | Fix TypeStr for Any type in reflection Init (#393) |
| 2026-01-18 | `360648f` | Add `__repr__` generation for `@c_class` (#411) |
| 2026-01-18 | `3a5bf5e` | Add `kw_only` support for dataclass init (#384) |
| 2026-02-14 | `5e564cd` | Add `DefaultFactory` for field reflection (#446) |
| 2026-02-17 | `3b26a09` | Document `field_static_type_index` + tests (#456) |
| 2026-02-18 | `b648c5d` | DFS-based `ffi.ReprPrint` for unified repr (#454) |

## Key Changes

### 1. Function Overloading (`84c5bdb`)

New `include/tvm/ffi/reflection/overload.h` (504 lines) provides a
`Function::OverloadedWith(Callable)` API for dynamic dispatch on FFI object
methods. `FunctionObjImpl` gained a generalized constructor and
`Function::FromPackedInplace` for efficient construction.

This enables defining multiple implementations for the same method name,
dispatched by argument types at runtime.

### 2. Default Factories (`5e564cd`)

New `DefaultFactory` trait for field reflection allows mutable default values
via callable factories:

```cpp
builder.def_field("items", &Obj::items)
       .set_default_factory([]() { return List<int>(); });
```

The C API gained `kTVMFFIObjectDefField_HasDefaultFactory` flag bit and
`SetFieldToDefault` helper. In Python, `@c_class` fields support
`default_factory=lambda: []` similarly to Python's `dataclasses.field()`.

### 3. `kw_only` Init Parameters (`3a5bf5e`)

Fields can be marked as keyword-only in `@c_class` init generation:

```python
@c_class("my.Type")
class MyType(Object):
    required: int
    optional: str = c_class.field(default="hello", kw_only=True)
```

This generates `__init__(self, required: int, *, optional: str = "hello")`.

### 4. Unified ReprPrint (`b648c5d`)

New C++ `ffi.ReprPrint` function (`src/ffi/extra/repr_print.cc`, 401 lines)
provides a DFS-based repr with:
- DAG memoization (shared objects printed once, then referenced by ID)
- Cycle detection
- Configurable `Repr` InfoTrait per object type
- Replaces previous per-type Python-side `exec`-based repr generation

### 5. `__repr__` Code Generation (`360648f`)

The `@c_class` decorator can now generate `__repr__` methods automatically for
Python dataclasses, printing field names and values in a structured format.

## Architecture

```
Reflection System
├── ObjectDef<T> builder (C++)
│   ├── def_field() / def_method()
│   ├── set_default() / set_default_factory()  ← NEW (5e564cd)
│   └── set_kw_only()                          ← NEW (3a5bf5e)
│
├── @c_class decorator (Python)
│   ├── __init__ generation (with kw_only)     ← NEW (3a5bf5e)
│   ├── __repr__ generation                    ← NEW (360648f)
│   └── default_factory support                ← NEW (5e564cd)
│
├── Function overloading (C++)
│   └── overload.h: OverloadedWith()           ← NEW (84c5bdb)
│
└── Repr system
    └── ffi.ReprPrint (DFS, DAG, cycles)       ← NEW (b648c5d)
```

## Design Decisions

1. **DFS repr over recursive Python**: C++ DFS traversal handles cycles
   correctly and is much faster than Python-side `exec`-based generation.
   The `Repr` InfoTrait allows per-type customization. (`b648c5d`)

2. **Factory pattern for mutable defaults**: Following Python's
   `dataclasses.field(default_factory=...)` pattern avoids the mutable default
   pitfall. The factory is called each time a new instance is created.
   (`5e564cd`)

3. **Overload dispatch at call time**: Rather than compile-time overload
   resolution, the overload system dispatches at call time based on packed
   argument types. This matches the type-erased nature of the FFI. (`84c5bdb`)
