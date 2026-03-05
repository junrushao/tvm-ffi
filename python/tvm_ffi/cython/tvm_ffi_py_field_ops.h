/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
/*!
 * \file tvm_ffi_py_field_ops.h
 * \brief Type-specific field getters and setters for Python-defined TVM-FFI types.
 *
 * These functions are compiled by Cython's C compiler and used as
 * TVMFFIFieldGetter / TVMFFIFieldSetter function pointers during
 * field registration.
 */
#ifndef TVM_FFI_PY_FIELD_OPS_H_
#define TVM_FFI_PY_FIELD_OPS_H_

#include <string.h>
#include <tvm/ffi/c_api.h>

/* =========================================================================
 * Field Getters
 *
 * Each getter reads the native field value from *field and writes it
 * into *ret (a pre-zeroed TVMFFIAny with type_index == kTVMFFINone).
 * ========================================================================= */

/*! \brief Getter for int64_t fields (kTVMFFIInt). */
static int TVMFFIPyGetFieldInt64(void* field, TVMFFIAny* ret) {
  ret->type_index = kTVMFFIInt;
  ret->zero_padding = 0;
  ret->v_int64 = *(int64_t*)field;
  return 0;
}

/*! \brief Getter for bool fields stored as int64_t (kTVMFFIBool). */
static int TVMFFIPyGetFieldBool(void* field, TVMFFIAny* ret) {
  ret->type_index = kTVMFFIBool;
  ret->zero_padding = 0;
  ret->v_int64 = *(int64_t*)field;
  return 0;
}

/*! \brief Getter for double fields (kTVMFFIFloat). */
static int TVMFFIPyGetFieldFloat64(void* field, TVMFFIAny* ret) {
  ret->type_index = kTVMFFIFloat;
  ret->zero_padding = 0;
  ret->v_float64 = *(double*)field;
  return 0;
}

/*! \brief Getter for void* fields (kTVMFFIOpaquePtr). */
static int TVMFFIPyGetFieldOpaquePtr(void* field, TVMFFIAny* ret) {
  ret->type_index = kTVMFFIOpaquePtr;
  ret->zero_padding = 0;
  ret->v_ptr = *(void**)field;
  return 0;
}

/*! \brief Getter for DLDataType fields (kTVMFFIDataType, 4 bytes). */
static int TVMFFIPyGetFieldDLDataType(void* field, TVMFFIAny* ret) {
  ret->type_index = kTVMFFIDataType;
  ret->zero_padding = 0;
  ret->v_int64 = 0; /* zero the full 8-byte union first */
  ret->v_dtype = *(DLDataType*)field;
  return 0;
}

/*! \brief Getter for DLDevice fields (kTVMFFIDevice, 8 bytes). */
static int TVMFFIPyGetFieldDLDevice(void* field, TVMFFIAny* ret) {
  ret->type_index = kTVMFFIDevice;
  ret->zero_padding = 0;
  ret->v_device = *(DLDevice*)field;
  return 0;
}

/*! \brief Getter for Object* fields (any type_index >= kTVMFFIStaticObjectBegin). */
static int TVMFFIPyGetFieldObject(void* field, TVMFFIAny* ret) {
  TVMFFIObjectHandle obj = *(TVMFFIObjectHandle*)field;
  if (obj == NULL) {
    ret->type_index = kTVMFFINone;
    ret->zero_padding = 0;
    ret->v_int64 = 0;
  } else {
    ret->type_index = ((TVMFFIObject*)obj)->type_index;
    ret->zero_padding = 0;
    ret->v_ptr = obj;
    TVMFFIObjectIncRef(obj);
  }
  return 0;
}

/*!
 * \brief Getter for TVMFFIAny fields (kTVMFFIAny, 16 bytes).
 * Requires ret pre-initialized to kTVMFFINone (TVMFFIAnyViewToOwnedAny contract).
 */
static int TVMFFIPyGetFieldAny(void* field, TVMFFIAny* ret) {
  return TVMFFIAnyViewToOwnedAny((const TVMFFIAny*)field, ret);
}

/* =========================================================================
 * Field Setters
 *
 * Each setter writes a TVMFFIAny value into native storage at *field.
 * The value has already been converted from Python by the call manager's
 * SetArgument before reaching the setter.
 * ========================================================================= */

/*! \brief Setter for int64_t fields. Accepts kTVMFFIInt and kTVMFFIBool. */
static int TVMFFIPySetFieldInt64(void* field, const TVMFFIAny* value) {
  if (value->type_index == kTVMFFIInt || value->type_index == kTVMFFIBool) {
    *(int64_t*)field = value->v_int64;
    return 0;
  }
  TVMFFIErrorSetRaisedFromCStr("TypeError", "expected int value for int64 field");
  return -1;
}

/*! \brief Setter for bool fields (stored as int64_t). Accepts kTVMFFIBool and kTVMFFIInt. */
static int TVMFFIPySetFieldBool(void* field, const TVMFFIAny* value) {
  if (value->type_index == kTVMFFIBool || value->type_index == kTVMFFIInt) {
    *(int64_t*)field = value->v_int64;
    return 0;
  }
  TVMFFIErrorSetRaisedFromCStr("TypeError", "expected bool value for bool field");
  return -1;
}

/*! \brief Setter for double fields. Accepts kTVMFFIFloat and kTVMFFIInt. */
static int TVMFFIPySetFieldFloat64(void* field, const TVMFFIAny* value) {
  if (value->type_index == kTVMFFIFloat) {
    *(double*)field = value->v_float64;
    return 0;
  }
  if (value->type_index == kTVMFFIInt) {
    *(double*)field = (double)value->v_int64;
    return 0;
  }
  TVMFFIErrorSetRaisedFromCStr("TypeError", "expected float value for float64 field");
  return -1;
}

/*! \brief Setter for void* fields. Accepts kTVMFFIOpaquePtr. */
static int TVMFFIPySetFieldOpaquePtr(void* field, const TVMFFIAny* value) {
  if (value->type_index == kTVMFFIOpaquePtr) {
    *(void**)field = value->v_ptr;
    return 0;
  }
  TVMFFIErrorSetRaisedFromCStr("TypeError", "expected opaque pointer value");
  return -1;
}

/*! \brief Setter for DLDataType fields (4 bytes). Accepts kTVMFFIDataType. */
static int TVMFFIPySetFieldDLDataType(void* field, const TVMFFIAny* value) {
  if (value->type_index == kTVMFFIDataType) {
    *(DLDataType*)field = value->v_dtype;
    return 0;
  }
  TVMFFIErrorSetRaisedFromCStr("TypeError", "expected DataType value");
  return -1;
}

/*! \brief Setter for DLDevice fields (8 bytes). Accepts kTVMFFIDevice. */
static int TVMFFIPySetFieldDLDevice(void* field, const TVMFFIAny* value) {
  if (value->type_index == kTVMFFIDevice) {
    *(DLDevice*)field = value->v_device;
    return 0;
  }
  TVMFFIErrorSetRaisedFromCStr("TypeError", "expected Device value");
  return -1;
}

/*!
 * \brief Setter for Object* fields. Accepts objects (>= kTVMFFIStaticObjectBegin) and None.
 * Properly manages reference counts.
 */
static int TVMFFIPySetFieldObject(void* field, const TVMFFIAny* value) {
  TVMFFIObjectHandle* obj_ptr = (TVMFFIObjectHandle*)field;
  TVMFFIObjectHandle old = *obj_ptr;
  if (value->type_index == kTVMFFINone) {
    *obj_ptr = NULL;
  } else if (value->type_index >= kTVMFFIStaticObjectBegin) {
    TVMFFIObjectIncRef(value->v_ptr);
    *obj_ptr = (TVMFFIObjectHandle)value->v_ptr;
  } else {
    TVMFFIErrorSetRaisedFromCStr("TypeError", "expected Object or None for object field");
    return -1;
  }
  if (old != NULL) {
    TVMFFIObjectDecRef(old);
  }
  return 0;
}

/*!
 * \brief Setter for TVMFFIAny fields (16 bytes).
 * Copies the value via TVMFFIAnyViewToOwnedAny after releasing the old value.
 */
static int TVMFFIPySetFieldAny(void* field, const TVMFFIAny* value) {
  /* Release old value first */
  TVMFFIAny* dst = (TVMFFIAny*)field;
  if (dst->type_index >= kTVMFFIStaticObjectBegin && dst->v_ptr != NULL) {
    TVMFFIObjectDecRef((TVMFFIObjectHandle)dst->v_ptr);
  }
  dst->type_index = kTVMFFINone;
  dst->v_int64 = 0;
  return TVMFFIAnyViewToOwnedAny(value, dst);
}

/* =========================================================================
 * Raw Object Allocation
 *
 * Allocates a zero-initialized object of arbitrary size with a proper
 * TVMFFIObject header. Used by Python-defined types that don't have a
 * C++ class to call make_object on.
 * ========================================================================= */

/*! \brief Deleter for raw-allocated objects (paired with TVMFFIPyAllocRawObject). */
static void TVMFFIPyRawObjectDeleter(void* self, int flags) {
  (void)flags;
  free(self);
}

/*!
 * \brief Allocate a zero-initialized object of the given size and type_index.
 * \param total_size Total byte size (must be >= sizeof(TVMFFIObject) and 8-byte aligned).
 * \param type_index The type index to stamp into the header.
 * \param result Output: the new object handle with ref_count = 1.
 * \return 0 on success, -1 on failure.
 */
static int TVMFFIPyAllocRawObject(int32_t total_size, int32_t type_index,
                                  TVMFFIObjectHandle* result) {
  void* mem = calloc(1, (size_t)total_size);
  if (mem == NULL) {
    TVMFFIErrorSetRaisedFromCStr("RuntimeError", "Failed to allocate object memory");
    return -1;
  }
  TVMFFIObject* obj = (TVMFFIObject*)mem;
  /* combined_ref_count: both strong and weak start at 1 */
  obj->combined_ref_count = ((uint64_t)1 << 32) | (uint64_t)1;
  obj->type_index = type_index;
  obj->__padding = 0;
  obj->deleter = TVMFFIPyRawObjectDeleter;
  *result = (TVMFFIObjectHandle)obj;
  return 0;
}

#endif /* TVM_FFI_PY_FIELD_OPS_H_ */
