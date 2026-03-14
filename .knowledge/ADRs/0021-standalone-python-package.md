---
scope:
  - "0014-python-bindings"
  - "0016-packaging-and-build"
---
# Standalone tvm_ffi Python Package

**TL;DR**: The decision to extract `tvm_ffi` as a standalone pip-installable Python package (`apache-tvm-ffi`) separate from the main TVM Python package, enabling lightweight FFI consumers without requiring the full TVM runtime.

## Context

The main TVM Python package (`apache-tvm`) contains the full compiler stack (LLVM integration, codegen, auto-tuning, etc.) with heavy dependencies. Downstream library plugins and lightweight inference runtimes need only the FFI layer (Object, Function, Array, Map, NDArray, Module, Error) to interact with compiled TVM artifacts. Requiring a full TVM install for these consumers creates:

- Unnecessary dependency bloat (LLVM, CUDA toolkit headers, etc.)
- Version coupling (FFI consumers forced to upgrade when compiler changes)
- Installation complexity (building TVM from source requires many prerequisites)

The FFI was previously embedded in `tvm.runtime`, making it impossible to import without the full `tvm` package.

Usecases:
- A lightweight Python wrapper for a pre-compiled TVM kernel library that only needs `load_module` and `Function.__call__`.
- A downstream ML framework plugin that uses `NDArray`, `Device`, and `Function` for interop without needing the TVM compiler.
- CI/CD pipelines that test FFI-level functionality independently of the compiler stack.
- Downstream C++ projects that `pip install apache-tvm-ffi` and then `find_package(tvm_ffi CONFIG)` to link against the library, without needing a TVM source checkout.

Design Decisions:
- **Standalone package**: `apache-tvm-ffi` is published as its own PyPI package with zero Python dependencies. The only requirement is `libtvm_ffi.so` (bundled in the wheel).
- **Self-contained wheel**: The wheel bundles not only the Python package and shared library, but also C++ headers, CMake config files, vendored 3rdparty source (dlpack, libbacktrace), and the C++ source for recompilation. This makes the wheel sufficient for both Python usage and downstream C++ development.
- **scikit-build-core backend**: Uses `scikit-build-core >= 0.10.0` with Cython for the build system, providing native CMake integration, Stable ABI (SABI 3.12+) wheel support, and cross-platform wheel building via `cibuildwheel`.
- **CMake dual-mode**: The same `CMakeLists.txt` supports both standalone builds (root project with `TVM_FFI_BUILD_PYTHON_MODULE=ON`) and sub-project integration via `add_subdirectory`. A guard (`if (NOT ${PROJECT_NAME} STREQUAL ${CMAKE_PROJECT_NAME}) return()`) separates the two modes.

**Alternatives considered**:

1. **Keep FFI inside `tvm.runtime`** (status quo):
   - Pros: Single package, no packaging complexity, single import namespace.
   - Cons: All FFI consumers must install the full TVM package. Version coupling between compiler and runtime. Cannot independently version the FFI layer.

2. **Publish as separate wheel without source** (binary-only):
   - Pros: Smaller wheel size, simpler packaging.
   - Cons: Downstream C++ consumers cannot compile against the headers without a separate header package. Cannot recompile the library with different options (e.g., `TVM_FFI_USE_EXTRA_CXX_API=OFF`). The self-contained wheel eliminates the need for a separate `-dev` package.

3. **Header-only Python package + separate binary distribution**:
   - Pros: Headers always available, binary can be platform-specific.
   - Cons: Two packages to manage and version together. The single wheel approach is simpler for users.

**Consequences**:
- The `tvm_ffi` package has its own version (`0.1.0a0` initially), decoupled from the main TVM version.
- Downstream packages can declare `apache-tvm-ffi` as a dependency instead of `apache-tvm`.
- The main TVM package will eventually depend on `apache-tvm-ffi` rather than bundling the FFI code.
- Two import namespaces coexist during transition: `tvm.runtime` (legacy) and `tvm_ffi` (new standalone).
- Wheel size increases due to bundled source and headers, but this is acceptable for the developer workflow benefits.
- SABI 3.12+ support reduces the number of platform-specific wheels needed.

## Implementation Notes

- Package name: `apache-tvm-ffi`. Import name: `tvm_ffi`.
- Entry point: `tvm-ffi-config` CLI for C++ toolchain discovery.
- `find_package(tvm_ffi CONFIG)` calls `python -m tvm_ffi.config` to discover paths.
- The package requires Python 3.9+ but targets Stable ABI 3.12+ for wheel compatibility.
- `libinfo.py` handles library discovery across installed-wheel and source-build layouts.

## Related Design Docs

- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Python package architecture
- [`.knowledge/designs/0016-packaging-and-build.md`](../designs/0016-packaging-and-build.md) -- Build system design
