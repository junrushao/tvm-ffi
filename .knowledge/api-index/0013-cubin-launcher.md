---
scope: "cubin-launcher"
---
# API Index: CUBIN Launcher and CUDA Utilities

**Scope**: C++ header-only classes and macros for CUDA CUBIN loading/launching via unified Driver/Runtime API abstraction, CUDA device guard, Python embedding/compilation toolchain, and CMake utilities.
**Design docs**: [0021-cubin-launcher.md](../designs/0021-cubin-launcher.md)
**ADRs**: [0023-cubin-symbol-naming.md](../ADRs/0023-cubin-symbol-naming.md), [0025-unified-cuda-api-abstraction.md](../ADRs/0025-unified-cuda-api-abstraction.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `cuda_api` namespace (b16f11f) | namespace | `StreamHandle`, `DeviceHandle`, `LibraryHandle`, `KernelHandle`, `ResultType`, `LaunchConfig`, `LaunchAttrType`, `kSuccess`; `LoadLibrary(...)`, `UnloadLibrary(...)`, `GetKernel(...)`, `LaunchKernel(...)`, `LaunchKernelEx(KernelHandle, void**, const LaunchConfig&)` (adac5eb), `ConstructLaunchConfig(KernelHandle, StreamHandle, uint32_t, dim3, dim3, int cluster_dim, LaunchConfig&, LaunchAttrType&)` (adac5eb), `GetDeviceCount(int*)`, `GetDeviceAttribute(...)` | Compile-time switchable Driver/Runtime API abstraction. `LaunchKernelEx`/`ConstructLaunchConfig` enable SM90+ cluster launch attributes. |
| `TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API` | macro (b16f11f) | `0` (Runtime API, CUDA >= 12.8) or `1` (Driver API, CUDA < 12.8) | Auto-detected compile flag. User-overridable. `static_assert` if Runtime API requested on CUDA < 12.8. |
| `CubinModule` | class | `CubinModule(const Bytes&)`, `CubinModule(const char*)`, `CubinModule(const unsigned char*)` (b16f11f), `GetKernel(const char*) -> CubinKernel`, `GetKernelWithMaxDynamicSharedMemory(const char*, int64_t) -> CubinKernel`, `operator[](const char*) -> CubinKernel`, `GetHandle() -> cuda_api::LibraryHandle` | RAII wrapper over `cuda_api::LibraryHandle`. Loads CUBIN via `cuda_api::LoadLibrary`. Non-copyable, movable. |
| `CubinKernel` | class | `CubinKernel(cuda_api::LibraryHandle, const char*)`, `Launch(void**, dim3, dim3, cuda_api::StreamHandle, uint32_t) -> cuda_api::ResultType`, `LaunchEx(void**, const cuda_api::LaunchConfig&) -> cuda_api::ResultType` (adac5eb), `GetHandle() -> cuda_api::KernelHandle` | RAII wrapper over `cuda_api::KernelHandle`. `Launch` uses `cuda_api::LaunchKernel`; `LaunchEx` uses `cuda_api::LaunchKernelEx` for extended launch (SM90+ cluster dims). Non-copyable, movable. |
| `dim3` | struct | `unsigned int x, y, z` (default 1,1,1) | Custom dim3 in `tvm::ffi` namespace. Relocated from `cubin_launcher.h` to `base.h` (b16f11f). |
| `CUDADeviceGuard` | struct | `CUDADeviceGuard(int device_index)`, `~CUDADeviceGuard() noexcept(false)` | RAII device guard. Default constructor deleted. |
| `TVM_FFI_EMBED_CUBIN(name)` | macro | Declares `extern "C" __tvm_ffi__cubin_<name>[]` + anonymous-namespace singleton `EmbedCubinModule_<name>` | Compile-time CUBIN embedding from linker symbols. |
| `TVM_FFI_EMBED_CUBIN_FROM_BYTES(name, imageBytes)` | macro (b16f11f) | Creates singleton `EmbedCubinModule_<name>` wrapping `CubinModule{imageBytes}` | Compile-time CUBIN embedding from byte arrays (C++23 `#embed` / `bin2c`). |
| `TVM_FFI_EMBED_CUBIN_GET_KERNEL(name, kernel_name)` | macro | Expands to `EmbedCubinModule_<name>::Global()->mod[kernel_name]` | Retrieves `CubinKernel` from embedded CUBIN singleton. |
| `TVM_FFI_CHECK_CUBIN_LAUNCHER_CUDA_ERROR(stmt)` | macro (10cb004) | Evaluates `stmt` as `cuda_api::ResultType`; throws `RuntimeError` on failure | Renamed from `TVM_FFI_CHECK_CUDA_ERROR` in `unified_api.h` (10cb004). Works with unified Driver/Runtime API types. Isolated to cubin launcher usage. |
| `TVM_FFI_CHECK_CUDA_ERROR(stmt)` | macro (10cb004) | Evaluates `stmt` as `cudaError_t`; throws `RuntimeError` via `cudaGetErrorName`/`cudaGetErrorString` | New in `base.h` (10cb004). Purely CUDA Runtime API-based. For general CUDA error checking outside cubin launcher. |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `nvrtc_compile` | `(source: str, *, name: str = "kernel.cu", arch: str \| None = None, extra_opts: Sequence[str] \| None = None) -> bytes` | Compile CUDA source to CUBIN via NVRTC. Auto-detects GPU arch if not specified. Requires `cuda.bindings`. (`tvm_ffi.cpp.nvrtc`) |
| `embed_cubin` | `(cubin_path: Path, input_obj_path: Path, output_obj_path: Path, name: str, verbose: bool = False) -> None` | Embed CUBIN into object file via `ld -r -b binary` + `objcopy`. Linux/Unix only. (`tvm_ffi.utils.embed_cubin`) |
| `build_inline` | `(..., embed_cubin: Mapping[str, bytes] \| None = None) -> str` | Extended with `embed_cubin` param. Writes CUBIN files to build dir; ninja embeds them via chained `embed_cubin` rules. (`tvm_ffi.cpp.extension`) |
| `load_inline` | `(..., embed_cubin: Mapping[str, bytes] \| None = None) -> Module` | Extended with `embed_cubin` param. Pass-through to `build_inline`, then loads resulting `.so` as `Module`. Now supports HIP via auto-detection (65b5e90). (`tvm_ffi.cpp.extension`) |
| `_detect_gpu_backend` (65b5e90) | `() -> Literal["cuda", "hip"]` | Auto-detect GPU backend (CUDA or HIP/ROCm). Checks `TVM_FFI_GPU_BACKEND` env var first, then probes for ROCm. Cached. (`tvm_ffi.cpp.extension`) |
| `_find_rocm_home` (65b5e90) | `() -> str` | Find ROCm install path via `ROCM_HOME`/`ROCM_PATH`, `hipcc` in PATH, or `/opt/rocm`. (`tvm_ffi.cpp.extension`) |
| `_get_rocm_target` (65b5e90) | `() -> list[str]` | Get `--offload-arch=gfxXXXX` flags via `rocm_agent_enumerator`. (`tvm_ffi.cpp.extension`) |

## CMake API
| Name | Signature | Description |
|------|-----------|-------------|
| `add_tvm_ffi_cubin` (b16f11f) | `(OUTPUT, SOURCE, ...)` | Compile CUDA source to CUBIN. Replaces deprecated `tvm_ffi_generate_cubin`. |
| `add_tvm_ffi_fatbin` (b16f11f) | `(OUTPUT, SOURCE, ...)` | Compile CUDA source to FATBIN. |
| `tvm_ffi_embed_bin_into` (b16f11f) | `(TARGET, BIN, NAME, ...)` | Embed binary into target via `PRE_LINK`. Replaces deprecated `tvm_ffi_embed_cubin`. |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | -- | CUBIN launcher is a C++ header-only utility; no Rust bindings. |
