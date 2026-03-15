---
scope: "python-package"
---
# API Index: Python Package (`tvm_ffi`)

**Scope**: Public Python API surface of the `tvm_ffi` package, including the `tvm-ffi-config` CLI and the CMake config-mode package.
**Design docs**: [0014-python-package.md](../designs/0014-python-package.md), [0015-python-ffi-call-dispatch.md](../designs/0015-python-ffi-call-dispatch.md)
**ADRs**: [0014-standalone-python-package.md](../ADRs/0014-standalone-python-package.md), [0016-type-cached-ffi-dispatch.md](../ADRs/0016-type-cached-ffi-dispatch.md)
**See also**: [0009-python-ffi-call-dispatch.md](0009-python-ffi-call-dispatch.md) (API index for the type-cached dispatch system)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `TVMFFIBacktrace` | function | `(const char* filename, int lineno, const char* func, int cross_ffi_boundary) -> const TVMFFIByteArray*` | Capture C++ stack backtrace (renamed from `TVMFFITraceback`); stores most-recent-call-first |
| `DetectFFIBoundary` | inline function | `(const char* filename, const char* symbol) -> bool` | Returns true if symbol is `TVMFFIFunctionCall` (the boundary frame) |
| `ShouldExcludeFrame` | inline function | `(const char* filename, const char* symbol) -> bool` | Returns true for internal frames (`tvm::ffi::details::*`, `TVMFFITraceback*`, `TVMFFIErrorSetRaisedFromCStr*`) |
| `TVMFFISegFaultHandler` | function | `(int sig) -> void` | SIGSEGV handler; prints full-stack traceback (`cross_ffi_boundary=1`) and re-raises |
| `TVMFFIInstallSignalHandler` | function | `() -> void` | Installs `TVMFFISegFaultHandler` for SIGSEGV/SIGBUS |
| `tvm_ffi_add_prefix_map` | CMake function | `(target_name, prefix_path)` | Adds `-ffile-prefix-map` for relative paths in tracebacks |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `register_object` | `(type_key: str \| None = None) -> Callable[[_T], _T]` where `_T = TypeVar("_T", bound=type)` | Register Python class for FFI object type; preserves decorated class type identity (0ee6444) |
| `register_global_func` | `(func_name: str, f=None, override=False) -> Function` | Register a Python callable as a global packed function (was `register_func`) |
| `get_global_func` | `(name: str, allow_missing=False) -> Function \| None` | Look up a global function by name |
| `list_global_func_names` | `() -> list[str]` | Get all registered global function names |
| `remove_global_func` | `(name: str) -> None` | Remove a global function by name |
| `init_ffi_api` | `(namespace: str, target_module_name=None) -> None` | Bulk-import registered functions matching namespace prefix into a module (was `_init_api`) |
| `convert` | `(value) -> Any` | Convert Python value to FFI-compatible type |
| `register_error` | `(name_or_cls: str \| type, cls: type = None) -> type` | Register error class for FFI error handler mapping |
| `load_module` | `(path: str \| PathLike, keep_module_alive: bool = True) -> Module` | Load a shared library as a Module; `keep_module_alive` registers in ModuleGlobals singleton (8dcaec1); accepts PathLike objects (af898a2) |
| `system_lib` | `(symbol_prefix: str = "") -> Module` | Get the system-wide library module singleton |
| `from_dlpack` | `(ext_tensor, *, require_alignment=0, require_contiguous=False) -> Tensor` | Create Tensor from DLPack tensor (relaxed defaults; was NDArray) |
| `dtype` | `(type_str: str) -> DLDataType` | Parse dtype string to DLDataType |
| `device` | `(device_type: str \| int, index: Integral \| None = None) -> Device` | Create a Device object; index widened to `numbers.Integral` + `.item()` fallback for numpy/torch scalars (a7ebc65) |
| `DLDeviceType` | IntEnum | `kDLCPU=1, kDLCUDA=2, kDLCUDAHost=3, kDLOpenCL=4, kDLVulkan=7, kDLMetal=8, kDLVPI=9, kDLROCM=10, kDLROCMHost=11, kDLExtDev=12, kDLCUDAManaged=13, kDLOneAPI=14, kDLWebGPU=15, kDLHexagon=16` | DLPack device type enum (extracted from Device) |
| `Module` | class (registered `"ffi.Module"`) | Runtime module with `get_function`, `import_module`, `__getattr__` dispatch |
| `Module.get_function` | `(self, name: str, query_imports=False) -> Function` | Get a function from the module by name |
| `Module.import_module` | `(self, module: Module) -> None` | Add module to import list |
| `Module.main` | attribute | Get the `__tvm_ffi_main` entry function (replaced `Module.entry_func`) |
| `Module.kind` | `@property -> str` | Module kind string (e.g., `"library"`) |
| `Module.inspect_source` | `(self, fmt="") -> str` | Get source code if available |
| `Module.get_property_mask` | `(self) -> int` | Get property bitmask |
| `Module.write_to_file` | `(self, file_name: str, fmt="") -> None` | Write module to file |
| `ModulePropertyMask` | IntEnum | `BINARY_SERIALIZABLE=0b001`, `RUNNABLE=0b010`, `COMPILATION_EXPORTABLE=0b100` (removed from top-level `tvm_ffi` re-exports; access via `tvm_ffi.module.ModulePropertyMask`) |
| `Array` | class (registered `"ffi.Array"`) | Immutable sequence container |
| `Map` | class (registered `"ffi.Map"`) | Immutable mapping container |
| `Shape` | class | Tuple subclass for shape objects |
| `Tensor` | class | DLPack tensor (renamed from `NDArray`; registered `"ffi.Tensor"`) |
| `Object` | class | Base class for all FFI objects |
| `Function` | class | Packed function wrapper; `release_gil: bool` property (default True) controls GIL release |
| `String` | class | FFI string type |
| `Bytes` | class | FFI bytes type |
| `Device` | class | Device descriptor; `type -> str`, `index -> int`, `dlpack_device_type() -> int` (aligned with torch.device) |
| `ObjectConvertible` | class | Base for types convertible to FFI Object via `asobject()` (was `ObjectGeneric`) |
| `TracebackManager` | class | Parses C++ traceback strings and synthesizes Python frame objects |
| `TracebackManager.append_traceback` | `(self, tb: TracebackType, filename: str, lineno: int, func: str) -> TracebackType` | Append a synthetic C++ frame to a Python traceback |
| `OpaquePyObject` | class (Cython) | `pyobject() -> object` | Wraps arbitrary Python objects as FFI objects; type_index=kTVMFFIOpaquePyObject(74) |
| `tvm_ffi.cpp.load_inline` | `(name: str, *, cpp_sources=None, cuda_sources=None, functions=None, extra_cflags=None, extra_cuda_cflags=None, extra_ldflags=None, extra_include_paths=None, build_directory=None) -> Module` | JIT-compile inline C++/CUDA source; now delegates to `build_inline` + `load_module` (4fcf94f) |
| `tvm_ffi.cpp.build_inline` | `(name: str, *, cpp_sources=None, cuda_sources=None, functions=None, extra_cflags=None, extra_cuda_cflags=None, extra_ldflags=None, extra_include_paths=None, build_directory=None) -> str` | Compile-only variant; returns path to compiled .so/.dll (4fcf94f) |
| `tvm_ffi.cpp.build` | `(name: str, *, cpp_files=None, cuda_files=None, extra_cflags=None, extra_cuda_cflags=None, extra_ldflags=None, extra_include_paths=None, build_directory=None) -> str` | Compile C++/CUDA source files into shared library; returns .so/.dll path; user must use `TVM_FFI_DLL_EXPORT_TYPED_FUNC` manually (5569e449) |
| `tvm_ffi.cpp.load` | `(name: str, *, cpp_files=None, cuda_files=None, extra_cflags=None, extra_cuda_cflags=None, extra_ldflags=None, extra_include_paths=None, build_directory=None) -> Module` | Build + load C++/CUDA source files; wraps `build()` + `load_module()` (5569e449) |
| `tvm_ffi.__version__` | `str` | Package version string; derived from git tags via `setuptools_scm` (ac63fb9); fallback `"0.0.0.dev0"` |
| `tvm_ffi.__version_tuple__` | `tuple` | Structured version tuple `(major, minor, micro, pre, dev)` from `_version.py` (ac63fb9) |
| `dtype.from_dlpack_data_type` | `(dltype_data_type: tuple[int, int, int]) -> dtype` | Static factory: construct dtype from DLPack `(type_code, bits, lanes)` tuple (5e648f0) |
| `StreamContext` | class | `__init__(self, device: Device, stream: int \| c_void_p)`, `__enter__() -> StreamContext`, `__exit__(*args) -> None` | Context manager for per-thread/per-device FFI environment stream; saves/restores via `TVMFFIEnvSetStream` |
| `TorchStreamContext` | class | `__init__(self, context: Optional[Any])`, `__enter__() -> TorchStreamContext`, `__exit__(*args) -> None` | Wraps torch stream/graph context; enters torch context first, then creates StreamContext from `torch.cuda.current_stream()` |
| `use_raw_stream` | `(device: Device, stream: int \| c_void_p) -> StreamContext` | Create a StreamContext for a raw device stream handle |
| `use_torch_stream` | `(context: Optional[Any] = None) -> TorchStreamContext` | Create a TorchStreamContext; accepts `torch.cuda.stream(s)` or `torch.cuda.graph(g)`; `None` captures current stream |
| `get_raw_stream` | `(device: Device) -> int` | Query current FFI environment stream handle for given device (added 22c049b) |
| `get_global_func_metadata` | `(name: str) -> dict[str, Any]` | Retrieve metadata JSON for a registered global function |
| `TypeSchema` | dataclass | `origin: str`, `args: tuple[TypeSchema, ...]`; `from_json_obj(dict)$`, `from_json_str(str)$`, `repr(ty_map=None) -> str` | Structured representation of JSON type schemas from C++ reflection |
| `Function.__from_extern_c__` | `(c_symbol: int, *, keep_alive_object=None) -> Function` | Construct Function from TVMFFISafeCallType C function pointer |
| `Function.__from_mlir_packed_safe_call__` | `(mlir_packed_symbol: int, *, keep_alive_object=None) -> Function` | Construct Function from MLIR `void(*)(void**)` packed convention |
| `tvm_ffi.utils.FileLock` | class | `__init__(lock_file_path: str)`, `acquire() -> bool` (returns False if already held by same instance, 021d78d), `blocking_acquire(timeout=None, poll_interval=0.1) -> bool` (raises RuntimeError if already held, 021d78d), `release() -> None`, `__enter__/__exit__` | Cross-platform advisory file lock (fcntl/msvcrt); re-entrant acquire guarded |
| `register_error` | `(name_or_cls: str \| type, cls: type = None) -> type` | Map C++ error kind string to Python exception class; pre-registered: RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, AssertionError, MemoryError (00a9ad7) |
| `tvm_ffi.libinfo.load_lib_ctypes` | `(package: str, target_name: str, mode: str) -> ctypes.CDLL` | Load shared library via importlib.metadata RECORD discovery + ctypes.CDLL (6887892) |
| `tvm_ffi.libinfo.load_lib_module` | `(package: str, target_name: str, keep_module_alive: bool = True) -> Module` | Load shared library as FFI Module via importlib.metadata; one-liner for downstream packages (f255650) |
| `tvm_ffi.LIB` | `ctypes.CDLL` | Loaded shared library handle; replaces `tvm_ffi.base._LIB` (6887892) |
| `tvm_ffi.utils.kwargs_wrapper.make_kwargs_wrapper` | `(target_func, arg_names, arg_defaults=(), kwonly_names=None, kwonly_defaults=None, prototype=None) -> Callable` | Codegen wrapper adding kwargs to positional-only FFI functions (3115b23) |
| `tvm_ffi.utils.kwargs_wrapper.make_kwargs_wrapper_from_signature` | `(target_func, signature: inspect.Signature, prototype=None, exclude_arg_names=None) -> Callable` | Convenience wrapper from inspect.Signature; `exclude_arg_names` skips params like `self` (6bc1a8e) |
| `tvm_ffi.utils.kwargs_wrapper.MISSING` | sentinel | Sentinel for "argument not passed" in generated wrappers (3115b23) |

## CLI: `tvm-ffi-config`
| Flag | Output |
|------|--------|
| `--includedir` | Path to C++ headers (`include/`) |
| `--dlpack-includedir` | Path to DLPack headers |
| `--cmakedir` | Path to CMake config directory |
| `--libdir` | Directory containing `libtvm_ffi` shared library |
| `--libfiles` | Full path to shared library file |
| `--sourcedir` | Package source root |
| `--cython-lib-path` | Path to Cython extension `.so` |
| `--cflags` | `-I<include> -I<dlpack>` (C compilation, no `-std=c++17`) |
| `--cxxflags` | `-I<include> -I<dlpack> -std=c++17` |
| `--ldflags` | `-L<libdir>` (Unix only) |
| `--libs` | `-ltvm_ffi` (Unix) or `.lib` path (Windows) |

## CMake Targets (via `find_package(tvm_ffi)`)
| Target | Kind | Description |
|--------|------|-------------|
| `tvm_ffi::header` | INTERFACE IMPORTED | Header-only; provides include dirs + C++17 (renamed from `tvm_ffi_header` in a1cb746) |
| `tvm_ffi::shared` | SHARED IMPORTED | Full library; provides include dirs + linked `libtvm_ffi` (renamed from `tvm_ffi_shared` in a1cb746) |

## CMake Functions (via `find_package(tvm_ffi)`)
| Function | Signature | Description |
|----------|-----------|-------------|
| `tvm_ffi_configure_target` | `(target [LINK_SHARED ON\|OFF] [LINK_HEADER ON\|OFF] [DEBUG_SYMBOL ON\|OFF] [MSVC_FLAGS ON\|OFF] [STUB_DIR <dir>] [STUB_INIT ON\|OFF] [STUB_PKG <pkg>] [STUB_PREFIX <prefix>])` | Single-call integration for downstream targets: links headers/shared lib, prefix map, dsymutil, MSVC flags, optional post-build stubgen (added ccd19f8) |
| `tvm_ffi_install` | `(target [DESTINATION <dir>])` | Platform-aware install helper; installs Apple dSYM bundles (added ccd19f8) |
| `tvm_ffi_add_prefix_map` | `(target_name, prefix_path)` | Adds `-ffile-prefix-map` for reproducible builds |
| `tvm_ffi_add_apple_dsymutil` | `(target_name)` | Post-build dsymutil on Apple; no-op elsewhere |
| `tvm_ffi_add_msvc_flags` | `(target_name)` | MSVC-specific definitions and flags |

## Dataclasses API (`tvm_ffi.dataclasses`)
| Name | Signature | Description |
|------|-----------|-------------|
| `c_class` | `(type_key: str, init: bool = True) -> Callable[[type], type]` | Dataclass-style decorator binding Python class to C++ type via reflection |
| `field` | `(*, default=MISSING, default_factory=MISSING, init: bool = True) -> _FieldValue` | Field descriptor for `@c_class`; mirrors `dataclasses.field` |
| `Field` | class | `__slots__ = ("default_factory", "init", "name")` | Field metadata container |
| `MISSING` | sentinel | Sentinel for unset default values |

## Type Introspection API (from `tvm_ffi.core`)
| Name | Signature | Description |
|------|-----------|-------------|
| `TypeInfo` | dataclass | `type_cls, type_index, type_key, fields, methods, parent_type_info` | Type reflection metadata |
| `TypeField` | dataclass | `name, doc, size, offset, frozen, getter, setter, dataclass_field` | Single field descriptor |
| `TypeMethod` | dataclass | `name, doc, func, is_static` | Single method descriptor |
| `_register_object_by_index` | `(type_index: int, type_cls: type) -> TypeInfo` | Register Python class for type index |
| `_lookup_or_register_type_info_from_type_key` | `(type_key: str) -> TypeInfo` | Get/create TypeInfo from C++ reflection; also registers into all three registries (renamed from `_lookup_type_info_from_type_key`, 98cb8af) |
| `_set_type_cls` | `(type_index: int, type_cls: type) -> None` | Deferred class registration |
