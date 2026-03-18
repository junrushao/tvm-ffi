---
scope: "containers"
---
# API Index: Containers

**Scope**: C++ and Python APIs for Array, List, Map, String, Tensor, TensorView, and related container types.
**Design docs**: [0007-containers.md](../designs/0007-containers.md)
**ADRs**: [0004-insertion-ordered-map.md](../ADRs/0004-insertion-ordered-map.md), [0012-inplace-tail-allocation-for-tensor-metadata.md](../ADRs/0012-inplace-tail-allocation-for-tensor-metadata.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `ArrayObj::operator[]` | method | `const Any& operator[](int64_t i)` | Element access; throws IndexError for `i < 0 or i >= size_` (ec56178e) |
| `ArrayObj::SetItem` | method | `void SetItem(int64_t i, Any item)` | Element mutation; throws IndexError for `i < 0 or i >= size_` (ec56178e) |
| `ffi.ArrayContains` | FFI function | `bool ArrayContains(Array, Any)` | Check element membership using AnyEqual (5bc7fcde) |
| `String::npos` | constant | `static constexpr size_t npos = static_cast<size_t>(-1)` | Sentinel for find() miss (bd12b26a) |
| `String::find` | method | `size_t find(String, pos=0)`, `size_t find(const char*, pos=0)`, `size_t find(const char*, pos, count)` | Substring search delegating to std::string_view (bd12b26a) |
| `String::substr` | method | `String substr(size_t pos=0, size_t count=npos)` | Substring extraction with bounds checking (bd12b26a) |
| `String::starts_with` | method | `bool starts_with(String)`, `bool starts_with(const char*)`, `bool starts_with(string_view)`, `bool starts_with(const char*, size_t)` | Check if string starts with prefix; returns true for empty prefix (02d1a96) |
| `String::ends_with` | method | `bool ends_with(String)`, `bool ends_with(const char*)`, `bool ends_with(string_view)`, `bool ends_with(const char*, size_t)` | Check if string ends with suffix; returns true for empty suffix (02d1a96) |
| `Tensor::size` | method | `int64_t size(int64_t idx)` | Shape access with negative indexing + bounds check; throws IndexError (e54d15d7) |
| `Tensor::stride` | method | `int64_t stride(int64_t idx)` | Stride access with negative indexing + bounds check; throws IndexError (e54d15d7) |
| `TensorView::size` | method | `int64_t size(int64_t idx)` | Shape access with bounds check; mirrors Tensor::size (e54d15d7) |
| `TensorView::stride` | method | `int64_t stride(int64_t idx)` | Stride access with bounds check; mirrors Tensor::stride (e54d15d7) |
| `SeqBaseObj` | class | `data: void*`, `size: int64`, `capacity: int64`, `data_deleter: void(*)(void*)`, `MutableBegin()`, `MutableEnd()` | Shared base for ArrayObj and ListObj; consolidates sequence data layout (9513c2f) |
| `ListObj` | class | inherits SeqBaseObj; `_type_index = kTVMFFIList (75)` | Mutable sequence container backed by contiguous Any buffer (9513c2f) |
| `List<T>` | class template | `operator[]`, `Set(i, val)`, `push_back(item)`, `pop_back()`, `insert(pos, val)`, `erase(pos)`, `resize(n)`, `reserve(n)`, `clear()` | Mutable typed list, analogous to Python list (9513c2f) |
| `ffi.GetInvalidObject` | FFI function | `ObjectRef GetInvalidObject()` | Returns global MISSING singleton; renamed from ffi.MapGetMissingObject (86c4042) |

| `DictObj` | class | inherits Object; backed by DenseMapNode | Mutable dictionary container reusing map_base.h internals (c1af3b3) |
| `Dict` | class | `__setitem__`, `__delitem__`, `__getitem__`, `__len__`, `__contains__`, `clear()`, `pop()`, `update()` | Mutable key-value container counterpart to immutable Map (c1af3b3) |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `Array.__contains__` | `def __contains__(self, value: object) -> bool` | Membership test via ffi.ArrayContains (5bc7fcde) |
| `Array.__bool__` | `def __bool__(self) -> bool` | Truthiness: empty=False, non-empty=True (46ab6448) |
| `Map.__bool__` | `def __bool__(self) -> bool` | Truthiness: empty=False, non-empty=True (46ab6448) |
| `tvm_ffi.List` | `class List(ObjectRef, MutableSequence[T])` | Mutable typed list with append, __getitem__, __setitem__, __len__, iteration (9513c2f) |
| `tvm_ffi.Dict` | `class Dict(ObjectRef)` | Mutable dict with `__setitem__`, `__delitem__`, `clear()`, `pop()`, `update()`. Keys must support AnyHash/AnyEqual (c1af3b3) |
| `tvm_ffi.core.MISSING` | `MISSING: Object` | Global singleton for missing-key sentinel; initialized at Cython import time (86c4042) |

## Rust API
N/A for this batch.
