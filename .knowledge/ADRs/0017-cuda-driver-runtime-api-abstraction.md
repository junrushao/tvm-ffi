---
scope:
  - "0018-cuda-extra-utilities.md"
---
# Compile-Time CUDA Driver/Runtime API Abstraction

**TL;DR**: The CUBIN launcher layer now supports both CUDA Driver API and Runtime API via a compile-time abstraction (`tvm::ffi::cuda_api`), defaulting to Runtime API on CUDA >= 12.8 and Driver API on older versions.

## Context
- CUDA 12.0-12.7 provide library loading (`cudaLibraryLoadData`, `cudaLibraryGetKernel`) only via the CUDA Runtime API, with limited feature parity. Some operations require Driver API fallbacks.
- CUDA 12.8+ introduces full Runtime API equivalents for all library/kernel operations, making the Runtime API the simpler choice (no need for `cuInit`, `cuDeviceGet`, etc.).
- Some downstream users prefer the Driver API for explicit device/context control, or run on older CUDA versions where Runtime API library functions are incomplete.

Usecases:
- Kernel library authors who target CUDA >= 12.8 prefer Runtime API for simplicity (no Driver API initialization).
- Kernel library authors who target older CUDA versions need Driver API for `cuLibraryLoadData` and `cuKernel` management.
- Users who want to override the default selection based on their deployment environment.

Design Decisions:
- Introduce `tvm::ffi::cuda_api` namespace with type aliases and wrapper functions that resolve at compile time to either Driver or Runtime API types.
- Default selection: `TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API = 0` (Runtime) when `CUDART_VERSION >= 12080`, else `1` (Driver).
- User can override via `-DTVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API=0|1`. A `static_assert` prevents requesting Runtime API on CUDA < 12.8.
- All `CubinModule` and `CubinKernel` internals use `cuda_api::` aliases (e.g., `cuda_api::LibraryHandle` instead of `cudaLibrary_t`), making the abstraction transparent to users who interact only through the CUBIN launcher macros.

## Implementation Notes
- Type aliases: `StreamHandle`, `DeviceHandle`, `LibraryHandle`, `KernelHandle`, `ResultType`, `kSuccess` each resolve to the corresponding Driver or Runtime type.
- Wrapper functions: `LoadLibrary`, `UnloadLibrary`, `GetKernel`, `LaunchKernel`, `GetDeviceHandle`, `GetDeviceCount`, `GetDeviceAttribute`, `GetKernelSharedMem`, `SetKernelMaxDynamicSharedMem`, `GetErrorString`.
- `TVM_FFI_CHECK_CUDA_ERROR` macro updated to use `cuda_api::ResultType` and `cuda_api::GetErrorString`.
- `dim3` struct moved to `base.h` (from `cubin_launcher.h`) to be usable without pulling in full CUDA headers.

## Related Design Docs
- [0018-cuda-extra-utilities.md](../designs/0018-cuda-extra-utilities.md)
