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
#include <tvm/ffi/extra/pyast.h>
#include <tvm/ffi/extra/std.h>
#include <tvm/ffi/reflection/accessor.h>
#include <tvm/ffi/reflection/creator.h>
#include <tvm/ffi/reflection/registry.h>

#include <algorithm>
#include <utility>

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

Array<String> DialectMnemonic(int32_t type_index) {
  static refl::TypeAttrColumn dialect_mnemonic_col(refl::type_attr::kDialectMnemonic);
  AnyView dialect_mnemonic_view = dialect_mnemonic_col[type_index];
  if (dialect_mnemonic_view == nullptr) {
    TVM_FFI_THROW(ValueError) << "No `__ffi_dialect_mnemonic__` registered for: "
                              << String(TVMFFIGetTypeInfo(type_index)->type_key);
  }
  return dialect_mnemonic_view.cast<Array<String>>();
}

text::ExprAST GetPrintedName(const pyast::PrinterConfig& cfg, String dialect, String mnemonic) {
  const auto& dialect_map = cfg->dialect_print_map;
  if (std::optional<String> mapped = dialect_map.Get(dialect + "$" + mnemonic)) {
    return (*mapped == "*") ? text::IdAST(std::move(mnemonic))
                            : text::DottedName(std::move(*mapped));
  }
  if (std::optional<String> mapped = dialect_map.Get(dialect)) {
    return (*mapped == "*") ? text::IdAST(std::move(mnemonic))
                            : text::DottedName(std::move(*mapped))->Attr(std::move(mnemonic));
  }
  if (dialect == "") {
    return text::IdAST(std::move(mnemonic));
  }
  return text::DottedName(std::move(dialect))->Attr(std::move(mnemonic));
}

text::ExprAST CallMnemonic(const text::PrinterConfig& cfg, const ObjectRef& obj) {
  Array<String> dialect_mnemonic = DialectMnemonic(obj->type_index());
  return GetPrintedName(cfg, dialect_mnemonic[0], dialect_mnemonic[1]);
}

String DialectName(const AnyView& obj) { return DialectMnemonic(obj.type_index())[0]; }

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

struct ExprCtx {
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

  void AddOperands(const text::IRPrinter& printer, const List<Expr>& values, const Path& path) {
    int64_t n = static_cast<int64_t>(values.size());
    operands.reserve(static_cast<int64_t>(operands.size()) + n);
    for (int64_t i = 0; i < n; ++i) {
      AddOperand(printer, values[i], path->ArrayItem(i));
    }
  }

  void AddVarDefTypes(const text::IRPrinter& printer, const List<Var>& vars, const Path& path) {
    int64_t n = static_cast<int64_t>(vars.size());
    operands.reserve(static_cast<int64_t>(operands.size()) + n);
    for (int64_t i = 0; i < n; ++i) {
      operands.push_back(printer->ToExpr(vars[i]->ty, path->ArrayItem(i)->Attr("ty")));
    }
  }

  void AddTy(const text::IRPrinter& printer, const Ty& ty, const Path& path) {
    kwargs_keys.push_back("ty");
    kwargs_values.push_back(printer->ToExpr(ty, path));
  }

  void AddAttrs(const text::IRPrinter& printer, const Optional<Attrs>& attrs, const Path& path) {
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

struct ScopeCtx {
  text::ExprAST scope_call;
  List<text::ExprAST> operands;
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  List<text::ExprAST> targets;
  List<text::StmtAST> body;

  ScopeCtx(const char* new_mnemonic, String dialect, const text::PrinterConfig& cfg)
      : scope_call(GetPrintedName(cfg, std::move(dialect), new_mnemonic)) {}

  void AddBodyStmt(const text::IRPrinter& printer, const Stmt& stmt, const Path& path) {
    body.push_back(printer->operator()(stmt, path).cast<text::StmtAST>());
  }

  void AddBodyStmts(const text::IRPrinter& printer, const List<Stmt>& stmts, const Path& path) {
    int64_t n = static_cast<int64_t>(stmts.size());
    for (int64_t i = 0; i < n; ++i) {
      AddBodyStmt(printer, stmts[i], path->ArrayItem(i));
    }
  }

  void AddAttrs(const text::IRPrinter& printer, const Optional<Attrs>& attrs, const Path& path) {
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
    } else {
      return scope_call->CallKw(std::move(operands), std::move(kwargs_keys),
                                std::move(kwargs_values));
    }
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

#define TVM_FFI_TEXT_PRINT_DISALLOW(TypeName)                                                    \
  text::NodeAST TextPrint(const TypeName& obj, const text::IRPrinter&, const Path&) {            \
    TVM_FFI_THROW(ValueError) << "No ffi.std text printer registered for " << obj->GetTypeKey(); \
    TVM_FFI_UNREACHABLE();                                                                       \
  }
TVM_FFI_TEXT_PRINT_DISALLOW(Node)
TVM_FFI_TEXT_PRINT_DISALLOW(Ty)
TVM_FFI_TEXT_PRINT_DISALLOW(Stmt)
TVM_FFI_TEXT_PRINT_DISALLOW(Attrs)
TVM_FFI_TEXT_PRINT_DISALLOW(Aggregate)
TVM_FFI_TEXT_PRINT_DISALLOW(Expr)
#undef TVM_FFI_TEXT_PRINT_DISALLOW

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
  ExprCtx ctx;
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
  Optional<text::ExprAST> stop;
  Optional<text::ExprAST> step;
  if (obj->start.has_value()) {
    start = printer->ToExpr(*obj->start, path->Attr("start"));
  }
  if (obj->stop.has_value()) {
    stop = printer->ToExpr(*obj->stop, path->Attr("stop"));
  }
  if (obj->step.has_value()) {
    step = printer->ToExpr(*obj->step, path->Attr("step"));
  }
  if (start.has_value() && !stop.has_value() && !step.has_value()) {
    return *start;
  }
  return text::SliceAST(std::move(start), std::move(stop), std::move(step));
}

text::NodeAST TextPrint(const Range& obj, const text::IRPrinter& printer, const Path& path) {
  List<text::ExprAST> args;
  auto maybe_append_operand = [&](const Optional<Expr>& operand, const char* name) {
    if (operand.has_value()) {
      args.push_back(printer->ToExpr(*operand, path->Attr(name)));
    } else {
      args.push_back(text::LiteralAST::Null({path->Attr(name)}));
    }
  };
  if (obj->start.has_value()) {
    args.push_back(printer->ToExpr(*obj->start, path->Attr("start")));
    maybe_append_operand(obj->stop, "stop");
    if (obj->step.has_value()) {
      args.push_back(printer->ToExpr(*obj->step, path->Attr("step")));
    }
  } else if (obj->stop.has_value()) {
    if (obj->step.has_value()) {
      args.push_back(text::LiteralAST::Null({path->Attr("start")}));
      args.push_back(printer->ToExpr(*obj->stop, path->Attr("stop")));
      args.push_back(printer->ToExpr(*obj->step, path->Attr("step")));
    } else {
      args.push_back(printer->ToExpr(*obj->stop, path->Attr("stop")));
    }
  } else if (obj->step.has_value()) {
    args.push_back(text::LiteralAST::Null({path->Attr("start")}));
    args.push_back(text::LiteralAST::Null({path->Attr("stop")}));
    args.push_back(printer->ToExpr(*obj->step, path->Attr("step")));
  }
  return CallMnemonic(printer->cfg, obj)->Call(std::move(args));
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
    values.push_back(printer->ToExpr(obj->values[key], values_path->MapItem(key)));
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
  ExprCtx ctx;
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
TVM_FFI_STD_BINARY_OP_TEXT_PRINT(Xor, text::OperationASTObj::kBitXor)
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
  ExprCtx ctx;
  ctx.AddOperand(printer, obj->operand, path->Attr("operand"));
  if (ctx.ExprDerivable()) {
    return text::OperationAST(static_cast<int64_t>(text::OperationASTObj::kNot),
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
  ExprCtx ctx;
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
  ExprCtx ctx;
  Path indices_path = path->Attr("indices");
  for (size_t i = 0; i < obj->indices.size(); ++i) {
    ctx.operands.push_back(TextPrintSlice(obj->indices[i], printer, indices_path->ArrayItem(i)));
  }
  ctx.AddOperand(printer, obj->rhs, path->Attr("rhs"));
  ctx.AddOperand(printer, obj->lhs, path->Attr("lhs"));
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  if (ctx.ExprDerivable()) {
    text::ExprAST lhs = ctx.operands.back();
    ctx.operands.pop_back();
    text::ExprAST rhs = ctx.operands.back();
    ctx.operands.pop_back();
    return text::AssignAST(text::IndexAST(std::move(lhs),  //
                                          {ctx.operands.begin(), ctx.operands.end()}),
                           std::move(rhs));
  } else {
    text::ExprAST lhs = ctx.operands.back();
    ctx.operands.pop_back();
    ctx.operands.insert(ctx.operands.begin(), lhs);
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
  ExprCtx ctx;
  ctx.AddOperand(printer, obj->cond, path->Attr("cond"));
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  if (ctx.ExprDerivable() || (ctx.dialects.empty() && ctx.StmtDerivable(printer, obj))) {
    return text::AssertAST(ctx.operands[0]);
  }
  return ctx.StmtCall(printer, obj);
}

text::NodeAST TextPrint(const Return& obj, const text::IRPrinter& printer, const Path& path) {
  ExprCtx ctx;
  ctx.AddOperands(printer, obj->exprs, path->Attr("exprs"));
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  if (ctx.ExprDerivable() || (ctx.dialects.empty() && ctx.StmtDerivable(printer, obj))) {
    return text::ReturnAST(StmtValue(std::move(ctx.operands)));
  }
  return ctx.StmtCall(printer, obj);
}

text::NodeAST TextPrint(const Yield_& obj, const text::IRPrinter& printer, const Path& path) {
  ExprCtx ctx;
  ctx.AddOperands(printer, obj->exprs, path->Attr("exprs"));
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  if (ctx.ExprDerivable() || (ctx.dialects.empty() && ctx.StmtDerivable(printer, obj))) {
    return text::ExprStmtAST(text::YieldAST(StmtValue(std::move(ctx.operands))));
  }
  return ctx.StmtCall(printer, obj);
}

text::NodeAST TextPrint(const Break& obj, const text::IRPrinter& printer, const Path& path) {
  ExprCtx ctx;
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  return ctx.StmtDerivable(printer, obj) ? text::BreakAST() : ctx.StmtCall(printer, obj);
}

text::NodeAST TextPrint(const Continue& obj, const text::IRPrinter& printer, const Path& path) {
  ExprCtx ctx;
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  return ctx.StmtDerivable(printer, obj) ? text::ContinueAST() : ctx.StmtCall(printer, obj);
}

/***************************************************************/
/*************** Section 6: Call Expressions *******************/
/***************************************************************/

text::NodeAST TextPrint(const Call& obj, const text::IRPrinter& printer, const Path& path) {
  ExprCtx ctx;
  text::ExprAST callee;
  if (std::optional<String> symbol = obj->callee.as<String>()) {
    callee = text::IdAST(*symbol);
  } else if (std::optional<Func> func = obj->callee.as<Func>()) {
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

text::NodeAST TextPrint(const BindExpr& obj, const text::IRPrinter& printer, const Path& path) {
  // Binding expressions keep literal type annotations on the RHS, unlike
  // arithmetic/operator sugar where typed immediates collapse to Python
  // literals.
  ExprCtx ctx;
  ctx.AddOperand(printer, obj->expr, path->Attr("expr"));
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  text::ExprAST rhs = ctx.kwargs_keys.empty()
                          ? ctx.operands[0]
                          : CallMnemonic(printer->cfg, obj)
                                ->CallKw(std::move(ctx.operands), std::move(ctx.kwargs_keys),
                                         std::move(ctx.kwargs_values));
  if (obj->vars.empty()) {
    return text::ExprStmtAST(std::move(rhs));
  }
  return text::AssignAST(DefineVarTuple(printer, obj->vars), std::move(rhs));
}

text::NodeAST TextPrint(const VarDef& obj, const text::IRPrinter& printer, const Path& path) {
  ExprCtx ctx;
  ctx.AddVarDefTypes(printer, obj->vars, path->Attr("vars"));
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  if (obj->vars.empty()) {
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
  return text::AssignAST(DefineVarTuple(printer, obj->vars), std::move(rhs));
}

/*****************************************************************/
/*************** Section 8. Body-Bearing Stmts *******************/
/*****************************************************************/

text::NodeAST TextPrint(const Module& obj, const text::IRPrinter& printer, const Path& path) {
  ScopeCtx ctx("module", DialectName(obj), printer->cfg);
  ctx.AddBodyStmts(printer, obj->funcs, path->Attr("funcs"));
  return text::ClassAST(text::IdAST("MyModule"), {}, {ctx.scope_call}, std::move(ctx.body));
}

text::NodeAST TextPrint(const IfStmt& obj, const text::IRPrinter& printer, const Path& path) {
  return text::IfAST(printer->ToExpr(obj->cond, path->Attr("cond")),
                     PrintList<text::StmtAST>(printer, obj->then_body, path->Attr("then_body")),
                     PrintList<text::StmtAST>(printer, obj->else_body, path->Attr("else_body")));
}

text::NodeAST TextPrint(const While& obj, const text::IRPrinter& printer, const Path& path) {
  ScopeCtx ctx("while_", DialectName(obj), printer->cfg);
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  ctx.AddBodyStmts(printer, obj->body, path->Attr("body"));
  text::ExprAST cond = printer->ToExpr(obj->cond, path->Attr("cond"));
  if (ctx.kwargs_keys.empty()) {
    return text::WhileAST(std::move(cond), std::move(ctx.body));
  } else {
    ctx.operands.push_back(cond);
    return text::WithAST({}, ctx.StmtCall(false), std::move(ctx.body));
  }
}

text::NodeAST TextPrint(const For& obj, const text::IRPrinter& printer, const Path& path) {
  ScopeCtx ctx("range", "", printer->cfg);
  ctx.AddTargets(printer, obj->vars);
  // ----------- "range" section ----------- //
  auto maybe_append_operand = [&](const Optional<Expr>& operand, const char* name) {
    if (operand.has_value()) {
      ctx.operands.push_back(printer->ToExpr(*operand, path->Attr(name)));
    } else {
      ctx.operands.push_back(text::LiteralAST::Null({path->Attr(name)}));
    }
  };
  if (obj->start.has_value()) {
    ctx.operands.push_back(printer->ToExpr(*obj->start, path->Attr("start")));
    maybe_append_operand(obj->stop, "stop");
    if (obj->step.has_value()) {
      ctx.operands.push_back(printer->ToExpr(*obj->step, path->Attr("step")));
    }
  } else if (obj->stop.has_value()) {
    if (obj->step.has_value()) {
      ctx.operands.push_back(text::LiteralAST::Null({path->Attr("start")}));
      ctx.operands.push_back(printer->ToExpr(*obj->stop, path->Attr("stop")));
      ctx.operands.push_back(printer->ToExpr(*obj->step, path->Attr("step")));
    } else {
      ctx.operands.push_back(printer->ToExpr(*obj->stop, path->Attr("stop")));
    }
  } else if (obj->step.has_value()) {
    ctx.operands.push_back(text::LiteralAST::Null({path->Attr("start")}));
    ctx.operands.push_back(text::LiteralAST::Null({path->Attr("stop")}));
    ctx.operands.push_back(printer->ToExpr(*obj->step, path->Attr("step")));
  }
  // --------------------------------------- //
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  ctx.AddBodyStmts(printer, obj->body, path->Attr("body"));
  text::ExprAST lhs = *ctx.Target(/*create_placeholder_for_none=*/true);
  text::ExprAST rhs = ctx.StmtCall(false);
  return text::ForAST(std::move(lhs), std::move(rhs), std::move(ctx.body));
}

text::NodeAST TextPrint(const Func& obj, const text::IRPrinter& printer, const Path& path) {
  ScopeCtx ctx("func", DialectName(obj), printer->cfg);
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
  ctx.AddBodyStmts(printer, obj->body, path->Attr("body"));
  Optional<text::ExprAST> ret_type;
  if (obj->ret_type.has_value()) {
    ret_type = printer->ToExpr(*obj->ret_type, path->Attr("ret_type"));
  }
  return text::FunctionAST(text::IdAST(obj->symbol), std::move(args), {ctx.StmtCall(true)},
                           std::move(ret_type), std::move(ctx.body));
}

text::NodeAST TextPrint(const Scope& obj, const text::IRPrinter& printer, const Path& path) {
  ScopeCtx ctx("scope", DialectName(obj), printer->cfg);
  ctx.AddAttrs(printer, obj->attrs, path->Attr("attrs"));
  int64_t n = static_cast<int64_t>(obj->binds.size());
  ctx.operands.reserve(n);
  Path binds_path = path->Attr("binds");
  for (int64_t i = 0; i < n; ++i) {
    const Stmt& bind = obj->binds[i];
    Path bind_path = binds_path->ArrayItem(i);
    ExprCtx bind_ctx;
    const List<Var>* vars = nullptr;
    if (const BindExprObj* bind_expr = bind.as<BindExprObj>()) {
      bind_ctx.AddOperand(printer, bind_expr->expr, bind_path->Attr("expr"));
      vars = &bind_expr->vars;
    } else if (const VarDefObj* var_def = bind.as<VarDefObj>()) {
      bind_ctx.AddVarDefTypes(printer, var_def->vars, bind_path->Attr("vars"));
      vars = &var_def->vars;
    } else {
      TVM_FFI_THROW(ValueError) << "ffi.std.Scope expected BindExpr or VarDef";
    }
    bind_ctx.AddAttrs(printer, bind->attrs, bind_path->Attr("attrs"));
    ctx.operands.push_back(bind_ctx.kwargs_keys.empty()
                               ? CallMnemonic(printer->cfg, bind)->Call(bind_ctx.operands)
                               : CallMnemonic(printer->cfg, bind)
                                     ->CallKw(bind_ctx.operands,     //
                                              bind_ctx.kwargs_keys,  //
                                              bind_ctx.kwargs_values));
    ctx.AddTargets(printer, *vars);
  }
  ctx.AddBodyStmts(printer, obj->body, path->Attr("body"));
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

TVM_FFI_STATIC_INIT_BLOCK() {
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

  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(NodeObj, Node, refl::init(false));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(TyObj, Ty, refl::init(false));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(StmtObj, Stmt, refl::init(false))
      .def_rw("attrs", &StmtObj::attrs, refl::kw_only(true), refl::default_value(nullptr));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(AttrsObj, Attrs, refl::init(false)).def_convert<Attrs>();
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(AggregateObj, Aggregate, refl::init(false));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(ExprObj, Expr, refl::init(false))
      .def_convert<Expr>()
      .def_rw("ty", &ExprObj::ty, refl::kw_only(true));
  TVM_FFI_STD_OBJECT_DEF(VarObj, Var, "Var")
      .def_rw("name", &VarObj::name, refl::AttachFieldFlag::SEqHashIgnore());
  TVM_FFI_STD_OBJECT_DEF(FuncObj, Func, "Func")
      .def_rw("symbol", &FuncObj::symbol)
      .def_rw("args", &FuncObj::args, refl::AttachFieldFlag::SEqHashDefRecursive())
      .def_rw("ret_type", &FuncObj::ret_type)
      .def_rw("body", &FuncObj::body);
  TVM_FFI_STD_OBJECT_DEF(ModuleObj, Module, "Module").def_rw("funcs", &ModuleObj::funcs);
  TVM_FFI_STD_OBJECT_DEF(RangeObj, Range, "Range")
      .def_convert<Range>()
      .def_rw("start", &RangeObj::start, refl::default_value(nullptr))
      .def_rw("stop", &RangeObj::stop, refl::default_value(nullptr))
      .def_rw("step", &RangeObj::step, refl::default_value(nullptr));
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

#define TVM_FFI_STD_DEF_BINARY(TypeName)                     \
  TVM_FFI_STD_OBJECT_DEF(TypeName##Obj, TypeName, #TypeName) \
      .def(refl::init<AnyView, AnyView, Ty>())               \
      .def_rw("a", &TypeName##Obj::a)                        \
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
  TVM_FFI_STD_DEF_BINARY(Xor);
  TVM_FFI_STD_DEF_BINARY(Min);
  TVM_FFI_STD_DEF_BINARY(Max);
  TVM_FFI_STD_DEF_BINARY(Eq);
  TVM_FFI_STD_DEF_BINARY(Ne);
  TVM_FFI_STD_DEF_BINARY(Le);
  TVM_FFI_STD_DEF_BINARY(Ge);
  TVM_FFI_STD_DEF_BINARY(Gt);
  TVM_FFI_STD_DEF_BINARY(Lt);
  TVM_FFI_STD_DEF_BINARY(And);
  TVM_FFI_STD_DEF_BINARY(Or);

#undef TVM_FFI_STD_DEF_BINARY

  TVM_FFI_STD_OBJECT_DEF(NotObj, Not, "Not")
      .def_convert<Not>()
      .def(refl::init<AnyView, Ty>())
      .def_rw("operand", &NotObj::operand);
  TVM_FFI_STD_OBJECT_DEF(LoadObj, Load, "Load")
      .def_rw("lhs", &LoadObj::lhs)
      .def_rw("indices", &LoadObj::indices);
  TVM_FFI_STD_OBJECT_DEF(CastObj, Cast, "Cast").def_rw("value", &CastObj::value);
  TVM_FFI_STD_OBJECT_DEF(CallObj, Call, "Call")
      .def_rw("callee", &CallObj::callee)
      .def_rw("args", &CallObj::args)
      .def_rw("attr", &CallObj::attr, refl::default_value(nullptr));
  TVM_FFI_STD_OBJECT_DEF(IfStmtObj, IfStmt, "IfStmt")
      .def_rw("cond", &IfStmtObj::cond)
      .def_rw("then_body", &IfStmtObj::then_body)
      .def_rw("else_body", &IfStmtObj::else_body);
  TVM_FFI_STD_OBJECT_DEF(BindExprObj, BindExpr, "BindExpr")
      .def_rw("vars", &BindExprObj::vars, refl::AttachFieldFlag::SEqHashDefRecursive())
      .def_rw("expr", &BindExprObj::expr);
  TVM_FFI_STD_OBJECT_DEF(VarDefObj, VarDef, "VarDef")
      .def_rw("vars", &VarDefObj::vars, refl::AttachFieldFlag::SEqHashDefRecursive());
  TVM_FFI_STD_OBJECT_DEF(ScopeObj, Scope, "Scope")
      .def_rw("binds", &ScopeObj::binds, refl::AttachFieldFlag::SEqHashDefRecursive())
      .def_rw("body", &ScopeObj::body);
  TVM_FFI_STD_OBJECT_DEF(ForObj, For, "For")
      .def_rw("start", &ForObj::start, refl::default_value(nullptr))
      .def_rw("stop", &ForObj::stop, refl::default_value(nullptr))
      .def_rw("step", &ForObj::step, refl::default_value(nullptr))
      .def_rw("vars", &ForObj::vars, refl::AttachFieldFlag::SEqHashDefRecursive())
      .def_rw("body", &ForObj::body);
  TVM_FFI_STD_OBJECT_DEF(WhileObj, While, "While")
      .def_rw("cond", &WhileObj::cond)
      .def_rw("body", &WhileObj::body);
  TVM_FFI_STD_OBJECT_DEF(StoreObj, Store, "Store")
      .def_rw("lhs", &StoreObj::lhs)
      .def_rw("indices", &StoreObj::indices)
      .def_rw("rhs", &StoreObj::rhs);
  TVM_FFI_STD_OBJECT_DEF(AssertObj, Assert, "Assert").def_rw("cond", &AssertObj::cond);
  TVM_FFI_STD_OBJECT_DEF(ReturnObj, Return, "Return").def_rw("exprs", &ReturnObj::exprs);
  TVM_FFI_STD_OBJECT_DEF(YieldObj, Yield_, "Yield").def_rw("exprs", &YieldObj::exprs);
  TVM_FFI_STD_OBJECT_DEF(BreakObj, Break, "Break");
  TVM_FFI_STD_OBJECT_DEF(ContinueObj, Continue, "Continue");
  TVM_FFI_STD_OBJECT_DEF(DictAttrsObj, DictAttrs, "DictAttrs")
      .def_rw("values", &DictAttrsObj::values);

#undef TVM_FFI_STD_OBJECT_DEF
#undef TVM_FFI_STD_OBJECT_DEF_BASE
#undef TVM_FFI_STD_OBJECT_DEF_BASE_INIT
}

}  // namespace
}  // namespace std_
}  // namespace ffi
}  // namespace tvm
