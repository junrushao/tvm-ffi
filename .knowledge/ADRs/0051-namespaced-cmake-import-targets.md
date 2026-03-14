---
scope:
  - "0016-packaging-and-build"
---
# Namespaced CMake Import Targets

**TL;DR**: Renamed CMake imported targets from `tvm_ffi_shared`/`tvm_ffi_header` to `tvm_ffi::shared`/`tvm_ffi::header` to follow CMake namespace conventions and avoid name collisions with locally-defined targets in the source build.

## Context

When a downstream project uses `find_package(tvm_ffi CONFIG)` to consume the pre-built TVM FFI library, the config file creates IMPORTED targets. The original target names (`tvm_ffi_shared`, `tvm_ffi_header`) were identical to the target names defined in the source `CMakeLists.txt`. This created a name collision: if a project simultaneously used `add_subdirectory(tvm-ffi)` (which defines `tvm_ffi_shared` as a regular target) and `find_package(tvm_ffi CONFIG)` (which attempted to create an IMPORTED target with the same name), CMake would error.

Even without that simultaneous usage, the naming ambiguity made it unclear in downstream `CMakeLists.txt` files whether `tvm_ffi_shared` referred to a locally-built target or an imported one.

Usecases:
- Downstream projects consuming TVM FFI via `find_package(tvm_ffi CONFIG)` that also have their own targets named with `tvm_ffi_` prefix.
- Build systems that switch between source-build and pre-built modes depending on environment variables or CI configuration.

Design Decisions:
- Rename imported targets from `tvm_ffi_shared` to `tvm_ffi::shared` and from `tvm_ffi_header` to `tvm_ffi::header` in `cmake/tvm_ffi-config.cmake`.
- Source-build targets (`tvm_ffi_shared`, `tvm_ffi_header`, `tvm_ffi_static`, `tvm_ffi_objs`) retain their original names since they are not namespaced IMPORTED targets.
- The `tvm_ffi_configure_target` and `tvm_ffi_install` helper functions reference the namespaced names (`tvm_ffi::shared`, `tvm_ffi::header`), making them work correctly when invoked from downstream projects that used `find_package`.
- All downstream references in examples (`quickstart`, `stable_c_abi`, `cubin_launcher`) and the `EmbedCubin.cmake` utility were updated to use the new names.

Alternatives considered:
- **Keep flat names with unique suffixes** (e.g., `tvm_ffi_imported_shared`): Avoids the collision but departs from CMake convention. Tools and IDEs that understand `::` namespace syntax (e.g., CMake's `IMPORTED_TARGET` checks) would not benefit.
- **Use ALIAS targets** to map `tvm_ffi::shared` to `tvm_ffi_shared` in source builds: This would allow a single consumer API (`tvm_ffi::shared`) regardless of integration mode. However, ALIAS targets for IMPORTED libraries require CMake 3.18+ and add complexity. The current approach keeps the two integration modes explicitly distinct.

Consequences:
- **Breaking change** for downstream CMake consumers that referenced the old names. Migration: replace `tvm_ffi_shared` with `tvm_ffi::shared` and `tvm_ffi_header` with `tvm_ffi::header` in `target_link_libraries` calls.
- Rollback: revert the `cmake/tvm_ffi-config.cmake` changes and update all references back. Low risk since the change is purely in CMake config files with no runtime effect.

## Implementation Notes

- `cmake/tvm_ffi-config.cmake`: `add_library(tvm_ffi::header INTERFACE IMPORTED)` and `add_library(tvm_ffi::shared SHARED IMPORTED)` replace the flat-named versions.
- `cmake/Utils/Library.cmake`: `tvm_ffi_configure_target` checks for `TARGET tvm_ffi::header` and `TARGET tvm_ffi::shared`.
- `cmake/Utils/EmbedCubin.cmake`: Updated to link against `tvm_ffi::header` instead of `tvm_ffi_header`.
- All example `CMakeLists.txt` files updated: `examples/quickstart`, `examples/stable_c_abi`, `examples/cubin_launcher/dynamic_cubin`, `examples/cubin_launcher/embedded_cubin`.

## Related Design Docs

- [`.knowledge/designs/0016-packaging-and-build.md`](../designs/0016-packaging-and-build.md)
- Evidence: `.knowledge/commits/2025-12-22-a1cb746201412a943c29d942e6b2c29b36d97c48.md` + `a1cb746`
