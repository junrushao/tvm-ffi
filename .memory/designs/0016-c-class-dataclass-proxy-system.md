---
design: "0016"
title: "c_class Dataclass Proxy System: Python-side TypeInfo and @c_class Decorator"
status: "active"
owners:
  - "Junru Shao"
created: "2025-09-19"
last_updated: "2025-09-25"
scope:
  - "python/tvm_ffi/dataclasses"
  - "python/tvm_ffi/cython/type_info.pxi"
  - "python/tvm_ffi/cython/object.pxi"
  - "python/tvm_ffi/registry.py"
  - "include/tvm/ffi/reflection/registry.h"
source_commits:
  - "53b2e00ef90a34f2dfa79014877dc6ca53e78c0f"
  - "c01dadf31a66e74cdbfd7fdb1ffc81a75007965f"
  - "e98b94e118dfa5ac4bcf3764a8b1695afee3d596"
  - "035975a7e6804d1d23b07942d7704c30b3fadda0"
  - "daeb235a29c576d8702d447fa5f4773170bb1e8f"
  - "b5dd851f7019f4f63a19d9dce074ba62706f16e7"
  - "d68c8d8d4520318d3598c39c71c444169b1244bc"
  - "8e471b01c8617e21404d8f6aaf80b57dd190f10f"
source_ledgers:
  - ".memory/commits/2025-09-19-53b2e00e.md"
  - ".memory/commits/2025-09-21-c01dadf3.md"
  - ".memory/commits/2025-09-21-e98b94e.md"
  - ".memory/commits/2025-09-23-035975a.md"
  - ".memory/commits/2025-09-24-daeb235.md"
  - ".memory/commits/2025-09-22-b5dd851.md"
  - ".memory/commits/2025-09-22-d68c8d8.md"
  - ".memory/commits/2025-09-25-8e471b0.md"
---

# c_class Dataclass Proxy System: Python-side TypeInfo and @c_class Decorator

## TL;DR
- The `@c_class` decorator provides a Python dataclass-like syntax for defining proxy classes that are backed by C++ FFI objects, automatically generating `__init__`, property accessors, and method bindings from C++ reflection metadata.
- A new Python-side `TypeInfo`/`TypeField`/`TypeMethod` metadata layer (implemented in Cython) bridges the gap between the C ABI `TVMFFITypeInfo` structs and pure Python, enabling reflection queries, class construction, and attribute binding without manual glue code.
- The `reflection::init<T, Args...>` C++ helper simplifies registration of `__init__` methods in `ObjectDef<T>`, and a `TYPE_INDEX_TO_CLS` fast-path cache eliminates one level of indirection on the critical FFI return path.

## Problem Statement
Exposing C++ objects to Python requires property accessors for each reflected field, an `__init__` that forwards to the C++ constructor, and method bindings that dispatch to the FFI. Before this system, each Python class required hand-written boilerplate: property definitions calling Cython getters/setters, manual `__init__` delegation, and explicit method wrappers. The C ABI `TVMFFITypeInfo` metadata was not directly accessible from pure Python, so adding a new reflected class required touching Cython code even when the C++ side was already fully annotated.

## Context and Constraints
- The C++ reflection system (Design 0006) already registers field metadata, methods, and type hierarchy via `ObjectDef<T>` and exposes it through the C ABI (`TVMFFIFieldInfo`, `TVMFFIMethodInfo`, `TVMFFITypeInfo`).
- Python bindings are implemented in Cython for performance. Cython provides low-overhead access to C structs but needs a Python-visible metadata layer for pure-Python consumers.
- The decorator must be compatible with `typing.dataclass_transform` (PEP 681) so that mypy and Pylance understand the synthesized `__init__` and field types.
- Field defaults and `default_factory` must follow Python `dataclasses.field()` conventions.
- Inheritance must be supported: a Python `@c_class` can subclass another `@c_class`, inheriting parent fields.

## Goals
- Provide `TypeInfo`, `TypeField`, and `TypeMethod` Python dataclasses that mirror the C ABI reflection metadata and are accessible from pure Python.
- Provide the `@c_class(type_key)` decorator that reads reflection metadata and synthesizes a proxy class with properties, `__init__`, and methods.
- Support `field(default=..., default_factory=..., init=...)` for controlling constructor signature and defaults.
- Provide `reflection::init<T, Args...>` to reduce boilerplate when registering C++ `__init__` methods.
- Optimize the FFI object return path to minimize Python-side overhead.

## Non-Goals
- Full Python `dataclasses` API parity (e.g., `repr`, `order`, `frozen`, `slots` parameters on the decorator).
- Automatic discovery or code generation of Python proxy classes from C++ reflection metadata.
- Replacing `@register_object` for types that do not need dataclass-style syntax.

## Design
### Components and Responsibilities

- **`TypeField`** (Python dataclass, `cython/type_info.pxi`): Mirrors a single `TVMFFIFieldInfo`. Fields: `name`, `doc`, `size`, `offset`, `frozen`, `getter` (Cython `FieldGetter`), `setter` (Cython `FieldSetter`). Method `as_property(cls)` creates a Python `property` with appropriate `fget`/`fset` bound to the Cython getter/setter.

- **`TypeMethod`** (Python dataclass, `cython/type_info.pxi`): Mirrors a single `TVMFFIMethodInfo`. Fields: `name`, `doc`, `func` (the wrapped `Function` callable), `is_static`.

- **`TypeInfo`** (Python dataclass, `cython/type_info.pxi`): Aggregated type metadata. Fields: `type_cls` (the Python class or `None` if not yet materialized), `type_index`, `type_key`, `fields` (list of `TypeField`), `methods` (list of `TypeMethod`), `parent_type_info` (linked `TypeInfo` for the parent type).

- **`FieldGetter` / `FieldSetter`** (Cython extension types, `cython/type_info.pxi`): Thin callables that read/write a field at a known offset from the Object handle. `FieldGetter.__call__(obj)` computes `field_ptr = obj.chandle + offset`, invokes the C-level `TVMFFIFieldGetter`, and returns the result via `make_ret`. `FieldSetter.__call__(obj, value)` does the inverse through `TVMFFIPyCallFieldSetter`.

- **`_type_info_create_from_type_key`** (Cython function, `cython/object.pxi`): Reads the C ABI `TVMFFITypeInfo` for a type key, iterates its `fields` and `methods` arrays, wraps each into `TypeField`/`TypeMethod` with Cython getter/setter objects, and returns a `TypeInfo` instance.

- **`_register_object_by_index`** (Cython function, `cython/object.pxi`): Creates a `TypeInfo` for a given `(type_index, type_cls)` pair and stores it in two registries: `TYPE_INDEX_TO_INFO` (list indexed by type_index) and `TYPE_KEY_TO_INFO` (dict keyed by type_key). Also populates `TYPE_INDEX_TO_CLS` for the fast return path.

- **`TYPE_INDEX_TO_CLS`** (Cython list, `cython/object.pxi`): Direct mapping from type_index to Python type class, introduced in commit `035975a` to bypass the `TypeInfo` indirection in `make_ret_object`. This is the hot-path optimization: `make_ret_object` checks `TYPE_INDEX_TO_CLS[tindex]` before falling back to `TYPE_INDEX_TO_INFO`.

- **`_add_class_attrs`** (Python function, `registry.py`): Given a `type_cls` and `TypeInfo`, attaches property descriptors (from `TypeField.getter`/`TypeField.setter`) and method wrappers (from `TypeMethod.func`) to the class. Called by `register_object` after `_register_object_by_index`.

- **`@c_class(type_key, init=True)`** (decorator, `dataclasses/c_class.py`): The primary entry point. Annotated with `@dataclass_transform` for PEP 681 compliance. Steps: (1) looks up `TypeInfo` from the registry, (2) inspects class annotations to match Python field declarations against C++ reflected fields, (3) fills `dataclass_field` metadata on each `TypeField`, (4) generates an `__init__` via `method_init` if requested, (5) creates the proxy class via `type_info_to_cls`.

- **`field(default, default_factory, init)`** (function, `dataclasses/field.py`): Returns a `Field` placeholder that `@c_class` consumes. Mirrors `dataclasses.field()`. The `init` parameter (added in commit `daeb235`) controls whether a field appears in the generated `__init__` signature.

- **`method_init`** (function, `dataclasses/_utils.py`): Generates an `__init__` method via `exec`-based code generation (following the pattern of stdlib `dataclasses` and `pydantic`). Splits fields into required (no default), optional (with default), and non-init (with `init=False`) groups. The generated code calls `self.__ffi_init__(*args)` then optionally `self.__post_init__()`.

- **`type_info_to_cls`** (function, `dataclasses/_utils.py`): Creates a new Python class by assembling base classes (defaulting to `Object` if the user class inherits from `object`), attaching field properties via `TypeField.as_property`, adding methods, and preserving class metadata (`__module__`, `__qualname__`). Returns the new class with `functools.wraps` applied.

- **`reflection::init<T, Args...>`** (C++ template, `include/tvm/ffi/reflection/registry.h`): A convenience function that constructs an `ObjectRef` wrapping a new `T` (or `T::ContainerType`). Used as `refl::ObjectDef<T>().def_static("__init__", refl::init<T, int64_t, int32_t>)` to avoid writing lambda boilerplate.

### Data Contracts and Invariants
- **Python/C++ field correspondence**: `@c_class` enforces that every Python-annotated field has a matching C++ reflected field and vice versa. Extra or missing fields raise `ValueError` at class creation time.
- **TypeInfo single-creation**: Each `type_key` gets at most one `TypeInfo` instance. Attempting to re-register raises `AssertionError`.
- **TYPE_INDEX_TO_CLS consistency**: `len(TYPE_INDEX_TO_CLS) == len(TYPE_INDEX_TO_INFO)` is asserted on every registration.
- **`__ffi_init__` requirement**: If `init=True`, the type's `TypeInfo.methods` must contain a method named `__ffi_init__`. Otherwise `method_init` raises `ValueError`.
- **Field ordering**: The generated `__init__` places required parameters (no default) before optional parameters (with default), regardless of declaration order. Fields with `init=False` are excluded from the signature entirely.

### Control Flow
1. **C++ registration**: At static init time, `ObjectDef<FooObj>().def_static("__init__", refl::init<FooObj, int64_t>).def_rw("x", &FooObj::x)` registers fields and methods into `TVMFFITypeInfo`.
2. **Python class registration via `@c_class("test.Foo")`**:
   a. `_lookup_type_info_from_type_key("test.Foo")` retrieves or creates a `TypeInfo` by reading the C ABI `TVMFFITypeInfo`.
   b. `_inspect_c_class_fields` matches Python annotations against `TypeInfo.fields`, enforcing 1:1 correspondence.
   c. `fill_dataclass_field` parses each field's RHS (bare value, `Field` instance, or `MISSING`) into a `Field` descriptor.
   d. `method_init` generates an `__init__` function via `exec()` with proper signature, defaults, and `__ffi_init__` delegation.
   e. `type_info_to_cls` creates the final class inheriting from `Object`, with properties and methods installed.
   f. The class is registered back into `TYPE_INDEX_TO_CLS` and `TYPE_INDEX_TO_INFO`.
3. **Object instantiation**: `Foo(x=42)` -> generated `__init__` -> `self.__ffi_init__(42)` -> Cython FFI call -> C++ constructor.
4. **Object return from FFI**: `make_ret_object` reads `result.type_index` -> `TYPE_INDEX_TO_CLS[tindex]` -> `cls.__new__(cls)` -> set `chandle` -> return Python object.

### Extension Points
- **New `Field` parameters**: Add more parameters to the `Field` dataclass (e.g., `repr`, `compare`) and handle them in `method_init` / `type_info_to_cls`.
- **`__post_init__` hook**: The generated `__init__` already calls `self.__post_init__()` if defined, allowing Python-only initialization logic after C++ construction.
- **Custom class transforms**: Override `type_info_to_cls` for specialized class generation (e.g., adding `__repr__`, `__eq__`, `__hash__`).
- **Lazy TypeInfo**: `_lookup_type_info_from_type_key` can create `TypeInfo` without a `type_cls`, enabling metadata queries before the Python class is defined.

## Alternatives Considered
### Manual property definitions per class
- Pros: No decorator magic. Each class is explicit.
- Cons: Extreme boilerplate. N fields requires N property definitions with getter/setter lambdas. Error-prone for inheritance. Does not scale.

### Extend `@register_object` with auto-property generation
- Pros: Single decorator. Backward compatible.
- Cons: `@register_object` is a minimal class-to-type_key binding. Adding dataclass semantics (defaults, `__init__`, field ordering) conflates two concerns and would break existing users who define their own `__init__`.

### Use Python `dataclasses.dataclass` directly
- Pros: Standard library. Full feature set.
- Cons: `dataclasses.dataclass` generates Python-only fields stored on `__dict__`. FFI objects store fields in C++ memory at known offsets. The two models are fundamentally incompatible without a custom descriptor protocol.

## Trade-offs
- **Optimized**: Developer experience (dataclass syntax for C++ objects), IDE support (PEP 681 `@dataclass_transform`), FFI return path performance (`TYPE_INDEX_TO_CLS` avoids indirection).
- **Sacrificed**: `exec`-based code generation is opaque to static analysis tools (though the signature is still inspectable). The `@c_class` decorator is marked experimental and may have breaking changes. Error messages from the generated `__init__` point to dynamically created code rather than source files.

## Interfaces and Compatibility
- **Python public API**: `tvm_ffi.dataclasses.c_class`, `tvm_ffi.dataclasses.field`, `tvm_ffi.dataclasses.Field`, `tvm_ffi.dataclasses.MISSING`.
- **Python internal API**: `tvm_ffi.core.TypeInfo`, `tvm_ffi.core.TypeField`, `tvm_ffi.core.TypeMethod`, `tvm_ffi.core._register_object_by_index`, `tvm_ffi.core._lookup_type_info_from_type_key`, `tvm_ffi.core._set_type_cls`.
- **C++ API**: `tvm::ffi::reflection::init<T, Args...>`.
- **Stub types**: `TypeInfo`, `TypeField`, `TypeMethod` are declared in `core.pyi` for type checker visibility.
- **Compatibility**: `@register_object` continues to work for types that do not need dataclass syntax. The two can coexist; `@register_object` uses the same `_register_object_by_index` + `_add_class_attrs` path.

## Failure Modes and Mitigations
- **Field mismatch between Python and C++**: `_inspect_c_class_fields` raises `ValueError` at class creation time listing the extra or missing fields. This is a fail-fast diagnostic.
- **Missing `__ffi_init__` method**: `method_init` raises `ValueError` with the type key. The user must register an `__init__` in C++ via `ObjectDef::def_static("__init__", ...)`.
- **Unregistered object type returned from FFI**: Commit `d68c8d8` adds a fallback in `make_ret_object` so unregistered types return a base `Object` instance instead of throwing.
- **Cython memory corruption in type_info creation**: Commit `8e471b0` fixes a read-after-free where the `ByteArrayArg` holding the type key was destructed before `TVMFFITypeKeyToIndex` used it. Fix ensures proper lifetime of the temporary.

## Observability and Validation
- `tests/python/test_dataclasses_c_class.py`: Tests `@c_class` with default values, `field(init=False)`, inheritance, and `__post_init__`.
- `tests/python/test_object.py`: Tests `register_object`, reflected field access, and unregistered type fallback.
- `tests/cpp/test_reflection.cc`: Tests `reflection::init<>` and `ObjectDef` registration.
- `core.pyi` stub file provides type checker coverage for `TypeInfo`, `TypeField`, `TypeMethod`.

## Migration and Rollout
- **New classes**: Use `@c_class("type.Key")` with annotated fields. Define C++ reflection via `ObjectDef<T>`.
- **Existing classes**: `@register_object` continues to work unchanged. To adopt `@c_class`, add field annotations and a `field()` default for each reflected field, then replace `@register_object` with `@c_class`.
- **Experimental status**: The `@c_class` API is marked experimental. Breaking changes are possible in future releases.

## Diagrams
- None yet.

## Related ADRs
- None.

## Evidence Matrix
- `TypeInfo`/`TypeField`/`TypeMethod` Python dataclasses introduced in `cython/type_info.pxi` -> `.memory/commits/2025-09-19-53b2e00e.md` + `53b2e00` + `python/tvm_ffi/cython/type_info.pxi`
- `_type_info_create_from_type_key` reads C ABI structs -> `.memory/commits/2025-09-19-53b2e00e.md` + `53b2e00` + `python/tvm_ffi/cython/object.pxi`
- `reflection::init<T, Args...>` template -> `.memory/commits/2025-09-21-c01dadf3.md` + `c01dadf` + `include/tvm/ffi/reflection/registry.h`
- `@c_class` decorator and `c_class.py` -> `.memory/commits/2025-09-21-e98b94e.md` + `e98b94e` + `python/tvm_ffi/dataclasses/c_class.py`
- `field.py` with `Field` dataclass -> `.memory/commits/2025-09-21-e98b94e.md` + `e98b94e` + `python/tvm_ffi/dataclasses/field.py`
- `method_init` and `type_info_to_cls` in `_utils.py` -> `.memory/commits/2025-09-21-e98b94e.md` + `e98b94e` + `python/tvm_ffi/dataclasses/_utils.py`
- `TYPE_INDEX_TO_CLS` fast-path cache -> `.memory/commits/2025-09-23-035975a.md` + `035975a` + `python/tvm_ffi/cython/object.pxi`
- `field(init=False)` and `exec`-based `__init__` generation -> `.memory/commits/2025-09-24-daeb235.md` + `daeb235` + `python/tvm_ffi/dataclasses/_utils.py`, `python/tvm_ffi/dataclasses/field.py`
- mypy `field()` type fix -> `.memory/commits/2025-09-22-b5dd851.md` + `b5dd851` + `python/tvm_ffi/dataclasses/field.py`
- Unregistered type fallback -> `.memory/commits/2025-09-22-d68c8d8.md` + `d68c8d8` + `python/tvm_ffi/cython/object.pxi`
- Cython memory corruption fix in `_type_info_create_from_type_key` -> `.memory/commits/2025-09-25-8e471b0.md` + `8e471b0` + `python/tvm_ffi/cython/object.pxi`

## Open Questions
- Should `@c_class` support `repr=True` to auto-generate `__repr__` from reflected fields?
- Should `@c_class` support `frozen=True` to make all properties read-only?
- Should the `exec`-based `__init__` generation be replaced with a code-object builder for better debuggability?

## Confidence and Risk
- Confidence: high
- Residual risks: The `exec`-based `__init__` generation is a common pattern (used by `dataclasses` and `pydantic`) but makes stack traces less readable. The `@c_class` API is experimental and may have breaking changes. The `TYPE_INDEX_TO_CLS` list grows unboundedly with type registrations, though this matches the behavior of all other type registries.
