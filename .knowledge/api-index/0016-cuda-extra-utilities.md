---
scope: "cuda-extra-utilities"
---
# API Index: CUDA Extra Utilities

**Scope**: Header-only CUDA utilities under `include/tvm/ffi/extra/cuda/` (CUBIN launcher, device guard, unified API layer, dtype traits) and related Python utilities.
**Design docs**: [0018-cuda-extra-utilities.md](../designs/0018-cuda-extra-utilities.md)
**ADRs**: [0016-cubin-embedding-via-symbol-injection.md](../ADRs/0016-cubin-embedding-via-symbol-injection.md), [0010-ffi-symbol-prefix-convention.md](../ADRs/0010-ffi-symbol-prefix-convention.md), [0017-cuda-driver-runtime-api-abstraction.md](../ADRs/0017-cuda-driver-runtime-api-abstraction.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `cuda_api::StreamHandle` | using | `CUstream` or `cudaStream_t` | Compile-time-resolved CUDA stream type (b16f11f6) |
| `cuda_api::LibraryHandle` | using | `CUlibrary` or `cudaLibrary_t` | Compile-time-resolved CUDA library type (b16f11f6) |
| `cuda_api::KernelHandle` | using | `CUkernel` or `cudaKernel_t` | Compile-time-resolved CUDA kernel type (b16f11f6) |
| `cuda_api::ResultType` | using | `CUresult` or `cudaError_t` | Compile-time-resolved CUDA error type (b16f11f6) |
| `cuda_api::LoadLibrary` | function | `(LibraryHandle*, void*) -> ResultType` | Load CUBIN library from memory (b16f11f6) |
| `cuda_api::LaunchKernel` | function | `(KernelHandle, void**, dim3, dim3, StreamHandle, int) -> ResultType` | Launch kernel (b16f11f6) |
| `CubinModule` | class | `CubinModule(Bytes)`, `CubinModule(const char*)`, `CubinModule(const unsigned char*)`, `GetKernel(name) -> CubinKernel`, `GetKernelWithMaxDynamicSharedMemory(name, smem_max) -> CubinKernel`, `operator[](name) -> CubinKernel` | RAII wrapper around `cuda_api::LibraryHandle` (d49effd, updated b16f11f6) |
| `CubinKernel` | class | `Launch(args, grid, block, stream, dyn_smem_bytes) -> cuda_api::ResultType`, `SetMaxDynamicSharedMemory(max)` (private) | Handle for a loaded CUDA kernel function (d49effd, updated b16f11f6) |
| `dim3` | struct | `x: uint`, `y: uint`, `z: uint` (all default 1) | 3D dimension type, moved to base.h (d49effd, moved b16f11f6) |
| `CUDADeviceGuard` | class | `CUDADeviceGuard(device_index: int)`, `original_device_index_` saved/restored | RAII CUDA device switcher (cdfd041) |
| `TVM_FFI_CHECK_CUDA_ERROR(stmt)` | macro | checks `cudaError_t` (runtime API only), throws `RuntimeError` | Runtime-API-only CUDA error check in base.h (10cb004, split from unified_api.h) |
| `TVM_FFI_CHECK_CUBIN_LAUNCHER_CUDA_ERROR(stmt)` | macro | checks `cuda_api::ResultType`, throws `RuntimeError` | Unified-API CUDA error check for cubin launcher only, in unified_api.h (10cb004, renamed from TVM_FFI_CHECK_CUDA_ERROR) |
| `TVM_FFI_EMBED_CUBIN(name)` | macro | declares `extern "C" __tvm_ffi__cubin_<name>[]`, creates singleton | Compile-time CUBIN embedding via symbol injection (d49effd) |
| `TVM_FFI_EMBED_CUBIN_FROM_BYTES(name, imageBytes)` | macro | creates singleton from byte array | Byte-array CUBIN loading for C++23 `#embed` / bin2c (b16f11f6) |
| `TVM_FFI_EMBED_CUBIN_GET_KERNEL(name, kernel_name)` | macro | `EmbedCubinModule_<name>::Global()->mod[kernel_name]` | Retrieve kernel from embedded CUBIN module (d49effd) |
| `dtype_trait<T>` | template struct | `static constexpr DLDataType value` | Compile-time C++ type to DLDataType mapping (c51e519b) |

## CMake API
| Name | Signature | Description |
|------|-----------|-------------|
| `add_tvm_ffi_cubin` | `add_tvm_ffi_cubin(target CUDA source)` | Compile CUDA source to CUBIN object library (b16f11f6) |
| `add_tvm_ffi_fatbin` | `add_tvm_ffi_fatbin(target CUDA source)` | Compile CUDA source to FATBIN object library (b16f11f6) |
| `tvm_ffi_embed_bin_into` | `tvm_ffi_embed_bin_into(target SYMBOL name BIN binfile)` | Embed binary into target via PRE_LINK (b16f11f6) |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `tvm_ffi.cpp.nvrtc.nvrtc_compile` | `def nvrtc_compile(source: str, *, name="kernel.cu", arch=None, extra_opts=None) -> bytes` | Compile CUDA source to CUBIN via NVRTC (d49effd) |
| `tvm_ffi.utils.embed_cubin` | `def embed_cubin(cubin_path, input_obj_path, output_obj_path, name, verbose=False) -> None` | Embed CUBIN into .o file via ld + objcopy pipeline (d49effd, Unix-only) |
| `tvm_ffi.cpp.to_cpp_dtype` | `def to_cpp_dtype(dtype_str: str | Any) -> str` | Convert dtype string/torch.dtype to C++ type name with backend auto-detection (c51e519b) |

## Rust API
N/A -- CUDA utilities are C++/Python only.
