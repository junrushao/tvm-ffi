---
scope:
  - "0011-extra-api-tier"
  - "0001-c-abi"
---
# TVM_FFI_EXTRA_CXX_API Macro and Extra API Tier

**TL;DR**: `TVM_FFI_EXTRA_CXX_API` marks non-core C++ APIs that are DLL-exported but not ABI-stable across MSVC/Itanium boundaries. These APIs live in `include/tvm/ffi/extra/` and are gated by `TVM_FFI_USE_EXTRA_CXX_API` at build time.

## Context

The structural equal/hash system provides useful C++ entry points (`StructuralEqual::Equal`, `StructuralHash::Hash`) that are not part of the core C ABI but need to be callable from other compilation units. These functions accept and return `Any`/`ObjectRef` types (not just POD), which means their C++ name mangling is compiler-specific. A mechanism was needed to distinguish these "extra" APIs from the core C ABI.

## Alternatives Considered

1. **Only expose via C function registry**: Register as global FFI functions callable through the packed calling convention. Fully ABI-portable. But less ergonomic from C++ -- callers must use `Function` objects and `Any` wrappers instead of direct C++ calls with typed parameters.

2. **Make them header-only**: No visibility/linking issues, always available. But the structural equal/hash implementations are 500+ lines each, increasing compile time for all consumers.

3. **Use TVM_FFI_DLL directly**: No new macro, but no documentation signal about the non-core nature and ABI limitations of these APIs.

## Decision

Introduce `TVM_FFI_EXTRA_CXX_API` in a dedicated header (`include/tvm/ffi/extra/base.h`), functionally equivalent to `TVM_FFI_DLL` but serving as documentation that:
- These APIs are non-core convenience features.
- They are implemented in `.cc` files (not header-only) to reduce compile overhead.
- They may have cross-ABI issues (MSVC vs Itanium) and should not be used across DLL boundaries compiled with different compilers.

The macro was originally defined in `c_api.h` (commit `9445fe7`) and later moved to `extra/base.h` (commit `3fc0391`) to keep `c_api.h` as the pure C ABI surface.

## Trade-offs

- **Pro**: Convenience for same-compiler consumers who can call `StructuralEqual::Equal(a, b)` directly.
- **Pro**: Clear documentation signal about ABI limitations.
- **Pro**: Build-time gating via `TVM_FFI_USE_EXTRA_CXX_API` allows smaller binaries.
- **Con**: These APIs are not portable across compiler ABIs (e.g., MSVC caller + GCC library).
- **Con**: Introduces a second visibility macro alongside `TVM_FFI_DLL`, adding conceptual overhead.

## Consequences

- All extra-tier APIs use `TVM_FFI_EXTRA_CXX_API` visibility and live under `include/tvm/ffi/extra/`.
- `c_api.h` remains free of non-core macros.
- The `TVM_FFI_USE_EXTRA_CXX_API` CMake option (default ON) gates compilation of extra `.cc` files.
- `AccessPath`/`AccessStep` were promoted to the unconditional core build despite being used by extra APIs, because they serve general reflection purposes.

## Implementation Notes

- Evidence: commits `9445fe7` (introduction), `2ec11f5` (CMake gating), `3fc0391` (move to extra/base.h).

## Related Design Docs

- [`.knowledge/designs/0011-extra-api-tier.md`](../designs/0011-extra-api-tier.md) -- Extra API tier design
- [`.knowledge/designs/0009-structural-equal-hash.md`](../designs/0009-structural-equal-hash.md) -- Primary consumer
