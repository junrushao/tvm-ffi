---
status: "active"
confidence: "high"
---
# TypeAttr: Extensible Per-Type Attribute Columns

**TL;DR**
- `TypeAttr` provides a column-oriented per-type attribute storage system where each named attribute has its own `std::vector<Any>` indexed by `type_index` for O(1) lookup. This complements the fixed row-oriented `TVMFFITypeMetadata` struct.
- Registration uses `TypeAttrDef<Class>` (analogous to `ObjectDef<Class>`) with `.def(name, func)` for function attributes and `.attr(name, value)` for constant attributes, registered during static initialization.
- Lookup uses `TypeAttrColumn(name)[type_index]`, returning `AnyView()` (null) for unregistered types, enabling sparse storage.

## Problem Statement

### Background

The existing `TVMFFITypeMetadata` struct stores a fixed set of per-type metadata fields (creator, total_size, doc, structural_eq_hash_kind). Adding new per-type attributes (e.g., custom equality functions, serialization hints, code generation metadata) would require modifying the struct and breaking the C ABI with each addition.

### Solution

A column-oriented attribute system where named attributes are stored in separate arrays, each indexed by `type_index`. New attributes can be added without modifying any C struct. The `TypeAttrDef<T>` builder provides a type-safe registration interface, and `TypeAttrColumn` provides the read-path accessor.

### Goals

- **Goal**: Extensible per-type attribute registration without ABI changes.
- **Goal**: O(1) lookup by type index (column array indexing).
- **Goal**: Sparse storage (unregistered types return null, no wasted per-type allocation).
- **Goal**: Both function-valued and constant-valued attributes.
- **Non-goal**: Thread-safe concurrent registration (all registration happens during static init).

## Design

### Storage Model

Each named attribute occupies one "column" -- a `std::vector<Any>` stored in the `TypeTable`. The column is indexed by `type_index`. Types that do not register a value for a given attribute have a `nullptr` entry (or the vector is shorter than their type_index).

```
Column "__s_equal__":  [null, null, ..., FuncA at index 130, null, FuncB at index 145, ...]
Column "__s_hash__":   [null, null, ..., FuncC at index 130, null, FuncD at index 145, ...]
Column "test.size":    [null, null, ..., 42 at index 130, ...]
```

The column-to-index mapping is stored as `Map<String, int64_t> type_attr_name_to_column_index_` in `TypeTable`.

### C ABI Surface

Two new C API functions:

| Function | Purpose |
|---|---|
| `TVMFFITypeRegisterAttr(type_index, name, value)` | Register a typed attribute for a type. `type_index == kTVMFFINone` creates the column without inserting a value. |
| `TVMFFIGetTypeAttrColumn(name)` | Return a `const TVMFFITypeAttrColumn*` for the named column. Returns `nullptr` if the column does not exist. |

```c
struct TVMFFITypeAttrColumn {
    const TVMFFIAny* data;  // Column array, indexed by (type_index - begin_index)
    int32_t size;           // Number of elements in the data array
    int32_t begin_index;    // Starting type index of the column data
};
```

The column covers type indices in the range `[begin_index, begin_index + size)`. For a given `type_index`, the corresponding entry is `data[type_index - begin_index]` when `begin_index <= type_index < begin_index + size`; otherwise the entry is not present (treated as null).

As of commit `c85fd42` (#471), `begin_index` was added and `size` was narrowed from `int64_t` to `int32_t` (total struct size unchanged due to the new `int32_t` field filling the same 8-byte slot). The `begin_index` enables columns to store a narrowly scoped range of type indices, optimizing for space and locality when type attributes are limited to a contiguous subscope of the type index space (e.g., operator types allocated in a block). For the initial rollout, `begin_index` is always set to 0; non-zero values are planned for v1.0 to maintain backward compatibility.

The `data` pointer may change on subsequent registrations (vector reallocation), but this is safe because registration only happens during single-threaded static initialization.

### Registration: TypeAttrDef<T>

```cpp
TVM_FFI_STATIC_INIT_BLOCK() {
  TypeAttrDef<MyTypeObj>()
    .def("__s_equal__", &MyTypeObj::SEqual)   // function attribute
    .attr("my_attr", 42);                      // constant attribute
}
```

`TypeAttrDef<Class>` deduces `type_index` from `Class::RuntimeTypeIndex()` and `type_key` from `Class::_type_key`. The `.def(name, func)` method wraps the function via `ReflectionDefBase::GetMethod<Class>`, generating a fully qualified name (`type_key + "." + name`). Both `.def()` and `.attr()` convert values to `TVMFFIAny` via `AnyView(value).CopyToTVMFFIAny()` before calling the C API.

### Lookup: TypeAttrColumn

```cpp
static reflection::TypeAttrColumn custom_equal("__s_equal__");
AnyView attr = custom_equal[type_info->type_index];
if (attr != nullptr) {
    // Use custom equal function
}
```

`TypeAttrColumn` wraps `TVMFFIGetTypeAttrColumn(name)` and caches the column pointer. `operator[](int32_t type_index)` computes `offset = type_index - column_->begin_index`, performs bounds checking (`offset < 0 || offset >= column_->size`), and reinterprets the `TVMFFIAny*` data as `AnyView*` for zero-copy access at `data[offset]`.

### EnsureTypeAttrColumn

`EnsureTypeAttrColumn(name)` creates a column if it does not exist by calling `TVMFFITypeRegisterAttr(kTVMFFINone, name, nullptr)`. This is used by read-path code that needs to obtain a column pointer before any type has registered values, avoiding a null column pointer during early access.

### Key Classes, Fields and Interfaces

- **`TypeAttrDef<Class>`** (`include/tvm/ffi/reflection/registry.h`): Registration builder. Methods: `def(name, func)`, `attr(name, value)`.
- **`TypeAttrColumn`** (`include/tvm/ffi/reflection/accessor.h`): Read-path accessor. `operator[](int32_t type_index) -> AnyView`.
- **`EnsureTypeAttrColumn(name)`** (`include/tvm/ffi/reflection/registry.h`): Pre-creates a named column.
- **`TVMFFITypeAttrColumn`** (`include/tvm/ffi/c_api.h`): C struct with `data`, `size` (int32_t), and `begin_index` (int32_t) fields.
- **`TVMFFITypeRegisterAttr`** (`c_api.h`): C API for registration.
- **`TVMFFIGetTypeAttrColumn`** (`c_api.h`): C API for column lookup.
- **`TypeAttrColumnData`** (`src/ffi/object.cc`): Internal struct extending `TVMFFITypeAttrColumn`, owning `std::vector<Any> data_`.

### Contracts, Assumptions and Invariants

- **Duplicate registration guard**: Registering the same attribute for the same type_index twice throws `RuntimeError`.
- **Single-threaded registration**: All `TypeAttrDef` calls happen during static initialization.
- **Null sentinel**: `type_index == kTVMFFINone` creates the column but inserts no value.
- **Sparse access**: `TypeAttrColumn[type_index]` returns null `AnyView` for unregistered types (the offset `type_index - begin_index` is out of `[0, size)` or the slot holds `nullptr`).
- **begin_index phased rollout**: `begin_index` is always 0 in the initial release; non-zero values planned for v1.0. This ensures `int64_t`-sized platform compatibility during the transition.
- **Zero-copy read**: `TypeAttrColumn::operator[]` returns `AnyView` (non-owning view into the column's `Any` storage).

### Extension Points

- **New attribute columns**: Any code can create new attributes by calling `TypeAttrDef<T>().attr("new_attr", value)` during static init.
- **Forward-declared columns**: Use `EnsureTypeAttrColumn("name")` to guarantee the column exists before type registrations run.
- **Column enumeration**: The `type_attr_name_to_column_index_` map in TypeTable can be iterated to discover all registered attributes (not currently exposed via C API).

## Alternatives & Trade-offs

### Alternative: Keep adding fields to TVMFFITypeMetadata

- Pros: Simple, all metadata in one struct.
- Cons: Breaks the C ABI for each new field. Every downstream binding must be recompiled.

### Alternative: Per-type Map<String, Any>

- Pros: Fully dynamic, no column management.
- Cons: O(log n) lookup per access. Column arrays provide O(1) access, which matters for hot paths like structural equality dispatch.

### Alternative: Virtual method table per type

- Pros: Familiar C++ pattern, direct dispatch.
- Cons: Not accessible from C bindings, not ABI-stable across DLL boundaries.

## Related Work

### Design Docs & ADRs

- [`.knowledge/designs/0006-reflection.md`](0006-reflection.md) -- `ObjectDef<T>` pattern that `TypeAttrDef<T>` mirrors
- [`.knowledge/designs/0003-object-system.md`](0003-object-system.md) -- `TypeTable` where columns are stored
- [`.knowledge/designs/0001-c-abi.md`](0001-c-abi.md) -- New C API functions
- [`.knowledge/designs/0009-structural-equal-hash.md`](0009-structural-equal-hash.md) -- Primary consumer of TypeAttrColumn
- [`.knowledge/ADRs/0011-column-vs-row-type-metadata.md`](../ADRs/0011-column-vs-row-type-metadata.md) -- Architectural decision

### Evidence Matrix

- TypeAttr introduction + TVMFFITypeMetadata rename -> `.knowledge/commits/2025-07-22-162d6009252dd44950a9aa9b890cbbce6b8e5155.md` + `162d600`
- Custom SEqHash via TypeAttr -> `.knowledge/commits/2025-07-26-2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec.md` + `2ec11f5`
- column_index bug fix -> `.knowledge/commits/2025-07-26-2ec11f5f1ed2c2607765b2cfd589cc2adcbea2ec.md` + `2ec11f5`
- Unified custom dispatch via TypeAttrColumn -> `.knowledge/commits/2025-07-28-59a837eb4040843051706cbf5c7b71725fd65364.md` + `59a837e`
- begin_index added to TVMFFITypeAttrColumn, size narrowed to int32_t, offset-based accessor logic -> `.knowledge/commits/2026-02-22-c85fd42df6eae4ae0ec1aaa4ebb67ac859758cf5.md` + `c85fd42`
