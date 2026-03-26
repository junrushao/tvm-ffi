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

# Plan — Re-implement Loom Weave IR on top of tvm-ffi `std` + `lang_kind`

## Why this plan exists

Commit `91462a02` ("feat(ir)!: add Tilus dialect addon and explicit attrs")
landed the Tilus IR addon at `addons/tilus/python/` on top of the `std` dialect
and the `pyast` parser/printer. It proves the recipe works end-to-end —
`tvm_ffi.dataclasses.py_class` subclasses of `std.*` with `field(lang_kind=...)`
produce a round-trippable text format with no per-node printer code.

We're now doing the same thing for **Loom's Weave IR**
(`/Users/junrus/Projects/loom`). Weave is roughly 10× larger than the Tilus IR
we just ported (~190 ops, ~30 top-level IR config dataclasses, a typed `Expr`
layer, a DSL builder, and a Python-AST DSL surface), so the workflow uses
6 subagents per stage to keep wall-clock time bounded.

## Where the new code lives

**All new IR code goes under `addons/weave/python/`**, as a fresh addon next to
`addons/tilus`. The Loom repo at `/Users/junrus/Projects/loom` is the
*reference*, not a build dependency. Nothing in this addon should import from
`loom.*`; everything is built fresh on top of `tvm_ffi.std`.

Target layout (mirrors `addons/tilus/`):

```
addons/weave/
├── pyproject.toml              # apache-weave, depends on tvm_ffi only
├── README.md
├── python/
│   └── weave/
│       ├── __init__.py         # re-export public surface
│       ├── ir/
│       │   ├── __init__.py
│       │   ├── dtypes.py       # DType + LM namespace, on top of std.PrimTy
│       │   ├── handles.py      # BufferRef, SmemView, TmemRegion, TmaDescriptor, MbarrierSpec, etc.
│       │   ├── config.py       # WarpConfig, PipelineConfig, GridConfig, TmemConfig, EpilogueConfig
│       │   ├── task.py         # TaskSpec, ScalarParam, ForLoop/IfElse/Block/Break/VarDecl/Assign
│       │   ├── ops/            # all ~190 Op subclasses, split by theme
│       │   │   ├── __init__.py
│       │   │   ├── memory.py   # BuiltinVar, Smem/Gmem/Tmem/Tma load/store, vec ops, scale-factor copy
│       │   │   ├── barriers.py # BarrierSync/Wait/Signal, MBarrier*, Fence, ClusterSync, GridSync
│       │   │   ├── mma.py      # MmaParams, Tcgen05Cp, FragmentOp, PackedF32x2, WarpGroupReduce
│       │   │   ├── atomic.py   # AtomicOp, AtomicFetchAdd, RelaxedFmax, AtomicMaxF32*, Multimem*
│       │   │   ├── clc.py      # ClcTryCancel/QueryCancel*/FenceRelease, GridDepSync/Launch
│       │   │   └── elementwise.py  # Elementwise, Reduce variants, PredicatedStore, ThreshMask, MaskFill
│       │   ├── kernel.py       # WeaveIR top-level: pipeline/warps/grid/tmem/epilogue, buffers, tasks, mbarriers
│       │   └── functors.py     # IRRewriter / IRVisitor on top of FieldCollectionResult
│       └── _weave_lang.py      # WeaveLang parser module + Frame factories + register_dialect("weave", ...)
└── tests/
    ├── conftest.py
    ├── test_weave_dtypes.py
    ├── test_weave_handles.py
    ├── test_weave_config.py
    ├── test_weave_task.py
    ├── test_weave_ops_*.py     # one per ops/<theme>.py
    ├── test_weave_kernel.py
    ├── test_weave_parser.py
    └── test_weave_text_roundtrip.py
```

## Goal

Port Loom's Weave IR (currently in `/Users/junrus/Projects/loom/loom/codegen/{weave_ir,ops,expr,compute_primitives,dtypes}.py` and the `loom/weave/{builder,decorator,types,handles,var}.py` DSL surface) into the new `addons/weave/python/weave/` package, built on top of the `std` core dialect. The new IR must:

1. Reuse `std`'s expression substrate (`std.Expr`, `std.Var`, `std.IntImm`, `std.PrimTy`, `std.Call`, etc.). **Do not** port `loom/codegen/expr.py` as a parallel expression tree.
2. Be defined entirely as `tvm_ffi.dataclasses.py_class` subclasses of `std.*` bases.
3. Use `field(lang_kind=...)` so that printer, parser-side collector, and field schema are derived automatically by `std.Node.__init_subclass__` + `__ffi_dialect_field_collector__` — we should never hand-write printers/collectors per node.
4. Plug into the parser via `register_dialect("weave", WeaveLang)`, including `Frame` factories for header-shaped syntax (`with w.role(...)`, `with pipe.iterate() as k`, `@loom.weave(...)` kernel decorator, etc.).

**A functioning, round-trippable parser *and* printer for the new dialect is
an explicit, non-negotiable deliverable of this work** — not a stretch goal,
not a follow-up. For every node type defined under
`addons/weave/python/weave/ir/`, the following must hold:

```python
node2 = parse(node.text())
assert structural_equal(node, node2)
```

If a node cannot be expressed in the printed surface (because it needs a
binding name, a header line, or a body), the addon must provide the matching
`Frame` factory in `_weave_lang.py` so the parser can reconstruct it. A node
without a round-trippable text form is considered incomplete.

It's fine — and expected — to redesign IR shape to fit `std`'s vocabulary
rather than copy Loom 1:1. In particular: Loom's frozen-dataclass IR uses
identity-based `__eq__`, but the new addon should opt into structural equality
via `@py_class(structural_eq="tree")` and rely on `tvm_ffi.structural.structural_equal`.

**Patching `std` / `pyast` is allowed.** The `std` dialect and the `pyast`
submodule (`python/tvm_ffi/std.py`, `python/tvm_ffi/pyast.py`,
`python/tvm_ffi/_pyast_*.py`, `python/tvm_ffi/_std_lang.py`,
`src/ffi/extra/{std,pyast_printer}.cc`, `include/tvm/ffi/extra/{std,pyast}.h`)
are first-party in this repo. If a round-trip failure or an awkward Frame
factory traces back to a bug or a missing hook in those files, fix it there
rather than working around it in the addon. Update the corresponding tests
under `tests/python/test_std*.py` / `test_pyast*.py` in the same change. The
Weave addon is allowed to drive evolution of `std`/`pyast`, not just consume
them as-is, just like the Tilus addon did in commit `91462a02`.

## The six work buckets

Weave IR is large enough that we partition it into six thematic buckets up
front. Every stage of the workflow operates on these same six buckets so that
context, tests, and reviews stay aligned.

| # | Bucket | Source-of-truth files in `/Users/junrus/Projects/loom/loom/codegen/` | New file(s) in addon |
|---|--------|---------------------------------------------------------------------|----------------------|
| 1 | **Expr, dtypes, type system** | `expr.py`, `dtypes.py`, `compute_primitives.py` enums, `loom/weave/types.py` (`lm` namespace) | `ir/dtypes.py` + reuse `std.Expr` |
| 2 | **Top-level IR config + handles** | `weave_ir.py` (PipelineStyle/EpilogueStyle/TmemBuffering, WarpRole, TmemRegion, MbarrierSpec, TmaDescriptor, BufferRef, ScalarParam, WarpConfig, PipelineConfig, GridConfig, TmemConfig, EpilogueConfig, SmemPool, SmemView, PhaseVar/Domain, MmaParams, SoftmaxParams, EpilogueParams, TmaLoadParams, **WeaveIR**) | `ir/config.py`, `ir/handles.py`, `ir/kernel.py` |
| 3 | **Task + control flow** | `ops.py` ForLoop, IfElse, Break, Block, VarDecl, Assign, ConditionalIteration, LeaderCtaBlock, ElectedThreadBlock, plus `TaskSpec` from `weave_ir.py` | `ir/task.py` |
| 4 | **Memory + elementwise ops** | `ops.py` BuiltinVar, TmemRegionLoad/Store, SmemDesc, SmemLoad/Store/Read/Write/LoadRegs/LoadVec/StoreVec, GmemLoad/Store, TmaStore, TmaReduceOp, TmaGatherLoad, ScaleFactorCopy, MetadataCopy, PredicatedStore, Elementwise, ThreshMask, BitmaskFill, MaskFill, RegArrayCast | `ir/ops/memory.py`, `ir/ops/elementwise.py` |
| 5 | **Barriers, fences, sync, mbarriers, reductions** | `ops.py` BarrierSync/TryWait/Wait/Signal, MBarrierArrive, PeerArriveCommit, MulticastCommit, DualCommit, Fence, ThreadFence, ClusterSync, GridSync, ClusterMapa, ClusterBarrierArrive, CpAsyncBulkSmem2SmemCluster, GridDepSync, GridDepLaunch, WarpReduce, BlockReduce, CrossWarpReduce, WarpGroupReduce, StAsync | `ir/ops/barriers.py` |
| 6 | **MMA, TMEM, atomics, multimem, CLC** | `ops.py` Tcgen05Cp, MmaParams (via task), FragmentOp, PackedF32x2, AtomicOp, AtomicFetchAdd, RelaxedFmax, AtomicMaxF32Positive, SysVolatileLoad128/Store128, MultimemLdReduce/Store/RedAddI32, AtomicMaxFloatEncode/Decode, ClcTryCancel, ClcQueryCancel, ClcQueryCancelGetCtaId, ClcFenceRelease | `ir/ops/mma.py`, `ir/ops/atomic.py`, `ir/ops/clc.py` |

These buckets are roughly equal in node count (~25–40 nodes each) and have
minimal cross-bucket coupling — exactly what a 6-way parallel split needs.

## Workflow — 6 subagents at every stage

Each of the six stages below must spawn **6 subagents in parallel**, one per
bucket. Subagents communicate through the plan, the codebase, and the test
suite — not through each other. The main agent is responsible for waiting on
all 6, integrating, and only then advancing to the next stage.

When launching subagents, the main agent MUST send a single message
containing 6 `Agent` tool calls so they run concurrently, per the project's
parallelism rules. Use `subagent_type="Explore"` for stages 1 and 5,
`subagent_type="general-purpose"` (or `Plan` for stage 2) for the rest,
and pass `isolation: "worktree"` only when the subagent will commit to a branch.

### Stage 1 — Exploration (6 subagents, parallel, read-only)

Spawn one **Explore** subagent per bucket. Each subagent's job:

1. Read the corresponding Loom source files end to end (limits below).
2. Produce a `findings.md` (returned as the subagent's final message — do not
   write to disk) covering: every node/op in the bucket, its semantically
   meaningful fields, which fields are positional vs keyword vs body-bearing,
   and which existing `std.*` base class is the right parent.
3. Flag anything that cannot map cleanly onto `std`'s vocabulary, so we can
   debate redesign before implementation begins.

The main agent collects all six findings, reconciles them in a single
`addons/weave/SCHEMA.md` document (one section per bucket, listing every
target `weave.*` class with parent, `mnemonic`, and field schema), and stops
to confirm with the user before stage 2.

### Stage 2 — Unit-test design (6 subagents, parallel, read-only)

Spawn one **Plan** (or `general-purpose`) subagent per bucket. Inputs: the
agreed `SCHEMA.md`, plus the bucket's Loom reference files. Each subagent
designs:

1. A pytest module skeleton for the bucket (one or more `test_weave_*.py`
   files), with named test functions but *empty bodies*.
2. A round-trip test that, for every node in the bucket, constructs an
   instance, prints it, parses it, and asserts `structural_equal`.
3. Targeted negative tests for fields that demand validation (rejecting raw
   strings in Expr fields, rejecting `attrs` on subclasses that don't declare
   it, etc. — mirror the discipline from `ops.py:Op.__post_init__`).
4. Parser surface tests: a small hand-written `weave.*` snippet per `Frame`
   factory, parsed and structurally equal to the Python-constructed form.

Subagents return the proposed file layout and a list of test names; the main
agent writes those skeletons into `addons/weave/tests/` *with `pytest.skip` or
`pytest.fail("not implemented")` bodies* before stage 3 begins. Tests are
checked in skipped/failing on purpose — they become the acceptance gate.

### Stage 3 — Parallel implementation (6 subagents, parallel, write)

Spawn one `general-purpose` subagent per bucket, each with `isolation: "worktree"`. Inputs: the agreed `SCHEMA.md`, the skipped test file for that bucket, and the corresponding Loom source. Each subagent:

1. Writes the bucket's IR module(s) — node classes inheriting from
   `std.Node` / `std.Stmt` / `std.Expr` / `std.Attrs` with `mnemonic="weave.X"`
   and `lang_kind=...` annotations on every field that participates in
   syntax.
2. Adds the matching `Frame` factories to `_weave_lang.py` and registers them
   on the bucket-scoped namespace inside `WeaveLang`.
3. Removes the `pytest.skip` markers and ensures every test in the bucket's
   test file passes locally (`pytest addons/weave/tests/test_weave_<bucket>.py`).
4. Returns the worktree branch name + a 5-line summary of what changed.

Buckets are ordered so that downstream buckets can depend on upstream ones:

- **Bucket 1 (Expr/dtypes)** must finish first, since every other bucket
  references dtypes.
- **Bucket 2 (config/handles)** can run as soon as 1 is in.
- **Buckets 3–6** run fully in parallel after 1 and 2 land.

The main agent waits for all six worktrees, then merges them sequentially
into the integration branch, resolving any cross-bucket import skew.

### Stage 4 — Verification (6 subagents, parallel, read-only)

Spawn one `general-purpose` subagent per bucket on the integrated branch.
Each subagent:

1. Runs the bucket's test file plus the global round-trip suite
   (`pytest addons/weave/tests/test_weave_text_roundtrip.py`).
2. Runs `python -m ruff check addons/weave` and `python -m ruff format --check addons/weave`.
3. Runs `ty check --error-on-warning` scoped to the bucket's files.
4. Constructs **at least one Loom kernel from `loom/examples/`** that exercises
   the bucket's nodes, ports the schedule into the new dialect by hand,
   prints it, re-parses it, and confirms structural equality.
5. Reports any failure as a structured bug list (node name, failing test,
   minimal repro).

The main agent collates the six bug lists; if any are non-empty, advance to
stage 5 with that input. Otherwise jump straight to stage 6.

### Stage 5 — Review (6 subagents, parallel, read-only)

Spawn the project's code review agents Reviewers return prioritized findings.
Anything graded "must fix" or "correctness" feeds stage 6.

### Stage 6 — Issue addressing (6 subagents, parallel, write)

Spawn one `general-purpose` subagent per bucket again (worktree mode),
hand each one its accumulated bug list from stages 4 and 5. Each subagent:

1. Fixes the listed bugs only — no scope creep.
2. Re-runs the bucket's tests + the global round-trip suite locally.
3. Returns its worktree branch and a `git diff --stat`.

The main agent merges, then re-runs the full `pytest addons/weave/tests` and
the full lint pipeline. If anything new breaks, loop back to stage 5 with the
new findings. Otherwise the IR layer is done.

### Stage gates

- **No stage starts until the previous stage's main-agent integration step
  has completed cleanly.**
- Each stage produces a written artifact (`findings.md` / `SCHEMA.md` /
  skipped test skeletons / integration commit / verification report / review
  report / fix commit). The artifact is the gate.
- The user is consulted at the end of stages 1 and 2 before code lands; the
  rest of the stages proceed autonomously unless a subagent is genuinely
  blocked.

## Phases (independent of workflow stages)

The workflow stages above are *process*. The phases below describe *what gets
built*. Stages 3 and 6 are where phase work happens; the other stages plan,
test, verify, or review the same phase output.

### Phase 0 — Addon scaffolding

- `addons/weave/pyproject.toml` declaring an `apache-weave` package with
  `apache-tvm-ffi` as the only runtime dep. Copy from
  `addons/tilus/pyproject.toml` and rename.
- `addons/weave/README.md` (one paragraph: what the addon is, how to install).
- `addons/weave/python/weave/__init__.py` empty for now; populated as modules
  land.
- Lint/format config inherits from the repo root.

### Phase 1 — Expr + dtypes (bucket 1)

Replace Loom's `loom/codegen/expr.py` *entirely* with `std.Expr` / `std.Var` /
`std.IntImm` / `std.FloatImm` / `std.BoolImm` / `std.StringImm` / `std.Add` /
`std.Sub` / `std.Mul` / `std.Eq` / `std.IfExpr` / `std.Call` / `std.Cast` /
`std.Load` / `std.Store`. Map Loom's nodes:

| Loom | std |
|---|---|
| `Lit` | `std.IntImm` / `std.FloatImm` / `std.BoolImm` (by type) |
| `Var` | `std.Var` |
| `Const` | new `weave.Const(std.Expr, mnemonic="weave.Const")` if we need the ALL_CAPS-as-Const distinction; otherwise just `std.Var` |
| `BinOp` | `std.Add` / `std.Sub` / `std.Mul` / `std.CDiv` / `std.FloorDiv` / `std.FloorMod` / `std.LShift` / `std.RShift` / `std.BitwiseAnd` / `std.BitwiseOr` / `std.BitwiseXor` |
| `UnaryOp` | `std.Not` / `std.BitwiseNot` (and a new `weave.Neg` if needed) |
| `Compare` | `std.Eq` / `std.Ne` / `std.Lt` / `std.Le` / `std.Gt` / `std.Ge` |
| `Index` | `std.Load` |
| `Field` | new `weave.Field(std.Expr, mnemonic="weave.Field")` — base + attribute name |
| `Call` | `std.Call` |
| `Ternary` | `std.IfExpr` |
| `CastExpr` | `std.Cast` |
| `AddrOf` / `Deref` | new `weave.AddrOf` / `weave.Deref` as `std.Expr` subclasses |
| `ReinterpretCastExpr` | new `weave.ReinterpretCast` |
| `SmemSwizzleOffset` / `SmemSwizzleAddress` / `SmemDescBuilt` | new dialect nodes |
| `Intrinsic` enum | `std.Call` with a known callee name |

Also build `weave.ir.dtypes` re-exporting `std.i32` / `std.u32` / `std.f32` /
`std.bf16` / `std.f16` / `std.u8` / `std.u64` / `std.f64` from
`tvm_ffi._std_lang.Std`, plus a `lm` namespace re-exporting the same with
TMA-descriptor and constexpr sentinel types (`_TmaType`, `_TmaGatherType`,
`_TmaReduceType`, `_GridCounterType`, `_ParamPtrInstance`, `_ConstexprType`)
ported as `std.Ty` subclasses with `mnemonic="weave.Tma2d"` etc.

### Phase 2 — Top-level IR config + handles (bucket 2)

Every "config" dataclass in `weave_ir.py` becomes a `std.Attrs` subclass with
all fields marked `lang_kind="attr"`. Every "handle" dataclass (BufferRef,
SmemView, TmemRegion, TmaDescriptor, MbarrierSpec, etc.) becomes a `std.Node`
subclass.

`WeaveIR` itself becomes a `std.Module`-shaped node — `weave.Kernel(std.Node,
mnemonic="weave.Kernel")` — with `tasks` as `lang_kind="body"`, and every
config as `lang_kind="attr"`.

### Phase 3 — Task + control flow (bucket 3)

`TaskSpec` becomes `weave.Task(std.BaseFunc, mnemonic="weave.Task")` — name as
`symbol`, params, body of ops via `lang_kind="body"`.

`ForLoop` → `std.For` (extend with Loom's `unroll`, `pipeline_name`, etc. as
`lang_kind="attr"`).
`IfElse` → `std.IfStmt`.
`Break` → `std.Break`.
`Block` → `std.Scope`.
`VarDecl` → `std.VarDef` (or new `weave.VarDecl(std.BaseVarDef)` if we keep
the `init` slot).
`Assign` → `std.Store` (or new `weave.Assign(std.Stmt)`).
`ConditionalIteration`, `LeaderCtaBlock`, `ElectedThreadBlock` → new
`std.BaseScope` subclasses with the leader-elect predicate as `lang_kind="arg"`.

### Phase 4 — Memory + elementwise ops (bucket 4)

Each op becomes a `weave.<Name>(std.Stmt, mnemonic="weave.<Name>")` with:

- Result handle (if any) as `lang_kind="var_def"`.
- Required positional operands (`src`, `dst`, `addr`) as `lang_kind="arg"`.
- Optional configuration (`swizzle`, `bytes`, `predicate`) as
  `lang_kind="attr"`.

Loom's `Op.__post_init__` discipline (reject raw strings in Expr fields,
require explicit dtypes) ports as `__post_init__` on each weave node, or as a
shared helper imported by every op file.

### Phase 5 — Barriers + fences + sync (bucket 5)

Same shape as bucket 4, with `std.Stmt` parents and `lang_kind="arg"`/`"attr"`
fields. The mbarrier topology — `MbarrierSpec` and its referencing ops —
needs structural equality wired through `std.Attrs`, since two mbarriers with
the same shape but different identities are different ops.

### Phase 6 — MMA + atomic + CLC (bucket 6)

Identical pattern. `MmaParams` becomes `std.Attrs`; `Tcgen05Cp` /
`FragmentOp` / `WarpGroupReduce` / `AtomicOp` and friends become `std.Stmt`
nodes with their operand exprs as `lang_kind="arg"`.

### Phase 7 — Parser frames, kernel decorator, functors

After buckets 1–6 are merged:

1. `_weave_lang.py` exposes a `WeaveLang` class with `__ffi_globals__` (`lm`,
   `role`, `pipeline`, `barrier`, `smem`, `tmem`, `gmem`), `__ffi_generics__`
   (operator delegation to std), and Frame factories for every body-bearing
   construct (KernelFactory, TaskFactory, RoleFactory, PipelineIterFactory,
   ForFactory, IfFactory).
2. `register_dialect("weave", WeaveLang)` at module import.
3. `weave.ir.functors` reimplements `IRRewriter` / `IRVisitor` on top of
   `FieldCollectionResult` (the same recipe `addons/tilus/python/tilus/ir/functors.py`
   uses today).

## Validation plan

1. **Per-node round-trip — the primary acceptance gate.** For *every* node
   type defined under `addons/weave/python/weave/ir/`, add a parametrized
   test that constructs a representative instance, calls `.text()`, calls
   `parse(text)`, and asserts `structural_equal(original, parsed)`. A node
   without a round-trip test is not done. A node whose round-trip fails is
   not done.
2. **Kernel-level round-trip.** Pick five representative kernels from
   `/Users/junrus/Projects/loom/loom/examples/` (suggest one each of FMHA,
   GQA, RMSNorm, TopK, and a TMA/cluster-heavy DeepGEMM variant). Translate
   each into the new dialect by hand, snapshot `.text()`, and round-trip.
   Snapshots live in `addons/weave/tests/snapshots/`.
3. **Parser surface coverage.** For each `Frame` factory in `_weave_lang.py`,
   add a `tests/test_weave_parser.py` case that parses a hand-written
   `weave.*` string and asserts the result equals the Python-constructed form.
4. **Functor smoke test.** Port one Loom analysis pass (suggest
   `loom/codegen/analysis/`'s smallest pass — race detection or a trivial
   classification pass) onto the new `IRRewriter`. Confirm it walks the new
   IR correctly.
5. **Schema parity check.** A test that imports every public symbol from the
   reference Loom files in bucket order and confirms an addon counterpart
   exists. Catches accidental drift if Loom grows.

## Out of scope (explicit non-goals)

- **No CUDA codegen.** This addon stops at the IR layer. We are not porting
  `loom/codegen/emitter.py`, `loom/codegen/expr_emit.py`, `loom/codegen/op_lowering.py`,
  or the `loom/runtime/` machinery.
- **No `@loom.weave` AST decorator port.** The decorator builds a `WeaveBuilder`
  from a Python function's AST. We're rebuilding the IR, not the trace API.
  The dialect parser already handles round-trip from text; the
  Python-function-trace pathway is a separate (future) decorator on top of
  this addon.
- **No analysis-pass port beyond the smoke test above.** Once the IR boots,
  porting `loom/codegen/analysis/` is a separate, larger task.
- **No dependency on the reference Loom checkout at runtime.** We read it
  while implementing, but the addon must be self-contained.
- **No backward-compat shims.** Per Loom's own `IR_DESIGN_PRINCIPLES.md`,
  one canonical form. If a node has two equivalent shapes in Loom today,
  pick the cleaner one and drop the other.

## Suggested execution order at the meta level

1. Stand up `addons/weave/` (Phase 0) — main agent does this directly.
2. **Stage 1 — Exploration** (6 subagents). Produce `SCHEMA.md`.
3. Pause for user review of `SCHEMA.md`.
4. **Stage 2 — Unit-test design** (6 subagents). Land skipped test skeletons.
5. **Stage 3 — Implementation** (6 subagents in worktrees). Land code per
   bucket; merge into integration branch. Run buckets in 1 → 2 → {3,4,5,6}
   dependency order.
6. **Stage 4 — Verification** (6 subagents). Produce verification report.
7. **Stage 5 — Review** (6 reviewer runs across three reviewer agents).
   Produce review report.
8. **Stage 6 — Issue addressing** (6 subagents in worktrees). Land fixes.
9. Re-run all tests + lint at the top level. If clean, declare the IR layer
   done and open a single PR analogous to commit `91462a02`.

## Key references inside this repo

- `addons/tilus/python/tilus/` — the just-shipped Tilus addon. **This is the
  pattern to mirror.** In particular:
  - `addons/tilus/python/tilus/ir/__init__.py` — public surface shape.
  - `addons/tilus/python/tilus/ir/inst.py` — `Instruction` base built on
    `std.Stmt` with `lang_kind`.
  - `addons/tilus/python/tilus/_tilus_lang.py` — `Frame` factories +
    `register_dialect("tilus", ...)`.
  - `addons/tilus/python/tilus/ir/functors.py` — `IRRewriter` / `IRVisitor`
    on top of `FieldCollectionResult`.
  - `addons/tilus/tests/` — round-trip and parser tests to copy in shape.
- `python/tvm_ffi/std.py:148-220` — `Node` base + auto-installation of
  `__ffi_dialect_field_collector__`.
- `python/tvm_ffi/std.py:69-119` — the default collector logic for `arg` /
  `attr` / `var_def` / `body`.
- `python/tvm_ffi/_std_lang.py:120-485` — `Frame` factories, `register_dialect`,
  `__ffi_globals__`, `__ffi_generics__`.
- `python/tvm_ffi/_pyast_parser.py:180-242` — `Factory` / `TyFactory` /
  `Frame` base classes.

## Key references in the Loom reference checkout

- `/Users/junrus/Projects/loom/loom/codegen/weave_ir.py` — top-level IR
  config + `WeaveIR` (bucket 2 source of truth).
- `/Users/junrus/Projects/loom/loom/codegen/ops.py` — ~190 ops, the bulk of
  the work (buckets 3–6 source of truth).
- `/Users/junrus/Projects/loom/loom/codegen/expr.py` — typed Expr tree
  (bucket 1 source of truth; do not port wholesale).
- `/Users/junrus/Projects/loom/loom/codegen/dtypes.py` +
  `/Users/junrus/Projects/loom/loom/codegen/compute_primitives.py` — enums
  and dtype machinery (bucket 1).
- `/Users/junrus/Projects/loom/loom/weave/{types,handles,builder,var,decorator}.py`
  — DSL surface; informs Frame factory design but **is not** ported here.
- `/Users/junrus/Projects/loom/loom/codegen/to_python.py` and
  `/Users/junrus/Projects/loom/loom/codegen/expr_parse.py` — Loom's existing
  text round-trip; useful for printer/parser test fixtures.
- `/Users/junrus/Projects/loom/loom/codegen/structural_eq.py` — Loom's own
  structural equality helper. Replaced by `tvm_ffi.structural.structural_equal`
  in the addon.
- `/Users/junrus/Projects/loom/IR_DESIGN_PRINCIPLES.md` — Loom's eight
  non-negotiable IR principles. Apply them when redesigning into `std`'s
  vocabulary, especially P3 (one canonical form) and P4 (type-soundness).
