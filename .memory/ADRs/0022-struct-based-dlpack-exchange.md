---
adr: "0022"
title: "Struct-Based DLPack Exchange Protocol for Zero-Copy Tensor Transfer"
status: "accepted"
date: "2025-09-12"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
  - "dlpack community"
informed:
  - "FFI binding authors (Python)"
  - "PyTorch interop users"
tags:
  - "performance"
  - "dlpack"
  - "tensor-interop"
source_commits:
  - "38d2cdaa03adc26a630e9cc3cc99b3c7e9f55097"
  - "f81ab9c25ae4d2a42706747c50c5c410c51d6cdd"
  - "4dee97f1b6473f32faeb8cd24fb2c960f3b17190"
  - "22a78943"
  - "9829dec"
  - "f679fe5"
  - "ef54bda"
  - "3373853"
source_ledgers:
  - ".memory/commits/2025-09-11-38d2cdaa.md"
  - ".memory/commits/2025-09-12-f81ab9c2.md"
  - ".memory/commits/2025-09-12-4dee97f1.md"
  - ".memory/commits/2025-10-11-22a78943.md"
  - ".memory/commits/2025-10-15-9829dec.md"
  - ".memory/commits/2025-10-15-f679fe5.md"
  - ".memory/commits/2025-10-15-ef54bda.md"
  - ".memory/commits/2025-10-16-3373853.md"
---

# ADR-0022: Struct-Based DLPack Exchange Protocol for Zero-Copy Tensor Transfer

## TL;DR
- DLPack tensor exchange between Python frameworks and TVM FFI is upgraded from PyCapsule-based protocol to a C-struct-based protocol (`DLPackExchangeAPI`), eliminating ~2-3 microseconds of PyCapsule allocation/destruction overhead per tensor argument.
- The exchange API struct bundles `from_pyobject`, `to_pyobject`, and `managed_tensor_allocator` function pointers, enabling symmetric import/export and pluggable allocators entirely in C.

## Status
Accepted

## Context
The standard DLPack exchange protocol (`__dlpack__` / `__dlpack_device__`) relies on Python PyCapsule objects to wrap `DLManagedTensor` pointers. Each tensor argument in an FFI call requires:
1. Creating a PyCapsule on the source side.
2. Calling into Python to invoke `__dlpack__`.
3. Extracting the `DLManagedTensor*` from the capsule.
4. Wrapping it as an FFI Tensor.
5. Destroying the capsule.

For ML inference hot paths that pass 1-3 tensor arguments per call, this PyCapsule overhead (measured at ~2-3 microseconds per tensor on modern hardware) is significant. Additionally, the standard protocol does not provide a mechanism for the consumer to specify a custom allocator for output tensors, forcing allocator-mismatched copies.

## Decision Drivers
- Tensor exchange must be zero-copy (no data copying, only metadata exchange).
- The protocol must work without touching Python objects during the actual exchange (pure C function pointer calls).
- The protocol must be symmetric: both import (framework -> FFI) and export (FFI -> framework) must be fast.
- The protocol must support pluggable tensor allocators so output tensors can be allocated in the caller's framework memory.
- The protocol must be optional and backward-compatible: objects without the C exchange API fall back to the standard PyCapsule `__dlpack__` protocol.

## Decision
Adopt the `DLPackExchangeAPI` struct from the dlpack specification as the exchange mechanism. The struct bundles three function pointers:
- `from_pyobject(PyObject* tensor, DLManagedTensor** out)`: Convert a Python tensor to a DLManagedTensor without PyCapsule.
- `to_pyobject(DLManagedTensor* tensor, PyObject** out)`: Convert a DLManagedTensor back to a Python tensor without PyCapsule.
- `managed_tensor_allocator`: A callback for allocating DLManagedTensor structs compatible with the framework's memory management.

Python tensor classes expose the struct via a `__dlpack_c_exchange_api__` attribute (a PyCapsule wrapping the `DLPackExchangeAPI*`). This attribute is checked once per Python type by the `TVMFFIPyArgSetterFactory` and cached in the `TVMFFIPyArgSetter.dlpack_c_exchange_api` field.

The naming evolved through three stages:
1. `__dlpack_c_exporter__` (commit `38d2cdaa`): Initial one-way protocol.
2. `__c_dlpack_exporter__` / `__c_dlpack_importer__` (commit `f81ab9c2`): Symmetric but separate attributes.
3. `__dlpack_c_exchange_api__` (commit `4dee97f1`): Unified struct-based attribute with directional naming.

## Alternatives Considered
### Keep PyCapsule-based __dlpack__ only
- Pros: Standard protocol. No custom attributes needed. Universally supported.
- Cons: ~2-3 us PyCapsule overhead per tensor. No way to set a custom allocator. No symmetric export path.

### Use separate C function pointers (not bundled in a struct)
- Pros: Simpler per-function caching.
- Cons: Multiple attributes needed per tensor class (`__c_dlpack_from_pyobject__`, `__c_dlpack_to_pyobject__`, `__c_dlpack_tensor_allocator__`). Cannot atomically check availability. More Python attribute lookups.

### Use a Python class with C methods (hybrid approach)
- Pros: More Pythonic API. Easier introspection.
- Cons: Still requires Python dispatch. Does not eliminate the core overhead of going through Python for the exchange.

## Why This Option Won
- Single attribute lookup per type (`__dlpack_c_exchange_api__`) instead of three separate attributes.
- The struct bundles all exchange functions, enabling atomic availability checking.
- The allocator function pointer enables the FFI to produce output tensors compatible with the caller's framework (e.g., using torch's allocator for torch tensors).
- The protocol aligns with the dlpack project's direction for C-level exchange APIs.
- Backward-compatible: falls back to `__dlpack__` capsule protocol for types without the attribute.

## Consequences
### Positive
- Tensor exchange drops from ~3 us to ~0.3 us per tensor (measured via `benchmark_dlpack.py`).
- Output tensors can be allocated in the caller's framework memory via the `managed_tensor_allocator`.
- The protocol is framework-agnostic: any framework can implement `DLPackExchangeAPI`.
- PyTorch integration is provided out-of-the-box via `_optional_torch_c_dlpack.py`.

### Negative
- New dependency on the `DLPackExchangeAPI` struct layout from dlpack. If dlpack changes the struct, the caching is invalidated.
- The `_optional_torch_c_dlpack.py` module uses JIT-compiled C++ extensions for PyTorch, adding first-use latency.
- The naming went through three iterations (exporter -> c_dlpack -> exchange_api), leaving potential confusion in historical commits.

### Risks
- Struct layout mismatch: if a framework's `DLPackExchangeAPI` struct has a different layout than the dlpack header used to build the Cython extension, function pointer calls will corrupt memory. Mitigated by PyCapsule name verification.
- Thread safety of `from_pyobject`/`to_pyobject`: these C functions may touch Python objects (incrementing/decrementing reference counts). If called without the GIL, they will corrupt Python's ref count state. The current design calls them with the GIL held (argument conversion happens before GIL release in `FuncCall`).

## Implementation Notes
- `DLPackExchangeAPI` struct is defined in `3rdparty/dlpack/include/dlpack/dlpack.h`.
- The `__dlpack_c_exchange_api__` attribute is a PyCapsule with name `"dlpack_exchange_api"`.
- `_optional_torch_c_dlpack.py` checks for native PyTorch support first, falls back to JIT-compiled extension. A skip guard was added (commit `3373853`) to avoid loading the extension if `torch.Tensor` already has `__c_dlpack_exchange_api__`.
- The `TVMFFIPyCallContext.dlpack_c_exchange_api` field propagates the exchange API from argument conversion to the return path and from nested constructor calls to the parent context.
- The `managed_tensor_allocator` is set as a thread-local via `TVMFFIEnvSetDLPackManagedTensorAllocator` before the FFI call, and restored after.
- **Unified struct evolution** (commit `22a78943`): The three separate function pointers (`__c_dlpack_from_pyobject__`, `__c_dlpack_to_pyobject__`, `__c_dlpack_tensor_allocator__`) were replaced with a single `DLPackExchangeAPI` struct exposed via `__c_dlpack_exchange_api__` on `torch.Tensor`. Non-owning `DLTensor` conversion (`dltensor_from_py_object_no_sync`) and `current_work_stream` callback were added for explicit stream synchronization. DLPack submodule was bumped for proposals dlpack#174/175.
- **Old typedef cleanup** (commit `9829dec`): Custom `DLPackTensorAllocator` typedef removed from `c_api.h`, replaced by upstream `DLPackManagedTensorAllocator` from dlpack headers across C++, Python/Cython, and Rust.
- **Tensor allocator refactoring** (commit `f679fe5`): C API functions renamed: `TVMFFIEnvSetTensorAllocator` -> `TVMFFIEnvSetDLPackManagedTensorAllocator`, `TVMFFIEnvGetTensorAllocator` -> `TVMFFIEnvGetDLPackManagedTensorAllocator`. New `TVMFFIEnvTensorAlloc` C API wraps the DLPack allocator returning a `TVMFFIObjectHandle`. `Tensor::FromDLPackAlloc` replaced by `Tensor::FromEnvAlloc`.
- **Torch DLPack API refactoring** (commit `ef54bda`): Free-standing `TorchDLPack*` functions consolidated into static methods of `TorchDLPackExchangeAPI` struct.

## Validation
- `tests/python/test_dlpack_exchange_api.py` validates the full round-trip with the C exchange protocol.
- `tests/python/test_tensor.py` validates DLPack tensor creation and conversion.
- `tests/python/test_optional_torch_c_dlpack.py` validates the PyTorch-specific integration.
- `scripts/benchmark_dlpack.py` measures exchange overhead with and without the C protocol.

## Migration and Rollback
- No migration needed: existing code using `__dlpack__` continues to work.
- Frameworks can opt in by adding `__dlpack_c_exchange_api__` to their tensor classes.
- Rollback: remove the `dlpack_c_exchange_api` field from `TVMFFIPyArgSetter` and `TVMFFIPyCallContext`, and revert `function.pxi` to use only the PyCapsule path.

## Related Design Docs
- [.memory/designs/0015-python-ffi-call-optimization.md](.memory/designs/0015-python-ffi-call-optimization.md)
- [.memory/designs/0011-cython-binding-layer.md](.memory/designs/0011-cython-binding-layer.md)

## Related Diagrams
- [.memory/diagrams/0012-python-ffi-call-optimization-flow.md](.memory/diagrams/0012-python-ffi-call-optimization-flow.md)

## Evidence Matrix
- Cached `DLManagedTensorVersioned` in `TensorObj` -> `.memory/commits/2025-09-11-38d2cdaa.md` + `38d2cdaa` + `include/tvm/ffi/container/tensor.h`
- `__dlpack_c_exporter__` initial protocol -> `38d2cdaa` + `python/tvm_ffi/cython/function.pxi`
- `DLPackExchangeAPI` struct-based exchange, symmetric protocol -> `.memory/commits/2025-09-12-f81ab9c2.md` + `f81ab9c2` + `python/tvm_ffi/cython/base.pxi`, `function.pxi`
- `DLPackTensorAllocator` callback type -> `f81ab9c2` + `include/tvm/ffi/extra/c_env_api.h`
- `TVMFFIEnvSetDLPackManagedTensorAllocator` / `TVMFFIEnvGetDLPackManagedTensorAllocator` -> `f81ab9c2` + `include/tvm/ffi/extra/c_env_api.h`
- `_optional_torch_c_dlpack.py` PyTorch integration -> `f81ab9c2` + `python/tvm_ffi/_optional_torch_c_dlpack.py`
- Naming refactor to `__dlpack_c_exchange_api__` (DLPackFromPyObject / DLPackToPyObject) -> `.memory/commits/2025-09-12-4dee97f1.md` + `4dee97f1`
- Unified `DLPackExchangeAPI` struct with non-owning DLTensor and stream callback -> `.memory/commits/2025-10-11-22a78943.md` + `22a78943` + `python/tvm_ffi/cython/`, `python/tvm_ffi/_optional_torch_c_dlpack.py`
- Removed custom `DLPackTensorAllocator` typedef, adopted upstream `DLPackManagedTensorAllocator` -> `.memory/commits/2025-10-15-9829dec.md` + `9829dec` + `include/tvm/ffi/c_api.h`
- `TVMFFIEnvTensorAlloc` C API and `Tensor::FromEnvAlloc` wrapper -> `.memory/commits/2025-10-15-f679fe5.md` + `f679fe5` + `include/tvm/ffi/extra/c_env_api.h`, `include/tvm/ffi/container/tensor.h`
- `TorchDLPackExchangeAPI` static member consolidation -> `.memory/commits/2025-10-15-ef54bda.md` + `ef54bda` + `python/tvm_ffi/_optional_torch_c_dlpack.py`
- Skip loading DLPack extension if `__c_dlpack_exchange_api__` already exists -> `.memory/commits/2025-10-16-3373853.md` + `3373853` + `python/tvm_ffi/_optional_torch_c_dlpack.py`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Track dlpack project's finalization of `DLPackExchangeAPI` struct to ensure compatibility.
- Consider removing `_optional_torch_c_dlpack.py` JIT compilation once PyTorch ships native `__dlpack_c_exchange_api__` support.
- Evaluate adding JAX and CuPy `DLPackExchangeAPI` integrations.
