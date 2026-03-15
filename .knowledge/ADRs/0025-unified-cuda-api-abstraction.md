---
scope:
  - "0021-cubin-launcher"
---
# Unified CUDA Driver/Runtime API Abstraction

**TL;DR**: The cubin launcher abstracts over CUDA Driver and Runtime APIs via a compile-time switchable `cuda_api` namespace, auto-selecting Runtime API for CUDA >= 12.8 and Driver API for older versions, avoiding hard dependency on either API while maintaining a single code path for `CubinModule`/`CubinKernel`.

## Context
The CUDA ecosystem provides two APIs for loading and launching kernels:
- **Driver API** (`cuLibraryLoadData`, `cuLibraryGetKernel`, `cuLaunchKernel`): Always available, requires explicit context management. Used in CUDA < 12.8 where the Runtime API lacked library-based kernel loading.
- **Runtime API** (`cudaLibraryLoadData`, `cudaLibraryGetKernel`, `cudaLaunchKernelExC`): Higher-level, manages contexts transparently via primary context, compatible with PyTorch's CUDA context model. Library-based loading APIs (`cudaLibrary*`) added in CUDA 12.0, but fully stable from CUDA 12.8.

Before this decision, `CubinModule`/`CubinKernel` called Runtime API functions directly (e.g., `cudaLibraryLoadData`), requiring CUDA >= 12.0 and making it impossible to use the Driver API when the Runtime API was unavailable or unstable.

Usecases:
- Supporting CUDA toolkit versions older than 12.8 where library-based Runtime APIs are unstable
- Future-proofing against Runtime API additions without source changes
- Keeping `CubinModule`/`CubinKernel` code clean with a single set of function calls

Design Decisions:
- Introduce a `tvm::ffi::cuda_api` namespace (`internal/unified_api.h`) with type aliases (`StreamHandle`, `LibraryHandle`, etc.) and wrapper functions that resolve to Driver or Runtime API calls based on `TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API`.
- Auto-select: Runtime API (`=0`) when `CUDART_VERSION >= 12080`; Driver API (`=1`) otherwise.
- Allow user override via `#define TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API` before inclusion. `static_assert` if Runtime API requested on CUDA < 12.8.
- Replace all direct `cuda*`/`cu*` calls in `CubinModule`/`CubinKernel` with `cuda_api::` wrappers.
- Relocate `TVM_FFI_CHECK_CUDA_ERROR` from `base.h` to `unified_api.h` (it now works with both `CUresult` and `cudaError_t`).
- Relocate `dim3` from `cubin_launcher.h` to `base.h` (it has no CUDA API dependency).

## Implementation Notes
- The compile-time switch is purely preprocessor-based -- no runtime branching. All `cuda_api::*` calls are resolved at compilation to either `cu*` or `cuda*` function calls, so there is zero overhead.
- The abstraction is scoped to the cubin launcher only (`TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API`) to avoid naming confusion if other CUDA API abstractions are added later.
- `cuda_api::GetDeviceHandle` has different semantics per API: Driver API returns a `CUdevice` from `cuDeviceGet()`; Runtime API returns the device `int` directly. This asymmetry is hidden by the wrapper.

```mermaid
flowchart TD
    FLAG["TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API"]
    FLAG -->|0 (CUDA >= 12.8)| RT["cuda_api -> cudaLibrary*, cudaLaunchKernelExC"]
    FLAG -->|1 (CUDA < 12.8)| DR["cuda_api -> cuLibrary*, cuLaunchKernel"]
    RT --> CM["CubinModule / CubinKernel"]
    DR --> CM
```

## Related Design Docs
- [0021-cubin-launcher.md](../designs/0021-cubin-launcher.md) -- the primary design doc for the cubin launcher system
