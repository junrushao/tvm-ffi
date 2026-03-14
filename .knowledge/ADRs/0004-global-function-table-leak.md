---
scope:
  - "0004-function-system"
---
# Intentional Memory Leak of GlobalFunctionTable

**TL;DR**: `GlobalFunctionTable` is allocated via `new` and never deleted. Entries are ref-counted `Object` subclasses stored in a leaked `Map<String, Any>`. This is intentional to avoid use-after-free bugs during Python interpreter shutdown and process forking.

## Context

The `GlobalFunctionTable` singleton holds registered `Function` objects, some of which contain Python callbacks (via `ExternCFunctionObjImpl`). These callbacks hold references to Python objects. Two scenarios make deterministic destruction dangerous:

1. **Python interpreter shutdown order**: When the Python interpreter shuts down, Python objects are freed in an unpredictable order. If the `GlobalFunctionTable` destructor runs and attempts to `DecRef` a `Function` that wraps a Python callback, it may call into the Python runtime after it has been partially torn down.

2. **Process forking**: When a process forks, static locals are shared via copy-on-write pages. If the child process triggers destruction of a `GlobalFunctionTable` that references Python objects from the parent's interpreter, it accesses invalid memory.

Usecases:
- Python registers `tvm.register_global_func("my_func", python_callable)`.
- At interpreter shutdown, Python destroys the callable. If the C++ table still holds a reference and tries to decrement it, use-after-free occurs.

Design Decisions:
- **Allocate with `new`, never `delete`**: `static GlobalFunctionTable* inst = new GlobalFunctionTable()` -- the singleton leaks at process exit.
- **Store `Entry` objects in `Map<String, Any>`**: Entries are `Object` subclasses embedding `TVMFFIMethodInfo` metadata. The `Map` itself is a ref-counted container, but since the `GlobalFunctionTable` pointer is leaked, the `Map` is never destructed either. This preserves the intentional-leak guarantee despite the migration from raw `Function*` pointers to ref-counted `Entry` objects.

**Alternatives considered**:

1. **Static local with destructor**: Destructor order relative to Python is undefined. Known to cause crashes.
2. **shared_ptr or ref-counted singleton**: The ref-count reaching zero during shutdown is the scenario we want to avoid.
3. **Weak references with explicit cleanup**: Requires Python-side cooperation. Error-prone.

**Consequences**:
- Memory leak at process exit. Bounded (one table + entries) and reclaimed by the OS.
- Valgrind/leak sanitizers will report these allocations. They should be suppressed in CI.
- The leak guarantee holds even after the migration from `std::unordered_map<String, Function*>` to `Map<String, Any>` with `Entry` objects, because the `Map` is inside the leaked singleton.

## Implementation Notes

- `GlobalFunctionTable::Global()` uses `static T* inst = new T()`.
- The table stores `Map<String, Any>` where each value is a `GlobalFunctionTable::Entry` object embedding `TVMFFIMethodInfo`.
- `Entry` inherits both `Object` (for ref-counting) and `TVMFFIMethodInfo` (for metadata).
- `EnvCAPIRegistry` uses the same intentional-leak pattern.
- `TypeTable` uses a different pattern (`static TypeTable inst;`) because it does not hold Python callbacks.
- Evidence: `src/ffi/function.cc` (GlobalFunctionTable::Global), commits `7d34eb8`, `1a85688`.

## Related Design Docs

- [`.knowledge/designs/0004-function-system.md`](../designs/0004-function-system.md) -- GlobalFunctionTable design
- [`.knowledge/ADRs/0010-globaldef-replaces-register-global.md`](0010-globaldef-replaces-register-global.md) -- GlobalDef replaced TVM_FFI_REGISTER_GLOBAL
