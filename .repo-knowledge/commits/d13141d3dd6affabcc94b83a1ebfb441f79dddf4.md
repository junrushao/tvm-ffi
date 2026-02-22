---
sha: "d13141d3dd6affabcc94b83a1ebfb441f79dddf4"
date: "2025-10-26T17:22:00-07:00"
author: "Junru Shao"
subject: "fix(doc): SVG images not rendering (#193)"
nature: ["fix"]
tags: ["docs"]
scope: ["docs"]
risk: "low"
---

# d13141d — fix(doc): SVG images not rendering (#193)

## TL;DR
- Attempts to fix SVG diagram rendering in `docs/get_started/stable_c_abi.rst` by changing GitHub raw URL format to use `?sanitize=true` query parameter.

## Why (intent / motivation)
- SVG diagrams embedded from `https://raw.githubusercontent.com/tlc-pack/web-data/...` were not rendering on the published docs page.

## What changed (facts from diff)
- `docs/get_started/stable_c_abi.rst`: Changed two `.. figure::` URLs from `.../stable-c-abi-layout-any.svg` to `.../stable-c-abi-layout-any.svg?sanitize=true` (same for `layout-func.svg`).

## Public surface changes (if any)
- API: none
- Flags/config: none
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none
- How to verify manually: Check rendered docs for SVG figure visibility.
- CI impact: none

## Risk & rollout notes
- Risk level: low — documentation URL change only. (Note: this fix was subsequently reverted in the next commit #196.)
- Rollout/migration: none
- Follow-ups: Reverted in commit 789e9e5 (`fix(doc): Remove ?sanitize=true in SVG URL (#196)`).

## Evidence
### Changed files
- `docs/get_started/stable_c_abi.rst` +2/-2 (M)

### Notable symbols / endpoints / configs touched
- SVG image URLs in `docs/get_started/stable_c_abi.rst`

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/d13141d3dd6affabcc94b83a1ebfb441f79dddf4.md`
