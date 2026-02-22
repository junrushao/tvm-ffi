# Container System Evolution

> Range: `8b46833..ecc7471` (2025-12-12 to 2026-02-21, 100 commits)

## Overview

The TVM-FFI container system evolved from two immutable containers (`Array<T>`,
`Map<K,V>`) into a four-container model with both immutable and mutable variants.
Two new mutable containers were introduced: `List<T>` (mutable sequence) and
`Dict<K,V>` (mutable mapping), each with full C++/Python bindings and integration
across serialization, structural equality/hash, deep copy, and repr.

## Timeline

| Date | SHA | Change |
|------|-----|--------|
| 2026-02-13 | `9513c2f` | Introduce `List<T>` as mutable sequence (#443) |
| 2026-02-18 | `5a6b211` | Refactor: extract `map_base.h`, remove `InplaceArrayBase` (#462) |
| 2026-02-19 | `c1af3b3` | Introduce mutable `Dict<K,V>` (#463) |
| 2026-02-20 | `07546c7` | Temp fix: revert `Array::operator[]` return to `const T` (#467) |
| 2026-02-21 | `7786133` | Distinct container type origins in stub generation (#469) |

Supporting commits:
- `5bc7fcd` — `Array.__contains__` support via `ffi.ArrayContains`
- `46ab644` — `Array.__bool__` and `Map.__bool__` truthiness
- `ec56178` — Negative index bounds check in `ArrayObj`
- `e54d15d` — Bounds checking for `Tensor::size()` and `Tensor::stride()`
- `438f643` — Fix perf issue in `Map.get`

## Architecture

### Container Taxonomy

```
ObjectObj
 ├── SeqBaseObj          (new shared base, 9513c2f)
 │    ├── ArrayObj       (immutable, copy-on-write)
 │    └── ListObj        (mutable, shared-reference)
 └── MapBaseObj          (extracted in 5a6b211)
      ├── MapObj         (immutable, copy-on-write)
      └── DictObj        (mutable, shared-reference)
```

### C ABI Type Indices

| Container | Type Index | Semantics | Introduced |
|-----------|-----------|-----------|------------|
| `Array<T>` | `kTVMFFIArray = 71` | Immutable (COW) | pre-existing |
| `Map<K,V>` | `kTVMFFIMap = 72` | Immutable (COW) | pre-existing |
| `List<T>` | `kTVMFFIList = 75` | Mutable (shared-ref) | `9513c2f` |
| `Dict<K,V>` | `kTVMFFIDict = 76` | Mutable (shared-ref) | `c1af3b3` |

### New C ABI Struct

`TVMFFISeqCell` was added to the stable C API (`9513c2f`):
```c
typedef struct { void* data; int64_t size; int64_t capacity; TVMFFIDeleter data_deleter; } TVMFFISeqCell;
```

### Key Headers

| Header | Purpose |
|--------|---------|
| `include/tvm/ffi/container/seq_base.h` | `SeqBaseObj` shared base for Array/List |
| `include/tvm/ffi/container/list.h` | `ListObj` + `List<T>` |
| `include/tvm/ffi/container/map_base.h` | `MapBaseObj` shared base for Map/Dict |
| `include/tvm/ffi/container/dict.h` | `DictObj` + `Dict<K,V>` |

### Python Bindings

| Python Class | C++ Class | Protocol | Module |
|-------------|-----------|----------|--------|
| `tvm_ffi.Array` | `Array<T>` | `Sequence` | `container.py` |
| `tvm_ffi.List` | `List<T>` | `MutableSequence` | `container.py` |
| `tvm_ffi.Map` | `Map<K,V>` | `Mapping` | `container.py` |
| `tvm_ffi.Dict` | `Dict<K,V>` | `MutableMapping` | `container.py` |

### Stub Generation

Commit `7786133` updated the type schema and stub generation to emit distinct
container type origins (`Array`, `List`, `Map`, `Dict`) instead of collapsing
to generic `list`/`dict`. Stubs now correctly annotate:
- `Array[T]` as `Sequence[T]`
- `List[T]` as `MutableSequence[T]`
- `Map[K,V]` as `Mapping[K,V]`
- `Dict[K,V]` as `MutableMapping[K,V]`

## Design Decisions

1. **Mutable containers use shared-reference semantics** (not COW): all handles
   to the same `List`/`Dict` see mutations immediately. This matches Python
   `list`/`dict` behavior. (Evidence: `c1af3b3`, `9513c2f`)

2. **Shared base classes** (`SeqBaseObj`, `MapBaseObj`): mutable and immutable
   variants share internal data structures and iteration logic, reducing
   duplication. `SeqBaseObj` consolidates element access, iteration, and reverse.
   `MapBaseObj` consolidates hash table operations. (Evidence: `5a6b211`, `9513c2f`)

3. **Cycle detection**: `List` and `Dict` can form reference cycles (unlike
   `Array`/`Map`). Serialization, structural hash/equal, JSON writer, and repr
   all include cycle detection for mutable containers. (Evidence: `9513c2f`, `c1af3b3`)

## Migration Notes

- Existing `Array`/`Map` code is unaffected; `List`/`Dict` are purely additive.
- `TypeTraits<std::vector<T>>` now accepts both `kTVMFFIArray` and `kTVMFFIList`
  (`9513c2f`).
- Downstream consumers of `InplaceArrayBase` CRTP must migrate (removed in `5a6b211`).

## Tests

- `tests/cpp/test_list.cc` (277 lines), `tests/cpp/test_dict.cc` (229 lines)
- `tests/python/test_container.py` (+533 lines across List and Dict)
- Serialization, structural equal/hash, deep copy, and repr tests updated
