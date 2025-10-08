..  Licensed to the Apache Software Foundation (ASF) under one
    or more contributor license agreements.  See the NOTICE file
    distributed with this work for additional information
    regarding copyright ownership.  The ASF licenses this file
    to you under the Apache License, Version 2.0 (the
    "License"); you may not use this file except in compliance
    with the License.  You may obtain a copy of the License at

..    http://www.apache.org/licenses/LICENSE-2.0

..  Unless required by applicable law or agreed to in writing,
    software distributed under the License is distributed on an
    "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
    KIND, either express or implied.  See the License for the
    specific language governing permissions and limitations
    under the License.

Apache TVM FFI Documentation
============================

TVM FFI is a pybind-style bridge that allows convenient distribution and interoperation of ML system components,
across ABIs, languages and platforms, with ultra low overhead.

.. figure:: https://gist.githubusercontent.com/junrushao/66c2decdf145e74022135fedd9daa053/raw/b44967433e1f80a6ea9f6a3f4a03364d23c435d8/tvm-ffi-bridge.svg
   :alt: TVM FFI as a universal bridge across languages
   :align: center
   :name: fig-arch

   Figure 1. TVM FFI is a universal bridge across languages


Installation
------------

To install via pip, run:

.. code-block:: bash

   pip install apache-tvm-ffi


Documentation Structure
-----------------------

This documentation is structured as follows:

- **Quick Start.** Simple examples, e.g. exposing C++/CUDA code and interacting with PyTorch and numpy;
- **Guides.** Developer-facing, such as wrapping kernels as packages and integrating with ML compilers;
- **Core Designs.** Learn the core design, and how tvm-ffi works under the hood;
- **API Reference.** Complete detailed reference of all the c++ and python APIs.


Table of Contents
-----------------

.. toctree::
   :maxdepth: 1
   :caption: Quick Start

   get_started/01_ship_cpp_addone.rst
   get_started/03_package_as_a_wheel.rst

.. toctree::
   :maxdepth: 1
   :caption: Guides

   guides/packaging.md
   guides/compiler_integration.md

.. toctree::
   :maxdepth: 1
   :caption: Designs

   concepts/abi_overview.md
   guides/cpp_guide.md
   guides/python_guide.md

.. toctree::
   :maxdepth: 1
   :caption: Reference

   guides/build_from_source.md
   reference/python/index.rst
   reference/cpp/index.rst
