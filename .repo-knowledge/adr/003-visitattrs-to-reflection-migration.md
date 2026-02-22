# ADR 003: Gradual Migration from VisitAttrs to Declarative Reflection

- Status: Accepted
- Date: 2025-06-25
- Owners: Tianqi Chen

## Context

The TVM codebase historically used a `VisitAttrs(AttrVisitor*)` virtual method
pattern for runtime introspection of object fields. Each object class
implemented `VisitAttrs` to enumerate its fields by calling visitor methods.
This pattern had several drawbacks:

1. **No static metadata**: Field names, types, and documentation were only
   available at runtime through visitor callbacks, making Python binding
   generation and serialization require executing visitor code.
2. **Search-and-stop semantics**: Some consumers of `VisitAttrs` relied on
   early-exit iteration (stopping when a specific field was found), which
   created an implicit contract between visitor and visited object.
3. **Inheritance complexity**: Derived classes had to manually call their base
   class's `VisitAttrs`, leading to boilerplate and occasional omissions.

The new reflection system (`ObjectDef<T>`) introduced in June 2025 provides
declarative field registration with rich metadata. However, migrating all
existing `VisitAttrs` implementations at once would be impractical given the
large surface area (TIR, IR builder, meta_schedule, and other modules).

## Decision

Adopt a **gradual migration** strategy with explicit bridge functions:

1. **`ForEachFieldInfoWithEarlyStop`** (`69f2484`): A field iteration function
   that accepts a `bool`-returning callback, stopping when the callback returns
   `true`. This directly maps to the search-and-stop semantics of the old
   `VisitAttrs` pattern, allowing consuming code to switch from `VisitAttrs` to
   reflection without changing its control flow.

2. **Base-class field pointer support** (`f7311e4`): `ObjectDef::def_ro` and
   `def_rw` accept `T BaseClass::*` field pointers (with
   `static_assert(std::is_base_of_v<BaseClass, Class>)`), allowing derived
   classes to register inherited fields in their own `ObjectDef` definition
   without modifying the base class. This removes the need for base classes to
   be migrated first.

3. **Enum TypeTraits** (`f7311e4`): A `TypeTraits<Enum>` specialization stores
   enum values as `int64_t` in `Any`, enabling enum fields (common in TIR node
   definitions) to be registered via `def_ro`/`def_rw` without manual
   conversion wrappers.

4. **Duplicate registration guard** (`a5a08b2`):
   `TypeTable::RegisterTypeExtraInfo` throws `RuntimeError` on duplicate
   registration, catching cases where both old and new registration paths might
   fire for the same type during the transition.

The migration proceeds module by module. The first concrete migration was
applied to `tir/ir_builder/meta_schedule` in `f7311e4`.

**Legacy flags removed (July 2025):**

Three legacy static constexpr flags were removed from the `Object` base class
as part of the VisitAttrs phase-out:

- `_type_has_method_visit_attrs` removed in `da47623` (2025-07-03). This was
  the last vestige of the VisitAttrs mechanism in the Object class.
- `_type_has_method_sequal_reduce` and `_type_has_method_shash_reduce` removed
  in `e52aed5` (2025-07-29). These flags tracked whether types implemented the
  legacy `SEqualReduce`/`SHashReduce` virtual methods, which were fully
  replaced by the reflection-based `StructuralEqual`/`StructuralHash` and
  `TypeAttrDef`-based `__s_equal__`/`__s_hash__` registration.

## Consequences

- Positive: No big-bang migration required. Each module can be migrated
  independently, and both old (`VisitAttrs`) and new (reflection) mechanisms
  coexist during the transition.
- Positive: The bridge functions (`ForEachFieldInfoWithEarlyStop`) preserve the
  existing control flow of consuming code, reducing the risk of behavioral
  regressions.
- Positive: Base-class field pointer support means the migration order is
  flexible -- derived classes can be migrated before or after their base classes.
- Negative: During the transition period, some types may have both `VisitAttrs`
  and `ObjectDef` definitions, requiring care to avoid inconsistencies.
- Negative: The `ForEachFieldInfoWithEarlyStop` bridge is a transitional API;
  once all code is migrated, it may become unnecessary overhead.
- Migration/Rollout: Migrate module by module. For each type:
  1. Add an `ObjectDef<T>` block registering all fields (including inherited
     ones via base-class pointers).
  2. Update consuming code to use `ForEachFieldInfo` or
     `ForEachFieldInfoWithEarlyStop` instead of `VisitAttrs`.
  3. Remove the `VisitAttrs` implementation once all consumers are migrated.

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-06-27-1C9B17A-F7311E4.md`
  - `.repo-knowledge/ranges/2025-07-31-0966C36-0342D85.md`
- Evidence commits: `69f2484f915d95886502a1f620ea69aeed623c49`, `f7311e495820859fba26d19010fc5bda0275293d`, `a5a08b2553a8327cb821b17aa4028ff5ba52e8f0`, `da47623098927c5b7e6380b1481b4002facdd6cd`, `e52aed53526d3a6207feb940303a6cd584fdf9d1`
- External references: none

## Related Design Docs
- `.repo-knowledge/design/004-reflection-system.md`
- `.repo-knowledge/design/005-structural-equal-hash.md`

## Notes
The `static_assert` added to `ForEachFieldInfo` (`69f2484`) enforces that its
callback returns `void`, preventing accidental use of the non-early-stop
variant with a bool-returning callback. This compile-time guard ensures callers
choose the correct iteration variant explicitly.
