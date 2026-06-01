<!--- Licensed to the Apache Software Foundation (ASF) under one -->
<!--- or more contributor license agreements.  See the NOTICE file -->
<!--- distributed with this work for additional information -->
<!--- regarding copyright ownership.  The ASF licenses this file -->
<!--- to you under the Apache License, Version 2.0 (the -->
<!--- "License"); you may not use this file except in compliance -->
<!--- with the License.  You may obtain a copy of the License at -->

<!---   http://www.apache.org/licenses/LICENSE-2.0 -->

<!--- Unless required by applicable law or agreed to in writing, -->
<!--- software distributed under the License is distributed on an -->
<!--- "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY -->
<!--- KIND, either express or implied.  See the License for the -->
<!--- specific language governing permissions and limitations -->
<!--- under the License. -->

# Tilus

This addon provides the Tilus IR package implemented on top of TVM-FFI's `std`
dialect. Install it from this checkout after installing `apache-tvm-ffi`:
`python -m pip install -e addons/tilus`.

## IR Construction Notes

Tilus expression operands use `lang_kind="arg"` and should be `std.Expr`
instances or lists of `std.Expr` instances. Compile-time descriptors such as
layouts, tensor shapes, static dimensions, and scalar configuration values use
`lang_kind="attr"` instead.

`TensorItemValue` and `TensorItemPtr` define their binding variable directly:
construct them from a `std.Var` whose `ty` is the tensor type. `TensorItemPtr`
derives its `space` property from that tensor type (`SharedTensor`,
`GlobalTensor`, or `TMemoryTensor`) rather than storing a separate space field.
