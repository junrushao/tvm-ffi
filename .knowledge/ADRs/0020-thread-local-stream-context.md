---
scope:
  - "0011-extra-api-tier"
  - "0001-c-abi"
---
# Thread-Local Storage for Per-Device Stream Context

**TL;DR**: The FFI uses `thread_local` storage for per-device GPU stream context (`TVMFFIEnvSetStream`/`TVMFFIEnvGetStream`, renamed from `TVMFFIEnvSetCurrentStream`/`TVMFFIEnvGetCurrentStream` in commit `f81ab9c`), matching the common GPU programming pattern (e.g., CUDA's per-thread default stream) with zero-contention reads and no locking. As of commit `f81ab9c`, the `StreamContext` class was replaced by `EnvContext` which also holds a `DLPackTensorAllocator` per thread.

## Context

GPU frameworks (CUDA, ROCm, Vulkan) use streams/queues to order device operations. The upstream TVM runtime had per-device stream management scattered across individual device APIs, with no centralized mechanism for a host runtime to set a stream and have loaded library modules observe it.

The core problem: when a host runtime sets a non-default stream (e.g., `torch.cuda.Stream`), loaded kernel modules must discover which stream to use without the stream being passed as a function argument. The FFI needs a side channel for stream context.

Usecases:
- AutoDLPack conversion from PyTorch tensors: when a `torch.Tensor` is passed to an FFI function under a non-default CUDA stream, the Cython argument setter calls `TVMFFIEnvSetCurrentStream` to record the current stream before invoking the kernel.
- Kernel library code: generated kernels call `TVMFFIEnvGetCurrentStream` to discover which stream to launch operations on.
- RAII stream restore: the `opt_out_original_stream` parameter enables callers to save/restore the previous stream around a scoped operation.

Design Decisions:
- Use `static thread_local StreamContext` for zero-contention access.
- Store streams as `void*` (weak references) in a 2D vector indexed by `(device_type, device_id)`.
- Both dimensions grow on demand; default state for any `(device_type, device_id)` is `nullptr`.
- Declare in `include/tvm/ffi/extra/c_env_api.h` as `extern "C"` with `TVM_FFI_DLL` visibility.
- `TVMFFIEnvSetCurrentStream` returns `int` (safe-call pattern); `TVMFFIEnvGetCurrentStream` returns `TVMFFIStreamHandle` directly (log-and-abort pattern, since it cannot fail in practice).

## Implementation Notes

- The `EnvContext` class (formerly `StreamContext`) is defined in `src/ffi/extra/env_context.cc` (renamed from `stream_context.cc` in commit `f81ab9c`), gated under `TVM_FFI_USE_EXTRA_CXX_API`. It holds both `stream_table_` and `dlpack_allocator_` fields.
- `TVMFFIStreamHandle` is typedef'd as `void*`, providing minimal type documentation.
- `SetStream` resizes both vector dimensions on demand. `GetStream` returns `nullptr` for out-of-range queries without resizing.
- Negative `device_type` or `device_id` values cause undefined behavior due to `static_cast<size_t>` on negative integers. This is not guarded, but DLPack/TVM conventions require non-negative device identifiers.
- Error handling asymmetry: `SetStream` uses `TVM_FFI_SAFE_CALL_BEGIN/END` (can report `std::bad_alloc` from vector resize); `GetStream` uses `TVM_FFI_LOG_EXCEPTION_CALL_BEGIN/END` (cannot throw in practice, but log-and-abort as a defensive measure since the return type is `void*`, not `int`).
- Evidence: commit `0daaffe` (`.knowledge/commits/2025-08-19-0daaffedd23982ea09f8c38fec4eef1cca1d8cac.md`), benchmarks in commit `6014406` (`.knowledge/commits/2025-08-19-6014406b540c80e1829bdd4271d7388e7a292180.md`)

## Alternatives Considered

1. **Global shared state with locking**: A single shared stream table protected by a mutex. Simpler cross-thread visibility (any thread can see any other thread's stream), but introduces contention on every stream read -- unacceptable for a function called on every kernel launch.

2. **Explicit stream passing as function arguments**: The stream is passed as an additional argument to every kernel invocation. Fully explicit, no side channel needed. But requires changing the packed calling convention (adding a stream parameter), which would be a breaking ABI change for every kernel function.

3. **Per-module stream context**: Each loaded module has its own stream table. Isolates modules from each other. But makes it impossible for a host to set a stream once and have all modules observe it -- the common use case in eager-mode ML frameworks.

## Consequences

- Zero-contention reads: `GetCurrentStream` is a simple vector index lookup with no atomics or locks.
- Cross-thread stream visibility requires explicit coordination: a stream set in thread A is invisible to thread B. If thread B needs the same stream, it must be set independently.
- Thread destruction automatically cleans up the stream table (thread-local storage is destroyed with the thread).
- The stream context can be extended with additional per-device metadata (e.g., stream priority, synchronization state) by adding fields alongside `TVMFFIStreamHandle` in the inner vector.
- If cross-thread stream visibility is ever needed, the thread-local storage would need to be replaced with a shared concurrent data structure, which would be a significant design change.

## Related Design Docs

- [`.knowledge/designs/0011-extra-api-tier.md`](../designs/0011-extra-api-tier.md) -- Extra tier where stream context lives
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI conventions for the extern "C" functions
- [`.knowledge/designs/0020-dlpack-exchange-acceleration.md`](../designs/0020-dlpack-exchange-acceleration.md) -- DLPack acceleration using EnvContext for allocator TLS
- StreamContext -> EnvContext rename: `.knowledge/commits/2025-09-12-f81ab9c25ae4d2a42706747c50c5c410c51d6cdd.md` + `f81ab9c`
