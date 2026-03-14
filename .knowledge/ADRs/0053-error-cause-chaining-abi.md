---
scope:
  - "0007-error-handling"
  - "0001-c-abi"
---
# Error Cause Chaining ABI Extension

**TL;DR**: The `TVMFFIErrorCell` C struct was extended with two appended fields (`cause_chain` and `extra_context`) to support error cause chaining across FFI boundaries. A new C API `TVMFFIErrorCreateWithCauseAndExtraContext` enables constructing errors with these fields. The change is backward compatible because only trailing fields are added.

## Context

When an error is re-raised or wrapped across FFI boundaries (e.g., a C++ function catches a Python-originated error and wraps it with additional context), the original cause is lost. Python natively supports `__cause__` (explicit chaining via `raise X from Y`) and `__context__` (implicit chaining). The FFI error ABI had no way to carry this causal chain.

Usecases:
- A C++ runtime catches an error from a Python callback and needs to wrap it with C++-side context while preserving the original Python traceback and error type.
- Cross-language error diagnostics: a debugger or logging framework wants to walk the full chain of errors that led to a failure, spanning C++ and Python boundaries.
- Attaching opaque framework-specific context (e.g., a Python exception object) to an FFI error for later retrieval by the originating language.

Design Decisions:
- Append two `TVMFFIObjectHandle` fields to `TVMFFIErrorCell`: `cause_chain` (optional linked error) and `extra_context` (optional opaque object). Both are `nullptr` by default and owned by the `ErrorCell` (ref-counted via `DecRefObjectHandle` in the `ErrorObj` destructor).
- Provide a new C API `TVMFFIErrorCreateWithCauseAndExtraContext` that accepts both fields at creation time, alongside the existing `TVMFFIErrorCreate` which leaves them null.
- On the C++ side, add a 5-argument `Error` constructor (`kind`, `message`, `backtrace`, `optional<Error> cause_chain`, `optional<ObjectRef> extra_context`) and corresponding accessor methods `Error::cause_chain()` and `Error::extra_context()` returning `std::optional`.

**Alternatives considered:**

1. **Separate error wrapper type**: Introduce a new `ErrorChain` object that wraps a list of errors.
   - Pro: Does not modify the stable `TVMFFIErrorCell` ABI.
   - Con: Adds a new type to the system. Error consumers would need to know about both `Error` and `ErrorChain`. Does not integrate naturally with existing error construction and propagation paths.

2. **Store cause chain in backtrace string**: Serialize the cause chain into the existing `backtrace` field as formatted text.
   - Pro: No ABI change.
   - Con: Loses structured access. Cannot walk the chain programmatically or extract error kind/message from causes. Cannot attach opaque Python exception objects.

**Why this decision was chosen:**
- Appending fields to a C struct is backward compatible in C ABI (field offsets of existing members are unchanged). Code that does not read the new fields continues to work.
- `TVMFFIObjectHandle` is the universal cross-language handle type, so both `cause_chain` (always an `Error`) and `extra_context` (any `Object`) can be any object. This avoids introducing new handle types.
- The ownership model (decref in destructor) follows the existing pattern for `TVMFFIObject` handles throughout the codebase.

## Implementation Notes

- `ErrorObj` default constructor initializes both new fields to `nullptr`.
- `ErrorObj` destructor calls `details::ObjectUnsafe::DecRefObjectHandle` on each non-null handle.
- The 5-argument `Error` constructor uses `details::ObjectUnsafe::MoveObjectRefToTVMFFIObjectPtr` to transfer ownership into the handles.
- `Error::cause_chain()` returns `std::optional<Error>` by constructing a non-owning reference from the handle.
- `Error::extra_context()` returns `std::optional<ObjectRef>` similarly.
- `TVMFFIErrorCreateWithCauseAndExtraContext` wraps the 5-argument constructor at the C API level with standard error-code return semantics.
- Python-side integration (mapping to `__cause__`/`__context__`) is not yet implemented; the C/C++ ABI is the enabler.

## Related Design Docs

- [`.knowledge/designs/0007-error-handling.md`](../designs/0007-error-handling.md)
- [`.knowledge/designs/0001-c-abi.md`](../designs/0001-c-abi.md)
- [`.knowledge/ADRs/0039-backtrace-rename-and-append-mode.md`](0039-backtrace-rename-and-append-mode.md)
