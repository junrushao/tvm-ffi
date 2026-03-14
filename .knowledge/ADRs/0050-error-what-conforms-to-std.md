---
scope:
  - "0007-error-handling"
---
# Error::what() Returns Message Only (std::exception Conformance)

**TL;DR**: `Error::what()` was changed to return only the message string (not the full trace+kind), conforming to `std::exception::what()` semantics. A new `Error::FullMessage()` provides the complete output for logging and display.

## Context

`Error::what()` previously returned a concatenation of traceback, error kind, and message, assembled in a `thread_local std::string`. This had two problems: (1) it violated the `std::exception` contract that `what()` returns a brief description, and (2) the thread-local string caused issues with LLVM JIT compilation (TLS is problematic in JIT'd code).

Usecases:
- C++ `catch` blocks that log `error.what()` expect a brief message, not a multi-line traceback.
- LLVM JIT environments where thread-local storage is unavailable or unreliable.
- Callers that need the full traceback use `FullMessage()` explicitly.

Design Decisions:
- **`what()` returns `obj->message.data`**: Direct pointer to the ErrorObj's message field. No allocation, no TLS.
- **`FullMessage()` returns `std::string`**: Constructs the full "Traceback...\nKind: message\n" string on demand. Not `noexcept`, which is acceptable since it is not called from destructors.
- **`ErrorBuilder` destructor uses `FullMessage()`**: The `log_before_throw_` path in `~ErrorBuilder` was updated to call `FullMessage()` instead of `what()` to preserve the detailed output when logging before throwing.

Alternatives considered:
- **Keep `what()` verbose but remove TLS**: Would still violate `std::exception` contract; callers that compare `what()` strings would break.
- **Return `kind + ": " + message` from `what()`**: A middle ground, but still does not conform to the brief-description expectation of `std::exception`.

## Implementation Notes

- All test assertions were updated from `error.what()` to `error.FullMessage()` for checking trace and kind presence.
- The change is observable: any code that was parsing `error.what()` for traceback info must switch to `error.FullMessage()`.

## Related Design Docs

- [`.knowledge/designs/0007-error-handling.md`](../designs/0007-error-handling.md)
- Evidence: `.knowledge/commits/2025-11-07-4bccb3eda0d543be67ec56204e045ca3e3b88641.md` + `4bccb3e`
