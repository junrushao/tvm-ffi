---
scope:
  - ".knowledge/designs/0014-python-bindings.md"
---
# ADR 012: Use Cython for the Python Binding Layer

**TL;DR**:
- The Python bindings use Cython to compile a native extension module that directly calls the C API, rather than using ctypes, pybind11, or nanobind.
- This decision optimizes hot-path performance (function calls, argument packing), enables GIL release during C calls, and is compatible with the Stable ABI for forward Python version compatibility.

## Context

The TVM FFI exposes a complete type-erased calling convention through a C ABI (`TVMFFISafeCallType`). The Python binding layer must:
1. Pack Python arguments into `TVMFFIAny` arrays and unpack results on every function call.
2. Manage object ref-counts (increment on acquisition, decrement on Python object destruction).
3. Wrap Python callables as FFI Functions (with GIL management).
4. Propagate errors bidirectionally with traceback reconstruction.

Function calls through the FFI are the hottest path in the system -- every cross-language interaction goes through argument packing. The binding technology must minimize per-call overhead.

Usecases:
- Calling C++-registered functions from Python with minimal latency (e.g., tensor operations).
- Wrapping Python callbacks for consumption by C++ code (e.g., custom scheduling).
- Managing hundreds of ref-counted objects in tight loops without GC pressure.

Design Decisions:
- Use Cython to implement the core binding layer (`core.pyx` + 8 `.pxi` files).
- Compile against the FFI's C API headers directly (not C++ wrappers).
- Use `cdef class` for extension types (`Object`, `NDArray`, `DataType`, `Device`).
- Use `with nogil` to release the GIL during `TVMFFIFunctionCall`.
- Support Stable ABI (`USE_SABI 3.12`) for Python 3.12+ to produce forward-compatible wheels.

## Alternatives

### Alternative A: ctypes-based binding (pure Python)
- Description: Use `ctypes.CDLL` to load the shared library and `ctypes.CFUNCTYPE` for callbacks. Pack arguments via ctypes struct construction.
- Pros: No compilation step; pure Python; works on any Python implementation.
- Cons: ctypes has significant per-call overhead (dictionary lookups for type resolution, Python-level struct construction). Cannot release the GIL during C calls. No direct struct field access (must use `ctypes.Structure` which involves Python attribute lookups). Cannot inline the `isinstance`-chain argument dispatch at C level.
- Why rejected: Hot-path performance is unacceptable. ctypes overhead is measured at 5-10x slower than Cython for small-argument function calls due to Python-level type resolution on every call.

### Alternative B: pybind11 or nanobind
- Description: Write C++ binding code using pybind11/nanobind to generate a Python extension module. Would wrap the C++ `Function`, `ObjectRef`, `AnyView` types directly.
- Pros: C++-native; automatic docstring generation; good type inference.
- Cons: Generates C++ binding code that duplicates the type-erased calling convention already provided by the C API. pybind11 has known overhead for small-argument calls (argument tuple unpacking). Tight coupling to Python version (no stable ABI support until recent nanobind versions). Would require wrapping C++ templates (`Any`, `AnyView`, `TypeTraits`) which adds compilation time and binary size. The FFI already has a well-defined C API -- the binding layer should call through C, not re-wrap C++.
- Why rejected: Redundant abstraction layer. The FFI's C API is the intended cross-language interface. Cython calls C API functions directly, matching the same pattern used by the Rust bindings (which call the C API via `tvm-ffi-sys`).

## Implementation Notes
- Cython `.pxi` files (include files) are used instead of separate `.pyx` files to compile everything into a single `core.so` extension module, reducing import overhead and enabling shared `cdef` declarations across all binding components.
- The argument dispatch is a **hybrid C++/Cython approach** (since 38d2cda): POD type setters (`float`, `int`, `bool`, `None`) are C++ functions defined in `tvm_ffi_python_helpers.h`, while complex setters (Tensor, DLPack, containers, strings, bytes) remain in Cython. The factory (`TVMFFIPyArgSetterFactory_`) uses a flat isinstance chain in Cython, but it runs only once per Python type -- subsequent calls for the same type go directly to the cached setter.
- `TVMFFIPyCallManager` (C++ class in `tvm_ffi_python_helpers.h`) manages a thread-local dispatch table (`unordered_map<PyTypeObject*, TVMFFIPyArgSetter>`) and a `CallStack` RAII allocator for per-call argument memory.
- `str` and `bytes` arguments are now passed as owned `String`/`Bytes` objects via `TVMFFIStringFromByteArray`/`TVMFFIBytesFromByteArray` (since 043d9f6), leveraging SSO, instead of non-owning views.
- Nested container conversion (`list`/`tuple`/`dict`) is handled by Cython setters calling `TVMFFIPyConstructorCall` for recursive conversion (since 043d9f6), replacing the old `_FUNC_CONVERT_TO_OBJECT` Python callback.
- `Function` is a `cdef class` (since f81ab9c) with a `release_gil` property controlling whether the GIL is released during the C call.
- `tvm_ffi_callback` (the C callback for Python-wrapped functions) is declared `noexcept with gil` -- it catches Python exceptions, converts them to FFI errors, and returns -1.

## Related Design Docs
- `.knowledge/designs/0014-python-bindings.md` -- Full Python binding layer design
- `.knowledge/designs/c-abi.md` -- C API consumed by the Cython layer
- `.knowledge/designs/function-system.md` -- Packed calling convention
