# Module System

- Doc ID: 007-module-system
- Status: Approved
- Last Updated: 2025-12-29
- Owners: Tianqi Chen

## Overview

The TVM FFI provides a formalized module system for loading and invoking packed
functions from shared libraries and system libraries. `ffi::Module` /
`ffi::ModuleObj` is the central abstraction, with `Library`, `DSOLibrary`, and
`SystemLibrary` as implementation classes. A thread-local `StreamContext`
provides per-device stream management for GPU-aware execution.

All module system code lives in `include/tvm/ffi/extra/` and `src/ffi/extra/`,
gated behind `TVM_FFI_USE_EXTRA_CXX_API=ON`.

## Key Design

### Module class hierarchy

`ffi::ModuleObj` (`538bef4`) is an abstract base class (`ObjectObj` subclass)
with virtual methods for function lookup and module metadata:

```
ObjectObj
  +-- ModuleObj (abstract)
        +-- LibraryModuleObj (DSO/system-lib wrapper)
```

`Module` is the `ObjectRef` wrapper. The `ModulePropertyMask` enum defines
module capability flags: `kBinarySerializable`, `kRunnable`,
`kCompilationExportable`.

### Library abstraction

The `Library` base class (`src/ffi/extra/module_internal.h`) provides a
platform-independent interface for loading symbols from shared libraries:

- `DSOLibrary`: Loads shared objects via `dlopen` (POSIX) or `LoadLibrary`
  (Windows). Registered as `ffi.Module.load_from_file.so`.
- `SystemLibrary`: Provides access to symbols compiled into the running
  binary. Registered as `ffi.SystemLib`.

`LibraryModuleObj` wraps a `Library` instance, providing function lookup via
the `__tvm_ffi_<name>` symbol prefix convention. It also supports loading
serialized binary modules embedded in library files via the
`__tvm_ffi_library_bin` symbol.

### Binary module format

Libraries can embed serialized module data in the `__tvm_ffi_library_bin`
symbol. The format is:

```
<nbytes:u64> <import_tree_indptr:vec<u64>> <import_tree_child_indices:vec<u64>>
<kind:str> [<bytes:str>] ...
```

`ProcessLibraryBin` (in `library_module.cc`) reads this blob via
`BufferInStream` and reconstructs the module import tree.

### Context symbol registry

`ContextSymbolRegistry` manages context-dependent symbols that modules may
register. This supports the pattern where a module's functions need to call
back into the host environment (e.g., for memory allocation or stream
management).

### Stream context

`StreamContext` (`0daaffe`) is a thread-local singleton that tracks the current
GPU stream per device type and device ID. C API functions:

- `TVMFFIEnvSetStream(device_type, device_id, stream, opt_out_original)`:
  Set the current stream for a device, optionally returning the previous stream.
- `TVMFFIEnvGetCurrentStream(device_type, device_id)`:
  Get the current stream for a device.

This enables FFI functions to be stream-aware without per-device API
dependencies. The torch stream context benchmark (`6014406`) demonstrated the
overhead of querying torch's current CUDA stream and validated the integration
path.

### Env C API relocation

Module-related env C API symbols were renamed (`023ea44`) with a `Mod` infix
and relocated from `src/ffi/function.cc` to `src/ffi/extra/env_c_api.cc`:

| Symbol | Purpose |
|--------|---------|
| `TVMFFIEnvModLookupFromImports` | Look up a function in imported modules |
| `TVMFFIEnvModRegisterContextSymbol` | Register a context symbol |
| `TVMFFIEnvModRegisterSystemLibSymbol` | Register a system library symbol |
| `TVMFFIEnvCheckSignals` | Check for pending Python signals |
| `TVMFFIEnvRegisterCAPI` | Register a C API function by name |

`EnvCAPIRegistry` (Python GIL/signal management) was moved to
`src/ffi/extra/env_c_api.cc` to keep the core FFI minimal.

### Function metadata stub

`ModuleObj::GetFunctionMetadata(const String& name)` (`777cf8d`) was added as
a virtual method stub that returns `std::nullopt` by default. A corresponding
non-virtual overload with `query_imports` was added to `Module`. The
`symbol::tvm_ffi_metadata_prefix` constant (`"__tvm_ffi_metadata_"`) was added
for metadata symbol naming. This was added before the ABI freeze to reserve
space in the vtable.

### Library virtual interface update (September 2025)

The `Library` base class was updated (`40e8a51`): `GetSymbol(const char*)`
was changed to `GetSymbol(const String&)`, and a new pure virtual
`GetSymbolWithSymbolPrefix(const String& name)` was added. This method
resolves symbols using the `__tvm_ffi_` prefix convention. The module entry
symbol was standardized to `__tvm_ffi_main` (dropping the trailing `__`).
Both `DSOLibrary` and `SystemLibrary` implement the new virtual method.

### System library symbol lookup fix (September 2025)

A bug in `SystemLibrary` symbol lookup was fixed (`315f4bb`). The system
library now correctly resolves symbols that were previously missed due to
prefix handling issues.

### `load_inline` and `build_inline` (September 2025)

`tvm_ffi.cpp.load_inline` (`83805ec`, `825aeb9`, `1ce0f6f`) provides an
inline C++ module compilation and loading utility, inspired by PyTorch's
`torch.utils.cpp_extension.load_inline`. It generates a ninja build file,
compiles C++ (and optionally CUDA) sources, links a shared library, and
loads it via `tvm_ffi.load_module`. Features include:

- Automatic injection of `TVM_FFI_DLL_EXPORT_TYPED_FUNC` wrappers
- Compiler auto-detection (`_find_compiler`)
- CUDA path discovery (`_find_cuda_path`)
- Hash-based caching for incremental rebuilds
- `FileLock` for concurrent build safety

The API was updated to match the torch interface (`825aeb9`) and further
refined (`1ce0f6f`). A simpler `build_inline` utility (`4fcf94f`) was added
that compiles without loading.

Platform support: Linux (primary), macOS (`4ffbc88`), Windows (`2df07e5`,
`4383b1a`).

### Stream exchange protocol (September 2025)

A generic stream exchange protocol was introduced (`db98729`): any tensor
object that defines a `__tvm_ffi_env_stream__()` method can communicate its
compute stream to TVM FFI during function dispatch. This generalizes the
previously PyTorch-specific stream retrieval.

The Python-side `tvm_ffi.stream` module (`3197cd0`) provides:
- `StreamContext` class for managing device streams
- Context manager integration for scoped stream switching
- `set_stream` / `get_stream` utility functions

### GetFunctionDoc virtual method (October 2025)

`ModuleObj::GetFunctionDoc(const String& name)` (`935a5a0`) was added as a
virtual method that returns `Optional<String>` with the function's
unstructured docstring. A non-virtual overload with `query_imports` was also
added to `Module`. `ffi.ModuleGetFunctionDoc` was registered as a global
function. This separates docstrings from structured metadata (which is
carried in `TVMFFIMethodInfo.metadata`).

### load_module PathLike support (October 2025)

`load_module` was enhanced (`af898a2`) to accept `os.PathLike` objects in
addition to string paths, improving integration with `pathlib.Path`.

### Version Query API (October 2025)

A version query API was added (`f0058a9`) allowing runtime queries of the
TVM FFI library version.

### InvokeExternC utility (October 2025)

`InvokeExternC` (`9186b44`) was introduced as a utility for calling
extern "C" functions from C++ code, simplifying the pattern of invoking
C-level FFI functions from C++ contexts.

### Expose stream methods (October 2025)

The `get_stream` method was exposed (`22c049b`) for querying device streams
from Python.

### Function from extern C (October 2025)

A Cython API was added (`a153647`) to construct `Function` objects from
extern C function pointers, enabling integration with MLIR packed functions
(`f6303b2`).

### File-based build and load (November 2025)

`tvm_ffi.cpp.build()` and `tvm_ffi.cpp.load()` (`c897e4c`) are file-based
companions to `build_inline`/`load_inline` that compile from existing
`.cc`/`.cu` file paths instead of raw source strings. The internal module
`load_inline.py` was renamed to `extension.py` and shared build logic was
refactored into `_build_impl()`. Cache keys for file-based builds use SHA256
of resolved file paths plus compiler flags.

```python
import tvm_ffi
mod = tvm_ffi.cpp.load("my_ext", cpp_files=["src/impl.cc"])
```

### Function metadata embedding (November 2025)

`TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` (`ac7bf68`) is a new compile-time
flag (default 0) that controls the export of type schema JSON and docstrings
alongside DLL-exported functions. When enabled:

- `TVM_FFI_DLL_EXPORT_TYPED_FUNC` emits a `__tvm_ffi__metadata_<name>` symbol
  containing the JSON type schema.
- The new `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC` macro additionally emits a
  `__tvm_ffi__doc_<name>` symbol containing the docstring.

C++ `LibraryModuleObj::GetFunctionMetadata()` and `GetFunctionDoc()` look up
these symbols. Python `Module.get_function_metadata(name)` returns
`dict | None`; `Module.get_function_doc(name)` returns `str | None`.

This enables compiler frameworks (JAX/XLA, MLIR-based) to validate third-party
FFI modules at compile time without invoking the function.

### CUDA kernel launcher utility (November 2025)

A header-only CUDA kernel launcher was added in `include/tvm/ffi/extra/cuda/`
(`d49effd`, `cdfd041`):

- **`cubin_launcher.h`**: `CubinModule` loads CUBIN from byte buffers or files
  via the CUDA driver API. `CubinKernel` wraps `cuFunction` for launching.
  `TVM_FFI_EMBED_CUBIN` / `TVM_FFI_EMBED_CUBIN_GET_KERNEL` macros enable
  compile-time CUBIN embedding.
- **`device_guard.h`**: `CUDADeviceGuard` is an RAII struct that saves the
  current CUDA device, sets a target device, and restores the original on
  scope exit.
- **`base.h`**: Shared `TVM_FFI_CHECK_CUDA_ERROR` macro extracted from
  `cubin_launcher.h`.

Python side:
- `tvm_ffi.cpp.nvrtc.nvrtc_compile()` compiles CUDA source to CUBIN via NVRTC.
- `tvm_ffi.utils.embed_cubin` generates C++ source with embedded CUBIN data.
- `cmake/Utils/EmbedCubin.cmake` provides CMake integration.

Benchmarks show 2.41x lower launch overhead vs Triton for empty kernels.

### Metadata string allocation safety (December 2025)

`TVM_FFI_DLL_EXPORT_TYPED_FUNC` and `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC` were
changed (`dcacb98`) to allocate metadata and doc strings in `libtvm_ffi`
rather than in the extension module. Previously, strings created with
`::tvm::ffi::String(...)` inside an extension module were allocated in the
extension's memory; if the module was unloaded before the string was freed,
the deleter became invalid. The fix uses `TVMFFIStringFromByteArray` to
allocate strings in the main library.

### `keep_module_alive` (December 2025)

`load_module` gained a `keep_module_alive: bool = True` parameter (`8dcaec1`).
When `True` (the default), the loaded module is registered in a C++-side
`ModuleGlobals` singleton inside `libtvm_ffi.so`, preventing Python from
unloading the library while the process runs. This fixes segfaults (#264,
#322) caused by destructors calling into already-unloaded shared libraries.

The `ModuleGlobals` class is a thread-safe `Map<Module, int>` singleton in
`src/ffi/extra/module.cc` with `Add`/`Remove` methods. Registered global
functions: `ffi.ModuleGlobalsAdd`, `ffi.ModuleGlobalsRemove`.

`cpp.load_inline` and `cpp.load` forward the `keep_module_alive` parameter.

This supersedes the earlier workaround (`79894c3`) of forcing `gc.collect()`
before releasing module references.

### `load_lib_module` utility (December 2025)

`tvm_ffi.libinfo.load_lib_module(package, target_name, keep_module_alive=True)`
(`f255650`) finds and loads a downstream shared library as a TVM-FFI `Module`
object. It encapsulates `_find_library_by_basename` + Windows DLL directory
setup + `load_module` into a single well-tested utility, reducing the
downstream packaging boilerplate from ~30 lines to a single call.

### Cubin launcher refactor (December 2025)

The CUDA cubin launcher was refactored (`b16f11f`):
- `tvm_ffi_generate_cubin` CMake function removed; replaced by
  `add_tvm_ffi_cubin(target CUDA src)` using native CMake CUDA support.
- `TVM_FFI_EMBED_CUBIN_FROM_BYTES(name, imageBytes)` macro added for
  registering CUBINs from raw byte arrays (supporting C++23 `#embed` and
  CUDA Toolkit `bin2c`).
- New internal header `include/tvm/ffi/extra/cuda/internal/unified_api.h`
  (206 lines) unifying CUDA/HIP device API.
- `examples/cubin_launcher/embedded_cubin` reorganized into three
  subdirectories: `cpp_embed`, `embed_with_tvm_ffi`, `include_bin2c`.

### Symbol visibility for extension builds (November 2025)

Extension builds now use `-fvisibility=hidden` by default (`7cd2e50`),
preventing symbol leakage from shared libraries built by the extension
compilation pipeline.

### Testing library split (October 2025)

`src/ffi/extra/testing.cc` was split into a separate `libtvm_ffi_testing.so`
shared library (`da7007f`), preventing test-only code from being linked into
production builds.

### `env_context.cc` replaces `stream_context.cc` (September 2025)

`src/ffi/extra/stream_context.cc` was deleted and replaced by
`src/ffi/extra/env_context.cc` (`f81ab9c`). The new file handles stream
context management, the DLPack exporter/importer/allocator registration,
and env API functions in a consolidated location.

## APIs

### C++ API

```cpp
// Module class (include/tvm/ffi/extra/module.h).
class ModuleObj : public ObjectObj {
  virtual Function GetFunction(const String& name,
                               bool query_imports = false) = 0;
  virtual Function GetModuleMetadata();  // stub, returns null
};

class Module : public ObjectRef {
  static Module LoadFromFile(const String& file_name,
                             const String& format = "");
  Function GetFunction(const String& name, bool query_imports = false);
  void Import(Module other);
  void ClearImports();
};
```

### Global functions

| Function name | Description |
|---------------|-------------|
| `ffi.ModuleLoadFromFile` | Load a module from a shared library file |
| `ffi.ModuleGetFunction` | Get a function from a module |
| `ffi.ModuleImportModule` | Import one module into another |
| `ffi.ModuleClearImports` | Clear all imports from a module |
| `ffi.ModuleGetKind` | Get the kind string of a module |
| `ffi.SystemLib` | Get the system library module |
| `ffi.Module.load_from_file.so` | DSO loader registration |
| `ffi.ModuleGlobalsAdd` | Keep a module alive in the global singleton |
| `ffi.ModuleGlobalsRemove` | Release a module from the global singleton |

### C API

```c
// Stream context (include/tvm/ffi/extra/c_env_api.h).
TVM_FFI_DLL int TVMFFIEnvSetStream(int device_type, int device_id,
                                    TVMFFIStreamHandle stream,
                                    TVMFFIStreamHandle* opt_out_original);
TVM_FFI_DLL int TVMFFIEnvGetCurrentStream(int device_type, int device_id);

// Module environment (include/tvm/ffi/extra/c_env_api.h).
TVM_FFI_DLL int TVMFFIEnvModLookupFromImports(void* mod, const char* name,
                                               TVMFFIAny* out);
TVM_FFI_DLL int TVMFFIEnvModRegisterContextSymbol(void* mod, const char* name,
                                                   const TVMFFIAny* value);
TVM_FFI_DLL int TVMFFIEnvModRegisterSystemLibSymbol(const char* name,
                                                     const TVMFFIAny* value);
```

### Build configuration

All module system sources require `TVM_FFI_USE_EXTRA_CXX_API=ON` in CMake.

## Implementation

Key files:
- `include/tvm/ffi/extra/module.h` -- `ModuleObj`, `Module`, `ModulePropertyMask`, `symbol::` constants
- `include/tvm/ffi/extra/c_env_api.h` -- C API declarations for module environment and stream context
- `src/ffi/extra/module.cc` -- Module methods, `LoadFromFile`, global registrations
- `src/ffi/extra/library_module.cc` -- `LibraryModuleObj`, `ProcessLibraryBin`, `ContextSymbolRegistry`
- `src/ffi/extra/library_module_dynamic_lib.cc` -- `DSOLibrary` (dlopen/LoadLibrary)
- `src/ffi/extra/library_module_system_lib.cc` -- `SystemLibrary`, `SystemLibModuleRegistry`
- `src/ffi/extra/module_internal.h` -- `Library` base class, `ModuleObj::InternalUnsafe`
- `src/ffi/extra/buffer_stream.h` -- `BufferInStream` for reading binary blobs
- `src/ffi/extra/stream_context.cc` -- `StreamContext` thread-local singleton
- `src/ffi/extra/env_c_api.cc` -- `EnvCAPIRegistry`, signal/GIL management

Python bindings:
- `python/tvm_ffi/module.py` -- Python `Module` class wrapping the global functions

## History
- 2025-08-17: `ffi::Module`, `ffi::ModuleObj`, `Library`, `DSOLibrary`, `SystemLibrary` introduced (`538bef4`)
- 2025-08-19: Thread-local `StreamContext` added with `TVMFFIEnvSetStream`/`TVMFFIEnvGetCurrentStream` (`0daaffe`)
- 2025-08-19: Auto-DLPack stream context benchmark (`6014406`)
- 2025-08-20: Env API symbols renamed with `Mod` infix; `EnvCAPIRegistry` relocated to extra layer (`023ea44`)
- 2025-08-30: `ModuleObj::GetModuleMetadata()` stub added; ABI type ordering adjusted (`777cf8d`)
- 2025-09-05: `load_inline` for inline C++ module compilation introduced (`83805ec`)
- 2025-09-06: `Library::GetSymbolWithSymbolPrefix` added; module entry symbol standardized (`40e8a51`)
- 2025-09-06: `load_inline` API updated to match torch interface (`825aeb9`)
- 2025-09-08: Windows `load_inline` bug fix (`2df07e5`); macOS support (`4ffbc88`)
- 2025-09-09: Generic stream exchange protocol added (`db98729`)
- 2025-09-10: System library symbol lookup fix (`315f4bb`)
- 2025-09-12: `env_context.cc` replaces `stream_context.cc`; DLPack fast path APIs (`f81ab9c`)
- 2025-09-12: `load_inline` interface refined (`1ce0f6f`)
- 2025-09-15: Python `tvm_ffi.stream` module added (`3197cd0`)
- 2025-09-29: `build_inline` utility added (`4fcf94f`)
- 2025-10-01: `ModuleObj::GetFunctionDoc` virtual method added; `ffi.ModuleGetFunctionDoc` registered (`935a5a0`)
- 2025-10-08: `get_stream` method exposed (`22c049b`)
- 2025-10-10: Cython API to construct `Function` from extern C (`a153647`)
- 2025-10-11: MLIR packed function creation from Cython (`f6303b2`)
- 2025-10-14: `InvokeExternC` utility added (`9186b44`)
- 2025-10-14: Testing library split into `libtvm_ffi_testing.so` (`da7007f`)
- 2025-10-15: CMake automatic config discovery (`df04392`)
- 2025-10-18: Version Query API added (`f0058a9`)
- 2025-10-24: `load_module` accepts `PathLike` objects (`af898a2`)
- 2025-11-05: `tvm_ffi.cpp.build()` and `tvm_ffi.cpp.load()` file-based extension API (`c897e4c`)
- 2025-11-18: Symbol visibility hidden by default for extension builds (`7cd2e50`)
- 2025-11-20: Function metadata embedding: `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA`, `GetFunctionMetadata()`, `GetFunctionDoc()` implemented in `LibraryModuleObj` (`ac7bf68`)
- 2025-11-25: CUDA cubin launcher utility added (`d49effd`); `CUDADeviceGuard` RAII struct (`cdfd041`)
- 2025-11-26: Kernel library guide updated with device guard usage (`803cdc8`)
- 2025-12-02: Metadata string allocation moved to `libtvm_ffi` for cross-module safety (`dcacb98`)
- 2025-12-04: Log level for JIT initialization changed from info to debug (`8d237f3`)
- 2025-12-11: `keep_module_alive` parameter added to `load_module`, `cpp.load_inline`, `cpp.load`; `ModuleGlobals` singleton introduced (`8dcaec1`)
- 2025-12-12: `tvm_ffi.libinfo.load_lib_module` utility added (`f255650`)
- 2025-12-25: Cubin launcher refactored: `add_tvm_ffi_cubin` replaces `tvm_ffi_generate_cubin`; `TVM_FFI_EMBED_CUBIN_FROM_BYTES` macro added; unified CUDA/HIP API header (`b16f11f`)

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
  - `.repo-knowledge/ranges/2025-09-30-CA9C3D1-F9179EC.md`
  - `.repo-knowledge/ranges/2025-10-31-FFA2DBF-BC0D225.md`
  - `.repo-knowledge/ranges/2025-11-30-0EE6444-4076EF5.md`
  - `.repo-knowledge/ranges/2025-12-29-5A82940-6E7CAFA.md`
- Related ADRs:
  - `.repo-knowledge/adr/014-keep-module-alive.md`
- Related design docs:
  - `.repo-knowledge/design/003-c-abi-stability.md`
  - `.repo-knowledge/design/002-namespace-and-api-migration.md`
  - `.repo-knowledge/design/009-tensor-and-dlpack.md`
