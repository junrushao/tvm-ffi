---
sha: "19da7e8f07bd85245ceddb6084f2b44afbfeadc1"
date: "2025-12-21"
author: "Junru Shao"
subject: "doc: Revamp Python Packaging (#349)"
nature: ["docs"]
tags: ["cleanup"]
scope: ["docs", "c++-headers", "python-cython", "stubgen"]
risk: "low"
---

# 19da7e8 — doc: Revamp Python Packaging (#349)

## TL;DR
- Rewrites the Python packaging guide from Markdown to RST with new structure
- Reorganizes the doc tree: renames guides, moves files to `dev/` and `packaging/` directories
- Fixes Doxygen doc-comment formatting across all C++ headers (`\code` -> `\code{.cpp}`, indentation)
- Updates intersphinx links for data-api and scikit_build_core; uses shorter Sphinx cross-refs in Cython

## Why (intent / motivation)
- The existing Python packaging guide was outdated Markdown and needed a full rewrite as RST
- The doc site structure did not match the desired information architecture (Get Started / Guides / Concepts / Packaging / Reference / Developer Manual)
- C++ Doxygen code blocks lacked language annotations, causing rendering issues
- Sphinx intersphinx links to data-api and scikit_build_core were missing

## What changed (facts from diff)
- Deleted `docs/guides/python_packaging.md` (460 lines) and created `docs/packaging/python_packaging.rst` (506 lines)
- Renamed `docs/guides/build_from_source.md` -> `docs/dev/build_from_source.md`
- Renamed `docs/guides/cpp_guide.md` -> `docs/guides/cpp_lang_guide.md`, `python_guide.md` -> `python_lang_guide.md`, `rust_guide.md` -> `rust_lang_guide.md`
- Moved `docs/guides/cpp_packaging.md` -> `docs/packaging/cpp_packaging.md`
- Rewrote `docs/index.rst` toctree to reflect new structure
- Updated `docs/conf.py`: added `data-api` and `scikit_build_core` intersphinx mappings; fixed `torch-cpp` trailing slash
- Updated `docs/.rstcheck.cfg` to ignore new Sphinx roles
- Fixed `docs/get_started/quickstart.rst` and `stable_c_abi.rst` for new structure references
- Across 9 C++ headers: changed `\code` -> `\code{.cpp}`, fixed comment indentation, removed stray blank lines, removed unused `#include` (`<atomic>`, `<memory>`, `<sstream>`, `<string_view>`)
- In `python/tvm_ffi/cython/tensor.pxi`: replaced raw URL intersphinx links with Sphinx `:py:meth:` cross-references
- In `python/tvm_ffi/stub/cli.py`: fixed prefix filtering logic to use `prefix_filter` and `root_prefix` instead of hardcoded `testing`/`ffi` checks; fixed help text
- Updated `tests/python/test_stubgen.py`: added `test_stage_2_filters_prefix_and_marks_root` test

## Public surface changes (if any)
- API: none (documentation and comment-only changes)
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/python/test_stubgen.py` (new test `test_stage_2_filters_prefix_and_marks_root`)
- How to verify manually: `uv run pytest -vvs tests/python/test_stubgen.py`; build docs with `cd docs && make html`
- CI impact: none

## Risk & rollout notes
- Risk level: low — documentation and formatting changes; the stubgen prefix filter fix is tested
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `docs/.rstcheck.cfg` (+1/-1, modified)
- `docs/concepts/abi_overview.md` (+1/-1, modified)
- `docs/conf.py` (+3/-1, modified)
- `docs/dev/build_from_source.md` (renamed from `docs/guides/build_from_source.md`)
- `docs/get_started/quickstart.rst` (+~60/-~57, modified)
- `docs/get_started/stable_c_abi.rst` (+6/-6, modified)
- `docs/guides/cpp_lang_guide.md` (renamed from `docs/guides/cpp_guide.md`)
- `docs/guides/python_lang_guide.md` (renamed from `docs/guides/python_guide.md`)
- `docs/guides/python_packaging.md` (-460, deleted)
- `docs/guides/rust_lang_guide.md` (+2/-2, renamed from `docs/guides/rust_guide.md`)
- `docs/index.rst` (+20/-16, modified)
- `docs/packaging/cpp_packaging.md` (renamed from `docs/guides/cpp_packaging.md`)
- `docs/packaging/python_packaging.rst` (+506, added)
- `docs/reference/python/index.rst` (+2/-1, modified)
- `include/tvm/ffi/base_details.h` (+2/-2, modified)
- `include/tvm/ffi/c_api.h` (+1/-1, modified)
- `include/tvm/ffi/container/container_details.h` (+1/-2, modified)
- `include/tvm/ffi/container/tensor.h` (+14/-24, modified)
- `include/tvm/ffi/error.h` (+5/-10, modified)
- `include/tvm/ffi/extra/cuda/device_guard.h` (+1/-1, modified)
- `include/tvm/ffi/extra/module.h` (+2/-2, modified)
- `include/tvm/ffi/function.h` (+18/-27, modified)
- `include/tvm/ffi/reflection/registry.h` (+25/-24, modified)
- `include/tvm/ffi/rvalue_ref.h` (+1/-3, modified)
- `python/tvm_ffi/cython/tensor.pxi` (+6/-6, modified)
- `python/tvm_ffi/stub/cli.py` (+8/-5, modified)
- `tests/python/test_stubgen.py` (+49/-1, modified)

### Notable symbols / endpoints / configs touched
- Sphinx `intersphinx_mapping` in `docs/conf.py`
- `_stage_2()` prefix filtering logic in `python/tvm_ffi/stub/cli.py`
- Doxygen `\code{.cpp}` annotations across all public C++ headers

### Diff notes
- Diff truncated: yes (full diff ~72KB; docs RST content is the bulk)
