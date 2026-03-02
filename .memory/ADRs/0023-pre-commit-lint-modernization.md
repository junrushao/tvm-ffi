---
adr: "0023"
title: "Replace task_lint.sh with pre-commit hooks and Ruff"
status: "accepted"
date: "2025-09-17"
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
  - "64e4b7f01896e3b755a49f5f4f7c25329aacc0b7"
  - "0bc968d1c6c76db80e69d2e860eafc8e0a3e9a69"
  - "8f4e044a90ff8a3db15742274f2c7df435142b04"
source_ledgers:
  - ".memory/commits/2025-09-17-64e4b7f01896e3b755a49f5f4f7c25329aacc0b7.md"
  - ".memory/commits/2025-09-17-0bc968d1c6c76db80e69d2e860eafc8e0a3e9a69.md"
  - ".memory/commits/2025-09-17-8f4e044a90ff8a3db15742274f2c7df435142b04.md"
---

# ADR-0023: Replace task_lint.sh with pre-commit hooks and Ruff

## TL;DR
- Replaced the monolithic `tests/scripts/task_lint.sh` shell script with composable pre-commit hooks covering Python (Ruff), C++ (clang-format), Cython (cython-lint), shell (shfmt/shellcheck), and ASF header/filetype checks.
- Adopted Ruff as the single Python lint and formatting tool, replacing black + isort + pylint, and progressively enabled UP, PL, I, RUF, NPY, F, PTH, D, and ANN rule sets.

## Status
accepted

## Context
The standalone TVM FFI repository inherited `task_lint.sh` from the main TVM project. This
script installed black, pylint, ruff, and clang-format via pip inside CI, ran them
sequentially, and was not easily runnable locally by developers. The script mixed concerns
(formatting, linting, header checks, filetype checks) into a single sequential shell flow.

The repository needed:
1. A lint system that developers can run locally with the same behavior as CI.
2. Per-language lint isolation (Python, C++, Cython, shell scripts).
3. A path to progressive rule tightening without breaking existing CI.

## Decision Drivers
- **Developer experience**: `pre-commit install` enables automatic local linting on commit.
- **CI simplicity**: A single `pre-commit run --all-files` replaces multi-step install+run.
- **Composability**: Each linter is an independent hook with its own configuration and version.
- **Progressive tightening**: New Ruff rules can be added incrementally; per-file ignores
  allow tests and examples to have relaxed rules.
- **Tool consolidation**: Ruff handles formatting (black), import sorting (isort), and
  linting (pylint, pyflakes, pydocstyle) in a single tool.

## Decision
1. **Pre-commit as the hook framework**: `.pre-commit-config.yaml` defines all hooks.
   CI uses the official `pre-commit/action@v3.0.1` GitHub Action.

2. **Ruff as the sole Python tool**: Replaces black, isort, pylint. Configured in
   `pyproject.toml` under `[tool.ruff]` with `line-length = 100`, `target-version = "py39"`.

3. **Three-phase rollout**:
   - Phase 1 (commit `64e4b7f0`): Hook framework, clang-format, cython-lint, shfmt,
     shellcheck, ASF header, filetype checks. Basic ruff-check + ruff-format.
   - Phase 2 (commit `0bc968d1`): Enable UP, PL, I, RUF, NPY, F, PTH, D rules.
     Remove black/isort configs. Fix all violations.
   - Phase 3 (commit `8f4e044a`): Enable ANN rules (type annotations on public APIs).
     Add annotations to all public functions/methods.

4. **Per-file ignores**: Test files (`tests/*`) ignore pydocstyle rules (D100, D101, D103,
   D107, D205). `__init__.py` ignores unused imports (F401).

5. **CI gate**: Test jobs depend on lint passing (`needs: [lint, prepare]`).

6. **clang-tidy remains separate**: Too expensive for pre-commit; stays in its own CI
   step with `clang_tidy_precommit.py`.

## Alternatives Considered
### Keep task_lint.sh and add ruff
- Pros: Minimal change, backward compatible.
- Cons: Still not runnable locally as pre-commit, still sequential, still requires
  manual tool installation, mixes concerns in one script.

### Use GitHub Super-Linter
- Pros: Zero config for many languages, maintained by GitHub.
- Cons: Opinionated defaults that may conflict, slower (runs all linters even unchanged
  files), not runnable locally with same behavior.

### Separate CI jobs per linter
- Pros: Parallel execution, clear failure attribution.
- Cons: More complex CI config, harder to keep in sync with local dev, no pre-commit
  hook benefit for developers.

## Why This Option Won
- Pre-commit is the de facto standard for polyglot lint orchestration.
- Ruff is 10-100x faster than the black+isort+pylint combination and provides a
  superset of their functionality.
- The three-phase rollout allowed progressive rule tightening without a single
  massive diff.

## Consequences
### Positive
- Developers get instant feedback via `pre-commit install` (runs on `git commit`).
- CI lint stage is a single action (faster, simpler, cacheable).
- All Python code has consistent formatting, import ordering, docstrings, and type
  annotations.
- Adding new linters (e.g., cmake-format, markdownlint) is a one-line config change.

### Negative
- Developers must install pre-commit (`pip install pre-commit && pre-commit install`).
- The initial migration touched 80+ files across three commits for formatting/lint fixes.
- Some Ruff rules may be overly strict for rapid prototyping (mitigated by per-file ignores).

### Risks
- Ruff version pinning (`rev: v0.12.3`) may need updates as Ruff evolves. Pre-commit
  `autoupdate` mitigates this.
- clang-format version (`v20.1.8`) must stay consistent with what CI uses to avoid
  formatting churn.

## Implementation Notes
- Pre-commit hooks are defined in `.pre-commit-config.yaml`.
- Ruff configuration is in `pyproject.toml` under `[tool.ruff]`.
- ASF header and filetype checks are local hooks calling `python tests/lint/check_asf_header.py`
  and `python tests/lint/check_file_type.py`.
- `default_install_hook_types: [pre-commit]` ensures only pre-commit hooks are installed
  (not commit-msg or pre-push).

## Validation
- `pre-commit run --all-files` passes on all files in the repository.
- CI lint stage passes with `pre-commit/action@v3.0.1`.
- `uv run pytest -vvs tests/python` passes after all formatting/annotation changes.

## Migration and Rollback
- Migration: One-time `pre-commit install` for each developer.
- Rollback: Revert the three commits and restore `task_lint.sh` + black/isort config.

## Related Design Docs
None (this is an infrastructure decision, not an API design).

## Related Diagrams
None

## Evidence Matrix
- Pre-commit config -> `.memory/commits/2025-09-17-64e4b7f01896e3b755a49f5f4f7c25329aacc0b7.md` + `64e4b7f0` + `.pre-commit-config.yaml`
- Ruff rule selection -> `.memory/commits/2025-09-17-0bc968d1c6c76db80e69d2e860eafc8e0a3e9a69.md` + `0bc968d1` + `pyproject.toml`
- ANN rule enforcement -> `.memory/commits/2025-09-17-8f4e044a90ff8a3db15742274f2c7df435142b04.md` + `8f4e044a` + `pyproject.toml`
- CI simplification -> `64e4b7f0` + `.github/workflows/ci_test.yml`

## Supersedes
None (replaces ad-hoc `task_lint.sh` which had no prior ADR)

## Superseded By
None

## Follow-up Actions
- ~~Add cmake-format and markdownlint-cli2 hooks (noted as TODO in `.pre-commit-config.yaml`).~~ cmake-format done in [ADR-0029](.memory/ADRs/0029-cmake-format-and-clang-tidy-toolchain.md) (commit `98b26edd`).
- Add mypy or ty for Python type checking.
- Add conventional commits hook for commit message validation.
