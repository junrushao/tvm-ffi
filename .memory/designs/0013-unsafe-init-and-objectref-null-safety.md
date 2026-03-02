---
design: "0013"
title: "UnsafeInit Pattern and ObjectRef Null Safety"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-09-08"
last_updated: "2025-09-08"
scope:
  - "ffi/object"
  - "ffi/memory"
  - "ffi/containers"
source_commits:
  - "472e10c4086e91fb788ffe1f0eee10df4bcf5db2"
source_ledgers:
  - ".memory/commits/2025-09-08-472e10c4086e91fb788ffe1f0eee10df4bcf5db2.md"
---

# UnsafeInit Pattern and ObjectRef Null Safety

## TL;DR
- The `ffi::UnsafeInit` tag struct replaces the implicit `ObjectPtr<Object>` constructors on non-nullable `ObjectRef` subclasses. Constructing an ObjectRef with `UnsafeInit{}` explicitly marks the initialization as potentially null, making null-safety violations grep-able.
- `ObjectUnsafe::ObjectRefFromObjectPtr<T>()` is the single centralized factory that constructs any `T : ObjectRef` from an `ObjectPtr` via the `UnsafeInit` path. All internal marshaling routes through this function.
- Nullable ref types accept `ObjectPtr<ContainerType>` (typed, not `ObjectPtr<Object>`), catching type mismatches at compile time.

## Problem Statement
Non-nullable `ObjectRef` subclasses previously had public constructors accepting `ObjectPtr<Object>` (untyped). This had two problems: (1) no compile-time type checking -- any `ObjectPtr<Object>` could be used to construct any ref type, and (2) no visibility into which code paths could introduce null `data_` pointers into non-nullable types. A ref type declared as non-nullable could silently hold null if constructed from a null `ObjectPtr<Object>`.

## Context and Constraints
- The object system uses the `FooObj` (data) + `Foo` (ref) pattern extensively. Hundreds of types follow this convention.
- Internal marshaling code (type traits, `GetRef`, `Optional::value()`, `RValueRef`, `ObjectRef::as()`) must construct ref types from `ObjectPtr` values retrieved from `Any`/`AnyView` containers.
- The solution must not add runtime overhead to the common path (marshaling already validates types before constructing refs).
- The change must be mechanical: the `TVM_FFI_DEFINE_*_OBJECT_REF_METHODS` macros generate the constructors.

## Goals
- Make it impossible to construct a non-nullable `ObjectRef` from an untyped `ObjectPtr<Object>` without an explicit opt-in.
- Provide a single centralized factory for all internal construction from `ObjectPtr`.
- Catch type mismatches at compile time for nullable ref types.
- Make all unsafe (potentially null-producing) construction sites grep-able via the `UnsafeInit` tag.

## Non-Goals
- Runtime null checking on every ObjectRef construction (too expensive for hot paths).
- Removing nullable types entirely (they are needed for optional fields and partial construction).

## Design
### Components and Responsibilities
- **`UnsafeInit`** (tag struct, `object.h`): A sentinel struct with no data. Constructors that accept `UnsafeInit{}` signal that the caller is opting into a potentially-null initialization.
- **`ObjectUnsafe::ObjectRefFromObjectPtr<T>(ObjectPtr<Object>)`** (static method, `object.h`): Centralized factory that constructs any `T : ObjectRef` from an `ObjectPtr<Object>` by calling `T(UnsafeInit{}, ptr)`. This is the only code path that creates refs from untyped pointers.
- **`TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE`** (macro): For nullable types. Generates a public constructor accepting `ObjectPtr<ObjectName>` (typed, not `ObjectPtr<Object>`) and a private `UnsafeInit` constructor.
- **`TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE`** (macro): For non-nullable types. Only generates the private `UnsafeInit` constructor. No public `ObjectPtr` constructor exists.

### Data Contracts and Invariants
- **Non-nullable ref invariant**: A non-nullable `ObjectRef` subclass has no public constructor that can produce a null `data_`. Only `ObjectUnsafe::ObjectRefFromObjectPtr` and the `UnsafeInit` path can create instances with potentially null data.
- **Type safety invariant**: Nullable ref constructors accept `ObjectPtr<ContainerType>` (the concrete data class), not `ObjectPtr<Object>`. A compile-time error results from passing the wrong container type.
- **Grep-ability invariant**: Every code path that can create a non-nullable ref from an untyped `ObjectPtr` contains either `UnsafeInit` or `ObjectRefFromObjectPtr` in its text. Searching for these tokens finds all potentially-unsafe construction sites.

### Control Flow
1. **Normal construction**: `Foo foo = make_object<FooObj>(args...)` -> `ObjectPtr<FooObj>` -> `Foo(ObjectPtr<FooObj>)` (typed constructor, compile-time checked).
2. **Internal marshaling**: `ObjectRefTypeTraitsBase::CopyFromAnyViewAfterCheck(src)` -> extract `ObjectPtr<Object>` from `AnyView` -> `ObjectUnsafe::ObjectRefFromObjectPtr<Foo>(ptr)` -> `Foo(UnsafeInit{}, ptr)` -> `data_ = ptr`.
3. **GetRef**: `GetRef<Foo>(obj_ptr)` -> `ObjectUnsafe::ObjectRefFromObjectPtr<Foo>(ObjectPtr<Object>(obj_ptr))`.

### Extension Points
- New `ObjectRef` subclasses automatically get the correct constructor pattern by using the standard macros.
- Custom constructors with null checks can be added alongside (e.g., `Module(ObjectPtr<ModuleObj>)` with explicit null check).

## Alternatives Considered
### Runtime null checks in every constructor
- Pros: Catches null at the point of construction.
- Cons: Runtime overhead on every construction, including hot marshaling paths. Prohibitively expensive.

### Removing nullable types entirely
- Pros: Eliminates the null problem at the type level.
- Cons: Too invasive. `Optional<T>` and partial-construction patterns require nullable refs.

### Static analysis (clang-tidy check)
- Pros: No runtime overhead.
- Cons: Does not prevent the bug, only detects it after the fact. Hard to configure for all downstream users.

## Why UnsafeInit Won
- Zero runtime overhead: the tag is a compile-time marker only.
- Grep-ability: all unsafe sites are findable by text search.
- Compile-time type safety: nullable types get typed constructors.
- Minimal code change: the macros handle everything.

## Trade-offs
- **Optimized**: Compile-time type safety, audit-ability of unsafe code paths, zero runtime overhead.
- **Sacrificed**: Slightly more verbose internal code (must use `ObjectUnsafe::ObjectRefFromObjectPtr` instead of direct construction). Private constructors require friend declarations for internal use.

## Interfaces and Compatibility
- **C++ API**: `UnsafeInit` tag struct, `ObjectUnsafe::ObjectRefFromObjectPtr<T>()`, updated `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE`/`TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE` macros.
- **Breaking change**: C++ code that constructs non-nullable ObjectRef subclasses from `ObjectPtr<Object>` must migrate to either typed `ObjectPtr<ContainerType>` (for nullable types) or `ObjectUnsafe::ObjectRefFromObjectPtr` (for internal marshaling).

## Failure Modes and Mitigations
- **Misuse of UnsafeInit in user code**: Users could bypass null safety by using `UnsafeInit{}` directly. Mitigated by making the `UnsafeInit` constructor private in the macros; only `ObjectUnsafe` (via friend declaration) can call it.
- **Forgetting to update internal code paths**: Internal marshaling code that was not updated would fail to compile (the old `T(ObjectPtr<Object>)` constructor no longer exists). This is a compile-time error, not a runtime bug.

## Observability and Validation
- Compile-time: any code using the old constructors fails to compile.
- `grep -r "UnsafeInit" include/ src/` finds all unsafe construction sites.
- Existing tests validate that marshaling, `GetRef`, `Optional::value()`, and all container access patterns still work.

## Migration and Rollout
- All macro-generated constructors were updated in commit `472e10c`.
- All internal code paths (`ObjectRefTypeTraitsBase`, `GetRef`, `Optional::value()`, `RValueRef`, `ObjectRef::as()`) were updated to use `ObjectUnsafe::ObjectRefFromObjectPtr`.
- Downstream C++ code must update: replace `T(ObjectPtr<Object>(ptr))` with `ObjectUnsafe::ObjectRefFromObjectPtr<T>(ptr)` or use typed constructors.

## Diagrams
None

## Related ADRs
None (the decision is straightforward given the clear benefits)

## Evidence Matrix
- `UnsafeInit` tag struct -> `.memory/commits/2025-09-08-472e10c4086e91fb788ffe1f0eee10df4bcf5db2.md` + `472e10c` + `include/tvm/ffi/object.h`
- `ObjectUnsafe::ObjectRefFromObjectPtr<T>()` factory -> `472e10c` + `include/tvm/ffi/object.h`
- Macro updates (`TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE`, `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE`) -> `472e10c` + `include/tvm/ffi/object.h`
- Typed `ObjectPtr<ContainerType>` in nullable macros -> `472e10c` + `include/tvm/ffi/object.h`
- `Shape::StridesFromShape()` static factory -> `472e10c` + `include/tvm/ffi/container/shape.h`
- `Module(ObjectPtr<ModuleObj>)` with null check -> `472e10c` + `include/tvm/ffi/extra/module.h`
- `MakeStridesFromShape` signature change -> `472e10c` + `include/tvm/ffi/container/ndarray.h`
- Internal marshaling updated (`ObjectRefTypeTraitsBase`, `GetRef`, `Optional::value()`, `RValueRef`) -> `472e10c` + `include/tvm/ffi/object.h`, `include/tvm/ffi/any.h`

## Open Questions
- Should `UnsafeInit` be exposed as a public API for advanced users who need to construct refs from opaque pointers, or should it remain strictly internal?

## Confidence and Risk
- Confidence: high
- Residual risks: The `UnsafeInit` constructor is private and accessed via friend. If new internal code paths need to construct refs from untyped pointers, they must go through `ObjectUnsafe::ObjectRefFromObjectPtr`, which adds a small maintenance burden.
