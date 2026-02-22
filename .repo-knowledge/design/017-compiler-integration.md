# 017 — Compiler Integration Patterns

- Doc ID: 017-compiler-integration
- Status: Approved
- Last Updated: 2026-02-22
- Owners: Tianqi Chen

## Overview

TVM FFI is a standalone ABI designed as a codegen target for DSL compilers and
graph compilers. A single shared library (`.so`) compiled against TVM FFI works
with PyTorch, JAX, PaddlePaddle, NumPy, CuPy, and more without recompilation,
because the ABI relies on DLPack for tensor interchange and a fixed 128-bit
tagged union (`TVMFFIAny`) for all value passing. This document describes the
concrete patterns that compiler authors use to integrate with the ABI: the
`TVMFFIAny` layout, the universal calling convention, the symbol naming
contract, kernel authoring patterns, tensor parameter conventions, runtime state
management, static linking strategies, and the automatic C++ wrapping rule.

## Key Design

### TVMFFIAny -- the 128-bit tagged union

Every argument and return value passes through `TVMFFIAny`, a fixed 16-byte
struct defined in `include/tvm/ffi/c_api.h` (lines 287--333):

```c
typedef struct {
  int32_t type_index;
  union { uint32_t zero_padding; uint32_t small_str_len; };
  union {
    int64_t v_int64;
    double v_float64;
    void* v_ptr;
    const char* v_c_str;
    TVMFFIObject* v_obj;
    DLDataType v_dtype;
    DLDevice v_device;
    char v_bytes[8];
    uint64_t v_uint64;
  };
} TVMFFIAny;
```

Layout: bits [0:31] hold `type_index` (identifies the stored type via the
`TVMFFITypeIndex` enum); bits [32:63] hold `zero_padding` (must be zero for
non-small-string types) or `small_str_len` (for `kTVMFFISmallStr`); bits
[64:127] hold the 8-byte payload union. Unused bytes must always be zeroed to
enable direct byte comparison and hashing.

Three payload categories matter for compiler codegen:

1. **Primitives** (`type_index < kTVMFFIStaticObjectBegin = 64`): stored inline.
   Includes `kTVMFFIInt` (1), `kTVMFFIBool` (2), `kTVMFFIFloat` (3),
   `kTVMFFIOpaquePtr` (4), `kTVMFFIDataType` (5), `kTVMFFIDevice` (6),
   `kTVMFFIDLTensorPtr` (7), `kTVMFFIRawStr` (8), `kTVMFFISmallStr` (11).

2. **Heap-allocated tensors** (`kTVMFFITensor = 70`): `v_obj` points to a
   `TVMFFIObject` header, and the `DLTensor` starts at
   `(char*)v_obj + sizeof(TVMFFIObject)`. Also `kTVMFFIDLTensorPtr` (7) for
   raw non-owning `DLTensor*` passed as `v_ptr`. A callee must handle both
   forms.

3. **Ref-counted objects** (`type_index >= kTVMFFIStaticObjectBegin = 64`):
   `v_obj` points to a heap-allocated `TVMFFIObject` (24 bytes:
   8-byte `combined_ref_count` + 4-byte `type_index` + 4-byte padding +
   8-byte `deleter`). Includes `kTVMFFIStr` (65), `kTVMFFIFunction` (68),
   `kTVMFFIArray` (71), `kTVMFFIMap` (72), `kTVMFFIModule` (73), etc.
   Dynamic types start at `kTVMFFIDynObjectBegin = 128`. After use, if
   `result.type_index >= kTVMFFIStaticObjectBegin`, the caller must call
   `TVMFFIObjectDecRef`.

### Universal calling convention

Every FFI function call uses the same C signature, `TVMFFISafeCallType`
(`c_api.h` line 491):

```c
typedef int (*TVMFFISafeCallType)(
    void* handle,
    const TVMFFIAny* args,
    int32_t num_args,
    TVMFFIAny* result
);
```

- `handle`: library/closure handle, typically `NULL` for exported symbols.
- `args`: contiguous array of `TVMFFIAny` inputs.
- `num_args`: argument count.
- `result`: out-parameter; caller must initialize `result->type_index = kTVMFFINone`.
- Returns 0 on success, -1 on error. Errors are stored in thread-local storage
  and retrieved via `TVMFFIErrorMoveFromRaised`.

This is the only calling convention. All functions, regardless of source
language, conform to this signature.

### DSL compiler codegen contract

A DSL compiler emitting code that conforms to the ABI must follow these rules:

**Symbol naming.** Exported functions use the `__tvm_ffi_<func_name>` prefix.
Defined as a constant in `include/tvm/ffi/extra/module.h` (line 283):

```cpp
constexpr const char* tvm_ffi_symbol_prefix = "__tvm_ffi_";
```

**Optional metadata symbol.** `__tvm_ffi__metadata_<func_name>` returns JSON
with `type_schema`. Controlled by `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA`
(default 0, `function.h` line 33). The prefix constant is
`symbol::tvm_ffi_metadata_prefix` (`module.h` line 294).

**Optional doc symbol.** `__tvm_ffi__doc_<func_name>` returns a docstring.
The prefix constant is `symbol::tvm_ffi_doc_prefix` (`module.h` line 296).

**Type checking.** The callee must check `args[i].type_index` before accessing
the payload. For tensors, check both `kTVMFFIDLTensorPtr` (raw pointer) and
`kTVMFFITensor` (ref-counted object with DLTensor at offset
`sizeof(TVMFFIObject)`).

**Error protocol.** On error, call `TVMFFIErrorSetRaisedFromCStr(kind, message)`
or `TVMFFIErrorSetRaisedFromCStrParts(kind, parts, num_parts)`, then return -1.
The `CStrParts` variant (`c_api.h` line 677) enables compilers to store shared
substrings (e.g., function signatures) and concatenate them at runtime, reducing
binary bloat from duplicated error messages.

Reference callee implementation from `examples/stable_c_abi/src/add_one_cpu.c`:

```c
TVM_FFI_DLL_EXPORT int __tvm_ffi_add_one_cpu(
    void* handle, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result) {
  DLTensor* x;
  if (args[0].type_index == kTVMFFIDLTensorPtr)
    x = (DLTensor*)(args[0].v_ptr);
  else if (args[0].type_index == kTVMFFITensor)
    x = (DLTensor*)(args[0].v_c_str + sizeof(TVMFFIObject));
  else {
    TVMFFIErrorSetRaisedFromCStr("ValueError", "Expects a Tensor input");
    return -1;
  }
  // ... kernel logic ...
  return 0;
}
```

### Three integration options for kernel DSL compilers

From `docs/guides/compiler_integration.md`, kernel languages such as Triton,
TileLang, Mojo, cuteDSL, Helion, and Hidet can integrate via:

1. **LLVM/codegen-based**: Directly emit a `__tvm_ffi_<func_name>` symbol with
   the `TVMFFISafeCallType` signature. For compilers targeting LLVM IR, this
   means generating the marshalling code in IR. Optionally also emit
   `__tvm_ffi__metadata_<func_name>` for reflection.

2. **C++ host code**: Use `TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, Function)`.
   Automatically generates the wrapper `__tvm_ffi_<ExportName>` with argument
   unpacking. Optionally generates `__tvm_ffi__metadata_<ExportName>` when
   `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA=1`.

3. **Documentation export**: Use
   `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC(ExportName, DocString)` to export a
   `__tvm_ffi__doc_<ExportName>` symbol for stub generation and IDE tooltips.

The key requirement for all: emit the `__tvm_ffi_` prefixed symbol, handle
`TVMFFIAny` argument marshalling, use `TVMFFIEnvGetStream` for stream
acquisition, and follow the error protocol.

Reference codegen example from `docs/guides/compiler_integration.md`:

```c
int __tvm_ffi_add_one_c(
    void* handle, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result) {
  DLTensor *x, *y;
  if (ReadDLTensorPtr(&args[0], &x) == -1) return -1;
  if (ReadDLTensorPtr(&args[1], &y) == -1) return -1;
  void* stream = TVMFFIEnvGetStream(x->device.device_type, x->device.device_id);
  // ... kernel launch ...
  return 0;
}
```

### Graph compiler integration

Graph compilers (e.g., XLA, TorchInductor-style, Relay, Relax) integrate by:

1. **`call_tvm_ffi` primitive**: A graph-level op that calls
   `Op.call_tvm_ffi("my_func", *args)`.

2. **Module API**: Load pre-compiled modules via
   `Module::LoadFromFile("lib.so")` (C++) or `tvm_ffi.load_module("lib.so")`
   (Python), then call functions via `mod->GetFunction("name")`.

3. **Direct function lookup**: Use global registry
   `Function::GetGlobal("func_name")` (C++) or
   `tvm_ffi.get_global_func("func_name")` (Python).

`ModuleObj::GetFunction` returns an `Optional<Function>`. The
`LibraryModuleObj` implementation looks up `__tvm_ffi_<name>` symbols from
the loaded DSO. Module property masks (`kBinarySerializable`, `kRunnable`,
`kCompilationExportable`) inform the graph compiler about module capabilities.

```python
# Graph compiler integration (Python)
mod = tvm_ffi.load_module("compiled_kernels.so")
add_func = mod["add_one_cpu"]  # looks up __tvm_ffi_add_one_cpu
add_func(x_tensor, y_tensor)
```

```cpp
// Graph compiler integration (C++)
ffi::Module mod = ffi::Module::LoadFromFile("compiled_kernels.so");
ffi::Function func = mod->GetFunction("add_one_cpu").value();
func(x, y);
```

### AOT compilation

Two approaches for ahead-of-time compilation with minimum runtime:

1. **Direct symbol calls**: The AOT compiler emits direct calls to
   `__tvm_ffi_<name>`. No `TVMFFIFunctionCall` overhead. The compiler emits
   the marshalling of args into a `TVMFFIAny` array and calls the symbol
   directly.

2. **Via `TVMFFIFunctionCall`**: Used when functions are wrapped in
   `ffi::Function` objects (ref-counted). Slightly more overhead due to
   indirection through the `safe_call` function pointer in
   `TVMFFIFunctionCell`, but more flexible.

`Function::InvokeExternC` (`function.h` line 587) provides a C++ convenience
for calling extern C symbols directly with type-safe argument packing:

```cpp
extern "C" int __tvm_ffi_add(
    void* handle, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result);

inline int add(int a, int b) {
  return tvm::ffi::Function::InvokeExternC(
      nullptr, __tvm_ffi_add, a, b).cast<int>();
}
```

`Function::FromExternC` (`function.h` line 392) wraps a C function pointer
into an `ffi::Function` object for use in the object system:

```cpp
Function func = Function::FromExternC(nullptr, __tvm_ffi_add, nullptr);
```

AOT compilers can use `TVMFFIEnvModRegisterSystemLibSymbol`
(`c_env_api.h` line 152) to register symbols into the system library, avoiding
dynamic loading entirely.

### C-only integration pattern

For environments without C++, the full caller-side workflow in pure C is:

1. Look up global functions via `TVMFFIFunctionGetGlobal` to get
   `ffi.Module.load_from_file.so` and `ffi.ModuleGetFunction`.
2. Construct `TVMFFIAny` args manually (type_index + payload).
3. Call via `TVMFFIFunctionCall(func_handle, args, num_args, &result)`.
4. Use goto-based RAII cleanup to ensure `TVMFFIObjectDecRef` is called on
   all owned objects.

Full example from `examples/stable_c_abi/src/load.c`:

```c
int Run(DLTensor* x, DLTensor* y) {
  int ret_code = 0;
  TVMFFIAny call_args[3] = {};
  TVMFFIAny mod = {.type_index = kTVMFFINone, .v_obj = NULL};
  TVMFFIAny func = {.type_index = kTVMFFINone, .v_obj = NULL};
  TVMFFIAny none = {.type_index = kTVMFFINone};

  // Step 1. Load module
  call_args[0] = (TVMFFIAny){.type_index = kTVMFFIRawStr,
                              .v_c_str = "build/add_one_cpu.so"};
  call_args[1] = (TVMFFIAny){.type_index = kTVMFFISmallStr, .v_int64 = 0};
  if ((ret_code = TVMFFIFunctionCall(fn_load_module, call_args, 2, &mod)))
    goto _RAII;

  // Step 2. Get function
  call_args[0] = (TVMFFIAny){.type_index = mod.type_index, .v_obj = mod.v_obj};
  call_args[1] = (TVMFFIAny){.type_index = kTVMFFIRawStr,
                              .v_c_str = "add_one_cpu"};
  call_args[2] = (TVMFFIAny){.type_index = kTVMFFIBool, .v_int64 = 0};
  if ((ret_code = TVMFFIFunctionCall(fn_get_function, call_args, 3, &func)))
    goto _RAII;

  // Step 3. Call function
  call_args[0] = (TVMFFIAny){.type_index = kTVMFFIDLTensorPtr, .v_ptr = x};
  call_args[1] = (TVMFFIAny){.type_index = kTVMFFIDLTensorPtr, .v_ptr = y};
  if ((ret_code = TVMFFIFunctionCall(func.v_ptr, call_args, 2, &none)))
    goto _RAII;

_RAII:
  if (mod.type_index >= kTVMFFIObject) TVMFFIObjectDecRef(mod.v_obj);
  if (func.type_index >= kTVMFFIObject) TVMFFIObjectDecRef(func.v_obj);
  if (none.type_index >= kTVMFFIObject) TVMFFIObjectDecRef(none.v_obj);
  return ret_code;
}
```

Error retrieval uses `TVMFFIErrorMoveFromRaised` to obtain the error object,
then reads the `TVMFFIErrorCell` at offset `sizeof(TVMFFIObject)` from the
object pointer to access `kind` and `message` fields.

### TensorView vs Tensor for kernel parameters

`TensorView` (`container/tensor.h` line 665) is a non-owning lightweight view
of a `DLTensor`. It stores a copy of the `DLTensor` struct (not a pointer to
the object):

- **No reference count overhead**: No `TVMFFIObjectIncRef`/`DecRef` on
  entry/exit.
- **Works with all sources**: Framework tensors (PyTorch, JAX), XLA buffers
  (which only provide views), raw `DLTensor*` pointers.
- Constructible from both `Tensor` (ref-counted) and raw `DLTensor*`.

`Tensor` is the owning ref-counted tensor. Wraps a `TensorObj` containing
`TVMFFIObject` header + `DLTensor`. Used when allocating and returning tensors.

**Rule of thumb**: Use `TensorView` for kernel parameters (input/output). Use
`Tensor` only when the function needs to allocate and return a tensor.

Both expose: `ndim()`, `shape()`, `size(i)`, `numel()`, `dtype()`, `device()`,
`data_ptr()`, `strides()`, `IsContiguous()`. PyTorch-familiar aliases: `dim()`,
`sizes()`, `is_contiguous()`.

### Pre-allocation rationale

Always pre-allocate output tensors on the Python side and pass them as
`TensorView` parameters:

```python
y = torch.empty_like(x)  # Pre-allocate
mod.scale(y, x, 2.0)     # Kernel writes into pre-allocated output
```

```cpp
void Scale(TensorView output, TensorView input, double factor);
```

Three reasons:

1. **Memory fragmentation**: Repeated small allocations inside kernels cause
   fragmentation.
2. **CUDA graph capture**: Requires deterministic memory addresses;
   kernel-internal allocation breaks this.
3. **Framework allocator bypass**: Internal allocation skips the framework's
   caching pool and memory planner.

When C++-side allocation is unavoidable (data-dependent output shapes), use
`Tensor::FromEnvAlloc(TVMFFIEnvTensorAlloc, shape, dtype, device)`
(`tensor.h` line 530) to reuse the host framework's allocator (e.g.,
`torch.empty` under PyTorch). For custom allocators: `Tensor::FromNDAlloc`.
Caveat: the kernel library must outlive allocated tensors since the custom
deleter lives in the library.

### Kernel authoring anatomy

Every TVM FFI CUDA kernel follows a 4-step anatomy:

1. **Validate** inputs (device, dtype, shape, contiguity)
2. **Set device guard** (RAII `CUDADeviceGuard`)
3. **Acquire stream** from host framework via `TVMFFIEnvGetStream`
4. **Dispatch** on dtype and launch the kernel

From `examples/kernel_library/scale_kernel.cu`:

```cpp
void Scale(TensorView output, TensorView input, double factor) {
  // 1. Validate
  CHECK_INPUT(input);
  CHECK_INPUT(output);
  CHECK_DIM(1, input);
  CHECK_DEVICE(input, output);

  // 2. Device guard and stream
  ffi::CUDADeviceGuard guard(input.device().device_id);
  cudaStream_t stream = get_cuda_stream(input.device());

  // 3. Dispatch on dtype and launch
  int64_t n = input.numel();
  int threads = 256;
  int blocks = (n + threads - 1) / threads;
  if (input.dtype() == dl_float32) {
    ScaleKernel<<<blocks, threads, 0, stream>>>(
        static_cast<float*>(output.data_ptr()),
        static_cast<float*>(input.data_ptr()),
        static_cast<float>(factor), n);
  } else { /* ... */ }
}

// 4. Export
TVM_FFI_DLL_EXPORT_TYPED_FUNC(scale, Scale);
```

Reusable macros from `examples/kernel_library/tvm_ffi_utils.h`:
`CHECK_CUDA`, `CHECK_CONTIGUOUS`, `CHECK_INPUT`, `CHECK_DIM`, `CHECK_DEVICE`.

Stream helper: `TVMFFIEnvGetStream(device_type, device_id)` returns `void*`;
cast to `cudaStream_t` for CUDA.

Error reporting: `TVM_FFI_THROW(TypeError)` / `TVM_FFI_CHECK(cond, ValueError)`
for user-facing errors; `TVM_FFI_ICHECK` for internal invariants.

Loading from Python (`examples/kernel_library/load_scale.py`):

```python
mod = tvm_ffi.load_module("build/scale_kernel.so")
y = torch.empty_like(x)
mod.scale(y, x, 2.0)
```

### Automatic wrapping rule

`TVM_FFI_DLL_EXPORT_TYPED_FUNC` (`function.h` lines 946--1011) uses template
metaprogramming (`FunctionInfo<decltype(Function)>`) to automatically generate
the `TVMFFISafeCallType` wrapper. The rule: **if an invocable's arguments and
return value can each be converted to/from `tvm::ffi::Any`/`tvm::ffi::AnyView`,
it is automatically ABI-compatible.**

Any function/lambda/functor with arguments of types like `int`, `double`,
`TensorView`, `String`, `Array<T>`, `Optional<T>`, etc. can be exported with
a single macro call. The `details::unpack_call` function template handles the
conversion from `TVMFFIAny*` array to typed arguments and back.

```cpp
// This single macro:
TVM_FFI_DLL_EXPORT_TYPED_FUNC(scale, Scale);

// Generates:
extern "C" TVM_FFI_DLL_EXPORT int __tvm_ffi_scale(
    void* self, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result) {
  TVM_FFI_SAFE_CALL_BEGIN();
  // ... automatic argument unpacking and type conversion ...
  TVM_FFI_SAFE_CALL_END();
}
```

### Static linking -- FromExternC / InvokeExternC

On platforms that prohibit dynamic loading (iOS, embedded, WebAssembly),
symbols must be statically linked.

`Function::FromExternC(self, safe_call, deleter)` (`function.h` line 392)
wraps a C function pointer into an `ffi::Function` object. When `self` and
`deleter` are both nullptr, uses a lightweight
`ExternCFunctionObjNullHandleImpl`.

`Function::InvokeExternC(handle, safe_call, args...)` (`function.h` line 587)
directly invokes an extern C symbol with automatic argument packing. No
`ffi::Function` object creation -- lowest overhead path.

`TVMFFIEnvModRegisterSystemLibSymbol("__tvm_ffi_<name>", ptr)`
(`c_env_api.h` line 152) registers statically linked symbols into the system
library. Retrieved via `tvm_ffi.system_lib()` in Python.

`TVMFFIEnvModRegisterContextSymbol` registers symbols that should be
initialized when a library module loads.

```cpp
// Static linking: wrap an extern C symbol into a Function object
extern "C" int __tvm_ffi_add(void*, const TVMFFIAny*, int32_t, TVMFFIAny*);
ffi::Function add_func = ffi::Function::FromExternC(
    nullptr, __tvm_ffi_add, nullptr);

// Zero-overhead direct call
int result = ffi::Function::InvokeExternC(
    nullptr, __tvm_ffi_add, 3, 4).cast<int>();
```

### Runtime state management

Compilers/DSLs often need their own runtime state (dynamic shapes, workspace
memory, etc.). The recommended pattern uses a global singleton registered via
`TVM_FFI_STATIC_INIT_BLOCK()`.

`TVM_FFI_STATIC_INIT_BLOCK()` (`base_details.h` lines 102--120) generates a
function called during static initialization. Uses
`__attribute__((constructor))` on GCC/Clang, a variable-trick on other
compilers.

```cpp
class GlobalState {
 public:
  static GlobalState* Global() {
    static auto* inst = new GlobalState();
    return inst;
  }
  // ... state variables ...
};

TVM_FFI_STATIC_INIT_BLOCK() {
  using refl = tvm::ffi::reflection;
  refl.GlobalDef()
      .def("mylang.get_global_state", []() -> void* {
        return GlobalState::Global();
      });
}
```

**Common vs. custom state.** TVM FFI manages common cross-cutting state
(streams via `TVMFFIEnvGetStream`/`TVMFFIEnvSetStream`, allocators via
`TVMFFIEnvSetDLPackManagedTensorAllocator`). Compiler-specific state should
live in the compiler's own runtime library.

**Distribution.** Package the runtime library as a separate `.so` (e.g.,
`libmylang_runtime.so`). Users import this before loading kernels. This
ensures state is shared across all kernels from that compiler.

**`TVMFFIHandleInitOnce`** (`c_api.h` line 1267, `src/ffi/init_once.cc`):
Thread-safe lazy initialization for DSLs without C++ static init support.
Uses atomic acquire/release for the fast path with a static mutex fallback
for first initialization. Implemented using `__atomic_load_n`/
`__atomic_store_n` (GCC/Clang) or `InterlockedCompareExchangePointerAcquire`
(MSVC).

```c
static void* my_state_handle = NULL;

int init_my_state(void** result) {
  *result = create_state();
  return 0;
}

// Thread-safe lazy init
if (TVMFFIHandleInitOnce(&my_state_handle, init_my_state) != 0) return -1;
```

## APIs

### C API (codegen target)

```c
// Calling convention (include/tvm/ffi/c_api.h)
typedef int (*TVMFFISafeCallType)(
    void* handle, const TVMFFIAny* args, int32_t num_args, TVMFFIAny* result);

// Error reporting (include/tvm/ffi/c_api.h)
TVM_FFI_DLL void TVMFFIErrorSetRaisedFromCStr(
    const char* kind, const char* message);
TVM_FFI_DLL void TVMFFIErrorSetRaisedFromCStrParts(
    const char* kind, const char** message_parts, int32_t num_parts);
TVM_FFI_DLL void TVMFFIErrorMoveFromRaised(TVMFFIObjectHandle* error);

// Object lifecycle (include/tvm/ffi/c_api.h)
TVM_FFI_DLL void TVMFFIObjectDecRef(TVMFFIObjectHandle obj);

// Function call (include/tvm/ffi/c_api.h)
TVM_FFI_DLL int TVMFFIFunctionCall(
    TVMFFIObjectHandle func, TVMFFIAny* args, int32_t num_args,
    TVMFFIAny* result);
TVM_FFI_DLL int TVMFFIFunctionGetGlobal(
    const TVMFFIByteArray* name, TVMFFIObjectHandle* out);

// Thread-safe lazy init (include/tvm/ffi/c_api.h)
TVM_FFI_DLL int TVMFFIHandleInitOnce(
    void** handle_addr, int (*init_func)(void** result));
TVM_FFI_DLL int TVMFFIHandleDeinitOnce(
    void** handle_addr, int (*deinit_func)(void* handle));
```

### C env API (include/tvm/ffi/extra/c_env_api.h)

```c
// Stream context
TVM_FFI_DLL TVMFFIStreamHandle TVMFFIEnvGetStream(
    int32_t device_type, int32_t device_id);
TVM_FFI_DLL int TVMFFIEnvSetStream(
    int32_t device_type, int32_t device_id,
    TVMFFIStreamHandle stream,
    TVMFFIStreamHandle* opt_out_original_stream);

// Tensor allocation
TVM_FFI_DLL int TVMFFIEnvTensorAlloc(
    DLTensor* prototype, TVMFFIObjectHandle* out);

// System library registration
TVM_FFI_DLL int TVMFFIEnvModRegisterSystemLibSymbol(
    const char* name, void* symbol);
TVM_FFI_DLL int TVMFFIEnvModRegisterContextSymbol(
    const char* name, void* symbol);
```

### C++ API

```cpp
// Module loading (include/tvm/ffi/extra/module.h)
class Module : public ObjectRef {
  static Module LoadFromFile(const String& file_name);
  Optional<Function> GetFunction(const String& name, bool query_imports);
};

// Static/AOT linking (include/tvm/ffi/function.h)
class Function : public ObjectRef {
  static Function FromExternC(void* self, TVMFFISafeCallType safe_call,
                              void (*deleter)(void* self));
  template <typename... Args>
  static Any InvokeExternC(void* handle, TVMFFISafeCallType safe_call,
                           Args&&... args);
  static std::optional<Function> GetGlobal(std::string_view name);
};

// Tensor view (include/tvm/ffi/container/tensor.h)
class TensorView {
  int ndim() const;
  ShapeView shape() const;
  DLDataType dtype() const;
  DLDevice device() const;
  void* data_ptr() const;
  bool IsContiguous() const;
  int64_t numel() const;
};

class Tensor : public ObjectRef {
  static Tensor FromEnvAlloc(int (*env_alloc)(DLTensor*, TVMFFIObjectHandle*),
                             ShapeView shape, DLDataType dtype, DLDevice device);
};
```

### Preprocessor macros

| Macro | Purpose |
|-------|---------|
| `TVM_FFI_DLL_EXPORT_TYPED_FUNC(ExportName, Function)` | Export a typed function as `__tvm_ffi_<ExportName>` |
| `TVM_FFI_DLL_EXPORT_TYPED_FUNC_DOC(ExportName, DocString)` | Export docstring as `__tvm_ffi__doc_<ExportName>` |
| `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` | Enable metadata/doc symbol export (default 0) |
| `TVM_FFI_STATIC_INIT_BLOCK()` | Register code to run during static initialization |
| `TVM_FFI_DLL_EXPORT` | Always-export visibility attribute |

### Symbol naming constants (include/tvm/ffi/extra/module.h)

| Constant | Value |
|----------|-------|
| `symbol::tvm_ffi_symbol_prefix` | `"__tvm_ffi_"` |
| `symbol::tvm_ffi_main` | `"__tvm_ffi_main"` |
| `symbol::tvm_ffi_metadata_prefix` | `"__tvm_ffi__metadata_"` |
| `symbol::tvm_ffi_doc_prefix` | `"__tvm_ffi__doc_"` |
| `symbol::tvm_ffi_library_bin` | `"__tvm_ffi__library_bin"` |

## Implementation

| Source file | Purpose |
|-------------|---------|
| `include/tvm/ffi/c_api.h` | `TVMFFIAny`, `TVMFFISafeCallType`, `TVMFFITypeIndex`, `TVMFFIHandleInitOnce` |
| `include/tvm/ffi/function.h` | `TVM_FFI_DLL_EXPORT_TYPED_FUNC`, `FromExternC`, `InvokeExternC` |
| `include/tvm/ffi/extra/module.h` | `Module`, `LibraryModuleObj`, symbol prefix constants |
| `include/tvm/ffi/extra/c_env_api.h` | `TVMFFIEnvGetStream`, `TVMFFIEnvTensorAlloc`, system lib registration |
| `include/tvm/ffi/base_details.h` | `TVM_FFI_STATIC_INIT_BLOCK` |
| `include/tvm/ffi/container/tensor.h` | `TensorView`, `Tensor`, `Tensor::FromEnvAlloc` |
| `include/tvm/ffi/extra/cuda/device_guard.h` | `CUDADeviceGuard` RAII struct |
| `src/ffi/init_once.cc` | `TVMFFIHandleInitOnce` / `TVMFFIHandleDeinitOnce` implementation |
| `src/ffi/extra/library_module.cc` | `LibraryModuleObj`, symbol lookup via `__tvm_ffi_` prefix |
| `src/ffi/extra/library_module_system_lib.cc` | `SystemLibrary`, `TVMFFIEnvModRegisterSystemLibSymbol` |
| `src/ffi/extra/env_context.cc` | Stream context, DLPack allocator registration |
| `docs/guides/compiler_integration.md` | Compiler integration guide (kernel DSLs, graph compilers, state mgmt) |
| `docs/get_started/stable_c_abi.rst` | Stable C ABI quickstart |
| `docs/guides/kernel_library_guide.rst` | Kernel library authoring guide |
| `examples/stable_c_abi/src/add_one_cpu.c` | C callee reference implementation |
| `examples/stable_c_abi/src/load.c` | C caller reference implementation |
| `examples/kernel_library/scale_kernel.cu` | CUDA kernel authoring example |
| `examples/kernel_library/tvm_ffi_utils.h` | Reusable validation macros and stream helper |
| `examples/kernel_library/load_scale.py` | Python-side kernel loading example |

## History

- 2025-05-29: `TVM_FFI_DLL_EXPORT` always-export visibility macro added (`192f196`)
- 2025-08-17: `ffi::Module`, `LibraryModuleObj`, `Library`, `DSOLibrary`, `SystemLibrary` formalized (`538bef4`)
- 2025-08-19: Thread-local `StreamContext` added with `TVMFFIEnvSetStream`/`TVMFFIEnvGetStream` (`0daaffe`)
- 2025-09-06: Symbol prefix standardized to `__tvm_ffi_`; `Library::GetSymbolWithSymbolPrefix` added (`a999de6`, `40e8a51`)
- 2025-10-14: `Function::InvokeExternC` utility for direct extern C invocation (`9186b44`)
- 2025-11-20: `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA` flag; metadata and doc symbol export (`ac7bf68`)
- 2025-12-05: `TVMFFIHandleInitOnce` / `TVMFFIHandleDeinitOnce` C API for thread-safe lazy init (`25c25ae`)
- 2025-12-05: `compiler_integration.md` documentation guide added (`240ea44`)
- 2025-12-05: `stable_c_abi` documentation and examples (`369ff23`)

## Related

- `.repo-knowledge/design/001-type-erased-value-system.md` -- Any/AnyView ownership semantics, type index system, POD vs object values
- `.repo-knowledge/design/003-c-abi-stability.md` -- struct-by-pointer convention, DLL visibility tiers, `TVM_FFI_DLL_EXPORT` vs `TVM_FFI_DLL`
- `.repo-knowledge/design/004-reflection-system.md` -- `TVM_FFI_DLL_EXPORT_INCLUDE_METADATA`, type_schema generation, field/method reflection
- `.repo-knowledge/design/007-module-system.md` -- `LibraryModuleObj`, `DSOLibrary`, `SystemLibrary`, `__tvm_ffi_` symbol prefix, binary module format
- `.repo-knowledge/design/009-tensor-and-dlpack.md` -- DLPack interop, DLTensor layout, Tensor/TensorView class hierarchy, stream handling
