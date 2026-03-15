---
scope:
  - "0017-dlpack-interop"
  - "0015-python-ffi-call-dispatch"
---
# ADR-0021: Replace Per-Attribute Function Pointers with DLPackExchangeAPI Struct

**TL;DR**: Replaces the three separate class-level dunder attributes (`__c_dlpack_from_pyobject__`, `__c_dlpack_to_pyobject__`, `__c_dlpack_tensor_allocator__`) with a single `__dlpack_c_exchange_api__` attribute pointing to a versioned `DLPackExchangeAPI` struct, per DLPack proposal #175.

## Context

The DLPack speed-converter protocol originally required setting three separate integer attributes on tensor classes, each holding a C function pointer address. This had several problems:
- **Class attribute pollution**: Three dunders per framework tensor class.
- **Atomic discovery impossible**: A consumer cannot tell if all three attributes are set atomically; partial registration could cause crashes.
- **No ABI evolution path**: Adding new function pointers (e.g., `current_work_stream`, `dltensor_from_py_object_no_sync`) would require new attribute names, growing the surface unboundedly.
- **No versioning**: Consumers cannot detect which version of the protocol a framework implements.

Usecases:
- Framework authors implementing DLPack exchange for their tensor types
- FFI dispatch code discovering all conversion capabilities atomically
- Future DLPack protocol evolution without breaking existing implementations

Design Decisions:
- Bundle all function pointers into a single `DLPackExchangeAPI` struct exposed via one `__dlpack_c_exchange_api__` class attribute.
- Include `DLPackExchangeAPIHeader` with `{version, prev_api}` for ABI evolution. `prev_api` is a linked list pointer to older struct versions.
- All conversion functions use `_no_sync` naming, decoupling stream synchronization from tensor import/export. Stream querying is handled by the new `current_work_stream` callback.
- Add `dltensor_from_py_object_no_sync` for zero-copy, zero-refcount metadata inspection (fills a caller-owned `DLTensor` struct).

## Implementation Notes
- `DLPackExchangeAPI` is defined in `dlpack/dlpack.h` (the DLPack submodule).
- Cython bindings in `base.pxi` mirror the struct and all function pointer typedefs.
- The `TVMFFIPyArgSetterDLPackExchangeAPI_` setter reads the struct pointer from `type(arg).__dlpack_c_exchange_api__`, casts to `DLPackExchangeAPI*`, and calls `managed_tensor_from_py_object_no_sync` directly.
- `TorchDLPackExchangeAPI` inherits from `DLPackExchangeAPI` and implements all five members as static member functions, initialized in the constructor. The singleton is exposed via `TorchDLPackExchangeAPIPtr() -> int64_t`.
- **Attribute value migrated from `int` to `PyCapsule`** (7f3bb77): The `__dlpack_c_exchange_api__` attribute value was originally a raw `int` (the pointer address). In 7f3bb77, it was upgraded to a `PyCapsule` with capsule name `"dlpack_exchange_api"` for type safety. Backward compatibility is preserved: the Cython accessor `_get_dlpack_exchange_api` accepts both `int` and `PyCapsule`. When an existing `int` value is detected, `load_torch_c_dlpack_extension()` eagerly upgrades it to `PyCapsule` via `_create_dlpack_exchange_api_capsule`.
- **Attribute renamed** (5393647): `__c_dlpack_exchange_api__` -> `__dlpack_c_exchange_api__` across full stack. Backward compat: `_check_and_update_dlpack_c_exchange_api()` detects old name and auto-creates new one. Environment variable renamed: `TVM_FFI_SKIP_C_DLPACK_EXCHANGE_API` -> `TVM_FFI_SKIP_DLPACK_C_EXCHANGE_API`.
- Evidence: 22a78943b783 (initial), ef54bdac61f4 (static member refactor), 965fc4642f3e (tests), 7f3bb77 (int-to-PyCapsule migration), 5393647 (rename)

## Related Design Docs
- [0017-dlpack-interop.md](../designs/0017-dlpack-interop.md) -- Full DLPack interop design
- [0015-python-ffi-call-dispatch.md](../designs/0015-python-ffi-call-dispatch.md) -- Dispatch system that consumes the exchange API
