---
scope:
  - "0016-packaging-and-build"
---
# CMake Cross-Compilation Toggles for Threads and DL

**TL;DR**: Two new CMake options (`TVM_FFI_USE_THREADS` and `TVM_FFI_USE_DL_LIBS`) were added to allow building TVM FFI on cross-compilation targets that lack pthreads or dlopen. Both default to ON, preserving existing behavior.

## Context

Cross-compilation targets (bare-metal ARM, WASM, embedded Linux with minimal sysroot) may not have `pthreads` or `libdl` available. Previously, `find_package(Threads REQUIRED)` was unconditional and would fail the CMake configure step on such targets, even though the core FFI library does not strictly require either at link time (it uses `std::atomic` rather than mutex for ref-counting, and `dlopen` is only used by the extra-tier module system).

Usecases:
- Cross-compiling TVM FFI as a static library for an embedded RISC-V target that has no pthreads implementation.
- Building a minimal WASM version of TVM FFI where dlopen is not available.
- Using TVM FFI's source bundle (shipped in the wheel) for bare-metal targets that consume only the header-only portion or a subset of the source.

Design Decisions:
- Add `option(TVM_FFI_USE_THREADS "Link against threads in shared lib" ON)`. When ON, `find_package(Threads REQUIRED)` and `target_link_libraries(... Threads::Threads)` are executed. When OFF, threading library is skipped entirely.
- Add `option(TVM_FFI_USE_DL_LIBS "Link against dl libs in shared lib" ON)`. When ON and the extra CXX API is enabled and `CMAKE_DL_LIBS` is non-empty, `target_link_libraries(... ${CMAKE_DL_LIBS})` is executed. When OFF, dl linking is skipped regardless of `CMAKE_DL_LIBS`.
- The evolution was in three steps: first Threads was made optional with graceful fallback (`0d157dc`), then an explicit option was added (`3b4a532`), then dl was made similarly toggleable (`dcd07cf`).

**Alternatives considered:**

1. **Auto-detect and silently skip**: Use `find_package(Threads)` (without REQUIRED) and only link if found.
   - Pro: No new options to document.
   - Con: Confusing failure modes: a broken sysroot might accidentally skip Threads leading to link errors elsewhere. The intermediate commit `0d157dc` used this approach but was quickly replaced by the explicit option in `3b4a532`.

2. **CMake toolchain file responsibility**: Leave it to the cross-compilation toolchain file to provide Threads/dl stubs.
   - Pro: No changes to TVM FFI CMakeLists.
   - Con: Requires every cross-compilation user to create a toolchain file with stubs. The toggle approach is simpler and self-documenting.

## Implementation Notes

- `TVM_FFI_USE_THREADS=ON` (default): `find_package(Threads REQUIRED)` followed by linking both shared and static targets.
- `TVM_FFI_USE_THREADS=OFF`: Entire Threads block is skipped. Code must not use `std::thread` or `pthread_*` directly in the core library.
- `TVM_FFI_USE_DL_LIBS=ON` (default): Links `${CMAKE_DL_LIBS}` when extra CXX API is enabled.
- `TVM_FFI_USE_DL_LIBS=OFF`: Skips dl linking. Module loading via `dlopen` will not be available.
- Both options are in the "Always" scope (not root-only), so sub-project consumers via `add_subdirectory` also respect them.

## Related Design Docs

- [`.knowledge/designs/0016-packaging-and-build.md`](../designs/0016-packaging-and-build.md)
