---
scope:
  - "0010-structural-equal-hash"
  - "0013-module-system"
---
# Isolate Non-Core C++ APIs into extra/ Module

**TL;DR**: The decision to separate non-core C++ APIs (`StructuralEqual`, `StructuralHash`, module system, stream context, env C APIs, testing utilities) into `include/tvm/ffi/extra/` with a dedicated `TVM_FFI_EXTRA_CXX_API` visibility macro and `TVM_FFI_USE_EXTRA_CXX_API` build toggle, while keeping `AccessPath` in core.

## Context
- `StructuralEqual` and `StructuralHash` are heavyweight features that not all consumers of TVM FFI need. They pull in reflection traversal, memoization tables, and free-variable mapping infrastructure.
- The `TVM_FFI_EXTRA_CXX_API` macro was initially defined in `c_api.h`, mixing C++-only concerns into the C ABI header.
- Lightweight consumers (embedded deployments, kernel-only libraries) want to build TVM FFI without these optional features to reduce binary size and compile time.
- `AccessPath` (access step recording for mismatch diagnostics) is used by core reflection registration and is lightweight enough to remain in core.

Usecases:
- Embedded ML deployment needing only core FFI (function calls, object management, containers) without structural comparison.
- Build configurations that minimize compile time and binary size.
- Clear documentation of what constitutes "core" vs "optional" API surface.

Design Decisions:
- **`include/tvm/ffi/extra/` directory**: New module boundary for non-core C++ APIs. `base.h` defines the `TVM_FFI_EXTRA_CXX_API` macro.
- **`TVM_FFI_EXTRA_CXX_API` relocated from `c_api.h` to `extra/base.h`**: Keeps C ABI header free of C++-only concerns.
- **`TVM_FFI_USE_EXTRA_CXX_API` CMake option (default ON)**: When OFF, the following source files are excluded from the shared library build: `structural_equal.cc`, `structural_hash.cc`, `serialization.cc`, `json_parser.cc`, `json_writer.cc`, `reflection_extra.cc`, `module.cc`, `library_module.cc`, `library_module_system_lib.cc`, `library_module_dynamic_lib.cc`, `stream_context.cc`, `env_c_api.cc`, `testing.cc` (all under `src/ffi/extra/`).
- **`access_path.cc` promoted to core**: Always compiled (unconditional in `CMakeLists.txt`) because it is used by reflection registration, not just structural equal/hash.
- **`reflection_extra.cc`**: Houses `MakeObjectFromPackedArgs` and `AccessStep`/`AccessPath` reflection registration (relocated from `object.cc` and `access_path.cc` in commit `f4ede98`).
- **Env C API relocation** (commit `023ea44`): `TVMFFIEnvCheckSignals` and `TVMFFIEnvRegisterCAPI` were moved from core `c_api.h` to `extra/c_env_api.h`, and their implementations from `src/ffi/function.cc` to `src/ffi/extra/env_c_api.cc`. Module-specific C API functions were renamed with a `Mod` infix (`TVMFFIEnvModLookupFromImports`, `TVMFFIEnvModRegisterContextSymbol`, `TVMFFIEnvModRegisterSystemLibSymbol`). See [ADR 0013](0013-env-api-naming-convention.md).
- **Corresponding global functions** (`ffi.GetFirstStructuralMismatch`, `ffi.StructuralHash`, `ffi.ModuleLoadFromFile`, `ffi.SystemLib`, etc.) are registered only when extra API is compiled.

## Implementation Notes
- `TVM_FFI_EXTRA_CXX_API` defaults to `TVM_FFI_DLL` (platform-specific import/export). It marks functions that are implemented in `.cc` files (not inline) to reduce compile-time overhead. These functions use only POD/Any/ObjectRef in their public signatures for ABI stability.
- The extra API may have C++ ABI compatibility issues across MSVC/Itanium ABI boundaries (noted in the header comment). For cross-ABI usage, the corresponding reflection-based global functions (registered via C API) should be used instead.

## Related Design Docs
- [0010-structural-equal-hash.md](../designs/0010-structural-equal-hash.md)
- [0012-json-and-serialization.md](../designs/0012-json-and-serialization.md)
- [0013-module-system.md](../designs/0013-module-system.md)
- [0013-env-api-naming-convention.md](0013-env-api-naming-convention.md)
