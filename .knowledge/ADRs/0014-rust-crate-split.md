---
scope:
  - "0016-rust-bindings.md"
---
# ADR 0014: Three-Crate Rust Workspace (sys / macros / ffi)

**TL;DR**: Decision to split Rust bindings into three crates (`tvm-ffi-sys`, `tvm-ffi-macros`, `tvm-ffi`) following the standard Rust `-sys` crate convention, rather than a single monolithic crate.

## Context
- Rust requires proc-macro crates to be separate from the crates that use them (`proc-macro = true` crates cannot export non-macro items). This means the derive macros (`#[derive(Object)]`, `#[derive(ObjectRef)]`) must live in their own crate regardless.
- The raw C ABI bindings (`#[repr(C)]` structs, `extern "C"` function declarations) are a logically distinct layer from the high-level safe API. Downstream Rust projects may want only the raw bindings for advanced use cases (custom unsafe wrappers, FFI code generators).
- The Rust ecosystem convention (`*-sys` crates) provides a well-understood separation: `-sys` crates handle C linkage and raw types; higher-level crates provide safe wrappers.

Usecases:
- `tvm-ffi-sys` only: Advanced users building custom unsafe wrappers or FFI code generators that need direct access to C ABI types without the high-level API overhead.
- `tvm-ffi` (full): Application developers writing Rust code that interacts with TVM FFI objects, functions, and modules through safe abstractions.
- `tvm-ffi-macros` (indirect): Used via `tvm-ffi` re-exports; end users rarely depend on it directly.

Design Decisions:
- **Three-crate workspace**: `tvm-ffi-sys` (raw C), `tvm-ffi-macros` (proc macros), `tvm-ffi` (high-level).
- **`tvm-ffi-sys`** contains: `#[repr(C)]` struct definitions (`TVMFFIObject`, `TVMFFIAny`, etc.), `extern "C"` function declarations, type index enum, and `build.rs` that invokes `tvm-ffi-config` for library discovery.
- **`tvm-ffi-macros`** contains: `#[derive(Object)]` and `#[derive(ObjectRef)]` proc macros.
- **`tvm-ffi`** depends on both and re-exports everything. Application code only needs `tvm-ffi` in their `Cargo.toml`.

## Implementation Notes
- `tvm-ffi-sys/build.rs` calls `tvm-ffi-config --libdir` to find `libtvm_ffi.so` and emits `cargo:rustc-link-search` directives.
- `tvm-ffi-macros` has no runtime dependencies; it generates token streams that reference types from `tvm-ffi-sys` and `tvm-ffi`.
- `tvm-ffi` re-exports key items from both sub-crates so users write `use tvm_ffi::*`.

### Alternative 1: Single monolithic crate
- Pros: Simpler dependency graph; `cargo add tvm-ffi` is the only step; no inter-crate version coordination.
- Cons: Impossible -- Rust requires proc-macro crates to be separate. At minimum, two crates are needed. Given the proc-macro constraint, the additional split of raw-C vs safe-API adds negligible complexity and follows ecosystem norms.

### Alternative 2: Two crates (macros + everything else)
- Pros: One fewer crate to version/publish.
- Cons: Mixes raw unsafe C bindings with safe high-level API in a single crate. Downstream projects that want only raw FFI types would pull in the entire safe API. Violates the `-sys` convention that Rust developers expect.

## Related Design Docs
- [0016-rust-bindings.md](../designs/0016-rust-bindings.md) -- Rust bindings design
