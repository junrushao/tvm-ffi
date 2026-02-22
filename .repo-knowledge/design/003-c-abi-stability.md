# C ABI Stability

- Doc ID: 003-c-abi-stability
- Status: Approved
- Last Updated: 2025-12-29
- Owners: Tianqi Chen

## Overview

The TVM FFI exposes a stable C ABI (`c_api.h`) to enable cross-language
interop (Python/Cython, Rust, JavaScript/Wasm). This document covers the C ABI
design principles established in May 2025, including the struct-by-pointer
convention, the DLL visibility model, and compiler compatibility fixes.

## Key Design

### Struct-by-pointer convention

Passing C structs by value across shared-library boundaries is
ABI-hazardous: different compilers and calling conventions disagree on whether
small structs are passed in registers or on the stack. The FFI adopts a
**pass-by-pointer** rule for all struct-typed C API parameters.

Concrete fix (`076ac23`): `TVMFFIDataTypeToString` was changed from accepting
`DLDataType dtype` (by value) to `const DLDataType* dtype` (by pointer). This
resolved ABI mismatches observed in the WebAssembly/Emscripten target.

### DLL visibility model

Three tiers of symbol visibility:

1. **`TVM_FFI_DLL`** -- Context-dependent. When building the shared library
   (`TVM_FFI_EXPORTS` defined), it expands to `dllexport` / `visibility("default")`.
   When consuming the library, it expands to `dllimport` / nothing.

2. **`TVM_FFI_DLL_EXPORT`** -- Always export. Used by module libraries and addons
   that must expose symbols regardless of `TVM_FFI_EXPORTS` state. Added in `192f196`.

3. **`TVM_FFI_WEAK`** -- Weak linkage. Allows a symbol to be optionally overridden
   by addons without causing multiple-definition linker errors. Uses
   `__attribute__((weak))` (GCC/Clang) or `__declspec(selectany)` (MSVC).
   Added in `8a00988`.

### Error logging for environments without exceptions

`TVM_FFI_ALWAYS_LOG_BEFORE_THROW` (default 0) is a compile-time flag that, when
set to 1, causes every `TVM_FFI_THROW` invocation to log the error message
before throwing. This is useful in WebAssembly environments where exceptions
may be caught silently and the log output is the only diagnostic channel.
Added in `076ac23`.

### Reflection struct ABI evolution (June 2025)

Several C ABI structs were extended or changed during the June 2025 reflection
buildout:

- **`TVMFFIFieldInfo`** (`1a85688`): Expanded with `doc`, `type_schema`,
  `flags`, `size`, `alignment`, `offset`, `getter` (`TVMFFIFieldGetter`),
  `setter` (`TVMFFIFieldSetter`), `default_value`, and
  `field_static_type_index` fields. ABI-breaking for any code reading this
  struct directly.
- **`TVMFFIMethodInfo`** (`1a85688`): New struct for method metadata with
  `name`, `doc`, `type_schema`, `flags`, `method` fields.
- **`TVMFFITypeInfo::type_acenstors`** (`837800e`): Changed from `const int32_t*`
  to `const struct TVMFFITypeInfo**`. ABI-breaking for C code reading this field.
- **`TVMFFITypeExtraInfo`** (`a419ed1`): New struct with `doc`
  (`TVMFFIByteArray`), `creator` (`TVMFFIObjectCreator`), `total_size`
  (`int64_t`). Registered via new `TVMFFITypeRegisterExtraInfo` C API function.
- **`TVMFFIFieldFlagBitMask`** (`1a85688`): New enum with
  `kTVMFFIFieldFlagBitMaskWritable`, `kTVMFFIFieldFlagBitMaskHasDefault`,
  `kTVMFFIFieldFlagBitMaskIsStaticMethod` bits.

These changes are part of a pre-1.0 ABI stabilization effort. All consuming code
must be recompiled after these changes.

### TypeExtraInfo renamed to TypeMetadata (July 2025)

`TVMFFITypeExtraInfo` was renamed to `TVMFFITypeMetadata` and
`TVMFFITypeRegisterExtraInfo` was renamed to `TVMFFITypeRegisterMetadata`
(`9445fe7`, `162d600`). The rationale was that "metadata" is a more precise
name than "extra info" for the type information structure. This is a breaking
C ABI change requiring recompilation of all pre-compiled binaries.

### TypeAttrColumn C ABI (July 2025)

A new extensible per-type attribute mechanism was added to the C ABI:

- **`TVMFFITypeAttrColumn`** (`9445fe7`): A struct representing a column of
  per-type attribute values, indexed by type index. Each column stores either
  function or constant values.
- **`TVMFFITypeRegisterAttr`** (`9445fe7`): C API function to register a
  per-type attribute value.
- **`TVMFFIGetTypeAttrColumn`** (`9445fe7`): C API function to retrieve a
  `TVMFFITypeAttrColumn` by name.

This column-store pattern enables extensible type traits (e.g., custom
structural equal/hash functions) without modifying the fixed `TVMFFITypeMetadata`
struct.

### TVM_FFI_EXTRA_CXX_API relocation (July 2025)

The `TVM_FFI_EXTRA_CXX_API` macro block (21 lines) was moved from `c_api.h` to
`include/tvm/ffi/extra/base.h` (`3fc0391`). This keeps `c_api.h` focused on
C-only definitions and establishes the core/extra boundary at the header level.

### Small string/bytes type indices (August 2025)

Two new type indices, `kTVMFFISmallStr` and `kTVMFFISmallBytes`, were added to
the C ABI (`49e2ed4`). These allow short strings and byte sequences to be stored
inline in the `TVMFFIAny` union, avoiding heap allocation. A `zero_padding`
field was added to the union to ensure unused bytes are zeroed for correct
equality comparison.

This is an ABI-breaking change: all pre-compiled binaries must be recompiled,
and type-index checks must account for both heap and inline variants (e.g.,
`kTVMFFIStr || kTVMFFISmallStr`).

### Map MSB tagging for layout dispatch (August 2025)

The `MapObj::slots_` field gained MSB-based tagging (`03e8a6b`) to distinguish
`SmallMapObj` from `DenseMapObj` at runtime. Previously, dispatch compared
`slots_ <= SmallMapObj::kMaxSize`. The MSB tag (`kSmallTagMask = 1ULL << 63`)
decouples the small/dense threshold from the dispatch logic, allowing the
boundary to be changed in the future without ABI breaks.

New accessor methods: `MapObj::IsSmallMap()`, `SmallMapObj::NumSlots()`,
`SmallMapObj::SetSlotsAndSmallLayoutTag()`, `DenseMapObj::NumSlots()`,
`DenseMapObj::SetSlotsAndDenseLayoutTag()`. Direct access to `slots_` is
discouraged.

### ABI type ordering pre-freeze (August 2025)

The type index ordering in `c_api.h` was adjusted (`777cf8d`) to place simple
C-ABI objects before complex C++-dependent ones, ahead of the ABI freeze.
This is an ABI-breaking change requiring recompilation. A `GetFunctionMetadata`
virtual method stub was added to `ModuleObj` for future per-function metadata
access from dynamically loaded modules.

### Env API symbol renames (August 2025)

Module-related C API symbols were renamed (`023ea44`) to use a `Mod` infix:

| Old name | New name |
|----------|----------|
| `TVMFFIEnvLookupFromImports` | `TVMFFIEnvModLookupFromImports` |
| `TVMFFIEnvRegisterContextSymbol` | `TVMFFIEnvModRegisterContextSymbol` |
| `TVMFFIEnvRegisterSystemLibSymbol` | `TVMFFIEnvModRegisterSystemLibSymbol` |

`TVMFFIEnvCheckSignals` and `TVMFFIEnvRegisterCAPI` were moved from the core
`function.cc` to `src/ffi/extra/env_c_api.cc`, now requiring
`TVM_FFI_USE_EXTRA_CXX_API=ON`. The `TVMFFIEnvRegisterCAPI` signature changed
from `(const TVMFFIByteArray*, void*)` to `(const char*, void*)`.

### Container ABI stabilization (June 2025)

`ArrayObj` storage was changed from an inplace array (via `InplaceArrayBase`)
to a separately managed `data_` pointer with `data_deleter_` (`7e0a4b3`). This
decouples the container storage from the object header, enabling future storage
changes without breaking the object header ABI. `MapObj` internals were similarly
restructured. `TupleObj` dropped its `InplaceArrayBase` dependency.

These are ABI-breaking changes; all shared libraries must be rebuilt.

### Atomic refcount inlining (June 2025)

`IncRef`, `DecRef`, and `use_count` atomic operations were inlined directly into
the `Object` class (`d5209f0`), removing the shared helper functions
`AtomicIncrementRelaxed`, `AtomicDecrementRelAcq`, `AtomicLoadRelaxed` from
`base_details.h`. This eliminates function call overhead on the hot refcount
path. The change is ABI-compatible (no struct layout changes) but requires
recompilation.

### Build model: always-on registry (June 2025)

The `TVM_FFI_BUILD_REGISTRY` CMake option was removed (`a419ed1`). The registry
is now always included in the build, simplifying the configuration matrix.
Build systems that previously used `-DTVM_FFI_BUILD_REGISTRY=ON/OFF` must
remove that flag.

### Error cause chaining (January 2026)

`TVMFFIErrorCell` was extended (`4c712ca`) with two new optional fields:
`cause_chain` (`TVMFFIObjectHandle`) and `extra_context` (`TVMFFIObjectHandle`),
appended at the end of the struct for ABI-backward compatibility. A new C API
function `TVMFFIErrorCreateWithCauseAndExtraContext` was added. On the C++ side,
`Error` gained constructors accepting `optional<Error>` and
`optional<ObjectRef>`, plus `cause_chain()` and `extra_context()` accessor
methods. The `extra_context` field is designed for attaching frontend-specific
error objects (e.g., Python exception state) to enable cross-language exception
chaining (`raise B from A`).

### Umbrella header (January 2026)

`include/tvm/ffi/tvm_ffi.h` (`8caa0cb`) was introduced as an umbrella header
following the nanobind/pybind11 convention. It includes `any.h`,
`base_details.h`, `c_api.h`, `error.h`, `function.h`, `object.h`, and key
container headers. Individual headers remain functional; the umbrella header
is optional.

### CUDA API isolation (January 2026)

The `TVM_FFI_CHECK_CUDA_ERROR` macro was split (`10cb004`): the runtime-API-only
variant remains in `base.h`; the driver/runtime-unified variant was renamed to
`TVM_FFI_CHECK_CUBIN_LAUNCHER_CUDA_ERROR` and confined to `internal/unified_api.h`
and `cubin_launcher.h`. This prevents general code from accidentally depending
on CUDA driver headers.

### CMake cross-compilation support (January 2026)

Three successive commits (`0d157dc`, `3b4a532`, `dcd07cf`) made
`find_package(Threads)` optional and added explicit CMake options, enabling
bare-metal and WASM cross-compilation targets. `TVM_FFI_USE_THREADS` (default
ON) and `TVM_FFI_USE_DL_LIBS` (default ON) were added to allow explicit
control over these dependencies.

### UBSan correctness fixes (January 2026)

Two undefined-behavior issues flagged by UBSan were resolved (`b508698`):
(a) `ObjectUnsafe::GetObjectOffsetToSubclass` now uses `__builtin_offsetof`
instead of null-pointer member access; (b) `String` copy guards `std::memcpy`
with `if (size > 0)` to avoid passing a null source pointer with size 0.

### Non-null-terminated DType parsing fix (January 2026)

`StringViewToDLDataType_` in `src/ffi/dtype.cc` was rewritten (`ae30cd6`) to
replace `strtoul()` calls (which require null-terminated strings) with bounded
manual digit parsers. The original code passed `std::string_view::data()` to
`strtoul()` without a null terminator, causing out-of-bounds reads. This was a
critical security/correctness fix, particularly affecting Electron apps due to
Chromium's aggressive memory reuse.

### Expected<T> for exception-free error handling (February 2026)

`ffi::Expected<T>` (`0a9d4b6`, `include/tvm/ffi/expected.h`, 236 lines)
provides a C++23 `std::expected`-style error container for callers that cannot
use exceptions (embedded systems, performance-critical paths). The companion
`Function::CallExpected<T>()` method (`include/tvm/ffi/function.h`) enables
calling FFI functions without exceptions, returning `Expected<T>` with either
the result or an `Error`.

### New container type indices (February 2026)

Two new type indices were added to `c_api.h`:
- `kTVMFFIList` (`9513c2f`): type index for `ListObj` (mutable sequence).
- `kTVMFFIDict` (`c1af3b3`): type index for `DictObj` (mutable map).

### New field flag bits (February 2026)

- `kTVMFFIFieldFlagBitMaskDefaultFromFactory = 1 << 5` (`5e564cd`): indicates
  that `TVMFFIFieldInfo::default_value_or_factory` holds a callable factory
  rather than a static default value.
- `kTVMFFIFieldFlagBitMaskReprOff = 1 << 6` (`b648c5d`): indicates that a
  field should be excluded from repr output.

### Field info struct rename (February 2026)

`TVMFFIFieldInfo::default_value` was renamed to `default_value_or_factory`
(`5e564cd`). This is an ABI-breaking change requiring recompilation of all
consumers that read this struct field.

### CHECK macro completion (February 2026)

`DCHECK`, `DCHECK_EQ` (debug-only), and typed `CHECK_EQ` with error type
template parameter were added to `error.h` (`35cbc32`). `DCHECK` macros are
no-ops in release builds.

### Compiler compatibility

`nullptr_t` was qualified to `std::nullptr_t` in `string.h` (`eda2b71`) to fix
a compilation error under Clang 20, which enforces stricter qualification rules
for types from `<cstddef>`.

`std::aligned_storage` (deprecated in C++23) was replaced with
`struct alignas(T) { char data[sizeof(T)]; }` in `memory.h` (`e909486`) for
forward compatibility.

### NDArray renamed to Tensor (September 2025)

The C++ class `NDArray`/`NDArrayObj` was renamed to `Tensor`/`TensorObj` and
the header `ndarray.h` was renamed to `tensor.h` (`3a551d8`). The Python class
`tvm_ffi.NDArray` was renamed to `tvm_ffi.Tensor`. This is an ABI- and
API-breaking rename touching approximately 30 files across `include/`,
`src/`, `python/`, `tests/`, `docs/`, and `examples/`.

### Opaque PyObject type index (September 2025)

A new type index constant `kTVMFFIOpaquePyObject = 74` was added to `c_api.h`
(`91d69f0`). A `TVMFFIOpaqueObjectCell` struct wraps a `void* handle`, and
the new C API function `TVMFFIObjectCreateOpaque(void* handle,
TVMFFIObjectHandle* out)` creates opaque objects that carry arbitrary Python
objects through the FFI layer without losing type identity.

### Symbol prefix for FFI exported functions (September 2025)

The `Library` virtual interface was changed (`40e8a51`): `GetSymbol(const
char*)` became `GetSymbol(const String&)`, and a new pure virtual
`GetSymbolWithSymbolPrefix(const String& name)` was added. The module entry
symbol was standardized to `__tvm_ffi_main` (dropping the trailing `__`).
`DSOLibrary` and `SystemLibrary` both implement the new virtual method.

### UnsafeInit tag for ObjectRef construction (September 2025)

A `struct UnsafeInit {}` tag type was introduced (`472e10c`). The
`TVM_FFI_DEFINE_OBJECT_REF_METHODS` macros now require `UnsafeInit` for
unsafe/null construction, replacing the implicit `ObjectPtr<Object>` path.
`ObjectUnsafe::ObjectRefFromObjectPtr<T>` provides a controlled escape hatch.
This is an API-breaking change for all `ObjectRef`-derived classes.

### Object declaration macro consolidation (September 2025)

Object declaration macros were renamed and consolidated (`a08fa6e`):

| Old macro | New macro |
|-----------|-----------|
| `TVM_FFI_DECLARE_BASE_OBJECT_INFO(T, Parent)` | `TVM_FFI_DECLARE_OBJECT_INFO("key", T, Parent)` |
| `TVM_FFI_DECLARE_FINAL_OBJECT_INFO(T, Parent)` | `TVM_FFI_DECLARE_OBJECT_INFO_FINAL("key", T, Parent)` |
| `TVM_FFI_DECLARE_STATIC_OBJECT_INFO(T, Parent)` | `TVM_FFI_DECLARE_OBJECT_INFO_STATIC("key", T, Parent)` |

The type key is now embedded directly in the macro call, eliminating the
separate `_type_key` assignment. The `ObjectRef` definition macros were also
consolidated, using `_type_mutable` to select const vs mutable `operator->`.

### Stream exchange protocol (September 2025)

A generic stream exchange protocol (`db98729`) allows non-torch tensors to
communicate their associated compute stream via a `__tvm_ffi_env_stream__()`
method. The C API function `TVMFFIEnvSetStream` was renamed from
`TVMFFIEnvSetCurrentStream`. New DLPack device constants `kDLMAIA` and
`kDLTrn` were added.

### Backtrace storage order change (September 2025)

Internal backtrace storage was changed to "most recent call first" (`6f020c1`)
for O(1) append during error propagation. The `TVMFFIErrorCreate` C API
signature was updated (ABI-breaking). Source files were renamed from
`traceback.*` to `backtrace.*`. User-visible error output is unchanged (the
rendering function reverses on demand).

### DLPack exchange speed and behavior (September 2025)

A `DLPackExchangeAPI` struct was introduced (`f81ab9c`) containing C-level
function pointers for high-speed DLPack tensor exchange:
`managed_tensor_allocator`, `managed_tensor_from_py_object_no_sync`, and
`managed_tensor_to_py_object_no_sync`. This bypasses Python object protocol
overhead on the tensor exchange hot path. The `stream_context.cc` source
file was replaced by `env_context.cc`. A `func.release_gil` option was added
for Python `Function` objects.

### DLPack exchange API rename (September 2025)

The DLPack exchange API naming was standardized (`4dee97f`). The Python-side
attribute for declaring exchange API support was renamed to
`__dlpack_c_exchange_api__` (with `__c_dlpack_exchange_api__` as a fallback).
The C++ struct was renamed to `DLPackExchangeAPI`. External types using the
old attribute names must be updated.

### TVMFFIObject header reorder (September 2025)

The `TVMFFIObject` struct fields were reordered (`13436f0`) to place
`strong_ref_count` and `weak_ref_count` (both `uint32_t`) before
`type_index` and `__padding`, aligning with PyTorch's `intrusive_ptr` layout
for better cache performance. The shared `type_index` position with
`TVMFFIAny.type_index` was intentionally broken. This is an ABI-breaking
change.

### Combined reference count (September 2025)

The two separate `uint32_t` counters (`strong_ref_count`,
`weak_ref_count`) were merged into a single `uint64_t combined_ref_count`
(`43d13e8`). Strong occupies the lower 32 bits, weak the upper 32 bits.
Constants `kCombinedRefCountStrongOne`, `kCombinedRefCountWeakOne`,
`kCombinedRefCountBothOne` enable single-atomic-operation detection of the
common case (both going to zero). This eliminates a separate weak-counter read
in the `DecRef` hot path, inspired by a similar PyTorch optimization.

### TVMFFIFunctionCell cpp_call field (September 2025)

A `void* cpp_call` field was added to `TVMFFIFunctionCell` (`4fe8b2b`)
alongside the existing `safe_call`. The `cpp_call` is the raw C++ throwing
call path for same-DLL calls; `safe_call` is the exception-catching path
for cross-DLL calls. `FunctionObj::call` private field was removed;
`CallPacked` now checks `cpp_call` first, with fallback to
`CppCallRedirectToSafeCall`. `ImportedFunctionObjImpl` was removed entirely.

### ShapeView and TensorObj minimization (September 2025)

`ffi::ShapeView` was introduced (`8ca0719`) as a lightweight non-owning view
over shape data, and `Tensor::shape()` / `Tensor::strides()` were changed to
return `ShapeView` instead of `Shape`. Internal `TensorObj` fields
(`shape_data_`, `strides_data_`, `cached_dl_managed_tensor_versioned_`) were
removed; shape/strides are now inlined after the object in memory, reducing
heap allocations. New convenience methods `Tensor::data_ptr()`,
`Tensor::ndim()`, `Tensor::numel()` were added.

### type_acenstors typo fix (September 2025)

`TVMFFITypeInfo::type_acenstors` was renamed to `type_ancestors` (`98cb8af`),
fixing a long-standing typo. This is an ABI-breaking change for any external
code reading this struct field by name.

### TVM_FFI_CHECK macro (September 2025)

A new `TVM_FFI_CHECK(cond, ErrorKind)` macro was added to `error.h`
(`327e8cc`, `ae06434`). Unlike `TVM_FFI_ICHECK` (which always throws
`InternalError`), `TVM_FFI_CHECK` throws a user-specified error kind
(e.g., `ValueError`, `IndexError`). The argument order was initially
`(ErrorKind, cond)` and immediately corrected to `(cond, ErrorKind)`.

### DLPack stride normalization removal (September 2025)

DLPack stride normalization was completely removed (`f4a65cd`). Previously
the FFI normalized 1D tensor strides on export (`53ffe5e` restricted this
to 1D only as an interim step). The removal simplifies the DLPack exchange
path and avoids unexpected stride mutations.

### Reflection metadata rename (October 2025)

`TVMFFIFieldInfo.type_schema` and `TVMFFIMethodInfo.type_schema` were renamed
to `metadata` (`935a5a0`). The field now carries arbitrary JSON metadata, not
just type schemas. This is an ABI-breaking change requiring recompilation.

### DLPackExchangeAPI struct (October 2025)

The three separate DLPack function pointer fields were replaced by a unified
`DLPackExchangeAPI` struct (`22a7894`), aligned with DLPack proposal #175.
External tensor types must now provide `__c_dlpack_exchange_api__` instead of
the old three-pointer protocol. This is an ABI-breaking change.

### Tensor allocator API rename (October 2025)

`TVMFFIEnvSetTensorAllocator` was renamed to
`TVMFFIEnvSetDLPackManagedTensorAllocator` and `TVMFFIEnvGetTensorAllocator`
to `TVMFFIEnvGetDLPackManagedTensorAllocator` (`f679fe5`). A new
`TVMFFIEnvTensorAlloc(DLTensor*, TVMFFIObjectHandle*)` C API was added that
keeps tensor metadata allocated inside `libtvm_ffi`. This is an ABI-breaking
change.

### `TVMFFIHandleInitOnce` / `TVMFFIHandleDeinitOnce` (December 2025)

Two new C API functions (`25c25ae`) provide thread-safe, lazy initialization
and deinitialization of static handles without requiring C++ `std::call_once`:

- `TVMFFIHandleInitOnce(void** handle_addr, int (*init_func)(void**))`:
  atomically initializes `*handle_addr` exactly once, even under concurrent
  calls.
- `TVMFFIHandleDeinitOnce(void** handle_addr, int (*deinit_func)(void*))`:
  atomically deinitializes `*handle_addr` exactly once.

Implemented using `__atomic_load_n`/`__atomic_store_n` (GCC/Clang) or
`InterlockedCompareExchangePointerAcquire` (MSVC) for the fast path, with a
static mutex for the slow path. These are usable from DSL runtimes (e.g.,
Rust, MLIR-based frontends) that may not link the C++ stdlib.

### `TVMFFITensorCreateUnsafeView` (December 2025)

`TVMFFITensorCreateUnsafeView(source, prototype, out)` (`8888eb4`) creates
a ref-counted tensor view sharing the source tensor's data memory. The
prototype's shape, strides, and dtype define the view layout. Callers must
validate the prototype themselves (hence "unsafe"). Backs the C++
`Tensor::as_strided` and `TensorView::as_strided` methods.

### Error C API addition (October 2025)

`TVMFFIErrorSetRaisedFromCStrParts` (`550e92f`) was added to set error
messages from C string parts, enabling error reporting from C code that
cannot use C++ exceptions.

### Version 0.1.0 (October 2025)

The version was formally bumped to 0.1.0 (`792dc01`). A Version Query API
was added (`f0058a9`). `TVM_FFI_VERSION_PATCH` was bumped to 1 with the
introduction of `setuptools_scm` (`ac63fb9`).

### Memory allocator: raw aligned alloc (September 2025)

The object allocator switched from `new StorageType` to
`AlignedAlloc<align>(size)` + placement-new (`6fb42a7`). This reduces
over-allocation in `InplaceArray` objects by computing exact allocation sizes.
`AlignedAlloc`/`AlignedFree` helpers handle MSVC/POSIX portability.

### Explicit padding in memory (September 2025)

Object memory padding was explicitly set to zero (`f9179ec`) to ensure
deterministic memory layouts.

## APIs

### C API functions affected

```c
// Before (076ac23):
TVM_FFI_DLL int TVMFFIDataTypeToString(DLDataType dtype, TVMFFIObjectHandle* out);
// After:
TVM_FFI_DLL int TVMFFIDataTypeToString(const DLDataType* dtype, TVMFFIObjectHandle* out);
```

### New C API functions (June 2025)

```c
// Register type-level metadata (total_size, creator, doc).
// Renamed from TVMFFITypeRegisterExtraInfo in July 2025.
TVM_FFI_DLL int TVMFFITypeRegisterMetadata(int32_t type_index, const TVMFFITypeMetadata* info);
```

### New C API functions (September 2025)

```c
// Create an opaque object wrapping an arbitrary pointer.
TVM_FFI_DLL int TVMFFIObjectCreateOpaque(void* handle, TVMFFIObjectHandle* out);
```

### New C API functions (July 2025)

```c
// Register a per-type attribute value.
TVM_FFI_DLL int TVMFFITypeRegisterAttr(int32_t type_index, const TVMFFIByteArray* attr_name,
                                       const TVMFFIAny* attr_value);

// Get a type attribute column by name. Returns NULL if not registered.
TVM_FFI_DLL const TVMFFITypeAttrColumn* TVMFFIGetTypeAttrColumn(const TVMFFIByteArray* attr_name);
```

### New C API functions (December 2025)

```c
// Thread-safe lazy handle initialization (include/tvm/ffi/c_api.h).
TVM_FFI_DLL int TVMFFIHandleInitOnce(void** handle_addr,
                                      int (*init_func)(void**));
TVM_FFI_DLL int TVMFFIHandleDeinitOnce(void** handle_addr,
                                        int (*deinit_func)(void*));

// Tensor strided view creation (include/tvm/ffi/c_api.h).
TVM_FFI_DLL int TVMFFITensorCreateUnsafeView(TVMFFIObjectHandle source,
                                              const DLTensor* prototype,
                                              TVMFFIObjectHandle* out);
```

### New C API functions (January 2026)

```c
// Create an error with cause chain and extra context (include/tvm/ffi/c_api.h).
TVM_FFI_DLL int TVMFFIErrorCreateWithCauseAndExtraContext(
    const TVMFFIByteArray* kind,
    const TVMFFIByteArray* message,
    const TVMFFIByteArray* backtrace,
    TVMFFIObjectHandle cause_chain,
    TVMFFIObjectHandle extra_context,
    TVMFFIObjectHandle* out);
```

### Preprocessor flags

| Flag                            | Default | Purpose                             |
|---------------------------------|---------|--------------------------------------|
| `TVM_FFI_EXPORTS`               | undef   | Set when building the shared library |
| `TVM_FFI_ALWAYS_LOG_BEFORE_THROW` | 0     | Log every error before throwing      |

## Implementation

Key files:
- `include/tvm/ffi/c_api.h` -- C ABI declarations, visibility macros, `TVM_FFI_WEAK`
- `include/tvm/ffi/error.h` -- `TVM_FFI_THROW`, `TVM_FFI_ALWAYS_LOG_BEFORE_THROW`
- `include/tvm/ffi/dtype.h` -- `DLDataTypeToString` wrapper
- `src/ffi/dtype.cc` -- `TVMFFIDataTypeToString` implementation
- `include/tvm/ffi/string.h` -- `std::nullptr_t` fix

## History
- 2025-05-11: `TVMFFIDataTypeToString` changed to pass-by-pointer; `TVM_FFI_ALWAYS_LOG_BEFORE_THROW` added (`076ac23`)
- 2025-05-12: `nullptr_t` -> `std::nullptr_t` for Clang 20 compatibility (`eda2b71`)
- 2025-05-24: `TVM_FFI_WEAK` macro added (`8a00988`)
- 2025-05-29: `TVM_FFI_DLL_EXPORT` macro added (`192f196`)
- 2025-06-05: `TVMFFISafeCallType` parameter renamed `self` to `handle` (`11a4a02`)
- 2025-06-15: `TVMFFIFieldInfo` expanded with metadata fields; `TVMFFIFieldFlagBitMask` added (`1a85688`)
- 2025-06-16: `TVMFFITypeExtraInfo`/`TVMFFITypeRegisterExtraInfo` added; `TVM_FFI_BUILD_REGISTRY` removed (`a419ed1`)
- 2025-06-17: `std::aligned_storage` replaced with `alignas` pattern in `memory.h` (`e909486`)
- 2025-06-18: Atomic refcount inlined into `Object` class (`d5209f0`)
- 2025-06-18: `ArrayObj`/`MapObj`/`TupleObj` ABI stabilized (`7e0a4b3`)
- 2025-06-19: `TVMFFITypeInfo::type_acenstors` changed to pointer-based (`837800e`)
- 2025-07-19: `TVMFFITypeAttrColumn`, `TVMFFITypeRegisterAttr`, `TVMFFIGetTypeAttrColumn` added; `TVMFFITypeExtraInfo` renamed to `TVMFFITypeMetadata` (`9445fe7`)
- 2025-07-22: `TVMFFITypeRegisterExtraInfo` renamed to `TVMFFITypeRegisterMetadata`; `TypeAttrDef` and `TypeAttrColumn` C++ APIs added (`162d600`)
- 2025-07-28: `kTVMFFISEqHashKindCustomTreeNode` removed from C ABI (`59a837e`)
- 2025-07-30: `TVM_FFI_EXTRA_CXX_API` macro moved from `c_api.h` to `extra/base.h` (`3fc0391`)
- 2025-08-04: `kTVMFFISmallStr`, `kTVMFFISmallBytes` type indices and `zero_padding` field added to `TVMFFIAny` (`49e2ed4`)
- 2025-08-09: `MapObj::slots_` MSB tagging for small/dense dispatch (`03e8a6b`)
- 2025-08-20: Env API symbol renames (`TVMFFIEnv*` -> `TVMFFIEnvMod*`); env C API relocated to extra layer (`023ea44`)
- 2025-08-30: ABI type ordering adjusted pre-freeze; `ModuleObj::GetFunctionMetadata` stub added (`777cf8d`)
- 2025-09-05: `kTVMFFIOpaquePyObject` type index and `TVMFFIObjectCreateOpaque` added (`91d69f0`)
- 2025-09-06: `NDArray`/`NDArrayObj` renamed to `Tensor`/`TensorObj` (`3a551d8`)
- 2025-09-06: `Library::GetSymbolWithSymbolPrefix` added; module entry symbol standardized (`40e8a51`)
- 2025-09-08: `UnsafeInit` tag introduced for `ObjectRef` construction (`472e10c`)
- 2025-09-09: Object declaration macros consolidated with embedded type key (`a08fa6e`)
- 2025-09-09: `__tvm_ffi_env_stream__()` stream exchange protocol; `TVMFFIEnvSetCurrentStream` renamed (`db98729`)
- 2025-09-11: Python FFI call mechanism refactored for performance; `tvm_ffi_python_helpers.h` introduced (`38d2cda`)
- 2025-09-12: DLPack exporter/importer/allocator C function pointers added; `TensorObj` atomic cache; `release_gil` option (`f81ab9c`)
- 2025-09-12: DLPack attribute protocol renamed (`4dee97f`)
- 2025-09-13: `TVM_FFI_STATIC_INIT_BLOCK` syntax updated to function style (`7b813f8`)
- 2025-09-13: Standalone `apache/tvm-ffi` repository established (`30f1e0a`)
- 2025-09-22: Backtrace storage changed to "most recent first"; `TVMFFIErrorCreate` signature updated (`6f020c1`)
- 2025-09-25: `TVMFFIObject` header reordered: ref counts first (`13436f0`)
- 2025-09-25: `type_acenstors` typo fixed to `type_ancestors` (`98cb8af`)
- 2025-09-26: `combined_ref_count` replaces separate strong/weak counters (`43d13e8`)
- 2025-09-27: Raw aligned alloc replaces `new StorageType` in object allocator (`6fb42a7`)
- 2025-09-27: `ShapeView` introduced; `TensorObj` internal fields minimized (`8ca0719`)
- 2025-09-28: `TVM_FFI_CHECK` macro added (`327e8cc`, `ae06434`)
- 2025-09-29: `TVMFFIFunctionCell::cpp_call` field added; `ImportedFunctionObjImpl` removed (`4fe8b2b`)
- 2025-09-29: DLPack stride normalization completely removed (`f4a65cd`)
- 2025-09-30: Explicit zero-padding in object memory (`f9179ec`)
- 2025-10-01: `TVMFFIFieldInfo.type_schema` and `TVMFFIMethodInfo.type_schema` renamed to `metadata` (ABI-breaking); `ModuleObj::GetFunctionDoc` added (`935a5a0`)
- 2025-10-01: `ffi::TensorView` added; `StaticTypeKey::kTVMFFIDLTensorPtr` added (`1ec6236`)
- 2025-10-11: `DLPackExchangeAPI` struct replaces 3-pointer DLPack protocol; `__c_dlpack_exchange_api__` attribute required (`22a7894`)
- 2025-10-13: `TVMFFIErrorSetRaisedFromCStrParts` C API added (`550e92f`)
- 2025-10-14: Static object auto-registration removed; explicit `ReserveDepthOneObjectTypeIndex` for built-in types; `StaticTypeKey::kTVMFFIError` added (`9ac3121`)
- 2025-10-15: `TVMFFIEnvTensorAllocator` renamed to `TVMFFIEnvSetDLPackManagedTensorAllocator`; `TVMFFIEnvTensorAlloc` C API added (`f679fe5`)
- 2025-10-16: Version formally bumped to 0.1.0 (`792dc01`)
- 2025-10-18: Version Query API added (`f0058a9`)
- 2025-10-26: `TVM_FFI_VERSION_PATCH` bumped to 1; `setuptools_scm` integration (`ac63fb9`)
- 2025-12-05: `TVMFFIHandleInitOnce` and `TVMFFIHandleDeinitOnce` C API functions added (`25c25ae`)
- 2025-12-12: `TVMFFITensorCreateUnsafeView` C API function added (`8888eb4`)
- 2025-12-24: Link `dl` and `pthread` dependencies for `tvm_ffi` on Linux (`8b9f28d`)
- 2026-01-04: `<tvm/ffi/tvm_ffi.h>` umbrella header introduced (`8caa0cb`)
- 2026-01-09: `StringViewToDLDataType_` rewritten to use bounded parsers instead of `strtoul` (`ae30cd6`)
- 2026-01-11: `TVMFFIErrorCell` extended with `cause_chain` and `extra_context` fields; `TVMFFIErrorCreateWithCauseAndExtraContext` C API added (`4c712ca`)
- 2026-01-11: `find_package(Threads)` made optional for cross-compilation (`0d157dc`)
- 2026-01-11: Explicit `TVM_FFI_USE_THREADS` CMake option added (`3b4a532`)
- 2026-01-11: Explicit `TVM_FFI_USE_DL` CMake option added (`dcd07cf`)
- 2026-01-12: `TVM_FFI_CHECK_CUDA_ERROR` macro split; `TVM_FFI_CHECK_CUBIN_LAUNCHER_CUDA_ERROR` introduced (`10cb004`)
- 2026-01-30: UBSan fixes: `__builtin_offsetof` in `object.h`, `memcpy` null guard in `string.h` (`b508698`)
- 2026-02-06: `include/tvm/ffi/expected.h` added: `Expected<T>`, `Unexpected<E>` for exception-free error handling; `Function::CallExpected<T>()` (`0a9d4b6`)
- 2026-02-13: `kTVMFFIList` type index added for `ListObj` (`9513c2f`)
- 2026-02-14: `kTVMFFIFieldFlagBitMaskDefaultFromFactory = 1 << 5` added; `TVMFFIFieldInfo::default_value` renamed to `default_value_or_factory` (ABI-breaking) (`5e564cd`)
- 2026-02-18: `kTVMFFIFieldFlagBitMaskReprOff = 1 << 6` added for per-field repr exclusion (`b648c5d`)
- 2026-02-19: `kTVMFFIDict` type index added for `DictObj` (`c1af3b3`)
- 2026-02-19: `DCHECK`, `DCHECK_EQ`, typed `CHECK_EQ` macros completed in `error.h` (`35cbc32`)

## References
- Range summaries:
  - `.repo-knowledge/ranges/2025-05-29-7D34EB8-024E45C.md`
  - `.repo-knowledge/ranges/2025-06-27-1C9B17A-F7311E4.md`
  - `.repo-knowledge/ranges/2025-07-31-0966C36-0342D85.md`
  - `.repo-knowledge/ranges/2025-08-31-F9D2BFF-3702E50.md`
  - `.repo-knowledge/ranges/2025-09-30-CA9C3D1-F9179EC.md`
  - `.repo-knowledge/ranges/2025-10-31-FFA2DBF-BC0D225.md`
  - `.repo-knowledge/ranges/2025-12-29-5A82940-6E7CAFA.md`
  - `.repo-knowledge/ranges/2026-01-30-C51E519-B508698.md`
  - `.repo-knowledge/ranges/2026-02-21-B1611E0-ECC7471.md`
- Related ADRs:
  - `.repo-knowledge/adr/002-struct-by-pointer-c-abi.md`
  - `.repo-knowledge/adr/016-error-cause-chaining.md`
  - `.repo-knowledge/adr/005-small-string-inline-abi.md`
  - `.repo-knowledge/adr/006-msb-tag-map-dispatch.md`
  - `.repo-knowledge/adr/008-ndarray-to-tensor-rename.md`
  - `.repo-knowledge/adr/009-combined-refcount-abi.md`
- Related design docs: `.repo-knowledge/design/004-reflection-system.md`, `.repo-knowledge/design/005-structural-equal-hash.md`, `.repo-knowledge/design/007-module-system.md`, `.repo-knowledge/design/009-tensor-and-dlpack.md`
