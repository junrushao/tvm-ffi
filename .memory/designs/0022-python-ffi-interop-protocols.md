---
design: "0022"
title: "Python FFI Interop Protocols: __tvm_ffi_object__, __tvm_ffi_opaque_ptr__, __cuda_stream__, __dlpack_data_type__, __dlpack_device__"
status: "active"
owners:
  - "Tianqi Chen"
created: "2025-10-13"
last_updated: "2025-10-20"
scope:
  - "python/tvm_ffi/cython/function.pxi"
  - "python/tvm_ffi/cython/object.pxi"
  - "python/tvm_ffi/_dtype.py"
  - "python/tvm_ffi/cython/dtype.pxi"
source_commits:
  - "4bc89254"
  - "8873700a"
  - "42e0612"
  - "b0537f04"
  - "965fc464"
  - "5e648f05"
  - "0f8bf9fc"
source_ledgers:
  - ".memory/commits/2025-10-13-4bc89254.md"
  - ".memory/commits/2025-10-14-8873700a.md"
  - ".memory/commits/2025-10-16-42e0612.md"
  - ".memory/commits/2025-10-13-b0537f04.md"
  - ".memory/commits/2025-10-13-965fc464.md"
  - ".memory/commits/2025-10-20-5e648f05.md"
  - ".memory/commits/2025-10-20-0f8bf9fc.md"
---

# Python FFI Interop Protocols: __tvm_ffi_object__, __tvm_ffi_opaque_ptr__, __cuda_stream__, __dlpack_data_type__, __dlpack_device__

## TL;DR
- Five duck-typing protocols enable third-party Python objects to participate in TVM FFI calls without requiring inheritance from FFI base classes: `__tvm_ffi_object__()` returns a cached FFI object, `__tvm_ffi_opaque_ptr__()` returns a raw pointer, `__cuda_stream__()` returns a CUDA stream handle, `__dlpack_data_type__()` returns a dtype tuple, and `__dlpack_device__()` returns a device tuple.
- These protocols are checked by the Cython arg setter factory (`TVMFFIPyArgSetterFactory`) at first use of a Python type and cached per-type for zero-overhead dispatch on subsequent calls.
- The `__tvm_ffi_object__` protocol superseded the short-lived `__tvm_ffi_tensor__` protocol, generalizing from tensor-specific to any FFI object type.
- The `__dlpack_data_type__` and `__dlpack_device__` protocols (commits `5e648f05`, `0f8bf9fc`) enable cross-framework dtype and device exchange using the DLPack specification as the interchange format, without requiring full tensor DLPack export.

## Problem Statement
External libraries (e.g., custom tensor wrappers, CUDA stream managers, hardware-specific runtime classes) need to pass their objects through TVM FFI calls. Without interop protocols, these libraries would need to either: (a) inherit from TVM FFI base classes (tight coupling), (b) manually convert objects before every FFI call (verbose and error-prone), or (c) modify the FFI Cython layer for each new library (not scalable). Duck-typing protocols solve this by letting any Python class opt in to FFI compatibility through method implementation.

## Context and Constraints
- The Cython arg setter factory dispatches argument conversion per Python type. Protocols are checked via `hasattr()` on the argument's class (not instance), and the result is cached in the `TVMFFIPyArgSetter` function pointer table.
- Protocol methods must return values compatible with FFI type indices (objects, pointers, integers).
- Protocols must compose: a class can implement multiple protocols (e.g., both `__tvm_ffi_object__` and `__cuda_stream__`).
- The `__cuda_stream__` protocol aligns with NVIDIA's cuda-python interop specification.

## Goals
- Enable any Python class to participate in FFI calls by implementing a protocol method.
- Maintain zero-overhead dispatch for classes that do not implement protocols (they fall through to DLPack or OpaquePyObject wrapping).
- Support five interop patterns: object forwarding (return an FFI object), opaque pointer passing (return a raw pointer), CUDA stream communication (return a stream handle), DLPack data type exchange (return a dtype tuple), and DLPack device exchange (return a device tuple).

## Non-Goals
- Defining protocols for non-Python languages (C++, Rust). These have their own type trait mechanisms.
- Providing default implementations of protocols on built-in types (each protocol is opt-in).
- Runtime type checking of protocol return values (the return value is trusted).

## Design
### Components and Responsibilities

- **`__tvm_ffi_object__()`** (protocol method): Returns a TVM FFI object (`Object` subclass instance). The Cython arg setter extracts the underlying `TVMFFIObjectHandle` from the returned object. This enables wrapper classes that hold an FFI object as a member to participate in FFI calls without subclassing `Object`.
  - **Evolution**: Initially introduced as `__tvm_ffi_tensor__()` (commit `4bc89254`, tensor-specific), then generalized to `__tvm_ffi_object__()` (commit `8873700a`) to support any FFI object type.
  - **Internal rename**: `PyNativeObject.__tvm_ffi_object__` attribute was renamed to `_tvm_ffi_cached_object` (commit `8873700a`) to avoid dunder naming convention for internal attributes.
  - **Cython setter**: `TVMFFIPyArgSetterFFIObjectCompatible_` calls the protocol method and extracts the handle.

- **`__tvm_ffi_opaque_ptr__()`** (protocol method): Returns an integer (or object castable to `ctypes.c_void_p`) representing a raw opaque pointer. The Cython arg setter converts this to `kTVMFFIOpaquePtr` type index. This enables hardware runtime objects, opaque handles, and other pointer-based abstractions to be passed through FFI.
  - **Cython setter**: `TVMFFIPyArgSetterFFIOpaquePtrCompatible_` calls the protocol method and converts the return value to an opaque pointer argument.
  - Added in commit `42e0612`.

- **`__cuda_stream__()`** (protocol method): Returns an integer representing a CUDA stream handle. Aligns with NVIDIA's cuda-python interop protocol. The Cython arg setter converts this to an opaque pointer argument (`kTVMFFIOpaquePtr`).
  - **Cython setter**: `TVMFFIPyArgSetterCUDAStream_` extracts the handle via the protocol method.
  - **Backward compatibility**: `_optional_torch_c_dlpack.py` monkey-patches `__cuda_stream__` onto `torch.cuda.Stream` for older PyTorch versions (commit `965fc464`).
  - Added in commit `b0537f04`.

- **`__dlpack_data_type__()`** (protocol method): Returns a `(type_code, bits, lanes)` tuple representing a DLPack data type. The Cython arg setter converts this to a `TVMFFIDevice` dtype value. Additionally, the `dtype.from_dlpack_data_type()` static factory method accepts the same tuple format for explicit conversion. Objects with this protocol are auto-converted in FFI calls when used in dtype-accepting argument positions.
  - **Cython setter**: `TVMFFIPyArgSetterDLPackDataTypeProtocol_` calls the protocol method and converts to `DLDataType`.
  - **Internal rename**: `__tvm_ffi_dtype__` slot renamed to `_tvm_ffi_dtype` for consistency.
  - Added in commit `5e648f05`.

- **`__dlpack_device__()`** (protocol method): Returns a `(device_type, device_id)` tuple representing a DLPack device. The Cython arg setter converts this to a `TVMFFIDevice` value. This protocol is only used for objects that have `__dlpack_device__` but NOT `__dlpack__` (which would trigger the full DLPack tensor conversion path instead).
  - **Cython setter**: `TVMFFIPyArgSetterDLPackDeviceProtocol_` calls `arg.__dlpack_device__()` and converts to `TVMFFIDevice`.
  - Added in commit `0f8bf9fc`.

- **`TVMFFIPyArgSetterFactory`** (Cython callback): The central dispatch point. When a new Python type is encountered, the factory checks for protocols in priority order:
  1. Is it a known FFI type (Object, Function, etc.)? -> use dedicated setter.
  2. Does `arg_class` have `__tvm_ffi_object__`? -> `TVMFFIPyArgSetterFFIObjectCompatible_`.
  3. Does `arg_class` have `__tvm_ffi_opaque_ptr__`? -> `TVMFFIPyArgSetterFFIOpaquePtrCompatible_`.
  4. Does `arg_class` have `__cuda_stream__`? -> `TVMFFIPyArgSetterCUDAStream_`.
  5. Does `arg_class` have `__dlpack_data_type__`? -> `TVMFFIPyArgSetterDLPackDataTypeProtocol_`.
  6. Does `arg_class` have `__dlpack_device__` (without `__dlpack__`)? -> `TVMFFIPyArgSetterDLPackDeviceProtocol_`.
  7. Does `arg_class` have `__dlpack__`? -> DLPack tensor conversion path.
  8. Fallback: wrap as `OpaquePyObject`.

### Data Contracts and Invariants
- **Protocol return type contract**: `__tvm_ffi_object__()` must return a valid `Object` instance. `__tvm_ffi_opaque_ptr__()` must return an integer-compatible value. `__cuda_stream__()` must return an integer-compatible value. `__dlpack_data_type__()` must return a `(type_code, bits, lanes)` tuple. `__dlpack_device__()` must return a `(device_type, device_id)` tuple. Violating these contracts causes `TypeError` or `ValueError` at argument conversion time.
- **Class-level caching invariant**: Protocol detection is cached per `PyTypeObject*`. If a class dynamically adds/removes a protocol method after its first FFI use, the change is not detected. This is by design: dynamic protocol modification is not a supported pattern.
- **Priority ordering invariant**: `__tvm_ffi_object__` > `__tvm_ffi_opaque_ptr__` > `__cuda_stream__` > `__dlpack_data_type__` > `__dlpack_device__` (without `__dlpack__`) > `__dlpack__` (full tensor). A class implementing multiple protocols will use the highest-priority one.
- **`__dlpack_device__` vs `__dlpack__` distinction**: Objects with `__dlpack_device__` but NOT `__dlpack__` are treated as device descriptors (converted to `TVMFFIDevice`). Objects with both `__dlpack_device__` and `__dlpack__` are treated as tensors (converted via the full DLPack tensor exchange path). This prevents tensors from being accidentally converted to devices.

### Control Flow
1. Python caller invokes `ffi_func(my_wrapper_obj)`.
2. `TVMFFIPyCallManager::SetArgument()` looks up the cached setter for `type(my_wrapper_obj)`.
3. On cache miss, `TVMFFIPyArgSetterFactory` is called:
   a. Checks `hasattr(arg_class, "__tvm_ffi_object__")` -> if true, returns `TVMFFIPyArgSetterFFIObjectCompatible_`.
   b. Checks `hasattr(arg_class, "__tvm_ffi_opaque_ptr__")` -> if true, returns `TVMFFIPyArgSetterFFIOpaquePtrCompatible_`.
   c. Checks `hasattr(arg_class, "__cuda_stream__")` -> if true, returns `TVMFFIPyArgSetterCUDAStream_`.
   d. Checks `hasattr(arg_class, "__dlpack_data_type__")` -> if true, returns `TVMFFIPyArgSetterDLPackDataTypeProtocol_`.
   e. Checks `hasattr(arg_class, "__dlpack_device__")` and NOT `hasattr(arg_class, "__dlpack__")` -> if true, returns `TVMFFIPyArgSetterDLPackDeviceProtocol_`.
   f. Falls through to DLPack tensor exchange or OpaquePyObject.
4. The cached setter is called with the argument, converting it to the appropriate FFI representation.
5. On subsequent calls with the same type, the cached setter is used directly (O(1) dispatch).

### Extension Points
- **New protocols**: Add a `hasattr` check and corresponding setter function in `TVMFFIPyArgSetterFactory`. The pattern is well-established and requires ~20 lines of Cython per protocol.
- **Protocol chaining**: A future enhancement could support chaining (e.g., call `__tvm_ffi_object__` then `__tvm_ffi_env_stream__` on the result), though this is not currently implemented.

## Alternatives Considered
### Require inheritance from FFI base classes
- Pros: Strong type safety. No protocol lookup overhead.
- Cons: Tight coupling. Third-party classes cannot be retrofitted. Multiple inheritance conflicts with Cython cdef classes.

### Use `register_adapter(type, converter)` function
- Pros: Explicit registration. No naming conventions needed.
- Cons: Requires importing and calling the registration function. Cannot be done from the class definition alone. Less discoverable.

### Use `__class_getitem__` or type annotations for protocol detection
- Pros: More Pythonic (PEP 544 Protocol).
- Cons: Cython cannot inspect PEP 544 Protocol at the C level efficiently. Runtime protocol checking via `isinstance` is too slow for the hot path.

## Trade-offs
- **Optimized**: Zero-cost per-type caching (protocol check happens once per type, not per call), duck-typing flexibility (any class can participate), standard naming conventions (`__dunder__` methods are familiar to Python developers).
- **Sacrificed**: No static type checking of protocol compliance (a class implementing `__tvm_ffi_object__` incorrectly will fail at runtime, not compile time), class-level caching means dynamic protocol modification is not detected, priority ordering may surprise users who implement multiple protocols expecting all to be used.

## Interfaces and Compatibility
- **Python protocols**: `__tvm_ffi_object__() -> Object`, `__tvm_ffi_opaque_ptr__() -> int`, `__cuda_stream__() -> int`, `__dlpack_data_type__() -> tuple[int, int, int]`, `__dlpack_device__() -> tuple[int, int]`.
- **Cython setters**: `TVMFFIPyArgSetterFFIObjectCompatible_`, `TVMFFIPyArgSetterFFIOpaquePtrCompatible_`, `TVMFFIPyArgSetterCUDAStream_`, `TVMFFIPyArgSetterDLPackDataTypeProtocol_`, `TVMFFIPyArgSetterDLPackDeviceProtocol_`.
- **Python factory method**: `dtype.from_dlpack_data_type(type_code, bits, lanes)` provides explicit conversion from the `__dlpack_data_type__` tuple format.
- **Internal rename**: `__tvm_ffi_dtype__` slot renamed to `_tvm_ffi_dtype` (commit `5e648f05`).
- **Breaking change**: `__tvm_ffi_tensor__` was removed and replaced by `__tvm_ffi_object__` (commit `8873700a`). This happened before any formal release, so external impact is minimal.

## Failure Modes and Mitigations
- **Protocol method returns wrong type**: If `__tvm_ffi_object__()` returns a non-Object, the Cython layer raises `TypeError` with a diagnostic message. Similarly for the other protocols.
- **Stale cache entry**: If a class dynamically adds a protocol method after first FFI use, the old (non-protocol) setter remains cached. Mitigation: this is documented as unsupported. In practice, protocol methods are defined at class definition time.
- **`__cuda_stream__` on non-CUDA object**: If called on a CPU-only object, the stream handle is meaningless but harmless (the FFI stream context is only used for non-CPU devices).

## Observability and Validation
- `tests/python/test_tensor.py` includes benchmark and correctness tests for `__tvm_ffi_object__` protocol.
- `tests/python/test_function.py` tests `__tvm_ffi_opaque_ptr__` protocol, `__dlpack_data_type__` protocol, and `__dlpack_device__` protocol.
- `tests/python/test_device.py` tests `__cuda_stream__` protocol.
- `tests/python/test_dtype.py` tests `dtype.from_dlpack_data_type()` factory method.
- The `DLTensorTestWrapper` test class implements all relevant protocols for integration testing.

## Migration and Rollout
- New protocols: no migration needed for existing code.
- Classes using the short-lived `__tvm_ffi_tensor__` must rename to `__tvm_ffi_object__`.
- Older PyTorch versions get `__cuda_stream__` via monkey-patch in `_optional_torch_c_dlpack.py`.

## Diagrams
- [.memory/diagrams/0016-python-ffi-protocol-dispatch.md](.memory/diagrams/0016-python-ffi-protocol-dispatch.md)

## Related ADRs
- [.memory/ADRs/0021-c-level-arg-setter-dispatch.md](.memory/ADRs/0021-c-level-arg-setter-dispatch.md) (the dispatch mechanism that powers protocol caching)
- [.memory/ADRs/0033-dlpack-dtype-device-exchange-protocols.md](.memory/ADRs/0033-dlpack-dtype-device-exchange-protocols.md) (decision to use DLPack tuple protocols for dtype and device exchange)

## Related Design Docs
- [.memory/designs/0011-cython-binding-layer.md](.memory/designs/0011-cython-binding-layer.md) (the Cython layer where protocols are dispatched)
- [.memory/designs/0014-stream-exchange-protocol.md](.memory/designs/0014-stream-exchange-protocol.md) (the `__tvm_ffi_env_stream__` protocol)

## Evidence Matrix
- `__tvm_ffi_tensor__` protocol (initial, tensor-specific) -> `.memory/commits/2025-10-13-4bc89254.md` + `4bc89254` + `python/tvm_ffi/cython/function.pxi`
- `__tvm_ffi_object__` protocol (generalized) -> `.memory/commits/2025-10-14-8873700a.md` + `8873700a` + `python/tvm_ffi/cython/function.pxi`, `python/tvm_ffi/cython/object.pxi`
- `_tvm_ffi_cached_object` internal rename -> `8873700a` + `python/tvm_ffi/cython/object.pxi`
- `__tvm_ffi_opaque_ptr__` protocol -> `.memory/commits/2025-10-16-42e0612.md` + `42e0612` + `python/tvm_ffi/cython/function.pxi`
- `__cuda_stream__` protocol -> `.memory/commits/2025-10-13-b0537f04.md` + `b0537f04` + `python/tvm_ffi/cython/function.pxi`
- `__cuda_stream__` monkey-patch on older PyTorch -> `.memory/commits/2025-10-13-965fc464.md` + `965fc464` + `python/tvm_ffi/_optional_torch_c_dlpack.py`
- `__dlpack_data_type__` protocol and `dtype.from_dlpack_data_type()` -> `.memory/commits/2025-10-20-5e648f05.md` + `5e648f05` + `python/tvm_ffi/_dtype.py`, `python/tvm_ffi/cython/function.pxi`, `python/tvm_ffi/cython/dtype.pxi`
- `__dlpack_device__` protocol -> `.memory/commits/2025-10-20-0f8bf9fc.md` + `0f8bf9fc` + `python/tvm_ffi/cython/function.pxi`

## Open Questions
- Should there be a way to dynamically invalidate the per-type setter cache (e.g., after dynamically adding a protocol method)?
- Should `__tvm_ffi_opaque_ptr__` support returning a ctypes pointer directly rather than requiring an integer?
- Should there be a formal `Protocol` definition (PEP 544) for each of these, even if the Cython layer does not use it for dispatch?

## Confidence and Risk
- Confidence: high
- Residual risks: The priority ordering of protocol checks is implicit and not documented in user-facing APIs. A class implementing both `__tvm_ffi_object__` and `__dlpack__` will always use `__tvm_ffi_object__`, which may surprise users expecting DLPack conversion. The class-level caching means protocol detection is not inheritance-aware: if a base class adds a protocol method after a subclass was already cached, the subclass's setter is not updated.
