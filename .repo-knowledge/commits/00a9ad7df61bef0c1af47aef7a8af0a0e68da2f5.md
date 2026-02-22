---
sha: "00a9ad7df61bef0c1af47aef7a8af0a0e68da2f5"
date: "2025-11-04T12:07:09-05:00"
author: "Tianqi Chen"
subject: "[LINT] Bump macro version after release (#223)"
nature: ["chore"]
tags: []
scope: ["include"]
risk: "low"
---

# 00a9ad7 — [LINT] Bump macro version after release (#223)

## TL;DR
- Bumps `TVM_FFI_VERSION_PATCH` from `1` to `2` in `include/tvm/ffi/c_api.h`
- Post-release version maintenance to mark the start of the next patch cycle

## Why (intent / motivation)
- Standard post-release version bump to prevent future changes from appearing as belonging to the already-released version

## What changed (facts from diff)
- `#define TVM_FFI_VERSION_PATCH 1` changed to `#define TVM_FFI_VERSION_PATCH 2`

## Public surface changes (if any)
- API: `TVM_FFI_VERSION_PATCH` macro value changed from 1 to 2; affects `TVMFFIVersionMinor()` and compile-time version checks
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none
- How to verify manually: `grep TVM_FFI_VERSION_PATCH include/tvm/ffi/c_api.h`
- CI impact: none

## Risk & rollout notes
- Risk level: low — version bump only
- Rollout/migration: none
- Follow-ups: none

## Evidence
### Changed files
- `include/tvm/ffi/c_api.h` +1/-1 (M)

### Notable symbols / endpoints / configs touched
- `TVM_FFI_VERSION_PATCH` macro

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/00a9ad7df61bef0c1af47aef7a8af0a0e68da2f5.md`
