# CUDA/ROCm Integration

> Range: `8b46833..ecc7471` (2025-12-12 to 2026-02-21, 100 commits)

## Overview

GPU support matured significantly: the CUBIN launcher was refactored with a
unified CUDA Driver/Runtime API abstraction, ROCm gained DLPack stream
integration, and AMD HIP support was added to the C++ extension build system.

## Timeline

| Date | SHA | Change |
|------|-----|--------|
| 2025-12-25 | `b16f11f` | Refactor cubin launcher: unified CUDA API (#300) |
| 2026-01-12 | `10cb004` | Isolate unified API to cubin launcher only (#408) |
| 2026-01-12 | `f9b5e7d` | Update torch-c-dlpack-ext to 0.1.5 (#398) |
| 2026-01-13 | `692a41a` | Fix missing unified_api.h include (#405) |
| 2026-01-25 | `e6e5d3a` | Bump DLPack to latest version (#420) |
| 2026-02-14 | `395db3c` | Add Ampere GPU name-based fallback for CUDA CC (#440) |
| 2026-02-19 | `65b5e90` | Support AMD HIP for cpp extension (#460) |
| 2026-02-20 | `37d0485` | ROCm: fix DLPack stream + force addon override (#466) |

## Key Changes

### 1. Cubin Launcher Refactor (`b16f11f`)

Major restructuring of CUBIN embedding and launching:

**Unified CUDA API** (`include/tvm/ffi/extra/cuda/internal/unified_api.h`):
- Abstractions: `LibraryHandle`, `KernelHandle`, `StreamHandle`, `ResultHandle`
- Selectable backend via `TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API` define
- Unified error checking: `TVM_FFI_CHECK_CUDA_ERROR` macro

**New CMake Functions** (replacing old `tvm_ffi_generate_cubin`/`tvm_ffi_embed_cubin`):
- `add_tvm_ffi_cubin(target, source)` — compile CUDA source to cubin
- `add_tvm_ffi_fatbin(target, source)` — compile to fatbin
- `tvm_ffi_embed_bin_into(target, binary)` — embed binary into C++ library

The refactor supports multiple embedding approaches: C++23 `#embed`,
`bin2c` headers, and CMake object linking. `CubinModule` accepts
`const unsigned char*` byte arrays directly.

### 2. ROCm DLPack Stream Fix (`37d0485`)

Fixed `current_work_stream` on ROCm to use `HIPStreamMasqueradingAsCUDA`
instead of raw HIP streams. Forces tvm-ffi addon override on ROCm platforms
to ensure correct Torch <-> TVM stream exchange.

### 3. AMD HIP C++ Extension Support (`65b5e90`)

The `tvm_ffi.cpp` extension build system now auto-detects AMD HIP/ROCm and
supports building CUDA-like kernels for AMD GPUs. New `backend` parameter
on `build()`, `load()`, `build_inline()`, `load_inline()` APIs.

### 4. DLPack Bump (`e6e5d3a`)

Updated the vendored DLPack submodule (`3rdparty/dlpack`) to the latest
version for improved interoperability.

## Architecture: Cubin Launcher

```
Embedding Approaches
├── CMake Object Linking (default)
│   └── tvm_ffi_embed_bin_into() → links .cubin as object
├── C++23 #embed
│   └── CubinModule(const unsigned char* bytes)
└── bin2c Header
    └── CubinModule(const unsigned char* bytes)

CUDA API Abstraction
├── Driver API (cuModuleLoadData, cuModuleGetFunction, cuLaunchKernel)
└── Runtime API (cudaLibraryLoadData, cudaLibraryGetKernel, cudaLaunchKernel)
    └── Selected at compile time via TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API
```

## Migration Notes

- Old CMake functions `tvm_ffi_generate_cubin`/`tvm_ffi_embed_cubin` were
  removed (`b16f11f`). Use `add_tvm_ffi_cubin` + `tvm_ffi_embed_bin_into`.
- `CubinModule` constructor now accepts `const unsigned char*` instead of
  `const char*` (`b16f11f`).
- ROCm users: torch-c-dlpack-ext addon is now force-overridden on ROCm
  platforms (`37d0485`).
