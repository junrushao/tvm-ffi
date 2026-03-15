# Group 10 Distillation: Standalone Repo Establishment

**Commits**: ef6d57b..8f4e044 (25 commits)
**Period**: Repo independence setup -- CI, lint, docs, and a few significant code changes
**Theme**: Establishing the apache/tvm-ffi standalone repository with CI/CD, documentation, tooling, and several notable code additions

## Narrative Summary

This group marks the transition of tvm-ffi from a subdirectory of the TVM monorepo to a standalone Apache project at `github.com/apache/tvm-ffi`. The bulk of the work is infrastructure and documentation, but four code changes stand out.

### CI and Lint Infrastructure (11 commits)

The repository gained a complete CI pipeline:

1. **GitHub Actions** (ef6d57b): `ci_test.yml` with prepare/lint/test jobs across 4 platform targets (Linux x86_64, Linux aarch64, Windows AMD64, macOS arm64), plus `publish_wheel.yml` for PyPI publishing via `cibuildwheel` with OIDC trusted publishing.

2. **Pre-commit modernization** (64e4b7f): Replaced the ad-hoc `task_lint.sh` CI approach with native pre-commit hooks -- ruff (check+format), clang-format, cython-lint, shfmt, shellcheck, check-yaml, check-toml, and local hooks for ASF header and file type checks. CI lint job now uses `pre-commit/action@v3.0.1`.

3. **Ruff rule expansion** (0bc968d): Enabled `UP`, `PL`, `I`, `RUF`, `NPY`, `F`, `PTH`, `D` ruff rules. Migrated all Python code from `os.path` to `pathlib.Path`, from `typing.List`/`Sequence` to `collections.abc` equivalents. Deleted legacy `task_lint.sh` and `git-clang-format.sh`.

4. **Type annotation enforcement** (8f4e044): Enabled the `ANN` ruff rule set, adding type annotations to all public Python APIs (~37 files). Also fixed a latent bug where `StreamContext.__enter__` and `TorchStreamContext.__enter__` did not `return self`.

### Repo Scaffolding (5 commits)

- `.asf.yaml` (306c8d0, 3e07df4, 46f7358, 89e0b88): ASF GitHub integration for branch protection (migrated from `dev` to `main`), squash-only merge policy with PR title+description commit messages, and mailing list notifications.
- `CONTRIBUTING.md` (5facac5): Contribution workflow, stability philosophy (C ABI first), and `0.X.Y` versioning scheme.
- Version bumps: `0.1.0a13` -> `0.1.0b0` (3e07df4) -> `0.1.0b1` (5facac5) -> `0.1.0b3` (9432896).

### Documentation (7 commits)

- Updated all docs to reflect standalone `apache/tvm-ffi` URLs (011b105).
- New compiler integration guide (240ea44) with kernel/graph compiler and custom module patterns.
- Runtime state management section for compiler runtimes (5511c6c): singleton `GlobalState` + `TVM_FFI_STATIC_INIT_BLOCK` registration pattern.
- `tvm_ffi.cpp.load_inline` documentation (742b16e) with examples migrated from `DLTensor*` to `tvm::ffi::Tensor`.
- Pure C example for low-level ABI/codegen integration (c100338).

### Notable Code Changes (4 commits)

1. **StreamContext Python API** (3197cd0): New `python/tvm_ffi/stream.py` module with `StreamContext`, `TorchStreamContext`, `use_raw_stream()`, and `use_torch_stream()`. These are context managers for the FFI thread-local stream (`TVMFFIEnvSetStream`/`TVMFFIEnvGetStream`), enabling `with` statement stream management from Python. `core._env_set_current_stream()` is the new Cython bridge function.

2. **v_char32 removal from TVMFFIAny** (c100338): The `char32_t v_char32[2]` member was removed from the `TVMFFIAny` union (ABI-breaking, but no in-tree consumer existed). `DLPackTensorAllocator` typedef was moved inside `extern "C"` for C compatibility. `tvm-ffi-config --cflags` added for C-only compilation (no `-std=c++17`).

3. **Optional CUDA in torch DLPack extension** (c665fa3): `BUILD_WITH_CUDA` preprocessor guard added to the JIT-compiled torch DLPack C++ extension, so it compiles on CPU-only torch installations.

4. **Windows MSVC dev env for inline compilation** (4383b1a): `_run_command_in_dev_prompt()` discovers Visual Studio via `vswhere.exe`, sources `VsDevCmd.bat -arch=x64`, and runs Ninja in that environment. Fixes inline compilation on Windows without requiring a Developer Command Prompt.

### Minor Code Changes (3 commits)

- **Reflection __name__ fix** (af82dbb): De-indented `method_pyfunc.__name__` assignment in `_add_class_attrs_by_reflection` so it always executes (was incorrectly nested under a docstring check).
- **bytearray helper refactor** (cc93373): New `bytearray_to_bytes()` Cython helper; replaced all raw `PyBytes_FromStringAndSize` patterns with `bytearray_to_str()`/`bytearray_to_bytes()`.
- **CMake install trailing slash fix** (9432896): Fixed `install(DIRECTORY ...)` rules for 3rdparty directories.

## Design Doc Updates

| Design Doc | Changes |
|-----------|---------|
| `0014-python-bindings.md` | Added StreamContext section (StreamContext, TorchStreamContext, factory functions, Cython bridge). Added type annotation convention (ANN + PTH enforcement). Updated evidence matrix. |
| `0017-inline-module-compilation.md` | Added `container/tensor.h` to auto-prepended headers. Updated problem statement for `tvm::ffi::Tensor` preference. Added Windows MSVC dev env subsection (`_run_command_in_dev_prompt`). Updated all code examples from `DLTensor*` to `tvm::ffi::Tensor`. Updated evidence matrix. |
| `0015-python-packaging.md` | Added `--cflags` to CLI tool docs. Added version bump evidence. Updated evidence matrix. |
| `c-abi.md` | Noted `v_char32` removal in TVMFFIAny union layout. Updated evidence matrix. |
| `0018-dlpack-fast-path.md` | Added conditional CUDA compilation evidence (c665fa3). |

## API Index Updates

| API Index | Changes |
|----------|---------|
| `0010-python-bindings.md` | Added StreamContext, TorchStreamContext, use_raw_stream, use_torch_stream. Added `--cflags` note. Updated last_updated_commit. Added 5 evidence rows. |
| `0013-inline-module.md` | Updated last_updated_commit. Added 2 evidence rows (tensor.h auto-include, Windows MSVC fix). |
| `0009-env-api.md` | Added Python API section with `_env_set_current_stream`, StreamContext, TorchStreamContext, factory functions. Updated last_updated_commit. Added evidence row. |

## Key Takeaways

- The repository is now fully independent with CI/CD, lint enforcement, documentation, branch protection, and squash-only merge policy.
- `pre-commit run --all-files` is the canonical lint entry point (replaces `task_lint.sh`).
- `tvm::ffi::Tensor` is now the preferred parameter type for inline module functions (over raw `DLTensor*`).
- The Python stream context protocol (`use_raw_stream`/`use_torch_stream`) provides a clean save/restore pattern for the FFI thread-local stream.
- All public Python APIs now have type annotations enforced by ruff `ANN` rules.
