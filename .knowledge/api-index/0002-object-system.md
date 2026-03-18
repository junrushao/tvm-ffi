---
scope: "object-system"
---
# API Index: Object System

**Scope**: C++ Object hierarchy, smart pointers, and type registration macros.
**Design docs**: [0002-object-system.md](../designs/0002-object-system.md)
**ADRs**: [0003-child-slot-type-checking.md](../ADRs/0003-child-slot-type-checking.md), [0009-weak-reference-counting.md](../ADRs/0009-weak-reference-counting.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `Object` | class | `TVMFFIObject header_`, `IsInstance<T>() -> bool`, `type_index() -> int32`, `use_count() -> int32`, `unique() -> bool`, `IncWeakRef()`, `DecWeakRef()`, `TryPromoteWeakPtr() -> bool` | Base of all ref-counted heap objects (24-byte header with split strong/weak counts) |
| `ObjectPtr<T>` | class | `T* get()`, `void reset()`, `bool unique()`, `int use_count()`, `void swap(ObjectPtr&)` | Intrusive smart pointer managing Object lifetime |
| `ObjectRef` | class | `ObjectPtr<Object> data_`, `as<T>() -> Optional<T>`, `same_as(other) -> bool`, `defined() -> bool`, `type_index() -> int32` | User-facing handle wrapper around ObjectPtr |
| `WeakObjectPtr<T>` | class | `lock() -> Optional<ObjectPtr<T>>`, `expired() -> bool`, `reset()`, `use_count() -> int` | Weak smart pointer; does not prevent destruction, only keeps memory alive. CAS-based lock() for thread-safe promotion |
| `ObjectPtrHash` | struct | `size_t operator()(const ObjectRef&)` | Hash functor based on pointer identity |
| `ObjectPtrEqual` | struct | `bool operator()(const ObjectRef&, const ObjectRef&)` | Equality functor based on pointer identity |
| `make_object<T>(args...)` | function | `ObjectPtr<T> make_object(Args&&... args)` | Allocate and construct a new Object of type T |
| `make_inplace_array_object<A,E>(n, args...)` | function | `ObjectPtr<A> make_inplace_array_object(size_t num_elems, Args&&...)` | Allocate array-type object with inline element storage |
| `UnsafeInit` | struct | (empty tag type) | Tag for explicit null initialization of ObjectRef subclasses. Only for internal FFI plumbing |
| `ObjectUnsafe::ObjectRefFromObjectPtr<T>` | function | `T ObjectRefFromObjectPtr(ObjectPtr<Object>)` | Construct ObjectRef from ObjectPtr via UnsafeInit + data_ assignment |
| `details::SimpleObjAllocator` | class | `Handler<T>::New(...)`, `Handler<T>::Deleter()` | Default allocator (moved to `details` namespace in 24125d0) |
| `details::ObjAllocatorBase<Derived>` | class | `make_object<T>(args...)`, `make_inplace_array<A,E>(n, args...)` | CRTP base for custom allocators (in `details` namespace) |
| `TypeTable::ReserveDepthOneObjectTypeIndex` | method | `(type_key: str, static_type_index: int) -> void` | Pre-register built-in depth-1 object type during TypeTable construction (9ac3121) |
| `StaticTypeKey::kTVMFFIError` | constant | `"ffi.Error"` | Type key for Error objects (9ac3121) |
| `TVM_FFI_DECLARE_OBJECT_INFO(TypeKey, TypeName, ParentType)` | macro | Sets `_type_key=TypeKey`, generates `_type_depth`, `_GetOrAllocRuntimeTypeIndex()`, `RuntimeTypeIndex()`. No auto-registration (9ac3121) | Declare a non-final object type; must call `ObjectDef<T>()` for IsInstance to work |
| `TVM_FFI_DECLARE_OBJECT_INFO_FINAL(TypeKey, TypeName, ParentType)` | macro | Sets `_type_child_slots=0`, `_type_final=true`, then calls DECLARE_OBJECT_INFO | Declare a final (leaf) object type (was `_FINAL_`, a08fa6e) |
| `TVM_FFI_DECLARE_OBJECT_INFO_STATIC(TypeKey, TypeName, ParentType)` | macro | Sets `_type_key=TypeKey`, uses static `_type_index` | Declare built-in type with fixed type index (was `_STATIC_`, a08fa6e) |
| `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(TypeName, ParentType, ObjName)` | macro | Default ctor, `TypeName(ObjectPtr<ObjName>)`, `TypeName(UnsafeInit)`, `conditional_t` pointer, `_type_is_nullable=true` | Define nullable ObjectRef (replaces both immutable and mutable variants, a08fa6e) |
| `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(TypeName, ParentType, ObjName)` | macro | `TypeName(UnsafeInit)` only, `conditional_t` pointer, `_type_is_nullable=false` | Define non-nullable ObjectRef (replaces both immutable and mutable variants, a08fa6e) |
| ~~`TVM_FFI_DEFINE_MUTABLE_OBJECT_REF_METHODS`~~ | macro | Removed: use `_NULLABLE` with `_type_mutable=true` on Obj class (a08fa6e) | |
| ~~`TVM_FFI_DEFINE_MUTABLE_NOTNULLABLE_OBJECT_REF_METHODS`~~ | macro | Removed: use `_NOTNULLABLE` with `_type_mutable=true` on Obj class (a08fa6e) | |
