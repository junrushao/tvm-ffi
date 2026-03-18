---
scope:
  - "0016-rust-bindings.md"
  - "0002-object-system.md"
---
# ADR 0013: Native Rust Atomic Ref-Counting (Bypassing C API)

**TL;DR**: Decision to implement `inc_ref`/`dec_ref` as native Rust atomic operations directly on `TVMFFIObject.combined_ref_count`, rather than calling the C API functions `TVMFFIObjectIncRef`/`TVMFFIObjectDecRef`. This trades code duplication for zero-overhead ref-counting in Rust.

## Context
- Every `ObjectArc<T>` clone and drop needs to adjust the reference count on the underlying `TVMFFIObject`.
- The C ABI provides `TVMFFIObjectIncRef` and `TVMFFIObjectDecRef` for this purpose. These are the canonical implementations used by the C++ side.
- Each call to these functions crosses the FFI boundary: Rust -> C linkage -> C++ implementation. In tight loops (e.g., building large Arrays or traversing object graphs), the per-operation overhead of the FFI call is measurable.
- The ref-count protocol uses a single `AtomicU64` (`combined_ref_count`) encoding both strong (low 32 bits) and weak (high 32 bits) counts. The decrement logic has a fast path (both strong and weak are 1 -> delete immediately) and a slow path (strong reaches 0 but weak > 0 -> two-phase deletion).
- The C++ `DecRef` implementation is ~30 lines of atomic compare-exchange logic. Replicating it in Rust means any future changes to the protocol must be synchronized between C++ and Rust.

Usecases:
- High-frequency clone/drop patterns: building `Array<ObjectRef>` in Rust, iterating over containers and extracting refs, nested function calls passing multiple `ObjectRef` arguments.
- Rust-heavy workloads where the FFI call overhead for ref-counting dominates (e.g., Rust-native IR passes).

Design Decisions:
- **Implement `unsafe_::inc_ref` and `unsafe_::dec_ref` in pure Rust** using `std::sync::atomic` operations on the `combined_ref_count` field. The implementation mirrors the C++ `IncRef`/`DecRef` logic exactly, including:
  - `inc_ref`: `fetch_add(1, Relaxed)` on combined_ref_count.
  - `dec_ref` fast path: if `old == BOTH_ONE`, call deleter with `BothMask`.
  - `dec_ref` slow path: if strong reaches 0 but weak > 0, call deleter with `Strong` flag, then decrement weak; if weak also reaches 0, call deleter with `Weak` flag.
- **The risk of divergence is accepted** because the ref-count protocol is part of the stable C ABI and is unlikely to change. If it does change, the Rust implementation must be updated simultaneously.

## Implementation Notes
- `inc_ref` is a single `fetch_add(1, Relaxed)` -- same as C++.
- `dec_ref` uses `fetch_sub(1, Release)` with an `Acquire` fence before the deleter call -- same memory ordering as C++.
- The deleter function pointer is read from `TVMFFIObject.deleter` and called via `extern "C"` FFI.
- `BOTH_ONE = 1 | (1 << 32)` -- the sentinel value meaning "exactly one strong and one weak reference."

### Alternative 1: Call C API for every ref-count operation
- Pros: Single source of truth; zero risk of Rust/C++ divergence; simpler Rust code.
- Cons: Each inc/dec crosses FFI boundary (~5-10ns overhead per call). For operations like cloning an `Array<ObjectRef>` of 1000 elements, that's 1000 unnecessary FFI calls.

### Alternative 2: Batch ref-count operations
- Pros: Amortize FFI call cost over multiple refs.
- Cons: Complex bookkeeping; does not help single-ref patterns (the common case); not compatible with Rust's Drop trait which fires per-object.

## Related Design Docs
- [0016-rust-bindings.md](../designs/0016-rust-bindings.md) -- Rust bindings design (ObjectArc, unsafe_ module)
- [0002-object-system.md](../designs/0002-object-system.md) -- Object ref-count protocol (combined_ref_count, two-phase deletion)
