---
scope:
  - "0001-c-abi"
  - "0003-object-system"
---
# void* Deleter Signature for Object System

**TL;DR**: The `FObjectDeleter` callback type was changed from `void (*)(TVMFFIObject*, int)` to `void (*)(void*, int)`, enabling more flexible custom allocators without requiring a cast to the specific object header type.

## Context

The `FObjectDeleter` typedef and the corresponding `TVMFFIObject.deleter` field in the C ABI were typed as `void (*)(TVMFFIObject*, int)`. This required custom allocators to accept the specific object header type, even though the deleter always knows the concrete type at allocation time (captured via the CRTP `Handler` in `SimpleObjAllocator`). The typed signature added an unnecessary constraint without providing type safety benefits, since the deleter body always casts to the concrete type anyway.

## Decision

Change the signature to `void (*)(void*, int)`. The `TVMFFIObject.deleter` field in `c_api.h` follows suit. This is a transparent ABI change because the previous `TVMFFIObject*` parameter was already treated as a generic pointer inside all deleter implementations.

This change was made alongside the Doxygen documentation effort in commit `24125d0` (#18279), which also moved `SimpleObjAllocator` and `ObjAllocatorBase` into `namespace details`.

## Consequences

- Callers that store or invoke the deleter directly must update the cast from `TVMFFIObject*` to `void*`.
- Custom allocators gain flexibility: they can pass any pointer through the deleter without an upcast.
- The C struct `TVMFFIObject` also changed to use anonymous typedef (removed self-referencing tag name), which is transparent to all users who reference it by typedef name.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- TVMFFIObject struct definition
- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- SimpleObjAllocator, deleter dispatch
- Commit: `.knowledge/commits/2025-09-07-24125d0ac466beb67965c1dd9ae23f2a71f424ad.md` + `24125d0`
