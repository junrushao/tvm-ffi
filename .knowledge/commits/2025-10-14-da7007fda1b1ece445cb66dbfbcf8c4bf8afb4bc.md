---
author: "da7007fda1b1"
subject: "Split testing utilities into a separate `libtvm_ffi_testing.so` shared library"
commit_shape: "standard"
commit_type: "chore"
secondary_commit_type: "feature"
potential_duplicate: ""
has_design_updates: true
scope:
  - "build"
  - "python/tvm_ffi"
  - "rust"
  - "src/ffi/testing"
---
# Split testing utilities into a separate `libtvm_ffi_testing.so` shared library

## TL;DR
- `src/ffi/extra/testing.cc` moved to `src/ffi/testing/testing.cc` and now compiled into a separate shared lib `libtvm_ffi_testing` (not included in the main `libtvm_ffi`).
- `python/tvm_ffi/libinfo.py` gains `find_library_by_basename(base)` — a generalized lib-finder used by both `find_libtvm_ffi()` and the new testing loader.
- `python/tvm_ffi/testing.py` now eagerly loads `libtvm_ffi_testing` on import; `testing` module removed from top-level `tvm_ffi.__init__` exports.

## Key Exports

```python
# python/tvm_ffi/libinfo.py
def find_library_by_basename(base: str) -> str:
    """Locate a shared library by base name across known DLL directories.
    Searches platform-specific candidate names: lib<base>.so (Linux),
    lib<base>.dylib / lib<base>.so (macOS), <base>.dll (Windows).
    Raises RuntimeError if not found.
    # Interacts with: get_dll_directories(), find_libtvm_ffi() (delegates to this)
    # Invariant: base must be the bare name without 'lib' prefix or extension
    """
    ...

def find_libtvm_ffi() -> str:
    # Old: inlined platform-switch logic
    # New: delegates to find_library_by_basename("tvm_ffi")
    return find_library_by_basename("tvm_ffi")

# python/tvm_ffi/testing.py (module-level, executed on import)
_LIBTVM_FFI_TESTING = load_module(libinfo.find_library_by_basename("tvm_ffi_testing"))
# Interacts with: load_module (0011-module-system), find_library_by_basename

# C ABI (src/ffi/testing/testing.cc)
extern "C" int TVMFFITestingDummyTarget() -> int  # returns 0; canary symbol for link verification
# Interacts with: tvm-ffi-sys/src/c_api.rs TVMFFITestingDummyTarget declaration

# CMake target (cmake/Utils/Library.cmake)
# tvm_ffi_add_target_from_obj(target_name, obj_target_name) now creates
# both `${target_name}_shared` and `${target_name}_testing` SHARED targets
# Invariant: tvm_ffi_testing links against tvm_ffi_shared (not tvm_ffi_static)
```

## Impact
- API: `find_libtvm_ffi()` signature unchanged; `find_library_by_basename(base)` is new public API in `libinfo.py`. `tvm_ffi.testing` removed from `tvm_ffi.__all__` — callers that imported `tvm_ffi.testing` via `tvm_ffi` namespace must now import directly.
- Behavioral: Importing `tvm_ffi.testing` now eagerly loads `libtvm_ffi_testing.so` at import time (was loaded lazily as part of main lib).
- Flags/config: CMake install now ships `libtvm_ffi_testing` alongside `libtvm_ffi_shared`.
- Data formats/schemas: `TVMFFITestingDummyTarget` added to Rust `c_api.rs` as `extern "C"` declaration; `cargo:rustc-link-lib=dylib=tvm_ffi_testing` added to `build.rs`.

## Design Elements
Design elements this commit consumes:
- `0011-module-system`: `load_module()` used in `testing.py` to load the new lib
- `0013-python-package`: `libinfo.py` is part of the Python package; `get_dll_directories()` consumed by the new `find_library_by_basename`
- `0018-rust-binding`: `tvm-ffi-sys/build.rs` and `c_api.rs` updated to link and declare `TVMFFITestingDummyTarget`
- `0004-function-system`: Testing globals registered via `TVM_FFI_STATIC_INIT_BLOCK` in `testing.cc` still use the packed function / global registry infrastructure

Design elements this commit produces:
- **`find_library_by_basename(base)`** — generalized platform-aware library locator in `libinfo.py`; new reusable primitive for finding any TVM FFI companion lib by base name
- **`libtvm_ffi_testing` build target** — a separate CMake shared library that holds testing-only registered functions, preventing them from leaking into production builds

## Usage Examples

```python
# Locating any companion shared library by base name (new pattern):
from tvm_ffi import libinfo
path = libinfo.find_library_by_basename("tvm_ffi_testing")
# e.g. "/path/to/lib/libtvm_ffi_testing.so"

# In tvm_ffi/testing.py (module-level eager load):
from . import libinfo
from .module import load_module
_LIBTVM_FFI_TESTING = load_module(libinfo.find_library_by_basename("tvm_ffi_testing"))
# All testing.* registered globals are now available after this import
```

```rust
// Rust: verifying the testing library link (rust/tvm-ffi/tests/test_function.rs)
#[test]
fn test_function_dummpy_c_api() {
    let ret = unsafe { tvm_ffi_sys::TVMFFITestingDummyTarget() };
    assert_eq!(ret, 0);
}
```

## Reflection

### Design docs / ADRs to write or update
- `/Users/junrus/Projects/tvm-ffi-knowledge/.knowledge/design-records/0013-python-package.md`: Add note about `find_library_by_basename(base)` as the generalized lib-locator pattern; note that `tvm_ffi.testing` is no longer in `__all__` and loads its companion `.so` eagerly on import.
- `/Users/junrus/Projects/tvm-ffi-knowledge/.knowledge/design-records/0018-rust-binding.md`: Add note that `tvm_ffi_testing` is a separately linked dylib required for test builds; CI must have `libtvm_ffi_testing` available.
- Consider a new `0019-testing-lib.md` design record: document the `libtvm_ffi_testing` separation convention — testing globals stay out of production lib, loaded on demand via `load_module(find_library_by_basename("tvm_ffi_testing"))`.

### Stale knowledge references
- `0013-python-package.md` currently does not mention `find_library_by_basename` or the eager load pattern in `testing.py` — low staleness risk (additive change, existing text remains accurate).
- `0018-rust-binding.md` does not mention the `tvm_ffi_testing` dylib requirement — low risk for tests, but could confuse CI setup docs.
