# ADR 016: Error Cause Chaining via TVMFFIErrorCell Extension

- Status: Accepted
- Date: 2026-01-11
- Owners: Tianqi Chen

## Context

Python supports exception chaining (`raise B from A`) to preserve the
causal relationship between exceptions. When errors cross the FFI boundary
(e.g., a Python callback raises inside a C++ function, which then raises
its own error), the original cause is lost because `TVMFFIErrorCell` had no
mechanism to attach a causal error or frontend-specific context.

## Decision

Extend `TVMFFIErrorCell` (`4c712ca`) with two new optional fields appended
at the end of the struct:

- `cause_chain` (`TVMFFIObjectHandle`): An optional reference to a prior
  `Error` object, forming a linked list of causal errors. This enables
  `raise B from A` semantics across language boundaries.

- `extra_context` (`TVMFFIObjectHandle`): An optional reference to an
  opaque object (e.g., a captured Python exception) for frontend-specific
  context that cannot be represented as a TVM FFI Error.

A new C API function was added:

```c
TVM_FFI_DLL int TVMFFIErrorCreateWithCauseAndExtraContext(
    const TVMFFIByteArray* kind,
    const TVMFFIByteArray* message,
    const TVMFFIByteArray* backtrace,
    TVMFFIObjectHandle cause_chain,
    TVMFFIObjectHandle extra_context,
    TVMFFIObjectHandle* out);
```

On the C++ side, `Error` gained:
- A constructor accepting `optional<Error> cause` and
  `optional<ObjectRef> extra_context`
- `cause_chain()` and `extra_context()` accessor methods
- Default constructor/destructor in `ErrorObj` to manage refcounts for the
  new fields

The extension is ABI-backward compatible: new fields are appended at the
end of `TVMFFIErrorCell`. Existing compiled code that does not read the new
fields is unaffected.

## Consequences

- Positive:
  - Enables future Python-side exception chaining (`raise B from A`) across
    the FFI boundary without losing the original cause
  - `extra_context` provides a generic hook for attaching frontend-specific
    error objects (e.g., Python exception state, JavaScript Error objects)
  - ABI-backward compatible: no recompilation needed for consumers that
    ignore the new fields

- Negative:
  - Code that allocates `TVMFFIErrorCell` by fixed size (e.g., via
    `sizeof(TVMFFIErrorCell)`) must be recompiled to account for the new
    fields
  - The Python-side exception chaining support is not yet implemented;
    this commit only lays the C/C++ groundwork

- Migration/Rollout:
  - Recompile consumer code against new headers to pick up the struct
    extension
  - The new fields default to `nullptr`; existing error creation code
    continues to work unchanged
  - Follow-up work: implement Python-side exception chaining using
    `extra_context`

## References

- Range summary: `.repo-knowledge/ranges/2026-01-30-C51E519-B508698.md`
- Evidence commits: `4c712ca3ec72ad18c10e42e5ef8b7f91ec23a803`
- External references: Python PEP 3134 (exception chaining)

## Related Design Docs

- `.repo-knowledge/design/003-c-abi-stability.md`

## Notes

The `cause_chain` field forms a singly-linked list of errors. Each error in
the chain is a full `Error` object with its own kind, message, and
backtrace. The chain is not limited in depth but is expected to be short in
practice (1-3 levels). Traversal is done via `error.cause_chain()` which
returns `Optional<Error>`.

The `extra_context` field is deliberately typed as `ObjectRef` (not
`Error`) to allow frontends to attach arbitrary metadata. A typical use
case is storing a Python exception object so that when the error is
re-raised in Python, the original traceback can be restored.
