# ast-testsuit

AST roundtrip test harness: parse Python files, run them through a transform,
re-parse the output, and diff the two ASTs field by field.

## Usage

```bash
uv run ast_roundtrip_check.py <directory> <method>
```

**Arguments:**

| Argument | Description |
|---|---|
| `directory` | Directory to walk recursively for `.py` files |
| `method` | Dotted callable (`ast.AST -> str`), e.g. `tvm_ffi.text._roundtrip` |
| `--include-positions` | Also compare `lineno`/`col_offset` fields (skipped by default) |

## Example

```bash
# roundtrip all Python files under tests/python/testdata/
uv run ast_roundtrip_check.py ../../tests/python/testdata/ tvm_ffi.text._roundtrip
```

## How it works

For each `.py` file found:

1. **Parse** the source into a Python AST (`a`).
2. **Transform** by calling `method(a)` to get a string `b`.
3. **Re-parse** `b` into a second AST (`b'`).
4. **Compare** `a` and `b'` recursively, field by field.

Positional fields (`lineno`, `col_offset`, `end_lineno`, `end_col_offset`,
`type_comment`) are skipped by default since printers rarely preserve them.

## Output

```text
OK tests/testdata/simple.py

MISMATCH tests/testdata/complex.py (2 diff(s))
  body[0].name: 'foo' != 'bar'
  body[1].value.args: length: 2 vs 3

ERROR tests/testdata/broken.py
Traceback ...

--- 3 files: 1 ok, 1 mismatched, 1 errors ---
```

Exit code is 0 when all files match, 1 otherwise.
