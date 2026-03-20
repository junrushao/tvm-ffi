---
author: "Junru Shao"
subject: "Split testing utilities into separate libtvm_ffi_testing shared library"
commit_shape: "ci-infra"
commit_type: "chore"
potential_duplicate: ""
has_design_updates: true
scope:
  - "build/cmake"
  - "python/libinfo"
  - "rust/ffi-sys"
  - "ffi/testing"
---
# Split testing utilities into separate libtvm_ffi_testing shared library
## TL;DR
- `src/ffi/extra/testing.cc` moved to `src/ffi/testing/testing.cc` and compiled into a new standalone `libtvm_ffi_testing.so` shared library, no longer bundled into `libtvm_ffi.so`.
- `python/tvm_ffi/libinfo.py` gains `find_library_by_basename(base)`, a generic library discovery function; `find_libtvm_ffi()` now delegates to it. `tvm_ffi.testing` is removed from auto-import in `__init__.py` and instead eagerly loads `libtvm_ffi_testing` on first import.
- Rust `tvm-ffi-sys` links `dylib=tvm_ffi_testing` and declares `TVMFFITestingDummyTarget()` as a link-check sentinel. Secondary: Windows ARM64 backtrace support added.

## Key Exports

```python
# --- python/tvm_ffi/libinfo.py ---

def find_library_by_basename(base: str) -> str:
    """Find a shared library by base name across known directories.
    # Interacts with: get_dll_directories() for candidate paths
    # Invariant: raises RuntimeError if no matching library found
    # Extension: use for any co-packaged library (e.g., "tvm_ffi_testing", future addons)
    """
    ...

def find_libtvm_ffi() -> str:
    """Find libtvm_ffi. Now delegates to find_library_by_basename('tvm_ffi')."""
    ...

# --- python/tvm_ffi/testing.py (load-time side effect) ---
_LIBTVM_FFI_TESTING: Module  # = load_module(find_library_by_basename("tvm_ffi_testing"))
# Interacts with: load_module (0011-ffi-module-system), find_library_by_basename (above)
# Invariant: libtvm_ffi_testing must be present at import time

# --- C/Rust ABI (src/ffi/testing/testing.cc) ---
# extern "C" TVM_FFI_DLL_EXPORT int TVMFFITestingDummyTarget();
# Returns 0. Link-check sentinel to verify libtvm_ffi_testing is loaded.
# Interacts with: Rust c_api.rs, C++ test_function.cc

# --- CMake (cmake/Utils/Library.cmake) ---
# tvm_ffi_add_target_from_obj now creates ${target_name}_testing alongside _shared/_static
# Interacts with: CMakeLists.txt top-level target configuration
```

## Impact
- API: `tvm_ffi.testing` removed from `tvm_ffi.__init__.__all__` and auto-import. Callers using `tvm_ffi.testing.xxx` must now use `from tvm_ffi import testing` or `from tvm_ffi.testing import xxx`. Loading `tvm_ffi.testing` now requires `libtvm_ffi_testing` to be installed.
- Behavioral: Testing-registered FFI functions (e.g., `testing.echo`, `testing.add_one`) are no longer loaded at `import tvm_ffi` time; they load only when `tvm_ffi.testing` is explicitly imported.
- Flags/config: none
- Data formats/schemas: none

## Design Elements
Design elements this commit consumes:
- Module loading system (`load_module`) -- [0011-ffi-module-system](../design-records/0011-ffi-module-system.md)
- Library discovery (`get_dll_directories`, `find_libtvm_ffi`) -- [0012-ffi-python-package](../design-records/0012-ffi-python-package.md)
- CMake packaging and install layout -- [0013-ffi-packaging-and-distribution](../design-records/0013-ffi-packaging-and-distribution.md)
- Rust FFI sys crate build/link mechanism -- [0017-ffi-rust-bindings](../design-records/0017-ffi-rust-bindings.md)
- `TVM_FFI_DLL_EXPORT` macro from C ABI -- [0001-ffi-c-abi](../design-records/0001-ffi-c-abi.md)

Design elements this commit produces:
- `find_library_by_basename(base)` -- generic library discovery function (new public API in `libinfo.py`)
- `libtvm_ffi_testing` build target and install target -- separate shared library for testing utilities
- `TVMFFITestingDummyTarget()` -- C ABI link-check sentinel for testing library
- CMake `${target_name}_testing` auto-creation pattern in `tvm_ffi_add_target_from_obj`

## Usage Examples
N/A -- infrastructure change.

## Reflection

### Design docs / ADRs to write or update
- `0012-ffi-python-package.md`: Update library discovery section to document `find_library_by_basename()` as the generic entry point, with `find_libtvm_ffi()` as a convenience wrapper. Note that `tvm_ffi.testing` is no longer auto-imported.
- `0013-ffi-packaging-and-distribution.md`: Document the separate `libtvm_ffi_testing` library as part of the install layout (two .so files shipped: `libtvm_ffi` + `libtvm_ffi_testing`).

### Stale knowledge references
- `0015-ffi-python-type-system.md` line 230: `tvm_ffi.testing.make_unregistered_object()` -- after this commit, `testing` is not auto-imported; needs `from tvm_ffi import testing` first. Severity: low.
- `commits/2025-09-26-9b3be5d12df257bef9a75e46ae8086b55b8cad49.md` line 30: references `src/ffi/extra/testing.cc` -- file moved to `src/ffi/testing/testing.cc`. Severity: low.
- Multiple commit ledgers reference `tvm_ffi.testing.xxx` as a directly accessible attribute. After this commit, explicit import is required. Severity: low (commit ledgers are historical records).
