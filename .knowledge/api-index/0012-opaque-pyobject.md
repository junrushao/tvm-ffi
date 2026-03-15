---
scope: "opaque-pyobject"
status: "active"
last_updated_commit: "91d69f0658eef18fd9c99d4ac195ad5319db3787"
related_designs:
  - ".knowledge/designs/object-system.md"
  - ".knowledge/designs/c-abi.md"
  - ".knowledge/designs/0014-python-bindings.md"
related_adrs:
  - ".knowledge/ADRs/003-type-index-ranges.md"
---
# API Index: Opaque PyObject Support

**Scope**: C ABI, C++, and Cython APIs for wrapping arbitrary Python objects as ref-counted FFI objects that can round-trip through C++ containers and callbacks.
**Design docs**: `.knowledge/designs/object-system.md`, `.knowledge/designs/c-abi.md`, `.knowledge/designs/0014-python-bindings.md`
**ADRs**: `.knowledge/ADRs/003-type-index-ranges.md`

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFIObjectCreateOpaque` | `int TVMFFIObjectCreateOpaque(void* handle, int32_t type_index, void (*deleter)(void*), TVMFFIObjectHandle* out)` | Create opaque object wrapping external handle; currently only `kTVMFFIOpaquePyObject` supported |
| `TVMFFIOpaqueObjectGetCellPtr` | `inline TVMFFIOpaqueObjectCell* TVMFFIOpaqueObjectGetCellPtr(TVMFFIObjectHandle obj)` | Returns pointer to `TVMFFIOpaqueObjectCell` after object header |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `TVMFFIOpaqueObjectCell` | struct | `void* handle` | Cell following object header; for Python: `handle` is `PyObject*` |
| `OpaqueObjectImpl` (internal) | class : Object, TVMFFIOpaqueObjectCell | `OpaqueObjectImpl(void*, void(*)(void*))`, `SetTypeIndex(int32_t)`, `~OpaqueObjectImpl()` | Internal implementation; destructor calls deleter(handle) |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `kTVMFFIOpaquePyObject` | `= 74` (TVMFFITypeIndex enum) | Static type index for opaque Python objects |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `OpaquePyObject` | `cdef class OpaquePyObject(Object)` | Cython class wrapping opaque Python objects |
| `OpaquePyObject.pyobject` | `def pyobject(self) -> object` | Extract the underlying Python object |
| `_convert_to_opaque_object` | `(object pyobject) -> OpaquePyObject` | Wrap a Python object via `Py_INCREF` + `TVMFFIObjectCreateOpaque` |
| `make_ret_opaque_object` | `(TVMFFIAny result) -> object` | Unwrap opaque return value back to original Python object |
| `convert()` (updated) | `(obj) -> Any` | No longer raises TypeError for unrecognized types; wraps as opaque |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| (none) | -- | Opaque objects not yet exposed in Rust bindings |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `tvm_ffi_callback_deleter` | `tvm_ffi_pyobject_deleter` | 91d69f0 | Generalized from function-specific to shared PyObject deleter |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 91d69f0 | `2025-09-05-91d69f0658eef18fd9c99d4ac195ad5319db3787.md` | kTVMFFIOpaquePyObject=74, TVMFFIOpaqueObjectCell, TVMFFIObjectCreateOpaque, OpaquePyObject Cython class, convert() fallback change |
