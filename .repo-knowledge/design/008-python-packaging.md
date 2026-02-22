# Python Packaging (tvm_ffi)

- Doc ID: 008-python-packaging
- Status: Approved
- Last Updated: 2025-12-29
- Owners: Tianqi Chen, Ruihang Lai

## Overview

The `tvm_ffi` Python package provides standalone Python bindings for the TVM
FFI layer, decoupled from the main TVM compiler. It uses Cython for C-to-Python
bridging and scikit-build-core for the build system. The package enables
lightweight ML library plugins to depend on `tvm_ffi` alone without the full
TVM runtime/compiler stack.

## Key Design

### Package structure

```
python/tvm_ffi/
  __init__.py          # Public API exports
  _ffi_api.py          # Internal FFI function lookups
  _ffi_api.pyi         # Type stubs for FFI API
  _convert.py          # Python-to-FFI type conversion (renamed from convert.py)
  _dtype.py            # DLDataType Python bindings (renamed from dtype.py)
  _tensor.py           # Tensor Python bindings
  _optional_torch_c_dlpack.py  # Optional PyTorch DLPack integration
  registry.py          # register_object, register_global_func, get_global_func
  container.py         # Array, Map, List, Dict wrappers
  error.py             # Error type mapping and traceback handling
  module.py            # Module Python wrapper
  access_path.py       # AccessPath/AccessStep Python bindings
  serialization.py     # ToJSONGraph/FromJSONGraph wrappers
  stream.py            # Stream context management
  testing.py           # Test utilities
  config.py            # Build configuration
  libinfo.py           # Library path discovery
  core.pyi             # Type stubs for Cython core
  py.typed             # PEP 561 typing marker
  dataclasses/
    __init__.py        # c_class, field, Field exports
    c_class.py         # @c_class decorator
    field.py           # Field descriptor
    _utils.py          # Utilities for decorator
  cpp/
    __init__.py        # load_inline, build_inline, load, build exports
    extension.py       # Inline and file-based C++ compilation (renamed from load_inline.py)
  stub/
    __init__.py        # Stub generation package
    cli.py             # tvm-ffi-stubgen CLI entry point
    codegen.py         # Stub code generation
    consts.py          # Directive and format constants
    file_utils.py      # File parsing and marker detection
    lib_state.py       # Loaded library state for stub generation
    utils.py           # Shared utilities
  utils/
    __init__.py        # Utility exports
    lockfile.py        # File locking
    kwargs_wrapper.py  # kwargs wrapping for positional-only FFI functions
    _build_optional_torch_c_dlpack.py  # Torch C DLPack build utility
  testing/
    __init__.py        # Test utilities
    _ffi_api.py        # FFI function bindings for testing
    testing.py         # Test utilities (functions)
  cython/
    core.pyx           # Cython extension entry point
    base.pxi           # C ABI type definitions, library loading
    object.pxi         # Object ref-counting, type dispatch
    function.pxi       # Function calling convention
    string.pxi         # String conversion
    tensor.pxi         # Tensor DLPack bridge (renamed from ndarray.pxi)
    device.pxi         # Device type handling
    dtype.pxi          # DType conversion
    error.pxi          # Error handling and traceback
    type_info.pxi      # TypeInfo/TypeField/TypeMethod dataclasses
    tvm_ffi_python_helpers.h  # C++ helpers for Python call dispatch
```

### Build system

The package uses `pyproject.toml` (`2d41a51`) with scikit-build-core as the
build backend. Key configuration:

- Build backend: `scikit_build_core.build`
- Cython extension: `tvm_ffi.cython.core`
- CMake integration: The C++ library is built as part of the wheel
- Optional dependencies: `test` group includes `pytest`, `numpy`

The primary installation workflow is:
```bash
uv pip install --force-reinstall --verbose -e .
```

C++ or Cython changes require re-running this command. Pure Python changes
are reflected immediately in editable installs.

### CMake integration

`cmake/tvm_ffi-config.cmake` (`2d41a51`) provides a CMake package config for
downstream C++ consumers:

```cmake
find_package(tvm_ffi REQUIRED)
target_link_libraries(my_target tvm_ffi::tvm_ffi)
```

The CMakeLists.txt was substantially reworked (+161/-37) to support:
- scikit-build-core integration
- Cython extension compilation
- libbacktrace as a git submodule with fallback download URL
- Windows compatibility fixes (`7358796`)

### libbacktrace integration

`3rdparty/libbacktrace` was added as a git submodule (`2d41a51`) for stack
trace support in error reporting. A fallback download URL was added
(`b245f1f`) for source-only distributions without submodules. The submodule
reference was later updated (`7d09d6a`) to fix the CMake download path.

### Packaging example

`examples/python_packaging/` (renamed from `examples/packaging/` in December
2025) provides a complete example of building a tvm_ffi extension package:

```
examples/python_packaging/
  CMakeLists.txt       # Extension library build (uses tvm_ffi_configure_target)
  pyproject.toml       # scikit-build-core packaging
  python/my_ffi_extension/
    __init__.py        # Extension entry point (auto-generated stubs)
    _ffi_api.py        # FFI function bindings (auto-generated stubs)
```

Since December 2025, the example uses `tvm_ffi_configure_target` to reduce
CMake boilerplate and `tvm-ffi-stubgen --init-*` to auto-generate Python stubs.

### Windows compatibility

Windows-specific fixes (`7358796`) addressed build issues including path
handling, DLL search paths, and compiler flag differences.

### Migration fixes

The final commit (`3702e50`) fixed two migration issues encountered when
porting code to the new `tvm_ffi` package.

### DSO discovery via `importlib.metadata` (December 2025)

`python/tvm_ffi/libinfo.py` was rewritten (`6887892`) to use
`importlib.metadata` (via the package `RECORD` file) as the primary DSO
discovery mechanism, with a fallback to env-variable-based path search.
`python/tvm_ffi/base.py` was deleted; library loading is now triggered
directly in `__init__.py` via `libinfo.load_lib_ctypes`. New APIs:

- `tvm_ffi.LIB` (public export): the loaded ctypes library handle
- `tvm_ffi.libinfo.load_lib_ctypes(package, target_name, mode)`: reusable
  helper for downstream libraries
- `tvm_ffi.libinfo.load_lib_module(package, target_name, keep_module_alive)`:
  finds and loads a downstream shared library as a TVM-FFI `Module` object
  (`f255650`)

Code importing `tvm_ffi.base` must switch to `tvm_ffi.libinfo`.

### kwargs wrapping utility (December 2025)

`python/tvm_ffi/utils/kwargs_wrapper.py` (`3115b23`, `6bc1a8e`) provides
`make_kwargs_wrapper()` and `make_kwargs_wrapper_from_signature()` for
wrapping positional-only FFI callables with keyword-argument support via
code generation. This follows the pattern used by `dataclasses` and
`pydantic` (exec-based code gen). Special-cases `None` and `bool` defaults
for direct embedding; all other defaults use a MISSING sentinel.

### Stubgen package generation (December 2025)

`tvm-ffi-stubgen` gained `--init-pypkg`, `--init-lib`, and `--init-prefix`
flags (`b58c2e3`) for one-command bootstrapping of `_ffi_api.py` and
`__init__.py` for new downstream packages. Re-running is idempotent:
existing stub blocks are detected and not duplicated. The `stub/analysis.py`
module was removed; new `stub/lib_state.py` was added.

### CMake helper functions (December 2025)

Two high-level CMake helper functions were added to `cmake/Utils/Library.cmake`
(`ccd19f8`):

- `tvm_ffi_configure_target(target ...)`: consolidates linking, debug symbol
  generation, MSVC flags, prefix map, and optional stub generation into a
  single call (similar to `pybind11_add_module`).
- `tvm_ffi_install(target ...)`: handles installation of the target.

`examples/packaging/CMakeLists.txt` was reduced from ~62 lines to 3 lines.

### CMake target namespace rename (December 2025)

CMake imported targets were renamed from flat names to namespaced form
(`a1cb746`):

- `tvm_ffi_shared` -> `tvm_ffi::shared`
- `tvm_ffi_header` -> `tvm_ffi::header`

Backward compatibility is provided in `EmbedCubin.cmake` via target probing.
Downstream CMake consumers using the old names must update.

### Error handling GC optimization (December 2025)

A reference cycle in `_with_append_backtrace` in `error.py` (`6ccbdb6`) was
eliminated. The cycle kept intermediate tensors alive until cyclic GC ran,
increasing GPU memory pressure during training. The fix uses `try/finally`
with explicit `del` to break the cycle at function return.

`Map.get` was also optimized (`438f643`) to avoid triggering the C++ error
pipeline (and its reference-cycle overhead) on every key-miss. A sentinel
`MapGetItemOrMissing` C++ function now returns a sentinel object instead of
raising `KeyError`.

### Release process documentation (December 2025)

`docs/dev/release_process.rst` (`6e7cafa`) was added documenting the
version bump, changelog, and wheel publication workflow.

### Standalone repository (September 2025)

The `apache/tvm-ffi` standalone repository was established (`30f1e0a`),
with `.gitignore`, `.gitmodules`, `LICENSE` (Apache 2.0), `NOTICE`,
`CONTRIBUTING.md`, and CI infrastructure (`ef6d57b`, `89e0b88`). The
repository was set up with GitHub Actions CI testing on Linux x86_64 +
aarch64, macOS arm64, and Windows AMD64 (`f5633e9`). Sphinx doc build
checks (`66778b5`) and Doxygen build checks (`3bc6418`) were added to CI.

### NDArray to Tensor rename (September 2025)

`tvm_ffi.NDArray` was renamed to `tvm_ffi.Tensor` (`3a551d8`), and internal
modules were renamed: `ndarray.py` -> `_tensor.py`, `ndarray.pxi` ->
`tensor.pxi`. The Python API cleanup (`40f4d9d`) also renamed `convert.py`
-> `_convert.py`, `dtype.py` -> `_dtype.py`, and added `DLDeviceType` enum.

### Type stubs and mypy (September 2025)

Type stubs for Cython-generated code were added (`785e8ca`): `core.pyi`
and `_ffi_api.pyi`. A `py.typed` marker file was added for PEP 561
compliance. mypy type checking was enabled (`40e9c83`) and the mypy config
was revamped (`5cfd705`). Parameterizable `Array[T]` and `Map[K, V]` type
annotations were introduced (`df58a05`).

### `@c_class` decorator (September 2025)

The `tvm_ffi.dataclasses` sub-package was introduced (`e98b94e`) with the
`@c_class` decorator for Python classes that mirror C++ FFI types with
dataclass-like syntax. See the reflection system design doc for details.

### `tvm_ffi.cpp.load_inline` (September 2025)

The `tvm_ffi.cpp` sub-package was introduced (`83805ec`) for inline C++
module compilation. See the module system design doc for details.

### `tvm_ffi.stream` module (September 2025)

The `tvm_ffi.stream` module (`3197cd0`) provides stream context management
with `StreamContext`, `set_stream`, and `get_stream` utilities.

### Auto Python class creation (September 2025)

Python stub classes are now auto-generated for unregistered FFI object types
(`98cb8af`), with all C++ fields and methods exposed automatically.

### Stub generation tooling (October 2025)

`tvm-ffi-stubgen` (`ea02e64`) is a CLI tool registered in `pyproject.toml`
that generates in-place type stubs from C++ reflection metadata. Stub blocks
are delimited by `# tvm-ffi-stubgen(begin/end)` markers inside `.py`/`.pyi`
files. The tool supports `global/<prefix>` blocks (function signatures) and
`object/<type_key>` blocks (field/method signatures). Type remapping is
available via `# tvm-ffi-stubgen(ty_map): A -> B` directives.

This replaced the hand-written `_ffi_api.pyi` file. Auto-extraction of type
annotations from function definitions was added to Sphinx docs (`17ff30b`).

### setuptools_scm versioning (October 2025)

Hardcoded `version = "0.1.0"` in `pyproject.toml` was replaced with
`dynamic = ["version"]` driven by `setuptools_scm` (`ac63fb9`).
`python/tvm_ffi/_version.py` is auto-generated from git tags; falls back to
`"0.0.0.dev0"` if not available. CI workflows were updated to use
`actions/checkout@v5` with `fetch-depth: 0` and `fetch-tags: true`.
`tests/lint/check_version.py` was rewritten to verify C++ and Rust version
macros match the SCM-derived version.

### torch_c_dlpack_ext addon (October 2025)

`addons/torch_c_dlpack_ext/` (`f703a0c`) is a standalone Python package that
ships the torch C DLPack extension as an AOT-compiled wheel. When installed,
`tvm_ffi` uses the pre-compiled library instead of JIT-compiling at import
time. A custom PEP 517 build backend handles the compilation. The default
JIT behavior is unchanged; AOT is opt-in.

### Free-threaded Python support (October 2025)

The Cython module was annotated as `freethreading_compatible` (`b64b46f`),
enabling builds with free-threaded Python (PEP 703). Object deletion
callbacks no longer explicitly acquire the GIL in nogil mode.

### Python 3.8 and manylinux wheels (October 2025)

Python 3.8 build support was added (`5e2a0e5`), with macOS arm64 Python 3.8
skipped due to lack of official builds (`d87502a`, `8831e88`). Manylinux2014
and manylinux2_28 wheel distribution was enabled (`d2e9aa6`, `997a366`).
Nightly wheel testing was introduced (`39d675d`).

### cmake-format, cmake-lint, and clang-tidy (October 2025)

`cmake-format` and `cmake-lint` were added to the pre-commit configuration
(`98b26ed`). `clang-tidy` was integrated into CI via
`tests/lint/clang_tidy_precommit.py` (`0899b5d`).

### ml_dtypes compatibility (October 2025)

Support for `ml_dtypes<0.5` was added (`9574e9d`).

### Pre-commit hooks modernization (September 2025)

Pre-commit hooks were modernized (`64e4b7f`) and expanded: basic Ruff rule
coverage (`0bc968d`), type annotation enforcement on public APIs (`8f4e044`),
Taplo for TOML linting (`23500b5`), RST/MD/YAML linters (`95825407`).

### Docker support (September 2025)

A Dockerfile was added (`fc0f5f5`) for containerized development and
testing, including a C++ CUDA example.

### uv-based doc building (September 2025)

The documentation build workflow was updated to use uv (`4f0b18c`) instead
of pip, matching the project's primary tool choice.

## APIs

### Python API

```python
import tvm_ffi

# Function registration and lookup
tvm_ffi.register_global_func("my.func", lambda x: x + 1)
f = tvm_ffi.get_global_func("my.func")

# Object registration
@tvm_ffi.register_object("my.Type")
class MyType(tvm_ffi.Object):
    pass

# Module loading
mod = tvm_ffi.Module.load("library.so")
f = mod.get_function("func_name")

# Serialization
json_str = tvm_ffi.save_json(obj)
restored = tvm_ffi.load_json(json_str)

# Tensor (DLPack)
arr = tvm_ffi.Tensor.from_dlpack(numpy_array)

# Inline C++ module
mod = tvm_ffi.cpp.load_inline("my_ext", cpp_source="...")

# Stream context
with tvm_ffi.stream.StreamContext(device, stream):
    f(tensor)

# c_class decorator
from tvm_ffi.dataclasses import c_class
@c_class("my.Type")
class MyType(tvm_ffi.Object):
    name: str
```

### Test suite

14 Python test files cover:
- `test_access_path.py` -- AccessPath construction and navigation
- `test_build_inline.py` -- `build_inline` compilation
- `test_container.py` -- Array, Map, List, Dict operations
- `test_dataclasses_c_class.py` -- `@c_class` decorator
- `test_device.py` -- Device type creation and properties
- `test_dtype.py` -- DType conversion and properties
- `test_error.py` -- Error type mapping and traceback
- `test_examples.py` -- End-to-end example tests
- `test_function.py` -- Function calling convention
- `test_load_inline.py` -- `load_inline` compilation and loading
- `test_object.py` -- Object registration, type dispatch, auto class creation
- `test_stream.py` -- Stream context management
- `test_string.py` -- String conversion
- `test_tensor.py` -- Tensor creation and DLPack exchange

## Implementation

Key files:
- `pyproject.toml` -- Package metadata, build system configuration
- `python/tvm_ffi/` -- Python package (16 modules + Cython directory)
- `python/tvm_ffi/cython/core.pyx` -- Cython extension entry point
- `cmake/tvm_ffi-config.cmake` -- CMake package config for downstream consumers
- `CMakeLists.txt` -- Build configuration (scikit-build-core integration)
- `3rdparty/libbacktrace` -- Git submodule for stack trace support
- `examples/get_started/` -- Minimal CPU/CUDA FFI usage example
- `examples/packaging/` -- Extension package example
- `tests/python/` -- Python test suite (9 files)

## History
- 2025-08-24: `tvm_ffi` Python package established with Cython bindings, test suite, examples (`2d41a51`)
- 2025-08-25: pyproject.toml robustified (`2cf211f`)
- 2025-08-26: Windows build fixes (`7358796`)
- 2025-08-28: libbacktrace fallback download URL added (`b245f1f`)
- 2025-08-29: libbacktrace submodule URL fix (`7d09d6a`)
- 2025-08-29: scikit-build-core packaging completed (`ad8e5d2`)
- 2025-08-30: Packaging documentation and examples added (`4523a83`)
- 2025-08-31: Migration issue fixes (`3702e50`)
- 2025-09-06: NDArray -> Tensor rename across Python (`3a551d8`)
- 2025-09-07: Python API cleanup: internal module renames, `DLDeviceType` enum (`40f4d9d`)
- 2025-09-13: Standalone `apache/tvm-ffi` repository established (`30f1e0a`)
- 2025-09-13: CI setup for standalone repo (`ef6d57b`)
- 2025-09-14: `CONTRIBUTING.md` and docs guides added (`5facac5`, `240ea44`)
- 2025-09-17: Pre-commit hooks modernized (`64e4b7f`, `0bc968d`, `8f4e044`)
- 2025-09-18: Type stubs for Cython code (`785e8ca`); `py.typed` marker added
- 2025-09-19: `TypeInfo`/`TypeField`/`TypeMethod` Python dataclasses (`53b2e00`)
- 2025-09-20: Docker support and CUDA example (`fc0f5f5`)
- 2025-09-20: uv-based doc building (`4f0b18c`)
- 2025-09-21: `@c_class` decorator (`e98b94e`)
- 2025-09-22: mypy type checking enabled (`40e9c83`)
- 2025-09-22: Parameterizable `Array[T]` and `Map[K, V]` (`df58a05`)
- 2025-09-22: CI: Sphinx doc build checks (`66778b5`), Doxygen build checks (`3bc6418`)
- 2025-09-22: Multi-Python CI testing (`f5633e9`)
- 2025-09-23: mypy config revamp and typing metadata (`5cfd705`)
- 2025-09-25: Auto Python class creation for unregistered types (`98cb8af`)
- 2025-09-26: `tvm_ffi.__version__` exposed (`ebea4dc`)
- 2025-10-05: cmake-format and cmake-lint added to pre-commit (`98b26ed`)
- 2025-10-10: Free-threaded Python build support (`b64b46f`)
- 2025-10-12: `tvm-ffi-stubgen` CLI tool and `tvm_ffi.stub` package (`ea02e64`)
- 2025-10-16: Python 3.8 build support (`5e2a0e5`); manylinux2014 wheels (`d2e9aa6`)
- 2025-10-16: Version formally bumped to 0.1.0 (`792dc01`)
- 2025-10-26: `setuptools_scm` replaces hardcoded version (`ac63fb9`)
- 2025-10-28: clang-tidy added to CI (`0899b5d`)
- 2025-10-28: `ml_dtypes<0.5` support (`9574e9d`)
- 2025-10-31: AOT `torch_c_dlpack_ext` addon package (`f703a0c`)
- 2025-12-01: Torch C DLPack CI actions merged into single workflow (`f6aa584`)
- 2025-12-04: `kwargs_wrapper` utility for wrapping positional-only FFI functions (`3115b23`, `6bc1a8e`)
- 2025-12-04: `__tvm_ffi_value__()` generic value protocol introduced (`3dd7a81`)
- 2025-12-06: DSO discovery rewritten to use `importlib.metadata`; `tvm_ffi.base` removed (`6887892`)
- 2025-12-07: `tvm-ffi-config --sourcedir` fix for wheels (`3cfc5c5`)
- 2025-12-11: `keep_module_alive` parameter added to `load_module` (`8dcaec1`)
- 2025-12-12: `tvm_ffi.libinfo.load_lib_module` utility added (`f255650`)
- 2025-12-12: `Map.get` performance fix via `MapGetItemOrMissing` sentinel (`438f643`)
- 2025-12-12: Reference cycle in error handling eliminated for faster GC (`6ccbdb6`)
- 2025-12-12: Pre-commit hooks updated; docstring formatter enabled (`8b46833`)
- 2025-12-18: `tvm_ffi.device(...)` accepts numpy/torch scalar for device ID (`a7ebc65`)
- 2025-12-18: Stubgen `--init-pypkg`, `--init-lib`, `--init-prefix` flags for package scaffolding (`b58c2e3`)
- 2025-12-20: CMake `tvm_ffi_configure_target` and `tvm_ffi_install` helpers (`ccd19f8`)
- 2025-12-22: CMake targets renamed to `tvm_ffi::shared`/`tvm_ffi::header` (`a1cb746`)
- 2025-12-22: Python packaging docs revamped (`19da7e8`, `dc0dd2f`, `89be2d3`)
- 2025-12-29: Release process documentation added (`6e7cafa`)

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
  - `.repo-knowledge/ranges/2025-09-30-CA9C3D1-F9179EC.md`
  - `.repo-knowledge/ranges/2025-10-31-FFA2DBF-BC0D225.md`
  - `.repo-knowledge/ranges/2025-12-29-5A82940-6E7CAFA.md`
- Related ADRs:
  - `.repo-knowledge/adr/014-keep-module-alive.md`
  - `.repo-knowledge/adr/015-cmake-namespaced-targets.md`
- Related design docs:
  - `.repo-knowledge/design/003-c-abi-stability.md`
  - `.repo-knowledge/design/007-module-system.md`
  - `.repo-knowledge/design/009-tensor-and-dlpack.md`
