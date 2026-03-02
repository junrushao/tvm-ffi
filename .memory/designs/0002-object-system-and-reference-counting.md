---
design: "0002"
title: "Object System and Reference Counting"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-05-06"
last_updated: "2025-10-01"
scope:
  - "ffi/object"
  - "ffi/memory"
  - "ffi/c_api"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
  - "d5209f0ce34d1f7c20c6cdc10cbc8445facb85e5"
  - "837800e772d8c1dfa3a00a9f23f096487c96bd37"
  - "f7311e495820859fba26d19010fc5bda0275293d"
  - "da47623098927c5b7e6380b1481b4002facdd6cd"
  - "ca9c3d10bb9640bffb972302f7064e49e592a526"
  - "472e10c4086e91fb788ffe1f0eee10df4bcf5db2"
  - "4ffbc88b60f659a74619035e699986792c071e8d"
  - "e9d29465ff70c5adcd5c551a69695922d8b03ea6"
  - "13436f01111bc4218feb440a29a2e421bc148cc4"
  - "43d13e86ee24d1558f929e3b0faa3182ca1af872"
  - "6fb42a77b1a4087e74918383e54cdecd88e50f54"
  - "ffa2dbf8bc18edb3114f18f619da08c4e3289de6"
source_ledgers:
  - ".memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md"
  - ".memory/commits/2025-06-18-d5209f0ce34d1f7c20c6cdc10cbc8445facb85e5.md"
  - ".memory/commits/2025-06-19-837800e772d8c1dfa3a00a9f23f096487c96bd37.md"
  - ".memory/commits/2025-06-27-f7311e495820859fba26d19010fc5bda0275293d.md"
  - ".memory/commits/2025-07-03-da47623098927c5b7e6380b1481b4002facdd6cd.md"
  - ".memory/commits/2025-09-01-ca9c3d10bb9640bffb972302f7064e49e592a526.md"
  - ".memory/commits/2025-09-08-472e10c4086e91fb788ffe1f0eee10df4bcf5db2.md"
  - ".memory/commits/2025-09-08-4ffbc88b60f659a74619035e699986792c071e8d.md"
  - ".memory/commits/2025-09-08-e9d29465ff70c5adcd5c551a69695922d8b03ea6.md"
  - ".memory/commits/2025-09-25-13436f01.md"
  - ".memory/commits/2025-09-26-43d13e86.md"
  - ".memory/commits/2025-09-27-6fb42a77.md"
  - ".memory/commits/2025-10-01-ffa2dbf8.md"
---

# Object System and Reference Counting

## TL;DR
- All heap-allocated values in TVM FFI derive from `Object` (C++ class wrapping `TVMFFIObject` header). Lifetime is managed via intrusive reference counting with a single `uint64_t combined_ref_count` (strong in lower 32 bits, weak in upper 32 bits) in the 24-byte header, enabling single-atomic fast-path deletion.
- The `ObjectPtr<T>` smart pointer manages strong references. `WeakObjectPtr<T>` manages weak references with `lock()` for CAS-based promotion. `ObjectRef` is the standard wrapper that users interact with. The pattern is `FooObj` (data class) + `Foo` (ref wrapper).
- Runtime type checking via `IsInstance<T>()` uses a fast-path slot-range check and a fallback ancestor-table walk, enabled by the `TypeTable` singleton that manages type registration and index allocation.

## Problem Statement
A cross-language object system needs a uniform way to allocate, reference-count, and type-check heap objects. Without a common object model, each language binding would need custom bridging code for every type, and cross-language object identity and lifetime would be impossible to manage safely.

## Context and Constraints
- Objects are shared across C++, Python, and Rust via opaque handles (`TVMFFIObjectHandle`).
- Reference counting must be atomic (objects can be shared across threads).
- Type checking must be fast: `IsInstance` is called on every typed function argument.
- The object header must be ABI-stable and visible to C code.
- The type hierarchy is open: user-defined types can be registered at runtime.

## Goals
- Provide a single base class (`Object`) for all heap-allocated FFI values.
- Enable safe, automatic lifetime management via reference counting.
- Support fast runtime type checking (`IsInstance<T>()`) for both static and dynamic types.
- Enable the `FooObj` + `Foo` (data + ref) pattern as the standard object authoring convention.
- Support `make_object<T>(args...)` for ergonomic object construction.

## Non-Goals
- Garbage collection. The system uses deterministic reference counting only.
- Thread-safe mutation of object contents (objects are immutable by convention; mutable containers like `List` are exceptions).

## Design
### Components and Responsibilities
- **`TVMFFIObject`** (C struct, `c_api.h`): The 24-byte object header. Fields: `combined_ref_count` (uint64_t, strong in lower 32 bits, weak in upper 32 bits), `type_index` (int32_t), `__padding` (uint32_t, zero-initialized), `deleter` function pointer `void(*)(void*, int flags)` (8 bytes). The header was reordered in commit `13436f0` to put ref counts first (aligned with torch `intrusive_ptr` ABI), then combined into a single u64 in commit `43d13e8` for single-atomic fast-path deletion.
- **`Object`** (C++ class, `object.h`): C++ wrapper inheriting `TVMFFIObject`. Provides `IsInstance<T>()`, `GetTypeKey()`, type registration macros.
- **`ObjectPtr<T>`** (template, `object.h`): Intrusive strong-reference smart pointer. Calls `TVMFFIObjectIncRef` on copy, `TVMFFIObjectDecRef` on destruction.
- **`WeakObjectPtr<T>`** (template, `object.h`): Weak-reference smart pointer. Increments/decrements `weak_ref_count`. Provides `lock()` for CAS-based promotion to `ObjectPtr<T>`, and `use_count()` for diagnostic strong count access. See [design 0012](.memory/designs/0012-weak-reference-counting.md) for full details.
- **`ObjectRef`** (class, `object.h`): Wrapper around `ObjectPtr<Object>`. Base class for all ref types. Provides `defined()`, `get()`, `as<T>()`, `operator==`. Type keys use the `ffi.*` namespace prefix (e.g., `"ffi.Object"`) per [ADR-0007](.memory/ADRs/0007-ffi-type-key-namespace.md).
- **`make_object<T>(args...)`** (function template, `memory.h`): Allocates a new object of type `T`, sets deleter and type_index, returns `ObjectPtr<T>`.
- **`make_inplace_array_object<ArrayType, ElemType>(n, args...)`** (function template, `memory.h`): Allocates an object with trailing inline array storage.
- **`TypeTable`** (singleton, `src/ffi/object.cc`): Manages type registration, index allocation (static + dynamic with child-slot reservation), ancestor arrays, and field/method metadata.
- **`UnsafeInit`** (tag struct, `object.h`): Sentinel struct that replaces implicit `ObjectPtr<Object>` constructors on non-nullable ObjectRef types. Constructing a ref with `UnsafeInit{}` explicitly marks the initialization as potentially null. See [design 0013](.memory/designs/0013-unsafe-init-and-objectref-null-safety.md) for full details.
- **`ObjectUnsafe::ObjectRefFromObjectPtr<T>()`** (static method, `object.h`): Centralized factory that constructs any `T : ObjectRef` from an `ObjectPtr<Object>` via the `UnsafeInit` path. All internal marshaling (`ObjectRefTypeTraitsBase`, `GetRef`, `Optional::value()`, `RValueRef`, `ObjectRef::as()`) routes through this single function, replacing scattered `T(ObjectPtr<Object>)` calls (commit `472e10c`).

### Data Contracts and Invariants
- **Header layout**: Every object starts with `TVMFFIObject` at offset 0. This is guaranteed by C++ inheritance from `Object`.
- **Refcount invariant**: An object is alive as long as the strong count (lower 32 bits of `combined_ref_count`) > 0. When strong count reaches 0, the deleter is called with `kTVMFFIObjectDeleterFlagBitMaskStrong` (or `Both` if weak count is also zero, detected via a single atomic read of `combined_ref_count`). When weak count also reaches 0, the memory is freed via `kTVMFFIObjectDeleterFlagBitMaskWeak`. The weak count starts at 1 (representing the strong reference group) and is incremented for each `WeakObjectPtr`.
- **Type index invariant**: `obj->type_index` is assigned once at construction by `make_object` and never changes. It matches the registered type's index in `TypeTable`.
- **Ancestor array invariant**: For a type at depth `d`, `type_ancestors[0..d-1]` are `const TVMFFITypeInfo**` pointers to the `TypeInfo` structs of all ancestor types in order from root to immediate parent. Changed from `int32_t*` (type index array) to direct pointers per commit `837800`, eliminating `TVMFFIGetTypeInfo` lookups during ancestor chain traversal.
- **Slot-range invariant**: If `IsInstance<T>(obj)` returns true via the fast path, then `T::_type_index <= obj->type_index < T::_type_index + T::_type_info->num_slots` (when slots are contiguously allocated). Overflow types that were allocated outside the parent's slot range fall back to ancestor-table check.

### Control Flow
1. **Object construction**: `make_object<T>(args...)` -> `AlignedAlloc` (via `details::AlignedAlloc<align>`, replacing `new StorageType` in commit `6fb42a7`) -> placement new -> set `type_index = T::RuntimeTypeIndex()` -> set `deleter` -> set `combined_ref_count = kCombinedRefCountBothOne` (strong=1, weak=1) -> set `__padding = 0` (commit `ffa2dbf`) -> return `ObjectPtr<T>`.
2. **Ref copy**: `ObjectPtr<T> copy(other)` -> `Object::IncRef()` -> `__atomic_fetch_add(&combined_ref_count, 1, RELAXED)` (plain +1 increments strong count without affecting weak count).
3. **Ref destruction**: `~ObjectPtr()` -> `Object::DecRef()` -> `__atomic_fetch_sub(&combined_ref_count, 1, RELEASE)` -> if prev strong bits == 1 (strong count reached 0), issue `ACQUIRE` fence, then check if `prev == kCombinedRefCountBothOne` (both counters are 1): if so, call `deleter(self, Both)` in a single atomic fast path; otherwise call `deleter(self, Strong)` and then `DecWeakRef()`. The combined u64 enables detecting zero-weak-refs without a separate atomic read (commit `43d13e8`). The split release/acquire pattern avoids an unnecessary acquire barrier on non-final decrements (see [ADR-0008](.memory/ADRs/0008-release-acquire-refcount-split.md)).
4. **IsInstance check**: `obj->IsInstance<T>()` -> check `type_index` in `[T::_type_index, T::_type_index + num_slots)` (fast path) -> if not, check `type_depth >= T::_type_depth` and `ancestors[T::_type_depth - 1] == T::type_info` (slow path).
5. **Type registration**: `TVM_FFI_DECLARE_OBJECT_INFO("key", Self, Parent)` macro generates a static `_type_info` structure and registers with `TypeTable` at static initialization time. Dynamic types get indices >= 128. The type key is embedded in the macro call (commit `4ffbc88`); a separate `_type_key` line is no longer needed.

### Extension Points
- **New object types**: Use `TVM_FFI_DECLARE_OBJECT_INFO("key", FooObj, ParentObj)` (or `_FINAL`/`_STATIC` variants) in the data class and `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Foo, ParentRef, FooObj)` (or `_NOTNULLABLE`) in the ref class. Mutability is auto-detected from `FooObj::_type_mutable` (commit `4ffbc88`; see [ADR-0020](.memory/ADRs/0020-object-macro-consolidation.md)).
- **Custom deleters**: Override the deleter function for objects with special cleanup (e.g., `TensorObj` that may own external DLPack memory).
- **Reflection**: `ObjectDef<T>` builder with `def_ro`/`def_rw`/`def`/`def_static` to register type metadata for cross-language access. See [design 0006](.memory/designs/0006-reflection-system.md). The legacy `VisitAttrs` pattern and `_type_has_method_visit_attrs` flag have been removed from `Object`.
- **Custom allocators**: The `details::AlignedAlloc<align>` and `details::AlignedFree` functions (commit `6fb42a7`) and `make_object` can be replaced with arena or pool allocators. The allocator switched from `new StorageType` wrappers to raw `posix_memalign`/`_aligned_malloc` for more precise allocation sizing (especially for inplace arrays), avoiding wasted memory from `StorageType` rounding.

## Alternatives Considered
### std::shared_ptr with type erasure
- Pros: Standard C++. Well-tested. Supports weak_ptr.
- Cons: Non-intrusive (separate control block allocation). Not C ABI compatible. Cannot expose header layout to foreign languages. Cannot optimize with inplace arrays.

### Manual reference counting without smart pointers
- Pros: Minimal abstraction.
- Cons: Error-prone (forgotten incref/decref). No RAII.

## Trade-offs
- **Optimized**: Object construction speed (single allocation for header + data), IsInstance performance (O(1) for slot-range types), ABI stability (fixed header layout), common-case ref counting (no weak ref overhead when none exist).
- **Sacrificed**: Cycle detection (no GC), weak reference cross-language exposure (C++ only, not Python/Rust -- Rust implements only strong `ObjectArc<T>` per [design 0017](.memory/designs/0017-rust-ffi-binding-layer.md)), thread-safe mutation (immutable by convention).

## Interfaces and Compatibility
- **C ABI**: `TVMFFIObject` struct, `TVMFFIObjectIncRef`/`TVMFFIObjectDecRef` (renamed from `TVMFFIObjectFree`), `TVMFFITypeKeyToIndex`, `TVMFFITypeIndexToInfo`.
- **C++ API**: `Object`, `ObjectRef`, `ObjectPtr<T>`, `WeakObjectPtr<T>`, `make_object<T>`, `IsInstance<T>`, `UnsafeInit`, `ObjectUnsafe::ObjectRefFromObjectPtr<T>`, `TVM_FFI_DECLARE_OBJECT_INFO[_FINAL|_STATIC]`, `TVM_FFI_DEFINE_OBJECT_REF_METHODS_[NULLABLE|NOTNULLABLE]`. Note: symbols are only accessible via `tvm::ffi::` qualified names; `using ffi::*` aliases in the `tvm::` namespace were removed in commit `e9d2946` (see [ADR-0018](.memory/ADRs/0018-ffi-namespace-isolation.md)).
- **Compatibility**: The `TVMFFIObject` header layout is ABI-frozen. Adding fields to the header or changing field offsets requires a major version bump.

## Failure Modes and Mitigations
- **Reference count overflow**: Strong count overflow (uint32_t in lower bits of `combined_ref_count`) is mitigated by practical impossibility of ~4 billion concurrent strong references. Weak count overflow (uint32_t in upper bits) is similarly impractical. An overflow of either 32-bit field would silently corrupt the other field in the combined u64.
- **Type index collision**: Two types registering the same key. Mitigated by `TypeTable` checking for duplicates and throwing on conflict.
- **Dangling ObjectPtr**: Using an `ObjectPtr` after the object is deleted. Mitigated by RAII and the convention that objects are always accessed through `ObjectRef`.
- **Cyclic references**: Objects that reference each other will never be freed. Mitigated by documentation recommending acyclic designs. No runtime cycle detection.

## Observability and Validation
- `tests/cpp/test_ffi_object.cc`: Tests type registration, IsInstance, reference counting, and the FooObj+Foo pattern.
- `tests/cpp/test_ffi_memory.cc`: Tests `make_object` and `make_inplace_array_object`.
- `TypeTable::GetRegisteredTypeKeys()` provides runtime introspection of all registered types.

## Migration and Rollout
- Foundational design from the root commit. All objects in the system derive from `Object`.

## Diagrams
- [.memory/diagrams/0002-object-type-hierarchy.md](.memory/diagrams/0002-object-type-hierarchy.md)

## Related ADRs
- [.memory/ADRs/0001-type-index-partitioning.md](.memory/ADRs/0001-type-index-partitioning.md)
- [.memory/ADRs/0002-combined-refcount-in-single-u64.md](.memory/ADRs/0002-combined-refcount-in-single-u64.md) -- re-adopted with header reorder in `13436f0`/`43d13e8`
- [.memory/ADRs/0026-tvmffiobject-header-reorder-combined-refcount.md](.memory/ADRs/0026-tvmffiobject-header-reorder-combined-refcount.md) -- header reorder + combined u64 re-introduction
- [.memory/ADRs/0007-ffi-type-key-namespace.md](.memory/ADRs/0007-ffi-type-key-namespace.md)
- [.memory/ADRs/0008-release-acquire-refcount-split.md](.memory/ADRs/0008-release-acquire-refcount-split.md)
- [.memory/ADRs/0018-ffi-namespace-isolation.md](.memory/ADRs/0018-ffi-namespace-isolation.md)
- [.memory/ADRs/0020-object-macro-consolidation.md](.memory/ADRs/0020-object-macro-consolidation.md)

## Evidence Matrix
- TVMFFIObject struct (24 bytes) -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `include/tvm/ffi/c_api.h` lines 227-278
- Object class (798 LOC) -> ledger + `7d34eb8` + `include/tvm/ffi/object.h`
- make_object and memory.h (209 LOC) -> ledger + `7d34eb8` + `include/tvm/ffi/memory.h`
- TypeTable singleton -> ledger + `7d34eb8` + `src/ffi/object.cc` lines 59-250
- IsInstance fast path (slot-range check) -> `7d34eb8` + `include/tvm/ffi/object.h` TVM_FFI_DECLARE_OBJECT_INFO macro
- Child-slot reservation -> `7d34eb8` + `src/ffi/object.cc` lines 139-170
- Combined refcount design -> ledger Reflection section
- Release/acquire split in DecRef -> `.memory/commits/2025-06-18-d5209f0ce34d1f7c20c6cdc10cbc8445facb85e5.md` + `d5209f` + `include/tvm/ffi/object.h`
- Ancestor pointer change (int32* to TypeInfo**) -> `.memory/commits/2025-06-19-837800e772d8c1dfa3a00a9f23f096487c96bd37.md` + `837800` + `include/tvm/ffi/c_api.h`
- Type key namespace (object.* to ffi.*) -> `.memory/commits/2025-06-27-f7311e495820859fba26d19010fc5bda0275293d.md` + `f7311e` + `include/tvm/ffi/object.h`
- VisitAttrs removal -> `.memory/commits/2025-07-03-da47623098927c5b7e6380b1481b4002facdd6cd.md` + `da4762` + `include/tvm/ffi/object.h`
- Weak reference counting (WeakObjectPtr, split refcounts, deleter flags) -> `.memory/commits/2025-09-01-ca9c3d10bb9640bffb972302f7064e49e592a526.md` + `ca9c3d1` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/object.h`, `include/tvm/ffi/memory.h`
- UnsafeInit tag and ObjectUnsafe::ObjectRefFromObjectPtr -> `.memory/commits/2025-09-08-472e10c4086e91fb788ffe1f0eee10df4bcf5db2.md` + `472e10c` + `include/tvm/ffi/object.h`
- Typed ObjectPtr<ContainerType> in nullable macros -> `472e10c` + `include/tvm/ffi/object.h`
- Macro consolidation (6->4 declare, 4->2 ref, TypeKey-in-macro, auto-mutable) -> `.memory/commits/2025-09-08-4ffbc88b60f659a74619035e699986792c071e8d.md` + `4ffbc88` + `include/tvm/ffi/object.h`
- Namespace isolation (using ffi::* removed from tvm::) -> `.memory/commits/2025-09-08-e9d29465ff70c5adcd5c551a69695922d8b03ea6.md` + `e9d2946` + `include/tvm/ffi/cast.h`, `include/tvm/ffi/memory.h`
- TVMFFIObject header reorder (refcounts first, aligned with torch intrusive_ptr) -> `.memory/commits/2025-09-25-13436f01.md` + `13436f0` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/object.h`
- Combined u64 refcount re-introduction (strong lower 32, weak upper 32) -> `.memory/commits/2025-09-26-43d13e86.md` + `43d13e8` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/object.h`
- Raw aligned alloc replacing StorageType wrappers -> `.memory/commits/2025-09-27-6fb42a77.md` + `6fb42a7` + `include/tvm/ffi/memory.h`
- Zero-init __padding in object allocator -> `.memory/commits/2025-10-01-ffa2dbf8.md` + `ffa2dbf` + `include/tvm/ffi/memory.h`

## Open Questions
- Should weak references be exposed in the Python/Rust bindings for caching patterns? Note: The Rust bindings (commit `09477ce`) implement only strong references (`ObjectArc<T>`). The native `dec_ref` handles the weak-ref protocol correctly (it calls `deleter(Strong)` + `dec_weak` when weak refs exist), but no `WeakObjectArc<T>` is exposed. See [design 0017](.memory/designs/0017-rust-ffi-binding-layer.md).
- Is the default child-slot reservation count (per-type) sufficient for deep type hierarchies?

## Confidence and Risk
- Confidence: high
- Residual risks: Cyclic references causing memory leaks in user code. The immutable-by-convention pattern relies on programmer discipline rather than compiler enforcement. Custom deleters must handle the `int flags` parameter correctly after the weak-rc change. The combined u64 refcount limits both strong and weak counts to 2^32 each; an overflow in either half would silently corrupt the other.
