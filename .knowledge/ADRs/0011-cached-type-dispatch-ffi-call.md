---
scope:
  - "0012-python-bindings"
---
# ADR 0011: Cached PyTypeObject Dispatch for FFI Call Path

**TL;DR**: Replaced the monolithic Cython `make_args` isinstance chain with a C++ `TVMFFIPyCallManager` that caches `PyTypeObject* -> TVMFFIPyArgSetter` in a thread-local map, eliminating repeated isinstance checks on hot paths and enabling GIL-aware call lifecycle management.

## Context
- The original `make_args` function in Cython (`function.pxi`) dispatched each argument through a chain of ~19 `isinstance` checks on every FFI function call. For functions called millions of times (e.g., per-element tensor operations), this isinstance overhead was measurable.
- Additionally, `make_args` was responsible for tracking temporary objects, managing CUDA stream context, and handling the GIL -- all interleaved in a single monolithic function, making the code difficult to extend and optimize.
- The key insight is that Python types are immutable: once `PyTypeObject*` for a value is determined, the appropriate setter function never changes. This makes type-dispatch caching safe without invalidation.

Usecases:
- High-frequency FFI calls (e.g., per-op dispatch in graph execution engines)
- Torch tensor interop where each call involves DLPack conversion
- Nested container conversion (list of tensors -> Array) where each element needs dispatch

Design Decisions:
- **Cache key is `PyTypeObject*`**: Python types are heap-allocated and immutable. Two values of the same type share the same `PyTypeObject*`, making it a perfect cache key. No cache invalidation is needed. However, locally-defined or dynamically-created types can be garbage collected, allowing a new type to be allocated at the same address, causing the dispatcher to use a stale arg setter for the wrong type. To prevent this, `_DISPATCH_TYPE_KEEP_ALIVE` (a module-level `set` with `threading.Lock`) in `function.pxi` retains strong references to all types seen by the factory (cfff30b). The lock prepares for future GIL-free Python (PEP 703); under the current GIL, it adds negligible overhead.
- **Thread-local cache**: The dispatch map is thread-local to avoid locking. Each thread builds its own cache on first encounter of each type.
- **RAII `CallStack` for temp lifecycle**: Temporary FFI objects (e.g., String created from `str`) and Python objects are tracked in per-call arrays and automatically cleaned up by the `CallStack` destructor, replacing the old `temp_args` Python list.
- **C++ implementation compiled into Cython extension**: `tvm_ffi_python_helpers.h` is compiled as part of the Cython extension, not the core `libtvm_ffi.so`. This keeps the Python-specific dispatch logic out of the language-agnostic C++ library.
- **Separate `FuncCall` vs `ConstructorCall`**: Top-level function calls release the GIL and manage stream context; constructor calls (for nested container conversion) do neither but propagate context back to the parent.

## Implementation Notes
- `TVMFFIPyFuncCall` is the top-level C-linkage entry point called from `Function.__call__` in Cython
- `TVMFFIPyArgSetterFactory_` remains in Cython (not C++) because it needs access to Cython-level type objects (Tensor, Object, etc.)
- The factory is called at most once per `(thread, PyTypeObject*)` pair; subsequent calls use the cached setter
- Per-type setters (`SetterInt_`, `SetterStr_`, `SetterTensor_`, etc.) are thin Cython `cdef` functions with `int` return type for error propagation

## Related Design Docs
- [0012-python-bindings.md](../designs/0012-python-bindings.md) -- Primary consumer of this decision
- [0001-c-abi.md](../designs/0001-c-abi.md) -- TVMFFIFunctionCall called by FuncCall
