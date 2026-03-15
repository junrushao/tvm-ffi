---
scope: "rust-bindings"
---
# API Index: Rust Bindings

**Scope**: Rust language bindings for TVM FFI — 3-crate workspace (`tvm-ffi-sys`, `tvm-ffi-macros`, `tvm-ffi`)
**Design docs**: [0019-rust-bindings.md](../designs/0019-rust-bindings.md)
**ADRs**: [0019-manual-c-abi-in-rust.md](../ADRs/0019-manual-c-abi-in-rust.md), [0020-native-rust-refcounting.md](../ADRs/0020-native-rust-refcounting.md)

## C++ API: Types, Methods, Functions, Macros
(Not applicable — this scope covers Rust-only APIs. The underlying C ABI is documented in [0001-c-abi.md](../api-index/0001-c-abi.md).)

## Rust API

### Crate: `tvm-ffi-sys` (raw C ABI bindings)

| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFITypeIndex` | `#[repr(i32)] enum { kTVMFFINone=0, kTVMFFIInt=1, ..., kTVMFFIOpaquePyObject=74 }` | ABI type index discriminator |
| `TVMFFIObjectDeleterFlagBitMask` | `#[repr(i32)] enum { Strong=1, Weak=2, Both=3 }` | Deleter flag for two-phase destruction |
| `TVMFFIObject` | `#[repr(C)] struct { combined_ref_count: AtomicU64, type_index: i32, __padding: u32, deleter: Option<TVMFFIObjectDeleter> }` | 24-byte heap object header |
| `TVMFFIAny` | `#[repr(C)] struct { type_index: i32, small_str_len: u32, data_union: TVMFFIAnyDataUnion }` | 16-byte type-erased value |
| `TVMFFIAnyDataUnion` | `#[repr(C)] union { v_int64: i64, v_float64: f64, v_ptr: *mut c_void, v_obj: *mut TVMFFIObject, v_dtype: DLDataType, v_device: DLDevice, v_bytes: [u8;8], ... }` | Data payload for TVMFFIAny |
| `TVMFFIByteArray` | `struct { data: *const u8, size: usize }` | Borrowed byte slice for C strings |
| `TVMFFIFunctionCell` | `struct { safe_call: TVMFFISafeCallType, cxx_call: *mut c_void }` | Function dispatch cell |
| `TVMFFIErrorCell` | `struct { kind: TVMFFIByteArray, message: TVMFFIByteArray, backtrace: TVMFFIByteArray, update_backtrace: fn(...) }` | Error storage cell |
| `TVMFFIShapeCell` | `struct { data: *const i64, size: usize }` | Shape trailing data cell |
| `TVMFFISafeCallType` | `type = unsafe extern "C" fn(*mut c_void, *const TVMFFIAny, i32, *mut TVMFFIAny) -> i32` | Universal function call ABI |
| `TVMFFIObjectHandle` | `type = *mut c_void` | Opaque object handle for C API |
| `COMBINED_REF_COUNT_STRONG_ONE` | `const u64 = 1` | One strong reference increment |
| `COMBINED_REF_COUNT_WEAK_ONE` | `const u64 = 1 << 32` | One weak reference increment |
| `COMBINED_REF_COUNT_BOTH_ONE` | `const u64 = STRONG_ONE \| WEAK_ONE` | Initial refcount for new objects |
| `COMBINED_REF_COUNT_MASK_U32` | `const u64 = (1 << 32) - 1` | Mask to extract strong count |
| `TVMFFIFunctionGetGlobal` | `unsafe extern "C" fn(*const TVMFFIByteArray, *mut TVMFFIObjectHandle) -> i32` | Look up global function by name |
| `TVMFFIFunctionSetGlobal` | `unsafe extern "C" fn(*const TVMFFIByteArray, TVMFFIObjectHandle, i32) -> i32` | Register global function |
| `TVMFFIFunctionCreate` | `unsafe extern "C" fn(*mut c_void, TVMFFISafeCallType, Option<fn(*mut c_void)>, *mut TVMFFIObjectHandle) -> i32` | Create function from C callbacks |
| `TVMFFIFunctionCall` | `unsafe extern "C" fn(TVMFFIObjectHandle, *const TVMFFIAny, i32, *mut TVMFFIAny) -> i32` | Call a function |
| `TVMFFIErrorCreate` | `unsafe extern "C" fn(*const TVMFFIByteArray, *const TVMFFIByteArray, *const TVMFFIByteArray, *mut TVMFFIObjectHandle) -> i32` | Create error object |
| `TVMFFIErrorSetRaised` | `unsafe extern "C" fn(TVMFFIObjectHandle)` | Store error in TLS |
| `TVMFFIErrorMoveFromRaised` | `unsafe extern "C" fn(*mut TVMFFIObjectHandle)` | Retrieve error from TLS |
| `TVMFFITypeKeyToIndex` | `unsafe extern "C" fn(*const TVMFFIByteArray, *mut i32) -> i32` | Look up type index by key |
| `TVMFFIGetTypeInfo` | `unsafe extern "C" fn(i32) -> *const TVMFFITypeInfo` | Get runtime type info |
| `TVMFFIStringFromByteArray` | `unsafe extern "C" fn(*const TVMFFIByteArray, *mut TVMFFIAny) -> i32` | Create String (SSO-aware) |
| `TVMFFIBytesFromByteArray` | `unsafe extern "C" fn(*const TVMFFIByteArray, *mut TVMFFIAny) -> i32` | Create Bytes (SSO-aware) |
| `TVMFFIAnyViewToOwnedAny` | `unsafe extern "C" fn(*const TVMFFIAny, *mut TVMFFIAny) -> i32` | Convert view to owned |

### Crate: `tvm-ffi-macros` (proc-macro)

| Name | Signature | Description |
|------|-----------|-------------|
| `#[derive(Object)]` | Attributes: `#[type_key = "..."]`, `#[type_index(...)]` (optional). Requires first field to impl `ObjectCore` | Generates `unsafe impl ObjectCore for T { TYPE_KEY, type_index(), object_header_mut() }` |
| `#[derive(ObjectRef)]` | Requires first field named `data: ObjectArc<T>` | Generates `unsafe impl ObjectRefCore`, `unsafe impl AnyCompatible`, `impl_try_from_any!`, `impl_arg_into_ref!`, `impl_into_arg_holder_default!` |

### Crate: `tvm-ffi` (high-level API)

#### Traits

| Name | Signature | Description |
|------|-----------|-------------|
| `AnyCompatible` | `unsafe trait { copy_to_any_view, move_to_any, check_any_strict, copy_from_any_view_after_check, move_from_any_after_check, try_cast_from_any_view, type_str }` | Enables round-trip through Any/AnyView. Rust equiv of C++ `TypeTraits<T>` |
| `ObjectCore` | `unsafe trait { TYPE_KEY: &str, type_index() -> i32, object_header_mut(&mut Self) -> &mut TVMFFIObject }` | Object data class protocol |
| `ObjectCoreWithExtraItems` | `unsafe trait: ObjectCore { ExtraItem, extra_items_count, extra_items, extra_items_mut }` | Trailing-data objects (String, Bytes, Shape) |
| `ObjectRefCore` | `unsafe trait { ContainerType: ObjectCore, data(&Self), into_data(Self), from_data(ObjectArc) }` | Reference wrapper protocol |
| `AsPackedCallable<I, O>` | `trait { fn call_packed(&self, &[AnyView]) -> Result<Any> }` | Typed-to-packed function adapter (impl for Fn with 0-8 args) |
| `TupleAsPackedArgs` | `trait { LEN: usize, fn fill_any_view(&self, &mut [AnyView]) }` | Tuple-to-AnyView conversion at call sites (impl for tuples 0-8) |
| `ArgTryFromAnyView` | `trait { fn try_from_any_view(view: &AnyView, idx: usize) -> Result<Self> }` | Extract typed arg from AnyView with error context |
| `IntoArgHolder` | `trait { type Target; fn into_arg_holder(self) -> Target }` | Convert arg types to canonical holding types (e.g., `&str` -> `String`) |
| `ArgIntoRef` | `trait { type Target; fn to_ref(&self) -> &Target }` | Borrow argument for AnyView creation |
| `DLDataTypeExt` | `trait on DLDataType { int8(), float32(), ..., bits(), lanes(), type_code() }` | Extension methods for DLPack data type |

#### Types

| Name | Signature | Description |
|------|-----------|-------------|
| `Any` | `#[repr(C)] struct { data: TVMFFIAny }` | Owning type-erased value. Clone=inc_ref, Drop=dec_ref for objects |
| `AnyView<'a>` | `#[repr(C)] struct { data: TVMFFIAny }` | Non-owning type-erased value view |
| `ObjectArc<T: ObjectCore>` | `#[repr(C)] struct { ptr: NonNull<T> }` | Arc-like wrapper. Clone=inc_ref, Drop=dec_ref. Deref to T |
| `Object` | `#[repr(C)] struct { header: TVMFFIObject }` | Base object type (TYPE_KEY="ffi.Object") |
| `ObjectRef` | `struct { data: ObjectArc<Object> }` | Base reference wrapper |
| `Function` | `struct { data: ObjectArc<FunctionObj> }` | Packed callable. `call_packed`, `call_tuple`, `get_global`, `register_global`, `from_packed`, `from_typed`, `from_extern_c` |
| `Error` | `struct { data: ObjectArc<ErrorObj> }` | Error with kind/message/backtrace. `new`, `from_raised`, `set_raised`, `with_appended_backtrace`. Implements `std::error::Error` |
| `ErrorKind<'a>` | `struct(&'a str)` | Named error categories: `VALUE_ERROR`, `TYPE_ERROR`, `RUNTIME_ERROR`, `ATTRIBUTE_ERROR`, `KEY_ERROR`, `INDEX_ERROR` |
| `Result<T>` | `type = std::result::Result<T, Error>` | Default result alias |
| `String` | `#[repr(C)] struct { data: TVMFFIAny }` | SSO string (<=7 bytes inline). `as_str`, `len`, `From<AsRef<str>>`, `Deref<Target=str>` |
| `Bytes` | `#[repr(C)] struct { data: TVMFFIAny }` | SSO byte slice. `as_slice`, `len`, `From<AsRef<[u8]>>`, `Deref<Target=[u8]>` |
| `Tensor` | `struct { data: ObjectArc<TensorObj> }` | `from_slice`, `data_ptr`, `data_as_slice::<T>`, `data_as_slice_mut::<T>` |
| `Shape` | `struct { data: ObjectArc<ShapeObj> }` | Immutable shape with trailing i64 data |
| `Module` | `struct { data: ObjectArc<ModuleObj> }` | `load_from_file(path) -> Result<Module>`, `get_function(name) -> Result<Function>` |
| `ArrayObj` | `#[repr(C)] #[derive(Object)] #[type_key = "ffi.Array"] struct { object: Object, data: *mut c_void, size: i64, capacity: i64, data_deleter: Option<...> }` | Array data object with trailing TVMFFIAny items (d0d0e2f) |
| `Array<T: AnyCompatible + Clone>` | `#[repr(C)] struct { data: ObjectArc<ArrayObj>, _marker: PhantomData<T> }` | Generic immutable array. `new(Vec<T>)`, `len()`, `get(usize) -> Result<T>`, `iter() -> ArrayIterator<T>`, `Index<usize>`. Traits: `FromIterator<T>`, `IntoIterator`, `TryFrom<Any>`, `AnyCompatible` with recursive element-type checking (d0d0e2f) |

#### Macros

| Name | Signature | Description |
|------|-----------|-------------|
| `check_safe_call!(expr)` | `-> Result<(), Error>` | Wrap C API call; nonzero return -> `Err(Error::from_raised())` |
| `bail!(kind, fmt, args...)` | `-> !` (returns Err) | Return `Err(Error::new(...))` with file/line traceback |
| `ensure!(cond, kind, fmt, args...)` | conditional bail | Conditional error return |
| `attach_context!(result)` | `Result<T> -> Result<T>` | Append file/line to error traceback |
| `function_name!()` | `-> &'static str` | Get enclosing function name via `type_name_of` trick |
| `tvm_ffi_dll_export_typed_func!(name, func)` | Generates `pub unsafe extern "C" fn __tvm_ffi_<name>(...)` | Export Rust fn as DLL entry point following FFI ABI |
| `into_typed_fn!(func, Fn(T0, ..) -> Result<R>)` | `-> impl Fn(T0, ..) -> Result<R>` | Wrap `Function` into typed closure (0-8 args) |
| `impl_try_from_any!(types...)` | Generates TryFrom<AnyView> + TryFrom<Any> | TryFrom implementations for listed types |
| `impl_any_compatible_for_int!(types...)` | Generates `AnyCompatible` for int types | Bulk AnyCompatible for i8..usize |
| `impl_any_compatible_for_float!(types...)` | Generates `AnyCompatible` for float types | Bulk AnyCompatible for f32, f64 |
| `impl_arg_into_ref!(types...)` | Generates `ArgIntoRef` for T and &T | Bulk ArgIntoRef for call-site ergonomics |
| `impl_into_arg_holder_default!(types...)` | Generates `IntoArgHolder` identity impls | Bulk IntoArgHolder for types that need no conversion |

#### Internal (unsafe) Functions

| Name | Signature | Description |
|------|-----------|-------------|
| `object::unsafe_::inc_ref` | `unsafe fn(handle: *mut TVMFFIObject)` | Native Rust strong ref increment (Relaxed) |
| `object::unsafe_::dec_ref` | `unsafe fn(handle: *mut TVMFFIObject)` | Native Rust strong ref decrement with deleter dispatch |
| `object::unsafe_::strong_count` | `unsafe fn(handle: *mut TVMFFIObject) -> usize` | Read strong ref count |
| `object::unsafe_::weak_count` | `unsafe fn(handle: *mut TVMFFIObject) -> usize` | Read weak ref count |
| `object::unsafe_::object_deleter_for_new::<T>` | `unsafe extern "C" fn(*mut c_void, i32)` | Generic deleter for Box-allocated objects |
| `object::unsafe_::object_deleter_for_new_with_extra_items::<T,U>` | `unsafe extern "C" fn(*mut c_void, i32)` | Deleter for trailing-data objects (two-phase: drop then dealloc) |

## Python API
(Not applicable — this scope covers Rust-only APIs.)
