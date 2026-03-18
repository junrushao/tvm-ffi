---
scope:
  - "0002-object-system.md"
---
# ADR: Child-Slot Optimization for O(1) IsInstance Checks

**TL;DR**: Decision to reserve contiguous type index ranges ("child slots") for base types, enabling O(1) `IsInstance` checks via a range comparison, with fallback to ancestor-depth lookup when slots overflow.

## Context
- `IsInstance<T>(object)` is a hot-path operation in the FFI: every `Any.cast<T>()`, every function argument type check, and every container element validation calls it.
- A naive implementation requires walking the type hierarchy (O(depth) per check) or a global hash table lookup.
- The type hierarchy is a single-inheritance tree with a mix of wide hierarchies (many subtypes of a base) and narrow hierarchies (final types with no children).
- For final types, `IsInstance` is trivially a single equality check. The challenge is non-final base types.

Usecases:
- Checking if an `ObjectRef` is an instance of `ExprNode` (base class with potentially hundreds of subclasses in a compiler IR).
- Validating every element in an `Array<Expr>` satisfies the `Expr` type constraint.
- Cross-language type checking: Python passes an object to C++, C++ checks `IsInstance<FooObj>` before downcasting.

Design Decisions:
- **Reserve child slots at type registration**: Each non-final base type declares `_type_child_slots = N`. The type registration system (`TVMFFIGetOrAllocTypeIndex`) assigns the base type index `B` and reserves `[B, B+N+1)` for its subtypes.
- **O(1) range check**: `IsInstance<T>(obj)` first checks if `obj.type_index` is in `[T.RuntimeTypeIndex(), T.RuntimeTypeIndex() + T._type_child_slots + 1)`. If yes, it's an instance (O(1)).
- **Ancestor-depth fallback**: If the range check fails but `_type_child_slots_can_overflow = true`, look up the global type table: `TVMFFITypeInfo.type_ancestors[T._type_depth] == T.RuntimeTypeIndex()`. This is O(1) after the table lookup but requires the table access.
- **Strict mode**: Setting `_type_child_slots_can_overflow = false` disallows subtypes beyond the reserved range, enabling the range check to be sufficient (no fallback needed). Useful when the exact number of subtypes is known.
- **Final type fast path**: For `_type_final = true` types, `IsInstance` is a single `==` comparison. This is the common case for leaf types.

## Implementation Notes
- The check order in `details::IsObjectInstance<T>`:
  1. If `T == Object`: always true (constexpr, compiled away).
  2. If `T._type_final`: `obj.type_index == T.RuntimeTypeIndex()`.
  3. If `T._type_child_slots != 0`: range check `[begin, begin + child_slots + 1)`.
  4. If `T._type_child_slots == 0`: equality check only.
  5. If overflow allowed and range check failed: `type_ancestors[T._type_depth] == target_type_index` via `TVMFFIGetTypeInfo`.
  6. Quick reject: `obj.type_index < target_type_index` means cannot be a subclass (parent indices are always smaller).
- `constexpr` and `if constexpr` ensure dead branches are compiled away for each specialization, so final types and zero-child-slot types have zero overhead.

## Related Design Docs
- [0002-object-system.md](../designs/0002-object-system.md) -- Object hierarchy, type registration macros
- [0001-c-abi.md](../designs/0001-c-abi.md) -- TVMFFITypeInfo.type_ancestors, TVMFFIGetOrAllocTypeIndex
