---
scope:
  - "0019-rust-bindings"
  - "0001-c-abi-layer"
---
# Manual C ABI Bindings in Rust (No bindgen)

**TL;DR**
- The Rust `tvm-ffi-sys` crate hand-writes all `#[repr(C)]` struct definitions and `extern "C"` function declarations rather than using `bindgen` to auto-generate them from `c_api.h`.
- This decision enables precise control over atomic types (`AtomicU64` for `combined_ref_count`), correct `#[repr(C)]` annotations, and custom helper methods on ABI types.

## Context
The TVM FFI C ABI (`c_api.h`) defines approximately 15 struct types and 20+ exported functions. A Rust binding needs corresponding Rust types. Two approaches exist:

Usecases:
- Rust code must manipulate `TVMFFIObject::combined_ref_count` as an `AtomicU64` with specific ordering guarantees (`Relaxed` for inc, `Relaxed` + `Acquire` fence for dec). This is the most critical correctness requirement.
- Rust code must construct `TVMFFIAny` values on the stack and pass them as `*const TVMFFIAny` arrays to C functions, requiring precise union layout control.
- Helper methods (e.g., `TVMFFIByteArray::from_str`, `TVMFFIAny::new`) need to be added to ABI types, which is not possible with bindgen-generated types without wrapper structs.

Design Decisions:
- **Hand-write all C ABI bindings in `tvm-ffi-sys`** with `#[repr(C)]` structs and explicit `extern "C"` blocks. The C ABI surface is small (~15 types, ~20 functions) and changes infrequently, so manual maintenance cost is low.

## Implementation Notes
- `TVMFFIObject.combined_ref_count` is declared as `AtomicU64` in Rust (bindgen would generate `u64`, losing atomicity guarantees).
- `TVMFFIAny.data_union` is a `#[repr(C)] union TVMFFIAnyDataUnion` with all variant fields explicitly declared, matching the C union exactly.
- `TVMFFIByteArray` has convenience methods (`from_str`, `as_str`) added directly to the type, impossible with bindgen without newtype wrappers.
- All enum types (`TVMFFITypeIndex`, `TVMFFIObjectDeleterFlagBitMask`, `TVMFFIBacktraceUpdateMode`) use `#[repr(i32)]` matching the C `int` underlying type.
- Key signatures:
  - `pub struct TVMFFIObject { pub combined_ref_count: AtomicU64, pub type_index: i32, pub __padding: u32, pub deleter: Option<TVMFFIObjectDeleter> }`
  - `pub struct TVMFFIAny { pub type_index: i32, pub small_str_len: u32, pub data_union: TVMFFIAnyDataUnion }`
  - `pub type TVMFFISafeCallType = unsafe extern "C" fn(*mut c_void, *const TVMFFIAny, i32, *mut TVMFFIAny) -> i32`

Evidence: `2025-10-01-09477ce1.md` (09477ce) — initial bringup comment in `c_api.rs`: "we manually write the C ABI as they are reasonably minimal and we need to ensure clear control of the atomic access etc."

## Related Design Docs
- [0019-rust-bindings.md](../designs/0019-rust-bindings.md) — Rust binding architecture
- [0001-c-abi-layer.md](../designs/0001-c-abi-layer.md) — C ABI that these bindings mirror
