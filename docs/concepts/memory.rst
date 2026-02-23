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

Memory Management
=================

All heap objects in TVM-FFI are reference-counted via intrusive pointers. The
reference counting system combines strong and weak reference counts into a single
atomic 64-bit integer, enabling efficient two-stage deletion: the object destructor
runs when the strong count reaches zero, and memory is freed when the weak count
reaches zero.

The memory management implementation is split across several files:

- ``include/tvm/ffi/c_api.h`` -- C-level :cpp:class:`TVMFFIObject` header and deleter flags
- ``include/tvm/ffi/object.h`` -- :cpp:class:`~tvm::ffi::ObjectPtr`, :cpp:class:`~tvm::ffi::WeakObjectPtr`, and reference counting logic
- ``include/tvm/ffi/memory.h`` -- Allocator framework and :cpp:func:`~tvm::ffi::make_object`

Combined Reference Counter
---------------------------

The :cpp:member:`TVMFFIObject::combined_ref_count` field packs both the strong and
weak reference counts into a single ``uint64_t``. The strong reference count occupies
the lower 32 bits and the weak reference count occupies the upper 32 bits:

.. code-block:: text

   |<-------- 64 bits -------->|
   | weak (32 bits) | strong (32 bits) |

This encoding is defined by the following constants in the ``tvm::ffi::details`` namespace:

.. code-block:: cpp

   constexpr uint64_t kCombinedRefCountStrongOne = 1;
   constexpr uint64_t kCombinedRefCountWeakOne   = static_cast<uint64_t>(1) << 32;
   constexpr uint64_t kCombinedRefCountBothOne   = kCombinedRefCountWeakOne | kCombinedRefCountStrongOne;
   constexpr uint64_t kCombinedRefCountMaskUInt32 = (static_cast<uint64_t>(1) << 32) - 1;

**Rationale.** Packing both counts into a single word allows the common-case
deletion path (where both counts reach zero simultaneously) to be handled with
a single atomic operation, avoiding the extra atomic read of the weak count that
a two-word design would require. Incrementing and decrementing the strong count
remains a simple ``+1`` / ``-1`` on the combined value, because the strong count
sits in the low bits.

Platform-specific Atomics
~~~~~~~~~~~~~~~~~~~~~~~~~

Reference count operations use platform-specific atomic intrinsics to ensure
thread safety:

- **GCC/Clang**: ``__atomic_fetch_add``, ``__atomic_fetch_sub``, ``__atomic_load_n``,
  ``__atomic_compare_exchange_n``, and ``__atomic_thread_fence``.
- **MSVC**: ``_InterlockedIncrement64``, ``_InterlockedDecrement64``,
  ``_InlineInterlockedAdd64``, and ``_InterlockedCompareExchange64``.

Decrements use release semantics (``__ATOMIC_RELEASE``) to ensure that all prior
writes to the object are visible before the deleter runs. An acquire fence
(``__ATOMIC_ACQUIRE``) is issued only when the deleter actually needs to be
called, keeping the fast path lightweight.

ObjectPtr (Strong Reference)
-----------------------------

:cpp:class:`tvm::ffi::ObjectPtr\<T\> <tvm::ffi::ObjectPtr>` is the intrusive smart pointer that manages
strong reference counts. It is the building block for :cpp:class:`~tvm::ffi::ObjectRef`
and all typed object reference classes.

Lifetime Operations
~~~~~~~~~~~~~~~~~~~

- **Construction from raw pointer**: Calls ``Object::IncRef()`` to atomically
  increment the combined count by ``kCombinedRefCountStrongOne`` (i.e., ``+1``).
- **Destruction / reset**: Calls ``Object::DecRef()`` to decrement the strong
  count and trigger deletion when appropriate.
- **Copy**: Increments the strong reference count.
- **Move**: Transfers ownership by stealing the internal pointer and nulling out
  the source. No atomic operation is performed.

.. code-block:: cpp

   // Creating a strong reference
   ObjectPtr<MyObj> p1 = make_object<MyObj>(args...);  // refcount = 1

   // Copying increments the count
   ObjectPtr<MyObj> p2 = p1;                           // refcount = 2

   // Moving does NOT touch the count
   ObjectPtr<MyObj> p3 = std::move(p2);                // refcount = 2, p2 is null

   // Destruction decrements
   p3.reset();                                         // refcount = 1

Introspection
~~~~~~~~~~~~~

- :cpp:func:`ObjectPtr::use_count() <tvm::ffi::ObjectPtr::use_count>` -- Returns the current strong reference count by masking the
  low 32 bits of the combined counter.
- :cpp:func:`ObjectPtr::unique() <tvm::ffi::ObjectPtr::unique>` -- Returns ``true`` when ``use_count() == 1``.

ObjectRef
~~~~~~~~~

:cpp:class:`tvm::ffi::ObjectRef` wraps an ``ObjectPtr<Object>`` and serves as
the type-erased base class for all object references. Subclasses use macros like
:c:macro:`TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE` to add typed accessors
(``operator->``, ``get()``) that static-cast the internal pointer to the
concrete object type.

WeakObjectPtr (Weak Reference)
-------------------------------

:cpp:class:`tvm::ffi::WeakObjectPtr\<T\> <tvm::ffi::WeakObjectPtr>` holds a weak reference to an object.
It allows observing an object without preventing its destructor from running.

Lifetime Operations
~~~~~~~~~~~~~~~~~~~

- **Construction**: Calls ``Object::IncWeakRef()`` to atomically increment the
  combined count by ``kCombinedRefCountWeakOne`` (i.e., ``+1ULL << 32``).
- **Destruction / reset**: Calls ``Object::DecWeakRef()`` to decrement the weak
  count. If the weak count reaches zero and the strong count is already zero,
  the deleter is invoked with the ``kTVMFFIObjectDeleterFlagBitMaskWeak`` flag to
  free the memory.
- **Move**: Transfers ownership without any atomic operation, same as
  :cpp:class:`~tvm::ffi::ObjectPtr`.

Promoting a Weak Reference
~~~~~~~~~~~~~~~~~~~~~~~~~~~

:cpp:func:`WeakObjectPtr::lock() <tvm::ffi::WeakObjectPtr::lock>` attempts to promote a weak reference to a strong one.
It uses a compare-and-swap (CAS) loop on the combined counter:

1. Load the current combined count.
2. If the strong count (low 32 bits) is zero, the object is already dead -- return ``nullptr``.
3. Otherwise, attempt to atomically increment the strong count by one.
4. If the CAS succeeds, return a valid :cpp:class:`~tvm::ffi::ObjectPtr`. If another
   thread modified the counter, retry from step 1.

.. code-block:: cpp

   WeakObjectPtr<MyObj> weak = strong_ptr;  // weak ref created

   // Later, attempt to use the object
   if (ObjectPtr<MyObj> locked = weak.lock()) {
     // Object is still alive, use it
   } else {
     // Object has been destroyed
   }

:cpp:func:`WeakObjectPtr::expired() <tvm::ffi::WeakObjectPtr::expired>` provides a non-blocking check that returns ``true`` if the
strong count has reached zero. Note that the result may be stale by the time it
is used, so ``lock()`` should be preferred when the caller intends to access the
object.

Two-Stage Deletion
-------------------

TVM-FFI separates object destruction from memory deallocation to support weak
references safely. The :cpp:member:`TVMFFIObject::deleter` function pointer is
invoked with flags from :cpp:enum:`TVMFFIObjectDeleterFlagBitMask` to indicate
which action to perform:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Flag
     - Action
   * - ``kTVMFFIObjectDeleterFlagBitMaskStrong`` (``1 << 0``)
     - Call the object's destructor. The object becomes a "zombie": its fields
       are destroyed but its memory remains allocated.
   * - ``kTVMFFIObjectDeleterFlagBitMaskWeak`` (``1 << 1``)
     - Free the memory block.
   * - ``kTVMFFIObjectDeleterFlagBitMaskBoth`` (``0x3``)
     - Both actions combined. This is the fast path when strong and weak counts
       reach zero simultaneously.

The ``Object::DecRef()`` method implements the two-stage logic:

1. Atomically decrement the strong count with release semantics.
2. **Fast path**: If the value before the decrement was ``kCombinedRefCountBothOne``
   (strong=1, weak=1), both counts are now zero. Issue an acquire fence and call
   the deleter with ``kTVMFFIObjectDeleterFlagBitMaskBoth``. This handles the
   common case in a single atomic operation.
3. **Slow path**: If only the strong count reached zero (weak count is still
   nonzero), issue an acquire fence, call the deleter with
   ``kTVMFFIObjectDeleterFlagBitMaskStrong`` to run the destructor, then
   atomically decrement the weak count. If the weak count also reaches zero,
   call the deleter again with ``kTVMFFIObjectDeleterFlagBitMaskWeak`` to free
   the memory.

.. code-block:: text

   Strong reaches 0, weak > 0:
     deleter(obj, Strong)   -->  destructor runs, object is zombie
     ...
   Weak reaches 0:
     deleter(obj, Weak)     -->  memory freed

   Strong and weak both reach 0 at once:
     deleter(obj, Both)     -->  destructor + free in one call

Allocator Framework
--------------------

The allocator framework lives in ``include/tvm/ffi/memory.h`` and uses the
curiously recurring template pattern (CRTP) to allow different allocation
strategies.

ObjAllocatorBase
~~~~~~~~~~~~~~~~

:cpp:class:`tvm::ffi::details::ObjAllocatorBase\<Derived\> <tvm::ffi::details::ObjAllocatorBase>` is the CRTP base class. It provides two
template methods:

- ``make_object<T>(args...)`` -- Allocates a single object of type ``T``,
  constructs it in-place, initializes the :cpp:class:`TVMFFIObject` header
  (setting ``combined_ref_count`` to ``kCombinedRefCountBothOne``,
  ``type_index``, and ``deleter``), and returns an ``ObjectPtr<T>``.
- ``make_inplace_array<ArrayType, ElemType>(num_elems, args...)`` -- Allocates
  an object with a contiguous trailing array (see below).

SimpleObjAllocator
~~~~~~~~~~~~~~~~~~

:cpp:class:`tvm::ffi::details::SimpleObjAllocator` is the default allocator. It uses
aligned ``malloc`` / ``free`` for memory management:

- On non-MSVC platforms, ``std::malloc`` is used when the alignment requirement
  does not exceed ``alignof(std::max_align_t)``; otherwise ``posix_memalign`` is
  used.
- On MSVC, ``_aligned_malloc`` and ``_aligned_free`` are used.

The allocator defines a nested ``Handler<T>`` template that captures the
type-specific destructor and free operation as a static deleter function:

.. code-block:: cpp

   // Simplified view of Handler<T>::Deleter_
   static void Deleter_(void* objptr, int flags) {
     T* tptr = /* recover typed pointer from TVMFFIObject* */;
     if (flags & kTVMFFIObjectDeleterFlagBitMaskStrong) {
       tptr->T::~T();  // explicit non-virtual destructor call
     }
     if (flags & kTVMFFIObjectDeleterFlagBitMaskWeak) {
       AlignedFree(tptr);
     }
   }

Note that the destructor is called as ``tptr->T::~T()`` rather than
``tptr->~T()``. This explicitly invokes the concrete type's destructor,
avoiding reliance on virtual dispatch (which may not be available for all object
types).

make_object
~~~~~~~~~~~

:cpp:func:`tvm::ffi::make_object\<T\>(args...) <tvm::ffi::make_object>` is the primary factory function for creating
TVM-FFI objects. It instantiates a :cpp:class:`~tvm::ffi::details::SimpleObjAllocator` and delegates to its
``make_object`` method:

.. code-block:: cpp

   template <typename T, typename... Args>
   inline ObjectPtr<T> make_object(Args&&... args) {
     return details::SimpleObjAllocator().make_object<T>(std::forward<Args>(args)...);
   }

The returned ``ObjectPtr<T>`` has a strong count of 1 and a weak count of 1
(encoded as ``kCombinedRefCountBothOne``). The weak count of 1 represents the
implicit "weak reference" held by the strong reference itself, ensuring that
memory is not freed while any strong reference exists.

Inplace Array Allocation
--------------------------

:cpp:func:`tvm::ffi::make_inplace_array_object\<ArrayType, ElemType\>(count, args...) <tvm::ffi::make_inplace_array_object>`
allocates an object header and ``count`` elements of type ``ElemType`` in a
single contiguous memory block:

.. code-block:: text

   |<-- sizeof(ArrayType) -->|<-- count * sizeof(ElemType) -->|
   [ ArrayType header        | elem[0] | elem[1] | ...        ]

This layout is used by ``ArrayObj`` for cache-friendly element storage, avoiding
an extra pointer indirection and a separate heap allocation for the element buffer.

The ``ArrayHandler<ArrayType, ElemType>`` template enforces alignment constraints
(``alignof(ArrayType) % alignof(ElemType) == 0``) and computes the total
allocation size, rounding up to the array's alignment:

.. code-block:: cpp

   size_t size = sizeof(ArrayType) + sizeof(ElemType) * num_elems;
   constexpr size_t align = alignof(ArrayType);
   size_t aligned_size = (size + (align - 1)) & ~(align - 1);

Its deleter follows the same two-stage pattern as ``Handler<T>``: the
``kTVMFFIObjectDeleterFlagBitMaskStrong`` flag triggers the destructor, and the
``kTVMFFIObjectDeleterFlagBitMaskWeak`` flag frees the entire block.

Further Reading
----------------

- :doc:`object_and_class` -- Object system overview, type registration, and reflection
- :doc:`any` -- How objects are stored in :cpp:class:`~tvm::ffi::Any` and :cpp:class:`~tvm::ffi::AnyView`
- :doc:`abi_overview` -- C-level ABI details including :cpp:class:`TVMFFIObject` layout and reference counting APIs
