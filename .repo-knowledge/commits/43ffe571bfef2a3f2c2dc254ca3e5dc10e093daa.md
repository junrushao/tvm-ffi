---
sha: "43ffe571bfef2a3f2c2dc254ca3e5dc10e093daa"
date: "2025-09-26T12:03:39-07:00"
author: "Junru Shao"
subject: "fix: Only attach docstring when it's defined (#60)"
nature: ["fix"]
tags: ["test"]
scope: ["python", "src", "tests"]
risk: "low"
---

# 43ffe57 — fix: Only attach docstring when it's defined (#60)

## TL;DR
- `TypeField.as_property` and `TypeMethod.as_callable` no longer synthesise a default docstring when the C++ field/method has no doc comment; `__doc__` is only set if `self.doc` is non-empty
- Fixes a conflict with Sphinx autodoc that was triggered by the auto-generated docstrings from PR #49
- Adds `"Field \`a\`"` and `"Field \`b\`"` docstrings to `TestIntPairObj` C++ reflection to enable a positive docstring test

## Why (intent / motivation)
- Auto-generated fallback docstrings of the form `"Method X of class Y"` were being picked up by Sphinx and causing confusing documentation output
- When no doc is intentionally set, `__doc__` should remain `None` (Python's default)

## What changed (facts from diff)
- `python/tvm_ffi/cython/type_info.pxi`: `as_property` sets `__doc__` only when `self.doc` is truthy; `as_callable` similarly conditional
- `src/ffi/extra/testing.cc`: `def_ro("a", ..., "Field \`a\`")` and `def_ro("b", ..., "Field \`b\`")` doc strings added to `TestIntPairObj`
- `tests/python/test_object.py`: `test_attribute` added verifying `a.__doc__` and `b.__doc__`

## Public surface changes (if any)
- API: fields and methods without C++ doc comments now have `__doc__ = None` instead of a synthesised string
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: `tests/python/test_object.py::test_attribute`
- How to verify manually: `uv run pytest -vvs tests/python/test_object.py::test_attribute`
- CI impact: new test

## Risk & rollout notes
- Risk level: low — docstring change only; no functional behaviour affected
- Rollout/migration: Any code that relied on the synthesised fallback docstring will now see `None`
- Follow-ups: none

## Evidence
### Changed files
- `python/tvm_ffi/cython/type_info.pxi` +9/-6 (M)
- `src/ffi/extra/testing.cc` +2/-2 (M)
- `tests/python/test_object.py` +8/-0 (M)

### Notable symbols / endpoints / configs touched
- `TypeField.as_property`, `TypeMethod.as_callable` in `type_info.pxi`
- `TestIntPairObj` field doc strings in `testing.cc`

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/43ffe571bfef2a3f2c2dc254ca3e5dc10e093daa.md`
