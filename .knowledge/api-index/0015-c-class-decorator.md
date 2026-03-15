---
scope: "c-class-decorator"
status: "active"
last_updated_commit: "daeb235a29c576d8702d447fa5f4773170bb1e8f"
related_designs:
  - ".knowledge/designs/0019-c-class-decorator.md"
  - ".knowledge/designs/0014-python-bindings.md"
related_adrs: []
---
# API Index: c_class Decorator (tvm_ffi.dataclasses)

**Scope**: The `@c_class` decorator subsystem for FFI-backed dataclass-style Python classes.
**Design docs**: `.knowledge/designs/0019-c-class-decorator.md`, `.knowledge/designs/0014-python-bindings.md`
**ADRs**: None specific.

## C ABI Functions

(Not applicable -- this is a Python-level subsystem consuming C++ reflection metadata.)

## C++ Types

(Not applicable -- C++ types are registered via `ObjectDef`; see `.knowledge/api-index/0003-reflection.md`.)

## C++ Functions & Macros

| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `reflection::init<T, Args...>` | `inline ObjectRef init(Args&&... args)` | Constructs ObjectRef from `make_object<T>(args...)` or `<T::ContainerType>` |

## Python API

| Name | Signature | Description |
|------|-----------|-------------|
| `c_class` | `def c_class(type_key: str, init: bool = True) -> Callable[[type], type]` | `@dataclass_transform` decorator; validates annotations against C++ fields, synthesizes `__init__` |
| `field` | `def field(*, default: _FieldValue = MISSING, default_factory: Callable[[], _FieldValue] = MISSING, init: bool = True) -> _FieldValue` | Field descriptor factory with TypeVar return for mypy |
| `Field` | `class Field` | `__slots__ = ("default_factory", "init", "name")` |
| `MISSING` | `_MISSING_TYPE` | Sentinel for unset defaults |
| `Object.__ffi_init__` | `def __ffi_init__(self, *args) -> None` | Dispatches to `type(self).__c_ffi_init__(*args)` via `__init_handle_by_constructor__` |
| `_inspect_c_class_fields` | `def _inspect_c_class_fields(type_cls, type_info) -> list[TypeField]` | Validates Python annotations match C++ reflected fields |
| `fill_dataclass_field` | `def fill_dataclass_field(type_cls, type_field) -> None` | Maps class-body RHS to Field descriptor on TypeField.dataclass_field |
| `method_init` | `def method_init(type_cls, type_info) -> Callable` | Generates `__init__` via exec-based code generation |
| `type_info_to_cls` | `def type_info_to_cls(type_info, cls, methods) -> type` | Creates new class with properties, methods, bases adjusted |
| `get_parent_type_info` | `def get_parent_type_info(type_cls) -> TypeInfo` | Walks `__bases__` for `__tvm_ffi_type_info__` |

## Rust API

(Not applicable.)

## Deprecated / Renamed

| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `__create__` (C++ reflection method) | `__ffi_init__` | c01dadf | Canonical constructor method name |
| `Field` as `@dataclass(kw_only=True)` | `Field` with `__slots__` + explicit `__init__` | 40e9c83 | mypy compatibility |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| c01dadf | `2025-09-21-c01dadf31a66e74cdbfd7fdb1ffc81a75007965f.md` | `reflection::init<T>` + `__ffi_init__` convention |
| e98b94e | `2025-09-21-e98b94e118dfa5ac4bcf3764a8b1695afee3d596.md` | `c_class` decorator, `Field`/`field()`, `Object.__ffi_init__` |
| daeb235 | `2025-09-24-daeb235a29c576d8702d447fa5f4773170bb1e8f.md` | `field(init=False)`, exec-based code gen |

(plus 1 supporting commit: b5dd851 TypeVar field return type)
