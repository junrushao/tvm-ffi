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
"""Minimal Tilus transform pass surface."""

from __future__ import annotations

from tilus.ir.func import Function


class FunctionPass:
    """Callable transform over one Tilus function."""

    name = "function_pass"

    def __call__(self, func: Function) -> Function:
        if not isinstance(func, Function):
            raise TypeError(f"{self.name} expects tilus.ir.Function, got {type(func).__name__}")
        return self.transform_function(func)

    def transform_function(self, func: Function) -> Function:
        """Transform a function."""
        raise NotImplementedError


__all__ = ["FunctionPass"]
