---
adr: "0030"
title: "Support Free-Threaded Python (PEP 703, Py_GIL_DISABLED)"
status: "accepted"
date: "2025-10-10"
deciders:
  - "Tianqi Chen"
consulted:
  - "Junru Shao"
informed:
  - "TVM FFI contributors"
tags:
  - "architecture"
  - "python"
  - "threading"
source_commits:
  - "b64b46f32e845b650850d73a5828a2d3f07d3406"
source_ledgers:
  - ".memory/commits/2025-10-10-b64b46f3.md"
---

# ADR-0030: Support Free-Threaded Python (PEP 703, Py_GIL_DISABLED)

## TL;DR
- The Cython binding layer now supports free-threaded Python (no GIL) by replacing Cython's `with gil` pattern with a C++-level GIL acquisition helper (`TVMFFIPyWithGILIfNotFreeThreaded`) that is a no-op under `Py_GIL_DISABLED`.
- The Stable ABI (Limited API) is automatically disabled for free-threaded Python builds since `Py_GIL_DISABLED` is incompatible with the Limited API.

## Status
accepted

## Context
PEP 703 introduces free-threaded Python (CPython 3.13t+) where the Global Interpreter Lock is removed. The TVM FFI Cython binding layer uses `with gil` in several places (object deleters, callback wrappers) which either does not compile or behaves incorrectly under free-threaded Python. Additionally, the Stable ABI/Limited API (`USE_SABI`) is not supported by free-threaded Python builds. The FFI needed to handle both standard and free-threaded Python from the same source code.

## Decision Drivers
- Free-threaded Python is an experimental feature in CPython 3.13t and expected to become standard in future CPython versions.
- The TVM FFI must work correctly under free-threaded Python to remain viable as ML frameworks adopt it.
- The Cython `with gil` syntax generates code that may not work correctly with `Py_GIL_DISABLED`.
- Object deleters called from C++ destructors need to safely decrement Python reference counts regardless of GIL state.

## Decision
1. **Replace `with gil` with C++ GIL helper**: Introduced `TVMFFIPyWithGILIfNotFreeThreaded` RAII class that:
   - Under standard CPython: calls `PyGILState_Ensure()` in constructor, `PyGILState_Release()` in destructor.
   - Under free-threaded Python (`Py_GIL_DISABLED`): is a completely empty no-op class (default constructor/destructor).
   The selection is compile-time via `#if defined(Py_GIL_DISABLED)`.

2. **Unified object deleter**: Introduced `TVMFFIPyObjectDeleter` as an `extern "C"` function that uses the GIL helper internally. This replaces the Cython `tvm_ffi_pyobject_deleter` function for both function and opaque object creation.

3. **CMake Stable ABI detection**: At CMake configure time, detect `Py_GIL_DISABLED` by querying the Python interpreter. When detected, force `USE_SABI=OFF`. This prevents compilation failures from missing Limited API symbols.

4. **OpaqueObject type hierarchy fix**: Changed `OpaqueObject` registration from `ReserveBuiltinTypeIndex` to `GetOrAllocTypeIndex` with proper parent type information. This was an orthogonal bug exposed by free-threaded Python ref count tests (different ref count behavior revealed the registration was incorrect).

## Alternatives Considered
### Use Cython's native free-threaded Python support (when available)
- Pros: No C++ helper code needed. Maintained by Cython team.
- Cons: Cython's free-threaded support was immature at the time. The `with gil` syntax does not have a clean `Py_GIL_DISABLED` conditional path. The Cython team was still working on proper free-threaded support.

### Runtime GIL detection instead of compile-time
- Pros: Single binary works for both GIL and no-GIL Python.
- Cons: Python's free-threaded mode is a build-time decision (separate `python3.13t` executable). Runtime detection adds an unnecessary branch to every deleter call. The `Py_GIL_DISABLED` macro is the official way to check.

### Skip free-threaded Python support
- Pros: No code changes needed.
- Cons: TVM FFI would be unusable on free-threaded Python builds. As ML frameworks adopt free-threaded Python for better multi-threaded performance, this would be a significant limitation.

## Why This Option Won
- Compile-time conditional (`Py_GIL_DISABLED`) is the official CPython mechanism for free-threaded builds.
- The RAII helper pattern is minimal, well-understood, and has zero overhead under free-threaded builds.
- CMake detection + Stable ABI disable is the most reliable way to prevent build failures.
- The approach is forward-compatible: when free-threaded Python becomes the default, the `#else` branch becomes dead code.

## Consequences
### Positive
- TVM FFI compiles and works correctly under free-threaded Python.
- Object lifecycle management (ref counting) is safe under both GIL and no-GIL modes.
- CI matrix includes free-threaded Python for continuous validation.
- OpaqueObject is properly part of the Object type hierarchy.

### Negative
- Two code paths (GIL vs no-GIL) increase testing surface.
- Stable ABI is unavailable for free-threaded Python builds, requiring per-version wheels instead of universal wheels.
- The compile-time approach means a binary built for standard Python cannot run on free-threaded Python and vice versa.

### Risks
- Free-threaded Python may change its ABI or GIL semantics in future versions. The `Py_GIL_DISABLED` check would need updating.
- Thread-safety of FFI containers (Array, Map, etc.) under free-threaded Python is not addressed by this ADR. Containers are assumed to be single-threaded.
- The `TVMFFIPyObjectDeleter` is `noexcept` but calls `Py_DecRef`, which in theory could trigger Python finalizers that raise exceptions. Under CPython, `Py_DecRef` in a destructor context swallows exceptions.

## Implementation Notes
- `TVMFFIPyWithGILIfNotFreeThreaded`: two implementations selected by `#if defined(Py_GIL_DISABLED)`.
- `TVMFFIPyObjectDeleter`: `extern "C" void TVMFFIPyObjectDeleter(void* py_obj) noexcept`.
- CMake detection: `execute_process(COMMAND ${Python_EXECUTABLE} -c "import sysconfig; print(sysconfig.get_config_var('Py_GIL_DISABLED'))")`.
- OpaqueObject: `GetOrAllocTypeIndex("OpaqueObject", 1, kTVMFFIObject)` instead of `ReserveBuiltinTypeIndex`.

## Validation
- CI matrix includes free-threaded Python (CPython 3.13t).
- `uv run pytest tests/python/` passes under both standard and free-threaded Python.
- Object ref count tests pass (the OpaqueObject fix was needed for these).

## Migration and Rollback
- Migration: None for users. Internal change only.
- Rollback: Revert commit `b64b46f3` and remove free-threaded CI matrix entry.

## Related Design Docs
- [.memory/designs/0020-external-function-construction.md](.memory/designs/0020-external-function-construction.md) (uses `TVMFFIPyObjectDeleter` for keep-alive objects)
- [.memory/designs/0011-cython-binding-layer.md](.memory/designs/0011-cython-binding-layer.md) (Cython binding layer where deleters are used)

## Related Diagrams
None

## Evidence Matrix
- `TVMFFIPyWithGILIfNotFreeThreaded` RAII class -> `.memory/commits/2025-10-10-b64b46f3.md` + `b64b46f3` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- `TVMFFIPyObjectDeleter` extern C function -> `b64b46f3` + `python/tvm_ffi/cython/tvm_ffi_python_helpers.h`
- CMake `Py_GIL_DISABLED` detection and `USE_SABI=OFF` -> `b64b46f3` + `CMakeLists.txt`
- OpaqueObject `GetOrAllocTypeIndex` fix -> `b64b46f3` + `src/ffi/object.cc`
- Cython callback simplification (direct return, no branching) -> `b64b46f3` + `python/tvm_ffi/cython/function.pxi`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Monitor Cython's native free-threaded Python support and evaluate whether the C++ helper can be replaced.
- Evaluate thread-safety of FFI container operations under free-threaded Python.
- Track CPython 3.14+ free-threaded ABI stability.
