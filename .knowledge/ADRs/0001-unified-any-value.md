---
scope:
  - "0001-c-abi-layer"
  - "0002-any-value-system"
---
# Unified 16-byte TVMFFIAny for POD and Object Storage

**TL;DR**: The decision to represent all FFI values (POD types like int/float/bool AND reference-counted objects) in a single 16-byte `TVMFFIAny` struct, replacing the previous separate `TVMValue` (8-byte union) + `type_code` (int) pair.

## Context
- The old TVM runtime used a two-field representation: `TVMValue` (an 8-byte union holding the value) + `int type_code` (identifying the type), passed as parallel arrays.
- This prevented containers like `Array<int>` because POD values could not be stored in the same slot as object pointers — arrays could only hold `TVMValue+type_code` pairs, requiring boxing for POD types.
- Cross-language function calls required passing two parallel arrays (`TVMValue* args, int* type_codes, int num_args`), complicating both the C ABI and language binding implementations.
- The "Unified Packed and Object RFC" proposed merging value and type code into a single struct.

Usecases:
- `Array<int>` stores int values directly without boxing (each element is one `TVMFFIAny` slot with `type_index=kTVMFFIInt` and `v_int64=value`).
- Packed function arguments are a single `TVMFFIAny[]` array instead of parallel `TVMValue[]` + `int[]` arrays.
- Return values from functions are a single `TVMFFIAny` instead of a (value, type_code) pair.

Design Decisions:
- **Use a 16-byte struct** with 4-byte `type_index` + 4-byte `zero_padding`/`small_str_len` union + 8-byte union.
- **Share the `type_index` field at offset 0** with `TVMFFIObject`, so type dispatch works uniformly for both on-stack values and heap objects.
- **`zero_padding`/`small_str_len` union**: For small strings (`kTVMFFISmallStr=11`, `kTVMFFISmallBytes=12`), stores the string length (0-7); for all other types, MUST be zero. This enables full 16-byte comparison in `Any::same_as`.
- **Separate AnyView (non-owning) from Any (owning)** to avoid refcount overhead on the argument-passing hot path.

## Implementation Notes
- `TVMFFIAny.type_index` is `int32_t`, matching `TVMFFIObject.type_index` at byte offset 0.
- The 8-byte union covers: `int64_t`, `double`, `void*`, `const char*`, `TVMFFIObject*`, `DLDataType`, `DLDevice`, `char[8]`, `char32_t[2]`, `uint64_t`.
- `AnyView` wraps `TVMFFIAny` without ownership. Constructing from a C++ value calls `TypeTraits<T>::CopyToAnyView` which stores the raw pointer for objects (no IncRef).
- `Any` wraps `TVMFFIAny` with ownership. Copy IncRefs objects; destructor DecRefs. Converting AnyView->Any calls `InplaceConvertAnyViewToAny` which promotes `kTVMFFIRawStr` to `kTVMFFIStr` (owned String) and IncRefs object pointers.
- The 16-byte size was chosen as a trade-off: 8 bytes is too small (cannot hold type_index alongside the value), 24+ bytes wastes cache for argument arrays.

## Related Design Docs
- [0001-c-abi-layer.md](.knowledge/designs/0001-c-abi-layer.md)
- [0002-any-value-system.md](.knowledge/designs/0002-any-value-system.md)
- [0005-type-traits.md](.knowledge/designs/0005-type-traits.md)
