---
sha: "af82dbb9a4cbb31f1ac9dc38195eaae747c31bcb"
date: "2025-09-14T03:59:24-07:00"
author: "Junru Shao"
subject: "fix: Always specify `method_pyfunc.__name__` (#7)"
nature: ["fix"]
tags: ["reflection", "python", "cython", "method"]
scope: ["python"]
risk: "low"
---

# af82dbb — fix: Always specify `method_pyfunc.__name__` (#7)

## TL;DR
- Fixes a bug where `method_pyfunc.__name__` was only set when `doc` was not None, meaning methods without documentation strings got no `__name__` attribute set.

## Why (intent / motivation)
- A method's `__name__` should always be set to its registered name for correct introspection, regardless of whether it has a docstring.

## What changed (facts from diff)
- `python/tvm_ffi/cython/function.pxi`: Moved `method_pyfunc.__name__ = name` outside the `if doc is not None:` block so it is always executed.

## Public surface changes (if any)
- API: none (behavioral fix, no API change)
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none
- How to verify manually: Inspect `.__name__` on methods of FFI-reflected objects that have no docstring.
- CI impact: none

## Risk & rollout notes
- Risk level: low — one-line fix, no performance impact.
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `python/tvm_ffi/cython/function.pxi` +1/-1 (M)

### Notable symbols / endpoints / configs touched
- `_add_class_attrs_by_reflection`: `method_pyfunc.__name__` assignment

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/af82dbb9a4cbb31f1ac9dc38195eaae747c31bcb.md`
