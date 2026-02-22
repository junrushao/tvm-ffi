# ADR 015: CMake Namespaced Import Targets

- Status: Accepted
- Date: 2025-12-22
- Owners: Junru Shao

## Context

CMake imported targets from `tvm_ffi-config.cmake` used flat names
(`tvm_ffi_shared`, `tvm_ffi_header`). Flat target names can conflict with
targets defined in user `CMakeLists.txt` files. CMake convention for
imported targets from packages uses the `Package::Target` namespaced form
to avoid collisions.

## Decision

CMake imported targets were renamed to namespaced form (`a1cb746`):

| Old name | New name |
|----------|----------|
| `tvm_ffi_shared` | `tvm_ffi::shared` |
| `tvm_ffi_header` | `tvm_ffi::header` |

Backward compatibility is provided in `EmbedCubin.cmake` via target
probing (`if(TARGET tvm_ffi::header) ... elseif(TARGET tvm_ffi_header)`).
The `Library.cmake` helper functions (`tvm_ffi_configure_target`,
`tvm_ffi_install`) use the new names exclusively.

All examples and documentation were updated to use the new target names.
The `quickstart.rst` doc was also updated to reference `tvm_ffi_ROOT`
instead of `tvm_ffi_DIR`.

## Consequences

- Positive: Eliminates potential target name collisions with user-defined
  targets; follows CMake community conventions; cleaner configuration.
- Negative: Downstream CMake consumers using old target names
  (`tvm_ffi_shared`, `tvm_ffi_header`) will get build errors after
  upgrade. Backward compatibility is only provided in `EmbedCubin.cmake`,
  not in `Library.cmake`.
- Migration/Rollout: Update `target_link_libraries(... tvm_ffi_shared)` to
  `target_link_libraries(... tvm_ffi::shared)` and `tvm_ffi_header` to
  `tvm_ffi::header`.

## References

- Range summary: `.repo-knowledge/ranges/2025-12-29-5A82940-6E7CAFA.md`
- Evidence commits: `a1cb746`

## Related Design Docs

- `.repo-knowledge/design/008-python-packaging.md`
- `.repo-knowledge/design/003-c-abi-stability.md`
