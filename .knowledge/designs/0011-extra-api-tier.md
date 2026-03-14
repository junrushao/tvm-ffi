---
status: "active"
confidence: "high"
---
# Extra API Tier

**TL;DR**
- The `include/tvm/ffi/extra/` directory and `TVM_FFI_EXTRA_CXX_API` visibility macro formalize a new architectural tier for non-core C++ APIs that depend on the core FFI but are not required for essential functionality.
- The extra tier is gated by the CMake option `TVM_FFI_USE_EXTRA_CXX_API` (default ON), allowing downstream projects to build a smaller core library without these features.
- Current extra-tier features: `StructuralEqual`, `StructuralHash`, dataclass operations (`DeepCopy`, `ReprPrint`, `RecursiveHash`, `RecursiveEq`, `RecursiveLt/Le/Gt/Ge` -- consolidated in `dataclass.cc`), JSON parser/writer (`json::Parse`/`json::Stringify`), JSON graph serialization (`ToJSONGraph`/`FromJSONGraph`), Base64 utilities, AccessPath/AccessStep reflection registration, `MakeObjectFromPackedArgs`, Module system (`ModuleObj`/`Module`, library loading, import trees), environment context (`EnvContext` with stream table + DLPack allocator, exposed via `TVMFFIEnvSetStream`/`TVMFFIEnvGetStream`/`TVMFFIEnvSetTensorAllocator`/`TVMFFIEnvGetTensorAllocator`), environment C APIs (`TVMFFIEnvCheckSignals`, `TVMFFIEnvRegisterCAPI`), STL interop (`stl.h`), CUDA utilities (`cuda/cubin_launcher.h`, `cuda/device_guard.h`, unified Driver/Runtime API), `dtype_trait<T>` C++ type-to-DLDataType mapping, and testing utilities. Core reflection primitives like the `AccessPath` header remain unconditionally compiled.

## Problem Statement

### Background

The structural equal/hash implementations are useful for compiler IR but are not needed by all consumers of the FFI (e.g., inference-only deployments). They add compilation units and link-time overhead. Additionally, these C++ APIs have cross-ABI limitations (MSVC vs Itanium name mangling) that make them unsuitable for the core C ABI header.

### Solution

A separate directory (`include/tvm/ffi/extra/`) with its own visibility macro (`TVM_FFI_EXTRA_CXX_API`), gated by a CMake option. This cleanly separates core and non-core functionality at both the source and build levels.

### Goals

- **Goal**: Allow downstream projects to exclude non-core features for smaller binaries.
- **Goal**: Keep the C ABI header (`c_api.h`) free of non-core macros and declarations.
- **Goal**: Clear layering contract: extra depends on core, never vice versa.
- **Non-goal**: Extra-tier APIs do not have C ABI stability guarantees across different compiler ABIs.

## Design

### Directory Layout

```
include/tvm/ffi/extra/
    base.h                  # TVM_FFI_EXTRA_CXX_API macro definition
    structural_equal.h      # StructuralEqual class
    structural_hash.h       # StructuralHash class
    structural_key.h        # StructuralKey (hash-caching wrapper)
    dataclass.h             # DeepCopy, ReprPrint, RecursiveHash, RecursiveEq, RecursiveLt/Le/Gt/Ge
    json.h                  # json::Parse, json::Stringify, type aliases
    serialization.h         # ToJSONGraph, FromJSONGraph
    base64.h                # Base64Encode, Base64Decode (header-only)
    stl.h                   # STL container <-> FFI conversion (header-only)
    module.h                # ModuleObj, Module (dynamically loadable modules)
    c_env_api.h             # extern "C" environment APIs (stream, signals, module symbols)
    dtype.h                 # dtype_trait<T> compile-time C++ type to DLDataType mapping
    cuda/
        base.h              # Common CUDA driver API declarations, dim3 struct
        cubin_launcher.h    # CubinModule, CubinKernel (header-only, unified Driver/Runtime)
        device_guard.h      # CUDADeviceGuard RAII (header-only, requires CUDA RT)
        internal/
            unified_api.h   # Unified CUDA Driver/Runtime API abstraction (internal)

src/ffi/extra/
    structural_equal.cc     # Structural equality (gated by TVM_FFI_USE_EXTRA_CXX_API)
    structural_hash.cc      # Structural hashing (gated by TVM_FFI_USE_EXTRA_CXX_API)
    json_parser.cc          # JSONParserContext + JSONParser
    json_writer.cc          # JSONWriter
    serialization.cc        # ObjectGraphSerializer + ObjectGraphDeserializer
    reflection_extra.cc     # AccessPath/AccessStep reflection, MakeObjectFromPackedArgs, StructuralKey reflection
    dataclass.cc            # Unified: DeepCopy, ReprPrint, RecursiveHash, RecursiveEq/Lt/Le/Gt/Ge (replaces deep_copy.cc + repr_print.cc)
    module.cc               # ModuleObj base, LoadFromFile, global function registrations
    library_module.cc       # LibraryModuleObj, ProcessLibraryBin, ContextSymbolRegistry
    library_module_dynamic_lib.cc  # DSOLibrary (dlopen/LoadLibrary)
    library_module_system_lib.cc   # SystemLibrary, SystemLibSymbolRegistry
    module_internal.h       # Library base class, ModuleObj::InternalUnsafe
    buffer_stream.h         # BufferInStream for binary deserialization
    env_context.cc          # Unified EnvContext TLS (stream table + DLPack allocator)
    env_c_api.cc            # EnvCAPIRegistry, TVMFFIEnvCheckSignals, TVMFFIEnvRegisterCAPI
    testing.cc              # testing.nop and other test utilities (moved from core)
```

### Visibility Macro

`TVM_FFI_EXTRA_CXX_API` is defined in `include/tvm/ffi/extra/base.h` and defaults to `TVM_FFI_DLL`. It is functionally identical to `TVM_FFI_DLL` on all platforms but serves as a documentation marker:

- Implementations live in `.cc` files (not header-only) to reduce compile-time overhead.
- Inputs/outputs are restricted to POD, `Any`, and `ObjectRef` types for ABI stability.
- May have cross-ABI issues between MSVC and Itanium name mangling on Windows.

The macro was originally defined in `c_api.h` and moved to `extra/base.h` in commit `3fc0391` to keep `c_api.h` as the pure C ABI surface.

### Build Gating

```cmake
option(TVM_FFI_USE_EXTRA_CXX_API "Build extra C++ API" ON)

if(TVM_FFI_USE_EXTRA_CXX_API)
  list(APPEND tvm_ffi_objs_sources
    src/ffi/extra/structural_equal.cc
    src/ffi/extra/structural_hash.cc
    src/ffi/extra/json_parser.cc
    src/ffi/extra/json_writer.cc
    src/ffi/extra/serialization.cc
    src/ffi/extra/dataclass.cc
    src/ffi/extra/reflection_extra.cc
    src/ffi/extra/module.cc
    src/ffi/extra/library_module.cc
    src/ffi/extra/library_module_dynamic_lib.cc
    src/ffi/extra/library_module_system_lib.cc
    src/ffi/extra/stream_context.cc
    src/ffi/extra/env_c_api.cc
    src/ffi/extra/testing.cc)
endif()
```

The `AccessPath`/`AccessStep` header (`include/tvm/ffi/reflection/access_path.h`) is always available as a core header. However, the reflection registration for `AccessPathObj`/`AccessStepObj` fields/methods and `MakeObjectFromPackedArgs` was moved to `reflection_extra.cc` and is now gated behind `TVM_FFI_USE_EXTRA_CXX_API`. When the extra tier is disabled, these types exist in the type table (via static init of the header) but lack field/method reflection metadata.

### Layering Contract

```
c_api.h (C ABI) -- stable, no C++ types
    |
    v
include/tvm/ffi/*.h (core C++ headers) -- ABI-stable for same-compiler builds
    |
    v
include/tvm/ffi/extra/base.h -- visibility macro
    |
    v
include/tvm/ffi/extra/*.h (extra features) -- non-core, same-compiler only
    |
    v
include/tvm/ffi/reflection/*.h (core reflection read-path)
```

Extra headers may include core headers. Core headers never include extra headers.

### Key Classes, Fields and Interfaces

- **`TVM_FFI_EXTRA_CXX_API`** (`include/tvm/ffi/extra/base.h`): Visibility macro for extra-tier API functions.
- **`TVM_FFI_USE_EXTRA_CXX_API`** (CMake option): Build-time gate. Default ON.
- **`StructuralEqual`** (`include/tvm/ffi/extra/structural_equal.h`): Deep comparison of `Any` values.
- **`StructuralHash`** (`include/tvm/ffi/extra/structural_hash.h`): Stable hashing of `Any` values.
- **`json::Parse`** / **`json::Stringify`** (`include/tvm/ffi/extra/json.h`): Lightweight JSON parsing and serialization. Supports extended syntax (NaN, Infinity, int64 integers). Safe under `-ffast-math`.
- **`ToJSONGraph`** / **`FromJSONGraph`** (`include/tvm/ffi/extra/serialization.h`): Reflection-based JSON graph serialization preserving object identity. Custom per-type hooks via `__data_to_json__`/`__data_from_json__` TypeAttrColumns.
- **`ToJSONGraphString`** / **`FromJSONGraphString`**: String-in/string-out convenience wrappers.
- **`Base64Encode`** / **`Base64Decode`** (`include/tvm/ffi/extra/base64.h`): Header-only RFC 4648 base64.
- **`reflection_extra.cc`**: AccessPath/AccessStep reflection registration, `MakeObjectFromPackedArgs` (moved from core build), and `StructuralKey` reflection registration.
- **`StructuralKeyObj` / `StructuralKey`** (`include/tvm/ffi/extra/structural_key.h`): Frozen wrapper caching structural hash for content-addressed object lookup. See [0009-structural-equal-hash](0009-structural-equal-hash.md).
- **`ffi.DeepCopy`**, **`ffi.ReprPrint`**, **`ffi.RecursiveHash`**, **`ffi.RecursiveEq`**, **`ffi.RecursiveLt/Le/Gt/Ge`** (`src/ffi/extra/dataclass.cc`): Unified dataclass operations backed by the `ObjectGraphDFS` CRTP engine. Replaces former `deep_copy.cc` and `repr_print.cc`. See [0027-dataclass-operations](0027-dataclass-operations.md).
- **`ModuleObj`** / **`Module`** (`include/tvm/ffi/extra/module.h`): Abstract base class for dynamically loadable modules. Virtual interface for function lookup, serialization, import management. See [0013-module-system](0013-module-system.md).
- **`TVMFFIEnvSetStream`** / **`TVMFFIEnvGetStream`** (`include/tvm/ffi/extra/c_env_api.h`): `extern "C"` functions for thread-local per-device stream context management (renamed from `TVMFFIEnvSetCurrentStream`/`TVMFFIEnvGetCurrentStream` in commit `f81ab9c`). Unlike other extra-tier APIs, these follow the C ABI convention (POD parameters, `int` return codes) and use `TVM_FFI_DLL` visibility (not `TVM_FFI_EXTRA_CXX_API`) because they are `extern "C"`.
- **`TVMFFIEnvSetTensorAllocator`** / **`TVMFFIEnvGetTensorAllocator`** (`include/tvm/ffi/extra/c_env_api.h`): `extern "C"` functions for setting/getting the thread-local `DLPackTensorAllocator`. The allocator has a two-tier lookup: TLS first, then global static. Added in commit `f81ab9c`. See [0020-dlpack-exchange-acceleration](0020-dlpack-exchange-acceleration.md).
- **`TVMFFIEnvCheckSignals`** / **`TVMFFIEnvRegisterCAPI`** (`include/tvm/ffi/extra/c_env_api.h`): Host-environment integration APIs (Python signal checking, C API registration). Moved from `c_api.h` to the extra tier because they are not needed by minimal deployments.
- **`TVMFFIEnvModLookupFromImports`** / **`TVMFFIEnvModRegisterContextSymbol`** / **`TVMFFIEnvModRegisterSystemLibSymbol`** (`include/tvm/ffi/extra/c_env_api.h`): Module-scoped `extern "C"` APIs for generated kernel code to resolve functions and register symbols.
- **`testing.cc`**: Test utility functions (`testing.nop` etc.), moved from the core build to extra tier.
- **STL interop** (`include/tvm/ffi/extra/stl.h`): Header-only TypeTraits specializations for `std::vector`, `std::array`, `std::tuple`, `std::optional`, `std::variant`, `std::map`, `std::unordered_map`, `std::pair`, `std::string`. Converts STL types to/from FFI containers at the packed-function boundary. See [0024-stl-interop-layer](0024-stl-interop-layer.md).
- **CUDA CubinModule/CubinKernel** (`include/tvm/ffi/extra/cuda/cubin_launcher.h`): Header-only CUDA wrapper (unified Driver/Runtime API) for loading CUBIN from memory and launching kernels. Includes `TVM_FFI_EMBED_CUBIN` and `TVM_FFI_LOAD_LIBRARY_FROM_BYTES` macros. See [0025-cubin-launcher-system](0025-cubin-launcher-system.md).
- **Unified CUDA API** (`include/tvm/ffi/extra/cuda/internal/unified_api.h`): Internal header providing unified type aliases and macros over CUDA Driver and Runtime APIs. Selects API backend based on `CUDART_VERSION`.
- **CUDADeviceGuard** (`include/tvm/ffi/extra/cuda/device_guard.h`): RAII device context guard analogous to PyTorch's `c10::cuda::CUDAGuard`.
- **dtype_trait** (`include/tvm/ffi/extra/dtype.h`): Header-only compile-time mapping from C++ scalar types to `DLDataType` values. Covers standard integer/float types, CUDA half/bfloat16/fp8/fp4 types, and HIP equivalents. Companion Python module `tvm_ffi.cpp.dtype` provides the reverse mapping for Python-side dtype construction.
- **AMD HIP support in `cpp.extension`** (`python/tvm_ffi/cpp/extension.py`, commit `65b5e90` #460): The `load_inline`/`build_inline` functions support AMD HIP (ROCm) compilation alongside CUDA. Auto-detection via `_detect_gpu_backend()` checks `TVM_FFI_GPU_BACKEND` env var, then probes for ROCm installation. HIP compilation uses `hipcc` with `--offload-arch` flags auto-detected via `rocm_agent_enumerator` or `rocminfo`. The `backend` parameter (`"cuda"` or `"hip"`) can be set explicitly, or defaults to auto-detection. ROCm-specific flags: `-D__HIP_PLATFORM_AMD__=1`, `-fno-gpu-rdc`, `-lamdhip64`.

### Contracts, Assumptions and Invariants

- **One-way dependency**: Extra code depends on core, never the reverse.
- **AccessPath header is core, registration is extra**: The `AccessPath`/`AccessStep` header is unconditionally available, but field/method reflection metadata and `MakeObjectFromPackedArgs` require the extra tier. This means Python bindings for these types require `TVM_FFI_USE_EXTRA_CXX_API=ON`.
- **Same-compiler assumption**: Extra APIs assume callers and the library are compiled with the same C++ compiler/ABI. Cross-ABI calls (e.g., MSVC caller + GCC library) are not supported for extra APIs.
- **Fast-math safety**: The JSON parser and writer handle NaN/Infinity correctly even under `-ffast-math` via bit-level IEEE 754 helpers (using union-based type punning for strict-aliasing compliance).
- **C ABI within extra tier**: The `c_env_api.h` header hosts `extern "C"` functions that follow C ABI conventions (POD parameters, `int` return codes) despite living in the extra tier. These use `TVM_FFI_DLL` visibility, not `TVM_FFI_EXTRA_CXX_API`, because they do not have C++ name mangling concerns.
- **Environment context is thread-local**: `TVMFFIEnvSetStream`/`TVMFFIEnvGetStream` (renamed from `TVMFFIEnvSetCurrentStream`/`TVMFFIEnvGetCurrentStream`) operate on a per-thread, per-device stream table. `TVMFFIEnvSetTensorAllocator`/`TVMFFIEnvGetTensorAllocator` operate on a per-thread allocator. Both are managed by the unified `EnvContext` class (replacing the former `StreamContext`). Context set in one thread is invisible to other threads.

### Extension Points

- **New extra modules**: Add headers to `include/tvm/ffi/extra/` and sources to `src/ffi/extra/`, gated under `TVM_FFI_USE_EXTRA_CXX_API` in CMakeLists.txt.
- **Selective gating**: Finer-grained CMake options could be added for individual extra modules.

## Alternatives & Trade-offs

### Alternative: Only expose via C function registry

- Pros: Fully ABI-portable, works across MSVC/Itanium boundaries.
- Cons: Less ergonomic from C++ (must call through packed function interface). Extra APIs are convenience features where C++ ergonomics matter.

### Alternative: Header-only extra APIs

- Pros: No build gating needed, always available.
- Cons: Increases compile time for all consumers. The structural equal/hash implementations are substantial (500+ lines each).

### Alternative: Keep everything in one directory

- Pros: Simpler directory structure.
- Cons: No clear signal about which APIs are core vs. optional. The directory split makes the layering explicit.

## Related Work

### Design Docs & ADRs

- [`.knowledge/designs/0001-c-abi.md`](0001-c-abi.md) -- C ABI where `TVM_FFI_EXTRA_CXX_API` was originally defined
- [`.knowledge/designs/0009-structural-equal-hash.md`](0009-structural-equal-hash.md) -- Structural equal/hash consumer of the extra tier
- [`.knowledge/designs/0012-json-and-serialization.md`](0012-json-and-serialization.md) -- JSON module and graph serialization
- [`.knowledge/designs/0013-module-system.md`](0013-module-system.md) -- Module system (extra-tier consumer)
- [`.knowledge/ADRs/0012-extra-cxx-api-macro.md`](../ADRs/0012-extra-cxx-api-macro.md) -- Decision record for the macro
- [`.knowledge/ADRs/0015-json-reuses-any-as-value.md`](../ADRs/0015-json-reuses-any-as-value.md) -- Decision to reuse Any as JSON value type
- [`.knowledge/ADRs/0018-module-in-extra-tier.md`](../ADRs/0018-module-in-extra-tier.md) -- Decision to place Module in extra tier
- [`.knowledge/ADRs/0020-thread-local-stream-context.md`](../ADRs/0020-thread-local-stream-context.md) -- Decision for thread-local stream context
- [`.knowledge/designs/0027-dataclass-operations.md`](0027-dataclass-operations.md) -- Unified dataclass operations (dataclass.cc)
- [`.knowledge/ADRs/0067-crtp-object-graph-dfs.md`](../ADRs/0067-crtp-object-graph-dfs.md) -- Decision to use CRTP-based DFS engine

### Evidence Matrix

- TVM_FFI_EXTRA_CXX_API introduction -> `.knowledge/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md` + `9445fe7`
- TVM_FFI_USE_EXTRA_CXX_API CMake option -> `.knowledge/commits/2025-07-26-2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec.md` + `2ec11f5`
- Move to extra/ directory, macro moved from c_api.h -> `.knowledge/commits/2025-07-30-3fc0391e29dac100ad37db45348090438e1db739.md` + `3fc0391`
- AccessPath promoted to core build -> `.knowledge/commits/2025-07-30-3fc0391e29dac100ad37db45348090438e1db739.md` + `3fc0391`
- JSON parser/writer added to extra tier -> `.knowledge/commits/2025-08-04-de541e37ad3820033856cc8a0af55e896af55a3b.md` + `de541e3`
- JSON graph serialization added -> `.knowledge/commits/2025-08-05-8eaefe04a044292e071263aca309b6991124c566.md` + `8eaefe0`
- AccessPath reflection + MakeObjectFromPackedArgs moved to extra tier -> `.knowledge/commits/2025-08-06-f4ede982f00257881d9ba7fe82dd8abc07e14690.md` + `f4ede98`
- JSON fast-math safety -> `.knowledge/commits/2025-08-15-1a271f00321b8cc16b72e58436716a05e2f62500.md` + `1a271f0`
- JSON fast-math union fix -> `.knowledge/commits/2025-08-22-3f4f4f11184fc9862670d929a32ab81beb79286b.md` + `3f4f4f1`
- Module system (ModuleObj, Library, DSOLibrary, SystemLibrary) -> `.knowledge/commits/2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md` + `538bef4`
- Stream context (TVMFFIEnvSetCurrentStream/GetCurrentStream) -> `.knowledge/commits/2025-08-19-0daaffedd23982ea09f8c38fec4eef1cca1d8cac.md` + `0daaffe`
- Env APIs moved to extra tier, Mod infix renames, testing.cc moved -> `.knowledge/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md` + `023ea44`
- TVMFFIEnvSetStream renamed to TVMFFIEnvSetCurrentStream -> `.knowledge/commits/2025-09-09-db987299f74aadcb4d8003cc6009cb67a75662c8.md` + `db98729`
- __tvm_ffi_env_stream__ generic stream protocol -> `.knowledge/commits/2025-09-09-db987299f74aadcb4d8003cc6009cb67a75662c8.md` + `db98729`
- C++ Doxygen docs (Breathe/Exhale integration) -> `.knowledge/commits/2025-09-07-24125d0ac466beb67965c1dd9ae23f2a71f424ad.md` + `24125d0`
- StreamContext -> EnvContext + DLPackTensorAllocator TLS + stream API rename to short form -> `.knowledge/commits/2025-09-12-f81ab9c25ae4d2a42706747c50c5c410c51d6cdd.md` + `f81ab9c`
- STL interop header (stl.h, 649 lines) -> `.knowledge/commits/2025-11-30-c3fc8f7f0e95a97beed342b6ddec4c3f6add0441.md` + `c3fc8f7`
- CUBIN launcher header + CUDA utilities -> `.knowledge/commits/2025-11-25-d49effdb22392363050e1f2d85cd4b31bf242cf0.md` + `d49effd`
- CUDA DeviceGuard utility -> `.knowledge/commits/2025-11-25-cdfd04109f74a2115c909302f4adf90536bce865.md` + `cdfd041`
- Cubin launcher refactor: unified CUDA API + byte-array loading -> `.knowledge/commits/2025-12-25-b16f11f60156cf07c6e5d3f9ddfa9e2273bdea03.md` + `b16f11f`
- dtype_trait<T> C++ type-to-DLDataType mapping + Python tvm_ffi.cpp.dtype -> `.knowledge/commits/2026-01-02-c51e519b2253c2c8754bebaf2f9af0434d89e1fc.md` + `c51e519`
- StructuralKey frozen wrapper (structural_key.h) -> `.knowledge/commits/2026-02-16-6adc8df7d2180ea14e463d3beeaa3d7eecb6f897.md` + `6adc8df`
- DFS-based ffi.ReprPrint (repr_print.cc) -> `.knowledge/commits/2026-02-18-b648c5d6b7981350c165096efbb98d00787e2900.md` + `b648c5d`
- Consolidation into dataclass.cc (deep_copy.cc + repr_print.cc -> dataclass.cc + RecursiveHash/Eq/Lt/Le/Gt/Ge) -> `.knowledge/commits/2026-02-27-6b39efbf381e48a8a42ab3779bc2adf587458fb3.md` + `6b39efb`
- AMD HIP support for cpp extension -> `.knowledge/commits/2026-02-19-65b5e90576185cb6300f43bc1307158dc99afb54.md` + `65b5e90`
