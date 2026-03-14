---
scope:
  - "0019-python-ffi-call-dispatch"
  - "0014-python-bindings"
---
# Optional Per-Function GIL Release

**TL;DR**: `Function` becomes a Cython `cdef class` with a `release_gil` property (defaulting from `TVM_FFI_RELEASE_GIL_BY_DEFAULT` env var), enabling per-function opt-out of GIL release to avoid ~50ns overhead on short-running functions.

## Context

The FFI previously always released the GIL (`with nogil:`) around every `TVMFFIFunctionCall`. For short-running functions (e.g., shape queries, property accessors), the cost of `Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS` (~50ns on typical platforms) is a significant fraction of total call time. For long-running kernels, GIL release is essential to allow other Python threads to proceed.

Usecases:
- Short-running FFI functions (property getters, shape queries) where GIL release overhead exceeds computation time.
- Long-running GPU kernels where GIL release enables Python-level concurrency.
- Benchmarking: measuring pure call overhead requires disabling GIL release.

Design Decisions:
- `Function` changes from a Python `class` (extending `Object`) to a Cython `cdef class` with a C-level `c_release_gil` field.
- Default from `TVM_FFI_RELEASE_GIL_BY_DEFAULT` environment variable (default "1", meaning GIL release is on by default).
- The `release_gil` property is readable and writable at the Python level.

## Alternatives

### 1. Per-function configurable GIL release (chosen)
- Pros: Fine-grained control. Default-safe (GIL released by default for long calls). Opt-out for short calls.
- Cons: User must know which functions are short-running. Extra property on every `Function` object.

### 2. Always release GIL (status quo before `f81ab9c`)
- Pros: Simple. Thread-safe by default.
- Cons: ~50ns overhead per call. Measurable for short-running functions.

### 3. Never release GIL
- Pros: Zero GIL overhead.
- Cons: Blocks all other Python threads during long-running GPU kernels. Breaks Python-level concurrency.

### 4. Heuristic auto-detection (e.g., function metadata flag)
- Pros: No user configuration needed.
- Cons: Cannot reliably predict execution time from metadata. Over-engineering for a simple on/off decision.

## Decision

Option 1. `Function` as `cdef class` also enables direct C-level field access (`self.c_release_gil`) without Python attribute lookup overhead on the critical path.

## Implementation Notes

- `Function.__call__` passes `self.release_gil` to `TVMFFIPyFuncCall`, which threads it through `TVMFFIPyCallManager::Call`. The C++ call manager conditionally wraps `TVMFFIFunctionCall` in `Py_BEGIN_ALLOW_THREADS`/`Py_END_ALLOW_THREADS`.
- `ConstructorCall` inherits the parent call's `release_gil` setting.
- DLPack tensor operations (`TVMFFITensorFromDLPack`, `TVMFFITensorToDLPack`, etc.) no longer release the GIL in Cython because they are fast in-process operations.

## Consequences

- **Performance**: Short-running functions with `release_gil=False` save ~50ns per call.
- **Breaking change**: `Function` is now a `cdef class`, which cannot be subclassed from pure Python. Code that subclasses `Function` directly (unusual) would break.
- **Rollback**: Set `TVM_FFI_RELEASE_GIL_BY_DEFAULT=1` to restore always-release behavior.

## Related Design Docs

- [`.knowledge/designs/0019-python-ffi-call-dispatch.md`](../designs/0019-python-ffi-call-dispatch.md) -- Call dispatch architecture
- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Python bindings package
- Commit: `.knowledge/commits/2025-09-12-f81ab9c25ae4d2a42706747c50c5c410c51d6cdd.md` + `f81ab9c`
