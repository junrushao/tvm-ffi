---
scope:
  - ".knowledge/designs/0015-python-packaging.md"
  - ".knowledge/designs/0014-python-bindings.md"
---
# ADR 013: Package tvm_ffi as a Standalone Installable Python Package

**TL;DR**:
- The FFI layer is decoupled from the main TVM compiler and packaged as `apache-tvm-ffi`, a standalone pip-installable wheel with zero Python dependencies.
- This enables lightweight downstream packages that depend only on the FFI (not the entire TVM compiler stack) and supports independent versioning and release cycles.

## Context

TVM FFI provides core abstractions (Object, Function, NDArray, containers) that are consumed by:
1. The main TVM compiler (Python frontend).
2. Downstream ML serving frameworks that only need FFI for loading and calling compiled models.
3. Custom kernel libraries that use `load_module` and `get_global_func`.

Previously, these consumers all had to depend on the full TVM Python package, which includes the compiler, passes, and extensive dependencies. Lightweight deployments (e.g., inference-only servers) only need the FFI layer.

Usecases:
- A model serving container installs only `apache-tvm-ffi` (plus compiled models) for minimal image size.
- The main TVM compiler package (`apache-tvm`) depends on `apache-tvm-ffi` and adds compiler-specific Python modules.
- A downstream project compiles C++ kernels against tvm_ffi headers (via `find_package(tvm_ffi)`) without installing the full TVM compiler.

Design Decisions:
- Package as `apache-tvm-ffi` with zero Python runtime dependencies.
- Use `scikit-build-core` as the PEP 517 build backend to drive CMake + Cython compilation.
- Bundle C++ shared library, headers, dlpack headers, cmake config, and Cython extension inside the wheel.
- Provide `tvm-ffi-config` CLI and `tvm_ffi-config.cmake` for downstream build integration.
- Target Stable ABI on Python 3.12+ for forward compatibility.
- CMake supports dual-mode: standalone wheel build and subdirectory inclusion.

## Alternatives

### Alternative A: Keep FFI embedded in the monolithic TVM package
- Description: The FFI remains part of `apache-tvm`. Users who need only the FFI install the full package and import a subset.
- Pros: Single package to maintain; no dependency management between FFI and compiler packages.
- Cons: Bloated install size for inference-only use cases. Coupled release cycle forces FFI changes to wait for TVM releases. Downstream C++ projects that only need the FFI header and library must install the full Python package with all its dependencies (numpy, scipy, etc.).
- Why rejected: The FFI is a foundational layer with a stable API surface. Inference-only deployments should not carry compiler-weight dependencies.

### Alternative B: Header-only / system-installed C library (no Python package)
- Description: Distribute the FFI as a system-level C/C++ library (e.g., via apt/brew). Python bindings installed separately via pip.
- Pros: Standard C library distribution; language-agnostic; separate C and Python packaging.
- Cons: Requires system package manager coordination; version mismatch risk between C library and Python bindings; no cross-platform build reproducibility; users must manually ensure header/library versions match the Python extension.
- Why rejected: A single wheel that bundles both the shared library and Python bindings ensures version consistency. The `find_package(tvm_ffi)` pattern discovers the correct versions from the Python installation.

## Implementation Notes
- The wheel layout places the shared library at `tvm_ffi/lib/libtvm_ffi.so`, headers at `tvm_ffi/include/`, and cmake config at `tvm_ffi/lib/cmake/`. This mirrors a standard installation prefix within the Python package.
- `libinfo.py` searches multiple paths to support both installed wheels and source builds (editable installs).
- The CMake subproject guard (`PROJECT_NAME != CMAKE_PROJECT_NAME`) allows the same CMakeLists.txt to serve both as the wheel build root and as a subdirectory in larger projects.
- `cibuildwheel` configuration skips Python < 3.12 because the Stable ABI (`abi3`) wheel from 3.12 serves all future versions, making older builds redundant.

## Related Design Docs
- `.knowledge/designs/0015-python-packaging.md` -- Full packaging architecture details
- `.knowledge/designs/0014-python-bindings.md` -- The Cython binding layer packaged by this wheel
