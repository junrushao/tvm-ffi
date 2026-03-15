---
scope:
  - "0014-python-package"
---
# ADR-0024: Use importlib.metadata RECORD for DSO Discovery

**TL;DR**: Replaces directory-scanning DSO discovery with `importlib.metadata.distribution(package).read_text("RECORD")` as the primary mechanism for locating shared libraries in pip-installed packages.

## Context

Library discovery in `tvm_ffi` previously used `find_library_by_basename()` which scanned a list of directories (package-local `lib/`, source-tree `build/lib/`, `LD_LIBRARY_PATH`). This approach had several problems:
- For pip-installed packages, the shared library might be in an unexpected location (e.g., platform-specific subdirectories in virtual environments).
- The `get_dll_directories()` function was fragile -- inaccessible paths on `PATH`/`LD_LIBRARY_PATH` could crash the import.
- Downstream extension packages had to replicate the same platform-specific discovery logic (25+ lines of boilerplate).

Usecases:
- `tvm_ffi` itself loading `libtvm_ffi.so`/`.dylib`/`.dll` at import time
- Downstream extension packages loading their own DSOs (e.g., `my_ffi_extension.so`)
- Windows DLL directory registration for dependent libraries

Design Decisions:
- Use `importlib.metadata.distribution(package).read_text("RECORD")` as the primary discovery mechanism. The RECORD file is part of PEP 376 and lists all files in the installed distribution, making it the most reliable source for finding installed shared libraries.
- Provide `load_lib_ctypes(package, target_name, mode) -> ctypes.CDLL` as the public API for low-level library loading, and `load_lib_module(package, target_name, keep_module_alive=True) -> Module` for FFI module loading.
- `base.py` is deleted; `tvm_ffi.LIB = libinfo.load_lib_ctypes("apache-tvm-ffi", "tvm_ffi", "RTLD_GLOBAL")` in `__init__.py` replaces it.
- Directory scanning is retained as a fallback for development/editable installs where RECORD may not exist.
- `_find_library_by_basename(package, target_name)` handles platform-specific filename patterns (`.so`, `.dylib`, `.dll`, `lib` prefix) transparently.

## Implementation Notes
- `load_lib_ctypes` discovers the library path via `_find_library_by_basename`, then loads via `ctypes.CDLL(path, mode)`. On Windows, it also calls `os.add_dll_directory` for the library's parent directory.
- `load_lib_module` combines `_find_library_by_basename` with `load_module(path, keep_module_alive)`, providing a one-liner for downstream packages.
- `_resolve_and_validate(paths, cond)` centralizes all path resolution with `try/except OSError` safety, replacing scattered `path.is_dir()` patterns.
- Public symbols removed: `split_env_var`, `get_dll_directories`, `find_library_by_basename`. `tvm_ffi.base` module deleted entirely; `tvm_ffi.LIB` replaces `tvm_ffi.base._LIB`.
- Evidence: 6887892 (initial refactor), 3cfc5c5 (find_source_path fix), f255650 (load_lib_module)

## Related Design Docs
- [0014-python-package.md](../designs/0014-python-package.md) -- Python package layout and module import flow
- [0013-module-system.md](../designs/0013-module-system.md) -- Module loading with keep_module_alive
