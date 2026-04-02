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
"""Text format IR module for Python-style AST representation.

This package provides AST node definitions and utilities for representing
and rendering TVM FFI objects as Python-style source code.

* **ast** submodule -- expression and statement node types.
* **ast.from_py** -- convert Python source strings to TVM-FFI AST nodes.
* **IRPrinter** -- a stateful printer that converts arbitrary TVM FFI objects
  into AST nodes, tracks variable bindings, and manages scoping frames.
* **Helper factories** (``Int``, ``Float``, ``Str``, ``Bool``, ``None_``) --
  convenience constructors for ``Literal`` expression nodes.
* **Top-level utilities** (``to_python``, ``print_python``) -- one-shot
  functions that convert an object to its Python-style text representation.
"""

from __future__ import annotations

from . import ast
from .ast import PrinterConfig
from .printer import (
    Bool,
    DefaultFrame,
    Float,
    Int,
    IRPrinter,
    None_,
    Str,
    print_python,
    to_python,
)
