---
adr: "0017"
title: "Opaque PyObject Wrapping for Unrecognized Python Types in FFI"
status: "accepted"
date: "2025-09-05"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python)"
  - "Downstream library authors"
tags:
  - "architecture"
  - "python-interop"
  - "type-system"
source_commits:
  - "91d69f0658eef18fd9c99d4ac195ad5319db3787"
source_ledgers:
  - ".memory/commits/2025-09-05-91d69f0658eef18fd9c99d4ac195ad5319db3787.md"
---

# ADR-0017: Opaque PyObject Wrapping for Unrecognized Python Types in FFI

## TL;DR
- Python objects that do not match any known FFI type are now automatically wrapped as opaque ref-counted FFI objects (`OpaquePyObject`) instead of raising `TypeError`.
- This enables passing arbitrary Python objects through FFI function boundaries without requiring explicit type registration.

## Status
Accepted

## Context
Before this change, passing a Python object of an unrecognized type (e.g., a user-defined class, a framework-specific object) to an FFI function raised `TypeError` in the Cython `make_args()` function. This forced users to either register every Python type they wanted to pass through the FFI, or manually wrap objects. In practice, many FFI use cases involve storing or forwarding opaque Python objects (callbacks, configuration objects, framework-specific types) through C++ code that does not need to inspect their contents.

## Decision Drivers
- Enable interop with frameworks that define their own types (e.g., custom training loop objects, optimizer states) without requiring registration.
- Preserve Python object identity and lifecycle through the FFI round-trip.
- Maintain type safety: opaque objects should not be confused with typed FFI objects.
- Minimize overhead for the common case (known types should not be affected).

## Decision
Introduce `kTVMFFIOpaquePyObject` (type index 74) as a new static object type. In the Cython `make_args()` function, unrecognized Python types are wrapped as `OpaquePyObject` instead of raising `TypeError`. In `make_ret()`, objects with this type index are unwrapped back to the original Python object.

The implementation consists of:
1. **C API**: `TVMFFIObjectCreateOpaque(handle, type_index, deleter, out)` creates an opaque object wrapping a `void*` handle.
2. **C++ implementation**: `OpaqueObjectImpl` (in `src/ffi/object.cc`) is a simple `Object` subclass holding a `void* handle` and a cleanup deleter.
3. **Cython layer**: `OpaquePyObject` cdef class exposes `.pyobject()` to retrieve the original Python object. The shared deleter (`tvm_ffi_pyobject_deleter`) decrements the Python reference count when the FFI object is freed.
4. **Round-trip identity**: The original `PyObject*` pointer is stored directly, so `obj is original_obj` holds after round-tripping through FFI.

## Alternatives Considered
### Require explicit registration for all Python types
- Pros: Full type safety. No "escape hatch" for arbitrary types.
- Cons: Impractical for frameworks with many types. Requires registration code for every type that might be passed through FFI. Breaks the "just works" philosophy for common interop patterns.

### Store as raw opaque pointer (kTVMFFIOpaquePtr) without ref counting
- Pros: Simpler. Reuses existing type index.
- Cons: No lifecycle management. The Python object could be garbage-collected while the FFI holds a reference. Would require manual reference counting in user code.

### Use Any with a special tag (not a separate type index)
- Pros: No new type index needed.
- Cons: Cannot be stored in containers (which require object-typed values). Breaks the type index dispatch in `make_ret()`.

## Why This Option Won
- Automatic wrapping eliminates the most common FFI interop pain point (TypeError on unknown types).
- Ref-counted lifecycle management prevents use-after-free without user intervention.
- A dedicated type index (74) enables clean dispatch in both `make_args()` and `make_ret()`.
- The shared deleter pattern (`tvm_ffi_pyobject_deleter`) is already used for Function callbacks, so the infrastructure is proven.

## Consequences
### Positive
- Python users can pass arbitrary objects through FFI without registration or manual wrapping.
- Object identity is preserved through round-trips.
- The opaque wrapper integrates naturally with the existing object system (ref counting, container storage).

### Negative
- Silent wrapping: previously, passing an unsupported type raised a clear `TypeError`. Now it silently succeeds, which could mask bugs where the user intended to pass a specific FFI type but accidentally passed the wrong object.
- New type index (74) in the static range, consuming one of the limited slots.

### Risks
- Silent wrapping of wrong types could lead to confusing downstream errors (e.g., C++ code receiving an opaque object when it expected a typed one). Mitigated by the fact that C++ code will get an `OpaqueObjectImpl` which can only be inspected via `handle` -- any typed access attempt will fail with a type error.

## Implementation Notes
- `kTVMFFIOpaquePyObject = 74` in `TVMFFITypeIndex` enum.
- `TVMFFIOpaqueObjectCell` struct in `c_api.h` holds the opaque handle and type index.
- `TVMFFIObjectCreateOpaque` C API function creates opaque objects.
- In Cython `make_args()`, the fallback branch (previously `raise TypeError`) now creates an `OpaquePyObject`.
- In Cython `make_ret()`, `kTVMFFIOpaquePyObject` returns the unwrapped Python object.
- The `tvm_ffi_callback_deleter` was renamed to `tvm_ffi_pyobject_deleter` to reflect its broader role (shared between Function callbacks and opaque objects).

## Validation
- Tests verify round-trip identity: pass a custom Python class through FFI and assert `is` identity on return.
- Tests verify lifecycle: the opaque object holds a reference to the Python object, preventing premature GC.

## Migration and Rollback
- No migration needed for existing code. This is purely additive behavior.
- Rollback would require removing the type index and reverting `make_args()` to raise `TypeError` on unknown types.

## Related Design Docs
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)
- [.memory/designs/0011-cython-binding-layer.md](.memory/designs/0011-cython-binding-layer.md)

## Related Diagrams
- [.memory/diagrams/0009-cython-binding-type-marshaling.md](.memory/diagrams/0009-cython-binding-type-marshaling.md)

## Evidence Matrix
- `kTVMFFIOpaquePyObject = 74` type index -> `.memory/commits/2025-09-05-91d69f0658eef18fd9c99d4ac195ad5319db3787.md` + `91d69f0` + `include/tvm/ffi/c_api.h`
- `TVMFFIObjectCreateOpaque` C API -> `91d69f0` + `include/tvm/ffi/c_api.h`
- `OpaqueObjectImpl` C++ class -> `91d69f0` + `src/ffi/object.cc`
- `OpaquePyObject` Cython class -> `91d69f0` + `python/tvm_ffi/cython/object.pxi`
- `make_args()` fallback wrapping -> `91d69f0` + `python/tvm_ffi/cython/function.pxi`
- `tvm_ffi_pyobject_deleter` shared deleter -> `91d69f0` + `python/tvm_ffi/cython/function.pxi`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Consider adding a warning or debug log when an object is silently wrapped as opaque, to help users detect accidental wrapping.
- Evaluate whether Rust bindings should support a similar opaque wrapping mechanism.
