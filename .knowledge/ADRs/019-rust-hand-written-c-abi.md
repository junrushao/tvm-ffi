---
scope:
  - ".knowledge/designs/rust-bindings.md"
  - ".knowledge/designs/c-abi.md"
---
# ADR-019: Hand-Written `#[repr(C)]` Declarations for Rust C ABI Bindings

**TL;DR**:
- The Rust `tvm-ffi-sys` crate uses hand-written `#[repr(C)]` struct declarations instead of `bindgen` to mirror the C ABI.
- This gives explicit control over atomic types (`AtomicU64` for `combined_ref_count`), memory ordering semantics, and keeps the build dependency chain minimal.

## Context
The TVM FFI defines a stable C ABI with structs like `TVMFFIObject` (24 bytes), `TVMFFIAny` (16 bytes), `TVMFFIFunctionCell`, and various reflection structs. The Rust crate needs to declare matching types to interoperate.

The C ABI surface is deliberately small and stable (around 15 struct types and 30 extern functions). The most critical struct, `TVMFFIObject`, contains an `AtomicU64 combined_ref_count` that requires specific atomic ordering semantics (Relaxed for IncRef, Relaxed+Acquire fence for DecRef) for correctness.

Usecases:
- Rust code implementing native IncRef/DecRef via the same atomic protocol as C++ (avoiding function call overhead through the dylib)
- Rust code creating objects with `ObjectArc::new` that must write a correctly-initialized `TVMFFIObject` header
- Rust `unsafe` code accessing union fields of `TVMFFIAny` with correct type interpretation

Design Decisions:
- Use hand-written `#[repr(C)]` struct declarations in `tvm-ffi-sys/src/c_api.rs` for all C ABI types, with `AtomicU64` for the combined reference count field.
- Declare all C ABI extern functions manually in an `unsafe extern "C"` block.

## Alternatives
### Use `bindgen` to auto-generate Rust bindings from C headers
- Description: Run `bindgen` on `include/tvm/ffi/c_api.h` at build time to produce Rust struct and function declarations.
- Pros: Always in sync with C headers; no manual maintenance when C ABI changes; well-established tooling.
- Cons: `bindgen` does not know about C++ `std::atomic<uint64_t>` semantics -- it would generate a plain `u64` for `combined_ref_count`, losing atomicity. Adding `AtomicU64` requires post-processing or manual patches. Requires `libclang` as a build dependency, complicating CI and developer setup. The C ABI surface is small enough that manual declarations are tractable and not error-prone.
- Why rejected: The atomic semantics of `combined_ref_count` are critical for correctness of native Rust ref-counting. The manual maintenance burden is low given the small, stable ABI surface.

### Hybrid: `bindgen` for most types + manual override for atomics
- Description: Use `bindgen` for the bulk of types but manually patch `TVMFFIObject` to use `AtomicU64`.
- Pros: Reduces manual declaration burden for non-critical types; keeps atomic correctness.
- Cons: Fragile -- requires careful coordination between generated and manual code. The TVMFFIObject patch would need to be maintained across bindgen regenerations. Adds complexity for marginal benefit (the non-atomic types are equally simple to declare manually).
- Why rejected: The additional build system complexity and fragility are not justified given the small total number of types.

## Implementation Notes
- All C ABI structs are in `rust/tvm-ffi-sys/src/c_api.rs`, with DLPack types in `dlpack.rs` and environment APIs in `c_env_api.rs`.
- The `combined_ref_count` field is declared as `pub combined_ref_count: AtomicU64`, enabling native `fetch_add`/`fetch_sub` with explicit `Ordering` parameters.
- The `TVMFFIAnyDataUnion` is declared as a `#[repr(C)] union` with all variant fields matching the C union layout.
- The note `// NOTE: we manually write the C ABI as they are reasonably minimal and we need to ensure clear control of the atomic access etc.` appears at the top of `c_api.rs` (commit 09477ce).

## Related Design Docs
- `.knowledge/designs/rust-bindings.md`
- `.knowledge/designs/c-abi.md`
- `.knowledge/ADRs/018-combined-ref-count.md`
