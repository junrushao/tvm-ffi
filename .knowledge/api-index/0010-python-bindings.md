---
scope: "python-bindings"
status: "active"
last_updated_commit: "a7ebc65f14eecd1592d407f1d5c952c65603a9aa"
related_designs:
  - ".knowledge/designs/0014-python-bindings.md"
  - ".knowledge/designs/0015-python-packaging.md"
  - ".knowledge/designs/0018-dlpack-fast-path.md"
related_adrs:
  - ".knowledge/ADRs/012-cython-binding-layer.md"
  - ".knowledge/ADRs/013-standalone-ffi-packaging.md"
---
# API Index: Python Bindings (tvm_ffi)

**Scope**: Public Python API surface of the `tvm_ffi` package, including Cython extension types, pure-Python wrappers, and the packaging/discovery utilities.
**Design docs**: `.knowledge/designs/0014-python-bindings.md`, `.knowledge/designs/0015-python-packaging.md`
**ADRs**: `.knowledge/ADRs/012-cython-binding-layer.md`, `.knowledge/ADRs/013-standalone-ffi-packaging.md`

## C ABI Functions

(Not applicable -- this index covers the Python layer. See `0009-env-api.md` for C env APIs consumed by the Python layer.)

## C++ Types

(Not applicable -- see other API indexes for C++ types consumed by the Python bindings.)

## C++ Functions & Macros

(Not applicable.)

## Python API

### Top-Level Exports (`tvm_ffi.__init__`)

| Name | Signature | Description |
|------|-----------|-------------|
| `register_object` | `def register_object(type_key: str \| None = None) -> Callable[[_T], _T]` | Decorator to register Python class by type key; auto-populates via reflection. `_T = TypeVar("_T", bound=type)` preserves class type (since 0ee6444) |
| `register_global_func` | `def register_global_func(func_name: str, f=None, override=False) -> Function` | Register a global function in the FFI registry (renamed from `register_func` in 40f4d9d) |
| `get_global_func` | `def get_global_func(name: str, allow_missing=False) -> Optional[Function]` | Look up a global function by name |
| `init_ffi_api` | `def init_ffi_api(namespace: str, target_module_name: str = None)` | Populate module namespace from global function registry by prefix (renamed from `_init_api` in 40f4d9d) |
| `convert` | `def convert(value: Any) -> Any` | Convert Python object to FFI value (list->Array, dict->Map, etc.) |
| `register_error` | `def register_error(name_or_cls=None, cls=None)` | Register Python exception class for FFI error mapping |
| `dtype` | `def dtype(content: str) -> DataType` | Create a TVM dtype (subclasses str); static method `dtype.from_dlpack_data_type(tuple[int,int,int]) -> dtype` (since 5e648f0) |
| `DLDeviceType` | `class DLDeviceType(IntEnum)` | DLPack device type constants (kDLCPU=1, kDLCUDA=2, ...). Added in 40f4d9d. |
| `Device` | `cdef class Device` | Wraps DLDevice. Properties: `type` (str), `index` (int, renamed from `device_id`), `dlpack_device_type()` (int method). Torch-aligned since 40f4d9d. |
| `device` | `def device(dev_type, index=0) -> Device` | Construct a Device from type int/str and index; `index` accepts numpy/torch scalars (since a7ebc65f) |
| `from_dlpack` | `def from_dlpack(ext_tensor, *, require_alignment=0, require_contiguous=False) -> Tensor` | Import DLPack tensor to Tensor (defaults relaxed in 1b824e8; renamed `NDArray` -> `Tensor` in 3a551d8) |
| `Tensor` | `cdef class Tensor` | DLTensor-based array with DLPack, numpy interop (renamed from `NDArray` in 3a551d8) |
| `Shape` | `class Shape(tuple, PyNativeObject)` | Tuple subclass wrapping ffi.Shape object |
| `Array` | `class Array(Object, Sequence[T])` | Immutable generic array; `__add__`/`__radd__`; slice returns `list[T]` |
| `Map` | `class Map(Object, Mapping[K, V])` | Immutable generic map; overloaded `Map.get`; consistent `KeyError` |
| `Module` | `class Module(Object)` | Runtime module with get_function, import_module; `__call__` delegates to `self.main` |
| `system_lib` | `def system_lib(symbol_prefix="") -> Module` | Get system-wide library module singleton |
| `load_module` | `def load_module(path: str | PathLike) -> Module` | Load shared library as Module (PathLike since 53a7fe9) |
| `Object` | `cdef class Object` | Base class for all FFI objects with chandle and ref-counting |
| `ObjectConvertible` | `class ObjectConvertible` | Abstract base for objects convertible via asobject() (renamed from `ObjectGeneric` in 40f4d9d) |
| `Function` | `cdef class Function(Object)` | FFI function with type-dispatch call via `TVMFFIPyCallManager`; `release_gil` property (default from `TVM_FFI_RELEASE_GIL_BY_DEFAULT` env var) |
| `StreamContext` | `class StreamContext(device, stream)` | Context manager for FFI thread-local stream save/restore (added in 3197cd0) |
| `TorchStreamContext` | `class TorchStreamContext(context)` | Context manager bridging torch and FFI stream contexts (added in 3197cd0; requires torch) |
| `use_raw_stream` | `def use_raw_stream(device: Device, stream: Union[int, c_void_p]) -> StreamContext` | Factory for StreamContext (added in 3197cd0) |
| `use_torch_stream` | `def use_torch_stream(context: Optional[Any] = None) -> TorchStreamContext` | Factory for TorchStreamContext (added in 3197cd0) |
| `get_raw_stream` | `def get_raw_stream(device: Device) -> int` | Query current FFI thread-local stream handle (added in a153647) |
| `get_global_func_metadata` | `def get_global_func_metadata(name: str) -> dict[str, Any]` | Retrieve metadata for globally registered function (added in 28fe3cc) |
| `tvm_ffi.float16` | `DataType("float16")` | Float16 dtype literal constant (since 408aa78) |
| `tvm_ffi.float32` | `DataType("float32")` | Float32 dtype literal constant (since 408aa78) |
| `tvm_ffi.float64` | `DataType("float64")` | Float64 dtype literal constant (since 408aa78) |
| `tvm_ffi.int8` | `DataType("int8")` | Int8 dtype literal constant (since 408aa78) |
| `tvm_ffi.int16` | `DataType("int16")` | Int16 dtype literal constant (since 408aa78) |
| `tvm_ffi.int32` | `DataType("int32")` | Int32 dtype literal constant (since 408aa78) |
| `tvm_ffi.int64` | `DataType("int64")` | Int64 dtype literal constant (since 408aa78) |
| `tvm_ffi.uint8` | `DataType("uint8")` | Uint8 dtype literal constant (since 408aa78) |
| `tvm_ffi.bool` | `DataType("bool")` | Bool dtype literal constant (since 408aa78) |
| `tvm_ffi.bfloat16` | `DataType("bfloat16")` | BFloat16 dtype literal constant (since 408aa78) |
| `tvm_ffi.float8_e4m3fn` | `DataType("float8_e4m3fn")` | FP8 E4M3 dtype literal constant (since 408aa78) |
| `tvm_ffi.float8_e5m2` | `DataType("float8_e5m2")` | FP8 E5M2 dtype literal constant (since 408aa78) |
| `get_raw_stream` | `def get_raw_stream(device: Device) -> int` | Query current FFI thread-local stream handle (added in a153647) |

### Cython Internal API (`tvm_ffi.cython.core`)

| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFIPyFuncCall` | `int (TVMFFIPyArgSetterFactory, void*, PyObject*, TVMFFIAny*, int*, bool, DLPackToPyObject*)` | Main FFI call entry point via `TVMFFIPyCallManager` (replaces `FuncCall`/`FuncCall3`) |
| `TVMFFIPyConstructorCall` | `int (TVMFFIPyArgSetterFactory, void*, PyObject*, TVMFFIAny*, int*, TVMFFIPyCallContext*)` | Nested constructor call with context propagation |
| `TVMFFIPyArgSetterFactory_` | `int (PyObject*, TVMFFIPyArgSetter*)` | Cython factory: creates setter per Python type via isinstance chain; now includes `__cuda_stream__`, `__tvm_ffi_object__`, `__tvm_ffi_opaque_ptr__` dispatch (since b0537f0, 8873700, 42e0612) |
| `make_ret` | `cdef object make_ret(TVMFFIAny result, DLPackToPyObject c_dlpack_to_pyobject)` | Unpack TVMFFIAny to Python object with optional framework tensor conversion |
| `make_ret_object` | `cdef object make_ret_object(TVMFFIAny result)` | Dispatch by TYPE_INDEX_TO_CLS table (since 035975a) |
| `ConstructorCall` | `cdef int ConstructorCall(void*, tuple, void**) except -1` | Call constructor, extract handle |
| `_convert_to_ffi_func` | `def _convert_to_ffi_func(pyfunc) -> Function` | Wrap Python callable as FFI Function |
| `_register_global_func` | `def _register_global_func(name, pyfunc, override) -> Function` | Register in global table via C API |
| `_get_global_func` | `def _get_global_func(name, allow_missing) -> Optional[Function]` | Retrieve from global table |
| `_lookup_type_attr` | `def _lookup_type_attr(type_index: int, attr_key: str) -> Any` | Query per-type attribute via TVMFFIGetTypeAttrColumn (since 4edf4f3) |
| `_register_object_by_index` | `def _register_object_by_index(type_index: int, type_cls: type) -> TypeInfo` | Register class in TYPE_INDEX_TO_INFO/CLS (since 53b2e00) |
| `_set_type_cls` | `def _set_type_cls(type_info: TypeInfo, type_cls: type) -> None` | Update TYPE_INDEX_TO_CLS for existing TypeInfo (signature changed in 98cb8af) |
| `_lookup_or_register_type_info_from_type_key` | `def _lookup_or_register_type_info_from_type_key(type_key: str) -> TypeInfo` | Lazy TypeInfo lookup/register by type key (renamed from `_lookup_type_info_from_type_key` in 98cb8af) |
| `_update_registry` | `cdef _update_registry(int type_index, str type_key, TypeInfo type_info, type type_cls)` | Centralized registry update for all three registries (since 98cb8af) |
| `_object_type_key_to_index` | `def _object_type_key_to_index(str type_key) -> Optional[int]` | Resolve type key to index |
| `FieldGetter` | `cdef class FieldGetter` | Calls TVMFFIFieldGetter at object offset |
| `FieldSetter` | `cdef class FieldSetter` | Calls TVMFFIFieldSetter at object offset |
| `CHECK_CALL` | `cdef int CHECK_CALL(int ret) except -2` | Check C API return code, raise on error |
| `Error` | `cdef class Error(Object)` | FFI error with kind/message/traceback properties |
| `_init_env_api` | `cdef _init_env_api()` | Register PyErr_CheckSignals, GIL functions |
| `ByteArrayArg` | `cdef class ByteArrayArg` | Wraps Python bytes as TVMFFIByteArray* |
| `tvm_ffi_callback` | `cdef int tvm_ffi_callback(void*, const TVMFFIAny*, int32_t, TVMFFIAny*) noexcept with gil` | C callback for Python-wrapped functions |
| `Function.__from_extern_c__` | `@staticmethod (c_symbol: int, *, keep_alive_object=None) -> Function` | Create Function from extern C symbol (added in b64b46f) |
| `Function.__from_mlir_packed_safe_call__` | `@staticmethod (mlir_symbol: int, *, keep_alive_object=None) -> Function` | Create Function from MLIR packed pointer (added in f6303b2) |
| `TypeSchema` | `@dataclass; origin: str, args: tuple[TypeSchema, ...]` | Parse and render C++ type schemas (added in 28fe3cc) |
| `TypeSchema.repr` | `def repr(ty_map: Callable[[str], str] | None = None) -> str` | Render with optional type name remapping (added in dd4fb0a) |

### Error Handling (`tvm_ffi.error`)

| Name | Signature | Description |
|------|-----------|-------------|
| `register_error` | `def register_error(name_or_cls=None, cls=None)` | Register Python exception class for FFI error kind mapping |
| `_parse_backtrace` | `def _parse_backtrace(backtrace: str) -> list[tuple[str, int, str]]` | Parse C++ backtrace string (renamed from `_parse_traceback` in 6f020c1) |
| `TracebackManager` | `class TracebackManager` | Caches code objects, reconstructs Python TracebackType chains |
| `TracebackManager.append_traceback` | `def append_traceback(tb, filename, lineno, func) -> TracebackType` | Append one frame to traceback chain |
| `_with_append_backtrace` | `def _with_append_backtrace(py_error, backtrace: str) -> Exception` | Reconstruct full traceback on exception (renamed in 6f020c1) |
| `_traceback_to_backtrace_str` | `def _traceback_to_backtrace_str(tb) -> str` | Convert Python traceback to backtrace string (renamed in 6f020c1) |

### Registry (`tvm_ffi.registry`)

| Name | Signature | Description |
|------|-----------|-------------|
| `register_object` | `def register_object(type_key: str \| None = None) -> Callable[[_T], _T]` | Decorator; resolves type index, adds reflection, registers class. TypeVar `_T = TypeVar("_T", bound=type)` preserves decorated class type (since 0ee6444) |
| `register_global_func` | `def register_global_func(func_name, f=None, override=False)` | Register global function (renamed from `register_func` in 40f4d9d) |
| `get_global_func` | `def get_global_func(name, allow_missing=False) -> Optional[Function]` | Look up global function |
| `list_global_func_names` | `def list_global_func_names() -> list[str]` | List all registered global function names |
| `get_registered_type_keys` | `def get_registered_type_keys() -> list[str]` | Return all registered type keys from global type table (since 8fcd924) |
| `remove_global_func` | `def remove_global_func(name: str)` | Remove a global function |
| `init_ffi_api` | `def init_ffi_api(namespace, target_module_name=None)` | Auto-bind global functions by prefix (renamed from `_init_api` in 40f4d9d) |

### Container Wrappers (`tvm_ffi.container`)

| Name | Signature | Description |
|------|-----------|-------------|
| `Array` | `class Array(Object, Sequence)` | `__init__(input_list)`, `__getitem__`, `__len__`; delegates to ffi.Array* |
| `Map` | `class Map(Object, Mapping)` | `__init__(input_dict)`, `__getitem__`, `__contains__`, `keys()`, `values()`, `items()` |
| `getitem_helper` | `def getitem_helper(obj, elem_getter, length, idx)` | Handles slice/negative index for Array |

### Module System (`tvm_ffi.module`)

| Name | Signature | Description |
|------|-----------|-------------|
| `Module` | `class Module(Object)` | `get_function(name, query_imports)`, `import_module`, `write_to_file`, `inspect_source`, `__getitem__`, `__call__` (delegates to `self.main`), `__getattr__`; `entry_name = "main"` |
| `Module.get_function_metadata` | `def get_function_metadata(name: str, query_imports: bool = False) -> dict[str, Any] \| None` | Get metadata dict (parsed from JSON) for exported function; includes `type_schema` (since ac7bf68) |
| `Module.get_function_doc` | `def get_function_doc(name: str, query_imports: bool = False) -> str \| None` | Get docstring for exported function (since ac7bf68) |
| `system_lib` | `def system_lib(symbol_prefix="") -> Module` | Get/create system library singleton |
| `load_module` | `def load_module(path: str \| PathLike, keep_module_alive: bool = True) -> Module` | Load shared library module; `keep_module_alive` prevents premature GC (since 8dcaec1f; PathLike since 53a7fe9) |
| `tvm_ffi.libinfo.load_lib_module` | `def load_lib_module(name: str) -> Module` | Find library by basename + load with keep_alive (since f255650b) |

### Library Discovery (`tvm_ffi.libinfo`)

| Name | Signature | Description |
|------|-----------|-------------|
| `find_libtvm_ffi` | `def find_libtvm_ffi() -> str` | Find shared library path |
| `find_include_path` | `def find_include_path() -> str` | Find C++ header directory |
| `find_dlpack_include_path` | `def find_dlpack_include_path() -> str` | Find DLPack header directory |
| `find_cmake_path` | `def find_cmake_path() -> str` | Find cmake config directory |
| `find_source_path` | `def find_source_path() -> str` | Find packaged source root |
| `find_cython_lib` | `def find_cython_lib() -> str` | Find compiled Cython extension |
| `get_dll_directories` | `def get_dll_directories() -> list[str]` | Search paths for shared libraries |
| `find_python_helper_include_path` | `def find_python_helper_include_path() -> str` | Locate `tvm_ffi_python_helpers.h` (added in f81ab9c) |
| `include_paths` | `def include_paths() -> list[str]` | All include paths needed for FFI-related C++ compilation (added in f81ab9c) |
| `find_library_by_basename` | `def find_library_by_basename(base: str) -> str` | Generalized shared library finder for `libtvm_ffi_*` sibling libraries (added in da7007f) |

### CLI Tool (`tvm_ffi.config`)

| Name | Signature | Description |
|------|-----------|-------------|
| `__main__` | `def __main__()` | CLI with --includedir, --dlpack-includedir, --cmakedir, --sourcedir, --libfiles, --libdir, --libs, --cython-lib-path, --cflags, --cxxflags, --ldflags (--cflags added in c100338) |

### Stub Generation CLI (`tvm-ffi-stubgen`, since ea02e64, refactored in 1af6d9f)

| Name | Signature | Description |
|------|-----------|-------------|
| `tvm-ffi-stubgen` | CLI entry point | Registered as `tvm_ffi.stub.cli:__main__` in `pyproject.toml` (module path since 1af6d9f) |
| `tvm_ffi.stub.file_utils` | module | File parsing utilities for stubgen markers (since 1af6d9f) |
| `tvm_ffi.stub.consts` | module | Directive and format constants (since 1af6d9f) |
| `tvm_ffi.stub.analysis` | module | Type information extraction from C++ reflection registry (since 1af6d9f) |
| `tvm_ffi.stub.codegen` | module | Code generation for inline stubs (since 1af6d9f) |
| `tvm_ffi.stub.cli` | module | CLI entry point with arg parsing (since 1af6d9f) |
| `tvm_ffi.stub.utils` | module | Shared utilities including `__all__` generation (since 1af6d9f) |
| `Options` | dataclass | `dlls: list[str]`, `indent: int`, `files: list[str]`, `suppress_print: bool` |
| `StubConfig` | dataclass | `name: str`, `indent: int`, `lineno: int`, `ty_map: dict[str, str]` |
| `_generate_global` | `(stub, global_func_tab, opt) -> list[str]` | Generate function stubs for `global/<prefix>` blocks |
| `_generate_object` | `(stub, opt) -> list[str]` | Generate field/method stubs for `object/<type_key>` blocks |
| `generate_all_list` | `(symbols: list[str]) -> str` | Generate formatted `__all__` assignment (since 92e150b) |

### Kwargs Wrapper Utilities (`tvm_ffi.utils.kwargs_wrapper`, since 3115b237)

| Name | Signature | Description |
|------|-----------|-------------|
| `make_kwargs_wrapper` | `(target_func, arg_names, arg_defaults, kwonly_names, kwonly_defaults, prototype) -> Callable` | Code-gen wrapper adding kwargs support to positional-only functions |
| `make_kwargs_wrapper_from_signature` | `(target_func, signature, prototype, exclude_arg_names) -> Callable` | Extract params from `inspect.Signature` and generate wrapper |
| `MISSING` | sentinel object | Sentinel for unset default values in generated code |

### Conversion (`tvm_ffi.convert`)

| Name | Signature | Description |
|------|-----------|-------------|
| `convert` | `def convert(value: Any) -> Any` | Auto-convert Python objects to FFI values |

### Testing (`tvm_ffi.testing`)

| Name | Signature | Description |
|------|-----------|-------------|
| `create_object` | `def create_object(type_key: str, **kwargs) -> Object` | Create objects by reflection for testing |

### Dataclasses (`tvm_ffi.dataclasses`)

| Name | Signature | Description |
|------|-----------|-------------|
| `c_class` | `def c_class(type_key: str, init: bool = True) -> Callable[[type], type]` | `@dataclass_transform` decorator for FFI-backed dataclasses (since e98b94e) |
| `field` | `def field(*, default=MISSING, default_factory=MISSING, init: bool = True) -> _FieldValue` | Field descriptor factory; `init=False` support since daeb235 |
| `Field` | `class Field` | Descriptor class with `__slots__ = ("default_factory", "init", "name")` |
| `MISSING` | `_MISSING_TYPE` | Sentinel for unset defaults |

## Rust API

(Not applicable -- see other API indexes for Rust bindings.)

## Deprecated / Renamed

| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `register_func` | `register_global_func` | 40f4d9d | Clear non-abbreviated naming |
| `_init_api` | `init_ffi_api` | 40f4d9d | Public API, no underscore prefix |
| `ObjectGeneric` | `ObjectConvertible` | 40f4d9d | Clearer semantics |
| `NDArray` | `Tensor` | 3a551d8 | Align with torch.Tensor |
| `Device.device_id` | `Device.index` | 40f4d9d | Torch-aligned naming |
| `Device.device_type` (int property) | `Device.type` (str) + `Device.dlpack_device_type()` (int) | 40f4d9d | Torch-aligned naming |
| `cpu()`, `cuda()`, etc. | `device("cuda", 0)` | 40f4d9d | Removed convenience constructors |
| `String`, `Bytes` (top-level `__all__`) | Still accessible via `tvm_ffi.core` | 40f4d9d | Removed from public exports |
| `DataTypeCode` (top-level) | `tvm_ffi._dtype.DataTypeCode` | 40f4d9d | Removed from public exports |
| `ModulePropertyMask` (top-level) | `tvm_ffi.module.ModulePropertyMask` | 40f4d9d | Removed from public exports |
| `from_dlpack(..., required_alignment=8, required_contiguous=True)` | `from_dlpack(..., require_alignment=0, require_contiguous=False)` | 1b824e8 | Relaxed defaults + param rename |
| `make_args` / `FuncCall` / `FuncCall3` | `TVMFFIPyFuncCall` / `TVMFFIPyCallManager` | 38d2cda | isinstance chain replaced by C++ type-dispatch |
| `_FUNC_CONVERT_TO_OBJECT` | `TVMFFIPyArgSetterTuple_` / `Map_` | 043d9f6 | Nested container conversion moved to Cython setters |
| `__c_dlpack_exporter__` | `__c_dlpack_from_pyobject__` | 4dee97f | Clarify data-flow direction |
| `__c_dlpack_importer__` | `__c_dlpack_to_pyobject__` | 4dee97f | Clarify data-flow direction |
| `DLPackPyObjectExporter` | `DLPackFromPyObject` | 4dee97f | Typedef renamed |
| `DLPackPyObjectImporter` | `DLPackToPyObject` | 4dee97f | Typedef renamed |
| `__c_dlpack_from_pyobject__`, `__c_dlpack_to_pyobject__`, `__c_dlpack_tensor_allocator__` | `__c_dlpack_exchange_api__` | 22a7894 | Three attributes replaced by single `DLPackExchangeAPI` struct pointer |
| `TVMFFIPyArgSetterDLPackCExporter_` | `TVMFFIPyArgSetterDLPackExchangeAPI_` | 22a7894 | Renamed to match struct-based protocol |
| `__tvm_ffi_tensor__` | `__tvm_ffi_object__` | 8873700 | Generalized from tensor-only to any Object |
| `PyNativeObject.__tvm_ffi_object__` (attribute) | `PyNativeObject._tvm_ffi_cached_object` | 8873700 | Dunder reserved for protocols, not data |
| `__init_tvm_ffi_object_by_constructor__` | `__init_cached_object_by_constructor__` | 8873700 | Internal method rename |
| `TVMFFIPyArgSetterFFITensorCompatible_` | `TVMFFIPyArgSetterFFIObjectCompatible_` | 8873700 | Setter renamed to match generalized protocol |
| `_ffi_api.pyi` (stub file) | Inline stubs in `_ffi_api.py` | ea02e64 | Hand-written stub replaced by `tvm-ffi-stubgen` |
| `OBJECT_TYPE` | `TYPE_INDEX_TO_INFO` + `TYPE_INDEX_TO_CLS` | 53b2e00 | Split into metadata + fast-path lists |
| `OBJECT_INDEX` | (removed) | c86235c | Unused reverse-lookup dict |
| `_add_class_attrs_by_reflection` | `_add_class_attrs` (in `registry.py`) | 53b2e00 | Moved from Cython to pure Python, consumes TypeInfo |
| `_parse_traceback` | `_parse_backtrace` | 6f020c1 | Backtrace rename |
| `_with_append_traceback` | `_with_append_backtrace` | 6f020c1 | Backtrace rename |
| `_TRACEBACK_TO_STR` | `_TRACEBACK_TO_BACKTRACE_STR` | 6f020c1 | Backtrace rename |
| `_WITH_APPEND_TRACEBACK` | `_WITH_APPEND_BACKTRACE` | 6f020c1 | Backtrace rename |
| `Error.traceback` (property) | `Error.backtrace` | 6f020c1 | Backtrace rename |
| `Error.update_traceback()` | `Error.update_backtrace()` | 6f020c1 | Backtrace rename |
| `__create__` (reflection method) | `__ffi_init__` | c01dadf | Canonical constructor name |
| `tvm_ffi_pyobject_deleter` (Cython) | `TVMFFIPyObjectDeleter` (C++) | 22c049b | Free-threaded Python support |
| `FieldInfoTrait` | `InfoTrait` | 28fe3cc | Generalized for fields and methods |
| `_lookup_type_info_from_type_key` | `_lookup_or_register_type_info_from_type_key` | 98cb8af | Now always registers into global registries |
| `_set_type_cls(type_index, type_cls)` | `_set_type_cls(type_info, type_cls)` | 98cb8af | Takes TypeInfo instead of int |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 2d41a51 | `2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` | Full Python package: Cython bindings, packaging, wrappers, tests |
| 38d2cda | `2025-09-11-38d2cdaa.md` | Type-dispatch call manager, cached DLPack, arg setter factory |
| f81ab9c | `2025-09-12-f81ab9c2.md` | DLPack fast path, env allocator, per-function GIL, Function cdef class |
| 043d9f6 | `2025-09-13-043d9f64.md` | String/Bytes C API, nested container Cython setters |

(plus 2 supporting commits: 4dee97f rename, 1ce0f6f inline module)
| cc93373 | `2025-09-14-cc93373b344715422d158d14b5502d7c673a0153.md` | `bytearray_to_bytes` Cython helper refactor |
| af82dbb | `2025-09-14-af82dbb9a4cbb31f1ac9dc38195eaae747c31bcb.md` | Reflection `__name__` fix for undocumented methods |
| 3197cd0 | `2025-09-15-3197cd0949ae9bb9a41eb5a429a4b1519d061db4.md` | StreamContext, TorchStreamContext, use_raw_stream, use_torch_stream |
| c100338 | `2025-09-14-c100338de52825097ddc44bbac3d03a92f45b33a.md` | `--cflags` CLI flag, C example, v_char32 removal |
| 8f4e044 | `2025-09-17-8f4e044a90ff8a3db15742274f2c7df435142b04.md` | ANN enforcement, type annotations, StreamContext `__enter__` fix |
| 53b2e00 | `2025-09-19-53b2e00ef90a34f2dfa79014877dc6ca53e78c0f.md` | TypeInfo metadata model, TYPE_INDEX_TO_INFO, _add_class_attrs |
| 6f020c1 | `2025-09-22-6f020c11c304ef11ac5d0dad904d41ebe42a3ffd.md` | Backtrace rename, reversed storage, TVMFFIBacktraceUpdateMode |
| e98b94e | `2025-09-21-e98b94e118dfa5ac4bcf3764a8b1695afee3d596.md` | c_class decorator, __ffi_init__ convention |

| 28fe3cc | `2025-10-03-28fe3cc.md` | TypeSchema/Metadata, get_global_func_metadata, InfoTrait rename |
| 22c049b | `2025-10-08-22c049b.md` | Free-threaded Python, TVMFFIPyObjectDeleter, OpaquePyObject fix |
| a153647 | `2025-10-10-a153647.md` | get_raw_stream Python API |
| b64b46f | `2025-10-10-b64b46f.md` | Function.__from_extern_c__ |
| f6303b2 | `2025-10-11-f6303b2.md` | Function.__from_mlir_packed_safe_call__ |

(plus 9 supporting commits: 929effa, 53ffe5e, 785e8ca, c86235c, d77606a, 40e9c83, df58a05, 035975a, 8e471b0)

| 22a7894 | `2025-10-11-22a78943b783.md` | DLPackExchangeAPI struct, `__c_dlpack_exchange_api__` replaces three attrs |
| ea02e64 | `2025-10-12-ea02e646.md` | `tvm-ffi-stubgen` CLI tool |
| b0537f0 | `2025-10-13-b0537f04.md` | `__cuda_stream__` protocol, hasattr class-level fix |
| 550e92f | `2025-10-13-550e92fc.md` | `TVMFFIErrorSetRaisedFromCStrParts` C API |
| 8873700 | `2025-10-14-8873700a.md` | `__tvm_ffi_object__` protocol, `_tvm_ffi_cached_object` rename |
| da7007f | `2025-10-14-da7007fd.md` | `find_library_by_basename`, testing library split |
| 9829dec | `2025-10-15-9829dec9.md` | `DLPackTensorAllocator` -> `DLPackManagedTensorAllocator` |
| f679fe5 | `2025-10-15-f679fe54.md` | `TVMFFIEnvTensorAlloc`, `Tensor::FromEnvAlloc`, env API renames |
| 42e0612 | `2025-10-16-42e06128.md` | `__tvm_ffi_opaque_ptr__` protocol |
| 3373853 | `2025-10-16-33738534.md` | Forward-compat guard for `__c_dlpack_exchange_api__` |

(plus ~43 supporting commits in Group 15: version bumps, CI/build, doc, MSVC fixes, cmake config)

| 0729193 | `2025-10-19-0729193f.md` | Auto-generate `__init__` for @register_object classes from `__ffi_init__` |
| 5e648f0 | `2025-10-20-5e648f05.md` | `__dlpack_data_type__` protocol, `dtype.from_dlpack_data_type()` |
| 0f8bf9f | `2025-10-20-0f8bf9fc.md` | `__dlpack_device__` protocol for device ingestion |
| e10d1ed | `2025-10-20-e10d1ed7.md` | Migrate docstrings from `.pyi` to Cython `.pxi` for Sphinx autodoc |
| 53a7fe9 | `2025-10-21-53a7fe9f.md` | `load_module(path: str | PathLike)` |
| ac63fb9 | `2025-10-26-ac63fb9b.md` | setuptools_scm git-based versioning |

(plus 14 supporting commits in Group 16: docs polish, Rust docs, version API, libinfo fix, README updates)

| 0ee6444 | `2025-11-01-0ee644421cae936c459a3e0ff41863cf07259647.md` | `register_object` TypeVar `_T` preserves decorated class type |
| 227bdd0 | `2025-11-04-227bdd0c5c70f186fac3b3c99427a032424ed58e.md` | `register_error("MemoryError", MemoryError)` added |

(plus 4 supporting commits in Group 17: 9574e9d + b9a2b92 ml_dtypes compat guard, 9c0b869 docstring examples, 276c6f6 Sphinx author)

| c1df05f | `2025-11-08-c1df05f3.md` | `__tvm_ffi_as_int__`/`__tvm_ffi_as_float__` number protocols |
| 4edf4f3 | `2025-11-08-4edf4f30.md` | `_lookup_type_attr` Cython function |
| 8fcd924 | `2025-11-09-8fcd9245.md` | `get_registered_type_keys()` Python API |
| 408aa78 | `2025-11-14-408aa78c.md` | Dtype literal constants (`tvm_ffi.float32`, etc.) |
| 1af6d9f | `2025-11-15-1af6d9f9.md` | Stubgen staged pipeline refactor + `import` directive |
| 92e150b | `2025-11-16-92e150b9.md` | Stubgen `__all__` generation |

(plus 13 supporting commits in Group 18: e6a85e9 nullptr fix, 6c85e562 cuda stream, 5a877494 dtype, 82bc7b63 DLTensor*, 6897a5f5 TypeInfo, 4628f06b module-name, ae346ec9 bool dtype, d6bfb45e DLPack, 752ac8ed ROCm, 7a355c77 FunctionObj, dd3de074 lint, 9a153994/74f53c57/7cd2e500 build, db53ce4f docs)

| ac7bf68 | `2025-11-20-ac7bf68058b392c3a8475619016fde48bd08334b.md` | Module.get_function_metadata, Module.get_function_doc, build_inline docstring support |

(plus 1 supporting commit: a999de6 clang-tidy fix for metadata tests)

| 3115b237 | `2025-12-04-3115b237d43fa2c7a24157ec88e1a9f9ec403900.md` | kwargs_wrapper module: make_kwargs_wrapper, make_kwargs_wrapper_from_signature |
| 3dd7a817 | `2025-12-04-3dd7a8173363bdf79806610818121e83e99b3b56.md` | Generic value protocol: __tvm_ffi_as_object__ for extensible Python-to-FFI conversion |
| 6887892d | `2025-12-06-6887892d888e0f69df8bd0a8167c5ebe98873a0b.md` | importlib.metadata-based DSO discovery (replaces __file__-based paths) |
| 8dcaec1f | `2025-12-11-8dcaec1fb47bf7873b105385b7d2808d51f6b342.md` | load_module keep_module_alive parameter |
| 6ccbdb6b | `2025-12-12-6ccbdb6b48ca0bcf44db61cb705a960d359d6cf6.md` | Remove reference cycle in error handling for faster GC |
| a7ebc65f | `2025-12-18-a7ebc65f14eecd1592d407f1d5c952c65603a9aa.md` | device() accepts numpy/torch scalar as device id |

(plus 15 supporting commits: version bumps, lint, CI, test fixes, torch-c-dlpack updates)
