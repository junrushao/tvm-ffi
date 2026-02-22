# Mutable Containers (List, Dict)

- Doc ID: 011-mutable-containers
- Status: Approved
- Last Updated: 2026-02-21
- Owners: Junru Shao, Tianqi Chen

## Overview

The TVM FFI container system originally provided only immutable (copy-on-write)
containers: `Array<T>` for sequences and `Map<K,V>` for associative maps. In
February 2026, mutable counterparts were introduced: `List<T>` as a mutable
sequence and `Dict<K,V>` as a mutable map. These new containers provide
shared-reference mutation semantics for cases where copy-on-write is unsuitable.

Both mutable and immutable variants share common base classes (`SeqBaseObj` for
sequences, `MapObj` for maps) to avoid code duplication while preserving
distinct type identities in the C ABI.

## Key Design

### Immutable vs mutable container split

The existing `Array<T>` and `Map<K,V>` are immutable: mutations create a new
object (copy-on-write). This is desirable for IR nodes and other value types
where sharing must be transparent. However, building up data structures
incrementally (e.g., populating a list in a loop, updating a cache map) requires
mutable containers with reference semantics.

Rather than adding mutation methods to `Array` and `Map` (which would break
their COW invariant), separate `List<T>` and `Dict<K,V>` types were introduced.
This preserves backward compatibility and makes mutability explicit in the type.

### SeqBaseObj: shared base for Array and List

`SeqBaseObj` (`include/tvm/ffi/container/seq_base.h`, 365 lines, `9513c2f`)
extracts the common sequence infrastructure from `ArrayObj`:

- `data_` pointer and `data_deleter_` for element storage
- `num_elem_` element count
- `capacity_` allocation capacity
- Iterator support, element access, size queries

`ArrayObj` and `ListObj` both inherit from `SeqBaseObj`. The extraction removed
approximately 300 lines of duplicated code from `array.h`.

### ListObj: mutable sequence

`ListObj` (`include/tvm/ffi/container/list.h`, 527 lines, `9513c2f`) provides
mutable sequence operations:

- `push_back`, `pop_back`, `insert`, `erase`, `clear`
- `reserve`, `resize` for capacity management
- `Set(index, value)` for element mutation
- `begin()`, `end()` mutable iterators

`List<T>` is the typed ref wrapper with `operator[]` returning `T`.

The type index `kTVMFFIList` was added to `c_api.h`.

### MapObj reorganization and Dict

Before `Dict` could be introduced, `MapObj` was extracted from `map.h` into
`map_base.h` (`5a6b211`, 1694 lines). This reorganization:

- Moved `MapObj`, `DenseMapObj`, `SmallBaseMapObj` into `map_base.h`
- Removed the now-unused `InplaceArrayBase` from `container_details.h`
- Added `clear()` helper method

`DictObj` (`include/tvm/ffi/container/dict.h`, 374 lines, `c1af3b3`) provides
mutable map operations:

- `Set(key, value)`, `Del(key)`, `Clear()`
- `PopItem()`, `Update(other)`
- Shares `MapObj` base with the immutable `Map`

`Dict<K,V>` is the typed ref wrapper. The type index `kTVMFFIDict` was added
to `c_api.h`.

### Python bindings

Both `List` and `Dict` are exposed as Python classes in `tvm_ffi.container`:

- `tvm_ffi.List` implements `MutableSequence` (`9513c2f`)
- `tvm_ffi.Dict` implements `MutableMapping` (`c1af3b3`)

Global functions for Dict mutation (`DictSetItem`, `DictDelItem`, `DictClear`,
`DictPopItem`, `DictUpdate`) are registered in `src/ffi/container.cc`.

### Cycle detection

Unlike `Array` and `Map`, mutable containers can form reference cycles (e.g.,
a `List` containing itself). The serialization system (`src/ffi/extra/serialization.cc`),
structural hash/equal (`structural_hash.cc`, `structural_equal.cc`), and JSON
writer (`json_writer.cc`) were all updated to detect and handle cycles when
processing `List` and `Dict` objects (`9513c2f`, `c1af3b3`).

### TypeSchema and stub generation

TypeSchema now emits `Array`, `List`, `Map`, `Dict` as distinct container
origins (`7786133`). Generated stubs use `Sequence`/`MutableSequence` for
`Array`/`List` and `Mapping`/`MutableMapping` for `Map`/`Dict`, preserving
the mutability distinction in Python type annotations.

A new documentation page `docs/concepts/containers.rst` (208 lines, `7786133`)
describes all container types, their mutability semantics, thread safety, and
usage guidance.

## APIs

### C++ API

```cpp
// List: mutable sequence (include/tvm/ffi/container/list.h).
template <typename T>
class List : public ObjectRef {
  void push_back(T value);
  T pop_back();
  void insert(int64_t index, T value);
  void erase(int64_t index);
  void clear();
  void Set(int64_t index, T value);
  T operator[](int64_t index) const;
  int64_t size() const;
};

// Dict: mutable map (include/tvm/ffi/container/dict.h).
template <typename K, typename V>
class Dict : public ObjectRef {
  void Set(K key, V value);
  void Del(K key);
  void Clear();
  Tuple<K, V> PopItem();
  void Update(Dict other);
  V operator[](K key) const;
  int64_t size() const;
};
```

### C ABI type indices

- `kTVMFFIList`: type index for `ListObj` (`9513c2f`)
- `kTVMFFIDict`: type index for `DictObj` (`c1af3b3`)

### Python API

```python
import tvm_ffi

# List (MutableSequence)
lst = tvm_ffi.List([1, 2, 3])
lst.append(4)
lst[0] = 10

# Dict (MutableMapping)
d = tvm_ffi.Dict({"key": "value"})
d["new_key"] = 42
del d["key"]
```

### Global functions

| Function name | Description |
|---------------|-------------|
| `ffi.ListAppend` | Append element to List |
| `ffi.ListInsert` | Insert element at index |
| `ffi.ListPop` | Remove and return element |
| `ffi.ListClear` | Clear all elements |
| `ffi.DictSetItem` | Set key-value pair |
| `ffi.DictDelItem` | Delete key |
| `ffi.DictClear` | Clear all entries |
| `ffi.DictPopItem` | Remove and return arbitrary entry |
| `ffi.DictUpdate` | Merge another dict |

## Implementation

Key files:
- `include/tvm/ffi/container/seq_base.h` -- `SeqBaseObj` shared sequence base
- `include/tvm/ffi/container/list.h` -- `ListObj`, `List<T>`
- `include/tvm/ffi/container/array.h` -- `ArrayObj` (now inherits `SeqBaseObj`)
- `include/tvm/ffi/container/map_base.h` -- `MapObj` shared map base
- `include/tvm/ffi/container/dict.h` -- `DictObj`, `Dict<K,V>`
- `include/tvm/ffi/container/map.h` -- `Map<K,V>` (now uses `map_base.h`)
- `python/tvm_ffi/container.py` -- Python `List` and `Dict` classes
- `src/ffi/container.cc` -- Global function registrations
- `docs/concepts/containers.rst` -- Container documentation

Tests:
- `tests/cpp/test_list.cc` -- C++ List tests (277 lines)
- `tests/cpp/test_dict.cc` -- C++ Dict tests (229 lines)
- `tests/cpp/extra/test_serialization.cc` -- Serialization with cycle detection (477 new lines)
- `tests/cpp/extra/test_structural_equal_hash.cc` -- Structural equal/hash with List/Dict (94 new lines)
- `tests/python/test_container.py` -- Python container tests (484 new lines)
- `tests/python/test_serialization.py` -- Python serialization tests (573 lines)

## History
- 2026-02-13: `List<T>` introduced as mutable sequence; `SeqBaseObj` extracted from `ArrayObj` (`9513c2f`)
- 2026-02-18: `MapObj` extracted into `map_base.h`; `InplaceArrayBase` removed (`5a6b211`)
- 2026-02-19: `Dict<K,V>` introduced as mutable map sharing `MapObj` base (`c1af3b3`)
- 2026-02-20: Array compact temp fix (`07546c7`)
- 2026-02-21: TypeSchema emits distinct container origins; `docs/concepts/containers.rst` added (`7786133`)

## References
- Range summary: `.repo-knowledge/ranges/2026-02-21-B1611E0-ECC7471.md`
- Related ADRs:
  - `.repo-knowledge/adr/017-mutable-vs-immutable-containers.md`
- Related design docs:
  - `.repo-knowledge/design/001-type-erased-value-system.md`
  - `.repo-knowledge/design/003-c-abi-stability.md`
  - `.repo-knowledge/design/005-structural-equal-hash.md`
  - `.repo-knowledge/design/006-serialization-system.md`
