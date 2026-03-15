---
scope:
  - ".knowledge/designs/0016-weak-reference-counting.md"
  - ".knowledge/designs/object-system.md"
  - ".knowledge/designs/memory.md"
  - ".knowledge/designs/c-abi.md"
---
# ADR-014: Split Counter Weak References with 24-Byte Object Header

**TL;DR**:
- Chose `uint32_t weak_ref_count` + `uint64_t strong_ref_count` in a 24-byte `TVMFFIObject` header, rejecting alternatives of two uint64 counters (32 bytes), single combined counter (16 bytes), or external weak reference table (no header change).
- The 24-byte design balances header size against counter capacity: weak refs are rare (uint32 suffices), strong refs are common (uint64 needed for high-throughput paths).

## Context
The TVM FFI object system needed weak reference support to enable cache-friendly patterns and break reference cycles. The core tension was between minimizing the object header size (every heap object pays this overhead) and providing sufficient counter capacity for both strong and weak references.

Usecases:
- **Cycle breaking**: Parent objects hold strong refs to children; children hold weak refs back to parents without preventing parent destruction.
- **Observation caches**: A cache holds weak refs to live objects without extending their lifetime. When an object is destroyed, the cache entry becomes expired.
- **Lazy initialization**: A factory holds weak refs to previously-created objects, reusing them if still alive.

Design Decisions:
- Use `uint32_t` for `weak_ref_count` and `uint64_t` for `strong_ref_count` in the `TVMFFIObject` header, growing it from 16 to 24 bytes.
- The strong reference implicitly holds one weak reference (`weak_ref_count=1` at creation), following the `std::shared_ptr` / Rust `Arc` convention.
- The deleter function signature changes to `void (*deleter)(TVMFFIObject*, int flags)` to support two-phase deletion (destroy vs. free).

## Alternatives

### Alternative A: Two uint64_t counters (32-byte header)
- Description: Both `strong_ref_count` and `weak_ref_count` as `uint64_t`, header grows to 32 bytes.
- Pros: Symmetric counter types; no risk of weak count overflow; simpler mental model.
- Cons: 32 bytes per object is a 100% increase from the original 16-byte header. Every heap object pays this cost regardless of whether weak refs are used. For workloads with millions of small objects (e.g., IR nodes), the extra 8 bytes per object is significant memory overhead.
- Why rejected: Weak references are expected to be rare -- most objects will never have a `WeakObjectPtr` pointing to them. Using uint64 for a counter that typically stays at 1 wastes 4 bytes per object. The 24-byte header is the sweet spot between functionality and memory efficiency.

### Alternative B: Single combined counter with bit splitting (16-byte header preserved)
- Description: Pack both counters into a single `int64_t` using bit splitting (e.g., upper 32 bits = strong, lower 32 bits = weak). Preserves the 16-byte header.
- Pros: No ABI size change; all existing code continues to work with the same header size.
- Cons: Complex bit manipulation for every ref-count operation; strong count limited to 2^32 (was previously unlimited); CAS operations on the combined value are more complex; harder to debug; the two counters are not independently addressable which complicates the `DecRef` fast path.
- Why rejected: The implementation complexity outweighs the benefit of preserving 16 bytes. The strong count would lose half its range. The `DecRef` fast path (check weak==1 before doing the slow path) becomes more expensive when both counters share a single atomic word.

### Alternative C: External weak reference table (no header change)
- Description: Maintain a global hash map from object pointer to weak ref count. No header modification.
- Pros: Zero per-object overhead when no weak refs exist; no ABI change at all.
- Cons: Every `WeakObjectPtr` construction/destruction requires a global hash map lookup (potentially contended); cache-unfriendly; requires global locking or a concurrent hash map; `lock()` promotion requires both the hash map and the object's strong count to be atomically consistent, which is very hard to implement correctly without locks.
- Why rejected: The global hash map introduces unavoidable contention and cache misses on weak ref operations. The correctness challenge of atomic weak-to-strong promotion across two independent data structures (hash map + object header) would likely require a global lock, defeating the purpose of lock-free ref counting.

## Implementation Notes
- The `TVMFFIObject` header at commit ca9c3d1 is:
  ```c
  typedef struct TVMFFIObject {
      int32_t type_index;         // offset 0, 4 bytes
      uint32_t weak_ref_count;    // offset 4, 4 bytes
      uint64_t strong_ref_count;  // offset 8, 8 bytes
      union {
          void (*deleter)(struct TVMFFIObject* self, int flags);
          int64_t __ensure_align;
      };                          // offset 16, 8 bytes
  } TVMFFIObject;                 // total: 24 bytes
  ```
- `make_object` sets `strong_ref_count=1, weak_ref_count=1` at creation.
- The C API function `TVMFFIObjectFree` was renamed to `TVMFFIObjectDecRef` and a new `TVMFFIObjectIncRef` was added, creating a symmetric Inc/Dec pair.
- All allocator deleters updated to accept and dispatch on the `TVMFFIObjectDeleterFlagBitMask` flags parameter.
- Cython bindings updated to call `TVMFFIObjectDecRef` instead of `TVMFFIObjectFree`.

## Related Design Docs
- `.knowledge/designs/0016-weak-reference-counting.md` -- Full weak RC design
- `.knowledge/designs/object-system.md` -- Object header, ObjectPtr
- `.knowledge/designs/memory.md` -- Allocator framework, deletion sequence
- `.knowledge/designs/c-abi.md` -- TVMFFIObject struct layout
