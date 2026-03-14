---
status: "active"
confidence: "high"
---
# Rust Bindings

**TL;DR**
- The Rust bindings are organized as a three-crate workspace: `tvm-ffi-sys` (raw C ABI `#[repr(C)]` types and `extern "C"` function declarations), `tvm-ffi-macros` (proc-macros for `#[derive(Object)]` and `#[derive(ObjectRef)]`), and `tvm-ffi` (safe, ergonomic Rust API).
- The key Rust-side abstraction is the `AnyCompatible` unsafe trait -- the Rust analogue of `TypeTraits<T>` in C++ -- which provides a 7-method protocol for moving values in and out of the type-erased `Any`/`AnyView` containers.
- Object lifetime management uses `ObjectArc<T>`, an intrusive ref-counted smart pointer that implements the two-phase destruction protocol (strong/weak deleter flags) natively in Rust without calling C API ref-counting functions, providing zero-overhead ref-counting on the hot path.
- The crate supports both consuming FFI objects (calling global functions, loading modules) and producing them (exporting Rust functions via `tvm_ffi_dll_export_typed_func!`).

## Problem Statement

### Background

The TVM FFI provides a stable C ABI and C++ API. Python bindings exist via Cython. Adding a third first-class language binding (Rust) validates the C ABI's language-agnosticism and provides a typed systems language option for performance-critical ML infrastructure. The binding must be safe and ergonomic while remaining ABI-compatible at the binary level.

### Solution

A three-crate workspace where responsibilities are cleanly separated: `tvm-ffi-sys` owns the C ABI contract, `tvm-ffi-macros` eliminates boilerplate via proc-macros, and `tvm-ffi` provides the public safe API. Native Rust ref-counting avoids FFI overhead for the common inc/dec-ref path.

### Goals

- **Goal**: Binary-compatible with all C ABI types (`TVMFFIAny`, `TVMFFIObject`, `TVMFFIFunctionCell`, etc.) via `#[repr(C)]` structs.
- **Goal**: Ergonomic Rust API that mirrors the C++ design (same naming, same patterns).
- **Goal**: Zero FFI overhead for ref-counting hot paths (native atomic operations).
- **Goal**: Support both loading foreign modules and exporting Rust functions via the `__tvm_ffi_` symbol convention.
- **Non-goal (partially achieved)**: Full container API parity with C++ -- `Array<T>` was added in commit `d0d0e2f` (#348); List, Map, Dict remain unimplemented.

## Design

### Three-Crate Workspace Architecture

```text
rust/
  Cargo.toml             # workspace: [tvm-ffi, tvm-ffi-sys, tvm-ffi-macros]
  tvm-ffi-sys/           # Raw C ABI bindings
    build.rs             # Runs tvm-ffi-config --libdir for library discovery
    src/c_api.rs         # #[repr(C)] structs, extern "C" function declarations
    src/c_env_api.rs     # Stream, allocator, and env C API functions
    src/dlpack.rs        # DLPack types (DLTensor, DLDataType, DLDevice)
  tvm-ffi-macros/        # Proc-macro crate
    src/object_macros.rs # #[derive(Object)], #[derive(ObjectRef)]
  tvm-ffi/               # Safe public API
    build.rs             # Also runs tvm-ffi-config; generates example lib optionally
    src/any.rs           # Any, AnyView containers
    src/object.rs        # ObjectArc<T>, ObjectCore, ObjectRefCore traits
    src/type_traits.rs   # AnyCompatible trait + impls for primitives
    src/function.rs      # Function, FunctionObj, CallbackFunctionObjImpl
    src/function_internal.rs  # AsPackedCallable, TupleAsPackedArgs helpers
    src/string.rs        # String, Bytes (with small-string optimization)
    src/error.rs         # Error, ErrorObj, bail!/ensure!/check_safe_call! macros
    src/macros.rs        # Utility macros (error handling, any conversion, function export)
    src/collections/     # Array, Shape, Tensor, NDAllocator
    src/extra/           # Module (higher-level wrappers)
```

### AnyCompatible Trait Protocol

The `AnyCompatible` unsafe trait is the central type-erasure mechanism, mapping directly to the C++ `TypeTraits<T>` specializations:

| Rust method | C++ analogue | Purpose |
|---|---|---|
| `copy_to_any_view(&T, &mut TVMFFIAny)` | `TypeTraits<T>::CopyToAnyView` | Borrow value into AnyView (non-owning) |
| `move_to_any(T, &mut TVMFFIAny)` | `TypeTraits<T>::MoveToAny` | Transfer ownership into Any |
| `check_any_strict(&TVMFFIAny) -> bool` | `TypeTraits<T>::CheckAnyStrict` | Fast exact-type check |
| `copy_from_any_view_after_check(&TVMFFIAny) -> T` | `TypeTraits<T>::CopyFromAnyViewAfterCheck` | Extract value from AnyView (with ref inc) |
| `move_from_any_after_check(&mut TVMFFIAny) -> T` | `TypeTraits<T>::MoveFromAnyAfterCheck` | Move ownership out of Any |
| `try_cast_from_any_view(&TVMFFIAny) -> Result<T, ()>` | `TypeTraits<T>::TryCastFromAnyView` | Lenient cast (e.g., int -> float) |
| `type_str() -> String` | (for error messages) | Human-readable type name |

Implementations are provided for:
- **Primitives**: `bool`, `i8`-`i64`, `u8`-`u64`, `isize`, `usize`, `f32`, `f64`
- **Unit type**: `()` maps to `kTVMFFINone`
- **Pointers**: `*mut c_void` maps to `kTVMFFIOpaquePtr`
- **DLPack types**: `DLDataType`, `DLDevice`
- **Generics**: `Option<T>` where `T: AnyCompatible` (maps `None` to `kTVMFFINone`)
- **ObjectRef types**: Auto-generated by `#[derive(ObjectRef)]` proc-macro

### Object System Traits

Three traits form the Rust object hierarchy:

```mermaid
classDiagram
    class ObjectCore {
        <<unsafe trait>>
        +TYPE_KEY: &str
        +type_index() i32
        +object_header_mut(&mut Self) &mut TVMFFIObject
    }
    class ObjectCoreWithExtraItems {
        <<unsafe trait>>
        +ExtraItem: type
        +extra_items_count(&Self) usize
        +extra_items(&Self) &[ExtraItem]
        +extra_items_mut(&mut Self) &mut [ExtraItem]
    }
    class ObjectRefCore {
        <<unsafe trait>>
        +ContainerType: ObjectCore
        +data(&Self) &ObjectArc~ContainerType~
        +into_data(Self) ObjectArc~ContainerType~
        +from_data(ObjectArc) Self
    }
    class ObjectArc~T~ {
        <<intrusive smart ptr>>
        -ptr: NonNull~T~
        +new(T) Self
        +new_with_extra_items(T) Self
        +from_raw(*const T) Self
        +into_raw(Self) *const T
        +strong_count(&Self) usize
    }
    ObjectCore <|-- ObjectCoreWithExtraItems
    ObjectCore <.. ObjectArc : "T: ObjectCore"
    ObjectRefCore *-- ObjectArc : "holds"
```

**`ObjectCore`** (Rust analogue of C++ `Object` base):
- Associates a `TYPE_KEY` string and `type_index()` with a Rust struct.
- Provides `object_header_mut` for accessing the `TVMFFIObject` header. The first field of every object struct is its parent type, and `object_header_mut` transitively delegates to the parent, ultimately reaching the `TVMFFIObject`.

**`ObjectCoreWithExtraItems`** (Rust analogue of C++ `InplaceArrayBase`):
- For objects with variable-length trailing data (e.g., `StringObj`, `BytesObj`, `ShapeObj`).
- Extra items are stored immediately after `sizeof::<Self>()` in memory.

**`ObjectRefCore`** (Rust analogue of C++ `ObjectRef`):
- Wraps an `ObjectArc<T>` and provides `data()`, `into_data()`, `from_data()` accessors.

### ObjectArc and Native Ref-Counting

`ObjectArc<T>` is the Rust equivalent of `ObjectPtr<T>`. It is an intrusive reference-counted smart pointer that directly operates on the `combined_ref_count` field in the `TVMFFIObject` header.

**Allocation**: `ObjectArc::new(data)` allocates via `std::alloc::alloc`, writes the data, then overwrites the `TVMFFIObject` header at offset 0 with the correct `combined_ref_count` (initialized to `COMBINED_REF_COUNT_BOTH_ONE`), `type_index`, and `deleter` function pointer. For objects with extra items, `ObjectArc::new_with_extra_items` computes the allocation size as `sizeof::<T>() + count * sizeof::<ExtraItem>()`.

**Inc/Dec ref**: Implemented natively in `object::unsafe_` using Rust atomics:
- `inc_ref`: `fetch_add(1, Relaxed)` on `combined_ref_count`.
- `dec_ref`: `fetch_sub(COMBINED_REF_COUNT_STRONG_ONE, Relaxed)`, then check old value:
  - If old was `COMBINED_REF_COUNT_BOTH_ONE` (common case: sole owner, no weak refs): `fence(Acquire)` then call `deleter(ptr, Both)`.
  - If old strong count was 1 but weak count > 1: `fence(Acquire)`, call `deleter(ptr, Strong)` to run destructor, then `fetch_sub(COMBINED_REF_COUNT_WEAK_ONE, Release)` on the weak portion and if weak hits zero, call `deleter(ptr, Weak)` to free memory.

**Deleters**: Two generic extern "C" deleters are provided:
- `object_deleter_for_new<T>`: For fixed-size objects -- calls `drop_in_place` on Strong, `dealloc` on Weak.
- `object_deleter_for_new_with_extra_items<T, U>`: For variable-size objects -- must capture `extra_items_count` before dropping (since the count field lives inside the object), stores it in the now-dead memory for the Weak phase to read for correct deallocation layout.

### Proc-Macros

**`#[derive(Object)]`** generates an `ObjectCore` impl for a struct:
- Reads `#[type_key = "..."]` for the type key string.
- Reads optional `#[type_index(...)]` for static index; if absent, uses `LazyLock` + `TVMFFITypeKeyToIndex` for dynamic lookup.
- Generates `object_header_mut` by delegating to the first field's `ObjectCore::object_header_mut`.

**`#[derive(ObjectRef)]`** generates:
- `ObjectRefCore` impl with `data()`, `into_data()`, `from_data()`.
- Full `AnyCompatible` impl for the ref type (copy/move to/from `TVMFFIAny`, type checking).
- `impl_try_from_any!`, `impl_arg_into_ref!`, `impl_into_arg_holder_default!` invocations for integration with the function argument system.

### Function System

`Function` wraps `FunctionObj` which contains a `TVMFFIFunctionCell` with `safe_call` and `cxx_call` function pointers.

**Calling**: `call_packed(&[AnyView]) -> Result<Any>` invokes `safe_call` directly. `call_tuple(tuple)` and `call_tuple_with_len::<N, _>(tuple)` convert Rust tuples to `AnyView` slices via the `TupleAsPackedArgs` trait.

**Creating from Rust closures**: `Function::from_packed(closure)` wraps any `Fn(&[AnyView]) -> Result<Any>` by creating a `CallbackFunctionObjImpl<F>` -- a `#[repr(C)]` struct that extends `FunctionObj` with the closure `F` stored immediately after the function cell. The `safe_call` pointer is set to a monomorphized `invoke_callback` that casts the handle back to `CallbackFunctionObjImpl<F>`.

**Creating from typed functions**: `Function::from_typed(func)` uses the `AsPackedCallable<I, O>` trait (implemented for `Fn(T0, T1, ...) -> Result<O>` for 0-8 args via macro) to auto-unpack `AnyView` arguments into typed values before calling the function.

**Typed function wrappers**: `into_typed_fn!(func, Fn(i32, &str) -> Result<i64>)` wraps a `Function` in a closure with compile-time type checking, using `IntoArgHolderTuple` for argument conversion and `TryInto` for result conversion.

**Exporting to C**: `tvm_ffi_dll_export_typed_func!(name, func)` generates a `pub unsafe extern "C" fn __tvm_ffi_<name>(...)` symbol with the packed calling convention.

**`from_extern_c` is `unsafe fn`** (commit `8255069` #496): Takes raw `*mut c_void` handle and C function pointers that cannot be validated by Rust. The caller must guarantee handle validity and function pointer compatibility.

### Clippy Soundness Fixes (commit `8255069` #496)

Three deny-level clippy lints were fixed:

1. **`Tensor::data_as_slice_mut(&self)`**: The original signature returned `&mut [T]` from `&self`, allowing aliased mutable references through multiple shared borrows (unsound). The method now takes `&self` but with a documented design rationale: like `std::fs::File::write`, the tensor metadata is governed by Rust ownership, but writing to the underlying data buffer (CPU/GPU memory) is an external side-effect. Most C/CUDA kernel APIs accept a non-mut tensor and mutate its data, so the design intentionally mirrors that pattern while documenting the safety invariant.

2. **`Device::with_stream`**: Marked `unsafe fn` because the `TVMFFIStreamHandle` (`*mut c_void`) cannot be validated (CUDA stream handles are opaque). The caller must uphold the invariant that the handle is a valid stream.

3. **`Function::from_extern_c`**: Marked `unsafe fn` because it takes a raw handle, a C function pointer, and an optional deleter, all forwarded to `TVMFFIFunctionCreate`. The function cannot verify handle validity or function pointer compatibility.

### String and Bytes with Small-String Optimization

`String` and `Bytes` are **not** `ObjectRef` types. They directly wrap a `TVMFFIAny` and implement a dual representation:

- **Small** (<=7 bytes): Stored inline in `TVMFFIAny.data_union.v_bytes` with `type_index = kTVMFFISmallStr/kTVMFFISmallBytes` and `small_str_len` recording the length. No heap allocation, no ref counting.
- **Large** (>7 bytes): Allocate `StringObj`/`BytesObj` via `ObjectArc::new_with_extra_items`. The `TVMFFIByteArray` data pointer points to trailing extra items. `type_index = kTVMFFIStr/kTVMFFIBytes`.

Clone/Drop check `type_index >= kTVMFFIStaticObjectBegin` to decide whether ref-counting applies.

The `AnyCompatible` implementation for `String` handles `try_cast_from_any_view` for `kTVMFFIRawStr` (C string pointer) by deep-copying into a new `String`. `Bytes` similarly handles `kTVMFFIByteArrayPtr`.

### Array<T> (commit `d0d0e2f` #348)

`Array<T>` is a generic container backed by `ArrayObj` (`#[repr(C)]`, type key `ffi.Array`, type index `kTVMFFIArray`):

- **Layout**: `ArrayObj` contains `object: Object`, `data: *mut c_void`, `size: i64`, `capacity: i64`, `data_deleter: Option<fn>`. Elements are stored as `TVMFFIAny` values inline via `ObjectCoreWithExtraItems<ExtraItem = TVMFFIAny>`.
- **Construction**: `Array::new(items)` allocates via `ObjectArc::new_with_extra_items`, writes each item as a raw `TVMFFIAny` into the trailing buffer, and sets the `data` pointer to the start of the extra items region.
- **Element access**: `get(index)` retrieves elements via `T::try_cast_from_any_view` on the raw `TVMFFIAny` at the given offset. `Index<usize>` returns `&AnyView<'static>` for zero-copy access.
- **Type checking**: `AnyCompatible` implementation uses recursive element-level checking. `check_any_strict` validates `type_index == kTVMFFIArray` and then checks each element against `T::check_any_strict`. Short-circuit: if `T` is `Any` (via `TypeId` comparison), element checking is skipped. `try_cast_from_any_view` supports a slow-path element-by-element conversion when strict checking fails. See [ADR 0058](../ADRs/0058-rust-array-recursive-type-checking.md).
- **Traits**: `FromIterator<T>`, `IntoIterator` (via `ArrayIterator`), `Clone`, `Default`, `Debug`, `Index<usize>`, `TryFrom<Any>`, `TryFrom<AnyView>`.
- **Memory fix**: `Any::into_raw_ffi_any` was fixed to use `ManuallyDrop` to prevent double-free when elements are moved into the array.

### Error Handling

`Error` wraps `ErrorObj` which contains `TVMFFIErrorCell` (kind, message, backtrace byte arrays plus an `update_backtrace` function pointer). Key operations:

- `Error::new(kind, message, traceback)` calls `TVMFFIErrorCreate` C API.
- `Error::from_raised()` / `Error::set_raised(&error)` use TLS error transport via `TVMFFIErrorMoveFromRaised` / `TVMFFIErrorSetRaised`.
- `Error::with_appended_backtrace` mutates in-place if `strong_count == 1`, otherwise clones.
- `bail!`, `ensure!`, `check_safe_call!`, `attach_context!` macros provide ergonomic error creation with automatic `file!()`, `line!()`, `function_name!()` traceback info.

`type Result<T, E = Error> = std::result::Result<T, E>` is the standard result alias.

### Module System

`Module` wraps `ModuleObj` and provides:
- `Module::load_from_file(path)` -- calls `ffi.ModuleLoadFromFile` global function via lazy-initialized `Function::get_global`.
- `module.get_function(name)` -- calls `ffi.ModuleGetFunction`.

Both use `LazyLock<Function>` for one-time global function lookup.

### Build System Integration

Both `tvm-ffi-sys/build.rs` and `tvm-ffi/build.rs`:
1. Run `tvm-ffi-config --libdir` to discover the library directory (provided by the Python package).
2. Emit `cargo:rustc-link-search=native=<libdir>` and `cargo:rustc-link-lib=dylib=tvm_ffi`.
3. Set platform-appropriate library path env vars (`LD_LIBRARY_PATH`, `DYLD_LIBRARY_PATH`, `PATH`) via `cargo:rustc-env` so that `cargo test` works without manual environment setup.

`tvm-ffi/build.rs` additionally supports an optional `CARGO_FEATURE_EXAMPLE` flag that runs a Python script to generate an example shared library for the `load_library` example.

## Key Files

| Path | Purpose |
|---|---|
| `rust/Cargo.toml` | Workspace definition |
| `rust/tvm-ffi-sys/src/c_api.rs` | All `#[repr(C)]` C ABI type definitions and extern "C" declarations |
| `rust/tvm-ffi-sys/src/c_env_api.rs` | Stream/allocator/env C API declarations |
| `rust/tvm-ffi-sys/build.rs` | Library discovery via tvm-ffi-config |
| `rust/tvm-ffi-macros/src/object_macros.rs` | `#[derive(Object)]` and `#[derive(ObjectRef)]` proc-macros |
| `rust/tvm-ffi/src/object.rs` | `ObjectArc<T>`, `ObjectCore`, `ObjectRefCore`, native ref-counting |
| `rust/tvm-ffi/src/any.rs` | `Any`, `AnyView` containers |
| `rust/tvm-ffi/src/type_traits.rs` | `AnyCompatible` trait and primitive impls |
| `rust/tvm-ffi/src/function.rs` | `Function`, `FunctionObj`, `CallbackFunctionObjImpl` |
| `rust/tvm-ffi/src/function_internal.rs` | `AsPackedCallable`, `TupleAsPackedArgs`, argument helpers |
| `rust/tvm-ffi/src/string.rs` | `String`, `Bytes` with SSO |
| `rust/tvm-ffi/src/error.rs` | `Error`, `ErrorObj`, error handling macros |
| `rust/tvm-ffi/src/macros.rs` | `tvm_ffi_dll_export_typed_func!`, `into_typed_fn!`, `bail!`, etc. |
| `rust/tvm-ffi/src/collections/array.rs` | `Array<T>`, `ArrayObj`, `ArrayIterator` |
| `rust/tvm-ffi/src/collections/tensor.rs` | `Tensor`, `TensorObj`, `NDAllocator` |
| `rust/tvm-ffi/src/collections/shape.rs` | `Shape`, `ShapeObj` |
| `rust/tvm-ffi/src/extra/module.rs` | `Module` wrapper |

## Cross-Language Type Mapping

| C ABI type | C++ type | Rust type |
|---|---|---|
| `TVMFFIAny` | `AnyView` / `Any` | `AnyView<'a>` / `Any` |
| `TVMFFIObject` | `Object` | `Object` (+ `ObjectCore` trait) |
| `ObjectPtr<T>` | `ObjectPtr<T>` | `ObjectArc<T>` |
| `ObjectRef` | `ObjectRef` | `ObjectRef` (+ `ObjectRefCore` trait) |
| `TVMFFIFunctionCell` | `Function` | `Function` |
| `TVMFFIErrorCell` | `Error` | `Error` |
| `TVMFFIByteArray` | `String` / `Bytes` | `String` / `Bytes` |
| `TVMFFIShapeCell` | `Shape` | `Shape` |
| (ArrayObj inline) | `Array<T>` | `Array<T>` |
| `DLTensor` | `Tensor` | `Tensor` |
| `TypeTraits<T>` | `TypeTraits<T>` | `AnyCompatible` (unsafe trait) |
| `TVM_FFI_DECLARE_OBJECT_INFO` | macro | `#[derive(Object)]` + `#[type_key]` |
| `TVM_FFI_DEFINE_OBJECT_REF_METHODS` | macro | `#[derive(ObjectRef)]` |
| `TVM_FFI_DLL_EXPORT_TYPED_FUNC` | macro | `tvm_ffi_dll_export_typed_func!` |

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](0001-c-abi.md) -- C ABI types consumed by tvm-ffi-sys
- [`.knowledge/designs/0002-any-system.md`](0002-any-system.md) -- Any/AnyView design mirrored in Rust
- [`.knowledge/designs/0003-object-system.md`](0003-object-system.md) -- Object system and ref-counting protocol
- [`.knowledge/designs/0004-function-system.md`](0004-function-system.md) -- Packed function calling convention
- [`.knowledge/designs/0007-error-handling.md`](0007-error-handling.md) -- Error/traceback system
- [`.knowledge/designs/0013-module-system.md`](0013-module-system.md) -- Module loading
- [`.knowledge/ADRs/0040-native-rust-ref-counting.md`](../ADRs/0040-native-rust-ref-counting.md) -- Why native Rust ref-counting was chosen
- [`.knowledge/ADRs/0041-manual-c-api-transcription-in-rust.md`](../ADRs/0041-manual-c-api-transcription-in-rust.md) -- Why hand-written #[repr(C)] over bindgen
- [`.knowledge/ADRs/0058-rust-array-recursive-type-checking.md`](../ADRs/0058-rust-array-recursive-type-checking.md) -- Recursive element-level type checking for Array<T>
- Commit: `.knowledge/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md`
- Rust Array<T> binding (ArrayObj, AnyCompatible, ManuallyDrop fix) -> `.knowledge/commits/2026-01-30-d0d0e2f935cda443bd85e097a3cfb18de2a96f4d.md` + `d0d0e2f`
- Fix 3 deny-level clippy lints (data_as_slice_mut signature, with_stream unsafe, from_extern_c unsafe) -> `.knowledge/commits/2026-03-04-8255069663aad60ae24876a592ae4282cc91733e.md` + `8255069`
