# Distill Report: Group 16

**Commits**: 426ec96 be3de4c 6e448cf 573d76f 1fb25db 729f971 f0058a9 9a6ec6e 8626100 0729193 e10d1ed 5e648f0 0f8bf9f 618c03bd aeaeca0 d6f922a 53a7fe9 a23c5a0 af898a2 ac63fb9
**Last commit**: ac63fb9b0e13aed9da18153398e5f2332cbbc02f

## Summary

Group 16 contains 20 commits spanning October 17-26, 2025. The group is predominantly documentation and developer experience improvements (11 docs-only, 2 trivial), with several significant API additions (aten-style Tensor aliases, DLPack protocol extensions, version API, auto-__init__ generation) and one build system change (setuptools_scm versioning).

## Files Created

| File | Action | Description |
|------|--------|-------------|
| `.knowledge/ADRs/020-setuptools-scm-versioning.md` | **created** | ADR documenting the decision to adopt setuptools_scm for git-tag-based versioning across Python/C++/Rust |

## Files Updated

| File | Action | Key Changes |
|------|--------|-------------|
| `.knowledge/designs/containers.md` | **updated** | Added Tensor/TensorView aten-style aliases (`dim()`, `sizes()`, `is_contiguous()`), negative indexing for `size(int64_t)`/`stride(int64_t)`, v26 evolution entry, evidence matrix entry |
| `.knowledge/designs/c-abi.md` | **updated** | Added Version API section (TVMFFIGetVersion, TVMFFIVersion struct, compile-time macros), updated non-goals text, added to C API Function Summary and evidence matrix |
| `.knowledge/designs/function-system.md` | **updated** | Added `FunctionInfo<R (&)(Args...)>` specialization for function lvalue references, v13 evolution entry, evidence matrix entry |
| `.knowledge/designs/0014-python-bindings.md` | **updated** | Added `__dlpack_data_type__` and `__dlpack_device__` protocol entries to arg setter dispatch table; added auto-`__init__` generation protocol in `_add_class_attrs`; updated Cython Type Stubs section for docstring migration and `annotation_typing=False` |
| `.knowledge/designs/0015-python-packaging.md` | **updated** | Updated pyproject.toml example for `dynamic = ["version"]` + setuptools_scm, added build-system requires `setuptools-scm`, documented git-based versioning contract, added evidence matrix entries |
| `.knowledge/designs/rust-bindings.md` | **updated** | Added rustdoc-safe `build.rs` graceful degradation, Sphinx-Rust documentation build pipeline, evidence matrix entries |
| `.knowledge/designs/0013-module-system.md` | **updated** | Updated `load_module` signature to `str | PathLike`, v11 evolution entry |
| `.knowledge/api-index/0010-python-bindings.md` | **updated** | Updated `load_module` signatures to `str | PathLike`, added `dtype.from_dlpack_data_type`, updated `last_updated_commit`, added 6 evidence entries + 14 supporting commit note |
| `.knowledge/api-index/0008-module-system.md` | **updated** | Updated `last_updated_commit` to 53a7fe9 |

## Key Insights Captured

1. **DLPack duck-typing protocols**: Two new arg setter protocols (`__dlpack_data_type__` for dtype, `__dlpack_device__` for device) generalize FFI argument ingestion beyond hardcoded framework types. The `__dlpack_device__` protocol includes a `not __dlpack__` guard to avoid misrecognizing tensor types.

2. **Auto-`__init__` generation**: `_add_class_attrs` now implements a three-way dispatch for `@register_object` classes without explicit `__init__`: wire to `__ffi_init__` if available, install error sentinel if not a PyNativeObject, or leave alone for PyNativeObject subclasses. This eliminates a class of silent segfaults.

3. **Version API architecture**: `TVMFFIGetVersion` is the first C ABI function explicitly documented as "always stable across all versions," making it the foundation for future ABI negotiation. Combined with `setuptools_scm`, the project now has a single source of truth (git tags) for version across Python/C++/Rust.

4. **FunctionInfo completeness**: The `R (&)(Args...)` specialization completes the function-type decomposition family (bare, pointer, reference), fixing compilation failures with certain macro/constexpr patterns.

5. **Documentation infrastructure**: Docstrings migrated from `.pyi` to Cython `.pxi` sources for Sphinx autodoc; `annotation_typing=False` directive enables Python-style type annotations in Cython without affecting codegen; Rust docs integrated into Sphinx build pipeline via `BUILD_RUST_DOCS` env var.

## Unresolved Evidence Gaps

- The Rust docs build pipeline details (exact `cargo doc` flags, output path structure) are documented at a high level but the `docs/conf.py` implementation details were not captured in the Rust bindings design doc in full detail.
- `tvm_ffi.cpp` submodule export (added in e10d1ed) is not tracked in any API index -- it was previously omitted from `__all__` and is now included.
- The `__init__invalid` sentinel function in `registry.py` (from 0729193) is internal but has behavioral impact; it is documented in the design doc but not in the API index (correctly, as it is not public API).
