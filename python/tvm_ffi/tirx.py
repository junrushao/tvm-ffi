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

# ruff: noqa: D100, D101
from __future__ import annotations

from typing import Any

from tvm_ffi import dataclasses as dc

from . import std


@dc.py_class("tirx.PointerTy")
class PointerTy(std.Ty):
    element_type: std.Ty
    storage_scope: str = ""


@dc.py_class("tirx.FuncType")
class FuncTy(std.Ty):
    arg_types: list[std.Ty]
    ret_type: std.Ty


@dc.py_class("tirx.GlobalVar")
class GlobalVar(std.Value):
    pass


@dc.py_class("tirx.Var")
class Var(std.Value):
    pass


@dc.py_class("tirx.SizeVar")
class SizeVar(Var):
    pass


@dc.py_class("tirx.Buffer")
class Buffer(std.Value):
    pass


class IterVarType:
    kDataPar = 0
    kThreadIndex = 1
    kCommReduce = 2
    kOrdered = 3
    kOpaque = 4
    kUnrolled = 5
    kVectorized = 6
    kParallelized = 7
    kTensorized = 8


@dc.py_class("tirx.IterVar")
class IterVar(std.Node):
    dom: std.Range
    var: Var
    iter_type: int  # IterVarType
    thread_tag: str


@dc.py_class("tirx.BufferTy")
class BufferTy(std.TensorTy):
    # dtype: DataType = None
    # shape: list[PrimExpr] = field(default_factory=list)
    data: Var
    strides: list[std.Expr]
    elem_offset: std.Expr
    axis_separators: list[std.IntImm]
    data_alignment: int = 0
    offset_factor: int = 0


@dc.py_class("tirx.Select")
class Select(std.Expr):
    condition: std.Expr
    true_value: std.Expr
    false_value: std.Expr


@dc.py_class("tirx.Ramp")
class Ramp(std.Expr):
    base: std.Expr
    stride: std.Expr
    lanes: int


@dc.py_class("tirx.Broadcast")
class Broadcast(std.Expr):
    value: std.Expr
    lanes: std.Expr


@dc.py_class("tirx.Shuffle")
class Shuffle(std.Expr):
    vectors: list[std.Expr]
    indices: list[std.Expr]


@dc.py_class("tirx.CommReducer")
class CommReducer(std.Node):
    lhs: list[Var]
    rhs: list[Var]
    result: list[std.Expr]
    identity_element: list[std.Expr]


@dc.py_class("tirx.Reduce")
class Reduce(std.Expr):
    combiner: CommReducer
    source: list[std.Expr]
    init: list[std.Expr]
    axis: list[IterVar]
    condition: std.Expr
    value_index: int = 0


@dc.py_class("tirx.AttrStmt")
class AttrStmt(std.Stmt):
    node: Any
    """
`AttrStmt.node` identifies **which IR object the attribute is about** — it's the *subject* of the annotation.
The other three fields say what to attach: `attr_key` (the kind of attribute), `value` (the attribute payload),
and `body` (the scope over which the attribute applies). The C++ field is `ffi::Any node`, so it's deliberately untyped —
different `attr_key`s expect different node types. For example:

| `attr_key`                                        | `node` is                                   | What it means                                                                            |
| ------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `tvm::attr::kTarget`                              | A `Target` object                           | "Compile this `body` for this target" — `annotate_device_regions.cc:48`                  |
| `attr::thread_extent`                             | An `IterVar` (thread iv)                    | "This thread's extent is `value`, used by device API" — `lower_opaque_block.cc:148`      |
| `attr::storage_alignment`                         | A buffer `Var` (data ptr)                   | "This buffer pointer is aligned to `value` bytes" — `tvm_ffi_binder.cc:792`              |
| `attr::device_id` / `device_type`                 | An opaque marker (e.g. `String("default")`) | "Set device context for `body`" — `make_packed_api.cc:259-260`                           |
| `attr::compute_scope`                             | `Integer(0)` placeholder                    | "Start a new compute function here" — `make_packed_api.cc:254`                           |
| `s_tir::attr::fragment_shape` / `fragment_layout` | Buffer `data` `Var`                         | "This fragment buffer has shape/layout `value`" — `tensorcore_infer_fragment.cc:189-191` |
| `s_tir::attr::double_buffer_write`                | A `Buffer`                                  | "Double-buffer this buffer" — `inject_double_buffer.cc:291`                              |
| reduction-related keys                            | A `CommReducer`                             | The reducer being annotated — `lower_cross_thread_reduction.cc:421`                      |

So `node` ranges over `Var`, `IterVar`, `Buffer`, `Target`, `CommReducer`, `String`, `Integer`, etc. depending on the key.
When the key doesn't logically need a subject (e.g. `compute_scope`, `device_scope`), an `Integer(0)` is used as a placeholder.
The header comment `// this is attribute about certain node` at `include/tvm/tirx/stmt.h:118` matches this —
`node` is the entity the attribute is *about*; the constructor at `src/tirx/ir/stmt.cc:121` just stores it verbatim.
    """
    attr_key: str
    value: std.Expr
    body: list[std.Stmt]


@dc.py_class("tirx.Assert")
class Assert(std.Stmt):
    condition: std.Expr
    error_kind: str
    message_parts: list[str]


@dc.py_class("tirx.DeclBuffer")
class DeclBuffer(std.SingleBinding):
    pass


@dc.py_class("tirx.AllocBuffer")
class AllocBuffer(std.SingleBinding):
    pass
