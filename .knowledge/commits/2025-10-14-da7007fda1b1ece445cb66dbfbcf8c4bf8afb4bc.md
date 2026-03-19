---
author: "Junru Shao <junrushao@apache.org>"
subject: "Split testing utilities into separate libtvm_ffi_testing shared library"
commit_shape: "refactor"
commit_type: "chore"
potential_duplicate: ""
has_design_updates: true
scope:
  - "build/cmake"
  - "python/tvm_ffi/libinfo"
  - "python/tvm_ffi/testing"
  - "rust/tvm-ffi-sys"
  - "src/ffi/testing"
  - "src/ffi/backtrace_win"
---
# Split testing utilities into separate libtvm_ffi_testing shared library
## TL;DR
- Moved `src/ffi/extra/testing.cc` to `src/ffi/testing/testing.cc` and built it as a separate `libtvm_ffi_testing.so` shared library, removing testing code from `libtvm_ffi.so`.
- Python `tvm_ffi.testing` now loads `libtvm_ffi_testing` on-demand via `load_module`, and is no longer auto-imported in `tvm_ffi.__init__`.
- Generalized `find_libtvm_ffi()` into `find_library_by_basename(base)` for locating any companion shared library by base name.

## Key Exports

```python
# --- libinfo.py: new generic library finder ---
def find_library_by_basename(base: str) -> str:
    """Find a shared library by base name across known directories.
    # Interacts with: get_dll_directories(), platform-specific naming
    # Invariant: raises RuntimeError if library not found
    # Extension: works for any companion library (e.g., "tvm_ffi_testing")
    """
    ...

def find_libtvm_ffi() -> str:
    """Find libtvm_ffi. Now delegates to find_library_by_basename('tvm_ffi')."""
    ...

# --- testing.py: on-demand library loading ---
_LIBTVM_FFI_TESTING: Module = load_module(
    libinfo.find_library_by_basename("tvm_ffi_testing")
)
# Invariant: loaded at module import time (not at tvm_ffi.__init__)
# Interacts with: Module system (0011), load_module

# --- C ABI: link validation symbol ---
# extern "C" TVM_FFI_DLL_EXPORT int TVMFFITestingDummyTarget();
#   Returns 0. Used by C++ and Rust tests to verify libtvm_ffi_testing is linked.

# --- Rust: tvm-ffi-sys/c_api.rs ---
# pub fn TVMFFITestingDummyTarget() -> i32;
# Linked via: cargo:rustc-link-lib=dylib=tvm_ffi_testing (build.rs)

# --- CMake: new target ---
# tvm_ffi_testing: SHARED library target
#   Sources: src/ffi/testing/testing.cc
#   Links: tvm_ffi_shared (private), tvm_ffi_header (public)
#   Output: ${CMAKE_BINARY_DIR}/lib/
#   Installed alongside tvm_ffi_shared

# --- tvm_ffi.__init__: testing no longer auto-imported ---
# Removed: from . import testing
# Removed: "testing" from __all__
```

## Impact
- API: `find_library_by_basename` is a new public API in `tvm_ffi.libinfo`. `tvm_ffi.testing` is no longer auto-imported -- callers must explicitly `from tvm_ffi import testing` or `import tvm_ffi.testing`.
- Behavioral: Testing-registered global functions (e.g., `testing.echo`, `testing.add_one`) are only available after `tvm_ffi.testing` is imported (which triggers loading `libtvm_ffi_testing`).
- Flags/config: none
- Data formats/schemas: none

## Design Elements
Design elements this commit consumes:
- Module system load_module pattern ([0011-module-system.md](/Users/junrus/Projects/tvm-ffi-knowledge/.knowledge/design-records/0011-module-system.md)) -- used to load `libtvm_ffi_testing` on-demand
- Python libinfo library discovery ([0012-python-bindings.md](/Users/junrus/Projects/tvm-ffi-knowledge/.knowledge/design-records/0012-python-bindings.md)) -- `find_libtvm_ffi` refactored
- Rust build.rs linkage pattern ([0014-rust-bindings.md](/Users/junrus/Projects/tvm-ffi-knowledge/.knowledge/design-records/0014-rust-bindings.md)) -- extended with `tvm_ffi_testing` link
- CMake Library.cmake target creation utility -- extended with `_testing` target

Design elements this commit produces:
- **Companion library pattern**: testing (and potentially other) functionality split into separate shared libraries loaded on-demand, keeping the main `libtvm_ffi` lean
- **Generic library finder**: `find_library_by_basename` enables discovering any companion library by base name
- **Link validation symbol**: `TVMFFITestingDummyTarget` as a minimal extern C symbol for verifying library linkage in tests
- **Drive-by: Windows ARM64 backtrace support** in `backtrace_win.cc`

## Usage Examples

Loading testing utilities explicitly:
```python
# Before this commit: testing was auto-imported
import tvm_ffi
tvm_ffi.testing.add_one(1)  # worked immediately

# After this commit: explicit import required
from tvm_ffi import testing  # triggers load_module("libtvm_ffi_testing")
testing.add_one(1)           # testing functions now available
```

Using the generic library finder:
```python
from tvm_ffi import libinfo

# Find any companion library by base name
path = libinfo.find_library_by_basename("tvm_ffi_testing")
# Returns e.g., "/path/to/lib/libtvm_ffi_testing.dylib"
```

C++ test verifying link to testing library:
```cpp
extern "C" TVM_FFI_DLL int TVMFFITestingDummyTarget();

TEST(Func, DummyCFunc) {
  int value = TVMFFITestingDummyTarget();
  EXPECT_EQ(value, 0);
}
```

## Reflection

### Design docs to write or update
- Update `0012-python-bindings.md` to document `find_library_by_basename` as a public API and the companion library loading pattern.
- Update `0014-rust-bindings.md` to note `tvm_ffi_testing` linkage in build.rs.
- Update `0011-module-system.md` to reference the companion library on-demand loading pattern as a usage example.

### Stale knowledge references
None -- no symbols were renamed or removed in existing knowledge files. The `testing.py` module still exists, it's just no longer auto-imported.
