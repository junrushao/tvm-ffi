---
scope:
  - "0018-cuda-extra-utilities"
  - "0011-module-system"
---
# CUBIN Embedding via Symbol Injection (ld + objcopy)

**TL;DR**: Embed precompiled CUBIN data into object files using `ld -r -b binary` + `objcopy` symbol renaming, producing `__tvm_ffi__cubin_<name>` / `__tvm_ffi__cubin_<name>_end` symbols consumable by the `TVM_FFI_EMBED_CUBIN` macro.

## Context

Kernel libraries need to embed precompiled CUBIN (GPU binary) data into shared libraries so that `CubinModule` can load kernels from memory without runtime file I/O. The embedding must work across CMake, Python CLI, and JIT (`load_inline`) build pipelines with a uniform C++ consumption API.

Usecases:
- JIT workflow: `nvrtc_compile()` produces CUBIN bytes -> `load_inline(embed_cubin={"name": bytes})` embeds and links
- AOT workflow: CMake `add_tvm_ffi_cubin`/`add_tvm_ffi_fatbin` + `tvm_ffi_embed_bin_into` for pre-compiled kernels (replaces `tvm_ffi_generate_cubin` + `tvm_ffi_embed_cubin`, b16f11f6)
- CLI workflow: `python -m tvm_ffi.utils.embed_cubin` for standalone toolchain integration

Design Decisions:
- **Use `ld -r -b binary` to convert raw CUBIN bytes into a relocatable object**, then `objcopy --redefine-sym` to rename the auto-generated linker symbols (`_binary_embedded_<name>_cubin_start` / `_end`) to the canonical `__tvm_ffi__cubin_<name>` / `__tvm_ffi__cubin_<name>_end` names.
- **Final `objcopy --localize-symbols`** prevents cross-object symbol conflicts when multiple CUBINs are linked into the same shared library.
- **Three-pipeline convergence**: CMake, Python CLI, and JIT all produce object files with identical symbol naming, so the same C++ macros (`TVM_FFI_EMBED_CUBIN`) work regardless of which pipeline embedded the data.
- **Unix-only**: This approach depends on GNU binutils (`ld`, `objcopy`). Windows is not supported for CUBIN embedding.

## Implementation Notes
- Pipeline: `ld -r -b binary cubin.cubin -o cubin_raw.o` -> `objcopy --add-section .note.GNU-stack` -> `objcopy --redefine-sym` -> `ld -r original.o cubin_renamed.o -o merged.o` -> `objcopy --localize-symbols`
- Symbol convention follows [ADR-0010](../ADRs/0010-ffi-symbol-prefix-convention.md): `__tvm_ffi__cubin_<name>` uses the double-underscore internal namespace
- The `_end` symbol points one byte past the last byte of CUBIN data, enabling size computation: `size = __tvm_ffi__cubin_<name>_end - __tvm_ffi__cubin_<name>`
- `CubinModule` constructor accepts `const char*` pointing directly to the embedded data -- zero-copy from the binary segment

**Alternatives rejected:**
- **xxd-generated C arrays**: Converts CUBIN to `unsigned char[]` in a `.cc` file. Simpler and cross-platform, but large CUBINs (>100KB) significantly slow compilation and bloat intermediate `.o` files. Not viable for multi-MB production kernels.
- **CUDA fatbinary (`--fatbin`)**: Native CUDA embedding format. Requires NVCC at build time, not just runtime. Tightly coupled to the CUDA build system, incompatible with non-CUDA host compilers (plain `g++`/`clang++`).
- **`incbin` assembler directive**: Inline assembly embedding. Portable across GCC/Clang but not MSVC. Requires careful section placement and doesn't integrate with build system dependency tracking. Less debuggable than the ld+objcopy approach.

## Related Design Docs
- [0018-cuda-extra-utilities.md](../designs/0018-cuda-extra-utilities.md) -- CubinModule/CubinKernel consuming the embedded data
- [0011-module-system.md](../designs/0011-module-system.md) -- `load_inline(embed_cubin=...)` JIT pipeline
- [ADR 0010](../ADRs/0010-ffi-symbol-prefix-convention.md) -- `__tvm_ffi__cubin_<name>` naming convention

### Evidence
- `commits/2025-11-25-d49effdb22392363050e1f2d85cd4b31bf242cf0.md` (d49effd)
