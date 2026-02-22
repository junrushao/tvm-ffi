---
sha: "5bf7e8ce20fae0df47dd0adf7b39919ac6fafa11"
date: "2026-01-06"
author: "Yaxing Cai"
subject: "[ADDONS] Add licence and notice for torch-c-dlpack-ext (#385)"
nature: ["chore"]
tags: []
scope: ["addons-torch-dlpack", "lint"]
risk: "low"
---

# 5bf7e8c -- [ADDONS] Add licence and notice for torch-c-dlpack-ext (#385)

## TL;DR
- Adds Apache 2.0 LICENSE and NOTICE files to the `addons/torch_c_dlpack_ext` directory.
- Updates `pyproject.toml` with proper authors, license, and classifiers metadata.
- Adds the addon LICENSE/NOTICE paths to the lint allowlist.

## Why (intent / motivation)
- The `torch_c_dlpack_ext` addon lacked its own LICENSE and NOTICE files, which are required for Apache 2.0 compliance and alignment with the main TVM-FFI project.

## What changed (facts from diff)
- New file `addons/torch_c_dlpack_ext/LICENSE`: full Apache 2.0 license text (201 lines).
- New file `addons/torch_c_dlpack_ext/NOTICE`: ASF attribution notice (5 lines).
- Updated `addons/torch_c_dlpack_ext/pyproject.toml` with `authors`, `readme`, `license`, and `classifiers` fields.
- Updated `tests/lint/check_file_type.py`: added `addons/torch_c_dlpack_ext/LICENSE` and `addons/torch_c_dlpack_ext/NOTICE` to `ALLOW_SPECIFIC_FILE` set.

## Public surface changes (if any)
- API: none
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none (lint allowlist update in `check_file_type.py`).
- How to verify manually: Run `python tests/lint/check_file_type.py` to verify the new files pass the file type check.
- CI impact: Lint job will now accept the new LICENSE/NOTICE files.

## Risk & rollout notes
- Risk level: low -- licensing/metadata files only, no code changes.
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `addons/torch_c_dlpack_ext/LICENSE` (+201/-0, new file)
- `addons/torch_c_dlpack_ext/NOTICE` (+5/-0, new file)
- `addons/torch_c_dlpack_ext/pyproject.toml` (+11/-0, modified)
- `tests/lint/check_file_type.py` (+8/-1, modified)

### Notable symbols / endpoints / configs touched
- `ALLOW_SPECIFIC_FILE` in `tests/lint/check_file_type.py`
- `pyproject.toml` metadata fields: `authors`, `readme`, `license`, `classifiers`

### Diff notes
- Diff truncated: no
