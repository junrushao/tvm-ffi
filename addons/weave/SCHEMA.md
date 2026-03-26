# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

# Weave IR Schema

This schema ports Loom's Weave IR onto `tvm_ffi.std`. Nodes are
`tvm_ffi.dataclasses.py_class` classes with `structural_eq="tree"` and
`lang_kind` fields. Normal expressions use `std.Expr`; Weave only adds the
expression and type nodes missing from `std`.

Common rules:

- Store enum-like domains as canonical strings, not Python `Enum` instances.
- Use `std.Expr` fields for dynamic operands and reject raw strings in those
  fields unless the field is explicitly a name/callee/type spelling.
- Use `std.BaseFunc`, `std.BaseScope`, and `std.BaseFor` for body-bearing
  constructs. Generic body fields on plain `std.Node` / `std.Stmt` are not
  printable.
- Avoid positional list fields where std's collector would flatten the list;
  put such fields in `attr` unless a custom parser factory deliberately gathers
  varargs.

## Bucket 1: Expr, DTypes, Type System

Reuse `std.IntImm`, `std.FloatImm`, `std.BoolImm`, `std.Var`, binary/unary
`std` nodes, `std.Load`, `std.Call`, `std.IfExpr`, and `std.Cast`.

Additional nodes:

| Class / mnemonic | Parent | Fields |
| --- | --- | --- |
| `Const` / `weave.Const` | `std.Expr` | args: `name`; attrs: `result_ty` |
| `Field` / `weave.Field` | `std.Expr` | args: `base`; attrs: `field`, `result_ty` |
| `PtrTy` / `weave.PtrTy` | `std.Ty` | args: `elem_ty`; attrs: `const`, `volatile`, `space` |
| `AddrOf` / `weave.AddrOf` | `std.Expr` | args: `expr`; attrs: `result_ty` |
| `Deref` / `weave.Deref` | `std.Expr` | args: `expr`; attrs: `result_ty` |
| `ReinterpretCast` / `weave.ReinterpretCast` | `std.Expr` | args: `expr`, `target_type` |
| `SmemSwizzleOffset` / `weave.SmemSwizzleOffset` | `std.Expr` | args: `expr`; attrs: `swizzle`, `result_ty` |
| `SmemSwizzleAddress` / `weave.SmemSwizzleAddress` | `std.Expr` | args: `expr`; attrs: `swizzle`, `view`, `row_stride_bytes`, `layout`, `coord_row`, `coord_col`, `coord_col_unit`, `tcgen05_tile_height`, `tcgen05_k_elements`, `addr_space`, `result_ty` |
| `TmemRef` / `weave.TmemRef` | `std.Expr` | args: `region`; attrs: `offset`, `result_ty` |
| `SmemRef` / `weave.SmemRef` | `std.Expr` | args: `buffer`; attrs: `offset`, `result_ty` |
| `SmemDescRef` / `weave.SmemDescRef` | `std.Expr` | args: `buffer`, `k_idx`; attrs: `mode`, `result_ty` |
| `BarrierRef` / `weave.BarrierRef` | `std.Expr` | args: `barrier`; attrs: `stage`, `result_ty` |
| `BuiltinRef` / `weave.BuiltinRef` | `std.Expr` | args: `name`; attrs: `result_ty` |
| `UniformTy` / `weave.UniformTy` | `std.Ty` | args: `base` |
| `RawTy`, `ConstexprTy`, `TmaTy`, `TmaGatherTy`, `TmaReduceTy`, `GridCounterTy`, `Ue4m3Ty` | `std.Ty` | small type marker nodes |
| `Swizzle` / `weave.Swizzle` | `std.Node` | args: `base`, `bits`, `shift` |

Primitive dtype aliases are exposed through an `lm` namespace and map to
`std.PrimTy` where possible: `i8/i16/i32/i64/u8/u16/u32/u64/f16/bf16/f32/f64`,
`f8_e4m3`, `f8_e5m2`, `f8_e8m0fnu`, `f4_e2m1fn`, plus Weave-specific
`f32x2`, `bf16x2`, `ue4m3`, `raw`, `constexpr`, `tma2d`, `tma3d`, `tma4d`,
`tma5d`, `tma_gather`, `tma_reduce`, and `grid_counter`.

## Bucket 2: Top-Level Config and Handles

Config and handle records are `std.Node` unless otherwise noted.

| Class / mnemonic | Fields |
| --- | --- |
| `WarpRole` / `weave.WarpRole` | args: `name`, `warp_ids`; attrs: `register_budget`, `auto_warp_vars`, `tmem_var_regions`, `warp_group_size`, `instances` |
| `TmemRegion` / `weave.TmemRegion` | args: `name`, `start_col`, `ncols`; attrs: `num_buffers`, `kparam_name`, `var_name`, `dtype` |
| `PipelineSpec` / `weave.Pipeline` | args: `name`, `num_stages`; attrs: `style`, `smem_buffers`, `cta_group`, `producer_barriers`, `consumer_barriers`, `release_barriers`, `smem_region`, `kparam_name` |
| `PipelineProtocol` / `weave.PipelineProtocol` | args: `pipeline`; attrs: `load_tasks`, `compute_tasks`, `empty_barrier`, `full_barrier` |
| `MbarrierSpec` / `weave.Mbarrier` | args: `role`, `count`; attrs: `init_count`, `producers`, `consumers`, `signaling_mode`, `producer_warps`, `stage_var`, `pipeline`, `init_phase` |
| `TmaDescriptor` / `weave.TmaDescriptor` | args: `ndim`, `box_shape`; attrs: `swizzle`, `global_shape`, `global_strides` |
| `BufferRef` / `weave.Buffer` | args: `name`, `dtype`, `shape`; attrs: `space`, `tmem_col`, `smem_offset`, `swizzle`, `stage`, `tma`, `source_gmem`, `scale_buffer`, `align`, `volatile` |
| `ScalarParam` / `weave.Param` | args: `name`, `ctype` |
| `WarpConfig` / `weave.WarpConfig` | args: `num_warps`; attrs: `roles`, `tma_warp`, `mma_warp`, `epilogue_warps` |
| `PipelineConfig` / `weave.PipelineConfig` | attrs: `style`, `num_stages`, `pipelines` |
| `GridConfig` / `weave.GridConfig` | attrs: `cluster_dims`, `cta_group` |
| `TmemConfig` / `weave.TmemConfig` | attrs: `buffering`, `regions`, `total_cols`, `allocator_warp` |
| `EpilogueConfig` / `weave.EpilogueConfig` | args: `style`; attrs: `vectorized`, `num_epilogue_warps` |
| `SmemPool` / `weave.SmemPool` | args: `name`, `size` |
| `SmemView` / `weave.SmemView` | args: `name`, `pool`, `offset`, `shape`, `dtype`; attrs: `stage`, `stride`, `swizzle`, `layout`, `alias_of` |
| `PhaseVar` / `weave.PhaseVar` | args: `name`; attrs: `dtype`, `init_value`, `rotation_rule`, `rotation_trigger` |
| `PhaseDomain` / `weave.PhaseDomain` | args: `pipeline`, `stage_var`, `num_stages`; attrs: `phase_vars`, `owner_role`, `stage_ctype`, `stage_init` |
| `MmaParams` / `weave.MmaParams` | args: `k_steps_per_group`, `k_groups`, `group_lo_offset`; attrs: `cta_group`, `tile_m`, `tile_n`, `dtype` |
| `SoftmaxParams` / `weave.SoftmaxParams` | args: `tile_n`; attrs: `num_load_chunks`, `num_store_chunks` |
| `EpilogueParams` / `weave.EpilogueParams` | args: `head_dim`, `num_chunks_16`; attrs: `use_tma_store` |
| `TmaLoadParams` / `weave.TmaLoadParams` | args: `pipeline_name`; attrs: `num_stages`, `src_buffers`, `dst_buffers`, `full_barrier`, `empty_barrier`, `stage_var`, `phase_vars` |
| `TaskTiming`, `BarrierEdge`, `SmemAllocation`, `TmemAllocation` | attrs-only analysis artifacts |
| `NamedBarrierSpec`, `ProcessGroup`, `SymmetricMemory` | additional explicit handle-intent nodes for Loom surfaces not represented in `weave_ir.py` |

`Kernel` maps `WeaveIR` to `std.BaseFunc` with `symbol`, args, optional return
type, body scopes, and attrs for pipeline/warps/grid/tmem/epilogue/buffers/
mbarriers/smem pools/views/protocols/phase domains/params/constants and
analysis artifacts.

## Bucket 3: Tasks and Control Flow

| Class / mnemonic | Parent | Fields |
| --- | --- | --- |
| `TaskSpec` / `weave.TaskSpec` | `std.BaseScope` | args: `name`, `kind`, `assigned_role`; attrs: `pipeline`, `inputs`, `outputs`, `depends_on`, `sync_before`, `sync_after`; body |
| `ForLoop` / `weave.ForLoop` | `std.BaseFor` | inherited `extent`, `var`; attrs: `start`, `step`, `step_expr`, `constexpr`, `unroll`, `ctype`; body |
| `Block` / `weave.Block` | `std.BaseScope` | body |
| `LeaderCtaBlock` / `weave.LeaderCtaBlock` | `std.BaseScope` | body |
| `ElectedThreadBlock` / `weave.ElectedThreadBlock` | `std.BaseScope` | body |
| `ConditionalIteration` / `weave.ConditionalIteration` | `std.BaseScope` | args: `iter_var`; attrs: `last_expr`; body as a canonicalized common body |
| `VarDecl` / `weave.VarDecl` | `std.BaseVarDef` | var_def: `var`; args: `ctype`; attrs: `init`, `array_size`, `uniform`, `zero_init` |
| `Assign` / `weave.Assign` | `std.Stmt` | args: `target`, `expr`; attrs: `op` |

`IfElse` and `Break` use `std.IfStmt` and `std.Break` directly as the canonical
form unless a future std patch adds subclass-aware if/break printers.

## Bucket 4: Memory and Elementwise Ops

All nodes inherit `weave.Op(std.Stmt)` and print as generic call statements.

| Class / mnemonic | Fields |
| --- | --- |
| `BuiltinVar` | args: `name`; attrs: `dst` |
| `TmemRegionLoad` | args: `region`; attrs: `dst`, `col_offset`, `num`, `dst_offset`, `wait`, `row_base` |
| `TmemRegionStore` | args: `region`; attrs: `src`, `col_offset`, `num`, `dtype`, `row_base` |
| `SmemDesc` | args: `buffer`; attrs: `k_idx`, `mode`, `dst`, `step`, `offset` |
| `GmemLoad` | args: `src`, `dst`; attrs: `count`, `dtype`, `dst_dtype`, `dst_offset`, `index` |
| `GmemStore` | args: `src`, `dst`; attrs: `count`, `dtype`, `src_dtype`, `src_offset`, `index`, `scale`, `cache_hint` |
| `SmemStore` | args: `src`, `dst`; attrs: `predicate`, `index` |
| `SmemLoad` | args: `src`, `dst` |
| `SmemRead` | args: `src`; attrs: `dst`, `index` |
| `SmemLoadRegs` | args: `name`, `src_expr`; attrs: `count`, `dtype` |
| `SmemWrite` | args: `src`, `dst`; attrs: `index` |
| `SmemLoadVec` | args: `dst`, `src_addr`; attrs: `count`, `dst_offset` |
| `SmemStoreVec` | args: `dst_addr`, `src` |
| `TmaStore` | args: `src`, `dst` |
| `TmaReduceOp` | args: `src`, `dst`; attrs: `op` |
| `TmaGatherLoad` | args: `src`, `dst`, `page_table`; attrs: `tokens_per_page`, `mbar_expr`, `token_offset` |
| `ScaleFactorCopy` | args: `src`, `dst`; attrs: `cta_group`, `sbo`, `elected` |
| `MetadataCopy` | args: `src`, `dst`; attrs: `cta_group` |
| `Elementwise` | attrs: `op`, `inputs`, `output` |
| `PredicatedStore` | args: `dst`, `src`; attrs: `bound_m`, `bound_n`, `tile_offset_m`, `tile_offset_n` |
| `ThreshMask` | args: `dst`, `limit`; attrs: `width` |
| `BitmaskFill` | args: `array`, `mask`; attrs: `fill_value`, `offset`, `count` |
| `MaskFill` | args: `array`, `fill`; attrs: `size`, `lo`, `hi` |
| `RegArrayCast` | args: `src`, `dst`; attrs: `src_dtype`, `dst_dtype`, `count`, `offset` |

## Bucket 5: Barriers, Fences, Sync, Reductions

All nodes inherit `weave.Op(std.Stmt)`.

| Class / mnemonic | Fields |
| --- | --- |
| `BarrierSync` | attrs: `barrier_id` |
| `BarrierTryWait` | args: `barrier`, `stage`, `phase`; var_def: `dst`; attrs: `stage_is_deterministic` |
| `BarrierWait` | args: `barrier`, `stage`, `phase`; attrs: `token`, `stage_is_deterministic` |
| `BarrierSignal` | args: `barrier`, `action`, `stage`; attrs: `tx_bytes`, `arrive_count`, `cta_group`, `cluster`, `stage_is_deterministic`, `elected`, `transaction_group` |
| `MBarrierArrive` | args: `addr` |
| `PeerArriveCommit` | args: `barrier`, `stage`; attrs: `cta_group`, `elected` |
| `MulticastCommit` | args: `barrier`, `stage`, `multicast_mask`; attrs: `cta_group`, `elected` |
| `DualCommit` | args: `barrier_0`, `barrier_1`, `stage_0`, `stage_1`; attrs: `cta_group`, `elected` |
| `Fence` | attrs: `kind` |
| `ThreadFence` | attrs: `scope` |
| `ClusterSync`, `GridSync`, `GridDepSync`, `GridDepLaunch` | no fields |
| `ClusterMapa` | args: `src_addr`, `peer_rank`; var_def: `dst` |
| `ClusterBarrierArrive` | args: `barrier`; attrs: `tx_count`, `peer_rank` |
| `CpAsyncBulkSmem2SmemCluster` | args: `dst_addr`, `src_addr`, `bytes`; attrs: `barrier`, `mbar_addr` |
| `WarpReduce` | args: `val`; attrs: `op`, optional var_def `dst` |
| `BlockReduce` | args: `val`, `smem`; attrs: `op` |
| `CrossWarpReduce` | args: `src`, `smem`; var_def: `dst`; attrs: `op`, `finalize` |
| `WarpGroupReduce` | args: `src`, `smem`; var_def: `dst`; attrs: `op`, `num_warp_groups` |
| `StAsync` | args: `dst_addr`, `srcs`; attrs: `bytes`, `barrier`, `src_is_int` |

## Bucket 6: MMA, TMEM, Atomics, Multimem, CLC

All executable nodes inherit `weave.Op(std.Stmt)`.

| Class / mnemonic | Fields |
| --- | --- |
| `Tcgen05Cp` | args: `src`, `dst`; attrs: `shape`, `cta_group`, `sbo`, `elected` |
| `PackedF32x2` | args: `op`; attrs: `inputs`, `output` |
| `FragmentOp` | args: `op`, `dst`; attrs: `srcs`, `size`, `dtype` |
| `AtomicOp` | args: `op`, `src`, `dst`; attrs: `space`, `index`, `dtype` |
| `AtomicFetchAdd` | args: `dst`, `addr`, `val`; attrs: `index`, `dtype` |
| `RelaxedFmax` | args: `addr`, `val`; attrs: `space` |
| `AtomicMaxF32Positive` | args: `addr`, `val`; attrs: `index`, `dst` |
| `AtomicMaxFloatEncode`, `AtomicMaxFloatDecode` | args: `dst`, `src` |
| `SysVolatileLoad128` | args: `addr`, `dst` |
| `SysVolatileStore128` | args: `addr`, `src` |
| `MultimemLdReduce` | args: `addr`, `dst`; attrs: `payload` |
| `MultimemStore` | args: `addr`, `src`; attrs: `payload` |
| `MultimemRedAddI32` | args: `addr`, `value`; attrs: `sem`, `scope` |
| `ClcTryCancel` | args: `response_addr`, `mbar_addr`; attrs: `multicast` |
| `ClcQueryCancel` | args: `response_addr`, `dst` |
| `ClcQueryCancelGetCtaId` | args: `response_addr`, `dst`; attrs: `dim` |
| `ClcFenceRelease` | no fields |

`MmaTile` is included as the first explicit MMA tile operation. Additional TMA
descriptor replacement ops, cp.async family ops, named-barrier ops, WGMMA/MMA
sync ops, and late helper ops from the current Loom checkout remain follow-up
schema work.
