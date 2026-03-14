---
scope:
  - "0011-extra-api-tier"
  - "0014-python-bindings"
---
# Generic __tvm_ffi_env_stream__ Protocol for Stream Context Exchange

**TL;DR**: A Python duck-typing protocol (`__tvm_ffi_env_stream__`) enables any DLPack-compatible object to provide its GPU stream handle when passed as an FFI argument, generalizing the torch-specific CUDA stream detection to any ML framework.

## Context

The FFI's argument packing (`make_args`) already detected `torch.Tensor` on CUDA devices and queried the current stream via `torch._C._cuda_getCurrentRawStream`. However, this was torch-specific: other frameworks (JAX, CuPy, etc.) that implement `__dlpack__` could not participate in automatic stream context exchange. Each new framework would require adding framework-specific detection code to `make_args`.

## Alternatives

### 1. Duck-typing protocol on the Python object (chosen)

Any object implementing `__dlpack__` can optionally implement `__tvm_ffi_env_stream__() -> int` to provide a stream handle. The protocol is queried during `make_args` for non-CPU DLPack objects.

- Pros: Zero coupling to specific frameworks. Fully opt-in. No TVM FFI code changes needed when new frameworks adopt the protocol.
- Cons: No compile-time enforcement (duck typing). The return value must be a raw pointer as integer, which is fragile. Silent no-op if protocol is not implemented.

### 2. Framework-specific detection in make_args

Add `if isinstance(arg, jax.Array)` / `if isinstance(arg, cupy.ndarray)` branches alongside the existing torch branch.

- Pros: Each framework's stream query API is used directly.
- Cons: O(frameworks) maintenance burden in TVM FFI. Requires importing each framework. New frameworks require code changes to TVM FFI.

### 3. Explicit stream passing as function argument

Require callers to pass the stream as an additional FFI function argument.

- Pros: Fully explicit, no side channel.
- Cons: Breaking ABI change (all kernels need an extra parameter). Incompatible with the packed calling convention's fixed argument layout.

### 4. Global stream registry (register per-framework query functions)

A registry mapping framework names to stream query callables.

- Pros: Framework-agnostic registration.
- Cons: Still requires framework-specific registration code somewhere. More complex than duck typing for the same extensibility.

## Decision

Alternative 1. The protocol is integrated in the `hasattr(arg, "__dlpack__")` branch of `make_args`:

- **Non-CPU guard**: Only queried when `device.device_type != kDLCPU`.
- **First-writer-wins**: Only the first non-CPU DLPack argument with stream info sets the context (`ctx_dev_type[0] == -1`).
- **Variable rename**: The converted tensor is stored as `ffi_arg` (not `arg`) to preserve the original object for protocol access.
- **Contract**: `__tvm_ffi_env_stream__()` must return a Python integer castable to `TVMFFIStreamHandle` (`void*`).

The C API rename `TVMFFIEnvSetStream` -> `TVMFFIEnvSetCurrentStream` was done in the same commit (`db98729`) for naming symmetry. However, in commit `f81ab9c`, the names were reverted back to the shorter form: `TVMFFIEnvSetStream`/`TVMFFIEnvGetStream`. The final stable names are the short form, aligning with CUDA API naming conventions.

## Consequences

- Frameworks beyond PyTorch can participate in automatic stream context exchange by implementing a single method.
- The `DLTensorTestWrapper` Cython class was added for testing the round-trip.
- No breaking change to existing callers: objects without `__tvm_ffi_env_stream__` are handled exactly as before.

## Related Design Docs

- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Argument packing priority order
- [`.knowledge/designs/0011-extra-api-tier.md`](../designs/0011-extra-api-tier.md) -- Stream context APIs
- [`.knowledge/ADRs/0020-thread-local-stream-context.md`](0020-thread-local-stream-context.md) -- Thread-local stream storage
- Commit: `.knowledge/commits/2025-09-09-db987299f74aadcb4d8003cc6009cb67a75662c8.md` + `db98729`
