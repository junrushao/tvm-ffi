---
author: "Junru Shao"
subject: "Split testing.cc into a separate libtvm_ffi_testing.so shared library"
commit_shape: "standard"
scope:
  - "build/cmake"
  - "python/libinfo"
  - "rust/tvm-ffi-sys"
  - "ffi/testing"
impact: "low"
abi_breaking: false
related_commits: []
---
# Split testing.cc into a separate libtvm_ffi_testing.so shared library
## TL;DR
- Moves `src/ffi/extra/testing.cc` to `src/ffi/testing/testing.cc` and builds it as a standalone `libtvm_ffi_testing.so` instead of embedding it in `libtvm_ffi.so`.
- Adds `find_library_by_basename()` to `libinfo.py`, generalizing library discovery beyond just `tvm_ffi`, and uses it to lazily load `libtvm_ffi_testing` in `testing.py`.
- Updates Rust `tvm-ffi-sys` to link `tvm_ffi_testing` and declares a `TVMFFITestingDummyTarget` extern for testing linkage. Adds Windows ARM64 backtrace support.

## Key Exports
**Functions (Python)**:
- `libinfo.find_library_by_basename(base: str) -> str` -- Generalized shared library finder that searches known directories for platform-appropriate filenames (`.so`, `.dylib`, `.dll`). `find_libtvm_ffi()` now delegates to `find_library_by_basename("tvm_ffi")`.

**Functions (C)**:
- `TVMFFITestingDummyTarget() -> int` -- `TVM_FFI_DLL_EXPORT` extern "C" function that returns 0. Serves as a linkage test target ensuring `libtvm_ffi_testing.so` is loadable.

**CMake targets**:
- `tvm_ffi_testing` -- New `SHARED` library target built from `src/ffi/testing/testing.cc`, linked against `tvm_ffi_shared`. Created by `tvm_ffi_add_target_from_obj` alongside the existing `_shared`/`_static` targets.

## Impact
- API: `libinfo.find_libtvm_ffi()` return value unchanged. New `find_library_by_basename()` is additive. `tvm_ffi.testing` is no longer imported at `tvm_ffi.__init__` (removed from `__all__`); consumers must import `tvm_ffi.testing` explicitly to trigger the library load.
- ABI: none. The testing global functions (e.g., `testing.echo`, `testing.add_one`) are still registered via the same mechanism, just from a different `.so`.
- Behavioral: Testing-only global functions are no longer available until `import tvm_ffi.testing` is called (or `load_module` is used to load `libtvm_ffi_testing`). This is intentional -- test utilities should not pollute the default global function registry.
- Flags/config: none.
- Data formats/schemas: none.

## Design Elements
Design elements this commit consumes:
- Module system load mechanism (`load_module`) to load `libtvm_ffi_testing.so` on demand (`.knowledge/designs/0013-module-system.md`)
- Library discovery via `libinfo.get_dll_directories()` (`.knowledge/designs/0015-python-packaging.md`)
- `TVM_FFI_DLL_EXPORT` macro for C ABI symbol export (`.knowledge/designs/c-abi.md`)
- CMake `tvm_ffi_add_target_from_obj` helper for creating library targets (`cmake/Utils/Library.cmake`)

Design elements this commit produces:
- Pattern for factoring optional/testing code into separate loadable shared libraries, loaded via `load_module` at import time
- `find_library_by_basename()` as a reusable primitive for locating any `libtvm_ffi_*` sibling library

## Usage Examples
Loading the testing library explicitly in Python:
```python
# Before this commit: testing symbols always available via tvm_ffi.testing
import tvm_ffi
tvm_ffi.testing.add_one(1)

# After this commit: must import testing explicitly to trigger library load
from tvm_ffi import testing
testing.add_one(1)
# Alternatively, the module load is triggered at import:
from tvm_ffi.testing import add_one
add_one(1)
```

Using `find_library_by_basename` to locate a custom sibling library:
```python
from tvm_ffi.libinfo import find_library_by_basename
path = find_library_by_basename("tvm_ffi_testing")
# Returns e.g., "/path/to/tvm_ffi/lib/libtvm_ffi_testing.dylib"
```

## Reflection

### Design docs to write or update
- `.knowledge/designs/0015-python-packaging.md`: Add `find_library_by_basename()` to the Key Classes table and document the `tvm_ffi_testing` library as a second bundled `.so` in the wheel layout.
- `.knowledge/designs/0013-module-system.md`: Note that `testing.cc` is now in a separate `libtvm_ffi_testing.so` loaded on demand, not part of `libtvm_ffi`.

### ADRs to write or update
None

### Stale knowledge references
- `.knowledge/designs/0015-python-packaging.md`: The wheel layout section only mentions `libtvm_ffi.so` under `tvm_ffi/lib/`; it should now also include `libtvm_ffi_testing.so` (or `libtvm_ffi_testing.dylib`).
- `.knowledge/designs/rust-bindings.md`: The build.rs section states it links `tvm_ffi` dylib only; it now also links `tvm_ffi_testing`.
