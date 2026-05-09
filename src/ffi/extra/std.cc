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
#include <tvm/ffi/extra/json.h>
#include <tvm/ffi/extra/pyast.h>
#include <tvm/ffi/extra/std.h>
#include <tvm/ffi/function.h>
#include <tvm/ffi/reflection/accessor.h>
#include <tvm/ffi/reflection/creator.h>
#include <tvm/ffi/reflection/registry.h>

#include <algorithm>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
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
                                 String printed_name) {
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
  return text::IdAST(std::move(printed_name));
}

class ResolvedPrintInfo {
 public:
  ResolvedPrintInfo(ObjectRef source_obj, int32_t std_kind_type_index)
      : source_obj_(std::move(source_obj)), std_kind_type_index_(std_kind_type_index) {
    this->Collect();
  }

  Any ReadStdField(const String& std_field_name) const {
    const TVMFFIFieldInfo* source_field = this->ResolveStdField(std_field_name);
    return refl::FieldGetter(source_field)(this->source_obj_);
  }

  ObjectRef ReadStdFieldObject(const String& std_field_name) const {
    return this->ReadStdField(std_field_name).cast<ObjectRef>();
  }

  Optional<Any> TryReadStdField(const String& std_field_name) const {
    const TVMFFIFieldInfo* source_field = this->TryResolveStdField(std_field_name);
    if (source_field == nullptr) {
      return {};
    }
    return refl::FieldGetter(source_field)(this->source_obj_);
  }

  refl::AccessPath PathForStdField(const refl::AccessPath& object_path,
                                   const String& std_field_name) const {
    const TVMFFIFieldInfo* source_field = this->ResolveStdField(std_field_name);
    return object_path->Attr(String(source_field->name));
  }

  refl::AccessPath PathForField(const refl::AccessPath& object_path,
                                const TVMFFIFieldInfo* field) const {
    return object_path->Attr(String(field->name));
  }

  struct PrintPart {
    String kind;
    String target;
    int64_t order = 0;
    String render;
    const TVMFFIFieldInfo* field = nullptr;
    int64_t ordinal = 0;
  };

  std::vector<PrintPart> Parts(const String& kind, const String& target) const {
    std::vector<PrintPart> result;
    for (const PrintPart& part : this->print_parts_) {
      if (part.kind == kind && part.target == target) {
        result.push_back(part);
      }
    }
    std::stable_sort(result.begin(), result.end(), [](const PrintPart& lhs, const PrintPart& rhs) {
      if (lhs.order != rhs.order) {
        return lhs.order < rhs.order;
      }
      return lhs.ordinal < rhs.ordinal;
    });
    return result;
  }

  Any ReadField(const String& field_name) const {
    auto it = this->source_fields_by_name_.find(field_name);
    if (it == this->source_fields_by_name_.end()) {
      TVM_FFI_THROW(ValueError) << "Type `" << this->source_obj_->GetTypeKey()
                                << "` has no reflected field `" << field_name << "`";
    }
    return refl::FieldGetter(it->second)(this->source_obj_);
  }

  Function FindMethod(const String& method_name) const {
    auto it = this->methods_by_name_.find(method_name);
    if (it == this->methods_by_name_.end()) {
      TVM_FFI_THROW(ValueError) << "Type `" << this->source_obj_->GetTypeKey()
                                << "` has no reflected method `" << method_name << "`";
    }
    return it->second;
  }

  const ObjectRef& source_obj() const { return source_obj_; }

  bool HasAnyPrintPart() const { return !this->print_parts_.empty(); }

 private:
  static std::optional<json::Object> ParseMetadata(const TVMFFIByteArray& metadata,
                                                   const String& context) {
    if (metadata.size == 0) {
      return {};
    }
    String parse_error;
    String metadata_json(metadata.data, metadata.size);
    Any parsed = json::Parse(metadata_json, &parse_error);
    if (!parse_error.empty()) {
      TVM_FFI_THROW(ValueError) << "Invalid metadata JSON for " << context << ": " << parse_error;
    }
    std::optional<json::Object> obj = parsed.as<json::Object>();
    if (!obj.has_value()) {
      TVM_FFI_THROW(ValueError) << "Metadata for " << context << " must be a JSON object";
    }
    return obj;
  }

  static bool HasKey(const json::Object& obj, const String& key) { return obj.count(key) != 0; }

  static std::optional<String> GetString(const json::Object& obj, const String& key) {
    if (!HasKey(obj, key)) {
      return {};
    }
    std::optional<String> value = obj[key].as<String>();
    if (!value.has_value()) {
      TVM_FFI_THROW(ValueError) << "Metadata key `" << key << "` must be a string";
    }
    return value;
  }

  static int64_t GetIntOrDefault(const json::Object& obj, const String& key,
                                 int64_t default_value) {
    if (!HasKey(obj, key)) {
      return default_value;
    }
    std::optional<int64_t> value = obj[key].as<int64_t>();
    if (!value.has_value()) {
      TVM_FFI_THROW(ValueError) << "Metadata key `" << key << "` must be an integer";
    }
    return value.value();
  }

  void AddRole(const json::Object& role, const TVMFFIFieldInfo* field) {
    std::optional<String> kind = GetString(role, "kind");
    if (!kind.has_value()) {
      TVM_FFI_THROW(ValueError) << "Print role metadata must define string key `kind`";
    }
    if (kind.value() == "ignore") {
      if (field != nullptr) {
        this->consumed_fields_.insert(String(field->name));
      }
      return;
    }

    std::optional<String> target = GetString(role, "target");
    if (!target.has_value()) {
      std::optional<String> slot = GetString(role, "slot");
      target = slot.has_value() ? slot : String("");
    }

    PrintPart part;
    part.kind = kind.value();
    part.target = target.value();
    part.order = GetIntOrDefault(role, "order", 0);
    if (std::optional<String> render = GetString(role, "render")) {
      part.render = render.value();
    }
    part.field = field;
    part.ordinal = static_cast<int64_t>(this->print_parts_.size());
    if (field != nullptr) {
      this->consumed_fields_.insert(String(field->name));
    }
    this->print_parts_.push_back(std::move(part));
  }

  void AddRolesFromValue(const Any& value, const TVMFFIFieldInfo* field) {
    if (std::optional<json::Object> role = value.as<json::Object>()) {
      this->AddRole(role.value(), field);
      return;
    }
    if (std::optional<json::Array> roles = value.as<json::Array>()) {
      for (const Any& item : roles.value()) {
        std::optional<json::Object> role = item.as<json::Object>();
        if (!role.has_value()) {
          TVM_FFI_THROW(ValueError) << "Print role arrays must contain JSON objects";
        }
        this->AddRole(role.value(), field);
      }
      return;
    }
    TVM_FFI_THROW(ValueError) << "Print metadata must be a JSON object or array of objects";
  }

  void CollectField(const TVMFFIFieldInfo* field) {
    String field_name(field->name);
    this->source_fields_by_name_[field_name] = field;

    std::optional<json::Object> metadata =
        ParseMetadata(field->metadata, String("field `") + field_name + "`");
    if (!metadata.has_value()) {
      return;
    }

    if (std::optional<String> std_field = GetString(metadata.value(), "std_field")) {
      this->std_field_bindings_[std_field.value()].push_back(field);
      this->consumed_fields_.insert(field_name);
    }
    String print_key("print");
    if (HasKey(metadata.value(), print_key)) {
      this->AddRolesFromValue(metadata.value()[print_key], field);
    }
  }

  void CollectMethod(const TVMFFIMethodInfo* method) {
    String method_name(method->name);
    Function method_fn = AnyView::CopyFromTVMFFIAny(method->method).cast<Function>();
    this->methods_by_name_[method_name] = method_fn;
  }

  void ValidateConsumedFields() const {
    for (const auto& kv : this->source_fields_by_name_) {
      const String& field_name = kv.first;
      if (this->consumed_fields_.count(field_name) != 0) {
        continue;
      }
      if (this->std_kind_field_names_.count(field_name) != 0) {
        continue;
      }
      TVM_FFI_THROW(ValueError) << "Field `" << field_name << "` in `"
                                << this->source_obj_->GetTypeKey()
                                << "` is not consumed by std field resolution or print roles";
    }
  }

  void Collect() {
    const TVMFFITypeInfo* std_kind_info = TVMFFIGetTypeInfo(this->std_kind_type_index_);
    refl::ForEachFieldInfo(std_kind_info, [&](const TVMFFIFieldInfo* field) {
      this->std_kind_field_names_.insert(String(field->name));
    });

    const TVMFFITypeInfo* source_info = TVMFFIGetTypeInfo(this->source_obj_->type_index());
    refl::ForEachFieldInfo(source_info,
                           [&](const TVMFFIFieldInfo* field) { this->CollectField(field); });
    for (int32_t i = 1; i < source_info->type_depth; ++i) {
      const TVMFFITypeInfo* ancestor_info = source_info->type_ancestors[i];
      for (int32_t j = 0; j < ancestor_info->num_methods; ++j) {
        this->CollectMethod(ancestor_info->methods + j);
      }
    }
    for (int32_t i = 0; i < source_info->num_methods; ++i) {
      this->CollectMethod(source_info->methods + i);
    }

    this->ValidateConsumedFields();
  }

  const TVMFFIFieldInfo* TryResolveStdField(const String& std_field_name) const {
    auto projected = this->std_field_bindings_.find(std_field_name);
    if (projected != this->std_field_bindings_.end()) {
      const std::vector<const TVMFFIFieldInfo*>& fields = projected->second;
      if (fields.size() != 1) {
        TVM_FFI_THROW(ValueError) << "Multiple fields in `" << this->source_obj_->GetTypeKey()
                                  << "` resolve std field `" << std_field_name << "`";
      }
      return fields[0];
    }

    auto same_name = this->source_fields_by_name_.find(std_field_name);
    if (same_name != this->source_fields_by_name_.end() &&
        this->std_kind_field_names_.count(std_field_name) != 0) {
      return same_name->second;
    }
    return nullptr;
  }

  const TVMFFIFieldInfo* ResolveStdField(const String& std_field_name) const {
    const TVMFFIFieldInfo* field = this->TryResolveStdField(std_field_name);
    if (field == nullptr) {
      TVM_FFI_THROW(ValueError) << "No field in `" << this->source_obj_->GetTypeKey()
                                << "` resolves std field `" << std_field_name << "` for std kind `"
                                << TypeIndexToTypeKey(this->std_kind_type_index_) << "`";
    }
    return field;
  }

  ObjectRef source_obj_;
  int32_t std_kind_type_index_;
  std::unordered_map<String, const TVMFFIFieldInfo*> source_fields_by_name_;
  std::unordered_map<String, Function> methods_by_name_;
  std::unordered_map<String, std::vector<const TVMFFIFieldInfo*>> std_field_bindings_;
  std::unordered_set<String> std_kind_field_names_;
  std::unordered_set<String> consumed_fields_;
  std::vector<PrintPart> print_parts_;
};

class DialectFrame {
 public:
  DialectFrame(const text::IRPrinter& printer, const ObjectRef& obj) : printer_(printer.get()) {
    printer_->dialects.push_back(Dialect(obj.type_index()));
  }

  ~DialectFrame() { printer_->dialects.pop_back(); }  // NOLINT(modernize-use-equals-default)

 private:
  text::IRPrinterObj* printer_;
};

class CachedPrinter {
 public:
  explicit CachedPrinter(text::IRPrinter printer) : printer_(std::move(printer)) {}

  Any RunCache(const ObjectRef& obj, const refl::AccessPath& path) {
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

bool AppendAttrsAsKwargs(const text::ExprAST& attrs_ast, List<String>* kwargs_keys,
                         List<text::ExprAST>* kwargs_values) {
  // Attrs subclasses must print as CallAST with keyword-only arguments:
  // DictAttrs({"tag": "demo"}) -> std.DictAttrs(tag="demo").
  // This helper strips the callee and appends only "tag=..." so enclosing
  // syntax can print as std.Call(callee, tag="demo") or range(..., tag="demo").
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
  //   Scope(binds=[BindVarDef(vars=[x: i32])], body=...)
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
                               const refl::AccessPath&, const Function& get_cached) {
  // PrimTy casts prefer dtype-call syntax, e.g. std.Cast(std.i32, x) prints as
  // std.i32(x).  Non-primitive casts stay explicit as std.Cast(ty, x).
  text::ExprAST ty = get_cached(obj->ty).cast<text::ExprAST>();
  text::ExprAST value = get_cached(obj->value).cast<text::ExprAST>();
  if (obj->ty.as<PrimTyObj>() != nullptr) {
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

Any InvokePrintPartMethod(const ResolvedPrintInfo& info, const Function& method,
                          const text::IRPrinter& printer, const refl::AccessPath& path,
                          const std::vector<Any>& values) {
  std::vector<Any> owned_args;
  owned_args.reserve(values.size() + 3);
  owned_args.push_back(info.source_obj());
  owned_args.push_back(printer);
  owned_args.push_back(path);
  for (const Any& value : values) {
    owned_args.push_back(value);
  }

  std::vector<AnyView> arg_views;
  arg_views.reserve(owned_args.size());
  for (const Any& arg : owned_args) {
    arg_views.push_back(arg);
  }

  Any result;
  method.CallPacked(arg_views.data(), static_cast<int32_t>(arg_views.size()), &result);
  return result;
}

class PrintBuilderBase {
 protected:
  // Shared operational layer for std-kind builders.  ResolvedPrintInfo owns the
  // reflection facts; this base class turns those facts into the read/path/render
  // helpers that concrete builders need while keeping the original object intact.
  PrintBuilderBase(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                   int32_t std_kind_type_index)
      : obj_(std::move(obj)),
        printer_(std::move(printer)),
        path_(std::move(path)),
        std_kind_type_index_(std_kind_type_index),
        info_(obj_, std_kind_type_index_) {}

  Any ReadStdField(const String& std_field_name) const {
    return this->info_.ReadStdField(std_field_name);
  }

  ObjectRef ReadStdFieldObject(const String& std_field_name) const {
    return this->info_.ReadStdFieldObject(std_field_name);
  }

  Optional<Any> TryReadStdField(const String& std_field_name) const {
    return this->info_.TryReadStdField(std_field_name);
  }

  Optional<Any> TryReadOptionalStdField(const String& std_field_name) const {
    Optional<Any> value = this->TryReadStdField(std_field_name);
    if (!value.has_value() || value.value() == nullptr) {
      return {};
    }
    return value;
  }

  List<Any> ReadStdFieldList(const String& std_field_name) const {
    return this->ReadStdField(std_field_name).cast<List<Any>>();
  }

  refl::AccessPath PathForStdField(const String& std_field_name) const {
    return this->info_.PathForStdField(this->path_, std_field_name);
  }

  bool HasAnyPrintPart() const { return this->info_.HasAnyPrintPart(); }

  void CheckNoCustomPrintParts(const char* builder_name) const {
    if (!this->HasAnyPrintPart()) {
      return;
    }
    TVM_FFI_THROW(ValueError) << builder_name << " for `" << this->obj_->GetTypeKey()
                              << "` does not consume custom print roles";
  }

  bool AppendOptionalAttrsFieldAsKwargs(const String& std_field_name, List<String>* kwargs_keys,
                                        List<text::ExprAST>* kwargs_values) const {
    Optional<Any> attrs = this->TryReadOptionalStdField(std_field_name);
    return attrs.has_value() &&
           AppendAttrsAsKwargs(
               this->printer_->operator()(attrs.value(), this->PathForStdField(std_field_name))
                   .cast<text::ExprAST>(),
               kwargs_keys, kwargs_values);
  }

  List<Any> ReadOptionalBindList() const {
    Optional<Any> value = this->TryReadOptionalStdField("binds");
    if (!value.has_value()) {
      return {};
    }
    return value.value().cast<List<Any>>();
  }

  text::ExprAST PrintExprField(const String& std_field_name) const {
    return this->printer_
        ->operator()(this->ReadStdField(std_field_name), this->PathForStdField(std_field_name))
        .cast<text::ExprAST>();
  }

  Optional<text::ExprAST> PrintOptionalExprField(const String& std_field_name) const {
    Optional<Any> value = this->TryReadOptionalStdField(std_field_name);
    if (!value.has_value()) {
      return {};
    }
    return this->printer_->operator()(value.value(), this->PathForStdField(std_field_name))
        .cast<text::ExprAST>();
  }

  List<text::ExprAST> PrintExprListField(const String& std_field_name) const {
    List<Any> values = this->ReadStdFieldList(std_field_name);
    return this->PrintExprList(values, this->PathForStdField(std_field_name));
  }

  List<text::StmtAST> PrintStmtListField(const String& std_field_name) const {
    List<Any> values = this->ReadStdFieldList(std_field_name);
    return this->PrintStmtList(values, this->PathForStdField(std_field_name));
  }

  List<text::ExprAST> PrintExprList(const List<Any>& values,
                                    const refl::AccessPath& values_path) const {
    List<text::ExprAST> result;
    int64_t n = static_cast<int64_t>(values.size());
    result.reserve(n);
    for (int64_t i = 0; i < n; ++i) {
      result.push_back(
          this->printer_->operator()(values[i], values_path->ArrayItem(i)).cast<text::ExprAST>());
    }
    return result;
  }

  List<text::StmtAST> PrintStmtList(const List<Any>& values,
                                    const refl::AccessPath& values_path) const {
    List<text::StmtAST> result;
    int64_t n = static_cast<int64_t>(values.size());
    result.reserve(n);
    for (int64_t i = 0; i < n; ++i) {
      result.push_back(
          this->printer_->operator()(values[i], values_path->ArrayItem(i)).cast<text::StmtAST>());
    }
    return result;
  }

  Optional<String> GenericMnemonic() const {
    Array<String> dialect_mnemonic = DialectMnemonic(this->obj_->type_index());
    if (dialect_mnemonic.size() != 3) {
      return {};
    }
    return dialect_mnemonic[2];
  }

  bool CanUseStdGeneric(const CachedPrinter& cache, const String& generic) const {
    Optional<String> obj_generic = this->GenericMnemonic();
    Optional<String> common_dialect = cache.CommonDialect();
    return obj_generic.has_value() && obj_generic.value() == generic &&
           common_dialect.has_value() && common_dialect.value() == "std";
  }

  List<text::StmtAST> PrintBody(const String& body_field_name) const {
    List<text::StmtAST> body;
    // Prefix hooks run before the body so render methods can update printer
    // state, such as declaring names that the body may reference.
    for (const ResolvedPrintInfo::PrintPart& part :
         this->info_.Parts("body_prepend", body_field_name)) {
      this->AppendAnyAsStatements(this->RenderPrintPart(part), this->PathForPrintPart(part), &body);
    }

    body.reserve(static_cast<int64_t>(body.size()) + 1);
    this->AppendAnyAsStatements(this->ReadStdField(body_field_name),
                                this->PathForStdField(body_field_name), &body);

    for (const ResolvedPrintInfo::PrintPart& part :
         this->info_.Parts("body_append", body_field_name)) {
      this->AppendAnyAsStatements(this->RenderPrintPart(part), this->PathForPrintPart(part), &body);
    }

    std::vector<ResolvedPrintInfo::PrintPart> wrappers =
        this->info_.Parts("body_wrap", body_field_name);
    for (auto it = wrappers.rbegin(); it != wrappers.rend(); ++it) {
      Any wrapped_body = text::StmtBlockAST(body);
      List<text::StmtAST> next_body;
      this->AppendAnyAsStatements(this->RenderPrintPart(*it, {std::move(wrapped_body)}),
                                  this->PathForPrintPart(*it), &next_body);
      body = std::move(next_body);
    }
    return body;
  }

  refl::AccessPath PathForPrintPart(const ResolvedPrintInfo::PrintPart& part) const {
    this->CheckPrintPartHasField(part);
    return this->info_.PathForField(this->path_, part.field);
  }

  Any RenderPrintPart(const ResolvedPrintInfo::PrintPart& part,
                      std::vector<Any> extra_args = {}) const {
    this->CheckPrintPartHasField(part);

    std::vector<Any> values;
    values.reserve(1 + extra_args.size());
    values.push_back(this->info_.ReadField(String(part.field->name)));
    if (part.render.empty()) {
      if (!extra_args.empty()) {
        TVM_FFI_THROW(ValueError)
            << "Print role `" << part.kind << "` on field `" << String(part.field->name) << "` of `"
            << this->obj_->GetTypeKey()
            << "` requires a render method because the builder passes extra state";
      }
      return values[0];
    }

    values.insert(values.end(), extra_args.begin(), extra_args.end());
    return InvokePrintPartMethod(this->info_, this->info_.FindMethod(part.render), this->printer_,
                                 this->PathForPrintPart(part), values);
  }

  void AppendAnyAsStatements(Any value, const refl::AccessPath& value_path,
                             List<text::StmtAST>* out) const {
    if (value == nullptr) {
      return;
    }
    if (std::optional<List<Any>> values = value.as<List<Any>>()) {
      int64_t n = static_cast<int64_t>(values.value().size());
      out->reserve(static_cast<int64_t>(out->size()) + n);
      for (int64_t i = 0; i < n; ++i) {
        this->AppendAnyAsStatements(values.value()[i], value_path->ArrayItem(i), out);
      }
      return;
    }
    if (std::optional<text::StmtBlockAST> block = value.as<text::StmtBlockAST>()) {
      for (const text::StmtAST& stmt : block.value()->stmts) {
        out->push_back(stmt);
      }
      return;
    }
    if (std::optional<text::StmtAST> stmt = value.as<text::StmtAST>()) {
      out->push_back(stmt.value());
      return;
    }
    if (std::optional<text::ExprAST> expr = value.as<text::ExprAST>()) {
      out->push_back(text::ExprStmtAST(expr.value()));
      return;
    }

    Any printed = this->printer_->operator()(value, value_path);
    if (std::optional<text::StmtBlockAST> block = printed.as<text::StmtBlockAST>()) {
      for (const text::StmtAST& stmt : block.value()->stmts) {
        out->push_back(stmt);
      }
      return;
    }
    if (std::optional<text::StmtAST> stmt = printed.as<text::StmtAST>()) {
      out->push_back(stmt.value());
      return;
    }
    if (std::optional<text::ExprAST> expr = printed.as<text::ExprAST>()) {
      out->push_back(text::ExprStmtAST(expr.value()));
      return;
    }
    TVM_FFI_THROW(ValueError)
        << "Print contribution did not produce an expression or statement AST";
  }

  const ObjectRef obj_;
  const text::IRPrinter printer_;
  const refl::AccessPath path_;
  const int32_t std_kind_type_index_;
  const ResolvedPrintInfo info_;

 private:
  void CheckPrintPartHasField(const ResolvedPrintInfo::PrintPart& part) const {
    if (part.field != nullptr) {
      return;
    }
    TVM_FFI_THROW(ValueError) << "Print role `" << part.kind << "` in `" << this->obj_->GetTypeKey()
                              << "` is not associated with a reflected field";
  }
};

text::ExprAST DefineForeignVar(const text::IRPrinter& printer, const ObjectRef& obj,
                               const String& name) {
  if (!printer->VarIsDefined(obj)) {
    return printer->VarDef(name, obj, {});
  }
  Optional<text::ExprAST> ret = printer->VarGet(obj);
  if (!ret.has_value()) {
    TVM_FFI_THROW(ValueError) << "ffi.std.Var printer failed to fetch variable " << name;
  }
  return ret.value();
}

std::optional<int32_t> ResolveStdSchemaTypeIndex(const ObjectRef& obj) {
  static refl::TypeAttrColumn std_schema_col(refl::type_attr::kStdSchema);
  auto try_lookup = [&](int32_t type_index) -> std::optional<int32_t> {
    AnyView std_schema_view = std_schema_col[type_index];
    if (std_schema_view == nullptr) {
      return {};
    }
    std::optional<int64_t> std_schema = std_schema_view.as<int64_t>();
    if (!std_schema.has_value()) {
      TVM_FFI_THROW(ValueError) << "Type `" << TypeIndexToTypeKey(type_index) << "` declares "
                                << refl::type_attr::kStdSchema
                                << ", but the value is not an integer type index";
    }
    return static_cast<int32_t>(std_schema.value());
  };

  if (std::optional<int32_t> result = try_lookup(obj->type_index())) {
    return result;
  }
  const TVMFFITypeInfo* info = TVMFFIGetTypeInfo(obj->type_index());
  for (int32_t i = info->type_depth - 1; i >= 0; --i) {
    if (std::optional<int32_t> result = try_lookup(info->type_ancestors[i]->type_index)) {
      return result;
    }
  }
  return {};
}

int32_t RequiredStdSchemaTypeIndex(const ObjectRef& obj) {
  if (std::optional<int32_t> schema = ResolveStdSchemaTypeIndex(obj)) {
    return schema.value();
  }
  TVM_FFI_THROW(ValueError) << "Object `" << obj->GetTypeKey() << "` has no "
                            << refl::type_attr::kStdSchema << " declaration";
  TVM_FFI_UNREACHABLE();
}

bool HasStdSchema(const ObjectRef& obj, int32_t std_kind_type_index) {
  std::optional<int32_t> schema = ResolveStdSchemaTypeIndex(obj);
  return schema.has_value() && schema.value() == std_kind_type_index;
}

Any ReadObjectStdField(const ObjectRef& obj, int32_t std_kind_type_index,
                       const String& std_field_name) {
  return ResolvedPrintInfo(obj, std_kind_type_index).ReadStdField(std_field_name);
}

Optional<Any> TryReadOptionalObjectStdField(const ObjectRef& obj, int32_t std_kind_type_index,
                                            const String& std_field_name) {
  Optional<Any> value = ResolvedPrintInfo(obj, std_kind_type_index).TryReadStdField(std_field_name);
  if (!value.has_value() || value.value() == nullptr) {
    return {};
  }
  return value;
}

refl::AccessPath PathForObjectStdField(const ObjectRef& obj, int32_t std_kind_type_index,
                                       const refl::AccessPath& object_path,
                                       const String& std_field_name) {
  return ResolvedPrintInfo(obj, std_kind_type_index).PathForStdField(object_path, std_field_name);
}

List<Any> ReadObjectStdFieldList(const ObjectRef& obj, int32_t std_kind_type_index,
                                 const String& std_field_name) {
  return ReadObjectStdField(obj, std_kind_type_index, std_field_name).cast<List<Any>>();
}

text::ExprAST DefineVarLike(const text::IRPrinter& printer, const ObjectRef& var) {
  String name =
      ReadObjectStdField(var, Var::ContainerType::RuntimeTypeIndex(), "name").cast<String>();
  return DefineForeignVar(printer, var, name);
}

text::ExprAST DefineVarTupleLike(const text::IRPrinter& printer, const List<Any>& vars) {
  if (vars.size() == 1) {
    return DefineVarLike(printer, vars[0].cast<ObjectRef>());
  }
  List<text::ExprAST> lhs_vars;
  lhs_vars.reserve(static_cast<int64_t>(vars.size()));
  for (const Any& var : vars) {
    lhs_vars.push_back(DefineVarLike(printer, var.cast<ObjectRef>()));
  }
  return text::TupleAST(std::move(lhs_vars));
}

Optional<text::ExprAST> DefineScopeVarsAsWithTargetsLike(const text::IRPrinter& printer,
                                                         const List<Any>& binds) {
  List<text::ExprAST> targets;
  for (const Any& bind_value : binds) {
    ObjectRef bind = bind_value.cast<ObjectRef>();
    int32_t bind_schema = RequiredStdSchemaTypeIndex(bind);
    List<Any> vars = ReadObjectStdFieldList(bind, bind_schema, "vars");
    for (const Any& var : vars) {
      targets.push_back(DefineVarLike(printer, var.cast<ObjectRef>()));
    }
  }
  if (targets.empty()) return {};
  if (targets.size() == 1) return targets[0];
  return text::TupleAST(std::move(targets));
}

text::ExprAST BindInitializerCallLike(const ObjectRef& bind, const text::IRPrinter& printer,
                                      const refl::AccessPath& path) {
  int32_t bind_schema = RequiredStdSchemaTypeIndex(bind);
  List<text::ExprAST> args;
  if (bind_schema == BindExpr::ContainerType::RuntimeTypeIndex()) {
    args.push_back(printer
                       ->operator()(ReadObjectStdField(bind, bind_schema, "expr"),
                                    PathForObjectStdField(bind, bind_schema, path, "expr"))
                       .cast<text::ExprAST>());
  } else if (bind_schema == BindVarDef::ContainerType::RuntimeTypeIndex()) {
    List<Any> vars = ReadObjectStdFieldList(bind, bind_schema, "vars");
    args.reserve(static_cast<int64_t>(vars.size()));
    refl::AccessPath vars_path = PathForObjectStdField(bind, bind_schema, path, "vars");
    int64_t n = static_cast<int64_t>(vars.size());
    for (int64_t i = 0; i < n; ++i) {
      ObjectRef var = vars[i].cast<ObjectRef>();
      args.push_back(
          printer
              ->operator()(ReadObjectStdField(var, Var::ContainerType::RuntimeTypeIndex(), "ty"),
                           PathForObjectStdField(var, Var::ContainerType::RuntimeTypeIndex(),
                                                 vars_path->ArrayItem(i), "ty"))
              .cast<text::ExprAST>());
    }
  } else {
    TVM_FFI_THROW(ValueError) << "ffi.std.Scope expected BindExpr or BindVarDef-like object, got `"
                              << bind->GetTypeKey() << "`";
  }

  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  bool has_attrs = false;
  if (Optional<Any> attrs = TryReadOptionalObjectStdField(bind, bind_schema, "attrs")) {
    has_attrs = AppendAttrsAsKwargs(
        printer->operator()(attrs.value(), PathForObjectStdField(bind, bind_schema, path, "attrs"))
            .cast<text::ExprAST>(),
        &kwargs_keys, &kwargs_values);
  }
  return has_attrs ? text::ExprCallKw(CallMnemonic(printer->cfg, bind), std::move(args),
                                      std::move(kwargs_keys), std::move(kwargs_values))
                   : text::ExprCall(CallMnemonic(printer->cfg, bind), std::move(args));
}

std::optional<int64_t> BinaryOperationKind(const String& generic) {
  if (generic == "__add__") return text::OperationASTObj::kAdd;
  if (generic == "__sub__") return text::OperationASTObj::kSub;
  if (generic == "__mul__") return text::OperationASTObj::kMult;
  if (generic == "__floordiv__") return text::OperationASTObj::kFloorDiv;
  if (generic == "__mod__") return text::OperationASTObj::kMod;
  if (generic == "__eq__") return text::OperationASTObj::kEq;
  if (generic == "__ne__") return text::OperationASTObj::kNotEq;
  if (generic == "__le__") return text::OperationASTObj::kLtE;
  if (generic == "__ge__") return text::OperationASTObj::kGtE;
  if (generic == "__gt__") return text::OperationASTObj::kGt;
  if (generic == "__lt__") return text::OperationASTObj::kLt;
  if (generic == "__and__") return text::OperationASTObj::kAnd;
  if (generic == "__or__") return text::OperationASTObj::kOr;
  return {};
}

template <typename RefType>
class CastCompatiblePrintBuilder : public PrintBuilderBase {
 public:
  CastCompatiblePrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                             int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Std-kind print builder");
    if (std::optional<RefType> typed = this->obj_.as<RefType>()) {
      return TextPrint(typed.value(), this->printer_, this->path_);
    }
    TVM_FFI_THROW(ValueError) << "Std-kind print builder `"
                              << TypeIndexToTypeKey(this->std_kind_type_index_)
                              << "` cannot print non-inheriting foreign type `"
                              << this->obj_->GetTypeKey() << "` yet";
    TVM_FFI_UNREACHABLE();
  }
};

class ModulePrintBuilder : public PrintBuilderBase {
 public:
  ModulePrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                     int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Module std-kind printer");
    List<text::StmtAST> stmts = this->PrintStmtListField("funcs");
    List<text::ExprAST> decorators{CallMnemonic(this->printer_->cfg, this->obj_)};
    return text::ClassAST(text::IdAST("MyModule"), {}, std::move(decorators), std::move(stmts));
  }
};

class FuncPrintBuilder : public PrintBuilderBase {
 public:
  FuncPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                   int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Func std-kind printer");
    List<Any> arg_values = this->ReadStdFieldList("args");
    List<text::AssignAST> args;
    int64_t n = static_cast<int64_t>(arg_values.size());
    args.reserve(n);
    refl::AccessPath args_path = this->PathForStdField("args");
    for (int64_t i = 0; i < n; ++i) {
      ObjectRef arg = arg_values[i].cast<ObjectRef>();
      text::ExprAST lhs = DefineVarLike(this->printer_, arg);
      Optional<text::ExprAST> annotation;
      Optional<Any> ty =
          TryReadOptionalObjectStdField(arg, Var::ContainerType::RuntimeTypeIndex(), "ty");
      if (ty.has_value()) {
        annotation = this->printer_
                         ->operator()(ty.value(), PathForObjectStdField(
                                                      arg, Var::ContainerType::RuntimeTypeIndex(),
                                                      args_path->ArrayItem(i), "ty"))
                         .cast<text::ExprAST>();
      }
      args.push_back(text::AssignAST(std::move(lhs), {}, std::move(annotation)));
    }

    List<text::StmtAST> body = this->PrintStmtListField("body");
    Optional<text::ExprAST> ret_type = this->PrintOptionalExprField("ret_type");
    List<String> decorator_keys;
    List<text::ExprAST> decorator_values;
    bool has_attrs =
        this->AppendOptionalAttrsFieldAsKwargs("attrs", &decorator_keys, &decorator_values);

    List<text::ExprAST> decorators;
    if (!has_attrs) {
      decorators.push_back(CallMnemonic(this->printer_->cfg, this->obj_));
    } else {
      decorators.push_back(text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), {},
                                            std::move(decorator_keys),
                                            std::move(decorator_values)));
    }
    return text::FunctionAST(text::IdAST(this->ReadStdField("symbol").cast<String>()),
                             std::move(args), std::move(decorators), std::move(ret_type),
                             std::move(body));
  }
};

class RangePrintBuilder : public PrintBuilderBase {
 public:
  RangePrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                    int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Range std-kind printer");
    Optional<text::ExprAST> start = this->PrintOptionalExprField("start");
    Optional<text::ExprAST> stop = this->PrintOptionalExprField("stop");
    Optional<text::ExprAST> step = this->PrintOptionalExprField("step");
    if (start.has_value() && !stop.has_value() && !step.has_value()) {
      return start.value();
    }
    return text::SliceAST(std::move(start), std::move(stop), std::move(step));
  }
};

class AnyTyPrintBuilder : public PrintBuilderBase {
 public:
  AnyTyPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                    int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("AnyTy std-kind printer");
    return CallMnemonic(this->printer_->cfg, this->obj_);
  }
};

class PrimTyPrintBuilder : public PrintBuilderBase {
 public:
  PrimTyPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                     int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("PrimTy std-kind printer");
    Any dtype = this->ReadStdField("dtype");
    String printed_name = DTypeAbbrev(dtype.cast<DLDataType>());
    Array<String> dialect_mnemonic = DialectMnemonic(this->obj_->type_index());
    String dialect = dialect_mnemonic[0];
    String mnemonic = dialect_mnemonic[1];
    String full_mnemonic(std::string(dialect.data(), dialect.size()) + "$" +
                         std::string(mnemonic.data(), mnemonic.size()));
    if (this->printer_->cfg->dialect_print_map.count(full_mnemonic)) {
      String mapped = this->printer_->cfg->dialect_print_map[full_mnemonic];
      if (mapped == "*") {
        return text::IdAST(std::move(printed_name));
      }
      return text::DottedName(std::move(mapped));
    }
    if (this->printer_->cfg->dialect_print_map.count(dialect)) {
      String mapped = this->printer_->cfg->dialect_print_map[dialect];
      if (mapped == "*") {
        return text::IdAST(std::move(printed_name));
      }
      return text::ExprAttr(text::DottedName(std::move(mapped)), printed_name);
    }
    return text::ExprAttr(text::DottedName(std::move(dialect)), printed_name);
  }
};

class TupleTypePrintBuilder : public PrintBuilderBase {
 public:
  TupleTypePrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                        int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("TupleType std-kind printer");
    return text::IndexAST(CallMnemonic(this->printer_->cfg, this->obj_),
                          this->PrintExprListField("fields"));
  }
};

class TensorTyPrintBuilder : public PrintBuilderBase {
 public:
  TensorTyPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                       int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("TensorTy std-kind printer");
    Any dtype_value = this->ReadStdField("dtype");
    PrimTy dtype(dtype_value.cast<DLDataType>());
    return text::IndexAST(
        this->printer_->operator()(dtype, this->PathForStdField("dtype")).cast<text::ExprAST>(),
        this->PrintExprListField("shape"));
  }
};

class IntImmPrintBuilder : public PrintBuilderBase {
 public:
  IntImmPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                     int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("IntImm std-kind printer");
    return text::LiteralAST::Int(this->ReadStdField("value").cast<int64_t>());
  }
};

class FloatImmPrintBuilder : public PrintBuilderBase {
 public:
  FloatImmPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                       int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("FloatImm std-kind printer");
    return text::LiteralAST::Float(this->ReadStdField("value").cast<double>());
  }
};

class StringImmPrintBuilder : public PrintBuilderBase {
 public:
  StringImmPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                        int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("StringImm std-kind printer");
    return text::LiteralAST::Str(this->ReadStdField("value").cast<String>());
  }
};

class BinaryPrintBuilder : public PrintBuilderBase {
 public:
  BinaryPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                     int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Binary std-kind printer");

    Array<String> dialect_mnemonic = DialectMnemonic(this->obj_->type_index());
    ObjectRef lhs = this->ReadStdFieldObject("a");
    ObjectRef rhs = this->ReadStdFieldObject("b");
    CachedPrinter cache(this->printer_);
    cache.RunCache(lhs, this->PathForStdField("a"));
    cache.RunCache(rhs, this->PathForStdField("b"));
    List<text::ExprAST> operands{cache.ExprFromCache(lhs), cache.ExprFromCache(rhs)};

    Optional<String> common_dialect = cache.CommonDialect();
    if (dialect_mnemonic.size() == 3 && common_dialect.has_value() &&
        common_dialect.value() == "std") {
      String generic = dialect_mnemonic[2];
      if (std::optional<int64_t> op = BinaryOperationKind(generic)) {
        return text::OperationAST(op.value(), std::move(operands));
      }
      if (generic == "min") {
        return text::ExprCall(text::IdAST("min"), std::move(operands));
      }
      if (generic == "max") {
        return text::ExprCall(text::IdAST("max"), std::move(operands));
      }
    }
    return text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(operands));
  }
};

class NotPrintBuilder : public PrintBuilderBase {
 public:
  NotPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                  int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Not std-kind printer");
    ObjectRef operand = this->ReadStdFieldObject("operand");
    CachedPrinter cache(this->printer_);
    cache.RunCache(operand, this->PathForStdField("operand"));
    if (this->CanUseStdGeneric(cache, "__invert__")) {
      return text::OperationAST(text::OperationASTObj::kNot, {cache.ExprFromCache(operand)});
    }
    return text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_),
                          {cache.ExprFromCache(operand)});
  }
};

class LoadPrintBuilder : public PrintBuilderBase {
 public:
  LoadPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                   int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Load std-kind printer");
    ObjectRef lhs = this->ReadStdFieldObject("lhs");
    List<Any> indices = this->ReadStdFieldList("indices");
    CachedPrinter cache(this->printer_);
    cache.RunCache(lhs, this->PathForStdField("lhs"));
    refl::AccessPath indices_path = this->PathForStdField("indices");
    int64_t n = static_cast<int64_t>(indices.size());
    for (int64_t i = 0; i < n; ++i) {
      cache.RunCache(indices[i].cast<ObjectRef>(), indices_path->ArrayItem(i));
    }

    List<text::ExprAST> operands{cache.ExprFromCache(lhs)};
    operands.reserve(n + 1);
    for (const Any& index : indices) {
      operands.push_back(cache.ExprFromCache(index.cast<ObjectRef>()));
    }
    if (this->CanUseStdGeneric(cache, "__load__")) {
      return LoadStore(operands, /*end_index_offset=*/0);
    }
    return text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(operands));
  }
};

class CastPrintBuilder : public PrintBuilderBase {
 public:
  CastPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                   int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Cast std-kind printer");
    ObjectRef ty = this->ReadStdFieldObject("ty");
    ObjectRef value = this->ReadStdFieldObject("value");
    CachedPrinter cache(this->printer_);
    cache.RunCache(ty, this->PathForStdField("ty"));
    cache.RunCache(value, this->PathForStdField("value"));
    text::ExprAST ty_ast = cache.ExprFromCache(ty);
    text::ExprAST value_ast = cache.ExprFromCache(value);
    if (this->CanUseStdGeneric(cache, "__cast__") &&
        HasStdSchema(ty, PrimTy::ContainerType::RuntimeTypeIndex())) {
      return text::ExprCall(std::move(ty_ast), {std::move(value_ast)});
    }
    return text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_),
                          {std::move(ty_ast), std::move(value_ast)});
  }
};

class CallPrintBuilder : public PrintBuilderBase {
 public:
  CallPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                   int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Call std-kind printer");
    Any callee_value = this->ReadStdField("callee");
    Optional<String> callee_name;
    if (std::optional<String> symbol = callee_value.as<String>()) {
      callee_name = symbol.value();
    } else if (std::optional<ObjectRef> callee_obj = callee_value.as<ObjectRef>()) {
      if (HasStdSchema(callee_obj.value(), Func::ContainerType::RuntimeTypeIndex())) {
        callee_name = ReadObjectStdField(callee_obj.value(),
                                         Func::ContainerType::RuntimeTypeIndex(), "symbol")
                          .cast<String>();
      }
    }

    text::ExprAST callee =
        callee_name.has_value()
            ? text::ExprAST(text::IdAST(callee_name.value()))
            : this->printer_->operator()(callee_value, this->PathForStdField("callee"))
                  .cast<text::ExprAST>();
    List<text::ExprAST> args = this->PrintExprListField("args");
    List<text::ExprAST> call_args{std::move(callee)};
    call_args.reserve(static_cast<int64_t>(args.size() + 1));
    for (text::ExprAST arg : args) {
      call_args.push_back(arg);
    }

    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    if (!this->AppendOptionalAttrsFieldAsKwargs("attr", &kwargs_keys, &kwargs_values)) {
      return text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(call_args));
    }
    return text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), std::move(call_args),
                            std::move(kwargs_keys), std::move(kwargs_values));
  }
};

class VarPrintBuilder : public PrintBuilderBase {
 public:
  VarPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                  int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Var std-kind printer");
    return DefineForeignVar(this->printer_, this->obj_, this->ReadStdField("name").cast<String>());
  }
};

class IfStmtPrintBuilder : public PrintBuilderBase {
 public:
  IfStmtPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                     int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("IfStmt std-kind printer");
    return text::IfAST(this->PrintExprField("cond"), this->PrintStmtListField("then_body"),
                       this->PrintStmtListField("else_body"));
  }
};

class BindExprPrintBuilder : public PrintBuilderBase {
 public:
  BindExprPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                       int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("BindExpr std-kind printer");
    List<Any> vars = this->ReadStdFieldList("vars");
    ObjectRef expr = this->ReadStdFieldObject("expr");
    CachedPrinter cache(this->printer_);
    refl::AccessPath vars_path = this->PathForStdField("vars");
    int64_t n = static_cast<int64_t>(vars.size());
    for (int64_t i = 0; i < n; ++i) {
      cache.RunCache(vars[i].cast<ObjectRef>(), vars_path->ArrayItem(i));
    }
    cache.RunCache(expr, this->PathForStdField("expr"));

    if (this->CanUseStdGeneric(cache, "__bind_expr__")) {
      text::ExprAST rhs = cache.ExprFromCache(expr);
      List<String> kwargs_keys;
      List<text::ExprAST> kwargs_values;
      if (this->AppendOptionalAttrsFieldAsKwargs("attrs", &kwargs_keys, &kwargs_values)) {
        rhs = text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), {rhs},
                               std::move(kwargs_keys), std::move(kwargs_values));
      }
      if (vars.empty()) {
        return text::ExprStmtAST(std::move(rhs));
      }
      return text::AssignAST(DefineVarTupleLike(this->printer_, vars), std::move(rhs));
    }

    List<text::ExprAST> args;
    args.reserve(n + 1);
    for (const Any& var : vars) {
      args.push_back(cache.ExprFromCache(var.cast<ObjectRef>()));
    }
    args.push_back(cache.ExprFromCache(expr));
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    text::ExprAST call =
        this->AppendOptionalAttrsFieldAsKwargs("attrs", &kwargs_keys, &kwargs_values)
            ? text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), std::move(args),
                               std::move(kwargs_keys), std::move(kwargs_values))
            : text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(args));
    return text::ExprStmtAST(std::move(call));
  }
};

class BindVarDefPrintBuilder : public PrintBuilderBase {
 public:
  BindVarDefPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                         int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("BindVarDef std-kind printer");
    List<Any> vars = this->ReadStdFieldList("vars");
    CachedPrinter cache(this->printer_);
    refl::AccessPath vars_path = this->PathForStdField("vars");
    int64_t n = static_cast<int64_t>(vars.size());
    for (int64_t i = 0; i < n; ++i) {
      cache.RunCache(vars[i].cast<ObjectRef>(), vars_path->ArrayItem(i));
    }

    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    bool has_attrs = this->AppendOptionalAttrsFieldAsKwargs("attrs", &kwargs_keys, &kwargs_values);
    if (this->CanUseStdGeneric(cache, "__bind_var_def__")) {
      if (vars.empty()) {
        if (!has_attrs) {
          return text::ExprStmtAST(text::IdAST("pass"));
        }
        return text::ExprStmtAST(text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), {},
                                                  std::move(kwargs_keys),
                                                  std::move(kwargs_values)));
      }
      List<text::ExprAST> types;
      types.reserve(n);
      for (int64_t i = 0; i < n; ++i) {
        ObjectRef var = vars[i].cast<ObjectRef>();
        types.push_back(
            this->printer_
                ->operator()(ReadObjectStdField(var, Var::ContainerType::RuntimeTypeIndex(), "ty"),
                             PathForObjectStdField(var, Var::ContainerType::RuntimeTypeIndex(),
                                                   vars_path->ArrayItem(i), "ty"))
                .cast<text::ExprAST>());
      }
      text::ExprAST rhs =
          has_attrs
              ? text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), std::move(types),
                                 std::move(kwargs_keys), std::move(kwargs_values))
              : text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(types));
      return text::AssignAST(DefineVarTupleLike(this->printer_, vars), std::move(rhs));
    }

    List<text::ExprAST> args;
    args.reserve(n);
    for (const Any& var : vars) {
      args.push_back(cache.ExprFromCache(var.cast<ObjectRef>()));
    }
    text::ExprAST call =
        has_attrs ? text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), std::move(args),
                                     std::move(kwargs_keys), std::move(kwargs_values))
                  : text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(args));
    return text::ExprStmtAST(std::move(call));
  }
};

class ScopePrintBuilder : public PrintBuilderBase {
 public:
  ScopePrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                    int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    DialectFrame dialect_frame(this->printer_, this->obj_);

    List<String> scope_kwarg_keys;
    List<text::ExprAST> scope_kwarg_values;
    bool has_attrs =
        this->AppendOptionalAttrsFieldAsKwargs("attrs", &scope_kwarg_keys, &scope_kwarg_values);
    List<text::StmtAST> body = this->PrintBody("body");
    List<Any> binds = this->ReadOptionalBindList();
    if (binds.empty() && !has_attrs) {
      return text::StmtBlockAST(std::move(body));
    }

    List<text::ExprAST> scope_args;
    int64_t n = static_cast<int64_t>(binds.size());
    scope_args.reserve(n);
    refl::AccessPath binds_path = this->PathForStdField("binds");
    for (int64_t i = 0; i < n; ++i) {
      scope_args.push_back(BindInitializerCallLike(binds[i].cast<ObjectRef>(), this->printer_,
                                                   binds_path->ArrayItem(i)));
    }
    text::ExprAST rhs =
        scope_kwarg_keys.empty()
            ? text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(scope_args))
            : text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), std::move(scope_args),
                               std::move(scope_kwarg_keys), std::move(scope_kwarg_values));
    Optional<text::ExprAST> lhs = DefineScopeVarsAsWithTargetsLike(this->printer_, binds);
    return text::WithAST(std::move(lhs), std::move(rhs), std::move(body));
  }
};

class ForPrintBuilder : public PrintBuilderBase {
 public:
  ForPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                  int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    DialectFrame dialect_frame(this->printer_, this->obj_);
    List<Any> binds = this->ReadOptionalBindList();
    List<text::ExprAST> targets;
    for (const Any& bind_value : binds) {
      ObjectRef bind = bind_value.cast<ObjectRef>();
      int32_t bind_schema = RequiredStdSchemaTypeIndex(bind);
      List<Any> vars = ReadObjectStdFieldList(bind, bind_schema, "vars");
      for (const Any& var : vars) {
        targets.push_back(DefineVarLike(this->printer_, var.cast<ObjectRef>()));
      }
    }
    text::ExprAST lhs = text::IdAST("_");
    if (targets.size() == 1) {
      lhs = targets[0];
    } else if (!targets.empty()) {
      lhs = text::TupleAST(std::move(targets));
    }

    ObjectRef range = this->ReadStdFieldObject("range_");
    int32_t range_schema = Range::ContainerType::RuntimeTypeIndex();
    refl::AccessPath range_path = this->PathForStdField("range_");
    List<text::ExprAST> range_args;
    Optional<Any> start = TryReadOptionalObjectStdField(range, range_schema, "start");
    Optional<Any> stop = TryReadOptionalObjectStdField(range, range_schema, "stop");
    Optional<Any> step = TryReadOptionalObjectStdField(range, range_schema, "step");
    if (start.has_value()) {
      range_args.push_back(
          this->printer_
              ->operator()(start.value(),
                           PathForObjectStdField(range, range_schema, range_path, "start"))
              .cast<text::ExprAST>());
    }
    if (stop.has_value()) {
      if (!start.has_value()) {
        range_args.push_back(text::LiteralAST::Null());
      }
      range_args.push_back(this->printer_
                               ->operator()(stop.value(), PathForObjectStdField(range, range_schema,
                                                                                range_path, "stop"))
                               .cast<text::ExprAST>());
    }
    if (step.has_value()) {
      if (!stop.has_value()) {
        range_args.push_back(text::LiteralAST::Null());
      }
      range_args.push_back(this->printer_
                               ->operator()(step.value(), PathForObjectStdField(range, range_schema,
                                                                                range_path, "step"))
                               .cast<text::ExprAST>());
    }

    List<String> range_kwarg_keys;
    List<text::ExprAST> range_kwarg_values;
    this->AppendOptionalAttrsFieldAsKwargs("attrs", &range_kwarg_keys, &range_kwarg_values);
    text::ExprAST rhs =
        range_kwarg_keys.empty()
            ? text::ExprCall(CallCustomMnemonic(this->printer_->cfg, this->obj_, "range"),
                             std::move(range_args))
            : text::ExprCallKw(CallCustomMnemonic(this->printer_->cfg, this->obj_, "range"),
                               std::move(range_args), std::move(range_kwarg_keys),
                               std::move(range_kwarg_values));
    return text::ForAST(std::move(lhs), std::move(rhs), this->PrintBody("body"));
  }
};

class WhilePrintBuilder : public PrintBuilderBase {
 public:
  WhilePrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                    int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    DialectFrame dialect_frame(this->printer_, this->obj_);
    List<String> while_kwarg_keys;
    List<text::ExprAST> while_kwarg_values;
    bool has_attrs =
        this->AppendOptionalAttrsFieldAsKwargs("attrs", &while_kwarg_keys, &while_kwarg_values);
    List<Any> binds = this->ReadOptionalBindList();
    text::ExprAST cond = this->PrintExprField("cond");
    List<text::StmtAST> body = this->PrintBody("body");
    if (binds.empty() && !has_attrs) {
      return text::WhileAST(std::move(cond), std::move(body));
    }

    List<text::ExprAST> while_args{std::move(cond)};
    refl::AccessPath binds_path = this->PathForStdField("binds");
    int64_t n = static_cast<int64_t>(binds.size());
    for (int64_t i = 0; i < n; ++i) {
      while_args.push_back(BindInitializerCallLike(binds[i].cast<ObjectRef>(), this->printer_,
                                                   binds_path->ArrayItem(i)));
    }
    text::ExprAST rhs =
        while_kwarg_keys.empty()
            ? text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(while_args))
            : text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), std::move(while_args),
                               std::move(while_kwarg_keys), std::move(while_kwarg_values));
    Optional<text::ExprAST> lhs = DefineScopeVarsAsWithTargetsLike(this->printer_, binds);
    return text::WithAST(std::move(lhs), std::move(rhs), std::move(body));
  }
};

class StorePrintBuilder : public PrintBuilderBase {
 public:
  StorePrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                    int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Store std-kind printer");
    ObjectRef lhs = this->ReadStdFieldObject("lhs");
    List<Any> indices = this->ReadStdFieldList("indices");
    ObjectRef rhs = this->ReadStdFieldObject("rhs");
    CachedPrinter cache(this->printer_);
    cache.RunCache(lhs, this->PathForStdField("lhs"));
    refl::AccessPath indices_path = this->PathForStdField("indices");
    int64_t n = static_cast<int64_t>(indices.size());
    for (int64_t i = 0; i < n; ++i) {
      cache.RunCache(indices[i].cast<ObjectRef>(), indices_path->ArrayItem(i));
    }
    cache.RunCache(rhs, this->PathForStdField("rhs"));

    List<text::ExprAST> args{cache.ExprFromCache(lhs)};
    args.reserve(n + 2);
    for (const Any& index : indices) {
      args.push_back(cache.ExprFromCache(index.cast<ObjectRef>()));
    }
    args.push_back(cache.ExprFromCache(rhs));
    if (this->CanUseStdGeneric(cache, "__store__")) {
      return text::AssignAST(LoadStore(args, /*end_index_offset=*/1), args[args.size() - 1]);
    }
    return text::ExprStmtAST(
        text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(args)));
  }
};

class AssertPrintBuilder : public PrintBuilderBase {
 public:
  AssertPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                     int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Assert std-kind printer");
    ObjectRef cond = this->ReadStdFieldObject("cond");
    CachedPrinter cache(this->printer_);
    cache.RunCache(cond, this->PathForStdField("cond"));
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    if (this->AppendOptionalAttrsFieldAsKwargs("attrs", &kwargs_keys, &kwargs_values)) {
      return text::ExprStmtAST(text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_),
                                                {cache.ExprFromCache(cond)}, std::move(kwargs_keys),
                                                std::move(kwargs_values)));
    }
    if (this->CanUseStdGeneric(cache, "__assert__")) {
      return text::AssertAST(cache.ExprFromCache(cond));
    }
    return text::ExprStmtAST(
        text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), {cache.ExprFromCache(cond)}));
  }
};

class ReturnPrintBuilder : public PrintBuilderBase {
 public:
  ReturnPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                     int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Return std-kind printer");
    List<Any> exprs = this->ReadStdFieldList("exprs");
    CachedPrinter cache(this->printer_);
    refl::AccessPath exprs_path = this->PathForStdField("exprs");
    int64_t n = static_cast<int64_t>(exprs.size());
    for (int64_t i = 0; i < n; ++i) {
      cache.RunCache(exprs[i].cast<ObjectRef>(), exprs_path->ArrayItem(i));
    }
    List<text::ExprAST> args;
    args.reserve(n);
    for (const Any& expr : exprs) {
      args.push_back(cache.ExprFromCache(expr.cast<ObjectRef>()));
    }
    if (this->CanUseStdGeneric(cache, "__return__")) {
      return text::ReturnAST(PackOptionalValue(std::move(args)));
    }
    return text::ExprStmtAST(
        text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(args)));
  }
};

class YieldPrintBuilder : public PrintBuilderBase {
 public:
  YieldPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                    int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Yield std-kind printer");
    List<Any> exprs = this->ReadStdFieldList("exprs");
    CachedPrinter cache(this->printer_);
    refl::AccessPath exprs_path = this->PathForStdField("exprs");
    int64_t n = static_cast<int64_t>(exprs.size());
    for (int64_t i = 0; i < n; ++i) {
      cache.RunCache(exprs[i].cast<ObjectRef>(), exprs_path->ArrayItem(i));
    }
    List<text::ExprAST> args;
    args.reserve(n);
    for (const Any& expr : exprs) {
      args.push_back(cache.ExprFromCache(expr.cast<ObjectRef>()));
    }
    if (this->CanUseStdGeneric(cache, "__yield__")) {
      return text::ExprStmtAST(text::YieldAST(PackOptionalValue(std::move(args))));
    }
    return text::ExprStmtAST(
        text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), std::move(args)));
  }
};

class BreakPrintBuilder : public PrintBuilderBase {
 public:
  BreakPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                    int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Break std-kind printer");
    CachedPrinter cache(this->printer_);
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    if (this->AppendOptionalAttrsFieldAsKwargs("attrs", &kwargs_keys, &kwargs_values)) {
      return text::ExprStmtAST(text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), {},
                                                std::move(kwargs_keys), std::move(kwargs_values)));
    }
    if (this->CanUseStdGeneric(cache, "__break__")) {
      return text::ExprStmtAST(text::IdAST("break"));
    }
    return text::ExprStmtAST(text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), {}));
  }
};

class ContinuePrintBuilder : public PrintBuilderBase {
 public:
  ContinuePrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                       int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("Continue std-kind printer");
    CachedPrinter cache(this->printer_);
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    if (this->AppendOptionalAttrsFieldAsKwargs("attrs", &kwargs_keys, &kwargs_values)) {
      return text::ExprStmtAST(text::ExprCallKw(CallMnemonic(this->printer_->cfg, this->obj_), {},
                                                std::move(kwargs_keys), std::move(kwargs_values)));
    }
    if (this->CanUseStdGeneric(cache, "__continue__")) {
      return text::ExprStmtAST(text::IdAST("continue"));
    }
    return text::ExprStmtAST(text::ExprCall(CallMnemonic(this->printer_->cfg, this->obj_), {}));
  }
};

class DictAttrsPrintBuilder : public PrintBuilderBase {
 public:
  DictAttrsPrintBuilder(ObjectRef obj, text::IRPrinter printer, refl::AccessPath path,
                        int32_t std_kind_type_index)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_kind_type_index) {
  }

  text::NodeAST Build() const {
    this->CheckNoCustomPrintParts("DictAttrs std-kind printer");
    Dict<String, Any> values = this->ReadStdField("values").cast<Dict<String, Any>>();
    List<String> kwargs_keys;
    List<text::ExprAST> kwargs_values;
    std::vector<String> sorted_keys;
    sorted_keys.reserve(values.size());
    for (const auto& kv : values) {
      sorted_keys.push_back(kv.first);
    }
    std::sort(sorted_keys.begin(), sorted_keys.end());

    kwargs_keys.reserve(static_cast<int64_t>(sorted_keys.size()));
    kwargs_values.reserve(static_cast<int64_t>(sorted_keys.size()));
    refl::AccessPath values_path = this->PathForStdField("values");
    int64_t n = static_cast<int64_t>(sorted_keys.size());
    for (int64_t i = 0; i < n; ++i) {
      const String& key = sorted_keys[i];
      kwargs_keys.push_back(key);
      kwargs_values.push_back(
          this->printer_->operator()(values[key], values_path->MapItem(key)).cast<text::ExprAST>());
    }
    return text::CallAST(CallMnemonic(this->printer_->cfg, this->obj_), {}, std::move(kwargs_keys),
                         std::move(kwargs_values));
  }
};

template <typename Builder>
text::NodeAST RunPrintBuilder(const ObjectRef& obj, const text::IRPrinter& printer,
                              const refl::AccessPath& path, int32_t std_kind_type_index) {
  return Builder(obj, printer, path, std_kind_type_index).Build();
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
  List<text::ExprAST> decorators{CallMnemonic(printer->cfg, obj)};
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
    decorators.push_back(CallMnemonic(printer->cfg, obj));
  } else {
    decorators.push_back(text::ExprCallKw(CallMnemonic(printer->cfg, obj), {},
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

#define TVM_FFI_STD_LITERAL_TEXT_PRINT(TypeName, LiteralFactory)               \
  text::NodeAST TextPrint(const TypeName& obj, const text::IRPrinter& printer, \
                          const refl::AccessPath& path) {                      \
    /* TODO(junrushao( If literal immediates are not treated as text generics, \
     * print the explicit mnemonic form instead of a raw Python literal. */    \
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
    cache.RunCache(obj->a, path->Attr("a"));                                     \
    cache.RunCache(obj->b, path->Attr("b"));                                     \
    return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST { \
      return text::ExprCall(CallMnemonic(printer->cfg, obj),                     \
                            BinaryOperands(obj, cache.GetCachedFunction()));     \
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
  cache.RunCache(obj->operand, path->Attr("operand"));
  return ApplyTextGenericOrFallback(obj, path, cache, [&]() -> text::NodeAST {
    return text::ExprCall(CallMnemonic(printer->cfg, obj), {cache.ExprFromCache(obj->operand)});
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
    return text::ExprCall(CallMnemonic(printer->cfg, obj), LoadOperands(obj, get_cached));
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
  List<text::ExprAST> args = PrintExprList(printer, obj->args, path->Attr("args"));
  List<text::ExprAST> call_args{std::move(callee)};
  call_args.reserve(static_cast<int64_t>(obj->args.size() + 1));
  for (text::ExprAST arg : args) {
    call_args.push_back(arg);
  }
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  if (!obj->attr.has_value() ||
      !AppendAttrsAsKwargs(
          printer->operator()(*obj->attr, path->Attr("attr")).cast<text::ExprAST>(), &kwargs_keys,
          &kwargs_values)) {
    return text::ExprCall(CallMnemonic(printer->cfg, obj), std::move(call_args));
  }
  return text::ExprCallKw(CallMnemonic(printer->cfg, obj), std::move(call_args),
                          std::move(kwargs_keys), std::move(kwargs_values));
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
  text::ExprAST rhs =
      while_kwarg_keys.empty()
          ? text::ExprCall(CallMnemonic(printer->cfg, obj), std::move(while_args))
          : text::ExprCallKw(CallMnemonic(printer->cfg, obj), std::move(while_args),
                             std::move(while_kwarg_keys), std::move(while_kwarg_values));
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
  text::ExprAST rhs =
      scope_kwarg_keys.empty()
          ? text::ExprCall(CallMnemonic(printer->cfg, obj), std::move(scope_args))
          : text::ExprCallKw(CallMnemonic(printer->cfg, obj), std::move(scope_args),
                             std::move(scope_kwarg_keys), std::move(scope_kwarg_values));
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
    List<text::ExprAST> args = OperandList(get_cached, obj->vars, obj->expr);
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
    return text::ExprStmtAST(
        text::ExprCall(CallMnemonic(printer->cfg, obj),
                       OperandList(get_cached, obj->lhs, obj->indices, obj->rhs)));
  });
}

text::NodeAST TextPrint(const Assert& obj, const text::IRPrinter& printer,
                        const refl::AccessPath& path) {
  CachedPrinter cache(printer);
  cache.RunCache(obj->cond, path->Attr("cond"));
  Function get_cached = cache.GetCachedFunction();
  List<String> kwargs_keys;
  List<text::ExprAST> kwargs_values;
  if (obj->attrs.has_value() &&
      AppendAttrsAsKwargs(
          printer->operator()(*obj->attrs, path->Attr("attrs")).cast<text::ExprAST>(), &kwargs_keys,
          &kwargs_values)) {
    return text::ExprStmtAST(text::ExprCallKw(CallMnemonic(printer->cfg, obj),
                                              {get_cached(obj->cond).cast<text::ExprAST>()},
                                              std::move(kwargs_keys), std::move(kwargs_values)));
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
  return text::CallAST(CallMnemonic(printer->cfg, obj), {}, std::move(kwargs_keys),
                       std::move(kwargs_values));
}

// NOLINTEND(bugprone-misplaced-widening-cast,bugprone-narrowing-conversions)

}  // namespace

TVM_FFI_STATIC_INIT_BLOCK() {
  GenericsRegistry* registry = GenericsRegistry::Global();
  registry->Register("std", "__add__", ApplyOperationGeneric<Add, text::OperationASTObj::kAdd>);
  registry->Register("std", "__sub__", ApplyOperationGeneric<Sub, text::OperationASTObj::kSub>);
  registry->Register("std", "__mul__", ApplyOperationGeneric<Mul, text::OperationASTObj::kMult>);
  registry->Register("std", "__floordiv__",
                     ApplyOperationGeneric<FloorDiv, text::OperationASTObj::kFloorDiv>);
  registry->Register("std", "__mod__",
                     ApplyOperationGeneric<FloorMod, text::OperationASTObj::kMod>);
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
  refl::ObjectDef<ObjType>().def_type_attr(           \
      refl::type_attr::kStdSchema,                    \
      static_cast<int64_t>(RefType::ContainerType::RuntimeTypeIndex()))

#define TVM_FFI_STD_OBJECT_DEF_BASE_INIT(ObjType, RefType, ...) \
  refl::ObjectDef<ObjType>(__VA_ARGS__)                         \
      .def_type_attr(refl::type_attr::kStdSchema,               \
                     static_cast<int64_t>(RefType::ContainerType::RuntimeTypeIndex()))

#define TVM_FFI_STD_OBJECT_DEF(ObjType, RefType, Name)  \
  TVM_FFI_STD_OBJECT_DEF_BASE(ObjType, RefType)         \
      .def_type_attr(refl::type_attr::kDialectMnemonic, \
                     Array<String>{String("std"), String(Name)})

#define TVM_FFI_STD_OBJECT_DEF_GENERIC(ObjType, RefType, Name, Generic) \
  TVM_FFI_STD_OBJECT_DEF_BASE(ObjType, RefType)                         \
      .def_type_attr(refl::type_attr::kDialectMnemonic,                 \
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
      .def_rw("vars", &BindObj::vars, refl::AttachFieldFlag::SEqHashDef());
  TVM_FFI_STD_OBJECT_DEF_GENERIC(BindExprObj, BindExpr, "BindExpr", "__bind_expr__")
      .def_rw("expr", &BindExprObj::expr);
  TVM_FFI_STD_OBJECT_DEF_GENERIC(BindVarDefObj, BindVarDef, "BindVarDef", "__bind_var_def__");
  TVM_FFI_STD_OBJECT_DEF(ScopeObj, Scope, "Scope")
      .def_rw("binds", &ScopeObj::binds, refl::AttachFieldFlag::SEqHashDef())
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

#define TVM_FFI_REGISTER_CAST_COMPATIBLE_BUILDER(RefType)                           \
  text::details::RegisterIRPrintBuilder(RefType::ContainerType::RuntimeTypeIndex(), \
                                        RunPrintBuilder<CastCompatiblePrintBuilder<RefType>>)

#define TVM_FFI_REGISTER_BINARY_BUILDER(RefType)                                    \
  text::details::RegisterIRPrintBuilder(RefType::ContainerType::RuntimeTypeIndex(), \
                                        RunPrintBuilder<BinaryPrintBuilder>)

#define TVM_FFI_REGISTER_BUILDER(RefType, Builder)                                  \
  text::details::RegisterIRPrintBuilder(RefType::ContainerType::RuntimeTypeIndex(), \
                                        RunPrintBuilder<Builder>)

  TVM_FFI_REGISTER_CAST_COMPATIBLE_BUILDER(Node);
  TVM_FFI_REGISTER_CAST_COMPATIBLE_BUILDER(Ty);
  TVM_FFI_REGISTER_CAST_COMPATIBLE_BUILDER(Stmt);
  TVM_FFI_REGISTER_CAST_COMPATIBLE_BUILDER(Attrs);
  TVM_FFI_REGISTER_CAST_COMPATIBLE_BUILDER(Aggregate);
  TVM_FFI_REGISTER_CAST_COMPATIBLE_BUILDER(Expr);
  TVM_FFI_REGISTER_BUILDER(Var, VarPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Func, FuncPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Module, ModulePrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Range, RangePrintBuilder);
  TVM_FFI_REGISTER_BUILDER(AnyTy, AnyTyPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(PrimTy, PrimTyPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(TupleType, TupleTypePrintBuilder);
  TVM_FFI_REGISTER_BUILDER(TensorTy, TensorTyPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(IntImm, IntImmPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(FloatImm, FloatImmPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(StringImm, StringImmPrintBuilder);
  TVM_FFI_REGISTER_BINARY_BUILDER(Add);
  TVM_FFI_REGISTER_BINARY_BUILDER(Sub);
  TVM_FFI_REGISTER_BINARY_BUILDER(Mul);
  TVM_FFI_REGISTER_BINARY_BUILDER(FloorDiv);
  TVM_FFI_REGISTER_BINARY_BUILDER(FloorMod);
  TVM_FFI_REGISTER_BINARY_BUILDER(Min);
  TVM_FFI_REGISTER_BINARY_BUILDER(Max);
  TVM_FFI_REGISTER_BINARY_BUILDER(Eq);
  TVM_FFI_REGISTER_BINARY_BUILDER(Ne);
  TVM_FFI_REGISTER_BINARY_BUILDER(Le);
  TVM_FFI_REGISTER_BINARY_BUILDER(Ge);
  TVM_FFI_REGISTER_BINARY_BUILDER(Gt);
  TVM_FFI_REGISTER_BINARY_BUILDER(Lt);
  TVM_FFI_REGISTER_BINARY_BUILDER(And);
  TVM_FFI_REGISTER_BINARY_BUILDER(Or);
  TVM_FFI_REGISTER_BUILDER(Not, NotPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Load, LoadPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Cast, CastPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Call, CallPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(IfStmt, IfStmtPrintBuilder);
  TVM_FFI_REGISTER_CAST_COMPATIBLE_BUILDER(Bind);
  TVM_FFI_REGISTER_BUILDER(BindExpr, BindExprPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(BindVarDef, BindVarDefPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Scope, ScopePrintBuilder);
  TVM_FFI_REGISTER_BUILDER(For, ForPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(While, WhilePrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Store, StorePrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Assert, AssertPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Return, ReturnPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Yield_, YieldPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Break, BreakPrintBuilder);
  TVM_FFI_REGISTER_BUILDER(Continue, ContinuePrintBuilder);
  TVM_FFI_REGISTER_BUILDER(DictAttrs, DictAttrsPrintBuilder);

#undef TVM_FFI_STD_OBJECT_DEF
#undef TVM_FFI_STD_OBJECT_DEF_GENERIC
#undef TVM_FFI_STD_OBJECT_DEF_BASE
#undef TVM_FFI_STD_OBJECT_DEF_BASE_INIT
#undef TVM_FFI_REGISTER_CAST_COMPATIBLE_BUILDER
#undef TVM_FFI_REGISTER_BINARY_BUILDER
#undef TVM_FFI_REGISTER_BUILDER
}

}  // namespace std_
}  // namespace ffi
}  // namespace tvm
