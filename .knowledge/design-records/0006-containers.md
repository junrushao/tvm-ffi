---
status: "active"
confidence: "high"
---
# Container Library

**TL;DR**.
- The container library provides immutable and mutable collections that store elements as `Any` values inline, enabling `Array<int>` to work directly without boxing primitives. All containers are ref-counted objects following the `FooObj`+`Foo` pattern.
- `Array<T>` is immutable with inline `Any` elements (inplace array pattern); `Map<K,V>` is insertion-ordered with separate key/value `Any` arrays. Both use `TypeTraits<T>::CheckAnyStrict` for element type enforcement.
- Supporting types include `String` (immutable UTF-8), `Bytes` (immutable byte buffer), `Shape` (immutable int64 array), `Tensor` (DLPack-compatible tensor, renamed from NDArray in `3a551d8`), `Tuple` (fixed-size heterogeneous), `Variant<V...>` (tagged union of ObjectRef subtypes), and `Optional<T>` (nullable wrapper).

## Problem Statement

### Background
- FFI containers must be usable from C++, Python, and Rust, requiring ref-counted objects that follow the Object system.
- Prior designs required boxing primitives (wrapping int in a heap object) to store them in containers, creating allocation overhead.
- Map implementations commonly use hash maps that do not preserve insertion order, making serialization non-deterministic.

### Solution
- Store elements as `Any` values inline. Since `Any` is a 16-byte tagged union that stores POD values directly, `Array<int>` holds ints without heap allocation per element.
- `ArrayObj` uses the inplace array pattern: elements are allocated as trailing storage after the object header, avoiding a separate heap allocation for the backing buffer.
- `MapObj` uses insertion-ordered storage with parallel key/value `Any` arrays, preserving insertion order for deterministic serialization.

### Goals
- Zero-boxing for POD values in containers.
- Type-safe element access via `TypeTraits<T>::CheckAnyStrict`.
- Insertion-ordered Map for deterministic behavior.
- Immutable containers (Array, Map) for safe sharing across threads.
- Non-goal: thread-safe mutation; concurrent container access.

## Design

```mermaid
graph TD
    subgraph "Immutable Containers"
        ArrayObj["ArrayObj : Object<br/>InplaceArrayBase&lt;ArrayObj, Any&gt;<br/>inline Any[] elements"]
        Array["Array&lt;T&gt; : ObjectRef<br/>typed view over ArrayObj"]
        MapObj["MapObj : Object<br/>insertion-ordered<br/>dense arrays + hash index"]
        Map["Map&lt;K,V&gt; : ObjectRef<br/>typed view over MapObj"]
    end
    subgraph "Value Types"
        BytesBaseCell["BytesBaseCell (internal)<br/>dual small/large repr<br/>stores TVMFFIAny"]
        String["String : value type<br/>backed by BytesBaseCell<br/>SSO for ≤7 bytes"]
        Bytes["Bytes : value type<br/>backed by BytesBaseCell<br/>SSO for ≤7 bytes"]
        ShapeObj["ShapeObj : Object<br/>TVMFFIShapeCell layout<br/>inline int64[]"]
        Shape["Shape : ObjectRef"]
    end
    subgraph "Tensor"
        TensorObj["TensorObj : Object<br/>DLTensor layout<br/>strides always non-null"]
        Tensor["Tensor : ObjectRef<br/>shape(), strides(), IsContiguous(), IsAligned()"]
        TensorView["TensorView<br/>non-owning DLTensor view<br/>storage_enabled=false"]
    end
    subgraph "Algebraic Types"
        Tuple["Tuple : ObjectRef<br/>fixed-size heterogeneous"]
        Variant["Variant&lt;V...&gt; : ObjectRef<br/>tagged union of ObjectRefs"]
        Optional["Optional&lt;T&gt;<br/>nullable wrapper"]
    end

    ArrayObj --> Array
    MapObj --> Map
    BytesBaseCell --> String
    BytesBaseCell --> Bytes
    ShapeObj --> Shape
    TensorObj --> Tensor
    TensorObj --> TensorView
```

### Key Classes, Fields and Interfaces

```python
class ArrayObj(Object):
    """Immutable array with inline Any elements (inplace array pattern)."""
    _type_index: ClassVar[int32] = kTVMFFIArray  # 69
    _type_key: ClassVar[str] = "ffi.Array"
    size_: int64                # number of active elements
    capacity_: int64            # allocated slots
    # Trailing storage: Any[capacity_] allocated inline after the object header
    # Invariant: elements stored as Any (16 bytes each), inline after ArrayObj fields
    # Invariant: for Array<T>, all elements satisfy TypeTraits<T>::CheckAnyStrict
    # Interacts with: InplaceArrayBase (CRTP mixin for trailing array access)

    def size(self) -> int: ...
    def at(self, i: int64) -> Any: ...
    def begin(self) -> Any_ptr: ...
    def end(self) -> Any_ptr: ...
    @staticmethod
    def Empty(n: int64) -> ObjectPtr[ArrayObj]:
        """Allocate with capacity n, size 0."""
        # Interacts with: make_inplace_array_object (allocates header + trailing storage)
    @staticmethod
    def CopyFrom(cap: int64, source: ArrayObj) -> ObjectPtr[ArrayObj]:
        """Deep-copy elements from source into new array."""
    @staticmethod
    def MoveFrom(cap: int64, source: ArrayObj) -> ObjectPtr[ArrayObj]:
        """Move elements from source into new array (source becomes empty)."""
    # Extension: use Array<T> wrapper for typed access

class Array[T](ObjectRef):
    """Typed immutable array reference."""
    def __getitem__(self, i: int) -> T:
        """Access element with automatic TypeTraits<T> conversion."""
    def size(self) -> int: ...
    def push_back(self, val: T) -> Array[T]:
        """Return new array with val appended (COW semantics)."""
        # If unique(): mutate in place; otherwise: copy, then mutate
    # Invariant: all elements satisfy TypeTraits<T>::CheckAnyStrict
    # Interacts with: ArrayObj, TypeTraits<T>

class MapObj(Object):
    """Insertion-ordered map with Any keys and Any values."""
    _type_index: ClassVar[int32] = kTVMFFIMap  # 70
    _type_key: ClassVar[str] = "ffi.Map"
    slots_: uint64           # bit 63 = SmallMap tag (1=SmallMap, 0=DenseMap)
    data_: Any_ptr           # pointer to key/value storage
    data_deleter_: Callable  # cleanup for data_
    kSmallTagMask: ClassVar[uint64] = 1 << 63  # MSB tag bit

    def IsSmallMap(self) -> bool:
        """Check MSB tag: 1=SmallMap, 0=DenseMap."""
        # return (slots_ & kSmallTagMask) != 0
    # Invariant: preserves insertion order for iteration
    # Invariant: keys are compared by structural equality (SameAs for objects, value for POD)
    # Invariant: usable slot count = slots_ & ~kSmallTagMask for SmallMap, slots_ directly for DenseMap
    # Interacts with: SmallMapObj (<=4 entries, linear probe), DenseMapObj (Robin Hood hash)

class Map[K, V](ObjectRef):
    """Typed immutable map reference."""
    def __getitem__(self, key: K) -> V: ...
    def count(self, key: K) -> int: ...
    def __len__(self) -> int: ...
    def Set(self, key: K, value: V) -> Map[K, V]:
        """Return new map with key->value added (COW)."""
    # Interacts with: MapObj, TypeTraits<K>, TypeTraits<V>

class BytesBaseCell:
    """Internal backing cell for String and Bytes value types."""
    data_: TVMFFIAny  # private
    # Dual representation:
    #   Small (<=7 bytes): type_index = kTVMFFISmallStr/kTVMFFISmallBytes, data in v_bytes
    #   Large (>7 bytes): type_index = kTVMFFIStr/kTVMFFIBytes, v_obj points to heap object
    # Invariant: if type_index >= kTVMFFIStaticObjectBegin, ref-counted
    # Invariant: if type_index is kTVMFFINone, cell is null (used by Optional)
    # Interacts with: String, Bytes, Optional<String>, Optional<Bytes>

    def data(self) -> const_char_ptr: ...
        # Small: returns &data_.v_bytes; Large: returns heap object's byte array
    def size(self) -> size_t: ...
        # Small: returns data_.small_str_len; Large: returns heap object's size
    def InitSpaceForSize(self, size: int, small_type_index: int, large_type_index: int) -> char_ptr: ...
        # If size <= 7: inline storage; If size > 7: heap-allocates
    def MoveToAny(self, result: TVMFFIAny_ptr) -> None: ...
    def CopyToTVMFFIAny(self) -> TVMFFIAny: ...

class String:
    """Immutable UTF-8 string. Value type backed by BytesBaseCell (NOT an ObjectRef)."""
    data_: BytesBaseCell  # private
    # Invariant: type_index is kTVMFFISmallStr (<=7 bytes) or kTVMFFIStr (heap)
    # Invariant: never None (use Optional<String> for nullable)
    def data(self) -> const_char_ptr: ...   # noexcept
    def c_str(self) -> const_char_ptr: ...  # noexcept
    def size(self) -> size_t: ...           # noexcept
    def __eq__(self, other: str) -> bool: ...
    def __hash__(self) -> int: ...
    # Interacts with: TypeTraits<String> (standalone specialization, not ObjectRefWithFallbackTraitsBase)

class Bytes:
    """Immutable byte buffer. Value type backed by BytesBaseCell (NOT an ObjectRef)."""
    data_: BytesBaseCell  # private
    # Invariant: type_index is kTVMFFISmallBytes (<=7 bytes) or kTVMFFIBytes (heap)
    def data(self) -> const_char_ptr: ...
    def size(self) -> size_t: ...
    # Interacts with: TypeTraits<Bytes> (standalone specialization)

class Optional_String:
    """Zero-overhead nullable String. Uses BytesBaseCell null state (kTVMFFINone)."""
    data_: String  # private; null when data_.data_.type_index == kTVMFFINone
    # Invariant: sizeof(Optional<String>) == sizeof(String) -- no extra flag byte

class ShapeView:
    """Lightweight non-owning view over shape data (pointer+size). Analogous to span<int64>. (8ca0719)"""
    data: Ptr[int64]  # raw pointer, non-owning
    size: int         # number of elements
    # Invariant: underlying data must outlive the view
    # Interacts with: Shape (implicit conversion both ways), Tensor.shape(), Tensor.strides()
    # Extension: use ShapeView instead of Shape where possible to avoid heap allocation

    def __getitem__(self, idx: int) -> int64: ...  # unchecked
    def at(self, idx: int) -> int64: ...           # bounds-checked, throws IndexError
    def Product(self) -> int64: ...                # product of all elements

class Shape(ObjectRef):
    """Managed immutable int64 array for tensor shapes. When possible, prefer ShapeView. (8ca0719)"""
    _type_index: ClassVar[int32] = kTVMFFIShape  # 71
    # Interacts with: TVMFFIShapeGetCellPtr (C API accessor), ShapeView (implicit conversion)
    # Invariant: all elements are non-negative (convention, not enforced)

    def __init__(self, view: ShapeView): ...  # construct from view
    def __shapeview__(self) -> ShapeView: ... # implicit conversion to ShapeView
    @staticmethod
    def StridesFromShape(shape: ShapeView) -> Shape:
        """Compute contiguous (row-major) strides. Parameter changed from (data,ndim) to ShapeView (8ca0719)."""
        ...

def FillStridesFromShape(shape: ShapeView, out_strides: Ptr[int64]) -> None:
    """Fill strides in-place from shape view without heap allocation. (8ca0719)"""
    # Interacts with: TensorObjFromNDAlloc, TensorObjFromDLPack

class TensorObj(Object):
    """DLPack-compatible tensor object (renamed from NDArrayObj in 3a551d8)."""
    _type_index: ClassVar[int32] = kTVMFFITensor  # 70
    _type_key: ClassVar[str] = "ffi.Tensor"
    # DLTensor follows header at offset sizeof(TVMFFIObject) = 24 bytes
    # Shape and strides are stored inplace after the object body using make_inplace_array_object (8ca0719)
    # Removed: shape_data_, strides_data_, cached_dl_managed_tensor_versioned_ fields (8ca0719)
    # Invariant: strides is always non-null after construction
    # Interacts with: DLPack managed tensor protocol, make_inplace_array_object

class Tensor(ObjectRef):
    """DLPack-compatible tensor ref wrapper (renamed from NDArray in 3a551d8)."""
    _type_index: ClassVar[int32] = kTVMFFITensor  # 70

    def shape(self) -> ShapeView:
        """Return shape as non-owning ShapeView (no heap allocation). Was Shape before 8ca0719."""
        ...
    def strides(self) -> ShapeView:
        """Return strides as non-owning ShapeView. Was Shape before 8ca0719."""
        # Invariant: strides may be null iff ndim == 0 (4fefeb0); checked via TVM_FFI_ICHECK(strides != nullptr || ndim == 0)
        ...
    def data_ptr(self) -> void_ptr:
        """Raw data pointer. (8ca0719)"""
        ...
    def device(self) -> DLDevice:
        """Device of the tensor. (0dcd4d2)"""
        ...
    def ndim(self) -> int32:
        """Number of dimensions. (8ca0719)"""
        ...
    def dtype(self) -> DLDataType:
        """Data type. (0dcd4d2)"""
        ...
    def size(self, idx: int64) -> int64:
        """Shape element at given index. Supports negative indexing (wraps from end). (0dcd4d2, 573d76f)"""
        ...
    def stride(self, idx: int64) -> int64:
        """Stride element at given index. Supports negative indexing (wraps from end). (0dcd4d2, 573d76f)"""
        ...
    def dim(self) -> int32:
        """ATen-style alias for ndim(). (573d76f)"""
        ...
    def sizes(self) -> ShapeView:
        """ATen-style alias for shape(). (573d76f)"""
        ...
    def is_contiguous(self) -> bool:
        """ATen-style alias for IsContiguous(). (573d76f)"""
        ...
    def numel(self) -> int64:
        """Number of elements (product of shape). (8ca0719)"""
        ...
    def byte_offset(self) -> uint64:
        """Byte offset of the data pointer. (0dcd4d2)"""
        ...
    def GetDLTensorPtr(self) -> const_DLTensor_ptr:
        """Explicit raw DLTensor* access. Replaces operator->(). (0dcd4d2)"""
        ...
    def IsContiguous(self) -> bool: ...
    def IsAligned(self, alignment: int) -> bool:
        """Check if tensor data meets alignment requirement."""
        # Interacts with: IsDirectAddressDevice (only direct-address devices checked)
        ...
    # operator->() removed in 0dcd4d2; use method accessors or GetDLTensorPtr()
    # get() is now a protected method returning const TensorObj*
    # Interacts with: TVMFFITensorGetDLTensorPtr, TVMFFITensorFromDLPack, TVMFFITensorToDLPack
    # Extension: supports DLManagedTensor and DLManagedTensorVersioned for zero-copy sharing

class TensorView:
    """Non-owning view of a DLTensor. Stores a copy of DLTensor by value. (1ec6236)"""
    # Constructors:
    #   TensorView(const Tensor&)   — copies DLTensor from owning Tensor
    #   TensorView(const DLTensor*) — copies DLTensor from raw pointer
    #   TensorView(Tensor&&) = delete  — prevents accidental move from owned Tensor
    # Invariant: user must ensure underlying DLTensor (data, shape, strides) outlives TensorView
    # Invariant: strides may be null iff ndim == 0 (4fefeb0)
    def shape(self) -> ShapeView: ...
    def strides(self) -> ShapeView:
        """Returns strides view. Asserts strides != nullptr || ndim == 0. (4fefeb0)"""
        ...
    def data_ptr(self) -> void_ptr: ...
    def ndim(self) -> int32: ...
    def numel(self) -> int64: ...
    def dtype(self) -> DLDataType: ...
    def size(self, idx: int64) -> int64:
        """Shape element at given index. Supports negative indexing. (573d76f)"""
        ...
    def stride(self, idx: int64) -> int64:
        """Stride element at given index. Supports negative indexing. (573d76f)"""
        ...
    def dim(self) -> int32:
        """ATen-style alias for ndim(). (573d76f)"""
        ...
    def sizes(self) -> ShapeView:
        """ATen-style alias for shape(). (573d76f)"""
        ...
    def is_contiguous(self) -> bool:
        """ATen-style alias for IsContiguous(). (573d76f)"""
        ...
    def IsContiguous(self) -> bool: ...
    # Interacts with: TypeTraits<TensorView> (storage_enabled=false, cannot be stored in Any)
    # Interacts with: Tensor (implicit construction from Tensor& via DLTensor copy)
    # Extension: use TensorView as FFI function parameter type for non-owning tensor access

    # TypeTraits<TensorView> specialization:
    #   storage_enabled = False  — cannot be stored in Any (no ownership)
    #   field_static_type_index = kTVMFFIDLTensorPtr
    #   CopyToAnyView: type_index=kTVMFFIDLTensorPtr, v_ptr=DLTensor*
    #   CheckAnyStrict: type_index == kTVMFFIDLTensorPtr only
    #   TryCastFromAnyView: accepts kTVMFFIDLTensorPtr OR kTVMFFITensor (implicit promotion)
    #     When kTVMFFITensor: extracts DLTensor* via TVMFFITensorGetDLTensorPtr
    #   MoveToAny/MoveFromAny: deliberately NOT defined (storage_enabled=false)

def GetDataSize(tensor: Tensor) -> size_t:
    """Compute total data size in bytes for a Tensor. (0dcd4d2)"""
    ...
def GetDataSize(tensor: TensorView) -> size_t:
    """Compute total data size in bytes for a TensorView. (0dcd4d2)"""
    ...

def IsDirectAddressDevice(device: DLDevice) -> bool:
    """Returns True for devices where data pointer addresses reflect real memory alignment.
    Covers: CPU, CUDA, CUDAHost, CUDAManaged, ROCm, ROCmHost."""
    # Interacts with: Tensor.IsAligned (determines if pointer-based alignment check applies)
    # Invariant: device_type <= kDLCUDAHost covers CPU/CUDA/OpenCL/Vulkan/Metal/VPI/ROCM/CUDAHost

class Shape(ObjectRef):
    # ... (see above)
    # StridesFromShape now takes ShapeView parameter (see above definition)

class Tuple(ObjectRef):
    """Fixed-size heterogeneous container backed by ArrayObj."""
    # Same underlying ArrayObj storage but semantically fixed-size
    # Interacts with: ArrayObj (reuses storage)

class Variant[*V](ObjectRef):
    """Tagged union of ObjectRef subtypes."""
    # Stores one of V... as a ref-counted object
    # Type discrimination via IsInstance checks
    # Invariant: exactly one variant is active at a time
    # Extension: add new variant types at compile time

class Optional[T]:
    """Nullable wrapper for FFI types."""
    # For ObjectRef: nullptr means empty (no separate flag needed)
    # For POD: wraps std::optional<T>
    # Interacts with: TypeTraits<Optional<T>> (accepts kTVMFFINone)
```

### Inplace Array Pattern

```python
# ArrayObj uses InplaceArrayBase<ArrayObj, Any> to store elements
# as trailing storage after the object fields.
#
# Memory layout:
# [TVMFFIObject header (24 bytes)]
# [ArrayObj fields: size_, capacity_ (16 bytes)]
# [Any[0], Any[1], ..., Any[capacity_-1]]  (16 bytes each, trailing)
#
# Allocation:
# make_inplace_array_object<ArrayObj, Any>(capacity)
#   = new (alloc(sizeof(ArrayObj) + sizeof(Any) * capacity)) ArrayObj
#
# Benefits:
# - Single allocation for header + elements
# - Cache-friendly: elements are contiguous after header
# - No separate heap allocation for backing buffer
```

### Contracts, Assumptions and Invariants
- **Array<T> element type invariant**: Every element in `Array<T>` satisfies `TypeTraits<T>::CheckAnyStrict`. This is checked on insertion and ensured by copy-on-write operations. `Array<Any>` accepts any element (CheckAnyStrict always true for Any).
- **Map insertion order**: `Map<K,V>` preserves the order in which keys were first inserted. Iteration yields entries in insertion order, ensuring deterministic serialization.
- **String/Bytes dual representation**: Strings and Bytes are value types (not ObjectRef). Small strings (<=7 bytes) are stored inline in `TVMFFIAny.v_bytes`; large strings are heap-allocated objects with layout `{ TVMFFIObject, TVMFFIByteArray, trailing_chars[] }`. Cross-representation equality and hashing are guaranteed: a small "hello" and a heap-allocated "hello" compare equal and produce the same hash.
- **Map MSB tag protocol**: Bit 63 of `MapObj::slots_` distinguishes SmallMap (bit set) from DenseMap (bit clear). Usable slot count accessed via `SmallMapObj::NumSlots()` / `DenseMapObj::NumSlots()` which mask off the tag. All dispatch uses `IsSmallMap()` instead of raw slot-count thresholds.
- **Tensor method-based API**: Since `0dcd4d2`, Tensor and TensorView expose method accessors (`data_ptr()`, `device()`, `ndim()`, `dtype()`, `size(idx)`, `stride(idx)`, `byte_offset()`, `numel()`). `operator->()` is removed from both; use `GetDLTensorPtr()` for raw DLTensor* access. `TensorView` gains matching methods.
- **DLPack _no_sync convention**: Since `22a78943`, all DLPack from/to conversions use `*_no_sync` naming, separating stream synchronization from tensor exchange. Callers must handle synchronization explicitly. `current_work_stream` is a separate function pointer in `DLPackExchangeAPI`.
- **Tensor DLTensor offset**: `DLTensor` starts at exactly `sizeof(TVMFFIObject)` (24 bytes) from the object pointer. This is hard-coded in `TVMFFITensorGetDLTensorPtr` and in `TypeTraits<DLTensor*>::TryConvertFromAnyView`.
- **Tensor strides always non-null (with zero-dim exception)**: After `ca95b41`, all TVM-constructed tensors have `strides != nullptr`. The previous DLPack convention of `strides == nullptr` for contiguous layout is eliminated at construction time. DLPack import fills in strides when the incoming tensor has `strides == nullptr`. DLPack export always includes strides. **Exception**: zero-dimensional tensors (`ndim == 0`) may have `strides == nullptr` per DLPack convention; all accessors and `FromDLPack*` constructors enforce `strides != nullptr || ndim == 0` (`4fefeb0`).
- **Relaxed DLPack import defaults**: `from_dlpack()` defaults to `require_alignment=0, require_contiguous=False` (`1b824e8`), making tensor import succeed without manual opt-out. Callers needing strict checks pass explicit parameters or use `Tensor.IsAligned()`/`Tensor.IsContiguous()` after import.
- **Copy-on-write (COW)**: Immutable containers (Array, Map) use COW for mutation methods. If `use_count() == 1`, mutate in place; otherwise, copy first. This enables efficient functional-style APIs.

### Extension Points
- **Custom container element types**: Any type with a `TypeTraits` specialization can be stored in `Array<T>` and used as Map keys/values.
- **Tensor DLPack interop**: `TVMFFITensorFromDLPack`/`TVMFFITensorToDLPack` enable zero-copy tensor sharing with frameworks like PyTorch and NumPy.
- **Variant extension**: `Variant<A, B, C>` can hold any of the listed types. Adding new variant members is a compile-time change.

### Usage Examples

#### Creating and using typed arrays
**Context**: Working with Array<int> that stores ints directly (no boxing).
```cpp
// Create array from initializer list -- ints stored inline as Any
Array<int> arr({1, 2, 3, 4, 5});
int sum = 0;
for (int i = 0; i < arr.size(); ++i) {
  sum += arr[i];  // TypeTraits<int>::CopyFromAnyStorageAfterCheck
}
// sum == 15

// Functional append (COW: copies only if shared)
Array<int> arr2 = arr;      // shared (refcount 2)
Array<int> arr3 = arr2.push_back(6);  // arr2 is shared, so copy+append

// Mixed type array
Array<Any> mixed({42, String("hello"), 3.14});
```

#### String and Map usage across FFI
**Context**: Creating a String-keyed Map in C++ and passing it to Python via FFI.
```cpp
// String construction from various sources
String s1("hello");                  // from const char*
String s2 = std::string("world");   // from std::string

// Insertion-ordered map
Map<String, int> m({{"a", 1}, {"b", 2}, {"c", 3}});
int v = m["b"];  // v == 2
// Iteration: "a"->1, "b"->2, "c"->3 (insertion order preserved)

// Pass through FFI -- Map<String, int> is an ObjectRef, stored in Any
Any val = m;  // type_index = kTVMFFIMap, v_obj = MapObj*
```

#### Using TensorView as a non-owning kernel argument
**Context**: When an FFI function does not need to retain tensor ownership, use `TensorView` to accept both `Tensor` and raw `DLTensor*` callers.
```cpp
// C++ kernel accepting TensorView (no ownership transfer)
TVM_FFI_DLL_EXPORT_TYPED_FUNC(add_one, [](ffi::TensorView x, ffi::TensorView y) -> void {
    int64_t n = x.numel();
    const float* px = static_cast<const float*>(x.data_ptr());
    float* py = static_cast<float*>(y.data_ptr());
    for (int64_t i = 0; i < n; ++i) py[i] = px[i] + 1.0f;
});
// Python caller: mod.add_one(x_tensor, y_tensor) — TryCastFromAnyView promotes Tensor to TensorView
```

## Alternatives & Trade-offs
### Boxed primitives in containers (rejected)
- Pros: Uniform treatment of all elements as heap objects; simpler container implementation.
- Cons: Heap allocation per primitive element; 10-100x slower for arrays of ints/floats; defeats the purpose of the unified Any value system.

### std::unordered_map for Map (rejected)
- Pros: Standard library; O(1) average lookup.
- Cons: Non-deterministic iteration order breaks serialization reproducibility; cannot share across C ABI boundary; no ref-counting.

## Related Work
### Design Records
- `0001-any-anyview-value-system.md` -- Any is the element storage type for all containers
- `0002-object-system.md` -- All containers follow the Object/ObjectRef pattern with make_inplace_array_object
- `0005-type-traits-protocol.md` -- CheckAnyStrict enforces container element types; TypeTraits enables custom element types
- `0007-c-abi.md` -- TVMFFIByteArray, TVMFFIShapeCell, DLTensor layout contracts

### Evidence Matrix
- Array inplace pattern -> `commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `ArrayObj`, `InplaceArrayBase`
- Map insertion order -> `commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `MapObj`
- String/Bytes SSO and BytesBaseCell -> `commits/2025-08-04-49e2ed4a...md` + `49e2ed4` + `BytesBaseCell`, `kTVMFFISmallStr`
- Tensor (was NDArray) DLPack interop -> `commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `NDArray`, `TVMFFINDArrayFromDLPack`
- No-boxing for POD in Array -> `commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `Array<int>`, `Any`
- Map MSB tag protocol -> `commits/2025-08-09-03e8a6b8...md` + `03e8a6b` + `IsSmallMap`, `NumSlots`, `kSmallTagMask`
- Tuple re-export removed -> `commits/2025-08-06-ed56a5e7...md` + `ed56a5e` + `tvm::Tuple` removed
- NDArray->Tensor rename -> `commits/2025-09-06-3a551d83...md` + `3a551d8` + `TensorObj`, `Tensor`, `kTVMFFITensor`
- Strides always non-null -> `commits/2025-09-06-ca95b412...md` + `ca95b41` + `MakeStridesFromShape`, `stride_data_`
- Tensor::strides() accessor -> `commits/2025-09-06-6fa40b58...md` + `6fa40b5` + `Tensor::strides()`, `strides_data_`
- Relaxed DLPack import defaults, IsDirectAddressDevice -> `commits/2025-09-08-1b824e88...md` + `1b824e8` + `IsDirectAddressDevice`, `Tensor::IsAligned`
- Shape::StridesFromShape, UnsafeInit ctor -> `commits/2025-09-08-472e10c4...md` + `472e10c` + `Shape::StridesFromShape`, `UnsafeInit`
- tvm:: namespace re-exports removed -> `commits/2025-09-08-e9d29465...md` + `e9d2946` + `tvm::ffi::Array` required
- DLPack _no_sync convention, DLPackExchangeAPI -> `commits/2025-10-11-22a78943...md` + `22a78943` + `DLPackExchangeAPI`, `_no_sync`
- Tensor.strides Python property, DLPack v1.2 -> `commits/2025-10-12-83770118...md` + `8377011` + `Tensor.strides`, DLPack v1.2
- Tensor/TensorView method-based accessors, operator->() removed -> `commits/2025-10-14-0dcd4d2b...md` + `0dcd4d2` + `device()`, `size()`, `stride()`, `GetDLTensorPtr()`
- TensorView non-owning view type -> `commits/2025-10-01-1ec62367...md` + `1ec6236` + `TensorView`, `TypeTraits<TensorView>`
- Zero-dim strides null-check fix -> `commits/2025-10-01-4fefeb0f...md` + `4fefeb0` + `strides != nullptr || ndim == 0`
- ATen-style aliases (dim/sizes/is_contiguous) and negative indexing for size/stride -> `commits/2025-10-17-573d76f2...md` + `573d76f` + `dim()`, `sizes()`, `is_contiguous()`, `int64_t idx`
