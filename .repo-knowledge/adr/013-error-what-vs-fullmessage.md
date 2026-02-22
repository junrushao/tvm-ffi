# ADR 013: Error::what() vs Error::FullMessage() Split

- Status: Accepted
- Date: 2025-11-07
- Owners: Tianqi Chen

## Context

`tvm::ffi::Error` inherits from `std::exception`. The C++ standard requires
`std::exception::what()` to be `noexcept(true)` and return a simple
descriptive string.

The previous implementation of `Error::what()` allocated a thread-local
`std::string` containing the full traceback-prefixed message (kind, message,
and stack trace). This violated both the spirit and letter of the standard:

1. `what()` is `noexcept` but allocation can fail.
2. Thread-local storage (TLS) in headers caused issues with LLVM JIT
   compilation contexts.
3. The full traceback string was returned even when callers only needed the
   plain error message.

## Decision

Split `Error` output into two methods (`4bccb3e`):

- **`Error::what()`** returns only the plain error message
  (`obj->message.data`) with no allocation and no traceback or kind prefix.
  Truly `noexcept`.

- **`Error::FullMessage()`** returns the full
  `"Traceback (most recent call last):\n{trace}{kind}: {message}\n"` string,
  equivalent to the previous `what()` output. This method may allocate.

`ErrorBuilder::~ErrorBuilder()` was updated to use `FullMessage()` for
`std::cerr` logging.

## Consequences

- Positive:
  - `what()` now conforms to `std::exception::what()` noexcept semantics
  - Eliminates TLS usage in the error header, improving JIT compatibility
  - Callers that only need the message get a simpler, allocation-free path

- Negative:
  - Breaking change: C++ code parsing `what()` output to extract error kind
    or stack trace must migrate to `FullMessage()`
  - Four C++ test cases were updated (`tests/cpp/test_error.cc`)

- Migration/Rollout:
  - Replace `error.what()` with `error.FullMessage()` wherever the full
    traceback-prefixed message is needed
  - Python-side error formatting uses the C++ call path and was verified
    to work correctly

## References
- Range summary: `.repo-knowledge/ranges/2025-11-30-0EE6444-4076EF5.md`
- Evidence commits: `4bccb3e`
- External references: C++ standard `[exception]` clause; `noexcept` requirement on `std::exception::what()`

## Related Design Docs
- `.repo-knowledge/design/001-type-erased-value-system.md`

## Notes
The `FullMessage()` method constructs the string on each call rather than
caching it. This is acceptable because error formatting is not a hot path.
The thread-local string that was previously used for caching in `what()` has
been removed entirely.
