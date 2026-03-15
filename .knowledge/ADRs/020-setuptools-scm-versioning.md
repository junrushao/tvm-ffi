---
scope:
  - ".knowledge/designs/0015-python-packaging.md"
  - ".knowledge/designs/c-abi.md"
---
# ADR-020: Git-Based Versioning via setuptools_scm

**TL;DR**: The project adopts `setuptools_scm` to derive the canonical version from git tags, replacing manually maintained version strings in `pyproject.toml` and `__init__.py`. All other version locations (C++ macros, Rust Cargo.toml) are validated against this single source of truth.

## Context
Before this decision, the version was manually maintained in three places: `pyproject.toml` (`version = "0.1.0"`), `python/tvm_ffi/__init__.py` (`__version__ = "0.1.0"`), and a lint script checked they matched. C++ macros (`TVM_FFI_VERSION_MAJOR/MINOR/PATCH`) and Rust crate versions were managed independently. This led to:
- Version update commits being pure ceremony (touching 2+ files per bump)
- Risk of inconsistency between Python, C++, and Rust version numbers
- No automatic dev/pre-release versioning for non-tagged commits

Usecases:
- Developers working on unreleased code see accurate dev versions (e.g., `0.1.1.dev9+g43f0820f6`)
- CI can validate that C++ and Rust versions match the canonical git-derived version
- Release managers tag a commit and all version locations align automatically

Design Decisions:
- The canonical version source is git tags, accessed via `setuptools_scm.get_version()`
- `python/tvm_ffi/_version.py` is auto-generated at build time (gitignored)
- `pyproject.toml` uses `dynamic = ["version"]` with `scikit_build_core.metadata.setuptools_scm` provider
- A multi-language version linter (`tests/lint/check_version.py`) validates C++ macros (`--cpp`) and Rust Cargo.toml (`--rust`) against the canonical version
- CI workflows require `fetch-depth: 0` + `fetch-tags: true` for correct version computation

## Alternatives
### Keep manual version strings
- Description: Continue maintaining `version = "X.Y.Z"` in pyproject.toml and syncing to `__init__.py`
- Pros: Simple, no build-time dependency, works without git history
- Cons: Error-prone manual sync; no automatic dev versioning; ceremony commits for every bump; C++/Rust versions still checked separately
- Why rejected: The project already has three language targets to keep in sync, and the lint script was already automating the check; making the source of truth git tags eliminates the manual step entirely

### Use versioneer or hatch-vcs
- Description: Alternative SCM-based version tools
- Pros: Similar functionality to setuptools_scm
- Cons: `versioneer` is deprecated in favor of setuptools_scm; `hatch-vcs` requires switching to hatch build backend which conflicts with the existing scikit-build-core backend
- Why rejected: setuptools_scm has first-class integration with scikit-build-core via `scikit_build_core.metadata.setuptools_scm` provider, making it the natural choice

## Implementation Notes
- `[tool.setuptools_scm]` in pyproject.toml: `version_file = "python/tvm_ffi/_version.py"`, `write_to = "python/tvm_ffi/_version.py"`
- `[tool.scikit-build] metadata.version.provider = "scikit_build_core.metadata.setuptools_scm"`
- `tvm_ffi.__init__.py` imports `__version__` and `__version_tuple__` from `_version.py` with fallback to `"0.0.0.dev0"`
- `tests/lint/check_version.py` functions: `_version_info()`, `_check_cpp(info)`, `_check_rust(info)`, `_map_pep440_pre_to_semver(pre)`
- C++ `TVM_FFI_VERSION_PATCH` bumped from 0 to 1 in this commit
- Pre-commit hook renamed from `check-version` to `check-version-consistency`

## Related Design Docs
- `.knowledge/designs/0015-python-packaging.md`
- `.knowledge/designs/c-abi.md` (Version API section)
