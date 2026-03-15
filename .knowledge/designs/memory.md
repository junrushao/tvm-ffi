---
status: "active"
confidence: "high"
---
# Memory Management Design

**TL;DR**:
- TVM FFI uses intrusive reference counting with a pluggable CRTP-based allocator (`SimpleObjAllocator`).
- `DecRef` uses a split release/acquire pattern: RELEASE-only on the fast path, ACQUIRE fence only when the counter reaches zero.
- `SimpleObjAllocator` uses `AlignedAlloc<alignof(T)>`/`AlignedFree` raw memory allocation (replaced `new StorageType` pattern in 6fb42a77).

## Problem Statement
### Background
- All heap objects need deterministic lifetime management without garbage collection.
- The ref-counting must be thread-safe with minimal overhead on the common (non-deleting) path.

### Solution
- Intrusive ref-counting in the `TVMFFIObject` header.
- `make_object<T>()` delegates to `SimpleObjAllocator` for allocation and header initialization.
- Platform-specific atomic intrinsics for ref-count manipulation.

### Goals
- Zero-overhead moves (no atomics on move construct/assign).
- Minimal overhead on the non-deleting DecRef path (release-only atomic).
- Non-goals: arena allocators (documented as future possibility).

## Design

### make_object<T>

```cpp
template<typename T, typename... Args>
ObjectPtr<T> make_object(Args&&... args);
```

Delegates to `details::SimpleObjAllocator().make_object<T>(args...)` (moved to `details` namespace in 24125d0). The `tvm::make_object<T>` alias was removed in e9d2946; use `tvm::ffi::make_object<T>` instead.

#### Allocation Sequence

1. `Handler::New()` allocates an `alignas(T)` storage struct via `new`
2. Placement `new(data) T(args...)` constructs the object
3. `ObjAllocatorBase::make_object` sets the header: `combined_ref_count=kCombinedRefCountBothOne`, `type_index=T::RuntimeTypeIndex()`, `__padding=0`, `deleter=Handler::Deleter()`
4. Returns `ObjectPtr<T>` from the owned pointer (no IncRef -- starts at 1)

#### Deletion Sequence

When `strong_ref_count` reaches 0, `Object::DecRef()` invokes the two-phase deletion protocol:

**Common path** (no external weak refs, `weak_ref_count==1`):
1. Calls `header_.deleter(&header_, kTVMFFIObjectDeleterFlagBitMaskBoth)`
2. `Deleter_` recovers the typed pointer via `ObjectUnsafe::RawObjectPtrFromUnowned<T>`
3. Calls `tptr->T::~T()` (explicit destructor) then `delete reinterpret_cast<StorageType*>(tptr)` (free memory)

**Slow path** (weak refs exist, `weak_ref_count > 1`):
1. Calls `header_.deleter(&header_, kTVMFFIObjectDeleterFlagBitMaskStrong)` -- runs destructor only
2. Decrements `weak_ref_count`; if it also reaches 0, calls `header_.deleter(&header_, kTVMFFIObjectDeleterFlagBitMaskWeak)` -- frees memory only

See `.knowledge/designs/0016-weak-reference-counting.md` for the full weak RC design.

### SimpleObjAllocator (in `details` namespace since 24125d0)

Uses `AlignedAlloc<alignof(T)>(sizeof(T))` for single objects and `AlignedAlloc<alignof(ArrayType)>(aligned_size)` for array objects (replaced `new StorageType` pattern with raw aligned allocation in 6fb42a77). `FObjectDeleter` signature: `void (*)(void*, int flags)` (parameter widened from `TVMFFIObject*` to `void*` in 24125d0).

- **Handler<T>**: `AlignedAlloc<alignof(T)>(sizeof(T))` + placement new; `AlignedFree` on deallocation
- **ArrayHandler<ArrayType, ElemType>**: `AlignedAlloc<alignof(ArrayType)>(aligned_size)` + placement new; `AlignedFree` on deallocation

#### AlignedAlloc / AlignedFree (since 6fb42a77)

```cpp
template <size_t align>
void* AlignedAlloc(size_t size);  // align must be power of 2
void AlignedFree(void* data);
```

Platform-specific implementations:
- MSVC: `_aligned_malloc` / `_aligned_free`
- POSIX: `std::malloc` when `align <= alignof(std::max_align_t)`, `posix_memalign` otherwise; `std::free` for deallocation

### Reference Counting Atomics

#### IncRef
```cpp
// GCC/Clang:
__atomic_fetch_add(&header_.strong_ref_count, 1, __ATOMIC_RELAXED);
// MSVC:
_InterlockedIncrement64(&header_.strong_ref_count);
```
RELAXED ordering: no synchronization needed for increment.

#### DecRef (optimized in d5209f0, extended for weak RC in ca9c3d1)

**GCC/Clang path**:
```cpp
// Release-only strong decrement (fast path: no acquire barrier)
if (__atomic_fetch_sub(&header_.strong_ref_count, 1, __ATOMIC_RELEASE) == 1) {
    // Strong count just hit zero. Check weak count.
    if (__atomic_load_n(&header_.weak_ref_count, __ATOMIC_RELAXED) == 1) {
        // Common fast path: no external weak refs.
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        header_.deleter(&header_, kTVMFFIObjectDeleterFlagBitMaskBoth);
    } else {
        // Slow path: weak refs exist.
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        header_.deleter(&header_, kTVMFFIObjectDeleterFlagBitMaskStrong);
        DecWeakRef();  // may trigger deleter(Weak)
    }
}
```

**MSVC path**: `_InterlockedDecrement64` for strong count; `_InterlockedDecrement` for weak count.

This split release/acquire pattern is the canonical `shared_ptr` decref optimization (used by Boost and libstdc++). It reduces memory ordering overhead on weakly-ordered architectures (e.g., ARM) for the common non-deleting path.

**Previous implementation**: Used `__ATOMIC_ACQ_REL` for every decrement, paying the acquire barrier even when the object was not being deleted.

### make_inplace_array_object

```cpp
template<typename ArrayType, typename ElemType, typename... Args>
ObjectPtr<ArrayType> make_inplace_array_object(size_t num_elems, Args&&... args);
```

Allocates contiguous block sized for `sizeof(ArrayType) + num_elems * sizeof(ElemType)`, with alignment constraints verified at compile time.

### ObjAllocatorBase (CRTP)

```cpp
template<typename Derived>
class ObjAllocatorBase {
    template<typename T, typename... Args>
    ObjectPtr<T> make_object(Args&&...);

    template<typename ArrayType, typename ElemType, typename... Args>
    ObjectPtr<ArrayType> make_inplace_array(size_t num_elems, Args&&...);
};
```

### Key Classes, Fields and Interfaces

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `make_object<T>(args...)` | `template<T, Args...> ObjectPtr<T>` | Primary allocation function |
| `make_inplace_array_object<A,E>(n, args...)` | `template<A,E,Args...> ObjectPtr<A>` | Variable-length array allocation |
| `Object::IncRef()` | `void IncRef()` | RELAXED atomic increment |
| `Object::DecRef()` | `void DecRef()` | RELEASE strong decrement + ACQUIRE fence + two-phase deletion on zero |
| `Object::IncWeakRef()` | `void IncWeakRef()` | RELAXED atomic increment of weak_ref_count |
| `Object::DecWeakRef()` | `void DecWeakRef()` | RELEASE weak decrement + deleter(Weak) on zero |
| `Object::use_count()` | `int32_t use_count() const` | RELAXED atomic load of strong_ref_count |

### Contracts, Assumptions and Invariants
- **strong_ref_count == 1, weak_ref_count == 1 at creation**: `make_object` initializes both counters to 1; the strong reference implicitly holds one weak reference.
- **Non-virtual destruction**: Deleter calls explicit `T::~T()`, not virtual destructor. Deleter receives `TVMFFIObjectDeleterFlagBitMask` flags for two-phase deletion.
- **Two-phase deletion**: Object destruction (strong=0) and memory deallocation (weak=0) are separate phases. The common path (no weak refs) executes both in a single deleter call.
- **Release-before-acquire ordering**: On the deletion path, `ACQUIRE` fence after the counter reaches zero ensures all prior writes from threads that released references are visible before the deleter runs.
- **alignas(T) storage**: Allocation uses properly aligned storage structs, not deprecated `std::aligned_storage`.

### Extension Points
- Custom allocators: inherit from `ObjAllocatorBase<Derived>` and provide `Handler<T>` / `ArrayHandler<A,E>`.
- Arena allocator with `deleter = nullptr` (arena owns memory) is a documented future possibility.

### Usage Examples

#### Standard allocation and ref-counting
**Context**: Creating and sharing an object across multiple references.
```cpp
auto ptr1 = make_object<MyObj>(42);        // strong_ref_count == 1, weak_ref_count == 1
ObjectPtr<MyObj> ptr2 = ptr1;              // strong_ref_count == 2 (IncRef: RELAXED)
{
    ObjectPtr<MyObj> ptr3 = std::move(ptr2);  // strong_ref_count == 2 (no atomics)
}                                             // strong_ref_count == 1 (DecRef: RELEASE only)
// ptr1 goes out of scope: strong_ref_count == 0 -> ACQUIRE fence -> deleter(Both)
```

### Evolution Timeline
| Version | Commit | Change | Motivation |
|---------|--------|--------|------------|
| v1 | 7d34eb8 | Initial: `std::aligned_storage`, `ACQ_REL` DecRef, `details::Atomic*` helpers | Establish allocation and ref-counting |
| v2 | d5209f0 | Split release/acquire DecRef; inline atomics; remove `details::Atomic*` helpers | Performance on weakly-ordered architectures |
| v3 | e909486 | Replace `std::aligned_storage` with `alignas(T)` struct | Fix C++23 deprecation |
| v4 | ca9c3d1 | Weak RC: split `ref_counter` into `strong_ref_count` (u64) + `weak_ref_count` (u32); deleter gains `int flags` param; `WeakObjectPtr<T>` | Weak reference support |
| v5 | 24125d0 | `FObjectDeleter` parameter widened from `TVMFFIObject*` to `void*`; `SimpleObjAllocator`/`ObjAllocatorBase` moved to `details` namespace | Doxygen clean API surface; public/internal boundary |

## Alternatives & Trade-offs
### ACQ_REL on every DecRef
- Pros: Simpler implementation; single atomic operation
- Cons: Acquire barrier on every non-deleting decrement is wasted on weakly-ordered architectures
### Deferred reference counting (like Python's GC)
- Pros: Batches ref-count updates; reduces contention
- Cons: Non-deterministic destruction; complex implementation; incompatible with RAII patterns

## Related Work
### Design Docs & ADRs
- `.knowledge/designs/object-system.md` -- Object, ObjectPtr, ObjectRef
- `.knowledge/designs/containers.md` -- Uses `make_inplace_array_object` for Array, String, Shape
- `.knowledge/designs/0016-weak-reference-counting.md` -- Full weak RC design: WeakObjectPtr, two-phase deletion
- `.knowledge/ADRs/014-weak-ref-24byte-header.md` -- Decision: split counter 24-byte header

### Evidence Matrix
- DecRef optimization -> `2025-06-18-d5209f0.md` + commit d5209f0
- `aligned_storage` replacement -> `2025-06-17-e909486.md` + commit e909486
- `tvm::make_object` alias -> `2025-05-08-16e9f0a.md` + commit 16e9f0a
- Weak RC + two-phase deletion + deleter flags -> `2025-09-01-ca9c3d1.md` + commit ca9c3d1
