---
sha: "d5d2d12eab1bac530abfcac06b258a6d99f5cd7b"
date: "2025-10-28T07:03:41-07:00"
author: "Junru Shao"
subject: "chore: Fix clang-tidy warnings (#197)"
nature: ["chore"]
tags: ["cpp", "lint"]
scope: ["include", "src"]
risk: "low"
---

# d5d2d12 — chore: Fix clang-tidy warnings (#197)

## TL;DR
- Addresses new clang-tidy warnings to ensure the codebase passes per-commit clang-tidy (enabled in the subsequent PR #95).
- Changes include NOLINTBEGIN/END blocks, function signature fixes, and a method wrapper refactor.

## Why (intent / motivation)
- Preparing for clang-tidy enforcement in CI (PR #95); resolving all outstanding warnings before enabling the check.

## What changed (facts from diff)
- `include/tvm/ffi/base_details.h`: Replaced per-line `NOLINTNEXTLINE` with `NOLINTBEGIN/END` block around `StableHashBytes` body.
- `include/tvm/ffi/c_api.h`: Added `NOLINTBEGIN/END(modernize-macro-to-enum)` around version macros.
- `include/tvm/ffi/container/array.h`: Added `NOLINT(performance-unnecessary-value-param)` to iterator constructor and `Assign` method.
- `include/tvm/ffi/reflection/access_path.h`: Added `NOLINTNEXTLINE(performance-unnecessary-value-param)` to `FromSteps`.
- `include/tvm/ffi/reflection/registry.h`: Changed method wrapper lambda `const Class target` to `const Class& target` (avoids unnecessary copy).
- `src/ffi/testing/testing.cc`: Added `NOLINTNEXTLINE(bugprone-reserved-identifier)` and `NOLINTNEXTLINE(bugprone-casting-through-void)` comments.

## Public surface changes (if any)
- API: `const Class&` in reflection method wrapper is a behavior-neutral fix (avoids a copy).
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none
- How to verify manually: `uv run --no-project --with "clang-tidy==21.1.1" python tests/lint/clang_tidy_precommit.py --build-dir=build-pre-commit --jobs=4 ./src/ ./include ./tests`
- CI impact: Required for the clang-tidy CI job enabled in PR #95.

## Risk & rollout notes
- Risk level: low — lint suppressions and minor code cleanup.
- Rollout/migration: none
- Follow-ups: PR #95 enables clang-tidy in CI.

## Evidence
### Changed files
- `include/tvm/ffi/base_details.h` +2/-2 (M)
- `include/tvm/ffi/c_api.h` +2/-0 (M)
- `include/tvm/ffi/container/array.h` +2/-2 (M)
- `include/tvm/ffi/reflection/access_path.h` +1/-1 (M)
- `include/tvm/ffi/reflection/registry.h` +1/-1 (M)
- `src/ffi/testing/testing.cc` +3/-0 (M)

### Notable symbols / endpoints / configs touched
- `StableHashBytes` NOLINT block
- `const Class&` fix in `ReflectionDefBase` method wrapper

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/d5d2d12eab1bac530abfcac06b258a6d99f5cd7b.md`
