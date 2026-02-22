---
sha: "6bc1a8ebb228bd0a6357e1e1da86a8febebf07ba"
date: "2025-12-04T14:07:50-05:00"
author: "Tianqi Chen"
subject: "[FEAT] Further robustify kwargs wrapper (#311)"
nature: ["feat"]
tags: ["refactor", "test"]
scope: ["python", "tests"]
risk: "low"
---

# 6bc1a8e — [FEAT] Further robustify kwargs wrapper (#311)

## TL;DR
- Adds Python keyword validation (rejects names like `if`, `for`) to `make_kwargs_wrapper`
- Renames `args_names`/`args_defaults`/`kwargsonly_names`/`kwargsonly_defaults`/`prototype_func` parameters to shorter `arg_names`/`arg_defaults`/`kwonly_names`/`kwonly_defaults`/`prototype`
- Adds `exclude_arg_names` parameter to `make_kwargs_wrapper_from_signature` to skip certain parameters
- Updates all tests and benchmarks to use new parameter names

## Why (intent / motivation)
- Python keywords cannot be used as function parameter names and the original code did not validate this; also the long parameter names were verbose; the `exclude_arg_names` feature enables selective parameter skipping when wrapping complex signatures

## What changed (facts from diff)
- `python/tvm_ffi/utils/kwargs_wrapper.py`: Added `import keyword`; added `keyword.iskeyword` check in `_validate_argument_names`; renamed all parameters; added `exclude_arg_names` to `make_kwargs_wrapper_from_signature` with a `skip_set`
- `tests/python/utils/test_kwargs_wrapper.py`: Updated all calls to use new parameter names; added `test_validation_errors` case for Python keyword rejection; added extensive `exclude_arg_names` tests
- `tests/scripts/benchmark_kwargs_wrapper.py`: Updated parameter name

## Public surface changes (if any)
- API: `make_kwargs_wrapper` parameter renames (breaking: old `args_names`, `kwargsonly_names`, etc. no longer work); new `exclude_arg_names` on `make_kwargs_wrapper_from_signature`
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/python/utils/test_kwargs_wrapper.py` — keyword validation test, exclude_arg_names tests
- How to verify manually: `uv run pytest -vvs tests/python/utils/test_kwargs_wrapper.py`
- CI impact: none

## Risk & rollout notes
- Risk level: low — parameter renames are a breaking API change but this utility was just added in #309; no external users yet
- Rollout/migration: Update calls from `args_names=` to `arg_names=`, `kwargsonly_names=` to `kwonly_names=`, etc.
- Follow-ups: none

## Evidence
### Changed files
- `python/tvm_ffi/utils/kwargs_wrapper.py` +97/-82 (modified)
- `tests/python/utils/test_kwargs_wrapper.py` +92/-42 (modified)
- `tests/scripts/benchmark_kwargs_wrapper.py` +1/-1 (modified)

### Notable symbols / endpoints / configs touched
- `make_kwargs_wrapper` — parameter renames, keyword validation added
- `make_kwargs_wrapper_from_signature` — added `exclude_arg_names` parameter
- `_validate_argument_names` — added `keyword.iskeyword` check

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/6bc1a8ebb228bd0a6357e1e1da86a8febebf07ba.md`
