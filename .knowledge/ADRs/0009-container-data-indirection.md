---
scope:
  - "0005-containers"
  - "0001-c-abi"
---
# Container Data Indirection (data_ / data_deleter_)

**TL;DR**: `ArrayObj` and `MapObj` now have `void* data_` and `void (*data_deleter_)(void*)` fields, decoupling element storage from the object itself. This enables non-inplace allocation strategies and cross-DLL-safe deallocation.

## Context

Previously, `ArrayObj` elements were accessed solely through `InplaceArrayBase::AddressOf(0)`, tightly coupling element access to inplace (trailing) storage. This prevented external buffers and made cross-DLL deallocation unsafe -- memory allocated in one shared library could be freed by a different allocator in another library.

Usecases:
- `DenseMapObj` allocates a separate `Block[]` array via `new[]`. Without `data_deleter_`, the `delete[]` call could use a different allocator than the `new[]` if the map was created in a different DLL.
- Future non-inplace arrays (e.g., mmap-backed, externally owned DLPack-style buffers) need `data_` to point outside the object.

Design Decisions:
- **`void* data_` pointer**: Points to element storage. For inplace arrays, set to `AddressOf(0)` at creation time. For `DenseMapObj`, points to a separately heap-allocated `Block` array.
- **`void (*data_deleter_)(void*)` callback**: Called during object destruction to free the data buffer. `nullptr` for inplace arrays (no separate deallocation needed). `BlockDeleter` for `DenseMapObj`.
- **`InplaceArrayBase` template parameter change**: `ArrayObj` uses `TVMFFIAny` (not `Any`) as the element type, preventing `InplaceArrayBase` from invoking `Any` destructors. `SmallMapObj` uses `KVRawStorageType` (POD struct with `TVMFFIAny first; TVMFFIAny second;`).

**Alternatives considered**:

1. **Keep pure inplace arrays, add separate `ExternalArrayObj` subclass**: Two array types adds complexity to every call site that dispatches on array type.
2. **`std::unique_ptr<void, Deleter>`**: Standard-library solution but adds overhead (size of unique_ptr) and interacts poorly with C ABI struct layout requirements.

**Consequences**:
- ABI-breaking change to `ArrayObj` and `MapObj` field layouts.
- One additional pointer and one function pointer per array/map instance (16 bytes overhead).
- `DenseMapObj::slots_` now stores actual slot count (not `n_slots - 1`). Probing uses `% slots_` instead of `& slots_`.
- Cross-DLL deallocation is safe: `data_deleter_` is set at allocation time in the same compilation unit as `new[]`.

## Implementation Notes

- `ArrayObj::at()` returns `const Any&` (by reference, via `data_` + offset), not `const Any` (by value).
- `DenseMapObj::BlockDeleter` is a static function that casts `void*` back to `Block*` and calls `delete[]`.
- `SmallMapObj::~SmallMapObj()` explicitly destructs elements; `InplaceArrayBase` template param `KVRawStorageType` prevents double-destruct.
- Evidence: `include/tvm/ffi/container/array.h`, `include/tvm/ffi/container/map.h`, commit `7e0a4b3`.

## Related Design Docs

- [`.knowledge/designs/0005-containers.md`](../designs/0005-containers.md) -- Container system
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI layout stability
