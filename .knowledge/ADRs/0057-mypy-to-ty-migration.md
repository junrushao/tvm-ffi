---
scope:
  - "0021-ci-cd-pipeline"
  - "0016-packaging-and-build"
---
# Migrate from mypy to ty for Python Type Checking

**TL;DR**: The Python type checker was switched from mypy to Astral's `ty` (run via `uvx ty check`), providing significantly faster checking, tighter integration with the `uv`/`ruff` toolchain, and more accurate type inference.

## Context

The project used mypy as a pre-commit hook with several `additional_dependencies` (numpy, ml-dtypes, pytest, typing-extensions). mypy had several pain points:
1. **Slow**: mypy's incremental checking was still slow for the full codebase.
2. **Dependency overhead**: Required manually specifying additional dependencies for type stubs.
3. **False positives/negatives**: Some patterns required extensive `type: ignore[...]` annotations.
4. **Separate ecosystem**: mypy is not part of the Astral tooling ecosystem (uv, ruff) already used by the project.

## Decision

Replace mypy with `ty` (Astral's type checker):
- Run as a local pre-commit hook: `uvx ty@0.0.15 check --error-on-warning`.
- No `additional_dependencies` needed; `ty` resolves types from the project environment.
- CI lint job adds `uv sync --group dev --no-install-project` before pre-commit to ensure the dev environment is available.
- Simultaneously migrated `pyproject.toml` from optional-dependencies (`[test]`, `[torch]`) to dependency-groups (`[dependency-groups]`), which is the modern `uv` convention.

## Rationale

1. **Speed**: `ty` is written in Rust and is significantly faster than mypy.
2. **Accuracy**: `ty` has better inference for modern Python patterns.
3. **Unified toolchain**: With `uv` (package management), `ruff` (linting/formatting), and `ty` (type checking), all Python tooling comes from Astral, ensuring consistency.
4. **Simpler configuration**: No need for `mypy.ini` or `[tool.mypy]` sections; `ty` configuration lives in `pyproject.toml` under `[tool.ty]`.

## Migration Details

- `.pre-commit-config.yaml`: Removed `pre-commit/mirrors-mypy` repo; added local `ty` hook.
- `pyproject.toml`: Added `[tool.ty]` configuration; migrated from `[project.optional-dependencies]` to `[dependency-groups]` for `test`, `dev`, `torch` groups.
- ~38 Python files: Updated type annotations, replaced `type: ignore[mypy-code]` with `ty`-compatible patterns, fixed `Optional` vs `| None` patterns.
- CI: Added `uv sync` step before pre-commit in lint job; changed `pip install` commands from `-e ".[test]"` to `--group test -e .`.
- cibuildwheel: Changed `test-extras` to `test-groups` in `pyproject.toml`.
- The migration was done in two commits: `7619669` (initial switch) and `e08dd68` (pin version, fix CI).
- A follow-up fix `89cb606` corrected broken wheel testing caused by the dependency group migration.

## Related Design Docs

- [`.knowledge/designs/0021-ci-cd-pipeline.md`](../designs/0021-ci-cd-pipeline.md)
- [`.knowledge/designs/0016-packaging-and-build.md`](../designs/0016-packaging-and-build.md)
- Commits: `.knowledge/commits/2026-02-07-761966953fec7e8ceba0fcc20dc003e39cf2692d.md`, `.knowledge/commits/2026-02-11-e08dd6839a10d77d05ddef649840bcea99659d2f.md`, `.knowledge/commits/2026-02-11-89cb6066d1d8851e61e6201ca0782d78a4ed8160.md`
