---
scope: "weak-reference-counting"
status: "active"
last_updated_commit: "ca9c3d10bb9640bffb972302f7064e49e592a526"
related_designs:
  - ".knowledge/designs/0016-weak-reference-counting.md"
  - ".knowledge/designs/object-system.md"
  - ".knowledge/designs/memory.md"
related_adrs:
  - ".knowledge/ADRs/014-weak-ref-24byte-header.md"
---
# API Index: Weak Reference Counting

**Scope**: C ABI and C++ APIs for weak reference counting, including the `WeakObjectPtr<T>` smart pointer, the two-phase deleter protocol, and the Inc/DecRef C API functions.
**Design docs**: `.knowledge/designs/0016-weak-reference-counting.md`, `.knowledge/designs/object-system.md`
**ADRs**: `.knowledge/ADRs/014-weak-ref-24byte-header.md`

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFIObjectIncRef` | `int TVMFFIObjectIncRef(TVMFFIObjectHandle obj)` | Increment strong reference count |
| `TVMFFIObjectDecRef` | `int TVMFFIObjectDecRef(TVMFFIObjectHandle obj)` | Decrement strong reference count (was `TVMFFIObjectFree`) |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `WeakObjectPtr<T>` | template class | `lock() -> ObjectPtr<T>`, `expired() -> bool`, `reset()`, `swap()`, `use_count() -> int` | Non-owning weak reference smart pointer |
| `TVMFFIObjectDeleterFlagBitMask` | enum : int32_t | `kStrong=1, kWeak=2, kBoth=3` | Bitmask for two-phase deleter dispatch |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `Object::TryPromoteWeakPtr` | `bool TryPromoteWeakPtr()` | CAS-based atomic strong increment if >0 |
| `Object::IncWeakRef` | `void IncWeakRef()` | Atomic increment weak_ref_count |
| `Object::DecWeakRef` | `void DecWeakRef()` | Atomic decrement weak_ref_count; calls deleter(Weak) at 0 |
| `Object::DecRef` | `void DecRef()` | Strong decrement with two-phase deletion protocol |
| `FObjectDeleter` | `typedef void (*FObjectDeleter)(void* obj, int flags)` | Deleter function type with flags parameter (parameter widened from `TVMFFIObject*` to `void*` in 24125d0) |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| (none) | -- | WeakObjectPtr is not currently exposed to Python |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| (none) | -- | Weak references not yet exposed in Rust bindings |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `TVMFFIObjectFree` | `TVMFFIObjectDecRef` | ca9c3d1 | Renamed to symmetric Inc/Dec pair |
| `void (*deleter)(TVMFFIObject*)` | `void (*deleter)(TVMFFIObject*, int flags)` | ca9c3d1 | Added flags parameter for two-phase deletion |
| `int32_t ref_counter` | `uint64_t strong_ref_count` + `uint32_t weak_ref_count` | ca9c3d1 | Split single counter into strong+weak |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| ca9c3d1 | `2025-09-01-ca9c3d10bb9640bffb972302f7064e49e592a526.md` | Full weak RC system: 24-byte header, WeakObjectPtr, deleter flags, CAS promotion |

