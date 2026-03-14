---
scope:
  - "0019-python-ffi-call-dispatch"
  - "0014-python-bindings"
---
# Recursive Container Conversion in Cython via ConstructorCall

**TL;DR**: Moves `list`/`tuple`/`dict`/`ObjectConvertible` conversion from the Python-level `_FUNC_CONVERT_TO_OBJECT` callback into Cython-level `ConstructorCall` with stream/allocator context propagation, fixing torch CUDA stream detection for nested containers.

## Context

Previously, when `make_args` encountered a `list`, `tuple`, `dict`, or `ObjectConvertible`, it called a Python-level callback (`_FUNC_CONVERT_TO_OBJECT`, registered by `_convert.py`) that called `convert()`. This Python callback:
1. Did not participate in the `TVMFFIPyCallContext`, so torch CUDA stream detection was lost for tensors nested inside containers.
2. Required a Python function call per conversion, adding overhead.
3. Created a circular initialization dependency: `_convert.py` had to register itself into the Cython core layer.

Usecases:
- Passing `dict[str, torch.Tensor]` to FFI functions where the tensors are on CUDA and the kernel needs the correct CUDA stream.
- Passing `list[list[int]]` where nested containers need recursive conversion to `Array<Array<int>>`.
- `ObjectConvertible` types (custom user types with `__tvm_ffi_object__` protocol).

Design Decisions:
- Add Cython argument setters for `tuple`, `list`, `dict`, and `ObjectConvertible` that call `ffi.Array` or `ffi.Map` constructors via `ConstructorCall`.
- `ConstructorCall` propagates `device_type`, `device_id`, `stream`, `c_dlpack_tensor_allocator`, and `c_dlpack_to_pyobject` from inner context back to outer context.
- Remove `_FUNC_CONVERT_TO_OBJECT` callback and `_convert.py` registration from the initialization chain.

## Alternatives

### 1. Cython-level recursive conversion via ConstructorCall (chosen)
- Pros: Correct stream propagation through nested containers. Faster (no Python function call). Eliminates circular initialization dependency.
- Cons: Increased Cython/C++ complexity. Container conversion logic duplicated between Cython setters and `_convert.py` (which still exists for direct Python-level `convert()` calls).

### 2. Pass stream context as Python-level thread-local
- Pros: Simpler implementation. `_convert.py` callback can read the TLS.
- Cons: Two sources of truth (Python TLS and C++ TLS). Fragile. Does not eliminate Python function call overhead.

### 3. Require users to pre-convert containers
- Pros: No implicit conversion. Explicit is better than implicit.
- Cons: Poor ergonomics. Users must call `tvm_ffi.Array([...])` explicitly for every container argument.

## Decision

Option 1. The key insight is that `ConstructorCall` (unlike `FuncCall`) does not set stream/allocator context itself but propagates detected context back to the parent `TVMFFIPyCallContext`. This enables correct stream detection even when tensors are buried deep in nested containers.

## Implementation Notes

- `TVMFFIPyArgSetterTuple_`: Calls `ConstructorCall(ffi.Array, *elements)`.
- `TVMFFIPyArgSetterTupleLike_`: Same as `Tuple_` but for `list` (which may not be tuple).
- `TVMFFIPyArgSetterMap_`: Interleaves keys and values, calls `ConstructorCall(ffi.Map, k0, v0, k1, v1, ...)`.
- `TVMFFIPyArgSetterObjectConvertible_`: Calls `arg.__tvm_ffi_object__` protocol.
- `TVMFFIPyArgSetterPyNativeObjectStr_/Bytes_/General_`: Split from the former mixed `PyNativeObject` handling.

## Consequences

- **Correctness**: Torch CUDA stream detection now works through nested containers.
- **Performance**: Eliminates Python function call overhead for container conversion.
- **Initialization simplification**: `_convert.py` no longer registers into the Cython core layer. `_OBJECT_FROM_JSON_GRAPH_STR` and `_OBJECT_TO_JSON_GRAPH_STR` moved from Python globals to Cython `cdef` variables.
- **Rollback**: Would require re-introducing `_FUNC_CONVERT_TO_OBJECT` and accepting broken stream propagation for nested containers.

## Related Design Docs

- [`.knowledge/designs/0019-python-ffi-call-dispatch.md`](../designs/0019-python-ffi-call-dispatch.md) -- ConstructorCall architecture
- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Python bindings package
- [`.knowledge/ADRs/0020-thread-local-stream-context.md`](0020-thread-local-stream-context.md) -- Stream context TLS
- Commit: `.knowledge/commits/2025-09-13-043d9f647677cc3b4a8baba198a2ced45f99cc98.md` + `043d9f6`
