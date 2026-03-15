---
scope: "python-dataclasses"
---
# API Index: Python Dataclasses (`tvm_ffi.dataclasses`)

**Scope**: The `tvm_ffi.dataclasses` sub-package providing `@c_class` decorator with structural dunder installation, and supporting types for dataclass-style Python proxies over C++ FFI objects.
**Design docs**: [0018-python-dataclasses.md](../designs/0018-python-dataclasses.md), [0009-reflection.md](../designs/0009-reflection.md)
**ADRs**: [0017-c-class-over-register-object.md](../ADRs/0017-c-class-over-register-object.md), [0027-auto-init-from-reflection.md](../ADRs/0027-auto-init-from-reflection.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `reflection::init<Args...>` | struct template (fc2630f) | `init()` ctor; type deduced from `ObjectDef<Class>` context | Constructor registration tag; used with `ObjectDef::def(refl::init<Args...>())` |
| `__ffi_init__` | convention | Static method name auto-registered via `ObjectDef::def(refl::init<Args...>())` | Standard C++ constructor method name consumed by Python via `Object.__ffi_init__` dispatch |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `c_class` | `(type_key: str, *, init: bool=True, repr: bool=True, eq: bool=False, order: bool=False, unsafe_hash: bool=False) -> Callable[[_T], _T]` (e5f3af7b) | Combines `register_object` with `_install_dataclass_dunders`. `@dataclass_transform(eq_default=False, order_default=False)` for IDE support. `eq` installs `__eq__`/`__ne__` via RecursiveEq; `order` installs `__lt__`/`__le__`/`__gt__`/`__ge__`; `unsafe_hash` installs `__hash__` via RecursiveHash |
| `_install_dataclass_dunders` | `(cls: type, *, init: bool, repr: bool, eq: bool, order: bool, unsafe_hash: bool) -> None` (e5f3af7b) | Install structural dunders delegating to C++ recursive ops. Never overwrites user-defined dunders in `cls.__dict__` |
| `_make_init` | `(type_cls: type, type_info: TypeInfo) -> Callable[..., None]` (b1abaeac) | Build Python `__init__` delegating to `__ffi_init__` via KWARGS sentinel protocol. Sets `__signature__` from `_make_init_signature` |
| `_make_init_signature` | `(type_info: TypeInfo) -> inspect.Signature` (b1abaeac) | Build `inspect.Signature` from reflection fields; walks parent chain, respects `c_init`/`c_kw_only`/`c_has_default` |
| `_install_init` | `(cls: type, *, enabled: bool) -> None` (6973d225) | Install `__init__` from C++ reflection metadata; checks `auto_init` metadata flag. If disabled, installs TypeError guard |
| `field` | **REMOVED** (b97ff1a) | -- | Deleted in b97ff1a. Field metadata now controlled entirely in C++ via `refl::DefaultValue`, `refl::init(false)`, `refl::kw_only(true)`, `refl::repr(false)` |
| `Field` | **REMOVED** (b97ff1a) | -- | Deleted in b97ff1a |
| `KW_ONLY` | **REMOVED** (b97ff1a) | -- | Deleted in b97ff1a. Use C++ `refl::kw_only(true)` trait instead |
| `MISSING` | **REMOVED** (b97ff1a) | -- | Deleted in b97ff1a |
| `TypeInfo` | dataclass (Cython) | `type_cls: type \| None, type_index: int, type_key: str, fields: list[TypeField], methods: list[TypeMethod], parent_type_info: TypeInfo \| None` | Aggregated type reflection metadata from C++ |
| `TypeField` | dataclass (Cython) | `name: str, doc: str \| None, size: int, offset: int, frozen: bool, getter: FieldGetter, setter: FieldSetter, dataclass_field: Field \| None, c_init: bool, c_kw_only: bool, c_has_default: bool` | Single field descriptor; `as_property(cls) -> property` creates a Python property. `c_init`/`c_kw_only`/`c_has_default` (b1abaeac) expose init-related bitmask flags |
| `TypeMethod` | dataclass (Cython) | `name: str, doc: str \| None, func: object, is_static: bool` | Single method descriptor |
| `Object.__ffi_init__` | `(self, *args) -> None` | Dispatch method; calls `type(self).__c_ffi_init__` via `__init_handle_by_constructor__` |
| `_register_object_by_index` | `(type_index: int, type_cls: type) -> TypeInfo` | Register Python class for a type index; returns TypeInfo. Updates `TYPE_INDEX_TO_INFO`, `TYPE_KEY_TO_INFO`, `TYPE_INDEX_TO_CLS` |
| `_lookup_or_register_type_info_from_type_key` | `(type_key: str) -> TypeInfo` | Create/return TypeInfo from C++ reflection data via `TVMFFIGetTypeInfo`; registers into all three registries (renamed from `_lookup_type_info_from_type_key`, 98cb8af) |
| `_set_type_cls` | `(type_info: TypeInfo, type_cls: type) -> None` | Deferred class registration; sets class after TypeInfo created with `type_cls=None` (signature changed from `(int, type)`, 98cb8af) |
| `make_fallback_cls_for_type_index` | `(type_index: int) -> object` | Auto-generate Python class for unregistered C++ type using reflection metadata; recursive parent class creation (98cb8af) |
| `TypeMethod.as_callable` | `(cls: type) -> Callable` | Create Python method from reflected method; wraps instance methods with `_member_method_wrapper`, static methods with `staticmethod()` (98cb8af) |
| `_update_registry` | `(type_index, type_key, type_info, type_cls)` | Factored-out helper updating all three registries atomically (98cb8af) |
| `_add_class_attrs` | `(type_cls: type, type_info: TypeInfo) -> type` | Attach field properties and methods from TypeInfo to a class. Renames `__ffi_init__` to `__c_ffi_init__` |
| `RecursiveEq` | `(lhs: Any, rhs: Any) -> bool` (Python `_ffi_api` stub, b87196f) | Recursive structural equality via C++ `ffi.RecursiveEq` |
| `RecursiveLt` | `(lhs: Any, rhs: Any) -> bool` (Python `_ffi_api` stub, b87196f) | Recursive structural less-than |
| `RecursiveLe` | `(lhs: Any, rhs: Any) -> bool` (Python `_ffi_api` stub, b87196f) | Recursive structural less-than-or-equal |
| `RecursiveGt` | `(lhs: Any, rhs: Any) -> bool` (Python `_ffi_api` stub, b87196f) | Recursive structural greater-than |
| `RecursiveGe` | `(lhs: Any, rhs: Any) -> bool` (Python `_ffi_api` stub, b87196f) | Recursive structural greater-than-or-equal |
| `RecursiveHash` | `(value: Any) -> int` (Python `_ffi_api` stub, 5796ff4) | Recursive structural hash via C++ `ffi.RecursiveHash` |
| `core.KWARGS` | sentinel object (b1abaeac) | KWARGS sentinel for KWARGS calling convention (`ffi.GetKwargsObject()`) |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | -- | Rust bindings do not currently use the dataclass system |
