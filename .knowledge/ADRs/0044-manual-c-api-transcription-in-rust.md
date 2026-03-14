---
scope:
  - "0001-c-abi"
  - "0022-rust-bindings"
---
# Hand-Written #[repr(C)] Structs Instead of bindgen for C ABI Types

**TL;DR**: The `tvm-ffi-sys` crate manually defines all C ABI types as `#[repr(C)]` Rust structs rather than auto-generating them with `bindgen` from `c_api.h`. This gives precise control over atomic types, union safety, and Rust-idiomatic naming at the cost of manual synchronization with the C header.

## Context

The TVM FFI C ABI defines approximately 15 struct types and 20 function declarations in `include/tvm/ffi/c_api.h`. The `tvm-ffi-sys` crate needs Rust definitions of these types that are binary-compatible. Two approaches exist: use `bindgen` to auto-generate bindings, or hand-write `#[repr(C)]` structs.

The C ABI is deliberately small and stable (changes are ABI-breaking and versioned). The types include atomic fields (`std::atomic<uint64_t>` in `TVMFFIObject`), unions (`TVMFFIAnyDataUnion`), and function pointers with specific calling conventions.

Usecases:
- `TVMFFIObject.combined_ref_count` must be `AtomicU64` in Rust for native ref-counting to work correctly.
- `TVMFFIAnyDataUnion` fields like `v_bytes: [u8; 8]` and `v_obj: *mut TVMFFIObject` must be precisely laid out for the small-string optimization.
- Enum values like `TVMFFITypeIndex` need to be `#[repr(i32)]` with exact discriminant values matching the C header.

Design Decisions:
- All C ABI types are in `tvm-ffi-sys/src/c_api.rs` (432 lines) and `tvm-ffi-sys/src/dlpack.rs` (124 lines).
- `TVMFFIObject.combined_ref_count` is `AtomicU64` (bindgen would generate `u64` or a platform-specific atomic wrapper).
- `TVMFFIAnyDataUnion` is a `#[repr(C)] union` with explicit field names matching the C union.
- Constants like `COMBINED_REF_COUNT_BOTH_ONE` are defined as Rust `const u64` values.
- `extern "C"` blocks declare all 16+ C API functions with Rust-side type names.
- The code carries a comment: "NOTE: we manually write the C ABI as they are reasonably minimal and we need to ensure clear control of the atomic access etc."

## Implementation Notes

The hand-written structs in `c_api.rs` directly correspond to types in `include/tvm/ffi/c_api.h`:

| C header type | Rust struct | Key difference |
|---|---|---|
| `TVMFFIObject` | `TVMFFIObject` | `combined_ref_count: AtomicU64` (C uses `std::atomic<uint64_t>`) |
| `TVMFFIAny` | `TVMFFIAny` | Derives `Copy, Clone` for by-value passing |
| `TVMFFIAnyDataUnion` (anonymous) | `TVMFFIAnyDataUnion` | Named union type |
| `TVMFFIByteArray` | `TVMFFIByteArray` | Adds helper methods `as_str()`, `from_str()` |
| `TVMFFIFunctionCell` | `TVMFFIFunctionCell` | Manual `Send + Sync` impl |
| `TVMFFITypeIndex` enum | `TVMFFITypeIndex` | `#[repr(i32)]` enum |

The `dlpack.rs` module similarly hand-writes `DLTensor`, `DLDataType`, `DLDevice`, `DLDeviceType`, `DLDataTypeCode` matching the DLPack specification.

### Alternatives Considered

**Alternative A: Use `bindgen` for automatic binding generation from `c_api.h`**
- Pros: Automatically stays in sync with C header changes. Zero manual work for new struct fields.
- Cons:
  - `bindgen` generates `u64` for `std::atomic<uint64_t>`, not `AtomicU64`. The Rust bindings need `AtomicU64` for native ref-counting ([ADR 0043](0043-native-rust-ref-counting.md)). Post-processing bindgen output to patch atomic types would be fragile.
  - Anonymous unions in C get awkward bindgen names. The hand-written `TVMFFIAnyDataUnion` with field names like `v_int64`, `v_obj`, `v_bytes` is more readable.
  - `bindgen` adds a build-time dependency on `libclang`, complicating CI and developer setup.
  - The C ABI surface is small (~15 types, ~20 functions), making manual maintenance tractable.

**Alternative B: Hybrid approach -- bindgen for functions, manual for structs**
- Pros: Gets function signatures automatically.
- Cons: Two sources of truth for the same header. Struct types referenced in function signatures would still need manual definitions for the atomic/union cases.

### Consequences

- **Correctness**: Binary layout is manually verified to match C. The test suite exercises cross-language round-trips (Rust creates objects consumed by C++ and vice versa).
- **Maintenance risk**: When the C ABI adds new types or modifies existing ones, `c_api.rs` must be updated manually. This is mitigated by the C ABI's stability promise (changes are versioned and infrequent).
- **Developer experience**: New Rust contributors need to understand that `c_api.rs` is a manual mirror of `c_api.h`, not auto-generated.
- **Build simplicity**: No `libclang` dependency in the build chain. The crate compiles with just `rustc`.
- **Rollback**: Switching to `bindgen` would require adding the dependency, creating a `build.rs` that invokes bindgen with appropriate configuration, and patching the output for atomic types.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md) -- C ABI types that are manually transcribed
- [`.knowledge/designs/0022-rust-bindings.md`](../designs/0022-rust-bindings.md) -- Three-crate workspace architecture
- [`.knowledge/ADRs/0043-native-rust-ref-counting.md`](0043-native-rust-ref-counting.md) -- Depends on `AtomicU64` in `TVMFFIObject`
- Commit: `.knowledge/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md`
