---
design: "0010"
title: "Python Packaging and Distribution Architecture"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-08-24"
last_updated: "2025-10-26"
scope:
  - "pyproject.toml"
  - "python/tvm_ffi"
  - "CMakeLists.txt"
  - "cmake/tvm_ffi-config.cmake"
  - "python/tvm_ffi/config.py"
  - "python/tvm_ffi/libinfo.py"
source_commits:
  - "2d41a5115f6a91e2781012a3379f9626bc9e18a1"
  - "2cf211f14a41a11c536fd16b6ea102dac3627c0a"
  - "ad8e5d2c3345c4cca1a9ce50a24238c0cafcb05e"
  - "4523a834e6d7331870230873365a895ce94da050"
  - "5a3e3cbd4dbdf1f01d61bdfbe17b38134cc45e84"
  - "40f4d9dc38e3794d5a5ec617002eba90311f86f4"
  - "24125d0ac466beb67965c1dd9ae23f2a71f424ad"
  - "315f4bb00eac8b4d26cdcd6839fb1a077bab6976"
  - "ac63fb9b"
source_ledgers:
  - ".memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md"
  - ".memory/commits/2025-08-25-2cf211f14a41a11c536fd16b6ea102dac3627c0a.md"
  - ".memory/commits/2025-08-29-ad8e5d2c3345c4cca1a9ce50a24238c0cafcb05e.md"
  - ".memory/commits/2025-08-30-4523a834e6d7331870230873365a895ce94da050.md"
  - ".memory/commits/2025-09-01-5a3e3cbd4dbdf1f01d61bdfbe17b38134cc45e84.md"
  - ".memory/commits/2025-09-07-40f4d9dc38e3794d5a5ec617002eba90311f86f4.md"
  - ".memory/commits/2025-09-07-24125d0ac466beb67965c1dd9ae23f2a71f424ad.md"
  - ".memory/commits/2025-09-10-315f4bb00eac8b4d26cdcd6839fb1a077bab6976.md"
  - ".memory/commits/2025-10-26-ac63fb9b.md"
---

# Python Packaging and Distribution Architecture

## TL;DR
- `tvm_ffi` is a standalone pip-installable Python package (`apache-tvm-ffi`) built via scikit-build-core + Cython, enabling lightweight downstream packages that depend only on the FFI layer without the full TVM compiler.
- The package bundles the compiled Cython extension (`core.cpython-*.so`), the shared library (`libtvm_ffi.{so,dylib,dll}`), C++ headers, dlpack headers, and CMake config files, making it both a Python runtime library and a C++ SDK.
- The `tvm-ffi-config` CLI and `cmake/tvm_ffi-config.cmake` provide downstream C++ integration, enabling `find_package(tvm_ffi CONFIG)` in CMake projects.

## Problem Statement
TVM's FFI layer (type-erased values, packed functions, object system, containers) is used by the compiler, runtime, and downstream tools alike. Previously, using any FFI functionality required installing the entire TVM compiler toolchain. Decoupling the FFI into a standalone package allows lightweight deployment targets (e.g., inference-only runtimes, model serving libraries) to depend on `tvm_ffi` alone, reducing dependency weight and build times.

## Context and Constraints
- The package must support Python 3.8+ across Linux (x86_64, aarch64), macOS (x86_64, arm64), and Windows (AMD64).
- Wheels must bundle platform-specific shared libraries and Cython extensions.
- The Python Stable ABI (SABI, Limited API) starting at cp312 must be supported to avoid per-minor-version wheel builds for Python 3.12+.
- Editable installs (`pip install -e .`) must work for development without requiring Cython recompilation for pure-Python changes.
- Downstream C++ projects must be able to discover headers, libraries, and CMake config from the installed Python package.

## Goals
- Provide a zero-runtime-dependency Python package (only `typing-extensions>=4.5` required).
- Support `pip install`, editable installs, and sdist/wheel distribution via cibuildwheel.
- Provide `tvm-ffi-config` CLI for querying include/lib/cmake paths.
- Provide `cmake/tvm_ffi-config.cmake` for `find_package(tvm_ffi CONFIG)` support.
- Support dual CMake mode: subproject (header-only or object library) and root project (tests, Python module, install targets).

## Non-Goals
- Bundling the TVM compiler or runtime libraries beyond the FFI layer.
- Supporting non-Python package managers (e.g., conda) as a primary distribution channel (though conda-forge recipes can wrap the pip package).
- Auto-detecting CUDA or other accelerator toolchains during package build (CUDA support is handled by downstream packages).

## Design
### Components and Responsibilities
- **`pyproject.toml`**: Package metadata, build system (`scikit-build-core`), version management (`setuptools_scm` with `git tag` as the single source of truth; commit `ac63fb9b`), wheel/sdist configuration, linting tools, and cibuildwheel settings. The `version` field is `dynamic = ["version"]` and `setuptools_scm` derives it from the latest git tag.
- **`python/tvm_ffi/__init__.py`**: Package entry point. Loads `libtvm_ffi` via ctypes (RTLD_GLOBAL), then imports all public modules (registry, containers, ndarray, module, dtype, error, etc.).
- **`python/tvm_ffi/libinfo.py`**: Library and path discovery. Uses `importlib.metadata` (RECORD file) as primary lookup, with fallback to filesystem heuristics (build/lib, LD_LIBRARY_PATH, etc.).
- **`python/tvm_ffi/config.py`**: `tvm-ffi-config` CLI entry point. Delegates to `libinfo` for path queries.
- **`cmake/tvm_ffi-config.cmake`**: CMake config-mode file. Discovers paths by invoking `python -m tvm_ffi.config`, then creates `tvm_ffi::header` (interface) and `tvm_ffi::shared` (imported shared) targets.
- **`cmake/Utils/Library.cmake`**: CMake utility functions (`tvm_ffi_add_target_from_obj`, `tvm_ffi_add_prefix_map`, `tvm_ffi_add_msvc_flags`, `tvm_ffi_add_apple_dsymutil`) for building shared/static libraries from object targets.

- **RPATH configuration** (CMakeLists.txt): The Cython extension module has `INSTALL_RPATH` set to `@loader_path/lib` on macOS and `$ORIGIN/lib` on Linux, so it can find `libtvm_ffi_shared` at relative `lib/` path within the wheel. The `BUILD_WITH_INSTALL_RPATH` property is NOT set (removed in `ad8e5d2`), letting CMake handle build vs install RPATH distinction properly for scikit-build-core.
- **Extension wheel packaging example** (`examples/packaging/`): A complete reference project demonstrating how to build an ABI-agnostic wheel for a tvm-ffi extension, including `CMakeLists.txt`, `pyproject.toml`, C++ source with both C-symbol export (`TVM_FFI_DLL_EXPORT_TYPED_FUNC`) and reflection-based registration (`refl::GlobalDef().def(...)`), and a Python package with the `_LIB`/`_ffi_api` pattern. Added in commits `4523a83` and `5a3e3cb`.
- **`tvm_ffi-config.cmake` improvements**: Now includes `Utils/Library.cmake` (providing `tvm_ffi_add_prefix_map`, `tvm_ffi_add_apple_dsymutil`) for downstream consumers. Install directory changed from `lib/cmake/tvm_ffi/` to `cmake/` for simpler wheel layout. `find_cmake_path` updated to match.

### Data Contracts and Invariants
- The package name is `apache-tvm-ffi` and the import name is `tvm_ffi`. These must remain consistent across pyproject.toml, importlib.metadata lookups, and CMake config.
- `libinfo.find_libtvm_ffi()` must always succeed after a successful `pip install`. The primary lookup path is via `importlib.metadata.distribution("apache-tvm-ffi").read_text("RECORD")`.
- `tvm_ffi.LIB` (ctypes.CDLL) must be loaded with `RTLD_GLOBAL` mode before any Cython extension import, as the extension references C symbols from `libtvm_ffi`.
- The Cython extension is built as `core.cpython-*.so` and placed into `tvm_ffi/` at install time. It is Python Stable ABI (cp312-abi3) when built with Python 3.12+.

### Control Flow
1. **Build**: `scikit-build-core` invokes CMake with `-DTVM_FFI_BUILD_PYTHON_MODULE=ON`. CMake compiles `tvm_ffi_objs` (C++ core), `tvm_ffi_shared` (shared library), runs Cython to generate `core.cpp`, and compiles the Cython extension module.
2. **Install**: scikit-build-core places the shared library, Cython extension, Python sources, headers, and CMake config into the wheel. `setuptools_scm` writes `_version.py`. A lint script (`tests/lint/check_version.py`) verifies that C++ macros (`TVM_FFI_VERSION_MAJOR/MINOR/PATCH`) and Rust `Cargo.toml` versions match the canonical `setuptools_scm` version (commit `ac63fb9b`).
3. **Import**: `tvm_ffi.__init__` loads `libtvm_ffi` via `libinfo.load_lib_ctypes()` (ctypes CDLL with RTLD_GLOBAL), then Cython `core` is imported, providing the fast path for all FFI operations.
4. **Downstream C++**: A downstream CMake project runs `python -m tvm_ffi.config --cmakedir` to get the cmake dir, sets `tvm_ffi_ROOT`, and calls `find_package(tvm_ffi CONFIG REQUIRED)`. This creates `tvm_ffi::header` and `tvm_ffi::shared` targets.

### Extension Points
- New Python modules can be added to `python/tvm_ffi/` and imported in `__init__.py`.
- New Cython `.pxi` files can be included from `core.pyx`.
- New CMake utility functions can be added to `cmake/Utils/` and included from `tvm_ffi-config.cmake`.
- New `tvm-ffi-config` flags can be added to `config.py`.

## Alternatives Considered
### Pure ctypes FFI (no Cython)
- Pros: Simpler build, no Cython dependency, easier cross-platform wheels.
- Cons: Significantly slower argument marshaling (~10x overhead per call), no direct C struct access, complex error propagation. The performance cost is unacceptable for the FFI layer which is on the hot path of every ML kernel invocation.

### pybind11 bindings
- Pros: Mature ecosystem, good C++ integration, automatic type conversion.
- Cons: Requires per-Python-version compilation (no Stable ABI support), larger binary size, less control over the marshaling hot path. The TVM FFI needs fine-grained control over type-index-based dispatch that pybind11's template machinery does not expose efficiently.

## Trade-offs
- **Cython complexity vs. performance**: The Cython binding layer (~1900 lines across 8 `.pxi` files) is substantial but provides zero-overhead access to C structs, direct type-index dispatch, and seamless error propagation between Python and C++ with traceback stitching.
- **SABI vs. feature access**: Using Stable ABI (Limited API) for Python 3.12+ means one wheel covers all future Python versions, but restricts the extension to a subset of CPython internals. Features like `PyFrame_LocalsToFastRev` are unavailable.
- **RTLD_GLOBAL loading**: Loading `libtvm_ffi` with RTLD_GLOBAL makes its symbols available to all subsequently loaded shared libraries (including downstream kernel libraries), but can cause symbol conflicts with other libraries. The torch import-first hack in `__init__.py` mitigates a known conflict on Windows.

## Interfaces and Compatibility
- **Python API**: `import tvm_ffi` provides all public symbols (Object, Function, Array, Dict, Tensor, etc.). See `__all__` in `__init__.py`. API cleaned up in commit `40f4d9d`: `register_func` -> `register_global_func`, `_init_api` -> `init_ffi_api`, `ObjectGeneric` -> `ObjectConvertible`. Internal modules prefixed with underscore (`_tensor.py`, `_convert.py`, `_dtype.py`). Per-device shortcuts (`cpu`, `cuda`, `rocm`) removed; use `tvm_ffi.device("cuda")` instead. `DLDeviceType` enum added. Sphinx API reference docs added in commit `24125d0`.
- **CLI**: `tvm-ffi-config --includedir --libdir --cmakedir --cxxflags --ldflags --libfiles --libs --cflags --sourcedir --cython-lib-path`.
- **CMake**: `find_package(tvm_ffi CONFIG)` provides `tvm_ffi::header` (interface) and `tvm_ffi::shared` (imported shared) targets, plus utility functions from `Library.cmake`.
- **Wheel**: `apache_tvm_ffi-{version}-cp312-abi3-{platform}.whl` for Python 3.12+ (Stable ABI), plus per-version wheels for cp38-cp311.

## Failure Modes and Mitigations
- **Library not found**: `libinfo.find_libtvm_ffi()` raises `RuntimeError("Cannot find libtvm_ffi")` if the shared library is missing. Mitigation: fallback search in build/lib, LD_LIBRARY_PATH, PATH.
- **Symbol conflict with torch**: Loading both torch and tvm_ffi can cause DLL symbol conflicts on Windows. Mitigation: `__init__.py` imports torch first to establish its symbol table.
- **Editable install stale Cython**: C++/Cython changes are not reflected until `pip install -e .` is re-run. Mitigation: `editable.rebuild = false` in pyproject.toml avoids auto-rebuild confusion.

## Observability and Validation
- `python -c "import tvm_ffi; print(tvm_ffi.__version__)"` verifies successful import and version.
- `tvm-ffi-config --includedir` verifies path discovery works.
- `pytest tests/python/` validates the full binding layer.
- CI runs `cibuildwheel` across all target platforms.

## Migration and Rollout
- Downstream packages that previously used `from tvm.runtime import ...` must migrate to `import tvm_ffi` for the FFI layer.
- Downstream C++ projects must switch from manual include path setup to `find_package(tvm_ffi CONFIG)`.

## Diagrams
- [.memory/diagrams/0008-python-package-architecture.md](.memory/diagrams/0008-python-package-architecture.md)

## Related ADRs
- [.memory/ADRs/0014-scikit-build-core-sabi-packaging.md](.memory/ADRs/0014-scikit-build-core-sabi-packaging.md)
- [.memory/ADRs/0015-dual-cmake-mode.md](.memory/ADRs/0015-dual-cmake-mode.md)

## Evidence Matrix
- `pyproject.toml` scikit-build-core config -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `pyproject.toml`
- `libinfo.py` RECORD-based library discovery -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `python/tvm_ffi/libinfo.py`
- `config.py` CLI entry point -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `python/tvm_ffi/config.py`
- `tvm_ffi-config.cmake` find_package support -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `cmake/tvm_ffi-config.cmake`
- `__init__.py` RTLD_GLOBAL load and torch hack -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `python/tvm_ffi/__init__.py`
- SABI cp312-abi3 wheel config -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `pyproject.toml` lines 106, 236
- RPATH setup (INSTALL_RPATH @loader_path/lib, $ORIGIN/lib) -> `.memory/commits/2025-08-25-2cf211f14a41a11c536fd16b6ea102dac3627c0a.md` + `2cf211f` + `CMakeLists.txt`
- cibuildwheel config (cp39-cp312, skip musllinux, abi3 test on cp312) -> `2cf211f` + `pyproject.toml`
- numpy-optional dtype.py guard -> `2cf211f` + `python/tvm_ffi/dtype.py`
- RPATH fix: remove BUILD_WITH_INSTALL_RPATH -> `.memory/commits/2025-08-29-ad8e5d2c3345c4cca1a9ce50a24238c0cafcb05e.md` + `ad8e5d2` + `CMakeLists.txt`
- Wheel packaging example -> `.memory/commits/2025-08-30-4523a834e6d7331870230873365a895ce94da050.md` + `4523a83` + `examples/packaging/`
- cmake install path change (cmake/ instead of lib/cmake/tvm_ffi/) -> `4523a83` + `cmake/tvm_ffi-config.cmake`
- Library.cmake inclusion in tvm_ffi-config.cmake -> `4523a83` + `cmake/tvm_ffi-config.cmake`
- Missing packaging example files (run_example.py, extension.cc) -> `.memory/commits/2025-09-01-5a3e3cbd4dbdf1f01d61bdfbe17b38134cc45e84.md` + `5a3e3cb` + `examples/packaging/`
- Python API cleanup (register_global_func, init_ffi_api, underscore modules) -> `.memory/commits/2025-09-07-40f4d9dc38e3794d5a5ec617002eba90311f86f4.md` + `40f4d9d` + `python/tvm_ffi/`
- C++ API reference docs (Breathe/Doxygen) -> `.memory/commits/2025-09-07-24125d0ac466beb67965c1dd9ae23f2a71f424ad.md` + `24125d0` + `docs/reference/cpp/index.rst`
- Version bump 0.1.0a8 -> 0.1.0a9 -> `.memory/commits/2025-09-10-315f4bb00eac8b4d26cdcd6839fb1a077bab6976.md` + `315f4bb` + `pyproject.toml`
- `setuptools_scm` adoption: git-tag-derived Python versioning, `_version.py` auto-generated, `check_version.py` lint for cross-language version consistency -> `.memory/commits/2025-10-26-ac63fb9b.md` + `ac63fb9b` + `pyproject.toml`, `tests/lint/check_version.py`, `.github/workflows/`, `include/tvm/ffi/c_api.h`

## Open Questions
- Whether to support `conda` as a first-class distribution channel alongside pip.
- Whether to ship pre-built wheels with CUDA support in the base package or keep it as a separate addon.

## Confidence and Risk
- Confidence: high
- Residual risks: The RTLD_GLOBAL loading strategy may cause symbol conflicts with future versions of torch or other large C++ libraries. The torch import-first workaround is fragile and specific to one known conflict scenario.
