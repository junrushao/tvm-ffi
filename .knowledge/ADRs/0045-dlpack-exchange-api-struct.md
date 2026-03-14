---
scope:
  - "0020-dlpack-exchange-acceleration"
---
# Adopt Unified DLPackExchangeAPI Struct for Tensor Exchange

**TL;DR**: Replaced the previous approach of registering three separate function pointers (`__c_dlpack_from_pyobject__`, `__c_dlpack_to_pyobject__`, `__c_dlpack_tensor_allocator__`) on framework tensor types with a single `DLPackExchangeAPI` struct pointer (`__c_dlpack_exchange_api__`), following the upstream DLPack proposal #175.

## Context

The C-level DLPack exchange bypass (ADR 0034) originally used three separate function pointers registered as `int64_t` class attributes on framework tensor types. This had several issues:

1. **Fragile protocol**: Three separate attributes must be kept in sync. Missing one silently degrades.
2. **No versioning**: No mechanism to evolve the protocol without breaking existing implementations.
3. **No stream handling**: Stream synchronization required a separate mechanism outside the exchange protocol.
4. **No non-owning path**: Every conversion required a managed tensor (ref-counted), even when a non-owning view sufficed.

The DLPack project proposed a unified struct approach (proposal #175, PR #174) that addresses all these concerns.

Usecases:
- PyTorch tensor arguments passed to TVM FFI functions at high frequency
- C++ kernel code that allocates output tensors using the caller's framework allocator
- Multi-framework pipelines where stream synchronization is critical for correctness

Design Decisions:
- Replace three separate function pointer attributes with a single `DLPackExchangeAPI` struct pointer exposed via `__c_dlpack_exchange_api__`.
- All conversion functions use `_no_sync` suffix, with explicit `current_work_stream()` for stream handling.
- Add `dltensor_from_py_object_no_sync` for non-owning `DLTensor` access without managed tensor overhead.
- Include a versioned header (`DLPackExchangeAPIHeader`) with `prev_api` linked list for backward-compatible evolution.

**Alternatives considered:**

1. **Keep separate function pointers, add more attributes**: Simpler migration but does not solve the versioning or atomicity problems. Each new capability requires yet another attribute.

2. **Use Python-level protocol methods**: Define `__c_dlpack_exchange_api__` as a Python method returning a capsule. Rejected because it reintroduces Python method dispatch overhead, defeating the purpose of the C-level bypass.

3. **Wait for upstream DLPack standardization**: The DLPack project was already converging on the struct approach. Adopting early allows TVM FFI to validate the design and provide feedback. The versioned header ensures compatibility with the eventual standard.

**Consequences:**
- Breaking change: previous separate function pointer attributes are no longer recognized. All framework integrations must update.
- The `TVMFFIPyCallContext` struct holds `const DLPackExchangeAPI*` instead of three separate pointers, simplifying the call manager.
- Stream synchronization is explicit, preventing subtle correctness bugs from implicit sync behavior.

**Rollback**: If the upstream DLPack struct diverges significantly, the `prev_api` linked list in the versioned header provides a migration path. Old implementations can be wrapped in a compatibility shim that provides the new struct layout.

## Implementation Notes
- Commit `22a7894` (#96) introduced the `DLPackExchangeAPI` struct and updated all Cython/Python exchange paths.
- The `_optional_torch_c_dlpack.py` JIT module was updated to build and register the struct instead of separate pointers.
- Updated `3rdparty/dlpack` submodule to incorporate the latest DLPack standard.

## Related Design Docs
- [`.knowledge/designs/0020-dlpack-exchange-acceleration.md`](../designs/0020-dlpack-exchange-acceleration.md)
- [`.knowledge/ADRs/0034-dlpack-c-level-exchange-protocol.md`](0034-dlpack-c-level-exchange-protocol.md) -- superseded by this ADR for the struct layout
