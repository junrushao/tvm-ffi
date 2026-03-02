---
design: "0014"
title: "Stream Exchange Protocol (__tvm_ffi_env_stream__)"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-09-09"
last_updated: "2025-10-13"
scope:
  - "ffi/extra/c_env_api"
  - "python/tvm_ffi/cython"
  - "python/tvm_ffi/stream"
  - "ffi/extra/stream_context"
source_commits:
  - "a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806"
  - "3197cd0949ae9bb9a41eb5a429a4b1519d061db4"
  - "22c049b8f3b64e7e2f17b28df044b065ae3fba83"
  - "b0537f04"
  - "965fc464"
source_ledgers:
  - ".memory/commits/2025-09-09-a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806.md"
  - ".memory/commits/2025-09-15-3197cd0949ae9bb9a41eb5a429a4b1519d061db4.md"
  - ".memory/commits/2025-10-08-22c049b8.md"
  - ".memory/commits/2025-10-13-b0537f04.md"
  - ".memory/commits/2025-10-13-965fc464.md"
---

# Stream Exchange Protocol (__tvm_ffi_env_stream__)

## TL;DR
- The `__tvm_ffi_env_stream__` protocol enables any DLPack-compatible Python object to communicate its GPU stream to TVM FFI's stream context, allowing cross-framework stream synchronization without direct C API calls.
- When a non-CPU tensor argument implements `__tvm_ffi_env_stream__()`, the Cython marshaling layer calls it before the FFI function call, passing the stream handle via `TVMFFIEnvSetCurrentStream`.
- The C API was renamed from `TVMFFIEnvSetStream`/`TVMFFIEnvGetStream` to `TVMFFIEnvSetCurrentStream`/`TVMFFIEnvGetCurrentStream` for clarity.

## Problem Statement
GPU-accelerated FFI calls need to execute on the correct CUDA/ROCm stream to avoid implicit synchronization and correctness bugs. When a Python framework (PyTorch, CuPy, etc.) passes a tensor to an FFI function, the FFI needs to know which stream the tensor's data was produced on. Without a protocol, each framework needs custom integration code in the Cython layer, and new frameworks cannot participate in stream exchange without modifying the FFI.

## Context and Constraints
- GPU tensors from multiple frameworks may be passed to the same FFI function.
- Each framework has its own stream management API (e.g., `torch.cuda.current_stream()`).
- The FFI uses a thread-local `StreamContext` to track the "current stream" for each device.
- The stream must be set before the FFI function call and restored after.
- The protocol must be opt-in: existing DLPack objects without `__tvm_ffi_env_stream__` should continue to work.

## Goals
- Define a duck-typing protocol (`__tvm_ffi_env_stream__`) for Python objects to communicate GPU streams.
- Automatically detect and invoke the protocol during argument marshaling.
- Support multiple GPU devices (the stream is per-device).
- Minimize overhead for CPU tensors (no stream exchange needed).

## Non-Goals
- Stream synchronization across different devices (e.g., CUDA to ROCm). Each device has its own stream context.
- Automatic multi-stream scheduling. The protocol communicates one stream per device per call.
- Replacing framework-specific stream management. The protocol is a bridge, not a replacement.

## Design
### Components and Responsibilities

- **`__tvm_ffi_env_stream__`** (Python protocol): A duck-typing method on Python objects. When called, returns an integer representing the stream handle (cast to `long long`). The object must also implement `__dlpack_device__()` to provide the device type and ID.

- **`TVMFFIEnvSetCurrentStream(device_type, device_id, stream_handle)`** (C API, `extra/c_env_api.h`): Sets the current stream for the given device. Renamed from `TVMFFIEnvSetStream`.

- **`TVMFFIEnvGetCurrentStream(device_type, device_id, out_stream)`** (C API, `extra/c_env_api.h`): Gets the current stream for the given device. Renamed from `TVMFFIEnvGetStream`.

- **`StreamContext`** (thread-local, `src/ffi/extra/stream_context.cc`): Stores a `Map<Device, int64_t>` mapping each device to its current stream handle. Thread-local to avoid contention.

- **Cython marshaling integration** (`function.pxi`): In `make_args()`, when processing a non-CPU argument that has `__tvm_ffi_env_stream__`, the marshaling layer: (1) calls `__dlpack_device__()` to get device info, (2) calls `__tvm_ffi_env_stream__()` to get the stream handle, (3) calls `TVMFFIEnvSetCurrentStream` to set the stream before the FFI call.

- **`DLTensorTestWrapper`** (Cython class, `tensor.pxi`): Test utility that wraps a `Tensor` and implements `__tvm_ffi_env_stream__`, `__dlpack__`, and `__dlpack_device__` for verifying the protocol in tests.

- **DLPack device type constants** (`base.pxi`): `kDLCPU`, `kDLCUDA`, `kDLROCm`, etc. are declared from `dlpack/dlpack.h` to enable device-type branching in Cython code.

- **`StreamContext`** (Python class, `python/tvm_ffi/stream.py`): Explicit context manager for scope-based stream management. On `__enter__`, saves the current stream via `_env_set_current_stream()` and sets the new one; on `__exit__`, restores the previous stream. This complements the implicit `__tvm_ffi_env_stream__` protocol with a user-controlled scope-based approach.

- **`TorchStreamContext`** (Python class, `python/tvm_ffi/stream.py`): Wraps a PyTorch `torch.cuda.stream()` or `torch.cuda.graph()` context, extracting the CUDA stream handle and device from `torch.cuda.current_stream()`, then delegating to `StreamContext`. Conditionally defined (only when `torch` is importable).

- **`use_torch_stream(context=None)`** (factory function): Returns a `TorchStreamContext`. Accepts a torch stream context, graph context, or `None` (uses current default stream).

- **`use_raw_stream(device, stream)`** (factory function): Returns a `StreamContext` from a raw `Device` and stream handle (`int` or `ctypes.c_void_p`).

- **`get_raw_stream(device)`** (function, `stream.py`): Queries the current FFI stream for a given device. Returns an integer representing the stream handle. Wraps `_env_get_current_stream(device_type, device_id)` which calls `TVMFFIEnvGetStream` (commit `22c049b8`). Exported from `tvm_ffi.__init__`.

- **`_env_get_current_stream(device_type, device_id)`** (Cython function, `base.pxi`): Wraps `TVMFFIEnvGetStream()`, returning the current stream handle as `int`. Added in commit `22c049b8`.

- **`__cuda_stream__`** (Python protocol, commit `b0537f04`): NVIDIA's cuda-python interop protocol for stream handles. Supported in the Cython arg setter factory via `TVMFFIPyArgSetterCUDAStream_`. Also fixes `__dlpack__` check to use `arg_class` instead of `arg` (instance-level). Older PyTorch versions get `__cuda_stream__` monkey-patched onto `torch.cuda.Stream` (commit `965fc464`). See also [Design 0022](.memory/designs/0022-python-ffi-interop-protocols.md).

- **`_env_set_current_stream(device_type, device_id, stream)`** (Cython function, `base.pxi`): Wraps `TVMFFIEnvSetStream()`, returning the previous stream handle as `uint64_t`.

### Data Contracts and Invariants
- **Protocol contract**: An object implementing `__tvm_ffi_env_stream__` must also implement `__dlpack_device__()`. The return value of `__tvm_ffi_env_stream__()` must be a valid stream handle (integer) for the device.
- **Thread-local invariant**: The stream context is per-thread. Setting a stream on one thread does not affect other threads.
- **Save/restore invariant**: The Cython layer saves the previous stream before calling `TVMFFIEnvSetCurrentStream` and restores it after the FFI function call completes. This prevents stream context leakage.
- **CPU skip invariant**: CPU tensors (device type `kDLCPU`) skip stream exchange entirely, even if they implement `__tvm_ffi_env_stream__`.

### Control Flow
1. Python caller invokes `func(tensor_arg)`.
2. `make_args()` processes `tensor_arg`.
3. If `tensor_arg` has `__dlpack__` and `__tvm_ffi_env_stream__`:
   a. Call `tensor_arg.__dlpack_device__()` -> `(device_type, device_id)`.
   b. If `device_type != kDLCPU`:
      - Call `tensor_arg.__tvm_ffi_env_stream__()` -> `stream_handle`.
      - Call `TVMFFIEnvSetCurrentStream(device_type, device_id, stream_handle)`.
4. Call `TVMFFIFunctionCall()` with packed arguments.
5. Restore the previous stream context.

### Explicit Stream Context Control Flow (commit `3197cd09`)
1. User creates a stream context: `with tvm_ffi.use_torch_stream(torch.cuda.stream(s)):`.
2. `TorchStreamContext.__enter__()` enters the torch context (if provided), then queries `torch.cuda.current_stream()` for the device and stream handle.
3. A `StreamContext` is created and entered, calling `_env_set_current_stream()` which invokes `TVMFFIEnvSetStream()` and caches the previous stream handle.
4. All FFI calls within the `with` block use the new stream context.
5. On `__exit__`, the previous stream is restored via another `_env_set_current_stream()` call.

### Extension Points
- Any new framework can participate by implementing `__tvm_ffi_env_stream__` on its tensor class.
- The `StreamContext` can be extended to support new device types as DLPack adds them.
- torch-specific fast path: torch tensors use `torch._C._cuda_getCurrentRawStream(device_id)` directly, which is faster than the generic protocol for the common case.
- The explicit `use_raw_stream` API allows non-Python-framework stream management (e.g., from C++ callbacks or custom CUDA runtime wrappers).

## Alternatives Considered
### Explicit stream argument in every FFI call
- Pros: No implicit behavior. Caller controls the stream.
- Cons: Extremely verbose. Every FFI call site needs to pass a stream. Breaks existing APIs.

### Framework-specific detection in make_args only
- Pros: No protocol definition needed.
- Cons: Every new framework requires changes to the Cython layer. Not extensible.

### Global stream context without per-call save/restore
- Pros: Simpler implementation.
- Cons: Stream context leakage between calls. Unsafe in nested call scenarios.

## Trade-offs
- **Optimized**: Extensibility (any framework can implement the protocol), automatic stream propagation (no user code needed), zero overhead for CPU tensors.
- **Sacrificed**: Explicitness (stream exchange happens implicitly during marshaling), potential confusion if a framework's `__tvm_ffi_env_stream__` returns an incorrect handle.

## Interfaces and Compatibility
- **C API**: `TVMFFIEnvSetCurrentStream`, `TVMFFIEnvGetCurrentStream` (renamed from `TVMFFIEnvSetStream`, `TVMFFIEnvGetStream`).
- **Python protocol**: `__tvm_ffi_env_stream__()` -> `int` on any Python object.
- **Python explicit API** (commit `3197cd09`): `tvm_ffi.StreamContext`, `tvm_ffi.use_raw_stream`, `tvm_ffi.use_torch_stream` -- all exported from `tvm_ffi.__init__`. `tvm_ffi.get_raw_stream` (commit `22c049b8`) provides the read-side query API.
- **Breaking change**: C code calling `TVMFFIEnvSetStream` or `TVMFFIEnvGetStream` must update to the `CurrentStream` names.

## Failure Modes and Mitigations
- **Missing `__dlpack_device__`**: If an object has `__tvm_ffi_env_stream__` but not `__dlpack_device__`, the marshaling layer skips stream exchange (graceful degradation).
- **Invalid stream handle**: If `__tvm_ffi_env_stream__` returns a non-integer or invalid handle, `TVMFFIEnvSetCurrentStream` may silently use the wrong stream. Mitigated by documentation requiring valid handles.
- **Stream context not restored on exception**: The save/restore pattern must be in a try/finally block to ensure restoration even if the FFI call raises.

## Observability and Validation
- `DLTensorTestWrapper` in `tensor.pxi` provides a test harness for the protocol.
- `benchmark_dlpack.py` benchmarks stream exchange overhead.
- The `StreamContext` state can be inspected via `TVMFFIEnvGetCurrentStream` for debugging.

## Migration and Rollout
- New protocol: no migration needed for existing code.
- C API rename: callers of `TVMFFIEnvSetStream`/`TVMFFIEnvGetStream` must update.
- Framework integrations: torch auto-detection remains built-in; other frameworks opt-in by implementing `__tvm_ffi_env_stream__`.

## Diagrams
- [.memory/diagrams/0011-stream-exchange-flow.md](.memory/diagrams/0011-stream-exchange-flow.md)

## Related ADRs
None

## Evidence Matrix
- `__tvm_ffi_env_stream__` protocol in Cython `make_args()` -> `.memory/commits/2025-09-09-a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806.md` + `a08fa6e` + `python/tvm_ffi/cython/function.pxi`
- `TVMFFIEnvSetCurrentStream` rename -> `a08fa6e` + `include/tvm/ffi/extra/c_env_api.h`
- `DLTensorTestWrapper` test class -> `a08fa6e` + `python/tvm_ffi/cython/tensor.pxi`
- DLPack device type constants in `base.pxi` -> `a08fa6e` + `python/tvm_ffi/cython/base.pxi`
- `StreamContext` thread-local storage -> `a08fa6e` + `src/ffi/extra/stream_context.cc`
- Python `StreamContext` class -> `.memory/commits/2025-09-15-3197cd0949ae9bb9a41eb5a429a4b1519d061db4.md` + `3197cd0` + `python/tvm_ffi/stream.py`
- `TorchStreamContext` and `use_torch_stream` -> `3197cd0` + `python/tvm_ffi/stream.py`
- `_env_set_current_stream` Cython wrapper -> `3197cd0` + `python/tvm_ffi/cython/base.pxi`
- `StreamContext`, `use_raw_stream`, `use_torch_stream` in public API -> `3197cd0` + `python/tvm_ffi/__init__.py`
- `get_raw_stream(device)` query function -> `.memory/commits/2025-10-08-22c049b8.md` + `22c049b8` + `python/tvm_ffi/stream.py`, `python/tvm_ffi/__init__.py`
- `_env_get_current_stream` Cython wrapper for `TVMFFIEnvGetStream` -> `22c049b8` + `python/tvm_ffi/cython/base.pxi`
- `__cuda_stream__` protocol in Cython arg setter factory -> `.memory/commits/2025-10-13-b0537f04.md` + `b0537f04` + `python/tvm_ffi/cython/function.pxi`
- `__cuda_stream__` monkey-patch for older PyTorch `torch.cuda.Stream` -> `.memory/commits/2025-10-13-965fc464.md` + `965fc464` + `python/tvm_ffi/_optional_torch_c_dlpack.py`

## Open Questions
- Should the protocol support asynchronous stream queries (for frameworks with async stream management)?
- Should there be a C++ analog of `__tvm_ffi_env_stream__` for C++ callers?

## Confidence and Risk
- Confidence: high
- Residual risks: The protocol depends on framework correctness for stream handles. An incorrect handle could cause silent GPU synchronization bugs that are difficult to diagnose.
