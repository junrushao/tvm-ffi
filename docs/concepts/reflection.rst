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

Reflection System
=================

The reflection system in TVM-FFI enables cross-language exposure of C++ classes
by recording metadata about constructors, fields, and methods at static initialization
time. This metadata drives automatic Python binding generation, serialization,
structural equality/hashing, deep copy, and IDE support (via stub generation)
without requiring hand-written binding code for each field or method.

The key components are:

- :cpp:class:`ObjectDef\<T\> <tvm::ffi::reflection::ObjectDef>` -- builder that registers metadata for an object type ``T``
- :cpp:class:`TVMFFIFieldInfo` -- C-level struct describing a single field
- :cpp:class:`TVMFFIMethodInfo` -- C-level struct describing a single method
- ``TypeSchema<T>`` -- compile-time template that generates JSON type descriptions
- :cpp:class:`ObjectCreator <tvm::ffi::reflection::ObjectCreator>` -- creates objects from reflection metadata at runtime
- :cpp:class:`GlobalDef <tvm::ffi::reflection::GlobalDef>` -- registers global functions with typed metadata


ObjectDef Builder Pattern
-------------------------

:cpp:class:`ObjectDef\<T\> <tvm::ffi::reflection::ObjectDef>` is a builder class
located in ``include/tvm/ffi/reflection/registry.h``. It registers metadata for the
object type ``T`` (which must inherit from :cpp:class:`~tvm::ffi::Object`). All its
methods return ``*this``, enabling a fluent chaining interface.

Registration is performed inside a :c:macro:`TVM_FFI_STATIC_INIT_BLOCK`, which
ensures that metadata is recorded during static initialization before any
cross-language calls can reference the type.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Method
     - Description
   * - ``.def(init<Args...>())``
     - Register a constructor with the given argument types.
       Stored as a static ``__ffi_init__`` method.
   * - ``.def_ro("name", &T::field)``
     - Register a read-only field.
   * - ``.def_rw("name", &T::field)``
     - Register a read-write field.
       Only allowed when ``T::_type_mutable`` is true.
   * - ``.def("name", &T::method)``
     - Register an instance method.
       The first argument is automatically bound to ``self``.
   * - ``.def_static("name", &func)``
     - Register a static method (no ``self`` argument).

Each method accepts optional trailing arguments for documentation strings,
default values, metadata, and field flags (see :ref:`reflection-defaults` and
:ref:`reflection-field-metadata`).

**Example.** The following code registers a complete class with constructor,
fields, and methods:

.. code-block:: cpp

   #include <tvm/ffi/tvm_ffi.h>

   class MyObjectObj : public ffi::Object {
    public:
     int64_t value;
     ffi::String name;

     MyObjectObj(int64_t value, ffi::String name)
         : value(value), name(std::move(name)) {}

     int64_t GetValue() const { return value; }

     static MyObjectObj* Create(int64_t v, ffi::String n) {
       return ffi::make_object<MyObjectObj>(v, std::move(n)).release();
     }

     TVM_FFI_DECLARE_OBJECT_INFO("my_ext.MyObject", MyObjectObj, ffi::Object);
   };

   TVM_FFI_STATIC_INIT_BLOCK() {
     namespace refl = tvm::ffi::reflection;
     refl::ObjectDef<MyObjectObj>()
         .def(refl::init<int64_t, ffi::String>())
         .def_rw("value", &MyObjectObj::value, "The integer value")
         .def_rw("name", &MyObjectObj::name, "The name string")
         .def("get_value", &MyObjectObj::GetValue, "Returns the value")
         .def_static("create", &MyObjectObj::Create, "Factory function");
   }

.. note::

   The constructor is bound through the ``init<Args...>`` helper. At the C
   level this creates a static method named ``__ffi_init__`` whose body calls
   ``make_object<T>(args...)``. Python uses this method to implement
   ``__init__``.


Constructor Registration with ``init``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :cpp:class:`init\<Args...\> <tvm::ffi::reflection::init>` helper is a
lightweight tag type. When passed to ``ObjectDef::def()``, it causes a static
``__ffi_init__`` method to be registered that constructs the object by forwarding
the given arguments to ``make_object<T>(args...)``.

.. code-block:: cpp

   // Register a constructor that takes (int64_t, int32_t)
   refl::ObjectDef<ExampleObj>()
       .def(refl::init<int64_t, int32_t>());

The registered method is a :cpp:class:`~tvm::ffi::Function` with full type
schema metadata, so Python and other languages can discover the constructor
signature via reflection.


Automatic Shallow Copy
~~~~~~~~~~~~~~~~~~~~~~

When a type ``T`` is copy-constructible, ``ObjectDef<T>`` automatically registers
a ``__ffi_shallow_copy__`` method (both as an instance method and a type
attribute). This method creates a new object via the C++ copy constructor and is
used by the deep-copy infrastructure as the per-node copy step.


Field and Method Metadata
-------------------------

At the C ABI level, reflection metadata is stored in two structs defined in
``include/tvm/ffi/c_api.h``.

TVMFFIFieldInfo
~~~~~~~~~~~~~~~

Each registered field is represented by a :cpp:class:`TVMFFIFieldInfo` struct
with the following key members:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Member
     - Description
   * - ``name``
     - The field name as a :cpp:class:`TVMFFIByteArray`.
   * - ``doc``
     - Optional documentation string.
   * - ``metadata``
     - JSON string with structured metadata (e.g., ``type_schema``).
   * - ``flags``
     - Bitmask combining values from :cpp:enum:`TVMFFIFieldFlagBitMask`.
   * - ``offset``
     - Byte offset from the :cpp:class:`~tvm::ffi::Object` header to the field.
   * - ``size`` / ``alignment``
     - The field's size and alignment in bytes.
   * - ``getter`` / ``setter``
     - Function pointers of type :cpp:type:`TVMFFIFieldGetter` /
       :cpp:type:`TVMFFIFieldSetter` that read/write the field at a raw address.
   * - ``default_value_or_factory``
     - Holds either a static default value or a factory function
       (see :ref:`reflection-defaults`).
   * - ``field_static_type_index``
     - Compile-time type index hint for the serializer.

TVMFFIMethodInfo
~~~~~~~~~~~~~~~~

Each registered method is represented by a :cpp:class:`TVMFFIMethodInfo` struct:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Member
     - Description
   * - ``name``
     - The method name.
   * - ``doc``
     - Optional documentation string.
   * - ``metadata``
     - JSON string (includes ``type_schema`` for the method signature).
   * - ``flags``
     - Bitmask. ``kTVMFFIFieldFlagBitMaskIsStaticMethod`` distinguishes
       static methods from instance methods.
   * - ``method``
     - The method stored as a :cpp:class:`~tvm::ffi::Function` inside a
       :cpp:class:`TVMFFIAny`. For instance methods, the first argument is
       the ``self`` pointer.

Field Flags
~~~~~~~~~~~

The :cpp:enum:`TVMFFIFieldFlagBitMask` enum defines the following bit flags:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Flag
     - Meaning
   * - ``kTVMFFIFieldFlagBitMaskWritable``
     - The field can be written (set by ``def_rw``).
   * - ``kTVMFFIFieldFlagBitMaskHasDefault``
     - A default value or factory is available.
   * - ``kTVMFFIFieldFlagBitMaskIsStaticMethod``
     - The entry is a static method (no ``self``).
   * - ``kTVMFFIFieldFlagBitMaskSEqHashIgnore``
     - Structural equality/hash should skip this field.
   * - ``kTVMFFIFieldFlagBitMaskSEqHashDef``
     - The field enters a definition region for structural eq/hash
       (used for variable binding scopes).
   * - ``kTVMFFIFieldFlagBitMaskDefaultFromFactory``
     - ``default_value_or_factory`` holds a factory ``() -> Any``
       rather than a static value.
   * - ``kTVMFFIFieldFlagBitMaskReprOff``
     - Exclude this field from the generic ``repr`` output.

.. _reflection-defaults:

DefaultValue and DefaultFactory
-------------------------------

Fields can carry default values that are used when creating objects from
partial keyword dictionaries (e.g., during deserialization or from Python).

``DefaultValue(value)``
  Stores a static default. The value is kept in the
  :cpp:member:`TVMFFIFieldInfo::default_value_or_factory` slot and used directly
  by the setter.

.. code-block:: cpp

   .def_rw("count", &MyObj::count, refl::DefaultValue(int64_t(0)))

``DefaultFactory(callable)``
  Stores a factory function ``() -> Any`` that is invoked each time a default
  is needed. This avoids aliasing when the default is a mutable container
  (e.g., an empty :cpp:class:`~tvm::ffi::Array` or :cpp:class:`~tvm::ffi::Map`).

.. code-block:: cpp

   .def_rw("items", &MyObj::items,
           refl::DefaultFactory(ffi::Function::FromTyped(
               []() -> ffi::Array<ffi::String> { return {}; })))

Both traits set the ``kTVMFFIFieldFlagBitMaskHasDefault`` flag.
``DefaultFactory`` additionally sets ``kTVMFFIFieldFlagBitMaskDefaultFromFactory``
so that the runtime knows to call the factory instead of using the value directly.

.. _reflection-field-metadata:

Metadata and Documentation
~~~~~~~~~~~~~~~~~~~~~~~~~~

Arbitrary key-value metadata can be attached to fields and methods via the
:cpp:class:`Metadata <tvm::ffi::reflection::Metadata>` trait. Values must be
``int``, ``bool``, or ``String``. The metadata is serialized to a JSON string
stored in the ``metadata`` member of :cpp:class:`TVMFFIFieldInfo` or
:cpp:class:`TVMFFIMethodInfo`.

.. code-block:: cpp

   .def_rw("value", &MyObj::value,
           "The integer value",                        // docstring
           refl::DefaultValue(int64_t(0)),             // default
           refl::Metadata{{"min", 0}, {"max", 100}})  // custom metadata

Documentation strings are passed as plain ``const char*`` trailing arguments.
They are stored separately from structured metadata in the ``doc`` field.


Structural Equality/Hash Flags
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two special traits control structural equality and hashing behavior:

``AttachFieldFlag::SEqHashIgnore()``
  Mark a field so that structural equality and hash computations skip it.

``AttachFieldFlag::SEqHashDef()``
  Mark a field as entering a variable-definition region, enabling
  scope-aware structural comparison (e.g., matching bound variables).

.. code-block:: cpp

   .def_ro("span", &MyObj::span, refl::AttachFieldFlag::SEqHashIgnore())
   .def_ro("var", &MyObj::var, refl::AttachFieldFlag::SEqHashDef())


Repr Control
~~~~~~~~~~~~

By default, all fields appear in the reflection-based ``repr`` output.
Use ``Repr(false)`` to exclude a field:

.. code-block:: cpp

   .def_ro("internal_cache", &MyObj::cache, refl::Repr(false))


TypeSchema
----------

``TypeSchema<T>`` (defined in ``include/tvm/ffi/base_details.h``) is a template
alias that generates a JSON-based type description for any FFI-compatible type
``T``. It strips ``const`` and reference qualifiers and delegates to
``TypeSchemaImpl<T>``, which in turn calls ``TypeTraits<T>::TypeSchema()``.

The schema is used by:

- **Stub generation** (``tvm-ffi-stubgen``) to produce Python type annotations.
- **Metadata APIs** to describe field types and method signatures in a
  language-neutral format.
- **Global function registration** to record typed signatures alongside packed functions.

Schema Format
~~~~~~~~~~~~~

Primitive types produce a simple JSON object:

.. code-block:: json

   {"type": "int"}
   {"type": "bool"}
   {"type": "float"}
   {"type": "str"}
   {"type": "None"}

Generic container types include an ``args`` array with nested schemas:

.. code-block:: json

   {"type": "ffi.Array", "args": [{"type": "str"}]}
   {"type": "ffi.Map", "args": [{"type": "str"}, {"type": "int"}]}
   {"type": "ffi.List", "args": [{"type": "int"}]}
   {"type": "Optional", "args": [{"type": "str"}]}
   {"type": "Tuple", "args": [{"type": "int"}, {"type": "str"}]}
   {"type": "Variant", "args": [{"type": "int"}, {"type": "str"}]}

Function types encode the return type as the first element of ``args``,
followed by each parameter type:

.. code-block:: json

   {"type": "ffi.Function", "args": [{"type": "int"}, {"type": "str"}, {"type": "int"}]}

User-defined object types use their type key:

.. code-block:: json

   {"type": "my_ext.MyObject"}

Type Mapping Summary
~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - C++ Type
     - Schema ``type`` Value
   * - ``int64_t``, ``int32_t``, ``int``
     - ``"int"``
   * - ``bool``
     - ``"bool"``
   * - ``double``, ``float``
     - ``"float"``
   * - ``String``
     - ``"str"``
   * - ``Bytes``
     - ``"bytes"``
   * - ``void`` / ``nullptr_t``
     - ``"None"``
   * - ``DLDataType``
     - ``"DLDataType"``
   * - ``DLDevice``
     - ``"DLDevice"``
   * - ``Array<T>``
     - ``"ffi.Array"`` with args ``[T_schema]``
   * - ``List<T>``
     - ``"ffi.List"`` with args ``[T_schema]``
   * - ``Map<K, V>``
     - ``"ffi.Map"`` with args ``[K_schema, V_schema]``
   * - ``Dict<K, V>``
     - ``"ffi.Dict"`` with args ``[K_schema, V_schema]``
   * - ``Optional<T>``
     - ``"Optional"`` with args ``[T_schema]``
   * - ``Tuple<T...>``
     - ``"Tuple"`` with args ``[T_schemas...]``
   * - ``Variant<T...>``
     - ``"Variant"`` with args ``[T_schemas...]``
   * - ``Function`` / ``TypedFunction<R(Args...)>``
     - ``"ffi.Function"`` with args ``[R_schema, Args_schemas...]``
   * - ``Any`` / ``AnyView``
     - ``"Any"``
   * - ``ObjectRef`` subclass
     - The ``_type_key`` of the underlying object type


ObjectCreator
-------------

:cpp:class:`ObjectCreator <tvm::ffi::reflection::ObjectCreator>` (defined in
``include/tvm/ffi/reflection/creator.h``) creates object instances from
reflection metadata at runtime. It is the backbone of deserialization and
keyword-based construction from other languages.

Construction
~~~~~~~~~~~~

``ObjectCreator`` is initialized with a type key or a ``TVMFFITypeInfo*``.
It verifies that:

1. The type has reflection metadata registered (``metadata != nullptr``).
2. A default creator function exists (``metadata->creator != nullptr``).

If the object type is default-constructible, the creator calls
``make_object<T>()``. If the type supports ``UnsafeInit``, the creator uses
``make_object<T>(UnsafeInit{})``. Otherwise, no creator is available and
construction via ``ObjectCreator`` will throw.

Field Population
~~~~~~~~~~~~~~~~

Calling ``ObjectCreator(type_key)(fields)`` with a ``Map<String, Any>``
performs the following steps:

1. Allocate a new, default-constructed instance via the creator.
2. Iterate over all registered fields (including inherited fields from parent
   types, traversed in parent-to-child order).
3. For each field:

   - If the field name exists in the ``fields`` map, set it via the field's setter.
   - Otherwise, if the field has a default value or factory, apply it.
   - Otherwise, throw a :cpp:class:`TypeError` for the missing required field.

4. Verify that no extra keys in the map are unrecognized.

.. code-block:: cpp

   #include <tvm/ffi/reflection/creator.h>

   namespace refl = tvm::ffi::reflection;

   // Create an object from a field map
   ffi::Map<ffi::String, ffi::Any> fields;
   fields.Set("value", int64_t(42));
   fields.Set("name", ffi::String("hello"));

   refl::ObjectCreator creator("my_ext.MyObject");
   ffi::Any obj = creator(fields);


TVMFFITypeMetadata
~~~~~~~~~~~~~~~~~~

The :cpp:class:`TVMFFITypeMetadata` struct stores per-type metadata registered
by ``ObjectDef``:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Member
     - Description
   * - ``doc``
     - Optional documentation string for the type.
   * - ``creator``
     - :cpp:type:`TVMFFIObjectCreator` function pointer that allocates
       a new empty instance.
   * - ``total_size``
     - ``sizeof(T)`` for the object struct.
   * - ``structural_eq_hash_kind``
     - :cpp:enum:`TVMFFISEqHashKind` that controls how structural
       equality and hashing treat this type (tree node, DAG node,
       free variable, etc.).


GlobalDef for Functions
-----------------------

:cpp:class:`GlobalDef <tvm::ffi::reflection::GlobalDef>` registers global
functions with typed metadata in the FFI global function table. Unlike the
older :c:macro:`TVM_FFI_REGISTER_GLOBAL` macro, ``GlobalDef`` attaches a
``type_schema`` to each function so that Python and other language bindings can
discover the function's signature.

.. code-block:: cpp

   TVM_FFI_STATIC_INIT_BLOCK() {
     namespace refl = tvm::ffi::reflection;
     refl::GlobalDef()
         .def("my_ext.add", [](int64_t a, int64_t b) -> int64_t { return a + b; },
              "Add two integers")
         .def("my_ext.greet", [](ffi::String name) -> ffi::String {
           return ffi::String("Hello, " + std::string(name));
         });
   }

``GlobalDef`` provides three registration methods:

``def(name, func, extra...)``
  Register a typed function. The type schema is automatically inferred from
  the function signature.

``def_packed(name, func, extra...)``
  Register a function in packed-args format (``TVMFFISafeCallType``).
  The type schema is recorded as a generic ``Function``.

``def_method(name, func, extra...)``
  Register a class method as a global function. If the method is not static,
  an additional ``self`` argument is prepended.

All methods support optional trailing arguments for docstrings and
:cpp:class:`Metadata <tvm::ffi::reflection::Metadata>`.


TypeAttrDef for Type Attributes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:cpp:class:`TypeAttrDef\<T\> <tvm::ffi::reflection::TypeAttrDef>` registers
type-level attributes (not per-instance fields) that can be looked up by type
index at runtime. This is used for registering well-known type functions such
as ``__ffi_shallow_copy__``.

.. code-block:: cpp

   namespace refl = tvm::ffi::reflection;
   refl::TypeAttrDef<MyObjectObj>()
       .def("my_custom_printer", &MyObjectObj::CustomPrint);


ForEachFieldInfo
----------------

Two traversal functions in ``include/tvm/ffi/reflection/accessor.h`` iterate
over all fields of a type, including inherited fields from parent types.

``ForEachFieldInfo(type_info, callback)``
  Iterates over every field in parent-to-child order and calls
  ``callback(const TVMFFIFieldInfo*)`` for each. The callback must return
  ``void``.

``ForEachFieldInfoWithEarlyStop(type_info, callback)``
  Same traversal order, but the callback returns ``bool``. Returning ``true``
  stops the iteration early. The function returns ``true`` if iteration was
  stopped.

.. code-block:: cpp

   #include <tvm/ffi/reflection/accessor.h>

   const TVMFFITypeInfo* info = TVMFFIGetTypeInfo(type_index);

   // Print all field names
   tvm::ffi::reflection::ForEachFieldInfo(info, [](const TVMFFIFieldInfo* field) {
     std::cout << std::string(field->name.data, field->name.size) << std::endl;
   });

   // Search for a specific field
   bool found = tvm::ffi::reflection::ForEachFieldInfoWithEarlyStop(
       info, [](const TVMFFIFieldInfo* field) {
         return std::strncmp(field->name.data, "value", field->name.size) == 0;
       });

These functions are the building blocks for serialization, structural equality,
deep copy, and the ``ObjectCreator``.


Field and Method Accessors
~~~~~~~~~~~~~~~~~~~~~~~~~~

The accessor header also provides wrapper classes for direct field access:

:cpp:class:`FieldGetter <tvm::ffi::reflection::FieldGetter>`
  Wraps a :cpp:class:`TVMFFIFieldInfo` and provides ``operator()`` to read a
  field value from an object pointer.

:cpp:class:`FieldSetter <tvm::ffi::reflection::FieldSetter>`
  Wraps a :cpp:class:`TVMFFIFieldInfo` and provides ``operator()`` to write a
  field value on an object pointer.

:cpp:class:`TypeAttrColumn <tvm::ffi::reflection::TypeAttrColumn>`
  Provides indexed access to a type attribute column by type index.

.. code-block:: cpp

   namespace refl = tvm::ffi::reflection;

   refl::FieldGetter getter("my_ext.MyObject", "value");
   ffi::Any val = getter(obj);

   refl::FieldSetter setter("my_ext.MyObject", "value");
   setter(obj, ffi::AnyView(int64_t(100)));


C API Registration Functions
----------------------------

The reflection system ultimately calls the following C API functions defined in
``include/tvm/ffi/c_api.h``:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - C Function
     - Purpose
   * - :cpp:func:`TVMFFITypeRegisterField`
     - Register a field for a type index.
   * - :cpp:func:`TVMFFITypeRegisterMethod`
     - Register a method for a type index.
   * - :cpp:func:`TVMFFITypeRegisterMetadata`
     - Register the type metadata (creator, size, SEqHash kind).
   * - :cpp:func:`TVMFFITypeRegisterAttr`
     - Register a type attribute in a column store.
   * - :cpp:func:`TVMFFIGetTypeInfo`
     - Retrieve the full :cpp:class:`TVMFFITypeInfo` by type index,
       including fields, methods, and metadata.
   * - :cpp:func:`TVMFFIGetTypeAttrColumn`
     - Retrieve a type attribute column by attribute name.
   * - :cpp:func:`TVMFFIFunctionSetGlobalFromMethodInfo`
     - Register a global function with method info metadata.

These functions are stable ABI entry points, allowing language bindings
written in C, Rust, or other languages to register and query reflection
metadata without depending on C++ headers.


Further Reading
---------------

.. seealso::

   :doc:`object_and_class`
     Object system fundamentals: ``Object``, ``ObjectRef``, type registration,
     and reference counting.

   :doc:`func_module`
     The :cpp:class:`~tvm::ffi::Function` type and the global function registry.

   :doc:`any`
     The :cpp:class:`~tvm::ffi::Any` / :cpp:class:`~tvm::ffi::AnyView`
     type-erased value containers used by the reflection getter/setter system.

   :doc:`abi_overview`
     Low-level C ABI layout for :cpp:class:`TVMFFIObject`, :cpp:class:`TVMFFIAny`,
     and the type info table.

   :doc:`serialization`
     How reflection metadata drives object serialization.

   :doc:`structural_ops`
     How reflection enables structural equality and hashing.

   :doc:`type_traits`
     Type traits and TypeSchema.
