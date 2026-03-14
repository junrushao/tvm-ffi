---
scope:
  - "0016-packaging-and-build"
  - "0015-traceback-system"
---
# Libbacktrace Vendoring Strategy: Git Submodule over CMake Fetch

**TL;DR**: The decision to use a git submodule pointing to upstream `ianlancetaylor/libbacktrace` (at `3rdparty/libbacktrace`) rather than CMake `ExternalProject_Add` with `GIT_REPOSITORY`/`GIT_TAG` for downloading libbacktrace source.

## Context

Libbacktrace is a required dependency for native stack-frame collection (`TVMFFITraceback`) on non-Windows platforms. It was previously vendored as a git submodule pointing to a fork (`tlc-pack/libbacktrace`) that carried a single macOS Mach-O patch.

Commit `b245f1f` (#18246) briefly added `GIT_REPOSITORY` and `GIT_TAG` parameters to the `ExternalProject_Add` call in `AddLibbacktrace.cmake`, providing a direct download fallback from the upstream repository. This was immediately reverted in `7d09d6a` (#18249) after discussion concluded that the submodule approach was preferred, and the upstream repository had already incorporated the macOS patch from the fork.

## Alternatives

### 1. Git submodule pointing to upstream (chosen)

Keep `3rdparty/libbacktrace` as a git submodule, updated from the fork to upstream HEAD (`793921876c981ce49759114d7bb89bb89b2d3a2d`).

- Pros: No network dependency during build. Version pinned by submodule SHA. Consistent with the repo's established `3rdparty/` pattern for all vendored dependencies. Offline/air-gapped builds work.
- Cons: Requires `git submodule update --init --recursive` before building.

### 2. CMake `ExternalProject_Add` with `GIT_REPOSITORY` / `GIT_TAG`

Download source from GitHub at build time.

- Pros: Builds work without submodule initialization.
- Cons: Network dependency during build. Breaks offline/air-gapped builds. Inconsistent with how other `3rdparty/` dependencies are managed.

## Decision

Alternative 1. The submodule was updated from the `tlc-pack` fork to upstream `ianlancetaylor/libbacktrace` since the fork's macOS patch is now merged upstream. The `GIT_REPOSITORY`/`GIT_TAG` lines were removed.

## Consequences

- Builds require `git submodule update --init --recursive` (already a documented prerequisite in `CLAUDE.md`).
- The `tlc-pack/libbacktrace` fork is no longer referenced. All future updates should track upstream.
- No behavioral change to the compiled library.

## Related Design Docs

- [`.knowledge/designs/0016-packaging-and-build.md`](../designs/0016-packaging-and-build.md) -- Build system
- [`.knowledge/designs/0015-traceback-system.md`](../designs/0015-traceback-system.md) -- Traceback system using libbacktrace
- Commits: `.knowledge/commits/2025-08-28-b245f1f9f96bf21a36dfb5b6db29de8e47c92103.md` (add), `.knowledge/commits/2025-08-29-7d09d6ae1670edeb2c3e2076ec3cbce3f1a3266d.md` (revert)
