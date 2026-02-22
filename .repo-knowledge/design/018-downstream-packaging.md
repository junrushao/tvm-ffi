# 018 — Downstream Packaging and Tooling

- Doc ID: 018-downstream-packaging
- Status: Approved
- Last Updated: 2026-02-22
- Owners: Tianqi Chen, Ruihang Lai

## Overview

TVM FFI provides a complete toolchain for building, packaging, and distributing
downstream C++ extension libraries as Python wheels with auto-generated typed
bindings. The system is organized into three layers: a **build layer** of CMake
functions (`tvm_ffi_configure_target`, `tvm_ffi_install`) and the
`tvm-ffi-config` CLI for compiling C++ against TVM FFI headers and libraries; a
**load layer** centered on `load_lib_module` which discovers and loads the built
shared library at Python import time via `importlib.metadata`; and a **stub
layer** where `tvm-ffi-stubgen` auto-generates typed Python bindings from C++
reflection metadata. Together, these layers allow a downstream project to go from
a single `.cc` file to a fully typed, pip-installable, ABI-agnostic Python wheel
with as little as three lines of CMake.

## Key Design

### CMake integration: `tvm_ffi_configure_target`

The primary CMake entry point is `tvm_ffi_configure_target`, which consolidates
linking, debug symbol generation, MSVC flags, prefix map setup, and optional
stub generation into a single function call. Its full signature is:

```cmake
tvm_ffi_configure_target(
  <target>
  [LINK_SHARED  ON|OFF]   # default: ON  -- link against tvm_ffi::shared
  [LINK_HEADER  ON|OFF]   # default: ON  -- link against tvm_ffi::header
  [DEBUG_SYMBOL ON|OFF]   # default: ON  -- dsymutil on Apple
  [MSVC_FLAGS   ON|OFF]   # default: ON  -- MSVC compat definitions
  [STUB_INIT    ON|OFF]   # default: OFF -- allow generating new files/directives
  [STUB_DIR     <dir>]    # stub output directory (relative to CMAKE_CURRENT_SOURCE_DIR)
  [STUB_PKG     <pkg>]    # Python package name (default: SKBUILD_PROJECT_NAME or target)
  [STUB_PREFIX  <prefix>] # registry prefix filter (default: "<STUB_PKG>.")
)
```

Key behaviors:

- `LINK_SHARED=ON` links the target against `tvm_ffi::shared` (the actual
  `.so`/`.dylib`/`.dll`). Set to `OFF` for header-only or deferred-loading use
  cases.
- `LINK_HEADER=ON` links `tvm_ffi::header`, providing include paths and compile
  definitions.
- `DEBUG_SYMBOL=ON` runs `dsymutil` as a post-build step on Apple platforms;
  no-op elsewhere.
- `MSVC_FLAGS=ON` applies `WIN32_LEAN_AND_MEAN`, `_CRT_SECURE_NO_WARNINGS`,
  `_SCL_SECURE_NO_WARNINGS`, `_ENABLE_EXTENDED_ALIGNED_STORAGE`, `NOMINMAX`,
  and `/Zi` on MSVC.
- The function always calls `tvm_ffi_add_prefix_map` to remap source paths for
  reproducible builds.
- Stub generation runs as a CMake `POST_BUILD` custom command:
  `python -m tvm_ffi.stub.cli <args>`.
- Validation rules: `STUB_PKG`/`STUB_PREFIX` require `STUB_INIT=ON`;
  `STUB_INIT=ON` requires `STUB_DIR`.
- Default `STUB_PKG` fallback chain: `SKBUILD_PROJECT_NAME` -> CMake target
  name.

Source: `cmake/Utils/Library.cmake` lines 140-342.

### CMake integration: `tvm_ffi_install`

The companion install function handles platform-specific artifact packaging:

```cmake
tvm_ffi_install(
  <target>
  [DESTINATION <dir>]   # default: "."
)
```

On Apple, it installs the `$<TARGET_FILE:target>.dSYM` bundle (`OPTIONAL`, so
no error if absent). On non-Apple platforms, it is currently a no-op but is
extensible for PDB/DWARF packaging. Must be paired with
`tvm_ffi_configure_target(... DEBUG_SYMBOL ON)` for dSYM generation.

Source: `cmake/Utils/Library.cmake` lines 363-396.

### CMake discovery: `find_package` and `tvm_ffi_ROOT`

Downstream projects discover TVM FFI via standard CMake config-mode:

```cmake
find_package(tvm_ffi CONFIG REQUIRED)
```

When using scikit-build-core, `tvm_ffi_ROOT` is auto-discovered from the active
Python environment. For manual builds, override with:

```bash
cmake -Dtvm_ffi_ROOT="$(tvm-ffi-config --cmakedir)" ..
```

### `tvm-ffi-config` CLI tool

The `tvm-ffi-config` CLI is registered as a console script entry point in
`pyproject.toml` (`tvm-ffi-config = "tvm_ffi.config:__main__"`). It exposes
build configuration flags for direct compilation workflows:

| Flag                  | Output                                                       |
|-----------------------|--------------------------------------------------------------|
| `--cxxflags`          | `-I<include_dir> -I<dlpack_include_dir> -std=c++17`         |
| `--cflags`            | `-I<include_dir> -I<dlpack_include_dir>` (no `-std=c++17`)  |
| `--ldflags`           | `-L<libdir>` (empty on Windows)                              |
| `--libs`              | `-ltvm_ffi` (full implib path on Windows)                    |
| `--includedir`        | Path to TVM FFI headers (`include/`)                         |
| `--dlpack-includedir` | Path to DLPack headers                                       |
| `--cmakedir`          | Path to CMake config files (`share/cmake/tvm_ffi/`)          |
| `--libdir`            | Directory containing `libtvm_ffi.so`                         |
| `--libfiles`          | Full path to `libtvm_ffi.so` (or `tvm_ffi.lib` on Windows)  |
| `--sourcedir`         | Package source root directory                                |
| `--cython-lib-path`   | Path to Cython extension `.so`                               |

Example: compile a shared library directly without CMake:

```bash
g++ -shared -O3 my_extension.cc  \
    -fPIC -fvisibility=hidden    \
    $(tvm-ffi-config --cxxflags) \
    $(tvm-ffi-config --ldflags)  \
    $(tvm-ffi-config --libs)     \
    -o libmy_extension.so
```

Source: `python/tvm_ffi/config.py`, `examples/quickstart/raw_compile.sh`.

### Two-path function export design

TVM FFI provides two complementary mechanisms for exporting C++ functions to
Python.

**Path 1: Module-level export via `TVM_FFI_DLL_EXPORT_TYPED_FUNC`.** This
exports a function as a C ABI symbol `__tvm_ffi_<ExportName>`, accessed through
the `Module` object in Python (e.g., `LIB.add_two(1)`). It optionally exports
metadata (`__tvm_ffi__metadata_<ExportName>`) when
`TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` is defined, and docstrings
(`__tvm_ffi__doc_<ExportName>`) via `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC`.

```cpp
static int AddTwo(int x) { return x + 2; }
TVM_FFI_DLL_EXPORT_TYPED_FUNC(add_two, AddTwo)
```

**Path 2: Global registry export via `GlobalDef`.** This registers functions
into the global function registry with a namespaced key, accessible through
`init_ffi_api` (which populates module attributes) or `get_global_func`.
Functions registered this way are discoverable by `tvm-ffi-stubgen` for type
stub generation.

```cpp
static int AddOne(int x) { return x + 1; }

TVM_FFI_STATIC_INIT_BLOCK() {
  namespace refl = tvm::ffi::reflection;
  refl::GlobalDef()
      .def("my_ffi_extension.add_one", AddOne);
}
```

| Aspect              | `TVM_FFI_DLL_EXPORT_TYPED_FUNC`      | `GlobalDef`                              |
|---------------------|---------------------------------------|------------------------------------------|
| Symbol              | C ABI `__tvm_ffi_<name>`              | Global registry string key               |
| Python access       | `LIB.<name>(*args)`                   | `module.<name>(*args)` via `init_ffi_api`|
| Stub generation     | Not covered by stubgen                | Covered by `global/<prefix>` directive   |
| Metadata support    | Optional via `_INCLUDE_METADATA`      | Via reflection type schema               |
| Isolation           | Per-module (namespace by library)     | Global (namespace by prefix convention)  |

Source: `include/tvm/ffi/function.h` lines 942-1068,
`include/tvm/ffi/extra/module.h` (symbol prefix at line 283),
`examples/python_packaging/src/extension.cc`.

### `load_lib_module`: library loading

The `load_lib_module` function discovers and loads a downstream shared library
at Python import time:

```python
from tvm_ffi.libinfo import load_lib_module

LIB = load_lib_module(
    package="my-ffi-extension",     # pip package name (pyproject.toml [project].name)
    target_name="my_ffi_extension", # CMake target name
)
```

Parameters:

- `package`: The pip-registered package name (not the import name). Uses
  `importlib.metadata.distribution(package)` to find installed files via
  RECORD.
- `target_name`: The CMake target name. Derives platform-specific filenames:
  Linux `lib{target_name}.so`, macOS `lib{target_name}.dylib` (fallback `.so`),
  Windows `{target_name}.dll`.
- `keep_module_alive` (default `True`): Prevents the loaded module from being
  unloaded during process lifetime.

The internal `_find_library_by_basename` function implements a two-tier
discovery algorithm:

1. **Primary path:** Parse the `RECORD` file from
   `importlib.metadata.distribution(package)` and match against
   platform-specific filenames.
2. **Fallback paths** (for dev environments without proper pip install):
   `<tvm_ffi_dir>/build/lib/`, `<tvm_ffi_dir>/lib/`,
   `<project_root>/build/lib/`, `<project_root>/lib/`, and environment
   variables `LD_LIBRARY_PATH` (Linux), `DYLD_LIBRARY_PATH` (macOS),
   `PATH` (Windows).

On Windows, `os.add_dll_directory()` is also called for proper DLL search.
Under the hood, `load_lib_module` delegates to `tvm_ffi.module.load_module`
which creates a `Module` object wrapping the DSO with `__tvm_ffi_<name>`
symbol lookup.

Source: `python/tvm_ffi/libinfo.py` lines 175-276.

### `init_ffi_api`: automatic function discovery

The `init_ffi_api` function bridges globally registered C++ functions into
Python module attributes:

```python
# _ffi_api.py
import tvm_ffi
tvm_ffi.init_ffi_api("my_ffi_extension", __name__)
```

It iterates all global function names via `list_global_func_names()`, filters
by prefix match (only functions starting with the given namespace), strips the
prefix plus dot (so `"my_ffi_extension.add_one"` becomes `add_one`), and skips
functions with dots in the suffix (i.e., nested namespaces). Each function is
attached as an attribute on the target module with its `__name__` set for
better repr/debugging. Special handling: if the namespace starts with `"tvm."`,
the `"tvm."` prefix is stripped before matching.

Source: `python/tvm_ffi/registry.py` lines 283-331.

### Stubgen directive reference

The `tvm-ffi-stubgen` tool uses inline directives delimited by
`# tvm-ffi-stubgen(begin)` / `# tvm-ffi-stubgen(end)` markers to manage
auto-generated code within `.py` files.

#### Directive syntax

```python
# tvm-ffi-stubgen(begin): <directive-type>/<parameter>
# ... generated code ...
# tvm-ffi-stubgen(end)
```

#### Directive reference table

| Directive                    | Location           | Purpose                                             |
|------------------------------|--------------------|-----------------------------------------------------|
| `global/<prefix>`            | `_ffi_api.py`      | Global function stubs for all funcs with given prefix |
| `object/<type_key>`          | Class body         | Fields + methods for a registered object type        |
| `import-section`             | File top           | Auto-populated imports for types used in stubs       |
| `export/<module>`            | `__init__.py`      | Re-exports from a submodule                          |
| `__all__`                    | Inside `__all__`   | Populates export list with generated names           |
| `ty-map`                     | Anywhere (single)  | Map C++ type key to different Python type path       |
| `import-object`              | Anywhere (single)  | Inject custom import (`full_name;tc_only;alias`)     |
| `skip-file`                  | Anywhere (single)  | Prevent stubgen from modifying the file              |

#### Directive examples

**`global/<prefix>`:**

```python
# tvm-ffi-stubgen(begin): global/my_ffi_extension
# fmt: off
_FFI_INIT_FUNC("my_ffi_extension", __name__)
if TYPE_CHECKING:
    def add_one(_0: int, /) -> int: ...
    def raise_error(_0: str, /) -> None: ...
# fmt: on
# tvm-ffi-stubgen(end)
```

**`object/<type_key>`:**

```python
@_FFI_REG_OBJ("my_ffi_extension.IntPair")
class IntPair(_ffi_Object):
    # tvm-ffi-stubgen(begin): object/my_ffi_extension.IntPair
    # fmt: off
    a: int
    b: int
    if TYPE_CHECKING:
        @staticmethod
        def __c_ffi_init__(_0: int, _1: int, /) -> Object: ...
        def sum(self, /) -> int: ...
    # fmt: on
    # tvm-ffi-stubgen(end)
```

**`import-section`:**

```python
# tvm-ffi-stubgen(begin): import-section
# fmt: off
# isort: off
from __future__ import annotations
from tvm_ffi import Object as _ffi_Object, init_ffi_api as _FFI_INIT_FUNC, register_object as _FFI_REG_OBJ
from tvm_ffi.libinfo import load_lib_module as _FFI_LOAD_LIB
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tvm_ffi import Object
# isort: on
# fmt: on
# tvm-ffi-stubgen(end)
```

**`export/<module>`:**

```python
# tvm-ffi-stubgen(begin): export/_ffi_api
# fmt: off
# isort: off
from ._ffi_api import *  # noqa: F403
from ._ffi_api import __all__ as _ffi_api__all__
if "__all__" not in globals():
    __all__ = []
__all__.extend(_ffi_api__all__)
# isort: on
# fmt: on
# tvm-ffi-stubgen(end)
```

**`__all__`:**

```python
__all__ = [
    # tvm-ffi-stubgen(begin): __all__
    "LIB",
    "IntPair",
    "add_one",
    "raise_error",
    # tvm-ffi-stubgen(end)
]
```

**`ty-map` (single-line):**

```python
# tvm-ffi-stubgen(ty-map): ffi.reflection.AccessStep -> ffi.access_path.AccessStep
```

**`import-object` (single-line):**

```python
# tvm-ffi-stubgen(import-object): ffi.Object;False;_ffi_Object
```

**`skip-file` (single-line):**

```python
# tvm-ffi-stubgen(skip-file)
```

### STUB_INIT ON vs OFF modes

**`STUB_INIT OFF` (Update Mode):** The default mode. Only fills in content
within existing `tvm-ffi-stubgen(begin)` / `tvm-ffi-stubgen(end)` markers.
Does not create new files or new directives. Preserves all code outside
directive blocks. Use after customizing generated files to update stubs without
losing manual edits.

**`STUB_INIT ON` (Init Mode):** Generates new files from scratch: `_ffi_api.py`
and `__init__.py`. Creates all directive blocks: `import-section`,
`global/<prefix>`, `object/<type_key>`, `export/<module>`, `__all__`.
Additional required parameters: `STUB_PKG` (defaults to `SKBUILD_PROJECT_NAME`
or target name), `STUB_PREFIX` (defaults to `"<STUB_PKG>."`). Re-running is
idempotent: existing stub blocks are detected and not duplicated.

CLI equivalents:

| CMake                   | CLI                                       |
|-------------------------|-------------------------------------------|
| `STUB_DIR "./python"`   | `<positional dir>`                        |
| `STUB_INIT ON`          | Presence of `--init-*` flags              |
| `STUB_PKG "my-ext"`     | `--init-pypkg my-ext`                     |
| `STUB_PREFIX "my_ext."` | `--init-prefix "my_ext."`                 |
| *(target name)*         | `--init-lib my_ffi_extension`             |
| *(implicit)*            | `--dlls build/libmy_ffi_extension.so`     |

Full generation:

```bash
tvm-ffi-stubgen                          \
  python/my_ffi_extension                \
  --dlls build/libmy_ffi_extension.so    \
  --init-pypkg my-ffi-extension          \
  --init-lib my_ffi_extension            \
  --init-prefix "my_ffi_extension."
```

Update only:

```bash
tvm-ffi-stubgen                          \
  python/my_ffi_extension                \
  --dlls build/libmy_ffi_extension.so
```

### Wheel auditing: `libtvm_ffi` exclusion

Downstream wheels link against `libtvm_ffi.so`, but this library is guaranteed
to be loaded by `import tvm_ffi` before any downstream code runs. Therefore,
`libtvm_ffi` must be excluded from wheel auditing to avoid bundling it (which
would create version conflicts):

```bash
# Linux
auditwheel repair --exclude libtvm_ffi.so dist/*.whl
# macOS
delocate-wheel -w dist -v --exclude libtvm_ffi.dylib dist/*.whl
# Windows
delvewheel repair --exclude tvm_ffi.dll -w dist dist\*.whl
```

The `import tvm_ffi` statement in the downstream package's `_ffi_api.py`
preloads `libtvm_ffi.so` into the process. The dynamic linker finds the
symbols at load time without the downstream library needing to bundle them.
This follows the same pattern used by numpy/scipy.

### RPATH handling

**Python distribution (no RPATH needed):** Because `import tvm_ffi` preloads
`libtvm_ffi.so` into the process, downstream shared libraries loaded
subsequently can resolve `libtvm_ffi` symbols from the process image. No RPATH
or `LD_LIBRARY_PATH` configuration is needed.

**Pure C++ distribution (RPATH required):** Must ensure `libtvm_ffi.so` is
findable at runtime. Either set RPATH at link time or place `libtvm_ffi.so`
alongside the binary:

```bash
g++ -fvisibility=hidden -O3 my_app.cc \
    $(tvm-ffi-config --cxxflags)      \
    $(tvm-ffi-config --ldflags)       \
    $(tvm-ffi-config --libs)          \
    -Wl,-rpath,$(tvm-ffi-config --libdir) \
    -o my_app
```

### ABI-agnostic wheels

Downstream TVM FFI extensions produce ABI-agnostic wheels by setting
`wheel.py-api = "py3"` in `pyproject.toml`:

```toml
[tool.scikit-build]
# The wheel is Python ABI-agnostic
wheel.py-api = "py3"
```

This means the wheel is compatible with any Python 3.x version without needing
a specific CPython ABI tag. The extension is a compiled C++ shared library that
communicates through the stable TVM FFI C ABI, not through the CPython C API.
This contrasts with TVM FFI itself (`wheel.py-api = "cp312"`), which uses
Cython and is tied to a specific CPython ABI.

## APIs

### Minimal packaging example

The complete file structure for a downstream extension:

```
examples/python_packaging/
  CMakeLists.txt                   # Build + install (3 lines of core logic)
  pyproject.toml                   # scikit-build-core config
  src/extension.cc                 # C++ source with exports
  python/my_ffi_extension/
    __init__.py                    # Re-exports from _ffi_api (auto-generated)
    _ffi_api.py                    # FFI bindings + stubs (auto-generated)
  run_example.py                   # Demo script
```

**CMakeLists.txt (complete):**

```cmake
cmake_minimum_required(VERSION 3.18)
project(my_ffi_extension)

find_package(Python COMPONENTS Interpreter REQUIRED)
find_package(tvm_ffi CONFIG REQUIRED)

add_library(my_ffi_extension SHARED src/extension.cc)
tvm_ffi_configure_target(my_ffi_extension STUB_DIR "./python" STUB_INIT ON)
install(TARGETS my_ffi_extension DESTINATION .)
tvm_ffi_install(my_ffi_extension DESTINATION .)
```

**pyproject.toml (key sections):**

```toml
[project]
name = "my-ffi-extension"
version = "0.1.0"
dependencies = ["apache-tvm-ffi"]

[build-system]
requires = ["scikit-build-core>=0.10.0", "apache-tvm-ffi"]
build-backend = "scikit_build_core.build"

[tool.scikit-build]
wheel.py-api = "py3"
wheel.packages = ["python/my_ffi_extension"]
wheel.install-dir = "my_ffi_extension"
build-dir = "build-wheel"
cmake.build-type = "Release"
cmake.version = "CMakeLists.txt"
```

**C++ source showing both export paths:**

```cpp
#include <tvm/ffi/tvm_ffi.h>

namespace my_ffi_extension {
namespace ffi = tvm::ffi;

// Path 1: Module-level export (C ABI symbol)
static int AddTwo(int x) { return x + 2; }
TVM_FFI_DLL_EXPORT_TYPED_FUNC(add_two, AddTwo)

// Path 2: Global registry export (discoverable by stubgen)
static int AddOne(int x) { return x + 1; }
TVM_FFI_STATIC_INIT_BLOCK() {
  namespace refl = tvm::ffi::reflection;
  refl::GlobalDef().def("my_ffi_extension.add_one", AddOne);
}

// Path 2: Object type with reflection
class IntPairObj : public ffi::Object {
 public:
  int64_t a;
  int64_t b;
  IntPairObj(int64_t a, int64_t b) : a(a), b(b) {}
  int64_t Sum() const { return a + b; }
  static constexpr bool _type_mutable = true;
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("my_ffi_extension.IntPair", IntPairObj, ffi::Object);
};

TVM_FFI_STATIC_INIT_BLOCK() {
  namespace refl = tvm::ffi::reflection;
  refl::ObjectDef<IntPairObj>()
      .def(refl::init<int64_t, int64_t>())
      .def_rw("a", &IntPairObj::a, "the first field")
      .def_rw("b", &IntPairObj::b, "the second field")
      .def("sum", &IntPairObj::Sum, "IntPairObj::Sum() method");
}
}  // namespace my_ffi_extension
```

**Auto-generated `_ffi_api.py`:**

```python
"""FFI API bindings for my_ffi_extension."""

# tvm-ffi-stubgen(begin): import-section
# fmt: off
# isort: off
from __future__ import annotations
from tvm_ffi import Object as _ffi_Object, init_ffi_api as _FFI_INIT_FUNC, register_object as _FFI_REG_OBJ
from tvm_ffi.libinfo import load_lib_module as _FFI_LOAD_LIB
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tvm_ffi import Object
# isort: on
# fmt: on
# tvm-ffi-stubgen(end)
# tvm-ffi-stubgen(import-object): tvm_ffi.libinfo.load_lib_module;False;_FFI_LOAD_LIB
LIB = _FFI_LOAD_LIB("my_ffi_extension", "my_ffi_extension")
# tvm-ffi-stubgen(begin): global/my_ffi_extension
# fmt: off
_FFI_INIT_FUNC("my_ffi_extension", __name__)
if TYPE_CHECKING:
    def add_one(_0: int, /) -> int: ...
    def raise_error(_0: str, /) -> None: ...
# fmt: on
# tvm-ffi-stubgen(end)
# tvm-ffi-stubgen(import-object): tvm_ffi.register_object;False;_FFI_REG_OBJ
# tvm-ffi-stubgen(import-object): ffi.Object;False;_ffi_Object
@_FFI_REG_OBJ("my_ffi_extension.IntPair")
class IntPair(_ffi_Object):
    """FFI binding for `my_ffi_extension.IntPair`."""

    # tvm-ffi-stubgen(begin): object/my_ffi_extension.IntPair
    # fmt: off
    a: int
    b: int
    if TYPE_CHECKING:
        @staticmethod
        def __c_ffi_init__(_0: int, _1: int, /) -> Object: ...
        def sum(self, /) -> int: ...
    # fmt: on
    # tvm-ffi-stubgen(end)


__all__ = [
    # tvm-ffi-stubgen(begin): __all__
    "LIB",
    "IntPair",
    "add_one",
    "raise_error",
    # tvm-ffi-stubgen(end)
]
```

**Auto-generated `__init__.py`:**

```python
"""Package my_ffi_extension."""

# tvm-ffi-stubgen(begin): export/_ffi_api
# fmt: off
# isort: off
from ._ffi_api import *  # noqa: F403
from ._ffi_api import __all__ as _ffi_api__all__
if "__all__" not in globals():
    __all__ = []
__all__.extend(_ffi_api__all__)
# isort: on
# fmt: on
# tvm-ffi-stubgen(end)
```

**Usage from Python:**

```python
import my_ffi_extension

# Module-level export (via LIB object)
my_ffi_extension.LIB.add_two(1)  # => 3

# Global registry export (via init_ffi_api, with type stubs)
my_ffi_extension.add_one(3)  # => 4

# Object with reflection
pair = my_ffi_extension.IntPair(1, 2)
pair.a   # => 1
pair.b   # => 2
pair.sum()  # => 3
```

**Build and install:**

```bash
cd examples/python_packaging
uv pip install --reinstall --verbose .
```

## Implementation

| File | Purpose |
|------|---------|
| `cmake/Utils/Library.cmake` | `tvm_ffi_configure_target`, `tvm_ffi_install` implementations |
| `python/tvm_ffi/config.py` | `tvm-ffi-config` CLI tool |
| `python/tvm_ffi/libinfo.py` | `load_lib_module`, `_find_library_by_basename`, path discovery |
| `python/tvm_ffi/registry.py` | `init_ffi_api`, `register_global_func`, `get_global_func` |
| `python/tvm_ffi/module.py` | `load_module`, `Module` class |
| `python/tvm_ffi/stub/cli.py` | `tvm-ffi-stubgen` CLI entry point |
| `python/tvm_ffi/stub/codegen.py` | Stub code generation |
| `python/tvm_ffi/stub/consts.py` | Directive and format constants |
| `python/tvm_ffi/stub/file_utils.py` | File parsing and marker detection |
| `python/tvm_ffi/stub/lib_state.py` | Loaded library state for stub generation |
| `include/tvm/ffi/function.h` | `TVM_FFI_DLL_EXPORT_TYPED_FUNC` macro |
| `include/tvm/ffi/extra/module.h` | `__tvm_ffi_` symbol prefix, `ModuleObj` |
| `include/tvm/ffi/reflection/registry.h` | `GlobalDef`, `ObjectDef` |
| `examples/python_packaging/` | Complete minimal packaging example |
| `examples/quickstart/raw_compile.sh` | Direct g++/nvcc compilation with tvm-ffi-config |
| `docs/packaging/python_packaging.rst` | Python packaging guide |
| `docs/packaging/stubgen.rst` | Stub generation guide |
| `docs/packaging/cpp_tooling.rst` | C++ tooling guide |

## History

- 2025-10-12: `tvm-ffi-stubgen` CLI tool and `tvm_ffi.stub` package (`ea02e64`)
- 2025-12-06: DSO discovery rewritten to use `importlib.metadata`; `tvm_ffi.base` removed (`6887892`)
- 2025-12-12: `tvm_ffi.libinfo.load_lib_module` utility added (`f255650`)
- 2025-12-18: Stubgen `--init-pypkg`, `--init-lib`, `--init-prefix` flags for package scaffolding (`b58c2e3`)
- 2025-12-20: CMake `tvm_ffi_configure_target` and `tvm_ffi_install` helpers (`ccd19f8`)
- 2025-12-22: Stubgen documentation added to docs site (`463083f`)
- 2025-09-07: Python API cleanup: `init_ffi_api` renamed from earlier form (`40f4d9d`)
- 2025-12-29: Wheel auditing documentation and `libtvm_ffi` exclusion guidance (`d6bfb45`)

## Related

- `.repo-knowledge/design/004-reflection-system.md` -- Reflection system underlying `GlobalDef`/`ObjectDef` and stubgen type introspection
- `.repo-knowledge/design/007-module-system.md` -- Module system for DSO loading and `__tvm_ffi_` symbol lookup
- `.repo-knowledge/design/008-python-packaging.md` -- TVM FFI's own Python packaging (scikit-build-core, Cython, versioning)
- `docs/packaging/python_packaging.rst` -- Python packaging guide (wheel auditing, RPATH)
- `docs/packaging/stubgen.rst` -- Stub generation guide (directive reference, init modes)
- `docs/packaging/cpp_tooling.rst` -- C++ tooling guide (tvm-ffi-config, RPATH)
