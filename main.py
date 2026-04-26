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
# ruff: noqa: D100, D101, D102, D103, D106
from __future__ import annotations

import dataclasses as dc
from numbers import Number
from typing import Any, Callable

from tvm_ffi import dataclasses as tdc
from tvm_ffi import pyast, std
from tvm_ffi import tirx as _tirx  # noqa: F401
from tvm_ffi._pyast_parser import MISSING, Parser, Source


@tdc.py_class("T.AllocTensor")
class AllocTensor(std.SingleBinding):
    shape: list[std.Expr]
    dtype: str

    def __ffi_text_print__(self, printer: pyast.IRPrinter, path: Any) -> pyast.Assign:
        lhs = printer.var_def(self.value.name, self.value, None)
        annotation = printer(self.value.ty, path.attr("value").attr("ty"))
        shape = pyast.List(
            [printer(dim, path.attr("shape").array_item(i)) for i, dim in enumerate(self.shape)]
        )
        dtype = printer(self.dtype, path.attr("dtype"))
        rhs = pyast.Call(pyast.Attr(pyast.Id("T"), "alloc_tensor"), [shape, dtype], [], [])
        return pyast.Assign(lhs, rhs, annotation)


@dc.dataclass
class FuncFrame:
    # TODO: mnemonic???
    symbol: str
    attrs: dict[str, Any]
    ret_type: std.Ty
    args: list[std.Value]
    body: list[std.Stmt]

    def __init__(self, symbol: str, attrs: dict[str, Any]) -> None:
        self.symbol = symbol
        self.attrs = attrs

    def to_dialect(self) -> std.Func:
        return std.Func(
            symbol=self.symbol,
            args=self.args,
            ret_type=self.ret_type,
            attrs=std.DictAttrs(self.attrs),
            body=self.body,
        )


class ForFrame:
    range_: std.Range
    value: std.Value
    attrs: std.Attrs
    body: list[std.Stmt]

    def __init__(
        self,
        range_: std.Range,
        value: std.Value,
        attrs: std.Attrs,
    ) -> None:
        self.range_ = range_
        self.value = value
        self.attrs = attrs

    def to_dialect(self) -> std.For:
        return std.For(
            range_=self.range_,
            values=[self.value],
            attrs=std.Attrs(),
            body=self.body,
            carry_inits=[],
        )


@dc.dataclass
class IFThenElseFrame:
    cond: std.Expr
    then_body: list[std.Stmt]
    else_body: list[std.Stmt]


class T:
    class Expr:
        pass

    class Tensor:
        # TODO: add __getitem__ for buffer loading
        # TODO: add __setitem__ for buffer storing
        pass

    class f32(Expr):
        def __class_getitem__(cls, *shape: int) -> T.Tensor:
            return std.TensorTy(shape=shape, dtype="float32")

    class i32(Expr):
        def __class_getitem__(cls, *shape: int) -> T.Tensor:
            return std.TensorTy(shape=shape, dtype="int32")

    def prim_func(**kwargs: Any) -> Callable[..., Any]:
        def decorator(func: Any) -> Any:
            return func

        decorator.__ffi_parse__ = FuncFrame(
            symbol="",
            attrs=kwargs,
        )
        return decorator

    def range(
        start: int,
        stop: std.Expr | int | object = MISSING,
        step: std.Expr | int = 1,
        /,
    ) -> ForFrame:
        if MISSING.is_(stop):
            start, stop = 0, start
        if isinstance(start, int):
            start = std.IntImm(std.AnyTy(), start)
        if isinstance(stop, int):
            stop = std.IntImm(std.AnyTy(), stop)
        if isinstance(step, int):
            if step == 1:
                step = None
            else:
                step = std.IntImm(std.AnyTy(), step)

        return ForFrame(
            range_=std.Range(start=start, stop=stop, step=step),
            value=std.Value(name="_", ty=std.PrimTy(dtype="int32")),
            attrs=std.Attrs(),
        )

    def alloc_tensor(shape: tuple[int, ...], dtype: str) -> T.Tensor:
        ty = std.TensorTy(shape=shape, dtype=dtype)
        return AllocTensor(
            shape=shape,
            dtype=dtype,
            value=std.Value(ty, "_"),
            expr=None,
        )

    def Cast(dtype: str, value: std.Expr) -> std.Expr:
        return std.Cast(std.PrimTy(dtype), value=value)


def _tensor_load(tensor: std.Value, *indices: std.Expr) -> std.Expr:
    return std.Load(
        value=tensor,
        indices=indices,
        ty=std.PrimTy(tensor.ty.dtype),
    )


def _tensor_store(tensor: std.Value, value: std.Expr | Number, *indices: std.Expr) -> std.Stmt:
    if isinstance(value, Number):
        value = std.Expr._make(value, ty=std.PrimTy(tensor.ty.dtype))
    assert value.ty.dtype == tensor.ty.dtype
    return std.Store(
        value=tensor,
        indices=indices,
        rhs=value,
    )


_MORE_GENERICS: dict[tuple[str, type[std.Ty]], Callable[..., Any]] = {
    ("__load__", std.TensorTy): _tensor_load,
    ("__store__", std.TensorTy): _tensor_store,
    ("__add__", std.PrimTy): std.Add._make,
    ("__sub__", std.PrimTy): std.Sub._make,
    ("__lt__", std.PrimTy): std.Lt._make,
    ("__mul__", std.PrimTy): std.Mul._make,
}


def main() -> None:
    parser = Parser(
        source=Source(
            program="""
@T.prim_func(private=True, my_attr="hello")
def main_func(p0: T.f32[30], p1: T.i32[1], hybrid_nms: T.f32[30]):
    argsort_nms_cpu = T.alloc_tensor((5,), "int32")
    for i in range(1):
        nkeep = T.alloc_tensor((1,), "int32")
        if 0 < p1[i]:
            nkeep[0] = p1[i]
            if 2 < nkeep[0]:
                nkeep[0] = 2
            for j in range(nkeep[0]):
                for k in range(6):
                    hybrid_nms[i * 30 + j * 6 + k] = p0[i * 30 + argsort_nms_cpu[i * 5 + j] * 6 + k]
                hybrid_nms[i * 5 + j] = T.Cast("float32", argsort_nms_cpu[i * 5 + j])
            if 2 < p1[i]:
                for j in T.range(p1[i] - nkeep[0]): # TODO: replace with T.parallel
                    for k in range(6):
                        hybrid_nms[i * 30 + j * 6 + nkeep[0] * 6 + k] = -1.0
                    hybrid_nms[i * 5 + j + nkeep[0]] = -1.0
""",
            feature_version=(3, 14),
        ),
        extra_vars={
            "T": T,
            "range": T.range,
        },
    )
    for key, handler in _MORE_GENERICS.items():
        parser.generics[key] = handler
    parser.dialect_stack.append("T")
    (func,) = parser.run()
    print(func)
    # print(pyast.to_python(func))


if __name__ == "__main__":
    main()
