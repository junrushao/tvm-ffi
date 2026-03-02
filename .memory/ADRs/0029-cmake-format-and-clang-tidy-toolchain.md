---
adr: "0029"
title: "Adopt cmake-format/cmake-lint and clang-tidy for C++/CMake quality"
status: "accepted"
date: "2025-10-07"
deciders:
  - "Junru Shao"
consulted:
  - "Tianqi Chen"
informed:
  - "TVM FFI contributors"
tags:
  - "infrastructure"
  - "lint"
  - "ci"
source_commits:
  - "98b26edda72c3d9b9480cb638a68d07d3df6b88f"
  - "0d8fec88eca5acaeaa7e771003d183c31711574a"
  - "cdc1ccca64bf6fda32da0be266cc727e0c3bcb34"
source_ledgers:
  - ".memory/commits/2025-10-05-98b26edd.md"
  - ".memory/commits/2025-10-07-0d8fec88.md"
  - ".memory/commits/2025-10-08-cdc1ccca.md"
---

# ADR-0029: Adopt cmake-format/cmake-lint and clang-tidy for C++/CMake quality

## TL;DR
- Added `cmake-format` and `cmake-lint` to pre-commit hooks with a `.cmake-format.json` configuration (100-col, 2-space indent), completing the TODO from ADR-0023.
- Introduced `.clang-tidy` configuration enabling modernize-*, bugprone-*, performance-*, portability-*, and google-* checks, with a manual `clang_tidy_precommit.py` runner (not integrated into pre-commit due to cost).

## Status
accepted

## Context
After adopting pre-commit hooks (ADR-0023), CMake files had no formatting standard and C++ code had no static analysis beyond clang-format. CMake files used inconsistent indentation, variable naming, and parenthesization. C++ code had modernization opportunities (e.g., `_v`/`_t` type trait suffixes, `using` over `typedef`, `noexcept` on move operations) and a correctness issue (`AnyUnsafe::MoveTVMFFIAnyToAny` taking rvalue ref instead of pointer). Additionally, the libbacktrace build configuration used an undefined `${MACHINE_NAME}` CMake variable for `--host`, silently breaking cross-compilation.

## Decision Drivers
- ADR-0023 explicitly listed cmake-format as a follow-up TODO.
- clang-tidy can catch correctness bugs (e.g., the `MoveTVMFFIAnyToAny` dangling reference) that clang-format cannot.
- CMake files are a cross-platform surface that benefits from consistent formatting.
- libbacktrace cross-compilation was silently broken due to the undefined variable.

## Decision
1. **cmake-format**: Added `cmake-format` (v0.6.13) and `cmake-lint` hooks to `.pre-commit-config.yaml`. Configuration in `.cmake-format.json`: 100-col line width, 2-space indent, dangle parentheses, unix line endings, underscore-prefixed local variables.

2. **clang-tidy**: Added `.clang-tidy` configuration file enabling:
   - `modernize-*`: `_v`/`_t` suffixes, `using` over `typedef`, `std::move`, `= default`
   - `bugprone-*`: dangling references, unused variables, forwarding issues
   - `performance-*`: unnecessary copies, `reserve()` calls
   - `portability-*`: platform-specific issues
   - `google-*`: Google style compliance
   With selected exclusions (e.g., `modernize-concat-nested-namespaces` since TVM FFI uses pre-C++17 namespace syntax).

   clang-tidy is NOT added to pre-commit (too expensive) and runs via `tests/lint/clang_tidy_precommit.py` with explicit invocation or CI step.

3. **libbacktrace cleanup**: Replaced the broken `--host=${MACHINE_NAME}` with a new `detect_target_triple()` CMake function in `cmake/Utils/DetectTargetTriple.cmake` that auto-detects the target triple from the compiler. Suppressed noisy libbacktrace build output with `LOG_*` directives.

## Alternatives Considered
### Add clang-tidy to pre-commit hooks
- Pros: Automatic enforcement, same as cmake-format.
- Cons: clang-tidy requires a full compile_commands.json and takes 30-60 seconds per file. Pre-commit hooks should complete in seconds. Would slow down every commit significantly.

### Use cmake-format without cmake-lint
- Pros: Simpler config (one hook instead of two).
- Cons: cmake-lint catches semantic issues (e.g., wrong function signatures, deprecated commands) that cmake-format does not.

### Fix libbacktrace --host with a simple uname -m
- Pros: One-line fix.
- Cons: Does not handle cross-compilation (e.g., building on x86_64 for aarch64). The `detect_target_triple()` approach handles Emscripten, Android, iOS, QNX, Windows, Linux, macOS, and FreeBSD.

## Why This Option Won
- cmake-format fills a concrete gap identified in ADR-0023 and integrates seamlessly with pre-commit.
- clang-tidy as a manual/CI tool balances correctness catching with developer velocity.
- The target triple detection is comprehensive and reusable for any cross-compilation scenario.

## Consequences
### Positive
- All CMake files have consistent formatting and pass cmake-lint.
- C++ code uses modern idioms (`_v`/`_t` suffixes, `using`, `noexcept` on move ops).
- The `MoveTVMFFIAnyToAny` dangling reference bug was caught and fixed.
- libbacktrace cross-compilation now works correctly.

### Negative
- Large initial diff for cmake-format (+496/-322) and clang-tidy (60+ files), all mechanical.
- clang-tidy is not enforced automatically; developers must run it manually or rely on CI.

### Risks
- cmake-format version pinning (v0.6.13) may drift from cmake-lint expectations. Mitigated by pre-commit `autoupdate`.
- clang-tidy check selection may be too aggressive or miss important checks. Can be tuned in `.clang-tidy`.
- `detect_target_triple()` may not handle all exotic cross-compilation targets. Has a synthesis fallback for unknown targets.

## Implementation Notes
- `.cmake-format.json` configuration with 100-col, 2-space indent, dangle parens.
- `.clang-tidy` with selected check groups and exclusions.
- `tests/lint/clang_tidy_precommit.py` runner script for manual invocation.
- `cmake/Utils/DetectTargetTriple.cmake` (303 lines) with compiler query, platform detection, and synthesis fallback.
- libbacktrace ExternalProject uses `LOG_CONFIGURE ON`, `LOG_BUILD ON`, `LOG_INSTALL ON`, `LOG_OUTPUT_ON_FAILURE ON`.

## Validation
- `pre-commit run cmake-format --all-files` passes on all CMake files.
- `pre-commit run cmake-lint --all-files` passes on all CMake files.
- `clang_tidy_precommit.py` runs cleanly on all C++ sources.
- `cmake . -B build_test` succeeds with the new detect_target_triple for libbacktrace.

## Migration and Rollback
- Migration: One-time reformatting applied in the commits. No developer action needed.
- Rollback: Remove hooks from `.pre-commit-config.yaml`, delete `.cmake-format.json` and `.clang-tidy`.

## Related Design Docs
None (infrastructure decision)

## Related Diagrams
None

## Evidence Matrix
- `.cmake-format.json` and cmake-format/cmake-lint hooks -> `.memory/commits/2025-10-05-98b26edd.md` + `98b26edd` + `.cmake-format.json`, `.pre-commit-config.yaml`
- `.clang-tidy` config and modernization fixes -> `.memory/commits/2025-10-07-0d8fec88.md` + `0d8fec88` + `.clang-tidy`, `include/tvm/ffi/`, `src/ffi/`
- `MoveTVMFFIAnyToAny` signature fix (rvalue ref to pointer) -> `0d8fec88` + `include/tvm/ffi/any.h`
- `noexcept` on `Any`/`AnyView` move ops -> `0d8fec88` + `include/tvm/ffi/any.h`
- `clang_tidy_precommit.py` runner -> `0d8fec88` + `tests/lint/clang_tidy_precommit.py`
- `detect_target_triple()` CMake function -> `.memory/commits/2025-10-08-cdc1ccca.md` + `cdc1ccca` + `cmake/Utils/DetectTargetTriple.cmake`
- libbacktrace LOG suppression -> `cdc1ccca` + `cmake/Utils/AddLibbacktrace.cmake`

## Supersedes
None (extends ADR-0023 follow-up items)

## Superseded By
None

## Follow-up Actions
- Add clang-tidy to CI as a conditional step (triggered when C++ files change).
- Consider enabling additional clang-tidy check groups as the codebase matures.
