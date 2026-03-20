---
status: "active"
confidence: "high"
---
# FFI Container Suite

**TL;DR**.
- The FFI provides a suite of ref-counted container types: `Array<T>` (immutable list), `Map<K,V>` (insertion-ordered immutable map), `String`, `Bytes`, `Shape` (int64 tuple), `Tensor` (DLPack tensor wrapper, renamed from NDArray), `TensorView` (non-owning DLTensor view, recommended for kernel signatures), `Tuple`, `Variant<T...>`, and `Optional<T>`.
- All containers follow the `XxxObj`/`Xxx` (data class / ref wrapper) pattern and have static type indices in the `[64, 128)` range for fast type checking.
- A key design choice: containers like `Array<T>` use the `TypeTraits<T>::CheckAnyStorage` invariant -- every element passes the strict storage check for type `T`. This enables zero-copy access when the container already stores the correct element types.
- `List<T>` provides a mutable sequence alongside immutable `Array<T>`. Both share `SeqBaseObj` (backed by `TVMFFISeqCell`), consolidating iteration, element access, and capacity management. `List` mutations are in-place (no copy-on-write); reference cycles are possible and handled by structural eq/hash and JSON serialization via cycle detection.
- `Dict<K,V>` provides a mutable mapping alongside immutable `Map<K,V>`. Both share the `MapBaseObj` base (backed by `DenseMapBaseObj`). `Dict` mutations are shared-reference (no COW) -- all handles pointing to the same `DictObj` see mutations immediately. `kTVMFFIDict = 76` is the static type index.

## Problem Statement
### Background
- Cross-language data structures need to be ref-counted, type-erased (passable as `Any`), and accessible from C, C++, Python, and Rust.
- Different mutability semantics are needed: `Array` and `Map` are immutable (safe for sharing), while mutable variants may be needed for construction.

### Solution
- Each container type has a fixed `TVMFFITypeIndex` in the static range, allowing efficient type discrimination without dynamic lookup.
- Container objects follow the standard `Object` header layout, enabling C API accessors via pointer arithmetic from the header.
- `String` and `Bytes` store a `TVMFFIByteArray` (pointer + size) immediately after the header, providing O(1) access from C bindings.

### Goals
- Type-safe containers visible to all language bindings.
- Immutable by default for safe cross-language sharing.
- Zero-copy interop with DLPack for `Tensor` (renamed from `NDArray`).
- Non-goal: general-purpose mutable collections (use `List`/`Dict` from later commits).

## Design

### Key Classes, Fields and Interfaces

```python
class BytesBaseCell:
    """Internal backing cell for String/Bytes. Wraps a TVMFFIAny directly.
    Handles ref-counting for large strings, no-op for small (inline) strings."""
    data_: TVMFFIAny
    # Invariant: if type_index >= kTVMFFIStaticObjectBegin, data_.v_obj is ref-counted (large)
    # Invariant: if type_index < kTVMFFIStaticObjectBegin, data_ holds inline bytes (small)
    def data(self) -> const_char_ptr: ...
    def size(self) -> size_t: ...
    def InitSpaceForSize(self, size: int, small_type_index: int, large_type_index: int) -> char_ptr: ...
        # Invariant: strings <= 7 bytes use small path, > 7 bytes use heap allocation
    def MoveToAny(self, result: TVMFFIAny_ptr) -> None: ...
    def CopyToTVMFFIAny(self) -> TVMFFIAny: ...
    # Interacts with: String, Bytes (both use BytesBaseCell as backing storage)
    # Interacts with: Optional<String>, Optional<Bytes> (use nullopt via BytesBaseCell)

class String:  # NOTE: no longer inherits ObjectRef
    """Immutable UTF-8 string. Backed by BytesBaseCell, not ObjectRef.
    Short strings (<= 7 bytes) stored inline in TVMFFIAny (kTVMFFISmallStr, no heap).
    Long strings heap-allocated via details::BytesObjStdImpl (kTVMFFIStr)."""
    _type_key = "ffi.String"
    npos: ClassVar[int] = -1  # static constexpr size_t(-1), sentinel for "not found"
    # Interacts with: TypeTraits<String> (field_static_type_index = kTVMFFIAny, not kTVMFFIStr)
    # Interacts with: AnyView (kTVMFFIRawStr -> String conversion in InplaceConvertAnyViewToAny)
    # Invariant: default-constructed String has type_index kTVMFFISmallStr (empty string)
    # Invariant: data is null-terminated regardless of small/large path
    # Extension: nullptr comparison operators are deleted (compile-time safety)

    def find(self, str: "String", pos: int = 0) -> int: ...
        # Overload 1: search for String; delegates to find(str.data(), pos, str.size())
    def find(self, str: "const char*", pos: int = 0) -> int: ...
        # Overload 2: search for const char*; delegates to find(str, pos, strlen(str))
    def find(self, str: "const char*", pos: int, count: int) -> int: ...
        # Overload 3: via std::string_view(data(), size()).find(std::string_view(str, count), pos)
        # Invariant: returns npos if no match found
        # Extension: follows std::string::find semantics exactly

    def substr(self, pos: int = 0, count: int = npos) -> "String": ...
        # Invariant: pos <= size(), else raises std::out_of_range
        # Invariant: actual count is min(count, size() - pos)
        # Interacts with: String(const char*, size_t) constructor (creates new owning String)

    def starts_with(self, prefix: "String | str_view | const_char_ptr", count: int = ...) -> bool: ...
        # Four overloads: String, string_view, const char*, (const char*, size_t) (02d1a96)
        # Invariant: count > size() returns false immediately (no OOB access)
        # Invariant: empty prefix always returns true
        # Interacts with: BytesBaseCell.data()/size() (raw buffer access), std::memcmp

    def ends_with(self, suffix: "String | str_view | const_char_ptr", count: int = ...) -> bool: ...
        # Four overloads: String, string_view, const char*, (const char*, size_t) (02d1a96)
        # Invariant: count > size() returns false immediately
        # Invariant: empty suffix always returns true
        # Interacts with: BytesBaseCell.data()/size(), std::memcmp

class Bytes:  # NOTE: no longer inherits ObjectRef
    """Immutable byte array. Backed by BytesBaseCell, not ObjectRef.
    Short bytes (<= 7 bytes) stored inline (kTVMFFISmallBytes), long bytes heap-allocated (kTVMFFIBytes)."""
    _type_key = "ffi.Bytes"
    # Same backing as String but uses kTVMFFISmallBytes/kTVMFFIBytes type indices

class Shape(ObjectRef):
    """Immutable int64 tuple for tensor shapes. Layout: TVMFFIObject + TVMFFIShapeCell + data."""
    _type_index = kTVMFFIShape  # 69
    # Interacts with: Tensor (shape of tensor), TVMFFIShapeGetCellPtr C API accessor
    # Interacts with: ShapeView (implicit conversion via operator ShapeView())
    # Note: operator[] is unchecked, at() is bounds-checked (swapped from pre-ShapeView convention)

class ShapeView:
    """Non-owning lightweight view over int64 shape data. Backed by TVMFFIShapeCell."""
    # Invariant: data pointer must outlive the ShapeView (non-owning)
    # Interacts with: Shape (implicit conversion Shape -> ShapeView via operator)
    # Interacts with: Tensor.shape(), Tensor.strides() (return ShapeView instead of Shape)
    # Extension: use ShapeView in any API that reads shape without needing ownership

    def __init__(self): ...                                     # default: null, size=0
    def __init__(self, data: Ptr[int64], size: int): ...        # from raw pointer + size
    def __init__(self, init: InitializerList[int64]): ...       # from initializer list

    def data(self) -> Ptr[int64]: ...
    def size(self) -> int: ...
    def Product(self) -> int64: ...
        # Invariant: returns 1 for empty shape (scalar)
    def __getitem__(self, idx: int) -> int64: ...               # unchecked
    def at(self, idx: int) -> int64: ...                        # bounds-checked, raises IndexError
    def begin(self) -> Ptr[int64]: ...
    def end(self) -> Ptr[int64]: ...
    def empty(self) -> bool: ...
    def front(self) -> int64: ...
    def back(self) -> int64: ...

class TensorObj(Object, DLTensor):
    """Managed tensor wrapping DLTensor. Layout: TVMFFIObject + DLTensor.
    Renamed from NDArrayObj. Shape/strides stored as trailing inplace int64 arrays."""
    # REMOVED: shape_data_, strides_data_, cached_dl_managed_tensor_versioned_, destructor
    _type_index = kTVMFFITensor  # 70 (was kTVMFFINDArray)
    _type_key = "ffi.Tensor"    # was "ffi.NDArray"
    # Invariant: DLTensor.strides may be null when ndim == 0 (scalar tensors);
    #            for ndim > 0, strides is always populated after construction
    # Invariant: shape/strides data stored as trailing int64 arrays after TensorObj struct
    #            (allocated via make_inplace_array_object, not separate Shape objects)
    # Interacts with: DLPack (TVMFFITensorFromDLPack/ToDLPack for zero-copy exchange)
    # Interacts with: TypeTraits<DLTensor*> (auto-converts Tensor to DLTensor*)
    # Invariant: DLTensor is at offset sizeof(TVMFFIObject) from object pointer

class Tensor(ObjectRef):
    """Managed tensor ref wrapper. Renamed from NDArray.
    No longer uses TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE; uses manual constructors
    + TVM_FFI_DEFINE_DEFAULT_COPY_MOVE_AND_ASSIGN + protected get(). operator->() removed."""

    # --- Accessors (replace removed operator->() field access) ---
    def data_ptr(self) -> Ptr[void]: ...     # get()->data
    def device(self) -> DLDevice: ...        # get()->device
    def ndim(self) -> int32: ...             # get()->ndim
    def dtype(self) -> DLDataType: ...       # get()->dtype
    def size(self, idx: int64) -> int64: ...   # get()->shape[idx]; negative index supported
        # Invariant: idx in range [-ndim, ndim); negative indices resolved as ndim + idx
        # Invariant: throws IndexError if adjusted idx out of range (enforced at runtime, e54d15d7)
    def stride(self, idx: int64) -> int64: ... # get()->strides[idx]; negative index supported
        # Invariant: idx in range [-ndim, ndim); strides may be null for scalar (ndim==0)
        # Invariant: throws IndexError if adjusted idx out of range (enforced at runtime, e54d15d7)
    def byte_offset(self) -> uint64: ...     # get()->byte_offset
    def shape(self) -> ShapeView: ...
        # Zero-alloc: reads DLTensor.shape/ndim directly (no caching)
    def strides(self) -> ShapeView: ...
        # Zero-alloc: reads DLTensor.strides/ndim directly (no caching)
    def numel(self) -> int64: ...            # shape().Product()
    def IsContiguous(self) -> bool: ...
    # --- Aten-style aliases (573d76f) ---
    def dim(self) -> int32: ...             # Alias for ndim()
    def sizes(self) -> ShapeView: ...       # Alias for shape()
    def is_contiguous(self) -> bool: ...    # Alias for IsContiguous()
        # Interacts with: ndim(), shape(), IsContiguous() (thin redirects)
        # Extension: add further PyTorch-compatible aliases following this pattern
    def IsAligned(self, alignment: int) -> bool: ...
        # Invariant: alignment=0 always returns True
        # Interacts with: IsDirectAddressDevice
    def GetDLTensorPtr(self) -> Ptr[const DLTensor]: ...
        # Replaces operator->() for callers needing the raw DLTensor pointer
    @staticmethod
    def FromDLPack(managed: DLManagedTensor, require_alignment: int = 0,
                   require_contiguous: bool = False) -> "Tensor": ...
    @staticmethod
    def FromDLPackVersioned(managed: DLManagedTensorVersioned, require_alignment: int = 0,
                            require_contiguous: bool = False) -> "Tensor": ...
    @staticmethod
    def FromNDAlloc(alloc: TNDAlloc, shape: ShapeView, dtype: DLDataType,
                    device: DLDevice, *extra_args) -> "Tensor": ...
        # Interacts with: make_inplace_array_object (allocates shape+strides after struct)
    def as_strided(
        self,
        shape: ShapeView,
        strides: ShapeView,
        element_offset: Optional[int64] = None,  # in dtype elements, not bytes
    ) -> "Tensor": ...
        # Creates a non-contiguous view sharing source tensor's data
        # Interacts with: TVMFFITensorCreateUnsafeView (C ABI call under the hood)
        # Interacts with: IsDirectAddressDevice (folds byte_offset into data pointer for CPU/CUDA)
        # Invariant: returned Tensor holds a ref to source, keeping source data alive
        # Invariant: element_offset >= 0
        # Extension: analogous to numpy.lib.stride_tricks.as_strided / torch.as_strided
    @staticmethod
    def FromNDAllocStrided(
        alloc: TNDAlloc, shape: ShapeView, strides: ShapeView,
        dtype: DLDataType, device: DLDevice, *extra_args,
    ) -> "Tensor": ...
        # Allocates tensor with explicit strides (e.g., column-major layout)
        # Invariant: shape.size() == strides.size()
    def ToDLPack(self) -> DLManagedTensor: ...
    def ToDLPackVersioned(self) -> DLManagedTensorVersioned: ...
        # Note: no longer caches — creates fresh DLManagedTensorVersioned each call

class TensorView:
    """Non-owning view of a DLTensor. Stores a shallow copy of the DLTensor struct.
    The caller must ensure the underlying data (including shape/strides memory) outlives this view.
    Recommended argument type for exported FFI kernel functions (instead of Tensor).
    operator->() removed; uses explicit accessor methods."""
    # Invariant: constructed from owning Tensor (must be defined()) or non-null DLTensor*
    # Invariant: explicitly deleted: TensorView(Tensor&&) and operator=(Tensor&&)
    #   Rationale: moving an owning Tensor into a non-owning view would drop the refcount
    # Interacts with: ShapeView (shape/strides return type)
    # Interacts with: TypeTraits<TensorView> (enables TensorView as FFI function parameter)
    # Extension: use TensorView in any API that reads tensor data without needing ownership

    def __init__(self, tensor: Tensor): ...
        # Copies DLTensor struct (not data) from Tensor
    def __init__(self, tensor: DLTensor_ptr): ...
        # Copies DLTensor struct from pointer

    # --- Accessors (replace removed operator->()) ---
    def data_ptr(self) -> void_ptr: ...
    def device(self) -> DLDevice: ...
    def ndim(self) -> int32: ...
    def dtype(self) -> DLDataType: ...
    def size(self, idx: int64) -> int64: ...  # negative index supported (idx in [-ndim, ndim))
    def stride(self, idx: int64) -> int64: ...  # negative index supported
    def byte_offset(self) -> uint64: ...
    def shape(self) -> ShapeView: ...
    def strides(self) -> ShapeView: ...
        # Invariant: strides may be null when ndim == 0; check is (strides != nullptr || ndim == 0)
    def numel(self) -> int64: ...
    def IsContiguous(self) -> bool: ...
    def as_strided(
        self,
        shape: ShapeView,
        strides: ShapeView,
        element_offset: Optional[int64] = None,
    ) -> "TensorView": ...
        # Non-owning strided view. Caller must ensure shape/strides arrays outlive the view.
        # Invariant: shape.size() == strides.size() (checked via ICHECK_EQ)
    # --- Aten-style aliases (573d76f) ---
    def dim(self) -> int32: ...             # Alias for ndim()
    def sizes(self) -> ShapeView: ...       # Alias for shape()
    def is_contiguous(self) -> bool: ...    # Alias for IsContiguous()

# --- Sentinel-based map lookup (438f6439, renamed 86c4042d) ---

def GetInvalidObject() -> ObjectRef:
    """Process-global singleton sentinel for invalid/missing values.
    Renamed from GetMissingObject / ffi.MapGetMissingObject (86c4042d)."""
    # Registered as global function: "ffi.GetInvalidObject"
    # Invariant: same object identity on every call (static local)
    # Interacts with: MapGetItemOrMissing (returns this on miss)
    # Interacts with: Python MISSING constant (initialized in core.pyx, identity-compared via `is`)

def MapGetItemOrMissing(map: MapObj, key: Any) -> Any:
    """Look up key; return value if found, MISSING sentinel if not. Never raises."""
    # Interacts with: MapObj.at() (delegates), GetInvalidObject() (on tvm::ffi::Error catch)
    # Extension: same sentinel pattern applicable to other container lookups

# --- Free functions ---
def GetDataSize(tensor: Tensor) -> int: ...   # Delegates to GetDataSize(tensor.numel(), tensor.dtype())
def GetDataSize(tensor: TensorView) -> int: ...  # Same delegation

# TypeTraits<TensorView> specialization:
#   storage_enabled = False  (cannot be stored in Any -- non-owning)
#   field_static_type_index = kTVMFFIDLTensorPtr
#   CopyToAnyView: stores pointer as kTVMFFIDLTensorPtr in TVMFFIAny.v_ptr
#   TryCastFromAnyView: accepts kTVMFFIDLTensorPtr (direct) OR kTVMFFITensor (via accessor)
#   No MoveToAny/MoveFromAny -- deliberately non-owning
#   Interacts with: AnyView (enables implicit TensorView -> AnyView conversion)
#   Interacts with: Function::FromTyped (enables TensorView as FFI function parameter type)
#   This is the first storage_enabled=false TypeTraits among view types (ShapeView has none)

def IsDirectAddressDevice(device: DLDevice) -> bool:
    """Check if device uses direct address where data pointer indicates alignment."""
    # Returns True for: device_type <= kDLCUDAHost, kDLCUDAManaged, kDLROCM, kDLROCMHost
    # Interacts with: Tensor.IsAligned(), DLPack device types

def FillStridesFromShape(shape: ShapeView, out_strides: Ptr[int64]) -> None:
    """Fill row-major strides into pre-allocated buffer. (details:: namespace)"""
    # Invariant: out_strides must have space for shape.size() elements
    # Interacts with: MakeStridesFromShape, TensorObjFromNDAlloc, TensorObjFromDLPack

def MakeStridesFromShape(shape: ShapeView) -> ObjectPtr[ShapeObj]:
    """Compute row-major strides from shape. (details:: namespace)."""
    # Invariant: strides[i] = product(shape[i+1:]); strides[-1] == 1
    # Interacts with: TensorObj construction, DLPack import

# Also available as static method:
# Shape.StridesFromShape(shape: ShapeView) -> Shape

class ArrayObj(SeqBaseObj):
    """Variable-length typed array with COW semantics. Inherits SeqBaseObj (9513c2f8)."""
    data_: void_ptr          # pointer to first element (may differ from inplace address)
    size_: int64
    capacity_: int64
    data_deleter_: Callable  # optional external data cleanup
    # Invariant: data_ == AddressOf(0) for inplace arrays; may point elsewhere for external storage
    # Invariant: if data_deleter_ is not None, called on data_ in ~ArrayObj()
    # Invariant: operator[] and SetItem check 0 <= i < size_ (ec56178e: added negative index check)
    # Extension: set data_ to external buffer + data_deleter_ for non-inplace storage

class SeqBaseObj(Object):
    """Abstract base for ArrayObj and ListObj; holds TVMFFISeqCell data."""
    # Backed by TVMFFISeqCell: { void* data; int64_t size; int64_t capacity; void (*data_deleter)(void*); }
    # Invariant: when data_deleter is nullptr, data is inplace (ArrayObj); when non-null, heap-allocated (ListObj)
    def size(self) -> int: ...
    def at(self, i: int) -> Any: ...
        # Invariant: bounds-checked; raises IndexError on out-of-range
    def front(self) -> Any: ...
    def back(self) -> Any: ...
    def begin(self) -> Iterator[Any]: ...
    def end(self) -> Iterator[Any]: ...
    def clear(self) -> None: ...
    # Interacts with: ArrayObj (refactored to inherit), ListObj (new)

class ListObj(SeqBaseObj):
    """Mutable sequence node; heap-allocated buffer with dynamic resizing."""
    # type_index: kTVMFFIList = 75
    # Invariant: NOT thread-safe; external sync required for concurrent access
    # Warning: reference cycles are possible (List containing itself); NOT gc'd by refcount alone
    # Interacts with: StructuralEqual, StructuralHash, json::Stringify (all with cycle detection)
    # Interacts with: TypeTraits<std::vector<T>> (accepts both kTVMFFIArray and kTVMFFIList)

class List(ObjectRef, Generic[T]):
    """Mutable ref wrapper for ListObj. Unlike Array, mutations are in-place (no COW)."""
    _type_index = kTVMFFIList  # 75
    _type_key = "ffi.List"
    def __init__(self, iterable: Iterable[T] = ...) -> None: ...
    def __getitem__(self, idx: int | slice) -> T | list[T]: ...
    def __setitem__(self, idx: int | slice, val: T | Iterable[T]) -> None: ...
    def __delitem__(self, idx: int | slice) -> None: ...
    def __len__(self) -> int: ...
    def append(self, val: T) -> None: ...
    def insert(self, idx: int, val: T) -> None: ...
    def pop(self, idx: int = -1) -> T: ...
    def extend(self, iterable: Iterable[T]) -> None: ...
    def clear(self) -> None: ...
    def reverse(self) -> None: ...
    # Interacts with: _ffi_api.List (constructor), _ffi_api.ListGetItem, ListSetItem, ListReplaceSlice
    # Interacts with: StructuralEqual, StructuralHash, json::Stringify (all with cycle detection)
    # Extension: Python @register_object("ffi.List") implements MutableSequence[T]

class Array(ObjectRef, Generic[T]):
    """Immutable typed array."""
    _type_index = kTVMFFIArray  # 69
    _type_key = "ffi.Array"    # renamed from "object.Array"
    # Invariant: all elements satisfy TypeTraits<T>::CheckAnyStrict
    # This enables zero-copy access: if CheckAnyStorage passes for all elements,
    # no per-element conversion needed when casting Array<Object> to Array<String>
    # Interacts with: TypeTraits<Array<T>> (recursive storage check)

    def __contains__(self, value: object) -> bool: ...
        # Delegates to ffi.ArrayContains FFI function (5bc7fcde)
        # O(n) linear scan using AnyEqual for element comparison
        # Interacts with: AnyEqual (structural equality), ArrayObj.begin()/end()
    def __bool__(self) -> bool: ...
        # Returns len(self) > 0 (46ab6448). Empty arrays are falsy.

class MapBaseObj(Object):
    """FFI-transparent base for all map specializations. No type index of its own.
    Follows BytesObjBase pattern: transparent to FFI type system.
    Extracted from MapObj into map_base.h (5a6b211)."""
    data_: void_ptr          # pointer to map data region
    size_: uint64
    slots_: uint64           # MSB (bit 63) is layout tag: 1=SmallMap, 0=DenseMap
    data_deleter_: Callable  # optional external data cleanup
    kSmallTagMask: ClassVar[uint64] = 1 << 63  # static constexpr
    # Invariant: sizeof(MapObj) == sizeof(MapBaseObj) (enforced by static_assert in subclasses)
    # Interacts with: SmallMapBaseObj, DenseMapBaseObj (via IsSmallMap dispatch)
    # Interacts with: TVM_FFI_DISPATCH_MAP / TVM_FFI_DISPATCH_MAP_CONST macros
    # Extension: subclass MapBaseObj to create new map variants with distinct type indices

    def IsSmallMap(self) -> bool: ...
        # Returns (slots_ & kSmallTagMask) != 0
        # Interacts with: TVM_FFI_DISPATCH_MAP macro, all dispatch points

    @staticmethod
    def Empty[MapObjType]() -> ObjectPtr[Object]: ...
        # Delegates to SmallMapBaseObj.Empty<MapObjType>()
    @staticmethod
    def CreateFromRange[MapObjType, IterType](first: IterType, last: IterType) -> ObjectPtr[Object]: ...
        # Routes to SmallMapBaseObj or DenseMapBaseObj based on capacity
    @staticmethod
    def InsertMaybeReHash[MapObjType](kv: KVType, map: ObjectPtr[Object]) -> None: ...
        # Stamps header_.type_index = MapObjType::RuntimeTypeIndex()
    @staticmethod
    def CopyFrom[MapObjType](from_: MapBaseObj) -> ObjectPtr[Object]: ...
    def clear(self) -> None: ...  # dispatches to SmallMapBaseObj/DenseMapBaseObj.clear()

    # Invariant: slots_ must NEVER be read directly; use NumSlots() accessor

class SmallMapBaseObj(MapBaseObj):
    """Small-capacity linear-scan map (<=4 entries). Uses inplace array storage.
    Renamed from SmallMapObj (5a6b211)."""
    # Invariant: data_ = reinterpret_cast<char*>(this) + sizeof(SmallMapBaseObj)
    #   (was InplaceArrayBase, now direct offset)
    def NumSlots(self) -> uint64: ...
        # Returns slots_ & ~kSmallTagMask (masks off tag bit)
    def clear(self) -> None: ...  # destroys entries, resets size to 0

class DenseMapBaseObj(MapBaseObj):
    """Array-based hash map with Fibonacci hashing. Renamed from DenseMapObj (5a6b211)."""
    # Invariant: header_.type_index stamped to MapObjType::RuntimeTypeIndex() at creation
    # static_assert: sizeof(MapObjType) == sizeof(MapBaseObj)
    # static_assert: is_base_of_v<MapBaseObj, MapObjType>
    def NumSlots(self) -> uint64: ...
        # Returns slots_ directly (MSB always clear for dense maps)
    def clear(self) -> None: ...  # clears entries without releasing memory

class MapObj(MapBaseObj):
    """Concrete map type with kTVMFFIMap type index. Thin subclass of MapBaseObj (5a6b211)."""
    _type_index = kTVMFFIMap  # 72
    # Invariant: sizeof(MapObj) == sizeof(MapBaseObj) (no additional fields)
    # Interacts with: Map<K,V> ref wrapper (friend), stl.h TypeTraits (CreateFromRange<MapObj>)

class Map(ObjectRef, Generic[K, V]):
    """Immutable insertion-ordered map."""
    _type_index = kTVMFFIMap  # 70
    _type_key = "ffi.Map"    # renamed from "object.Map"
    # Invariant: preserves insertion order
    # Invariant: SmallMapObj::CreateFromRange now deduplicates keys (last value wins)
    # Interacts with: TypeTraits<Map<K,V>> (recursive key/value storage check)

    def __bool__(self) -> bool: ...
        # Returns len(self) > 0 (46ab6448). Empty maps are falsy.

class DictObj(MapBaseObj):
    """Mutable dict object; layout == MapBaseObj (static_assert enforced).
    Shares storage backend with MapObj but allows in-place mutation (c1af3b3)."""
    _type_index = kTVMFFIDict  # 76
    _type_key = "ffi.Dict"
    # Invariant: sizeof(DictObj) == sizeof(MapBaseObj) (enforced by static_assert)
    # Invariant: mutations are shared-reference -- all handles see changes immediately (no COW)
    # Interacts with: MapBaseObj (shared storage), DenseMapBaseObj.InplaceSwitchTo
    # Interacts with: StructuralEqual, StructuralHash, DeepCopy, JSON serialization, ReprPrint
    # Extension: use Dict<K,V> when mutable mapping is needed; use Map<K,V> for immutable sharing

class Dict(ObjectRef, Generic[K, V]):
    """Mutable dictionary ref wrapper. Mutations visible to all handles sharing same DictObj.
    Contrast with Map (immutable, COW). Both share MapBaseObj base (c1af3b3)."""
    _type_index = kTVMFFIDict  # 76
    _type_key = "ffi.Dict"
    # Invariant: storage_enabled_v<K> && storage_enabled_v<V>
    # Interacts with: MapBaseObj.InsertMaybeReHash, DenseMapBaseObj.InplaceSwitchTo

    def __init__(self, init: "Iterable[tuple[K,V]] | None" = None): ...
    def __getitem__(self, key: K) -> V: ...      # raises KeyError
    def __setitem__(self, key: K, value: V): ... # in-place, no COW
    def __delitem__(self, key: K): ...
    def Set(self, key: K, value: V) -> None: ...  # C++ mutation API
    def erase(self, key: K) -> None: ...
    def clear(self) -> None: ...
    def size(self) -> int: ...
    def count(self, key: K) -> int: ...          # 0 or 1
    def begin(self) -> "iterator": ...
    def end(self) -> "iterator": ...
    def find(self, key: K) -> "iterator": ...

# MapBaseObj mutation primitive (c1af3b3):
# MapBaseObj.InplaceSwitchTo(self, other: ObjectPtr[Object]) -> None
#   Moves DenseMapBaseObj internals (data_, slots_, size_, etc.) in-place.
#   Invariant: `other` must be a DenseMapBaseObj (not SmallMapBaseObj).
#   Used by Dict insertion when rehash produces a new backing store.

# InsertMaybeReHash signature changed (c1af3b3):
#   OLD: static void InsertMaybeReHash(KVType&&, ObjectPtr<Object>* map)
#   NEW: static ObjectPtr<Object> InsertMaybeReHash(KVType&&, const ObjectPtr<Object>& map)
#   Returns new container if rehash needed, nullptr otherwise.

# Global FFI functions for Dict:
# ffi.Dict(k0, v0, k1, v1, ...) -> Dict[Any,Any]
# ffi.DictSize, ffi.DictGetItem, ffi.DictSetItem, ffi.DictCount
# ffi.DictErase, ffi.DictClear, ffi.DictForwardIterFunctor
# ffi.DictGetItemOrMissing (returns MISSING sentinel on miss)

class Tuple(ObjectRef, Generic[*Types]):
    """Fixed-size heterogeneous tuple stored as Array of Any.
    Supports C++17 structured bindings, ADL-friendly get, and move semantics."""
    # Reuses Array storage internally

    def get(self, I: int) -> Types[I]:
        """(const& overload) Copy I-th element."""
        # Invariant: I < len(Types), checked at compile time
        # Interacts with: AnyUnsafe::CopyFromAnyViewAfterCheck

    def get_rvalue(self, I: int) -> Types[I]:
        """(&& overload) Move I-th element if uniquely owned, else copy."""
        # Invariant: if self.use_count() > 1, falls back to const& copy
        # Invariant: if self.use_count() == 1, moves via AnyUnsafe::MoveFromAnyAfterCheck
        # Interacts with: ObjectRef::unique(), ArrayObj::MutableBegin()

    # ADL-friendly free functions (in namespace tvm::ffi):
    # def get(t: Tuple[*Types], I: int) -> Types[I]:  # const& and && overloads
    #     Enables: using std::get; get<0>(t);

    # C++17 deduction guide:
    # Tuple(args...) -> Tuple<remove_cv_t<remove_reference_t<decltype(args)>>...>
    # Example: Tuple{1, 2.0f, String{"hi"}} -> Tuple<int, float, String>

    # std::tuple_size / std::tuple_element specializations:
    # tuple_size<Tuple<Types...>> = sizeof...(Types)
    # tuple_element<I, Tuple<Types...>>::type = tuple_element_t<I, tuple<Types...>>
    # Interacts with: C++17 structured bindings (auto [a, b, c] = tuple;)
    # Extension: structured bindings on rvalue tuples move elements when refcount == 1

class Variant(Generic[*Ts]):
    """Type-safe union. Specializes storage based on type composition."""
    # When ALL types derive from ObjectRef: inherits ObjectRef (sizeof == sizeof(ObjectRef))
    #   via VariantBase<true> specialization. Enables ObjectPtrHash/ObjectPtrEqual.
    # When any type is non-ObjectRef: backed by Any (sizeof == sizeof(Any))
    #   via VariantBase<false> generic path.
    # Interacts with: all_object_ref_v trait (compile-time storage selection)
    # Extension: add new variant types to the Variant<T...> template parameter pack

class Optional(Generic[T]):
    """Optional value. For ObjectRef types, uses nullptr to represent nullopt (zero overhead).
    For String/Bytes, uses BytesBaseCell(nullopt) with type_index == kTVMFFINone."""
    # For POD types: wraps std::optional<T>
    # For ObjectRef types: nullable ObjectRef (defined() == has_value())
    # For String/Bytes: sizeof(Optional<String>) == sizeof(String) (zero overhead)
    # Interacts with: TypeTraits<Optional<T>> (delegates to TypeTraits<T> or nullptr)
```

### Contracts, Assumptions and Invariants
- **Static type indices**: All built-in containers have fixed indices in `[64, 76]`. Language bindings can hard-code these for fast type dispatch. Additionally, `kTVMFFISmallStr` (11) and `kTVMFFISmallBytes` (12) are in the POD range for inline small strings. `kTVMFFIList = 75` was added in 9513c2f8. `kTVMFFIDict = 76` was added in c1af3b3.
- **Object header + cell layout**: Shape, Tensor (was NDArray), Function, and Error store domain-specific data immediately after the `TVMFFIObject` header. String and Bytes now use `BytesBaseCell` (wrapping `TVMFFIAny`) and are NOT Object-derived; large strings still use heap-allocated `BytesObjStdImpl`.
- **Cross-type string equality**: `AnyHash(SmallStr("x")) == AnyHash(Str("x"))` and `AnyEqual(SmallStr("x"), Str("x")) == true`. Hashing and equality transparently handle cross-type small/large string comparison.
- **Array element invariant**: `Array<T>` guarantees that `TypeTraits<T>::CheckAnyStorage(elem)` is true for every element. This means casting `Array<ObjectRef>` to `Array<String>` may require a new array if elements are not all strings.
- **Iterator conformance**: `IterAdapter` and `ReverseIterAdapter` use `const ResultType*` for `pointer` and `const ResultType` for `reference`, conforming to C++ LegacyInputIterator requirements. `operator*()` returns `reference` (consistent with the alias). This enables safe use with STL algorithms like `std::make_move_iterator` (14f3c82e).
- **Map insertion order**: `Map<K,V>` preserves insertion order, which is observable and relied upon by serialization code.
- **List cycle safety**: `List<T>` can form reference cycles (e.g., list containing itself). Structural eq/hash and JSON serialization handle cycles via visited-set tracking. However, pure ref-counting will NOT reclaim cycles; callers must break cycles manually.
- **List/Array duality**: `Array<T>` is immutable (safe for sharing, COW not implemented at this layer). `List<T>` is mutable (in-place mutations, no COW). `TypeTraits<std::vector<T>>` accepts both `kTVMFFIArray` and `kTVMFFIList`, enabling transparent C++ interop. Both share `SeqBaseObj` iteration and element access.
- **Dict/Map duality**: `Map<K,V>` is immutable (COW semantics). `Dict<K,V>` is mutable (shared-reference, no COW -- all handles see mutations). Both share `MapBaseObj` storage and `DenseMapBaseObj` hash table implementation. `Dict` uses `InplaceSwitchTo` to swap in a new backing store during rehash without invalidating the `DictObj` pointer. `GetDataSize` uses `int64_t` cast to prevent integer overflow on 32-bit platforms (a8f05405).
- **MISSING singleton identity**: The `MISSING` sentinel (from `ffi.GetInvalidObject`) must be compared via identity (`is`), not equality. It is initialized at Cython core module load (86c4042d, promoted from container to core).

### Extension Points
- **Custom containers**: New container types should follow the `XxxObj` (data) + `Xxx` (ref) pattern with a static or dynamic type index. Register with `TVM_FFI_DECLARE_OBJECT_INFO_STATIC` for static indices.
- **DLPack versioned API**: `TVMFFITensorFromDLPackVersioned`/`ToDLPackVersioned` support `DLManagedTensorVersioned` for forward compatibility.
- **Non-owning view pattern**: `TensorView` and `ShapeView` establish the convention for non-owning lightweight views. New view types should follow this pattern: copy the C struct (not the data), no ref-counting, use `storage_enabled = false` in `TypeTraits` to prevent storing in `Any`.

### Usage Examples

#### Working with Containers
**Context**: Creating and using FFI containers in C++.
```cpp
// Array: immutable typed list
Array<int> arr({1, 2, 3});
int first = arr[0];  // 1

// Map: insertion-ordered
Map<String, int> m({{"a", 1}, {"b", 2}});
int v = m["a"];  // 1

// String: auto-converts from const char*; small strings are inline
String s("hello");        // 5 bytes <= 7: stored inline (kTVMFFISmallStr)
Any a = s;
// a.type_index() == kTVMFFISmallStr (no heap allocation)

String long_s("this is a long string");  // > 7 bytes: heap-allocated
Any b = long_s;
// b.type_index() == kTVMFFIStr

// Cross-type equality: small and large strings with same content are equal
assert(AnyEqual()(Any("ab"), Any(String(std::string("ab")))));

// Optional<String> with zero overhead:
Optional<String> opt_str;
assert(!opt_str.has_value());
opt_str = "hello";
static_assert(sizeof(Optional<String>) == sizeof(String));

// Tensor (renamed from NDArray): DLPack interop
Tensor nd = Tensor::Empty({2, 3}, DLDataType{kDLFloat, 32, 1}, DLDevice{kDLCPU, 0});
ShapeView s = nd.shape();      // zero-alloc, reads DLTensor fields directly
ShapeView st = nd.strides();   // zero-alloc: {3, 1} for row-major
assert(nd.numel() == 6);       // new helper
assert(nd.ndim() == 2);        // new helper
assert(nd.data_ptr() == nd.GetDLTensorPtr()->data);  // accessor method
assert(nd.IsAligned(8));       // check alignment

// Aten-style aliases and negative indexing (573d76f):
int32_t d = nd.dim();              // same as nd.ndim() -> 2
ShapeView sz = nd.sizes();         // same as nd.shape() -> {2, 3}
bool contig = nd.is_contiguous();  // same as nd.IsContiguous()
assert(nd.size(-1) == 3);         // last dimension via negative index
assert(nd.stride(-1) == 1);       // stride of last dimension

// Tuple: C++17 structured bindings and move semantics (5569e449)
auto t = Tuple{1, 2.0f, String{"hello"}};  // CTAD deduction guide
auto [a, b, c] = t;                         // copies; t still valid
auto p = Tuple{Array<int>{0}};
auto [arr] = std::move(p);                   // moves; arr.use_count() == 1

// Scalar tensor (ndim==0): strides may be null
Tensor scalar = Tensor::FromDLPack(scalar_dlpack);  // ndim==0, strides==nullptr OK
ShapeView scalar_st = scalar.strides();              // returns empty ShapeView(nullptr, 0)
assert(scalar_st.size() == 0);

// TensorView: non-owning view, recommended for kernel signatures
TensorView view_from_tensor = nd;                   // implicit conversion from Tensor
TensorView view_from_dltensor = nd.GetDLTensorPtr(); // from DLTensor*
assert(view_from_tensor.ndim() == 2);
AnyView any_view = view_from_tensor;                 // CopyToAnyView as kTVMFFIDLTensorPtr
TensorView round_tripped = any_view.as<TensorView>().value();  // TryCastFromAnyView

// ShapeView: non-owning view over shape data
Shape shape = Shape({1, 2, 3});
ShapeView view = shape;  // zero-copy, implicit conversion
assert(view.size() == 3 && view.Product() == 6);

// DLPack round-trip (zero-copy)
DLManagedTensor* dlpack = nd.ToDLPack();
assert(dlpack->dl_tensor.strides != nullptr);  // always populated
Tensor nd2 = Tensor::FromDLPack(dlpack);       // permissive defaults (alignment=0, contiguous=false)
```

#### Mutable List Container (9513c2f8)
**Context**: Using `List<T>` for in-place mutation, and its relationship to `Array<T>` via `SeqBaseObj`.
```cpp
// C++: create and mutate a List
ffi::List<int64_t> lst;
lst.Append(1); lst.Append(2); lst.Append(3);
lst.Set(0, 10);
lst.PopBack();
// lst = [10, 2]

// TypeTraits<std::vector<T>> accepts both Array and List
std::vector<int64_t> vec = AnyView(lst).cast<std::vector<int64_t>>();
```

```python
# Python: List behaves like a Python list (MutableSequence)
import tvm_ffi
lst = tvm_ffi.List([1, 2, 3])
lst.append(4)
lst[0] = 10
del lst[1]
assert list(lst) == [10, 3, 4]
```

#### Mutable Dict Container (c1af3b3)
**Context**: Using `Dict<K,V>` for shared-reference mutable mapping, contrasting with `Map<K,V>` COW semantics.
```cpp
// C++: create and mutate a Dict
ffi::Dict<String, int64_t> d1;
d1.Set("a", 1);
d1.Set("b", 2);

// Shared-reference: d2 sees mutations through d1
ffi::Dict<String, int64_t> d2 = d1;
d1.Set("c", 3);
assert(d2.count("c") == 1);  // mutation visible via d2

d1.erase("a");
d1.clear();
```

```python
# Python: Dict implements MutableMapping with shared-reference semantics
import tvm_ffi
d1 = tvm_ffi.Dict({"a": 1, "b": 2})
d2 = d1                       # same underlying DictObj
d1["c"] = 3
assert d2["c"] == 3           # mutation visible through d2
del d1["a"]
d1.update({"d": 4})
assert set(d2.keys()) == {"b", "c", "d"}  # all mutations shared
```

## Implementation Notes
- Container objects use in-place array allocation (`make_inplace_array_object`) for variable-length storage (e.g., `ArrayObj` with inline element slots). The former `InplaceArrayBase` CRTP class has been removed (5a6b211); `ArrayObj` and `SmallMapBaseObj` now compute inplace data offsets directly via `reinterpret_cast<char*>(p.get()) + sizeof(T)`.
- `String` and `Bytes` are no longer `ObjectRef` subclasses. They use `BytesBaseCell` which wraps `TVMFFIAny` directly. Short strings (<= 7 bytes) are stored inline in the `v_bytes` union member with `kTVMFFISmallStr`/`kTVMFFISmallBytes` type indices. Long strings still use `details::BytesObjStdImpl` (heap-allocated `BytesObjBase` layout).
- `Map` internally uses a dense hash table that preserves insertion order (similar to Python 3.7+ dict). The `MapBaseObj::slots_` field uses bit 63 as a layout tag: MSB set = `SmallMapBaseObj`, MSB clear = `DenseMapBaseObj`. Callers must use `IsSmallMap()` and `NumSlots()` accessors, never read `slots_` directly. `MapObj` is now a thin subclass of `MapBaseObj` with only a type index (5a6b211); all implementation logic lives in `map_base.h`. Factory methods (`Empty`, `CreateFromRange`, `InsertMaybeReHash`, `CopyFrom`) are templatized on `<MapObjType>` to allow future map variants with distinct type indices.
- Container repr (b648c5d6): `Array.__repr__()` format is tuple-style `(1, 2, 3)` (not list-style `[1, 2, 3]`). `List.__repr__()` uses `[1, 2, 3]`. `Map.__repr__()` uses `{k: v}`. `Dict.__repr__()` uses `{k: v}` (same format as Map). All delegate to `ffi.ReprPrint` (see [0023-repr-print.md](0023-repr-print.md)).

## Alternatives & Trade-offs
### Immutable Containers vs. Mutable
- Pros of immutable: Safe for concurrent read access. No synchronization needed. Functional programming patterns.
- Cons: Mutation requires creating a new container (copy-on-write not implemented at this layer). Later commits add `List<T>` and `Dict<K,V>` for mutable use cases.
### Static Type Indices for Containers vs. Dynamic
- Pros of static: Fast type checking (integer comparison). Hard-coded in C API accessors. No runtime registration needed.
- Cons: Limited to ~64 static slots. New built-in containers require reserving an index at compile time.

## Evidence
| Commit | Scope | Contribution |
|--------|-------|-------------|
| 7d34eb8 | ffi/containers | Introduced Array, Map, String, Bytes, Shape, NDArray, Tuple, Variant, Optional |
| 296e2f7e | ffi/containers | Variant specializes to ObjectRef storage when all types are ObjectRef-derived |
| 7e0a4b35 | ffi/containers | Stabilized ArrayObj/MapObj ABI: added data_ pointer, data_deleter_, fixed DenseMapObj slot arithmetic |
| ba0ea87d | ffi/containers | Optimized string equality (Bytes::memequal) and hash (StableHashBytes aligned path) |
| 0342d85f | ffi/containers | Fixed SmallMapObj::CreateFromRange key deduplication |
| f9d2bff8 | ffi/containers | Moved StringObj/BytesObj into details:: namespace |
| 0966c368 | ffi/containers | Renamed type keys from `object.*` to `ffi.*` |
| 49e2ed4a | ffi/containers, ffi/c-api | Small string optimization: String/Bytes no longer ObjectRef, BytesBaseCell, kTVMFFISmallStr/SmallBytes, cross-type equality |
| 03e8a6b8 | ffi/containers | Map MSB tag in slots_ for SmallMap/DenseMap dispatch, IsSmallMap(), NumSlots() |
| ed56a5e7 | ffi/containers | Removed `using ffi::Tuple` from namespace `tvm` |
| ca95b41 | ffi/containers | NDArray always constructs strides (never null), added `stride_data_` field, `MakeStridesFromShape` |
| 3a551d8 | ffi/containers, ffi/c-api | Renamed NDArray->Tensor across all layers |
| 6fa40b5 | ffi/containers | Added `Tensor::strides()` accessor with lazy-cached Shape return, renamed `stride_data_` -> `strides_data_` |
| 1b824e8 | ffi/containers | Relaxed `from_dlpack` defaults (alignment=0, contiguous=false), added `IsDirectAddressDevice`, `Tensor::IsAligned` |
| e9d2946 | ffi/containers | Removed all remaining `using ffi::` namespace aliases from `tvm` (Array, Map, String, etc.) |
| 472e10c | ffi/containers | `Shape::StridesFromShape` static factory replacing free function |
| c88110e7 | ffi/containers | Fixed `DenseMapObj::At` to throw `KeyError` (was `IndexError`), enabling `Map.get()` |
| df58a05e | ffi/containers, python | Made Python `Array[T]`, `Map[K,V]` fully parameterizable generics (`Sequence[T]`, `Mapping[K,V]`) |
| 54f527f4 | ffi/containers, python | Added `Array.__add__`/`__radd__` for `+` concatenation |
| 90dba57c | ffi/containers, python | Restored `Array.__getitem__(slice)` to return `list[T]` (reverted PR #37 regression) |
| 8ca0719f | ffi/containers | Introduced `ShapeView` non-owning view class; removed `TensorObj` cached fields; inplace shape/strides storage; added `Tensor.data_ptr()`, `ndim()`, `numel()` |
| 1ec6236 | ffi/containers, ffi/type-traits | Introduced `TensorView` non-owning view with `TypeTraits<TensorView>` (storage_enabled=false); established convention for kernel argument type |
| 4fefeb0 | ffi/containers | Relaxed strides-not-null invariant: null strides allowed when ndim==0 (scalar tensors from DLPack) |
| 22a78943 | python/ffi-bindings | Unified DLPack exchange into DLPackExchangeAPI struct with non-owning conversion and stream query |
| 83770118 | python/ffi-bindings | Exposed Tensor.strides property in Python Cython bindings, bumped DLPack to v1.2 |
| 0dcd4d2b | ffi/containers | Replaced operator->() on Tensor/TensorView with explicit accessor methods: device(), size(idx), stride(idx), byte_offset(), GetDLTensorPtr() |
| 573d76f | ffi/containers | Added aten-style aliases (dim, sizes, is_contiguous) on Tensor/TensorView; changed size()/stride() param from size_t to int64_t for negative indexing |
| 5569e449 | ffi/containers | C++17 structured binding, ADL get, deduction guide, and move-get for Tuple |
| 14f3c82e | ffi/containers | Fixed IterAdapter/ReverseIterAdapter type aliases for C++ LegacyInputIterator conformance |
| 8888eb4b | ffi/containers, ffi/c-api | Added `Tensor::as_strided`, `TensorView::as_strided`, `Tensor::FromNDAllocStrided`, `TVMFFITensorCreateUnsafeView` |
| 438f6439 | ffi/containers, python | Added sentinel-based `MapGetItemOrMissing` and `GetMissingObject` for fast `Map.get()` |
| e54d15d7 | ffi/containers | Tensor::size()/stride() and TensorView::size()/stride() now throw IndexError on out-of-bounds indices |
| ec56178e | ffi/containers | ArrayObj::operator[] and SetItem: added negative index bounds check (was UB) |
| 5bc7fcde | ffi/containers, python | Added `ffi.ArrayContains` FFI function and `Array.__contains__` for `in` operator |
| 46ab6448 | python/ffi-bindings | Added `__bool__` on Array and Map (empty containers are falsy) |
| bd12b26a | ffi/containers | Added String::find() (3 overloads), String::substr(), String::npos |
| 02d1a96 | ffi/containers | Added String::starts_with() and String::ends_with() (4 overloads each) |
| 9513c2f8 | ffi/containers, ffi/c-api | Introduced `List<T>`, `ListObj`, `SeqBaseObj`, `TVMFFISeqCell`; cycle detection in eq/hash/JSON |
| 86c4042d | ffi/containers, python | Renamed `ffi.MapGetMissingObject` -> `ffi.GetInvalidObject`; promoted MISSING to core |
| d3b5532f | ffi/extra, ffi/json | Fixed JSON parser rejecting non-ASCII UTF-8 on signed-char platforms |
| 5a6b211 | ffi/containers | Extracted MapBaseObj hierarchy into map_base.h, templatized factory methods, removed InplaceArrayBase, added clear() |
| b648c5d6 | ffi/containers, python | Container repr changed to ffi.ReprPrint: Array->tuple-style, List->list-style, Map->dict-style |
| c1af3b33 | ffi/containers, ffi/c-api | Introduced `Dict<K,V>`, `DictObj`, `kTVMFFIDict = 76`, `InplaceSwitchTo` mutation primitive |
| a8f05405 | ffi/containers | Fixed `GetDataSize` integer overflow on 32-bit platforms via `int64_t` cast |
| Plus 6 supporting commits (ae30cd6, d0d0e2f, b508698, 0f455282, 395db3ce, 07546c75 Array compat temp revert) |

## Related Design Docs & ADRs
- [0001-c-abi.md](0001-c-abi.md) -- Static type index assignments, C API cell accessors
- [0002-any-value-system.md](0002-any-value-system.md) -- TypeTraits for container types
- [0003-object-system.md](0003-object-system.md) -- Object header layout that containers extend
- [0023-repr-print.md](0023-repr-print.md) -- Unified repr for all container types via `__ffi_repr__` callbacks
