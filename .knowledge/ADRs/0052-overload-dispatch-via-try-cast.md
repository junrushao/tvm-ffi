---
scope:
  - "0006-reflection"
  - "0004-function-system"
---
# Use try_cast-Based Dynamic Dispatch for Overloaded FFI Methods

**TL;DR**: Overloaded FFI object methods are dispatched at runtime by attempting `try_cast` (lenient conversion) on each argument in registration order, choosing the first overload whose argument types all match. This favors simplicity over most-specific-match semantics.

## Context

FFI object types sometimes need multiple method signatures for the same name (e.g., a `lookup` method that accepts either `int` or `String`). C++ templates and overload resolution are not available at the FFI boundary because all calls go through the packed `(const AnyView*, int32_t, Any*)` convention.

Usecases:
- An object method `get` that accepts either an integer index or a string key.
- A constructor `__init__` that supports multiple argument-count signatures.
- Interop scenarios where Python callers pass dynamically-typed arguments.

Design Decisions:
- **First-match via `try_cast`**: Overloads are tried in registration order. For each overload, every argument is checked via `try_cast<T>()` (lenient conversion). The first overload where all arguments succeed is selected.
- **`OverloadObjectDef<Class>`** is the registration entry point, replacing `ObjectDef<Class>` when overloading is needed. It tracks registered method names and chains subsequent registrations to the same `OverloadedFunction`.
- **`Function::FromPackedInplace`** stores the `OverloadedFunction` inline in `FunctionObj` memory, avoiding a separate heap allocation for the dispatch state.

**Why try_cast (lenient) instead of as (strict)?**
- `as<T>()` (strict) rejects implicit conversions (e.g., `int` does not match `float`). This would make overloading impractical: `f(int)` and `f(float)` would require callers to pass exactly the right type.
- `try_cast<T>()` (lenient) allows natural coercions (int -> float, String -> DLDataType), matching Python's dynamic typing expectations.
- The trade-off: overlapping lenient conversions resolve by registration order, not specificity. Registering `f(int)` before `f(float)` means an `int` argument always dispatches to `f(int)`, even though `f(float)` would also accept it.

**Why first-match instead of most-specific-match?**
- Most-specific-match (like C++ overload resolution) requires a subtyping lattice and complex ranking rules. The FFI type system is flat (type indices, not a hierarchy for value types).
- First-match is O(n) in the number of overloads with a trivial implementation. Most objects have 1-3 overloads per method.
- The `num_args_` fast check (integer comparison before any try_cast) eliminates most candidates immediately.

**Alternatives considered:**
1. **Separate method names** (e.g., `get_by_int`, `get_by_str`): No dispatch needed, but breaks Pythonic APIs and requires callers to know the argument type.
   - Pros: Zero dispatch overhead, unambiguous.
   - Cons: Poor API ergonomics, especially from Python.
2. **Python-side dispatch only** (generic Python wrapper that dispatches based on `isinstance`): Keeps C++ simple but duplicates logic per language binding.
   - Pros: No C++ complexity.
   - Cons: Dispatch logic duplicated per language; Rust/C bindings would need their own dispatch.

## Implementation Notes

- `OverloadObjectDef<Class>` inherits privately from `ObjectDef<Class>`, reusing field/method registration machinery but overriding method registration to support chaining.
- Each `OverloadedFunction` stores overloads in a `vector<pair<unique_ptr<OverloadBase>, FnPtr>>`. The `FnPtr` is stored alongside the `unique_ptr` to de-virtualize the dispatch call (one fewer pointer indirection).
- When no overloads are registered (common case), `OverloadedFunction::operator()` falls through to `unpack_call` directly, adding zero overhead versus non-overloaded `ObjectDef`.
- Error messages on dispatch failure enumerate all overloads with their type signatures and the specific argument that caused each mismatch.

## Related Design Docs

- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- Reflection system and overload dispatch section
- [`.knowledge/designs/0004-function-system.md`](../designs/0004-function-system.md) -- Function::FromPackedInplace
- [`.knowledge/ADRs/0008-as-strict-cast-lenient.md`](0008-as-strict-cast-lenient.md) -- as/try_cast/cast distinction that underpins the dispatch decision
