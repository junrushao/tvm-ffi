---
adr: "0014"
title: "scikit-build-core with Python Stable ABI for Packaging"
status: "accepted"
date: "2025-08-24"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "Python package maintainers"
  - "Downstream library authors"
tags:
  - "packaging"
  - "python"
  - "build-system"
source_commits:
  - "2d41a5115f6a91e2781012a3379f9626bc9e18a1"
source_ledgers:
  - ".memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md"
---

# ADR-0014: scikit-build-core with Python Stable ABI for Packaging

## TL;DR
- `tvm_ffi` uses `scikit-build-core` as the PEP 517 build backend, delegating CMake-based compilation (C++ shared library + Cython extension) to a modern Python packaging tool, with `setuptools-scm` for version management.
- Python Stable ABI (Limited API, tagged `cp312-abi3`) is used for the Cython extension starting at Python 3.12, producing a single wheel that works on all future CPython versions 3.12+.

## Status
Accepted

## Context
TVM FFI consists of a C++ shared library (`libtvm_ffi`) and a Cython extension module (`core`). Both must be compiled from source during package build. Traditional `setup.py`-based builds with `setuptools` require custom build logic for CMake integration and do not natively support Stable ABI tagging. The project needs a build backend that:
1. Integrates CMake as the primary build system (since the C++ library is already CMake-based).
2. Supports editable installs for development.
3. Supports Python Stable ABI wheel tagging to minimize the number of platform wheels.
4. Supports sdist generation with correct file inclusion.
5. Is compatible with `cibuildwheel` for CI-based wheel building.

## Decision Drivers
- CMake is already the build system for the C++ library; the build backend must delegate to it rather than duplicating build logic.
- Wheel proliferation: without Stable ABI, a wheel must be built for every Python minor version on every platform (e.g., cp38, cp39, cp310, cp311, cp312, cp313), leading to 30+ wheels per release.
- Development workflow: editable installs must work without requiring Cython recompilation for pure-Python changes.
- Version management: versions must be derived from git tags, not manually maintained.

## Decision
Use `scikit-build-core>=0.10.0` as the PEP 517 build backend with the following configuration:

1. **Build system**: `scikit-build-core` invokes CMake with `-DTVM_FFI_BUILD_PYTHON_MODULE=ON`, which compiles the C++ library and Cython extension in a single CMake build.
2. **Stable ABI**: `wheel.py-api = "cp312"` in `pyproject.toml` tells scikit-build-core to use the Limited API for Python 3.12+. CMake uses `Python_add_library(... USE_SABI 3.12)` when the `Development.SABIModule` component is available.
3. **Version management**: `setuptools-scm` reads version from git tags and writes `python/tvm_ffi/_version.py`.
4. **Editable installs**: `editable.rebuild = false` avoids automatic rebuild, requiring explicit `pip install -e .` for C++/Cython changes.
5. **cibuildwheel**: Configured to build cp38-cp312 per-version wheels plus cp312-abi3 (covers 3.12+) and cp314t (free-threaded), skipping musllinux.

## Alternatives Considered
### setuptools + custom build_ext
- Pros: Well-known, large ecosystem.
- Cons: No native CMake integration (requires `cmake_build_extension` or custom code), no Stable ABI support without manual wheel tag manipulation, increasingly deprecated for compiled extensions.

### meson-python
- Pros: Modern, good C/C++ integration, supports Stable ABI.
- Cons: Would require rewriting the existing CMake build system in Meson. The C++ library build is already CMake-based with complex conditional compilation (libbacktrace, extra CXX API, MSVC flags), making a port costly.

### CMake alone (no Python build backend)
- Pros: Full control, no additional dependencies.
- Cons: Cannot produce PEP-compliant wheels, no sdist support, no PyPI upload, no editable install support.

## Why This Option Won
- **Zero CMake migration cost**: scikit-build-core delegates to the existing CMakeLists.txt without modification. The only addition is a `TVM_FFI_BUILD_PYTHON_MODULE` option.
- **Stable ABI support**: Built-in support via `wheel.py-api` configuration, reducing wheel count from ~30 to ~12 (per-version for 3.8-3.11, single abi3 for 3.12+, plus free-threaded 3.14t).
- **Editable install**: scikit-build-core supports `pip install -e .` with configurable rebuild behavior.
- **setuptools-scm integration**: Native support for version metadata from git tags.
- **cibuildwheel compatibility**: First-class support as the recommended CMake build backend.

## Consequences
### Positive
- Single abi3 wheel covers Python 3.12, 3.13, and all future CPython versions.
- Development workflow is streamlined: `pip install -e .` for full rebuild, pure-Python changes reflected immediately.
- Version is always derived from git tags, eliminating version drift.
- CI wheel building is standardized via cibuildwheel.

### Negative
- Developers must install `scikit-build-core`, `cython`, and `setuptools-scm` as build dependencies.
- Editable install requires explicit re-run for C++/Cython changes (no automatic rebuild).
- The `build/` directory is shared between scikit-build-core and manual CMake builds, requiring care to avoid conflicts.

### Risks
- scikit-build-core is newer than setuptools and may have undiscovered edge cases. Mitigation: pinned minimum version (`>=0.10.0`).
- Stable ABI may restrict future use of CPython internals in the Cython extension. Mitigation: the current Cython code uses only Limited API-compatible operations.

## Implementation Notes
- `pyproject.toml` `[tool.scikit-build]` section configures CMake args, wheel packages path, sdist includes/excludes, and editable install behavior.
- `CMakeLists.txt` uses `Python_add_library(core MODULE ${core_cpp} USE_SABI 3.12 WITH_SOABI)` when SABI is available, falling back to `Python_add_library(core MODULE ${core_cpp} WITH_SOABI)` otherwise.
- The Cython extension links against `tvm_ffi_objs` (object library) to avoid double-linking the shared library.
- `wheel.install-dir = "tvm_ffi"` ensures the compiled extension and library land in the correct package directory.

## Validation
- `pip install --verbose -e .` succeeds and produces a working `tvm_ffi` package.
- `python -c "import tvm_ffi; print(tvm_ffi.__version__)"` prints the git-derived version.
- `pytest tests/python/` passes with the installed package.
- cibuildwheel produces wheels for all target platforms (Linux x86_64/aarch64, macOS x86_64/arm64, Windows AMD64).

## Migration and Rollback
- Rollback: Replace `scikit-build-core` with `setuptools` + `cmake_build_extension` in pyproject.toml. Would require custom build_ext logic and manual wheel tagging.
- No data migration needed as this is a build system change.

## Related Design Docs
- [.memory/designs/0010-python-packaging-architecture.md](.memory/designs/0010-python-packaging-architecture.md)

## Related Diagrams
- [.memory/diagrams/0008-python-package-architecture.md](.memory/diagrams/0008-python-package-architecture.md)

## Evidence Matrix
- scikit-build-core config in pyproject.toml -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `pyproject.toml` lines 100-133
- SABI configuration -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `pyproject.toml` line 106 (`wheel.py-api = "cp312"`)
- CMake SABI usage -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `CMakeLists.txt` (Python_add_library with USE_SABI)
- setuptools-scm version -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `pyproject.toml` lines 288-290
- cibuildwheel config -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `pyproject.toml` lines 230-253

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Monitor scikit-build-core releases for Stable ABI improvements.
- Consider adding `cp313t` (free-threaded) wheel target when CPython 3.13t stabilizes.
- The cibuildwheel configuration was refined in commit `2cf211f`: builds cp39-cp312, skips musllinux, tests only on cp312 (abi3), runs pytest correctly via `{package}/tests/python`. RPATH setup (`@loader_path/lib` on macOS, `$ORIGIN/lib` on Linux) was added for the Cython extension and further fixed in `ad8e5d2` (removing `BUILD_WITH_INSTALL_RPATH` to let scikit-build-core handle it correctly).
