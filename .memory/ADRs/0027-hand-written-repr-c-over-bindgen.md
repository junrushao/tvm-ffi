---
adr: "0027"
title: "Hand-Written #[repr(C)] Structs Over Bindgen for Rust ABI"
status: "accepted"
date: "2025-10-01"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM FFI contributors"
informed:
  - "Rust binding users"
tags:
  - "architecture"
  - "rust"
  - "abi"
source_commits:
  - "09477ce10de566f8cf511cce7dfe56e77759f100"
source_ledgers:
  - ".memory/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md"
---

# ADR-0027: Hand-Written #[repr(C)] Structs Over Bindgen for Rust ABI

## TL;DR
- The Rust FFI bindings use manually authored `#[repr(C)]` structs to mirror the C ABI structs, rather than auto-generating them with `bindgen`.
- This gives precise control over atomic types, alignment, optional function pointers, and semantic annotations that bindgen cannot produce correctly.

## Status
accepted

## Context
The Rust bindings for TVM FFI need `#[repr(C)]` structs that exactly match the layout of `TVMFFIAny`, `TVMFFIObject`, `TVMFFIFunctionCell`, `TVMFFIErrorCell`, `TVMFFIByteArray`, `TVMFFIShapeCell`, DLPack types, and all type info structs defined in `include/tvm/ffi/c_api.h`. The question is whether to auto-generate these with `bindgen` (which parses C headers) or write them by hand.

The C ABI surface is intentionally small (approximately 20 struct definitions and 30 function declarations) and designed to be stable across major versions. The structs contain fields that require special Rust treatment: `combined_ref_count` must be `AtomicU64` (not `u64`), `deleter` must be `Option<extern "C" fn(...)>` (Rust's niche optimization for nullable function pointers), and union fields need careful typing.

## Decision Drivers
- Precise control over atomic types: `TVMFFIObject.combined_ref_count` must be `AtomicU64` for the native ref-counting implementation, not a plain `u64`.
- Nullable function pointers: Rust `Option<extern "C" fn(...)>` provides null-safety and niche optimization; `bindgen` would generate raw function pointers.
- Small, stable ABI surface: The C ABI has approximately 20 struct types and changes rarely. The maintenance burden of manual mirroring is low.
- Semantic annotations: Rust structs can carry doc comments, derive macros, and trait implementations that `bindgen` output would not include.
- Reproducible builds: No build-time dependency on `libclang` or system headers.

## Decision
All C ABI struct definitions are manually written as `#[repr(C)]` structs in `rust/tvm-ffi-sys/src/c_api.rs` (core types), `rust/tvm-ffi-sys/src/dlpack.rs` (DLPack types), and `rust/tvm-ffi-sys/src/c_env_api.rs` (environment APIs). `extern "C"` function declarations are also manually written in the same files.

## Alternatives Considered
### Auto-generate with bindgen
- Pros: Automatically stays in sync with C header changes. Less manual effort for initial setup. Catches new fields/functions added to headers.
- Cons: Cannot produce `AtomicU64` for `combined_ref_count` (generates `u64` by default). Cannot produce `Option<extern "C" fn>` for nullable function pointers (generates raw pointers). Requires `libclang` at build time. Output is verbose and unidiomatic. Post-processing to fix types would negate the automation benefit. Would need to re-derive traits and add doc comments separately.

### Hybrid approach (bindgen for some, manual for others)
- Pros: Automated for simple structs, manual for special cases.
- Cons: Two sources of truth for struct layouts. Confusion about which structs are auto-generated. Build complexity from mixing approaches. The ABI is small enough that the hybrid approach adds more complexity than it saves.

## Why This Option Won
- The ABI surface is small (approximately 20 structs, 30 functions) and designed to be stable. Manual mirroring is a one-time cost with low ongoing maintenance.
- Atomic types and nullable function pointers are critical correctness requirements that `bindgen` cannot satisfy without extensive workarounds.
- Manual structs provide better ergonomics: doc comments, trait derives, and semantic naming in Rust.
- No build-time dependency on `libclang` simplifies the build chain, especially for CI and cross-compilation.

## Consequences
### Positive
- Full control over Rust-specific type choices (atomics, optionals, unions).
- Clean, documented Rust API with idiomatic naming.
- Simpler build system (no `libclang` dependency).
- Easier to review: all ABI definitions are in a few readable files.

### Negative
- When `c_api.h` adds or modifies struct fields, the Rust mirrors must be updated manually. There is no compile-time check that the Rust structs match the C structs (beyond cross-language test failures).
- Risk of silent ABI divergence if a C header change is missed.

### Risks
- **ABI divergence risk**: If `c_api.h` changes field order or adds fields, the Rust structs silently produce incorrect memory layouts. Mitigated by cross-language integration tests that exercise all struct types across the FFI boundary, and by the ABI stability guarantee (struct layouts do not change within a major version).

## Implementation Notes
- All `#[repr(C)]` structs are defined in three files: `c_api.rs` (core), `dlpack.rs` (DLPack), `c_env_api.rs` (environment).
- `TVMFFIObject.combined_ref_count` is `AtomicU64` with platform-conditional alignment padding for 32-bit targets.
- `TVMFFIAnyDataUnion` is a `#[repr(C)] #[derive(Copy, Clone)] union` with all C union members.
- Function declarations use `unsafe extern "C"` blocks.

## Validation
- `rust/tvm-ffi/tests/test_any.rs`: Tests `TVMFFIAny` layout by constructing values in Rust and passing them to C++ functions.
- `rust/tvm-ffi/tests/test_object.rs`: Tests `TVMFFIObject` layout by creating objects in Rust and verifying ref-count behavior through C++ APIs.
- `rust/tvm-ffi/tests/test_function.rs`: Tests `TVMFFIFunctionCell` layout by creating Rust callbacks callable from C++.

## Migration and Rollback
- To switch to `bindgen`: add `bindgen` as a build dependency, generate bindings from `c_api.h`, and post-process to replace `u64` with `AtomicU64` and raw function pointers with `Option<extern "C" fn(...)>`. The existing test suite validates correctness regardless of generation method.

## Related Design Docs
- [.memory/designs/0017-rust-ffi-binding-layer.md](.memory/designs/0017-rust-ffi-binding-layer.md)
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)

## Related Diagrams
- [.memory/diagrams/0014-rust-crate-architecture.md](.memory/diagrams/0014-rust-crate-architecture.md)

## Evidence Matrix
- Hand-written `#[repr(C)]` structs with `AtomicU64` -> `.memory/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md` + `09477ce` + `rust/tvm-ffi-sys/src/c_api.rs` lines 105-114
- Explicit comment "we manually write the C ABI as they are reasonably minimal" -> `09477ce` + `rust/tvm-ffi-sys/src/c_api.rs` line 19
- `Option<TVMFFIObjectDeleter>` for nullable deleter -> `09477ce` + `rust/tvm-ffi-sys/src/c_api.rs` line 111
- Ledger reflection: "The Rust crate manually mirrors C ABI structs rather than using bindgen" -> ledger Reflection section

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Add compile-time `static_assert` equivalents (e.g., `const _: () = assert!(std::mem::size_of::<TVMFFIAny>() == 16)`) to catch layout mismatches early.
- Consider a CI step that compares Rust struct sizes against C struct sizes to detect divergence.
