---
scope: "python-dataclasses"
---
# API Index: Python Dataclass Decorators (tvm_ffi.dataclasses)

**Scope**: Public API surface of `tvm_ffi.dataclasses` -- `@c_class`, `@py_class`, `field()`, and `Field` descriptor.
**Design docs**: [0015-python-dataclasses.md](../designs/0015-python-dataclasses.md)
**ADRs**: [0019-python-defined-ffi-classes.md](../ADRs/0019-python-defined-ffi-classes.md)

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `c_class` | `def c_class(type_key: str, init: bool = True, kw_only: bool = False, repr: bool = True) -> Callable[[type], type]` | Decorator binding Python class to C++ FFI type. Implemented as `register_object` + `_install_structural_dunders` (e5f3af7) |
| `py_class` | `def py_class(cls_or_type_key: type \| str \| None = None, /, *, type_key: str \| None = None, init: bool = True, repr: bool = True, eq: bool = False, order: bool = False, unsafe_hash: bool = False, kw_only: bool = False, structure: str \| None = None, slots: bool = True) -> Callable \| type` | Decorator for Python-defined FFI dataclasses. Two-phase registration with forward-reference support (3374f57) |
| `field` | `def field(*, default=MISSING, default_factory=MISSING, init: bool = True, repr: bool = True, hash: bool \| None = None, compare: bool = True, kw_only: bool \| None = None, structure: str \| None = None, doc: str \| None = None) -> Any` | Declare field with default, init/repr/hash/compare flags, structural eq annotation, and doc (84f46d4) |
| `Field` | `class Field: __slots__ = ("compare", "default", "default_factory", "doc", "hash", "init", "kw_only", "name", "repr", "structure", "ty")` | Descriptor for a single field. `name` and `ty` filled by decorator from annotations |
| `KW_ONLY` | `class KW_ONLY` | Sentinel annotation: all fields after this become keyword-only |

## Internal API (architecturally important)
| Name | Signature | Description |
|------|-----------|-------------|
| `Object.__ffi_init__` | `def __ffi_init__(self, *args: Any) -> None` | Unified constructor bridge. Dispatches to `type(self).__c_ffi_init__` |
| `_install_init` | `def _install_init(cls: type, type_key: str) -> None` | Auto-wire `__init__` from C++ `__ffi_init__` on `register_object` classes (b1abaee) |
| `_install_structural_dunders` | `def _install_structural_dunders(cls: type, type_key: str) -> None` | Install `__eq__`, `__hash__`, `__repr__`, `__copy__`, `__deepcopy__` (e5f3af7) |
| `_phase1_register_type` | `def _phase1_register_type(cls: type, type_key: str \| None) -> TypeInfo` | Phase 1: allocate type index, register in type table |
| `_phase2_register_fields` | `def _phase2_register_fields(cls, type_info, globalns, params) -> bool` | Phase 2: resolve annotations, register fields. Returns False to defer |
| `_collect_py_methods` | `def _collect_py_methods(cls: type) -> list[tuple[str, Any, bool]] \| None` | Extract `__ffi_*` dunders from class body for TypeMethod registration (5735098) |
| `_FFI_RECOGNIZED_METHODS` | `frozenset[str]` | Allowlist of `__ffi_*` dunder names auto-registered as TypeMethod/TypeAttr |
| `_STRUCTURE_KIND_MAP` | `dict[str \| None, int]` | Maps structure parameter strings to `TVMFFISEqHashKind` enum values |

## Cython Internals (architecturally important)
| Name | Signature | Description |
|------|-----------|-------------|
| `TypeSchema` | `class TypeSchema` | Type converter dispatching to C++ `__ffi_convert__` methods (5f5ca5a) |
| `CAny` | `class CAny` | Owned-value wrapper mirroring C++ `Any` for safe lifetime management (2885cf8) |
| `__ffi_new__` | `def __ffi_new__(type_index: int) -> Object` | Cython object allocator, fallback when no `__ffi_init__` registered (e3333e2) |
