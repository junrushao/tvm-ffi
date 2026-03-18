---
scope: "rust-bindings"
---
# API Index: Rust Bindings

**Scope**: Rust crate workspace providing idiomatic bindings over the TVM FFI C ABI.
**Design docs**: [0016-rust-bindings.md](../designs/0016-rust-bindings.md)
**ADRs**: [0013-rust-native-refcounting.md](../ADRs/0013-rust-native-refcounting.md), [0014-rust-crate-split.md](../ADRs/0014-rust-crate-split.md)

## C++ API: Types, Methods, Functions, Macros
N/A -- Rust bindings consume the C ABI, they do not add C++ API surface.

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| `ObjectArc<T>` | `struct ObjectArc<T: ObjectCore> { ptr: NonNull<T> }` | Ref-counted smart pointer for FFI objects; native Rust atomics for inc/dec ref |
| `ObjectArc::new` | `fn new(data: T) -> ObjectArc<T>` | Allocate and wrap a new object with ref count = 1 |
| `ObjectArc::new_with_extra_items` | `fn new_with_extra_items<U>(data: T, extra: &[U]) -> ObjectArc<T>` | Allocate with tail-allocated items (String, Bytes, Shape) |
| `ObjectArc::from_raw` | `fn from_raw(ptr: *const T) -> ObjectArc<T>` | Take ownership from raw pointer (no inc_ref) |
| `ObjectArc::into_raw` | `fn into_raw(self) -> *const T` | Release ownership to raw pointer (no dec_ref) |
| `ObjectCore` (trait) | `trait ObjectCore { TYPE_KEY, type_index(), object_header_mut() }` | Marks a struct as an FFI object with TVMFFIObject header |
| `ObjectCoreWithExtraItems` (trait) | `trait ObjectCoreWithExtraItems: ObjectCore { ExtraItem, extra_items_count(), extra_items() }` | Extension for tail-allocated objects |
| `ObjectRefCore` (trait) | `trait ObjectRefCore { ContainerType, data(), into_data(), from_data() }` | Maps ref wrapper to its ObjectArc |
| `AnyCompatible` (trait) | `trait AnyCompatible { copy_to_any_view(), move_to_any(), check_any_strict(), ... }` | Protocol for FFI type conversion (Rust analog of C++ TypeTraits) |
| `Any` | `struct Any { inner: TVMFFIAny }` | Owning type-erased value; manages ref counts on Drop/Clone |
| `AnyView` | `struct AnyView<'a> { inner: TVMFFIAny, ... }` | Non-owning type-erased value; Copy+Clone, no ref-count ops |
| `Function` | `struct Function { data: ObjectArc<FunctionObj> }` | Owned FFI function handle |
| `Function::get_global` | `fn get_global(name: &str) -> Result<Function>` | Retrieve global function by name |
| `Function::register_global` | `fn register_global(name: &str, func: Function) -> Result<()>` | Register function in global registry |
| `Function::from_typed` | `fn from_typed<F, I, O>(func: F) -> Function` | Wrap typed Rust closure as FFI Function |
| `Function::from_packed` | `fn from_packed(func: impl Fn(&[AnyView]) -> Result<Any>) -> Function` | Wrap untyped packed function |
| `Function::call_packed` | `fn call_packed(&self, args: &[AnyView]) -> Result<Any>` | Call with packed arguments |
| `Error` | `struct Error { data: ObjectArc<ErrorObj> }` | FFI error; implements std::error::Error |
| `Error::new` | `fn new(kind: ErrorKind, message: &str, traceback: &str) -> Error` | Create error with kind and message |
| `Error::from_raised` | `fn from_raised() -> Error` | Retrieve TLS-raised error |
| `String` | `struct String { inner: TVMFFIAny }` | ABI-stable string with SSO (<=7 bytes inline) |
| `Bytes` | `struct Bytes { inner: TVMFFIAny }` | ABI-stable byte sequence with SSO |
| `Tensor` | `struct Tensor { data: ObjectArc<TensorObj> }` | DLTensor-backed tensor |
| `Tensor::from_slice` | `fn from_slice<T>(data: &[T], shape: &[i64]) -> Result<Tensor>` | Create tensor from Rust slice |
| `Shape` | `struct Shape { data: ObjectArc<ShapeObj> }` | Immutable shape descriptor (tail-allocated i64) |
| `Array<T>` | `struct Array<T: AnyCompatible + Clone> { data: ObjectArc<ArrayObj> }` | Typed array container with FFI-compatible layout matching C++ ArrayObj (d0d0e2f) |
| `Array::new` | `fn new(items: Vec<T>) -> Array<T>` | Create array from Vec; uses ObjectCoreWithExtraItems for tail allocation |
| `Array::get` | `fn get(&self, index: usize) -> Result<T>` | Element access; returns IndexError for out-of-bounds |
| `Array::len` | `fn len(&self) -> usize` | Number of elements |
| `Array::iter` | `fn iter(&self) -> ArrayIterator<T>` | Iterator over elements |
| `Module` | `struct Module { data: ObjectArc<ModuleObj> }` | Runtime module for loading shared libraries |
| `Module::load_from_file` | `fn load_from_file(file_name: &str) -> Result<Module>` | Load shared library as Module |
| `tvm_ffi_dll_export_typed_func!` | `macro_rules! tvm_ffi_dll_export_typed_func($name, $func)` | Generate `extern "C" fn __tvm_ffi_$name(...)` symbol |
| `into_typed_fn!` | `macro_rules! into_typed_fn($func, Fn(...) -> Result<R>)` | Wrap untyped Function into typed Rust closure |
| `check_safe_call!` | `macro_rules! check_safe_call($expr)` | Check FFI call return code; convert to Result |
| `bail!` | `macro_rules! bail($kind, $fmt, ...)` | Create and raise FFI error with traceback |
| `ensure!` | `macro_rules! ensure($cond, $kind, $fmt, ...)` | Assert condition; bail on failure |
| `unsafe_::inc_ref` | `fn inc_ref(handle: *mut TVMFFIObject)` | Native Rust atomic strong ref increment |
| `unsafe_::dec_ref` | `fn dec_ref(handle: *mut TVMFFIObject)` | Native Rust atomic strong ref decrement (two-phase) |
| `current_stream` | `fn current_stream(device: &DLDevice) -> TVMFFIStreamHandle` | Get current stream for device |
| `with_stream` | `fn with_stream<T>(device, stream, f: FnOnce() -> Result<T>) -> Result<T>` | Execute closure with stream context |
| `#[derive(Object)]` | `#[derive(Object)] #[type_key = "..."] struct MyObj { ... }` | Generate ObjectCore impl from struct |
| `#[derive(ObjectRef)]` | `#[derive(ObjectRef)] struct MyRef { data: ObjectArc<MyObj> }` | Generate ObjectRefCore + AnyCompatible impls |

## Python API
N/A -- Rust bindings do not add Python API surface.
