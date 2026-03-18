---
scope: "python-bindings"
---
# API Index: Python Bindings (tvm_ffi)

**Scope**: Public Python API surface of the `tvm_ffi` package, including Cython internals, registry, conversion, containers, module, ndarray, error, and dtype.
**Design docs**: [0012-python-bindings.md](../designs/0012-python-bindings.md), [0013-packaging.md](../designs/0013-packaging.md)
**ADRs**: [0008-standalone-python-package.md](../ADRs/0008-standalone-python-package.md), [0015-dlpack-exchange-api-struct.md](../ADRs/0015-dlpack-exchange-api-struct.md)

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `register_object` | `def register_object(type_key: str \| type) -> Callable` | Register Python class for C++ type by type_key; attaches reflected fields/methods |
| `register_global_func` | `def register_global_func(func_name: str, f: Callable = None, override: bool = False) -> Callable` | Register Python callable in global function registry (was `register_func`) |
| `get_global_func` | `def get_global_func(name: str, allow_missing: bool = False) -> Optional[Function]` | Look up global function by name |
| `get_global_func_metadata` | `def get_global_func_metadata(name: str) -> dict[str, Any]` | Get metadata dict (incl. type_schema) for a registered global function |
| `init_ffi_api` | `def init_ffi_api(namespace: str, target_module_name: str = None) -> None` | Auto-populate Python module from C++ global functions with prefix (was `_init_api`) |
| `convert` | `def convert(value: Any) -> Any` | Convert Python objects to FFI values (list->Array, dict->Map, etc.) |
| `register_error` | `def register_error(name_or_cls: str \| type, cls: type = None) -> type` | Register Python exception for C++ error kind mapping |
| `Array` | `class Array(Object, Sequence[T])` | Immutable parameterized array; slice returns `list[T]`, `__add__`/`__radd__` for concatenation |
| `Map` | `class Map(Object, Mapping[K, V])` | Immutable parameterized map; `get()` uses sentinel-based MapGetItemOrMissing FFI call (438f643) |
| `Module` | `class Module(Object)` | Module wrapper with `get_function`, `import_module`, `write_to_file`, `__call__`, `__getattr__` |
| `load_module` | `def load_module(path: str \| PathLike) -> Module` | Load compiled shared library as Module (widened to PathLike, af898a2) |
| `system_lib` | `def system_lib(symbol_prefix: str = "") -> Module` | Get system library module singleton |
| `Function` | `class Function(Object)` | FFI Function wrapper with `__call__`, `release_gil: bool`, `__from_extern_c__`, `__from_mlir_packed_safe_call__` |
| `Function.__from_extern_c__` | `@staticmethod def __from_extern_c__(c_symbol: int, *, keep_alive_object: object \| None = None) -> Function` | Construct Function from raw C function pointer (a153647) |
| `Function.__from_mlir_packed_safe_call__` | `@staticmethod def __from_mlir_packed_safe_call__(mlir_packed_symbol: int, *, keep_alive_object: object \| None = None) -> Function` | Construct Function from MLIR packed safe call pointer (f6303b2) |
| `get_raw_stream` | `def get_raw_stream(device: Device) -> int` | Get current FFI env stream for device (22c049b) |
| `StreamContext` | `class StreamContext` | Context manager for save/restore of FFI env stream via `TVMFFIEnvSetStream` |
| `TorchStreamContext` | `class TorchStreamContext` | Bridge torch.cuda.Stream/CUDAGraph to FFI env stream |
| `use_torch_stream` | `def use_torch_stream(context: Optional[Any] = None) -> TorchStreamContext` | Factory for TorchStreamContext |
| `use_raw_stream` | `def use_raw_stream(device: Device, stream: Union[int, c_void_p]) -> StreamContext` | Factory for raw StreamContext |
| `Object` | `class Object` | Base class for all FFI objects in Python |
| `Shape` | `class Shape(tuple, PyNativeObject)` | Shape object (dual tuple + FFI backing) |
| `Tensor` | `class Tensor(Object)` | Managed tensor with DLPack interop (was `NDArray`) |
| `from_dlpack` | `def from_dlpack(ext_tensor, *, require_alignment=0, require_contiguous=False) -> Tensor` | Create Tensor from DLPack (relaxed defaults since 1b824e8) |
| `OpaquePyObject` | `class OpaquePyObject(Object)` | Wraps arbitrary Python objects as FFI objects. `pyobject() -> object` unwraps with identity preserved |
| `DLDeviceType` | `class DLDeviceType(IntEnum)` | Standalone enum for DLPack device types (kDLCPU=1, kDLCUDA=2, ...) |
| `ObjectConvertible` | `class ObjectConvertible` | Base for objects convertible to FFI Object via `asobject()` (was `ObjectGeneric`) |
| `String` | `class String(Object)` | FFI string object |
| `Bytes` | `class Bytes(Object)` | FFI bytes object |
| `dtype` | `class dtype(str)` | Data type with `type_code`, `bits`, `lanes`, `itemsize`, `with_lanes()`, `from_dlpack_data_type((code,bits,lanes))` (5e648f0) |
| `Device` | `class Device` | Device descriptor with `.type` (str), `.index` (int), `.dlpack_device_type()` (int). Was `device_type`/`device_id` |
| `device` | `def device(device_type: int \| str, index: int = None) -> Device` | Create device handle (params renamed from `dev_type`/`dev_id`) |
| `to_json_graph_str` | `def to_json_graph_str(obj: Any, metadata: dict = None) -> str` | Serialize object graph to JSON |
| `from_json_graph_str` | `def from_json_graph_str(json_str: str) -> Any` | Deserialize object from JSON |
| `TracebackManager` | `class TracebackManager` | Cross-language traceback reconstruction |
| `tvm_ffi.cpp.load_inline` | `def load_inline(name, *, cpp_sources, cuda_sources, functions, ..., build_directory) -> Module` | JIT-compile C++/CUDA source into TVM FFI Module (Linux, macOS, Windows) |
| `tvm_ffi.cpp.build` | `def build(name, *, cpp_files, cuda_files, extra_cflags, ..., build_directory) -> str` | Compile C++/CUDA files into shared library, return path (c897e4c) |
| `tvm_ffi.cpp.load` | `def load(name, *, cpp_files, cuda_files, ..., build_directory) -> Module` | Compile and load as Module (c897e4c); convenience wrapper around build() + load_module() |
| `tvm_ffi.utils.FileLock` | `class FileLock` | Cross-platform advisory file lock (fcntl/msvcrt). Context manager with `acquire()`, `blocking_acquire()`, `release()`. Re-entrant guard: acquire() returns False if already held (021d78d) |
| `tvm_ffi.registry.get_registered_type_keys` | `def get_registered_type_keys() -> Sequence[str]` | Get all registered type keys from global type table (8fcd924) |
| `tvm_ffi.float32` | `dtype("float32")` | Pre-instantiated dtype literal constant (408aa78). 20 total: bool, int8-64, uint8-64, float16/32/64, bfloat16, float8 variants, float4_e2m1fnx2 |
| `DataTypeCode.BOOL` | `BOOL = 6` | DLPack kDLBool type code added to Python enum (ae346ec) |

## CLI Entry Points
| Name | Signature | Description |
|------|-----------|-------------|
| `tvm-ffi-config` | `--includedir \| --cmakedir \| --libdir \| --libs \| --cflags \| ...` | Query installed tvm_ffi paths and flags (--cflags for C-only include flags, c100338) |
| `tvm-ffi-stubgen` | `tvm-ffi-stubgen [--dlls LIB] [--init-pypkg PKG] [--init-lib LIB] [--init-prefix PFX] [--imports MOD] [--verbose] [--dry-run] PATH...` | Generate inline TYPE_CHECKING stubs; --init-* for whole-package bootstrapping (ea02e64, 1af6d9f, 92e150b, b58c2e3d). Entry: `tvm_ffi.stub.cli:__main__` |

## Cython Internals (not public, but architecturally important)
| Name | Signature | Description |
|------|-----------|-------------|
| ~~`make_args`~~ | Removed (38d2cdaa) | Replaced by `TVMFFIPyCallManager` + per-type `TVMFFIPyArgSetter` dispatch |
| `TVMFFIPyCallStack` | C++ class in `tvm_ffi_python_helpers.h` | Thread-local memory arena; owns args_stack and extra_temp_py_objects_stack (3dd7a817) |
| `TVMFFIPyCallManager` | C++ class in `tvm_ffi_python_helpers.h` | Thread-local FFI call dispatcher with `PyTypeObject*`-keyed cache, owns TVMFFIPyCallStack, GIL release |
| `TVMFFIPyArgSetterFactory_` | Cython factory function | Maps `PyTypeObject*` to `TVMFFIPyArgSetter` (called once per type per thread) |
| `TVMFFIPyFuncCall` | `int TVMFFIPyFuncCall(factory, func, args, result, ret_code)` | Top-level C entry for FFI function calls |
| `TVMFFIPyConstructorCall` | `int TVMFFIPyConstructorCall(factory, func, args, result, ret_code, parent_ctx)` | Recursive constructor call for nested containers (043d9f6) |
| `make_ret` | `def make_ret(result: TVMFFIAny) -> object` | Convert TVMFFIAny result to Python |
| `TYPE_INDEX_TO_CLS` | `cdef list[type \| None]` | type_index -> Python class (hot-path, replaces OBJECT_TYPE) |
| `TYPE_INDEX_TO_INFO` | `list[TypeInfo \| None]` | type_index -> TypeInfo metadata |
| `TYPE_KEY_TO_INFO` | `dict[str, TypeInfo]` | type_key -> TypeInfo metadata |
| `TypeInfo` | `@dataclass: type_cls, type_index, type_key, type_ancestors, fields, methods, parent_type_info` | Aggregated type reflection metadata |
| `TypeSchema` | `@dataclass(repr=False): origin: str, args: tuple[TypeSchema, ...]` | Parsed JSON type schema with `repr(ty_map)` for custom rendering. No longer frozen (dd4fb0a). Methods: `from_json_obj(dict)`, `from_json_str(str)`, `repr(ty_map=None)` |
| `DLPackExchangeAPI` | C struct with 5 function pointers + version header | Unified DLPack exchange protocol (22a7894). Replaces 3 separate dunders |
| `TVMFFIPyWithGILIfNotFreeThreaded` | RAII class (C++) | GIL guard for free-threaded Python; no-op when Py_GIL_DISABLED (b64b46f) |
| `TVMFFIPyObjectDeleter` | `extern "C" void TVMFFIPyObjectDeleter(void* py_obj) noexcept` | C++ deleter for Python objects held by FFI (b64b46f, replaces Cython `with gil` deleter) |
| `TypeField` | `@dataclass: name, doc, size, offset, frozen, metadata, getter, setter, dataclass_field` | Single reflected field descriptor. `metadata: dict[str, Any]` includes `type_schema` key |
| `TypeMethod` | `@dataclass: name, doc, func, metadata, is_static` | Single reflected method descriptor with `as_callable()`. `metadata: dict[str, Any]` includes `type_schema` key |
| `make_fallback_cls_for_type_index` | `def make_fallback_cls_for_type_index(type_index: int) -> type` | Auto-create fallback class for unregistered C++ type with full reflection |
| `c_class` | `def c_class(type_key: str, init: bool = True) -> Callable[[type], type]` | Dataclass-style decorator for C++ FFI proxies. See [0015-python-dataclasses.md](../designs/0015-python-dataclasses.md) |
| `field` | `def field(*, default=MISSING, default_factory=MISSING, init=True) -> _FieldValue` | Field descriptor for `@c_class` with optional init exclusion |
| `__tvm_ffi_opaque_ptr__` | protocol dunder | `def __tvm_ffi_opaque_ptr__(self) -> int` | Pass opaque void* through FFI as `kTVMFFIOpaquePtr` (42e0612) |
| `__dlpack_data_type__` | protocol dunder | `def __dlpack_data_type__(self) -> tuple[int,int,int]` | Dtype exchange via DLPack tuple `(type_code, bits, lanes)` (5e648f0) |
| `__dlpack_device__` | protocol dunder | `def __dlpack_device__(self) -> tuple[int,int]` | Device exchange (without `__dlpack__`) via `(device_type, device_id)` (0f8bf9f) |
| `__tvm_ffi_int__` | protocol dunder | `def __tvm_ffi_int__(self) -> int` | Custom int value for FFI calls (c1df05f) |
| `__tvm_ffi_float__` | protocol dunder | `def __tvm_ffi_float__(self) -> float` | Custom float value for FFI calls (c1df05f) |
| `__tvm_ffi_value__` | protocol dunder | `def __tvm_ffi_value__(self) -> Any` | Generic value protocol for FFI re-dispatch; supports recursive nesting (3dd7a817) |
| `TYPE_CLS_TO_INFO` | `dict[type, TypeInfo]` | Reverse lookup: Python class -> TypeInfo (6897a5f) |
| `_type_cls_to_type_info` | `def _type_cls_to_type_info(type_cls: type) -> TypeInfo \| None` | Reverse TypeInfo lookup by class (6897a5f) |
| `_lookup_type_attr` | `def _lookup_type_attr(type_index: int, attr_key: str) -> Any` | Per-type attribute lookup via TVMFFIGetTypeAttrColumn C API (4edf4f3) |
| `tvm_ffi.libinfo.load_lib_ctypes` | `def load_lib_ctypes(package: str, target_name: str, mode: str) -> ctypes.CDLL` | Locate and load DSO via importlib.metadata + ctypes (6887892d) |
| `tvm_ffi.libinfo.load_lib_module` | `def load_lib_module(package: str, target_name: str, keep_module_alive: bool = True) -> Module` | Locate and load DSO as Module (f255650b) |
| `tvm_ffi.utils.kwargs_wrapper.make_kwargs_wrapper` | `def make_kwargs_wrapper(target_func, arg_names, arg_defaults=(), kwonly_names=None, kwonly_defaults=None, prototype=None) -> Callable` | Wrap positional-only callable with kwargs via exec() codegen (3115b237, renamed 6bc1a8eb) |
| `tvm_ffi.utils.kwargs_wrapper.make_kwargs_wrapper_from_signature` | `def make_kwargs_wrapper_from_signature(target_func, signature, prototype=None, exclude_arg_names=None) -> Callable` | Convenience: extract args from inspect.Signature (3115b237, 6bc1a8eb) |
| `tvm_ffi.utils.kwargs_wrapper.MISSING` | `object()` sentinel | Identity-compared sentinel for "not passed" vs explicit None (3115b237) |
| `FuncInfo` | `class FuncInfo: schema: NamedTypeSchema, is_member: bool` | Stubgen data class encapsulating function schema; `from_global_name(name)` factory, `gen(ty_map, indent) -> str` (92e150b) |
| `ObjectInfo` | `class ObjectInfo: fields: list[NamedTypeSchema], methods: list[FuncInfo]` | Stubgen data class for object type; `from_type_key(key)` factory, `gen_fields()`/`gen_methods()` (92e150b) |
| `NamedTypeSchema` | `class NamedTypeSchema(TypeSchema): name: str` | TypeSchema with associated name for fields/functions (92e150b) |
| `generate_all` | `def generate_all(code: CodeBlock, names: set[str], opt: Options) -> None` | Stubgen codegen: populate `__all__` block with sorted names (92e150b) |
| `FN_NAME_MAP` | `dict[str, str]` | FFI-to-Python method name mapping, e.g. `{"__ffi_init__": "__c_ffi_init__"}` (92e150b) |
