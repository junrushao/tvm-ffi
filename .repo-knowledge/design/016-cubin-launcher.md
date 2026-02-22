# 016 -- CUBIN Launcher Subsystem

- Doc ID: 016-cubin-launcher
- Status: Approved
- Last Updated: 2026-02-22
- Owners: Tianqi Chen

## Overview

The CUBIN launcher is a header-only C++ subsystem in TVM FFI for loading
pre-compiled CUDA binary (CUBIN/FATBIN) modules from memory and launching
kernels with RAII resource management and multi-GPU awareness. It lives
entirely within `include/tvm/ffi/extra/cuda/` and is gated behind CUDA
availability, not part of the core FFI ABI. Three header files form the core:
`cubin_launcher.h` (public API with `CubinModule`, `CubinKernel`, and macros),
`internal/unified_api.h` (compile-time abstraction over Runtime vs Driver API),
and `base.h` (`dim3` struct and error-checking macro). Complementary tooling in
CMake (`cmake/Utils/EmbedCubin.cmake`) and Python
(`python/tvm_ffi/utils/embed_cubin.py`, `python/tvm_ffi/cpp/nvrtc.py`) supports
the full workflow from CUDA source to embedded kernel launch.

```text
include/tvm/ffi/extra/cuda/
  base.h                 -- dim3, TVM_FFI_CHECK_CUDA_ERROR
  cubin_launcher.h       -- CubinModule, CubinKernel, TVM_FFI_EMBED_CUBIN macros
  internal/
    unified_api.h        -- cuda_api namespace (Runtime/Driver API abstraction)
```

## Key Design

### CubinModule and CubinKernel RAII classes

`CubinModule` (`d49effd`, `b16f11f`) is the RAII owner of a
`cuda_api::LibraryHandle` (which resolves to `cudaLibrary_t` or `CUlibrary`
depending on the API mode). Three constructors accept `Bytes`, `const char*`,
or `const unsigned char*`, all calling `cuda_api::LoadLibrary()`. The
destructor calls `cuda_api::UnloadLibrary()`. Copy is deleted; move transfers
the handle and nulls the source.

```cpp
class CubinModule {
 public:
  explicit CubinModule(const Bytes& bytes);
  explicit CubinModule(const char* code);
  explicit CubinModule(const unsigned char* code);
  ~CubinModule();
  CubinKernel GetKernel(const char* name);
  CubinKernel GetKernelWithMaxDynamicSharedMemory(const char* name,
                                                   int64_t dynamic_smem_max = -1);
  CubinKernel operator[](const char* name);
  CubinModule(CubinModule&& other) noexcept;
  CubinModule& operator=(CubinModule&& other) noexcept;
  // Non-copyable
 private:
  cuda_api::LibraryHandle library_ = nullptr;
};
```

`CubinKernel` is the RAII owner of a `cuda_api::KernelHandle` (`cudaKernel_t` /
`CUkernel`). The constructor takes a `LibraryHandle` and kernel name, calling
`cuda_api::GetKernel()`. The destructor is defaulted because kernel handles are
implicitly tied to the library lifetime. `CubinKernel` is nonetheless move-only
to prevent aliasing confusion.

```cpp
class CubinKernel {
 public:
  CubinKernel(cuda_api::LibraryHandle library, const char* name);
  ~CubinKernel() = default;
  cuda_api::ResultType Launch(void** args, dim3 grid, dim3 block,
                              cuda_api::StreamHandle stream,
                              uint32_t dyn_smem_bytes = 0);
  CubinKernel(CubinKernel&& other) noexcept;
  CubinKernel& operator=(CubinKernel&& other) noexcept;
  // Non-copyable
 private:
  void SetMaxDynamicSharedMemory(int64_t dynamic_smem_max = -1);
  cuda_api::KernelHandle kernel_ = nullptr;
  friend class CubinModule;
};
```

`SetMaxDynamicSharedMemory` is private, accessible only through
`CubinModule::GetKernelWithMaxDynamicSharedMemory`. It iterates over all
devices, queries `CU_DEVICE_ATTRIBUTE_MAX_SHARED_MEMORY_PER_BLOCK` (attribute
8), computes `device_max - kernel_static_shared_mem`, and sets the maximum
dynamic shared memory per device. It only throws an error if ALL devices fail.

### Unified CUDA API abstraction

The `tvm::ffi::cuda_api` namespace in `internal/unified_api.h` (`b16f11f`,
`10cb004`) provides a compile-time abstraction layer over the CUDA Runtime API
and Driver API, controlled by the `TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API`
macro:

```cpp
#ifndef TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API
#if CUDART_VERSION >= 12080
#define TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API 0
#else
#define TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API 1
#endif
#endif
```

The decision tree is:

- If `TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API` is **not defined**: auto-detected.
  Runtime API if `CUDART_VERSION >= 12080`, Driver API otherwise.
- If user-defined to **0**: forces Runtime API (`static_assert` if CUDA < 12.8).
- If user-defined to **1**: forces Driver API.

Type aliases switch between Runtime and Driver types:

| `cuda_api` alias   | Runtime API type     | Driver API type       |
|---------------------|----------------------|-----------------------|
| `StreamHandle`      | `cudaStream_t`       | `CUstream`            |
| `DeviceHandle`      | `int`                | `CUdevice`            |
| `LibraryHandle`     | `cudaLibrary_t`      | `CUlibrary`           |
| `KernelHandle`      | `cudaKernel_t`       | `CUkernel`            |
| `ResultType`        | `cudaError_t`        | `CUresult`            |
| `kSuccess`          | `cudaSuccess`        | `CUDA_SUCCESS`        |

Function wrappers use the `_TVM_FFI_CUDA_FUNC(name)` macro (resolving to
`cuda##name` or `cu##name`) for most operations. The `LaunchKernel` wrapper
diverges because the Runtime and Driver APIs have different parameter packing:
the Runtime API uses `cudaLaunchKernel(kernel_as_void_ptr, ::dim3, ::dim3,
args, smem, stream)`, while the Driver API uses `cuLaunchKernel(func, gridX,
gridY, gridZ, blockX, blockY, blockZ, smem, stream, args, nullptr)`.

When using Driver API, link against `cuda` (`libcuda.so.1`). When using Runtime
API, link against `CUDA::cudart`.

### base.h: dim3 and error checking

`tvm::ffi::dim3` is a custom 3D dimension struct (not CUDA's `::dim3`) to
avoid including CUDA host headers in the general TVM FFI namespace:

```cpp
struct dim3 {
  unsigned int x, y, z;
  dim3() : x(1), y(1), z(1) {}
  explicit dim3(unsigned int x_) : x(x_), y(1), z(1) {}
  dim3(unsigned int x_, unsigned int y_) : x(x_), y(y_), z(1) {}
  dim3(unsigned int x_, unsigned int y_, unsigned int z_) : x(x_), y(y_), z(z_) {}
};
```

Two error-checking macros exist:

- `TVM_FFI_CHECK_CUDA_ERROR(stmt)` (in `base.h`): strictly Runtime API,
  always uses `cudaGetErrorName`/`cudaGetErrorString`. For non-cubin-launcher
  CUDA code.
- `TVM_FFI_CHECK_CUBIN_LAUNCHER_CUDA_ERROR(stmt)` (in `unified_api.h`): the
  unified macro that works with both `cudaError_t` and `CUresult` via
  `cuda_api::GetErrorString()`.

Error messages include both the symbolic name and numeric code, for example:
`"CUDA Error: cudaErrorInvalidValue (1): invalid argument"`.

### CUBIN embedding strategies

Three macros for consuming embedded CUBIN data correspond to three embedding
mechanisms:

**Object linking** (`TVM_FFI_EMBED_CUBIN`):

Declares `extern "C"` symbols `__tvm_ffi__cubin_<name>` and
`__tvm_ffi__cubin_<name>_end`, and creates an anonymous-namespace singleton
`EmbedCubinModule_<name>` wrapping a `CubinModule`:

```cpp
#define TVM_FFI_EMBED_CUBIN(name)                        \
  extern "C" const char __tvm_ffi__cubin_##name[];       \
  extern "C" const char __tvm_ffi__cubin_##name##_end[]; \
  namespace {                                            \
  struct EmbedCubinModule_##name {                       \
    tvm::ffi::CubinModule mod{__tvm_ffi__cubin_##name};  \
    static EmbedCubinModule_##name* Global() {           \
      static EmbedCubinModule_##name inst;               \
      return &inst;                                      \
    }                                                    \
  };                                                     \
  }
```

The symbols are created by the embedding toolchain (`ld -r -b binary` + `objcopy`
renaming) via CMake utilities or the Python `embed_cubin` tool.

**bin2c header** (`TVM_FFI_EMBED_CUBIN_FROM_BYTES`):

Takes a `name` and a `const unsigned char[]` byte array (e.g., from NVIDIA's
`bin2c` tool). Same singleton pattern, no `extern "C"` needed:

```cpp
#include "kernel_fatbin.h"  // bin2c-generated: unsigned char imageBytes[] = { ... };
TVM_FFI_EMBED_CUBIN_FROM_BYTES(env, imageBytes);
```

**C++23/26 `#embed`** (same `TVM_FFI_EMBED_CUBIN_FROM_BYTES` macro):

The byte array comes from `#embed "file.fatbin"`:

```cpp
constexpr unsigned char image[]{
#embed "kernel_fatbin.fatbin"
};
TVM_FFI_EMBED_CUBIN_FROM_BYTES(env, image);
```

Requires Clang 19+, GCC 15+, or C++26 standard mode. The CMake example
(`cpp_embed/CMakeLists.txt`) sets `CMAKE_CXX_STANDARD 26` and checks
`__cpp_pp_embed` via `CheckCXXSymbolExists` (`ed067c1`).

**Kernel retrieval** via `TVM_FFI_EMBED_CUBIN_GET_KERNEL(name, kernel_name)`
expands to `EmbedCubinModule_##name::Global()->mod[kernel_name]`.

| Strategy          | Macro                            | Requires         | Portability      |
|-------------------|----------------------------------|------------------|------------------|
| Object linking    | `TVM_FFI_EMBED_CUBIN`            | ld + objcopy     | Linux only       |
| bin2c header      | `TVM_FFI_EMBED_CUBIN_FROM_BYTES` | NVIDIA bin2c     | Any compiler     |
| C++23/26 `#embed` | `TVM_FFI_EMBED_CUBIN_FROM_BYTES` | C++26 compiler   | Modern compilers |

### Static kernel caching pattern

The recommended usage pattern caches the `CubinKernel` in a function-local
`static` variable for zero-overhead repeated access:

```cpp
static auto kernel = TVM_FFI_EMBED_CUBIN_GET_KERNEL(my_kernels, "add_one");
```

This works because the `EmbedCubinModule_<name>` singleton is initialized once
(function-local static with thread-safe initialization per C++11), `operator[]`
returns a `CubinKernel` by move so the static variable captures the kernel
handle on first call, and subsequent calls skip initialization entirely.

### Multi-GPU execution

CUBIN modules loaded via `cudaLibraryLoadData` / `cuLibraryLoadData` are
usable across all GPUs. The kernel launch targets whichever device is current
at launch time. TVM FFI uses `TVMFFIEnvGetStream(device_type, device_id)` to
get the correct per-device stream from the `StreamContext` thread-local state:

```cpp
DLDevice device = tensor.device();
cuda_api::StreamHandle stream = static_cast<cuda_api::StreamHandle>(
    TVMFFIEnvGetStream(device.device_type, device.device_id));
kernel.Launch(args, grid, block, stream);
```

`SetMaxDynamicSharedMemory` iterates over ALL devices (via
`cuda_api::GetDeviceCount`) and sets the attribute per device, tolerating
individual device failures.

### Canonical kernel launch pattern

```cpp
TVM_FFI_EMBED_CUBIN(my_kernels);

void MyKernel(tvm::ffi::TensorView x, tvm::ffi::TensorView y) {
  static auto kernel = TVM_FFI_EMBED_CUBIN_GET_KERNEL(my_kernels, "my_kernel");

  int64_t n = x.size(0);
  void* x_ptr = x.data_ptr();
  void* y_ptr = y.data_ptr();
  void* args[] = {&x_ptr, &y_ptr, &n};

  tvm::ffi::dim3 grid((n + 255) / 256);
  tvm::ffi::dim3 block(256);

  DLDevice device = x.device();
  tvm::ffi::cuda_api::StreamHandle stream =
      static_cast<tvm::ffi::cuda_api::StreamHandle>(
          TVMFFIEnvGetStream(device.device_type, device.device_id));

  TVM_FFI_CHECK_CUBIN_LAUNCHER_CUDA_ERROR(kernel.Launch(args, grid, block, stream));
}

TVM_FFI_DLL_EXPORT_TYPED_FUNC(my_kernel, MyKernel);
```

Key points: the `args` array must contain **pointers to values**, not values
themselves. Grid/block dimensions use `tvm::ffi::dim3`. Functions are exported
to Python via `TVM_FFI_DLL_EXPORT_TYPED_FUNC`.

### Dynamic CUBIN loading at runtime

As an alternative to compile-time embedding, `CubinModule` can be constructed
directly from runtime-provided `Bytes` or `const char*` data:

```cpp
static std::unique_ptr<tvm::ffi::CubinModule> g_cubin_module;
static std::unique_ptr<tvm::ffi::CubinKernel> g_add_one_kernel;

void SetCubin(const tvm::ffi::Bytes& cubin) {
  g_cubin_module = std::make_unique<tvm::ffi::CubinModule>(cubin);
  g_add_one_kernel = std::make_unique<tvm::ffi::CubinKernel>(
      (*g_cubin_module)["add_one_cuda"]);
}
```

Use cases include JIT-compiled kernels, CUBIN loaded from file or network at
runtime, and CUBIN swapping for A/B testing.

### Dynamic shared memory

Basic usage passes `dyn_smem_bytes` to `kernel.Launch()`:

```cpp
kernel.Launch(args, grid, block, stream, /*dyn_smem_bytes=*/1024);
```

Advanced usage: `GetKernelWithMaxDynamicSharedMemory(name, max)` pre-configures
the kernel to allow up to `max` bytes. If `max == -1` (default), it computes
`device_max_shared_mem - kernel_static_shared_mem` for each device by querying
`cudaDevAttrMaxSharedMemoryPerBlock` (attribute 8) and the kernel's static
shared memory via `cuda_api::GetKernelSharedMem`, then calls
`cuda_api::SetKernelMaxDynamicSharedMem`.

## APIs

### C++ API

```cpp
// include/tvm/ffi/extra/cuda/cubin_launcher.h
namespace tvm { namespace ffi {

class CubinModule {
 public:
  explicit CubinModule(const Bytes& bytes);
  explicit CubinModule(const char* code);
  explicit CubinModule(const unsigned char* code);
  ~CubinModule();
  CubinKernel GetKernel(const char* name);
  CubinKernel GetKernelWithMaxDynamicSharedMemory(
      const char* name, int64_t dynamic_smem_max = -1);
  CubinKernel operator[](const char* name);
  cuda_api::LibraryHandle GetHandle() const;
};

class CubinKernel {
 public:
  CubinKernel(cuda_api::LibraryHandle library, const char* name);
  cuda_api::ResultType Launch(void** args, dim3 grid, dim3 block,
                              cuda_api::StreamHandle stream,
                              uint32_t dyn_smem_bytes = 0);
  cuda_api::KernelHandle GetHandle() const;
};

// Macros
TVM_FFI_EMBED_CUBIN(name)
TVM_FFI_EMBED_CUBIN_FROM_BYTES(name, imageBytes)
TVM_FFI_EMBED_CUBIN_GET_KERNEL(name, kernel_name)
TVM_FFI_CHECK_CUDA_ERROR(stmt)
TVM_FFI_CHECK_CUBIN_LAUNCHER_CUDA_ERROR(stmt)

}}  // namespace tvm::ffi
```

### CMake API

```cmake
# cmake/Utils/EmbedCubin.cmake

# Compile .cu source to CUBIN (compatibility for CMake < 3.27)
add_tvm_ffi_cubin(<target> CUDA <source>)

# Compile .cu source to FATBIN (multi-architecture)
add_tvm_ffi_fatbin(<target> CUDA <source>)

# Embed a CUBIN/FATBIN file into an object library target
tvm_ffi_embed_bin_into(<target> SYMBOL <symbol> BIN <bin_file>)
```

Typical CMake workflow:

```cmake
# Step 1: Compile to FATBIN
set(CMAKE_CUDA_ARCHITECTURES 75;80;86;89;90;100;120)
add_tvm_ffi_fatbin(kernel_fatbin CUDA src/kernel.cu)

# Step 2: Build shared library with C++ wrapper
add_library(lib_embedded SHARED src/lib_embedded.cc)
target_link_libraries(lib_embedded PRIVATE tvm_ffi::header tvm_ffi::shared CUDA::cudart)

# Step 3: Embed FATBIN into the object file
tvm_ffi_embed_bin_into(lib_embedded SYMBOL env BIN "$<TARGET_OBJECTS:kernel_fatbin>")
```

`EmbedCubin.cmake` defaults `CMAKE_CUDA_RUNTIME_LIBRARY` to `Shared` if unset,
to prevent static cudart linking which pins the required driver version.

### Python API

```python
# NVRTC compilation
from tvm_ffi.cpp import nvrtc
cubin_bytes = nvrtc.nvrtc_compile(source, name="kernel.cu", arch=None, extra_opts=None)

# Inline loading with embedded CUBIN
from tvm_ffi import cpp
mod = cpp.load_inline(
    "my_module",
    cuda_sources=cpp_code,
    embed_cubin={"my_kernels": cubin_bytes},
)

# CLI embedding utility
# python -m tvm_ffi.utils.embed_cubin \
#     --output-obj new.o --input-obj old.o --cubin kernel.cubin --name my_kernels
```

## Implementation

### Source files

| File | Role |
|------|------|
| `include/tvm/ffi/extra/cuda/cubin_launcher.h` | Public API: CubinModule, CubinKernel, macros |
| `include/tvm/ffi/extra/cuda/internal/unified_api.h` | Compile-time Runtime/Driver API abstraction |
| `include/tvm/ffi/extra/cuda/base.h` | dim3, `TVM_FFI_CHECK_CUDA_ERROR` |
| `include/tvm/ffi/extra/c_env_api.h` | `TVMFFIEnvGetStream` declaration |
| `cmake/Utils/EmbedCubin.cmake` | CMake utilities for CUBIN/FATBIN embedding |
| `cmake/Utils/ObjectCopyUtil.cmake` | Helper for copying object files with new extension |
| `python/tvm_ffi/utils/embed_cubin.py` | Python utility for CUBIN embedding into `.o` files |
| `python/tvm_ffi/cpp/nvrtc.py` | NVRTC compilation wrapper |
| `python/tvm_ffi/cpp/extension.py` | `load_inline` with `embed_cubin` support |

### embed_cubin.py: 5-step process

The `embed_cubin` function in `python/tvm_ffi/utils/embed_cubin.py` (`8b46833`)
performs 5 steps to merge CUBIN data into an existing object file:

1. **Create CUBIN object:** `ld -r -b binary -o cubin_<name>.o
   embedded_<name>.cubin` wraps raw binary as a relocatable ELF object with
   auto-generated symbols `_binary_embedded_<name>_cubin_start` / `_end`.
2. **Add `.note.GNU-stack`:** `objcopy --add-section
   .note.GNU-stack=/dev/null --set-section-flags
   .note.GNU-stack=noload,readonly` marks the stack as non-executable to
   avoid linker warnings.
3. **Rename symbols:** `objcopy --rename-section .data=.rodata,...
   --redefine-sym _binary_embedded_<name>_cubin_start=__tvm_ffi__cubin_<name>
   --redefine-sym
   _binary_embedded_<name>_cubin_end=__tvm_ffi__cubin_<name>_end` moves
   data to `.rodata` and renames symbols to TVM FFI convention.
4. **Merge objects:** `ld -r -o output.o input.o cubin_renamed.o` performs a
   relocatable link combining the C++ code object and the CUBIN data object.
5. **Localize symbols:** `objcopy --localize-symbol __tvm_ffi__cubin_<name>
   --localize-symbol __tvm_ffi__cubin_<name>_end` prevents symbol collisions
   when multiple object files embed CUBINs with the same name.

Requirements: GNU binutils (`ld`, `objcopy`). Linux/Unix only.

### load_inline embed_cubin integration

`tvm_ffi.cpp.load_inline()` accepts `embed_cubin: Mapping[str, bytes] | None`.
When provided, the ninja-based build system:

1. Writes each CUBIN to the build directory as `<name>.cubin`.
2. Compiles all C++ sources to individual `.o` files.
3. Merges all `.o` files into `unified.o` via `ld -r`.
4. Chains `embed_cubin` operations: for each CUBIN name, runs `python -m
   tvm_ffi.utils.embed_cubin` to merge the CUBIN into the unified object.
5. Links the final object into the shared library.

```text
.cc files -> compile -> .o files -> ld -r -> unified.o
.cubin files ------+
                   v
unified.o + cubin -> embed_cubin -> unified_with_X.o -> link -> .so
```

Cache key includes the `embed_cubin` dict in the SHA-256 hash. Windows
limitation: `embed_cubin` raises `NotImplementedError`.

### NVRTC integration

`tvm_ffi.cpp.nvrtc.nvrtc_compile()` compiles CUDA C++ source to CUBIN at
runtime using NVIDIA NVRTC. Requires the `cuda-python` package
(`cuda.bindings.driver` and `cuda.bindings.nvrtc`). Auto-detects GPU
architecture via `cuDeviceGetAttribute` for compute capability if `arch` is not
specified. On compilation failure, retrieves the NVRTC log via
`nvrtcGetProgramLog` for diagnostic output.

```python
from tvm_ffi.cpp import nvrtc

cuda_source = '''
extern "C" __global__ void add_one(float* x, float* y, int n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) y[idx] = x[idx] + 1.0f;
}
'''
cubin_bytes = nvrtc.nvrtc_compile(cuda_source, name="kernels.cu")
```

### Triton integration

Triton kernels can be compiled to CUBIN and launched through TVM FFI's CUBIN
launcher (`731955b`). The workflow is: define a Triton kernel with `@triton.jit`,
trigger compilation by calling it once, extract CUBIN bytes from
`compiled_kernel.kernel`, and embed via `load_inline(...,
embed_cubin={"triton_cubin": cubin_bytes})`.

Triton kernels may require extra dummy parameters in the argument list, and the
actual block size may differ from the `BLOCK` constexpr in the Triton source
(e.g., Triton may use `.reqntid 128` regardless of `BLOCK=1024`):

```cpp
uint64_t dummy_ptr = 0;
void* args[] = {&x_ptr, &y_ptr, &n, &dummy_ptr, &dummy_ptr};
```

### Integration with broader TVM FFI

- **Module system:** CUBIN launcher libraries are loaded as TVM FFI modules via
  `load_module("path.so")` or `load_inline()`. Functions are exported with
  `TVM_FFI_DLL_EXPORT_TYPED_FUNC` and discovered via the `__tvm_ffi_<name>`
  symbol prefix.
- **TensorView:** Kernel arguments arrive as `tvm::ffi::TensorView` (a
  non-owning DLPack tensor view), providing `data_ptr()`, `device()`,
  `size()`, `ndim()`.
- **StreamContext:** `TVMFFIEnvGetStream` bridges TVM FFI stream management
  (thread-local `StreamContext`) with CUDA stream handles.
- **Bytes type:** `tvm::ffi::Bytes` is an owning value type for binary data (with small-bytes optimization), used
  for passing CUBIN data from Python to C++ in the dynamic loading path.
- **Error system:** Uses `TVM_FFI_THROW(RuntimeError)` and `TVM_FFI_CHECK`
  from the core FFI error system.

### Example directory structure

```text
examples/cubin_launcher/
  embedded_cubin/
    embed_with_tvm_ffi/   -- Object linking example (ld + objcopy)
    include_bin2c/        -- bin2c header example
    cpp_embed/            -- C++23/26 #embed example
  dynamic_cubin/          -- Runtime CUBIN loading example
  example_nvrtc_cubin.py  -- NVRTC + inline embed example
  example_triton_cubin.py -- Triton + inline embed example
  benchmark_overhead.py   -- Launch overhead benchmark
```

## History

- 2025-11-25: Initial cubin launcher utility added as extra header: `CubinModule`, `CubinKernel`, `TVM_FFI_EMBED_CUBIN` macros, `TVM_FFI_CHECK_CUDA_ERROR` (`d49effd`)
- 2025-11-25: `CUDADeviceGuard` RAII struct added (`cdfd041`)
- 2025-12-12: `embed_cubin.py` docstring formatting updated (`8b46833`)
- 2025-12-22: CMake import targets renamed for backward compatibility (`a1cb746`)
- 2025-12-25: Major refactor: three embedding strategies (`TVM_FFI_EMBED_CUBIN`, `TVM_FFI_EMBED_CUBIN_FROM_BYTES`); `add_tvm_ffi_cubin`/`add_tvm_ffi_fatbin` replace `tvm_ffi_generate_cubin`; `internal/unified_api.h` introduced for Runtime/Driver API abstraction; examples reorganized into `cpp_embed`, `embed_with_tvm_ffi`, `include_bin2c` (`b16f11f`)
- 2026-01-12: CUDA unified API isolated to cubin launcher only, renamed macro to `TVM_FFI_CUBIN_LAUNCHER_USE_DRIVER_API` (`10cb004`)
- 2026-01-27: Updated `#embed` detection logic using `CheckCXXSymbolExists` for `__cpp_pp_embed` (`ed067c1`)
- 2026-02-10: Triton integration simplified: extract `compiled_kernel` directly from Triton call (`731955b`)

## Related

- Design docs:
  - `.repo-knowledge/design/007-module-system.md` -- Module system, `load_inline`, `StreamContext`
  - `.repo-knowledge/design/009-tensor-and-dlpack.md` -- TensorView and DLPack integration
- Range summaries:
  - `.repo-knowledge/ranges/2025-11-30-0EE6444-4076EF5.md`
  - `.repo-knowledge/ranges/2025-12-29-5A82940-6E7CAFA.md`
  - `.repo-knowledge/ranges/2026-01-31-0CAA06E-E4D3B3E.md`
  - `.repo-knowledge/ranges/2026-02-22-F0B3AAA-97FFC9B.md`
