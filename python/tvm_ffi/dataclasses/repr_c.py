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
"""C++ layout representation for Python-defined FFI dataclasses."""

from __future__ import annotations

import re
from typing import Any

_CPP_KEYWORDS: frozenset[str] = frozenset(
    {
        "alignas",
        "alignof",
        "and",
        "and_eq",
        "asm",
        "atomic_cancel",
        "atomic_commit",
        "atomic_noexcept",
        "auto",
        "bitand",
        "bitor",
        "bool",
        "break",
        "case",
        "catch",
        "char",
        "char8_t",
        "char16_t",
        "char32_t",
        "class",
        "compl",
        "concept",
        "const",
        "consteval",
        "constexpr",
        "constinit",
        "const_cast",
        "continue",
        "co_await",
        "co_return",
        "co_yield",
        "decltype",
        "default",
        "delete",
        "do",
        "double",
        "dynamic_cast",
        "else",
        "enum",
        "explicit",
        "export",
        "extern",
        "false",
        "float",
        "for",
        "friend",
        "goto",
        "if",
        "inline",
        "int",
        "long",
        "mutable",
        "namespace",
        "new",
        "noexcept",
        "not",
        "not_eq",
        "nullptr",
        "operator",
        "or",
        "or_eq",
        "private",
        "protected",
        "public",
        "reflexpr",
        "register",
        "reinterpret_cast",
        "requires",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "static_assert",
        "static_cast",
        "struct",
        "switch",
        "synchronized",
        "template",
        "this",
        "thread_local",
        "throw",
        "true",
        "try",
        "typedef",
        "typeid",
        "typename",
        "union",
        "unsigned",
        "using",
        "virtual",
        "void",
        "volatile",
        "wchar_t",
        "while",
        "xor",
        "xor_eq",
    }
)

_IDENT_RE = re.compile(r"[^0-9A-Za-z_]")

_CPP_FIELD_STORAGE_TYPES: dict[str, str] = {
    "int": "int64_t",
    "float": "double",
    "bool": "bool",
    "ctypes.c_void_p": "void*",
    "dtype": "DLDataType",
    "Device": "DLDevice",
    "Any": "::tvm::ffi::Any",
    "str": "::tvm::ffi::Any",
    "bytes": "::tvm::ffi::Any",
    "Optional": "::tvm::ffi::Any",
    "Union": "::tvm::ffi::Any",
}

_TVMFFI_OBJECT_HEADER_SIZE = 24
_TVMFFI_OBJECT_ALIGNMENT = 8


def _cpp_identifier(name: str, *, fallback: str = "T") -> str:
    ident = _IDENT_RE.sub("_", name)
    ident = ident or fallback
    if ident[0].isdigit():
        ident = f"_{ident}"
    if ident in _CPP_KEYWORDS:
        ident = f"{ident}_"
    return ident


def _default_cpp_names(cls: type) -> tuple[str, str]:
    ref_name = _cpp_identifier(cls.__name__, fallback="FFIObject")
    if ref_name.endswith("Obj") and len(ref_name) > len("Obj"):
        return ref_name, ref_name[: -len("Obj")]
    return f"{ref_name}Obj", ref_name


def _cpp_string_literal(value: str) -> str:
    return value.encode("unicode_escape").decode("ascii").replace('"', r"\"")


def _cpp_field_storage_type(schema: Any | None) -> str:
    if schema is None:
        return "::tvm::ffi::ObjectRef"
    return _CPP_FIELD_STORAGE_TYPES.get(schema.origin, "::tvm::ffi::ObjectRef")


def _registered_parent_type_info(cls: type) -> Any | None:
    type_info = getattr(cls, "__tvm_ffi_type_info__", None)
    if type_info is None:
        return None
    return type_info.parent_type_info


def _default_parent_names(cls: type) -> tuple[str, str]:
    parent_info = _registered_parent_type_info(cls)
    if parent_info is None or parent_info.type_key == "ffi.Object":
        return "::tvm::ffi::Object", "::tvm::ffi::ObjectRef"
    parent_cls = parent_info.type_cls
    if parent_cls is not None:
        return _default_cpp_names(parent_cls)
    parent_base = parent_info.type_key.rsplit(".", 1)[-1]
    parent_ref = _cpp_identifier(parent_base, fallback="Parent")
    return f"{parent_ref}Obj", parent_ref


def _indent(text: str, spaces: int) -> str:
    if spaces <= 0:
        return text
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else line for line in text.splitlines())


def _align_up(value: int, alignment: int) -> int:
    if alignment <= 1:
        return value
    return (value + alignment - 1) & ~(alignment - 1)


def _fields_parent_first(type_info: Any) -> list[Any] | None:
    chain: list[Any] = []
    cursor = type_info
    while cursor is not None:
        if cursor.fields is None:
            return None
        chain.append(cursor)
        cursor = cursor.parent_type_info
    fields: list[Any] = []
    for info in reversed(chain):
        fields.extend(info.fields)
    return fields


def _namespace_open(namespace: str) -> str:
    return f"namespace {namespace} {{"


def _namespace_close(namespace: str) -> str:
    return f"}}  // namespace {namespace}"


def _render_repr_c(
    cls: type,
    *,
    object_name: str | None = None,
    ref_name: str | None = None,
    parent_object_name: str | None = None,
    parent_ref_name: str | None = None,
    namespace: str | None = None,
    indent: int = 0,
) -> str:
    if not getattr(cls, "__tvm_ffi_is_py_class__", False):
        raise TypeError(f"repr_c() expects a @py_class type, got {cls.__name__!r}")
    type_info = getattr(cls, "__tvm_ffi_type_info__", None)
    if type_info is None:
        raise TypeError(f"{cls.__name__}.repr_c() requires a registered @py_class type")
    if type_info.fields is None:
        raise TypeError(f"{cls.__name__}.repr_c() cannot run until forward references are resolved")

    default_object_name, default_ref_name = _default_cpp_names(cls)
    object_name = object_name or default_object_name
    ref_name = ref_name or default_ref_name

    default_parent_object_name, default_parent_ref_name = _default_parent_names(cls)
    parent_object_name = parent_object_name or default_parent_object_name
    parent_ref_name = parent_ref_name or default_parent_ref_name

    object_name = _cpp_identifier(object_name, fallback="FFIObject")
    ref_name = _cpp_identifier(ref_name, fallback="FFIRef")
    if "::" not in parent_object_name:
        parent_object_name = _cpp_identifier(parent_object_name, fallback="ParentObj")
    if "::" not in parent_ref_name:
        parent_ref_name = _cpp_identifier(parent_ref_name, fallback="Parent")

    lines: list[str] = [
        f"// C++ layout mirror for Python @py_class {cls.__module__}.{cls.__qualname__}",
        f"// FFI type key: {_cpp_string_literal(type_info.type_key)}",
        f"class {object_name} : public {parent_object_name} {{",
        " public:",
    ]
    if type_info.fields:
        for field in type_info.fields:
            field_name = _cpp_identifier(field.name, fallback="field")
            field_ty = _cpp_field_storage_type(field.ty)
            schema = field.ty.repr() if field.ty is not None else "Any"
            lines.append(
                f"  {field_ty} {field_name};  // offset={field.offset}, "
                f"size={field.size}, schema={schema}"
            )
    else:
        lines.append("  // No fields declared directly on this type.")
    lines.extend(
        [
            "",
            "  static constexpr bool _type_mutable = true;",
            f'  TVM_FFI_DECLARE_OBJECT_INFO("{_cpp_string_literal(type_info.type_key)}", '
            f"{object_name}, {parent_object_name});",
            "};",
            "",
            f"static_assert(sizeof({object_name}) == {type_info.total_size}, "
            f'"{object_name} size must match the Python @py_class layout");',
            "",
            f"class {ref_name} : public {parent_ref_name} {{",
            " public:",
            f"  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE({ref_name}, {parent_ref_name}, "
            f"{object_name});",
            "};",
        ]
    )

    rendered = "\n".join(lines)
    if namespace:
        rendered = "\n".join([_namespace_open(namespace), rendered, _namespace_close(namespace)])
    return _indent(rendered, indent)


def repr_c(obj_or_cls: Any, **kwargs: Any) -> str:
    """Return a C++ C-layout mirror for a ``@py_class`` type or instance.

    The generated object class mirrors the storage layout used by Python-defined
    TVM-FFI classes: POD fields are emitted as their ABI storage type, string
    and union-like values as :class:`tvm::ffi::Any`, and object-like values as
    :class:`tvm::ffi::ObjectRef`.
    """
    cls = obj_or_cls if isinstance(obj_or_cls, type) else type(obj_or_cls)
    if not getattr(cls, "__tvm_ffi_is_py_class__", False):
        raise TypeError(f"repr_c() expects a @py_class type or instance, got {type(obj_or_cls)}")
    return _render_repr_c(cls, **kwargs)


def is_repr_c_layout(type_info: Any) -> bool:
    """Return True when *type_info* is representable by the ``repr_c`` C layout.

    This is derived from reflection metadata, not a registered marker.  It checks
    that every field appears at the offset produced by C ABI alignment from the
    object header, and that ``TypeInfo.total_size`` equals the final aligned end.
    """
    if not hasattr(type_info, "total_size"):
        raise TypeError(f"is_repr_c_layout() expects a TypeInfo, got {type(type_info)}")
    all_fields = _fields_parent_first(type_info)
    if all_fields is None:
        return False

    current_offset = _TVMFFI_OBJECT_HEADER_SIZE
    max_alignment = _TVMFFI_OBJECT_ALIGNMENT
    for field in all_fields:
        alignment = getattr(field, "alignment", None)
        if alignment is None:
            return False
        alignment = max(int(alignment), 1)
        current_offset = _align_up(current_offset, alignment)
        if field.offset != current_offset:
            return False
        current_offset += field.size
        max_alignment = max(max_alignment, alignment)

    expected_total_size = _align_up(current_offset, max_alignment)
    return type_info.total_size == expected_total_size


def _repr_c_classmethod(cls: type, **kwargs: Any) -> str:
    return _render_repr_c(cls, **kwargs)


def _install_repr_c(cls: type) -> None:
    """Install ``repr_c`` on a ``@py_class`` unless the class defines it."""
    if "repr_c" not in cls.__dict__:
        cls.repr_c = classmethod(_repr_c_classmethod)  # type: ignore[attr-defined]
        cls.__tvm_ffi_repr_c_installed__ = True  # type: ignore[attr-defined]
