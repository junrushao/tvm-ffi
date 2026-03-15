---
scope: "dtype-traits"
---
# API Index: DType Traits

**Scope**: Compile-time C++ type to DLPack data type mapping and Python dtype conversion utility.
**Design docs**: [0022-dtype-traits.md](../designs/0022-dtype-traits.md)
**ADRs**: N/A

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `tvm_ffi::dtype_trait<T>` | struct template (`extra/dtype.h`, c51e519) | `static constexpr DLDataType value = {code, bits, lanes}` | Primary: empty. Specializations for standard integers, float, double, bool, CUDA half/bf16/fp8/fp4, HIP half/bf16/fp8/fp4. Forward-declares vendor types (no CUDA/HIP header dependency). |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `to_cpp_dtype` (`tvm_ffi.cpp.dtype`, c51e519) | `(dtype_str: str \| Any) -> str` | Convert TVM/PyTorch dtype string to C++ type name. Auto-detects CUDA/ROCm/CPU backend via torch. |
| `CPU_DTYPE_MAP` (`tvm_ffi.cpp.dtype`) | `dict[str, str]` | Mapping for CPU types (e.g., `"float32" -> "float"`) |
| `CUDA_DTYPE_MAP` (`tvm_ffi.cpp.dtype`) | `dict[str, str]` | Extends CPU map with CUDA types (`"bfloat16" -> "__nv_bfloat16"`) |
| `ROCM_DTYPE_MAP` (`tvm_ffi.cpp.dtype`) | `dict[str, str]` | Extends CPU map with HIP types (`"bfloat16" -> "__hip_bfloat16"`) |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| N/A | -- | DType traits are C++/Python only; no Rust bindings. |
