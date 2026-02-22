---
sha: "19da7e8f07bd85245ceddb6084f2b44afbfeadc1"
date: "2025-12-21T19:12:40-08:00"
author: "Junru Shao"
subject: "doc: Revamp Python Packaging (#349)"
nature: ["docs"]
tags: ["refactor"]
scope: ["docs", "include", "python", "tests"]
risk: "low"
---

# 19da7e8 — doc: Revamp Python Packaging (#349)

## TL;DR
- Reorganized the documentation into a cleaner structure with dedicated sections (Get Started, Guides, Concepts, Packaging, Reference, Developer Manual)
- Replaced the old `docs/guides/python_packaging.md` with a new `docs/packaging/python_packaging.rst` (506 additions, 460 deletions)
- Fixed C++/Doxygen comment formatting across multiple headers
- Added intersphinx cross-reference targets for `data-api` and `scikit_build_core`

## Why (intent / motivation)
- The previous packaging guide was a flat markdown file lacking proper Sphinx integration and structured navigation
- Documentation cross-references used hardcoded URLs instead of intersphinx roles
- Guide filenames did not follow a consistent naming convention (`_lang_guide` suffix)

## What changed (facts from diff)
- `docs/guides/python_packaging.md` deleted (460 lines); new `docs/packaging/python_packaging.rst` created (506 lines) with proper RST directives
- `docs/guides/build_from_source.md` moved to `docs/dev/build_from_source.md`
- `docs/guides/{cpp,python,rust}_guide.md` renamed to `*_lang_guide.md`; `docs/guides/cpp_packaging.md` moved to `docs/packaging/`
- `docs/conf.py` adds `data-api` and `scikit_build_core` intersphinx mappings
- `docs/index.rst` updated with 19+/17- to reflect new toctree layout
- C++ headers (`function.h`, `error.h`, `tensor.h`, `registry.h`, `rvalue_ref.h`) had Doxygen comment fixes (no behavioral change)
- `python/tvm_ffi/stub/cli.py` updated stub generation helper messages
- `tests/python/test_stubgen.py` expanded significantly (+49)

## Public surface changes (if any)
- API: none (header fixes are doc-only)
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/python/test_stubgen.py` (+49 lines, stub generation tests)
- How to verify manually: `uv run sphinx-build docs _docs` — check new packaging section renders correctly
- CI impact: documentation build job affected; intersphinx now fetches data-api and scikit_build_core inventories

## Risk & rollout notes
- Risk level: low — documentation-only; header changes are comment reformatting only
- Rollout/migration: users linking to old URL `docs/guides/python_packaging.md` will need to update to `docs/packaging/python_packaging.rst`
- Follow-ups: ABI overview, tensors, cmake_integration, configure_linters, release_process noted as TODOs

## Evidence
### Changed files
- M `docs/.rstcheck.cfg` +1/-1
- M `docs/concepts/abi_overview.md` +1/-1
- M `docs/conf.py` +3/-1
- R100 `docs/dev/build_from_source.md` (from `docs/guides/`)
- M `docs/get_started/quickstart.rst` +67/-50
- M `docs/get_started/stable_c_abi.rst` +6/-6
- R100 `docs/guides/cpp_lang_guide.md` (renamed)
- R100 `docs/guides/python_lang_guide.md` (renamed)
- D `docs/guides/python_packaging.md` -460
- R097 `docs/guides/rust_lang_guide.md` (renamed)
- M `docs/index.rst` +19/-17
- R100 `docs/packaging/cpp_packaging.md` (moved)
- A `docs/packaging/python_packaging.rst` +506
- M `docs/reference/python/index.rst` +2/-1
- M `include/tvm/ffi/base_details.h` +2/-2
- M `include/tvm/ffi/c_api.h` +1/-1
- M `include/tvm/ffi/container/container_details.h` +1/-2
- M `include/tvm/ffi/container/tensor.h` +16/-22
- M `include/tvm/ffi/error.h` +5/-10
- M `include/tvm/ffi/extra/cuda/device_guard.h` +1/-1
- M `include/tvm/ffi/extra/module.h` +2/-2
- M `include/tvm/ffi/function.h` +17/-28
- M `include/tvm/ffi/reflection/registry.h` +25/-24
- M `include/tvm/ffi/rvalue_ref.h` +1/-3
- M `python/tvm_ffi/cython/tensor.pxi` +6/-6
- M `python/tvm_ffi/stub/cli.py` +7/-6
- M `tests/python/test_stubgen.py` +49/-1

### Notable symbols / endpoints / configs touched
- `intersphinx_mapping` in `docs/conf.py` — added `data-api`, `scikit_build_core`
- `docs/packaging/python_packaging.rst` — new RST packaging guide
- Doxygen comments in `function.h`, `error.h`, `tensor.h`, `registry.h`

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/19da7e8f07bd85245ceddb6084f2b44afbfeadc1.md`
