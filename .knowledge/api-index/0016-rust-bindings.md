---
scope: "rust-bindings"
status: "active"
last_updated_commit: "09477ce10de566f8cf511cce7dfe56e77759f100"
related_designs:
  - ".knowledge/designs/rust-bindings.md"
related_adrs:
  - ".knowledge/ADRs/019-rust-hand-written-c-abi.md"
---
# API Index: Rust Bindings

**Scope**: Public API surface of the `tvm-ffi` and `tvm-ffi-sys` Rust crates
**Design docs**: `.knowledge/designs/rust-bindings.md`
**ADRs**: `.knowledge/ADRs/019-rust-hand-written-c-abi.md`

## Rust API

### Core Traits (`tvm-ffi`)
| Name | Signature | Description |
|------|-----------|-------------|
| `AnyCompatible` | `unsafe trait AnyCompatible: Sized` with `copy_to_any_view`, `move_to_any`, `check_any_strict`, `copy_from_any_view_after_check`, `move_from_any_after_check`, `try_cast_from_any_view`, `type_str` | Rust equivalent of C++ `TypeTraits<T>`; enables type to be stored in Any/AnyView |
| `ObjectCore` | `unsafe trait ObjectCore: Sized + 'static` with `TYPE_KEY: &'static str`, `fn type_index() -> i32`, `unsafe fn object_header_mut(&mut Self) -> &mut TVMFFIObject` | Declares a type as an FFI object (data class) |
| `ObjectCoreWithExtraItems` | `unsafe trait ObjectCoreWithExtraItems: ObjectCore` with `type ExtraItem`, `fn extra_items_count(&Self) -> usize`, `unsafe fn extra_items(&Self) -> &[ExtraItem]` | Extension for objects with trailing variable-length data |
| `ObjectRefCore` | `unsafe trait ObjectRefCore: Sized + Clone` with `type ContainerType: ObjectCore`, `fn data(&Self) -> &ObjectArc<ContainerType>`, `fn into_data(Self) -> ObjectArc<ContainerType>`, `fn from_data(ObjectArc<ContainerType>) -> Self` | Declares a type as an FFI object ref (wrapper class) |
| `AsPackedCallable<I, O>` | `trait AsPackedCallable<I, O>` with `fn call_packed(&self, &[AnyView]) -> Result<Any>` | Converts typed Rust function to packed calling convention; impl for `Fn(T0,...,TN) -> Result<Out>` (0-8 args) |
| `TupleAsPackedArgs` | `trait TupleAsPackedArgs` with `const LEN: usize`, `fn fill_any_view(&self, &mut [AnyView])` | Packs a tuple of arguments into AnyView slice; impl for tuples of 0-8 elements |
| `IntoArgHolder` | `trait IntoArgHolder` with `type Target`, `fn into_arg_holder(self) -> Target` | Converts argument to canonical holding type (e.g., `&str` -> `String`) |
| `IntoArgHolderTuple` | `trait IntoArgHolderTuple` with `type Target`, `fn into_arg_holder_tuple(self) -> Target` | Applies `IntoArgHolder` across a tuple |
| `ArgIntoRef` | `trait ArgIntoRef` with `type Target`, `fn to_ref(&self) -> &Target` | Converts argument type to reference type |
| `NDAllocator` | `unsafe trait NDAllocator` with `const MIN_ALIGN: usize`, `fn alloc_data(...)`, `fn free_data(...)` | Pluggable tensor memory allocation |
| `DLDataTypeExt` | `trait DLDataTypeExt` with `fn to_string() -> String`, `fn try_from_str(&str) -> Result<DLDataType>` | Extension methods for `DLDataType` |
| `AsDLDataType` | `trait AsDLDataType` with `const DL_DATA_TYPE: DLDataType` | Associates a Rust scalar type with its `DLDataType`; impl for `i8`-`i64`, `u8`-`u64`, `f32`, `f64` |
| `DLTensorExt` | `trait DLTensorExt` with `fn numel() -> usize`, `fn item_size() -> usize` | Extension methods for `DLTensor` |

### Core Types (`tvm-ffi`)
| Name | Signature | Description |
|------|-----------|-------------|
| `Any` | `pub struct Any { data: TVMFFIAny }` | Owning type-erased value; Clone does IncRef, Drop does DecRef |
| `AnyView<'a>` | `pub struct AnyView<'a> { data: TVMFFIAny, _phantom: PhantomData<&'a ()> }` | Non-owning type-erased view with lifetime; Copy + Clone |
| `TryFromTemp<T>` | `pub struct TryFromTemp<T> { value: T }` | Helper for orphan-rule-safe `TryFrom<AnyView/Any>` impl |
| `ObjectArc<T: ObjectCore>` | `pub struct ObjectArc<T: ObjectCore> { ptr: NonNull<T>, _phantom: PhantomData<T> }` | Intrusive refcounted smart pointer (Rust `ObjectPtr<T>`) |
| `Object` | `pub struct Object { header: TVMFFIObject }` | Base object type |
| `ObjectRef` | `pub struct ObjectRef { data: ObjectArc<Object> }` | Base object ref wrapper |
| `Function` | `pub struct Function { data: ObjectArc<FunctionObj> }` | FFI function object |
| `Error` | `pub struct Error { data: ObjectArc<ErrorObj> }` | FFI error with kind, message, backtrace |
| `ErrorKind<'a>` | `pub struct ErrorKind<'a>(&'a str)` | Error kind wrapper; constants: `VALUE_ERROR`, `TYPE_ERROR`, `RUNTIME_ERROR`, `ATTRIBUTE_ERROR`, `KEY_ERROR`, `INDEX_ERROR` |
| `String` | SSO-aware ABI string | `Deref<Target=str>`, `Clone` (IncRef), `Drop` (DecRef), `From<T: AsRef<str>>` |
| `Bytes` | SSO-aware ABI bytes | `Deref<Target=[u8]>`, `Clone`, `Drop`, `From<T: AsRef<[u8]>>` |
| `Shape` | `pub struct Shape { data: ObjectArc<ShapeObj> }` | Shape with `Deref<Target=[i64]>`, `From<T: AsRef<[i64]>>` |
| `Tensor` | `pub struct Tensor { data: ObjectArc<TensorObj> }` | DLPack-compatible tensor; `from_slice`, `data_as_slice`, `shape`, `dtype`, etc. |
| `CPUNDAlloc` | CPU-based `NDAllocator` (64-byte alignment) | Default allocator for `Tensor::from_nd_alloc` |
| `Module` | `pub struct Module { data: ObjectArc<ModuleObj> }` | Loaded shared library module; `load_from_file`, `get_function` |
| `Result<T>` | `type Result<T, E = Error> = std::result::Result<T, E>` | Alias for `std::result::Result` with `Error` default |

### Core Methods
| Name | Signature | Description |
|------|-----------|-------------|
| `Any::new()` | `pub fn new() -> Self` | Creates None-typed Any |
| `Any::type_index()` | `pub fn type_index(&self) -> i32` | Returns type index |
| `Any::try_as::<T>()` | `pub fn try_as<T: AnyCompatible>(&self) -> Option<T>` | Strict type check (no conversion) |
| `AnyView::try_as::<T>()` | `pub fn try_as<T: AnyCompatible>(&self) -> Option<T>` | Strict type check (no conversion) |
| `ObjectArc::new(data)` | `pub fn new(data: T) -> Self` | Allocate + initialize header |
| `ObjectArc::from_raw(ptr)` | `pub unsafe fn from_raw(ptr: *const T) -> Self` | Take ownership of raw pointer |
| `ObjectArc::into_raw(self)` | `pub unsafe fn into_raw(this: Self) -> *const T` | Leak ownership |
| `ObjectArc::strong_count(&self)` | `pub fn strong_count(this: &Self) -> usize` | Strong reference count |
| `Function::call_packed(&self, &[AnyView])` | `pub fn call_packed(&self, packed_args: &[AnyView]) -> Result<Any>` | Invoke via packed convention |
| `Function::call_tuple(&self, T)` | `pub fn call_tuple<T: TupleAsPackedArgs>(&self, args: T) -> Result<Any>` | Invoke with tuple args (SVO) |
| `Function::from_typed(f)` | `pub fn from_typed<F, I, O>(func: F) -> Self where F: AsPackedCallable<I, O>` | Wrap typed function |
| `Function::from_packed(f)` | `pub fn from_packed<F: Fn(&[AnyView]) -> Result<Any>>(func: F) -> Self` | Wrap packed function |
| `Function::from_extern_c(h, c, d)` | `pub fn from_extern_c(handle, safe_call, deleter) -> Self` | Wrap C callback |
| `Function::get_global(name)` | `pub fn get_global(name: &str) -> Result<Function>` | Lookup global function |
| `Function::register_global(name, func)` | `pub fn register_global(name: &str, func: Function) -> Result<()>` | Register global function |
| `Error::new(kind, message, traceback)` | `pub fn new(kind: ErrorKind, message: &str, traceback: &str) -> Self` | Create error |
| `Error::from_raised()` | `pub fn from_raised() -> Self` | Retrieve error from TLS |
| `Error::set_raised(&self)` | `pub fn set_raised(error: &Self)` | Store error in TLS |

### Macros (`tvm-ffi`)
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `check_safe_call!(expr)` | Wraps `if ret_code == 0 { Ok(()) } else { Err(Error::from_raised()) }` | Check FFI return code |
| `bail!(kind, fmt, args...)` | Creates `Error::new(kind, formatted_msg, file_line_context)` and returns `Err` | Error with file/line |
| `ensure!(cond, kind, fmt, args...)` | `if !cond { bail!(...) }` | Conditional bail |
| `attach_context!(expr)` | Appends file/line to error backtrace if `Err` | Context attachment |
| `function_name!()` | Returns enclosing function name via type name introspection | For error messages |
| `into_typed_fn!(f, Fn(T0,...) -> Result<R>)` | Generates closure: `move \|a0: T0, ...\| -> Result<R> { f.call_tuple_with_len::<N>((a0,...))?.try_into() }` | Convert Function to typed closure (0-8 args) |
| `tvm_ffi_dll_export_typed_func!(name, func)` | Generates `pub unsafe extern "C" fn __tvm_ffi_<name>(handle, args, num_args, result) -> i32` | Export Rust function as C symbol |
| `impl_try_from_any!(types...)` | Generates `TryFrom<AnyView>` and `TryFrom<Any>` for listed types via `TryFromTemp` | Orphan-rule-safe TryFrom |
| `impl_try_from_any_for_parametric!(Generic<T>)` | Same as above for generic types like `Option<T>` | Parametric TryFrom |
| `impl_into_arg_holder_default!(types...)` | Generates `IntoArgHolder` with identity conversion | Default arg holder |
| `impl_arg_into_ref!(types...)` | Generates `ArgIntoRef` with identity conversion | Default arg ref |

### Derive Macros (`tvm-ffi-macros`)
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `#[derive(Object)]` | Generates `unsafe impl ObjectCore for T` with `TYPE_KEY`, `type_index()`, `object_header_mut()` | Requires `#[type_key = "..."]`; optional `#[type_index(...)]` |
| `#[derive(ObjectRef)]` | Generates `unsafe impl ObjectRefCore for T` + `unsafe impl AnyCompatible for T` + TryFrom + IntoArgHolder + ArgIntoRef | Expects first field `data: ObjectArc<ContainerType>` |

### Raw C ABI Types (`tvm-ffi-sys`)
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `TVMFFITypeIndex` | `#[repr(i32)]` enum | `kTVMFFINone=0` through `kTVMFFIOpaquePyObject=74` | All ABI type indices |
| `TVMFFIObject` | `#[repr(C)]` struct | `combined_ref_count: AtomicU64`, `type_index: i32`, `__padding: u32`, `deleter: Option<TVMFFIObjectDeleter>` | 24-byte object header |
| `TVMFFIAny` | `#[repr(C)]` struct | `type_index: i32`, `small_str_len: u32`, `data_union: TVMFFIAnyDataUnion` | 16-byte type-erased value |
| `TVMFFIAnyDataUnion` | `#[repr(C)]` union | `v_int64`, `v_float64`, `v_ptr`, `v_c_str`, `v_obj`, `v_dtype`, `v_device`, `v_bytes`, `v_uint64` | 8-byte data union |
| `TVMFFIByteArray` | `#[repr(C)]` struct | `data: *const u8`, `size: usize` | Byte array view |
| `TVMFFIFunctionCell` | `#[repr(C)]` struct | `safe_call: TVMFFISafeCallType`, `cxx_call: *mut c_void` | Function cell |
| `TVMFFIErrorCell` | `#[repr(C)]` struct | `kind`, `message`, `backtrace: TVMFFIByteArray`, `update_backtrace: fn(...)` | Error cell |
| `TVMFFIShapeCell` | `#[repr(C)]` struct | `data: *const i64`, `size: usize` | Shape cell |
| `TVMFFIFieldInfo` | `#[repr(C)]` struct | `name`, `doc`, `metadata`, `flags`, `offset`, `size`, `alignment`, `getter`, `setter`, `default_value`, `field_static_type_index` | Reflection field info |
| `TVMFFIMethodInfo` | `#[repr(C)]` struct | `name`, `doc`, `metadata`, `flags`, `method: TVMFFIAny` | Reflection method info |
| `TVMFFITypeMetadata` | `#[repr(C)]` struct | `doc`, `creator`, `total_size: i32`, `structural_eq_hash_kind: i32` | Type metadata |
| `TVMFFITypeInfo` | `#[repr(C)]` struct | `type_index`, `type_depth`, `type_key`, `type_acenstors`, `type_key_hash`, `num_fields`, `num_methods`, `fields`, `methods`, `metadata` | Runtime type info |
| `TVMFFIObjectDeleterFlagBitMask` | `#[repr(i32)]` enum | `Strong=1`, `Weak=2`, `Both=3` | Deleter phase flags |

### Raw C ABI Extern Functions (`tvm-ffi-sys`)
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFITypeKeyToIndex` | `fn(type_key: *const TVMFFIByteArray, out: *mut i32) -> i32` | Map type key to index |
| `TVMFFIFunctionGetGlobal` | `fn(name: *const TVMFFIByteArray, out: *mut TVMFFIObjectHandle) -> i32` | Get global function |
| `TVMFFIFunctionSetGlobal` | `fn(name: *const TVMFFIByteArray, f: TVMFFIObjectHandle, can_override: i32) -> i32` | Register global function |
| `TVMFFIFunctionCreate` | `fn(self_ptr: *mut c_void, safe_call: TVMFFISafeCallType, deleter: Option<fn(*mut c_void)>, out: *mut TVMFFIObjectHandle) -> i32` | Create function from C callback |
| `TVMFFIFunctionCall` | `fn(func: TVMFFIObjectHandle, args: *const TVMFFIAny, num_args: i32, result: *mut TVMFFIAny) -> i32` | Invoke function |
| `TVMFFIAnyViewToOwnedAny` | `fn(any_view: *const TVMFFIAny, out: *mut TVMFFIAny) -> i32` | Materialize view to owned |
| `TVMFFIErrorMoveFromRaised` | `fn(result: *mut TVMFFIObjectHandle)` | Retrieve TLS error |
| `TVMFFIErrorSetRaised` | `fn(error: TVMFFIObjectHandle)` | Store error in TLS |
| `TVMFFIErrorCreate` | `fn(kind, message, backtrace: *const TVMFFIByteArray, out: *mut TVMFFIObjectHandle) -> i32` | Create error object |
| `TVMFFITensorFromDLPack` | `fn(from: *mut c_void, require_alignment: i32, require_contiguous: i32, out: *mut TVMFFIObjectHandle) -> i32` | DLPack import |
| `TVMFFITensorToDLPack` | `fn(from: TVMFFIObjectHandle, out: *mut *mut c_void) -> i32` | DLPack export |
| `TVMFFIStringFromByteArray` | `fn(input: *const TVMFFIByteArray, out: *mut TVMFFIAny) -> i32` | Create owned String (SSO) |
| `TVMFFIBytesFromByteArray` | `fn(input: *const TVMFFIByteArray, out: *mut TVMFFIAny) -> i32` | Create owned Bytes (SSO) |
| `TVMFFIGetTypeInfo` | `fn(type_index: i32) -> *const TVMFFITypeInfo` | Query type info |
| `TVMFFITraceback` | `fn(filename: *const i8, lineno: i32, func: *const i8, cross_ffi_boundary: i32) -> *const TVMFFIByteArray` | Collect backtrace |

## Deprecated / Renamed
(No deprecations yet -- this is the initial Rust binding.)

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 09477ce | `2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md` | Initial bringup of complete Rust binding workspace (tvm-ffi-sys, tvm-ffi-macros, tvm-ffi) |
