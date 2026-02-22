# Rust Bindings

- Doc ID: 010-rust-bindings
- Status: Draft
- Last Updated: 2026-01-30
- Owners: Tianqi Chen

## Overview

The TVM FFI Rust bindings provide safe, ergonomic access to the TVM FFI
from Rust. Introduced as an experimental feature in October 2025, the
`rust/` directory contains a Cargo workspace with three crates that mirror
the C++/Python FFI layer. The Rust bindings link against the
`libtvm_ffi` shared library and require the Python package to be installed
first for C headers.

## Key Design

### Crate workspace

The `rust/` directory (`09477ce`) contains a Cargo workspace with three
crates:

```
rust/
  Cargo.toml              # Workspace definition
  tvm-ffi-sys/            # Raw C API bindings
    Cargo.toml
    build.rs              # Links against libtvm_ffi shared library
    src/
      c_api.rs            # TVMFFIAny, TVMFFIObject, etc.
      c_env_api.rs        # TVMFFIEnv* functions
      dlpack.rs           # DLTensor, DLDevice, DLDataType
      lib.rs
  tvm-ffi/                # Safe ergonomic API
    Cargo.toml
    build.rs              # Builds example libraries for tests
    src/
      any.rs              # Any, AnyView type-erased containers
      object.rs           # Object, ObjectRef ref-counted wrappers
      function.rs         # Function packed calling convention
      function_internal.rs
      string.rs           # String wrapper
      device.rs           # Device type
      dtype.rs            # DType (DLDataType wrapper)
      error.rs            # Error handling
      type_traits.rs      # TypeTraits and conversion traits
      macros.rs           # Helper macros
      derive.rs           # Derive utilities
      collections/
        mod.rs
        array.rs          # Array<T> immutable container
        shape.rs          # Shape container
        tensor.rs         # Tensor wrapper
      extra/
        mod.rs
        module.rs         # Module loading
      lib.rs
    examples/
      load_library.rs     # Example: loading a shared library
    scripts/
      generate_example_lib.py  # Script to generate test libraries
    tests/
      test_any.rs         # Comprehensive Any tests
      test_array.rs       # Array<T> tests
      test_device.rs      # Device tests
      test_dtype.rs       # DType tests
      test_error.rs       # Error handling tests
      test_function.rs    # Function calling tests
      test_object.rs      # Object tests
      test_shape.rs       # Shape tests
      test_string.rs      # String tests
      test_tensor.rs      # Tensor tests
  tvm-ffi-macros/         # Proc-macro crate
    Cargo.toml
    src/
      lib.rs              # Entry point
      object_macros.rs    # #[tvm_object] derive macro
      utils.rs            # Macro utilities
```

### tvm-ffi-sys: raw C bindings

`tvm-ffi-sys` (`09477ce`) provides unsafe Rust bindings to the TVM FFI C
API. `c_api.rs` defines the raw struct layouts (`TVMFFIAny`,
`TVMFFIObject`, `TVMFFIFunctionCell`, etc.) and extern "C" function
declarations. `dlpack.rs` provides DLPack struct definitions.

The `build.rs` script links against the `libtvm_ffi` shared library by
discovering its path from the Python package installation.

### tvm-ffi: safe API

`tvm-ffi` (`09477ce`) provides safe Rust wrappers for the core FFI types:

- `Any` / `AnyView`: Type-erased value containers with automatic
  conversion traits
- `Object` / `ObjectRef`: Reference-counted heap objects with safe
  downcasting
- `Function`: Type-erased callable with packed calling convention
- `String`: FFI string with `Deref<Target=str>`
- `Shape`: Shape container
- `Tensor`: DLPack tensor wrapper
- `Device`: Device type/id pair
- `DType`: Data type (code, bits, lanes)
- `Error`: FFI error handling with Rust `Result` integration
- `Module`: Shared library loading and function lookup

### #[tvm_object] derive macro

`tvm-ffi-macros` (`09477ce`) provides the `#[tvm_object]` proc-macro
attribute for declaring Rust types that correspond to TVM FFI objects.
The macro generates:

- `TypeTraits` implementation for automatic type dispatch
- `From`/`Into` conversions for `Any`/`AnyView`
- Safe downcast methods
- Type key and type index constants

### Array<T> binding (January 2026)

`tvm_ffi::Array<T>` (`d0d0e2f`, 341 lines) implements the TVM FFI immutable
array container in Rust with:

- Correct `inc_ref`/`dec_ref` reference counting for `ObjectRef` elements
- `get(index)` returning `Option<T>`
- `FromIterator<T>` and `IntoIterator` trait implementations
- `len()`, `is_empty()`, element iteration

The implementation also fixed a double-free bug in `Any::into_raw_ffi_any` by
wrapping `self` in `ManuallyDrop` before accessing `self.data`, preventing
the drop implementation from running after the data has been moved out.

132 lines of integration tests cover construction, retrieval, edge cases.

### Build model

The Rust crates require the Python `tvm_ffi` package to be installed
first, because:

1. `tvm-ffi-sys/build.rs` discovers the `libtvm_ffi` shared library path
   from the Python installation
2. C header files are needed for struct layout verification
3. Tests require the shared library to be loadable at runtime

Running `cd rust && cargo test` exercises the full test suite.

### Documentation

Rust documentation was added to the Sphinx docs site (`729f971`,
`9a6ec6e`) with a dedicated `docs/reference/rust/index.rst` section and
`docs/guides/rust_guide.md`.

## APIs

### Rust API

```rust
use tvm_ffi::{Any, Function, Module, String as TvmString, Tensor};

// Load a shared library module
let module = Module::load("library.so", "")?;
let func: Function = module.get_function("add_one", false)?;

// Call a function
let result: Any = func.call(&[Any::from(42i64)])?;
let value: i64 = result.try_into()?;

// Create objects
let s = TvmString::from("hello");
let tensor = Tensor::empty(&[2, 3], tvm_ffi::DType::float32(), tvm_ffi::Device::cpu(0));
```

### Derive macro

```rust
use tvm_ffi_macros::tvm_object;

#[tvm_object("my.CustomObj")]
struct CustomObj {
    value: i64,
}
```

## Implementation

Key files:
- `rust/tvm-ffi-sys/src/c_api.rs` -- Raw C API struct definitions and extern functions
- `rust/tvm-ffi-sys/build.rs` -- Library discovery and linking
- `rust/tvm-ffi/src/any.rs` -- Any/AnyView type-erased containers
- `rust/tvm-ffi/src/object.rs` -- Object/ObjectRef with ref-counting
- `rust/tvm-ffi/src/function.rs` -- Function packed calling convention
- `rust/tvm-ffi/src/string.rs` -- String wrapper
- `rust/tvm-ffi/src/collections/tensor.rs` -- Tensor wrapper
- `rust/tvm-ffi/src/collections/array.rs` -- Array<T> immutable container
- `rust/tvm-ffi/src/extra/module.rs` -- Module loading
- `rust/tvm-ffi-macros/src/object_macros.rs` -- #[tvm_object] proc-macro

Tests:
- `rust/tvm-ffi/tests/` -- 10 test files covering all major types

## History
- 2025-10-01: Initial bringup of Rust crate workspace with tvm-ffi-sys, tvm-ffi, tvm-ffi-macros (`09477ce`)
- 2025-10-15: Rust env API bindings renamed to match C API changes (`f679fe5`)
- 2025-10-18: Rust documentation and guide added to Sphinx docs (`729f971`)
- 2025-10-18: Rust docs fixes (`9a6ec6e`)
- 2025-10-26: `setuptools_scm` version check extended with `--rust` flag (`ac63fb9`)
- 2026-01-30: `tvm_ffi::Array<T>` Rust binding added with 341 lines of implementation and 132 lines of tests; `Any::into_raw_ffi_any` double-free fix via `ManuallyDrop` (`d0d0e2f`)

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-10-31-FFA2DBF-BC0D225.md`
  - `.repo-knowledge/ranges/2026-01-30-C51E519-B508698.md`
- Related design docs:
  - `.repo-knowledge/design/003-c-abi-stability.md`
  - `.repo-knowledge/design/001-type-erased-value-system.md`
