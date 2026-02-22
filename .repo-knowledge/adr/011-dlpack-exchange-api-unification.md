# ADR 011: DLPack Exchange API Unification

- Status: Accepted
- Date: 2025-10-11
- Owners: Kathryn (Jinqi) Chen, Tianqi Chen

## Context

Prior to this change, the TVM FFI DLPack tensor exchange protocol required
external tensor types (e.g., `torch.Tensor`) to expose three separate
function pointer fields:

- `__c_dlpack_from_pyobject__`
- `__c_dlpack_to_pyobject__`
- `__c_dlpack_tensor_allocator__`

Each field was an integer-valued class attribute pointing to a C function.
This protocol had several problems:

1. Three separate attributes created a fragile protocol surface: if one was
   missing or mismatched, behavior was silently incorrect.
2. No versioning mechanism: future additions (e.g., stream querying) would
   require yet another attribute.
3. DLPack proposal #175 introduced a unified struct pattern that the
   ecosystem was converging on.

Additionally, multi-stream GPU execution required querying the current work
stream from external tensor types, which had no place in the existing
protocol.

## Decision

Replace the three separate function pointers with a single
`DLPackExchangeAPI` struct (`22a7894`), following DLPack proposal #175. The
struct bundles five function pointers:

```c
struct DLPackExchangeAPI {
    ManagedTensorAllocator managed_tensor_allocator;
    ManagedTensorFromPyObjectNoSync managed_tensor_from_py_object_no_sync;
    ManagedTensorToPyObjectNoSync managed_tensor_to_py_object_no_sync;
    DLTensorFromPyObjectNoSync dltensor_from_py_object_no_sync;
    CurrentWorkStream current_work_stream;
};
```

External tensor types now expose a single `__c_dlpack_exchange_api__` class
attribute (integer pointer to the struct) instead of the old three-pointer
protocol.

The `3rdparty/dlpack` submodule was updated to v1.2 to include the proposal
definitions.

## Consequences

- Positive:
  - Single versioned struct simplifies the protocol surface
  - `current_work_stream` enables safe multi-stream tensor exchange
  - Aligned with the DLPack community standard
  - Adding new capabilities in the future only requires extending the struct

- Negative:
  - Breaking change: all external tensor types using the old three-pointer
    protocol must update to `__c_dlpack_exchange_api__`
  - The torch extension (`_optional_torch_c_dlpack.py`) was rewritten to
    expose a `TorchDLPackExchangeAPI` singleton

- Migration/Rollout:
  - External tensor classes must replace `__c_dlpack_from_pyobject__`,
    `__c_dlpack_to_pyobject__`, `__c_dlpack_tensor_allocator__` with a
    single `__c_dlpack_exchange_api__` class attribute
  - The `TVM_FFI_SKIP_c_dlpack_from_pyobject` env var is still honored
  - Mitigated by pre-release status (pre-0.1.0)

## References
- Range summary: `.repo-knowledge/ranges/2025-10-31-FFA2DBF-BC0D225.md`
- Evidence commits: `22a7894`, `8377011`, `b0537f0`, `7f3bb77`, `7f3f872`
- External references: DLPack proposal #175

## Related Design Docs
- `.repo-knowledge/design/009-tensor-and-dlpack.md`
- `.repo-knowledge/design/003-c-abi-stability.md`

## Notes
The `__c_dlpack_exchange_api__` naming (with `c_` prefix) was chosen to
indicate a C-level API pointer, distinguishing it from Python-level
`__dlpack__`/`__dlpack_device__` protocols. The torch extension generates a
`TorchDLPackExchangeAPI` singleton and attaches it to `torch.Tensor` as a
class attribute. In October 2025, an AOT-compiled `torch_c_dlpack_ext` addon
package was also introduced (`f703a0c`) to avoid JIT compilation overhead.

### PyCapsule upgrade (November 2025)

In November 2025 (`7f3bb77`), the `__c_dlpack_exchange_api__` attribute was
upgraded from a raw integer pointer to a PyCapsule wrapping the same pointer.
This is safer and more Pythonic. Backward compatibility is maintained:

- The Cython `_get_dlpack_exchange_api()` helper accepts both `int` and
  PyCapsule forms.
- When loading the torch extension, integer-form attributes are eagerly
  upgraded to PyCapsule (`_create_dlpack_exchange_api_capsule()`).
- The torch extension itself still sets the integer form for backward
  compatibility with older tvm-ffi versions; the upgrade happens on the
  tvm-ffi side.

The integer fallback will eventually be removed once all consumers are
updated.
