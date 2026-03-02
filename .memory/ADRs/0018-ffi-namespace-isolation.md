---
adr: "0018"
title: "FFI Namespace Isolation: Remove using ffi::* from tvm Namespace"
status: "accepted"
date: "2025-09-08"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "Downstream C++ users"
tags:
  - "architecture"
  - "namespace"
  - "breaking-change"
source_commits:
  - "e9d29465ff70c5adcd5c551a69695922d8b03ea6"
source_ledgers:
  - ".memory/commits/2025-09-08-e9d29465ff70c5adcd5c551a69695922d8b03ea6.md"
---

# ADR-0018: FFI Namespace Isolation: Remove using ffi::* from tvm Namespace

## TL;DR
- All `using ffi::X` declarations are removed from FFI headers, requiring callers to use fully-qualified `tvm::ffi::X` names instead of `tvm::X` aliases.
- This establishes the invariant that FFI headers never leak symbols into `tvm::`, enabling standalone packaging of `tvm::ffi` as an independent library.

## Status
Accepted

## Context
FFI symbols like `Array`, `Map`, `String`, `make_object`, `Optional`, `Variant`, `GetRef`, `GetObjectPtr`, and `Bytes` were historically re-exported into the `tvm::` namespace via `using ffi::X` declarations in 8 FFI headers (`cast.h`, `array.h`, `map.h`, `variant.h`, `memory.h`, `optional.h`, `string.h`, `dtype.h`). This was convenient for code in the main TVM project that frequently used these types, but it created a tight coupling between the FFI namespace and the parent `tvm` namespace.

As TVM FFI is being extracted as a standalone library (`tvm-ffi`), the FFI headers must not assume the existence of a parent `tvm::` namespace or pollute it with aliases. The `using` declarations also made it unclear which types were FFI types vs. TVM-specific types.

## Decision Drivers
- **Standalone packaging**: `tvm::ffi` is being extracted as an independent package. FFI headers must not leak symbols into a parent namespace that may not exist.
- **Namespace clarity**: Callers should know whether they are using an FFI type (`tvm::ffi::Array`) or a TVM-specific type. The `using` aliases obscured this.
- **Forward compatibility**: Removing the aliases now prevents a larger migration burden as more code is written against the `tvm::X` aliases.

## Decision
Remove all `using ffi::X` declarations from FFI headers. Symbols `Array`, `Map`, `String`, `make_object`, `Optional`, `Variant`, `GetRef`, `GetObjectPtr`, `Bytes` are only accessible via `tvm::ffi::` qualified names from FFI headers.

Affected headers:
- `cast.h`: `GetRef`, `GetObjectPtr`
- `array.h`: `Array`
- `map.h`: `Map`
- `variant.h`: `Variant`
- `memory.h`: `make_object`
- `optional.h`: `Optional`
- `string.h`: `String`, `Bytes`
- `dtype.h`: stale `TODO` comment removed

## Alternatives Considered
### Keep the using declarations
- Pros: No migration needed. Convenient for existing code.
- Cons: Blocks standalone extraction. Perpetuates namespace pollution. Makes it harder to identify FFI vs. non-FFI types.

### Provide a separate compatibility header
- Pros: Non-breaking for existing code. Can be included by code that wants the aliases.
- Cons: Adds maintenance burden. Encourages continued use of the aliases instead of migrating.

### Use inline namespaces
- Pros: Types accessible from both `tvm::ffi::X` and `tvm::X` without `using` declarations.
- Cons: Inline namespaces change mangled names, which is an ABI break. Does not solve the standalone packaging problem.

## Why This Option Won
- Clean break that establishes a firm invariant: FFI headers do not pollute parent namespaces.
- The migration is mechanical: replace `tvm::X` with `tvm::ffi::X` in downstream code.
- No ongoing maintenance burden (unlike a compatibility header).

## Consequences
### Positive
- FFI can be packaged standalone without namespace conflicts.
- Clear distinction between FFI types and other types in downstream code.
- No ambiguity about where `Array`, `String`, etc. are defined.

### Negative
- Breaking change for all downstream C++ code using `tvm::Array`, `tvm::Map`, `tvm::String`, `tvm::make_object`, `tvm::Optional`, `tvm::Variant`, `tvm::GetRef`, `tvm::GetObjectPtr`, `tvm::Bytes` without the `ffi::` qualifier.

### Risks
- Large downstream codebases may have many call sites to update. Mitigated by the mechanical nature of the change (global find-and-replace).

## Implementation Notes
- Commit `e9d2946` removed `using ffi::X` from 8 headers.
- Also removed a stale `TODO(tvm-team)` comment in `dtype.h`.

## Validation
- The TVM FFI project itself builds and tests pass after the removal.
- All in-tree code was already using `tvm::ffi::` qualified names.

## Migration and Rollback
- Migration: Replace `tvm::X` with `tvm::ffi::X` for all affected symbols in downstream code.
- Rollback: Re-add the `using ffi::X` declarations to the 8 headers.

## Related Design Docs
- [.memory/designs/0004-container-library.md](.memory/designs/0004-container-library.md) -- containers whose aliases were removed.
- [.memory/designs/0002-object-system-and-reference-counting.md](.memory/designs/0002-object-system-and-reference-counting.md) -- `make_object`, `GetRef`, `GetObjectPtr`.

## Related Diagrams
None

## Evidence Matrix
- `using ffi::Array` removed from `array.h` -> `.memory/commits/2025-09-08-e9d29465ff70c5adcd5c551a69695922d8b03ea6.md` + `e9d2946` + `include/tvm/ffi/container/array.h`
- `using ffi::Map` removed from `map.h` -> `e9d2946` + `include/tvm/ffi/container/map.h`
- `using ffi::String` and `using ffi::Bytes` removed from `string.h` -> `e9d2946` + `include/tvm/ffi/string.h`
- `using ffi::make_object` removed from `memory.h` -> `e9d2946` + `include/tvm/ffi/memory.h`
- `using ffi::Optional` removed from `optional.h` -> `e9d2946` + `include/tvm/ffi/optional.h`
- `using ffi::Variant` removed from `variant.h` -> `e9d2946` + `include/tvm/ffi/container/variant.h`
- `using ffi::GetRef` and `using ffi::GetObjectPtr` removed from `cast.h` -> `e9d2946` + `include/tvm/ffi/cast.h`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Downstream projects (TVM main repo) must update all call sites from `tvm::X` to `tvm::ffi::X`.
