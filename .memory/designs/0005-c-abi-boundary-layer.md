---
design: "0005"
title: "Stable C ABI Boundary Layer"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-05-06"
last_updated: "2025-10-18"
scope:
  - "ffi/c_api"
  - "ffi/error"
source_commits:
  - "7d34eb8abfe987bf0031e4d4ff479895d867a966"
  - "076ac23e994e404c40a789ccc42a1497a31e1280"
  - "8a009885a44a132baba886bead112924aef0d45f"
  - "192f196ec7b342677217e854fae7e7970fa100c5"
  - "1a856886c8c14c6271e156d1ce4d76335d42f0ff"
  - "a419ed175aac752a3df2ee73faad360a2824ecd8"
  - "837800e772d8c1dfa3a00a9f23f096487c96bd37"
  - "11a4a02d83e41ca4ccaf81df59d14b75309f65e9"
  - "9445fe734839cffc8bdf881788528b7763f7be03"
  - "162d6009252dd44950a9aa9b890cbbce6b8e5155"
  - "59a837eb4040843051706cbf5c7b71725fd65364"
  - "49e2ed4a169918d346fe8f96c208a4cec56cf3e8"
  - "538bef49b4daa91970f0f9cea137acdcb696562a"
  - "0daaffedd23982ea09f8c38fec4eef1cca1d8cac"
  - "023ea448be6e86e09f4ebaba5a235ee53f3cdeef"
  - "2d41a5115f6a91e2781012a3379f9626bc9e18a1"
  - "777cf8d51f2054d96e0413b7406ed38ef43a7b39"
  - "ca9c3d10bb9640bffb972302f7064e49e592a526"
  - "91d69f0658eef18fd9c99d4ac195ad5319db3787"
  - "40e8a519f5270dfb18436b2f26c2d691cf24c9c1"
  - "3a551d83f7c05106fa8033a61970a5ce34aa8aef"
  - "a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806"
  - "f81ab9c25ae4d2a42706747c50c5c410c51d6cdd"
  - "043d9f647677cc3b4a8baba198a2ced45f99cc98"
  - "c100338de52825097ddc44bbac3d03a92f45b33a"
  - "13436f01111bc4218feb440a29a2e421bc148cc4"
  - "43d13e86ee24d1558f929e3b0faa3182ca1af872"
  - "4fe8b2b79dfeb469b2499acecb3e10038ddcee0f"
  - "327e8cc63c9517df7ec9f1abc5f9c599c1b78c4d"
  - "ae06434d8363c9a668a63152bd35cb878209da9f"
  - "935a5a074686839ae42a9bc52581232beeb5b1fc"
  - "09477ce10de566f8cf511cce7dfe56e77759f100"
  - "f0058a9e"
source_ledgers:
  - ".memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md"
  - ".memory/commits/2025-05-11-076ac23e994e404c40a789ccc42a1497a31e1280.md"
  - ".memory/commits/2025-05-24-8a009885a44a132baba886bead112924aef0d45f.md"
  - ".memory/commits/2025-05-29-192f196ec7b342677217e854fae7e7970fa100c5.md"
  - ".memory/commits/2025-06-15-1a856886c8c14c6271e156d1ce4d76335d42f0ff.md"
  - ".memory/commits/2025-06-16-a419ed175aac752a3df2ee73faad360a2824ecd8.md"
  - ".memory/commits/2025-06-19-837800e772d8c1dfa3a00a9f23f096487c96bd37.md"
  - ".memory/commits/2025-06-05-11a4a02d83e41ca4ccaf81df59d14b75309f65e9.md"
  - ".memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md"
  - ".memory/commits/2025-07-22-162d6009252dd44950a9aa9b890cbbce6b8e5155.md"
  - ".memory/commits/2025-07-28-59a837eb4040843051706cbf5c7b71725fd65364.md"
  - ".memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md"
  - ".memory/commits/2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md"
  - ".memory/commits/2025-08-19-0daaffedd23982ea09f8c38fec4eef1cca1d8cac.md"
  - ".memory/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md"
  - ".memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md"
  - ".memory/commits/2025-08-30-777cf8d51f2054d96e0413b7406ed38ef43a7b39.md"
  - ".memory/commits/2025-09-01-ca9c3d10bb9640bffb972302f7064e49e592a526.md"
  - ".memory/commits/2025-09-05-91d69f0658eef18fd9c99d4ac195ad5319db3787.md"
  - ".memory/commits/2025-09-06-40e8a519f5270dfb18436b2f26c2d691cf24c9c1.md"
  - ".memory/commits/2025-09-06-3a551d83f7c05106fa8033a61970a5ce34aa8aef.md"
  - ".memory/commits/2025-09-09-a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806.md"
  - ".memory/commits/2025-09-12-f81ab9c2.md"
  - ".memory/commits/2025-09-13-043d9f64.md"
  - ".memory/commits/2025-09-14-c100338de52825097ddc44bbac3d03a92f45b33a.md"
  - ".memory/commits/2025-09-25-13436f01.md"
  - ".memory/commits/2025-09-26-43d13e86.md"
  - ".memory/commits/2025-09-29-4fe8b2b7.md"
  - ".memory/commits/2025-09-28-327e8cc6.md"
  - ".memory/commits/2025-09-29-ae06434d.md"
  - ".memory/commits/2025-10-01-935a5a07.md"
  - ".memory/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md"
  - ".memory/commits/2025-10-18-f0058a9e.md"
---

# Stable C ABI Boundary Layer

## TL;DR
- `c_api.h` defines the entire C ABI surface of TVM FFI: struct layouts (`TVMFFIAny`, `TVMFFIObject`, `TVMFFIByteArray`, `TVMFFISeqCell`, `TVMFFIErrorCell`, `TVMFFIFunctionCell`), enum constants (`TVMFFITypeIndex`), and C function declarations (`TVMFFI*` prefix).
- The ABI is versioned (`TVM_FFI_VERSION_{MAJOR,MINOR,PATCH}` = 0.1.9) and designed to be stable across shared library boundaries: foreign language bindings (Python, Rust) link against these C symbols.
- The safe-call convention (`TVMFFISafeCallType`) and TLS error propagation protocol are the cornerstones of cross-language error handling.

## Problem Statement
Foreign language bindings need a stable, well-defined binary interface to call into and be called by TVM FFI. C++ ABI is not portable across compilers or versions. The C ABI must define every struct layout, function signature, and calling convention precisely so that bindings can be implemented without access to C++ internals.

## Context and Constraints
- The C ABI must work across compiler versions and platforms (GCC, Clang, MSVC on Linux/macOS/Windows).
- Struct layouts must be fixed: field offsets cannot change between versions.
- Symbol visibility must be controlled (`TVM_FFI_DLL` / `TVM_FFI_DLL_EXPORT`).
- The ABI must support Emscripten (WebAssembly) in addition to native platforms.
- All C ABI functions return `int` (0 = success, -1 = error with TLS).

## Goals
- Define a complete, self-contained C header that foreign languages can use without any C++ dependency.
- Version the ABI to detect incompatibilities.
- Provide C functions for all core operations: reference counting, function calls, error handling, type registration, tensor exchange.
- Keep the ABI minimal: expose only what is needed for cross-language interop, not internal implementation details.

## Non-Goals
- Exposing C++ class methods via the C ABI (use packed functions instead).
- Supporting every container operation via C functions (containers are manipulated via packed functions).
- Guaranteeing forward compatibility of the ABI (minor version changes may add new functions but not change existing ones).

## Design
### Components and Responsibilities

- **Struct definitions**: `TVMFFIAny` (16 bytes, with `zero_padding`/`small_str_len` union; `v_char32` field removed in commit `c100338`), `TVMFFIObject` (24 bytes), `TVMFFIByteArray`, `TVMFFIShapeCell`, `TVMFFISeqCell`, `TVMFFIErrorCell`, `TVMFFIFunctionCell`, `TVMFFIFieldInfo` (enriched with offset, size, alignment, type_schema, flags, doc, default_value, getter, setter, metadata), `TVMFFIMethodInfo` (enriched with type_schema, flags, doc, metadata), `TVMFFITypeInfo` (with ancestor pointers instead of indices, metadata pointer), `TVMFFITypeMetadata` (creator, total_size `int32_t`, doc, structural_eq_hash_kind; renamed from `TVMFFITypeExtraInfo`), `TVMFFITypeAttrColumn` (column-array of `TVMFFIAny` indexed by type_index), `TVMFFIVersion` (struct with `major`, `minor`, `patch` fields, all `uint32_t`; added in commit `f0058a9e`). The `DLPackTensorAllocator` typedef was moved inside the `extern "C"` block (commit `c100338`) for pure C compiler compatibility, with a forward declaration of `DLManagedTensorVersioned`.

- **Enum definitions**: `TVMFFITypeIndex` (type discriminator, including `kTVMFFISmallStr=11`, `kTVMFFISmallBytes=12`, `kTVMFFIOpaquePyObject=74`; static object indices reordered: Shape=69, NDArray=70, Array=71, Map=72 per [ADR-0016](.memory/ADRs/0016-reorder-static-type-indices.md)), `TVMFFIObjectDeleterFlagBitMask` (deletion flags: `Strong=1`, `Weak=2`, `Both=3`), `TVMFFIBacktraceUpdateMode`, `TVMFFIFieldFlagBitMask` (with `kTVMFFIFieldFlagBitMaskWritable`, `kTVMFFIFieldFlagBitMaskHasDefault`, `kTVMFFIFieldFlagBitMaskIsStaticMethod`, `kTVMFFIFieldFlagBitMaskSEqHashIgnore`, `kTVMFFIFieldFlagBitMaskSEqHashDef`), `TVMFFISEqHashKind` (structural comparison semantics per type, values 0-5).

- **`TVMFFIFunctionCell`** (C struct, `c_api.h`): Contains `safe_call` (TVMFFISafeCallType, C ABI safe) and `cpp_call` (void*, direct C++ call path with exception propagation). Added in commit `4fe8b2b`. When `cpp_call` is non-null, `FunctionObj::CallPacked` uses it directly; when null, falls back to `CppCallDedirectToSafeCall` wrapper.

- **Object lifecycle**: `TVMFFIObjectIncRef(handle)`, `TVMFFIObjectDecRef(handle)` (renamed from `TVMFFIObjectFree`). The `TVMFFIObjectCreateOpaque(handle, type_index, deleter, out)` creates opaque objects wrapping arbitrary handles (commit `91d69f0`).

- **Function operations**: `TVMFFIFunctionCreate(safe_call, ...)`, `TVMFFIFunctionCall(func, args, n, rv)`, `TVMFFIFunctionGetGlobal(name, out)`, `TVMFFIFunctionSetGlobal(name, func, override)`, `TVMFFIFunctionListGlobal(out)`.

- **Error handling**: `TVMFFIErrorCreate(kind, msg, backtrace)`, `TVMFFIErrorSetRaised(error)`, `TVMFFIErrorMoveFromRaised(out)`, `TVMFFIErrorUpdateBacktrace(error, trace, mode)`.

- **Type registration**: `TVMFFITypeKeyToIndex(key, out)`, `TVMFFITypeIndexToInfo(index, out)`, `TVMFFITypeGetOrAllocIndex(key, ...)` (renamed from `TVMFFIGetOrAllocTypeIndex`), `TVMFFITypeRegisterField(index, info)` (renamed from `TVMFFIRegisterTypeField`), `TVMFFITypeRegisterMethod(index, info)`, `TVMFFITypeRegisterMetadata(index, metadata)` (renamed from `TVMFFITypeRegisterExtraInfo`), `TVMFFITypeRegisterAttr(type_index, attr_name, value)`, `TVMFFIGetTypeAttrColumn(attr_name)`.

- **Function registration with metadata**: `TVMFFIFunctionSetGlobalFromMethodInfo(info)` registers a global function with doc, type_schema, and flags.

- **Value conversion**: `TVMFFIAnyViewToOwnedAny(view, out)` (promotes AnyView to owning Any).

- **Tensor exchange**: `TVMFFITensorFromDLPack(managed, out)`, `TVMFFITensorToDLPack(tensor, out)`. Renamed from `TVMFFINDArray*` in commit `3a551d8` as part of the NDArray->Tensor rename.

- **String/Bytes construction**: `TVMFFIStringFromByteArray(input, out)` and `TVMFFIBytesFromByteArray(input, out)` construct owned FFI String/Bytes from byte arrays. Produces SmallStr/SmallBytes for small payloads or heap-allocated objects for larger ones. Added in commit `043d9f6`.

- **DLPack allocator APIs** (in `extra/c_env_api.h`): `TVMFFIEnvSetDLPackManagedTensorAllocator(allocator, flags, prev)` and `TVMFFIEnvGetDLPackManagedTensorAllocator(out)` manage a thread-local `DLPackManagedTensorAllocator` callback for pluggable tensor memory allocation. Added in commit `f81ab9c2`.

- **Module system**: `TVMFFIModuleLoadFromFile(path, format, out)`.

- **Symbol prefix**: `TVM_FFI_DLL_EXPORT_TYPED_FUNC` now emits C symbols with `__tvm_ffi_` prefix (e.g., `__tvm_ffi_ExportName`), standardized in commit `40e8a51`. Internal/special library symbols use double-underscore `__tvm_ffi__` (e.g., `__tvm_ffi__library_ctx`). See module system design for details.

- **Version**: `TVMFFIGetVersion(TVMFFIVersion* out)` (commit `f0058a9e`): Returns the C ABI version triple. Unlike all other `TVMFFI*` functions, this function returns `void` (not `int`) because it cannot fail and must be callable before any error handling infrastructure is initialized. The implementation lives in `src/ffi/object.cc` and populates the struct from the `TVM_FFI_VERSION_MAJOR/MINOR/PATCH` macros. This function is guaranteed stable across all future ABI versions, making it the first symbol a binding should resolve after loading the shared library.

### Data Contracts and Invariants
- **TVMFFIAny size**: Exactly 16 bytes on all platforms (`4 + 4 + 8`).
- **TVMFFIObject size**: Exactly 24 bytes on all platforms (`8 + 4 + 4 + 8`). Layout: `combined_ref_count` (uint64_t, strong in lower 32 bits, weak in upper 32 bits) + `type_index` (int32_t) + `__padding` (uint32_t, zero-initialized) + `deleter` (void*)(void*, int) (8 bytes). Ref counts were reordered to be first (aligned with torch `intrusive_ptr`) in commit `13436f0`, then combined into a single u64 in commit `43d13e8`.
- **Alignment**: `TVMFFIObject::deleter` is 8-byte aligned (ensured by `__ensure_align` union member). `TVMFFIAny` value union is 8-byte aligned.
- **Return code protocol**: All `TVMFFI*` functions returning `int` use 0 for success and -1 for error. The error is retrieved via `TVMFFIErrorMoveFromRaised`.
- **Symbol naming**: All exported C functions use the `TVMFFI` prefix. All exported macros use the `TVM_FFI_` prefix.
- **Version stability**: Within a major version, struct layouts and existing function signatures do not change. New functions may be added.

### Control Flow
1. **Foreign binding initialization**: Load the shared library -> resolve `TVMFFIGetVersion` -> verify major version compatibility -> resolve all needed `TVMFFI*` symbols.
2. **Function call from Python**: Python binding has a `Function` wrapper -> calls `TVMFFIFunctionCall(handle, packed_args, n, &rv)` -> checks return code -> on error, calls `TVMFFIErrorMoveFromRaised` and raises Python exception -> on success, converts `rv` to Python object.
3. **Function call from Rust**: Rust `Function::call_packed` invokes `safe_call` directly via the function pointer in `TVMFFIFunctionCell`, checks return code, and on error calls `Error::from_raised()` which wraps `TVMFFIErrorMoveFromRaised`. See [design 0017](.memory/designs/0017-rust-ffi-binding-layer.md).
4. **Object passing**: Python creates an object wrapper holding a `TVMFFIObjectHandle` -> calls `TVMFFIObjectIncRef` on share -> calls `TVMFFIObjectDecRef` on release. Rust `ObjectArc<T>` reimplements inc_ref/dec_ref natively with `AtomicU64` operations on `combined_ref_count` (see [ADR-0028](.memory/ADRs/0028-native-rust-refcounting.md)).
4. **Type introspection**: `TVMFFITypeIndexToInfo(index, &info)` -> returns `TVMFFITypeInfo*` with `type_key`, `type_depth`, `type_ancestors` (now `const TVMFFITypeInfo**` pointers instead of `int32_t*`), `fields`, `methods`, and `metadata` (containing creator, total_size, doc, structural_eq_hash_kind).

### Extension Points
- **New C ABI functions**: Added as new `TVMFFI*` declarations with minor version bump.
- **New struct fields**: Added at the end of existing structs with minor version bump (forward compatible). Existing field offsets never change.
- **Module system**: `TVMFFIModuleLoadFromFile` loads shared libraries that expose `__tvm_ffi_*` symbols. New module formats can be added.

- **Extra environment APIs** (in `extra/c_env_api.h`, not in core `c_api.h`): Host-environment APIs (`TVMFFIEnvCheckSignals`, `TVMFFIEnvRegisterCAPI`) and module-scoped APIs (`TVMFFIEnvModLookupFromImports`, `TVMFFIEnvModRegisterContextSymbol`, `TVMFFIEnvModRegisterSystemLibSymbol`) were moved out of core `c_api.h` into `extra/c_env_api.h` (commit `023ea44`). Stream context APIs (`TVMFFIEnvSetCurrentStream`, `TVMFFIEnvGetCurrentStream`; renamed from `TVMFFIEnvSetStream`/`TVMFFIEnvGetStream` in commit `a08fa6e`) and DLPack allocator APIs (`TVMFFIEnvSetDLPackManagedTensorAllocator`, `TVMFFIEnvGetDLPackManagedTensorAllocator`, `TVMFFIEnvTensorAlloc`) are also in `extra/c_env_api.h`. The module-scoped APIs use the `TVMFFIEnvMod*` prefix to distinguish from host-environment `TVMFFIEnv*` APIs (see [ADR-0013](.memory/ADRs/0013-module-scoped-c-api-naming.md)).

## Alternatives Considered
### C++ ABI directly
- Pros: More expressive. Template support.
- Cons: Not portable across compilers. Name mangling varies. vtable layout is compiler-specific. Exceptions are not interoperable.

### Protocol Buffers / gRPC as the ABI
- Pros: Schema-defined. Cross-language.
- Cons: Serialization overhead for every call. Not suitable for in-process FFI. Requires a runtime dependency.

### COM / XPCOM style interfaces
- Pros: Stable ABI. Reference counted. QueryInterface for type checking.
- Cons: Windows-centric (COM). Complex. Requires interface IDs. Over-engineered for this use case.

## Trade-offs
- **Optimized**: ABI stability (C structs with fixed layout), cross-platform compatibility (C linkage), minimal runtime dependency (just a shared library).
- **Sacrificed**: Expressiveness (no templates, no overloading, no namespaces in the C ABI), discoverability (callers must know the function names), compile-time type safety at the ABI boundary.

## Interfaces and Compatibility
- **Public C ABI**: Core operations in `include/tvm/ffi/c_api.h`. Extended environment APIs (signals, C API registration, stream context, module symbol management) in `include/tvm/ffi/extra/c_env_api.h`. Foreign language bindings that need environment APIs must include both headers.
- **DLPack dependency**: `c_api.h` includes `<dlpack/dlpack.h>` for tensor types. DLPack version compatibility is a transitive requirement.
- **Version contract**: `TVMFFIGetVersion()` returns `{major, minor, patch}`. Bindings should check `major == expected_major`.
- **Rust consumer**: The `tvm-ffi-sys` crate (`rust/tvm-ffi-sys/src/c_api.rs`) hand-writes `#[repr(C)]` mirrors of all C ABI structs and `extern "C"` declarations for all `TVMFFI*` functions. The Rust crate links `libtvm_ffi` dynamically via `tvm-ffi-config --libdir`. See [design 0017](.memory/designs/0017-rust-ffi-binding-layer.md) and [ADR-0027](.memory/ADRs/0027-hand-written-repr-c-over-bindgen.md).

## Failure Modes and Mitigations
- **ABI version mismatch**: A binding compiled against version X links with library version Y. Mitigated by `TVMFFIGetVersion` check at initialization.
- **Symbol not found**: A binding tries to resolve a function added in a newer minor version. Mitigated by checking minor version before calling new functions.
- **Struct layout mismatch**: A binding assumes a different field offset than the library. Mitigated by the ABI stability guarantee within a major version. If violated, this is a critical bug.
- **Memory leak from missed DecRef**: A binding forgets to call `TVMFFIObjectDecRef`. Mitigated by wrapping handles in RAII wrappers in each binding language.

## Observability and Validation
- `tests/cpp/test_ffi_c_api.cc`: Tests C ABI functions directly.
- The version triple is hardcoded as `TVM_FFI_VERSION_{MAJOR,MINOR,PATCH}` macros.
- All C ABI functions are tested indirectly through C++ API tests (which call the C ABI under the hood).

## Migration and Rollout
- Foundational from the root commit. The C ABI is the contract between the core library and all foreign language bindings.
- Breaking changes require a major version bump. Adding new functions or extending structs at the end requires a minor version bump.

## Diagrams
- [.memory/diagrams/0001-any-value-memory-layout.md](.memory/diagrams/0001-any-value-memory-layout.md) (TVMFFIAny layout)
- [.memory/diagrams/0002-object-type-hierarchy.md](.memory/diagrams/0002-object-type-hierarchy.md) (TVMFFIObject layout)
- [.memory/diagrams/0003-function-call-flow.md](.memory/diagrams/0003-function-call-flow.md) (safe-call flow)

## Related ADRs
- [.memory/ADRs/0001-type-index-partitioning.md](.memory/ADRs/0001-type-index-partitioning.md)
- [.memory/ADRs/0002-combined-refcount-in-single-u64.md](.memory/ADRs/0002-combined-refcount-in-single-u64.md)
- [.memory/ADRs/0003-small-string-optimization-in-any.md](.memory/ADRs/0003-small-string-optimization-in-any.md)
- [.memory/ADRs/0004-tls-error-propagation.md](.memory/ADRs/0004-tls-error-propagation.md)
- [.memory/ADRs/0006-container-abi-data-deleter.md](.memory/ADRs/0006-container-abi-data-deleter.md)
- [.memory/ADRs/0007-ffi-type-key-namespace.md](.memory/ADRs/0007-ffi-type-key-namespace.md)
- [.memory/ADRs/0009-extra-api-isolation.md](.memory/ADRs/0009-extra-api-isolation.md)
- [.memory/ADRs/0010-string-bytes-as-value-types.md](.memory/ADRs/0010-string-bytes-as-value-types.md)
- [.memory/ADRs/0013-module-scoped-c-api-naming.md](.memory/ADRs/0013-module-scoped-c-api-naming.md)
- [.memory/ADRs/0016-reorder-static-type-indices.md](.memory/ADRs/0016-reorder-static-type-indices.md)
- [.memory/ADRs/0017-opaque-pyobject.md](.memory/ADRs/0017-opaque-pyobject.md)
- [.memory/ADRs/0026-tvmffiobject-header-reorder-combined-refcount.md](.memory/ADRs/0026-tvmffiobject-header-reorder-combined-refcount.md)

## Evidence Matrix
- c_api.h (718+ LOC) -> `.memory/commits/2025-05-06-7d34eb8abfe987bf0031e4d4ff479895d867a966.md` + `7d34eb8` + `include/tvm/ffi/c_api.h`
- Version 0.1.9 -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 61-65
- TVMFFIAny struct (16 bytes) -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 280-333
- TVMFFIObject struct (24 bytes) -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 227-278
- TVMFFISafeCallType (handle parameter rename) -> `7d34eb8` + `include/tvm/ffi/c_api.h`; `.memory/commits/2025-06-05-11a4a02d83e41ca4ccaf81df59d14b75309f65e9.md` + `11a4a0`
- Symbol visibility macros (TVM_FFI_DLL, TVM_FFI_DLL_EXPORT, TVM_FFI_WEAK) -> `7d34eb8` + `include/tvm/ffi/c_api.h`; `.memory/commits/2025-05-24-8a009885a44a132baba886bead112924aef0d45f.md` + `8a0098`; `.memory/commits/2025-05-29-192f196ec7b342677217e854fae7e7970fa100c5.md` + `192f19`
- Emscripten support -> `7d34eb8` + `include/tvm/ffi/c_api.h` lines 42-45
- DLDataType ABI fix (pass by pointer) -> `.memory/commits/2025-05-11-076ac23e994e404c40a789ccc42a1497a31e1280.md` + `076ac2` + `include/tvm/ffi/c_api.h`
- TVMFFIFieldInfo enrichment (offset, size, alignment, type_schema, flags, doc, default_value) -> `.memory/commits/2025-06-15-1a856886c8c14c6271e156d1ce4d76335d42f0ff.md` + `1a8568`; `.memory/commits/2025-06-16-a419ed175aac752a3df2ee73faad360a2824ecd8.md` + `a419ed`
- TVMFFITypeMetadata struct (was TVMFFITypeExtraInfo) -> `a419ed` + `include/tvm/ffi/c_api.h`; renamed in `162d600`
- TVMFFITypeInfo ancestor pointer change -> `.memory/commits/2025-06-19-837800e772d8c1dfa3a00a9f23f096487c96bd37.md` + `837800`
- TVM_FFI_ALWAYS_LOG_BEFORE_THROW flag -> `076ac2` + `include/tvm/ffi/error.h`
- C API function renames (TVMFFITypeGetOrAllocIndex, TVMFFITypeRegisterField, TVMFFIErrorSetRaisedFromCStr) -> `a419ed`
- `TVMFFISEqHashKind` enum (6 values) and `TVMFFITypeMetadata.structural_eq_hash_kind` -> `.memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md` + `9445fe7` + `include/tvm/ffi/c_api.h`
- `TVMFFITypeExtraInfo` renamed to `TVMFFITypeMetadata`, `TVMFFITypeAttrColumn` struct, `TVMFFITypeRegisterAttr`/`TVMFFIGetTypeAttrColumn` C APIs -> `.memory/commits/2025-07-22-162d6009252dd44950a9aa9b890cbbce6b8e5155.md` + `162d600`
- `kTVMFFISEqHashKindCustomTreeNode` removed -> `.memory/commits/2025-07-28-59a837eb4040843051706cbf5c7b71725fd65364.md` + `59a837e`
- `kTVMFFISmallStr=11`, `kTVMFFISmallBytes=12`, `TVMFFIAny.zero_padding`/`small_str_len` union, `TVMFFIDataTypeToString` signature change -> `.memory/commits/2025-08-04-49e2ed4a169918d346fe8f96c208a4cec56cf3e8.md` + `49e2ed4`
- SEqHash field flag bits (`kTVMFFIFieldFlagBitMaskSEqHashIgnore`, `kTVMFFIFieldFlagBitMaskSEqHashDef`) -> `.memory/commits/2025-07-19-9445fe734839cffc8bdf881788528b7763f7be03.md` + `9445fe7`
- `ffi::Module` with static type index `kTVMFFIModule = 73` -> `.memory/commits/2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md` + `538bef4` + `include/tvm/ffi/extra/module.h`
- `TVMFFIEnvModLookupFromImports`, `TVMFFIEnvModRegisterContextSymbol`, `TVMFFIEnvModRegisterSystemLibSymbol` C ABI -> `.memory/commits/2025-08-17-538bef49b4daa91970f0f9cea137acdcb696562a.md` + `538bef4`; renamed with `Mod` infix -> `.memory/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md` + `023ea44`
- `TVMFFIEnvSetCurrentStream`, `TVMFFIEnvGetCurrentStream` (stream context C ABI; renamed from `TVMFFIEnvSetStream`/`TVMFFIEnvGetStream` in `a08fa6e`) -> `.memory/commits/2025-08-19-0daaffedd23982ea09f8c38fec4eef1cca1d8cac.md` + `0daaffe`; `.memory/commits/2025-09-09-a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806.md` + `a08fa6e` + `include/tvm/ffi/extra/c_env_api.h`
- `TVMFFIEnvCheckSignals`, `TVMFFIEnvRegisterCAPI` moved from `c_api.h` to `extra/c_env_api.h` -> `.memory/commits/2025-08-20-023ea448be6e86e09f4ebaba5a235ee53f3cdeef.md` + `023ea44`
- `TVMFFIEnvRegisterCAPI` parameter type changed from `const TVMFFIByteArray*` to `const char*` -> `023ea44`
- `EnvCAPIRegistry` moved from `src/ffi/function.cc` to `src/ffi/extra/env_c_api.cc` -> `023ea44`
- Core API declarations reordered in `c_api.h` (core APIs moved earlier) -> `023ea44`
- `TVMFFITraceback` signature changed: added 4th parameter `int cross_ffi_boundary` (0 = stop at boundary, 1 = cross boundary). `TVM_FFI_TRACEBACK_HERE` internal macro removed, replaced by direct `TVMFFITraceback(file, line, sig, 0)` calls in `TVM_FFI_THROW` and `TVM_FFI_LOG_AND_THROW` -> `.memory/commits/2025-08-24-2d41a5115f6a91e2781012a3379f9626bc9e18a1.md` + `2d41a51` + `include/tvm/ffi/error.h`
- Traceback frame filtering improved: `ShouldExcludeFrame` checks symbol names first (more reliable), adds `TVMFFITraceback`, `tvm::ffi::Function`, `tvm::ffi::details::` symbol exclusions. `ShouldStopTraceback` renamed to `DetectFFIBoundary`, adds `slot_tp_call` and `object_is_not_callable` Python ABI detection. `TracebackStorage` gains `skip_frame_count` and `stop_at_boundary` fields -> `2d41a51` + `src/ffi/traceback.h`
- MSVC pragma fix: `#pragma disagnostic push/pop` corrected to `#pragma warning(push/pop)` -> `2d41a51` + `include/tvm/ffi/error.h`
- Static type index reorder (Shape=69, NDArray=70, Array=71, Map=72) -> `.memory/commits/2025-08-30-777cf8d51f2054d96e0413b7406ed38ef43a7b39.md` + `777cf8d` + `include/tvm/ffi/c_api.h`
- `override` -> `allow_override` parameter rename in `TVMFFIFunctionSetGlobal` -> `777cf8d` + `include/tvm/ffi/c_api.h`
- Module metadata API: `GetFunctionMetadata`, `tvm_ffi_metadata_prefix` symbol -> `777cf8d` + `include/tvm/ffi/extra/module.h`
- TVMFFIObject header split refcounts (strong_ref_count + weak_ref_count) -> `.memory/commits/2025-09-01-ca9c3d10bb9640bffb972302f7064e49e592a526.md` + `ca9c3d1` + `include/tvm/ffi/c_api.h`
- `TVMFFIObjectFree` renamed to `TVMFFIObjectDecRef` -> `ca9c3d1` + `include/tvm/ffi/c_api.h`
- `TVMFFIObjectDeleterFlagBitMask` (Strong=1, Weak=2, Both=3) -> `ca9c3d1` + `include/tvm/ffi/c_api.h`
- `kTVMFFIOpaquePyObject = 74` type index -> `.memory/commits/2025-09-05-91d69f0658eef18fd9c99d4ac195ad5319db3787.md` + `91d69f0` + `include/tvm/ffi/c_api.h`
- `TVMFFIObjectCreateOpaque` C API -> `91d69f0` + `include/tvm/ffi/c_api.h`
- `TVMFFIOpaqueObjectCell` struct -> `91d69f0` + `include/tvm/ffi/c_api.h`
- `__tvm_ffi_` symbol prefix for exported functions -> `.memory/commits/2025-09-06-40e8a519f5270dfb18436b2f26c2d691cf24c9c1.md` + `40e8a51` + `include/tvm/ffi/extra/module.h`
- NDArray->Tensor rename (kTVMFFINDArray->kTVMFFITensor, TVMFFINDArray*->TVMFFITensor*) -> `.memory/commits/2025-09-06-3a551d83f7c05106fa8033a61970a5ce34aa8aef.md` + `3a551d8` + `include/tvm/ffi/c_api.h`
- `TVMFFIEnvSetStream`->`TVMFFIEnvSetCurrentStream` rename -> `.memory/commits/2025-09-09-a08fa6eb0d7a67de9f5a4354d9a1fe41c0dfa806.md` + `a08fa6e` + `include/tvm/ffi/extra/c_env_api.h`
- `DLPackTensorAllocator` callback type, `TVMFFIEnvSetDLPackManagedTensorAllocator`/`TVMFFIEnvGetDLPackManagedTensorAllocator` -> `.memory/commits/2025-09-12-f81ab9c2.md` + `f81ab9c2` + `include/tvm/ffi/extra/c_env_api.h`
- `TVMFFIStringFromByteArray`, `TVMFFIBytesFromByteArray` C APIs -> `.memory/commits/2025-09-13-043d9f64.md` + `043d9f64` + `include/tvm/ffi/c_api.h`, `src/ffi/object.cc`
- `v_char32` removed from `TVMFFIAny` union -> `.memory/commits/2025-09-14-c100338de52825097ddc44bbac3d03a92f45b33a.md` + `c100338` + `include/tvm/ffi/c_api.h`
- `DLPackTensorAllocator` moved inside `extern "C"` block, `DLManagedTensorVersioned` forward decl added -> `c100338` + `include/tvm/ffi/c_api.h`
- Pure C example (`__tvm_ffi_add_one_c`) demonstrating C ABI usage -> `c100338` + `examples/quick_start/src/add_one_c.c`
- TVMFFIObject header reorder: refcounts first (torch alignment) -> `.memory/commits/2025-09-25-13436f01.md` + `13436f0` + `include/tvm/ffi/c_api.h`
- TVMFFIObject combined_ref_count u64 (strong lower 32, weak upper 32) -> `.memory/commits/2025-09-26-43d13e86.md` + `43d13e8` + `include/tvm/ffi/c_api.h`
- TVMFFIFunctionCell gains `void* cpp_call` field -> `.memory/commits/2025-09-29-4fe8b2b7.md` + `4fe8b2b` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/function.h`
- `TVM_FFI_CHECK(cond, ErrorKind)` macro -> `.memory/commits/2025-09-28-327e8cc6.md` + `327e8cc`; `.memory/commits/2025-09-29-ae06434d.md` + `ae06434` + `include/tvm/ffi/error.h`
- `TVMFFIFieldInfo.type_schema` -> `metadata` rename, `ModuleObj::GetFunctionDoc` -> `.memory/commits/2025-10-01-935a5a07.md` + `935a5a0` + `include/tvm/ffi/c_api.h`, `include/tvm/ffi/extra/module.h`
- Rust `#[repr(C)]` ABI struct mirrors (hand-written, not bindgen) -> `.memory/commits/2025-10-01-09477ce10de566f8cf511cce7dfe56e77759f100.md` + `09477ce` + `rust/tvm-ffi-sys/src/c_api.rs`
- `TVMFFIVersion` struct and `TVMFFIGetVersion()` API -> `.memory/commits/2025-10-18-f0058a9e.md` + `f0058a9e` + `include/tvm/ffi/c_api.h`, `src/ffi/object.cc`
- `TVM_FFI_VERSION_MAJOR/MINOR/PATCH` macros (initially 0.1.0) -> `f0058a9e` + `include/tvm/ffi/c_api.h`

## Open Questions
- Should the C ABI include a function to query ABI feature flags (e.g., "supports weak refs", "supports reflection")?
- Should there be a separate "minimal ABI" header for lightweight embeddings?

## Confidence and Risk
- Confidence: high
- Residual risks: The DLPack transitive dependency means DLPack ABI changes could affect TVM FFI. The version check is advisory (bindings must implement it; the library does not enforce it).
