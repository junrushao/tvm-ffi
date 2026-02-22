# Tensor and DLPack Exchange

- Doc ID: 009-tensor-and-dlpack
- Status: Approved
- Last Updated: 2025-12-29
- Owners: Tianqi Chen

## Overview

The TVM FFI Tensor abstraction provides a unified tensor representation with
DLPack-based zero-copy exchange across frameworks (PyTorch, NumPy, JAX, etc.).
This document covers the Tensor class design, DLPack exchange optimizations,
stride handling, and the ShapeView lightweight accessor.

The Tensor class was established in September 2025 by renaming the previous
`NDArray` class to align with standard ML framework naming conventions.

## Key Design

### NDArray to Tensor rename

The C++ class `NDArray`/`NDArrayObj` was renamed to `Tensor`/`TensorObj`
(`3a551d8`), and the header `ndarray.h` was renamed to `tensor.h`. The Python
class `tvm_ffi.NDArray` was renamed to `tvm_ffi.Tensor`. This ABI-breaking
rename touched approximately 30 files across the entire codebase. The
rationale was that "Tensor" is the standard name in the ML ecosystem.

### Bounds checking (January 2026)

`Tensor::size(dim)` and `Tensor::stride(dim)` (and their `TensorView`
counterparts) now throw `IndexError` for out-of-range dimension indices
(`e54d15d`). Previously these methods performed no bounds check, resulting in
undefined behavior. The fix ensures well-defined error reporting for invalid
dimension access.

### Tensor strides

Default strides construction was added (`ca95b41`): `Tensor` objects now
always have valid strides, computed from shape by default (row-major). A
`Tensor::strides()` method returning `Shape` (later `ShapeView`) was added
(`6fa40b5`).

### ShapeView

`ffi::ShapeView` (`8ca0719`) is a lightweight non-owning view over a shape
array, analogous to `std::span<const int64_t>`. It provides `data()`,
`size()`, `operator[]`, `at()`, iterators, `Product()`, and other standard
accessors. `Tensor::shape()` and `Tensor::strides()` return `ShapeView`
instead of `Shape`, eliminating redundant heap allocations on the read path.
`Shape` has an implicit conversion to `ShapeView`, so existing code that
accepts `ShapeView` works transparently with `Shape` values.

### TensorObj minimization

Internal `TensorObj` fields were reduced (`8ca0719`): `shape_data_`,
`strides_data_`, and `cached_dl_managed_tensor_versioned_` were removed.
Shape and strides data are now inlined after the object in memory via
`make_inplace_array_object`, reducing per-tensor heap allocations from 3 to
1. The `TensorObjFromNDAlloc` and `TensorObjFromDLPack` allocation functions
were updated to compute exact allocation sizes.

Convenience methods were added: `Tensor::data_ptr()`, `Tensor::ndim()`,
`Tensor::numel()`.

### DLPack exchange speed

The DLPack exchange path was optimized in several stages:

1. **Python FFI call dispatch** (`38d2cda`): A `TVMFFIPyCallManager` with
   thread-local per-type dispatch cache was introduced in
   `tvm_ffi_python_helpers.h`. The `TVMFFIPyArgSetterFactory` dispatches to
   per-type setter functions (`TVMFFIPyArgSetterXXX_`), amortizing Python
   isinstance dispatch across calls.

2. **C-level function pointers** (`f81ab9c`): A `DLPackExchangeAPI` struct
   was introduced containing `managed_tensor_allocator`,
   `managed_tensor_from_py_object_no_sync`, and
   `managed_tensor_to_py_object_no_sync` function pointers for high-speed
   DLPack exchange that bypasses Python object protocol overhead entirely.
   These are invoked from the Cython call path.

3. **Atomic DLPack cache** (`f81ab9c`): `TensorObj::ToDLPackVersioned()` was
   given atomic caching of the `DLManagedTensorVersioned*`, eliminating
   repeated allocation when the same tensor is exported multiple times.
   (This cache was later removed in `8ca0719` when TensorObj was minimized.)

4. **`__dlpack_c_exchange_api__` protocol** (`38d2cda`, `4dee97f`):
   Tensor-like objects can expose a `__dlpack_c_exchange_api__` attribute
   to enable C-level fast DLPack exchange.

5. **`__dlpack_c_exchange_api__` attribute** (`4dee97f`): The DLPack exchange
   API naming was standardized. The Python attribute was renamed to
   `__dlpack_c_exchange_api__` (with `__c_dlpack_exchange_api__` as a
   fallback). External types implementing the old attribute names must
   update.

### TensorView non-owning view (October 2025)

`ffi::TensorView` (`1ec6236`) is a non-owning view over a `DLTensor*`,
analogous to `std::string_view` for strings. It wraps a `DLTensor` pointer
without ref-counting, avoiding ownership overhead in function parameters that
only need to read tensor data.

`StaticTypeKey::kTVMFFIDLTensorPtr` was added for type dispatch.
Documentation now recommends `TensorView` for function parameters where
ownership is not needed. Existing code using `ffi::Tensor` continues to work
(additive API). All examples were updated to use `TensorView`.

### Zero-dim tensor strides (October 2025)

Zero-dimensional tensors now allow null strides (`4fefeb0`), fixing an edge
case where the strides check would fail for scalar tensors.

### Tensor.strides Cython exposure (October 2025)

`Tensor.strides` was exposed in the Python Cython bindings (`8377011`),
allowing Python code to access tensor stride information directly.

### DLPackExchangeAPI unification (October 2025)

The three separate DLPack function pointer fields (`c_dlpack_from_pyobject`,
`c_dlpack_to_pyobject`, `c_dlpack_tensor_allocator`) were replaced by a
unified `DLPackExchangeAPI` struct (`22a7894`), following DLPack proposal
#175. The struct bundles:

- `managed_tensor_allocator`
- `managed_tensor_from_py_object_no_sync`
- `managed_tensor_to_py_object_no_sync`
- `dltensor_from_py_object_no_sync`
- `current_work_stream`

External tensor types must now provide `__c_dlpack_exchange_api__` (a class
attribute, integer pointer to the struct) instead of the old three separate
attributes. The `3rdparty/dlpack` submodule was updated to v1.2.

### TVMFFIEnvTensorAlloc (October 2025)

The tensor allocator API was refactored (`f679fe5`) to align with DLPack
conventions:

- `TVMFFIEnvSetTensorAllocator` renamed to `TVMFFIEnvSetDLPackManagedTensorAllocator`
- `TVMFFIEnvGetTensorAllocator` renamed to `TVMFFIEnvGetDLPackManagedTensorAllocator`
- New `TVMFFIEnvTensorAlloc(DLTensor*, TVMFFIObjectHandle*)` C API allocates
  a `ffi::Tensor` directly, keeping metadata in `libtvm_ffi`
- `Tensor::FromDLPackAlloc` removed; replaced by `Tensor::FromEnvAlloc`

The key motivation is that keeping tensor metadata allocated inside
`libtvm_ffi` avoids the module unloading order problem (object deleter in
an already-unloaded library).

### Python tensor/object protocols (October 2025)

Several duck-typed protocols were introduced for zero-overhead FFI argument
passing:

1. **`__tvm_ffi_tensor__`** (`4bc8925`): If a class defines this method,
   it is called to retrieve the underlying `tvm_ffi.Tensor` directly,
   bypassing DLPack overhead.

2. **`__tvm_ffi_object__`** (`8873700`): Generalized from `__tvm_ffi_tensor__`
   to support any FFI object type (not just tensors). The internal cached
   attribute was renamed from `__tvm_ffi_object__` to `_tvm_ffi_cached_object`.

3. **`__dlpack_data_type__`** (`5e648f0`): Objects implementing this method
   are automatically converted to TVM FFI dtype in function calls.
   `dtype.from_dlpack_data_type()` static method was added.

4. **`__dlpack_device__`** (`0f8bf9f`): Objects implementing this method
   are automatically converted to TVM FFI device in function calls.

5. **`__tvm_ffi_opaque_ptr__`** (`42e0612`): Allows passing opaque C pointers
   through FFI calls.

### DLPack exchange API preference in from_dlpack (November 2025)

`from_dlpack()` now preferentially uses the `__c_dlpack_exchange_api__` fast
path when available (`7f3f872`), falling back to the standard `__dlpack__`
protocol only when the exchange API is not present. A new
`_from_dlpack_exchange_api()` Cython helper was added for this code path.
A memory leak was also fixed: when `TVMFFITensorFromDLPackVersioned` fails,
the managed tensor deleter is now called to reclaim memory.

### DLPack exchange API PyCapsule upgrade (November 2025)

The `__c_dlpack_exchange_api__` attribute was changed from a raw integer
pointer to a PyCapsule (`7f3bb77`), with backward compatibility for the
integer form. The Cython `_get_dlpack_exchange_api()` helper accepts both
`int` and PyCapsule. When loading the torch extension, integer-form
attributes are eagerly upgraded to PyCapsule. This is safer and more
Pythonic than passing raw integer pointers.

### Bool dtype alignment to DLPack (November 2025)

The `bool` dtype representation was changed (`ae346ec`) from `kDLUInt(1)/1bit`
to `kDLBool(6)/8bits` to match the DLPack standard. `DataTypeCode.BOOL = 6`
was added to the Python enum. This is a breaking change: code checking
`dtype.type_code == 1 and dtype.bits == 1` for bool must update to
`dtype.type_code == 6`.

### DLPack dtype literals (November 2025)

Module-level dtype literal instances were added (`408aa78`): `tvm_ffi.bool`,
`tvm_ffi.int8`, `tvm_ffi.float32`, etc. These provide convenient access to
common dtype values without constructing them from strings.

### ROCm DLPack tensor support (November 2025)

PyTorch tensor conversion on the ROCm backend was enabled (`752ac8e`),
extending the torch-c-dlpack-ext to support AMD GPUs.

### CUDA stream interop improvements (November 2025)

`cuda.bindings.driver.CUstream` objects from the `cuda-python` package are
now accepted as FFI arguments (`6c85e56`). A fallback argument setter treats
`CUstream` as an integer pointer until `cuda-python` adds native
`__cuda_stream__` protocol support.

### AOT PyTorch DLPack extension (October 2025)

`addons/torch_c_dlpack_ext/` (`f703a0c`) is a new standalone Python package
that ships the torch C DLPack extension as an AOT-compiled wheel. When
installed, `tvm_ffi` uses the pre-compiled library instead of JIT-compiling
at import time. The default JIT behavior is unchanged; AOT is opt-in.

### Strided tensor views (December 2025)

`Tensor::as_strided(shape, strides, element_offset)` (`8888eb4`) creates a
ref-counted view sharing the source tensor's data memory.
`TensorView::as_strided(shape, strides, element_offset)` provides the
lightweight non-owning variant. `Tensor::FromNDAllocStrided` is a static
factory for creating tensors with custom strides from an NDAllocator.

The new C API function `TVMFFITensorCreateUnsafeView(source, prototype, out)`
backs this feature. The implementation (`src/ffi/tensor.cc`) uses a local
`ViewNDAlloc` functor that keeps the source tensor alive via `ObjectPtr`.

### DLPack from_dlpack PyCapsule fallback fix (December 2025)

After the PyCapsule migration (#288 in November 2025),
`_from_dlpack_universal` still used a direct integer cast for
`__c_dlpack_exchange_api__`, breaking `tvm_ffi.from_dlpack(torch_tensor)`
when the attribute was a PyCapsule (`4147ba7`). The fix calls
`_get_dlpack_exchange_api()` to handle both forms.

### DLPack further compatibility (December 2025)

Additional DLPack compatibility fixes (`5393647`) and torch int8 support
for torch<2.6.0 (`91c64b7`) were applied. The torch C DLPack extension
version was bumped to 0.1.4 (`f7e09d6`).

### `tvm_ffi.device(...)` scalar ID support (December 2025)

`tvm_ffi.device(..., id)` now accepts numpy or torch scalar values for
the device ID parameter (`a7ebc65`), improving interop with frameworks
that return 0-dim tensors for device indices.

### DLPack stride normalization removal

DLPack stride normalization was progressively removed:
- `53ffe5e`: Restricted stride normalization to 1D tensors on export.
- `f4a65cd`: Completely removed all stride normalization.

The removal simplifies the DLPack exchange path and avoids unexpected stride
mutations that could confuse downstream frameworks.

### DLPack f4 support

DLPack conversion was updated to enable the f4 (float4) data type (`929effa`).

### GIL release option

A `func.release_gil` boolean option was added to Python `Function` objects
(`f81ab9c`), allowing the GIL to be released during C function dispatch for
compute-heavy operations.

### External dtype support

torch, numpy, and ml_dtypes dtype objects can now be used directly as FFI
input (`d77606a`), automatically converting to `DLDataType`.

## APIs

### C++ API

```cpp
// Tensor class (include/tvm/ffi/container/tensor.h).
class TensorObj : public ObjectObj {
  // Internal layout: DLTensor header + inlined shape/strides data
};

class Tensor : public ObjectRef {
  ShapeView shape() const;
  ShapeView strides() const;
  void* data_ptr() const;
  int64_t ndim() const;
  int64_t numel() const;
  DLManagedTensorVersioned* ToDLPackVersioned() const;
  Tensor as_strided(ShapeView shape, ShapeView strides,
                    std::optional<int64_t> element_offset = std::nullopt) const;
  template <typename TNDAlloc, typename... ExtraArgs>
  static Tensor FromNDAllocStrided(TNDAlloc alloc, ShapeView shape,
                                   ShapeView strides, DLDataType dtype,
                                   DLDevice device, ExtraArgs&&... extra_args);
};

// ShapeView (include/tvm/ffi/container/shape.h).
class ShapeView {
  const int64_t* data() const;
  int64_t size() const;
  int64_t operator[](int64_t i) const;
  int64_t Product() const;
  // Standard iterator interface
};

// Shape has implicit conversion to ShapeView.
class Shape : public ObjectRef {
  operator ShapeView() const;
  static Shape StridesFromShape(ShapeView shape);
};
```

### C API

```c
// DLPack tensor allocator (include/tvm/ffi/c_api.h).
typedef int (*DLPackTensorAllocator)(
    DLTensor* prototype, DLManagedTensorVersioned** out, void* error_ctx,
    void (*SetError)(void* error_ctx, const char* kind, const char* message)
);
```

The `DLPackExchangeAPI` struct (defined in Cython/C++ helper headers)
bundles the allocator with `managed_tensor_from_py_object_no_sync` and
`managed_tensor_to_py_object_no_sync` function pointers. This struct is
passed via the `__dlpack_c_exchange_api__` Python attribute on tensor
classes (e.g., `torch.Tensor`).

### Python API

```python
import tvm_ffi

# Tensor creation
tensor = tvm_ffi.Tensor.from_dlpack(numpy_array)

# DLPack exchange
dl = tensor.__dlpack__()

# Properties
shape = tensor.shape
strides = tensor.strides
dtype = tensor.dtype
device = tensor.device
```

## Implementation

Key files:
- `include/tvm/ffi/container/tensor.h` -- `TensorObj`, `Tensor`, DLPack exchange
- `include/tvm/ffi/container/shape.h` -- `ShapeObj`, `Shape`, `ShapeView`
- `src/ffi/tensor.cc` -- Tensor implementation (renamed from `ndarray.cc`)
- `python/tvm_ffi/_tensor.py` -- Python Tensor class (renamed from `ndarray.py`)
- `python/tvm_ffi/cython/tensor.pxi` -- Cython Tensor bridge (renamed from `ndarray.pxi`)
- `python/tvm_ffi/cython/tvm_ffi_python_helpers.h` -- C++ helpers for Python call dispatch
- `python/tvm_ffi/_optional_torch_c_dlpack.py` -- Optional PyTorch DLPack integration

Tests:
- `tests/cpp/test_tensor.cc` -- C++ tensor tests (renamed from `test_ndarray.cc`)
- `tests/cpp/test_shape.cc` -- Shape and ShapeView tests
- `tests/python/test_tensor.py` -- Python tensor tests
- `tests/scripts/benchmark_dlpack.py` -- DLPack exchange benchmarks

## History
- 2025-09-06: `NDArray`/`NDArrayObj` renamed to `Tensor`/`TensorObj` (`3a551d8`)
- 2025-09-06: Default strides construction added (`ca95b41`)
- 2025-09-06: `Tensor::strides()` returning `Shape` added (`6fa40b5`)
- 2025-09-08: Relaxed default alignment and contiguity requirements (`1b824e8`)
- 2025-09-11: Python FFI call dispatch optimized (`38d2cda`)
- 2025-09-12: DLPack exporter/importer/allocator C function pointers; atomic cache; `release_gil` (`f81ab9c`)
- 2025-09-12: DLPack attribute protocol renamed (`4dee97f`)
- 2025-09-13: Better string and nested container handling in call dispatch (`043d9f6`)
- 2025-09-18: DLPack f4 support (`929effa`)
- 2025-09-18: Stride normalization restricted to 1D (`53ffe5e`)
- 2025-09-19: External dtype support (torch, numpy, ml_dtypes) (`d77606a`)
- 2025-09-23: Critical path perf improvement in Cython `make_ret_object` (`035975a`)
- 2025-09-25: Cython memory corruption fix reported by ASan (`8e471b0`)
- 2025-09-27: `ShapeView` introduced; `TensorObj` minimized (`8ca0719`)
- 2025-09-29: DLPack stride normalization completely removed (`f4a65cd`)
- 2025-10-01: `ffi::TensorView` non-owning view introduced (`1ec6236`)
- 2025-10-01: Zero-dim tensor strides allowed to be null (`4fefeb0`)
- 2025-10-11: DLPackExchangeAPI unification: 3-pointer protocol -> single struct (`22a7894`)
- 2025-10-12: `Tensor.strides` exposed in Cython (`8377011`)
- 2025-10-13: `__tvm_ffi_tensor__` protocol for zero-copy tensor pass-through (`4bc8925`)
- 2025-10-13: CUDA stream protocol support (`b0537f0`)
- 2025-10-14: `__tvm_ffi_tensor__` generalized to `__tvm_ffi_object__` (`8873700`)
- 2025-10-15: `TVMFFIEnvTensorAlloc` and allocator API rename (`f679fe5`)
- 2025-10-16: `__tvm_ffi_opaque_ptr__` protocol introduced (`42e0612`)
- 2025-10-20: `__dlpack_data_type__` protocol for dtype conversion (`5e648f0`)
- 2025-10-20: `__dlpack_device__` protocol for device conversion (`0f8bf9f`)
- 2025-10-31: AOT `torch_c_dlpack_ext` addon package (`f703a0c`)
- 2025-11-07: CUDA stream compat with `cuda-python` `CUstream` objects (`6c85e56`)
- 2025-11-10: ROCm tensor conversion enabled for torch-c-dlpack-ext (`752ac8e`)
- 2025-11-12: `from_dlpack()` prefers exchange API fast path when available (`7f3f872`)
- 2025-11-14: Bool dtype changed to `kDLBool(6)/8bits` per DLPack standard (`ae346ec`)
- 2025-11-14: Module-level dtype literal instances added (`408aa78`)
- 2025-11-26: DLPack exchange API attribute changed from integer to PyCapsule (`7f3bb77`)
- 2025-12-02: `from_dlpack` PyCapsule fallback fix for `__c_dlpack_exchange_api__` (`4147ba7`)
- 2025-12-05: DLPack further compatibility improvements (`5393647`)
- 2025-12-08: torch int8 fix for torch<2.6.0 (`91c64b7`)
- 2025-12-12: `Tensor::as_strided`, `TensorView::as_strided`, `TVMFFITensorCreateUnsafeView` C API (`8888eb4`)
- 2025-12-18: `tvm_ffi.device(...)` accepts numpy/torch scalar for device ID (`a7ebc65`)
- 2026-01-02: `Tensor::size()`, `Tensor::stride()`, `TensorView::size()`, `TensorView::stride()` now throw `IndexError` for out-of-range indices (previously UB) (`e54d15d`)
- 2026-01-13: Error propagation fix for tensor arguments: `TVMFFIPyCallManager` no longer silently swallows function errors when the DLPack allocator restore path overwrites the return code (`e1bd421`)
- 2026-01-17: Improved dtype handling in `torch_c_dlpack_ext` for older PyTorch versions (`4fec972`)
- 2026-01-25: DLPack submodule bumped from `93c8f2a` to `84d107b` (`e6e5d3a`)

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-09-30-CA9C3D1-F9179EC.md`
  - `.repo-knowledge/ranges/2025-10-31-FFA2DBF-BC0D225.md`
  - `.repo-knowledge/ranges/2025-11-30-0EE6444-4076EF5.md`
  - `.repo-knowledge/ranges/2025-12-29-5A82940-6E7CAFA.md`
  - `.repo-knowledge/ranges/2026-01-30-C51E519-B508698.md`
- Related ADRs:
  - `.repo-knowledge/adr/008-ndarray-to-tensor-rename.md`
- Related design docs:
  - `.repo-knowledge/design/003-c-abi-stability.md`
  - `.repo-knowledge/design/008-python-packaging.md`
