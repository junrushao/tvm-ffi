# 2025-08-19 -- 0daaffedd23982ea09f8c38fec4eef1cca1d8cac (shape: standard)
- **Procedure friction**: None.
- **Template gap**: The template has no section for "error-handling pattern choice" -- this commit's most interesting design decision is *why* `TVMFFIEnvGetCurrentStream` uses `LOG_EXCEPTION_CALL` instead of `SAFE_CALL`, but that reasoning fits awkwardly into either Key Exports or Design Elements. Had to fold it into Design Elements as a "produced" element.
- **Wasted effort**: Step 3.4 cross-layer consistency check was irrelevant -- this commit only touches C++ and CMake, no Python/Rust/Cython layer changes.
- **Suggested skill change**: None -- the friction is minor and specific to this commit's small scope.
