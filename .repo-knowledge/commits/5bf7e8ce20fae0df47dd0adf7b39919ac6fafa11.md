---
sha: "5bf7e8ce20fae0df47dd0adf7b39919ac6fafa11"
date: "2026-01-06T20:38:14+08:00"
author: "Yaxing Cai"
subject: "[ADDONS] Add licence and notice for torch-c-dlpack-ext (#385)"
nature: ["chore"]
tags: ["build"]
scope: ["addons", "tests"]
risk: "low"
---

# 5bf7e8c — [ADDONS] Add licence and notice for torch-c-dlpack-ext (#385)

## TL;DR
- Added Apache License 2.0 (`LICENSE`) and `NOTICE` file to `addons/torch_c_dlpack_ext/`
- Updated `addons/torch_c_dlpack_ext/pyproject.toml` to reference the license and include `NOTICE` in wheel metadata
- Updated `tests/lint/check_file_type.py` to recognize the new `NOTICE` and `LICENSE` files

## Why (intent / motivation)
- The `torch-c-dlpack-ext` addon package was missing proper Apache Software Foundation licensing files, which is required for ASF compliance and proper PyPI package metadata

## What changed (facts from diff)
- `addons/torch_c_dlpack_ext/LICENSE`: Apache 2.0 license text added (201 lines)
- `addons/torch_c_dlpack_ext/NOTICE`: 5-line notice file added
- `addons/torch_c_dlpack_ext/pyproject.toml`: `license` and `license-files` fields added; `NOTICE` included in wheel (+11/-0)
- `tests/lint/check_file_type.py`: file type checker updated to allow `LICENSE` and `NOTICE` files (+8/-1)

## Public surface changes (if any)
- API: none
- Flags/config: `pyproject.toml` for `torch-c-dlpack-ext` now declares license metadata
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/lint/check_file_type.py` updated to not flag `LICENSE`/`NOTICE` as unknown file types
- How to verify manually: `pre-commit run check-file-type --all-files` — should pass without errors
- CI impact: lint job now handles `LICENSE`/`NOTICE` files in addons correctly

## Risk & rollout notes
- Risk level: low — license metadata addition; no code changes
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- A `addons/torch_c_dlpack_ext/LICENSE` +201/-0
- A `addons/torch_c_dlpack_ext/NOTICE` +5/-0
- M `addons/torch_c_dlpack_ext/pyproject.toml` +11/-0
- M `tests/lint/check_file_type.py` +8/-1

### Notable symbols / endpoints / configs touched
- `addons/torch_c_dlpack_ext/LICENSE` — new Apache 2.0 license
- `addons/torch_c_dlpack_ext/NOTICE` — new notice file
- `tests/lint/check_file_type.py` — updated file type allowlist

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/5bf7e8ce20fae0df47dd0adf7b39919ac6fafa11.md`
