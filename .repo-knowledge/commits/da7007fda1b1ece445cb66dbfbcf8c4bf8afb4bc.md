---
sha: "da7007fda1b1ece445cb66dbfbcf8c4bf8afb4bc"
date: "2025-10-14T17:19:08-07:00"
author: "Junru Shao"
subject: "chore(build): Split `src/ffi/extra/testing.cc` into `libtvm_ffi_testing.so` (#114)"
nature: ["build"]
tags: ["build", "test"]
scope: ["CMakeLists.txt", "cmake", "python", "rust", "src", "tests"]
risk: "medium"
---

# da7007f — chore(build): Split testing.cc into libtvm_ffi_testing.so (#114)

## TL;DR
- Moves `src/ffi/extra/testing.cc` to `src/ffi/testing/testing.cc` and builds it as a separate shared library `libtvm_ffi_testing.so`.
- Testing functions are no longer bundled into the main `libtvm_ffi` shared library.
- Adds `TVMFFITestingDummyTarget()` C export as a library smoke-test symbol.
- Updates Python, Rust, and CMake to load/link the testing library on-demand.

## Why (intent / motivation)
- Bundling testing utilities into the production library is wasteful and adds binary size; splitting them allows end-users to install a clean library while tests still work.

## What changed (facts from diff)
- `CMakeLists.txt`: Removes `testing.cc` from `_tvm_ffi_extra_objs_sources`; adds new `tvm_ffi_testing` CMake target with its own compile flags, linking, and install rule.
- `cmake/Utils/Library.cmake`: Adds `${target_name}_testing` shared library target creation with MSVC config-specific output directories.
- `src/ffi/testing/testing.cc`: Renamed from `src/ffi/extra/testing.cc`; added `TVMFFITestingDummyTarget()` export.
- `python/tvm_ffi/testing.py`: Loads `libtvm_ffi_testing` at import time via `load_module(find_library_by_basename("tvm_ffi_testing"))`.
- `python/tvm_ffi/libinfo.py`: Refactored `find_libtvm_ffi` to delegate to new `find_library_by_basename(base)` helper.
- `rust/tvm-ffi-sys/build.rs`, `c_api.rs`: Link against `tvm_ffi_testing`; expose `TVMFFITestingDummyTarget`.
- `tests/cpp/CMakeLists.txt`: Links `tvm_ffi_tests` against `tvm_ffi_testing`.
- `src/ffi/backtrace_win.cc`: Adds ARM64 support to Windows stack walking.

## Public surface changes (if any)
- API: `TVMFFITestingDummyTarget()` new exported C symbol in testing library.
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `rust/tvm-ffi/tests/test_function.rs::test_function_dummpy_c_api`, `tests/cpp/test_function.cc::TEST(Func, DummyCFunc)`
- How to verify manually: Build with `TVM_FFI_BUILD_TESTS=ON`; run `ctest`
- CI impact: none

## Risk & rollout notes
- Risk level: medium — splits build artifact; any existing pipeline that expects testing functions in the main library will fail unless updated.
- Rollout/migration: Ensure `libtvm_ffi_testing.so` is installed and on `LD_LIBRARY_PATH` / RPATH for test workloads.
- Follow-ups: none

## Evidence
### Changed files
- `CMakeLists.txt` +18/-1 (M)
- `cmake/Utils/Library.cmake` +15/-0 (M)
- `python/tvm_ffi/__init__.py` +0/-2 (M)
- `python/tvm_ffi/libinfo.py` +43/-9 (M)
- `python/tvm_ffi/testing.py` +6/-0 (M)
- `rust/tvm-ffi-sys/build.rs` +1/-0 (M)
- `rust/tvm-ffi-sys/src/c_api.rs` +1/-0 (M)
- `rust/tvm-ffi/tests/test_function.rs` +6/-0 (M)
- `src/ffi/backtrace_win.cc` +13/-8 (M)
- `src/ffi/{extra => testing}/testing.cc` +2/-0 (R099)
- `tests/cpp/CMakeLists.txt` +1/-0 (M)
- `tests/cpp/test_function.cc` +7/-0 (M)

### Notable symbols / endpoints / configs touched
- `TVMFFITestingDummyTarget` (new C export)
- `find_library_by_basename` (new Python helper)
- `tvm_ffi_testing` CMake target (new)

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/da7007fda1b1ece445cb66dbfbcf8c4bf8afb4bc.md`
