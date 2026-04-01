#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.9"
# ///
"""AST roundtrip comparison: parse -> transform -> re-parse -> diff field-by-field."""

from __future__ import annotations

import argparse
import ast
import importlib
import sys
import warnings
from collections.abc import Generator
from pathlib import Path
from typing import Any

_POSITION_FIELDS = frozenset(
    {"lineno", "col_offset", "end_lineno", "end_col_offset", "type_comment"}
)
_SENTINEL = object()


def import_callable(dotted: str) -> Any:
    """Import 'pkg.mod.func' -> callable."""
    mod_path, _, attr = dotted.rpartition(".")
    if not mod_path:
        print(f"error: need 'module.name', got {dotted!r}", file=sys.stderr)
        sys.exit(1)
    return getattr(importlib.import_module(mod_path), attr)


def compare(
    a: Any, b: Any, path: str = "", *, skip: frozenset[str] = _POSITION_FIELDS
) -> Generator[tuple[str, str], None, None]:
    """Recursively compare two AST values. Yield (path, message) for each mismatch."""
    if type(a) is not type(b):
        yield (path or "<root>", f"type: {type(a).__name__} vs {type(b).__name__}")
        return

    if isinstance(a, ast.AST):
        a_fields = {f for f, _ in ast.iter_fields(a)}
        b_fields = {f for f, _ in ast.iter_fields(b)}
        for field in sorted(a_fields | b_fields):
            if field in skip:
                continue
            child = f"{path}.{field}" if path else field
            val_a = getattr(a, field, _SENTINEL)
            val_b = getattr(b, field, _SENTINEL)
            if val_a is _SENTINEL:
                yield (child, "extra field in roundtripped AST")
            elif val_b is _SENTINEL:
                yield (child, "field missing in roundtripped AST")
            else:
                yield from compare(val_a, val_b, child, skip=skip)
    elif isinstance(a, list):
        if len(a) != len(b):
            yield (path, f"length: {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            yield from compare(x, y, f"{path}[{i}]", skip=skip)
    elif a != b:
        yield (path or "<root>", f"{a!r} != {b!r}")


def main() -> int:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", type=Path, help="directory to walk for .py files")
    ap.add_argument(
        "method",
        help="dotted callable: ast.AST -> str (e.g. tvm_ffi.text._roundtrip)",
    )
    ap.add_argument(
        "--include-positions",
        action="store_true",
        help="also compare lineno / col_offset fields",
    )
    args = ap.parse_args()

    if not args.directory.is_dir():
        print(f"error: {args.directory} is not a directory", file=sys.stderr)
        return 1

    fn = import_callable(args.method)
    skip = frozenset() if args.include_positions else _POSITION_FIELDS

    files = sorted(args.directory.rglob("*.py"))
    if not files:
        print(f"no .py files found under {args.directory}")
        return 0

    n_ok = n_err = n_mismatch = n_skip = 0

    for path in files:
        # Step 1: parse the original source
        try:
            source = path.read_text()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                a = ast.parse(source, filename=str(path))
        except Exception as exc:
            n_skip += 1
            print(f"SKIP {path}: {exc}")
            continue

        # Step 2: roundtrip through the transform and re-parse
        try:
            b_str: str = fn(a)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", SyntaxWarning)
                b_prime = ast.parse(b_str)
            if caught:
                msgs = "; ".join(str(w.message) for w in caught)
                raise SyntaxWarning(msgs)
        except Exception as exc:
            n_err += 1
            print(f"\nERROR {path}: {exc}")
            continue

        diffs = list(compare(a, b_prime, skip=skip))
        if diffs:
            n_mismatch += 1
            print(f"\nMISMATCH {path} ({len(diffs)} diff(s))")
            for field_path, msg in diffs:
                print(f"  {field_path}: {msg}")
        else:
            n_ok += 1
            print(f"OK {path}")

    total = n_ok + n_err + n_mismatch
    skipped = f", {n_skip} skipped" if n_skip else ""
    print(f"\n--- {total} files: {n_ok} ok, {n_mismatch} mismatched, {n_err} errors{skipped} ---")
    return 1 if (n_err or n_mismatch) else 0


if __name__ == "__main__":
    raise SystemExit(main())
