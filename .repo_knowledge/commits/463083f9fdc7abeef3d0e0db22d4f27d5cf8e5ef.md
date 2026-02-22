---
sha: "463083f9fdc7abeef3d0e0db22d4f27d5cf8e5ef"
date: "2026-02-05"
author: "Junru Shao"
subject: "doc: Standalone Stub Generation Doc (#427)"
nature: ["docs"]
tags: ["cleanup"]
scope: ["docs", "stubgen"]
risk: "low"
---

# 463083f — doc: Standalone Stub Generation Doc (#427)

## TL;DR
- Extracts stub generation documentation from `python_packaging.rst` into a standalone `stubgen.rst` (400 lines)
- Provides comprehensive CLI and CMake reference for `tvm-ffi-stubgen`
- Documents all 8 inline directive types with examples
- Updates the DOC_URL constant in Python stubgen code to point to the new page

## Why (intent / motivation)
- Stub generation is a complex, standalone tool that deserves its own documentation page
- The previous inline treatment in `python_packaging.rst` made the packaging doc too long and harder to navigate
- Provides a single authoritative reference for all stubgen directives and CLI options

## What changed (facts from diff)
- New file `docs/packaging/stubgen.rst` (400 lines) covering:
  - CMake-based generation (`STUB_INIT ON` vs `OFF`, `STUB_PKG`, `STUB_PREFIX`)
  - CLI-based generation with option-to-CMake mapping table
  - Complete inline directive reference (8 directives: `global/`, `object/`, `import-section`, `export/`, `__all__`, `ty-map`, `import-object`, `skip-file`)
- `docs/packaging/python_packaging.rst`: Stub generation section reduced to a 4-line summary with cross-reference (-176 lines)
- `docs/index.rst`: Added `packaging/stubgen.rst` to toctree
- `docs/conf.py`: Added additional Doxygen EXCLUDE_SYMBOLS and EXCLUDE_PATTERNS for internal macros
- `python/tvm_ffi/stub/consts.py`: DOC_URL updated from `python_packaging.html#stub-generation-tool` to `stubgen.html`

## Public surface changes (if any)
- API: none
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none
- How to verify manually: Build docs and verify `stubgen.rst` page renders; verify `tvm-ffi-stubgen --help` link in error messages
- CI impact: none

## Risk & rollout notes
- Risk level: low — Documentation restructuring plus one URL constant change
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `docs/conf.py` (+4/-1, modified)
- `docs/index.rst` (+1)
- `docs/packaging/python_packaging.rst` (+9/-176, modified)
- `docs/packaging/stubgen.rst` (+400, new file)
- `python/tvm_ffi/stub/consts.py` (+1/-1, modified)

### Notable symbols / endpoints / configs touched
- `DOC_URL` constant in `python/tvm_ffi/stub/consts.py`
- docs toctree entry `packaging/stubgen.rst`
- Doxygen `EXCLUDE_SYMBOLS` and `EXCLUDE_PATTERNS` in `docs/conf.py`

### Diff notes
- Diff truncated: no
