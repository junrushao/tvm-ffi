---
scope: "any-system"
status: "active"
last_updated_commit: "49e2ed4a169918d346fe8f96c208a4cec56cf3e8"
related_designs:
  - ".knowledge/designs/any-system.md"
related_adrs:
  - ".knowledge/ADRs/001-unified-any-and-object.md"
  - ".knowledge/ADRs/005-as-vs-cast-semantics.md"
---
# API Index: Any System

**Scope**: Type-erased value containers `Any` and `AnyView`, including access methods and hash/equality utilities.
**Design docs**: `.knowledge/designs/any-system.md`
**ADRs**: `.knowledge/ADRs/001-unified-any-and-object.md`, `.knowledge/ADRs/005-as-vs-cast-semantics.md`

## C ABI Functions
| Name | Signature | Description |
|------|-----------|-------------|
| `TVMFFIAnyViewToOwnedAny` | `int TVMFFIAnyViewToOwnedAny(const TVMFFIAny* view, TVMFFIAny* owned)` | Convert non-owning view to owned Any (materializes view-only types) |

## C++ Types
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `AnyView` | class | `TVMFFIAny data_`; `as<T>()`, `cast<T>()`, `try_cast<T>()`, `type_index()` | Non-owning 16-byte type-erased value view |
| `Any` | class | `TVMFFIAny data_`; `as<T>() const&`, `as<T>() &&`, `cast<T>() const&`, `cast<T>() &&`, `try_cast<T>()`, `reset()`, `same_as()` | Owning 16-byte type-erased value |
| `AnyHash` | struct | `size_t operator()(const AnyView&) const` | String-aware hash; SmallStr cross-repr; NaN canonicalization |
| `AnyEqual` | struct | `bool operator()(const AnyView&, const AnyView&) const` | String-aware equality; SmallStr vs Str cross-type; NaN-equal; 16-byte fast path |

## C++ Functions & Macros
| Name | Signature / Expansion | Description |
|------|----------------------|-------------|
| `AnyView::as<T>()` | `template<T> std::optional<T> as() const` | Strict type check, no conversion |
| `AnyView::cast<T>()` | `template<T> T cast() const` | Conversion-enabled, throws TypeError |
| `AnyView::try_cast<T>()` | `template<T> std::optional<T> try_cast() const` | Conversion-enabled, returns nullopt |
| `Any::as<T>() &&` | `template<T> std::optional<T> as() &&` | Rvalue strict check with move semantics |
| `Any::cast<T>() &&` | `template<T> T cast() &&` | Rvalue conversion with move fast path |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| (Python bindings consume Any/AnyView transparently through the packed calling convention; no direct Python API) | | |

## Deprecated / Renamed
| Old Name | New Name | Since Commit | Notes |
|----------|----------|-------------|-------|
| `AnyView::as<T>()` (lenient) | `AnyView::try_cast<T>()` | 37a2e7c | `as` is now strict-only |
| `Any::cast<T>()` (no rvalue) | `Any::cast<T>() &&` added | 37a2e7c | Rvalue overload added |

## Evidence
| Commit | Ledger | Key Change |
|--------|--------|------------|
| 37a2e7c | `2025-05-14-37a2e7c.md` | Split as/cast/try_cast semantics |
| 192f196 | `2025-05-29-192f196.md` | Add tvm::Any/tvm::AnyView aliases |
| a5a08b2 | `2025-06-27-a5a08b2.md` | DLDataType padding fix for AnyEqual |
| 59a837e | `2025-07-28-59a837e.md` | NaN canonicalization in structural eq/hash |
| 49e2ed4 | `2025-08-04-49e2ed4.md` | SSO: zero_padding invariant, cross-repr AnyHash/AnyEqual |
