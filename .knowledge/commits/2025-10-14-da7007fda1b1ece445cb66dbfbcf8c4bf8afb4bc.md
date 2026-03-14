---
author: "external-contributor"
subject: "Split testing.cc into separate libtvm_ffi_testing.so library"
scope:
  - "packaging-and-build"
impact: "low"
---
# Split testing.cc into separate libtvm_ffi_testing.so library
## TL;DR
- Moves `src/ffi/extra/testing.cc` to `src/ffi/testing/testing.cc` and builds it as a separate `libtvm_ffi_testing.so` shared library.
- Python `tvm_ffi.testing` auto-loads the testing library. Rust tests updated to link against it.
- Reduces main library size by excluding test-only registrations.

## Impact
- API: Testing functions now in separate library. Python `testing.py` loads it transparently.
- Flags/config: New CMake target `tvm_ffi_testing`.
- Data formats/schemas: None.

## Design Elements
Design elements this commit consumes:
- **Packaging and build** (`.knowledge/designs/0016-packaging-and-build.md`): CMake library targets.
- **Module system** (`.knowledge/designs/0013-module-system.md`): Shared library loading.

Design elements this commit produces:
- **Separate testing library pattern**: Test-only FFI registrations split into their own shared library.

## Reflection
* **Design docs to write**: None.
* **ADRs to write**: None.
* **Design diagrams to draw**: None.
* **Skill evolution (`/commit-ledger`)**: None.

## Self-Evolution of Skill /commit-ledger
None.
