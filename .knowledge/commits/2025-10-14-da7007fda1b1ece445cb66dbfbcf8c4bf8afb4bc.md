---
author: "Junru Shao"
subject: "Split testing utilities into separate libtvm_ffi_testing.so library"
commit_shape: "standard"
commit_type: "chore"
scope:
  - "build"
  - "python-package"
  - "module-system"
  - "rust-bindings"
---
# Split testing utilities into separate libtvm_ffi_testing.so library
## TL;DR
- Moved `src/ffi/extra/testing.cc` to `src/ffi/testing/testing.cc` and built it as a separate `libtvm_ffi_testing.so` shared library, removing testing code from the main `libtvm_ffi.so`.
- Introduced `find_library_by_basename(base)` in `python/tvm_ffi/libinfo.py` -- a generic helper to locate platform-specific shared libraries by base name.
- `tvm_ffi.testing` is no longer auto-imported in `tvm_ffi.__init__`; it now lazy-loads `libtvm_ffi_testing` via `load_module` at import time.
- Added `TVMFFITestingDummyTarget()` C API symbol as a linkage verification target, tested from both C++ and Rust.

## Key Exports

**Functions** (Python -- `python/tvm_ffi/libinfo.py`):
- `find_library_by_basename(base: str) -> str` -- Locates a shared library across known directories using platform-specific naming (`.so`, `.dylib`, `.dll`). `find_libtvm_ffi()` now delegates to this.

**C API** (`src/ffi/testing/testing.cc`):
- `extern "C" int TVMFFITestingDummyTarget()` -- Returns 0; exists solely to verify linkage to the testing library.

**CMake targets** (`CMakeLists.txt`, `cmake/Utils/Library.cmake`):
- `tvm_ffi_testing` -- New shared library target built from `src/ffi/testing/testing.cc`, linked against `tvm_ffi_shared`.
- `tvm_ffi_add_target_from_obj` now also creates a `${target_name}_testing` target.

## Impact
- API: `tvm_ffi.testing` no longer auto-imported -- callers using `tvm_ffi.testing` via `import tvm_ffi` must now do explicit `from tvm_ffi import testing`.
- Behavioral: Testing global functions (`testing.echo`, `testing.add_one`, etc.) are now registered only when `libtvm_ffi_testing` is loaded, not at `libtvm_ffi` load time.
- Flags/config: none
- Data formats/schemas: none

## Design Elements
Design elements this commit consumes:
- **Module system** ([0013-module-system.md](../designs/0013-module-system.md)): `load_module` used to load `libtvm_ffi_testing` in Python.
- **Python package layout** ([0014-python-package.md](../designs/0014-python-package.md)): `libinfo.py` library discovery.
- **Rust bindings** ([0019-rust-bindings.md](../designs/0019-rust-bindings.md)): `tvm-ffi-sys` build script extended to link the new library.

Design elements this commit produces:
- **Separate testing library pattern**: Testing-only registrations (global functions, test object types) live in a dedicated shared library loaded on demand, keeping the core `libtvm_ffi` clean.
- **`find_library_by_basename`**: Generic library discovery function enabling any auxiliary shared library to be located.

## Usage Examples

```python
# Locating and loading the testing library (from python/tvm_ffi/testing.py)
from tvm_ffi import libinfo
from tvm_ffi.module import load_module

_LIBTVM_FFI_TESTING = load_module(libinfo.find_library_by_basename("tvm_ffi_testing"))
```

## Reflection

### Design docs to write or update
- `/Users/junrus/Projects/tvm-ffi-knowledge/.knowledge/designs/0014-python-package.md` -- Add `find_library_by_basename` to the library discovery section; document that `testing` is no longer auto-imported.

### ADRs to write or update
None

### Stale knowledge references
- `/Users/junrus/Projects/tvm-ffi-knowledge/.knowledge/designs/0014-python-package.md` -- May still describe `testing` as auto-imported from `tvm_ffi.__init__`.
