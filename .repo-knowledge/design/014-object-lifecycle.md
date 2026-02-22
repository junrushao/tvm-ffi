# 014 — Object System and Lifetime Management

- Doc ID: 014-object-lifecycle
- Status: Approved
- Last Updated: 2026-02-22
- Owners: Tianqi Chen

## Overview

The TVM FFI object system provides reference-counted heap objects with single
inheritance, type-erased lifetime management, and cross-language ownership
semantics. All objects inherit from `tvm::ffi::Object`, which embeds a 24-byte
`TVMFFIObject` C header containing a combined strong/weak reference counter, a
runtime type index, and a deleter callback. Objects are allocated via
`make_object<T>`, wrapped in `ObjectPtr<T>` smart pointers, and exposed to
users through `ObjectRef` reference wrappers. The system is RTTI-independent,
using its own type index hierarchy with O(1) `IsInstance` checks via ancestor
arrays. Python bindings hold a single `void*` handle per wrapper object,
delegating all lifetime management to the C++ reference counter.

## Key Design

### TVMFFIObject header layout

The `TVMFFIObject` struct (defined in `c_api.h`) is a 24-byte C struct that
forms the common prefix of every heap-allocated FFI object:

```
Offset  Size  Field
------  ----  -----
  0       8   combined_ref_count  (uint64_t: strong[31:0] | weak[63:32])
  8       4   type_index          (int32_t)
 12       4   __padding           (uint32_t)
 16       8   deleter / __ensure_align  (function pointer / int64_t union)
------  ----
Total:   24 bytes
```

The reference counter occupies the first field to align with PyTorch's
`intrusive_ptr` layout for cache efficiency. The `deleter` field is a
union with `int64_t __ensure_align` to guarantee 8-byte alignment on all
platforms.

### Object / ObjectRef pattern

The codebase follows a two-class convention. `FooObj` (the "data class")
inherits from `Object` and holds the actual data fields. `Foo` (the "ref
wrapper") inherits from `ObjectRef` and wraps an `ObjectPtr<Object> data_`
smart pointer:

```cpp
class MyObjectObj : public ffi::Object {
 public:
  int64_t value;
  ffi::String name;
  TVM_FFI_DECLARE_OBJECT_INFO("my_ext.MyObject", MyObjectObj, ffi::Object);
};

class MyObject : public ffi::ObjectRef {
 public:
  MyObject(int64_t v, ffi::String n)
      : ObjectRef(ffi::make_object<MyObjectObj>(v, std::move(n))) {}
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(MyObject, ffi::ObjectRef, MyObjectObj);
};
```

`ObjectPtr<T>` is the intrusive smart pointer. Its copy constructor calls
`IncRef()`, its destructor calls `DecRef()`, and move transfers the raw
pointer without touching the reference count:

```cpp
explicit ObjectPtr(Object* data) : data_(data) {
  if (data_ != nullptr) data_->IncRef();
}
~ObjectPtr() { this->reset(); }
void reset() {
  if (data_ != nullptr) { data_->DecRef(); data_ = nullptr; }
}
```

`ObjectRef` provides `get()` (returns `const Object*` without releasing
ownership), `defined()` (null check), `same_as()` (pointer identity), and
`as<T>()` (safe downcast returning `std::optional<T>`). Mutable access
through `operator->()` is controlled by the `_type_mutable` constexpr flag
on the data class.

### Allocation: make_object<T>

`make_object<T>(args...)` (defined in `memory.h`) is the primary allocation
entry point. It delegates to `SimpleObjAllocator::make_object`:

```cpp
template <typename T, typename... Args>
ObjectPtr<T> make_object(Args&&... args) {
  return details::SimpleObjAllocator().make_object<T>(std::forward<Args>(args)...);
}
```

The allocation sequence in `ObjAllocatorBase::make_object`:

1. `AlignedAlloc<alignof(T)>(sizeof(T))` -- allocate aligned memory.
2. Placement new: `new (data) T(std::forward<Args>(args)...)`.
3. Initialize the header fields:
   - `combined_ref_count = kCombinedRefCountBothOne` (strong=1, weak=1)
   - `type_index = T::RuntimeTypeIndex()`
   - `__padding = 0`
   - `deleter = Handler::Deleter()` -- type-specific deleter captured at
     compile time
4. Return `ObjectPtr<T>` via `ObjectPtrFromOwned` (no additional `IncRef`).

The initial refcount is `{strong=1, weak=1}` (value `kCombinedRefCountBothOne`),
not `{strong=1, weak=0}`. The extra `weak=1` ensures the fast path in
`DecRef` works: when the single owner drops the strong ref,
`count_before_sub == kCombinedRefCountBothOne` triggers the single-atomic
deletion path.

For objects with trailing element arrays (e.g., `StringObj`, `ArrayObj`),
`make_inplace_array_object<ArrayType, ElemType>(num_elems, args...)` allocates
`sizeof(ArrayType) + sizeof(ElemType) * num_elems`, rounded up to the
array alignment.

### Combined reference count

Two 32-bit counters are packed into a single `uint64_t combined_ref_count`.
Strong count occupies the lower 32 bits; weak count occupies the upper 32
bits. Constants defined in `object.h`:

```cpp
constexpr uint64_t kCombinedRefCountStrongOne = 1;
constexpr uint64_t kCombinedRefCountWeakOne = static_cast<uint64_t>(1) << 32;
constexpr uint64_t kCombinedRefCountBothOne = kCombinedRefCountWeakOne | kCombinedRefCountStrongOne;
constexpr uint64_t kCombinedRefCountMaskUInt32 = (static_cast<uint64_t>(1) << 32) - 1;
```

`IncRef()` is a single `fetch_add(1, RELAXED)` on the 64-bit field -- it
increments only the strong count because the lower 32 bits are contiguous.
`use_count()` reads with `RELAXED` ordering and masks to the lower 32 bits.

### DecRef fast path and slow path

`DecRef()` performs a single `fetch_sub(kCombinedRefCountStrongOne, RELEASE)`:

```cpp
void DecRef() {
  uint64_t count_before_sub = __atomic_fetch_sub(
      &(header_.combined_ref_count), kCombinedRefCountStrongOne, __ATOMIC_RELEASE);
  if (count_before_sub == kCombinedRefCountBothOne) {
    // Fast path: both strong and weak go to zero in one atomic op
    __atomic_thread_fence(__ATOMIC_ACQUIRE);
    if (header_.deleter != nullptr) {
      header_.deleter(&(this->header_), kTVMFFIObjectDeleterFlagBitMaskBoth);
    }
  } else if ((count_before_sub & kCombinedRefCountMaskUInt32) == kCombinedRefCountStrongOne) {
    // Slow path: strong -> 0 but weak > 0
    __atomic_thread_fence(__ATOMIC_ACQUIRE);
    if (header_.deleter != nullptr) {
      header_.deleter(&(this->header_), kTVMFFIObjectDeleterFlagBitMaskStrong);
    }
    // Then decrement weak
    if (__atomic_fetch_sub(&(header_.combined_ref_count),
                           kCombinedRefCountWeakOne, __ATOMIC_RELEASE)
        == kCombinedRefCountWeakOne) {
      __atomic_thread_fence(__ATOMIC_ACQUIRE);
      if (header_.deleter != nullptr) {
        header_.deleter(&(this->header_), kTVMFFIObjectDeleterFlagBitMaskWeak);
      }
    }
  }
}
```

The fast path (most common case, no weak references outstanding) requires
only a single atomic operation to detect that both counts are reaching zero.
Before this optimization (commit `43d13e8`), detecting this condition required
two separate atomic operations.

### Two-phase deletion

When the last strong reference drops, the object undergoes a two-phase
deletion controlled by `TVMFFIObjectDeleterFlagBitMask`:

- `kTVMFFIObjectDeleterFlagBitMaskStrong = 1`: call destructor only.
- `kTVMFFIObjectDeleterFlagBitMaskWeak = 2`: free memory only.
- `kTVMFFIObjectDeleterFlagBitMaskBoth = 3`: destructor and free memory.

The `SimpleObjAllocator::Handler::Deleter_` implementation:

```cpp
static void Deleter_(void* objptr, int flags) {
  T* tptr = details::ObjectUnsafe::RawObjectPtrFromUnowned<T>(
      static_cast<TVMFFIObject*>(objptr));
  if (flags & kTVMFFIObjectDeleterFlagBitMaskStrong) {
    tptr->T::~T();  // explicit non-virtual destructor call
  }
  if (flags & kTVMFFIObjectDeleterFlagBitMaskWeak) {
    AlignedFree(static_cast<void*>(tptr));
  }
}
```

The destructor is called via `tptr->T::~T()` (explicit qualified call),
not `tptr->~T()`. This avoids requiring a virtual destructor -- the deleter
is captured at allocation time and knows the concrete type.

### Weak references: WeakObjectPtr<T>

`WeakObjectPtr<T>` manages the weak counter (upper 32 bits of
`combined_ref_count`). Construction from `ObjectPtr<T>` calls `IncWeakRef()`
which performs `fetch_add(kCombinedRefCountWeakOne, RELAXED)`.

`WeakObjectPtr::lock()` attempts to promote weak to strong via
`TryPromoteWeakPtr()`, which uses a CAS loop:

```cpp
ObjectPtr<T> lock() const {
  if (data_ != nullptr && data_->TryPromoteWeakPtr()) {
    ObjectPtr<T> ret;
    ret.data_ = data_;  // already incremented by TryPromoteWeakPtr
    return ret;
  }
  return nullptr;
}
```

`TryPromoteWeakPtr` reads `combined_ref_count`, checks if strong > 0, and
attempts to atomically increment the strong count with `ACQ_REL` on success
and `RELAXED` on failure. `expired()` returns true if the data pointer is
null or `use_count() == 0`.

Weak references are only exposed at the `ObjectPtr` layer. There is no
`WeakObjectRef` type alias, and weak references are not exposed at the
Python level.

### Type index system

`TVMFFITypeIndex` (in `c_api.h`) defines three ranges:

| Range | Indices | Contents |
|-------|---------|----------|
| On-stack POD / special | `[0, 64)` | None(0), Int(1), Bool(2), Float(3), OpaquePtr(4), DataType(5), Device(6), DLTensorPtr(7), RawStr(8), ByteArrayPtr(9), ObjectRValueRef(10), SmallStr(11), SmallBytes(12) |
| Static heap objects | `[64, 128)` | Object(64), Str(65), Bytes(66), Error(67), Function(68), Shape(69), Tensor(70), Array(71), Map(72), Module(73), OpaquePyObject(74), List(75), Dict(76) |
| Dynamic types | `[128, +inf)` | Allocated at runtime via `TVMFFITypeGetOrAllocIndex` |

`TypeTable` (in `src/ffi/object.cc`) is a singleton that maps type keys to
type indices and stores `TypeInfo` entries. Static builtins are reserved
at `TypeTable` construction via `ReserveBuiltinTypeIndex` (depth 0, for POD
types) and `ReserveDepthOneObjectTypeIndex` (depth 1, parent = `kTVMFFIObject`,
for static object types). Dynamic types get indices from parent's reserved
child slots or from an overflow counter starting at 128.

The `TypeTable` does not use a mutex. The assumption (documented in source
comments) is that type registration happens in the main thread during
initialization or is explicitly locked by the caller.

### O(1) IsInstance via ancestor arrays

`TVMFFITypeInfo` stores `type_ancestors` -- a pointer-based array where
`type_ancestors[depth]` is the `TVMFFITypeInfo*` of the ancestor at that
depth. `type_depth` records the depth in the hierarchy (Object is depth 0).

`IsObjectInstance<TargetType>()` uses a multi-strategy approach:

```cpp
template <typename TargetType>
TVM_FFI_INLINE bool IsObjectInstance(int32_t object_type_index) {
  if constexpr (std::is_same_v<TargetType, Object>) return true;
  else if constexpr (TargetType::_type_final) {
    return object_type_index == TargetType::RuntimeTypeIndex();
  } else {
    int32_t begin = TargetType::RuntimeTypeIndex();
    if constexpr (TargetType::_type_child_slots != 0) {
      int32_t end = begin + TargetType::_type_child_slots + 1;
      if (object_type_index >= begin && object_type_index < end) return true;
    } else {
      if (object_type_index == begin) return true;
    }
    if constexpr (TargetType::_type_child_slots_can_overflow) {
      if (object_type_index < begin) return false;
      const TypeInfo* info = TVMFFIGetTypeInfo(object_type_index);
      return (info->type_depth > TargetType::_type_depth &&
              info->type_ancestors[TargetType::_type_depth]->type_index == begin);
    }
    return false;
  }
}
```

The child slots mechanism enables range-based O(1) checks for base types
with bounded subtypes. The ancestor array provides O(1) fallback for overflow
cases at the cost of a pointer chase into the global TypeInfo table.

### Single inheritance and RTTI independence

Only single inheritance is supported. The type hierarchy forms a tree, enforced
by the ancestor array design where `type_ancestors[i]` stores exactly one
parent at each depth. The system is completely independent of C++ RTTI:
`dynamic_cast` is never used; all downcasting goes through `IsInstance` +
`static_cast`. This ensures consistent behavior across C++, Python, and Rust
FFI boundaries.

### Nullable vs non-nullable ObjectRef macros

Two macro variants define ObjectRef methods:

`TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(TypeName, ParentType, ObjectName)`:
- Provides default constructor initializing to nullptr.
- Sets `_type_is_nullable = true`.
- Includes `ObjectPtr<ObjectName>` constructor.

`TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(TypeName, ParentType, ObjectName)`:
- No default constructor.
- Sets `_type_is_nullable = false`.
- Only `UnsafeInit` constructor for internal use.

Both provide `operator->()`, `get()` (returning `const ObjectName*` or mutable
if `_type_mutable`), copy/move constructors, and a `ContainerType` typedef.
The `_type_is_nullable` flag affects `GetRef<T>()`: non-nullable refs assert
non-null, nullable refs allow nullptr.

### UnsafeInit tag

`struct UnsafeInit {}` is an empty tag type. Constructing an ObjectRef with
`UnsafeInit{}` sets `data_` to nullptr without triggering non-null checks.
Primary use cases:

1. **Internal construction**: `ObjectUnsafe::ObjectRefFromObjectPtr<T>` creates
   refs with UnsafeInit then assigns `data_`.
2. **Field initialization**: non-default-constructible ObjectRef fields are
   first UnsafeInit'd then set via reflection setters.
3. **`ObjectRef::as<T>()`**: creates a temporary ref with UnsafeInit, assigns
   the data pointer, returns it:

```cpp
template <typename ObjectRefType>
std::optional<ObjectRefType> as() const {
  if (data_ != nullptr && data_->IsInstance<typename ObjectRefType::ContainerType>()) {
    ObjectRefType ref(UnsafeInit{});
    ref.data_ = data_;
    return ref;
  }
  return std::nullopt;
}
```

### GetRef<T> and get()

`GetRef<RefType>(const ObjectType* ptr)` (in `cast.h`) converts a raw
`Object*` to a managed `RefType`, incrementing the reference count via
`ObjectPtrFromUnowned`. It checks nullability: non-nullable refs assert
non-null, nullable refs allow nullptr.

```cpp
template <typename RefType, typename ObjectType>
inline RefType GetRef(const ObjectType* ptr) {
  using ContainerType = typename RefType::ContainerType;
  static_assert(std::is_base_of_v<ContainerType, ObjectType>);
  if constexpr (is_optional_type_v<RefType> || RefType::_type_is_nullable) {
    if (ptr == nullptr) return /* null ref */;
  } else {
    TVM_FFI_ICHECK_NOTNULL(ptr);
  }
  return /* ObjectRef from ObjectPtrFromUnowned */;
}
```

`ObjectRef::get()` returns `const Object*` without releasing ownership. These
form a symmetric pair for crossing between raw pointer and managed reference
worlds. Common pattern: within a method on `FooObj`, use
`GetRef<Foo>(this)` to get a managed reference to self.

### Explicit registration: ObjectDef<T>

Before commit `9ac3121`, `TVM_FFI_DECLARE_OBJECT_INFO` contained a
`static _register_type_index` that auto-registered on DLL load, causing
binary bloat and unpredictable initialization ordering. After that commit,
auto-registration was removed. Types must be explicitly registered:

1. `reflection::ObjectDef<T>()` -- the recommended approach, registers both
   the type index and reflection metadata.
2. `T::_GetOrAllocRuntimeTypeIndex()` -- minimal registration without
   reflection.

`ObjectDef<T>` provides a builder API:

```cpp
TVM_FFI_STATIC_INIT_BLOCK() {
  namespace refl = tvm::ffi::reflection;
  refl::ObjectDef<MyObjectObj>()
      .def(refl::init<int64_t, ffi::String>())
      .def_rw("value", &MyObjectObj::value, "The integer value")
      .def_rw("name", &MyObjectObj::name, "The name string")
      .def("get_value", &MyObjectObj::GetValue, "Returns the value");
}
```

Static built-in types (Str, Bytes, Error, Function, etc.) are reserved at
`TypeTable` construction via `ReserveDepthOneObjectTypeIndex` rather than
through `ObjectDef`.

### Python cross-language lifetime

Python `Object` (defined in `object.pxi`) extends the Cython `CObject`
extension type, which holds `void* chandle` -- a raw pointer to the C++
`TVMFFIObject` header:

```cython
cdef class CObject:
    cdef void* chandle

    def __cinit__(self):
        self.chandle = NULL

    def __dealloc__(self):
        if self.chandle != NULL:
            CHECK_CALL(TVMFFIObjectDecRef(self.chandle))
            self.chandle = NULL
```

When a Python wrapper is created (via `make_ret_object`), the object handle
is stored directly into `chandle` with the refcount already at +1 from the
C++ side. No additional `IncRef` is needed. When the Python wrapper is
garbage-collected, `__dealloc__` fires `TVMFFIObjectDecRef` to decrement
the strong refcount.

Python aliasing does not increment the C++ refcount. Python's own GC tracks
references to the `CObject` wrapper. Only when the last Python reference is
collected does `__dealloc__` fire:

```python
obj = MyObject(42, "test")    # C++ refcount = 1
obj2 = obj                    # Python alias, C++ refcount still 1
del obj                       # Python alias removed, C++ refcount still 1
del obj2                      # Last Python reference, C++ refcount -> 0
```

The object return path in `make_ret_object`:

1. Check `TYPE_INDEX_TO_CLS` for a registered Python class.
2. Allocate Python wrapper via `cls.__new__(cls)`.
3. Set `chandle = result.v_obj` (ownership transferred, no extra `IncRef`).

Move semantics are expressed via `ObjectRValueRef`, which wraps an object to
signal to the FFI layer that ownership can be transferred.
`__init_handle_by_constructor__` uses a special `ConstructorCall` convention
where the result handle is set directly into the `CObject`.

## APIs

### C API

```c
// Type registration
int TVMFFITypeGetOrAllocIndex(const TVMFFIByteArray* type_key,
                              int32_t static_type_index, int32_t type_depth,
                              int32_t num_child_slots, int child_slots_can_overflow,
                              int32_t parent_type_index);

// Type info lookup
const TVMFFITypeInfo* TVMFFIGetTypeInfo(int32_t type_index);
int TVMFFITypeKeyToIndex(const TVMFFIByteArray* type_key, int32_t* out_tindex);

// Object refcount management
int TVMFFIObjectIncRef(TVMFFIObjectHandle obj);
int TVMFFIObjectDecRef(TVMFFIObjectHandle obj);

// Deleter flag bitmask
enum TVMFFIObjectDeleterFlagBitMask {
  kTVMFFIObjectDeleterFlagBitMaskStrong = 1,
  kTVMFFIObjectDeleterFlagBitMaskWeak   = 2,
  kTVMFFIObjectDeleterFlagBitMaskBoth   = 3,
};
```

### C++ API

```cpp
namespace tvm { namespace ffi {
// Allocation
template <typename T, typename... Args>
ObjectPtr<T> make_object(Args&&... args);

template <typename ArrayType, typename ElemType, typename... Args>
ObjectPtr<ArrayType> make_inplace_array_object(size_t num_elems, Args&&... args);

// Smart pointers
template <typename T> class ObjectPtr;       // strong reference
template <typename T> class WeakObjectPtr;   // weak reference

// Base classes
class Object;      // data base class
class ObjectRef;   // reference wrapper base class

// Casting
template <typename RefType, typename ObjectType>
RefType GetRef(const ObjectType* ptr);

template <typename BaseType, typename ObjectType>
ObjectPtr<BaseType> GetObjectPtr(ObjectType* ptr);

// Tag type
struct UnsafeInit {};

// Registration
namespace reflection {
  template <typename Class> class ObjectDef;
  template <typename... Args> class init;
}
}}
```

### Python API

```python
class Object(CObject):
    """Base class of all TVM FFI objects."""
    def same_as(self, other) -> bool: ...
    def _move(self) -> ObjectRValueRef: ...
    def __init_handle_by_constructor__(self, fconstructor, *args): ...
    def __ffi_init__(self, *args): ...

class ObjectRValueRef:
    """Rvalue reference wrapper for move semantics."""
    obj: Object

class ObjectConvertible:
    """Base class for Python objects convertible to Object."""
    def asobject(self) -> Object: ...
```

## Implementation

| File | Role |
|------|------|
| `include/tvm/ffi/c_api.h` | `TVMFFIObject` struct, `TVMFFITypeIndex` enum, `TVMFFIObjectDeleterFlagBitMask` |
| `include/tvm/ffi/object.h` | `Object`, `ObjectPtr<T>`, `WeakObjectPtr<T>`, `ObjectRef`, `UnsafeInit`, `IsObjectInstance`, declare/define macros |
| `include/tvm/ffi/memory.h` | `make_object`, `SimpleObjAllocator`, `AlignedAlloc`, deleter implementation |
| `include/tvm/ffi/cast.h` | `GetRef<T>`, `GetObjectPtr<T>` |
| `include/tvm/ffi/reflection/registry.h` | `ObjectDef<T>`, `init<Args...>`, builder API for type registration |
| `src/ffi/object.cc` | `TypeTable` singleton, `GetOrAllocTypeIndex`, `ReserveDepthOneObjectTypeIndex`, runtime type registry |
| `python/tvm_ffi/cython/object.pxi` | `CObject`, `Object`, `make_ret_object`, Python lifetime model |
| `python/tvm_ffi/cython/base.pxi` | Cython `TVMFFIObject` declaration, `TVMFFIObjectDecRef` |

## History

- **13436f0** 2025-09-25 — `TVMFFIObject` header reordered: ref counts placed first to align with PyTorch `intrusive_ptr` ABI
- **43d13e8** 2025-09-26 — Combined strong/weak refcount into single `uint64_t`; single-atomic fast path for common deletion case
- **ca9c3d1** 2025-09-01 — Introduced weak reference counting support (`WeakObjectPtr<T>`, `IncWeakRef`/`DecWeakRef`, `TryPromoteWeakPtr`)
- **b64b46f** 2025-10-10 — Free-threaded Python build support; GIL-related lifetime adjustments
- **a08fa6e** 2025-09-09 — Streamlined object declaration macros; embedded type key directly in `TVM_FFI_DECLARE_OBJECT_INFO`; nullable/non-nullable variants
- **472e10c** 2025-09-08 — Introduced `UnsafeInit` tag for `ObjectRef` construction; enhanced null safety
- **9ac3121** 2025-10-14 — Removed static line-based auto-registration in favor of explicit `ObjectDef<T>` registration
- **4be1af7** 2025-08-08 — Moved `Downcast` out of FFI core; all downcasting now goes through `IsInstance` + `static_cast` via `as<T>()`

## Related

- `.repo-knowledge/adr/009-combined-refcount-abi.md` — ADR for the combined reference count design
- `.repo-knowledge/design/003-c-abi-stability.md` — C ABI stability covering `TVMFFIObject` layout
- `.repo-knowledge/design/004-reflection-system.md` — Reflection system and `ObjectDef<T>` builder
- `.repo-knowledge/design/005-structural-equal-hash.md` — Structural equality that depends on the type index system
- `.repo-knowledge/design/012-error-handling.md` -- Error object lifetime and `ErrorObj` destructor
- `.repo-knowledge/design/013-function-calling-convention.md` -- Function calling convention and `FunctionObj` lifecycle
