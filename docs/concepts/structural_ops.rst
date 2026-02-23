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

Structural Operations
=====================

TVM-FFI provides reflection-driven **structural equality**, **structural hashing**,
and **deep copy** for object graphs. These operations compare and copy objects
by their *content* rather than their identity, recursively traversing fields
registered through the reflection system.

Unlike earlier approaches that relied on virtual methods (``SEqualReduce`` /
``SHashReduce``), the current design is driven entirely by reflection metadata
(see :doc:`reflection`) recorded in :cpp:class:`TVMFFIFieldInfo`. Each registered field is visited automatically
during comparison, hashing, or copying, and types can opt in to custom behavior
through the :ref:`type-attr-column-mechanism` when the default field-by-field
traversal is insufficient.

The implementation lives in three header/source pairs:

- ``include/tvm/ffi/extra/structural_equal.h`` / ``src/ffi/extra/structural_equal.cc``
- ``include/tvm/ffi/extra/structural_hash.h`` / ``src/ffi/extra/structural_hash.cc``
- ``include/tvm/ffi/extra/deep_copy.h`` / ``src/ffi/extra/deep_copy.cc``

Structural Equality
-------------------

Overview
~~~~~~~~

:cpp:class:`tvm::ffi::StructuralEqual` compares two :cpp:class:`~tvm::ffi::Any`
values by recursively examining their content. The comparison dispatches on the
runtime type index stored in each value:

- **Primitives** (integers, floats, booleans, pointers, ``None``) are compared
  bitwise, with special handling for floating-point NaN values so that
  ``NaN == NaN`` holds.
- **Strings and bytes** are compared by content, correctly handling both
  small-string-optimized and heap-allocated representations.
- **Containers** (``Array``, ``List``, ``Map``, ``Dict``, ``Shape``) are
  compared element-wise or entry-wise.
- **Tensors** are compared by shape and dtype; data content comparison can be
  optionally skipped via the ``skip_tensor_content`` flag.
- **General objects** are compared field-by-field using registered
  :cpp:class:`TVMFFIFieldInfo` metadata.

C++ API
~~~~~~~

.. code-block:: cpp

   #include <tvm/ffi/extra/structural_equal.h>

   namespace ffi = tvm::ffi;

   ffi::Any a = ...;
   ffi::Any b = ...;

   // Simple equality check
   bool eq = ffi::StructuralEqual::Equal(a, b);

   // With options: map free variables, skip tensor content
   bool eq2 = ffi::StructuralEqual::Equal(a, b,
       /*map_free_vars=*/true,
       /*skip_tensor_content=*/true);

   // Functor form (map_free_vars=false, skip_tensor_content=true)
   ffi::StructuralEqual cmp;
   bool eq3 = cmp(a, b);

The ``map_free_vars`` parameter controls whether unbound variables (objects with
``_type_s_eq_hash_kind = kTVMFFISEqHashKindFreeVar``) can be mapped to each
other during comparison. When enabled, the comparator records a bidirectional
mapping between free variables encountered on the left-hand and right-hand sides
and enforces consistency across subsequent references.

Object Graph Handling
~~~~~~~~~~~~~~~~~~~~~

The ``TVMFFISEqHashKind`` enum, set via the ``_type_s_eq_hash_kind`` static
member on each object class, controls how the comparator treats object identity
versus content:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Kind
     - Behavior
   * - ``kTVMFFISEqHashKindUnsupported``
     - Structural equality is not supported; comparison throws ``TypeError``.
   * - ``kTVMFFISEqHashKindTreeNode``
     - Compare by content (field-by-field). Shared references are compared
       independently at each occurrence.
   * - ``kTVMFFISEqHashKindConstTreeNode``
     - Same as ``TreeNode``, but pointer equality implies content equality,
       enabling a fast-path short-circuit. No free variables appear as
       descendants.
   * - ``kTVMFFISEqHashKindDAGNode``
     - DAG-aware: the first time a pair ``(lhs, rhs)`` is compared
       successfully, the mapping is recorded. Subsequent encounters of the same
       ``lhs`` require it to map to the same ``rhs``.
   * - ``kTVMFFISEqHashKindFreeVar``
     - Free variable: when ``map_free_vars`` is enabled, the comparator binds
       unmatched free variables to each other and checks consistency.
   * - ``kTVMFFISEqHashKindUniqueInstance``
     - Singleton objects: compared by pointer identity only.

Custom Comparators
~~~~~~~~~~~~~~~~~~

Types can register a custom comparison function via the ``__s_equal__`` type
attribute (see :ref:`type-attr-column-mechanism`). When present, the custom
function is called instead of the default field-by-field traversal:

.. code-block:: cpp

   // Signature: (ObjectRef lhs, ObjectRef rhs, Function callback) -> bool
   // The callback has signature: (AnyView lhs, AnyView rhs, bool def_region, AnyView field_name) -> bool
   // Call the callback for each sub-component that needs comparison.

Structural Hashing
------------------

Overview
~~~~~~~~

:cpp:class:`tvm::ffi::StructuralHash` produces a ``uint64_t`` hash value for
any :cpp:class:`~tvm::ffi::Any` value, consistent with structural equality:
if ``StructuralEqual::Equal(a, b)`` returns ``true``, then
``StructuralHash::Hash(a) == StructuralHash::Hash(b)``.

The hash traversal mirrors the equality traversal: primitives are hashed from
their bit representation, strings and bytes from their content, containers
element-wise, and general objects field-by-field using reflection metadata.
All intermediate hash values are combined with a stable hash combiner
(``details::StableHashCombine``) to ensure deterministic results across runs.

C++ API
~~~~~~~

.. code-block:: cpp

   #include <tvm/ffi/extra/structural_hash.h>

   namespace ffi = tvm::ffi;

   ffi::Any value = ...;

   // Compute structural hash
   uint64_t h = ffi::StructuralHash::Hash(value);

   // With options
   uint64_t h2 = ffi::StructuralHash::Hash(value,
       /*map_free_vars=*/true,
       /*skip_tensor_content=*/true);

   // Functor form
   ffi::StructuralHash hasher;
   uint64_t h3 = hasher(value);

Map Hashing
~~~~~~~~~~~

Maps require order-independent hashing since iteration order is not guaranteed.
The implementation collects ``(key_hash, value)`` pairs, sorts them by key hash,
and then hashes the sorted sequence. When multiple keys produce the same hash
(a tie), the value hashes are skipped for those entries to maintain
determinism.

Free Variables and DAG Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Free variables** (``kTVMFFISEqHashKindFreeVar``): when ``map_free_vars`` is
  enabled, each free variable is assigned a monotonically increasing counter
  value that contributes to the hash, establishing a canonical ordering. When
  disabled, the hash falls back to pointer-based hashing.
- **DAG nodes** (``kTVMFFISEqHashKindDAGNode``): each node is assigned a graph
  counter that distinguishes shared references from independent subtrees with
  identical content. Memoization prevents redundant recomputation.

Custom Hash Functions
~~~~~~~~~~~~~~~~~~~~~

Types can register a custom hash function via the ``__s_hash__`` type attribute:

.. code-block:: cpp

   // Signature: (ObjectRef obj, int64_t init_hash, Function callback) -> int64_t
   // The callback has signature: (AnyView val, uint64_t init_hash, bool def_region) -> int64_t
   // Call the callback for each sub-component that needs hashing.

Deep Copy
---------

Overview
~~~~~~~~

:cpp:func:`tvm::ffi::DeepCopy` creates a deep clone of an object graph,
recursively copying all reachable objects while preserving shared references
and handling cycles through memoization.

.. code-block:: cpp

   #include <tvm/ffi/extra/deep_copy.h>

   namespace ffi = tvm::ffi;

   ffi::Any original = ...;
   ffi::Any cloned = ffi::DeepCopy(original);

The implementation uses the :cpp:class:`ObjectDeepCopier` class internally,
which maintains a ``copy_map_`` (hash map from original ``Object*`` to cloned
``Any``) and a ``resolve_queue_`` of objects whose fields still need resolution.

Copy Algorithm
~~~~~~~~~~~~~~

The copier processes values in two phases:

1. **Resolve**: For each value encountered, dispatch on its type:

   - **Primitives, strings, bytes, and shapes** are immutable and returned as-is.
   - **Immutable containers** (``Array``, ``Map``) are rebuilt by recursively
     resolving each element/entry. The copy is registered in the memo *after*
     all children are resolved (safe because immutable containers cannot form cycles).
   - **Mutable containers** (``List``, ``Dict``) are registered in the memo
     *before* resolving children, so that cyclic back-references resolve to the
     same new container.
   - **General objects** are shallow-copied via the ``__ffi_shallow_copy__``
     type attribute (looked up from the ``TypeAttrColumn`` for
     ``"__shallow_copy__"``), then registered in the memo and queued for field
     resolution.

2. **Field resolution**: The queue is drained iteratively. For each queued
   object, the copier reads every reflected field via
   :cpp:class:`~tvm::ffi::reflection::FieldGetter`, resolves the field value
   (which may trigger further copies), and writes it back via
   :cpp:class:`~tvm::ffi::reflection::FieldSetter` if the resolved value
   differs from the original.

This two-phase approach bounds recursion depth to container nesting rather than
object-graph depth, preventing stack overflow on deep graphs.

AccessPath
----------

Overview
~~~~~~~~

:cpp:class:`tvm::ffi::reflection::AccessPath` describes a path through nested
objects, such as ``root.attr("x").array_item(0)``. It is primarily used by
:cpp:func:`tvm::ffi::StructuralEqual::GetFirstMismatch` to report *where* two
objects differ, providing precise diagnostics for structural comparison failures.

The implementation lives in ``include/tvm/ffi/reflection/access_path.h``.

AccessStep and AccessKind
~~~~~~~~~~~~~~~~~~~~~~~~~

Each step in a path is represented by :cpp:class:`~tvm::ffi::reflection::AccessStep`,
which pairs an :cpp:enum:`~tvm::ffi::reflection::AccessKind` with a key:

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - AccessKind
     - Key Type
     - Meaning
   * - ``kAttr``
     - ``String``
     - Object attribute access (e.g., ``.name``)
   * - ``kArrayItem``
     - ``int64_t``
     - Array/list element access by index
   * - ``kMapItem``
     - ``Any``
     - Map/dict entry access by key
   * - ``kAttrMissing``
     - ``String``
     - Attribute exists on one side but not the other
   * - ``kArrayItemMissing``
     - ``int64_t``
     - Array index exists on one side but not the other
   * - ``kMapItemMissing``
     - ``Any``
     - Map key exists on one side but not the other

The "Missing" variants are used in mismatch reporting to indicate that the
expected element does not exist on one side of the comparison.

Path Structure
~~~~~~~~~~~~~~

``AccessPath`` uses a parent-pointing linked structure: each node stores an
optional parent path and the current step. This representation is space-efficient
when many paths share a common prefix (which is typical during recursive
comparison).

.. code-block:: cpp

   using namespace tvm::ffi::reflection;

   AccessPath root = AccessPath::Root();
   AccessPath p = root->Attr("layer")->Attr("weight")->ArrayItem(2);

   // Convert to flat array of steps
   Array<AccessStep> steps = p->ToSteps();

   // Check prefix relationships
   AccessPath prefix = root->Attr("layer");
   bool is_prefix = prefix->IsPrefixOf(p);  // true

Getting the First Mismatch
~~~~~~~~~~~~~~~~~~~~~~~~~~

:cpp:func:`tvm::ffi::StructuralEqual::GetFirstMismatch` returns an
``Optional<AccessPathPair>`` (a ``Tuple<AccessPath, AccessPath>``) that
identifies the first point of divergence between two values:

.. code-block:: cpp

   #include <tvm/ffi/extra/structural_equal.h>

   auto mismatch = ffi::StructuralEqual::GetFirstMismatch(a, b);
   if (mismatch.has_value()) {
     auto [lhs_path, rhs_path] = mismatch.value();
     // lhs_path and rhs_path point to the first differing location
   }

When the comparison fails, the handler builds the mismatch path by collecting
``AccessStep`` objects in reverse order (from leaf to root) as the recursive
comparison unwinds, then reverses them to produce the final path.

.. _type-attr-column-mechanism:

TypeAttrColumn
--------------

:cpp:class:`tvm::ffi::reflection::TypeAttrColumn` is a per-type attribute
mechanism that allows registering custom functions indexed by type. It is backed
by a global column array (one entry per registered type index), looked up by
a string name.

Structural equality, hashing, and deep copy each use a ``TypeAttrColumn`` to
allow types to override the default reflection-driven behavior:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute Name
     - Purpose
   * - ``"__s_equal__"``
     - Custom structural equality comparison function for a type.
   * - ``"__s_hash__"``
     - Custom structural hash function for a type.
   * - ``"__shallow_copy__"``
     - Shallow copy constructor used by deep copy to clone individual objects.

Columns are ensured to exist at static initialization time via
:cpp:func:`~tvm::ffi::reflection::EnsureTypeAttrColumn`. Custom functions are
registered as type attributes on the type info and looked up by type index at
runtime.

.. code-block:: cpp

   #include <tvm/ffi/reflection/accessor.h>

   // Look up the column (must exist)
   tvm::ffi::reflection::TypeAttrColumn column("__s_equal__");

   // Access the custom function for a specific type
   AnyView custom_fn = column[type_index];
   if (custom_fn != nullptr) {
     // Use custom comparison
   }

Field-Level Control
~~~~~~~~~~~~~~~~~~~

Individual fields can be annotated with flags that affect structural operations:

- ``kTVMFFIFieldFlagBitMaskSEqHashIgnore``: The field is skipped during
  structural equality and hashing (e.g., cached or derived data).
- ``kTVMFFIFieldFlagBitMaskSEqHashDef``: The field enters a "def region"
  where free variable mapping is enabled during comparison and hashing.

Python API
----------

The Python bindings expose structural operations as top-level functions in the
``tvm_ffi`` package.

Structural Equality and Hashing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import tvm_ffi

   a = tvm_ffi.Array([1, 2, 3])
   b = tvm_ffi.Array([1, 2, 3])
   c = tvm_ffi.Array([1, 2, 4])

   # Structural equality
   assert tvm_ffi.structural_equal(a, b)
   assert not tvm_ffi.structural_equal(a, c)

   # Structural hashing (consistent with equality)
   assert tvm_ffi.structural_hash(a) == tvm_ffi.structural_hash(b)

:py:func:`tvm_ffi.structural_equal` and :py:func:`tvm_ffi.structural_hash`
both accept optional ``map_free_vars`` and ``skip_tensor_content`` keyword
arguments.

Mismatch Diagnostics
~~~~~~~~~~~~~~~~~~~~

:py:func:`tvm_ffi.get_first_structural_mismatch` returns a tuple of two
``AccessPath`` objects pointing to the first divergence, or ``None`` if the
values are equal:

.. code-block:: python

   import tvm_ffi

   a = tvm_ffi.Array([1, 2, 3])
   b = tvm_ffi.Array([1, 2, 4])

   result = tvm_ffi.get_first_structural_mismatch(a, b)
   if result is not None:
       lhs_path, rhs_path = result
       # lhs_path and rhs_path point to index 2

StructuralKey
~~~~~~~~~~~~~

:py:class:`tvm_ffi.StructuralKey` wraps a value so that it can be used as a
dictionary key with structural equality and hashing semantics. The hash is
computed once at construction and cached:

.. code-block:: python

   import tvm_ffi

   k0 = tvm_ffi.StructuralKey([1, 2, 3])
   k1 = tvm_ffi.StructuralKey([1, 2, 3])

   d = {k0: "hello"}
   assert d[k1] == "hello"  # k1 matches k0 structurally

Deep Copy
~~~~~~~~~

Python's ``copy.deepcopy`` and ``copy.copy`` are supported for TVM-FFI objects
that have copy support. Under the hood, ``copy.deepcopy(obj)`` calls
:cpp:func:`tvm::ffi::DeepCopy` through the ``ffi.DeepCopy`` global function,
while ``copy.copy(obj)`` calls the object's ``__ffi_shallow_copy__`` method:

.. code-block:: python

   import copy
   import tvm_ffi

   obj = MyObject(42, "hello")
   shallow = copy.copy(obj)     # calls __ffi_shallow_copy__
   deep = copy.deepcopy(obj)    # calls ffi.DeepCopy

   # Containers also support deep copy
   arr = tvm_ffi.Array([1, 2, 3])
   arr_copy = copy.deepcopy(arr)

Further Reading
---------------

- :doc:`object_and_class`: Object system fundamentals, reflection registration,
  and cross-language exposure
- :doc:`containers`: Built-in container types (Array, List, Map, Dict, Shape)
- :doc:`any`: The ``Any`` / ``AnyView`` type-erased value containers
- :doc:`reflection`: Reflection metadata and TypeAttrColumn
