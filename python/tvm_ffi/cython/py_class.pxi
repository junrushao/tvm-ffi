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
"""Python-defined object registration: allocate type indices and register fields."""
import json


# ---------------------------------------------------------------------------
# TypeSchema origin → native layout mapping
# ---------------------------------------------------------------------------
# Maps TypeSchema.origin strings to (size, alignment, type_index) tuples.
# Object-ref types (str, bytes, Array, etc.) all use pointer storage.
_ORIGIN_NATIVE_LAYOUT = {
    "int": (8, 8, kTVMFFIInt),
    "float": (8, 8, kTVMFFIFloat),
    "bool": (8, 8, kTVMFFIBool),
    "ctypes.c_void_p": (8, 8, kTVMFFIOpaquePtr),
    "dtype": (4, 2, kTVMFFIDataType),
    "Device": (8, 4, kTVMFFIDevice),
    "Any": (16, 8, kTVMFFIAny),
}

# Origins that map to object-ref storage (TVMFFIObject*, 8 bytes, align 8).
_OBJECT_ORIGINS = frozenset({
    "str", "bytes", "Object", "Tensor",
    "Array", "List", "Map", "Dict",
    "Callable", "tuple",
})


cdef inline tuple _field_native_layout(object ty):
    """Return (size, alignment, field_static_type_index) for a TypeSchema."""
    cdef str origin = ty.origin
    layout = _ORIGIN_NATIVE_LAYOUT.get(origin)
    if layout is not None:
        return layout
    # Anything else is an object ref (custom types, Union, Optional, etc.)
    return (8, 8, kTVMFFIObject)


cdef inline TVMFFIFieldGetter _select_getter(int32_t type_index):
    """Return the appropriate getter function pointer for a field type index."""
    if type_index == kTVMFFIInt:
        return TVMFFIPyGetFieldInt64
    elif type_index == kTVMFFIBool:
        return TVMFFIPyGetFieldBool
    elif type_index == kTVMFFIFloat:
        return TVMFFIPyGetFieldFloat64
    elif type_index == kTVMFFIOpaquePtr:
        return TVMFFIPyGetFieldOpaquePtr
    elif type_index == kTVMFFIDataType:
        return TVMFFIPyGetFieldDLDataType
    elif type_index == kTVMFFIDevice:
        return TVMFFIPyGetFieldDLDevice
    elif type_index == kTVMFFIAny:
        return TVMFFIPyGetFieldAny
    elif type_index >= kTVMFFIStaticObjectBegin:
        return TVMFFIPyGetFieldObject
    else:
        raise ValueError(
            f"Unsupported field type index for getter: {type_index}. "
            f"Only int, bool, float, void*, DataType, Device, Any, "
            f"and Object (type_index >= {kTVMFFIStaticObjectBegin}) are supported."
        )


cdef inline TVMFFIFieldSetter _select_setter(int32_t type_index):
    """Return the appropriate setter function pointer for a field type index."""
    if type_index == kTVMFFIInt:
        return TVMFFIPySetFieldInt64
    elif type_index == kTVMFFIBool:
        return TVMFFIPySetFieldBool
    elif type_index == kTVMFFIFloat:
        return TVMFFIPySetFieldFloat64
    elif type_index == kTVMFFIOpaquePtr:
        return TVMFFIPySetFieldOpaquePtr
    elif type_index == kTVMFFIDataType:
        return TVMFFIPySetFieldDLDataType
    elif type_index == kTVMFFIDevice:
        return TVMFFIPySetFieldDLDevice
    elif type_index == kTVMFFIAny:
        return TVMFFIPySetFieldAny
    elif type_index >= kTVMFFIStaticObjectBegin:
        return TVMFFIPySetFieldObject
    else:
        raise ValueError(
            f"Unsupported field type index for setter: {type_index}. "
            f"Only int, bool, float, void*, DataType, Device, Any, "
            f"and Object (type_index >= {kTVMFFIStaticObjectBegin}) are supported."
        )


cdef inline int64_t _compute_flags(object py_field):
    """Compute TVMFFIFieldFlagBitMask from a Field descriptor."""
    cdef int64_t flags = kTVMFFIFieldFlagBitMaskWritable
    if py_field.default is not MISSING or py_field.default_factory is not MISSING:
        flags |= kTVMFFIFieldFlagBitMaskHasDefault
    if py_field.default_factory is not MISSING:
        flags |= kTVMFFIFieldFlagBitMaskDefaultFromFactory
    if not py_field.init:
        flags |= kTVMFFIFieldFlagBitMaskInitOff
    if not py_field.repr:
        flags |= kTVMFFIFieldFlagBitMaskReprOff
    if not py_field.hash:
        flags |= kTVMFFIFieldFlagBitMaskHashOff
    if not py_field.compare:
        flags |= kTVMFFIFieldFlagBitMaskCompareOff
    if py_field.kw_only:
        flags |= kTVMFFIFieldFlagBitMaskKwOnly
    return flags


cdef inline dict _type_schema_to_json(object ts):
    """Convert a TypeSchema to a JSON-compatible dict."""
    cdef dict result = {"type": ts.origin}
    if ts.args:
        result["args"] = [_type_schema_to_json(a) for a in ts.args]
    return result


cdef int64_t _compute_current_offset(int32_t type_index):
    """Compute the current end-of-fields offset for a type from its registered fields."""
    cdef const TVMFFITypeInfo* info = TVMFFIGetTypeInfo(type_index)
    if info == NULL:
        raise ValueError(f"Unknown type index: {type_index}")
    if info.num_fields > 0:
        # Use the last field's offset + size
        return info.fields[info.num_fields - 1].offset + info.fields[info.num_fields - 1].size
    # No fields yet on this type: start after parent's total_size.
    # Parent must have metadata with total_size registered.
    cdef const TVMFFITypeInfo* parent_info
    if info.type_depth > 0:
        parent_info = info.type_ancestors[info.type_depth - 1]
        if parent_info.metadata == NULL or parent_info.metadata.total_size <= 0:
            raise ValueError(
                f"Parent type '{bytearray_to_str(&parent_info.type_key)}' "
                f"does not have metadata with total_size registered. "
                f"Register __ffi_total_size__ on the parent before appending "
                f"fields to a child type."
            )
        return parent_info.metadata.total_size
    # Root type (should not happen in practice — ffi.Object has metadata)
    if info.metadata != NULL and info.metadata.total_size > 0:
        return info.metadata.total_size
    raise ValueError(
        f"Type '{bytearray_to_str(&info.type_key)}' has no metadata with total_size"
    )


cdef _register_one_field(int32_t type_index, object py_field, int64_t* current_offset):
    """Build a TVMFFIFieldInfo and register it for the given type."""
    cdef TVMFFIFieldInfo info
    cdef int64_t size, alignment
    cdef int32_t field_type_index

    # --- name ---
    name_bytes = c_str(py_field.name)
    cdef ByteArrayArg name_arg = ByteArrayArg(name_bytes)
    info.name = name_arg.cdata

    # --- doc ---
    cdef ByteArrayArg doc_arg
    if py_field.doc is not None:
        doc_bytes = c_str(py_field.doc)
        doc_arg = ByteArrayArg(doc_bytes)
        info.doc = doc_arg.cdata
    else:
        info.doc.data = NULL
        info.doc.size = 0

    # --- metadata (JSON with type_schema) ---
    metadata_str = json.dumps({"type_schema": _type_schema_to_json(py_field.ty)})
    metadata_bytes = c_str(metadata_str)
    cdef ByteArrayArg metadata_arg = ByteArrayArg(metadata_bytes)
    info.metadata = metadata_arg.cdata

    # --- flags ---
    info.flags = _compute_flags(py_field)

    # --- native layout ---
    layout = _field_native_layout(py_field.ty)
    size = layout[0]
    alignment = layout[1]
    field_type_index = layout[2]
    info.size = size
    info.alignment = alignment

    # --- offset (align up) ---
    current_offset[0] = (current_offset[0] + alignment - 1) & ~(alignment - 1)
    info.offset = current_offset[0]
    current_offset[0] += size

    # --- getter / setter ---
    info.getter = _select_getter(field_type_index)
    info.setter = <void*>_select_setter(field_type_index)

    # --- default value ---
    cdef TVMFFIAny default_any
    cdef int c_api_ret_code
    if py_field.default is not MISSING:
        default_any.type_index = kTVMFFINone
        default_any.v_int64 = 0
        TVMFFIPyPyObjectToFFIAny(
            TVMFFIPyArgSetterFactory_,
            <PyObject*>py_field.default,
            &default_any,
            &c_api_ret_code
        )
        CHECK_CALL(c_api_ret_code)
        info.default_value_or_factory = default_any
    elif py_field.default_factory is not MISSING:
        default_any.type_index = kTVMFFINone
        default_any.v_int64 = 0
        TVMFFIPyPyObjectToFFIAny(
            TVMFFIPyArgSetterFactory_,
            <PyObject*>py_field.default_factory,
            &default_any,
            &c_api_ret_code
        )
        CHECK_CALL(c_api_ret_code)
        info.default_value_or_factory = default_any
    else:
        info.default_value_or_factory.type_index = kTVMFFINone
        info.default_value_or_factory.v_int64 = 0

    # --- field_static_type_index ---
    info.field_static_type_index = field_type_index

    CHECK_CALL(TVMFFITypeRegisterField(type_index, &info))


# ---------------------------------------------------------------------------
# Type attribute registration helpers
# ---------------------------------------------------------------------------

# Attribute names that map to TVMFFITypeMetadata fields
_METADATA_ATTR_NAMES = frozenset({"__ffi_total_size__", "__ffi_doc__", "__ffi_structure__"})


cdef _register_type_attr_raw(int32_t type_index, str attr_name, object attr_value):
    """Register a single type attribute via TVMFFITypeRegisterAttr."""
    cdef TVMFFIAny c_value
    cdef int c_api_ret_code
    c_value.type_index = kTVMFFINone
    c_value.v_int64 = 0
    TVMFFIPyPyObjectToFFIAny(
        TVMFFIPyArgSetterFactory_,
        <PyObject*>attr_value,
        &c_value,
        &c_api_ret_code
    )
    CHECK_CALL(c_api_ret_code)
    attr_name_bytes = c_str(attr_name)
    cdef ByteArrayArg attr_name_arg = ByteArrayArg(attr_name_bytes)
    CHECK_CALL(TVMFFITypeRegisterAttr(type_index, attr_name_arg.cptr(), &c_value))


def _make_ffi_new(int32_t total_size, int32_t type_index):
    """Create a __ffi_new__ function that allocates an empty object."""
    def ffi_new():
        cdef TVMFFIObjectHandle handle
        CHECK_CALL(TVMFFIPyAllocRawObject(total_size, type_index, &handle))
        obj = Object.__new__(Object)
        (<CObject>obj).chandle = handle
        return obj
    return ffi_new


cdef _register_metadata_from_attrs(int32_t type_index, dict attrs):
    """Build TVMFFITypeMetadata from accumulated __ffi_*__ attrs and register it."""
    cdef TVMFFITypeMetadata metadata
    cdef ByteArrayArg doc_arg

    # total_size
    total_size = attrs.get("__ffi_total_size__", 0)
    metadata.total_size = <int32_t>total_size

    # doc
    doc = attrs.get("__ffi_doc__")
    if doc is not None:
        doc_bytes = c_str(doc)
        doc_arg = ByteArrayArg(doc_bytes)
        metadata.doc = doc_arg.cdata
    else:
        metadata.doc.data = NULL
        metadata.doc.size = 0

    # structure (structural_eq_hash_kind)
    structure = attrs.get("__ffi_structure__", kTVMFFISEqHashKindUnsupported)
    metadata.structural_eq_hash_kind = <TVMFFISEqHashKind><int32_t>structure

    # creator is always NULL for Python-defined types
    metadata.creator = NULL

    CHECK_CALL(TVMFFITypeRegisterMetadata(type_index, &metadata))

    # Register __ffi_new__ when total_size is known
    if total_size > 0:
        ffi_new_func = _make_ffi_new(total_size, type_index)
        _register_type_attr_raw(type_index, "__ffi_new__", ffi_new_func)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def py_class_make_type(str type_key, int32_t parent_type_index):
    """Allocate a type index for a Python-defined TVM-FFI type.

    Parameters
    ----------
    type_key : str
        The unique key that identifies this type in the FFI registry.
    parent_type_index : int
        The type index of the parent type.

    Returns
    -------
    int
        The allocated type_index.
    """
    cdef const TVMFFITypeInfo* parent_info = TVMFFIGetTypeInfo(parent_type_index)
    if parent_info == NULL:
        raise ValueError(f"Unknown parent type index: {parent_type_index}")
    cdef int32_t type_depth = parent_info.type_depth + 1
    type_key_bytes = c_str(type_key)
    cdef ByteArrayArg type_key_arg = ByteArrayArg(type_key_bytes)
    cdef int32_t type_index = TVMFFITypeGetOrAllocIndex(
        type_key_arg.cptr(),
        -1,            # static_type_index = -1 (dynamic)
        type_depth,
        0,             # num_child_slots
        1,             # child_slots_can_overflow
        parent_type_index,
    )
    return type_index


def py_class_append_field(int32_t type_index, object py_field):
    """Register one field of a Python-defined type.

    The field offset is computed automatically from the type's existing
    fields (or parent layout if this is the first field).

    Parameters
    ----------
    type_index : int
        The type index from :func:`py_class_make_type`.
    py_field : Field
        A :class:`~tvm_ffi.dataclasses.Field` descriptor.
    """
    cdef int64_t offset = _compute_current_offset(type_index)
    _register_one_field(type_index, py_field, &offset)


def register_type_attr(int32_t type_index, str attr_name, object attr_value):
    """Register a type attribute by name.

    Special attribute names are dispatched to ``TVMFFITypeRegisterMetadata``:

    - ``__ffi_total_size__`` (int): total byte size of the object struct
    - ``__ffi_doc__`` (str): docstring for the type
    - ``__ffi_structure__`` (int): structural eq/hash kind

    All attributes (including the special ones above) are also registered
    via ``TVMFFITypeRegisterAttr`` for lookup with ``_lookup_type_attr``.

    Parameters
    ----------
    type_index : int
        The type index from :func:`py_class_make_type`.
    attr_name : str
        The attribute name.
    attr_value : Any
        The attribute value.
    """
    # Always register as a type attr for lookup
    _register_type_attr_raw(type_index, attr_name, attr_value)
    # For metadata attrs, also update TVMFFITypeMetadata
    if attr_name in _METADATA_ATTR_NAMES:
        _register_metadata_from_attrs(type_index, {attr_name: attr_value})


def get_type_attr(int32_t type_index, str attr_name):
    """Look up a type attribute by name.

    Parameters
    ----------
    type_index : int
        The type index.
    attr_name : str
        The attribute name.

    Returns
    -------
    Any or None
        The attribute value, or None if not found.
    """
    return _lookup_type_attr(type_index, attr_name)
