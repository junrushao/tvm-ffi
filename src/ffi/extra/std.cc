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
#include <functional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace tvm {
namespace ffi {
namespace std_ {

namespace {

// The text AST APIs use int64_t sizes, while container sizes are size_t.
// Casts in this file are local size conversions for printer construction.
// NOLINTBEGIN(bugprone-misplaced-widening-cast,bugprone-narrowing-conversions)

namespace refl = ::tvm::ffi::reflection;
namespace text = ::tvm::ffi::pyast;

#define TVM_FFI_STD_TEXT_PRINT_DECL(TypeName)                                  \
  text::NodeAST TextPrint(const TypeName& obj, const text::IRPrinter& printer, \
                          const refl::AccessPath& path);

TVM_FFI_STD_TEXT_PRINT_DECL(Node)
TVM_FFI_STD_TEXT_PRINT_DECL(Ty)
TVM_FFI_STD_TEXT_PRINT_DECL(Stmt)
TVM_FFI_STD_TEXT_PRINT_DECL(Attrs)
TVM_FFI_STD_TEXT_PRINT_DECL(Aggregate)
TVM_FFI_STD_TEXT_PRINT_DECL(Expr)
TVM_FFI_STD_TEXT_PRINT_DECL(Var)
TVM_FFI_STD_TEXT_PRINT_DECL(Func)
TVM_FFI_STD_TEXT_PRINT_DECL(Module)
TVM_FFI_STD_TEXT_PRINT_DECL(Range)
TVM_FFI_STD_TEXT_PRINT_DECL(AnyTy)
TVM_FFI_STD_TEXT_PRINT_DECL(PrimTy)
TVM_FFI_STD_TEXT_PRINT_DECL(TupleType)
TVM_FFI_STD_TEXT_PRINT_DECL(TensorTy)
TVM_FFI_STD_TEXT_PRINT_DECL(IntImm)
TVM_FFI_STD_TEXT_PRINT_DECL(FloatImm)
TVM_FFI_STD_TEXT_PRINT_DECL(StringImm)
TVM_FFI_STD_TEXT_PRINT_DECL(Add)
TVM_FFI_STD_TEXT_PRINT_DECL(Sub)
TVM_FFI_STD_TEXT_PRINT_DECL(Mul)
TVM_FFI_STD_TEXT_PRINT_DECL(FloorDiv)
TVM_FFI_STD_TEXT_PRINT_DECL(FloorMod)
TVM_FFI_STD_TEXT_PRINT_DECL(Min)
TVM_FFI_STD_TEXT_PRINT_DECL(Max)
TVM_FFI_STD_TEXT_PRINT_DECL(Eq)
TVM_FFI_STD_TEXT_PRINT_DECL(Ne)
TVM_FFI_STD_TEXT_PRINT_DECL(Le)
TVM_FFI_STD_TEXT_PRINT_DECL(Ge)
TVM_FFI_STD_TEXT_PRINT_DECL(Gt)
TVM_FFI_STD_TEXT_PRINT_DECL(Lt)
TVM_FFI_STD_TEXT_PRINT_DECL(And)
TVM_FFI_STD_TEXT_PRINT_DECL(Or)
TVM_FFI_STD_TEXT_PRINT_DECL(Not)
TVM_FFI_STD_TEXT_PRINT_DECL(Load)
TVM_FFI_STD_TEXT_PRINT_DECL(Cast)
TVM_FFI_STD_TEXT_PRINT_DECL(Call)
TVM_FFI_STD_TEXT_PRINT_DECL(IfStmt)
TVM_FFI_STD_TEXT_PRINT_DECL(Scope)
TVM_FFI_STD_TEXT_PRINT_DECL(For)
TVM_FFI_STD_TEXT_PRINT_DECL(While)
TVM_FFI_STD_TEXT_PRINT_DECL(Bind)
TVM_FFI_STD_TEXT_PRINT_DECL(BindExpr)
TVM_FFI_STD_TEXT_PRINT_DECL(BindVarDef)
TVM_FFI_STD_TEXT_PRINT_DECL(Store)
TVM_FFI_STD_TEXT_PRINT_DECL(Assert)
TVM_FFI_STD_TEXT_PRINT_DECL(Return)
TVM_FFI_STD_TEXT_PRINT_DECL(Yield_)
TVM_FFI_STD_TEXT_PRINT_DECL(Break)
TVM_FFI_STD_TEXT_PRINT_DECL(Continue)
TVM_FFI_STD_TEXT_PRINT_DECL(DictAttrs)

#undef TVM_FFI_STD_TEXT_PRINT_DECL

template <typename T>
auto TextPrintHook() {
  return
      [](const T& obj, const text::IRPrinter& printer,
         const refl::AccessPath& path) -> text::NodeAST { return TextPrint(obj, printer, path); };
}

Array<String> DialectMnemonic(int32_t type_index) {
  static refl::TypeAttrColumn dialect_mnemonic_col(refl::type_attr::kDialectMnemonic);
  AnyView dialect_mnemonic_view = dialect_mnemonic_col[type_index];
  if (dialect_mnemonic_view == nullptr) {
    TVM_FFI_THROW(ValueError) << "No __ffi_dialect_mnemonic__ registered for: "
                              << String(TVMFFIGetTypeInfo(type_index)->type_key);
  }
  Array<String> dialect_mnemonic = dialect_mnemonic_view.cast<Array<String>>();
  if (dialect_mnemonic.size() != 2 && dialect_mnemonic.size() != 3) {
    TVM_FFI_THROW(ValueError) << "Invalid __ffi_dialect_mnemonic__ for "
                              << String(TVMFFIGetTypeInfo(type_index)->type_key)
                              << ", expected `{dialect, mnemonic}` or "
                                 "`{dialect, mnemonic, generics}`";
  }
  return dialect_mnemonic;
}

String Dialect(int32_t type_index) { return DialectMnemonic(type_index)[0]; }

class DialectFrame {
 public:
  DialectFrame(const text::IRPrinter& printer, const Node& obj) : printer_(printer.get()) {
    printer_->dialects.push_back(Dialect(obj.type_index()));
  }

  ~DialectFrame() { printer_->dialects.pop_back(); }  // NOLINT(modernize-use-equals-default)

 private:
  text::IRPrinterObj* printer_;
};

class CachedPrinter {
 public:
  explicit CachedPrinter(text::IRPrinter printer) : printer_(std::move(printer)) {}

  Any ApplyDialect(const ObjectRef& obj, const refl::AccessPath& path) {
    Any ast = printer_->operator()(obj, path);
    text::NodeAST ast_node = ast.cast<text::NodeAST>();
    if (!ast_node->IsInstance<text::LiteralASTObj>()) {
      this->dialects_.insert(Dialect(obj.type_index()));
    }
    this->cache_[obj] = std::move(ast);
    return this->cache_.at(obj);
  }

  Optional<String> CommonDialect() const {
    if (this->dialects_.empty()) {
      return this->printer_->dialects.back();
    }
    if (this->dialects_.size() == 1) {
      return *this->dialects_.begin();
    }
    return {};
  }

  text::ExprAST GetCachedExpr(const ObjectRef& obj) const {
    return cache_.at(obj).cast<text::ExprAST>();
  }
  const text::IRPrinter& printer() const { return printer_; }

 private:
  text::IRPrinter printer_;
  std::unordered_map<ObjectRef, Any, ObjectPtrHash, ObjectPtrEqual> cache_;
  std::unordered_set<String> dialects_;
};

using FnApplyGenerics =
    std::function<text::NodeAST(const Node&, const CachedPrinter&, const refl::AccessPath&)>;

class GenericsRegistry {
 public:
  static GenericsRegistry* Global() {
    static GenericsRegistry registry;
    return &registry;
  }

  void Register(const String& dialect, const String& generic, FnApplyGenerics fn) {
    generics_map_[dialect + "$" + generic] = std::move(fn);
  }

  FnApplyGenerics Lookup(const String& dialect, const String& generic) const {
    auto it = generics_map_.find(dialect + "$" + generic);
    return it == generics_map_.end() ? nullptr : (*it).second;
  }

 private:
  std::unordered_map<String, FnApplyGenerics> generics_map_;
};

List<text::ExprAST> PrintExprList(const text::IRPrinter& printer, const List<Expr>& values,
                                  const refl::AccessPath& path) {
  List<text::ExprAST> result;
  int64_t n = static_cast<int64_t>(values.size());
  result.reserve(n);
  for (int64_t i = 0; i < n; ++i) {
    result.push_back(printer->operator()(values[i], path->ArrayItem(i)).cast<text::ExprAST>());
  }
  return result;
}

List<text::StmtAST> PrintStmtList(const text::IRPrinter& printer, const List<Stmt>& values,
                                  const refl::AccessPath& path) {
  List<text::StmtAST> result;
  int64_t n = static_cast<int64_t>(values.size());
  result.reserve(n);
  for (int64_t i = 0; i < n; ++i) {
    result.push_back(printer->operator()(values[i], path->ArrayItem(i)).cast<text::StmtAST>());
  }
  return result;
}

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

Optional<text::ExprAST> DefineScopeVarsAsWithTargets(const text::IRPrinter& printer,
                                                     const List<Bind>& binds) {
  // A with-statement target is optional.  No bindings print as
  // "with std.Scope(...):", one binding prints as "with std.Scope(...) as x:",
  // and multiple bindings print as tuple target syntax:
  // "with std.Scope(...) as (x, state):".
  List<text::ExprAST> targets;
  for (const Bind& bind : binds) {
    for (const Var& var : bind->vars) {
      targets.push_back(DefineVar(printer, var));
    }
  }
  if (targets.empty()) return {};
  if (targets.size() == 1) return targets[0];
  return text::TupleAST(std::move(targets));
}

bool AppendAttrsAsKwargs(const text::IRPrinter& printer, const Optional<Attrs>& attrs,
                         const refl::AccessPath& attrs_path, List<String>* kwargs_keys,
                         List<text::ExprAST>* kwargs_values) {
  // Attrs subclasses must print as CallAST with keyword-only arguments:
  // DictAttrs({"tag": "demo"}) -> std.DictAttrs(tag="demo").
  // This helper strips the callee and appends only "tag=..." so enclosing
  // syntax can print as std.Call(callee, tag="demo") or range(..., tag="demo").
  if (!attrs.has_value()) return false;
  text::ExprAST attrs_ast = printer->operator()(*attrs, attrs_path).cast<text::ExprAST>();
  const text::CallASTObj* call = attrs_ast.as<text::CallASTObj>();
  if (call == nullptr) {
    TVM_FFI_THROW(ValueError) << "ffi.std.Attrs text printer must return CallAST";
  }
  if (!call->args.empty()) {
    TVM_FFI_THROW(ValueError) << "ffi.std.Attrs text printer must use keyword arguments only";
  }
  kwargs_keys->reserve(static_cast<int64_t>(kwargs_keys->size() + call->kwargs_keys.size()));
  kwargs_values->reserve(static_cast<int64_t>(kwargs_values->size() + call->kwargs_values.size()));
  int64_t n = static_cast<int64_t>(call->kwargs_keys.size());
  for (int64_t i = 0; i < n; ++i) {
    kwargs_keys->push_back(call->kwargs_keys[i]);
    kwargs_values->push_back(call->kwargs_values[i]);
  }
  return n != 0;
}

text::ExprAST BindInitializerCall(const Bind& bind, const text::IRPrinter& printer,
                                  const refl::AccessPath& path) {
  // Build the initializer expression that appears inside a scope-like context
  // manager call.  Scope and While carry their variables as Bind nodes:
  //
  //   Scope(vars=[BindVarDef(vars=[x: i32])], body=...)
  //
  // prints as:
  //
  //   with std.Scope(std.BindVarDef(std.i32)) as x:
  //
  // This helper builds only the `std.BindVarDef(std.i32)` part.  The `as x`
  // target is produced separately by DefineScopeVarsAsWithTargets after the
  // same Var has been registered with the IRPrinter.
  //
  // BindExpr uses the bound expression as its initializer:
  //
  //   BindExpr(vars=[x], expr=y + 1, attrs={"tag": "demo"})
  //     -> std.BindExpr(y + 1, tag="demo")
  //
  // BindVarDef has no value expression, so it uses each variable's type as its
  // initializer argument:
  //
  //   BindVarDef(vars=[x: i32, y: f32]) -> std.BindVarDef(std.i32, std.f32)
  List<text::ExprAST> args;
  if (const BindExprObj* bind_expr = bind.as<BindExprObj>()) {
    args.push_back(printer->operator()(bind_expr->expr, path->Attr("expr")).cast<text::ExprAST>());
  } else if (const BindVarDefObj* bind_var_def = bind.as<BindVarDefObj>()) {
    int64_t n = static_cast<int64_t>(bind_var_def->vars.size());
    args.reserve(n);
    refl::AccessPath vars_path = path->Attr("vars");
    for (int64_t i = 0; i < n; ++i) {
      args.push_back(
          printer->operator()(bind_var_def->vars[i]->ty, vars_path->ArrayItem(i)->Attr("ty"))
              .cast<text::ExprAST>());
    }
  } else {
    TVM_FFI_THROW(ValueError) << "ffi.std.Scope expected BindExpr or BindVarDef";
  }
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  return AppendAttrsAsKwargs(printer, bind->attrs, path->Attr("attrs"), &kwargs_keys,
                             &kwargs_values)
             ? text::ExprCallKw(printer->CallMnemonic(bind), std::move(args),
                                std::move(kwargs_keys), std::move(kwargs_values))
             : text::ExprCall(printer->CallMnemonic(bind), std::move(args));
}

Optional<text::ExprAST> PackOptionalValue(List<text::ExprAST> values) {
  // Used by return/yield.  "return" has no expression, "return x" has one,
  // and "return x, y" is represented as a tuple expression.
  if (values.empty()) return {};
  if (values.size() == 1) return values[0];
  return text::TupleAST(std::move(values));
}

text::ExprAST IndexFromPrintedOperands(const List<text::ExprAST>& printed_operands,
                                       int64_t end_index_offset) {
  // Convert flattened load/store operands into index syntax.  For a load,
  // [x, i, j] becomes x[i, j].  For a store, [x, i, rhs] ignores the trailing
  // rhs by using end_index_offset=1.  Empty indices intentionally print as
  // x[()] or x[()] = rhs so scalar loads/stores remain explicit.
  text::ExprAST base = printed_operands[0];
  int64_t end_index = static_cast<int64_t>(printed_operands.size()) - end_index_offset;
  List<text::ExprAST> indices;
  indices.reserve(end_index - 1);
  for (int64_t i = 1; i < end_index; ++i) {
    indices.push_back(printed_operands[i]);
  }
  return text::IndexAST(std::move(base), std::move(indices));
}

template <typename ObjType>
List<text::ExprAST> BinaryOperands(const Node& obj, const CachedPrinter& cache) {
  const ObjType* op = obj.as<ObjType>();
  return {cache.GetCachedExpr(op->a), cache.GetCachedExpr(op->b)};
}

List<text::ExprAST> IndexOperands(const LoadObj* load, const CachedPrinter& cache) {
  List<text::ExprAST> args{cache.GetCachedExpr(load->var)};
  args.reserve(static_cast<int64_t>(load->indices.size() + 1));
  for (const Range& index : load->indices) {
    args.push_back(cache.GetCachedExpr(index));
  }
  return args;
}

List<text::ExprAST> StoreOperands(const StoreObj* store, const CachedPrinter& cache) {
  List<text::ExprAST> args{cache.GetCachedExpr(store->var)};
  args.reserve(static_cast<int64_t>(store->indices.size() + 2));
  for (const Range& index : store->indices) {
    args.push_back(cache.GetCachedExpr(index));
  }
  args.push_back(cache.GetCachedExpr(store->rhs));
  return args;
}

List<text::ExprAST> VarOperands(const List<Var>& vars, const CachedPrinter& cache) {
  List<text::ExprAST> args;
  args.reserve(static_cast<int64_t>(vars.size()));
  for (const Var& var : vars) {
    args.push_back(cache.GetCachedExpr(var));
  }
  return args;
}

template <typename ObjType, int64_t Op>
text::NodeAST ApplyOperationGeneric(const Node& obj, const CachedPrinter& cache,
                                    const refl::AccessPath&) {
  return text::OperationAST(Op, BinaryOperands<ObjType>(obj, cache));
}

template <typename ObjType>
text::NodeAST ApplyMinGeneric(const Node& obj, const CachedPrinter& cache,
                              const refl::AccessPath&) {
  return text::ExprCall(text::IdAST("min"), BinaryOperands<ObjType>(obj, cache));
}

template <typename ObjType>
text::NodeAST ApplyMaxGeneric(const Node& obj, const CachedPrinter& cache,
                              const refl::AccessPath&) {
  return text::ExprCall(text::IdAST("max"), BinaryOperands<ObjType>(obj, cache));
}

text::NodeAST ApplyNotGeneric(const Node& obj, const CachedPrinter& cache,
                              const refl::AccessPath&) {
  const NotObj* not_op = obj.as<NotObj>();
  return text::OperationAST(text::OperationASTObj::kNot, {cache.GetCachedExpr(not_op->operand)});
}

text::NodeAST ApplyLoadGeneric(const Node& obj, const CachedPrinter& cache,
                               const refl::AccessPath&) {
  return IndexFromPrintedOperands(IndexOperands(obj.as<LoadObj>(), cache), /*end_index_offset=*/0);
}

text::NodeAST ApplyCastGeneric(const Node& obj, const CachedPrinter& cache,
                               const refl::AccessPath&) {
  // PrimTy casts prefer dtype-call syntax, e.g. std.Cast(std.i32, x) prints as
  // std.i32(x).  Non-primitive casts stay explicit as std.Cast(ty, x).
  const CastObj* cast = obj.as<CastObj>();
  text::ExprAST ty = cache.GetCachedExpr(cast->ty);
  text::ExprAST value = cache.GetCachedExpr(cast->value);
  if (cast->ty.as<PrimTyObj>() != nullptr) {
    return text::ExprCall(std::move(ty), {std::move(value)});
  }
  return text::ExprCall(cache.printer()->CallMnemonic(obj), {std::move(ty), std::move(value)});
}

text::NodeAST ApplyBindExprGeneric(const Node& obj, const CachedPrinter& cache,
                                   const refl::AccessPath& path) {
  // BindExpr sugar is assignment-like.  With vars it prints "x = rhs" or
  // "x, y = rhs"; without vars it degrades to expression-statement "rhs".
  // Attrs wrap the RHS as std.BindExpr(rhs, key=value) before assignment.
  const BindExprObj* bind = obj.as<BindExprObj>();
  const text::IRPrinter& printer = cache.printer();
  text::ExprAST rhs = cache.GetCachedExpr(bind->expr);
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  if (AppendAttrsAsKwargs(printer, bind->attrs, path->Attr("attrs"), &kwargs_keys,
                          &kwargs_values)) {
    rhs = text::ExprCallKw(printer->CallMnemonic(obj), {rhs}, std::move(kwargs_keys),
                           std::move(kwargs_values));
  }
  if (bind->vars.empty()) {
    return text::ExprStmtAST(std::move(rhs));
  }
  return text::AssignAST(DefineVarTuple(printer, bind->vars), std::move(rhs));
}

text::NodeAST ApplyBindVarDefGeneric(const Node& obj, const CachedPrinter& cache,
                                     const refl::AccessPath& path) {
  // Var definitions have no RHS value.  They print as
  // "x = std.BindVarDef(i32)" or "x, y = std.BindVarDef(i32, f32)" so the
  // variable types remain visible at the definition site.
  const BindVarDefObj* bind = obj.as<BindVarDefObj>();
  const text::IRPrinter& printer = cache.printer();
  if (bind->vars.empty()) {
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    if (!AppendAttrsAsKwargs(printer, bind->attrs, path->Attr("attrs"), &kwargs_keys,
                             &kwargs_values)) {
      return text::ExprStmtAST(text::IdAST("pass"));
    }
    return text::ExprStmtAST(text::ExprCallKw(printer->CallMnemonic(obj), {},
                                              std::move(kwargs_keys), std::move(kwargs_values)));
  }
  List<text::ExprAST> types;
  types.reserve(static_cast<int64_t>(bind->vars.size()));
  refl::AccessPath vars_path = path->Attr("vars");
  int64_t n = static_cast<int64_t>(bind->vars.size());
  for (int64_t i = 0; i < n; ++i) {
    types.push_back(printer->operator()(bind->vars[i]->ty, vars_path->ArrayItem(i)->Attr("ty"))
                        .cast<text::ExprAST>());
  }
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  text::ExprAST rhs =
      AppendAttrsAsKwargs(printer, bind->attrs, path->Attr("attrs"), &kwargs_keys, &kwargs_values)
          ? text::ExprCallKw(printer->CallMnemonic(obj), std::move(types), std::move(kwargs_keys),
                             std::move(kwargs_values))
          : text::ExprCall(printer->CallMnemonic(obj), std::move(types));
  return text::AssignAST(DefineVarTuple(printer, bind->vars), std::move(rhs));
}

text::NodeAST ApplyStoreGeneric(const Node& obj, const CachedPrinter& cache,
                                const refl::AccessPath&) {
  // Store operands are [var, *indices, rhs].  The generic turns them into
  // indexed assignment, for example [x, i, v] -> "x[i] = v".
  List<text::ExprAST> args = StoreOperands(obj.as<StoreObj>(), cache);
  return text::AssignAST(IndexFromPrintedOperands(args, /*end_index_offset=*/1),
                         args[args.size() - 1]);
}

text::NodeAST ApplyAssertGeneric(const Node& obj, const CachedPrinter& cache,
                                 const refl::AccessPath&) {
  // Attr-free Assert uses Python assert syntax: std.Assert(cond) -> "assert cond".
  // Attr-bearing asserts are handled by TextPrint(Assert) with an explicit call.
  return text::AssertAST(cache.GetCachedExpr(obj.as<AssertObj>()->cond));
}

text::NodeAST ApplyReturnGeneric(const Node& obj, const CachedPrinter& cache,
                                 const refl::AccessPath&) {
  return text::ReturnAST(PackOptionalValue(VarOperands(obj.as<ReturnObj>()->vars, cache)));
}

text::NodeAST ApplyYieldGeneric(const Node& obj, const CachedPrinter& cache,
                                const refl::AccessPath&) {
  return text::ExprStmtAST(
      text::YieldAST(PackOptionalValue(VarOperands(obj.as<YieldObj>()->vars, cache))));
}

text::NodeAST ApplyBreakGeneric(const Node&, const CachedPrinter&, const refl::AccessPath&) {
  return text::ExprStmtAST(text::IdAST("break"));
}

text::NodeAST ApplyContinueGeneric(const Node&, const CachedPrinter&, const refl::AccessPath&) {
  return text::ExprStmtAST(text::IdAST("continue"));
}

template <typename Fallback>
text::NodeAST ApplyTextGenericOrFallback(const Node& obj, const refl::AccessPath& path,
                                         const CachedPrinter& cache, Fallback fallback) {
  // Shared path for simple expression/statement printers.  The generic path
  // reads structured fields from the original node and the cache.  The fallback
  // lambda captures the surrounding TextPrint state, so it can preserve syntax
  // that is not representable as a flat mnemonic call, such as Bind attrs.
  //
  // Generic lookup is gated by the cached operands: if all non-literal operands
  // share one dialect, use that dialect; if every operand is literal, use the
  // current dialect from the printer stack.  Otherwise, keep the explicit
  // mnemonic spelling via the fallback.
  Array<String> dialect_mnemonic = DialectMnemonic(obj->type_index());
  if (dialect_mnemonic.size() == 3) {
    Optional<String> dialect = cache.CommonDialect();
    if (dialect.has_value()) {
      if (FnApplyGenerics fn =
              GenericsRegistry::Global()->Lookup(dialect.value(), dialect_mnemonic[2])) {
        return fn(obj, cache, path);
      }
    }
  }
  return fallback();
}

#define TVM_FFI_STD_GENERIC_TEXT_PRINT(TypeName)                                                  \
  text::NodeAST TextPrint(const TypeName& obj, const text::IRPrinter&, const refl::AccessPath&) { \
    const TVMFFITypeInfo* info = TVMFFIGetTypeInfo(obj->type_index());                            \
    String type_key(info->type_key.data, info->type_key.size);                                    \
    TVM_FFI_THROW(ValueError) << "No ffi.std text printer registered for " << type_key;           \
    TVM_FFI_UNREACHABLE();                                                                        \
  }

TVM_FFI_STD_GENERIC_TEXT_PRINT(Node)
TVM_FFI_STD_GENERIC_TEXT_PRINT(Ty)
TVM_FFI_STD_GENERIC_TEXT_PRINT(Stmt)
TVM_FFI_STD_GENERIC_TEXT_PRINT(Attrs)
TVM_FFI_STD_GENERIC_TEXT_PRINT(Aggregate)
TVM_FFI_STD_GENERIC_TEXT_PRINT(Expr)
TVM_FFI_STD_GENERIC_TEXT_PRINT(Bind)

#undef TVM_FFI_STD_GENERIC_TEXT_PRINT

text::NodeAST TextPrint(const Var& obj, const text::IRPrinter& printer, const refl::AccessPath&) {
  return DefineVar(printer, obj);
}

text::NodeAST TextPrint(const Module& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  List<text::StmtAST> stmts;
  int64_t n = static_cast<int64_t>(obj->funcs.size());
  stmts.reserve(n);
  refl::AccessPath funcs_path = path->Attr("funcs");
  for (int64_t i = 0; i < n; ++i) {
    stmts.push_back(
        printer->operator()(obj->funcs[i], funcs_path->ArrayItem(i)).cast<text::StmtAST>());
  }
  return text::StmtBlockAST(std::move(stmts));
}

text::NodeAST TextPrint(const Func& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  List<text::AssignAST> args;
  int64_t n = static_cast<int64_t>(obj->args.size());
  args.reserve(n);
  refl::AccessPath args_path = path->Attr("args");
  for (int64_t i = 0; i < n; ++i) {
    const Var& arg = obj->args[i];
    text::ExprAST lhs = DefineVar(printer, arg);
    Optional<text::ExprAST> annotation;
    if (arg->ty.defined()) {
      annotation =
          printer->operator()(arg->ty, args_path->ArrayItem(i)->Attr("ty")).cast<text::ExprAST>();
    }
    args.push_back(text::AssignAST(std::move(lhs), {}, std::move(annotation)));
  }
  List<text::StmtAST> body = PrintStmtList(printer, obj->body, path->Attr("body"));
  Optional<text::ExprAST> ret_type;
  if (obj->ret_type.has_value()) {
    ret_type = printer->operator()(*obj->ret_type, path->Attr("ret_type")).cast<text::ExprAST>();
  }
  List<String> decorator_keys;
  List<text::ExprAST> decorator_values;
  bool has_attrs = AppendAttrsAsKwargs(printer, obj->attrs, path->Attr("attrs"), &decorator_keys,
                                       &decorator_values);
  List<text::ExprAST> decorators;
  if (!has_attrs) {
    decorators.push_back(printer->CallMnemonic(obj));
  } else {
    decorators.push_back(text::ExprCallKw(printer->CallMnemonic(obj), {}, std::move(decorator_keys),
                                          std::move(decorator_values)));
  }
  return text::FunctionAST(text::IdAST(obj->symbol), std::move(args), std::move(decorators),
                           std::move(ret_type), std::move(body));
}

text::NodeAST TextPrint(const Range& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  Optional<text::ExprAST> start;
  Optional<text::ExprAST> stop;
  Optional<text::ExprAST> step;
  if (obj->start.has_value()) {
    start = printer->operator()(*obj->start, path->Attr("start")).cast<text::ExprAST>();
  }
  if (obj->stop.has_value()) {
    stop = printer->operator()(*obj->stop, path->Attr("stop")).cast<text::ExprAST>();
  }
  if (obj->step.has_value()) {
    step = printer->operator()(*obj->step, path->Attr("step")).cast<text::ExprAST>();
  }
  if (start.has_value() && !stop.has_value() && !step.has_value()) {
    return *start;
  }
  return text::SliceAST(std::move(start), std::move(stop), std::move(step));
}

text::NodeAST TextPrint(const AnyTy& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  return printer->CallMnemonic(obj);
}

text::NodeAST TextPrint(const PrimTy& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  String printed_name = DTypeAbbrev(obj->dtype);
  Array<String> dialect_mnemonic = DialectMnemonic(obj->type_index());
  String dialect = dialect_mnemonic[0];
  String mnemonic = dialect_mnemonic[1];
  String full_mnemonic(std::string(dialect.data(), dialect.size()) + "$" +
                       std::string(mnemonic.data(), mnemonic.size()));
  if (printer->cfg->dialect_print_map.count(full_mnemonic)) {
    String mapped = printer->cfg->dialect_print_map[full_mnemonic];
    if (mapped == "*") {
      return text::IdAST(printed_name);
    }
    return text::DottedName(std::move(mapped));
  }
  if (printer->cfg->dialect_print_map.count(dialect)) {
    String mapped = printer->cfg->dialect_print_map[dialect];
    if (mapped == "*") {
      return text::IdAST(printed_name);
    }
    return text::ExprAttr(text::DottedName(std::move(mapped)), printed_name);
  }
  return text::ExprAttr(text::DottedName(std::move(dialect)), printed_name);
}

text::NodeAST TextPrint(const TupleType& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  List<text::ExprAST> fields;
  int64_t n = static_cast<int64_t>(obj->fields.size());
  fields.reserve(n);
  refl::AccessPath fields_path = path->Attr("fields");
  for (int64_t i = 0; i < n; ++i) {
    fields.push_back(
        printer->operator()(obj->fields[i], fields_path->ArrayItem(i)).cast<text::ExprAST>());
  }
  return text::IndexAST(printer->CallMnemonic(obj), std::move(fields));
}

text::NodeAST TextPrint(const TensorTy& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  PrimTy dtype(obj->dtype);
  return text::IndexAST(printer->operator()(dtype, path->Attr("dtype")).cast<text::ExprAST>(),
                        PrintExprList(printer, obj->shape, path->Attr("shape")));
}

#define TVM_FFI_STD_LITERAL_TEXT_PRINT(TypeName, LiteralFactory)               \
  text::NodeAST TextPrint(const TypeName& obj, const text::IRPrinter& printer, \
                          const refl::AccessPath& path) {                      \
    return text::LiteralAST::LiteralFactory(obj->value);                       \
  }

TVM_FFI_STD_LITERAL_TEXT_PRINT(IntImm, Int)
TVM_FFI_STD_LITERAL_TEXT_PRINT(FloatImm, Float)
TVM_FFI_STD_LITERAL_TEXT_PRINT(StringImm, Str)

#undef TVM_FFI_STD_LITERAL_TEXT_PRINT

#define TVM_FFI_STD_BINARY_TEXT_PRINT(TypeName)                                  \
  text::NodeAST TextPrint(const TypeName& obj, const text::IRPrinter& printer,   \
                          const refl::AccessPath& path) {                        \
    CachedPrinter cache(printer);                                                \
    cache.ApplyDialect(obj->a, path->Attr("a"));                                 \
    cache.ApplyDialect(obj->b, path->Attr("b"));                                 \
    return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST { \
      return text::ExprCall(printer->CallMnemonic(obj),                          \
                            BinaryOperands<TypeName##Obj>(obj, cache));          \
    });                                                                          \
  }

TVM_FFI_STD_BINARY_TEXT_PRINT(Add)
TVM_FFI_STD_BINARY_TEXT_PRINT(Sub)
TVM_FFI_STD_BINARY_TEXT_PRINT(Mul)
TVM_FFI_STD_BINARY_TEXT_PRINT(FloorDiv)
TVM_FFI_STD_BINARY_TEXT_PRINT(FloorMod)
TVM_FFI_STD_BINARY_TEXT_PRINT(Min)
TVM_FFI_STD_BINARY_TEXT_PRINT(Max)
TVM_FFI_STD_BINARY_TEXT_PRINT(Eq)
TVM_FFI_STD_BINARY_TEXT_PRINT(Ne)
TVM_FFI_STD_BINARY_TEXT_PRINT(Le)
TVM_FFI_STD_BINARY_TEXT_PRINT(Ge)
TVM_FFI_STD_BINARY_TEXT_PRINT(Gt)
TVM_FFI_STD_BINARY_TEXT_PRINT(Lt)
TVM_FFI_STD_BINARY_TEXT_PRINT(And)
TVM_FFI_STD_BINARY_TEXT_PRINT(Or)

#undef TVM_FFI_STD_BINARY_TEXT_PRINT

text::NodeAST TextPrint(const Not& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  cache.ApplyDialect(obj->operand, path->Attr("operand"));
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprCall(printer->CallMnemonic(obj), {cache.GetCachedExpr(obj->operand)});
  });
}

text::NodeAST TextPrint(const Load& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  cache.ApplyDialect(obj->var, path->Attr("var"));
  int64_t n = static_cast<int64_t>(obj->indices.size());
  refl::AccessPath indices_path = path->Attr("indices");
  for (int64_t i = 0; i < n; ++i) {
    cache.ApplyDialect(obj->indices[i], indices_path->ArrayItem(i));
  }
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprCall(printer->CallMnemonic(obj), IndexOperands(obj.as<LoadObj>(), cache));
  });
}

text::NodeAST TextPrint(const Cast& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  cache.ApplyDialect(obj->ty, path->Attr("ty"));
  cache.ApplyDialect(obj->value, path->Attr("value"));
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprCall(printer->CallMnemonic(obj),
                          {cache.GetCachedExpr(obj->ty), cache.GetCachedExpr(obj->value)});
  });
}

text::NodeAST TextPrint(const Call& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  Optional<String> callee_name;
  if (std::optional<String> symbol = obj->callee.as<String>()) {
    callee_name = *symbol;
  } else if (std::optional<Func> func = obj->callee.as<Func>()) {
    callee_name = (*func)->symbol;
  }
  text::ExprAST callee =
      callee_name.has_value()
          ? text::ExprAST(text::IdAST(callee_name.value()))
          : printer->operator()(obj->callee, path->Attr("callee")).cast<text::ExprAST>();
  List<text::ExprAST> args = PrintExprList(printer, obj->args, path->Attr("args"));
  List<text::ExprAST> call_args{std::move(callee)};
  call_args.reserve(static_cast<int64_t>(obj->args.size() + 1));
  for (text::ExprAST arg : args) {
    call_args.push_back(arg);
  }
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  if (!AppendAttrsAsKwargs(printer, obj->attr, path->Attr("attr"), &kwargs_keys, &kwargs_values)) {
    return text::ExprCall(printer->CallMnemonic(obj), std::move(call_args));
  }
  return text::ExprCallKw(printer->CallMnemonic(obj), std::move(call_args), std::move(kwargs_keys),
                          std::move(kwargs_values));
}

text::NodeAST TextPrint(const IfStmt& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  return text::IfAST(printer->operator()(obj->cond, path->Attr("cond")).cast<text::ExprAST>(),
                     PrintStmtList(printer, obj->then_body, path->Attr("then_body")),
                     PrintStmtList(printer, obj->else_body, path->Attr("else_body")));
}

text::NodeAST TextPrint(const For& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  DialectFrame dialect_frame(printer, obj);
  // A for-loop always needs a target.  Scope bindings such as
  // [VarDef([i]), VarDef([j])] become "for i, j in ..."; no carried bindings
  // become the placeholder target "for _ in ...".
  List<text::ExprAST> targets;
  for (const Bind& bind : obj->vars) {
    for (const Var& var : bind->vars) {
      targets.push_back(DefineVar(printer, var));
    }
  }
  text::ExprAST lhs = text::IdAST("_");
  if (targets.size() == 1) {
    lhs = targets[0];
  } else if (!targets.empty()) {
    lhs = text::TupleAST(std::move(targets));
  }
  List<text::ExprAST> range_args;
  refl::AccessPath range_path = path->Attr("range_");
  if (obj->range_->start.has_value()) {
    range_args.push_back(
        printer->operator()(*obj->range_->start, range_path->Attr("start")).cast<text::ExprAST>());
  }
  if (obj->range_->stop.has_value()) {
    if (!obj->range_->start.has_value()) {
      range_args.push_back(text::LiteralAST::Null());
    }
    range_args.push_back(
        printer->operator()(*obj->range_->stop, range_path->Attr("stop")).cast<text::ExprAST>());
  }
  if (obj->range_->step.has_value()) {
    if (!obj->range_->stop.has_value()) {
      range_args.push_back(text::LiteralAST::Null());
    }
    range_args.push_back(
        printer->operator()(*obj->range_->step, range_path->Attr("step")).cast<text::ExprAST>());
  }
  List<String> range_kwarg_keys;
  List<text::ExprAST> range_kwarg_values;
  AppendAttrsAsKwargs(printer, obj->attrs, path->Attr("attrs"), &range_kwarg_keys,
                      &range_kwarg_values);
  text::ExprAST rhs =
      range_kwarg_keys.empty()
          ? text::ExprCall(text::IdAST("range"), std::move(range_args))
          : text::ExprCallKw(text::IdAST("range"), std::move(range_args),
                             std::move(range_kwarg_keys), std::move(range_kwarg_values));
  return text::ForAST(std::move(lhs), std::move(rhs),
                      PrintStmtList(printer, obj->body, path->Attr("body")));
}

text::NodeAST TextPrint(const While& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  DialectFrame dialect_frame(printer, obj);
  List<String> while_kwarg_keys;
  List<text::ExprAST> while_kwarg_values;
  bool has_attrs = AppendAttrsAsKwargs(printer, obj->attrs, path->Attr("attrs"), &while_kwarg_keys,
                                       &while_kwarg_values);
  if (obj->vars.empty() && !has_attrs) {
    return text::WhileAST(printer->operator()(obj->cond, path->Attr("cond")).cast<text::ExprAST>(),
                          PrintStmtList(printer, obj->body, path->Attr("body")));
  }
  List<text::ExprAST> while_args{
      printer->operator()(obj->cond, path->Attr("cond")).cast<text::ExprAST>()};
  refl::AccessPath vars_path = path->Attr("vars");
  int64_t n = static_cast<int64_t>(obj->vars.size());
  for (int64_t i = 0; i < n; ++i) {
    while_args.push_back(BindInitializerCall(obj->vars[i], printer, vars_path->ArrayItem(i)));
  }
  text::ExprAST rhs =
      while_kwarg_keys.empty()
          ? text::ExprCall(printer->CallMnemonic(obj), std::move(while_args))
          : text::ExprCallKw(printer->CallMnemonic(obj), std::move(while_args),
                             std::move(while_kwarg_keys), std::move(while_kwarg_values));
  Optional<text::ExprAST> lhs = DefineScopeVarsAsWithTargets(printer, obj->vars);
  return text::WithAST(std::move(lhs), std::move(rhs),
                       PrintStmtList(printer, obj->body, path->Attr("body")));
}

text::NodeAST TextPrint(const Scope& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  DialectFrame dialect_frame(printer, obj);
  List<String> scope_kwarg_keys;
  List<text::ExprAST> scope_kwarg_values;
  bool has_attrs = AppendAttrsAsKwargs(printer, obj->attrs, path->Attr("attrs"), &scope_kwarg_keys,
                                       &scope_kwarg_values);
  if (obj->vars.empty() && !has_attrs) {
    return text::StmtBlockAST(PrintStmtList(printer, obj->body, path->Attr("body")));
  }
  List<text::ExprAST> scope_args;
  int64_t n = static_cast<int64_t>(obj->vars.size());
  scope_args.reserve(n);
  refl::AccessPath vars_path = path->Attr("vars");
  for (int64_t i = 0; i < n; ++i) {
    scope_args.push_back(BindInitializerCall(obj->vars[i], printer, vars_path->ArrayItem(i)));
  }
  text::ExprAST rhs =
      scope_kwarg_keys.empty()
          ? text::ExprCall(printer->CallMnemonic(obj), std::move(scope_args))
          : text::ExprCallKw(printer->CallMnemonic(obj), std::move(scope_args),
                             std::move(scope_kwarg_keys), std::move(scope_kwarg_values));
  Optional<text::ExprAST> lhs = DefineScopeVarsAsWithTargets(printer, obj->vars);
  return text::WithAST(std::move(lhs), std::move(rhs),
                       PrintStmtList(printer, obj->body, path->Attr("body")));
}

text::NodeAST TextPrint(const BindExpr& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  int64_t num_vars = static_cast<int64_t>(obj->vars.size());
  refl::AccessPath vars_path = path->Attr("vars");
  for (int64_t i = 0; i < num_vars; ++i) {
    cache.ApplyDialect(obj->vars[i], vars_path->ArrayItem(i));
  }
  cache.ApplyDialect(obj->expr, path->Attr("expr"));
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    List<text::ExprAST> args = VarOperands(obj->vars, cache);
    args.push_back(cache.GetCachedExpr(obj->expr));
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    text::ExprAST call =
        AppendAttrsAsKwargs(printer, obj->attrs, path->Attr("attrs"), &kwargs_keys, &kwargs_values)
            ? text::ExprCallKw(printer->CallMnemonic(obj), std::move(args), std::move(kwargs_keys),
                               std::move(kwargs_values))
            : text::ExprCall(printer->CallMnemonic(obj), std::move(args));
    return text::ExprStmtAST(std::move(call));
  });
}

text::NodeAST TextPrint(const BindVarDef& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  int64_t num_vars = static_cast<int64_t>(obj->vars.size());
  refl::AccessPath vars_path = path->Attr("vars");
  for (int64_t i = 0; i < num_vars; ++i) {
    cache.ApplyDialect(obj->vars[i], vars_path->ArrayItem(i));
  }
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    List<text::ExprAST> args = VarOperands(obj->vars, cache);
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    text::ExprAST call =
        AppendAttrsAsKwargs(printer, obj->attrs, path->Attr("attrs"), &kwargs_keys, &kwargs_values)
            ? text::ExprCallKw(printer->CallMnemonic(obj), std::move(args), std::move(kwargs_keys),
                               std::move(kwargs_values))
            : text::ExprCall(printer->CallMnemonic(obj), std::move(args));
    return text::ExprStmtAST(std::move(call));
  });
}

text::NodeAST TextPrint(const Store& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  cache.ApplyDialect(obj->var, path->Attr("var"));
  int64_t n = static_cast<int64_t>(obj->indices.size());
  refl::AccessPath indices_path = path->Attr("indices");
  for (int64_t i = 0; i < n; ++i) {
    cache.ApplyDialect(obj->indices[i], indices_path->ArrayItem(i));
  }
  cache.ApplyDialect(obj->rhs, path->Attr("rhs"));
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(
        text::ExprCall(printer->CallMnemonic(obj), StoreOperands(obj.as<StoreObj>(), cache)));
  });
}

text::NodeAST TextPrint(const Assert& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  cache.ApplyDialect(obj->cond, path->Attr("cond"));
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  if (AppendAttrsAsKwargs(printer, obj->attrs, path->Attr("attrs"), &kwargs_keys, &kwargs_values)) {
    return text::ExprStmtAST(text::ExprCallKw(printer->CallMnemonic(obj),
                                              {cache.GetCachedExpr(obj->cond)},
                                              std::move(kwargs_keys), std::move(kwargs_values)));
  }
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(
        text::ExprCall(printer->CallMnemonic(obj), {cache.GetCachedExpr(obj->cond)}));
  });
}

text::NodeAST TextPrint(const Return& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  refl::AccessPath vars_path = path->Attr("vars");
  int64_t num_vars = static_cast<int64_t>(obj->vars.size());
  for (int64_t i = 0; i < num_vars; ++i) {
    cache.ApplyDialect(obj->vars[i], vars_path->ArrayItem(i));
  }
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(
        text::ExprCall(printer->CallMnemonic(obj), VarOperands(obj->vars, cache)));
  });
}

text::NodeAST TextPrint(const Yield_& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  refl::AccessPath vars_path = path->Attr("vars");
  int64_t num_vars = static_cast<int64_t>(obj->vars.size());
  for (int64_t i = 0; i < num_vars; ++i) {
    cache.ApplyDialect(obj->vars[i], vars_path->ArrayItem(i));
  }
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(
        text::ExprCall(printer->CallMnemonic(obj), VarOperands(obj->vars, cache)));
  });
}

text::NodeAST TextPrint(const Break& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(text::ExprCall(printer->CallMnemonic(obj), {}));
  });
}

text::NodeAST TextPrint(const Continue& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(text::ExprCall(printer->CallMnemonic(obj), {}));
  });
}

text::NodeAST TextPrint(const DictAttrs& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  std::vector<String> sorted_keys;
  sorted_keys.reserve(obj->values.size());
  for (const auto& kv : obj->values) {
    sorted_keys.push_back(kv.first);
  }
  std::sort(sorted_keys.begin(), sorted_keys.end());

  kwargs_keys.reserve(static_cast<int64_t>(sorted_keys.size()));
  kwargs_values.reserve(static_cast<int64_t>(sorted_keys.size()));
  refl::AccessPath values_path = path->Attr("values");
  int64_t n = static_cast<int64_t>(sorted_keys.size());
  for (int64_t i = 0; i < n; ++i) {
    const String& key = sorted_keys[i];
    kwargs_keys.push_back(key);
    kwargs_values.push_back(
        printer->operator()(obj->values[key], values_path->MapItem(key)).cast<text::ExprAST>());
  }
  return text::CallAST(printer->CallMnemonic(obj), {}, std::move(kwargs_keys),
                       std::move(kwargs_values));
}

// NOLINTEND(bugprone-misplaced-widening-cast,bugprone-narrowing-conversions)

}  // namespace

TVM_FFI_STATIC_INIT_BLOCK() {
  GenericsRegistry* registry = GenericsRegistry::Global();
  registry->Register("std", "__add__", ApplyOperationGeneric<AddObj, text::OperationASTObj::kAdd>);
  registry->Register("std", "__sub__", ApplyOperationGeneric<SubObj, text::OperationASTObj::kSub>);
  registry->Register("std", "__mul__", ApplyOperationGeneric<MulObj, text::OperationASTObj::kMult>);
  registry->Register("std", "__floordiv__",
                     ApplyOperationGeneric<FloorDivObj, text::OperationASTObj::kFloorDiv>);
  registry->Register("std", "__mod__",
                     ApplyOperationGeneric<FloorModObj, text::OperationASTObj::kMod>);
  registry->Register("std", "min", ApplyMinGeneric<MinObj>);
  registry->Register("std", "max", ApplyMaxGeneric<MaxObj>);
  registry->Register("std", "__eq__", ApplyOperationGeneric<EqObj, text::OperationASTObj::kEq>);
  registry->Register("std", "__ne__", ApplyOperationGeneric<NeObj, text::OperationASTObj::kNotEq>);
  registry->Register("std", "__le__", ApplyOperationGeneric<LeObj, text::OperationASTObj::kLtE>);
  registry->Register("std", "__ge__", ApplyOperationGeneric<GeObj, text::OperationASTObj::kGtE>);
  registry->Register("std", "__gt__", ApplyOperationGeneric<GtObj, text::OperationASTObj::kGt>);
  registry->Register("std", "__lt__", ApplyOperationGeneric<LtObj, text::OperationASTObj::kLt>);
  registry->Register("std", "__and__", ApplyOperationGeneric<AndObj, text::OperationASTObj::kAnd>);
  registry->Register("std", "__or__", ApplyOperationGeneric<OrObj, text::OperationASTObj::kOr>);
  registry->Register("std", "__invert__", ApplyNotGeneric);
  registry->Register("std", "__load__", ApplyLoadGeneric);
  registry->Register("std", "__cast__", ApplyCastGeneric);
  registry->Register("std", "__bind_expr__", ApplyBindExprGeneric);
  registry->Register("std", "__bind_var_def__", ApplyBindVarDefGeneric);
  registry->Register("std", "__store__", ApplyStoreGeneric);
  registry->Register("std", "__assert__", ApplyAssertGeneric);
  registry->Register("std", "__return__", ApplyReturnGeneric);
  registry->Register("std", "__yield__", ApplyYieldGeneric);
  registry->Register("std", "__break__", ApplyBreakGeneric);
  registry->Register("std", "__continue__", ApplyContinueGeneric);

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

#define TVM_FFI_STD_OBJECT_DEF_GENERIC(ObjType, RefType, Name, Generic)     \
  refl::ObjectDef<ObjType>()                                                \
      .def_type_attr(refl::type_attr::kTextPrint, TextPrintHook<RefType>()) \
      .def_type_attr(refl::type_attr::kDialectMnemonic,                     \
                     Array<String>{String("std"), String(Name), String(Generic)})

  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(NodeObj, Node, refl::init(false));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(TyObj, Ty, refl::init(false));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(StmtObj, Stmt, refl::init(false))
      .def_rw("attrs", &StmtObj::attrs, refl::kw_only(true), refl::default_value(nullptr));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(AttrsObj, Attrs, refl::init(false)).def_convert<Attrs>();
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(AggregateObj, Aggregate, refl::init(false));
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(ExprObj, Expr, refl::init(false))
      .def_convert<Expr>()
      .def_rw("ty", &ExprObj::ty);
  TVM_FFI_STD_OBJECT_DEF(VarObj, Var, "Var")
      .def_rw("name", &VarObj::name, refl::AttachFieldFlag::SEqHashIgnore());
  TVM_FFI_STD_OBJECT_DEF(FuncObj, Func, "Func")
      .def_rw("symbol", &FuncObj::symbol)
      .def_rw("args", &FuncObj::args, refl::AttachFieldFlag::SEqHashDef())
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
  TVM_FFI_STD_OBJECT_DEF(TupleTypeObj, TupleType, "Tuple").def_rw("fields", &TupleTypeObj::fields);
  TVM_FFI_STD_OBJECT_DEF(TensorTyObj, TensorTy, "Tensor")
      .def_rw("shape", &TensorTyObj::shape)
      .def_rw("dtype", &TensorTyObj::dtype);
  TVM_FFI_STD_OBJECT_DEF(IntImmObj, IntImm, "IntImm").def_rw("value", &IntImmObj::value);
  TVM_FFI_STD_OBJECT_DEF(FloatImmObj, FloatImm, "FloatImm").def_rw("value", &FloatImmObj::value);
  TVM_FFI_STD_OBJECT_DEF(StringImmObj, StringImm, "StringImm")
      .def_rw("value", &StringImmObj::value);

#define TVM_FFI_STD_DEF_BINARY(TypeName, Generic)                             \
  TVM_FFI_STD_OBJECT_DEF_GENERIC(TypeName##Obj, TypeName, #TypeName, Generic) \
      .def_rw("a", &TypeName##Obj::a)                                         \
      .def_rw("b", &TypeName##Obj::b)

  TVM_FFI_STD_DEF_BINARY(Add, "__add__");
  TVM_FFI_STD_DEF_BINARY(Sub, "__sub__");
  TVM_FFI_STD_DEF_BINARY(Mul, "__mul__");
  TVM_FFI_STD_DEF_BINARY(FloorDiv, "__floordiv__");
  TVM_FFI_STD_DEF_BINARY(FloorMod, "__mod__");
  TVM_FFI_STD_DEF_BINARY(Min, "min");
  TVM_FFI_STD_DEF_BINARY(Max, "max");
  TVM_FFI_STD_DEF_BINARY(Eq, "__eq__");
  TVM_FFI_STD_DEF_BINARY(Ne, "__ne__");
  TVM_FFI_STD_DEF_BINARY(Le, "__le__");
  TVM_FFI_STD_DEF_BINARY(Ge, "__ge__");
  TVM_FFI_STD_DEF_BINARY(Gt, "__gt__");
  TVM_FFI_STD_DEF_BINARY(Lt, "__lt__");
  TVM_FFI_STD_DEF_BINARY(And, "__and__");
  TVM_FFI_STD_DEF_BINARY(Or, "__or__");

#undef TVM_FFI_STD_DEF_BINARY

  TVM_FFI_STD_OBJECT_DEF_GENERIC(NotObj, Not, "Not", "__invert__")
      .def_convert<Not>()
      .def_rw("operand", &NotObj::operand);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(LoadObj, Load, "Load", "__load__")
      .def_rw("var", &LoadObj::var)
      .def_rw("indices", &LoadObj::indices);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(CastObj, Cast, "Cast", "__cast__")
      .def_rw("value", &CastObj::value);
  TVM_FFI_STD_OBJECT_DEF(CallObj, Call, "Call")
      .def_rw("callee", &CallObj::callee)
      .def_rw("args", &CallObj::args)
      .def_rw("attr", &CallObj::attr, refl::default_value(nullptr));
  TVM_FFI_STD_OBJECT_DEF_GENERIC(IfStmtObj, IfStmt, "IfStmt", "__if__")
      .def_rw("cond", &IfStmtObj::cond)
      .def_rw("then_body", &IfStmtObj::then_body)
      .def_rw("else_body", &IfStmtObj::else_body);
  TVM_FFI_STD_OBJECT_DEF_BASE_INIT(BindObj, Bind, refl::init(false))
      .def_rw("vars", &BindObj::vars, refl::AttachFieldFlag::SEqHashDef());
  TVM_FFI_STD_OBJECT_DEF_GENERIC(BindExprObj, BindExpr, "BindExpr", "__bind_expr__")
      .def_rw("expr", &BindExprObj::expr);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(BindVarDefObj, BindVarDef, "BindVarDef", "__bind_var_def__");
  TVM_FFI_STD_OBJECT_DEF(ScopeObj, Scope, "Scope")
      .def_rw("vars", &ScopeObj::vars, refl::AttachFieldFlag::SEqHashDef())
      .def_rw("body", &ScopeObj::body);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(ForObj, For, "For", "__for__").def_rw("range_", &ForObj::range_);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(WhileObj, While, "While", "__while__")
      .def_rw("cond", &WhileObj::cond);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(StoreObj, Store, "Store", "__store__")
      .def_rw("var", &StoreObj::var)
      .def_rw("indices", &StoreObj::indices)
      .def_rw("rhs", &StoreObj::rhs);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(AssertObj, Assert, "Assert", "__assert__")
      .def_rw("cond", &AssertObj::cond);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(ReturnObj, Return, "Return", "__return__")
      .def_rw("vars", &ReturnObj::vars);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(YieldObj, Yield_, "Yield", "__yield__")
      .def_rw("vars", &YieldObj::vars);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(BreakObj, Break, "Break", "__break__");
  TVM_FFI_STD_OBJECT_DEF_GENERIC(ContinueObj, Continue, "Continue", "__continue__");
  TVM_FFI_STD_OBJECT_DEF(DictAttrsObj, DictAttrs, "DictAttrs")
      .def_rw("values", &DictAttrsObj::values);

#undef TVM_FFI_STD_OBJECT_DEF
#undef TVM_FFI_STD_OBJECT_DEF_GENERIC
#undef TVM_FFI_STD_OBJECT_DEF_BASE
#undef TVM_FFI_STD_OBJECT_DEF_BASE_INIT
}

}  // namespace std_
}  // namespace ffi
}  // namespace tvm
