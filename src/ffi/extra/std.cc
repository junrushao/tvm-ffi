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
 * \file src/ffi/extra/std.cc
 * \brief Standard core dialect registration and text printing.
 */
#include <tvm/ffi/extra/dataclass.h>
#include <tvm/ffi/extra/pyast.h>
#include <tvm/ffi/extra/std.h>
#include <tvm/ffi/extra/structural_equal.h>
#include <tvm/ffi/reflection/accessor.h>
#include <tvm/ffi/reflection/creator.h>
#include <tvm/ffi/reflection/registry.h>

#include <algorithm>
#include <cmath>
#include <limits>
#include <optional>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <vector>

namespace tvm {
namespace ffi {
namespace std_ {
namespace {

namespace refl = ::tvm::ffi::reflection;
namespace text = ::tvm::ffi::pyast;
using Path = ::tvm::ffi::reflection::AccessPath;

constexpr DLDataType kDefaultIntLiteralType{static_cast<uint8_t>(kDLInt), 64, 1};
constexpr DLDataType kDefaultFloatLiteralType{static_cast<uint8_t>(kDLFloat), 32, 1};
constexpr DLDataType kDefaultBoolLiteralType{static_cast<uint8_t>(kDLBool), 8, 1};

}  // namespace

namespace details {

void CheckExprDefined(const char* node_name, const char* operand_name, const Expr& expr) {
  TVM_FFI_CHECK(expr.defined(), TypeError)
      << node_name << " operand `" << operand_name << "` must be defined";
  TVM_FFI_CHECK(expr->ty.defined(), TypeError)
      << node_name << " operand `" << operand_name << "` type must be defined";
}

std::optional<DLDataType> DTypeFromTy(const char* node_name, const std::string& ty_name,
                                      const Ty& ty) {
  TVM_FFI_CHECK(ty.defined(), TypeError) << node_name << " " << ty_name << " type must be defined";
  if (ty.as<AnyTyObj>() != nullptr) {
    return std::nullopt;
  }
  if (const PrimTyObj* prim_ty = ty.as<PrimTyObj>()) {
    return prim_ty->dtype;
  }
  if (const TensorTyObj* tensor_ty = ty.as<TensorTyObj>()) {
    return tensor_ty->dtype;
  }
  TVM_FFI_THROW(TypeError) << node_name << " " << ty_name << " type " << ReprPrint(ty)
                           << " does not have a dtype";
  TVM_FFI_UNREACHABLE();
}

std::optional<DLDataType> DTypeFromExpr(const char* node_name, const char* operand_name,
                                        const Expr& expr) {
  CheckExprDefined(node_name, operand_name, expr);
  return DTypeFromTy(node_name, std::string("operand `") + operand_name + "`", expr->ty);
}

Ty IndexedTy(Ty ty, const List<Range>& indices) {
  auto is_unit_extent = [](const Expr& extent) {
    const IntImmObj* static_extent = extent.as<IntImmObj>();
    return static_extent != nullptr && static_extent->value == 1;
  };
  for (int64_t i = 0, n = static_cast<int64_t>(indices.size()); i < n;) {
    if (ty.as<AnyTyObj>() != nullptr) {
      return AnyTy();
    }
    if (const TensorTyObj* tensor_ty = ty.as<TensorTyObj>()) {
      int64_t num_indices = n - i;
      int64_t rank = static_cast<int64_t>(tensor_ty->shape.size());
      if (num_indices >= rank) {
        return PrimTy(tensor_ty->dtype);
      }
      List<Expr> shape;
      for (int64_t j = num_indices; j < rank; ++j) {
        shape.push_back(tensor_ty->shape[j]);
      }
      return TensorTy(std::move(shape), tensor_ty->dtype);
    }
    const TupleTyObj* tuple_ty = ty.as<TupleTyObj>();
    if (tuple_ty == nullptr) {
      return ty;
    }
    const Range& index = indices[i];
    if (!index->start.has_value() || !is_unit_extent(index->extent) || index->step.has_value()) {
      return AnyTy();
    }
    const IntImmObj* static_index = index->start.value().as<IntImmObj>();
    if (static_index == nullptr) {
      return AnyTy();
    }
    int64_t field_index = static_index->value;
    int64_t num_fields = static_cast<int64_t>(tuple_ty->fields.size());
    if (field_index < 0) {
      field_index += num_fields;
    }
    if (field_index < 0 || field_index >= num_fields) {
      return AnyTy();
    }
    ty = tuple_ty->fields[field_index];
    ++i;
  }
  return ty;
}

void CheckConcreteTysEqual(const char* node_name, const char* lhs_name, const Ty& lhs,
                           const char* rhs_name, const Ty& rhs) {
  TVM_FFI_CHECK(lhs.defined(), TypeError)
      << node_name << " " << lhs_name << " type must be defined";
  TVM_FFI_CHECK(rhs.defined(), TypeError)
      << node_name << " " << rhs_name << " type must be defined";
  if (lhs.as<AnyTyObj>() != nullptr || rhs.as<AnyTyObj>() != nullptr) {
    return;
  }
  TVM_FFI_CHECK(StructuralEqual::Equal(lhs, rhs), TypeError)
      << node_name << " " << lhs_name << " type " << ReprPrint(lhs) << " does not match "
      << rhs_name << " type " << ReprPrint(rhs);
}

void CheckConcreteDTypesEqual(const char* node_name, const char* lhs_name, DLDataType lhs,
                              const char* rhs_name, DLDataType rhs) {
  TVM_FFI_CHECK(lhs == rhs, TypeError)
      << node_name << " " << lhs_name << " dtype " << DLDataTypeToString(lhs) << " does not match "
      << rhs_name << " dtype " << DLDataTypeToString(rhs);
}

void CheckBoolDType(const char* node_name, const char* ty_name, DLDataType dtype) {
  TVM_FFI_CHECK(dtype.code == kDLBool && dtype.bits == 8, TypeError)
      << node_name << " " << ty_name << " dtype must be bool8, but got "
      << DLDataTypeToString(dtype);
}

void CheckBitwiseDType(const char* node_name, const char* ty_name, DLDataType dtype) {
  TVM_FFI_CHECK(DTypeIsInt(dtype), TypeError)
      << node_name << " " << ty_name << " dtype must be integer, but got "
      << DLDataTypeToString(dtype);
}

void CheckArithmeticTys(const char* node_name, const Ty& result_ty, const Expr& a, const Expr& b) {
  TVM_FFI_CHECK(result_ty.defined(), TypeError) << node_name << " result type must be defined";
  CheckExprDefined(node_name, "a", a);
  CheckExprDefined(node_name, "b", b);
  CheckConcreteTysEqual(node_name, "operand `a`", a->ty, "operand `b`", b->ty);
  CheckConcreteTysEqual(node_name, "result", result_ty, "operand `a`", a->ty);
  CheckConcreteTysEqual(node_name, "result", result_ty, "operand `b`", b->ty);
  DTypeFromTy(node_name, "result", result_ty);
  DTypeFromExpr(node_name, "a", a);
  DTypeFromExpr(node_name, "b", b);
}

void CheckComparisonResultShape(const char* node_name, const Ty& input_ty, const Ty& result_ty) {
  if (input_ty.as<AnyTyObj>() != nullptr || result_ty.as<AnyTyObj>() != nullptr) {
    return;
  }
  if (const PrimTyObj* input_prim = input_ty.as<PrimTyObj>()) {
    const PrimTyObj* result_prim = result_ty.as<PrimTyObj>();
    TVM_FFI_CHECK(result_prim != nullptr, TypeError)
        << node_name << " result type " << ReprPrint(result_ty)
        << " must be a primitive boolean type for primitive operands";
    CheckBoolDType(node_name, "result", result_prim->dtype);
    TVM_FFI_CHECK(result_prim->dtype.lanes == input_prim->dtype.lanes, TypeError)
        << node_name << " result dtype lane count " << result_prim->dtype.lanes
        << " does not match operand lane count " << input_prim->dtype.lanes;
    return;
  }
  if (const TensorTyObj* input_tensor = input_ty.as<TensorTyObj>()) {
    const TensorTyObj* result_tensor = result_ty.as<TensorTyObj>();
    TVM_FFI_CHECK(result_tensor != nullptr, TypeError)
        << node_name << " result type " << ReprPrint(result_ty)
        << " must be a tensor boolean type for tensor operands";
    CheckBoolDType(node_name, "result", result_tensor->dtype);
    TVM_FFI_CHECK(result_tensor->dtype.lanes == input_tensor->dtype.lanes, TypeError)
        << node_name << " result dtype lane count " << result_tensor->dtype.lanes
        << " does not match operand lane count " << input_tensor->dtype.lanes;
    TVM_FFI_CHECK(StructuralEqual::Equal(result_tensor->shape, input_tensor->shape), TypeError)
        << node_name << " result shape does not match operand shape";
    return;
  }
  TVM_FFI_THROW(TypeError) << node_name << " operand type " << ReprPrint(input_ty)
                           << " does not have a comparable dtype";
}

void CheckArithmeticUnaryTy(const char* node_name, const Ty& result_ty, const Expr& operand) {
  TVM_FFI_CHECK(result_ty.defined(), TypeError) << node_name << " result type must be defined";
  CheckExprDefined(node_name, "operand", operand);
  CheckConcreteTysEqual(node_name, "result", result_ty, "operand `operand`", operand->ty);
  DTypeFromTy(node_name, "result", result_ty);
  DTypeFromExpr(node_name, "operand", operand);
}

void CheckBitwiseBinaryTys(const char* node_name, const Ty& result_ty, const Expr& a,
                           const Expr& b) {
  CheckArithmeticTys(node_name, result_ty, a, b);
  if (std::optional<DLDataType> dtype = DTypeFromTy(node_name, "result", result_ty)) {
    CheckBitwiseDType(node_name, "result", *dtype);
  }
  if (std::optional<DLDataType> dtype = DTypeFromExpr(node_name, "a", a)) {
    CheckBitwiseDType(node_name, "operand `a`", *dtype);
  }
  if (std::optional<DLDataType> dtype = DTypeFromExpr(node_name, "b", b)) {
    CheckBitwiseDType(node_name, "operand `b`", *dtype);
  }
}

void CheckComparisonTys(const char* node_name, const Ty& result_ty, const Expr& a, const Expr& b) {
  TVM_FFI_CHECK(result_ty.defined(), TypeError) << node_name << " result type must be defined";
  CheckExprDefined(node_name, "a", a);
  CheckExprDefined(node_name, "b", b);
  CheckConcreteTysEqual(node_name, "operand `a`", a->ty, "operand `b`", b->ty);
  if (a->ty.as<AnyTyObj>() == nullptr) {
    DTypeFromExpr(node_name, "a", a);
    CheckComparisonResultShape(node_name, a->ty, result_ty);
  } else if (b->ty.as<AnyTyObj>() == nullptr) {
    DTypeFromExpr(node_name, "b", b);
    CheckComparisonResultShape(node_name, b->ty, result_ty);
  } else if (std::optional<DLDataType> dtype = DTypeFromTy(node_name, "result", result_ty)) {
    CheckBoolDType(node_name, "result", *dtype);
  }
}

void CheckLogicalBinaryTys(const char* node_name, const Ty& result_ty, const Expr& a,
                           const Expr& b) {
  CheckArithmeticTys(node_name, result_ty, a, b);
  if (std::optional<DLDataType> dtype = DTypeFromTy(node_name, "result", result_ty)) {
    CheckBoolDType(node_name, "result", *dtype);
  }
  if (std::optional<DLDataType> dtype = DTypeFromExpr(node_name, "a", a)) {
    CheckBoolDType(node_name, "operand `a`", *dtype);
  }
  if (std::optional<DLDataType> dtype = DTypeFromExpr(node_name, "b", b)) {
    CheckBoolDType(node_name, "operand `b`", *dtype);
  }
}

void CheckBitwiseUnaryTy(const char* node_name, const Ty& result_ty, const Expr& operand) {
  CheckArithmeticUnaryTy(node_name, result_ty, operand);
  if (std::optional<DLDataType> dtype = DTypeFromTy(node_name, "result", result_ty)) {
    CheckBitwiseDType(node_name, "result", *dtype);
  }
  if (std::optional<DLDataType> dtype = DTypeFromExpr(node_name, "operand", operand)) {
    CheckBitwiseDType(node_name, "operand `operand`", *dtype);
  }
}

void CheckLogicalUnaryTy(const char* node_name, const Ty& result_ty, const Expr& operand) {
  CheckArithmeticUnaryTy(node_name, result_ty, operand);
  if (std::optional<DLDataType> dtype = DTypeFromTy(node_name, "result", result_ty)) {
    CheckBoolDType(node_name, "result", *dtype);
  }
  if (std::optional<DLDataType> dtype = DTypeFromExpr(node_name, "operand", operand)) {
    CheckBoolDType(node_name, "operand `operand`", *dtype);
  }
}

void CheckScalarBoolCond(const char* node_name, const Expr& cond) {
  CheckExprDefined(node_name, "cond", cond);
  if (cond->ty.as<AnyTyObj>() != nullptr) {
    return;
  }
  const PrimTyObj* prim_ty = cond->ty.as<PrimTyObj>();
  TVM_FFI_CHECK(prim_ty != nullptr, TypeError)
      << node_name << " condition type " << ReprPrint(cond->ty)
      << " must be a primitive scalar bool type";
  CheckBoolDType(node_name, "condition", prim_ty->dtype);
  TVM_FFI_CHECK(prim_ty->dtype.lanes == 1, TypeError)
      << node_name << " condition dtype must be scalar bool, but got "
      << DLDataTypeToString(prim_ty->dtype);
}

void CheckIfExprTy(const Ty& result_ty, const Expr& cond, const Expr& then_expr,
                   const Expr& else_expr) {
  TVM_FFI_CHECK(result_ty.defined(), TypeError) << "IfExpr result type must be defined";
  CheckScalarBoolCond("IfExpr", cond);
  CheckExprDefined("IfExpr", "then_expr", then_expr);
  CheckExprDefined("IfExpr", "else_expr", else_expr);
  CheckConcreteTysEqual("IfExpr", "result", result_ty, "operand `then_expr`", then_expr->ty);
  CheckConcreteTysEqual("IfExpr", "result", result_ty, "operand `else_expr`", else_expr->ty);
  CheckConcreteTysEqual("IfExpr", "operand `then_expr`", then_expr->ty, "operand `else_expr`",
                        else_expr->ty);
}

void CheckRangeDTypes(const char* node_name, const Optional<Expr>& start, const Expr& extent,
                      const Optional<Expr>& step) {
  std::optional<DLDataType> expected_dtype;
  auto check = [&](const Optional<Expr>& expr, const char* operand_name) {
    if (expr.has_value()) {
      std::optional<DLDataType> dtype = DTypeFromExpr(node_name, operand_name, expr.value());
      if (dtype.has_value() && expected_dtype.has_value()) {
        CheckConcreteDTypesEqual(node_name, operand_name, *dtype, "previous range operand",
                                 *expected_dtype);
      } else if (dtype.has_value()) {
        expected_dtype = *dtype;
      }
    }
  };
  std::optional<DLDataType> extent_dtype = DTypeFromExpr(node_name, "extent", extent);
  if (extent_dtype.has_value()) {
    expected_dtype = *extent_dtype;
  }
  check(start, "start");
  check(step, "step");
}

void CheckRangeList(const char* node_name, const List<Range>& indices) {
  for (int32_t i = 0, n = static_cast<int32_t>(indices.size()); i < n; ++i) {
    TVM_FFI_CHECK(indices[i].defined(), TypeError)
        << node_name << " index range `" << i << "` must be defined";
    CheckRangeDTypes(node_name, indices[i]->start, indices[i]->extent, indices[i]->step);
  }
}

void CheckLoadTy(const Ty& result_ty, const Expr& lhs, const List<Range>& indices) {
  CheckRangeList("Load", indices);
  CheckExprDefined("Load", "lhs", lhs);
  CheckConcreteTysEqual("Load", "result", result_ty, "loaded element", IndexedTy(lhs->ty, indices));
}

void CheckStoreTy(const Expr& lhs, const List<Range>& indices, const Expr& rhs) {
  CheckRangeList("Store", indices);
  CheckExprDefined("Store", "lhs", lhs);
  CheckExprDefined("Store", "rhs", rhs);
  CheckConcreteTysEqual("Store", "stored value", rhs->ty, "stored element",
                        IndexedTy(lhs->ty, indices));
}

}  // namespace details

namespace {

Array<String> DialectMnemonic(int32_t type_index) {
  static refl::TypeAttrColumn dialect_mnemonic_col(refl::type_attr::kDialectMnemonic);
  AnyView dialect_mnemonic_view = dialect_mnemonic_col[type_index];
  if (dialect_mnemonic_view == nullptr) {
    TVM_FFI_THROW(ValueError) << "No `__ffi_dialect_mnemonic__` registered for: "
                              << String(TVMFFIGetTypeInfo(type_index)->type_key);
  }
  return dialect_mnemonic_view.cast<Array<String>>();
}

text::ExprAST GetPrintedName(const pyast::PrinterConfig& cfg, const String& dialect,
                             const String& mnemonic) {
  const auto& dialect_map = cfg->dialect_print_map;
  if (dialect_map.defined()) {
    if (std::optional<String> mapped = dialect_map.Get(dialect + "$" + mnemonic)) {
      return (*mapped == "*") ? text::IdAST(mnemonic) : text::DottedName(*mapped);
    }
    if (std::optional<String> mapped = dialect_map.Get(dialect)) {
      return (*mapped == "*") ? text::IdAST(mnemonic) : text::DottedName(*mapped)->Attr(mnemonic);
    }
  }
  if (dialect == "") {
    return text::IdAST(mnemonic);
  }
  return text::DottedName(dialect)->Attr(mnemonic);
}

text::ExprAST CallMnemonic(const text::PrinterConfig& cfg, const ObjectRef& obj) {
  Array<String> dialect_mnemonic = DialectMnemonic(obj->type_index());
  return GetPrintedName(cfg, dialect_mnemonic[0], dialect_mnemonic[1]);
}

String DialectName(const AnyView& obj) { return DialectMnemonic(obj.type_index())[0]; }

AnyView LookupTypeAttr(const refl::TypeAttrColumn& column, int32_t type_index, bool ancestor) {
  AnyView result = column[type_index];
  if (result != nullptr || !ancestor) {
    return result;
  }
  const TVMFFITypeInfo* type_info = TVMFFIGetTypeInfo(type_index);
  for (int32_t i = type_info->type_depth - 1; i >= 0; --i) {
    result = column[type_info->type_ancestors[i]->type_index];
    if (result != nullptr) {
      return result;
    }
  }
  return AnyView();
}

std::optional<FieldCollectionResult> CollectDialectFields(const ObjectRef& obj) {
  static refl::TypeAttrColumn field_collector_col(refl::type_attr::kDialectFieldCollector);
  AnyView func_view = LookupTypeAttr(field_collector_col, obj->type_index(), /*ancestor=*/true);
  if (func_view == nullptr) {
    return std::nullopt;
  }
  return func_view.cast<Function>()(obj).cast<FieldCollectionResult>();
}

FieldCollectionResult CollectRequiredDialectFields(const ObjectRef& obj) {
  std::optional<FieldCollectionResult> fields = CollectDialectFields(obj);
  if (!fields.has_value()) {
    TVM_FFI_THROW(ValueError) << "No `__ffi_dialect_field_collector__` registered for: "
                              << obj->GetTypeKey();
  }
  return fields.value();
}

FieldCollectionResult CollectLangKindFields(const ObjectRef& obj) {
  List<Any> args;
  Dict<String, Any> attrs;
  List<Var> outs;
  List<Node> body;
  static refl::TypeAttrColumn lang_kind_col(refl::type_attr::kDialectLangKind);
  AnyView lang_kind_view = LookupTypeAttr(lang_kind_col, obj->type_index(), /*ancestor=*/false);
  if (lang_kind_view == nullptr) {
    return FieldCollectionResult(std::move(args), DictAttrs(std::move(attrs)), std::move(outs),
                                 std::move(body));
  }
  Map<String, Array<int64_t>> lang_kind_map = lang_kind_view.cast<Map<String, Array<int64_t>>>();
  std::vector<const TVMFFIFieldInfo*> field_infos;
  refl::ForEachFieldInfo(TVMFFIGetTypeInfo(obj->type_index()),
                         [&](const TVMFFIFieldInfo* info) { field_infos.push_back(info); });
  auto append_value = [](List<Any>* target, const Any& value) { target->push_back(value); };
  auto extend_values = [](List<Any>* target, const Any& value) {
    if (value == nullptr) {
      return;
    }
    if (std::optional<Array<Any>> values = value.try_cast<Array<Any>>()) {
      for (const Any& item : *values) {
        target->push_back(item);
      }
    } else {
      target->push_back(value);
    }
  };
  auto extend_attrs = [](Dict<String, Any>* attrs, const String& name, const Any& value) {
    if (value == nullptr) {
      return;
    }
    if (name == "attrs") {
      if (std::optional<DictAttrs> dict_attrs = value.try_cast<DictAttrs>()) {
        for (const auto& kv : (*dict_attrs)->values) {
          attrs->Set(kv.first, kv.second);
        }
        return;
      }
      if (std::optional<Dict<String, Any>> dict = value.try_cast<Dict<String, Any>>()) {
        for (const auto& kv : *dict) {
          attrs->Set(kv.first, kv.second);
        }
        return;
      }
      if (std::optional<Map<String, Any>> map = value.try_cast<Map<String, Any>>()) {
        for (const auto& kv : *map) {
          attrs->Set(kv.first, kv.second);
        }
        return;
      }
    }
    attrs->Set(name, value);
  };
  auto extend_outs = [](auto&& self, List<Var>* outs, const Any& value) -> void {
    if (value == nullptr) {
      return;
    }
    if (std::optional<Var> var = value.try_cast<Var>()) {
      outs->push_back(*var);
      return;
    }
    if (std::optional<Array<Any>> values = value.try_cast<Array<Any>>()) {
      for (const Any& item : *values) {
        self(self, outs, item);
      }
      return;
    }
    if (std::optional<ObjectRef> obj = value.try_cast<ObjectRef>()) {
      FieldCollectionResult fields = CollectRequiredDialectFields(*obj);
      for (const Var& var : fields->outs) {
        outs->push_back(var);
      }
      return;
    }
    TVM_FFI_THROW(TypeError) << "expected std.Var or out node, got " << value.GetTypeKey();
  };
  for (const auto& kv : lang_kind_map) {
    const String& lang_kind = kv.first;
    for (int64_t index : kv.second) {
      TVM_FFI_CHECK(index >= 0 && static_cast<size_t>(index) < field_infos.size(), ValueError)
          << "__ffi_dialect_lang_kind__ index " << index << " for `" << lang_kind << "` on "
          << obj->GetTypeKey() << " is out of range for " << field_infos.size() << " fields";
      const TVMFFIFieldInfo* field_info = field_infos[static_cast<size_t>(index)];
      String name(field_info->name);
      Any value = refl::FieldGetter(field_info)(obj.get());
      if (lang_kind == "arg") {
        append_value(&args, value);
      } else if (lang_kind == "attr") {
        extend_attrs(&attrs, name, value);
      } else if (lang_kind == "out") {
        extend_outs(extend_outs, &outs, value);
      } else if (lang_kind == "body") {
        List<Any> body_values;
        extend_values(&body_values, value);
        for (const Any& item : body_values) {
          body.push_back(item.cast<Node>());
        }
      } else {
        TVM_FFI_THROW(ValueError) << "Invalid lang_kind `" << lang_kind << "` on "
                                  << obj->GetTypeKey() << "." << name;
      }
    }
  }
  while (!args.empty() && args.back() == nullptr) {
    args.pop_back();
  }
  return FieldCollectionResult(std::move(args), DictAttrs(std::move(attrs)), std::move(outs),
                               std::move(body));
}

FieldCollectionResult CollectWithBaseArgs(const ObjectRef& obj, List<Any> args) {
  FieldCollectionResult fields = CollectLangKindFields(obj);
  for (const Any& arg : fields->args) {
    args.push_back(arg);
  }
  return FieldCollectionResult(std::move(args), fields->attrs, fields->outs, fields->body,
                               fields->ty);
}

template <typename T>
FieldCollectionResult CollectBodyFields(const T& obj) {
  List<Node> body;
  body.reserve(static_cast<int64_t>(obj->body.size()));
  for (const Stmt& stmt : obj->body) {
    body.push_back(stmt);
  }
  return FieldCollectionResult(List<Any>{}, DictAttrs(Dict<String, Any>{}), List<Var>{},
                               std::move(body));
}

void AppendAttrsKwargs(const text::IRPrinter& printer, const Optional<Attrs>& attrs,
                       const Path& path, List<String>& kwargs_keys,
                       List<text::ExprAST>& kwargs_values) {
  if (!attrs.has_value()) {
    return;
  }
  text::ExprAST attrs_ast = printer->ToExpr(*attrs, path);
  if (const text::CallASTObj* call = attrs_ast.as<text::CallASTObj>()) {
    int64_t n = static_cast<int64_t>(call->kwargs_keys.size());
    for (int64_t i = 0; i < n; ++i) {
      kwargs_keys.push_back(call->kwargs_keys[i]);
      kwargs_values.push_back(call->kwargs_values[i]);
    }
    return;
  }
  TVM_FFI_THROW(ValueError) << "ffi.std.Attrs text printer must return CallAST";
}

text::ExprAST PrintDialectValue(const text::IRPrinter& printer, const Any& value, const Path& path);

text::ExprAST DefineVar(const text::IRPrinter& printer, const Var& var) {
  // Convert a std.Var object into its textual identifier and register it with
  // the printer if this is the first occurrence.  For example, the first visit
  // to Var("i") defines "i"; later visits fetch the same printed name.
  if (!printer->VarIsDefined(var)) {
    return printer->VarDef(var->name, var, {});
  }
  Optional<text::ExprAST> ret = printer->VarGet(var);
  if (!ret.has_value()) {
    TVM_FFI_THROW(ValueError) << "ffi.std.Var printer failed to fetch variable " << var->name;
  }
  return *ret;
}

struct ExprBuilder {
  std::vector<String> dialects;
  List<text::ExprAST> operands;
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;

  text::ExprAST AddOperand(const text::IRPrinter& printer, const AnyView& operand,
                           const Path& path) {
    text::ExprAST ret = printer->ToExpr(operand, path);
    bool is_literal = ret->IsInstance<text::LiteralASTObj>();
    operands.push_back(ret);
    if (!is_literal) {
      dialects.push_back(DialectName(operand));
    }
    return ret;
  }

  template <typename T>
  void AddOperands(const text::IRPrinter& printer, const List<T>& values, const Path& path) {
    int64_t n = static_cast<int64_t>(values.size());
    operands.reserve(static_cast<int64_t>(operands.size()) + n);
    for (int64_t i = 0; i < n; ++i) {
      AddOperand(printer, values[i], path->ArrayItem(i));
    }
  }

  void AddTy(const text::IRPrinter& printer, const Ty& ty, const Path& path) {
    kwargs_keys.push_back("ty");
    kwargs_values.push_back(printer->ToExpr(ty, path));
  }

  void AddAttrs(const text::IRPrinter& printer, const Optional<Attrs>& attrs, const Path& path) {
    AppendAttrsKwargs(printer, attrs, path, kwargs_keys, kwargs_values);
  }

  void AddDialectFields(const text::IRPrinter& printer, const FieldCollectionResult& fields,
                        const Path& path) {
    Path args_path = path->Attr("args");
    int64_t n = static_cast<int64_t>(fields->args.size());
    operands.reserve(static_cast<int64_t>(operands.size()) + n);
    for (int64_t i = 0; i < n; ++i) {
      operands.push_back(PrintDialectValue(printer, fields->args[i], args_path->ArrayItem(i)));
    }
    AddAttrs(printer, Optional<Attrs>(fields->attrs), path->Attr("attrs"));
    if (fields->ty.has_value()) {
      kwargs_keys.push_back("ty");
      kwargs_values.push_back(PrintDialectValue(printer, fields->ty.value(), path->Attr("ty")));
    }
  }

  bool ExprDerivable() const {
    // Checks C1 (no attr) & C2 (same dialect)
    return kwargs_keys.empty() && this->dialects.size() &&
           std::all_of(this->dialects.begin() + 1,  //
                       this->dialects.end(),        //
                       [d = this->dialects[0]](const String& i) { return i == d; });
  }

  bool StmtDerivable(const text::IRPrinter& printer, const ObjectRef& obj) const {
    return kwargs_keys.empty() && !printer->dialect_stack.empty() &&
           DialectName(obj) == printer->dialect_stack.back();
  }

  text::StmtAST StmtCall(const text::IRPrinter& printer, const ObjectRef& obj) {
    return text::ExprStmtAST(
        CallMnemonic(printer->cfg, obj)
            ->CallKw(std::move(operands), std::move(kwargs_keys), std::move(kwargs_values)));
  }
};

struct ScopeBuilder {
  text::ExprAST scope_call;
  List<text::ExprAST> operands;
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  List<text::ExprAST> targets;
  List<text::StmtAST> body;

  ScopeBuilder(const char* new_mnemonic, const String& dialect, const text::PrinterConfig& cfg)
      : scope_call(GetPrintedName(cfg, dialect, new_mnemonic)) {}

  template <typename T>
  void AddBodyStmt(const text::IRPrinter& printer, const T& stmt, const Path& path) {
    body.push_back(printer->operator()(stmt, path).template cast<text::StmtAST>());
  }

  template <typename T>
  void AddBodyStmts(const text::IRPrinter& printer, const List<T>& stmts, const Path& path) {
    int64_t n = static_cast<int64_t>(stmts.size());
    for (int64_t i = 0; i < n; ++i) {
      AddBodyStmt(printer, stmts[i], path->ArrayItem(i));
    }
  }

  void AddAttrs(const text::IRPrinter& printer, const Optional<Attrs>& attrs, const Path& path) {
    AppendAttrsKwargs(printer, attrs, path, kwargs_keys, kwargs_values);
  }

  void AddDialectArgsAttrs(const text::IRPrinter& printer, const FieldCollectionResult& fields,
                           const Path& path) {
    Path args_path = path->Attr("args");
    int64_t n = static_cast<int64_t>(fields->args.size());
    operands.reserve(static_cast<int64_t>(operands.size()) + n);
    for (int64_t i = 0; i < n; ++i) {
      operands.push_back(PrintDialectValue(printer, fields->args[i], args_path->ArrayItem(i)));
    }
    AddAttrs(printer, Optional<Attrs>(fields->attrs), path->Attr("attrs"));
    if (fields->ty.has_value()) {
      kwargs_keys.push_back("ty");
      kwargs_values.push_back(PrintDialectValue(printer, fields->ty.value(), path->Attr("ty")));
    }
  }

  void AddTargets(const text::IRPrinter& printer, const List<Var>& vars) {
    int64_t n = static_cast<int64_t>(vars.size());
    targets.reserve(static_cast<int64_t>(targets.size()) + n);
    for (int64_t i = 0; i < n; ++i) {
      targets.push_back(DefineVar(printer, vars[i]));
    }
  }

  Optional<text::ExprAST> Target(bool create_placeholder_for_none) {
    if (targets.empty()) {
      if (create_placeholder_for_none) {
        return text::IdAST("_");
      }
      return {};
    }
    if (targets.size() == 1) {
      return targets[0];
    }
    return text::TupleAST(std::move(targets));
  }

  text::ExprAST StmtCall(bool allow_omit_call) {
    if (allow_omit_call && operands.empty() && kwargs_keys.empty()) {
      return std::move(scope_call);
    }
    return scope_call->CallKw(std::move(operands), std::move(kwargs_keys),
                              std::move(kwargs_values));
  }
};

template <typename ResultType, typename InputType>
List<ResultType> PrintList(const text::IRPrinter& printer, const InputType& values,
                           const Path& path) {
  List<ResultType> result;
  int64_t n = static_cast<int64_t>(values.size());
  result.reserve(n);
  for (int64_t i = 0; i < n; ++i) {
    result.push_back(
        printer->operator()(values[i], path->ArrayItem(i)).template cast<ResultType>());
  }
  return result;
}

bool IsStdType(int32_t type_index) {
  TVMFFIByteArray type_key = TVMFFIGetTypeInfo(type_index)->type_key;
  std::string_view actual(type_key.data, type_key.size);
  return actual.rfind("ffi.std.", 0) == 0;
}

template <typename ObjType>
bool IsExactType(const ObjectRef& obj) {
  return obj->type_index() == ObjType::RuntimeTypeIndex();
}

// Binding statements use assignment targets.  One var prints as "x", while
// multiple vars print as a tuple target such as "x, y = rhs".
text::ExprAST DefineVarTuple(const text::IRPrinter& printer, const List<Var>& vars);

// Build the constructor-style expression used by the generic dialect printer.
//
// Example:
//
//   @py_class("testing.ExtValue")
//   class ExtValue(std.Node, mnemonic="testing.ExtValue"):
//       value: int = field(lang_kind="arg")
//       tag: str = field(lang_kind="attr")
//
// For an object whose collector returns
//
//   FieldCollectionResult(args=[1], attrs={"tag": "demo"})
//
// this helper emits:
//
//   testing.ExtValue(1, tag="demo")
//
// `GenericDialectCall` only builds the call expression.  `TextPrint(Node)` wraps
// that expression as a statement for Stmt nodes, or as an assignment when the
// collected fields define a single out target.
text::ExprAST GenericDialectCall(const ObjectRef& obj, const FieldCollectionResult& fields,
                                 const text::IRPrinter& printer, const Path& path) {
  Array<String> dialect_mnemonic = DialectMnemonic(obj->type_index());
  Path args_path = path->Attr("args");
  List<text::ExprAST> args;
  int64_t n_args = static_cast<int64_t>(fields->args.size());
  args.reserve(n_args);
  for (int64_t i = 0; i < n_args; ++i) {
    args.push_back(PrintDialectValue(printer, fields->args[i], args_path->ArrayItem(i)));
  }

  const Dict<String, Any>& attrs = fields->attrs->values;
  std::vector<String> sorted_keys;
  sorted_keys.reserve(attrs.size());
  for (const auto& kv : attrs) {
    sorted_keys.push_back(kv.first);
  }
  std::sort(sorted_keys.begin(), sorted_keys.end());

  Path attrs_path = path->Attr("attrs");
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  kwargs_keys.reserve(static_cast<int64_t>(sorted_keys.size()) + (fields->ty.has_value() ? 1 : 0));
  kwargs_values.reserve(static_cast<int64_t>(sorted_keys.size()) +
                        (fields->ty.has_value() ? 1 : 0));
  for (const String& key : sorted_keys) {
    kwargs_keys.push_back(key);
    kwargs_values.push_back(PrintDialectValue(printer, attrs[key], attrs_path->Attr(key)));
  }
  if (fields->ty.has_value()) {
    kwargs_keys.push_back("ty");
    kwargs_values.push_back(PrintDialectValue(printer, fields->ty.value(), path->Attr("ty")));
  }
  return GetPrintedName(printer->cfg, dialect_mnemonic[0], dialect_mnemonic[1])
      ->CallKw(std::move(args), std::move(kwargs_keys), std::move(kwargs_values));
}

text::NodeAST GenericDialectStmt(const ObjectRef& obj, const text::IRPrinter& printer,
                                 const Path& path) {
  FieldCollectionResult fields = CollectRequiredDialectFields(obj);
  TVM_FFI_CHECK(fields->outs.empty(), TypeError)
      << obj->GetTypeKey() << " generic statement printer does not support out fields";
  TVM_FFI_CHECK(fields->body.empty(), TypeError)
      << obj->GetTypeKey() << " generic statement printer does not support body fields";
  return text::ExprStmtAST(GenericDialectCall(obj, fields, printer, path));
}

// Print a value that appears inside the args, attrs, or ty of a generic dialect
// call.
//
// `printer->ToExpr` is enough for ordinary expression values, types, literals,
// and std nodes whose printers already produce ExprAST.  It is not enough for
// extension dialect statements used as values, because their normal printer
// entry point produces a StmtAST.
//
// Example:
//
//   @py_class("testing.ExtStmt")
//   class ExtStmt(std.Stmt, mnemonic="testing.ExtStmt"):
//       value: int = field(lang_kind="arg")
//
//   @py_class("testing.ExtOuter")
//   class ExtOuter(std.Node, mnemonic="testing.ExtOuter"):
//       arg_stmt: std.Stmt = field(lang_kind="arg")
//       attr_stmt: std.Stmt = field(lang_kind="attr")
//
// Printing `ExtOuter(ExtStmt(2), attr_stmt=ExtStmt(4))` needs the nested
// statements to be rendered as constructor expressions:
//
//   testing.ExtOuter(testing.ExtStmt(2), attr_stmt=testing.ExtStmt(4))
//
// This helper also recurses through Array and Map values, so containers such as
// `[ExtStmt(1)]` and `{"stmt": ExtStmt(2)}` preserve the same nested dialect
// representation.
//
// Builtin std statements are intentionally excluded from the nested generic
// path.  They inherit the root std.Node collector through ancestor lookup, but
// many of them have no exact generic field spec, or have collectors meant for
// their custom statement syntax rather than constructor syntax.  Treating such
// nodes as generic calls would silently drop fields, e.g.
// `std.Store(lhs, rhs)` would become `std.Store()`.  Falling back to the
// regular printer is the correct behavior for those statement-only std nodes.
text::ExprAST PrintDialectValue(const text::IRPrinter& printer, const Any& value,
                                const Path& path) {
  if (value == nullptr) {
    return printer->ToExpr(value, path);
  }
  if (std::optional<Array<Any>> values = value.try_cast<Array<Any>>()) {
    List<text::ExprAST> printed;
    int64_t n = static_cast<int64_t>(values->size());
    printed.reserve(n);
    for (int64_t i = 0; i < n; ++i) {
      printed.push_back(PrintDialectValue(printer, (*values)[i], path->ArrayItem(i)));
    }
    return text::ListAST(std::move(printed));
  }
  if (std::optional<List<Any>> values = value.try_cast<List<Any>>()) {
    List<text::ExprAST> printed;
    int64_t n = static_cast<int64_t>(values->size());
    printed.reserve(n);
    for (int64_t i = 0; i < n; ++i) {
      printed.push_back(PrintDialectValue(printer, (*values)[i], path->ArrayItem(i)));
    }
    return text::ListAST(std::move(printed));
  }
  if (std::optional<Map<Any, Any>> map = value.try_cast<Map<Any, Any>>()) {
    List<text::ExprAST> keys;
    List<text::ExprAST> values;
    keys.reserve(static_cast<int64_t>(map->size()));
    values.reserve(static_cast<int64_t>(map->size()));
    using KV = std::pair<Any, Any>;
    std::vector<KV> items;
    items.reserve(map->size());
    bool all_str_keys = true;
    for (const auto& kv : *map) {
      items.emplace_back(kv.first, kv.second);
      all_str_keys = all_str_keys && kv.first.try_cast<String>().has_value();
    }
    if (all_str_keys) {
      std::sort(items.begin(), items.end(), [](const KV& lhs, const KV& rhs) {
        return lhs.first.cast<String>() < rhs.first.cast<String>();
      });
    }
    for (const auto& kv : items) {
      Path item_path = path->MapItem(kv.first);
      keys.push_back(printer->ToExpr(kv.first, item_path));
      values.push_back(PrintDialectValue(printer, kv.second, item_path));
    }
    return text::DictAST(std::move(keys), std::move(values));
  }
  if (std::optional<Stmt> stmt = value.try_cast<Stmt>()) {
    std::optional<FieldCollectionResult> fields = CollectDialectFields(*stmt);
    if (fields.has_value() && fields.value()->outs.empty() && fields.value()->body.empty() &&
        !IsStdType((*stmt)->type_index())) {
      return GenericDialectCall(*stmt, fields.value(), printer, path);
    }
  }
  return printer->ToExpr(value, path);
}

text::NodeAST TextPrint(const Node& obj, const text::IRPrinter& printer, const Path& path) {
  FieldCollectionResult fields = CollectRequiredDialectFields(obj);
  List<Var> outs = fields->outs;
  TVM_FFI_CHECK(fields->body.empty(), TypeError)
      << obj->GetTypeKey() << " generic collector text printer does not support body fields";
  TVM_FFI_CHECK(
      outs.empty() || obj.as<BaseBindExprObj>() != nullptr || obj.as<BaseVarDefObj>() != nullptr,
      TypeError)
      << obj->GetTypeKey() << " generic collector text printer does not support out fields; "
      << "subclass std.BaseBindExpr or std.BaseVarDef";
  text::ExprAST call = GenericDialectCall(obj, fields, printer, path);
  if (!outs.empty()) {
    TVM_FFI_CHECK_EQ(outs.size(), 1, TypeError)
        << obj->GetTypeKey() << " generic collector text printer requires exactly one "
        << "out target, got " << outs.size();
    return text::AssignAST(DefineVarTuple(printer, outs), std::move(call));
  }
  if (obj.as<StmtObj>() != nullptr) {
    return text::ExprStmtAST(std::move(call));
  }
  return call;
}

// Abstract std bases are invalid to print directly.  If this hook is reached
// through inherited lookup for an extension subclass, keep walking semantically
// by delegating to the root std.Node collector printer.
#define TVM_FFI_TEXT_PRINT_EXACT_DISALLOW(TypeName)                                                \
  text::NodeAST TextPrint(const TypeName& obj, const text::IRPrinter& printer, const Path& path) { \
    if (obj->type_index() == TypeName::ContainerType::RuntimeTypeIndex()) {                        \
      TVM_FFI_THROW(ValueError) << "No ffi.std text printer registered for " << obj->GetTypeKey(); \
      TVM_FFI_UNREACHABLE();                                                                       \
    }                                                                                              \
    return TextPrint(static_cast<const Node&>(obj), printer, path);                                \
  }
TVM_FFI_TEXT_PRINT_EXACT_DISALLOW(Ty)
TVM_FFI_TEXT_PRINT_EXACT_DISALLOW(Stmt)
TVM_FFI_TEXT_PRINT_EXACT_DISALLOW(Attrs)
TVM_FFI_TEXT_PRINT_EXACT_DISALLOW(Aggregate)
TVM_FFI_TEXT_PRINT_EXACT_DISALLOW(Expr)
TVM_FFI_TEXT_PRINT_EXACT_DISALLOW(FieldCollectionResult)
#undef TVM_FFI_TEXT_PRINT_EXACT_DISALLOW

/************************************************************************/
/*************** Section 1: Types, Cast, Aggregate, Attrs ***************/
/************************************************************************/

text::NodeAST TextPrint(const AnyTy& obj, const text::IRPrinter& printer, const Path& path) {
  return CallMnemonic(printer->cfg, obj);
}

text::NodeAST TextPrint(const PrimTy& obj, const text::IRPrinter& printer, const Path& path) {
  String dialect = DialectName(obj);
  String mnemonic = DTypeAbbrev(obj->dtype);
  return GetPrintedName(printer->cfg, dialect, mnemonic);
}

text::NodeAST TextPrint(const TupleTy& obj, const text::IRPrinter& printer, const Path& path) {
  return CallMnemonic(printer->cfg, obj)
      ->Index(PrintList<text::ExprAST>(printer, obj->fields, path->Attr("fields")));
}

text::NodeAST TextPrint(const TensorTy& obj, const text::IRPrinter& printer, const Path& path) {
  return printer->ToExpr(PrimTy(obj->dtype), path->Attr("dtype"))
      ->Index(PrintList<text::ExprAST>(printer, obj->shape, path->Attr("shape")));
}

text::NodeAST TextPrint(const Cast& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->value, path->Attr("value"));
  text::ExprAST ty = printer->ToExpr(obj->ty, path->Attr("ty"));
  if (ctx.dialects.empty()) {
    // Casting a literal value. In this case, we will need to explicit print `std.Cast(ty, value)`
    // to disambiguate from a literal of the target type. For example:
    //   - `std.Cast(std.i32, 1)` is a cast of the literal `1` to `int64`
    //   - `std.i32(1)` is the literal `1` of type `int32`
    return CallMnemonic(printer->cfg, obj)->Call({std::move(ty), ctx.operands[0]});
  }
  return ty->Call({ctx.operands[0]});
}

text::ExprAST TextPrintSlice(const Range& obj, const text::IRPrinter& printer, const Path& path) {
  Optional<text::ExprAST> start;
  Optional<text::ExprAST> step;
  if (obj->start.has_value()) {
    start = printer->ToExpr(*obj->start, path->Attr("start"));
  }
  text::ExprAST extent = printer->ToExpr(obj->extent, path->Attr("extent"));
  if (obj->step.has_value()) {
    step = printer->ToExpr(*obj->step, path->Attr("step"));
  }
  if (start.has_value() && !obj->step.has_value()) {
    if (const IntImmObj* static_extent = obj->extent.as<IntImmObj>();
        static_extent != nullptr && static_extent->value == 1) {
      return *start;
    }
  }
  if (!start.has_value() && !step.has_value()) {
    return text::SliceAST({}, std::move(extent), {});
  }
  if (start.has_value() && !step.has_value()) {
    return text::SliceAST(std::move(start), std::move(extent), {});
  }
  if (!start.has_value()) {
    return text::SliceAST({}, std::move(extent), std::move(step));
  }
  return text::SliceAST(std::move(start), std::move(extent), std::move(step));
}

text::NodeAST TextPrint(const Range& obj, const text::IRPrinter& printer, const Path& path) {
  List<text::ExprAST> args;
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  if (obj->start.has_value()) {
    args.push_back(printer->ToExpr(*obj->start, path->Attr("start")));
    args.push_back(printer->ToExpr(obj->extent, path->Attr("extent")));
  } else {
    args.push_back(printer->ToExpr(obj->extent, path->Attr("extent")));
  }
  if (obj->step.has_value()) {
    kwargs_keys.push_back("step");
    kwargs_values.push_back(printer->ToExpr(*obj->step, path->Attr("step")));
  }
  return CallMnemonic(printer->cfg, obj)
      ->CallKw(std::move(args), std::move(kwargs_keys), std::move(kwargs_values));
}

text::NodeAST TextPrint(const DictAttrs& obj, const text::IRPrinter& printer, const Path& path) {
  std::vector<String> sorted_keys;
  sorted_keys.reserve(obj->values.size());
  for (const auto& kv : obj->values) {
    sorted_keys.push_back(kv.first);
  }
  std::sort(sorted_keys.begin(), sorted_keys.end());

  List<text::ExprAST> values;
  values.reserve(static_cast<int64_t>(sorted_keys.size()));
  Path values_path = path->Attr("values");
  int64_t n = static_cast<int64_t>(sorted_keys.size());
  List<String> kwargs_keys;
  kwargs_keys.reserve(n);
  for (int64_t i = 0; i < n; ++i) {
    const String& key = sorted_keys[i];
    kwargs_keys.push_back(key);
    values.push_back(PrintDialectValue(printer, obj->values[key], values_path->MapItem(key)));
  }
  return CallMnemonic(printer->cfg, obj)
      ->CallKw(List<text::ExprAST>{}, std::move(kwargs_keys), std::move(values));
}

/*********************************************************/
/*************** Section 2: Literals, Vars ***************/
/*********************************************************/

text::NodeAST TextPrint(const Var& obj, const text::IRPrinter& printer, const Path&) {
  return DefineVar(printer, obj);
}

text::NodeAST TextPrint(const BoolImm& obj, const text::IRPrinter& printer, const Path& path) {
  text::ExprAST value = text::LiteralAST::Bool(obj->value);
  if (const PrimTyObj* prim_ty = obj->ty.as<PrimTyObj>();
      prim_ty != nullptr && prim_ty->dtype != kDefaultBoolLiteralType) {
    text::ExprAST ty = printer->ToExpr(obj->ty, path->Attr("ty"));
    return ty->Call(List<text::ExprAST>{std::move(value)});
  }
  return value;
}

text::NodeAST TextPrint(const IntImm& obj, const text::IRPrinter& printer, const Path& path) {
  text::ExprAST value = text::LiteralAST::Int(obj->value);
  if (const PrimTyObj* prim_ty = obj->ty.as<PrimTyObj>();
      prim_ty != nullptr && prim_ty->dtype != kDefaultIntLiteralType) {
    text::ExprAST ty = printer->ToExpr(obj->ty, path->Attr("ty"));
    return ty->Call(List<text::ExprAST>{std::move(value)});
  }
  return value;
}

text::NodeAST TextPrint(const FloatImm& obj, const text::IRPrinter& printer, const Path& path) {
  text::ExprAST value = text::LiteralAST::Float(obj->value);
  if (const PrimTyObj* prim_ty = obj->ty.as<PrimTyObj>();
      prim_ty != nullptr && prim_ty->dtype != kDefaultFloatLiteralType) {
    text::ExprAST ty = printer->ToExpr(obj->ty, path->Attr("ty"));
    return ty->Call(List<text::ExprAST>{std::move(value)});
  }
  return value;
}

text::NodeAST TextPrint(const StringImm& obj, const text::IRPrinter&, const Path&) {
  return text::LiteralAST::Str(obj->value);
}

/*******************************************************************/
/*************** Section 3: Unary/Binary Expressions ***************/
/*******************************************************************/

template <typename T, text::OperationASTObj::Kind op_kind>
text::NodeAST PrintBinaryOp(const T& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->a, path->Attr("a"));
  ctx.AddOperand(printer, obj->b, path->Attr("b"));
  if constexpr (op_kind != text::OperationASTObj::kUndefined) {
    if (ctx.ExprDerivable()) {
      return text::OperationAST(static_cast<int64_t>(op_kind), std::move(ctx.operands));
    }
  }
  ctx.AddTy(printer, obj->ty, path->Attr("ty"));
  return CallMnemonic(printer->cfg, obj)
      ->CallKw(ctx.operands, std::move(ctx.kwargs_keys), std::move(ctx.kwargs_values));
}

#define TVM_FFI_STD_BINARY_OP_TEXT_PRINT(TypeName, OpKind)                                         \
  text::NodeAST TextPrint(const TypeName& obj, const text::IRPrinter& printer, const Path& path) { \
    return PrintBinaryOp<TypeName, OpKind>(obj, printer, path);                                    \
  }

TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Add, text::OperationASTObj::kAdd)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Sub, text::OperationASTObj::kSub)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Mul, text::OperationASTObj::kMult)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(CDiv, text::OperationASTObj::kDiv)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(FloorDiv, text::OperationASTObj::kFloorDiv)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(FloorMod, text::OperationASTObj::kMod)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Pow, text::OperationASTObj::kPow)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(LShift, text::OperationASTObj::kLShift)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(RShift, text::OperationASTObj::kRShift)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(BitwiseAnd, text::OperationASTObj::kBitAnd)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(BitwiseOr, text::OperationASTObj::kBitOr)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(BitwiseXor, text::OperationASTObj::kBitXor)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Eq, text::OperationASTObj::kEq)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Ne, text::OperationASTObj::kNotEq)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Le, text::OperationASTObj::kLtE)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Ge, text::OperationASTObj::kGtE)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Gt, text::OperationASTObj::kGt)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Lt, text::OperationASTObj::kLt)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(And, text::OperationASTObj::kAnd)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Or, text::OperationASTObj::kOr)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Min, text::OperationASTObj::kMin)
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Max, text::OperationASTObj::kMax)

#undef TVM_FFI_STD_BINARY_OP_TEXT_PRINT

// NOLINTBEGIN(bugprone-misplaced-widening-cast,bugprone-narrowing-conversions)

text::NodeAST TextPrint(const CMod& obj, const text::IRPrinter& printer, const Path& path) {
  bool is_float = false;
  if (const PrimTyObj* prim_ty = obj->ty.as<PrimTyObj>()) {
    is_float = DTypeIsFloat(prim_ty->dtype);
  }
  if (const TensorTyObj* tensor_ty = obj->ty.as<TensorTyObj>()) {
    is_float = DTypeIsFloat(tensor_ty->dtype);
  }
  if (is_float) {
    return PrintBinaryOp<CMod, text::OperationASTObj::kMod>(obj, printer, path);
  } else {
    return PrintBinaryOp<CMod, text::OperationASTObj::kUndefined>(obj, printer, path);
  }
}

text::NodeAST TextPrint(const Not& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->operand, path->Attr("operand"));
  if (ctx.ExprDerivable()) {
    return text::OperationAST(static_cast<int64_t>(text::OperationASTObj::kNot),
                              std::move(ctx.operands));
  }
  ctx.AddTy(printer, obj->ty, path->Attr("ty"));
  return CallMnemonic(printer->cfg, obj)
      ->CallKw(ctx.operands, std::move(ctx.kwargs_keys), std::move(ctx.kwargs_values));
}

text::NodeAST TextPrint(const BitwiseNot& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->operand, path->Attr("operand"));
  if (ctx.ExprDerivable()) {
    return text::OperationAST(static_cast<int64_t>(text::OperationASTObj::kInvert),
                              std::move(ctx.operands));
  }
  ctx.AddTy(printer, obj->ty, path->Attr("ty"));
  return CallMnemonic(printer->cfg, obj)
      ->CallKw(ctx.operands, std::move(ctx.kwargs_keys), std::move(ctx.kwargs_values));
}

text::NodeAST TextPrint(const Abs& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->operand, path->Attr("operand"));
  if (ctx.ExprDerivable()) {
    return text::IdAST("abs")->Call(std::move(ctx.operands));
  }
  ctx.AddTy(printer, obj->ty, path->Attr("ty"));
  return CallMnemonic(printer->cfg, obj)
      ->CallKw(ctx.operands, std::move(ctx.kwargs_keys), std::move(ctx.kwargs_values));
}

text::NodeAST TextPrint(const IfExpr& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->cond, path->Attr("cond"));
  ctx.AddOperand(printer, obj->then_expr, path->Attr("then_expr"));
  ctx.AddOperand(printer, obj->else_expr, path->Attr("else_expr"));
  if (ctx.ExprDerivable()) {
    return text::OperationAST(static_cast<int64_t>(text::OperationASTObj::kIfThenElse),
                              std::move(ctx.operands));
  }
  ctx.AddTy(printer, obj->ty, path->Attr("ty"));
  return CallMnemonic(printer->cfg, obj)
      ->CallKw(ctx.operands, std::move(ctx.kwargs_keys), std::move(ctx.kwargs_values));
}

/*****************************************************/
/*************** Section 4: Load/Store ***************/
/*****************************************************/

text::NodeAST TextPrint(const Load& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->lhs, path->Attr("lhs"));
  Path indices_path = path->Attr("indices");
  for (size_t i = 0; i < obj->indices.size(); ++i) {
    ctx.operands.push_back(TextPrintSlice(obj->indices[i], printer, indices_path->ArrayItem(i)));
  }
  if (ctx.ExprDerivable()) {  // Always true
    return text::IndexAST(ctx.operands[0], {ctx.operands.begin() + 1, ctx.operands.end()});
  } else {
    ctx.AddTy(printer, obj->ty, path->Attr("ty"));
    return CallMnemonic(printer->cfg, obj)
        ->CallKw(ctx.operands, std::move(ctx.kwargs_keys), std::move(ctx.kwargs_values));
  }
}

text::NodeAST TextPrint(const Store& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->lhs, path->Attr("lhs"));
  ctx.AddOperand(printer, obj->rhs, path->Attr("rhs"));
  Path indices_path = path->Attr("indices");
  for (size_t i = 0; i < obj->indices.size(); ++i) {
    ctx.operands.push_back(TextPrintSlice(obj->indices[i], printer, indices_path->ArrayItem(i)));
  }
  if (ctx.ExprDerivable()) {
    return text::AssignAST(text::IndexAST(ctx.operands[0],  //
                                          {ctx.operands.begin() + 2, ctx.operands.end()}),
                           ctx.operands[1]);
  } else {
    return text::ExprStmtAST(
        CallMnemonic(printer->cfg, obj)
            ->CallKw(ctx.operands, std::move(ctx.kwargs_keys), std::move(ctx.kwargs_values)));
  }
}

/**********************************************************************/
/*************** Section 5: Body-Free Control Stmts *******************/
/**********************************************************************/

Optional<text::ExprAST> StmtValue(List<text::ExprAST> operands) {
  if (operands.empty()) {
    return {};
  } else if (operands.size() == 1) {
    return operands[0];
  } else {
    return text::TupleAST(std::move(operands));
  }
}

text::NodeAST TextPrint(const Assert& obj, const text::IRPrinter& printer, const Path& path) {
  if (!IsExactType<AssertObj>(obj)) {
    return GenericDialectStmt(obj, printer, path);
  }
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->cond, path->Attr("cond"));
  if (ctx.ExprDerivable() || (ctx.dialects.empty() && ctx.StmtDerivable(printer, obj))) {
    return text::AssertAST(ctx.operands[0]);
  }
  return ctx.StmtCall(printer, obj);
}

text::NodeAST TextPrint(const Return& obj, const text::IRPrinter& printer, const Path& path) {
  if (!IsExactType<ReturnObj>(obj)) {
    return GenericDialectStmt(obj, printer, path);
  }
  ExprBuilder ctx;
  ctx.AddOperands(printer, obj->vars, path->Attr("vars"));
  if (ctx.ExprDerivable() || (ctx.dialects.empty() && ctx.StmtDerivable(printer, obj))) {
    return text::ReturnAST(StmtValue(std::move(ctx.operands)));
  }
  return ctx.StmtCall(printer, obj);
}

text::NodeAST TextPrint(const Yield_& obj, const text::IRPrinter& printer, const Path& path) {
  if (!IsExactType<YieldObj>(obj)) {
    return GenericDialectStmt(obj, printer, path);
  }
  ExprBuilder ctx;
  ctx.AddOperands(printer, obj->vars, path->Attr("vars"));
  if (ctx.ExprDerivable() || (ctx.dialects.empty() && ctx.StmtDerivable(printer, obj))) {
    return text::ExprStmtAST(text::YieldAST(StmtValue(std::move(ctx.operands))));
  }
  return ctx.StmtCall(printer, obj);
}

text::NodeAST TextPrint(const Break& obj, const text::IRPrinter& printer, const Path& path) {
  if (!IsExactType<BreakObj>(obj)) {
    return GenericDialectStmt(obj, printer, path);
  }
  ExprBuilder ctx;
  return ctx.StmtDerivable(printer, obj) ? text::BreakAST() : ctx.StmtCall(printer, obj);
}

text::NodeAST TextPrint(const Continue& obj, const text::IRPrinter& printer, const Path& path) {
  if (!IsExactType<ContinueObj>(obj)) {
    return GenericDialectStmt(obj, printer, path);
  }
  ExprBuilder ctx;
  return ctx.StmtDerivable(printer, obj) ? text::ContinueAST() : ctx.StmtCall(printer, obj);
}

/***************************************************************/
/*************** Section 6: Call Expressions *******************/
/***************************************************************/

text::NodeAST TextPrint(const Call& obj, const text::IRPrinter& printer, const Path& path) {
  // TODO(@junrushao): There are three main issues we havne't considered:
  // (Issue 1) There are multiple possible `Call`s we want to support separately:
  // 1. Calling a function in the same Module
  // 2. Calling an Enum - TVM style `Op`
  // 3. Calling an external function symbol
  // 4. Calling a lambda?
  // (Issue 2) Support type parameters supplied to a call for dynamic shape usecases
  // (Issue 3) Support type relations for type inference
  ExprBuilder ctx;
  text::ExprAST callee;
  if (std::optional<String> symbol = obj->callee.as<String>()) {
    callee = text::IdAST(*symbol);
  } else if (std::optional<BaseFunc> func = obj->callee.as<BaseFunc>()) {
    callee = text::IdAST((*func)->symbol);
    ctx.dialects.push_back(DialectName(*func));
  } else if (std::optional<Expr> expr = obj->callee.as<Expr>()) {
    callee = printer->ToExpr(*expr, path->Attr("callee"));
    if (!callee->IsInstance<text::LiteralASTObj>()) {
      ctx.dialects.push_back(DialectName(*expr));
    }
  } else {
    callee = printer->ToExpr(obj->callee, path->Attr("callee"));
  }

  ctx.AddOperands(printer, obj->args, path->Attr("args"));
  ctx.AddAttrs(printer, obj->attr, path->Attr("attr"));

  bool use_native =
      obj->ty.as<AnyTyObj>() != nullptr &&
      (ctx.ExprDerivable() || (ctx.dialects.empty() && ctx.StmtDerivable(printer, obj)));
  if (use_native) {
    return callee->Call(std::move(ctx.operands));
  }

  ctx.operands.insert(ctx.operands.begin(), callee);
  ctx.AddTy(printer, obj->ty, path->Attr("ty"));
  return CallMnemonic(printer->cfg, obj)
      ->CallKw(std::move(ctx.operands), std::move(ctx.kwargs_keys), std::move(ctx.kwargs_values));
}

/****************************************************************/
/*************** Section 7: Body-Free Binding *******************/
/****************************************************************/

text::ExprAST DefineVarTuple(const text::IRPrinter& printer, const List<Var>& vars) {
  // Binding statements use assignment targets.  One var prints as "x", while
  // multiple vars print as a tuple target such as "x, y = rhs".
  if (vars.size() == 1) {
    return DefineVar(printer, vars[0]);
  }
  List<text::ExprAST> lhs_vars;
  lhs_vars.reserve(static_cast<int64_t>(vars.size()));
  for (const Var& var : vars) {
    lhs_vars.push_back(DefineVar(printer, var));
  }
  return text::TupleAST(std::move(lhs_vars));
}

std::pair<text::ExprAST, List<Var>> ScopeBindingCall(const text::IRPrinter& printer,
                                                     const Stmt& bind, const Path& path) {
  ExprBuilder ctx;
  FieldCollectionResult fields(List<Any>{}, DictAttrs(Dict<String, Any>{}), List<Var>{},
                               List<Node>{});
  if (std::optional<BaseBindExpr> bind_expr = bind.as<BaseBindExpr>()) {
    ctx.AddOperand(printer, (*bind_expr)->expr, path->Attr("expr"));
    if (std::optional<FieldCollectionResult> collected = CollectDialectFields(*bind_expr)) {
      fields = collected.value();
      TVM_FFI_CHECK(fields->body.empty(), TypeError)
          << "ffi.std.BaseBindExpr text printer does not support body fields";
    }
  } else if (std::optional<BaseVarDef> var_def = bind.as<BaseVarDef>()) {
    if (std::optional<FieldCollectionResult> collected = CollectDialectFields(*var_def)) {
      fields = collected.value();
      TVM_FFI_CHECK(fields->body.empty(), TypeError)
          << "ffi.std.BaseVarDef text printer does not support body fields";
    }
  } else {
    TVM_FFI_THROW(ValueError) << "ffi.std.Scope expected BaseBindExpr or BaseVarDef";
  }
  ctx.AddDialectFields(printer, fields, path);
  return {CallMnemonic(printer->cfg, bind)
              ->CallKw(std::move(ctx.operands), std::move(ctx.kwargs_keys),
                       std::move(ctx.kwargs_values)),
          fields->outs};
}

text::NodeAST TextPrint(const BaseBindExpr& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->expr, path->Attr("expr"));
  std::optional<FieldCollectionResult> collected = CollectDialectFields(obj);
  if (!collected.has_value()) {
    return ctx.StmtCall(printer, obj);
  }
  const FieldCollectionResult& fields = collected.value();
  TVM_FFI_CHECK(fields->body.empty(), TypeError)
      << "ffi.std.BaseBindExpr text printer does not support body fields";
  ctx.AddDialectFields(printer, fields, path);
  text::ExprAST rhs = CallMnemonic(printer->cfg, obj)
                          ->CallKw(std::move(ctx.operands), std::move(ctx.kwargs_keys),
                                   std::move(ctx.kwargs_values));
  if (fields->outs.empty()) {
    return text::ExprStmtAST(std::move(rhs));
  }
  return text::AssignAST(DefineVarTuple(printer, fields->outs), std::move(rhs));
}

text::NodeAST TextPrint(const BindExpr& obj, const text::IRPrinter& printer, const Path& path) {
  // Binding expressions keep literal type annotations on the RHS, unlike
  // arithmetic/operator sugar where typed immediates collapse to Python
  // literals.
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->expr, path->Attr("expr"));
  FieldCollectionResult fields = CollectRequiredDialectFields(obj);
  TVM_FFI_CHECK(fields->body.empty(), TypeError)
      << "ffi.std.BindExpr text printer does not support body fields";
  ctx.AddDialectFields(printer, fields, path);
  text::ExprAST rhs = ctx.kwargs_keys.empty() && ctx.operands.size() == 1
                          ? ctx.operands[0]
                          : CallMnemonic(printer->cfg, obj)
                                ->CallKw(std::move(ctx.operands), std::move(ctx.kwargs_keys),
                                         std::move(ctx.kwargs_values));
  if (fields->outs.empty()) {
    return text::ExprStmtAST(std::move(rhs));
  }
  return text::AssignAST(DefineVarTuple(printer, fields->outs), std::move(rhs));
}

text::NodeAST TextPrint(const BaseVarDef& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  std::optional<FieldCollectionResult> collected = CollectDialectFields(obj);
  if (!collected.has_value()) {
    return ctx.StmtCall(printer, obj);
  }
  const FieldCollectionResult& fields = collected.value();
  TVM_FFI_CHECK(fields->body.empty(), TypeError)
      << "ffi.std.BaseVarDef text printer does not support body fields";
  ctx.AddDialectFields(printer, fields, path);
  if (!fields->outs.empty()) {
    TVM_FFI_CHECK_EQ(fields->outs.size(), 1, TypeError)
        << obj->GetTypeKey() << " generic collector text printer requires exactly one "
        << "out target, got " << fields->outs.size();
    return text::AssignAST(DefineVarTuple(printer, fields->outs),
                           CallMnemonic(printer->cfg, obj)
                               ->CallKw(std::move(ctx.operands), std::move(ctx.kwargs_keys),
                                        std::move(ctx.kwargs_values)));
  }
  return ctx.StmtCall(printer, obj);
}

text::NodeAST TextPrint(const VarDef& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  FieldCollectionResult fields = CollectRequiredDialectFields(obj);
  TVM_FFI_CHECK(fields->body.empty(), TypeError)
      << "ffi.std.VarDef text printer does not support body fields";
  ctx.AddDialectFields(printer, fields, path);
  if (fields->outs.empty()) {
    if (ctx.kwargs_keys.empty()) {
      return text::ExprStmtAST(text::IdAST("pass"));
    }
    return ctx.StmtCall(printer, obj);
  }
  text::ExprAST rhs = ctx.kwargs_keys.empty()
                          ? CallMnemonic(printer->cfg, obj)->Call(std::move(ctx.operands))
                          : CallMnemonic(printer->cfg, obj)
                                ->CallKw(std::move(ctx.operands), std::move(ctx.kwargs_keys),
                                         std::move(ctx.kwargs_values));
  return text::AssignAST(DefineVarTuple(printer, fields->outs), std::move(rhs));
}

/*****************************************************************/
/*************** Section 8. Body-Bearing Stmts *******************/
/*****************************************************************/

text::NodeAST TextPrint(const Module& obj, const text::IRPrinter& printer, const Path& path) {
  ScopeBuilder ctx("module", DialectName(obj), printer->cfg);
  ctx.AddBodyStmts(printer, obj->funcs, path->Attr("funcs"));
  return text::ClassAST(text::IdAST("MyModule"), {}, {ctx.scope_call}, std::move(ctx.body));
}

text::NodeAST TextPrint(const IfStmt& obj, const text::IRPrinter& printer, const Path& path) {
  return text::IfAST(printer->ToExpr(obj->cond, path->Attr("cond")),
                     PrintList<text::StmtAST>(printer, obj->then_body, path->Attr("then_body")),
                     PrintList<text::StmtAST>(printer, obj->else_body, path->Attr("else_body")));
}

text::NodeAST TextPrint(const BaseWhile& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->cond, path->Attr("cond"));
  std::optional<FieldCollectionResult> collected = CollectDialectFields(obj);
  if (!collected.has_value()) {
    return ctx.StmtCall(printer, obj);
  }
  const FieldCollectionResult& fields = collected.value();
  TVM_FFI_CHECK(fields->outs.empty(), TypeError)
      << "ffi.std.BaseWhile text printer does not support out fields";
  ScopeBuilder scope("while_", DialectName(obj), printer->cfg);
  scope.scope_call = CallMnemonic(printer->cfg, obj);
  scope.operands.push_back(printer->ToExpr(obj->cond, path->Attr("cond")));
  scope.AddDialectArgsAttrs(printer, fields, path);
  scope.AddBodyStmts(printer, fields->body, path->Attr("body"));
  return text::WithAST({}, scope.StmtCall(false), std::move(scope.body));
}

text::NodeAST TextPrint(const BaseFor& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  ctx.AddOperand(printer, obj->extent, path->Attr("extent"));
  ctx.operands.push_back(DefineVar(printer, obj->var));
  std::optional<FieldCollectionResult> collected = CollectDialectFields(obj);
  if (!collected.has_value()) {
    return ctx.StmtCall(printer, obj);
  }
  const FieldCollectionResult& fields = collected.value();
  TVM_FFI_CHECK(fields->outs.empty(), TypeError)
      << "ffi.std.BaseFor text printer does not support out fields";
  ScopeBuilder scope("range", "", printer->cfg);
  scope.scope_call = CallMnemonic(printer->cfg, obj);
  scope.AddTargets(printer, {obj->var});
  scope.operands.push_back(printer->ToExpr(obj->extent, path->Attr("extent")));
  Ty inferred_ty = PrimTy(kDefaultIntLiteralType);
  if (obj->extent.as<IntImmObj>() == nullptr || obj->extent->ty.as<AnyTyObj>() == nullptr) {
    inferred_ty = obj->extent->ty;
  }
  if (!StructuralEqual::Equal(obj->var->ty, inferred_ty)) {
    scope.kwargs_keys.push_back("ty");
    scope.kwargs_values.push_back(printer->ToExpr(obj->var->ty, path->Attr("var")->Attr("ty")));
  }
  scope.AddDialectArgsAttrs(printer, fields, path);
  scope.AddBodyStmts(printer, fields->body, path->Attr("body"));
  return text::ForAST(*scope.Target(/*create_placeholder_for_none=*/true), scope.StmtCall(false),
                      std::move(scope.body));
}

text::NodeAST TextPrint(const BaseFunc& obj, const text::IRPrinter& printer, const Path& path) {
  List<text::ExprAST> explicit_args;
  explicit_args.reserve(static_cast<int64_t>(obj->args.size()));
  for (const Var& arg : obj->args) {
    explicit_args.push_back(DefineVar(printer, arg));
  }
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  if (obj->ret_type.has_value()) {
    kwargs_keys.push_back("ret_type");
    kwargs_values.push_back(printer->ToExpr(*obj->ret_type, path->Attr("ret_type")));
  }
  std::optional<FieldCollectionResult> collected = CollectDialectFields(obj);
  if (!collected.has_value()) {
    return text::ExprStmtAST(
        CallMnemonic(printer->cfg, obj)
            ->CallKw({text::LiteralAST(obj->symbol), text::ListAST(std::move(explicit_args))},
                     std::move(kwargs_keys), std::move(kwargs_values)));
  }
  const FieldCollectionResult& fields = collected.value();
  TVM_FFI_CHECK(fields->outs.empty(), TypeError)
      << "ffi.std.BaseFunc text printer does not support out fields";

  ScopeBuilder scope("func", DialectName(obj), printer->cfg);
  scope.scope_call = CallMnemonic(printer->cfg, obj);
  scope.AddDialectArgsAttrs(printer, fields, path);
  List<text::AssignAST> args;
  int64_t n = static_cast<int64_t>(obj->args.size());
  args.reserve(n);
  Path args_path = path->Attr("args");
  for (int64_t i = 0; i < n; ++i) {
    const Var& arg = obj->args[i];
    args.push_back(text::AssignAST(DefineVar(printer, arg), {},
                                   printer->ToExpr(arg->ty, args_path->ArrayItem(i)->Attr("ty"))));
  }
  scope.AddBodyStmts(printer, fields->body, path->Attr("body"));
  Optional<text::ExprAST> ret_type;
  if (obj->ret_type.has_value()) {
    ret_type = printer->ToExpr(*obj->ret_type, path->Attr("ret_type"));
  }
  return text::FunctionAST(text::IdAST(obj->symbol), std::move(args), {scope.StmtCall(true)},
                           std::move(ret_type), std::move(scope.body));
}

text::NodeAST TextPrint(const BaseScope& obj, const text::IRPrinter& printer, const Path& path) {
  ExprBuilder ctx;
  std::optional<FieldCollectionResult> collected = CollectDialectFields(obj);
  if (!collected.has_value()) {
    return ctx.StmtCall(printer, obj);
  }
  const FieldCollectionResult& fields = collected.value();
  ScopeBuilder scope("scope", DialectName(obj), printer->cfg);
  scope.scope_call = CallMnemonic(printer->cfg, obj);
  scope.AddDialectArgsAttrs(printer, fields, path);
  scope.AddTargets(printer, fields->outs);
  scope.AddBodyStmts(printer, fields->body, path->Attr("body"));
  return text::WithAST(scope.Target(/*create_placeholder_for_none=*/false), scope.StmtCall(false),
                       std::move(scope.body));
}

text::NodeAST TextPrint(const While& obj, const text::IRPrinter& printer, const Path& path) {
  ScopeBuilder ctx("while_", DialectName(obj), printer->cfg);
  FieldCollectionResult fields = CollectRequiredDialectFields(obj);
  TVM_FFI_CHECK(fields->outs.empty(), TypeError)
      << "ffi.std.While text printer does not support out fields";
  ctx.AddDialectArgsAttrs(printer, fields, path);
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  ctx.AddBodyStmts(printer, fields->body, path->Attr("body"));
  text::ExprAST cond = printer->ToExpr(obj->cond, path->Attr("cond"));
  if (ctx.operands.empty() && ctx.kwargs_keys.empty()) {
    return text::WhileAST(std::move(cond), std::move(ctx.body));
  } else {
    ctx.operands.insert(ctx.operands.begin(), cond);
    return text::WithAST({}, ctx.StmtCall(false), std::move(ctx.body));
  }
}

text::NodeAST TextPrint(const For& obj, const text::IRPrinter& printer, const Path& path) {
  ScopeBuilder ctx("range", "", printer->cfg);
  FieldCollectionResult fields = CollectRequiredDialectFields(obj);
  TVM_FFI_CHECK(fields->outs.empty(), TypeError)
      << "ffi.std.For text printer does not support out fields";
  ctx.AddTargets(printer, {obj->var});
  // ----------- "range" section ----------- //
  Ty inferred_ty = PrimTy(kDefaultIntLiteralType);
  if (obj->start.has_value()) {
    ctx.operands.push_back(printer->ToExpr(*obj->start, path->Attr("start")));
    ctx.operands.push_back(printer->ToExpr(obj->extent, path->Attr("extent")));
    if ((*obj->start).as<IntImmObj>() == nullptr || (*obj->start)->ty.as<AnyTyObj>() == nullptr) {
      inferred_ty = (*obj->start)->ty;
    }
  } else {
    ctx.operands.push_back(printer->ToExpr(obj->extent, path->Attr("extent")));
  }
  if (obj->extent.as<IntImmObj>() == nullptr || obj->extent->ty.as<AnyTyObj>() == nullptr) {
    inferred_ty = obj->extent->ty;
  }
  if (obj->step.has_value()) {
    ctx.kwargs_keys.push_back("step");
    ctx.kwargs_values.push_back(printer->ToExpr(*obj->step, path->Attr("step")));
    if ((*obj->step).as<IntImmObj>() == nullptr || (*obj->step)->ty.as<AnyTyObj>() == nullptr) {
      inferred_ty = (*obj->step)->ty;
    }
  }
  if (!StructuralEqual::Equal(obj->var->ty, inferred_ty)) {
    ctx.kwargs_keys.push_back("ty");
    ctx.kwargs_values.push_back(printer->ToExpr(obj->var->ty, path->Attr("var")->Attr("ty")));
  }
  // --------------------------------------- //
  ctx.AddDialectArgsAttrs(printer, fields, path);
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  ctx.AddBodyStmts(printer, fields->body, path->Attr("body"));
  text::ExprAST lhs = *ctx.Target(/*create_placeholder_for_none=*/true);
  text::ExprAST rhs = ctx.StmtCall(false);
  return text::ForAST(std::move(lhs), std::move(rhs), std::move(ctx.body));
}

text::NodeAST TextPrint(const Func& obj, const text::IRPrinter& printer, const Path& path) {
  // TODO(@junrushao): Handle dynamic shape, where a VarDef may contain other variable definition.
  ScopeBuilder ctx("func", DialectName(obj), printer->cfg);
  FieldCollectionResult fields = CollectRequiredDialectFields(obj);
  TVM_FFI_CHECK(fields->outs.empty(), TypeError)
      << "ffi.std.Func text printer does not support out fields";
  ctx.AddDialectArgsAttrs(printer, fields, path);
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  // ----------- "args" section ----------- //
  List<text::AssignAST> args;
  int64_t n = static_cast<int64_t>(obj->args.size());
  args.reserve(n);
  Path args_path = path->Attr("args");
  for (int64_t i = 0; i < n; ++i) {
    const Var& arg = obj->args[i];
    args.push_back(text::AssignAST(DefineVar(printer, arg), {},
                                   printer->ToExpr(arg->ty, args_path->ArrayItem(i)->Attr("ty"))));
  }
  // -------------------------------------- //
  ctx.AddBodyStmts(printer, fields->body, path->Attr("body"));
  Optional<text::ExprAST> ret_type;
  if (obj->ret_type.has_value()) {
    ret_type = printer->ToExpr(*obj->ret_type, path->Attr("ret_type"));
  }
  return text::FunctionAST(text::IdAST(obj->symbol), std::move(args), {ctx.StmtCall(true)},
                           std::move(ret_type), std::move(ctx.body));
}

text::NodeAST TextPrint(const Scope& obj, const text::IRPrinter& printer, const Path& path) {
  ScopeBuilder ctx("scope", DialectName(obj), printer->cfg);
  FieldCollectionResult fields = CollectRequiredDialectFields(obj);
  TVM_FFI_CHECK(fields->outs.empty(), TypeError)
      << "ffi.std.Scope text printer does not support out fields";
  int64_t n = static_cast<int64_t>(obj->binds.size());
  ctx.operands.reserve(n);
  Path binds_path = path->Attr("binds");
  for (int64_t i = 0; i < n; ++i) {
    const Stmt& bind = obj->binds[i];
    auto [binding_call, vars] = ScopeBindingCall(printer, bind, binds_path->ArrayItem(i));
    ctx.operands.push_back(binding_call);
    ctx.AddTargets(printer, vars);
  }
  ctx.AddDialectArgsAttrs(printer, fields, path);
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  ctx.AddBodyStmts(printer, fields->body, path->Attr("body"));
  if (ctx.operands.empty() && ctx.kwargs_keys.empty()) {
    return text::StmtBlockAST(std::move(ctx.body));
  }
  Optional<text::ExprAST> lhs = ctx.Target(/*create_placeholder_for_none=*/false);
  text::ExprAST rhs = ctx.StmtCall(false);
  return text::WithAST(std::move(lhs), std::move(rhs), std::move(ctx.body));
}

// NOLINTEND(bugprone-misplaced-widening-cast,bugprone-narrowing-conversions)

template <typename T>
auto TextPrintHook() {
  return [](const T& obj, const text::IRPrinter& printer, const Path& path) -> text::NodeAST {
    return TextPrint(obj, printer, path);
  };
}

Expr CoerceInitArgToExpr(AnyView value, const Ty& result_ty) {
  TVMFFIAny raw = value.CopyToTVMFFIAny();
  if (std::optional<Expr> expr = ObjectRefTypeTraitsBase<Expr>::TryCastFromAnyView(&raw)) {
    return *std::move(expr);
  }

  if (const PrimTyObj* prim_ty = result_ty.as<PrimTyObj>()) {
    if (raw.type_index == TypeIndex::kTVMFFIBool) {
      bool bool_value = TypeTraits<bool>::CopyFromAnyViewAfterCheck(&raw);
      if (DTypeIsBool(prim_ty->dtype)) {
        return BoolImm(result_ty, bool_value);
      }
      if (DTypeIsInt(prim_ty->dtype)) {
        return IntImm(result_ty, static_cast<int64_t>(bool_value));
      }
      if (DTypeIsFloat(prim_ty->dtype)) {
        return FloatImm(result_ty, static_cast<double>(bool_value));
      }
    }
    if (std::optional<int64_t> int_value = TypeTraits<int64_t>::TryCastFromAnyView(&raw)) {
      if (DTypeIsBool(prim_ty->dtype)) {
        return BoolImm(result_ty, static_cast<bool>(*int_value));
      }
      if (DTypeIsInt(prim_ty->dtype)) {
        return IntImm(result_ty, *int_value);
      }
      if (DTypeIsFloat(prim_ty->dtype)) {
        return FloatImm(result_ty, static_cast<double>(*int_value));
      }
    }
    if (raw.type_index == TypeIndex::kTVMFFIFloat) {
      double float_value = TypeTraits<double>::CopyFromAnyViewAfterCheck(&raw);
      if (DTypeIsBool(prim_ty->dtype)) {
        return BoolImm(result_ty, static_cast<bool>(float_value));
      }
      if (DTypeIsInt(prim_ty->dtype)) {
        return IntImm(result_ty, static_cast<int64_t>(float_value));
      }
      if (DTypeIsFloat(prim_ty->dtype)) {
        return FloatImm(result_ty, float_value);
      }
    }
  }

  if (result_ty.as<AnyTyObj>() != nullptr) {
    if (raw.type_index == TypeIndex::kTVMFFIBool) {
      return BoolImm(result_ty, TypeTraits<bool>::CopyFromAnyViewAfterCheck(&raw));
    }
    if (std::optional<int64_t> int_value = TypeTraits<int64_t>::TryCastFromAnyView(&raw)) {
      return IntImm(result_ty, *int_value);
    }
    if (raw.type_index == TypeIndex::kTVMFFIFloat) {
      return FloatImm(result_ty, TypeTraits<double>::CopyFromAnyViewAfterCheck(&raw));
    }
    if (std::optional<String> str_value = TypeTraits<String>::TryCastFromAnyView(&raw)) {
      return StringImm(result_ty, *std::move(str_value));
    }
  }

  if (std::optional<Expr> expr = TypeTraits<Expr>::TryCastFromAnyView(&raw)) {
    return *std::move(expr);
  }
  TVM_FFI_THROW(TypeError) << "Unsupported type for conversion to Expr: " << value.GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

Ty BoolLikeTy(const Ty& ty) {
  if (!ty.defined() || ty.as<AnyTyObj>() != nullptr) {
    return AnyTy();
  }
  if (const PrimTyObj* prim_ty = ty.as<PrimTyObj>()) {
    DLDataType dtype{static_cast<uint8_t>(kDLBool), 8, prim_ty->dtype.lanes};
    return PrimTy(dtype);
  }
  if (const TensorTyObj* tensor_ty = ty.as<TensorTyObj>()) {
    DLDataType dtype{static_cast<uint8_t>(kDLBool), 8, tensor_ty->dtype.lanes};
    return TensorTy(tensor_ty->shape, dtype);
  }
  return AnyTy();
}

std::optional<DLDataType> TryDTypeFromTy(const Ty& ty) {
  if (!ty.defined() || ty.as<AnyTyObj>() != nullptr) {
    return std::nullopt;
  }
  if (const PrimTyObj* prim_ty = ty.as<PrimTyObj>()) {
    return prim_ty->dtype;
  }
  if (const TensorTyObj* tensor_ty = ty.as<TensorTyObj>()) {
    return tensor_ty->dtype;
  }
  return std::nullopt;
}

Ty ExprTyOrAny(const Expr& expr) {
  details::CheckExprDefined("expression operator", "operand", expr);
  if (expr->ty.as<AnyTyObj>() != nullptr) {
    return AnyTy();
  }
  return expr->ty;
}

Ty ValueTyOrAny(AnyView value) {
  TVMFFIAny raw = value.CopyToTVMFFIAny();
  if (std::optional<Expr> expr = ObjectRefTypeTraitsBase<Expr>::TryCastFromAnyView(&raw)) {
    return ExprTyOrAny(*expr);
  }
  if (raw.type_index == TypeIndex::kTVMFFIBool) {
    return PrimTy(kDefaultBoolLiteralType);
  }
  if (TypeTraits<int64_t>::TryCastFromAnyView(&raw).has_value()) {
    return PrimTy(kDefaultIntLiteralType);
  }
  if (raw.type_index == TypeIndex::kTVMFFIFloat) {
    return PrimTy(kDefaultFloatLiteralType);
  }
  return AnyTy();
}

Expr DefaultExprFromValue(AnyView value) { return CoerceInitArgToExpr(value, ValueTyOrAny(value)); }

std::optional<Expr> TryExprFromValue(AnyView value) {
  TVMFFIAny raw = value.CopyToTVMFFIAny();
  return ObjectRefTypeTraitsBase<Expr>::TryCastFromAnyView(&raw);
}

std::pair<Expr, Expr> CoerceBinaryValues(AnyView lhs, AnyView rhs) {
  std::optional<Expr> lhs_expr = TryExprFromValue(lhs);
  std::optional<Expr> rhs_expr = TryExprFromValue(rhs);
  if (lhs_expr.has_value() && !rhs_expr.has_value()) {
    return {*lhs_expr, CoerceInitArgToExpr(rhs, (*lhs_expr)->ty)};
  }
  if (!lhs_expr.has_value() && rhs_expr.has_value()) {
    return {CoerceInitArgToExpr(lhs, (*rhs_expr)->ty), *rhs_expr};
  }
  return {DefaultExprFromValue(lhs), DefaultExprFromValue(rhs)};
}

DLDataType PromoteDTypes(DLDataType lhs, DLDataType rhs) {
  if (lhs == rhs) {
    return lhs;
  }
  TVM_FFI_CHECK(lhs.lanes == rhs.lanes, TypeError)
      << "type mismatch: incompatible lane counts " << DLDataTypeToString(lhs) << " vs "
      << DLDataTypeToString(rhs);

  if (lhs.code == kDLFloat && rhs.code == kDLFloat) {
    return lhs.bits < rhs.bits ? rhs : lhs;
  }
  if (lhs.code != kDLFloat && rhs.code == kDLFloat) {
    return rhs;
  }
  if (lhs.code == kDLFloat && rhs.code != kDLFloat) {
    return lhs;
  }
  if (lhs.code != kDLBfloat && rhs.code == kDLBfloat) {
    return rhs;
  }
  if (lhs.code == kDLBfloat && rhs.code != kDLBfloat) {
    return lhs;
  }
  if ((lhs.code == kDLInt && rhs.code == kDLInt) || (lhs.code == kDLUInt && rhs.code == kDLUInt)) {
    return lhs.bits < rhs.bits ? rhs : lhs;
  }
  if ((lhs.code == kDLInt && rhs.code == kDLUInt) || (lhs.code == kDLUInt && rhs.code == kDLInt)) {
    if (lhs.bits < rhs.bits) {
      return rhs;
    }
    if (lhs.bits > rhs.bits) {
      return lhs;
    }
    return lhs.code == kDLUInt ? lhs : rhs;
  }
  TVM_FFI_THROW(TypeError) << "type mismatch: cannot match type " << DLDataTypeToString(lhs)
                           << " vs " << DLDataTypeToString(rhs);
  TVM_FFI_UNREACHABLE();
}

Ty PromoteTys(const Ty& lhs, const Ty& rhs) {
  TVM_FFI_CHECK(lhs.defined(), TypeError) << "type mismatch: lhs type must be defined";
  TVM_FFI_CHECK(rhs.defined(), TypeError) << "type mismatch: rhs type must be defined";
  if (StructuralEqual::Equal(lhs, rhs)) {
    return lhs;
  }
  if (lhs.as<AnyTyObj>() != nullptr || rhs.as<AnyTyObj>() != nullptr) {
    return AnyTy();
  }
  if (const TensorTyObj* lhs_tensor = lhs.as<TensorTyObj>()) {
    const TensorTyObj* rhs_tensor = rhs.as<TensorTyObj>();
    TVM_FFI_CHECK(rhs_tensor != nullptr, TypeError)
        << "type mismatch: cannot match type " << ReprPrint(lhs) << " vs " << ReprPrint(rhs);
    TVM_FFI_CHECK(StructuralEqual::Equal(lhs_tensor->shape, rhs_tensor->shape), TypeError)
        << "type mismatch: cannot match tensor shape " << ReprPrint(lhs) << " vs "
        << ReprPrint(rhs);
    return TensorTy(lhs_tensor->shape, PromoteDTypes(lhs_tensor->dtype, rhs_tensor->dtype));
  }
  const PrimTyObj* lhs_prim = lhs.as<PrimTyObj>();
  const PrimTyObj* rhs_prim = rhs.as<PrimTyObj>();
  TVM_FFI_CHECK(lhs_prim != nullptr && rhs_prim != nullptr, TypeError)
      << "type mismatch: cannot match type " << ReprPrint(lhs) << " vs " << ReprPrint(rhs);
  return PrimTy(PromoteDTypes(lhs_prim->dtype, rhs_prim->dtype));
}

int64_t FoldInt64(int64_t value, DLDataType dtype) {
  if (DTypeIsBool(dtype)) {
    return value != 0;
  }
  if (dtype.bits < 64) {
    uint64_t mask = (uint64_t{1} << dtype.bits) - 1;
    uint64_t wrapped = static_cast<uint64_t>(value) & mask;
    if (dtype.code == kDLInt) {
      uint64_t sign_bit = uint64_t{1} << (dtype.bits - 1);
      return static_cast<int64_t>((wrapped ^ sign_bit) - sign_bit);
    }
    return static_cast<int64_t>(wrapped);
  }
  return value;
}

double FoldFloat32(double value) {
  double res = static_cast<double>(static_cast<float>(value));
  if (std::isinf(res) || std::isnan(res)) {
    return res;
  }
  if (res < std::numeric_limits<float>::lowest()) {
    return -std::numeric_limits<double>::infinity();
  }
  if (res > std::numeric_limits<float>::max()) {
    return std::numeric_limits<double>::infinity();
  }
  return res;
}

std::optional<int64_t> TryIntImmValue(const Expr& expr) {
  if (const IntImmObj* int_imm = expr.as<IntImmObj>()) {
    return std::optional<int64_t>(int_imm->value);
  }
  if (const BoolImmObj* bool_imm = expr.as<BoolImmObj>()) {
    return std::optional<int64_t>(static_cast<int64_t>(bool_imm->value));
  }
  return std::nullopt;
}

std::optional<double> TryFloatImmValue(const Expr& expr) {
  if (const FloatImmObj* float_imm = expr.as<FloatImmObj>()) {
    return std::optional<double>(float_imm->value);
  }
  return std::nullopt;
}

Expr IntImmLike(const Ty& ty, int64_t value) {
  if (std::optional<DLDataType> dtype = TryDTypeFromTy(ty)) {
    if (DTypeIsBool(*dtype)) {
      return BoolImm(ty, value != 0);
    }
    return IntImm(ty, FoldInt64(value, *dtype));
  }
  return IntImm(ty, value);
}

Expr FloatImmLike(const Ty& ty, double value) {
  if (std::optional<DLDataType> dtype = TryDTypeFromTy(ty)) {
    if (dtype->code == kDLFloat && dtype->bits == 32) {
      return FloatImm(ty, FoldFloat32(value));
    }
  }
  return FloatImm(ty, value);
}

Expr CastExprTo(Expr value, const Ty& ty) {
  if (StructuralEqual::Equal(value->ty, ty)) {
    return value;
  }
  if (const PrimTyObj* prim_ty = ty.as<PrimTyObj>()) {
    if (std::optional<int64_t> int_value = TryIntImmValue(value)) {
      if (DTypeIsBool(prim_ty->dtype)) {
        return BoolImm(ty, *int_value != 0);
      }
      if (DTypeIsInt(prim_ty->dtype)) {
        return IntImmLike(ty, *int_value);
      }
      if (DTypeIsFloat(prim_ty->dtype)) {
        return FloatImmLike(ty, static_cast<double>(*int_value));
      }
    }
    if (std::optional<double> float_value = TryFloatImmValue(value)) {
      if (DTypeIsBool(prim_ty->dtype)) {
        return BoolImm(ty, *float_value != 0.0);
      }
      if (DTypeIsInt(prim_ty->dtype)) {
        return IntImmLike(ty, static_cast<int64_t>(*float_value));
      }
      if (DTypeIsFloat(prim_ty->dtype)) {
        return FloatImmLike(ty, *float_value);
      }
    }
  }
  return Cast(ty, value);
}

Ty MatchBinaryTypes(Expr* lhs, Expr* rhs) {
  details::CheckExprDefined("binary expression", "a", *lhs);
  details::CheckExprDefined("binary expression", "b", *rhs);
  Ty result_ty = PromoteTys((*lhs)->ty, (*rhs)->ty);
  if (result_ty.as<AnyTyObj>() == nullptr) {
    *lhs = CastExprTo(*lhs, result_ty);
    *rhs = CastExprTo(*rhs, result_ty);
  }
  return result_ty;
}

Ty CommonValueTy(AnyView a, AnyView b) {
  auto [lhs, rhs] = CoerceBinaryValues(a, b);
  return MatchBinaryTypes(&lhs, &rhs);
}

void ExpectIntOrUInt(const char* op_name, const Expr& expr, const char* operand_name) {
  if (std::optional<DLDataType> dtype = TryDTypeFromTy(expr->ty)) {
    TVM_FFI_CHECK(DTypeIsInt(*dtype), TypeError)
        << op_name << " expected integer dtype for " << operand_name << ", but got "
        << DLDataTypeToString(*dtype);
  }
}

void ExpectBool(const char* op_name, const Expr& expr, const char* operand_name) {
  if (std::optional<DLDataType> dtype = TryDTypeFromTy(expr->ty)) {
    TVM_FFI_CHECK(DTypeIsBool(*dtype), TypeError)
        << op_name << " expected bool dtype for " << operand_name << ", but got "
        << DLDataTypeToString(*dtype);
  }
}

void CheckShiftAmount(const char* op_name, const Expr& rhs, DLDataType dtype) {
  if (std::optional<int64_t> shift = TryIntImmValue(rhs)) {
    TVM_FFI_CHECK(*shift >= 0 && *shift < dtype.bits, ValueError)
        << op_name << " shift amount must be non-negative and less than "
        << static_cast<int32_t>(dtype.bits) << " bit(s) for type " << DLDataTypeToString(dtype);
  }
}

int64_t FloorDivValue(int64_t lhs, int64_t rhs) {
  int64_t div = lhs / rhs;
  int64_t mod = lhs % rhs;
  bool already_floor = (rhs >= 0 && mod >= 0) || (rhs < 0 && mod <= 0);
  return already_floor ? div : div - 1;
}

int64_t FloorModValue(int64_t lhs, int64_t rhs) {
  int64_t mod = lhs % rhs;
  bool already_floor = (rhs >= 0 && mod >= 0) || (rhs < 0 && mod <= 0);
  return already_floor ? mod : mod + rhs;
}

template <typename TObj>
int64_t FoldBitwiseValue(int64_t lhs, int64_t rhs) {
  if constexpr (std::is_same_v<TObj, BitwiseAndObj>) {
    return lhs & rhs;
  } else if constexpr (std::is_same_v<TObj, BitwiseOrObj>) {
    return lhs | rhs;
  } else {
    return lhs ^ rhs;
  }
}

template <typename TObj, typename T>
bool CompareValue(T lhs, T rhs) {
  if constexpr (std::is_same_v<TObj, EqObj>) {
    return lhs == rhs;
  } else if constexpr (std::is_same_v<TObj, NeObj>) {
    return lhs != rhs;
  } else if constexpr (std::is_same_v<TObj, LeObj>) {
    return lhs <= rhs;
  } else if constexpr (std::is_same_v<TObj, GeObj>) {
    return lhs >= rhs;
  } else if constexpr (std::is_same_v<TObj, GtObj>) {
    return lhs > rhs;
  } else {
    return lhs < rhs;
  }
}

template <typename TObj>
std::optional<Expr> TryFoldBinary(const Ty& ty, const Expr& lhs, const Expr& rhs) {
  std::optional<DLDataType> dtype = TryDTypeFromTy(ty);
  std::optional<int64_t> lhs_int = TryIntImmValue(lhs);
  std::optional<int64_t> rhs_int = TryIntImmValue(rhs);
  std::optional<double> lhs_float = TryFloatImmValue(lhs);
  std::optional<double> rhs_float = TryFloatImmValue(rhs);
  if constexpr (std::is_same_v<TObj, AddObj>) {
    if (lhs_int && rhs_int) return IntImmLike(ty, *lhs_int + *rhs_int);
    if (lhs_int && *lhs_int == 0) return rhs;
    if (rhs_int && *rhs_int == 0) return lhs;
    if (lhs_float && rhs_float) return FloatImmLike(ty, *lhs_float + *rhs_float);
    if (lhs_float && *lhs_float == 0.0) return rhs;
    if (rhs_float && *rhs_float == 0.0) return lhs;
  } else if constexpr (std::is_same_v<TObj, SubObj>) {
    if (lhs_int && rhs_int) return IntImmLike(ty, *lhs_int - *rhs_int);
    if (rhs_int && *rhs_int == 0) return lhs;
    if (lhs_float && rhs_float) return FloatImmLike(ty, *lhs_float - *rhs_float);
    if (rhs_float && *rhs_float == 0.0) return lhs;
  } else if constexpr (std::is_same_v<TObj, MulObj>) {
    if (lhs_int && rhs_int) return IntImmLike(ty, *lhs_int * *rhs_int);
    if (lhs_int && *lhs_int == 1) return rhs;
    if (lhs_int && *lhs_int == 0) return lhs;
    if (rhs_int && *rhs_int == 1) return lhs;
    if (rhs_int && *rhs_int == 0) return rhs;
    if (lhs_float && rhs_float) return FloatImmLike(ty, *lhs_float * *rhs_float);
    if (lhs_float && *lhs_float == 1.0) return rhs;
    if (lhs_float && *lhs_float == 0.0) return lhs;
    if (rhs_float && *rhs_float == 1.0) return lhs;
    if (rhs_float && *rhs_float == 0.0) return rhs;
  } else if constexpr (std::is_same_v<TObj, CDivObj>) {
    if (rhs_int && *rhs_int == 0) TVM_FFI_THROW(ValueError) << "Divide by zero";
    if (rhs_float && *rhs_float == 0.0) TVM_FFI_THROW(ValueError) << "Divide by zero";
    if (lhs_int && rhs_int) return IntImmLike(ty, *lhs_int / *rhs_int);
    if (lhs_int && *lhs_int == 0) return lhs;
    if (rhs_int && *rhs_int == 1) return lhs;
    if (lhs_float && rhs_float) return FloatImmLike(ty, *lhs_float / *rhs_float);
    if (lhs_float && *lhs_float == 0.0) return lhs;
    if (rhs_float && *rhs_float == 1.0) return lhs;
  } else if constexpr (std::is_same_v<TObj, CModObj>) {
    if (rhs_int && *rhs_int == 0) TVM_FFI_THROW(ValueError) << "Divide by zero";
    if (rhs_float && *rhs_float == 0.0) TVM_FFI_THROW(ValueError) << "Divide by zero";
    if (lhs_int && rhs_int) return IntImmLike(ty, *lhs_int % *rhs_int);
    if (lhs_int && *lhs_int == 0) return lhs;
    if (rhs_int && *rhs_int == 1) return IntImmLike(ty, 0);
    if (lhs_float && rhs_float) return FloatImmLike(ty, std::fmod(*lhs_float, *rhs_float));
  } else if constexpr (std::is_same_v<TObj, FloorDivObj>) {
    if (rhs_int && *rhs_int == 0) TVM_FFI_THROW(ValueError) << "Divide by zero";
    if (rhs_float && *rhs_float == 0.0) TVM_FFI_THROW(ValueError) << "Divide by zero";
    if (lhs_int && rhs_int) return IntImmLike(ty, FloorDivValue(*lhs_int, *rhs_int));
    if (lhs_int && *lhs_int == 0) return lhs;
    if (rhs_int && *rhs_int == 1) return lhs;
    if (lhs_float && rhs_float) return FloatImmLike(ty, std::floor(*lhs_float / *rhs_float));
    if (lhs_float && *lhs_float == 0.0) return lhs;
    if (rhs_float && *rhs_float == 1.0) return lhs;
  } else if constexpr (std::is_same_v<TObj, FloorModObj>) {
    if (rhs_int && *rhs_int == 0) TVM_FFI_THROW(ValueError) << "Divide by zero";
    if (rhs_float && *rhs_float == 0.0) TVM_FFI_THROW(ValueError) << "Divide by zero";
    if (lhs_int && rhs_int) return IntImmLike(ty, FloorModValue(*lhs_int, *rhs_int));
    if (lhs_int && *lhs_int == 0) return lhs;
    if (rhs_int && *rhs_int == 1) return IntImmLike(ty, 0);
    if (lhs_float && rhs_float) {
      double mod = std::fmod(*lhs_float, *rhs_float);
      bool already_floor = (*rhs_float >= 0 && mod >= 0) || (*rhs_float < 0 && mod <= 0);
      return FloatImmLike(ty, already_floor ? mod : mod + *rhs_float);
    }
  } else if constexpr (std::is_same_v<TObj, PowObj>) {
    if (lhs_int && rhs_int && *rhs_int >= 0) {
      return IntImmLike(ty, static_cast<int64_t>(std::pow(*lhs_int, *rhs_int)));
    }
    if (lhs_float && rhs_float) return FloatImmLike(ty, std::pow(*lhs_float, *rhs_float));
    if (rhs_int && *rhs_int == 0) return IntImmLike(ty, 1);
    if (rhs_int && *rhs_int == 1) return lhs;
    if (rhs_float && *rhs_float == 0.0) return FloatImmLike(ty, 1.0);
    if (rhs_float && *rhs_float == 1.0) return lhs;
  } else if constexpr (std::is_same_v<TObj, MinObj>) {
    if (lhs.same_as(rhs)) return lhs;
    if (lhs_int && rhs_int) return IntImmLike(ty, std::min(*lhs_int, *rhs_int));
    if (lhs_float && std::isinf(*lhs_float) && *lhs_float > 0) return rhs;
    if (lhs_float && std::isinf(*lhs_float) && *lhs_float < 0) return lhs;
    if (rhs_float && std::isinf(*rhs_float) && *rhs_float > 0) return lhs;
    if (rhs_float && std::isinf(*rhs_float) && *rhs_float < 0) return rhs;
    if (lhs_float && rhs_float) return FloatImmLike(ty, std::min(*lhs_float, *rhs_float));
  } else if constexpr (std::is_same_v<TObj, MaxObj>) {
    if (lhs.same_as(rhs)) return lhs;
    if (lhs_int && rhs_int) return IntImmLike(ty, std::max(*lhs_int, *rhs_int));
    if (lhs_float && std::isinf(*lhs_float) && *lhs_float > 0) return lhs;
    if (lhs_float && std::isinf(*lhs_float) && *lhs_float < 0) return rhs;
    if (rhs_float && std::isinf(*rhs_float) && *rhs_float > 0) return rhs;
    if (rhs_float && std::isinf(*rhs_float) && *rhs_float < 0) return lhs;
    if (lhs_float && rhs_float) return FloatImmLike(ty, std::max(*lhs_float, *rhs_float));
  } else if constexpr (std::is_same_v<TObj, LShiftObj>) {
    if (dtype) CheckShiftAmount("LShift", rhs, *dtype);
    if (lhs_int && rhs_int) return IntImmLike(ty, *lhs_int << *rhs_int);
    if (rhs_int && *rhs_int == 0) return lhs;
  } else if constexpr (std::is_same_v<TObj, RShiftObj>) {
    if (dtype) CheckShiftAmount("RShift", rhs, *dtype);
    if (lhs_int && rhs_int) return IntImmLike(ty, *lhs_int >> *rhs_int);
    if (rhs_int && *rhs_int == 0) return lhs;
  } else if constexpr (std::is_same_v<TObj, BitwiseAndObj> || std::is_same_v<TObj, BitwiseOrObj> ||
                       std::is_same_v<TObj, BitwiseXorObj>) {
    if (lhs_int && rhs_int) {
      return IntImmLike(ty, FoldBitwiseValue<TObj>(*lhs_int, *rhs_int));
    }
  } else if constexpr (std::is_same_v<TObj, AndObj>) {
    if (lhs_int && *lhs_int != 0) return rhs;
    if (lhs_int && *lhs_int == 0) return lhs;
    if (rhs_int && *rhs_int != 0) return lhs;
    if (rhs_int && *rhs_int == 0) return rhs;
  } else if constexpr (std::is_same_v<TObj, OrObj>) {
    if (lhs_int && *lhs_int != 0) return lhs;
    if (lhs_int && *lhs_int == 0) return rhs;
    if (rhs_int && *rhs_int != 0) return rhs;
    if (rhs_int && *rhs_int == 0) return lhs;
  }
  return std::nullopt;
}

template <typename TObj>
std::optional<Expr> TryFoldComparison(const Ty& ty, const Expr& lhs, const Expr& rhs) {
  std::optional<int64_t> lhs_int = TryIntImmValue(lhs);
  std::optional<int64_t> rhs_int = TryIntImmValue(rhs);
  std::optional<double> lhs_float = TryFloatImmValue(lhs);
  std::optional<double> rhs_float = TryFloatImmValue(rhs);
  auto make_bool = [&](bool value) { return BoolImm(ty, value); };
  if (lhs_int && rhs_int) {
    return make_bool(CompareValue<TObj>(*lhs_int, *rhs_int));
  }
  if (lhs_float && rhs_float) {
    return make_bool(CompareValue<TObj>(*lhs_float, *rhs_float));
  }
  return std::nullopt;
}

template <typename TObj>
void CheckHelperOperands(const char* op_name, const Expr& lhs, const Expr& rhs) {
  if constexpr (std::is_same_v<TObj, LShiftObj> || std::is_same_v<TObj, RShiftObj> ||
                std::is_same_v<TObj, BitwiseAndObj> || std::is_same_v<TObj, BitwiseOrObj> ||
                std::is_same_v<TObj, BitwiseXorObj>) {
    ExpectIntOrUInt(op_name, lhs, "lhs");
    ExpectIntOrUInt(op_name, rhs, "rhs");
  } else if constexpr (std::is_same_v<TObj, AndObj> || std::is_same_v<TObj, OrObj>) {
    ExpectBool(op_name, lhs, "lhs");
    ExpectBool(op_name, rhs, "rhs");
  }
}

template <typename TObj>
Expr BuildBinaryExpr(const char* op_name, Expr lhs, Expr rhs) {
  Ty ty = MatchBinaryTypes(&lhs, &rhs);
  CheckHelperOperands<TObj>(op_name, lhs, rhs);
  if (std::optional<Expr> folded = TryFoldBinary<TObj>(ty, lhs, rhs)) {
    return *std::move(folded);
  }
  return Expr(ObjectPtr<ExprObj>(make_object<TObj>(std::move(ty), std::move(lhs), std::move(rhs))));
}

template <typename TObj>
Expr BuildComparisonExpr(Expr lhs, Expr rhs) {
  Ty value_ty = MatchBinaryTypes(&lhs, &rhs);
  Ty result_ty = BoolLikeTy(value_ty);
  if (std::optional<Expr> folded = TryFoldComparison<TObj>(result_ty, lhs, rhs)) {
    return *std::move(folded);
  }
  return Expr(
      ObjectPtr<ExprObj>(make_object<TObj>(std::move(result_ty), std::move(lhs), std::move(rhs))));
}

template <typename TObj>
ObjectRef InitBinaryExpr(AnyView a, AnyView b, Ty ty) {
  Expr lhs = CoerceInitArgToExpr(a, ty);
  Expr rhs = CoerceInitArgToExpr(b, ty);
  return ObjectRef(make_object<TObj>(std::move(ty), std::move(lhs), std::move(rhs)));
}

template <typename TObj>
ObjectRef InitComparisonExpr(AnyView a, AnyView b, Ty ty) {
  Ty value_ty = CommonValueTy(a, b);
  Expr lhs = CoerceInitArgToExpr(a, value_ty);
  Expr rhs = CoerceInitArgToExpr(b, value_ty);
  return ObjectRef(make_object<TObj>(std::move(ty), std::move(lhs), std::move(rhs)));
}

template <typename TObj>
ObjectRef InitUnaryExpr(AnyView operand, Ty ty) {
  Expr expr = CoerceInitArgToExpr(operand, ty);
  return ObjectRef(make_object<TObj>(std::move(ty), std::move(expr)));
}

ObjectRef InitIfExpr(AnyView cond, AnyView then_expr, AnyView else_expr, Ty ty) {
  Expr cond_value = CoerceInitArgToExpr(cond, PrimTy(kDefaultBoolLiteralType));
  Expr then_value = CoerceInitArgToExpr(then_expr, ty);
  Expr else_value = CoerceInitArgToExpr(else_expr, ty);
  return ObjectRef(make_object<IfExprObj>(std::move(ty), std::move(cond_value),
                                          std::move(then_value), std::move(else_value)));
}

ObjectRef InitLoad(AnyView lhs, List<Range> indices, const Optional<Ty>& ty) {
  TVMFFIAny raw = lhs.CopyToTVMFFIAny();
  std::optional<Expr> lhs_expr = ObjectRefTypeTraitsBase<Expr>::TryCastFromAnyView(&raw);
  TVM_FFI_CHECK(lhs_expr.has_value(), TypeError) << "std.Load base must be an expression";
  Expr lhs_value = *std::move(lhs_expr);
  Ty result_ty = ty.has_value() ? ty.value() : details::IndexedTy(lhs_value->ty, indices);
  return ObjectRef(
      make_object<LoadObj>(std::move(result_ty), std::move(lhs_value), std::move(indices)));
}

template <typename TObj>
Expr MakeBinaryExpr(Expr a, Expr b) {
  return BuildBinaryExpr<TObj>(TObj::_type_key, std::move(a), std::move(b));
}

template <typename TObj>
Expr MakeBinaryExpr(Expr a, AnyView b) {
  Expr rhs = CoerceInitArgToExpr(b, a->ty);
  return BuildBinaryExpr<TObj>(TObj::_type_key, std::move(a), std::move(rhs));
}

template <typename TObj>
Expr MakeBinaryExpr(AnyView a, Expr b) {
  Expr lhs = CoerceInitArgToExpr(a, b->ty);
  return BuildBinaryExpr<TObj>(TObj::_type_key, std::move(lhs), std::move(b));
}

template <typename TObj>
Expr MakeBinaryExpr(AnyView a, AnyView b) {
  auto [lhs, rhs] = CoerceBinaryValues(a, b);
  return BuildBinaryExpr<TObj>(TObj::_type_key, std::move(lhs), std::move(rhs));
}

template <typename TObj>
Expr MakeComparisonExpr(Expr a, Expr b) {
  return BuildComparisonExpr<TObj>(std::move(a), std::move(b));
}

template <typename TObj>
Expr MakeComparisonExpr(Expr a, AnyView b) {
  Expr rhs = CoerceInitArgToExpr(b, a->ty);
  return BuildComparisonExpr<TObj>(std::move(a), std::move(rhs));
}

template <typename TObj>
Expr MakeComparisonExpr(AnyView a, Expr b) {
  Expr lhs = CoerceInitArgToExpr(a, b->ty);
  return BuildComparisonExpr<TObj>(std::move(lhs), std::move(b));
}

template <typename TObj>
Expr MakeComparisonExpr(AnyView a, AnyView b) {
  auto [lhs, rhs] = CoerceBinaryValues(a, b);
  return BuildComparisonExpr<TObj>(std::move(lhs), std::move(rhs));
}

template <typename TObj>
Expr MakeUnaryExpr(Expr operand) {
  Ty ty = operand->ty;
  if constexpr (std::is_same_v<TObj, NotObj>) {
    ExpectBool("Not", operand, "operand");
    if (std::optional<int64_t> value = TryIntImmValue(operand)) {
      return BoolImm(ty, *value == 0);
    }
  } else if constexpr (std::is_same_v<TObj, BitwiseNotObj>) {
    ExpectIntOrUInt("BitwiseNot", operand, "operand");
  } else if constexpr (std::is_same_v<TObj, AbsObj>) {
    if (std::optional<DLDataType> dtype = TryDTypeFromTy(ty)) {
      if (dtype->code == kDLUInt) {
        return operand;
      }
      if (std::optional<int64_t> value = TryIntImmValue(operand)) {
        return IntImmLike(ty, std::abs(*value));
      }
      if (std::optional<double> value = TryFloatImmValue(operand)) {
        return FloatImmLike(ty, std::fabs(*value));
      }
    }
  }
  return Expr(ObjectPtr<ExprObj>(make_object<TObj>(std::move(ty), std::move(operand))));
}

template <typename TObj>
Expr MakeUnaryExpr(AnyView operand) {
  return MakeUnaryExpr<TObj>(DefaultExprFromValue(operand));
}

Expr MakeNegExpr(AnyView operand) {
  Expr expr = DefaultExprFromValue(operand);
  if (std::optional<int64_t> int_value = TryIntImmValue(expr)) {
    return IntImmLike(expr->ty, -*int_value);
  }
  if (std::optional<double> float_value = TryFloatImmValue(expr)) {
    return FloatImmLike(expr->ty, -*float_value);
  }
  Expr zero = CoerceInitArgToExpr(AnyView(0), expr->ty);
  return BuildBinaryExpr<SubObj>("Sub", std::move(zero), std::move(expr));
}

Expr MakeCastExpr(const Ty& ty, AnyView value) {
  return CastExprTo(DefaultExprFromValue(value), ty);
}

Expr MakeIfThenElseExpr(AnyView cond, AnyView then_expr, AnyView else_expr) {
  Expr cond_value = CoerceInitArgToExpr(cond, PrimTy(kDefaultBoolLiteralType));
  auto [then_value, else_value] = CoerceBinaryValues(then_expr, else_expr);
  Ty ty = MatchBinaryTypes(&then_value, &else_value);
  if (std::optional<int64_t> cond_literal = TryIntImmValue(cond_value)) {
    return *cond_literal != 0 ? then_value : else_value;
  }
  return IfExpr(std::move(ty), std::move(cond_value), std::move(then_value), std::move(else_value));
}

}  // namespace

Expr cast(const Ty& ty, Expr value) { return CastExprTo(std::move(value), ty); }

#define TVM_FFI_STD_DEFINE_BINARY_FUNC(FuncName, ObjType)                                    \
  Expr FuncName(Expr a, Expr b) {                                                            \
    return MakeBinaryExpr<ObjType##Obj>(std::move(a), std::move(b));                         \
  }                                                                                          \
  Expr FuncName(Expr a, AnyView b) { return MakeBinaryExpr<ObjType##Obj>(std::move(a), b); } \
  Expr FuncName(AnyView a, Expr b) { return MakeBinaryExpr<ObjType##Obj>(a, std::move(b)); }

TVM_FFI_STD_DEFINE_BINARY_FUNC(add, Add)
TVM_FFI_STD_DEFINE_BINARY_FUNC(sub, Sub)
TVM_FFI_STD_DEFINE_BINARY_FUNC(mul, Mul)
TVM_FFI_STD_DEFINE_BINARY_FUNC(cdiv, CDiv)
TVM_FFI_STD_DEFINE_BINARY_FUNC(cmod, CMod)
TVM_FFI_STD_DEFINE_BINARY_FUNC(floordiv, FloorDiv)
TVM_FFI_STD_DEFINE_BINARY_FUNC(floormod, FloorMod)
TVM_FFI_STD_DEFINE_BINARY_FUNC(pow, Pow)
TVM_FFI_STD_DEFINE_BINARY_FUNC(min, Min)
TVM_FFI_STD_DEFINE_BINARY_FUNC(max, Max)
TVM_FFI_STD_DEFINE_BINARY_FUNC(logical_and, And)
TVM_FFI_STD_DEFINE_BINARY_FUNC(logical_or, Or)
TVM_FFI_STD_DEFINE_BINARY_FUNC(left_shift, LShift)
TVM_FFI_STD_DEFINE_BINARY_FUNC(right_shift, RShift)
TVM_FFI_STD_DEFINE_BINARY_FUNC(bitwise_and, BitwiseAnd)
TVM_FFI_STD_DEFINE_BINARY_FUNC(bitwise_or, BitwiseOr)
TVM_FFI_STD_DEFINE_BINARY_FUNC(bitwise_xor, BitwiseXor)

#undef TVM_FFI_STD_DEFINE_BINARY_FUNC

#define TVM_FFI_STD_DEFINE_COMPARISON_FUNC(FuncName, ObjType)                                    \
  Expr FuncName(Expr a, Expr b) {                                                                \
    return MakeComparisonExpr<ObjType##Obj>(std::move(a), std::move(b));                         \
  }                                                                                              \
  Expr FuncName(Expr a, AnyView b) { return MakeComparisonExpr<ObjType##Obj>(std::move(a), b); } \
  Expr FuncName(AnyView a, Expr b) { return MakeComparisonExpr<ObjType##Obj>(a, std::move(b)); }

TVM_FFI_STD_DEFINE_COMPARISON_FUNC(eq, Eq)
TVM_FFI_STD_DEFINE_COMPARISON_FUNC(ne, Ne)
TVM_FFI_STD_DEFINE_COMPARISON_FUNC(le, Le)
TVM_FFI_STD_DEFINE_COMPARISON_FUNC(ge, Ge)
TVM_FFI_STD_DEFINE_COMPARISON_FUNC(gt, Gt)
TVM_FFI_STD_DEFINE_COMPARISON_FUNC(lt, Lt)

#undef TVM_FFI_STD_DEFINE_COMPARISON_FUNC

Expr truncdiv(Expr a, Expr b) { return cdiv(std::move(a), std::move(b)); }
Expr truncdiv(Expr a, AnyView b) { return cdiv(std::move(a), b); }
Expr truncdiv(AnyView a, Expr b) { return cdiv(a, std::move(b)); }

Expr truncmod(Expr a, Expr b) { return cmod(std::move(a), std::move(b)); }
Expr truncmod(Expr a, AnyView b) { return cmod(std::move(a), b); }
Expr truncmod(AnyView a, Expr b) { return cmod(a, std::move(b)); }

Expr equal(Expr a, Expr b) { return eq(std::move(a), std::move(b)); }
Expr equal(Expr a, AnyView b) { return eq(std::move(a), b); }
Expr equal(AnyView a, Expr b) { return eq(a, std::move(b)); }

Expr not_equal(Expr a, Expr b) { return ne(std::move(a), std::move(b)); }
Expr not_equal(Expr a, AnyView b) { return ne(std::move(a), b); }
Expr not_equal(AnyView a, Expr b) { return ne(a, std::move(b)); }

Expr less_equal(Expr a, Expr b) { return le(std::move(a), std::move(b)); }
Expr less_equal(Expr a, AnyView b) { return le(std::move(a), b); }
Expr less_equal(AnyView a, Expr b) { return le(a, std::move(b)); }

Expr greater_equal(Expr a, Expr b) { return ge(std::move(a), std::move(b)); }
Expr greater_equal(Expr a, AnyView b) { return ge(std::move(a), b); }
Expr greater_equal(AnyView a, Expr b) { return ge(a, std::move(b)); }

Expr less(Expr a, Expr b) { return lt(std::move(a), std::move(b)); }
Expr less(Expr a, AnyView b) { return lt(std::move(a), b); }
Expr less(AnyView a, Expr b) { return lt(a, std::move(b)); }

Expr greater(Expr a, Expr b) { return gt(std::move(a), std::move(b)); }
Expr greater(Expr a, AnyView b) { return gt(std::move(a), b); }
Expr greater(AnyView a, Expr b) { return gt(a, std::move(b)); }

Expr neg(Expr operand) {
  if (std::optional<int64_t> int_value = TryIntImmValue(operand)) {
    return IntImmLike(operand->ty, -*int_value);
  }
  if (std::optional<double> float_value = TryFloatImmValue(operand)) {
    return FloatImmLike(operand->ty, -*float_value);
  }
  Expr zero = CoerceInitArgToExpr(AnyView(0), operand->ty);
  return BuildBinaryExpr<SubObj>("Sub", std::move(zero), std::move(operand));
}

Expr logical_not(Expr operand) { return MakeUnaryExpr<NotObj>(std::move(operand)); }
Expr bitwise_not(Expr operand) { return MakeUnaryExpr<BitwiseNotObj>(std::move(operand)); }
Expr bitwise_neg(Expr operand) { return bitwise_not(std::move(operand)); }
Expr abs(Expr operand) { return MakeUnaryExpr<AbsObj>(std::move(operand)); }

Expr if_then_else(Expr cond, Expr then_expr, Expr else_expr) {
  Ty ty = MatchBinaryTypes(&then_expr, &else_expr);
  if (std::optional<int64_t> cond_literal = TryIntImmValue(cond)) {
    return *cond_literal != 0 ? then_expr : else_expr;
  }
  return IfExpr(std::move(ty), std::move(cond), std::move(then_expr), std::move(else_expr));
}

Expr select(Expr cond, Expr then_expr, Expr else_expr) {
  return if_then_else(std::move(cond), std::move(then_expr), std::move(else_expr));
}

namespace {

TVM_FFI_STATIC_INIT_BLOCK() {
#define TVM_FFI_STD_GLOBAL_BINARY(FuncName, ObjType) \
  global_def.def("ffi.std." #FuncName,               \
                 [](AnyView a, AnyView b) { return MakeBinaryExpr<ObjType##Obj>(a, b); })

#define TVM_FFI_STD_GLOBAL_COMPARISON(FuncName, ObjType) \
  global_def.def("ffi.std." #FuncName,                   \
                 [](AnyView a, AnyView b) { return MakeComparisonExpr<ObjType##Obj>(a, b); })

  refl::GlobalDef global_def;
  global_def.def("ffi.std.cast",
                 [](const Ty& ty, AnyView value) { return MakeCastExpr(ty, value); });
  TVM_FFI_STD_GLOBAL_BINARY(add, Add);
  TVM_FFI_STD_GLOBAL_BINARY(sub, Sub);
  TVM_FFI_STD_GLOBAL_BINARY(mul, Mul);
  TVM_FFI_STD_GLOBAL_BINARY(cdiv, CDiv);
  TVM_FFI_STD_GLOBAL_BINARY(cmod, CMod);
  TVM_FFI_STD_GLOBAL_BINARY(truncdiv, CDiv);
  TVM_FFI_STD_GLOBAL_BINARY(truncmod, CMod);
  TVM_FFI_STD_GLOBAL_BINARY(floordiv, FloorDiv);
  TVM_FFI_STD_GLOBAL_BINARY(floormod, FloorMod);
  TVM_FFI_STD_GLOBAL_BINARY(pow, Pow);
  TVM_FFI_STD_GLOBAL_BINARY(min, Min);
  TVM_FFI_STD_GLOBAL_BINARY(max, Max);
  TVM_FFI_STD_GLOBAL_COMPARISON(eq, Eq);
  TVM_FFI_STD_GLOBAL_COMPARISON(ne, Ne);
  TVM_FFI_STD_GLOBAL_COMPARISON(le, Le);
  TVM_FFI_STD_GLOBAL_COMPARISON(ge, Ge);
  TVM_FFI_STD_GLOBAL_COMPARISON(gt, Gt);
  TVM_FFI_STD_GLOBAL_COMPARISON(lt, Lt);
  TVM_FFI_STD_GLOBAL_COMPARISON(equal, Eq);
  TVM_FFI_STD_GLOBAL_COMPARISON(not_equal, Ne);
  TVM_FFI_STD_GLOBAL_COMPARISON(less_equal, Le);
  TVM_FFI_STD_GLOBAL_COMPARISON(greater_equal, Ge);
  TVM_FFI_STD_GLOBAL_COMPARISON(less, Lt);
  TVM_FFI_STD_GLOBAL_COMPARISON(greater, Gt);
  TVM_FFI_STD_GLOBAL_BINARY(logical_and, And);
  TVM_FFI_STD_GLOBAL_BINARY(logical_or, Or);
  TVM_FFI_STD_GLOBAL_BINARY(left_shift, LShift);
  TVM_FFI_STD_GLOBAL_BINARY(right_shift, RShift);
  TVM_FFI_STD_GLOBAL_BINARY(bitwise_and, BitwiseAnd);
  TVM_FFI_STD_GLOBAL_BINARY(bitwise_or, BitwiseOr);
  TVM_FFI_STD_GLOBAL_BINARY(bitwise_xor, BitwiseXor);
  global_def.def("ffi.std.neg", [](AnyView operand) { return MakeNegExpr(operand); });
  global_def.def("ffi.std.logical_not",
                 [](AnyView operand) { return MakeUnaryExpr<NotObj>(operand); });
  global_def.def("ffi.std.bitwise_not",
                 [](AnyView operand) { return MakeUnaryExpr<BitwiseNotObj>(operand); });
  global_def.def("ffi.std.bitwise_neg",
                 [](AnyView operand) { return MakeUnaryExpr<BitwiseNotObj>(operand); });
  global_def.def("ffi.std.abs", [](AnyView operand) { return MakeUnaryExpr<AbsObj>(operand); });
  global_def.def("ffi.std.if_then_else", [](AnyView cond, AnyView then_expr, AnyView else_expr) {
    return MakeIfThenElseExpr(cond, then_expr, else_expr);
  });
  global_def.def("ffi.std.select", [](AnyView cond, AnyView then_expr, AnyView else_expr) {
    return MakeIfThenElseExpr(cond, then_expr, else_expr);
  });

  refl::EnsureTypeAttrColumn(refl::type_attr::kDialectFieldCollector);
  refl::EnsureTypeAttrColumn(refl::type_attr::kDialectLangKind);

#undef TVM_FFI_STD_GLOBAL_COMPARISON
#undef TVM_FFI_STD_GLOBAL_BINARY

#define TVM_FFI_STD_OBJECT_DEF_BASE(ObjType, RefType) \
  refl::ObjectDef<ObjType>().def_type_attr(refl::type_attr::kTextPrint, TextPrintHook<RefType>())

#define TVM_FFI_STD_OBJECT_DEF_BASE_INIT(ObjType, RefType, ...) \
  refl::ObjectDef<ObjType>(__VA_ARGS__)                         \
      .def_type_attr(refl::type_attr::kTextPrint, TextPrintHook<RefType>())

#define TVM_FFI_STD_OBJECT_DEF(ObjType, RefType, Name)                      \
  refl::ObjectDef<ObjType>()                                                \
      .def_type_attr(refl::type_attr::kTextPrint, TextPrintHook<RefType>()) \
      .def_type_attr(refl::type_attr::kDialectMnemonic,                     \
                     Array<String>{String("std"), String(Name)})

#define TVM_FFI_STD_OBJECT_DEF_INIT(ObjType, RefType, Name, ...)            \
  refl::ObjectDef<ObjType>(__VA_ARGS__)                                     \
      .def_type_attr(refl::type_attr::kTextPrint, TextPrintHook<RefType>()) \
      .def_type_attr(refl::type_attr::kDialectMnemonic,                     \
                     Array<String>{String("std"), String(Name)})

#define TVM_FFI_STD_OBJECT_DEF_CUSTOM_INIT(ObjType, RefType, Name, InitFunc) \
  refl::ObjectDef<ObjType>(refl::init(false))                                \
      .def_type_attr(refl::type_attr::kTextPrint, TextPrintHook<RefType>())  \
      .def_type_attr(refl::type_attr::kDialectMnemonic,                      \
                     Array<String>{String("std"), String(Name)})             \
      .def_static(refl::type_attr::kInit, InitFunc)                          \
      .def_type_attr(refl::type_attr::kInit, InitFunc)

  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(NodeObj, Node, refl::init(false))
      .def_type_attr(refl::type_attr::kDialectFieldCollector, CollectLangKindFields);
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(TyObj, Ty, refl::init(false));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(StmtObj, Stmt, refl::init(false));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(AttrsObj, Attrs, refl::init(false)).def_convert<Attrs>();
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(AggregateObj, Aggregate, refl::init(false));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(ExprObj, Expr, refl::init(false))
      .def_convert<Expr>()
      .def_rw("ty", &ExprObj::ty, refl::kw_only(true));
  TVM_FFI_STD_OBJECT_DEF(VarObj, Var, "Var")
      .def_rw("name", &VarObj::name, refl::AttachFieldFlag::SEqHashIgnore());
  TVM_FFI_STD_OBJECT_DEF(BaseFuncObj, BaseFunc, "BaseFunc")
      .def_rw("symbol", &BaseFuncObj::symbol)
      .def_rw("args", &BaseFuncObj::args, refl::AttachFieldFlag::SEqHashDefRecursive())
      .def_rw("ret_type", &BaseFuncObj::ret_type);
  TVM_FFI_STD_OBJECT_DEF(FuncObj, Func, "Func")
      .def_type_attr(refl::type_attr::kDialectFieldCollector, CollectBodyFields<Func>)
      .def(refl::init<String, List<Var>, Optional<Ty>, List<Stmt>, Optional<Attrs>>())
      .def_rw("body", &FuncObj::body)
      .def_rw("attrs", &FuncObj::attrs, refl::default_value(nullptr));
  TVM_FFI_STD_OBJECT_DEF(ModuleObj, Module, "Module").def_rw("funcs", &ModuleObj::funcs);
  TVM_FFI_STD_OBJECT_DEF(RangeObj, Range, "Range")
      .def_convert<Range>()
      .def(refl::init<Optional<Expr>, Expr, Optional<Expr>>())
      .def_rw("start", &RangeObj::start, refl::default_value(nullptr))
      .def_rw("extent", &RangeObj::extent)
      .def_rw("step", &RangeObj::step, refl::kw_only(true), refl::default_value(nullptr));
  TVM_FFI_STD_OBJECT_DEF(AnyTyObj, AnyTy, "Any");
  TVM_FFI_STD_OBJECT_DEF(PrimTyObj, PrimTy, "Prim").def_rw("dtype", &PrimTyObj::dtype);
  TVM_FFI_STD_OBJECT_DEF(TupleTyObj, TupleTy, "Tuple").def_rw("fields", &TupleTyObj::fields);
  TVM_FFI_STD_OBJECT_DEF(TensorTyObj, TensorTy, "Tensor")
      .def_rw("shape", &TensorTyObj::shape)
      .def_rw("dtype", &TensorTyObj::dtype);
  TVM_FFI_STD_OBJECT_DEF(BoolImmObj, BoolImm, "BoolImm").def_rw("value", &BoolImmObj::value);
  TVM_FFI_STD_OBJECT_DEF(IntImmObj, IntImm, "IntImm").def_rw("value", &IntImmObj::value);
  TVM_FFI_STD_OBJECT_DEF(FloatImmObj, FloatImm, "FloatImm").def_rw("value", &FloatImmObj::value);
  TVM_FFI_STD_OBJECT_DEF(StringImmObj, StringImm, "StringImm")
      .def_rw("value", &StringImmObj::value);

#define TVM_FFI_STD_DEF_BINARY(TypeName)                                 \
  TVM_FFI_STD_OBJECT_DEF_CUSTOM_INIT(TypeName##Obj, TypeName, #TypeName, \
                                     &InitBinaryExpr<TypeName##Obj>)     \
      .def_rw("a", &TypeName##Obj::a)                                    \
      .def_rw("b", &TypeName##Obj::b)

#define TVM_FFI_STD_DEF_COMPARISON(TypeName)                             \
  TVM_FFI_STD_OBJECT_DEF_CUSTOM_INIT(TypeName##Obj, TypeName, #TypeName, \
                                     &InitComparisonExpr<TypeName##Obj>) \
      .def_rw("a", &TypeName##Obj::a)                                    \
      .def_rw("b", &TypeName##Obj::b)

  TVM_FFI_STD_DEF_BINARY(Add);
  TVM_FFI_STD_DEF_BINARY(Sub);
  TVM_FFI_STD_DEF_BINARY(Mul);
  TVM_FFI_STD_DEF_BINARY(CDiv);
  TVM_FFI_STD_DEF_BINARY(FloorDiv);
  TVM_FFI_STD_DEF_BINARY(FloorMod);
  TVM_FFI_STD_DEF_BINARY(CMod);
  TVM_FFI_STD_DEF_BINARY(Pow);
  TVM_FFI_STD_DEF_BINARY(LShift);
  TVM_FFI_STD_DEF_BINARY(RShift);
  TVM_FFI_STD_DEF_BINARY(BitwiseAnd);
  TVM_FFI_STD_DEF_BINARY(BitwiseOr);
  TVM_FFI_STD_DEF_BINARY(BitwiseXor);
  TVM_FFI_STD_DEF_BINARY(Min);
  TVM_FFI_STD_DEF_BINARY(Max);
  TVM_FFI_STD_DEF_COMPARISON(Eq);
  TVM_FFI_STD_DEF_COMPARISON(Ne);
  TVM_FFI_STD_DEF_COMPARISON(Le);
  TVM_FFI_STD_DEF_COMPARISON(Ge);
  TVM_FFI_STD_DEF_COMPARISON(Gt);
  TVM_FFI_STD_DEF_COMPARISON(Lt);
  TVM_FFI_STD_DEF_BINARY(And);
  TVM_FFI_STD_DEF_BINARY(Or);

#undef TVM_FFI_STD_DEF_COMPARISON
#undef TVM_FFI_STD_DEF_BINARY

  TVM_FFI_STD_OBJECT_DEF_CUSTOM_INIT(NotObj, Not, "Not", &InitUnaryExpr<NotObj>)
      .def_convert<Not>()
      .def_rw("operand", &NotObj::operand);
  TVM_FFI_STD_OBJECT_DEF_CUSTOM_INIT(BitwiseNotObj, BitwiseNot, "BitwiseNot",
                                     &InitUnaryExpr<BitwiseNotObj>)
      .def_rw("operand", &BitwiseNotObj::operand);
  TVM_FFI_STD_OBJECT_DEF_CUSTOM_INIT(AbsObj, Abs, "Abs", &InitUnaryExpr<AbsObj>)
      .def_rw("operand", &AbsObj::operand);
  TVM_FFI_STD_OBJECT_DEF_CUSTOM_INIT(IfExprObj, IfExpr, "IfExpr", InitIfExpr)
      .def_rw("cond", &IfExprObj::cond)
      .def_rw("then_expr", &IfExprObj::then_expr)
      .def_rw("else_expr", &IfExprObj::else_expr);
  TVM_FFI_STD_OBJECT_DEF_CUSTOM_INIT(LoadObj, Load, "Load", InitLoad)
      .def_rw("lhs", &LoadObj::lhs)
      .def_rw("indices", &LoadObj::indices);
  TVM_FFI_STD_OBJECT_DEF(CastObj, Cast, "Cast").def_rw("value", &CastObj::value);
  TVM_FFI_STD_OBJECT_DEF(CallObj, Call, "Call")
      .def_rw("callee", &CallObj::callee)
      .def_rw("args", &CallObj::args)
      .def_rw("attr", &CallObj::attr, refl::default_value(nullptr));
  TVM_FFI_STD_OBJECT_DEF(IfStmtObj, IfStmt, "IfStmt")
      .def(refl::init<Expr, List<Stmt>, List<Stmt>>())
      .def_rw("cond", &IfStmtObj::cond)
      .def_rw("then_body", &IfStmtObj::then_body)
      .def_rw("else_body", &IfStmtObj::else_body);
  TVM_FFI_STD_OBJECT_DEF(BaseBindExprObj, BaseBindExpr, "BaseBindExpr")
      .def_rw("expr", &BaseBindExprObj::expr);
  TVM_FFI_STD_OBJECT_DEF(BindExprObj, BindExpr, "BindExpr")
      .def_type_attr(refl::type_attr::kDialectFieldCollector,
                     [](const BindExpr& obj) {
                       return FieldCollectionResult(List<Any>{}, DictAttrs(Dict<String, Any>{}),
                                                    obj->vars, List<Node>{});
                     })
      .def(refl::init<List<Var>, Expr>())
      .def_rw("vars", &BindExprObj::vars, refl::AttachFieldFlag::SEqHashDefRecursive());
  TVM_FFI_STD_OBJECT_DEF(BaseVarDefObj, BaseVarDef, "BaseVarDef");
  TVM_FFI_STD_OBJECT_DEF(VarDefObj, VarDef, "VarDef")
      .def_type_attr(refl::type_attr::kDialectFieldCollector,
                     [](const VarDef& obj) {
                       List<Any> args;
                       args.reserve(static_cast<int64_t>(obj->vars.size()));
                       for (const Var& var : obj->vars) {
                         args.push_back(var->ty);
                       }
                       return FieldCollectionResult(std::move(args), DictAttrs(Dict<String, Any>{}),
                                                    obj->vars, List<Node>{});
                     })
      .def_rw("vars", &VarDefObj::vars, refl::AttachFieldFlag::SEqHashDefRecursive());
  TVM_FFI_STD_OBJECT_DEF(BaseScopeObj, BaseScope, "BaseScope");
  TVM_FFI_STD_OBJECT_DEF(ScopeObj, Scope, "Scope")
      .def_type_attr(refl::type_attr::kDialectFieldCollector, CollectBodyFields<Scope>)
      .def(refl::init<List<Stmt>, List<Stmt>, Optional<Attrs>>())
      .def_rw("binds", &ScopeObj::binds, refl::AttachFieldFlag::SEqHashDefRecursive())
      .def_rw("body", &ScopeObj::body)
      .def_rw("attrs", &ScopeObj::attrs, refl::default_value(nullptr));
  TVM_FFI_STD_OBJECT_DEF(BaseForObj, BaseFor, "BaseFor")
      .def_rw("extent", &BaseForObj::extent)
      .def_rw("var", &BaseForObj::var, refl::AttachFieldFlag::SEqHashDefRecursive());
  TVM_FFI_STD_OBJECT_DEF(ForObj, For, "For")
      .def_type_attr(refl::type_attr::kDialectFieldCollector, CollectBodyFields<For>)
      .def(refl::init<Optional<Expr>, Expr, Optional<Expr>, Var, List<Stmt>, Optional<Attrs>>())
      .def_rw("start", &ForObj::start, refl::default_value(nullptr))
      .def_rw("step", &ForObj::step, refl::kw_only(true), refl::default_value(nullptr))
      .def_rw("body", &ForObj::body)
      .def_rw("attrs", &ForObj::attrs, refl::default_value(nullptr));
  TVM_FFI_STD_OBJECT_DEF(BaseWhileObj, BaseWhile, "BaseWhile").def_rw("cond", &BaseWhileObj::cond);
  TVM_FFI_STD_OBJECT_DEF(WhileObj, While, "While")
      .def_type_attr(refl::type_attr::kDialectFieldCollector, CollectBodyFields<While>)
      .def(refl::init<Expr, List<Stmt>, Optional<Attrs>>())
      .def_rw("body", &WhileObj::body)
      .def_rw("attrs", &WhileObj::attrs, refl::default_value(nullptr));
  TVM_FFI_STD_OBJECT_DEF(StoreObj, Store, "Store")
      .def(refl::init<Expr, List<Range>, Expr>())
      .def_rw("lhs", &StoreObj::lhs)
      .def_rw("indices", &StoreObj::indices)
      .def_rw("rhs", &StoreObj::rhs);
  TVM_FFI_STD_OBJECT_DEF(AssertObj, Assert, "Assert")
      .def_type_attr(
          refl::type_attr::kDialectFieldCollector,
          [](const Assert& obj) { return CollectWithBaseArgs(obj, List<Any>{obj->cond}); })
      .def(refl::init<Expr>())
      .def_rw("cond", &AssertObj::cond);
  TVM_FFI_STD_OBJECT_DEF(ReturnObj, Return, "Return")
      .def_type_attr(refl::type_attr::kDialectFieldCollector,
                     [](const Return& obj) {
                       List<Any> args;
                       args.reserve(static_cast<int64_t>(obj->vars.size()));
                       for (const Var& var : obj->vars) {
                         args.push_back(var);
                       }
                       return CollectWithBaseArgs(obj, std::move(args));
                     })
      .def_rw("vars", &ReturnObj::vars);
  TVM_FFI_STD_OBJECT_DEF(YieldObj, Yield_, "Yield")
      .def_type_attr(refl::type_attr::kDialectFieldCollector,
                     [](const Yield_& obj) {
                       List<Any> args;
                       args.reserve(static_cast<int64_t>(obj->vars.size()));
                       for (const Var& var : obj->vars) {
                         args.push_back(var);
                       }
                       return CollectWithBaseArgs(obj, std::move(args));
                     })
      .def_rw("vars", &YieldObj::vars);
  TVM_FFI_STD_OBJECT_DEF(BreakObj, Break, "Break")
      .def_type_attr(refl::type_attr::kDialectFieldCollector,
                     [](const Break& obj) { return CollectWithBaseArgs(obj, List<Any>{}); });
  TVM_FFI_STD_OBJECT_DEF(ContinueObj, Continue, "Continue")
      .def_type_attr(refl::type_attr::kDialectFieldCollector,
                     [](const Continue& obj) { return CollectWithBaseArgs(obj, List<Any>{}); });
  TVM_FFI_STD_OBJECT_DEF(DictAttrsObj, DictAttrs, "DictAttrs")
      .def_rw("values", &DictAttrsObj::values);
  TVM_FFI_STD_OBJECT_DEF(FieldCollectionResultObj, FieldCollectionResult, "FieldCollectionResult")
      .def_rw("args", &FieldCollectionResultObj::args)
      .def_rw("attrs", &FieldCollectionResultObj::attrs)
      .def_rw("outs", &FieldCollectionResultObj::outs, refl::AttachFieldFlag::SEqHashDefRecursive())
      .def_rw("body", &FieldCollectionResultObj::body)
      .def_rw("ty", &FieldCollectionResultObj::ty);

#undef TVM_FFI_STD_OBJECT_DEF
#undef TVM_FFI_STD_OBJECT_DEF_INIT
#undef TVM_FFI_STD_OBJECT_DEF_CUSTOM_INIT
#undef TVM_FFI_STD_OBJECT_DEF_BASE
#undef TVM_FFI_STD_OBJECT_DEF_BASE_INIT
}

}  // namespace
}  // namespace std_
}  // namespace ffi
}  // namespace tvm
