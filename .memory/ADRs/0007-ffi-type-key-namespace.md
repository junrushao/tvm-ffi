---
adr: "0007"
title: "Migrate Built-in Object Type Keys from object.* to ffi.* Namespace"
status: "accepted"
date: "2025-06-27"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM community"
informed:
  - "FFI binding authors (Python, Rust)"
tags:
  - "architecture"
  - "naming"
  - "abi"
source_commits:
  - "f7311e495820859fba26d19010fc5bda0275293d"
source_ledgers:
  - ".memory/commits/2025-06-27-f7311e495820859fba26d19010fc5bda0275293d.md"
---

# ADR-0007: Migrate Built-in Object Type Keys from object.* to ffi.* Namespace

## TL;DR
- All built-in object type key strings are renamed from the `object.*` prefix (e.g., `"object.String"`) to the `ffi.*` prefix (e.g., `"ffi.String"`), aligning type keys with the C++ namespace (`tvm::ffi`) and the Python package name (`tvm_ffi`).
- New `StaticTypeKey` constants are added for `Object`, `Function`, `Array`, and `Map`, and inline string literals are replaced with references to `StaticTypeKey` constants where applicable.

## Status
Accepted

## Context
The `object.*` prefix for built-in type keys was an ad-hoc convention inherited from the original TVM codebase, where objects lived in `tvm::runtime`. After the migration to `tvm::ffi`, the `object.*` prefix no longer aligned with the namespace or the Python package name. This mismatch confused users and made it harder to understand which layer a type belonged to.

Type keys are used in:
1. C++ type registration (`_type_key = "object.String"` on each `*Obj` class).
2. Python type dispatch (`register_object("object.String", StringClass)`).
3. Serialized IR (type keys appear in JSON/pickle output).
4. Error messages (type mismatch errors include type key strings).

## Decision Drivers
- Naming consistency: type keys should match the C++ namespace and Python package.
- Discoverability: `ffi.*` clearly signals the FFI layer.
- Centralized management: type keys should reference `StaticTypeKey` constants, not inline string literals scattered across headers.

## Decision
Rename all built-in type keys:

| Old Key | New Key |
|---------|---------|
| `object.Object` | `ffi.Object` |
| `object.String` | `ffi.String` |
| `object.Bytes` | `ffi.Bytes` |
| `object.Shape` | `ffi.Shape` |
| `object.NDArray` | `ffi.NDArray` |
| `object.Error` | `ffi.Error` |
| `object.Function` | `ffi.Function` |
| `object.Array` | `ffi.Array` |
| `object.Map` | `ffi.Map` |

Add new `StaticTypeKey` constants: `kTVMFFIObject`, `kTVMFFIFunction`, `kTVMFFIArray`, `kTVMFFIMap`.

Replace inline `_type_key` string literals with `StaticTypeKey::k*` references.

## Alternatives Considered
### Keep object.* prefix
- Pros: No migration needed. No breaking change.
- Cons: Perpetuates the naming mismatch. Confuses new contributors.

### Use tvm.ffi.* prefix (fully qualified)
- Pros: Matches the full Python import path.
- Cons: Overly verbose for a type key. The `tvm.` prefix adds no information since all types are in the TVM ecosystem.

### Use no prefix (just "String", "Array", etc.)
- Pros: Shortest possible keys.
- Cons: Risk of collision with user-defined types. Loses namespace information.

## Why This Option Won
- `ffi.*` is concise and unambiguous.
- It aligns with `tvm::ffi` (C++) and `tvm_ffi` (Python).
- The migration is mechanical (find-and-replace) and caught at compile/test time.

## Consequences
### Positive
- Type keys align with the project namespace at all layers.
- `StaticTypeKey` constants centralize type key management, reducing typo risk.

### Negative
- **Breaking change** for any code matching on type key strings. Serialized data using old keys will not match.
- `ErrorObj` still uses an inline `"ffi.Error"` literal (no `StaticTypeKey` constant was added for it), which is an inconsistency.

### Risks
- Persisted type keys (in serialized IR or checkpoints) using the old `object.*` format will fail to deserialize. Mitigated by the project being in pre-1.0 development where serialization format stability is not guaranteed.

## Implementation Notes
- `StaticTypeKey` struct in `include/tvm/ffi/object.h` holds all constants.
- `_type_key` fields on `*Obj` classes reference `StaticTypeKey::k*` constants.
- Python `register_object` calls must use the new keys.
- Test assertions updated (e.g., error messages referencing `ffi.Function` instead of `object.Function`).

## Validation
- All C++ tests pass with the new type keys.
- Python tests updated to use `ffi.*` keys.
- `TypeTable` type key lookup is string-based, so the migration is fully captured by the key changes.

## Migration and Rollback
- In-tree: all type keys migrated in a single commit.
- Out-of-tree: search for `"object.String"`, `"object.Array"`, etc. and replace with `"ffi.String"`, `"ffi.Array"`, etc.
- Rollback: revert the type key strings. Not recommended.

## Related Design Docs
- [.memory/designs/0002-object-system-and-reference-counting.md](.memory/designs/0002-object-system-and-reference-counting.md)
- [.memory/designs/0005-c-abi-boundary-layer.md](.memory/designs/0005-c-abi-boundary-layer.md)

## Related Diagrams
- None

## Evidence Matrix
- Type key rename (object.* to ffi.*) -> `.memory/commits/2025-06-27-f7311e495820859fba26d19010fc5bda0275293d.md` + `f7311e` + `include/tvm/ffi/object.h`, `string.h`, `error.h`, `container/ndarray.h`, `container/shape.h`, `container/array.h`, `container/map.h`
- New StaticTypeKey constants (kTVMFFIObject, kTVMFFIFunction, kTVMFFIArray, kTVMFFIMap) -> `f7311e` + `include/tvm/ffi/object.h`
- Test assertion updates -> `f7311e` + `tests/cpp/test_function.cc`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Add a `StaticTypeKey` constant for `Error` to eliminate the remaining inline literal.
- Document the `ffi.*` convention in the developer guide.
