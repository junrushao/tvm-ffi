---
design: "0017"
title: "Rust FFI Binding Layer"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-10-01"
last_updated: "2025-10-01"
scope:
  - "rust/tvm-ffi-sys"
  - "rust/tvm-ffi-macros"
  - "rust/tvm-ffi"
source_commits:
  - "09477ce10de566f8cf511cce7dfe56e77759f100"
source_ledgers:
  - ".memory/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md"
---

# Rust FFI Binding Layer

## TL;DR
- A three-crate Rust workspace (`tvm-ffi-sys`, `tvm-ffi-macros`, `tvm-ffi`) provides a complete third first-class language binding for TVM FFI, mirroring the C++/Python object model with idiomatic Rust ergonomics.
- Ref-counting (`ObjectArc<T>`) is reimplemented natively in Rust with atomics matching the C++ `combined_ref_count` protocol, avoiding FFI call overhead on every clone/drop.
- Proc-macro derives (`#[derive(Object)]`, `#[derive(ObjectRef)]`) generate the `ObjectCore`, `ObjectRefCore`, and `AnyCompatible` trait implementations, minimizing boilerplate for new Rust object types.

## Problem Statement
Rust is a valuable systems programming language for ML infrastructure. Without native bindings, Rust programs must call TVM FFI functions through raw C bindings without type safety, reference-counting automation, or ergonomic container types. The Rust binding must be ABI-compatible with the stable C ABI while providing safe, idiomatic Rust abstractions that map cleanly to the C++/Python equivalents.

## Context and Constraints
- The Rust bindings must consume the same stable C ABI (`c_api.h`) that Python and other languages use. No C++ dependency is allowed.
- All `#[repr(C)]` struct layouts must exactly match their C counterparts in field order, size, and alignment. These are hand-written, not bindgen-generated, for precise control over atomics and alignment (see [ADR-0027](.memory/ADRs/0027-hand-written-repr-c-over-bindgen.md)).
- Building the Rust crates requires the Python package to be installed first, as `tvm-ffi-config` is needed to locate the native library.
- The Rust bindings support both consuming FFI libraries from Rust and exposing Rust libraries as FFI-compatible shared objects (via `tvm_ffi_dll_export_typed_func!`).
- The design is explicitly tagged as experimental; the primary focus remains C++ and Python.

## Goals
- Provide safe, idiomatic Rust wrappers for all core TVM FFI types: `Any`/`AnyView`, `ObjectArc<T>`, `Function`, `String`, `Bytes`, `Tensor`, `Shape`, `Error`, `Module`, `Array`.
- Minimize FFI call overhead: ref-counting operations are native Rust atomics, not cross-language calls (see [ADR-0028](.memory/ADRs/0028-native-rust-refcounting.md)).
- Provide proc-macro derives to minimize boilerplate when defining new object types in Rust.
- Provide macros for registering global functions (`register_global_func!`) and creating typed function wrappers (`into_typed_fn!`).
- Support loading and calling functions from dynamically loaded FFI modules.

## Non-Goals
- Exposing the C++ reflection system (`ObjectDef<T>`) from Rust. Rust objects are defined using proc macros, not reflection builders.
- Weak reference support from Rust. Only strong references (`ObjectArc<T>`) are implemented.
- Full container generic typing (e.g., `Array<T>` with element-type checking). The initial `Array` is untyped.

## Design
### Components and Responsibilities

- **`tvm-ffi-sys`** (crate, `rust/tvm-ffi-sys/`): Raw C ABI bindings. Contains hand-written `#[repr(C)]` mirrors of `TVMFFIAny`, `TVMFFIObject`, `TVMFFIFunctionCell`, `TVMFFIErrorCell`, `TVMFFIByteArray`, `TVMFFIShapeCell`, DLPack structs, and `extern "C"` declarations for all `TVMFFI*` C functions. The `build.rs` runs `tvm-ffi-config --libdir` to discover the native library, links `libtvm_ffi` and `libtvm_ffi_testing`, and sets platform-specific library path environment variables for `cargo test`.

- **`tvm-ffi-macros`** (proc-macro crate, `rust/tvm-ffi-macros/`): Provides `#[derive(Object)]` and `#[derive(ObjectRef)]` proc macros. `derive(Object)` generates `ObjectCore` trait impl from `#[type_key]` and optional `#[type_index]` attributes. `derive(ObjectRef)` generates `ObjectRefCore` trait impl plus a full `AnyCompatible` impl with correct ref-counting semantics (inc_ref on copy_from_any, move semantics on move_from_any, etc.), plus `TryFrom<Any>`/`TryFrom<AnyView>` blanket impls.

- **`tvm-ffi`** (main crate, `rust/tvm-ffi/`): The safe ergonomic API. Contains:
  - **`any.rs`**: `AnyView<'a>` (non-owning, `Copy`, lifetime-bound) and `Any` (owning, ref-counting on drop). Both provide `try_as<T>()` for strict type checks. `Any` implements `Clone` (with inc_ref for objects) and `Drop` (with dec_ref). `AnyView` to `Any` conversion goes through `TVMFFIAnyViewToOwnedAny` C API to handle raw string promotion. `From<T> for Any` and `From<&T> for AnyView` are provided for all `AnyCompatible` types.
  - **`object.rs`**: `ObjectCore` unsafe trait (requires `TYPE_KEY`, `type_index()`, `object_header_mut()`), `ObjectCoreWithExtraItems` trait for variable-length objects, `ObjectRefCore` trait for ref wrappers. `ObjectArc<T>` is the ref-counted smart pointer (analogous to C++ `ObjectPtr<T>`). The `unsafe_` module contains native `inc_ref`/`dec_ref` implementations using `AtomicU64` fetch_add/fetch_sub with the same memory ordering protocol as C++ (Relaxed for increment, Release+Acquire for final decrement). Custom deleters (`object_deleter_for_new`, `object_deleter_for_new_with_extra_items`) handle the two-phase strong/weak deletion protocol.
  - **`type_traits.rs`**: `AnyCompatible` unsafe trait with 7 methods: `copy_to_any_view`, `move_to_any`, `check_any_strict`, `copy_from_any_view_after_check`, `move_from_any_after_check`, `try_cast_from_any_view`, `type_str`. Implemented for: `bool`, all integer types (via macro), `f32`/`f64` (via macro), `()` (maps to `kTVMFFINone`), `*mut c_void` (opaque pointer), `DLDataType`, `DLDevice`, `Option<T>`, and all `ObjectRef` subclasses (via `derive(ObjectRef)` proc macro). String and Bytes have custom implementations in `string.rs`.
  - **`function.rs`**: `FunctionObj` (Object + TVMFFIFunctionCell), `Function` (ObjectRef wrapper). `Function::call_packed` invokes via `safe_call` C ABI path. `Function::call_tuple` and `call_tuple_with_len` pack typed arguments into `AnyView` arrays. `Function::from_packed` creates a `CallbackFunctionObjImpl<F>` that wraps any `Fn(&[AnyView]) -> Result<Any>`. `Function::from_typed` wraps `Fn(T0, T1, ...) -> Result<O>` via `AsPackedCallable` trait. `Function::get_global`/`register_global` bridge to the global registry.
  - **`function_internal.rs`**: `AsPackedCallable<I, O>` trait (implemented for 0-8 arg functions via macro), `TupleAsPackedArgs` trait, `IntoArgHolder`/`IntoArgHolderTuple`/`ArgIntoRef` helper traits for argument marshaling.
  - **`string.rs`**: `String` and `Bytes` as value types (not ObjectRef). Dual representation: small-string optimization (<=7 bytes inline in `TVMFFIAny`) or heap-allocated `StringObj`/`BytesObj` with `ObjectCoreWithExtraItems`. Implement `Deref<Target=str>` / `Deref<Target=[u8]>`, `Clone` (with inc_ref), `Drop` (with dec_ref), `Hash`, `Eq`, `Ord`, `Display`, `Debug`, and custom `AnyCompatible` that handles `kTVMFFISmallStr`/`kTVMFFIStr` and `kTVMFFISmallBytes`/`kTVMFFIBytes` cross-type equivalence.
  - **`error.rs`**: `ErrorObj` (Object + TVMFFIErrorCell), `Error` (ObjectRef), `ErrorKind` wrapper, standard error kinds (`VALUE_ERROR`, `TYPE_ERROR`, etc.). `Error::from_raised()` moves error from TLS. `Error::set_raised()` pushes error to TLS. Implements `std::error::Error` and `Display` with Python-style traceback formatting.
  - **`macros.rs`**: `check_safe_call!` (C ABI return code handling), `bail!`/`ensure!` (error creation with file/line), `attach_context!` (backtrace augmentation), `impl_try_from_any!` (blanket TryFrom impls), `tvm_ffi_dll_export_typed_func!` (exports `__tvm_ffi_<name>` C symbols), `into_typed_fn!` (wraps untyped Function into typed closure).
  - **`collections/tensor.rs`**: `TensorObj` with `DLTensor`, `Tensor` ref wrapper, `NDAllocator` trait, `CPUNDAlloc` default allocator with `posix_memalign`.
  - **`collections/shape.rs`**: `ShapeObj` wrapping `TVMFFIShapeCell`, `Shape` ref wrapper with inline small-shape optimization.
  - **`extra/module.rs`**: `ModuleObj` / `Module` wrapping `ffi.Module`, with `load_from_file` and `get_function` methods that call through the global function registry.

### Data Contracts and Invariants
- **ABI struct layout fidelity**: Every `#[repr(C)]` struct in `tvm-ffi-sys` must have identical size, alignment, and field offsets to the corresponding C struct in `c_api.h`. This is verified by the test suite calling across the FFI boundary and receiving correctly-typed values.
- **TVMFFIAny is 16 bytes**: Rust `TVMFFIAny` has `type_index: i32`, `small_str_len: u32`, `data_union: TVMFFIAnyDataUnion` (8 bytes). The `data_union` is a `#[repr(C)] union` with the same fields as the C version.
- **Combined refcount protocol**: `ObjectArc<T>` initializes `combined_ref_count` to `COMBINED_REF_COUNT_BOTH_ONE` (strong=1, weak=1). Increment is `fetch_add(1, Relaxed)` on the lower 32 bits. Decrement follows the same three-branch protocol as C++: if `old == BOTH_ONE` then `deleter(Both)` (fast path); else if strong bits == 1 then `deleter(Strong)` + `dec_weak`; else no-op.
- **String/Bytes dual representation**: Strings <= 7 bytes use `kTVMFFISmallStr` with inline `v_bytes`. Strings > 7 bytes use heap-allocated `StringObj` with trailing byte array. The `AnyCompatible` impl treats both representations as equivalent for strict checking.
- **Function call convention**: All function calls from Rust go through `safe_call` (C ABI path with error code return), not `cpp_call`. This is correct because Rust is a foreign caller from the C ABI perspective.
- **Error propagation**: Rust errors go through `TVMFFIErrorSetRaised`/`TVMFFIErrorMoveFromRaised` TLS protocol, matching the Python binding behavior.

### Control Flow
1. **Rust calls a C++ function**: `func.call_packed(args)` -> `safe_call(self_ptr, args_ptr, num_args, &mut result)` -> check return code -> if 0, return `Any::from_raw_ffi_any(result)`; if -1, call `Error::from_raised()` and return `Err`.
2. **C++ calls a Rust function**: `CallbackFunctionObjImpl::invoke_callback` receives packed args -> creates `&[AnyView]` slice from raw pointer -> invokes `callback(packed_args)` -> on `Ok(value)`, writes `Any::into_raw_ffi_any(value)` to result; on `Err(error)`, calls `Error::set_raised(&error)` and returns -1.
3. **Object construction in Rust**: `ObjectArc::new(data)` -> `alloc(Layout::new::<T>())` -> `ptr::write(ptr, data)` -> overwrite header at offset 0 with `{combined_ref_count: BOTH_ONE, type_index: T::type_index(), deleter: object_deleter_for_new::<T>}` -> return `ObjectArc { ptr: NonNull }`.
4. **ObjectArc clone/drop**: Clone calls `unsafe_::inc_ref(header_ptr)` (Relaxed fetch_add). Drop calls `unsafe_::dec_ref(header_ptr)` which atomically decrements and dispatches to the deleter on final release.
5. **Module loading from Rust**: `Module::load_from_file("path.so")` -> looks up `ffi.ModuleLoadFromFile` global function -> calls it via packed convention -> returns `Module` ref wrapper.
6. **DSO export from Rust**: `tvm_ffi_dll_export_typed_func!(name, func)` generates `pub unsafe extern "C" fn __tvm_ffi_name(...)` with the `TVMFFISafeCallType` signature. The function unpacks args via `call_packed_callable`, serializes the result or error to the return slot.

### Extension Points
- **New Rust object types**: Use `#[derive(Object)]` with `#[type_key]` and optional `#[type_index]` on the data struct, and `#[derive(ObjectRef)]` on the ref wrapper. Dynamic type indices are resolved at first access via `TVMFFITypeKeyToIndex`.
- **Custom allocators**: The `NDAllocator` trait allows plugging in custom memory allocators for tensor data.
- **Additional container types**: New containers can implement `ObjectCore`/`ObjectRefCore` and `AnyCompatible` following the existing patterns for `Array`, `Tensor`, `Shape`.
- **New function argument types**: Implement `AnyCompatible` for new types and use `impl_try_from_any!`/`impl_arg_into_ref!` macros.

## Alternatives Considered
### Use bindgen to auto-generate Rust bindings
- Pros: Automatically stays in sync with C header changes. Less manual work.
- Cons: Cannot control atomic types (`AtomicU64` for `combined_ref_count`), alignment padding, and optional function pointers (`Option<extern "C" fn(...)>`). bindgen generates raw types that would need extensive post-processing. See [ADR-0027](.memory/ADRs/0027-hand-written-repr-c-over-bindgen.md).

### Call TVMFFIObjectIncRef/DecRef via C API instead of native Rust atomics
- Pros: Single source of truth for ref-counting logic. Guaranteed correctness.
- Cons: FFI call overhead on every clone/drop. Ref-counting is pervasive (every object pass incurs it), so the overhead is material. See [ADR-0028](.memory/ADRs/0028-native-rust-refcounting.md).

## Trade-offs
- **Optimized**: Interoperability (full ABI compatibility with C++ and Python), ref-counting performance (native atomics), ergonomics (proc-macro derives, typed function wrappers), safety (Rust borrow checker for lifetime management of `AnyView`).
- **Sacrificed**: Automatic ABI synchronization (manual `#[repr(C)]` structs must be updated when C headers change), weak reference support (not implemented in Rust), complete container typing (Array is untyped), runtime type checking for ObjectRef (only exact type_index match, no ancestor walk).

## Interfaces and Compatibility
- **C ABI consumed**: All `TVMFFI*` functions declared in `c_api.h` that are used by the Rust bindings are re-declared as `extern "C"` in `tvm-ffi-sys/src/c_api.rs`.
- **Rust public API**: `tvm_ffi` crate exports `Any`, `AnyView`, `ObjectArc`, `Object`, `ObjectCore`, `ObjectRefCore`, `AnyCompatible`, `Function`, `String`, `Bytes`, `Error`, `Tensor`, `Shape`, `Module`, `Array`, `DLDataType`, `DLDevice`, plus all macros.
- **DSO export**: `tvm_ffi_dll_export_typed_func!` generates C-compatible `__tvm_ffi_<name>` symbols that can be loaded by `Module::load_from_file`.
- **Build dependency**: `tvm-ffi-config` CLI tool (from Python package) must be available at build time. `tvm-ffi-sys/build.rs` panics if it is missing.

## Failure Modes and Mitigations
- **ABI struct mismatch**: If `c_api.h` changes field offsets without updating the Rust `#[repr(C)]` mirrors, values will be misinterpreted. Mitigated by cross-language tests (Rust test suite calls C++ functions and verifies round-trip correctness) and by the small, stable nature of the ABI surface.
- **Ref-count protocol divergence**: If the C++ ref-counting logic changes (e.g., different atomics ordering or phase protocol), the native Rust implementation in `unsafe_::dec_ref` must be updated in lockstep. Mitigated by the detailed code comment documenting the exact C++ function being mirrored (`ObjectInternal::DecRef`).
- **`tvm-ffi-config` not found at build time**: `build.rs` panics with a clear message. Mitigated by CI ordering (Python install before `cargo test`) and documentation.
- **String encoding mismatch**: Rust `String` assumes valid UTF-8 via `from_utf8_unchecked`. If the C++ side stores non-UTF-8 bytes in a `String` object, undefined behavior occurs. Mitigated by the convention that `ffi.String` is always UTF-8 (non-UTF-8 data uses `ffi.Bytes`).

## Observability and Validation
- `rust/tvm-ffi/tests/test_any.rs`: Tests `Any`/`AnyView` construction, conversion, ownership semantics, ref-counting for all POD and object types.
- `rust/tvm-ffi/tests/test_object.rs`: Tests `ObjectArc` construction, clone, drop, custom object types with `#[derive(Object)]`.
- `rust/tvm-ffi/tests/test_function.rs`: Tests function creation, packed calls, typed functions, `into_typed_fn!`, global function registry.
- `rust/tvm-ffi/tests/test_string.rs`: Tests small-string optimization, heap strings, cross-language string passing.
- `rust/tvm-ffi/tests/test_tensor.rs`: Tests tensor allocation, DLPack conversion, cross-language tensor passing.
- `rust/tvm-ffi/tests/test_error.rs`: Tests error creation, TLS propagation, backtrace formatting.
- CI: `cargo test` runs after Python pip install in `.github/workflows/ci_test.yml`.

## Migration and Rollout
- This is a greenfield addition. No existing code is affected. The Rust bindings are explicitly tagged as experimental.
- Future commits may add: weak reference support, typed `Array<T>`, reflection-based object definition, Rust-side `IsInstance` with ancestor walks.

## Diagrams
- [.memory/diagrams/0014-rust-crate-architecture.md](.memory/diagrams/0014-rust-crate-architecture.md)

## Related ADRs
- [.memory/ADRs/0027-hand-written-repr-c-over-bindgen.md](.memory/ADRs/0027-hand-written-repr-c-over-bindgen.md)
- [.memory/ADRs/0028-native-rust-refcounting.md](.memory/ADRs/0028-native-rust-refcounting.md)
- [.memory/ADRs/0002-combined-refcount-in-single-u64.md](.memory/ADRs/0002-combined-refcount-in-single-u64.md) (consumed)
- [.memory/ADRs/0008-release-acquire-refcount-split.md](.memory/ADRs/0008-release-acquire-refcount-split.md) (consumed)
- [.memory/ADRs/0010-string-bytes-as-value-types.md](.memory/ADRs/0010-string-bytes-as-value-types.md) (consumed)

## Evidence Matrix
- Three-crate workspace structure -> `.memory/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md` + `09477ce` + `rust/Cargo.toml`
- Hand-written `#[repr(C)]` ABI structs -> ledger Reflection + `09477ce` + `rust/tvm-ffi-sys/src/c_api.rs`
- Native ref-counting with `AtomicU64` -> ledger + `09477ce` + `rust/tvm-ffi/src/object.rs` `unsafe_::dec_ref`
- `ObjectCore`/`ObjectRefCore` traits -> ledger + `09477ce` + `rust/tvm-ffi/src/object.rs`
- `AnyCompatible` trait with 7 methods -> ledger + `09477ce` + `rust/tvm-ffi/src/type_traits.rs`
- `#[derive(Object)]` proc macro -> ledger + `09477ce` + `rust/tvm-ffi-macros/src/object_macros.rs`
- `#[derive(ObjectRef)]` proc macro with AnyCompatible generation -> ledger + `09477ce` + `rust/tvm-ffi-macros/src/object_macros.rs`
- `CallbackFunctionObjImpl<F>` struct inheritance pattern -> ledger + `09477ce` + `rust/tvm-ffi/src/function.rs`
- `String`/`Bytes` dual representation (SSO + heap) -> ledger + `09477ce` + `rust/tvm-ffi/src/string.rs`
- `tvm-ffi-config` build dependency -> ledger + `09477ce` + `rust/tvm-ffi-sys/build.rs`
- `tvm_ffi_dll_export_typed_func!` macro -> ledger + `09477ce` + `rust/tvm-ffi/src/macros.rs`
- `into_typed_fn!` macro -> ledger + `09477ce` + `rust/tvm-ffi/src/macros.rs`
- Module loading from Rust -> ledger + `09477ce` + `rust/tvm-ffi/src/extra/module.rs`
- CI integration (cargo test after pip install) -> ledger + `09477ce` + `.github/workflows/ci_test.yml`

## Open Questions
- Should weak references (`WeakObjectPtr` equivalent) be exposed in the Rust bindings?
- Should the Rust `ObjectRef` types support ancestor-walk `IsInstance` checking via `TVMFFIGetTypeInfo`, or is exact-type-index matching sufficient?
- Should `Array<T>` enforce element-type checking at insertion time?
- Should `tvm-ffi-sys` be publishable as a standalone crate, or must it always be built against a local TVM FFI install?

## Confidence and Risk
- Confidence: high (for core abstractions: Any, ObjectArc, Function, String/Bytes, Error)
- Residual risks: Manual ABI struct mirroring requires lockstep updates when `c_api.h` changes. The native ref-counting implementation must track any changes to the C++ protocol. The `tvm-ffi-config` build dependency creates a hard coupling to the Python package installation order.
