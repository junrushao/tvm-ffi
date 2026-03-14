---
scope:
  - "0003-object-system"
  - "0022-rust-bindings"
---
# Implement Ref-Counting Natively in Rust Instead of Calling C API

**TL;DR**: The Rust bindings implement `inc_ref`/`dec_ref` using native Rust atomics (`AtomicU64::fetch_add`/`fetch_sub`) directly on the `TVMFFIObject.combined_ref_count` field, duplicating the C++ logic rather than calling `TVMFFIObjectIncRef`/`TVMFFIObjectDecRef` through the C ABI.

## Context

Every `ObjectArc<T>` clone and drop requires a ref-count adjustment. In the C++/Python bindings, ref-counting is inlined in C++ header code. The Rust bindings face a choice: call the C API functions for every inc/dec (which requires an FFI call through the shared library's PLT/GOT on every object copy/drop), or reimplement the protocol in Rust.

Ref-counting is on the absolute hot path: every function argument conversion, every container element access, every temporary `ObjectRef` triggers inc/dec. In ML workloads that manipulate many small objects (e.g., packing/unpacking function arguments), the overhead of FFI calls per ref-count change can be significant.

The two-phase destruction protocol (strong decrement, then conditional weak decrement with different deleter flags) is well-defined by the C ABI and unlikely to change without a major ABI version bump.

Usecases:
- High-throughput function call dispatch that creates many temporary `ObjectArc` values.
- Concurrent Rust code sharing objects across threads, where atomic operation latency matters.

Design Decisions:
- `inc_ref(handle)`: `fetch_add(1, Relaxed)` -- identical to C++ `IncRef`.
- `dec_ref(handle)`: `fetch_sub(COMBINED_REF_COUNT_STRONG_ONE, Relaxed)`, then:
  - If old value was `COMBINED_REF_COUNT_BOTH_ONE`: `fence(Acquire)`, call `deleter(ptr, Both)`.
  - If old strong was 1 but weak > 1: `fence(Acquire)`, call `deleter(ptr, Strong)`, then `fetch_sub(COMBINED_REF_COUNT_WEAK_ONE, Release)`, and if weak hits zero: `fence(Acquire)`, call `deleter(ptr, Weak)`.
- The Rust implementation lives in `object::unsafe_` (a private `pub(crate)` module) so it cannot be called from outside the crate.
- `Any::clone`/`Any::drop` also inline the same check (`type_index >= kTVMFFIStaticObjectBegin`) and call `inc_ref`/`dec_ref` directly.

## Implementation Notes

The Rust atomics use the same memory ordering as C++: `Relaxed` for the common inc/dec path, `Acquire` fence before calling the deleter, `Release` for the weak decrement. This matches the C++ implementation in `include/tvm/ffi/object.h`.

The constants (`COMBINED_REF_COUNT_BOTH_ONE`, `COMBINED_REF_COUNT_STRONG_ONE`, `COMBINED_REF_COUNT_WEAK_ONE`, `COMBINED_REF_COUNT_MASK_U32`) are defined in `tvm-ffi-sys/src/c_api.rs` and must stay in sync with `include/tvm/ffi/c_api.h`.

### Alternatives Considered

**Alternative A: Call C API `TVMFFIObjectIncRef`/`TVMFFIObjectDecRef` for every ref-count change**
- Pros: Single source of truth for ref-counting logic. No risk of Rust implementation drifting.
- Cons: Every object clone/drop pays FFI call overhead (function pointer indirection through dynamic linker). This is the hot path for any non-trivial workload. The C++ bindings inline ref-counting for the same reason.

**Alternative B: Use `bindgen` to auto-generate inline functions from C headers**
- Pros: Would track header changes automatically.
- Cons: `bindgen` cannot inline C++ header code into Rust. The C ABI only exposes `TVMFFIObjectIncRef`/`TVMFFIObjectDecRef` as library functions, not inline code. Even if headers were processed, the atomic type mapping (`std::atomic<uint64_t>` to `AtomicU64`) requires manual annotation.

### Consequences

- **Performance**: Ref-counting is a direct atomic operation with no FFI call overhead, matching C++ inlined performance.
- **Maintenance risk**: If the C ABI changes the `combined_ref_count` layout or the destruction protocol (e.g., changing the bit packing of strong/weak counts), the Rust implementation in `object::unsafe_` must be updated manually. This is mitigated by the fact that such changes would be ABI-breaking and rare.
- **Correctness**: The Rust implementation must exactly match the C++ protocol. The test suite (`test_object.rs`) verifies strong/weak counts after clone/drop sequences.
- **Rollback**: Replacing with C API calls would require changing `ObjectArc::clone`/`drop`, `Any::clone`/`drop`, and `String`/`Bytes` clone/drop to call `TVMFFIObjectIncRef`/`TVMFFIObjectDecRef` instead.

## Related Design Docs

- [`.knowledge/designs/0003-object-system.md`](../designs/0003-object-system.md) -- Two-phase destruction protocol
- [`.knowledge/designs/0022-rust-bindings.md`](../designs/0022-rust-bindings.md) -- Rust bindings architecture
- [`.knowledge/ADRs/0041-combined-ref-count-atomic.md`](0041-combined-ref-count-atomic.md) -- Combined ref-count layout that Rust reimplements
- [`.knowledge/diagrams/0010-weak-rc-destruction-protocol.md`](../diagrams/0010-weak-rc-destruction-protocol.md) -- Destruction protocol diagram
- Commit: `.knowledge/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md`
