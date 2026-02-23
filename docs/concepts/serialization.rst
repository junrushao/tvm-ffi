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

Serialization
=============

The serialization system in TVM-FFI provides a three-layer stack for persisting
object graphs. Unlike simple tree serialization, it preserves object identity,
reference sharing, and full type information across a round-trip. This makes it
suitable for Python pickle support, cross-process communication, and lightweight
persistence of complex object structures.

The three layers, from lowest to highest, are:

1. **JSON Parser and Writer** -- standard JSON I/O built on top of :cpp:class:`tvm::ffi::Any`.
2. **JSONGraph Format** -- a graph-aware envelope that assigns IDs to nodes so
   shared references survive serialization.
3. **Reflection-Based Object Creator** -- uses registered field metadata to
   reconstruct C++ objects from their serialized form.

JSON Parser and Writer
----------------------

The lowest layer provides a lightweight JSON implementation that reuses TVM-FFI's
own value types instead of introducing an external JSON library.

Value Representation
~~~~~~~~~~~~~~~~~~~~

:cpp:type:`tvm::ffi::json::Value` is a type alias for :cpp:class:`tvm::ffi::Any`.
JSON values map to FFI types as follows:

.. list-table::
   :header-rows: 1
   :widths: 25 40

   * - JSON type
     - FFI type
   * - ``null``
     - ``None`` (null ``Any``)
   * - ``true`` / ``false``
     - ``bool``
   * - integer
     - ``int64_t``
   * - floating-point
     - ``double``
   * - string
     - :cpp:class:`tvm::ffi::String`
   * - array
     - :cpp:type:`tvm::ffi::json::Array` (alias for ``Array<Any>``)
   * - object
     - :cpp:type:`tvm::ffi::json::Object` (alias for ``Map<Any, Any>``)

Because integers are stored as ``int64_t`` rather than ``double``, the parser
preserves full 64-bit integer precision -- a common pain point with standard
JSON libraries.

Extensions Beyond Standard JSON
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The parser accepts JavaScript-style ``Infinity``, ``-Infinity``, and ``NaN``
literals. The writer emits these same literals so that floating-point special
values round-trip correctly. Integer values that fit in ``int64_t`` are parsed
as integers; values with a decimal point or exponent are parsed as ``double``.
The writer distinguishes the two: integer-valued doubles are printed with a
trailing ``.0`` (e.g. ``42.0``) to maintain the type distinction on re-parse.

API
~~~

The public C++ API lives in ``include/tvm/ffi/extra/json.h``:

.. code-block:: cpp

   #include <tvm/ffi/extra/json.h>

   namespace json = tvm::ffi::json;

   // Parse a JSON string into a json::Value.
   // Throws ValueError on malformed input.
   json::Value val = json::Parse(R"({"key": [1, 2, 3]})");

   // Stringify back to a compact JSON string.
   ffi::String compact = json::Stringify(val);

   // Pretty-print with 2-space indentation.
   ffi::String pretty = json::Stringify(val, 2);

:cpp:func:`tvm::ffi::json::Parse` accepts an optional ``String* error_msg``
out-parameter. When provided, parse errors are written there instead of being
thrown, and the function returns ``nullptr``.

Implementation Details
~~~~~~~~~~~~~~~~~~~~~~

The parser (``src/ffi/extra/json_parser.cc``) is a hand-written recursive
descent parser that avoids heap allocation for the fast path of short,
non-escaped strings. It uses a ``JSONParserContext`` helper that tracks line and
column numbers for error messages.

The writer (``src/ffi/extra/json_writer.cc``) streams output into a
``std::string`` via a ``std::back_insert_iterator``. It detects cycles in
``List`` containers and throws ``ValueError`` if a list contains itself.

Both the parser and writer are registered as global FFI functions:

- ``ffi.json.Parse`` -- parse a JSON string
- ``ffi.json.Stringify`` -- serialize a JSON value

JSONGraph Format
----------------

Plain JSON can represent trees, but TVM-FFI object graphs may contain shared
references: multiple fields pointing to the same heap object. The JSONGraph
format solves this by assigning each unique value a numeric node ID and using
ID-based indirection for references.

Wire Format
~~~~~~~~~~~

A serialized graph is a JSON object with the following top-level structure:

.. code-block:: json

   {
     "root_index": 3,
     "nodes": [
       {"type": "ffi.String", "data": "x"},
       {"type": "test.Var", "data": {"name": 0}},
       {"type": "ffi.Array", "data": [1]},
       {"type": "test.Func", "data": {"params": 2, "body": 2, "comment": 0}}
     ],
     "metadata": {}
   }

- ``root_index`` -- the index into ``nodes`` that represents the serialized
  root value.
- ``nodes`` -- a flat array where each element is a serialized node.
- ``metadata`` -- an optional object for user-supplied metadata (version
  strings, provenance, etc.).

Each node has a ``type`` field (the type key string) and an optional ``data``
field whose shape depends on the type:

.. list-table::
   :header-rows: 1
   :widths: 25 50

   * - Type
     - ``data`` format
   * - ``None``
     - absent
   * - ``bool``
     - ``true`` or ``false``
   * - ``int``
     - integer literal
   * - ``float``
     - float literal
   * - ``DataType``
     - dtype string (e.g. ``"float32"``)
   * - ``Device``
     - ``[device_type, device_id]``
   * - ``ffi.String``
     - the string value
   * - ``ffi.Bytes``
     - base64-encoded string
   * - ``ffi.Array``, ``ffi.List``
     - array of node indices
   * - ``ffi.Map``, ``ffi.Dict``
     - flat array of alternating ``[key_idx, val_idx, ...]``
   * - ``ffi.Shape``
     - array of ``int64_t`` dimension values
   * - user-defined objects
     - object mapping field names to values (see below)

For user-defined object nodes, primitive fields whose static type is known at
compile time (``bool``, ``int64_t``, ``double``, ``DLDataType``) are stored
inline in the ``data`` object. Fields with object or container types are stored
as node indices, enabling shared-reference deduplication.

Shared Reference Preservation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

During serialization, the ``ObjectGraphSerializer`` maintains a hash map from
``Any`` values to their assigned node index. When the same object is
encountered a second time, the existing index is returned instead of creating a
duplicate node. This guarantees that shared references in the original graph are
reconstructed as shared references on deserialization.

For example, serializing an ``Array`` that contains the same ``Var`` object
three times produces a single ``Var`` node and an array ``data`` of
``[idx, idx, idx]``. After deserialization, all three elements of the restored
array point to the same ``Var`` instance.

Cycle Detection
~~~~~~~~~~~~~~~

Immutable containers (``Array``, ``Map``) cannot form cycles by construction.
Mutable containers (``List``, ``Dict``) can theoretically contain themselves.
The serializer tracks containers currently being visited and throws
``ValueError`` if a cycle is detected.

Entry Points
~~~~~~~~~~~~

The C++ API is declared in ``include/tvm/ffi/extra/serialization.h``:

.. code-block:: cpp

   #include <tvm/ffi/extra/serialization.h>

   namespace ffi = tvm::ffi;

   // Serialize any value to a JSONGraph.
   ffi::Any obj = ...;
   ffi::json::Value graph = ffi::ToJSONGraph(obj);

   // Attach optional metadata.
   ffi::json::Object meta{{"version", "1.0"}};
   ffi::json::Value graph_with_meta = ffi::ToJSONGraph(obj, meta);

   // Deserialize back.
   ffi::Any restored = ffi::FromJSONGraph(graph);

String convenience wrappers combine the JSON and graph layers in one call:

.. code-block:: cpp

   // One-shot string round-trip.
   ffi::String json_str = ffi::ToJSONGraphString(obj);
   ffi::Any restored = ffi::FromJSONGraphString(json_str);

These are also registered as global FFI functions:

- ``ffi.ToJSONGraph`` / ``ffi.FromJSONGraph`` -- work with ``json::Value``
- ``ffi.ToJSONGraphString`` / ``ffi.FromJSONGraphString`` -- work with strings

Reflection-Based Deserialization
--------------------------------

The JSONGraph deserializer must reconstruct C++ objects from their type key and
field data. It does this by leveraging the reflection metadata registered via
:cpp:class:`tvm::ffi::reflection::ObjectDef`.

Object Reconstruction Flow
~~~~~~~~~~~~~~~~~~~~~~~~~~

When the deserializer encounters a node whose type key maps to a user-defined
object (type index >= ``kTVMFFIStaticObjectBegin``), it proceeds as follows:

1. **Look up type metadata.** The type key is resolved to a ``TVMFFITypeInfo``
   via the global type registry. The metadata must include a ``creator``
   function pointer.

2. **Create an empty object.** The ``creator`` is called to allocate a
   default-constructed (or ``UnsafeInit``-constructed) instance.

3. **Populate fields.** For each field registered in the type's
   ``TVMFFIFieldInfo`` array, the deserializer:

   - Checks whether the field name exists in the serialized ``data`` object.
   - If present, decodes the value: primitive fields are read directly; object
     fields are resolved by recursively decoding the referenced node index.
   - Calls the field's registered ``setter`` to write the value into the object
     at the correct byte offset.

4. **Handle defaults.** If a field is absent from the serialized data and has
   the ``kTVMFFIFieldFlagBitMaskHasDefault`` flag, its default value (or
   default factory) is applied via
   :cpp:func:`tvm::ffi::reflection::SetFieldToDefault`. If neither the field
   nor a default is available, a ``TypeError`` is thrown.

The :cpp:class:`tvm::ffi::reflection::ObjectCreator` class in
``include/tvm/ffi/reflection/creator.h`` provides a standalone helper for the
same pattern (create-from-field-map), used outside the serialization context as
well:

.. code-block:: cpp

   #include <tvm/ffi/reflection/creator.h>

   namespace refl = tvm::ffi::reflection;

   refl::ObjectCreator creator("my_ext.MyObject");
   ffi::Any obj = creator(ffi::Map<ffi::String, ffi::Any>{
       {"value", 42},
       {"name", ffi::String("hello")},
   });

Custom Serialization Hooks
~~~~~~~~~~~~~~~~~~~~~~~~~~

Some objects cannot be reconstructed from their reflected fields alone (for
example, objects without a default constructor, or objects whose internal
representation differs from their logical fields). These types can register
custom serialization hooks via type attributes:

- ``__data_to_json__`` -- a function ``(const ObjType*) -> json::Value`` that
  produces the ``data`` payload during serialization.
- ``__data_from_json__`` -- a function ``(json::Value) -> ObjRef`` that
  reconstructs the object during deserialization.

Registration example:

.. code-block:: cpp

   TVM_FFI_STATIC_INIT_BLOCK() {
     namespace refl = tvm::ffi::reflection;
     refl::TypeAttrDef<TIntObj>()
         .def("__data_to_json__",
              [](const TIntObj* self) -> Map<String, Any> {
                return Map<String, Any>{{"value", self->value}};
              })
         .def("__data_from_json__",
              [](Map<String, Any> json_obj) -> TInt {
                return TInt(json_obj["value"].cast<int64_t>());
              });
   }

When either hook is registered for a type, the serializer/deserializer uses
it instead of the default reflection-based field walk. The type attribute
columns ``__data_to_json__`` and ``__data_from_json__`` are initialized in
``src/ffi/extra/serialization.cc`` via
:cpp:func:`tvm::ffi::reflection::EnsureTypeAttrColumn`.

Python Integration
------------------

Pickle Support
~~~~~~~~~~~~~~

All :py:class:`tvm_ffi.Object` instances support Python's ``pickle`` protocol
out of the box. The Cython base class defines ``__reduce__``,
``__getstate__``, and ``__setstate__`` methods that delegate to the JSONGraph
string functions:

.. code-block:: python

   import pickle
   import tvm_ffi

   obj = tvm_ffi.convert([1, "hello", True])
   data = pickle.dumps(obj)
   restored = pickle.loads(data)
   assert list(restored) == [1, "hello", True]

Internally, ``__getstate__`` calls ``ffi.ToJSONGraphString`` and returns the
JSON string in a dict. ``__setstate__`` calls ``ffi.FromJSONGraphString`` to
reconstruct the object. This works across processes as long as both sides have
the same type registrations.

Explicit JSON Graph API
~~~~~~~~~~~~~~~~~~~~~~~

The module ``python/tvm_ffi/serialization.py`` exposes two functions for direct
use:

.. code-block:: python

   from tvm_ffi.serialization import to_json_graph_str, from_json_graph_str

   # Serialize with optional metadata.
   json_str = to_json_graph_str(obj, metadata={"version": "1.0"})

   # Deserialize.
   restored = from_json_graph_str(json_str)

:py:func:`tvm_ffi.serialization.to_json_graph_str` accepts any FFI-compatible
value (primitives, strings, containers, objects) and returns a plain Python
``str`` containing the JSONGraph representation.
:py:func:`tvm_ffi.serialization.from_json_graph_str` takes such a string and
returns the reconstructed value.

Supported Types
~~~~~~~~~~~~~~~

The following types can be serialized and deserialized through the JSONGraph
system:

- Primitives: ``None``, ``bool``, ``int``, ``float``
- ``DLDataType``, ``DLDevice``
- :cpp:class:`tvm::ffi::String`, :cpp:class:`tvm::ffi::Bytes` (base64-encoded)
- Containers: ``Array``, ``List``, ``Map``, ``Dict``, ``Shape``
- Any user-defined :cpp:class:`tvm::ffi::Object` subclass that has reflection
  metadata registered (or custom ``__data_to_json__`` / ``__data_from_json__``
  hooks)

Types without reflection metadata and without custom hooks (such as
``Function``) cannot be serialized and will raise a ``RuntimeError``.

Further Reading
---------------

- :doc:`object_and_class` -- object system basics, reflection registration,
  and type checking
- :doc:`any` -- the ``Any``/``AnyView`` type-erased containers underlying
  ``json::Value``
- :doc:`containers` -- ``Array``, ``Map``, ``List``, ``Dict``, and ``Shape``
  container types
- :doc:`func_module` -- function objects and the global function registry
- :doc:`reflection` -- Reflection metadata and ObjectCreator
