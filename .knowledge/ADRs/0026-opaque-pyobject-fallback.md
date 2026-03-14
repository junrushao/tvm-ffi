---
scope:
  - "0001-c-abi"
  - "0014-python-bindings"
  - "0003-object-system"
---
# Opaque PyObject Fallback for Unrecognized Python Types

**TL;DR**: The decision to silently wrap unrecognized Python types as opaque FFI objects (`OpaquePyObject`, type index `kTVMFFIOpaquePyObject = 74`) rather than raising `TypeError`, enabling arbitrary Python objects to round-trip through the FFI and be stored in containers.

## Context

Previously, passing an unrecognized Python type to an FFI function via `make_args` or `convert()` raised `TypeError`. This was inconvenient for mixed Python/C++ workflows where:
- Python objects need to be stored in `Array` or `Map` containers alongside FFI objects.
- Python callbacks need to pass arbitrary context objects through C++ code.
- Heterogeneous data structures contain a mix of FFI-native and Python-only types.

The opaque object mechanism wraps a `PyObject*` as a ref-counted FFI `Object` with `Py_INCREF` on creation and `Py_DECREF` via deleter on destruction, preserving Python reference counting semantics.

## Alternatives

### 1. Silent wrapping as OpaquePyObject (chosen)

`make_args` and `convert()` wrap any unrecognized Python type as `OpaquePyObject`. On return from C++, `make_ret_opaque_object` unwraps back to the original Python identity (`y is x`).

- Pros: Maximum interoperability. Containers can hold arbitrary Python objects. No explicit wrapping needed by users. Identity preservation across round-trips.
- Cons: Loses early error detection for genuinely mistyped arguments. Users who previously relied on `TypeError` as a type-safety guard will not get that signal.

### 2. Keep `TypeError` for unrecognized types

Require explicit wrapping via a user-visible API (e.g., `tvm_ffi.opaque(obj)`).

- Pros: Strong type safety. Accidental mistyped arguments caught at call site.
- Cons: Verbose. Breaks existing workflows that pass mixed types. Containers cannot transparently hold Python objects.

### 3. Registration mechanism for custom converters

Allow users to register `type -> converter` mappings for custom Python types.

- Pros: Flexible, opt-in, type-safe for registered types.
- Cons: More complex. Still leaves unregistered types with `TypeError`. Does not solve the general "pass any Python object through FFI" use case.

## Decision

Alternative 1. The opaque fallback is the last step in `make_args` priority order (step 20). The `convert()` function delegates to `_convert_to_opaque_object` for unknown types instead of raising `TypeError`.

Key design choices:
- `TVMFFIOpaqueObjectCell { void* handle; }` is the C ABI cell (at offset 24 from `TVMFFIObject`).
- `kTVMFFIOpaquePyObject = 74` is the static type index.
- `TVMFFIObjectCreateOpaque(handle, type_index, deleter, &out)` is the creation C API. The `type_index` parameter is validated at runtime (currently only `kTVMFFIOpaquePyObject` accepted), enabling future opaque types for other languages.
- The deleter (`tvm_ffi_pyobject_deleter`) calls `Py_DECREF` and is shared with the callback function wrapper.

## Consequences

- **Behavioral change**: `make_args` and `convert()` no longer raise `TypeError` for unrecognized types. Code that caught `TypeError` to detect unsupported types will need updating.
- **Identity preservation**: `OpaquePyObject` maintains Python object identity across FFI round-trips, verified by `y is x` assertions in tests.
- **Ref-count correctness**: `Py_INCREF` on creation, `Py_DECREF` on destruction. Tests verify explicit ref-count transitions.
- **Container support**: `Array`, `Map`, and other containers can now hold arbitrary Python objects without explicit conversion.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- TVMFFIOpaqueObjectCell, kTVMFFIOpaquePyObject
- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- make_args priority order, OpaquePyObject class
- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- Object system (OpaquePyObject is an Object subclass)
- Commit: `.knowledge/commits/2025-09-05-91d69f0658eef18fd9c99d4ac195ad5319db3787.md` + `91d69f0`
