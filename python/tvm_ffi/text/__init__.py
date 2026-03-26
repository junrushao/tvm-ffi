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
"""Text printer module for pretty-printing IR as Python-style source.

This package provides an AST-based intermediate representation for rendering
TVM FFI objects as human-readable, Python-style source code. The main
components are:

* **AST nodes** (``ast`` submodule) -- a lightweight tree of ``Expr`` and
  ``Stmt`` nodes that mirror Python syntax constructs (identifiers, calls,
  assignments, function definitions, etc.).
* **IRPrinter** -- a stateful printer that converts arbitrary TVM FFI objects
  into AST nodes, tracks variable bindings, and manages scoping frames.
* **Helper factories** (``Int``, ``Float``, ``Str``, ``Bool``, ``None_``) --
  convenience constructors for ``Literal`` expression nodes.
* **Top-level utilities** (``to_python``, ``print_python``) -- one-shot
  functions that convert an object to its Python-style text representation.

Examples
--------
.. code-block:: python

    import tvm_ffi.text as text

    # Convert any TVM FFI object to Python-style source
    source = text.to_python(my_obj)

    # Or build AST nodes manually
    node = text.ast.Id(name="x")
    print(node.to_python())

"""

from __future__ import annotations

from . import ast
from .printer import (
    Bool,
    DefaultFrame,
    Float,
    Int,
    IRPrinter,
    None_,
    PrinterConfig,
    Str,
    print_python,
    to_python,
)
