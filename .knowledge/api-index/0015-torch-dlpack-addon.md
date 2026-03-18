---
scope: "torch-dlpack-addon"
---
# API Index: Torch DLPack Addon

**Scope**: The torch_c_dlpack_ext addon package and its JIT/AOT build infrastructure for PyTorch DLPack exchange.
**Design docs**: [0017-torch-dlpack-addon.md](../designs/0017-torch-dlpack-addon.md)
**ADRs**: [0015-dlpack-exchange-api-struct.md](../ADRs/0015-dlpack-exchange-api-struct.md)

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `load_torch_c_dlpack_extension` | `def load_torch_c_dlpack_extension() -> Any` | Load prebuilt or JIT-compile torch DLPack extension; sets `torch.Tensor.__dlpack_c_exchange_api__` as PyCapsule (renamed from `__c_dlpack_exchange_api__` in 5393647) |
| `_check_and_update_dlpack_c_exchange_api` | `def _check_and_update_dlpack_c_exchange_api(tensor_cls: type) -> bool` | Backward compat shim: detects old `__c_dlpack_exchange_api__` and migrates to `__dlpack_c_exchange_api__` (5393647) |
| `_create_dlpack_exchange_api_capsule` | `def _create_dlpack_exchange_api_capsule(ptr_as_int: int) -> PyCapsule` | Wrap DLPackExchangeAPI pointer in PyCapsule with name `"dlpack_exchange_api"` (7f3bb77) |
| `parse_env_flags` | `def parse_env_flags(env_var_name: str) -> list[str]` | Parse shell-style flags from environment variable via shlex.split |
| `_build_optional_torch_c_dlpack.main` | `def main() -> None` | CLI entry point for building the torch DLPack addon shared library |
| `_run_build_on_linux_like` | `def _run_build_on_linux_like(build_dir, libname, source_path, extra_cflags, extra_ldflags, extra_include_paths) -> None` | Direct compiler invocation for non-Windows JIT build (7a355c7) |
| `_generate_ninja_build_windows` | `def _generate_ninja_build_windows(build_dir, libname, source_path, extra_cflags, extra_ldflags, extra_include_paths) -> None` | Ninja-based build for Windows only (7a355c7, renamed from `_generate_ninja_build`) |

## Environment Variables
| Name | Description |
|------|-------------|
| `TVM_FFI_DISABLE_TORCH_C_DLPACK` | Set to "1" to skip auto-loading of torch C DLPack extension at import time |
| `TVM_FFI_CACHE_DIR` | Override default cache location (`~/.cache/tvm-ffi`) for JIT-built libraries |
| `TVM_FFI_JIT_EXTRA_CFLAGS` | Extra compiler flags for JIT build (e.g., `--sysroot`, `--target` for cross-compilation) |
| `TVM_FFI_JIT_EXTRA_LDFLAGS` | Extra linker flags for JIT build |
| `TVM_FFI_SKIP_DLPACK_C_EXCHANGE_API` | Skip DLPack exchange API detection in arg setter factory (renamed from `TVM_FFI_SKIP_C_DLPACK_EXCHANGE_API` in 5393647) |

## C++ Exports
| Name | Signature | Description |
|------|-----------|-------------|
| `TorchDLPackExchangeAPIPtr` | `extern "C" int64_t TorchDLPackExchangeAPIPtr()` | Returns pointer to `DLPackExchangeAPI` singleton for PyTorch |

## CLI Flags (_build_optional_torch_c_dlpack.py)
| Flag | Description |
|------|-------------|
| `--output-dir` | Where final .so/.dll is placed (default: `~/.cache/tvm-ffi`) |
| `--build-dir` | Temporary build directory (default: tempfile.mkdtemp) |
| `--build-with-cuda` | Enable CUDA support (mutually exclusive with `--build-with-rocm`) |
| `--build-with-rocm` | Enable ROCm support (mutually exclusive with `--build-with-cuda`) |
| `--libname` | Library name (or "auto" for version-specific) |
