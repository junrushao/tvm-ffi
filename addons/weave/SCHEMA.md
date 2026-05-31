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
- Use `arg` for dynamic operands and reserve `attr` for compile-time metadata,
  constants, and configuration records.
- Use `std.BaseFunc`, `std.BaseScope`, and `std.BaseFor` for body-bearing
  constructs. Generic body fields on plain `std.Node` / `std.Stmt` are not
  printable.
- Use custom collectors when a node needs vararg presentation or a shape-like
  list should be grouped differently from ordinary positional fields.

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
| `SmemSwizzleAddress` / `weave.SmemSwizzleAddress` | `std.Expr` | args: `expr`, `row_stride_bytes`, `coord_row`, `coord_col`; attrs: `swizzle`, `view`, `layout`, `coord_col_unit`, `tcgen05_tile_height`, `tcgen05_k_elements`, `addr_space`, `result_ty` |
| `TmemRef` / `weave.TmemRef` | `std.Expr` | args: `region`, `offset`; attrs: `result_ty` |
| `SmemRef` / `weave.SmemRef` | `std.Expr` | args: `buffer`, `offset`; attrs: `result_ty` |
| `SmemDescRef` / `weave.SmemDescRef` | `std.Expr` | args: `buffer`, `k_idx`; attrs: `mode`, `result_ty` |
| `BarrierRef` / `weave.BarrierRef` | `std.Expr` | args: `barrier`, `stage`; attrs: `result_ty` |
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
| `SmemView` / `weave.SmemView` | args: `name`, `pool`, `offset`, `shape`, `stride`; attrs: `dtype`, `stage`, `swizzle`, `layout`, `alias_of` |
| `PhaseVar` / `weave.PhaseVar` | args: `name`, `init_value`; attrs: `dtype`, `rotation_rule`, `rotation_trigger` |
| `PhaseDomain` / `weave.PhaseDomain` | args: `pipeline`, `stage_var`, `num_stages`; attrs: `phase_vars`, `owner_role`, `stage_ctype`, `stage_init` |
| `MmaParams` / `weave.MmaParams` | args: `k_steps_per_group`, `k_groups`, `group_lo_offset`; attrs: `cta_group`, `tile_m`, `tile_n`, `dtype` |
| `SoftmaxParams` / `weave.SoftmaxParams` | args: `tile_n`; attrs: `num_load_chunks`, `num_store_chunks` |
| `EpilogueParams` / `weave.EpilogueParams` | args: `head_dim`, `num_chunks_16`; attrs: `use_tma_store` |
| `TmaLoadParams` / `weave.TmaLoadParams` | args: `pipeline_name`; attrs: `num_stages`, `src_buffers`, `dst_buffers`, `full_barrier`, `empty_barrier`, `stage_var`, `phase_vars` |
| `TaskTiming`, `BarrierEdge`, `SmemAllocation`, `TmemAllocation` | attrs-only analysis artifacts |
| `NamedBarrierSpec`, `ProcessGroup`, `SymmetricMemory` | additional explicit handle-intent nodes for Loom surfaces not represented in `weave_ir.py`; `SymmetricMemory.shape` is an arg |

`Kernel` maps `WeaveIR` to `std.BaseFunc` with `symbol`, args, optional return
type, body scopes, and attrs for pipeline/warps/grid/tmem/epilogue/buffers/
mbarriers/smem pools/views/protocols/phase domains/params and analysis
artifacts; `constants` is an arg because it may carry expression constants.

## Bucket 3: Tasks and Control Flow

| Class / mnemonic | Parent | Fields |
| --- | --- | --- |
| `TaskSpec` / `weave.TaskSpec` | `std.BaseScope` | args: `name`, `kind`, `assigned_role`, `sync_before`, `sync_after`; attrs: `pipeline`, `inputs`, `outputs`, `depends_on`; body |
| `ForLoop` / `weave.ForLoop` | `std.BaseFor` | inherited `extent`, `var`, `start`, `step_expr`; attrs: `step`, `constexpr`, `unroll`, `ctype`; body |
| `Block` / `weave.Block` | `std.BaseScope` | body |
| `LeaderCtaBlock` / `weave.LeaderCtaBlock` | `std.BaseScope` | body |
| `ElectedThreadBlock` / `weave.ElectedThreadBlock` | `std.BaseScope` | body |
| `ConditionalIteration` / `weave.ConditionalIteration` | `std.BaseScope` | args: `iter_var`, `last_expr`; body as a canonicalized common body |
| `VarDecl` / `weave.VarDecl` | `std.BaseVarDef` | out: `var`; args: `ctype`, `init`, `array_size`; attrs: `uniform`, `zero_init` |
| `Assign` / `weave.Assign` | `std.Stmt` | args: `target`, `expr`; attrs: `op` |

`IfElse` and `Break` use `std.IfStmt` and `std.Break` directly as the canonical
form unless a future std patch adds subclass-aware if/break printers.

## Bucket 4: Memory and Elementwise Ops

All nodes inherit `weave.Op(std.Stmt)` and print as generic call statements.

| Class / mnemonic | Fields |
| --- | --- |
| `BuiltinVar` | args: `name`, `dst` |
| `TmemRegionLoad` | args: `region`, `dst`, `col_offset`, `row_base`; attrs: `num`, `dst_offset`, `wait` |
| `TmemRegionStore` | args: `region`, `src`, `col_offset`, `row_base`; attrs: `num`, `dtype` |
| `SmemDesc` | args: `buffer`, `k_idx`, `dst`, `step`, `offset`; attrs: `mode` |
| `GmemLoad` | args: `src`, `dst`, `dst_offset`, `index`; attrs: `count`, `dtype`, `dst_dtype` |
| `GmemStore` | args: `src`, `dst`, `src_offset`, `index`, `scale`; attrs: `count`, `dtype`, `src_dtype`, `cache_hint` |
| `SmemStore` | args: `src`, `dst`, `predicate`, `index` |
| `SmemLoad` | args: `src`, `dst` |
| `SmemRead` | args: `src`, `dst`, `index` |
| `SmemLoadRegs` | args: `name`, `src_expr`; attrs: `count`, `dtype` |
| `SmemWrite` | args: `src`, `dst`, `index` |
| `SmemLoadVec` | args: `dst`, `src_addr`, `dst_offset`; attrs: `count` |
| `SmemStoreVec` | args: `dst_addr`, `src` |
| `TmaStore` | args: `src`, `dst` |
| `TmaReduceOp` | args: `src`, `dst`; attrs: `op` |
| `TmaGatherLoad` | args: `src`, `dst`, `page_table`, `mbar_expr`, `token_offset`; attrs: `tokens_per_page` |
| `ScaleFactorCopy` | args: `src`, `dst`; attrs: `cta_group`, `sbo`, `elected` |
| `MetadataCopy` | args: `src`, `dst`; attrs: `cta_group` |
| `Elementwise` | args: `inputs`, `output`; attrs: `op` |
| `PredicatedStore` | args: `dst`, `src`, `bound_m`, `bound_n`, `tile_offset_m`, `tile_offset_n` |
| `ThreshMask` | args: `dst`, `limit`; attrs: `width` |
| `BitmaskFill` | args: `array`, `mask`, `fill_value`, `offset`; attrs: `count` |
| `MaskFill` | args: `array`, `fill`, `lo`, `hi`; attrs: `size` |
| `RegArrayCast` | args: `src`, `dst`, `offset`; attrs: `src_dtype`, `dst_dtype`, `count` |

## Bucket 5: Barriers, Fences, Sync, Reductions

All nodes inherit `weave.Op(std.Stmt)`.

| Class / mnemonic | Fields |
| --- | --- |
| `BarrierSync` | attrs: `barrier_id` |
| `BarrierTryWait` | args: `barrier`, `stage`, `phase`; out: `dst`; attrs: `stage_is_deterministic` |
| `BarrierWait` | args: `barrier`, `stage`, `phase`, `token`; attrs: `stage_is_deterministic` |
| `BarrierSignal` | args: `barrier`, `action`, `stage`, `tx_bytes`, `arrive_count`; attrs: `cta_group`, `cluster`, `stage_is_deterministic`, `elected`, `transaction_group` |
| `MBarrierArrive` | args: `addr` |
| `PeerArriveCommit` | args: `barrier`, `stage`; attrs: `cta_group`, `elected` |
| `MulticastCommit` | args: `barrier`, `stage`, `multicast_mask`; attrs: `cta_group`, `elected` |
| `DualCommit` | args: `barrier_0`, `barrier_1`, `stage_0`, `stage_1`; attrs: `cta_group`, `elected` |
| `Fence` | attrs: `kind` |
| `ThreadFence` | attrs: `scope` |
| `ClusterSync`, `GridSync`, `GridDepSync`, `GridDepLaunch` | no fields |
| `ClusterMapa` | args: `src_addr`, `peer_rank`; out: `dst` |
| `ClusterBarrierArrive` | args: `barrier`, `tx_count`, `peer_rank` |
| `CpAsyncBulkSmem2SmemCluster` | args: `dst_addr`, `src_addr`, `bytes`, `barrier`, `mbar_addr` |
| `WarpReduce` | args: `val`; attrs: `op`, optional out `dst` |
| `BlockReduce` | args: `val`, `smem`; attrs: `op` |
| `CrossWarpReduce` | args: `src`, `smem`; out: `dst`; attrs: `op`, `finalize` |
| `WarpGroupReduce` | args: `src`, `smem`; out: `dst`; attrs: `op`, `num_warp_groups` |
| `StAsync` | args: `dst_addr`, `srcs`, `barrier`; attrs: `bytes`, `src_is_int` |

## Bucket 6: MMA, TMEM, Atomics, Multimem, CLC

All executable nodes inherit `weave.Op(std.Stmt)`.

| Class / mnemonic | Fields |
| --- | --- |
| `Tcgen05Cp` | args: `src`, `dst`; attrs: `shape`, `cta_group`, `sbo`, `elected` |
| `PackedF32x2` | args: `op`, `inputs`, `output` |
| `FragmentOp` | args: `op`, `dst`, `srcs`; attrs: `size`, `dtype` |
| `MmaTile` | args: `a_desc`, `b_desc`, `d_tmem`, `k_idx`; attrs: `mode`, `cta_group`, `a_dtype`, `b_dtype`, `acc_dtype` |
| `AtomicOp` | args: `op`, `src`, `dst`, `index`; attrs: `space`, `dtype` |
| `AtomicFetchAdd` | args: `dst`, `addr`, `val`, `index`; attrs: `dtype` |
| `RelaxedFmax` | args: `addr`, `val`; attrs: `space` |
| `AtomicMaxF32Positive` | args: `addr`, `val`, `index`, `dst` |
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
