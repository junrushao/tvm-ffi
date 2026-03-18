---
scope:
  - "0012-python-bindings.md"
  - "0013-packaging.md"
---
# ADR: Standalone tvm_ffi Python Package

**TL;DR**: Decision to decouple the FFI into a standalone pip-installable `tvm_ffi` Python package, separate from the main TVM compiler, enabling lightweight downstream dependencies and independent versioning.

## Context
- The TVM FFI was historically compiled and shipped as part of the monolithic `tvm` Python package. Users who only needed the FFI primitives (e.g., runtime extensions, inference-only deployments) were forced to install the full compiler stack.
- Downstream projects that extended the runtime (device backends, custom kernels) needed a stable, minimal dependency to link against. The full `tvm` package was too heavy and too volatile.
- Cross-language binding authors (Rust, Python, other languages) needed a clean, well-defined library boundary to target.

Usecases:
- Deploying compiled ML models in production with minimal dependencies (just `tvm_ffi`, not the full compiler).
- Building pip-installable extensions (`my_ffi_extension` pattern) that depend on the stable FFI without pulling in the compiler.
- Testing and CI for the FFI layer independently of compiler changes.

Design Decisions:
- **Decouple `tvm_ffi` as a standalone pip package** with its own `pyproject.toml`, version, and release cycle.
- **Use scikit-build-core as build backend** for Cython transpilation and shared library compilation, with Stable ABI support on Python >= 3.12.
- **Provide `tvm-ffi-config` CLI and `tvm_ffi-config.cmake`** for downstream C++ projects to discover and link against the installed package.
- **Optional numpy/torch**: Neither is a hard import-time dependency. `numpy.dtype` conversion is lazy; torch CUDA stream helper is JIT-compiled on first use.
- **RPATH relative linking**: The Cython extension finds `libtvm_ffi.so` via `@loader_path/lib` (macOS) / `$ORIGIN/lib` (Linux), not absolute paths.

## Implementation Notes
- `pyproject.toml` declares `scikit-build-core>=0.10.0` and `cython` as build requirements. The `tvm-ffi-config` CLI is installed as a console entry point.
- cibuildwheel builds `cp39-cp312`, skips `musllinux`, tests only on `cp312` (the abi3 target).
- The CMake build produces both `libtvm_ffi_shared.so` and the Cython `core.abi3.so` extension. Install destinations are tuned for `find_package(tvm_ffi)` discovery.
- `BUILD_WITH_INSTALL_RPATH` is NOT set on the Cython target (fixed in commit ad8e5d2) to allow proper RPATH behavior under scikit-build-core.

## Related Design Docs
- [0012-python-bindings.md](../designs/0012-python-bindings.md) -- Cython binding layer architecture
- [0013-packaging.md](../designs/0013-packaging.md) -- Build and wheel packaging details
- [0004-function-system.md](../designs/0004-function-system.md) -- Global function registry used by `init_ffi_api` (renamed from `_init_api` in 40f4d9d)
