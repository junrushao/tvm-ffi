---
scope:
  - "0001-c-abi"
  - "0002-any-system"
  - "0003-object-system"
  - "0004-function-system"
---
# Unified Packed Function and Object System

**TL;DR**: The FFI unifies the packed function calling convention with the object type system, so that `Function` is an `Object` subclass and all values (POD and objects alike) are passed through the same `Any`/`AnyView` type-erased containers. This eliminates the prior need for separate boxed-type workarounds (e.g., `Array<int>` now works directly).

## Context

In earlier TVM designs, the PackedFunc system and the Object system were separate subsystems. PackedFunc used `TVMValue` (a C union) and `type_code` for type erasure, while Object used ref-counted `ObjectPtr` with a type index. This separation led to:

1. **Duplicated type erasure**: Two different mechanisms for the same purpose.
2. **Boxed-type workarounds**: Containers like `Array<int>` required boxing integers into wrapper objects because PackedFunc could not natively carry POD values inside the object system.
3. **Inconsistent lifetime management**: PackedFunc arguments did not participate in ref-counting, leading to subtle lifetime bugs at language boundaries.

The Unified Packed and Object RFC (tvm-rfcs/0097) proposed merging these into a single system.

Usecases:
- Passing `int`, `float`, `bool` values and `Object` references through the same calling convention without boxing.
- Containers (`Array<T>`, `Map<K,V>`) that hold `Any` elements, storing both POD values and objects uniformly.
- Cross-language function dispatch where the same function can accept and return any type.

Design Decisions:
- **Merge PackedFunc into Object system**: `FunctionObj` inherits from `Object`, making functions ref-counted objects that can be stored in `Any`, passed as arguments, and managed by the same lifetime system as all other objects.
- **Unified type index space**: `TVMFFITypeIndex` covers both POD types (`[0, 64)`) and object types (`[64, +inf)`). The `Any`/`AnyView` container uses `type_index` to distinguish them, with `type_index >= kTVMFFIStaticObjectBegin` indicating a heap object.
- **Any replaces TVMValue+type_code**: The 16-byte `TVMFFIAny` struct replaces the old `TVMValue` union + separate `type_code` field. The `type_index` is embedded in the first 4 bytes of the struct, and the value/pointer occupies the remaining 8 bytes (with 4 bytes of padding/reserved).

**Alternatives considered**:

1. **Keep PackedFunc and Object separate**: Simpler to implement incrementally, but perpetuates the boxing problem and duplicated type erasure. Rejected because the long-term maintenance cost exceeds the migration cost.
2. **Use a different unification strategy (e.g., everything is Object)**: Would require boxing all POD values into heap objects. Rejected because boxing overhead for integers and floats in hot paths (tensor shape computation, loop bounds) is unacceptable.

**Consequences**:
- The unified system is more complex (a single 16-byte value can be a POD, an object pointer, or a non-owning reference).
- The `TypeTraits` protocol adds compile-time complexity for type conversion.
- `Array<int>` and `Map<String, int>` work natively without boxing.

**Rollback/migration**: Since this is the foundational commit, rollback is not applicable. Future changes to the Any layout would require coordinating all language bindings simultaneously.

## Implementation Notes

- `TVMFFIAny` struct layout: 4-byte `type_index` + 4-byte `small_len` + 8-byte union. The `small_len` field is reserved for future small-string optimization.
- `FunctionObj` inherits both `Object` (for ref-counting and type system participation) and `TVMFFIFunctionCell` (for the C-ABI-compatible `safe_call` pointer).
- The packed calling convention is `(const AnyView* args, int32_t num_args, Any* rv)` -- arguments are non-owning views, the return value is owning.
- Evidence: `include/tvm/ffi/c_api.h` (TVMFFITypeIndex, TVMFFIAny), `include/tvm/ffi/any.h` (Any/AnyView), `include/tvm/ffi/function.h` (FunctionObj), commit `7d34eb8`.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI that implements this unification
- [`.knowledge/designs/0002-any-system.md`](../designs/0002-any-system.md) -- Any/AnyView as the unified value container
- [`.knowledge/designs/0004-function-system.md`](../designs/0004-function-system.md) -- FunctionObj as an Object subclass
