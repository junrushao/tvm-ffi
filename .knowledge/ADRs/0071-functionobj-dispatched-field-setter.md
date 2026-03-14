---
scope:
  - "0001-c-abi"
  - "0006-reflection"
---
# FunctionObj-Dispatched Field Setter

**TL;DR**: The `TVMFFIFieldInfo.setter` field is changed from `TVMFFIFieldSetter` (static C function pointer) to `void*`, and a new flag `kTVMFFIFieldFlagBitSetterIsFunctionObj` (bit 11) controls whether the setter is interpreted as a raw function pointer or a `FunctionObj` handle invoked via `TVMFFIFunctionCall`.

## Context

The existing `TVMFFIFieldSetter` signature `int (*)(void*, const TVMFFIAny*)` is a static C function pointer. It works well for the default case where `FieldSetter<T>` is a compile-time-generated template instantiation. However, it cannot represent custom setter logic defined at runtime -- for example, a Python-side `__ffi_convert__` wrapped in a `FunctionObj` that performs type coercion before assigning to a field.

This limitation was a blocker for supporting user-defined field validators and custom type conversion in Python-defined types.

Usecases:
- Python-defined types that need custom field validation/conversion via `FunctionObj`
- Runtime-defined setter logic that cannot be expressed as a static C function pointer
- Downstream commits that wire `__ffi_convert__` through the reflection setter mechanism

Design Decisions:
- **`void*` setter type**: `TVMFFIFieldInfo::setter` is changed from `TVMFFIFieldSetter` to `void*` to accommodate both representations. When the new flag is clear, the `void*` is cast to `TVMFFIFieldSetter`. When set, it is a `TVMFFIObjectHandle` pointing to a `FunctionObj`.
- **New flag `kTVMFFIFieldFlagBitSetterIsFunctionObj` (bit 11)**: The flag is stored in the existing `TVMFFIFieldInfo::flags` bitmask. This avoids adding a new field to the ABI-critical struct.
- **Central dispatch helper `CallFieldSetter`**: A new inline function in `accessor.h` checks the flag and dispatches to either the raw function pointer or `TVMFFIFunctionCall`. All setter call sites are updated to use `CallFieldSetter` instead of calling `setter` directly.
- **FunctionObj retention via `any_pool_`**: When `TypeTable::RegisterTypeField` encounters a FunctionObj setter (flag set), it wraps the handle in an `Any` and stores it in `any_pool_` to maintain ref-counting without a custom destructor.
- **Cython fast-path update**: `TVMFFIPyCallFieldSetter` in `tvm_ffi_python_helpers.h` gains a `field_flags` parameter and mirrors the same dispatch logic.
- **Value-initialization for locals**: Both `CallFieldSetter` and the Cython helper use value-initialization (`TVMFFIAny args[2]{}`, `TVMFFIAny result{}`) instead of manual zeroing, reducing boilerplate.

## Implementation Notes

- **ABI-breaking**: `TVMFFIFieldInfo::setter` type change from `TVMFFIFieldSetter` to `void*` breaks code that reads `setter` directly (uncommon outside the framework).
- Default path (flag clear) has zero overhead -- the `void*` is simply cast back to `TVMFFIFieldSetter`.
- FunctionObj path adds one level of indirection via `TVMFFIFunctionCall` but enables arbitrary callable setters.
- The `FunctionObj` is invoked with signature `(field_addr_as_OpaquePtr, value_as_AnyView)`.
- Rust bindings (`tvm-ffi-sys/src/c_api.rs`) updated: `TVMFFIFieldInfo::setter` type changed from `TVMFFIFieldSetter` to `*mut c_void`.
- Evidence: `.knowledge/commits/2026-03-10-10dc59d196c8a88371a73a3fdc43d3400c0c0427.md` + `10dc59d`

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI where TVMFFIFieldInfo is defined
- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- Reflection system field setter mechanism
- [`.knowledge/designs/0022-rust-bindings.md`](../designs/0022-rust-bindings.md) -- Rust bindings that consume TVMFFIFieldInfo
