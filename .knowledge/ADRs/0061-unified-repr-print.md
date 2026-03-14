---
scope:
  - "0006-reflection"
  - "0014-python-bindings"
  - "0011-extra-api-tier"
---
# Unified C++ `ffi.ReprPrint` Replacing Per-Language Repr Generation

**TL;DR**: All object `__repr__` output is now produced by a single C++ function (`ffi.ReprPrint`) using DFS-based traversal with cycle/DAG handling, replacing the previous Python-side exec-based `method_repr` code generation in `c_class` and the `repr` parameter on `c_class()`/`field()`.

## Context

Before commit `b648c5d` (#454), `__repr__` for `@c_class`-decorated types was generated in Python via `_utils.method_repr`, which used `exec`-based code generation to produce a `__repr__` method iterating over reflected fields. This approach had several problems:

- **No cycle/DAG handling**: If an object graph contained cycles (e.g., mutually referencing nodes) or shared subexpressions (DAGs), the Python repr would recurse infinitely or produce redundant output.
- **Inconsistent repr across bindings**: Only Python had this repr generation; C++ and Rust had no equivalent, leading to different repr output depending on the language.
- **Duplicate repr control**: The `repr=True/False` parameter existed on both `c_class()` and `field()`, mirroring `dataclasses` conventions but separate from the C++ reflection metadata. This meant repr exclusion was a Python-only concept, invisible to other consumers.
- **Container repr inconsistency**: Built-in containers (Array, Map, List) had separate Python `__repr__` methods that did not share logic with the generic object repr.

Usecases:
- Debugging IR objects with complex DAG/cyclic structures (e.g., compiler IR with shared subexpressions and variable bindings).
- Consistent repr output in C++ test failures, Python REPL, and Rust debugging.
- Per-field repr exclusion at the C++ level (e.g., hiding internal bookkeeping fields).

Design Decisions:
- **Single C++ `ffi.ReprPrint` function**: Originally a standalone compilation unit (`src/ffi/extra/repr_print.cc`, commit `b648c5d`), now consolidated into `src/ffi/extra/dataclass.cc` (commit `6b39efb` #482) alongside deep copy, recursive hash, and recursive compare. The `ReprPrinter` class is implemented as a CRTP specialization of `ObjectGraphDFS`. Python `__object_repr__` lazily loads and delegates to it. The function is registered as `ffi.ReprPrint` in the global function table.
- **DFS with 3-state tracking**: The `ReprPrinter` class uses `NotVisited`/`InProgress`/`Done` states per object pointer. `Done` objects return cached repr (DAG handling). `InProgress` objects return `"..."` (cycle detection). This guarantees termination on arbitrary object graphs.
- **Per-field exclusion via C ABI flag**: `kTVMFFIFieldFlagBitMaskReprOff` (bit 6) in `TVMFFIFieldFlagBitMask` allows excluding fields at the C++ reflection level via `repr(false)` InfoTrait (renamed from uppercase `Repr` to lowercase `repr` in commit `6b39efb` #482). This replaces the Python-only `field(repr=False)`.
- **Custom per-type repr via `__ffi_repr__` TypeAttrColumn**: Types can register custom repr functions with signature `(const T*, const Function& fn_repr) -> String`. The `fn_repr` callback enables recursive repr of child values through the DFS printer. Built-in types (String, Bytes, Tensor, Shape, Array, List, Map) have pre-registered `__ffi_repr__` functions.
- **Removal of Python-side repr parameters**: `c_class(repr=...)` parameter removed; `field(repr=...)` parameter removed; `Field.repr` slot removed; `_utils.method_repr` function removed. The `repr` control surface is now exclusively in C++.
- **Address hiding by default**: Object addresses are hidden unless `TVM_FFI_REPR_WITH_ADDR=1` is set. This produces cleaner output for debugging while allowing address display when needed (e.g., distinguishing shared vs. distinct objects in a DAG).
- **Silent fallback**: If `ffi.ReprPrint` is unavailable (e.g., extra API tier disabled) or raises an exception, `__object_repr__` falls back to the old `ClassName(handle)` format. `__repr__` must never raise per Python convention.

**Alternatives considered**:

1. **Keep Python-side exec-based repr with cycle guard**: Could add a visited set to the Python `method_repr`. But this still leaves C++ and Rust without repr, and the dual repr-control surface (Python `field(repr=...)` vs C++ reflection flags) remains problematic.
2. **Virtual `__repr__` method on Object**: Would require vtable changes, breaking the C ABI. The TypeAttrColumn-based `__ffi_repr__` approach maintains ABI stability.
3. **Python-side wrapper around C++ field getter with cycle detection**: Possible but duplicates the DFS logic that the C++ printer already needs for structural operations (serialization, deep copy). Centralizing in C++ reuses the reflection infrastructure.

**Consequences**:
- All FFI objects now have consistent repr across language bindings (any binding can call `ffi.ReprPrint`).
- Cycle and DAG handling works transparently without per-type opt-in.
- The `ffi.ReprPrint` function now lives in `dataclass.cc` (consolidated from `repr_print.cc` in commit `6b39efb` #482).
- The `repr(false)` flag (renamed from `Repr(false)` in `6b39efb`) consumes bit 6 of `TVMFFIFieldFlagBitMask`. Bits 7-10 are now used by `CompareOff`, `HashOff`, `InitOff`, `KwOnly` respectively.
- Python `@c_class` users who previously relied on `repr=False` on `c_class()` must now use `repr(false)` on the C++ side. `Repr` -> `repr` rename is a **breaking change** for downstream C++ code.

**Rollback**: Revert `b648c5d` and `6b39efb`, restoring `_utils.method_repr`, the `repr` parameters on `c_class`/`field`, and the `Field.repr` slot. Remove `dataclass.cc` (or restore `repr_print.cc`), `kTVMFFIFieldFlagBitMaskReprOff`, the `repr` class, and the `__ffi_repr__` type attribute constant.

## Implementation Notes

- `ReprPrinter` is now a CRTP specialization of `ObjectGraphDFS` in `src/ffi/extra/dataclass.cc` (commit `6b39efb` #482). It maintains `std::unordered_map<const Object*, State>` and `std::unordered_map<const Object*, std::string>` for state tracking and repr caching. Built-in container formatting (String, Bytes, Tensor, Shape, Array, List, Map, Dict) is handled directly in `TryReprImmediate` rather than through registered hooks (simplification from the standalone `repr_print.cc`).
- Custom `__ffi_repr__` hooks on user types are still supported via `TypeAttrColumn`. When detected, the hook receives `(obj, fn_repr)` where `fn_repr` saves/restores the DFS stack for re-entrant calls.
- The `repr` InfoTrait (`include/tvm/ffi/reflection/registry.h`, renamed from uppercase `Repr` in `6b39efb`) sets `kTVMFFIFieldFlagBitMaskReprOff` on the field's flags bitmask when `repr(false)` is applied.
- Python `__object_repr__` (`object.pxi`) uses module-level `_REPR_PRINT` and `_REPR_PRINT_LOADED` globals for lazy loading, avoiding import-time dependency on the extra tier.
- Array repr uses tuple-style parentheses `(1, 2, 3)` with trailing comma for single-element `(1,)`. List repr uses brackets `[1, 2, 3]`. Map repr uses braces `{"key": "value"}`.
- Evidence: `.knowledge/commits/2026-02-18-b648c5d6b7981350c165096efbb98d00787e2900.md` + `b648c5d`
- Consolidation into dataclass.cc + Repr->repr rename: `.knowledge/commits/2026-02-27-6b39efbf381e48a8a42ab3779bc2adf587458fb3.md` + `6b39efb`

## Related Design Docs

- [`.knowledge/designs/0006-reflection.md`](../designs/0006-reflection.md) -- repr InfoTrait, kTVMFFIFieldFlagBitMaskReprOff, __ffi_repr__ type attribute
- [`.knowledge/designs/0009-structural-equal-hash.md`](../designs/0009-structural-equal-hash.md) -- Field flag bitmask system shared by structural equal/hash and repr
- [`.knowledge/designs/0011-extra-api-tier.md`](../designs/0011-extra-api-tier.md) -- dataclass.cc lives in the extra tier
- [`.knowledge/designs/0014-python-bindings.md`](../designs/0014-python-bindings.md) -- Python __repr__ delegation to ffi.ReprPrint
- [`.knowledge/designs/0027-dataclass-operations.md`](../designs/0027-dataclass-operations.md) -- Unified dataclass operations where ReprPrinter is now implemented
