---
scope: "cuda-extra-headers"
status: "active"
last_updated_commit: "cdfd04109f74a2115c909302f4adf90536bce865"
related_designs:
  - ".knowledge/designs/0021-cuda-extra-headers.md"
  - ".knowledge/designs/0017-inline-module-compilation.md"
related_adrs: []
---
# API Index: CUDA Extra Headers

**Scope**: Header-only CUDA utilities for kernel loading, launching, device management, and cubin embedding, plus Python/CMake tooling for the cubin workflow.
**Design docs**: `.knowledge/designs/0021-cuda-extra-headers.md`, `.knowledge/designs/0017-inline-module-compilation.md`
**ADRs**: (none)

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| (none) | -- | Header-only utilities; no C ABI functions added to libtvm_ffi |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `tvm::ffi::dim3` | struct | `unsigned x, y, z`; ctors: `dim3()`, `dim3(x)`, `dim3(x,y)`, `dim3(x,y,z)` | 3D launch dimension (mirrors CUDA `dim3`) |
| `tvm::ffi::CubinModule` | class | `CubinModule(const Bytes&)`, `CubinModule(const char*)`, `GetKernel(const char*)`, `GetKernelWithMaxDynamicSharedMemory(const char*, int64_t=-1)`, `operator[](const char*)`, `GetHandle()` | RAII wrapper around `cudaLibrary_t`; loads cubin from memory. Movable, not copyable. |
| `tvm::ffi::CubinKernel` | class | `Launch(void** args, dim3 grid, dim3 block, cudaStream_t stream, uint32_t dyn_smem_bytes=0) -> cudaError_t`, `GetHandle()` | Wrapper around `cudaKernel_t`; launches kernel via `cudaLaunchKernel`. Movable, not copyable. |
| `tvm::ffi::CUDADeviceGuard` | struct | `CUDADeviceGuard(int device_index)` | RAII guard: `cudaSetDevice(target)` on construction, restores original on destruction. Skips if same device. |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `TVM_FFI_CHECK_CUDA_ERROR(stmt)` | Evaluates `stmt`; if `!= cudaSuccess`, throws `RuntimeError` with error name and string | CUDA runtime error checking (in `base.h`) |
| `TVM_FFI_EMBED_CUBIN(name)` | Declares `extern "C" __tvm_ffi__cubin_<name>` / `_end` symbols; creates singleton `EmbedCubinModule_<name>` with `CubinModule` member | Declare embedded cubin for static init |
| `TVM_FFI_EMBED_CUBIN_GET_KERNEL(name, kernel_name)` | `EmbedCubinModule_<name>::Global()->mod[kernel_name]` | Get `CubinKernel` from embedded cubin singleton |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `tvm_ffi.cpp.nvrtc.nvrtc_compile` | `(source: str, *, name: str="kernel.cu", arch: str\|None=None, extra_opts: Sequence[str]\|None=None) -> bytes` | Compile CUDA source to cubin via NVRTC; auto-detects GPU arch. Requires `cuda-python`. |
| `tvm_ffi.utils.embed_cubin.embed_cubin` | `(cubin_path: Path, input_obj_path: Path, output_obj_path: Path, name: str, verbose: bool=False) -> None` | Embed cubin into object file via `ld`/`objcopy`. Linux-only. |
| `tvm_ffi.cpp.load_inline` (updated) | `embed_cubin: Mapping[str, bytes]\|None` param | New parameter: embeds cubin bytes into the compiled module |

## CMake API
| Name | Parameters | Description |
|------|------------|-------------|
| `tvm_ffi_generate_cubin` | `OUTPUT, SOURCE, [ARCH=native], [OPTIONS], [DEPENDS]` | Compile CUDA source to cubin with nvcc |
| `tvm_ffi_embed_cubin` | `OUTPUT, SOURCE, CUBIN, NAME, [DEPENDS]` | Compile C++ source + embed cubin data into combined object file |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| (none) | -- | CUDA headers are C++-only |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| (none) | -- | -- | New API; no deprecations |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| d49effdb | `2025-11-25-d49effdb22392363050e1f2d85cd4b31bf242cf0.md` | CubinModule, CubinKernel, dim3, NVRTC, embed_cubin, CMake utilities, embed_cubin param in load_inline |
| cdfd0410 | `2025-11-25-cdfd04109f74a2115c909302f4adf90536bce865.md` | CUDADeviceGuard, base.h extraction, TVM_FFI_CHECK_CUDA_ERROR |
| 803cdc84 | `2025-11-26-803cdc84a4bb4502c8da0e5f69a61c1e7b1a38cf.md` | DeviceGuard documentation in kernel library guide |
