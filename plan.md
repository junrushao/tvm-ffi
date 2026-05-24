<!---
  Licensed to the Apache Software Foundation (ASF) under one
  or more contributor license agreements.  See the NOTICE file
  distributed with this work for additional information
  regarding copyright ownership.  The ASF licenses this file
  to you under the Apache License, Version 2.0 (the
  "License"); you may not use this file except in compliance
  with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an
  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
  KIND, either express or implied.  See the License for the
  specific language governing permissions and limitations
  under the License.
-->

# Plan — Re-implement Tilus IR on top of tvm-ffi `std` + `lang_kind`

## Where the new code lives

**All new IR code goes under `addons/tilus/python/`**, as a fresh addon next to
`addons/tvm_ffi_orcjit`. The Tilus repo at `/Users/junrus/Projects/tilus` is the
*reference*, not a build dependency. Nothing in this addon should import from
`tilus.*`; everything is built fresh on top of `tvm_ffi.std`.

Target layout:

```
addons/tilus/
├── pyproject.toml              # minimal, depends on tvm_ffi only
├── README.md
├── python/
│   └── tilus/
│       ├── __init__.py         # re-export public surface
│       ├── ir/
│       │   ├── __init__.py
│       │   ├── tensor.py       # Tensor / RegisterTensor / SharedTensor / GlobalTensor / TMemoryTensor
│       │   ├── layout.py       # Layout + the four concrete layouts
│       │   ├── stmt.py         # ThreadGroup, InstStmt, TensorItemPtr/Value, etc.
│       │   ├── inst.py         # Instruction base
│       │   ├── instructions/   # concrete instruction dialects (generic, cuda, ...)
│       │   ├── func.py         # Function, Metadata, Analysis, Program
│       │   └── functors.py     # IRFunctor / IRRewriter / IRVisitor on top of FieldCollectionResult
│       └── _tilus_lang.py      # TilusLang parser module + Frame factories + register_dialect("tilus", ...)
└── tests/
    ├── test_tilus_ir.py
    └── test_tilus_parser.py
```

## Goal

Port the Tilus/Hidet IR currently in `/Users/junrus/Projects/tilus/python/tilus/{hidet/ir,ir}`
into the new `addons/tilus/python/tilus/` package, built on top of the `std`
core dialect introduced in commit `ece9c390`. The new IR must:

1. Reuse `std`'s expression/statement substrate (no parallel Hidet expression layer).
2. Be defined entirely as `tvm_ffi.dataclasses.py_class` subclasses of `std.*` bases.
3. Use `field(lang_kind=...)` so that printer, parser-side collector, and field schema
   are derived automatically by `std.Node.__init_subclass__` + `__ffi_dialect_field_collector__` —
   we should never hand-write printers/collectors per node.
4. Plug into the parser via `register_dialect("tilus", TilusLang)`, including `Frame`
   factories for header-shaped syntax (kernel definitions, `with thread_group(...)`, etc.).

**A functioning, round-trippable parser *and* printer for the new dialect is
an explicit, non-negotiable deliverable of this work** — not a stretch goal,
not a follow-up. For every node type defined under `addons/tilus/python/tilus/ir/`,
the following must hold:

```python
node2 = parse(node.text())
assert structural_equal(node, node2)
```

If a node cannot be expressed in the printed surface (because it needs a
binding name, a header line, or a body), the addon must provide the matching
`Frame` factory in `_tilus_lang.py` so the parser can reconstruct it. A node
without a round-trippable text form is considered incomplete.

It's fine — and expected — to redesign IR shape to fit `std`'s vocabulary rather
than copy Tilus 1:1.

**Patching `std` / `pyast` is allowed.** The `std` dialect and the `pyast`
submodule (`python/tvm_ffi/std.py`, `python/tvm_ffi/pyast.py`,
`python/tvm_ffi/_pyast_*.py`, `python/tvm_ffi/_std_lang.py`,
`src/ffi/extra/{std,pyast_printer}.cc`, `include/tvm/ffi/extra/{std,pyast}.h`)
are first-party in this repo. If a round-trip failure or an awkward Frame
factory traces back to a bug or a missing hook in those files, fix it there
rather than working around it in the addon. Update the corresponding tests
under `tests/python/test_std*.py` / `test_pyast*.py` in the same change.
The Tilus addon is allowed to drive evolution of `std`/`pyast`, not just
consume them as-is.

## Scope (what to build)

### Phase 0 — Addon scaffolding

- `addons/tilus/pyproject.toml` declaring a `tilus` package with `tvm_ffi` as the
  only runtime dep. Model after `addons/tvm_ffi_orcjit/pyproject.toml`.
- `addons/tilus/README.md` (one paragraph: what the addon is, how to install).
- `addons/tilus/python/tilus/__init__.py` empty for now; populated as modules
  land.
- Lint/format configuration inherits from the repo root.

### Phase 1 — Drop the Hidet expr/type layer entirely

Tilus' `hidet/ir/{expr,type,dtypes}.py` provides Var, Add/Sub/Mul/Div/Mod, Cast,
Constant, Call, Let, IfThenElse, comparisons, bit ops, DataType, PointerType,
TensorType, FuncType. Every one of these already exists in
`python/tvm_ffi/std.py` (`std.Var`, `std.Add`, …, `std.IntImm`/`FloatImm`/`BoolImm`/
`StringImm`, `std.PrimTy`, `std.TensorTy`, `std.Call`, `std.IfExpr`, `std.BindExpr`,
etc.).

**Action:** do not port `hidet/ir/expr.py` or `hidet/ir/type.py` into the addon
at all. Everywhere the Tilus reference uses `hidet.ir.Expr` / `hidet.ir.Var` /
`hidet.ir.DataType`, the new addon uses `tvm_ffi.std.Expr` / `std.Var` /
`std.PrimTy`. Anything missing (e.g. `Dereference`, `Address`, `TensorElement`,
`TensorPointerType`) becomes new `Expr` / `Ty` subclasses in the new `tilus`
dialect using the `lang_kind` schema below.

### Phase 2 — Tilus dialect types: tensors and layouts

In `addons/tilus/python/tilus/ir/tensor.py`:

- `tilus.Tensor(std.Ty, mnemonic="tilus.Tensor")` — abstract base.
- Subclasses: `RegisterTensor`, `SharedTensor`, `GlobalTensor`, `TMemoryTensor`,
  each with `mnemonic="tilus.RegTensor"` etc. Mark `dtype`, `shape`,
  `optional_layout` with `lang_kind="arg"` / `"attr"`.

In `addons/tilus/python/tilus/ir/layout.py`:

- `tilus.Layout(std.Node, mnemonic="tilus.Layout")` plus the four concrete
  layout kinds. The layout *algebra* (composition, reshaping, etc.) in the
  reference `tilus/ir/layout/{register_layout,shared_layout,global_layout,tmem_layout}.py`
  is intricate Python — bring the math over more or less as-is, but reshape its
  *nodes* into `std`-derived classes.
- Keep `tilus.Layout` immutable (`frozen=True`) to mirror today's `eq=False`
  identity semantics.

### Phase 3 — Tilus-specific statements not covered by `std`

Most Tilus statements map directly onto `std`:

| Tilus today | New form |
|---|---|
| `SeqStmt` | `std.Scope` / `std.BaseScope` with `body=` |
| `ForStmt` | `std.For` (+ `unroll_factor` as `lang_kind="attr"`) |
| `IfStmt` | `std.IfStmt` |
| `WhileStmt` | `std.While` |
| `BreakStmt` / `ReturnStmt` | `std.Break` / `std.Return` |
| `LetStmt` | `std.BindExpr` + `std.Scope` body, or a new `tilus.Let(std.BaseScope, ...)` if we want the single-stmt body shape |
| `AssignStmt` | `std.Store` (or new `tilus.Assign(std.Stmt)`) |
| `DeclareStmt` | `std.VarDef` (or new `tilus.Declare(std.BaseVarDef)` if we want `init: Expr` as `lang_kind="arg"`) |
| `EvaluateStmt` | new `tilus.Evaluate(std.Stmt, mnemonic="tilus.Eval")` |

New nodes (in `addons/tilus/python/tilus/ir/stmt.py`) that have no `std`
equivalent:

- `tilus.ThreadGroup(std.BaseScope, mnemonic="tilus.ThreadGroup")` —
  `thread_begin: int = field(lang_kind="arg")`,
  `num_threads: int = field(lang_kind="arg")`,
  body via `lang_kind="body"`. This is what makes
  `with tilus.thread_group(0, 32): ...` work via a `Frame` factory.
- `tilus.InstStmt(std.Stmt, mnemonic="tilus.Inst")` —
  `inst: tilus.Instruction = field(lang_kind="arg")`. We may also promote
  instructions to print as their own statements via a `std.BaseVarDef`-style
  binding (instructions with an `output` tensor print as `out = ...Inst(...)`).
- `tilus.TensorItemPtr` / `tilus.TensorItemValue` — `std.BaseVarDef` subclasses
  with `tensor: Tensor = field(lang_kind="arg")` and
  `var: Var = field(lang_kind="var_def")`.

### Phase 4 — Instructions

Tilus has ~100 instructions in `tilus/ir/instructions/{generic.py,hints.py,cuda/*.py}`
and ~10 layout-inference helpers.

In `addons/tilus/python/tilus/ir/inst.py` define:

- `tilus.Instruction(std.Node, mnemonic="tilus.Instruction")` as the abstract
  base.
- Standardized field naming:
  - `output: Tensor | None = field(default=None, lang_kind="var_def")` —
    printed as the lhs `out = ...`.
  - `inputs: Sequence[Tensor] = field(default_factory=list, lang_kind="arg")` —
    positional args.
  - Remaining instruction-specific fields use `lang_kind="arg"` for required
    positional config (`dim`, `offsets`) and `lang_kind="attr"` for optional
    config (`unroll_factor`, `space`).

Then in `addons/tilus/python/tilus/ir/instructions/`, each concrete instruction
is one short class:

```python
@dc.py_class("tilus.LoadGlobalInst")
class LoadGlobalInst(Instruction, mnemonic="tilus.LoadGlobal"):
    output: RegisterTensor = dc.field(lang_kind="var_def")
    inputs: List[Tensor] = dc.field(default_factory=list, lang_kind="arg")
    offsets: List[std.Expr] = dc.field(default_factory=list, lang_kind="arg")
    dims: List[int] = dc.field(default_factory=list, lang_kind="attr")
```

Drop the bespoke `.create(...)` constructors, `register_input` / `shared_input`
accessors, and the `attributes` introspection trick — the schema replaces them.
Keep validation in `__post_init__`/factory helpers where today's
`InstructionError` lives.

### Phase 5 — Functions, programs, metadata

In `addons/tilus/python/tilus/ir/func.py`:

- `tilus.Function(std.BaseFunc, mnemonic="tilus.Function")` — extra fields:
  `metadata: Metadata = field(lang_kind="attr")`. `name`/`params`/`body`/`ret_type`
  are inherited from `BaseFunc` (rename today's `name` to `symbol` to match
  `std.Func`).
- `tilus.Metadata`, `tilus.Analysis` as `std.Attrs` subclasses so they round-trip
  via the attrs slot.
- `tilus.Program(std.Module, mnemonic="tilus.Program")` if it diverges from
  `std.Module`; otherwise drop the wrapper.

### Phase 6 — Parser/Frame factories (`_tilus_lang.py`) — REQUIRED

This phase is **mandatory** and gated by the round-trip requirement in the
Goal. The package must not ship without it.

Build `addons/tilus/python/tilus/_tilus_lang.py` analogous to
`python/tvm_ffi/_std_lang.py`:

- A `TilusLang` class with `__ffi_globals__` (e.g. `thread_group`,
  `register_tensor`, `shared_tensor`, `global_tensor`), and `__ffi_generics__`
  if there are Tilus-specific operators (most should fall through to `std`).
- `Frame` subclasses for **every** header-shaped statement that cannot be
  reconstructed from the printed positional args alone. At minimum:
  - `ThreadGroupFactory(Frame)` — for `with tilus.thread_group(begin, num): ...`
  - `InstStmtFactory` (if instructions need a `var = inst(...)` binding form).
  - `TensorItemPtrFactory` / `TensorItemValueFactory` for the binding forms.
  - `FunctionFactory` — for `@tilus.function` (or whatever decorator is chosen)
    kernel definitions, so a printed kernel parses back to the same `tilus.Function`.
- `register_dialect("tilus", TilusLang)` at module import. This wires the
  parser to recognize `tilus.*` names, dispatch generics, and build region
  statements.

Concretely follow the patterns at `python/tvm_ffi/_std_lang.py:120-340`
(`FuncFactory`, `RegionFactory`, `ForFactory`).

**Acceptance bar for Phase 6:** every node type added in Phases 2–5 has a
matching round-trip test in `tests/test_tilus_parser.py`. If parsing a printed
node throws, fails to reconstruct, or produces a structurally non-equal node,
that's a bug to fix before the phase is considered done.

### Phase 7 — Visitors / rewriters / printer

In `addons/tilus/python/tilus/ir/functors.py`, reimplement Tilus'
`IRFunctor` / `IRRewriter` / `IRVisitor` on top of `tvm_ffi.std` reflection:

- Use `type(node).__ffi_dialect_field_collector__(node)` (which returns
  `FieldCollectionResult` with `args` / `attrs` / `var_def` / `body`) to drive
  a default `visit_default` that descends into all dialect children, mirroring
  how the current `IRRewriter` walks `dataclasses.fields`.
- Keep the identity-keyed memoization since tensors/instructions are still
  identity-equal.
- Do **not** port `tilus/ir/tools/printer.py` — `Node.text()` from `std`
  already covers the text form once `lang_kind` annotations are present.
  Snapshot a few golden outputs and update them.

## Out of scope (explicit non-goals)

- No CUDA/Hidet codegen changes. This addon stops at the IR layer.
- No transpiler (`tilus.lang.transpiler`) port in this pass — once the IR
  boots and `IRRewriter` works, the transpiler edit is a smaller follow-up.
- Don't try to preserve every existing `.create(...)` factory signature.
  Provide constructors that match `std`'s conventions.
- No dependency on the reference Tilus checkout at runtime. We can read it
  while implementing, but the addon must be self-contained.

## Validation plan

1. **Per-node round-trip — the primary acceptance gate.** For *every* node type
   defined under `addons/tilus/python/tilus/ir/`, add a parametrized test that:
   1. Constructs a representative instance via the Python API.
   2. Calls `.text()` to render it.
   3. Calls `parse(text)` and asserts `structural_equal(original, parsed)` via
      `tvm_ffi.structural.structural_equal`.

   A node that has no round-trip test is not done. A node whose round-trip fails
   is not done.

2. **Printer goldens:** drop ~5 representative kernel IRs into
   `addons/tilus/tests/test_tilus_ir.py`, snapshot their `.text()`, and verify
   the snapshots stay stable under unrelated changes.

3. **Parser surface coverage:** for each Frame factory in `_tilus_lang.py`, add
   a `tests/test_tilus_parser.py` case that parses a hand-written `tilus.*`
   string and asserts the result equals the Python-constructed form. This
   catches cases where the printer omits something the parser cannot recover.

4. **Pass smoke test:** port one representative pass (suggest
   `dead_code_elimination` — see Tilus' `CLAUDE.md` for context) onto the new
   `IRRewriter`. Run a small custom test.

## Suggested execution order

1. **Phase 0 + spike.** Stand up the addon, then prove a *complete* vertical
   slice — construct, print, parse, assert structural equality — for
   `tilus.RegisterTensor` + `tilus.LoadGlobalInst` + `tilus.InstStmt`. The
   round-trip test must pass *before* moving on. This is the canary that
   confirms `lang_kind` + a single `Frame` factory is enough to make the
   printer/parser pair work end-to-end.
2. Once (1) clears, mass-port the remaining ~100 instructions — they're
   mechanical. Each new instruction adds one row to the round-trip test.
3. Port `Function` / `Metadata` / `Program`, then statements (ThreadGroup, Let,
   etc.). Each gets its Frame factory and round-trip test in the same patch.
4. Replace `IRFunctor` / `IRRewriter` using the dialect field collector.
5. Migrate one pass + tests, then declare the IR layer done.

## Key references inside this repo

- `python/tvm_ffi/std.py:148-220` — `Node` base + auto-installation of
  `__ffi_dialect_field_collector__`.
- `python/tvm_ffi/std.py:69-119` — the default collector logic for `arg` /
  `attr` / `var_def` / `body`.
- `python/tvm_ffi/std.py:1454-1700` — `BaseFor` / `For` / `BaseWhile` /
  `BaseBindExpr` / `BaseVarDef` / `Store` examples (good templates for new
  statements).
- `python/tvm_ffi/_std_lang.py:120-485` — `Frame` factories, `register_dialect`,
  `__ffi_globals__`, `__ffi_generics__`.
- `python/tvm_ffi/_pyast_parser.py:180-242` — `Factory` / `TyFactory` / `Frame`
  base classes.
- `tests/python/test_std_parser.py:2423-2440` — minimum working example of
  `register_dialect` with a custom dialect.

## Key references in the Tilus reference checkout

- `/Users/junrus/Projects/tilus/python/tilus/ir/stmt.py` — statement set to map.
- `/Users/junrus/Projects/tilus/python/tilus/ir/inst.py` — `Instruction` base.
- `/Users/junrus/Projects/tilus/python/tilus/ir/instructions/{generic.py,hints.py,cuda/*.py}` —
  full instruction catalog to port.
- `/Users/junrus/Projects/tilus/python/tilus/ir/tensor.py` — tensor kinds.
- `/Users/junrus/Projects/tilus/python/tilus/ir/layout/` — layout algebra to bring across.
- `/Users/junrus/Projects/tilus/python/tilus/ir/func.py` — `Function` / `Metadata`.
- `/Users/junrus/Projects/tilus/python/tilus/ir/functors/functor.py` —
  `IRFunctor` / `IRRewriter` / `IRVisitor` shape to reimplement on top of
  `FieldCollectionResult`.
