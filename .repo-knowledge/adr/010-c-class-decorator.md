# ADR 010: `@c_class` Decorator for Python/C++ Class Mirroring

- Status: Accepted
- Date: 2025-09-21
- Owners: Junru Shao

## Context

The existing `@register_object` + manual `__init__` pattern for creating
Python wrappers of C++ FFI types was boilerplate-heavy. Each class required
manually defining `__init__`, properties for each field, and method wrappers.
The reflection system (design doc 004) already stored all necessary metadata
(field names, types, defaults, methods) in the C++ type table.

## Decision

Introduce `tvm_ffi.dataclasses.c_class` (`e98b94e`) as a Python decorator
that mirrors C++ FFI types with dataclass-like syntax. The decorator:

1. Reads the C++ reflection metadata via `TypeInfo` to discover fields and
   their types.
2. Auto-generates properties backed by the C++ object for each annotated
   field (via `TypeField.as_property`).
3. Synthesizes an `__init__` method from the reflected constructor signature,
   calling `Object.__ffi_init__` to invoke the C++ constructor.
4. Supports `field(default=...)`, `field(default_factory=...)`, and
   `field(init=False)` (`daeb235`) for customizing field initialization.
5. Supports `__post_init__` hooks for additional Python-side initialization.
6. Supports inheritance (up to three levels tested).

The convention for C++ constructors is `__ffi_init__` (replacing `__create__`),
registered via `reflection::init<T, Args...>` (`c01dadf`).

mypy compatibility was addressed by fixing warnings on `dataclasses.field(...)`
usage (`b5dd851`).

## Consequences

- Positive: Reduces Python boilerplate for C++ type wrappers from ~20 lines
  to ~5 lines per class.
- Positive: Constructor signatures are derived from C++ reflection, ensuring
  Python and C++ stay in sync.
- Positive: Works with the existing `@register_object` pattern; `@c_class`
  is additive, not a replacement.
- Negative: The decorator mutates `TypeInfo.parent_type_info` during
  application, which could cause issues if the same type is decorated twice.
- Negative: Marked as experimental; the API may change before 1.0.
- Migration/Rollout: Additive change. Existing `@register_object` classes
  continue to work. New classes can opt in to `@c_class` for reduced
  boilerplate.

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-09-30-CA9C3D1-F9179EC.md`
  - `.repo-knowledge/ranges/2026-01-30-C51E519-B508698.md`
- Evidence commits: `e98b94e118dfa5ac4bcf3764a8b1695afee3d596`, `c01dadf31a66e74cdbfd7fdb1ffc81a75007965f`, `daeb235a29c576d8702d447fa5f4773170bb1e8f`, `b5dd851f7019f4f63a19d9dce074ba62706f16e7`, `360648f30ccb14523ab6fbb81f37eb085b801f98`, `3a5bf5e68ad1b4108045ef6b336a13efcd2037d9`
- External references: Python `dataclasses` module (PEP 557)

## Related Design Docs
- `.repo-knowledge/design/004-reflection-system.md`

## Notes
The `@c_class` decorator depends on the `TypeInfo` Python metadata
(`53b2e00`) and `reflection::init<>` C++ helper (`c01dadf`).

As of January 2026, the following dataclass features have been implemented:
- `repr=True` parameter and `field(repr=True)` for auto-generated `__repr__`
  (`360648f`). Format: `ClassName(field=value, ...)`. Fields with `repr=False`
  are excluded.
- `kw_only` parameter and `KW_ONLY` sentinel for keyword-only fields
  (`3a5bf5e`). Mirrors `dataclasses.KW_ONLY` (PEP 557). Can be set at class
  level or per-field.

Remaining future work: ordering (`__lt__`, `__eq__` etc.), `frozen` support,
and `__hash__` generation.
