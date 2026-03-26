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
#include <tvm/ffi/function.h>
#include <tvm/ffi/reflection/accessor.h>
#include <tvm/ffi/reflection/creator.h>
#include <tvm/ffi/reflection/registry.h>

#include <algorithm>
#include <string>
#include <unordered_map>
#include <utility>

namespace tvm {
namespace ffi {
namespace std_ {

namespace {

// The text AST APIs use int64_t sizes, while container sizes are size_t.
// Casts in this file are local size conversions for printer construction.
// NOLINTBEGIN(bugprone-misplaced-widening-cast,bugprone-narrowing-conversions)

namespace refl = ::tvm::ffi::reflection;
namespace text = ::tvm::ffi::pyast;

constexpr DLDataType kDefaultIntLiteralType{static_cast<uint8_t>(kDLInt), 64, 1};
constexpr DLDataType kDefaultFloatLiteralType{static_cast<uint8_t>(kDLFloat), 32, 1};
constexpr DLDataType kDefaultBoolLiteralType{static_cast<uint8_t>(kDLBool), 8, 1};

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
TVM_FFI_STD_TEXT_PRINT_DECL(BoolImm)
TVM_FFI_STD_TEXT_PRINT_DECL(IntImm)
TVM_FFI_STD_TEXT_PRINT_DECL(FloatImm)
TVM_FFI_STD_TEXT_PRINT_DECL(StringImm)
TVM_FFI_STD_TEXT_PRINT_DECL(Add)
TVM_FFI_STD_TEXT_PRINT_DECL(Sub)
TVM_FFI_STD_TEXT_PRINT_DECL(Mul)
TVM_FFI_STD_TEXT_PRINT_DECL(CDiv)
TVM_FFI_STD_TEXT_PRINT_DECL(FloorDiv)
TVM_FFI_STD_TEXT_PRINT_DECL(FloorMod)
TVM_FFI_STD_TEXT_PRINT_DECL(CMod)
TVM_FFI_STD_TEXT_PRINT_DECL(Pow)
TVM_FFI_STD_TEXT_PRINT_DECL(LShift)
TVM_FFI_STD_TEXT_PRINT_DECL(RShift)
TVM_FFI_STD_TEXT_PRINT_DECL(Xor)
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

/*!
 * \brief Build a call target expression from an object's registered mnemonic.
 *
 * The ``__ffi_dialect_mnemonic__`` type attribute must be an
 * ``Array<String>`` with ``{dialect, mnemonic}`` or
 * ``{dialect, mnemonic, generics}``, for example ``{"std", "Add"}``.
 *
 * Full mnemonic aliases in ``cfg->dialect_print_map`` take precedence over
 * dialect aliases.  The alias value ``"*"`` drops the prefix and returns just
 * the printed name.
 */
text::ExprAST CallMnemonic(const text::PrinterConfig& cfg, const ObjectRef& obj) {
  Array<String> dialect_mnemonic = DialectMnemonic(obj->type_index());
  String dialect = dialect_mnemonic[0];
  String printed_name = dialect_mnemonic[1];
  String full_mnemonic = String(std::string(dialect.data(), dialect.size()) + "$" +
                                std::string(printed_name.data(), printed_name.size()));
  const Dict<String, String>& dialect_print_map = cfg->dialect_print_map;
  if (dialect_print_map.count(full_mnemonic)) {
    String mapped = dialect_print_map[full_mnemonic];
    if (mapped == "*") {
      return text::IdAST(std::move(printed_name));
    }
    return text::DottedName(std::move(mapped));
  }
  if (dialect_print_map.count(dialect)) {
    String mapped = dialect_print_map[dialect];
    if (mapped == "*") {
      return text::IdAST(std::move(printed_name));
    }
    return text::ExprAttr(text::DottedName(std::move(mapped)), std::move(printed_name));
  }
  return text::ExprAttr(text::DottedName(std::move(dialect)), std::move(printed_name));
}

text::ExprAST CallCustomMnemonic(const text::PrinterConfig& cfg, const ObjectRef& obj,
                                 String printed_name, bool prefix_dialect = false) {
  Array<String> dialect_mnemonic = DialectMnemonic(obj->type_index());
  String dialect = dialect_mnemonic[0];
  String full_mnemonic =
      String(std::string(dialect.data(), dialect.size()) + "$" +
             std::string(dialect_mnemonic[1].data(), dialect_mnemonic[1].size()));
  const Dict<String, String>& dialect_print_map = cfg->dialect_print_map;
  if (dialect_print_map.count(full_mnemonic)) {
    String mapped = dialect_print_map[full_mnemonic];
    if (mapped == "*") {
      return text::IdAST(std::move(printed_name));
    }
    return text::DottedName(std::move(mapped));
  }
  if (dialect_print_map.count(dialect)) {
    String mapped = dialect_print_map[dialect];
    if (mapped == "*") {
      return text::IdAST(std::move(printed_name));
    }
    return text::ExprAttr(text::DottedName(std::move(mapped)), std::move(printed_name));
  }
  if (prefix_dialect) {
    return text::ExprAttr(text::DottedName(std::move(dialect)), std::move(printed_name));
  }
  return text::IdAST(std::move(printed_name));
}

class DialectFrame {
 public:
  DialectFrame(const text::IRPrinter& printer, const Node& obj) : printer_(printer.get()) {
    printer_->dialects.push_back(Dialect(obj.type_index()));
  }

  ~DialectFrame() { printer_->dialects.pop_back(); }  // NOLINT(modernize-use-equals-default)

 private:
  text::IRPrinterObj* printer_;
};

Optional<text::ExprAST> LiteralValueAST(const ObjectRef& obj) {
  if (const BoolImmObj* bool_imm = obj.as<BoolImmObj>()) {
    return text::LiteralAST::Bool(bool_imm->value);
  }
  if (const IntImmObj* int_imm = obj.as<IntImmObj>()) {
    return text::LiteralAST::Int(int_imm->value);
  }
  if (const FloatImmObj* float_imm = obj.as<FloatImmObj>()) {
    return text::LiteralAST::Float(float_imm->value);
  }
  if (const StringImmObj* string_imm = obj.as<StringImmObj>()) {
    return text::LiteralAST::Str(string_imm->value);
  }
  return {};
}

class CachedPrinter {
 public:
  explicit CachedPrinter(text::IRPrinter printer) : printer_(std::move(printer)) {}

  Any RunCache(const ObjectRef& obj, const refl::AccessPath& path) {
    Any ast;
    if (Optional<text::ExprAST> literal = LiteralValueAST(obj)) {
      ast = *literal;
    } else {
      ast = printer_->operator()(obj, path);
    }
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

  Function GetCachedFunction() const {
    return Function::FromTyped(
        [this](const ObjectRef& obj) -> Any { return this->cache_.at(obj); });
  }

  text::ExprAST ExprFromCache(const ObjectRef& obj) const {
    return this->cache_.at(obj).cast<text::ExprAST>();
  }

  const text::IRPrinter& printer() const { return printer_; }

 private:
  text::IRPrinter printer_;
  std::unordered_map<ObjectRef, Any, ObjectPtrHash, ObjectPtrEqual> cache_;
  std::unordered_set<String> dialects_;
};

class GenericsRegistry {
 public:
  static GenericsRegistry* Global() {
    static GenericsRegistry registry;
    return &registry;
  }

  template <typename NodeType>
  void Register(const String& dialect, const String& generic,
                text::NodeAST (*fn)(const text::IRPrinter&, const NodeType&,
                                    const refl::AccessPath&, const Function&)) {
    using GenericFunc = TypedFunction<text::NodeAST(const text::IRPrinter&, const NodeType&,
                                                    const refl::AccessPath&, const Function&)>;
    generics_map_[dialect + "$" + generic] = GenericFunc(fn);
  }

  void Register(const String& dialect, const String& generic, Function fn) {
    generics_map_[dialect + "$" + generic] = std::move(fn);
  }

  Function Lookup(const String& dialect, const String& generic) const {
    auto it = generics_map_.find(dialect + "$" + generic);
    return it == generics_map_.end() ? nullptr : (*it).second;
  }

 private:
  std::unordered_map<String, Function> generics_map_;
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
  // "with std.scope(...):", one binding prints as "with std.scope(...) as x:",
  // and multiple bindings print as tuple target syntax:
  // "with std.scope(...) as (x, state):".
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

bool AppendAttrsAsKwargs(const text::ExprAST& attrs_ast, List<String>* kwargs_keys,
                         List<text::ExprAST>* kwargs_values) {
  // Attrs subclasses print as constructor calls.  This helper strips the
  // constructor and appends only "tag=..." so enclosing syntax can use compact
  // forms such as @std.func(tag="demo") or range(..., tag="demo").
  const text::CallASTObj* call = attrs_ast.as<text::CallASTObj>();
  if (call == nullptr) {
    TVM_FFI_THROW(ValueError) << "ffi.std.Attrs text printer must return CallAST";
  }
  if (call->args.empty()) {
    kwargs_keys->reserve(static_cast<int64_t>(kwargs_keys->size() + call->kwargs_keys.size()));
    kwargs_values->reserve(
        static_cast<int64_t>(kwargs_values->size() + call->kwargs_values.size()));
    int64_t n = static_cast<int64_t>(call->kwargs_keys.size());
    for (int64_t i = 0; i < n; ++i) {
      kwargs_keys->push_back(call->kwargs_keys[i]);
      kwargs_values->push_back(call->kwargs_values[i]);
    }
    return n != 0;
  }

  // Some attrs may not be representable as Python keyword arguments, for
  // example non-identifier DictAttrs keys.  Let callers fall back to attrs=...
  // instead of emitting invalid Python.
  return false;
}

void AppendAttrsKeyword(const text::IRPrinter& printer, const Optional<Attrs>& attrs,
                        const refl::AccessPath& path, List<String>* kwargs_keys,
                        List<text::ExprAST>* kwargs_values) {
  if (!attrs.has_value()) return;
  kwargs_keys->push_back("attrs");
  kwargs_values->push_back(printer->operator()(*attrs, path).cast<text::ExprAST>());
}

bool AppendAttrsAsKwargsOrKeyword(const text::IRPrinter& printer, const Optional<Attrs>& attrs,
                                  const refl::AccessPath& path, List<String>* kwargs_keys,
                                  List<text::ExprAST>* kwargs_values) {
  if (!attrs.has_value()) return false;
  text::ExprAST attrs_ast = printer->operator()(*attrs, path).cast<text::ExprAST>();
  if (AppendAttrsAsKwargs(attrs_ast, kwargs_keys, kwargs_values)) {
    return true;
  }
  AppendAttrsKeyword(printer, attrs, path, kwargs_keys, kwargs_values);
  return true;
}

text::ExprAST BindInitializerCall(const Bind& bind, const text::IRPrinter& printer,
                                  const refl::AccessPath& path) {
  // Build the initializer expression that appears inside a scope-like context
  // manager call.  Scope and While carry their variables as Bind nodes:
  //
  //   Scope(binds=[BindVarDef(vars=[x: i32])], body=...)
  //
  // prints as:
  //
  //   with std.scope(std.BindVarDef(std.i32)) as x:
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
  bool has_attrs = bind->attrs.has_value() &&
                   AppendAttrsAsKwargs(
                       printer->operator()(*bind->attrs, path->Attr("attrs")).cast<text::ExprAST>(),
                       &kwargs_keys, &kwargs_values);
  return has_attrs ? text::ExprCallKw(CallMnemonic(printer->cfg, bind), std::move(args),
                                      std::move(kwargs_keys), std::move(kwargs_values))
                   : text::ExprCall(CallMnemonic(printer->cfg, bind), std::move(args));
}

Optional<text::ExprAST> PackOptionalValue(List<text::ExprAST> values) {
  // Used by return/yield.  "return" has no expression, "return x" has one,
  // and "return x, y" is represented as a tuple expression.
  if (values.empty()) return {};
  if (values.size() == 1) return values[0];
  return text::TupleAST(std::move(values));
}

text::ExprAST LoadStore(const List<text::ExprAST>& printed_operands, int64_t end_index_offset) {
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

template <typename T>
int64_t OperandCount(const T&) {
  return 1;
}

template <typename T>
int64_t OperandCount(const List<T>& values) {
  return static_cast<int64_t>(values.size());
}

template <typename T>
void AppendOperand(const Function& get_cached, const T& value, List<text::ExprAST>* result) {
  result->push_back(get_cached(value).template cast<text::ExprAST>());
}

template <typename T>
void AppendOperand(const Function& get_cached, const List<T>& values, List<text::ExprAST>* result) {
  for (const T& value : values) {
    result->push_back(get_cached(value).template cast<text::ExprAST>());
  }
}

template <typename... Args>
List<text::ExprAST> OperandList(const Function& get_cached, const Args&... args) {
  List<text::ExprAST> result;
  result.reserve((OperandCount(args) + ... + 0));
  (AppendOperand(get_cached, args, &result), ...);
  return result;
}

template <typename NodeType>
List<text::ExprAST> BinaryOperands(const NodeType& obj, const Function& get_cached) {
  return OperandList(get_cached, obj->a, obj->b);
}

template <typename NodeType>
List<text::ExprAST> ExplicitBinaryOperands(const text::IRPrinter& printer, const NodeType& obj,
                                           const refl::AccessPath& path,
                                           const Function& get_cached) {
  List<text::ExprAST> result;
  result.reserve(3);
  result.push_back(printer->operator()(obj->ty, path->Attr("ty")).template cast<text::ExprAST>());
  List<text::ExprAST> operands = BinaryOperands(obj, get_cached);
  for (text::ExprAST operand : operands) {
    result.push_back(operand);
  }
  return result;
}

List<text::ExprAST> LoadOperands(const Load& load, const Function& get_cached) {
  return OperandList(get_cached, load->lhs, load->indices);
}

template <typename NodeType, int64_t Op>
text::NodeAST ApplyOperationGeneric(const text::IRPrinter&, const NodeType& obj,
                                    const refl::AccessPath&, const Function& get_cached) {
  return text::OperationAST(Op, BinaryOperands(obj, get_cached));
}

template <typename NodeType>
text::NodeAST ApplyMinGeneric(const text::IRPrinter&, const NodeType& obj, const refl::AccessPath&,
                              const Function& get_cached) {
  return text::ExprCall(text::IdAST("min"), BinaryOperands(obj, get_cached));
}

template <typename NodeType>
text::NodeAST ApplyMaxGeneric(const text::IRPrinter&, const NodeType& obj, const refl::AccessPath&,
                              const Function& get_cached) {
  return text::ExprCall(text::IdAST("max"), BinaryOperands(obj, get_cached));
}

text::NodeAST ApplyNotGeneric(const text::IRPrinter&, const Not& obj, const refl::AccessPath&,
                              const Function& get_cached) {
  return text::OperationAST(text::OperationASTObj::kNot,
                            {get_cached(obj->operand).cast<text::ExprAST>()});
}

text::NodeAST ApplyLoadGeneric(const text::IRPrinter&, const Load& obj, const refl::AccessPath&,
                               const Function& get_cached) {
  return LoadStore(LoadOperands(obj, get_cached), /*end_index_offset=*/0);
}

text::NodeAST ApplyCastGeneric(const text::IRPrinter& printer, const Cast& obj,
                               const refl::AccessPath& path, const Function& get_cached) {
  // PrimTy casts prefer dtype-call syntax, e.g. std.Cast(std.i32, x) prints as
  // std.i32(x).  Literal operands stay explicit so dtype-call syntax remains
  // available for typed immediate literals.
  text::ExprAST ty = get_cached(obj->ty).cast<text::ExprAST>();
  bool is_literal =
      obj->value.as<IntImmObj>() != nullptr || obj->value.as<BoolImmObj>() != nullptr ||
      obj->value.as<FloatImmObj>() != nullptr || obj->value.as<StringImmObj>() != nullptr;
  text::ExprAST value =
      is_literal ? printer->operator()(obj->value, path->Attr("value")).cast<text::ExprAST>()
                 : get_cached(obj->value).cast<text::ExprAST>();
  if (obj->ty.as<PrimTyObj>() != nullptr && !is_literal) {
    return text::ExprCall(std::move(ty), {std::move(value)});
  }
  return text::ExprCall(CallMnemonic(printer->cfg, obj), {std::move(ty), std::move(value)});
}

text::NodeAST ApplyBindExprGeneric(const text::IRPrinter& printer, const BindExpr& obj,
                                   const refl::AccessPath& path, const Function& get_cached) {
  // BindExpr sugar is assignment-like.  With vars it prints "x = rhs" or
  // "x, y = rhs"; without vars it degrades to expression-statement "rhs".
  // Attrs wrap the RHS as std.BindExpr(rhs, key=value) before assignment.
  text::ExprAST rhs = get_cached(obj->expr).cast<text::ExprAST>();
  // Literal RHS nodes need their normal printer so non-default immediate types
  // stay explicit, e.g. std.i32(1), while default int64 still prints as 1.
  if (LiteralValueAST(obj->expr).has_value()) {
    rhs = printer->operator()(obj->expr, path->Attr("expr")).cast<text::ExprAST>();
  }
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  if (obj->attrs.has_value() &&
      AppendAttrsAsKwargs(
          printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(), &kwargs_keys,
          &kwargs_values)) {
    rhs = text::ExprCallKw(CallMnemonic(printer->cfg, obj), {rhs}, std::move(kwargs_keys),
                           std::move(kwargs_values));
  }
  if (obj->vars.empty()) {
    return text::ExprStmtAST(std::move(rhs));
  }
  return text::AssignAST(DefineVarTuple(printer, obj->vars), std::move(rhs));
}

text::NodeAST ApplyBindVarDefGeneric(const text::IRPrinter& printer, const BindVarDef& obj,
                                     const refl::AccessPath& path, const Function& get_cached) {
  // Var definitions have no RHS value.  They print as
  // "x = std.BindVarDef(i32)" or "x, y = std.BindVarDef(i32, f32)" so the
  // variable types remain visible at the definition site.
  if (obj->vars.empty()) {
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    if (!obj->attrs.has_value() ||
        !AppendAttrsAsKwargs(
            printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(),
            &kwargs_keys, &kwargs_values)) {
      return text::ExprStmtAST(text::IdAST("pass"));
    }
    return text::ExprStmtAST(text::ExprCallKw(CallMnemonic(printer->cfg, obj), {},
                                              std::move(kwargs_keys), std::move(kwargs_values)));
  }
  List<text::ExprAST> types;
  types.reserve(static_cast<int64_t>(obj->vars.size()));
  refl::AccessPath vars_path = path->Attr("vars");
  int64_t n = static_cast<int64_t>(obj->vars.size());
  for (int64_t i = 0; i < n; ++i) {
    types.push_back(printer->operator()(obj->vars[i]->ty, vars_path->ArrayItem(i)->Attr("ty"))
                        .cast<text::ExprAST>());
  }
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  text::ExprAST rhs =
      obj->attrs.has_value() &&
              AppendAttrsAsKwargs(
                  printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(),
                  &kwargs_keys, &kwargs_values)
          ? text::ExprCallKw(CallMnemonic(printer->cfg, obj), std::move(types),
                             std::move(kwargs_keys), std::move(kwargs_values))
          : text::ExprCall(CallMnemonic(printer->cfg, obj), std::move(types));
  return text::AssignAST(DefineVarTuple(printer, obj->vars), std::move(rhs));
}

text::NodeAST ApplyStoreGeneric(const text::IRPrinter&, const Store& obj, const refl::AccessPath&,
                                const Function& get_cached) {
  // Store operands are [lhs, *indices, rhs].  The generic turns them into
  // indexed assignment, for example [x, i, v] -> "x[i] = v".
  List<text::ExprAST> args = OperandList(get_cached, obj->lhs, obj->indices, obj->rhs);
  return text::AssignAST(LoadStore(args, /*end_index_offset=*/1), args[args.size() - 1]);
}

text::NodeAST ApplyAssertGeneric(const text::IRPrinter&, const Assert& obj, const refl::AccessPath&,
                                 const Function& get_cached) {
  // Attr-free Assert uses Python assert syntax: std.Assert(cond) -> "assert cond".
  // Attr-bearing asserts are handled by TextPrint(Assert) with an explicit call.
  return text::AssertAST(get_cached(obj->cond).cast<text::ExprAST>());
}

text::NodeAST ApplyReturnGeneric(const text::IRPrinter&, const Return& obj, const refl::AccessPath&,
                                 const Function& get_cached) {
  return text::ReturnAST(PackOptionalValue(OperandList(get_cached, obj->exprs)));
}

text::NodeAST ApplyYieldGeneric(const text::IRPrinter&, const Yield_& obj, const refl::AccessPath&,
                                const Function& get_cached) {
  return text::ExprStmtAST(text::YieldAST(PackOptionalValue(OperandList(get_cached, obj->exprs))));
}

text::NodeAST ApplyBreakGeneric(const text::IRPrinter&, const Break&, const refl::AccessPath&,
                                const Function&) {
  return text::ExprStmtAST(text::IdAST("break"));
}

text::NodeAST ApplyContinueGeneric(const text::IRPrinter&, const Continue&, const refl::AccessPath&,
                                   const Function&) {
  return text::ExprStmtAST(text::IdAST("continue"));
}

template <typename NodeType, typename Fallback>
text::NodeAST ApplyTextGenericOrFallback(const NodeType& obj, const refl::AccessPath& path,
                                         const CachedPrinter& cache, Fallback fallback) {
  // Shared path for simple expression/statement printers.  The generic path
  // receives the same printer, typed node, access path, and cached-expression
  // callback shape as a registered generic handler, all derived from the
  // CachedPrinter that already evaluated the operands.  The fallback lambda
  // captures the surrounding TextPrint state, so it can preserve syntax that is
  // not representable as a flat mnemonic call, such as Bind attrs.
  //
  // Generic lookup is gated by the cached operands: if all non-literal operands
  // share one dialect, use that dialect; if every operand is literal, use the
  // current dialect from the printer stack.  Otherwise, keep the explicit
  // mnemonic spelling via the fallback.
  GenericsRegistry* registry = GenericsRegistry::Global();
  text::IRPrinter printer = cache.printer();
  Array<String> dialect_mnemonic = DialectMnemonic(obj->type_index());
  Optional<String> common_dialect = cache.CommonDialect();
  if (dialect_mnemonic.size() == 3 && common_dialect.has_value()) {
    Function fn = registry->Lookup(common_dialect.value(), dialect_mnemonic[2]);
    if (fn != nullptr) {
      return fn(printer, obj, path, cache.GetCachedFunction()).template cast<text::NodeAST>();
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
  List<text::ExprAST> decorators{CallCustomMnemonic(printer->cfg, obj, "module", true)};
  return text::ClassAST(text::IdAST("MyModule"), {}, std::move(decorators), std::move(stmts));
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
  bool has_attrs = obj->attrs.has_value() &&
                   AppendAttrsAsKwargs(
                       printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(),
                       &decorator_keys, &decorator_values);
  List<text::ExprAST> decorators;
  if (!has_attrs) {
    decorators.push_back(CallCustomMnemonic(printer->cfg, obj, "func", true));
  } else {
    decorators.push_back(text::ExprCallKw(CallCustomMnemonic(printer->cfg, obj, "func", true), {},
                                          std::move(decorator_keys), std::move(decorator_values)));
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
  return CallMnemonic(printer->cfg, obj);
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
  return text::IndexAST(CallMnemonic(printer->cfg, obj), std::move(fields));
}

text::NodeAST TextPrint(const TensorTy& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  PrimTy dtype(obj->dtype);
  return text::IndexAST(printer->operator()(dtype, path->Attr("dtype")).cast<text::ExprAST>(),
                        PrintExprList(printer, obj->shape, path->Attr("shape")));
}

bool IsDefaultIntLiteralType(const Ty& ty) {
  const PrimTyObj* prim_ty = ty.as<PrimTyObj>();
  return prim_ty != nullptr && prim_ty->dtype == kDefaultIntLiteralType;
}

bool IsDefaultFloatLiteralType(const Ty& ty) {
  const PrimTyObj* prim_ty = ty.as<PrimTyObj>();
  return prim_ty != nullptr && prim_ty->dtype == kDefaultFloatLiteralType;
}

bool IsDefaultBoolLiteralType(const Ty& ty) {
  const PrimTyObj* prim_ty = ty.as<PrimTyObj>();
  return prim_ty != nullptr && prim_ty->dtype == kDefaultBoolLiteralType;
}

text::NodeAST TextPrint(const BoolImm& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  text::ExprAST value = text::LiteralAST::Bool(obj->value);
  if (obj->ty.as<PrimTyObj>() != nullptr && !IsDefaultBoolLiteralType(obj->ty)) {
    text::ExprAST ty = printer->operator()(obj->ty, path->Attr("ty")).cast<text::ExprAST>();
    return text::ExprCall(std::move(ty), {std::move(value)});
  }
  return value;
}

text::NodeAST TextPrint(const IntImm& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  text::ExprAST value = text::LiteralAST::Int(obj->value);
  if (obj->ty.as<PrimTyObj>() != nullptr && !IsDefaultIntLiteralType(obj->ty)) {
    text::ExprAST ty = printer->operator()(obj->ty, path->Attr("ty")).cast<text::ExprAST>();
    return text::ExprCall(std::move(ty), {std::move(value)});
  }
  return value;
}

text::NodeAST TextPrint(const FloatImm& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  text::ExprAST value = text::LiteralAST::Float(obj->value);
  if (obj->ty.as<PrimTyObj>() != nullptr && !IsDefaultFloatLiteralType(obj->ty)) {
    text::ExprAST ty = printer->operator()(obj->ty, path->Attr("ty")).cast<text::ExprAST>();
    return text::ExprCall(std::move(ty), {std::move(value)});
  }
  return value;
}

text::NodeAST TextPrint(const StringImm& obj, const text::IRPrinter&, const refl::AccessPath&) {
  return text::LiteralAST::Str(obj->value);
}

#define TVM_FFI_STD_BINARY_TEXT_PRINT(TypeName)                                   \
  text::NodeAST TextPrint(const TypeName& obj, const text::IRPrinter& printer,    \
                          const refl::AccessPath& path) {                         \
    CachedPrinter cache(printer);                                                 \
    cache.RunCache(obj->a, path->Attr("a"));                                      \
    cache.RunCache(obj->b, path->Attr("b"));                                      \
    return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {  \
      return text::ExprCall(                                                      \
          CallMnemonic(printer->cfg, obj),                                        \
          ExplicitBinaryOperands(printer, obj, path, cache.GetCachedFunction())); \
    });                                                                           \
  }

TVM_FFI_STD_BINARY_TEXT_PRINT(Add)
TVM_FFI_STD_BINARY_TEXT_PRINT(Sub)
TVM_FFI_STD_BINARY_TEXT_PRINT(Mul)
TVM_FFI_STD_BINARY_TEXT_PRINT(CDiv)
TVM_FFI_STD_BINARY_TEXT_PRINT(FloorDiv)
TVM_FFI_STD_BINARY_TEXT_PRINT(FloorMod)
TVM_FFI_STD_BINARY_TEXT_PRINT(CMod)
TVM_FFI_STD_BINARY_TEXT_PRINT(Pow)
TVM_FFI_STD_BINARY_TEXT_PRINT(LShift)
TVM_FFI_STD_BINARY_TEXT_PRINT(RShift)
TVM_FFI_STD_BINARY_TEXT_PRINT(Xor)
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
  cache.RunCache(obj->operand, path->Attr("operand"));
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprCall(CallMnemonic(printer->cfg, obj),
                          {printer->operator()(obj->ty, path->Attr("ty")).cast<text::ExprAST>(),
                           cache.ExprFromCache(obj->operand)});
  });
}

text::NodeAST TextPrint(const Load& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  cache.RunCache(obj->lhs, path->Attr("lhs"));
  int64_t n = static_cast<int64_t>(obj->indices.size());
  refl::AccessPath indices_path = path->Attr("indices");
  for (int64_t i = 0; i < n; ++i) {
    cache.RunCache(obj->indices[i], indices_path->ArrayItem(i));
  }
  Function get_cached = cache.GetCachedFunction();
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    List<text::ExprAST> indices;
    indices.reserve(n);
    for (int64_t i = 0; i < n; ++i) {
      indices.push_back(get_cached(obj->indices[i]).cast<text::ExprAST>());
    }
    return text::ExprCall(
        CallMnemonic(printer->cfg, obj),
        {printer->operator()(obj->ty, path->Attr("ty")).cast<text::ExprAST>(),
         get_cached(obj->lhs).cast<text::ExprAST>(), text::ListAST(std::move(indices))});
  });
}

text::NodeAST TextPrint(const Cast& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  cache.RunCache(obj->ty, path->Attr("ty"));
  cache.RunCache(obj->value, path->Attr("value"));
  Function get_cached = cache.GetCachedFunction();
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprCall(
        CallMnemonic(printer->cfg, obj),
        {get_cached(obj->ty).cast<text::ExprAST>(), get_cached(obj->value).cast<text::ExprAST>()});
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
  text::ExprAST ty = printer->operator()(obj->ty, path->Attr("ty")).cast<text::ExprAST>();
  List<text::ExprAST> args = PrintExprList(printer, obj->args, path->Attr("args"));
  List<text::ExprAST> call_args{std::move(ty), std::move(callee)};
  call_args.reserve(args.size() + 2);
  for (text::ExprAST arg : args) {
    call_args.push_back(arg);
  }
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  if (obj->attr.has_value() &&
      AppendAttrsAsKwargs(printer->operator()(*obj->attr, path->Attr("attr")).cast<text::ExprAST>(),
                          &kwargs_keys, &kwargs_values)) {
    return text::ExprCallKw(CallMnemonic(printer->cfg, obj), std::move(call_args),
                            std::move(kwargs_keys), std::move(kwargs_values));
  }
  return text::ExprCall(CallMnemonic(printer->cfg, obj), std::move(call_args));
}

text::NodeAST TextPrint(const IfStmt& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  // TODO(junrushao): If IfStmt is not treated as a text generic, print the explicit
  // mnemonic form instead of native Python if syntax.
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
  for (const Bind& bind : obj->binds) {
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
  if (obj->attrs.has_value()) {
    AppendAttrsAsKwargs(printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(),
                        &range_kwarg_keys, &range_kwarg_values);
  }
  text::ExprAST rhs =
      range_kwarg_keys.empty()
          ? text::ExprCall(CallCustomMnemonic(printer->cfg, obj, "range"), std::move(range_args))
          : text::ExprCallKw(CallCustomMnemonic(printer->cfg, obj, "range"), std::move(range_args),
                             std::move(range_kwarg_keys), std::move(range_kwarg_values));
  return text::ForAST(std::move(lhs), std::move(rhs),
                      PrintStmtList(printer, obj->body, path->Attr("body")));
}

text::NodeAST TextPrint(const While& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  DialectFrame dialect_frame(printer, obj);
  List<String> while_kwarg_keys;
  List<text::ExprAST> while_kwarg_values;
  bool has_attrs = obj->attrs.has_value() &&
                   AppendAttrsAsKwargs(
                       printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(),
                       &while_kwarg_keys, &while_kwarg_values);
  if (obj->binds.empty() && !has_attrs) {
    return text::WhileAST(printer->operator()(obj->cond, path->Attr("cond")).cast<text::ExprAST>(),
                          PrintStmtList(printer, obj->body, path->Attr("body")));
  }
  List<text::ExprAST> while_args{
      printer->operator()(obj->cond, path->Attr("cond")).cast<text::ExprAST>()};
  refl::AccessPath binds_path = path->Attr("binds");
  int64_t n = static_cast<int64_t>(obj->binds.size());
  for (int64_t i = 0; i < n; ++i) {
    while_args.push_back(BindInitializerCall(obj->binds[i], printer, binds_path->ArrayItem(i)));
  }
  text::ExprAST rhs = while_kwarg_keys.empty()
                          ? text::ExprCall(CallCustomMnemonic(printer->cfg, obj, "while_", true),
                                           std::move(while_args))
                          : text::ExprCallKw(CallCustomMnemonic(printer->cfg, obj, "while_", true),
                                             std::move(while_args), std::move(while_kwarg_keys),
                                             std::move(while_kwarg_values));
  Optional<text::ExprAST> lhs = DefineScopeVarsAsWithTargets(printer, obj->binds);
  return text::WithAST(std::move(lhs), std::move(rhs),
                       PrintStmtList(printer, obj->body, path->Attr("body")));
}

text::NodeAST TextPrint(const Scope& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  DialectFrame dialect_frame(printer, obj);
  List<String> scope_kwarg_keys;
  List<text::ExprAST> scope_kwarg_values;
  bool has_attrs = obj->attrs.has_value() &&
                   AppendAttrsAsKwargs(
                       printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(),
                       &scope_kwarg_keys, &scope_kwarg_values);
  if (obj->binds.empty() && !has_attrs) {
    return text::StmtBlockAST(PrintStmtList(printer, obj->body, path->Attr("body")));
  }
  List<text::ExprAST> scope_args;
  int64_t n = static_cast<int64_t>(obj->binds.size());
  scope_args.reserve(n);
  refl::AccessPath binds_path = path->Attr("binds");
  for (int64_t i = 0; i < n; ++i) {
    scope_args.push_back(BindInitializerCall(obj->binds[i], printer, binds_path->ArrayItem(i)));
  }
  text::ExprAST rhs = scope_kwarg_keys.empty()
                          ? text::ExprCall(CallCustomMnemonic(printer->cfg, obj, "scope", true),
                                           std::move(scope_args))
                          : text::ExprCallKw(CallCustomMnemonic(printer->cfg, obj, "scope", true),
                                             std::move(scope_args), std::move(scope_kwarg_keys),
                                             std::move(scope_kwarg_values));
  Optional<text::ExprAST> lhs = DefineScopeVarsAsWithTargets(printer, obj->binds);
  return text::WithAST(std::move(lhs), std::move(rhs),
                       PrintStmtList(printer, obj->body, path->Attr("body")));
}

text::NodeAST TextPrint(const BindExpr& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  int64_t num_vars = static_cast<int64_t>(obj->vars.size());
  refl::AccessPath vars_path = path->Attr("vars");
  for (int64_t i = 0; i < num_vars; ++i) {
    cache.RunCache(obj->vars[i], vars_path->ArrayItem(i));
  }
  cache.RunCache(obj->expr, path->Attr("expr"));
  Function get_cached = cache.GetCachedFunction();
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    List<text::ExprAST> args = OperandList(get_cached, obj->vars);
    text::ExprAST expr =
        LiteralValueAST(obj->expr).has_value()
            ? printer->operator()(obj->expr, path->Attr("expr")).cast<text::ExprAST>()
            : get_cached(obj->expr).cast<text::ExprAST>();
    args.push_back(expr);
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    text::ExprAST call =
        obj->attrs.has_value() &&
                AppendAttrsAsKwargs(
                    printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(),
                    &kwargs_keys, &kwargs_values)
            ? text::ExprCallKw(CallMnemonic(printer->cfg, obj), std::move(args),
                               std::move(kwargs_keys), std::move(kwargs_values))
            : text::ExprCall(CallMnemonic(printer->cfg, obj), std::move(args));
    return text::ExprStmtAST(std::move(call));
  });
}

text::NodeAST TextPrint(const BindVarDef& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  int64_t num_vars = static_cast<int64_t>(obj->vars.size());
  refl::AccessPath vars_path = path->Attr("vars");
  for (int64_t i = 0; i < num_vars; ++i) {
    cache.RunCache(obj->vars[i], vars_path->ArrayItem(i));
  }
  Function get_cached = cache.GetCachedFunction();
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    List<text::ExprAST> args = OperandList(get_cached, obj->vars);
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    text::ExprAST call =
        obj->attrs.has_value() &&
                AppendAttrsAsKwargs(
                    printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(),
                    &kwargs_keys, &kwargs_values)
            ? text::ExprCallKw(CallMnemonic(printer->cfg, obj), std::move(args),
                               std::move(kwargs_keys), std::move(kwargs_values))
            : text::ExprCall(CallMnemonic(printer->cfg, obj), std::move(args));
    return text::ExprStmtAST(std::move(call));
  });
}

text::NodeAST TextPrint(const Store& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  cache.RunCache(obj->lhs, path->Attr("lhs"));
  int64_t n = static_cast<int64_t>(obj->indices.size());
  refl::AccessPath indices_path = path->Attr("indices");
  for (int64_t i = 0; i < n; ++i) {
    cache.RunCache(obj->indices[i], indices_path->ArrayItem(i));
  }
  cache.RunCache(obj->rhs, path->Attr("rhs"));
  Function get_cached = cache.GetCachedFunction();
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    List<text::ExprAST> args;
    args.reserve(n + 1);
    args.push_back(get_cached(obj->lhs).cast<text::ExprAST>());
    for (int64_t i = 0; i < n; ++i) {
      args.push_back(get_cached(obj->indices[i]).cast<text::ExprAST>());
    }
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    kwargs_keys.push_back("rhs");
    kwargs_values.push_back(get_cached(obj->rhs).cast<text::ExprAST>());
    AppendAttrsAsKwargsOrKeyword(printer, obj->attrs, path->Attr("attrs"), &kwargs_keys,
                                 &kwargs_values);
    return text::ExprStmtAST(text::ExprCallKw(CallMnemonic(printer->cfg, obj), std::move(args),
                                              std::move(kwargs_keys), std::move(kwargs_values)));
  });
}

text::NodeAST TextPrint(const Assert& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  cache.RunCache(obj->cond, path->Attr("cond"));
  Function get_cached = cache.GetCachedFunction();
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  if (obj->attrs.has_value()) {
    bool has_attrs = AppendAttrsAsKwargs(
        printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(), &kwargs_keys,
        &kwargs_values);
    if (has_attrs) {
      return text::ExprStmtAST(text::ExprCallKw(CallMnemonic(printer->cfg, obj),
                                                {get_cached(obj->cond).cast<text::ExprAST>()},
                                                std::move(kwargs_keys), std::move(kwargs_values)));
    }
  }
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(text::ExprCall(CallMnemonic(printer->cfg, obj),
                                            {get_cached(obj->cond).cast<text::ExprAST>()}));
  });
}

text::NodeAST TextPrint(const Return& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  refl::AccessPath exprs_path = path->Attr("exprs");
  int64_t num_exprs = static_cast<int64_t>(obj->exprs.size());
  for (int64_t i = 0; i < num_exprs; ++i) {
    cache.RunCache(obj->exprs[i], exprs_path->ArrayItem(i));
  }
  Function get_cached = cache.GetCachedFunction();
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(
        text::ExprCall(CallMnemonic(printer->cfg, obj), OperandList(get_cached, obj->exprs)));
  });
}

text::NodeAST TextPrint(const Yield_& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  refl::AccessPath exprs_path = path->Attr("exprs");
  int64_t num_exprs = static_cast<int64_t>(obj->exprs.size());
  for (int64_t i = 0; i < num_exprs; ++i) {
    cache.RunCache(obj->exprs[i], exprs_path->ArrayItem(i));
  }
  Function get_cached = cache.GetCachedFunction();
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(
        text::ExprCall(CallMnemonic(printer->cfg, obj), OperandList(get_cached, obj->exprs)));
  });
}

text::NodeAST TextPrint(const Break& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  if (obj->attrs.has_value()) {
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    bool has_attrs = AppendAttrsAsKwargs(
        printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(), &kwargs_keys,
        &kwargs_values);
    if (has_attrs) {
      return text::ExprStmtAST(text::ExprCallKw(CallMnemonic(printer->cfg, obj), {},
                                                std::move(kwargs_keys), std::move(kwargs_values)));
    }
  }
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(text::ExprCall(CallMnemonic(printer->cfg, obj), {}));
  });
}

text::NodeAST TextPrint(const Continue& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  if (obj->attrs.has_value()) {
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    bool has_attrs = AppendAttrsAsKwargs(
        printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(), &kwargs_keys,
        &kwargs_values);
    if (has_attrs) {
      return text::ExprStmtAST(text::ExprCallKw(CallMnemonic(printer->cfg, obj), {},
                                                std::move(kwargs_keys), std::move(kwargs_values)));
    }
  }
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprStmtAST(text::ExprCall(CallMnemonic(printer->cfg, obj), {}));
  });
}

text::NodeAST TextPrint(const DictAttrs& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  std::vector<String> sorted_keys;
  sorted_keys.reserve(obj->values.size());
  for (const auto& kv : obj->values) {
    sorted_keys.push_back(kv.first);
  }
  std::sort(sorted_keys.begin(), sorted_keys.end());

  bool can_print_as_kwargs = true;
  for (const String& key : sorted_keys) {
    if (!text::IsPythonIdentifier(key.data(), key.size()) ||
        text::IsPythonKeyword(key.data(), key.size())) {
      can_print_as_kwargs = false;
      break;
    }
  }

  List<text::ExprAST> values;
  values.reserve(static_cast<int64_t>(sorted_keys.size()));
  refl::AccessPath values_path = path->Attr("values");
  int64_t n = static_cast<int64_t>(sorted_keys.size());
  if (can_print_as_kwargs) {
    List<String> kwargs_keys;
    kwargs_keys.reserve(n);
    for (int64_t i = 0; i < n; ++i) {
      const String& key = sorted_keys[i];
      kwargs_keys.push_back(key);
      values.push_back(
          printer->operator()(obj->values[key], values_path->MapItem(key)).cast<text::ExprAST>());
    }
    return text::CallAST(CallMnemonic(printer->cfg, obj), {}, std::move(kwargs_keys),
                         std::move(values));
  }

  List<text::ExprAST> keys;
  keys.reserve(n);
  for (int64_t i = 0; i < n; ++i) {
    const String& key = sorted_keys[i];
    keys.push_back(text::LiteralAST::Str(key));
    values.push_back(
        printer->operator()(obj->values[key], values_path->MapItem(key)).cast<text::ExprAST>());
  }
  return text::CallAST(CallMnemonic(printer->cfg, obj),
                       {text::DictAST(std::move(keys), std::move(values))}, {}, {});
}

// NOLINTEND(bugprone-misplaced-widening-cast,bugprone-narrowing-conversions)

}  // namespace

TVM_FFI_STATIC_INIT_BLOCK() {
  GenericsRegistry* registry = GenericsRegistry::Global();
  registry->Register("std", "__add__", ApplyOperationGeneric<Add, text::OperationASTObj::kAdd>);
  registry->Register("std", "__sub__", ApplyOperationGeneric<Sub, text::OperationASTObj::kSub>);
  registry->Register("std", "__mul__", ApplyOperationGeneric<Mul, text::OperationASTObj::kMult>);
  registry->Register("std", "__truediv__",
                     ApplyOperationGeneric<CDiv, text::OperationASTObj::kDiv>);
  registry->Register("std", "__floordiv__",
                     ApplyOperationGeneric<FloorDiv, text::OperationASTObj::kFloorDiv>);
  registry->Register("std", "__mod__",
                     ApplyOperationGeneric<FloorMod, text::OperationASTObj::kMod>);
  registry->Register("std", "__pow__", ApplyOperationGeneric<Pow, text::OperationASTObj::kPow>);
  registry->Register("std", "__lshift__",
                     ApplyOperationGeneric<LShift, text::OperationASTObj::kLShift>);
  registry->Register("std", "__rshift__",
                     ApplyOperationGeneric<RShift, text::OperationASTObj::kRShift>);
  registry->Register("std", "__xor__", ApplyOperationGeneric<Xor, text::OperationASTObj::kBitXor>);
  registry->Register("std", "min", ApplyMinGeneric<Min>);
  registry->Register("std", "max", ApplyMaxGeneric<Max>);
  registry->Register("std", "__eq__", ApplyOperationGeneric<Eq, text::OperationASTObj::kEq>);
  registry->Register("std", "__ne__", ApplyOperationGeneric<Ne, text::OperationASTObj::kNotEq>);
  registry->Register("std", "__le__", ApplyOperationGeneric<Le, text::OperationASTObj::kLtE>);
  registry->Register("std", "__ge__", ApplyOperationGeneric<Ge, text::OperationASTObj::kGtE>);
  registry->Register("std", "__gt__", ApplyOperationGeneric<Gt, text::OperationASTObj::kGt>);
  registry->Register("std", "__lt__", ApplyOperationGeneric<Lt, text::OperationASTObj::kLt>);
  registry->Register("std", "__and__", ApplyOperationGeneric<And, text::OperationASTObj::kAnd>);
  registry->Register("std", "__or__", ApplyOperationGeneric<Or, text::OperationASTObj::kOr>);
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
  TVM_FFI_STD_OBJECT_DEF(TupleTypeObj, TupleType, "Tuple").def_rw("fields", &TupleTypeObj::fields);
  TVM_FFI_STD_OBJECT_DEF(TensorTyObj, TensorTy, "Tensor")
      .def_rw("shape", &TensorTyObj::shape)
      .def_rw("dtype", &TensorTyObj::dtype);
  TVM_FFI_STD_OBJECT_DEF(BoolImmObj, BoolImm, "BoolImm").def_rw("value", &BoolImmObj::value);
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
  TVM_FFI_STD_DEF_BINARY(CDiv, "__truediv__");
  TVM_FFI_STD_DEF_BINARY(FloorDiv, "__floordiv__");
  TVM_FFI_STD_DEF_BINARY(FloorMod, "__mod__");
  TVM_FFI_STD_OBJECT_DEF(CModObj, CMod, "CMod").def_rw("a", &CModObj::a).def_rw("b", &CModObj::b);
  TVM_FFI_STD_DEF_BINARY(Pow, "__pow__");
  TVM_FFI_STD_DEF_BINARY(LShift, "__lshift__");
  TVM_FFI_STD_DEF_BINARY(RShift, "__rshift__");
  TVM_FFI_STD_DEF_BINARY(Xor, "__xor__");
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
      .def_rw("lhs", &LoadObj::lhs)
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
      .def_rw("vars", &BindObj::vars, refl::AttachFieldFlag::SEqHashDefRecursive());
  TVM_FFI_STD_OBJECT_DEF_GENERIC(BindExprObj, BindExpr, "BindExpr", "__bind_expr__")
      .def_rw("expr", &BindExprObj::expr);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(BindVarDefObj, BindVarDef, "BindVarDef", "__bind_var_def__");
  TVM_FFI_STD_OBJECT_DEF(ScopeObj, Scope, "Scope")
      .def_rw("binds", &ScopeObj::binds, refl::AttachFieldFlag::SEqHashDefRecursive())
      .def_rw("body", &ScopeObj::body);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(ForObj, For, "For", "__for__").def_rw("range_", &ForObj::range_);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(WhileObj, While, "While", "__while__")
      .def_rw("cond", &WhileObj::cond);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(StoreObj, Store, "Store", "__store__")
      .def_rw("lhs", &StoreObj::lhs)
      .def_rw("indices", &StoreObj::indices)
      .def_rw("rhs", &StoreObj::rhs);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(AssertObj, Assert, "Assert", "__assert__")
      .def_rw("cond", &AssertObj::cond);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(ReturnObj, Return, "Return", "__return__")
      .def_rw("exprs", &ReturnObj::exprs);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(YieldObj, Yield_, "Yield", "__yield__")
      .def_rw("exprs", &YieldObj::exprs);
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
