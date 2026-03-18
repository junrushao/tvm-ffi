---
author: "unknown"
subject: "Split testing utilities into separate libtvm_ffi_testing.so shared library"
commit_shape: "standard"
commit_type: "chore"
potential_duplicate: ""
scope:
  - "packaging"
  - "module-system"
  - "rust-bindings"
---
# Split testing utilities into separate libtvm_ffi_testing.so shared library

## TL;DR
- Moves `src/ffi/extra/testing.cc` to `src/ffi/testing/testing.cc` and builds it as a separate `libtvm_ffi_testing.so` shared library, removing test-only code from the production `libtvm_ffi` library.
- Introduces `find_library_by_basename()` in `libinfo.py` (refactored from `find_libtvm_ffi()`), a generic helper for locating platform-specific shared libraries by base name.
- Python `tvm_ffi.testing` module is removed from eager `__init__.py` imports; it now loads `libtvm_ffi_testing` on-demand via `load_module()` at first `import tvm_ffi.testing`.

## Key Exports

```python
# === libinfo.py: new generic library finder ===

def find_library_by_basename(base: str) -> str:
    """Find a shared library by base name across known directories.
    Searches get_dll_directories() for platform-specific variants:
      Linux:  lib{base}.so
      macOS:  lib{base}.dylib, lib{base}.so
      Windows: {base}.dll
    """
    # Interacts with: get_dll_directories() (same search paths as find_libtvm_ffi)
    # Interacts with: testing.py (first consumer, loads "tvm_ffi_testing")
    # Extension: any new companion shared library can be found via this function
    # Invariant: raises RuntimeError if library not found in any candidate directory
    ...

def find_libtvm_ffi() -> str:
    """Now a thin wrapper: return find_library_by_basename("tvm_ffi")."""
    # Interacts with: find_library_by_basename (delegate)
    ...

# === testing.py: load testing library on import ===

# Module-level side effect at import time:
_LIBTVM_FFI_TESTING: Module = load_module(find_library_by_basename("tvm_ffi_testing"))
# Interacts with: Module::LoadFromFile -> DSOLibrary (0011-module-system)
# Interacts with: find_library_by_basename (0013-packaging)
# Invariant: all testing.* global functions are registered after this load

# === C ABI: link verification target ===

def TVMFFITestingDummyTarget() -> int:
    """No-op C ABI function exported from libtvm_ffi_testing.
    Returns 0. Used solely to verify that libtvm_ffi_testing links correctly."""
    # Interacts with: Rust tvm-ffi-sys (extern "C" declaration)
    # Interacts with: C++ test_function.cc (DummyCFunc test)
    ...

# === CMake: new tvm_ffi_testing target ===
# tvm_ffi_add_target_from_obj() now also creates ${target_name}_testing
# as a SHARED library with matching output directory properties.
# tvm_ffi_testing links against tvm_ffi_shared (runtime dependency).
# install(TARGETS tvm_ffi_testing DESTINATION lib) -- shipped alongside tvm_ffi.
```

## Impact
- API: `find_library_by_basename()` is a new public Python API in `libinfo.py`. `find_libtvm_ffi()` contract is unchanged (now delegates). `tvm_ffi.testing` is no longer importable via `tvm_ffi.testing` attribute on the top-level package (removed from `__init__.py`); must use `from tvm_ffi import testing` or `import tvm_ffi.testing` directly.
- Behavioral: Test-only functions (`testing.echo`, `testing.add_one`, `testing.make_unregistered_object`, etc.) are no longer registered at `libtvm_ffi` load time. They only become available after `libtvm_ffi_testing` is loaded (either via `import tvm_ffi.testing` or explicit `load_module`).
- Flags/config: None.
- Data formats/schemas: None.

## Design Elements
Design elements this commit consumes:
- **Module system** ([0011-module-system](../designs/0011-module-system.md)): Uses `load_module()` / `Module::LoadFromFile` to dynamically load the testing library. The testing module becomes a standard dynamically-loaded library module.
- **Packaging / library discovery** ([0013-packaging](../designs/0013-packaging.md)): Refactors `find_libtvm_ffi()` into a generic `find_library_by_basename()`, consuming the same `get_dll_directories()` search paths.
- **CMake build infrastructure** (`cmake/Utils/Library.cmake`): The `tvm_ffi_add_target_from_obj` function is extended to produce a `_testing` shared library target.

Design elements this commit produces:
- **`find_library_by_basename()`**: Generic library discovery by base name, enabling any companion `.so`/`.dylib`/`.dll` to be located using the same search paths as `libtvm_ffi`. First produced extension point for the packaging library discovery subsystem.
- **`tvm_ffi_testing` CMake target**: A separate shared library target for test-only code, establishing the pattern of splitting optional/test code into companion libraries that link against `tvm_ffi_shared`.
- **`TVMFFITestingDummyTarget()`**: C ABI entry point for link verification of companion libraries. Establishes the convention of a no-op dummy target function for validating that a companion library links correctly across C++, Python, and Rust.

## Usage Examples

Loading testing utilities (after this commit):
```python
# Explicit import triggers loading of libtvm_ffi_testing
from tvm_ffi.testing import create_object, add_one

obj = create_object("testing.TestObjectBase", v_i64=1, v_f64=2.0, v_str="hello")
assert add_one(1) == 2
```

C++ link verification test:
```cpp
extern "C" TVM_FFI_DLL int TVMFFITestingDummyTarget();

TEST(Func, DummyCFunc) {
  int value = TVMFFITestingDummyTarget();
  EXPECT_EQ(value, 0);
}
```

Rust link verification test:
```rust
#[test]
fn test_function_dummpy_c_api() {
    let ret = unsafe { tvm_ffi_sys::TVMFFITestingDummyTarget() };
    assert_eq(ret, 0);
}
```

## Reflection

### Design docs to write or update
- `0013-packaging.md`: Add `find_library_by_basename()` to the Key Classes section (currently only documents `find_libtvm_ffi()`). 1-line: generic library finder enabling companion library discovery.
- `0013-packaging.md`: Document the companion library pattern (`tvm_ffi_testing` as first instance of a separately-loadable test library). A Mermaid flowchart showing the tvm_ffi / tvm_ffi_testing build relationship would help.

### ADRs to write or update
None.

### Stale knowledge references
- `commits/2025-09-01-c695f5f16ab6e54c729fd6338361b555c7daf8b7.md`: References `src/ffi/extra/testing.cc` (old path, now `src/ffi/testing/testing.cc`). Severity: `low`.
- `commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md`: References `src/ffi/extra/testing.cc` as destination of a prior rename. Severity: `low`.
- `commits/2025-09-24-daeb235a29c576d8702d447fa5f4773170bb1e8f.md`: References `src/ffi/extra/testing.cc`. Severity: `low`.
- `commits/2025-09-25-bdad2184551353e49a9b6882f7b9a75a258862bb.md`: References `src/ffi/extra/testing.cc`. Severity: `low`.
- `commits/2025-10-08-dd4fb0ae92ab69b1cc0280e812a18a58273d4ae6.md`: References `src/ffi/extra/testing.cc`. Severity: `low`.
- `designs/0013-packaging.md`: Documents `find_libtvm_ffi()` without the new `find_library_by_basename()` delegate. Severity: `low` (existing behavior is unchanged, just missing the new API).
