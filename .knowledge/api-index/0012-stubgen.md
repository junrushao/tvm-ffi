---
scope: "stubgen"
---
# API Index: Stub Generation System

**Scope**: The `tvm-ffi-stubgen` CLI tool and its internal modules for generating inline Python type stubs from the FFI reflection registry.
**Design docs**: [0020-stubgen.md](../designs/0020-stubgen.md)
**ADRs**: [0022-inline-stubs-over-pyi.md](../ADRs/0022-inline-stubs-over-pyi.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| (none) | | | Stubgen is pure Python; no C++ API |

## Python API
| Name | Signature | Description |
|------|-----------|-------------|
| `__main__` | `def __main__() -> int` | CLI entry point (in `tvm_ffi.stub.cli`) |
| `Options` | `Options(imports: list[str], dlls: list[str], init: InitConfig \| None, indent: int, files: list[str], verbose: bool, dry_run: bool)` | CLI option container (in `utils.py`; extended with `imports` and `init` in b58c2e3) |
| `InitConfig` | `InitConfig(pkg: str, shared_target: str, prefix: str)` | Configuration for `--init-*` mode (in `utils.py`; added b58c2e3) |
| `ImportItem` | `ImportItem(name: str, type_checking_only: bool = False, alias: str \| None = None)` | Frozen dataclass representing an import statement; auto-splits `name` on `.`; applies `MOD_MAP` substitutions (in `utils.py`; added b58c2e3) |
| `ImportItem.name_with_alias` | `@property -> str` | Returns `name as alias` or just `name` |
| `ImportItem.full_name` | `@property -> str` | Returns `mod.name` or just `name` |
| `NamedTypeSchema` | `NamedTypeSchema(name: str, schema: TypeSchema)` | Extends `TypeSchema` with an associated name (in `utils.py`; added b58c2e3) |
| `FileInfo` | `FileInfo(path: Path, code_blocks: list[CodeBlock], lines: tuple[str, ...])` | Parsed file with code blocks (in `file_utils.py`) |
| `FileInfo.update` | `def update(self, verbose: bool, dry_run: bool) -> None` | Write changes back to file |
| `FileInfo.reload` | `def reload(self) -> None` | Re-read file from disk after init-mode writes |
| `FileInfo.from_file` | `@staticmethod def from_file(file: Path, include_empty: bool = False) -> FileInfo \| None` | Parse a single file |
| `CodeBlock` | `CodeBlock(kind: STUB_BLOCK_KINDS, param: str \| tuple[str, ...], lineno_start: int, lineno_end: int, lines: list[str])` | Parsed marker block; kind is `"global"`, `"object"`, `"ty-map"`, `"import-section"`, `"import-object"`, `"export"`, `"__all__"`, or `None`; `param` is tuple for `global` and `import-object` kinds (b58c2e3) |
| `FuncInfo` | `FuncInfo(schema: NamedTypeSchema, is_member: bool)` | Function metadata wrapper (in `utils.py`; `schema` changed to `NamedTypeSchema` in b58c2e3) |
| `FuncInfo.from_schema` | `@staticmethod def from_schema(name: str, schema: TypeSchema, *, is_member: bool = False) -> FuncInfo` | Factory from name and schema (renamed from `from_global_name` in b58c2e3) |
| `FuncInfo.gen` | `def gen(self, ty_map: Callable[[str], str], indent: int) -> str` | Generate stub line for this function |
| `ObjectInfo` | `ObjectInfo(fields: list[NamedTypeSchema], methods: list[FuncInfo], type_key: str \| None, parent_type_key: str \| None)` | Object metadata wrapper (in `utils.py`; fields changed to `NamedTypeSchema`, added `type_key`/`parent_type_key` in b58c2e3) |
| `ObjectInfo.from_type_info` | `@staticmethod def from_type_info(type_info: TypeInfo) -> ObjectInfo` | Factory from TypeInfo (renamed from `from_type_key` in b58c2e3) |
| `ObjectInfo.gen_fields` | `def gen_fields(self, ty_map: Callable[[str], str], indent: int) -> list[str]` | Generate field annotation lines |
| `ObjectInfo.gen_methods` | `def gen_methods(self, ty_map: Callable[[str], str], indent: int) -> list[str]` | Generate method stub lines |
| `ObjectInfo.gen_init` | `def gen_init(self, ty_map: Callable[[str], str], indent: int) -> list[str]` (6973d225) | Generate typed `__init__` stub from reflection metadata using `InitFieldInfo` |
| `InitFieldInfo` | `InitFieldInfo(name: str, type_schema: TypeSchema, kw_only: bool, has_default: bool)` (6973d225) | Per-field init metadata used by `gen_init()` for typed stub generation |
| `collect_files` | `def collect_files(paths: list[Path]) -> list[FileInfo]` | Recursively collect and parse `.py`/`.pyi` files (in `file_utils.py`) |
| `object_info_from_type_key` | `def object_info_from_type_key(type_key: str) -> ObjectInfo` | LRU-cached ObjectInfo factory (in `lib_state.py`; added b58c2e3) |
| `collect_global_funcs` | `def collect_global_funcs() -> dict[str, list[FuncInfo]]` | Build prefix-to-FuncInfo table from FFI registry (in `lib_state.py`; moved from `analysis.py` in b58c2e3) |
| `collect_type_keys` | `def collect_type_keys() -> dict[str, list[str]]` | Build prefix-to-type_key mapping from `GetRegisteredTypeKeys()` (in `lib_state.py`; added b58c2e3) |
| `toposort_objects` | `def toposort_objects(type_keys: list[str]) -> list[ObjectInfo]` | Topological sort of ObjectInfo by inheritance using heapq Kahn's algorithm (in `lib_state.py`; added b58c2e3) |
| `generate_global_funcs` | `def generate_global_funcs(code: CodeBlock, funcs: list[FuncInfo], ty_map: dict, imports: list[ImportItem], opt: Options) -> None` | Fill global function stub block (in `codegen.py`) |
| `generate_object` | `def generate_object(code: CodeBlock, ty_map: dict, imports: list[ImportItem], opt: Options, obj_info: ObjectInfo) -> None` | Fill object stub block (in `codegen.py`) |
| `generate_import_section` | `def generate_import_section(code: CodeBlock, imports: list[ImportItem], opt: Options) -> None` | Fill import-section block from collected imports (in `codegen.py`; renamed from `generate_imports` in b58c2e3) |
| `generate_all` | `def generate_all(code: CodeBlock, all_defined: set[str], opt: Options) -> None` | Fill `__all__` block (in `codegen.py`) |
| `generate_export` | `def generate_export(code: CodeBlock) -> None` | Fill export block with `from .{mod} import *` (in `codegen.py`; added b58c2e3) |
| `generate_ffi_api` | `def generate_ffi_api(code_blocks, ty_map, module_name, object_infos, init_cfg, is_root) -> str` | Generate full `_ffi_api.py` content for init mode (in `codegen.py`; added b58c2e3) |
| `generate_init` | `def generate_init(code_blocks, module_name, submodule="_ffi_api") -> str` | Generate `__init__.py` content for init mode (in `codegen.py`; added b58c2e3) |

## CLI: `tvm-ffi-stubgen`
| Flag | Description |
|------|-------------|
| `PATH` (positional) | Files or directories to process recursively |
| `--dlls LIBS` | Semicolon-separated shared libraries to preload |
| `--imports IMPORTS` | Semicolon-separated Python modules to pre-import (added b58c2e3) |
| `--init-pypkg PKG` | Python package name for init mode (added b58c2e3) |
| `--init-lib LIB` | CMake target name for init mode (added b58c2e3) |
| `--init-prefix PREFIX` | Registry prefix filter for init mode (added b58c2e3) |
| `--indent N` | Extra indentation inside generated blocks (default: 4) |
| `--verbose` | Print unified diffs |
| `--dry-run` | Preview changes without writing |

## Rust API
| Name | Signature | Description |
|------|-----------|-------------|
| (none) | | Stubgen has no Rust API |
