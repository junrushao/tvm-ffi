---
sha: "463083f9fdc7abeef3d0e0db22d4f27d5cf8e5ef"
date: "2026-02-05T09:36:04-08:00"
author: "Junru Shao"
subject: "doc: Standalone Stub Generation Doc (#427)"
nature: ["docs"]
tags: []
scope: ["docs", "python"]
risk: "low"
---

# 463083f — doc: Standalone Stub Generation Doc (#427)

## TL;DR
- Adds a dedicated 400-line RST doc for the stub generation system (`docs/packaging/stubgen.rst`)
- Extracts stub generation content from `python_packaging.rst` (removes 175 lines of duplication)
- Minor `docs/conf.py` exclusion list refinements for Doxygen
- Fixes a one-character version constant in `python/tvm_ffi/stub/consts.py`

## Why (intent / motivation)
- Stub generation is a significant enough feature to deserve its own doc page rather than being buried in the packaging guide
- Separating concerns makes both pages easier to navigate

## What changed (facts from diff)
- `docs/packaging/stubgen.rst` (new, 400 lines): Full standalone guide for tvm-ffi-stubgen including architecture, usage, and integration patterns
- `docs/packaging/python_packaging.rst`: Removed 175 lines of inline stub gen content; now cross-references `stubgen.rst` (+11/-175)
- `docs/index.rst`: Adds `stubgen.rst` entry to packaging toctree
- `docs/conf.py`: Extends `EXCLUDE_SYMBOLS` list for Doxygen (+4/-1)
- `python/tvm_ffi/stub/consts.py`: One-char fix (+1/-1)

## Public surface changes (if any)
- API: none
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none
- How to verify manually: `uv run sphinx-build docs docs/_build` and navigate to Packaging section
- CI impact: doc build CI step exercises this

## Risk & rollout notes
- Risk level: low — documentation reorganization only
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `docs/conf.py` +4/-1 (M)
- `docs/index.rst` +1 (M)
- `docs/packaging/python_packaging.rst` +11/-175 (M)
- `docs/packaging/stubgen.rst` +400 (A)
- `python/tvm_ffi/stub/consts.py` +1/-1 (M)

### Notable symbols / endpoints / configs touched
- `docs/packaging/stubgen.rst` (new doc page)

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/463083f9fdc7abeef3d0e0db22d4f27d5cf8e5ef.md`
