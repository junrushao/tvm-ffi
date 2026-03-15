---
scope: "inline-module-compilation"
status: "active"
last_updated_commit: "d49effdb22392363050e1f2d85cd4b31bf242cf0"
related_designs:
  - ".knowledge/designs/0017-inline-module-compilation.md"
  - ".knowledge/designs/0013-module-system.md"
related_adrs: []
---
# API Index: C++ Extension Module Compilation

**Scope**: Python APIs for compiling inline or file-based C++/CUDA source code into FFI modules.
**Design docs**: `.knowledge/designs/0017-inline-module-compilation.md`, `.knowledge/designs/0013-module-system.md`
**ADRs**: (none)

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| (none) | -- | No new C ABI functions; uses existing `TVM_FFI_DLL_EXPORT_TYPED_FUNC` in generated code |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| (none) | -- | -- | No new C++ types; generated code uses existing FFI headers |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| (none) | -- | Generated code uses `TVM_FFI_DLL_EXPORT_TYPED_FUNC(name, func)` from existing API |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `tvm_ffi.cpp.load_inline` | `(name: str, *, cpp_sources: str\|Sequence[str]=None, cuda_sources: str\|Sequence[str]=None, functions: Sequence[str]\|Mapping[str,str]\|str=None, extra_cflags: list=None, extra_cuda_cflags: list=None, extra_ldflags: list=None, extra_include_paths: list=None, build_directory: str=None, embed_cubin: Mapping[str,bytes]=None) -> Module` | JIT-compile inline C++/CUDA and load as Module (API renamed in 825aeb9; `embed_cubin` since d49effdb) |
| `tvm_ffi.cpp.build` | `(name: str, *, cpp_files: Sequence[str]\|str=None, cuda_files: Sequence[str]\|str=None, extra_cflags: list=None, extra_cuda_cflags: list=None, extra_ldflags: list=None, extra_include_paths: list=None, build_directory: str=None) -> str` | Compile file-based C++/CUDA into shared library; returns path (since c897e4c) |
| `tvm_ffi.cpp.load` | `(name: str, *, cpp_files: Sequence[str]\|str=None, cuda_files: Sequence[str]\|str=None, extra_cflags: list=None, extra_cuda_cflags: list=None, extra_ldflags: list=None, extra_include_paths: list=None, build_directory: str=None) -> Module` | Calls `build()` then `load_module()`; convenience wrapper (since c897e4c) |
| `tvm_ffi.cpp.build_ninja` | `(build_dir: str) -> None` | Run ninja in build directory; public since e6a654a (was `_build_ninja`) |
| `tvm_ffi.utils.FileLock` | `FileLock(lock_file_path: str)` | Cross-platform advisory file lock |
| `FileLock.acquire` | `() -> bool` | Non-blocking lock attempt; returns `False` if already held by same instance (since 021d78d) |
| `FileLock.blocking_acquire` | `(timeout: float=None, poll_interval: float=0.1) -> bool` | Blocking lock; raises `RuntimeError` if already held by same instance (since 021d78d) |
| `FileLock.release` | `() -> None` | Release lock |
| `tvm_ffi.cpp.nvrtc.nvrtc_compile` | `(source: str, *, name: str="kernel.cu", arch: str\|None=None, extra_opts: Sequence[str]\|None=None) -> bytes` | Compile CUDA source to cubin via NVRTC (since d49effdb). Requires `cuda-python`. |
| `tvm_ffi.utils.embed_cubin.embed_cubin` | `(cubin_path: Path, input_obj_path: Path, output_obj_path: Path, name: str, verbose: bool=False) -> None` | Embed cubin into object file via `ld`/`objcopy` (since d49effdb). Linux-only. |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| (none) | -- | Not available in Rust |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `cpp_source` param | `cpp_sources` | 825aeb9 | Accepts `str \| Sequence[str]` |
| `cuda_source` param | `cuda_sources` | 825aeb9 | Accepts `str \| Sequence[str]` |
| `cpp_functions` param | `functions` | 825aeb9 | Unified; exported name == C++ function name |
| `cuda_functions` param | *(removed)* | 825aeb9 | Merged into `functions` |
| `tvm_ffi.cpp.load_inline` (module path) | `tvm_ffi.cpp.extension` | c897e4c | Module file renamed; public API unchanged via `__init__.py` re-exports |
| `_build_ninja` | `build_ninja` | e6a654a | Renamed from private to public |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 83805ec | `2025-09-05-83805ec949227620d05e61358a4ecb4f0c931979.md` | `tvm_ffi.cpp.load_inline`, `tvm_ffi.utils.FileLock`, Ninja build, content cache |
| c897e4c | `2025-11-05-c897e4c9c2ed6f86cf5ef470a78e453eb040fb60.md` | File-based `build()`/`load()`, module rename to `extension.py`, `_build_impl` |
| 021d78d | `2025-11-04-021d78dbb8c5c5ba9ea07f8035eb9ce01a48bbc7.md` | FileLock re-entrance guard + tests |
| e6a654a | `2025-10-28-e6a654aaaad469ca455057821db01a995f312e2f.md` | `_build_ninja` -> `build_ninja` (public) |

| d49effdb | `2025-11-25-d49effdb22392363050e1f2d85cd4b31bf242cf0.md` | `embed_cubin` param on `load_inline`; `nvrtc.nvrtc_compile`; `embed_cubin` Python CLI tool |

(plus 5 supporting commits: 825aeb9 API rename, 2df07e5 Windows, 4ffbc88 macOS, 742b16e Tensor include, 4383b1a MSVC env)
