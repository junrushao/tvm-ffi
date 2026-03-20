---
status: "active"
confidence: "high"
---
# FFI Object Declaration Macros

**TL;DR**.
- Five declaration macros define the Object type system boilerplate: `TVM_FFI_DECLARE_OBJECT_INFO(TypeKey, TypeName, ParentType)` (non-final types), `TVM_FFI_DECLARE_OBJECT_INFO_FINAL` (leaf types), `TVM_FFI_DECLARE_OBJECT_INFO_STATIC` (static-index types), `TVM_FFI_DECLARE_OBJECT_INFO_PREDEFINED_TYPE_KEY` (internal helper for types that define `_type_key` separately), plus two ref macros: `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE` and `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE`.
- Declaration macros now absorb `_type_key` as their first parameter (eliminating the separate `static constexpr const char* _type_key = ...` line). Ref macros auto-derive pointer constness from `ObjectName::_type_mutable` via `std::conditional_t`, eliminating the need for separate `MUTABLE` variants.
- Each macro generates the `_GetOrAllocRuntimeTypeIndex()` static method that calls `TVMFFITypeGetOrAllocIndex` exactly once (cached via `static` local), plus `RuntimeTypeIndex()` accessor and type metadata fields.

## Problem Statement
### Background
- Every Object type in the FFI system requires the same boilerplate: static type fields (`_type_depth`, `_type_index`), a `RuntimeTypeIndex()` accessor, type registration via `TVMFFITypeGetOrAllocIndex`, and ref wrapper methods.
- Writing this boilerplate by hand is error-prone and verbose. Macros ensure consistency.
- The original six macros had unnecessary combinatorial explosion: four ref variants (`NULLABLE`, `NOTNULLABLE`, `MUTABLE_NULLABLE`, `MUTABLE_NOTNULLABLE`) and separate `_type_key` definitions alongside declaration macros.

### Solution
- A consolidated set of macros where: (a) declaration macros absorb `TypeKey` as a parameter, and (b) ref macros auto-derive mutability from `_type_mutable`, collapsing six old macros into five new ones.

### Goals
- Correct type hierarchy registration with parent linkage.
- Exactly-once registration via static local caching.
- Support for both static (pre-assigned) and dynamic (runtime-allocated) type indices.
- Minimal boilerplate: one macro line per type (no separate `_type_key` definition).
- Non-goal: hiding the type system mechanism (developers should understand the expansion).

## Design

### Macro Rename Map (a08fa6e)

| Old Macro | New Macro | Signature Change |
|---|---|---|
| `TVM_FFI_DECLARE_BASE_OBJECT_INFO(TypeName, ParentType)` | `TVM_FFI_DECLARE_OBJECT_INFO(TypeKey, TypeName, ParentType)` | `TypeKey` param added; absorbs `_type_key` definition |
| `TVM_FFI_DECLARE_FINAL_OBJECT_INFO(TypeName, ParentType)` | `TVM_FFI_DECLARE_OBJECT_INFO_FINAL(TypeKey, TypeName, ParentType)` | same |
| `TVM_FFI_DECLARE_STATIC_OBJECT_INFO(TypeName, ParentType)` | `TVM_FFI_DECLARE_OBJECT_INFO_STATIC(TypeKey, TypeName, ParentType)` | same |
| `TVM_FFI_DEFINE_OBJECT_REF_METHODS(T, P, O)` | `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(T, P, O)` | Adds `__PtrType` conditional + `_type_is_nullable = true` |
| `TVM_FFI_DEFINE_NOTNULLABLE_OBJECT_REF_METHODS(T, P, O)` | `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(T, P, O)` | Adds `__PtrType` conditional |
| `TVM_FFI_DEFINE_MUTABLE_OBJECT_REF_METHODS(T, P, O)` | *(removed)* | Merged into `NULLABLE` via `_type_mutable` |
| `TVM_FFI_DEFINE_MUTABLE_NOTNULLABLE_OBJECT_REF_METHODS(T, P, O)` | *(removed)* | Merged into `NOTNULLABLE` via `_type_mutable` |

Internal helper: `TVM_FFI_DECLARE_OBJECT_INFO_PREDEFINED_TYPE_KEY(TypeName, ParentType)` -- for types that define `_type_key` separately (e.g., custom `_type_child_slots`).

### Macro Expansions

#### TVM_FFI_DECLARE_OBJECT_INFO_FINAL(TypeKey, TypeName, ParentType)

For leaf types that cannot be subclassed in the type system.

```python
# Input (new pattern -- one line, no separate _type_key):
class MyNodeObj(Object):
    value: int64
    TVM_FFI_DECLARE_OBJECT_INFO_FINAL("test.MyNode", MyNodeObj, Object)

# Expansion:
class MyNodeObj(Object):
    _type_key: str = "test.MyNode"           # absorbed into macro (was separate line)
    _type_child_slots: int = 0               # no children allowed
    _type_final: bool = True                 # marks as final for IsInstance fast-path
    # --- from TVM_FFI_DECLARE_OBJECT_INFO_PREDEFINED_TYPE_KEY ---
    _type_depth: int = Object._type_depth + 1  # = 1
    @staticmethod
    def _GetOrAllocRuntimeTypeIndex() -> int32:
        assert not Object._type_final, "ParentType marked as final"
        type_key = TVMFFIByteArray("test.MyNode")
        tindex = TVMFFITypeGetOrAllocIndex(
            type_key,
            static_type_index=-1,       # dynamic allocation
            type_depth=1,
            num_child_slots=0,
            child_slots_can_overflow=True,
            parent_type_index=Object._GetOrAllocRuntimeTypeIndex()
        )
        return tindex  # cached in static local: only called once
        # Interacts with: TVMFFITypeGetOrAllocIndex C API
        # Invariant: parent MUST be registered before child

    @staticmethod
    def RuntimeTypeIndex() -> int32:
        return _GetOrAllocRuntimeTypeIndex()

    # NOTE: _type_index = _GetOrAllocRuntimeTypeIndex() was REMOVED (9ac31216).
    # Registration no longer happens automatically at static init.
    # Each type must explicitly call reflection::ObjectDef<T>() in a .cc file.
```

#### TVM_FFI_DECLARE_OBJECT_INFO(TypeKey, TypeName, ParentType)

For non-final types that can be subclassed. Same expansion as FINAL but without `_type_final = true` and `_type_child_slots = 0`.

```python
# Expansion adds:
#   static constexpr const char* _type_key = TypeKey;  # absorbed
#   _type_depth = ParentType._type_depth + 1
#   _GetOrAllocRuntimeTypeIndex() -> same as above, with static_type_index=-1
#   RuntimeTypeIndex() -> _GetOrAllocRuntimeTypeIndex()
#   NOTE: auto-registration removed (9ac31216); must use ObjectDef<T>() explicitly
```

#### TVM_FFI_DECLARE_OBJECT_INFO_STATIC(TypeKey, TypeName, ParentType)

For built-in types with pre-assigned static type indices (e.g., `FunctionObj`, `ErrorObj`).

```python
# Input:
class FunctionObj(Object):
    _type_index = kTVMFFIFunction  # = 68, pre-assigned
    TVM_FFI_DECLARE_OBJECT_INFO_STATIC("ffi.Function", FunctionObj, Object)

# Expansion:
class FunctionObj(Object):
    _type_key: str = "ffi.Function"   # absorbed into macro
    _type_index = kTVMFFIFunction     # 68

    @staticmethod
    def RuntimeTypeIndex() -> int32:
        return FunctionObj._type_index  # returns the static constant, not dynamic

    _type_depth = Object._type_depth + 1
    @staticmethod
    def _GetOrAllocRuntimeTypeIndex() -> int32:
        tindex = TVMFFITypeGetOrAllocIndex(
            type_key="ffi.Function",
            static_type_index=68,
            type_depth=1,
            num_child_slots=0,
            child_slots_can_overflow=True,
            parent_type_index=Object._GetOrAllocRuntimeTypeIndex()
        )
        return FunctionObj._type_index  # returns the static constant
    # NOTE: _register_type_index side-effect REMOVED (9ac31216).
    # Built-in depth-1 types are pre-registered in TypeTable::TypeTable() via
    # ReserveDepthOneObjectTypeIndex(). Key difference: RuntimeTypeIndex returns static constant.
```

#### TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(TypeName, ParentType, ObjectName)

For ref wrapper classes. Auto-derives pointer constness from `_type_mutable`.

```python
# Input:
class MyNode(ObjectRef):
    TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(MyNode, ObjectRef, MyNodeObj)

# Expansion:
class MyNode(ObjectRef):
    # Auto-derived pointer type (replaces separate MUTABLE variants):
    __PtrType = MyNodeObj* if MyNodeObj._type_mutable else const MyNodeObj*
    # Invariant: _type_mutable on the Obj class gates writable access

    _type_is_nullable: bool = True   # explicit marker (new)

    def __init__(self): ...  # default constructor (undefined state)
    def __init__(self, n: ObjectPtr[MyNodeObj]):  # typed
        super().__init__(n)
    def __init__(self, tag: UnsafeInit):  # unsafe init: data_ = nullptr
        super().__init__(tag)

    # copy/move constructors and assignment (via TVM_FFI_DEFINE_DEFAULT_COPY_MOVE_AND_ASSIGN)

    def __arrow__(self) -> __PtrType:  # operator->; const or mutable per _type_mutable
        return static_cast[__PtrType](self.data_.get())

    def get(self) -> __PtrType:
        return self.__arrow__()

    ContainerType = MyNodeObj
    # Interacts with: TypeTraits<MyNode> (uses ContainerType for IsInstance checks)
    # Extension: replaces both old OBJECT_REF_METHODS and MUTABLE_OBJECT_REF_METHODS

# For mutable types like Module:
# class ModuleObj(Object):
#     _type_mutable = True
#     TVM_FFI_DECLARE_OBJECT_INFO_STATIC("ffi.Module", ModuleObj, Object)
# class Module(ObjectRef):
#     TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(Module, ObjectRef, ModuleObj)
#     # __PtrType = ModuleObj* (because _type_mutable = True)
#     # No separate MUTABLE macro needed
```

#### TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(TypeName, ParentType, ObjectName)

Same auto-derived `__PtrType` logic but no default constructor, `_type_is_nullable = false`.

```python
# Only provides: explicit TypeName(UnsafeInit tag) : ParentType(tag) {}
# Used by: Error (always has a valid ErrorObj), Module (mutable + not nullable)
```

### Contracts, Assumptions and Invariants
- **Parent-before-child registration**: `_GetOrAllocRuntimeTypeIndex` calls `ParentType::_GetOrAllocRuntimeTypeIndex()` as the last argument to `TVMFFITypeGetOrAllocIndex`. This guarantees the parent is registered first (evaluated before the child's registration call).
- **Exactly-once registration**: The `static int32_t tindex = ...` pattern ensures `TVMFFITypeGetOrAllocIndex` is called exactly once per type, even if `_GetOrAllocRuntimeTypeIndex` is called from multiple threads.
- **Explicit registration required**: As of commit 9ac31216, the macros no longer auto-register types via static-init side effects. Each non-builtin type must call `reflection::ObjectDef<T>()` in a `.cc` file. Built-in types with static indices are pre-registered in `TypeTable::TypeTable()` via `ReserveDepthOneObjectTypeIndex()`.
- **Child slots constraint**: `static_assert` checks that if both child and parent specify `_type_child_slots`, the child's must be smaller. This prevents index range overlap.

### Extension Points
- **Custom base types**: To create a new base type in the hierarchy, use `TVM_FFI_DECLARE_OBJECT_INFO_PREDEFINED_TYPE_KEY` (with a manually defined `_type_key` and `_type_child_slots`) for the expected number of direct subtypes for fast `IsInstance` checking.
- **Dynamic types from other languages**: Python/Rust can register new types by calling `TVMFFITypeGetOrAllocIndex` with `static_type_index=-1` through the C API.

### Usage Examples

#### Declaring a Type Hierarchy
**Context**: Creating a base IR node type with subtypes.
```cpp
// Base class with reserved child slots -- uses PREDEFINED_TYPE_KEY because
// custom _type_child_slots requires defining _type_key separately.
class ExprObj : public Object {
 public:
  static constexpr const char* _type_key = "ir.Expr";
  static constexpr uint32_t _type_child_slots = 20;
  TVM_FFI_DECLARE_OBJECT_INFO_PREDEFINED_TYPE_KEY(ExprObj, Object);
};

// Leaf subclass -- uses the standard 3-arg macro (absorbs _type_key)
class AddObj : public ExprObj {
 public:
  ObjectRef lhs, rhs;
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ir.Add", AddObj, ExprObj);
};

// Ref wrappers -- NULLABLE replaces both old OBJECT_REF_METHODS and MUTABLE variants
class Expr : public ObjectRef {
 public:
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Expr, ObjectRef, ExprObj);
};

class Add : public ObjectRef {
 public:
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Add, ObjectRef, AddObj);
};

// Usage:
auto add = make_object<AddObj>();
Expr expr(add);
assert(expr->IsInstance<ExprObj>());  // fast: range check [ExprIdx, ExprIdx+20)
assert(expr->IsInstance<AddObj>());   // fast: exact match (final type)
```

## Implementation Notes
- The `_type_depth` and `_GetOrAllocRuntimeTypeIndex` generation logic is shared across `STATIC`, `BASE`, and `FINAL`. The former `TVM_FFI_REGISTER_STATIC_TYPE_INFO` sub-macro and its registration side-effect variables (`_register_type_index`, `_type_index = _GetOrAllocRuntimeTypeIndex()`) have been removed (9ac31216).
- `TVM_FFI_DEFINE_DEFAULT_COPY_MOVE_AND_ASSIGN` generates the five special member functions (copy/move constructors and assignments + destructor) to ensure proper `ObjectPtr` ref counting.
- The `TVM_FFI_STR_CONCAT` + `__COUNTER__` pattern generates unique variable names for the static registration variables.

## Alternatives & Trade-offs
### Macros vs. CRTP Base Classes
- Pros of macros: Simpler to use (one line per type). Can inject static data members. Compatible with the existing single-inheritance model.
- Cons: Hard to debug (macro expansion not visible). Cannot enforce constraints at the type system level.
### Explicit Registration vs. Implicit (Static Init)
- Pros of static init: Zero-effort for users. Types are registered before `main()`.
- Cons: Static initialization order fiasco (mitigated by `static local` caching). Registration timing may be surprising in DLL load scenarios.

## Evidence
| Commit | Scope | Contribution |
|--------|-------|-------------|
| 7d34eb8 | ffi/object | Introduced all object declaration macros and ref method macros |
| 1a856886 | ffi/object | Updated macros to use renamed TVMFFITypeGetOrAllocIndex |
| 0966c368 | ffi/object | Renamed type keys from `object.*` to `ffi.*` |
| 538bef49 | ffi/object | Fixed mutable ref macro bugs (trailing semicolons, TVM_DEFINE_ typo), added MUTABLE_NOTNULLABLE variant usage (Module) |
| 472e10c | ffi/object | Replaced `ObjectPtr[Object]` constructors with typed `ObjectPtr[ContainerType]` + `UnsafeInit` tag in all four ref macros |
| a08fa6e | ffi/object | Renamed all macros to new convention, absorbed TypeKey, auto-derived mutable pointer, eliminated separate MUTABLE variants |

### Evolution Timeline

| Commit | Change | Impact |
|--------|--------|--------|
| `7d34eb8` | Initial macros: `TVM_FFI_DECLARE_BASE/FINAL/STATIC_OBJECT_INFO`, `TVM_FFI_DEFINE_OBJECT_REF_METHODS` | Created subsystem |
| `538bef49` | Added `MUTABLE` and `MUTABLE_NOTNULLABLE` ref macro variants | Separate macros for mutable types |
| `472e10c` | Typed `ObjectPtr<ContainerType>` constructors, `UnsafeInit` tag | Compile-time safety for ref construction |
| `a08fa6e` | Consolidated rename: 6 old macros -> 5 new macros, TypeKey absorption, `_type_mutable` auto-derivation | Eliminated MUTABLE variants, reduced boilerplate |
| `9ac31216` | Removed static-init registration side-effects (`_register_type_index`, `_type_index = _GetOrAllocRuntimeTypeIndex()`); explicit `ObjectDef<T>()` now required. Built-in types pre-registered in TypeTable constructor via `ReserveDepthOneObjectTypeIndex()` | Registration contract change |

## Related Design Docs & ADRs
- [0003-object-system.md](0003-object-system.md) -- Object system that these macros configure
- [0007-reflection.md](0007-reflection.md) -- Reflection depends on _GetOrAllocRuntimeTypeIndex for type registration
- [0011-module-system.md](0011-module-system.md) -- Module uses TVM_FFI_DECLARE_OBJECT_INFO_STATIC and TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE
