# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Edge tests for Tilus transform functors."""

from __future__ import annotations

import pytest
import tilus  # noqa: F401  # Registers the Tilus dialect.
from tilus.ir.func import Function
from tilus.ir.functors import DELETE_STMT, IRRewriter, StmtSplice
from tilus.ir.inst import Instruction
from tilus.ir.instructions.cuda import (
    ClusterSyncThreadsInst,
    CopyAsyncCommitGroupInst,
    CopyAsyncWaitAllInst,
    FenceProxyAsyncRelease,
    Tcgen05StoreInst,
)
from tilus.ir.instructions.generic import (
    AddInst,
    CastInst,
    DivInst,
    LoadGlobalInst,
    LoadSharedInst,
    MulInst,
    NopInst,
    ReduceInst,
    StoreGlobalInst,
    StoreSharedInst,
    SubInst,
    SyncThreadsInst,
)
from tilus.ir.stmt import Evaluate, TensorItemValue, ThreadGroup
from tilus.ir.tensor import register_tensor
from tilus.transforms import (
    DeadCodeElimination,
    FunctionPass,
    dead_code_elimination,
    is_pure_instruction,
)
from tvm_ffi import dataclasses as dc
from tvm_ffi import std, structural_equal
from tvm_ffi.container import Array


@dc.py_class("test.tilus.DCEEdgeBindExpr", structural_eq="tree")
class DCEEdgeBindExpr(std.BaseBindExpr, mnemonic="test_tilus.DCEEdgeBindExpr"):
    target: std.Var = dc.field(lang_kind="out")

    def __ffi_update_var_name__(self, *name: str) -> tuple[std.Var, ...]:
        if len(name) != 1:
            raise TypeError(f"expected 1 binding target(s), got {len(name)}")
        self.target.name = name[0]
        return (self.target,)


@dc.py_class("test.tilus.DCEEdgeWhile", structural_eq="tree")
class DCEEdgeWhile(std.BaseWhile, mnemonic="test_tilus.DCEEdgeWhile"):
    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")


@dc.py_class("test.tilus.DCEEdgeFor", structural_eq="tree")
class DCEEdgeFor(std.BaseFor, mnemonic="test_tilus.DCEEdgeFor"):
    body: list[std.Stmt] = dc.field(default_factory=list, lang_kind="body")


@dc.py_class("test.tilus.DCEEdgeFunction", structural_eq="tree")
class DCEEdgeFunction(Function, mnemonic="test_tilus.DCEEdgeFunction"):
    tag: str = dc.field(default="edge", lang_kind="attr")


def _reg_var(name: str) -> std.Var:
    return std.Var(register_tensor("float32", (2, 2)), name)


def _bool_var(name: str) -> std.Var:
    return std.Var(std.PrimTy("bool"), name)


def _int_var(name: str) -> std.Var:
    return std.Var(std.PrimTy("int32"), name)


def _stmt_labels(body: list[std.Stmt]) -> list[str]:
    labels = []
    for stmt in body:
        if isinstance(stmt, Instruction) and (output := getattr(stmt, "output", None)) is not None:
            labels.append(output.name)
        else:
            labels.append(type(stmt).__name__)
    return labels


def test_dce_instruction_purity_classification_breadth() -> None:
    x = _reg_var("x")

    pure_insts = [
        AddInst(x, x, output=_reg_var("add")),
        CastInst(x, output=_reg_var("cast")),
        DivInst(x, x, output=_reg_var("div")),
        LoadGlobalInst(x, output=_reg_var("load_global")),
        LoadSharedInst(x, output=_reg_var("load_shared")),
        MulInst(x, x, output=_reg_var("mul")),
        NopInst(),
        ReduceInst(x, output=_reg_var("reduce")),
        SubInst(x, x, output=_reg_var("sub")),
    ]
    effectful_insts = [
        StoreGlobalInst(x, x),
        StoreSharedInst(x, x),
        SyncThreadsInst(),
        ClusterSyncThreadsInst(),
        CopyAsyncCommitGroupInst(),
        CopyAsyncWaitAllInst(),
        FenceProxyAsyncRelease(),
        Tcgen05StoreInst(),
    ]

    assert [type(inst).__name__ for inst in pure_insts if not is_pure_instruction(inst)] == []
    assert [type(inst).__name__ for inst in effectful_insts if is_pure_instruction(inst)] == []


def test_dce_rewrites_if_branch_bodies_independently() -> None:
    x = _reg_var("x")
    then_live = _reg_var("then_live")
    branch = std.IfStmt(
        True,
        [
            AddInst(x, x, output=_reg_var("then_dead")),
            AddInst(x, x, output=then_live),
            std.Return(then_live),
        ],
        [
            AddInst(x, x, output=_reg_var("else_dead")),
            StoreGlobalInst(x, x),
        ],
    )
    func = Function(symbol="kernel", args=[x], ret_type=None, body=[branch], metadata=None)

    rewritten = dead_code_elimination(func)

    assert isinstance(rewritten.body[0], std.IfStmt)
    assert _stmt_labels(list(rewritten.body[0].then_body)) == ["then_live", "Return"]
    assert _stmt_labels(list(rewritten.body[0].else_body)) == ["StoreGlobalInst"]


def test_dce_preserves_side_effects_and_drops_pure_no_output_instructions() -> None:
    x = _reg_var("x")
    func = Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[
            NopInst(),
            SyncThreadsInst(),
            StoreGlobalInst(x, x),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == [
        "SyncThreadsInst",
        "StoreGlobalInst",
    ]


def test_dce_keeps_if_branch_defs_used_after_region() -> None:
    x = _reg_var("x")
    then_live = _reg_var("then_live")
    else_live = _reg_var("else_live")
    branch = std.IfStmt(
        True,
        [AddInst(x, x, output=then_live)],
        [AddInst(x, x, output=else_live)],
    )
    func = Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[branch, StoreGlobalInst(then_live, else_live)],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert isinstance(rewritten.body[0], std.IfStmt)
    assert _stmt_labels(list(rewritten.body[0].then_body)) == ["then_live"]
    assert _stmt_labels(list(rewritten.body[0].else_body)) == ["else_live"]


def test_dce_keeps_if_condition_producer() -> None:
    x = _reg_var("x")
    i0 = _int_var("i0")
    cond_live = _bool_var("cond_live")
    func = Function(
        symbol="kernel",
        args=[x, i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=_bool_var("dead")),
            AddInst(i0, i0, output=cond_live),
            std.IfStmt(cond_live, [StoreGlobalInst(x, x)], []),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["cond_live", "IfStmt"]


def test_dce_keeps_thread_group_defs_used_after_region() -> None:
    x = _reg_var("x")
    group_live = _reg_var("group_live")
    group = ThreadGroup(0, 32, [AddInst(x, x, output=group_live)])
    func = Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[group, StoreGlobalInst(group_live, x)],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert isinstance(rewritten.body[0], ThreadGroup)
    assert _stmt_labels(list(rewritten.body[0].body)) == ["group_live"]


def test_dce_keeps_defs_used_only_by_scope_binds() -> None:
    x = _reg_var("x")
    scope_live = _reg_var("scope_live")
    bound = _reg_var("bound")
    scope = std.Scope([std.BindExpr(scope_live, bound)], [std.Return(bound)])
    func = Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[
            AddInst(x, x, output=_reg_var("dead")),
            AddInst(x, x, output=scope_live),
            scope,
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["scope_live", "Scope"]


def test_dce_keeps_defs_used_by_direct_bind_expr() -> None:
    x = _reg_var("x")
    source = _reg_var("source")
    bound = _reg_var("bound")
    func = Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[
            AddInst(x, x, output=_reg_var("dead")),
            AddInst(x, x, output=source),
            std.BindExpr(source, bound),
            std.Return(bound),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["source", "BindExpr", "Return"]


def test_dce_handles_live_and_dead_instructions() -> None:
    x = _reg_var("x")
    live = _reg_var("live")
    func = Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[
            AddInst(x, x, output=_reg_var("dead")),
            AddInst(x, x, output=live),
            std.Return(live),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["live", "Return"]


def test_dce_distinguishes_same_name_different_handles() -> None:
    x = _reg_var("x")
    live = _reg_var("same")
    dead_same_name = _reg_var("same")
    assert live.name == dead_same_name.name
    assert not live.same_as(dead_same_name)
    func = Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[
            AddInst(x, x, output=live),
            AddInst(x, x, output=dead_same_name),
            std.Return(live),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["same", "Return"]
    assert isinstance(rewritten.body[0], AddInst)
    assert rewritten.body[0].output.same_as(live)


def test_dce_matches_same_handle_var_wrappers() -> None:
    x = _reg_var("x")
    live = _reg_var("live")
    live_wrapper = Array([live])[0]
    assert live_wrapper is not live
    assert live_wrapper.same_as(live)
    func = Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[
            AddInst(x, x, output=live),
            std.Return(live_wrapper),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["live", "Return"]


def test_dce_keeps_defs_used_only_by_attrs_and_pred() -> None:
    x = _reg_var("x")
    i0 = _int_var("i0")
    attr_live = _int_var("attr_live")
    pred_live = _bool_var("pred_live")
    func = Function(
        symbol="kernel",
        args=[x, i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=_int_var("dead")),
            AddInst(i0, i0, output=attr_live),
            StoreGlobalInst(x, x, offsets=[attr_live], dims=[0]),
            AddInst(i0, i0, output=pred_live),
            Evaluate(std.IntImm(std.PrimTy("int32"), 0), pred=pred_live),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == [
        "attr_live",
        "StoreGlobalInst",
        "pred_live",
        "Evaluate",
    ]


def test_dce_keeps_defs_used_only_by_loop_bounds() -> None:
    x = _reg_var("x")
    i0 = _int_var("i0")
    start_live = _int_var("start_live")
    extent_live = _int_var("extent_live")
    step_live = _int_var("step_live")
    loop_var = _int_var("i")
    func = Function(
        symbol="kernel",
        args=[x, i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=_int_var("dead")),
            AddInst(i0, i0, output=start_live),
            AddInst(i0, i0, output=extent_live),
            AddInst(i0, i0, output=step_live),
            std.For(
                start_live,
                extent_live,
                loop_var,
                [StoreGlobalInst(x, x)],
                step=step_live,
            ),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == [
        "start_live",
        "extent_live",
        "step_live",
        "For",
    ]


def test_dce_custom_base_for_extent_is_live_and_loop_var_kills_old_def() -> None:
    x = _reg_var("x")
    i0 = _int_var("i0")
    extent_live = _int_var("extent_live")
    loop_var = _int_var("i")
    func = Function(
        symbol="kernel",
        args=[x, i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=loop_var),
            AddInst(i0, i0, output=extent_live),
            DCEEdgeFor(
                extent=extent_live,
                var=loop_var,
                body=[StoreGlobalInst(x, x, offsets=[loop_var], dims=[0])],
            ),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["extent_live", "DCEEdgeFor"]
    assert isinstance(rewritten.body[1], DCEEdgeFor)


def test_dce_custom_base_for_rewrites_body_with_outer_live_out() -> None:
    x = _reg_var("x")
    i0 = _int_var("i0")
    extent_live = _int_var("extent_live")
    loop_var = _int_var("i")
    body_live = _reg_var("body_live")
    func = Function(
        symbol="kernel",
        args=[x, i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=loop_var),
            AddInst(i0, i0, output=extent_live),
            DCEEdgeFor(
                extent=extent_live,
                var=loop_var,
                body=[
                    AddInst(x, x, output=_reg_var("body_dead")),
                    AddInst(x, x, output=body_live),
                ],
            ),
            StoreGlobalInst(x, body_live),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == [
        "extent_live",
        "DCEEdgeFor",
        "StoreGlobalInst",
    ]
    assert isinstance(rewritten.body[1], DCEEdgeFor)
    assert _stmt_labels(list(rewritten.body[1].body)) == ["body_live"]


def test_dce_std_for_loop_var_def_kills_pre_loop_producer() -> None:
    x = _reg_var("x")
    i0 = _int_var("i0")
    loop_var = _int_var("i")
    func = Function(
        symbol="kernel",
        args=[x, i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=loop_var),
            std.For(0, 2, loop_var, [StoreGlobalInst(x, x, offsets=[loop_var], dims=[0])]),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["For"]
    assert isinstance(rewritten.body[0], std.For)
    assert _stmt_labels(list(rewritten.body[0].body)) == ["StoreGlobalInst"]


def test_dce_keeps_defs_used_only_by_while_condition() -> None:
    x = _reg_var("x")
    i0 = _int_var("i0")
    cond_live = _bool_var("cond_live")
    func = Function(
        symbol="kernel",
        args=[x, i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=_bool_var("dead")),
            AddInst(i0, i0, output=cond_live),
            std.While(cond_live, [StoreGlobalInst(x, x)]),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["cond_live", "While"]


def test_dce_keeps_while_body_redefinition_of_condition() -> None:
    i0 = _int_var("i0")
    cond = _bool_var("cond_live")
    func = Function(
        symbol="kernel",
        args=[i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=cond),
            std.While(
                cond,
                [
                    AddInst(i0, i0, output=_bool_var("body_dead")),
                    AddInst(i0, i0, output=cond),
                ],
            ),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["cond_live", "While"]
    assert isinstance(rewritten.body[1], std.While)
    assert _stmt_labels(list(rewritten.body[1].body)) == ["cond_live"]


def test_dce_custom_base_while_keeps_body_redefinition_of_condition() -> None:
    i0 = _int_var("i0")
    cond = _bool_var("cond_live")
    func = Function(
        symbol="kernel",
        args=[i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=cond),
            DCEEdgeWhile(
                cond=cond,
                body=[
                    AddInst(i0, i0, output=_bool_var("body_dead")),
                    AddInst(i0, i0, output=cond),
                ],
            ),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["cond_live", "DCEEdgeWhile"]
    assert isinstance(rewritten.body[1], DCEEdgeWhile)
    assert _stmt_labels(list(rewritten.body[1].body)) == ["cond_live"]


def test_dce_keeps_while_condition_update_with_effectful_body() -> None:
    x = _reg_var("x")
    i0 = _int_var("i0")
    cond = _bool_var("cond_live")
    func = Function(
        symbol="kernel",
        args=[x, i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=cond),
            std.While(
                cond,
                [
                    StoreGlobalInst(x, x),
                    AddInst(i0, i0, output=cond),
                ],
            ),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["cond_live", "While"]
    assert isinstance(rewritten.body[1], std.While)
    assert _stmt_labels(list(rewritten.body[1].body)) == ["StoreGlobalInst", "cond_live"]


def test_dce_keeps_while_loop_carried_value_used_before_redefinition() -> None:
    x = _reg_var("x")
    i0 = _int_var("i0")
    cond = _bool_var("cond_live")
    value = _reg_var("loop_live")
    func = Function(
        symbol="kernel",
        args=[x, i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=cond),
            AddInst(x, x, output=value),
            std.While(
                cond,
                [
                    StoreGlobalInst(value, x),
                    AddInst(x, x, output=value),
                ],
            ),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["cond_live", "loop_live", "While"]
    assert isinstance(rewritten.body[2], std.While)
    assert _stmt_labels(list(rewritten.body[2].body)) == ["StoreGlobalInst", "loop_live"]


def test_dce_keeps_custom_base_bind_expr_rhs_producer() -> None:
    i0 = _int_var("i0")
    old_target = _int_var("target")
    rhs_live = _int_var("rhs_live")
    func = Function(
        symbol="kernel",
        args=[i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=old_target),
            AddInst(i0, i0, output=_int_var("dead")),
            AddInst(i0, i0, output=rhs_live),
            DCEEdgeBindExpr(expr=rhs_live, target=old_target),
            std.Return(old_target),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["rhs_live", "DCEEdgeBindExpr", "Return"]
    assert isinstance(rewritten.body[1], DCEEdgeBindExpr)


def test_dce_scope_tensor_item_value_bind_shadows_outer_producer() -> None:
    tensor = register_tensor("float32", (2, 2))
    value = std.Var(tensor, "value")
    func = Function(
        symbol="kernel",
        args=[],
        ret_type=None,
        body=[
            AddInst(value, value, output=value),
            std.Scope([TensorItemValue(value)], [std.Return(value)]),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["Scope"]
    assert isinstance(rewritten.body[0], std.Scope)
    assert isinstance(rewritten.body[0].binds[0], TensorItemValue)


def test_dce_keeps_custom_base_while_condition_producer() -> None:
    x = _reg_var("x")
    i0 = _int_var("i0")
    cond_live = _bool_var("cond_live")
    func = Function(
        symbol="kernel",
        args=[x, i0],
        ret_type=None,
        body=[
            AddInst(i0, i0, output=_bool_var("dead")),
            AddInst(i0, i0, output=cond_live),
            DCEEdgeWhile(cond=cond_live, body=[StoreGlobalInst(x, x)]),
        ],
        metadata=None,
    )

    rewritten = dead_code_elimination(func)

    assert _stmt_labels(list(rewritten.body)) == ["cond_live", "DCEEdgeWhile"]
    assert isinstance(rewritten.body[1], DCEEdgeWhile)


def test_dead_code_elimination_pass_accepts_function_subclass() -> None:
    x = _reg_var("x")
    live = _reg_var("live")
    func = DCEEdgeFunction(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[
            AddInst(x, x, output=_reg_var("dead")),
            AddInst(x, x, output=live),
            std.Return(live),
        ],
        metadata=None,
        tag="custom",
    )

    rewritten = DeadCodeElimination()(func)

    assert isinstance(rewritten, DCEEdgeFunction)
    assert rewritten.tag == "custom"
    assert _stmt_labels(list(rewritten.body)) == ["live", "Return"]


def test_function_pass_call_validates_type_and_allows_structural_result() -> None:
    x = _reg_var("x")
    func = Function(symbol="kernel", args=[x], ret_type=None, body=[std.Return(x)], metadata=None)

    class ClonePass(FunctionPass):
        name = "clone_pass"

        def transform_function(self, func: Function) -> Function:
            return Function(
                symbol=func.symbol,
                args=list(func.args),
                ret_type=func.ret_type,
                body=list(func.body),
                metadata=func.metadata,
            )

    transform = ClonePass()
    with pytest.raises(TypeError, match=r"clone_pass expects tilus\.ir\.Function, got Return"):
        transform(std.Return(x))

    rewritten = transform(func)

    assert rewritten is not func
    assert structural_equal(rewritten, func)


def test_rewriters_preserve_identity_for_unchanged_nested_bodies() -> None:
    x = _reg_var("x")
    group = ThreadGroup(0, 32, [StoreGlobalInst(x, x)])
    func = Function(symbol="kernel", args=[x], ret_type=None, body=[group], metadata=None)

    assert IRRewriter()(func) is func
    assert dead_code_elimination(func) is func


def test_dce_preserves_identity_for_unchanged_nested_live_out_body() -> None:
    x = _reg_var("x")
    live = _reg_var("live")
    group = ThreadGroup(0, 32, [AddInst(x, x, output=live)])
    func = Function(
        symbol="kernel",
        args=[x],
        ret_type=None,
        body=[group, StoreGlobalInst(live, x)],
        metadata=None,
    )

    assert dead_code_elimination(func) is func


@pytest.mark.parametrize("stmt_kind", ["if", "for", "while", "scope", "thread_group"])
def test_ir_rewriter_supports_delete_and_splice_in_nested_body_fields(stmt_kind: str) -> None:
    x = _reg_var("x")

    def make_body(prefix: str) -> list[std.Stmt]:
        return [
            AddInst(x, x, output=_reg_var(f"{prefix}_drop")),
            AddInst(x, x, output=_reg_var(f"{prefix}_keep")),
        ]

    if stmt_kind == "if":
        stmt = std.IfStmt(True, make_body("then"), make_body("else"))
        body_getters = (lambda node: node.then_body, lambda node: node.else_body)
        expected = (["then_keep", "NopInst"], ["else_keep", "NopInst"])
    elif stmt_kind == "for":
        stmt = std.For(0, 2, _int_var("i"), make_body("for"))
        body_getters = (lambda node: node.body,)
        expected = (["for_keep", "NopInst"],)
    elif stmt_kind == "while":
        stmt = std.While(_bool_var("cond"), make_body("while"))
        body_getters = (lambda node: node.body,)
        expected = (["while_keep", "NopInst"],)
    elif stmt_kind == "scope":
        stmt = std.Scope([], make_body("scope"))
        body_getters = (lambda node: node.body,)
        expected = (["scope_keep", "NopInst"],)
    else:
        stmt = ThreadGroup(0, 32, make_body("group"))
        body_getters = (lambda node: node.body,)
        expected = (["group_keep", "NopInst"],)

    class BodyRewrite(IRRewriter):
        def visit_AddInst(self, node: AddInst) -> object:
            assert node.output is not None
            if node.output.name.endswith("_drop"):
                return DELETE_STMT
            return StmtSplice([node, NopInst()])

    rewritten = BodyRewrite()(stmt)

    assert tuple(_stmt_labels(list(get_body(rewritten))) for get_body in body_getters) == expected


@pytest.mark.parametrize(
    "replacement",
    [DELETE_STMT, StmtSplice([std.Return(_int_var("replacement"))])],
)
def test_ir_rewriter_rejects_delete_or_splice_outside_statement_bodies(
    replacement: object,
) -> None:
    x = _reg_var("x")

    class RewriteArg(IRRewriter):
        def visit_Var(self, node: std.Var) -> object:
            if node.name == "x":
                return replacement
            return node

    func = Function(symbol="kernel", args=[x], ret_type=None, body=[], metadata=None)

    with pytest.raises(ValueError, match="only valid in statement bodies"):
        RewriteArg()(func)


def test_ir_rewriter_rejects_non_statement_body_rewrite() -> None:
    x = _reg_var("x")

    class ReturnExprFromStatement(IRRewriter):
        def visit_Return(self, node: std.Return) -> std.Var:
            return x

    func = Function(symbol="kernel", args=[x], ret_type=None, body=[std.Return(x)], metadata=None)

    with pytest.raises(TypeError, match="statement rewriter returned Var"):
        ReturnExprFromStatement()(func)
