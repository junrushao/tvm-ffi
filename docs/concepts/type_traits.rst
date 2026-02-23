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

Type Traits and Conversion
==========================

TVM-FFI stores every value in a type-erased 16-byte tagged union
(:cpp:class:`TVMFFIAny`), which underpins both :cpp:class:`tvm::ffi::Any` and
:cpp:class:`tvm::ffi::AnyView` (see :doc:`any`). The **type traits** system
defines how each C++ type is converted to and from this representation. It is the
central mechanism that makes the packed function calling convention work: callers
store arguments into :cpp:class:`~tvm::ffi::AnyView` slots, and callees extract
typed values back out, all with compile-time dispatch and no virtual calls.

The primary header is ``include/tvm/ffi/type_traits.h``. Additional
specializations live alongside the types they serve (e.g.,
``include/tvm/ffi/string.h`` for :cpp:class:`~tvm::ffi::String`,
``include/tvm/ffi/dtype.h`` for ``DLDataType``).


TypeTraits<T> Structure
-----------------------

:cpp:class:`tvm::ffi::TypeTraits\<T\>` is a struct template. The primary
(unspecialized) template disables conversion:

.. code-block:: cpp

   template <typename, typename = void>
   struct TypeTraits {
     static constexpr bool convert_enabled = false;
     static constexpr bool storage_enabled = false;
   };

Each specialization inherits from :cpp:class:`tvm::ffi::TypeTraitsBase` and
provides the following static members:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Member
     - Purpose
   * - ``static constexpr bool convert_enabled``
     - ``true`` when the type can participate in :cpp:class:`~tvm::ffi::AnyView`
       conversions. Inherited from :cpp:class:`~tvm::ffi::TypeTraitsBase`.
   * - ``static constexpr bool storage_enabled``
     - ``true`` when the type can be stored inside an owning
       :cpp:class:`~tvm::ffi::Any` or a container element. ``false`` for
       view-only types such as ``const char*`` and ``DLTensor*``.
   * - ``static constexpr int32_t field_static_type_index``
     - The :cpp:enum:`TVMFFITypeIndex` tag written into
       :cpp:member:`TVMFFIAny::type_index` when a value of this type is stored.
   * - ``CopyToAnyView(const T& value, TVMFFIAny* dst)``
     - Write a non-owning representation of *value* into *dst*.
       Used when constructing an :cpp:class:`~tvm::ffi::AnyView`.
   * - ``MoveToAny(T value, TVMFFIAny* dst)``
     - Move *value* into an owning :cpp:class:`~tvm::ffi::Any`.
       For objects this transfers the reference without incrementing the count.
   * - ``CheckAnyStrict(const TVMFFIAny* src) -> bool``
     - Return ``true`` if *src* was produced by ``CopyToAnyView`` or
       ``MoveToAny`` of the same type ``T``. No coercion is attempted.
   * - ``CopyFromAnyViewAfterCheck(const TVMFFIAny* src) -> T``
     - Extract a ``T`` from *src* after ``CheckAnyStrict`` has returned ``true``.
       For objects this creates a new reference (increments the count).
   * - ``MoveFromAnyAfterCheck(TVMFFIAny* src) -> T``
     - Move-extract a ``T`` from an owning ``Any``. Resets *src* to ``None``.
   * - ``TryCastFromAnyView(const TVMFFIAny* src) -> std::optional<T>``
     - Attempt a potentially **lenient** conversion. May apply coercion rules
       (e.g., ``int`` to ``double``). Returns ``std::nullopt`` on failure.
   * - ``GetMismatchTypeInfo(const TVMFFIAny* src) -> std::string``
     - Return a human-readable type description for error messages when
       conversion fails.
   * - ``TypeStr() -> std::string``
     - Return the type key string for ``T`` (e.g., ``"int"``, ``"ffi.Str"``).

The helper alias :cpp:type:`tvm::ffi::TypeTraitsNoCR\<T\>` strips ``const`` and
reference qualifiers before looking up the traits, so
``TypeTraitsNoCR<const int&>`` resolves to ``TypeTraits<int>``.


Built-in Specializations
------------------------

Primitive Types
~~~~~~~~~~~~~~~

Integer and floating-point types are matched through SFINAE-enabled partial
specializations. All integral types (``int``, ``int32_t``, ``int64_t``,
``uint64_t``, etc.) share a single specialization gated by
``std::is_integral_v<Int>``. Similarly, all floating-point types (``float``,
``double``) share a specialization gated by ``std::is_floating_point_v<Float>``.

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - C++ Type
     - type_index
     - Notes
   * - Integer types
     - :cpp:enumerator:`kTVMFFIInt`
     - Stored in :cpp:member:`~TVMFFIAny::v_int64`.
       Unsigned 64-bit values that exceed ``int64_t`` range throw
       :cpp:class:`~tvm::ffi::Error` (``OverflowError``).
   * - ``bool``
     - :cpp:enumerator:`kTVMFFIBool`
     - ``TryCastFromAnyView`` accepts both ``kTVMFFIBool`` and ``kTVMFFIInt``.
   * - :cpp:class:`~tvm::ffi::StrictBool`
     - :cpp:enumerator:`kTVMFFIBool`
     - Unlike ``bool``, rejects implicit conversion from ``int``.
   * - Floating-point types
     - :cpp:enumerator:`kTVMFFIFloat`
     - ``TryCastFromAnyView`` accepts ``kTVMFFIFloat``, ``kTVMFFIInt``, and
       ``kTVMFFIBool`` (int-to-float coercion).
   * - ``void*``
     - :cpp:enumerator:`kTVMFFIOpaquePtr`
     - ``TryCastFromAnyView`` also accepts ``kTVMFFINone`` (returning ``nullptr``).
   * - ``DLDevice``
     - :cpp:enumerator:`kTVMFFIDevice`
     - Strict: only ``kTVMFFIDevice`` accepted.
   * - ``DLDataType``
     - :cpp:enumerator:`kTVMFFIDataType`
     - Strict: only ``kTVMFFIDataType`` accepted.
   * - ``std::nullptr_t``
     - :cpp:enumerator:`kTVMFFINone`
     - Always stores ``v_int64 = 0``.
   * - Integral enums
     - :cpp:enumerator:`kTVMFFIInt`
     - ``std::is_enum_v<T>`` with integral underlying type.
       Stored and extracted as ``int64_t`` with a static cast.

All primitive types are POD -- ``MoveFromAnyAfterCheck`` simply delegates to
``CopyFromAnyViewAfterCheck`` because there is no ownership to transfer.

.. code-block:: cpp

   // Integer stored as kTVMFFIInt
   ffi::AnyView iv = 42;          // CopyToAnyView<int>
   int x = iv.cast<int>();        // TryCastFromAnyView<int> -> 42

   // Float accepts int via TryCastFromAnyView coercion
   double y = iv.cast<double>();  // TryCastFromAnyView<double> -> 42.0

String Types
~~~~~~~~~~~~

Strings have multiple representations in TVM-FFI, and the type traits handle
conversion between them:

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - C++ Type
     - type_index
     - Notes
   * - ``const char*``
     - :cpp:enumerator:`kTVMFFIRawStr`
     - Non-owning; ``storage_enabled = false``.
       ``MoveToAny`` promotes to an owned :cpp:class:`~tvm::ffi::String`.
   * - ``char[N]``
     - :cpp:enumerator:`kTVMFFIRawStr`
     - Same as ``const char*``; ``storage_enabled = false``.
   * - :cpp:class:`~tvm::ffi::String`
     - ``kTVMFFISmallStr`` or ``kTVMFFIStr``
     - ``TryCastFromAnyView`` also accepts ``kTVMFFIRawStr``
       (copies the raw pointer into an owned ``String``).
   * - :cpp:class:`~tvm::ffi::Bytes`
     - ``kTVMFFISmallBytes`` or ``kTVMFFIBytes``
     - ``TryCastFromAnyView`` also accepts ``kTVMFFIByteArrayPtr``.
   * - ``std::string``
     - ``kTVMFFIRawStr`` (view)
     - Uses :cpp:class:`~tvm::ffi::FallbackOnlyTraitsBase` to accept
       ``const char*``, ``TVMFFIByteArray*``, ``Bytes``, and ``String``
       via ``ConvertFallbackValue``.

.. code-block:: cpp

   // Raw string literal -> kTVMFFIRawStr (non-owning view)
   ffi::AnyView sv = "hello";

   // Extract as owned String (copies the raw pointer data)
   ffi::String s = sv.cast<ffi::String>();

   // Extract as std::string (via FallbackOnlyTraitsBase chain)
   std::string cpp_str = sv.cast<std::string>();

Object Types
~~~~~~~~~~~~

All types derived from :cpp:class:`~tvm::ffi::ObjectRef` are handled by the
:cpp:class:`tvm::ffi::ObjectRefTypeTraitsBase\<TObjRef\>` base class, which
provides a complete set of trait methods. The default specialization for
``ObjectRef`` subclasses is enabled via SFINAE:

.. code-block:: cpp

   template <typename TObjRef>
   struct TypeTraits<TObjRef,
                     std::enable_if_t<std::is_base_of_v<ObjectRef, TObjRef> &&
                                      use_default_type_traits_v<TObjRef>>>
       : public ObjectRefTypeTraitsBase<TObjRef> {};

Key behaviors of :cpp:class:`~tvm::ffi::ObjectRefTypeTraitsBase`:

- ``CopyToAnyView`` stores the raw :cpp:class:`TVMFFIObject` pointer and sets
  ``type_index`` to the object's runtime type index.
- ``MoveToAny`` transfers ownership without incrementing the reference count.
- ``CheckAnyStrict`` verifies the type index against the object's type hierarchy
  using ``IsObjectInstance<ContainerType>``.
- Nullable references (``_type_is_nullable = true``) also accept
  :cpp:enumerator:`kTVMFFINone`.

Raw object pointers (``TObject*`` where ``TObject`` derives from
:cpp:class:`~tvm::ffi::Object`) have a separate specialization that supports
non-owning views. The ``MoveToAny`` for raw pointers increments the reference
count since the original pointer does not own the object.

Optional<T>
~~~~~~~~~~~

:cpp:class:`tvm::ffi::Optional\<T\>` wraps an underlying ``TypeTraits<T>`` and
additionally accepts ``kTVMFFINone`` in both ``CheckAnyStrict`` and
``TryCastFromAnyView``. This makes ``Optional<T>`` the idiomatic way to handle
nullable values in function signatures:

.. code-block:: cpp

   ffi::Any value = nullptr;
   auto opt = value.cast<ffi::Optional<ffi::String>>();
   // opt.has_value() == false

   ffi::Any str_value = ffi::String("hello");
   auto opt2 = str_value.cast<ffi::Optional<ffi::String>>();
   // opt2.has_value() == true, *opt2 == "hello"


Conversion Strictness Levels
-----------------------------

The :cpp:class:`~tvm::ffi::AnyView` and :cpp:class:`~tvm::ffi::Any` classes
expose three extraction methods that differ in strictness and error handling.
Each method delegates to a different combination of ``TypeTraits<T>`` functions:

.. list-table::
   :header-rows: 1
   :widths: 18 22 30 30

   * - Method
     - Delegates to
     - Coercion
     - On Failure
   * - :cpp:func:`cast\<T\>() <tvm::ffi::AnyView::cast>`
     - ``TryCastFromAnyView``
     - Yes (lenient)
     - Throws :cpp:class:`~tvm::ffi::Error` (``TypeError``)
   * - :cpp:func:`try_cast\<T\>() <tvm::ffi::AnyView::try_cast>`
     - ``TryCastFromAnyView``
     - Yes (lenient)
     - Returns ``std::nullopt``
   * - :cpp:func:`as\<T\>() <tvm::ffi::AnyView::as>`
     - ``CheckAnyStrict`` + ``CopyFromAnyViewAfterCheck``
     - No (strict)
     - Returns ``std::nullopt``

The distinction between ``CheckAnyStrict`` and ``TryCastFromAnyView`` is the
heart of the two-tier design:

- **Strict** (``CheckAnyStrict``): returns ``true`` only if the stored value was
  produced by the same type's ``CopyToAnyView`` or ``MoveToAny``. For example,
  an ``int`` stored in the ``Any`` will not pass ``CheckAnyStrict`` for
  ``double``.

- **Lenient** (``TryCastFromAnyView``): may apply widening coercions. For
  example, ``TypeTraits<double>::TryCastFromAnyView`` will accept a stored
  ``int`` or ``bool`` and perform the numeric conversion.

.. code-block:: cpp

   ffi::Any value = 42;  // stored as kTVMFFIInt

   // cast<double>() succeeds: TryCastFromAnyView allows int -> double
   double d = value.cast<double>();  // 42.0

   // as<double>() fails: CheckAnyStrict requires kTVMFFIFloat
   std::optional<double> opt = value.as<double>();  // std::nullopt

   // as<int64_t>() succeeds: CheckAnyStrict matches kTVMFFIInt
   std::optional<int64_t> opt_int = value.as<int64_t>();  // 42

This two-tier design is critical for container types such as
:cpp:class:`~tvm::ffi::Array\<T\>`. An ``Array<T>`` maintains the invariant
that ``CheckAnyStrict`` holds for every element. When converting an
``Array<ObjectRef>`` to ``Array<MyObject>``, the strict check determines whether
each element already has the right type or needs recursive conversion.


Fallback Traits
---------------

FallbackOnlyTraitsBase
~~~~~~~~~~~~~~~~~~~~~~

:cpp:class:`tvm::ffi::FallbackOnlyTraitsBase\<T, FallbackTypes...\>` defines
a ``TryCastFromAnyView`` that tries each ``FallbackType`` in order. When a
fallback type's ``TryCastFromAnyView`` succeeds, the result is passed to
``TypeTraits<T>::ConvertFallbackValue(FallbackType)`` to produce the final ``T``.

This is used by ``TypeTraits<std::string>``, which accepts multiple source
representations:

.. code-block:: cpp

   template <>
   struct TypeTraits<std::string>
       : public FallbackOnlyTraitsBase<std::string,
                                       const char*,
                                       TVMFFIByteArray*,
                                       Bytes,
                                       String> {
     // CopyToAnyView, MoveToAny defined directly ...

     static std::string ConvertFallbackValue(const char* src) {
       return std::string(src);
     }
     static std::string ConvertFallbackValue(String src) {
       return src.operator std::string();
     }
     // ... other ConvertFallbackValue overloads
   };

The ``storage_enabled`` flag is ``false`` for ``FallbackOnlyTraitsBase``
because fallback types are meant only for conversion, not for direct storage
in containers.

.. note::

   ``bool`` must never appear in the ``FallbackTypes`` parameter pack. Because
   ``TypeTraits<bool>::TryCastFromAnyView`` accepts ``kTVMFFIInt``, using
   ``bool`` as a fallback would silently intercept integers. Use
   :cpp:class:`~tvm::ffi::StrictBool` instead. A ``static_assert`` enforces this
   at compile time.

ObjectRefWithFallbackTraitsBase
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:cpp:class:`tvm::ffi::ObjectRefWithFallbackTraitsBase\<ObjectRefType, FallbackTypes...\>`
combines the standard :cpp:class:`~tvm::ffi::ObjectRefTypeTraitsBase` with
a fallback chain. Its ``TryCastFromAnyView`` first tries the normal object cast;
if that fails, it tries each ``FallbackType`` in order and calls
``TypeTraits<ObjectRefType>::ConvertFallbackValue`` on the result.

This enables implicit construction of object types from primitive values in
function argument positions. For example, an expression type ``TPrimExpr`` might
define a fallback from ``int``, so that calling ``f(42)`` automatically wraps
the integer as an expression object:

.. code-block:: cpp

   // Hypothetical usage pattern:
   template <>
   struct TypeTraits<TPrimExpr>
       : public ObjectRefWithFallbackTraitsBase<TPrimExpr, int64_t, double> {
     static TPrimExpr ConvertFallbackValue(int64_t value) {
       return MakeConstInt(value);
     }
     static TPrimExpr ConvertFallbackValue(double value) {
       return MakeConstFloat(value);
     }
   };

   // Now a packed function expecting TPrimExpr can be called with a plain int:
   ffi::Function f = ...;
   f(42);  // 42 is auto-wrapped as TPrimExpr via fallback


AnyView to Any Conversion
--------------------------

When an :cpp:class:`~tvm::ffi::AnyView` (non-owning) is assigned to an
:cpp:class:`~tvm::ffi::Any` (owning), ownership must be established. The helper
function ``details::InplaceConvertAnyViewToAny`` handles this in-place:

.. code-block:: cpp

   void InplaceConvertAnyViewToAny(TVMFFIAny* data, size_t extra_any_bytes = 0);

The conversion depends on the stored ``type_index``:

**Object types** (``type_index >= kTVMFFIStaticObjectBegin``):
  The object's reference count is incremented via
  ``ObjectUnsafe::IncRefObjectHandle``. The pointer value is unchanged.

**Raw strings** (``kTVMFFIRawStr``):
  The ``const char*`` does not own its data. It is copied into a new, owned
  :cpp:class:`~tvm::ffi::String` object. The ``TVMFFIAny`` is updated in-place
  to point to the new string object with ``type_index`` set to
  ``kTVMFFIStr`` (or ``kTVMFFISmallStr`` if small enough).

**Byte array pointers** (``kTVMFFIByteArrayPtr``):
  Similar to raw strings: the pointed-to ``TVMFFIByteArray`` is copied into an
  owned :cpp:class:`~tvm::ffi::Bytes` object.

**Object rvalue references** (``kTVMFFIObjectRValueRef``):
  The rvalue reference is consumed. The pointer at the source address is set to
  ``nullptr`` to prevent double-move, and ownership transfers directly.

**Atomic types** (``kTVMFFINone``, ``kTVMFFIInt``, ``kTVMFFIFloat``, etc.):
  No action needed. The value is already stored inline and has no external
  resources.

This conversion is invoked automatically by the ``Any(const AnyView&)``
constructor:

.. code-block:: cpp

   ffi::AnyView view = "hello";  // kTVMFFIRawStr, points to string literal
   ffi::Any owned = view;        // InplaceConvertAnyViewToAny copies to owned String


Helper Utilities
----------------

TypeTraitsNoCR
~~~~~~~~~~~~~~

.. code-block:: cpp

   template <typename T>
   using TypeTraitsNoCR = TypeTraits<std::remove_const_t<std::remove_reference_t<T>>>;

Strips ``const`` and reference qualifiers before trait lookup. This ensures that
``TypeTraitsNoCR<const int&>`` resolves to ``TypeTraits<int>``.

TypeToFieldStaticTypeIndex
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: cpp

   template <typename T, typename = void>
   struct TypeToFieldStaticTypeIndex {
     static constexpr int32_t value = TypeIndex::kTVMFFIAny;
   };

Returns the ``field_static_type_index`` from ``TypeTraits<T>`` if conversion is
enabled, or ``kTVMFFIAny`` as a fallback. This is used by the reflection system
to record the static type of object fields.

TypeToRuntimeTypeIndex
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: cpp

   template <typename T, typename = void>
   struct TypeToRuntimeTypeIndex {
     static int32_t v() { return TypeToFieldStaticTypeIndex<T>::value; }
   };

For :cpp:class:`~tvm::ffi::ObjectRef` subclasses, this returns the dynamically
allocated runtime type index (``T::ContainerType::RuntimeTypeIndex()``). For
other types, it falls back to the static field type index. This is used at
runtime when the actual type index of an object needs to be queried.

use_default_type_traits_v
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: cpp

   template <typename T>
   inline constexpr bool use_default_type_traits_v = true;

This variable template controls whether an :cpp:class:`~tvm::ffi::ObjectRef`
subclass uses the default ``ObjectRefTypeTraitsBase`` specialization. Types that
need custom traits (such as :cpp:class:`~tvm::ffi::String` or
:cpp:class:`~tvm::ffi::Optional`) set this to ``false`` and provide their own
full ``TypeTraits`` specialization.


Further Reading
---------------

- :doc:`any`: The :cpp:class:`~tvm::ffi::Any` and :cpp:class:`~tvm::ffi::AnyView`
  containers that type traits convert to and from
- :doc:`func_module`: How type traits enable the packed function calling convention
  with automatic argument conversion
- :doc:`object_and_class`: Object reference type traits and the
  :cpp:class:`~tvm::ffi::ObjectRef` hierarchy
- :doc:`containers`: Container types and their ``CheckAnyStrict`` invariants
- :doc:`reflection`: TypeSchema and reflection metadata
