---
sha: "82efbbb7cf617e2deb83a7fa0d16e3bbf02d511d"
date: "2025-12-07T11:29:26-08:00"
author: "Junru Shao"
subject: "chore(release): Version bump after v0.1.5 release (#321)"
nature: ["chore"]
tags: ["release", "version"]
scope: ["include"]
risk: "low"
---

# 82efbbb — chore(release): Version bump after v0.1.5 release (#321)

## TL;DR
- Bumps `TVM_FFI_VERSION_PATCH` from 5 to 6 in `include/tvm/ffi/c_api.h` after the v0.1.5 release.

## Why (intent / motivation)
- Standard post-release version bump to mark the start of the next development cycle (v0.1.6-dev).

## What changed (facts from diff)
- `include/tvm/ffi/c_api.h`: `#define TVM_FFI_VERSION_PATCH 5` -> `6`.

## Public surface changes (if any)
- API: Version macro `TVM_FFI_VERSION_PATCH` changes from 5 to 6
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none
- How to verify manually: check `tvm_ffi.__version__`
- CI impact: none

## Risk & rollout notes
- Risk level: low — version number only
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `include/tvm/ffi/c_api.h` +1/-1 (M)

### Notable symbols / endpoints / configs touched
- `TVM_FFI_VERSION_PATCH`

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/82efbbb7cf617e2deb83a7fa0d16e3bbf02d511d.md`
