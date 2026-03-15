# Distill Group 14 Summary

**Commits**: 1ec6236, 4fefeb0, 119130d, 6e9b785, 5fba9e8, 7092774, 28fe3cc, ec422f1, 98b26ed, 368af82, 0d8fec8, c046b17, cdc1ccca, dd4fb0a, 22c049b, b64b46f, a153647, f6303b2

**Last Commit**: f6303b23fd97909b59f6ff67b85f2203371f5db1

## Key Themes

### 1. TensorView: Non-Owning Tensor View (1ec6236, 4fefeb0)
- `ffi::TensorView` introduced as the new recommended parameter type for FFI-exported kernel functions, superseding `ffi::Tensor`
- Non-owning view over `DLTensor` with `storage_enabled = false` TypeTraits
- `TryCastFromAnyView` accepts both `kTVMFFIDLTensorPtr` and `kTVMFFITensor`
- Zero-dim strides invariant relaxed: `strides == nullptr` OK when `ndim == 0`

### 2. Type Schema and Metadata System (28fe3cc, 368af82, c046b17, dd4fb0a)
- `TypeTraits<T>::TypeSchema()` generates JSON schema strings for all types
- `Metadata` class for attaching arbitrary key-value metadata to fields/methods/functions
- `FieldInfoTrait` renamed to `InfoTrait`; `FieldInfoBuilder`/`MethodInfoBuilder` introduced
- Python `TypeSchema` dataclass for parsing and rendering type schemas
- `get_global_func_metadata()` Python API
- `FunctionInfo<R (Class::*)(Args...)>` fixed to include `Class*` as first param
- `TypeSchema.repr(ty_map)` for pluggable rendering; bare container normalization
- `DataType` -> `dtype` display fix in `_TYPE_SCHEMA_ORIGIN_CONVERTER`

### 3. DLPack Memory Leak Fix (7092774)
- Fixed unbounded memory growth in `make_tensor_from_chandle` when DLPack fast-path converts tensors
- Original `chandle` now explicitly DecRef'd after successful DLPack-to-PyObject conversion
- Exception path cleanup: deleter called on `DLManagedTensorVersioned` when import fails

### 4. Free-Threaded Python Support (22c049b)
- `TVMFFIPyWithGILIfNotFreeThreaded` RAII class for conditional GIL acquisition
- `TVMFFIPyObjectDeleter` replaces Cython `tvm_ffi_pyobject_deleter`
- `freethreading_compatible = True` Cython directive
- CMake detects free-threaded Python and skips Stable ABI
- `cp314t-*` wheels added to cibuildwheel build list
- `OpaquePyObject` type hierarchy fixed (now child of Object)

### 5. Python Function Creation from Extern C / MLIR (b64b46f, f6303b2)
- `Function.__from_extern_c__(c_symbol, *, keep_alive_object)` for raw C function pointers
- `Function.__from_mlir_packed_safe_call__(mlir_symbol, *, keep_alive_object)` for MLIR JIT
- `TVMFFIPyMLIRPackedSafeCall` adapter: translates MLIR packed convention to FFI safe call
- `keep_alive_object` changed to keyword-only on `__from_extern_c__`

### 6. Stream Query API (a153647)
- `tvm_ffi.get_raw_stream(device)` completes the stream context protocol with a getter
- `core._env_get_current_stream` Cython bridge wrapping `TVMFFIEnvGetStream`

### 7. Build Tooling (ec422f1, 98b26ed, 0d8fec8, cdc1ccca)
- `.clang-tidy` configuration with ~600 lines of modernization fixes
- `tests/lint/clang_tidy_precommit.py` runner script
- cmake-format/cmake-lint pre-commit hooks with `.cmake-format.json`
- `detect_target_triple()` CMake function for cross-platform libbacktrace builds
- Correctness fixes: `ObjectRef` move nulls source, `MoveTVMFFIAnyToAny` takes pointer, `Object()` zero-init

### 8. Compiler Compatibility (5fba9e8)
- Two-phase `is_integeral_enum_v` SFINAE helper avoids GCC 8.x compile error

### 9. Version Bumps (119130d, 6e9b785)
- Package version bumped from 0.1.0b13 to 0.1.0b14

## Files Created
None

## Files Updated
- `.knowledge/designs/containers.md` -- Added TensorView section, zero-dim strides exception, evolution entries v21-v22
- `.knowledge/designs/type-traits.md` -- Added TensorView row, TypeSchema(), TensorView TypeTraits section, evolution entries v6-v7
- `.knowledge/designs/reflection.md` -- Added Metadata/TypeSchema section, InfoTrait rename, evolution entries v18-v20
- `.knowledge/designs/function-system.md` -- Added FunctionInfo member-pointer fix, Python __from_extern_c__/__from_mlir_packed_safe_call__, MLIR adapter, evolution entries v7-v11
- `.knowledge/designs/0014-python-bindings.md` -- Added free-threaded Python, Function creation, TypeSchema class, get_raw_stream, updated GIL discipline
- `.knowledge/designs/0017-inline-module-compilation.md` -- Updated preferred parameter type from Tensor to TensorView
- `.knowledge/designs/0018-dlpack-fast-path.md` -- Added ownership invariants for make_tensor_from_chandle
- `.knowledge/designs/0015-python-packaging.md` -- Added cp314t-* wheels, free-threaded SABI skip note
- `.knowledge/api-index/0002-type-traits.md` -- Added TensorView, TypeSchema evidence
- `.knowledge/api-index/0004-function-system.md` -- Added MLIR adapter, Python APIs, evidence
- `.knowledge/api-index/0010-python-bindings.md` -- Added get_raw_stream, metadata, TypeSchema, Function factories, renames
- `.knowledge/api-index/0014-dlpack-fast-path.md` -- Added memory leak fix evidence

## Unresolved Gaps
- `.knowledge/designs/c-abi.md` line 199 shows `+deleter: fn(TVMFFIObject*, int flags)` -- should be `fn(void*, int flags)` per commit 24125d0 (pre-existing staleness, not introduced by this group)
- `.knowledge/designs/0016-weak-reference-counting.md` line 38 and `.knowledge/ADRs/014-weak-ref-24byte-header.md` line 55 have the same stale deleter signature
