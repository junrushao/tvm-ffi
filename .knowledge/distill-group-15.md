# Distill Group 15 Summary

**Commits**: 22a7894, 8377011, ea02e64, 4bc8925, 550e92f, b0537f0, 80bd4d8, 965fc46, 58875b9, 7b57a46, 8873700, 9ac3121, 9186b44, bd19463, efd0a08, 46a1d88, 0dcd4d2, da7007f, 5dd60e6, 70caf4c, df04392, fc2630f, a97b7c6, 9829dec, f679fe5, d183a95, 4206f16, 2002e28, f0145b4, ef54bda, 78d3c42, 33b3768, 59c91c1, af9fc06, af25838, 5e2a0e5, d2e9aa6, 42e0612, 9d54755, d87502a, 792dc01, 8831e88, ed47043, 997a366, 3373853, 39d675d, 10fa010, 24cf519, 08dbabf, 6e9100c (plus 3 additional supporting commits)

**Last Commit**: 6e9100c13b83f1ab42cd067cc0121aad8766a507

## Key Themes

### 1. DLPackExchangeAPI Struct-Based Protocol (22a7894, 9829dec, f679fe5, 3373853)
- Three separate Python class attributes (`__c_dlpack_from_pyobject__`, `__c_dlpack_to_pyobject__`, `__c_dlpack_tensor_allocator__`) replaced by a single `__c_dlpack_exchange_api__` pointing to a `DLPackExchangeAPI` struct (per DLPack proposal #175)
- Stream querying decoupled from tensor export: `current_work_stream` function pointer in the struct replaces piggybacked stream out-parameter
- Non-owning `DLTensor` export path via `DLPackDLTensorFromPyObjectNoSync` (stack-allocated, no refcount)
- `DLPackTensorAllocator` typedef removed from local code, replaced by `DLPackManagedTensorAllocator` from upstream dlpack.h
- `TVMFFIEnvSetTensorAllocator` / `TVMFFIEnvGetTensorAllocator` renamed to `TVMFFIEnvSetDLPackManagedTensorAllocator` / `TVMFFIEnvGetDLPackManagedTensorAllocator`
- New `TVMFFIEnvTensorAlloc` high-level C API that wraps DLPack allocation + TensorObj construction inside libtvm_ffi, preventing module unloading order issues
- `Tensor::FromDLPackAlloc` replaced by `Tensor::FromEnvAlloc` with simplified signature
- Forward-compatibility guard: `load_torch_c_dlpack_extension()` skips JIT compilation when PyTorch natively provides `__c_dlpack_exchange_api__`

### 2. New Python Argument Setter Protocols (b0537f0, 80bd4d8, 8873700, 42e0612, 4bc8925)
- `__cuda_stream__` protocol: NVIDIA CUDA stream protocol support; objects implementing this are auto-converted to `kTVMFFIOpaquePtr`; torch backward-compat patch for older PyTorch
- `__tvm_ffi_object__` protocol: generalized from `__tvm_ffi_tensor__`; any object returning an `Object` (not just `Tensor`) is accepted; type index is read dynamically via `TVMFFIObjectGetTypeIndex`
- `__tvm_ffi_opaque_ptr__` protocol: allows arbitrary Python objects to declare themselves as carrying an opaque C pointer
- `PyNativeObject.__tvm_ffi_object__` (attribute) renamed to `_tvm_ffi_cached_object` (dunder reserved for protocols)
- `hasattr` check for `__dlpack__` corrected from instance-level to class-level

### 3. Inline Stub Generation Tool (ea02e64)
- `tvm-ffi-stubgen` CLI tool and `tvm_ffi.stub.stubgen` module for in-place type stub generation from FFI registry metadata
- Marker directive DSL: `# tvm-ffi-stubgen(begin): global/<prefix>`, `object/<type_key>`, type remapping, skip-file
- Replaces hand-maintained `_ffi_api.pyi` with auto-generated inline stubs in `.py` files
- Removes `# type: ignore[attr-defined]` annotations throughout the codebase

### 4. Tensor Method-Based API (0dcd4d2)
- `TensorView` and `Tensor` APIs switched from `operator->()` to named methods: `data_ptr()`, `ndim()`, `size(idx)`, `stride(idx)`, `shape()`, `strides()`, `dtype()`, `device()`

### 5. Testing Library Split and Build Improvements (da7007f, 5dd60e6, d183a95, 4206f16, df04392)
- `libtvm_ffi_testing.so` split from `libtvm_ffi.so`; testing functions isolated from production library
- `find_library_by_basename()` added to `libinfo.py` as generalized shared library finder
- Testing library loading changed from runtime `load_module` to compile-time linking via Cython
- Intentional-leak singleton pattern: `TypeTable::Global()` uses `new` without delete for shutdown safety
- CMake config relocated from `cmake/` to `share/cmake/tvm_ffi/` for automatic `find_package` discovery

### 6. Function System: InvokeExternC (9186b44)
- `Function::InvokeExternC(handle, safe_call, args...)` static template method for zero-allocation direct calls to extern C symbols

### 7. Error Handling: CStr Parts API (550e92f)
- `TVMFFIErrorSetRaisedFromCStrParts(kind, message_parts, num_parts)` C API for DSL compilers to construct error messages from reusable string fragments

### 8. Reflection: Explicit Registration (9ac3121, fc2630f)
- Static line-based object registration removed in favor of explicit `ObjectDef<T>` registration
- `reflection::init<Args...>` struct template for defining initializers via `ObjectDef::def(init<Args...>())`

### 9. Release and Packaging (792dc01, 5e2a0e5, d2e9aa6, 997a366, d87502a, 8831e88, 10fa010, 39d675d)
- Version bumped to `0.1.0` (first stable release, from beta series 0.1.0b20)
- Python 3.8 support added (lowered from 3.9) with `collections.abc` vs `typing` gating
- Dual manylinux wheels: `manylinux2014` and `manylinux_2_28`
- macOS cp38 arm64 skip, Windows build fixes

### 10. MSVC / Cross-Platform Fixes (6e9100c, 2002e28, ed47043, 33b3768)
- Forward declaration of `Tensor` class for MSVC compatibility
- Endian detection in CMake
- Hidden symbols from libbacktrace

## Files Created
- `.knowledge/designs/0020-stubgen-tool.md` -- Design doc for `tvm-ffi-stubgen` CLI tool

## Files Updated
- `.knowledge/designs/0018-dlpack-fast-path.md` -- DLPackExchangeAPI struct protocol, renamed APIs, module unloading safety, updated sequence diagram, evolution entries v8-v16
- `.knowledge/designs/0014-python-bindings.md` -- New setter protocols (`__cuda_stream__`, `__tvm_ffi_object__`, `__tvm_ffi_opaque_ptr__`), DLPackExchangeAPI struct, `_tvm_ffi_cached_object` rename, stubgen section, evolution entries
- `.knowledge/designs/reflection.md` -- `init<Args...>` struct template, FunctionInfo SFINAE, explicit registration, evolution entries v21-v23
- `.knowledge/designs/0013-module-system.md` -- Module lifetime docs, testing library split, compile-time linking, evolution entries v8-v10
- `.knowledge/designs/containers.md` -- TensorView method-based API, Tensor method-based API, evolution entries v23-v25
- `.knowledge/designs/0015-python-packaging.md` -- Version 0.1.0, Python 3.8, wheel layout, dual manylinux, CMake config relocation
- `.knowledge/designs/function-system.md` -- `Function::InvokeExternC`, DLPack exchange API reference update, evolution entry v12
- `.knowledge/api-index/0014-dlpack-fast-path.md` -- Struct-based protocol entries, renamed APIs, deprecated/renamed table
- `.knowledge/api-index/0010-python-bindings.md` -- New protocols, stubgen CLI, `find_library_by_basename`, deprecated/renamed, evidence
- `.knowledge/api-index/0009-env-api.md` -- Renamed tensor allocator APIs, `TVMFFIEnvTensorAlloc`, deprecated/renamed, evidence

## Unresolved Gaps
- `.knowledge/designs/0018-dlpack-fast-path.md` evolution timeline v2 entry still references `Tensor::FromDLPackAlloc` (historical context, acceptable as-is)
- The `c_dlpack_to_pyobject` parameter name in a few `make_tensor_from_chandle` references within `0018-dlpack-fast-path.md` may be slightly outdated but the overall semantics are documented correctly through the `DLPackExchangeAPI` struct description
- No design doc exists for the `__cuda_stream__` protocol integration (minor -- documented in the python bindings setter dispatch table)
