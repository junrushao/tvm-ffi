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

Python Binding Architecture
===========================

The Python binding layer bridges C++ objects to Python via Cython.
It provides a high-performance, type-safe interface that allows Python code to
create, manipulate, and call into TVM-FFI objects with minimal overhead.

The architecture follows a three-layer design:

1. **C ABI layer** -- The stable C API defined in ``include/tvm/ffi/c_api.h``,
   providing functions such as :c:func:`TVMFFIFunctionCall`,
   :c:func:`TVMFFIObjectIncRef`, and :c:func:`TVMFFIObjectDecRef`.

2. **Cython bridge layer** -- A compiled extension module (``tvm_ffi.core``)
   built from ``.pyx`` and ``.pxi`` files in ``python/tvm_ffi/cython/``.
   It holds native ``void*`` handles to C++ objects, performs argument packing
   and result extraction, and manages reference counting at the C level.

3. **Python wrapper layer** -- Pure Python modules in ``python/tvm_ffi/`` that
   provide idiomatic APIs: the :py:func:`~tvm_ffi.register_object` decorator,
   the :py:func:`~tvm_ffi.convert` function, container classes, error handling,
   and the ``@c_class`` dataclass decorator.


Cython Bridge Layer
-------------------

The Cython bridge is compiled from ``python/tvm_ffi/cython/core.pyx``, which
includes multiple ``.pxi`` files in a specific order.  The inclusion order
matters because certain base types must be registered before their subclasses.

.. code-block:: cython

   # core.pyx -- inclusion order
   include "./base.pxi"          # C API declarations, helpers
   include "./type_info.pxi"     # FieldGetter, FieldSetter, TypeSchema, TypeField, TypeInfo
   include "./object.pxi"        # CObject, Object, OpaquePyObject, PyNativeObject
   _register_object_by_index(kTVMFFIObject, Object)
   include "./error.pxi"
   _register_object_by_index(kTVMFFIError, Error)
   include "./dtype.pxi"
   include "./device.pxi"
   include "./string.pxi"
   include "./tensor.pxi"
   include "./function.pxi"
   _register_object_by_index(kTVMFFIFunction, Function)

Key Cython Classes
~~~~~~~~~~~~~~~~~~

``CObject`` (``object.pxi``)
  The Cython extension type at the root of the object hierarchy.  It holds a
  raw ``void* chandle`` pointing to the C++ :cpp:class:`tvm::ffi::Object`.
  Reference counting is managed through the ``__cinit__`` / ``__dealloc__``
  protocol: ``__cinit__`` initializes ``chandle`` to ``NULL``, and
  ``__dealloc__`` calls :c:func:`TVMFFIObjectDecRef` to release the reference.

  .. code-block:: cython

     cdef class CObject:
         cdef void* chandle

         def __cinit__(self):
             self.chandle = NULL

         def __dealloc__(self):
             if self.chandle != NULL:
                 CHECK_CALL(TVMFFIObjectDecRef(self.chandle))
                 self.chandle = NULL

:py:class:`~tvm_ffi.core.Object`
  A Python class that extends ``CObject`` with ``_ObjectSlotsMeta`` as its
  metaclass.  The metaclass enforces ``__slots__ = ()`` on all subclasses and
  broadens ``isinstance`` / ``issubclass`` checks to include ``CObject``
  instances.  :py:class:`~tvm_ffi.core.Object` also provides
  :py:meth:`same_as`, :py:meth:`_move`, ``__init_handle_by_constructor__``,
  and pickle support via ``__getstate__`` / ``__setstate__``.

:py:class:`~tvm_ffi.Function` (``function.pxi``)
  A Cython extension type that wraps a packed function handle.  Its
  ``__call__`` method packs Python arguments into a ``TVMFFIAny`` array via
  the argument setter factory (``TVMFFIPyArgSetterFactory_``), invokes the
  C function, and converts the result back to a Python object.

``TypeSchema``, ``TypeField``, ``TypeInfo`` (``type_info.pxi``)
  Python dataclasses built from C++ reflection metadata.  They expose field
  names, types, getters/setters, and methods for each registered object type.
  ``FieldGetter`` and ``FieldSetter`` are Cython extension types that read and
  write object fields at a computed memory offset using function pointers from
  the C type info struct.

Argument Packing
~~~~~~~~~~~~~~~~

When a :py:class:`~tvm_ffi.Function` is called, each Python argument is
converted into a ``TVMFFIAny`` value by the *argument setter factory*.  The
factory dispatches on the Python type of each argument and selects a
specialized setter function.  The dispatch is cached per Python type for
performance: the first call for a given type runs through the full
``isinstance`` chain; subsequent calls for the same type hit a cached C
function pointer directly.

The setter priority order (defined in ``TVMFFIPyArgSetterFactory_`` in
``base.pxi``) is:

1. ``None`` -- sets ``kTVMFFINone``
2. :py:class:`~tvm_ffi.core.Tensor` -- special handling for DLTensor
3. ``CObject`` subclasses -- pass the raw handle
4. ``ObjectRValueRef`` -- move semantics
5. ``__tvm_ffi_object__`` protocol -- custom conversion to FFI object
6. ``__dlpack_c_exchange_api__`` -- zero-copy DLPack C exchange
7. ``__cuda_stream__`` protocol -- CUDA stream handle
8. ``torch.Tensor`` -- fallback through DLPack
9. ``__dlpack__`` protocol -- DLPack through Python
10. ``bool``, ``Integral``, ``Real`` -- numeric scalars
11. ``dtype``, ``Device`` -- TVM-specific scalar types
12. ``PyNativeObject`` (``String``, ``Bytes``) -- zero-copy or encode
13. ``str``, ``bytes`` / ``bytearray`` -- UTF-8 encode or copy
14. ``tuple``, ``list`` -- recursively construct ``Array``
15. ``dict`` -- recursively construct ``Map``
16. ``ctypes.c_void_p`` -- opaque pointer
17. ``__tvm_ffi_opaque_ptr__`` protocol
18. Generic ``callable`` -- wrap as FFI Function
19. ``torch.dtype``, ``numpy.dtype`` -- data type conversion
20. ``__dlpack_data_type__``, ``__dlpack_device__`` protocols
21. ``__tvm_ffi_int__``, ``__tvm_ffi_float__``, ``__tvm_ffi_value__`` protocols
22. ``Exception`` -- convert to FFI Error
23. ``ObjectConvertible`` -- call ``.asobject()``
24. **Fallback** -- wrap as opaque Python object


Type Conversion System
----------------------

The explicit conversion API is located in ``python/tvm_ffi/_convert.py`` and
centers on a single entry point: :py:func:`tvm_ffi.convert`.  This function
mirrors the automatic argument conversion that happens inside packed function
calls, but is available for use in tests or when an explicit conversion is
desired.

The conversion priority is:

.. code-block:: python

   def convert(value):
       # 1. Pass-through: Object, PyNativeObject, bool, Number, c_void_p, dtype
       # 2. list / tuple  -> Array
       # 3. dict          -> Map
       # 4. str           -> String
       # 5. bytes         -> Bytes
       # 6. ObjectConvertible -> .asobject()
       # 7. callable      -> Function
       # 8. None          -> None
       # 9. __dlpack__    -> Tensor (via from_dlpack)
       # 10. torch.dtype / numpy.dtype -> dtype
       # 11. __dlpack_data_type__ -> dtype
       # 12. Exception    -> Error
       # 13. __tvm_ffi_object__ -> call protocol
       # 14. Protocol pass-through (__cuda_stream__, __tvm_ffi_opaque_ptr__, etc.)
       # 15. Fallback: wrap as opaque Python object

The difference between :py:func:`~tvm_ffi.convert` and the Cython argument
setter factory is that :py:func:`~tvm_ffi.convert` operates at the Python
level and returns Python wrapper objects, while the setter factory operates
at the C level, filling ``TVMFFIAny`` structs directly without creating
intermediate Python wrappers.


Object Registration
-------------------

The :py:func:`tvm_ffi.register_object` decorator (in ``python/tvm_ffi/registry.py``)
binds a Python class to its C++ counterpart through the type key system:

.. code-block:: python

   @tvm_ffi.register_object("testing.MyObject")
   class MyObject(tvm_ffi.Object):
       pass

The registration flow proceeds as follows:

1. **Look up the type index** -- ``core._object_type_key_to_index(type_key)``
   calls :c:func:`TVMFFITypeKeyToIndex` to resolve the string key
   (e.g. ``"testing.MyObject"``) to an integer type index that the C++ runtime
   assigned during static initialization.

2. **Register by index** -- ``core._register_object_by_index(type_index, cls)``
   reads the full :cpp:class:`TVMFFITypeInfo` struct from the C runtime,
   constructs ``TypeField``, ``TypeMethod``, and ``TypeInfo`` Python objects,
   and stores them in the global ``TYPE_INDEX_TO_CLS``, ``TYPE_INDEX_TO_INFO``,
   ``TYPE_KEY_TO_INFO``, and ``TYPE_CLS_TO_INFO`` lookup tables.

3. **Attach field properties and method wrappers** -- ``_add_class_attrs()``
   iterates over the fields and methods in ``TypeInfo``:

   - Each field becomes a Python ``property`` with a ``FieldGetter`` / ``FieldSetter``
     pair that reads/writes the C++ field at a known memory offset.
   - Each method becomes a Python callable that forwards to the underlying FFI
     function.  Instance methods receive ``self`` as the first argument;
     static methods are wrapped with ``staticmethod()``.
   - The ``__ffi_init__`` method is exposed as ``__c_ffi_init__`` and, if no
     explicit ``__init__`` exists, is also installed as ``__init__``.

4. **Set up copy support** -- ``_setup_copy_methods()`` installs ``__copy__``,
   ``__deepcopy__``, and ``__replace__`` based on whether the C++ type provides
   a ``__ffi_shallow_copy__`` method.  Types without shallow copy raise
   ``TypeError`` on copy attempts.  Container types (``Array``, ``Map``,
   ``List``, ``Dict``) support ``__deepcopy__`` through ``ffi.DeepCopy``.

When a function returns an object whose type index has not been registered in
Python, the Cython layer automatically creates a fallback class by walking the
C++ type hierarchy, ensuring every ancestor has a Python class, and
synthesizing a new class with the correct fields and methods.


Dataclass-style Classes (``@c_class``)
--------------------------------------

The :py:func:`tvm_ffi.dataclasses.c_class` decorator (in
``python/tvm_ffi/dataclasses/c_class.py``) provides a dataclass-like authoring
experience for C++ types that have been registered with the TVM-FFI reflection
system.

.. code-block:: python

   from tvm_ffi.dataclasses import c_class, field

   @c_class("example.MyClass")
   class MyClass:
       v_i64: int
       v_i32: int
       v_f64: float = field(default=0.0)
       v_f32: float = field(default_factory=lambda: 1.0)

   obj = MyClass(v_i64=4, v_i32=8)

The decorator's execution follows these steps:

1. **Retrieve type info** -- ``_lookup_or_register_type_info_from_type_key()``
   fetches or creates the ``TypeInfo`` for the given type key, which contains
   the C++ field metadata.

2. **Reconcile fields** -- ``_inspect_c_class_fields()`` resolves the Python
   type annotations via ``typing.get_type_hints()`` and matches them against
   the C++ field list.  Extra fields on either side raise ``ValueError``.
   A ``KW_ONLY`` sentinel annotation marks subsequent fields as keyword-only.

3. **Fill dataclass field descriptors** -- ``fill_dataclass_field()`` attaches
   default values or default factories from the Python class body (literals,
   ``field()`` specifications) to each ``TypeField``.

4. **Generate ``__init__``** -- ``method_init()`` builds an ``__init__`` method
   via dynamic code generation (``exec``-based, following the same pattern
   used by Python's ``dataclasses`` module).  The generated method:

   - Accepts positional and keyword-only parameters matching the field order.
   - Resolves ``MISSING`` defaults through factory functions.
   - Calls ``self.__ffi_init__(...)`` to invoke the C++ constructor.
   - Calls ``self.__post_init__()`` if defined on the class.

5. **Create the proxy class** -- ``type_info_to_cls()`` builds a new Python
   class with the correct bases (rooted at :py:class:`~tvm_ffi.core.Object`),
   field properties, method wrappers, and the generated ``__init__``.

6. **Set up copy methods** -- ``_setup_copy_methods()`` is called to provide
   ``__copy__`` / ``__deepcopy__`` / ``__replace__`` support.


Stub Generation
---------------

The ``tvm-ffi-stubgen`` CLI tool (in ``python/tvm_ffi/stub/``) generates inline
type stubs that give IDEs and type checkers accurate signatures for
FFI-generated functions and object attributes.

Running the tool:

.. code-block:: bash

   uv run tvm-ffi-stubgen python

The tool operates as follows:

1. **Load the compiled library** -- The tool imports the built Python package
   to access the C++ reflection registry at runtime.

2. **Scan source files** -- It finds marker comments in ``.py`` files:

   .. code-block:: python

      # tvm-ffi-stubgen(begin): global/${prefix}@${import_from}
      # ...existing content...
      # tvm-ffi-stubgen(end)

   These markers delimit regions that the tool rewrites in place.

3. **Generate code** -- For each marker region, the tool queries the
   reflection metadata and generates type-annotated stubs:

   - **Global function stubs** (``global/`` prefix) -- Generates function
     signatures with parameter types and return types derived from
     ``TypeSchema``.
   - **Object stubs** (``object/`` prefix) -- Generates field type
     annotations and method signatures for registered object types.
   - **Import sections** (``import-section``) -- Generates ``TYPE_CHECKING``
     guarded imports for the types referenced by the stubs.
   - **``__all__`` sections** -- Lists exported names.

4. **Write back** -- The tool replaces the content between markers while
   preserving the surrounding code.

The ``TypeSchema`` class (in ``type_info.pxi``) translates C++ type
information into Python typing syntax: ``Union`` becomes ``T1 | T2``,
``Optional`` becomes ``T | None``, containers like ``ffi.Array`` map to
``Array[T]``, and ``ffi.Function`` maps to ``Callable[..., Any]``.


Container Bindings
------------------

The container classes in ``python/tvm_ffi/container.py`` provide Pythonic
interfaces to the C++ container types:

:py:class:`tvm_ffi.Array`
  An immutable sequence, registered under ``ffi.Array``.  Implements
  :py:class:`collections.abc.Sequence`.  Supports indexing, slicing,
  iteration, ``__contains__``, concatenation (``+``), and ``len()``.
  Constructed from any iterable:

  .. code-block:: python

     a = tvm_ffi.Array([1, 2, 3])
     assert a[0] == 1
     assert list(a) == [1, 2, 3]

:py:class:`tvm_ffi.List`
  A mutable sequence, registered under ``ffi.List``.  Implements
  :py:class:`collections.abc.MutableSequence`.  Supports all ``list``
  operations including ``append``, ``insert``, ``pop``, ``reverse``,
  slice assignment, and slice deletion.

:py:class:`tvm_ffi.Map`
  An immutable mapping, registered under ``ffi.Map``.  Implements
  :py:class:`collections.abc.Mapping`.  Provides custom ``KeysView``,
  ``ValuesView``, and ``ItemsView`` classes that iterate using a
  forward-iterator functor obtained from the C++ runtime.

:py:class:`tvm_ffi.Dict`
  A mutable mapping, registered under ``ffi.Dict``.  Implements
  :py:class:`collections.abc.MutableMapping`.  Mutations happen directly
  on the shared underlying object (no copy-on-write).  Supports ``pop``,
  ``clear``, ``update``, and item deletion.

All container classes delegate element access to FFI function calls
(e.g., ``_ffi_api.ArrayGetItem``, ``_ffi_api.MapGetItem``).  The
iteration protocol for ``Map`` and ``Dict`` uses a stateful functor:
calling ``functor(0)`` returns the key, ``functor(1)`` returns the value,
and ``functor(2)`` advances the iterator and returns whether more items
remain.


Error Handling Bridge
---------------------

The error handling system in ``python/tvm_ffi/error.py`` provides bidirectional
exception translation across the FFI boundary.

Exception Registration
~~~~~~~~~~~~~~~~~~~~~~

:py:func:`tvm_ffi.register_error` maps C++ error kind strings to Python
exception classes:

.. code-block:: python

   @tvm_ffi.register_error
   class MyError(RuntimeError):
       pass

The built-in registrations include ``RuntimeError``, ``ValueError``,
``TypeError``, ``AttributeError``, ``KeyError``, ``IndexError``,
``AssertionError``, and ``MemoryError``.  The mapping is stored in two
dictionaries: ``ERROR_NAME_TO_TYPE`` (kind string to Python type) and
``ERROR_TYPE_TO_NAME`` (Python type to kind string).

Traceback Reconstruction
~~~~~~~~~~~~~~~~~~~~~~~~

When a C++ function raises an error, the FFI error object contains a
backtrace string with entries in the format
``File "path", line N, in func``.  The ``TracebackManager`` class
reconstructs a Python traceback chain from this string:

1. **Parse the backtrace** -- Extract ``(filename, lineno, func)`` tuples
   using a regex pattern.

2. **Create synthetic frames** -- For each entry, compile a minimal
   ``ast.parse("_getframe()")`` expression with the target filename, then
   replace the code object's ``co_name`` and ``co_firstlineno`` to point at
   the correct source location.  Executing this code object via ``eval``
   produces a ``types.FrameType`` pointing to the desired location.

3. **Chain tracebacks** -- Each frame is linked into a
   ``types.TracebackType`` chain, which is attached to the Python exception
   using ``with_traceback()``.

4. **Break reference cycles** -- The ``_with_append_backtrace`` function
   explicitly deletes local references to ``py_error`` and ``tb`` in a
   ``finally`` block to break the reference cycle between the traceback,
   the frame, and the exception.  This avoids delaying garbage collection
   of objects captured in the frame's locals.

C++ to Python Direction
~~~~~~~~~~~~~~~~~~~~~~~

When a packed function call returns an error code, the Cython
``Function.__call__`` method retrieves the FFI error object, looks up its
``kind`` in ``ERROR_NAME_TO_TYPE``, constructs the matching Python exception,
and appends the C++ backtrace as synthetic traceback frames.

Python to C++ Direction
~~~~~~~~~~~~~~~~~~~~~~~

When a Python callback raises an exception during an FFI call, the Cython
callback handler (``tvm_ffi_callback``) catches the exception and stores it
via ``set_last_ffi_error``.  The C++ side retrieves this error and can
re-raise it, preserving the Python traceback across the boundary.


Library Loading
---------------

The library loading system in ``python/tvm_ffi/libinfo.py`` locates and loads
the platform-specific shared library (``libtvm_ffi.so``, ``libtvm_ffi.dylib``,
or ``tvm_ffi.dll``).

:py:func:`tvm_ffi.libinfo.load_lib_ctypes` is called at package import time
in ``python/tvm_ffi/__init__.py``:

.. code-block:: python

   LIB = libinfo.load_lib_ctypes("apache-tvm-ffi", "tvm_ffi", "RTLD_GLOBAL")

The discovery strategy in ``_find_library_by_basename`` uses a multi-fallback
approach:

1. **RECORD metadata** -- Uses ``importlib.metadata.distribution`` to find the
   installed package's ``RECORD`` file, then scans it for the shared library
   path.  This is the most reliable path for pip/uv-installed packages.

2. **Build directories** -- Searches ``$PROJECT_ROOT/build/lib/`` and
   ``$PROJECT_ROOT/lib/`` relative to both the package location and the
   development source tree.

3. **Environment variables** -- Searches paths from ``LD_LIBRARY_PATH``
   (Linux), ``DYLD_LIBRARY_PATH`` (macOS), or ``PATH`` (Windows).

The library is loaded with ``RTLD_GLOBAL`` mode so that symbols are visible
to subsequently loaded shared libraries (e.g., extension modules).  On
Windows, ``os.add_dll_directory`` is called to ensure DLL dependencies can
be resolved.

An alternative loader, :py:func:`~tvm_ffi.libinfo.load_lib_module`, returns
a :py:class:`~tvm_ffi.Module` object instead of a ``ctypes.CDLL`` and is
used by downstream projects that need to load additional shared libraries
as TVM-FFI modules.

Helper functions such as :py:func:`~tvm_ffi.libinfo.find_include_path`,
:py:func:`~tvm_ffi.libinfo.find_cmake_path`, and
:py:func:`~tvm_ffi.libinfo.include_paths` assist with locating headers and
CMake files needed for compiling FFI extensions.


Further Reading
---------------

- :doc:`object_and_class`: The C++ object model and reference counting
  that underlies the Python :py:class:`~tvm_ffi.core.Object` class.
- :doc:`func_module`: The packed function calling convention and module
  system used by :py:class:`~tvm_ffi.Function` and :py:class:`~tvm_ffi.Module`.
- :doc:`any`: The ``Any`` / ``AnyView`` type-erased value containers that
  map to ``TVMFFIAny`` at the C ABI level.
- :doc:`containers`: The C++ container types (``Array``, ``Map``, ``List``,
  ``Dict``) that are wrapped by the Python container classes.
- :doc:`exception_handling`: The C++ error handling mechanisms that the
  Python error bridge translates.
- :doc:`reflection`: Reflection metadata, field registration, and stub generation.
