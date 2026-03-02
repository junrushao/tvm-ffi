---
design: "0021"
title: "Stubgen: Inline Type Stub Generation from FFI Reflection"
status: "active"
owners:
  - "Junru Shao"
created: "2025-10-12"
last_updated: "2025-10-12"
scope:
  - "python/tvm_ffi/stub"
  - "python/tvm_ffi/_ffi_api.py"
  - "python/tvm_ffi/testing"
source_commits:
  - "ea02e646"
source_ledgers:
  - ".memory/commits/2025-10-12-ea02e646.md"
---

# Stubgen: Inline Type Stub Generation from FFI Reflection

## TL;DR
- `tvm-ffi-stubgen` is a CLI tool that scans `.py`/`.pyi` files for marker comments and fills delimited blocks with generated type stubs (global functions, object fields, methods) derived from the TVM FFI reflection registry at runtime.
- Stubs are guarded by `TYPE_CHECKING` imports, providing IDE autocompletion and static type checking without runtime overhead. This replaces manually maintained `.pyi` files with inline blocks that stay synchronized with C++ reflection metadata.
- The tool is the consumer-side counterpart of the TypeSchema metadata system (Design 0019): TypeSchema generates JSON descriptors at registration time, and stubgen consumes them at stub-generation time.

## Problem Statement
TVM FFI exposes hundreds of global functions and dozens of object types with fields and methods, all registered via C++ reflection. Without corresponding Python type annotations, IDE autocompletion, static analysis (mypy/pyright), and documentation generation are blind to these APIs. Maintaining separate `.pyi` stub files manually is error-prone and drifts from the C++ source. The TypeSchema system (Design 0019) already generates structured type metadata at registration time; what is needed is a tool to consume that metadata and emit Python-native type stubs.

## Context and Constraints
- The FFI reflection registry is populated at runtime (during shared library load). Stub generation must import the library and query the registry.
- Stubs must be deterministic: re-running on unchanged metadata must produce identical output (no diff noise).
- The tool must support per-block `ty_map` directives for customizing type name rendering (e.g., mapping `ffi.Array` to `Sequence` for specific modules).
- Stubs must be compatible with Python 3.8+ (using `from __future__ import annotations`).
- Some files should be skippable via a `tvm-ffi-stubgen(skip-file)` directive.

## Goals
- Provide a single CLI entry point (`tvm-ffi-stubgen python`) that regenerates all inline stubs in the source tree.
- Support three categories of generated stubs: global function signatures, object field properties, and object method signatures.
- Use TypeSchema JSON metadata to produce accurate type annotations without manual annotation.
- Make the marker protocol extensible so downstream packages can adopt the same convention.

## Non-Goals
- Generating standalone `.pyi` files (the tool generates inline blocks within `.py` files).
- Runtime type checking or enforcement based on generated stubs.
- Generating stubs for C++ APIs (only Python-side stubs from the reflection registry).

## Design
### Components and Responsibilities

- **`python/tvm_ffi/stub/cli.py`**: CLI entry point registered as `tvm-ffi-stubgen` in `pyproject.toml`'s `[project.scripts]`. Parses command-line arguments (subcommand `python`, file paths or glob patterns).

- **`python/tvm_ffi/stub/codegen.py`** (~528 lines): Core stub generation engine. Scans files for `tvm-ffi-stubgen(begin)` / `tvm-ffi-stubgen(end)` marker comments. For each block, queries the FFI registry (via `list_global_func_names`, `get_global_func_metadata`, `_lookup_or_register_type_info_from_type_key`) and generates `if TYPE_CHECKING:` guarded stub code.

- **`python/tvm_ffi/stub/consts.py`**: Marker comment constants and block type identifiers.

- **`python/tvm_ffi/stub/utils.py`**: Utility functions for type name rendering, import resolution, and indentation management.

- **`python/tvm_ffi/stub/file_utils.py`**: File I/O helpers for reading, writing, and comparing stub blocks.

- **Marker protocol**: Files contain `# tvm-ffi-stubgen(begin)` and `# tvm-ffi-stubgen(end)` delimiters. Between them, the tool replaces content with generated stubs. A `# tvm-ffi-stubgen(ty_map ...)` directive within a block specifies a custom type name mapping. A `# tvm-ffi-stubgen(skip-file)` at the module level skips the entire file.

- **TypeSchema consumption**: The engine calls `TypeSchema.from_json_str()` on the `type_schema` field from method/field metadata, then renders Python type annotations using `TypeSchema.repr(ty_map=...)`.

### Data Contracts and Invariants
- **Deterministic output**: Given identical registry state, the tool produces byte-identical output. This is achieved by sorting function names and field names alphabetically within each block.
- **Marker integrity**: The tool never modifies content outside `begin`/`end` markers. If markers are malformed (e.g., `begin` without matching `end`), the tool raises an error.
- **TYPE_CHECKING guard**: All generated stubs are wrapped in `if TYPE_CHECKING:` blocks, meaning they have zero runtime cost. Imports used only in stubs are also guarded.
- **`__ffi_init__` -> `__c_ffi_init__` renaming**: Constructor methods registered as `__ffi_init__` in C++ are rendered as `__c_ffi_init__` in stubs to avoid collision with Python `__init__`.

### Control Flow
1. User runs `uv run tvm-ffi-stubgen python`.
2. CLI discovers all `.py` files in the configured source tree.
3. For each file, the engine scans for `skip-file` directive (skip if present) and `begin`/`end` marker pairs.
4. For each marker block, the engine reads the block type (global functions, object type key, etc.) and optional `ty_map` directives.
5. The engine queries the FFI registry for the relevant metadata.
6. TypeSchema JSON strings are parsed and rendered as Python type annotations.
7. Generated stub code replaces the content between markers.
8. The file is written back only if the content changed (no-op for unchanged files).

### Extension Points
- **New block types**: Add new marker block types for additional categories of generated stubs (e.g., enum types, container specializations).
- **Custom `ty_map` callbacks**: Downstream packages can define per-block type mappings for domain-specific rendering.
- **New source languages**: The marker protocol is language-agnostic; it could be adapted for Rust or other bindings.

## Alternatives Considered
### Standalone `.pyi` files generated from reflection
- Pros: Standard approach for Python type stubs. No source file modification.
- Cons: Separate files drift from source. IDEs may not always pick up `.pyi` files in editable installs. Two files to maintain per module.

### Manual type annotations in Python source
- Pros: Full control. No tooling dependency.
- Cons: Duplicates C++ type information. Drifts from C++ reflection. Maintenance burden scales with API surface.

### mypy plugin that queries FFI registry at analysis time
- Pros: No generated code. Always up-to-date.
- Cons: Requires running the shared library during static analysis (complex setup). mypy plugins are fragile and version-specific. Does not help non-mypy tools (pyright, IDE completion).

## Trade-offs
- **Optimized**: Automatic synchronization with C++ reflection (run once after build), zero runtime cost (TYPE_CHECKING guard), inline stubs are version-controlled alongside source code, deterministic output eliminates diff noise.
- **Sacrificed**: Requires a build step before stub generation (the shared library must be importable), marker comments add visual noise to source files, the tool is TVM-FFI-specific (not a general stub generator).

## Interfaces and Compatibility
- **CLI**: `tvm-ffi-stubgen python [--file FILE] [--dir DIR]`.
- **Marker protocol**: `# tvm-ffi-stubgen(begin)` / `# tvm-ffi-stubgen(end)` / `# tvm-ffi-stubgen(ty_map ...)` / `# tvm-ffi-stubgen(skip-file)`.
- **Python API consumed**: `tvm_ffi.registry.list_global_func_names`, `tvm_ffi.registry.get_global_func_metadata`, `tvm_ffi.core.TypeSchema`, `tvm_ffi.core._lookup_or_register_type_info_from_type_key`.
- **Dependency on Design 0019**: TypeSchema JSON format is the input data contract.

## Failure Modes and Mitigations
- **Registry not loaded**: If the shared library is not installed, the CLI fails with a clear import error. Mitigation: documentation specifies `uv pip install -e .` must precede `tvm-ffi-stubgen`.
- **Malformed markers**: Missing `end` marker raises a parse error with file path and line number.
- **Unknown type in TypeSchema**: If a C++ type lacks a Python equivalent in the `_TYPE_SCHEMA_ORIGIN_CONVERTER` mapping, the raw C++ type name is used as-is in the stub. This is a degraded but functional state.

## Observability and Validation
- The `_ffi_api.py` and `testing.py` files serve as reference examples of inline stubs.
- Running `tvm-ffi-stubgen python` twice produces no diff (idempotency check).
- mypy/pyright can validate the generated stubs against actual usage patterns.

## Migration and Rollout
- New tool: no migration from existing code needed.
- The previously maintained `python/tvm_ffi/_ffi_api.pyi` file was removed in favor of inline stubs in `_ffi_api.py`.
- Downstream packages can adopt the marker protocol incrementally.

## Diagrams
None

## Related ADRs
None

## Related Design Docs
- [.memory/designs/0019-typeschema-metadata-system.md](.memory/designs/0019-typeschema-metadata-system.md) (TypeSchema is the data source)
- [.memory/designs/0006-reflection-system.md](.memory/designs/0006-reflection-system.md) (reflection registry is the metadata provider)

## Evidence Matrix
- `tvm-ffi-stubgen` CLI entry point and core engine -> `.memory/commits/2025-10-12-ea02e646.md` + `ea02e646` + `python/tvm_ffi/stub/`
- Marker protocol (`tvm-ffi-stubgen(begin/end/ty_map/skip-file)`) -> `ea02e646` + `python/tvm_ffi/stub/consts.py`
- Inline stubs replacing `_ffi_api.pyi` -> `ea02e646` + `python/tvm_ffi/_ffi_api.py`
- `__ffi_init__` -> `__c_ffi_init__` renaming in stubs -> `ea02e646` + `python/tvm_ffi/stub/codegen.py`

## Open Questions
- Should stubgen support generating stubs for Rust bindings?
- Should there be a CI step that validates stubs are up-to-date (fail if `tvm-ffi-stubgen python` produces a diff)?
- Should the marker protocol support versioning to handle format changes?

## Confidence and Risk
- Confidence: high
- Residual risks: The tool depends on runtime reflection, meaning stubs can only be generated after a successful build. If the build is broken, stubs cannot be regenerated. The marker protocol is custom (not a community standard), which may surprise contributors unfamiliar with it.
