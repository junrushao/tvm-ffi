---
adr: "0025"
title: "Make Array[T] and Map[K,V] generic with proper PEP 484 parameterization"
status: "accepted"
date: "2025-09-22"
deciders:
  - "Junru Shao"
consulted:
  - "Tianqi Chen"
informed:
  - "TVM FFI contributors"
tags:
  - "typing"
  - "containers"
  - "python"
source_commits:
  - "df58a05ec400dc5e91ac86146aedaf3a8273b7bd"
  - "54f527f4d3d1ae1b950e0fe1a52ccb7bfc6df249"
  - "90dba57cf810e7fb6a5ad8316bcf4c53c699d51c"
  - "c88110e76e7bfb1c72e8a2bf371afaf7e018aa74"
source_ledgers:
  - ".memory/commits/2025-09-22-df58a05.md"
  - ".memory/commits/2025-09-23-54f527f.md"
  - ".memory/commits/2025-09-23-90dba57.md"
  - ".memory/commits/2025-09-23-c88110e.md"
---

# ADR-0025: Make Array[T] and Map[K,V] generic with proper PEP 484 parameterization

## TL;DR
- `Array` and `Map` are now properly parameterizable as `Array[T]` and `Map[K, V]`, inheriting from `Sequence[T]` and `Mapping[K, V]` respectively, with fully typed iterators, views, and `get`/`__getitem__` signatures.
- Array slicing was changed to return `list[T]` (matching legacy TVM behavior) instead of `Array[T]`, and `Map.get` was fixed to catch `KeyError` instead of relying on `__contains__` + `__getitem__` (which could throw `IndexError` on the C++ side).

## Status
accepted

## Context
`Array` and `Map` inherited from `collections.abc.Sequence` and `collections.abc.Mapping` but were not parameterized with type variables. This meant `Array[int]` was not valid in type annotations, and type checkers treated all element access as `Any`. With the introduction of mypy checking (commit `40e9c83`) and `py.typed` PEP 561 compliance (commit `5cfd705`), proper generic typing became necessary.

Additionally, two behavioral issues existed:
1. `Array.__getitem__` with a slice returned a new `Array[T]` (introduced as a side effect of the typing changes), but legacy TVM code expected slices to return `list[T]`.
2. `Map.get(key, default)` used `key in self` (which calls `MapCount`) followed by `self[key]` (which calls `MapGetItem`). The C++ `MapGetItem` threw `IndexError` for missing keys instead of `KeyError`, causing `Map.get` to propagate the wrong exception type if the containment check and lookup raced or if the C++ side was inconsistent.

## Decision Drivers
- Type checker compatibility (mypy, Pylance) requires proper generic parameterization for containers.
- PEP 561 `py.typed` compliance means the package's type annotations must be correct.
- Legacy TVM code depends on `Array` slicing returning `list`, not `Array`.
- `Map.get` must never throw for missing keys, matching the `dict.get` contract.

## Decision
1. Make `Array` inherit from `Sequence[T]` (not `Sequence`) and `Map` inherit from `Mapping[K, V]` (not `Mapping`). Add `TypeVar` declarations `T`, `K`, `V`, `_DefaultT`.
2. Add `@overload` signatures for `__getitem__` (index vs. slice) and `Map.get` (with/without default).
3. Use `operator.index()` in `getitem_helper` for proper `SupportsIndex` handling.
4. Make `Array.__getitem__` with a slice return `list[T]` (via `getitem_helper`), preserving legacy behavior.
5. Type the view classes: `KeysView[K]`, `ValuesView[V]`, `ItemsView[K, V]` with proper `__iter__` and `__contains__`.
6. Fix `Map.get` to use `try`/`except KeyError` instead of `__contains__` + `__getitem__`.
7. Fix C++ `Map.__getitem__` to throw `KeyError` instead of `IndexError` (commit `c88110e`).
8. Add `Array.__add__` and `__radd__` for concatenation (commit `54f527f`).

## Alternatives Considered
### Keep containers unparameterized, use `# type: ignore` pragmas
- Pros: No code changes. No risk of behavioral regressions.
- Cons: Type annotations are incorrect. mypy reports errors on legitimate code. PEP 561 compliance is violated.

### Create separate `TypedArray[T]` / `TypedMap[K,V]` wrapper classes
- Pros: No changes to existing `Array`/`Map`. Backward compatible.
- Cons: Two parallel class hierarchies. Confusing API. FFI return path cannot distinguish typed from untyped.

## Why This Option Won
- Standard Python generics (`Sequence[T]`, `Mapping[K, V]`) are the idiomatic way to express parameterized containers.
- The change is backward compatible at runtime (parameterization is erased at runtime in Python).
- Fixing `Map.get` and slice behavior addresses real bugs, not just type annotations.

## Consequences
### Positive
- `Array[int]`, `Map[str, Object]` are valid type annotations recognized by mypy and Pylance.
- IDE autocompletion correctly infers element types from parameterized containers.
- `Map.get` is now safe against exception type mismatches.
- `Array.__add__` enables natural concatenation syntax.

### Negative
- The slice-returns-`list` behavior differs from Python's `list.__getitem__` (which returns `list`). This may surprise users who expect `Array[slice]` to return `Array`.
- The `cast()` calls in view iterators add minor runtime overhead.

### Risks
- Downstream code that relied on `Array.__getitem__(slice)` returning `Array` (which was only briefly the behavior between commits `df58a05` and `90dba57`) will break. Mitigation: the fix was applied in the same release cycle.

## Implementation Notes
- `getitem_helper` now uses `operator.index(idx)` for `SupportsIndex` compliance and `idx.indices(length)` for slices.
- `KeysView`, `ValuesView`, `ItemsView` use bounded `for _ in range(size)` loops instead of unbounded `while True` loops, avoiding potential infinite loops if the iterator functor misbehaves.
- `ItemsView.__contains__` is explicitly implemented to match `Mapping` protocol requirements.
- `Map.__getitem__` returns `cast(V, ...)` and `Map.get` uses `try`/`except KeyError` for correctness.

## Validation
- `tests/python/test_container.py`: Tests parameterized `Array[int]`, `Map[str, int]`, slicing returns `list`, `Map.get` with missing keys, `Array.__add__`/`__radd__`, `KeysView`/`ValuesView`/`ItemsView` iteration.
- mypy pre-commit hook validates type annotations across the codebase.

## Migration and Rollback
- No migration needed. Existing unparameterized usage (`Array`, `Map`) continues to work.
- To rollback, revert the `TypeVar` additions and restore `collections.abc.Sequence`/`Mapping` as base classes.

## Related Design Docs
- [.memory/designs/0004-container-library.md](.memory/designs/0004-container-library.md) (defines the container classes)

## Related Diagrams
- None.

## Evidence Matrix
- `Array(Sequence[T])` and `Map(Mapping[K, V])` parameterization -> `.memory/commits/2025-09-22-df58a05.md` + `df58a05` + `python/tvm_ffi/container.py`
- `@overload` signatures for `__getitem__` and `get` -> `.memory/commits/2025-09-22-df58a05.md` + `df58a05` + `python/tvm_ffi/container.py`
- Typed `KeysView[K]`, `ValuesView[V]`, `ItemsView[K, V]` -> `.memory/commits/2025-09-22-df58a05.md` + `df58a05` + `python/tvm_ffi/container.py`
- Array slice returns `list` fix -> `.memory/commits/2025-09-23-90dba57.md` + `90dba57` + `python/tvm_ffi/container.py`
- `Map.__getitem__` throws `KeyError` fix -> `.memory/commits/2025-09-23-c88110e.md` + `c88110e` + `include/tvm/ffi/container/map.h`
- `Array.__add__`/`__radd__` concatenation -> `.memory/commits/2025-09-23-54f527f.md` + `54f527f` + `python/tvm_ffi/container.py`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Consider whether `Array.__getitem__(slice)` should return `Array[T]` instead of `list[T]` in a future major version.
- Add generic typing to `Dict` (mutable map) and `List` (mutable array) containers when they are exposed to Python.
