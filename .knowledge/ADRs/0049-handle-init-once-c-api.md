---
scope:
  - "0001-c-abi"
---
# Thread-Safe Handle Init Once via C API

**TL;DR**: `TVMFFIHandleInitOnce` and `TVMFFIHandleDeinitOnce` provide a C-ABI-level thread-safe one-time initialization primitive for static handles, targeting DSL/compiler-generated code that cannot rely on C++ `std::call_once`.

## Context

DSL settings (e.g., LLVM-generated code, MLIR-emitted function calls) need to lazily initialize static handles (function pointers, module references) in a thread-safe manner. C++ provides `std::call_once` and block-scope static initialization, but generated C code and some embedded environments lack these facilities.

Usecases:
- LLVM-generated code that needs to resolve a function handle once at first call.
- Compiler-generated C code that initializes global state lazily.
- Any C-only consumer of the FFI that needs thread-safe singleton initialization.

Design Decisions:
- **Double-checked locking with atomics**: Fast path uses `__atomic_load_n` (acquire) to check if the handle is already set. Slow path uses a global `std::mutex` for serialization. This avoids requiring C11 `_Atomic` or C++ `std::atomic` at the call site.
- **Platform-specific atomics**: Uses `InterlockedCompareExchangePointerAcquire` on MSVC, `__atomic_load_n/__atomic_store_n` on GCC/Clang. This makes the function usable from C code without C++ standard library dependency.
- **Non-null result requirement**: `init_func` must return a non-null handle; returning null is treated as an error. This simplifies the double-checked locking pattern (null = uninitialized).
- **Symmetric deinit**: `TVMFFIHandleDeinitOnce` uses `__atomic_exchange_n` (acq_rel) to atomically swap the handle to null and call the deinit function only if it was non-null.

Alternatives considered:
- **Require C++ `std::call_once`**: Simpler but excludes pure C consumers and LLVM-emitted code.
- **Expose `pthread_once`**: POSIX-only; no Windows support. The atomic approach is portable.
- **Static initializer sections**: Platform-specific (`__attribute__((constructor))`, `DllMain`), not suitable for lazy initialization.

## Implementation Notes

- Implementation in `src/ffi/init_once.cc` (94 lines).
- The global `std::mutex` for the slow path is acceptable because initialization happens at most once per handle; contention is transient.
- Error propagation: if `init_func` fails, it should call `TVMFFIErrorSetRaisedFromCStr` and return nonzero, which propagates to the caller.

## Related Design Docs

- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md)
- Evidence: `.knowledge/commits/2025-12-05-25c25aec22acadcf1aeb839297fe156bc0cf7183.md` + `25c25ae`
