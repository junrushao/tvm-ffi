---
adr: "0028"
title: "Native Rust Ref-Counting Over C API Calls"
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
  - "performance"
source_commits:
  - "09477ce10de566f8cf511cce7dfe56e77759f100"
source_ledgers:
  - ".memory/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md"
---

# ADR-0028: Native Rust Ref-Counting Over C API Calls

## TL;DR
- The Rust bindings reimplement `ObjectIncRef`/`ObjectDecRef` natively using `AtomicU64` operations on the `combined_ref_count` field, rather than calling the C API functions `TVMFFIObjectIncRef`/`TVMFFIObjectDecRef`.
- This eliminates FFI call overhead on every `ObjectArc` clone and drop, which is critical because ref-counting operations are the most frequent FFI-boundary operations.

## Status
accepted

## Context
Every `ObjectArc<T>` clone increments a ref count, and every `ObjectArc<T>` drop decrements it. In a typical program, these operations happen thousands to millions of times per second. The two options are:
1. Call the C API functions `TVMFFIObjectIncRef(handle)` / `TVMFFIObjectDecRef(handle)`, which involve a foreign function call per operation.
2. Directly manipulate the `combined_ref_count` atomic field in the `TVMFFIObject` header using Rust's `std::sync::atomic::AtomicU64` operations, matching the exact same protocol as the C++ implementation.

The `TVMFFIObject` header layout is ABI-frozen and well-documented. The `combined_ref_count` field is at offset 0 of the object header (strong in lower 32 bits, weak in upper 32 bits). The ref-counting protocol has three branches: fast-path single-owner deletion (`old == BOTH_ONE`), slow-path two-phase deletion (strong reaches zero with live weak refs), and non-final decrement (no-op beyond the atomic subtract).

## Decision Drivers
- **Performance**: FFI calls have non-trivial overhead (function pointer indirection, potential instruction cache miss, register save/restore). Ref-count operations are the most frequent per-object operation.
- **Inlinability**: Native Rust atomics can be `#[inline]`, allowing the compiler to optimize clone/drop sequences (e.g., eliding matching inc/dec pairs).
- **Correctness guarantee**: The ref-counting protocol is well-defined, documented in the C++ source, and the combined u64 layout is ABI-frozen.
- **Consistency with design intent**: The C ABI provides `TVMFFIObjectIncRef`/`TVMFFIObjectDecRef` for languages that cannot safely manipulate atomics on shared memory. Rust can.

## Decision
Implement `inc_ref` and `dec_ref` as native Rust functions in `object::unsafe_` that operate directly on `TVMFFIObject.combined_ref_count` using `AtomicU64::fetch_add` and `AtomicU64::fetch_sub` with the same memory ordering as the C++ implementation:
- **Increment**: `fetch_add(COMBINED_REF_COUNT_STRONG_ONE, Relaxed)` -- Relaxed is sufficient because incrementing only establishes that the caller has a valid reference (which it already must have to call inc_ref).
- **Decrement**: `fetch_sub(COMBINED_REF_COUNT_STRONG_ONE, Relaxed)` followed by conditional logic:
  - If `old == COMBINED_REF_COUNT_BOTH_ONE`: issue `fence(Acquire)`, call `deleter(Both)`. This is the fast path where no weak references exist.
  - Else if `old & MASK_U32 == STRONG_ONE` (strong count was 1): issue `fence(Acquire)`, call `deleter(Strong)`, then `fetch_sub(WEAK_ONE, Release)`, and if the weak count also reached zero, `fence(Acquire)` + `deleter(Weak)`.
  - Otherwise: no further action (non-final decrement).

## Alternatives Considered
### Call C API functions for all ref-counting
- Pros: Single source of truth for ref-counting logic. If the protocol changes in C++, the Rust side automatically picks it up. No risk of Rust-side logic diverging.
- Cons: FFI call overhead on every `ObjectArc` clone and drop. Cannot be inlined by the Rust compiler. Becomes a performance bottleneck for object-heavy workloads (function composition, container manipulation, etc.).

### Use a Rust wrapper that caches the C API function pointer
- Pros: Slightly less overhead than dynamic symbol resolution (function pointer is resolved once).
- Cons: Still a function pointer call per operation, still not inlinable. Marginal improvement over direct C API calls.

## Why This Option Won
- Ref-counting is the innermost hot loop of the object system. Every clone, every drop, every function return that produces an object incurs at least one ref-count operation. The cost difference between a native atomic operation (1-2 instructions) and an FFI call (10+ instructions, potential cache miss) is significant in aggregate.
- The protocol is well-specified and ABI-frozen. The `combined_ref_count` layout (strong lower 32, weak upper 32) and the three-branch decrement logic are documented and stable within a major version.
- Rust's `AtomicU64` provides the exact same atomic primitives as `__atomic_fetch_add`/`__atomic_fetch_sub` in C++, with the same memory ordering options (`Relaxed`, `Release`, `Acquire`).

## Consequences
### Positive
- Zero FFI overhead for ref-counting. `inc_ref` and `dec_ref` are `#[inline]` functions.
- Rust compiler can optimize clone/drop sequences (e.g., avoid inc+dec for temporaries).
- No performance penalty for object-heavy code patterns.

### Negative
- If the C++ ref-counting protocol changes, the Rust implementation must be updated in lockstep. This is a maintenance burden, not a correctness risk (because the protocol is ABI-versioned).
- Two implementations of the same logic exist (C++ `ObjectInternal::DecRef` and Rust `unsafe_::dec_ref`). Any subtle difference is a bug.

### Risks
- **Protocol divergence**: The C++ side changes the ref-counting logic (e.g., different ordering, different deleter flags) without updating Rust. Mitigated by: (a) the protocol is ABI-frozen within a major version, (b) cross-language tests verify correct ref-count behavior, (c) the Rust code has comments citing the specific C++ function it mirrors.
- **Memory ordering bug**: Using wrong ordering (e.g., `Relaxed` where `Acquire` is needed) could cause use-after-free. Mitigated by matching the exact same ordering choices as the C++ implementation, which has been validated across compilers and platforms.

## Implementation Notes
- `inc_ref`: `obj.combined_ref_count.fetch_add(1, Ordering::Relaxed)` -- note: adding 1 to the u64 increments the strong count (lower 32 bits) without affecting the weak count (upper 32 bits), because the strong count does not overflow to the weak count in practice.
- `dec_ref`: The three-branch logic in `rust/tvm-ffi/src/object.rs` lines 148-186 faithfully reproduces `ObjectInternal::DecRef` from `include/tvm/ffi/object.h`.
- The `object_deleter_for_new<T>` and `object_deleter_for_new_with_extra_items<T, U>` functions handle the `flags` parameter correctly: `Strong` flag runs `drop_in_place`, `Weak` flag runs `dealloc`, `Both` runs both in one call (fast path optimization for variable-length objects saves the extra items count before dropping).

## Validation
- `rust/tvm-ffi/tests/test_object.rs`: Tests `ObjectArc` strong_count and weak_count after clone/drop sequences.
- `rust/tvm-ffi/tests/test_any.rs`: Tests `debug_strong_count()` on `Any` values holding objects.
- `rust/tvm-ffi/tests/test_string.rs`: Tests ref-count correctness for heap-allocated strings across clone/drop.
- Cross-language tests: Rust creates objects, passes them to C++ functions, and verifies ref counts are correct after round-trip.

## Migration and Rollback
- To roll back: replace `unsafe_::inc_ref`/`dec_ref` calls with `TVMFFIObjectIncRef`/`TVMFFIObjectDecRef` C API calls. This requires adding the C function declarations to `tvm-ffi-sys` and removing the `#[inline]` native implementations. The semantic behavior is identical; only performance changes.

## Related Design Docs
- [.memory/designs/0017-rust-ffi-binding-layer.md](.memory/designs/0017-rust-ffi-binding-layer.md)
- [.memory/designs/0002-object-system-and-reference-counting.md](.memory/designs/0002-object-system-and-reference-counting.md)

## Related Diagrams
- [.memory/diagrams/0014-rust-crate-architecture.md](.memory/diagrams/0014-rust-crate-architecture.md)

## Evidence Matrix
- Native `inc_ref` with `fetch_add(1, Relaxed)` -> `.memory/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md` + `09477ce` + `rust/tvm-ffi/src/object.rs` lines 136-139
- Native `dec_ref` with three-branch protocol -> ledger + `09477ce` + `rust/tvm-ffi/src/object.rs` lines 148-186
- Ledger comment: "Rust reimplements inc_ref/dec_ref natively rather than calling the C functions, for efficiency" -> ledger line about ref-counting
- Combined ref-count constants (`COMBINED_REF_COUNT_BOTH_ONE`, etc.) -> `09477ce` + `rust/tvm-ffi-sys/src/c_api.rs` lines 98-103
- `ObjectArc::new` initializes with `COMBINED_REF_COUNT_BOTH_ONE` -> `09477ce` + `rust/tvm-ffi/src/object.rs` line 302

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Add `debug_assert!` checks for ref-count underflow in debug builds.
- Consider benchmarking Rust vs C API ref-counting to quantify the performance difference.
