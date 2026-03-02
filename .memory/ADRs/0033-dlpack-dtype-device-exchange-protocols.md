---
adr: "0033"
title: "DLPack-Based Dtype and Device Exchange Protocols"
status: "accepted"
date: "2025-10-20"
deciders:
  - "Tianqi Chen"
consulted:
  - "TVM FFI contributors"
informed:
  - "Python API users"
  - "Cross-framework interop developers"
tags:
  - "interop"
  - "dlpack"
  - "protocol"
source_commits:
  - "5e648f05"
  - "0f8bf9fc"
source_ledgers:
  - ".memory/commits/2025-10-20-5e648f05.md"
  - ".memory/commits/2025-10-20-0f8bf9fc.md"
---

# ADR-0033: DLPack-Based Dtype and Device Exchange Protocols

## TL;DR
- Two new duck-typing protocols (`__dlpack_data_type__` and `__dlpack_device__`) enable third-party Python objects to be automatically converted to FFI dtype and device values in function calls, without requiring inheritance from FFI types or full DLPack tensor export.
- These protocols use the DLPack specification as the interchange format because DLDataType and DLDevice are the closest-to-hardware representations of dtype and device.

## Status
Accepted

## Context
Cross-framework interoperability for machine learning requires exchanging not just tensor data (via DLPack) but also metadata like data types and device specifications. Before these protocols, passing a third-party framework's dtype or device object through TVM FFI required manual conversion (e.g., `tvm_ffi.dtype("float32")` instead of directly passing a framework's native dtype object). This friction was especially problematic in orchestration code that bridges multiple frameworks.

The DLPack specification already defines `DLDataType` (type_code, bits, lanes) and `DLDevice` (device_type, device_id) as standard interchange formats. Several frameworks (NumPy, PyTorch) are beginning to adopt `__dlpack_data_type__` and `__dlpack_device__` as protocol methods. TVM FFI can leverage these existing conventions.

## Decision Drivers
- DLPack is already the standard for tensor data exchange; extending it to dtype/device is a natural fit.
- The arg setter factory already supports duck-typing protocol dispatch, making new protocols cheap to add (~20 lines of Cython each).
- Cross-framework dtype exchange must not require full tensor creation (which `__dlpack__` would imply).
- Device exchange must distinguish between "I am a device descriptor" and "I am a tensor on a device" (the `__dlpack_device__` vs `__dlpack__` ambiguity).

## Decision
Implement two new arg setter protocols in the Cython `TVMFFIPyArgSetterFactory`:

1. **`__dlpack_data_type__`** protocol: If an argument's class has `__dlpack_data_type__`, the setter calls it to get a `(type_code, bits, lanes)` tuple and converts it to a `DLDataType` FFI value. A corresponding `dtype.from_dlpack_data_type(type_code, bits, lanes)` Python factory method provides explicit conversion. The internal slot was renamed from `__tvm_ffi_dtype__` to `_tvm_ffi_dtype` for naming consistency.

2. **`__dlpack_device__`** protocol: If an argument's class has `__dlpack_device__` but NOT `__dlpack__`, the setter calls it to get a `(device_type, device_id)` tuple and converts it to a `TVMFFIDevice` FFI value. The `__dlpack__` exclusion is critical: objects with both protocols (tensors) should use the full DLPack tensor conversion path, not the device-only path.

Both protocols are inserted into the existing priority chain after `__cuda_stream__` and before `__dlpack__` (full tensor).

## Alternatives Considered
### Framework-specific adapters (e.g., register_dtype_adapter)
- Pros: Explicit per-framework registration. No naming conventions needed.
- Cons: Every framework needs separate adapter registration. Not discoverable from the class definition. Scales poorly with N frameworks.

### Use numpy dtype protocol (once standardized)
- Pros: Follows numpy's lead in the dtype interop space.
- Cons: numpy dtype protocol was not yet materialized at the time of this decision. DLDataType is more general (supports custom type codes, lanes > 1, hardware-specific types). Can add numpy protocol support later as an additional fallback.

### Require explicit conversion before FFI calls
- Pros: No protocol machinery. Simple and predictable.
- Cons: Verbose. Forces every call site to convert explicitly. Defeats the purpose of the arg setter factory's automatic conversion.

## Why This Option Won
- DLPack is already the established interchange format for the ML ecosystem, and DLDataType/DLDevice are its fundamental building blocks.
- The duck-typing protocol pattern is already proven by `__tvm_ffi_object__`, `__cuda_stream__`, etc. Adding two more protocols follows the exact same pattern with minimal code (~20 lines each).
- The `__dlpack_device__` vs `__dlpack__` disambiguation handles the real-world ambiguity correctly: tensors are tensors, devices are devices.
- The `dtype.from_dlpack_data_type()` factory method provides an escape hatch for explicit conversion without the protocol.

## Consequences
### Positive
- Third-party dtype and device objects with DLPack protocol methods are now zero-friction in FFI calls.
- The DLPack-based interchange format is hardware-close and supports custom type codes (e.g., `float8_e4m3`).
- Consistent with the existing protocol dispatch pattern, maintaining code simplicity.

### Negative
- The `__dlpack_device__` exclusion of `__dlpack__` objects is a subtle semantic: objects with `__dlpack__` are treated as tensors regardless of `__dlpack_device__`. If a user implements `__dlpack_device__` on a non-tensor class that also has `__dlpack__`, the device protocol will not be used.
- Adding more protocols increases the priority chain length, though the per-type caching means the check only happens once.

### Risks
- The `__dlpack_data_type__` protocol is emerging and its semantics may evolve in the broader ecosystem. Mitigation: TVM FFI's interpretation is conservative (just reads a tuple) and can adapt.
- The internal slot rename (`__tvm_ffi_dtype__` -> `_tvm_ffi_dtype`) is a breaking change for any code that accessed the old slot. Mitigation: this was an internal implementation detail, not a public API.

## Implementation Notes
- `TVMFFIPyArgSetterDLPackDataTypeProtocol_` in `function.pxi` calls `arg.__dlpack_data_type__()`, expects a 3-tuple `(type_code, bits, lanes)`, and sets the arg as `DLDataType`.
- `TVMFFIPyArgSetterDLPackDeviceProtocol_` in `function.pxi` calls `arg.__dlpack_device__()`, expects a 2-tuple `(device_type, device_id)`, and sets the arg as `TVMFFIDevice`.
- `dtype.from_dlpack_data_type()` is a static factory method on the `dtype` class in `_dtype.py`.
- Tests in `test_function.py` and `test_dtype.py` validate both protocols.

## Validation
- `tests/python/test_function.py` tests automatic conversion via both `__dlpack_data_type__` and `__dlpack_device__` protocols.
- `tests/python/test_dtype.py` tests `dtype.from_dlpack_data_type()` factory.

## Migration and Rollback
- **Migration**: No migration needed. These are new opt-in protocols. Existing code is unaffected.
- **Rollback**: Remove the two `hasattr` checks and setter functions from `TVMFFIPyArgSetterFactory`. The `dtype.from_dlpack_data_type()` factory can remain as a standalone utility.

## Related Design Docs
- [.memory/designs/0022-python-ffi-interop-protocols.md](.memory/designs/0022-python-ffi-interop-protocols.md) (protocol dispatch system)
- [.memory/designs/0011-cython-binding-layer.md](.memory/designs/0011-cython-binding-layer.md) (Cython arg setter factory)

## Related Diagrams
- [.memory/diagrams/0016-python-ffi-protocol-dispatch.md](.memory/diagrams/0016-python-ffi-protocol-dispatch.md)

## Evidence Matrix
- `__dlpack_data_type__` protocol setter and `dtype.from_dlpack_data_type()` factory -> `.memory/commits/2025-10-20-5e648f05.md` + `5e648f05` + `python/tvm_ffi/_dtype.py`, `python/tvm_ffi/cython/function.pxi`, `python/tvm_ffi/cython/dtype.pxi`
- `__dlpack_device__` protocol setter -> `.memory/commits/2025-10-20-0f8bf9fc.md` + `0f8bf9fc` + `python/tvm_ffi/cython/function.pxi`
- Internal slot rename `__tvm_ffi_dtype__` -> `_tvm_ffi_dtype` -> `5e648f05` + `python/tvm_ffi/cython/dtype.pxi`

## Supersedes
None

## Superseded By
None

## Follow-up Actions
- Monitor numpy dtype protocol standardization and consider adding it as an additional fallback.
- Consider whether `__dlpack_data_type__` should also be checked on the `dtype` class construction path (not just the arg setter).
