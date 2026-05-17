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

#include <gtest/gtest.h>
#include <tvm/ffi/extra/pyast.h>
#include <tvm/ffi/extra/std.h>
#include <tvm/ffi/reflection/access_path.h>

#include <set>
#include <string>
#include <utility>
#include <vector>

namespace {

namespace ffi = tvm::ffi;
namespace stdir = tvm::ffi::std_;
namespace text = tvm::ffi::pyast;
namespace refl = tvm::ffi::reflection;

TEST(StdDialect, ConstructAndAccessFields) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::IntImm one(i32, 1);
  stdir::Var x(i32, "x");
  stdir::Add add(i32, x, one);

  EXPECT_EQ(ffi::DLDataTypeToString(i32->dtype), "int32");
  EXPECT_EQ(one->value, 1);
  EXPECT_EQ(x->name, "x");
  EXPECT_TRUE(add->a.as<stdir::Var>().has_value());
  EXPECT_TRUE(add->b.as<stdir::IntImm>().has_value());
}

TEST(StdDialect, TextPrintFunction) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Var x(i32, "x");
  stdir::Var y(i32, "y");
  stdir::IntImm one(i32, 1);
  stdir::Add add(i32, x, one);
  stdir::BindExpr bind({y}, ffi::Optional<stdir::Attrs>(), add);
  stdir::Return ret({y});
  stdir::Func func("main", ffi::Optional<stdir::Attrs>(), {x}, ffi::Optional<stdir::Ty>(i32),
                   {bind, ret});
  stdir::Module mod({func});

  text::IRPrinter printer{text::PrinterConfig()};
  text::NodeAST ast = printer->operator()(mod, refl::AccessPath::Root()).cast<text::NodeAST>();
  std::string rendered = ast->ToPython(text::PrinterConfig());

  EXPECT_NE(rendered.find("@std.func"), std::string::npos);
  EXPECT_NE(rendered.find("def main"), std::string::npos);
  EXPECT_NE(rendered.find("x + std.i32(1)"), std::string::npos);
  EXPECT_NE(rendered.find("return y"), std::string::npos);
}

TEST(StdDialect, TextPrintVarDef) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Var y(i32, "y");
  stdir::VarDef def({y}, ffi::Optional<stdir::Attrs>());

  text::IRPrinter printer{text::PrinterConfig()};
  text::NodeAST ast = printer->operator()(def, refl::AccessPath::Root()).cast<text::NodeAST>();

  EXPECT_EQ(ast->ToPython(text::PrinterConfig()), "y = std.VarDef(std.i32)");
}

TEST(StdDialect, TextPrintAssert) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::PrimTy bool_ty(ffi::StringToDLDataType("bool"));
  stdir::Var x(i32, "x");
  stdir::Assert assert_stmt(stdir::Lt(bool_ty, x, stdir::IntImm(i32, 2)));

  text::IRPrinter printer{text::PrinterConfig()};
  text::NodeAST ast =
      printer->operator()(assert_stmt, refl::AccessPath::Root()).cast<text::NodeAST>();

  EXPECT_EQ(ast->ToPython(text::PrinterConfig()), "assert x < std.i32(2)");
}

TEST(StdDialect, TextPrintCallIncludesResultType) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Call call(i32, ffi::String("callee"), {stdir::IntImm(i32, 1)});

  text::IRPrinter printer{text::PrinterConfig()};
  text::NodeAST ast = printer->operator()(call, refl::AccessPath::Root()).cast<text::NodeAST>();

  EXPECT_EQ(ast->ToPython(text::PrinterConfig()), "std.Call(callee, std.i32(1), ty=std.i32)");
}

TEST(StdDialect, DialectPrintMap) {
  ffi::Dict<ffi::String, ffi::Any> values;
  values.Set("tag", ffi::String("demo"));
  stdir::DictAttrs attrs(values);
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));

  text::IRPrinter drop_printer{text::PrinterConfig(
      true, 2, 0, -1, false, {}, ffi::Dict<ffi::String, ffi::String>{{"std", "*"}})};
  text::NodeAST drop_ast =
      drop_printer->operator()(attrs, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(drop_ast->ToPython(drop_printer->cfg), "DictAttrs(tag=\"demo\")");
  text::NodeAST drop_type_ast =
      drop_printer->operator()(i32, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(drop_type_ast->ToPython(drop_printer->cfg), "i32");

  text::IRPrinter rename_printer{text::PrinterConfig(
      true, 2, 0, -1, false, {}, ffi::Dict<ffi::String, ffi::String>{{"std", "core"}})};
  text::NodeAST rename_ast =
      rename_printer->operator()(attrs, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(rename_ast->ToPython(rename_printer->cfg), "core.DictAttrs(tag=\"demo\")");
  text::NodeAST rename_type_ast =
      rename_printer->operator()(i32, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(rename_type_ast->ToPython(rename_printer->cfg), "core.i32");

  text::IRPrinter exact_printer{text::PrinterConfig(
      true, 2, 0, -1, false, {},
      ffi::Dict<ffi::String, ffi::String>{{"std", "core"}, {"std$DictAttrs", "std.MyAttrs"}})};
  text::NodeAST exact_ast =
      exact_printer->operator()(attrs, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(exact_ast->ToPython(exact_printer->cfg), "std.MyAttrs(tag=\"demo\")");
}

TEST(StdDialect, DialectMnemonics) {
  refl::TypeAttrColumn dialect_mnemonic_col(refl::type_attr::kDialectMnemonic);
  std::vector<std::pair<int32_t, std::vector<std::string>>> cases = {
      {stdir::AnyTyObj::RuntimeTypeIndex(), {"std", "Any"}},
      {stdir::PrimTyObj::RuntimeTypeIndex(), {"std", "Prim"}},
      {stdir::TupleTyObj::RuntimeTypeIndex(), {"std", "Tuple"}},
      {stdir::TensorTyObj::RuntimeTypeIndex(), {"std", "Tensor"}},
      {stdir::RangeObj::RuntimeTypeIndex(), {"std", "Range"}},
      {stdir::DictAttrsObj::RuntimeTypeIndex(), {"std", "DictAttrs"}},
      {stdir::VarObj::RuntimeTypeIndex(), {"std", "Var"}},
      {stdir::FuncObj::RuntimeTypeIndex(), {"std", "Func"}},
      {stdir::ModuleObj::RuntimeTypeIndex(), {"std", "Module"}},
      {stdir::IntImmObj::RuntimeTypeIndex(), {"std", "IntImm"}},
      {stdir::FloatImmObj::RuntimeTypeIndex(), {"std", "FloatImm"}},
      {stdir::StringImmObj::RuntimeTypeIndex(), {"std", "StringImm"}},
      {stdir::AddObj::RuntimeTypeIndex(), {"std", "Add"}},
      {stdir::SubObj::RuntimeTypeIndex(), {"std", "Sub"}},
      {stdir::MulObj::RuntimeTypeIndex(), {"std", "Mul"}},
      {stdir::CDivObj::RuntimeTypeIndex(), {"std", "CDiv"}},
      {stdir::FloorDivObj::RuntimeTypeIndex(), {"std", "FloorDiv"}},
      {stdir::FloorModObj::RuntimeTypeIndex(), {"std", "FloorMod"}},
      {stdir::CModObj::RuntimeTypeIndex(), {"std", "CMod"}},
      {stdir::PowObj::RuntimeTypeIndex(), {"std", "Pow"}},
      {stdir::LShiftObj::RuntimeTypeIndex(), {"std", "LShift"}},
      {stdir::RShiftObj::RuntimeTypeIndex(), {"std", "RShift"}},
      {stdir::BitwiseAndObj::RuntimeTypeIndex(), {"std", "BitwiseAnd"}},
      {stdir::BitwiseOrObj::RuntimeTypeIndex(), {"std", "BitwiseOr"}},
      {stdir::BitwiseXorObj::RuntimeTypeIndex(), {"std", "BitwiseXor"}},
      {stdir::MinObj::RuntimeTypeIndex(), {"std", "Min"}},
      {stdir::MaxObj::RuntimeTypeIndex(), {"std", "Max"}},
      {stdir::EqObj::RuntimeTypeIndex(), {"std", "Eq"}},
      {stdir::NeObj::RuntimeTypeIndex(), {"std", "Ne"}},
      {stdir::LeObj::RuntimeTypeIndex(), {"std", "Le"}},
      {stdir::GeObj::RuntimeTypeIndex(), {"std", "Ge"}},
      {stdir::GtObj::RuntimeTypeIndex(), {"std", "Gt"}},
      {stdir::LtObj::RuntimeTypeIndex(), {"std", "Lt"}},
      {stdir::AndObj::RuntimeTypeIndex(), {"std", "And"}},
      {stdir::OrObj::RuntimeTypeIndex(), {"std", "Or"}},
      {stdir::NotObj::RuntimeTypeIndex(), {"std", "Not"}},
      {stdir::BitwiseNotObj::RuntimeTypeIndex(), {"std", "BitwiseNot"}},
      {stdir::AbsObj::RuntimeTypeIndex(), {"std", "Abs"}},
      {stdir::IfExprObj::RuntimeTypeIndex(), {"std", "IfExpr"}},
      {stdir::LoadObj::RuntimeTypeIndex(), {"std", "Load"}},
      {stdir::CastObj::RuntimeTypeIndex(), {"std", "Cast"}},
      {stdir::CallObj::RuntimeTypeIndex(), {"std", "Call"}},
      {stdir::IfStmtObj::RuntimeTypeIndex(), {"std", "IfStmt"}},
      {stdir::ScopeObj::RuntimeTypeIndex(), {"std", "Scope"}},
      {stdir::ForObj::RuntimeTypeIndex(), {"std", "For"}},
      {stdir::WhileObj::RuntimeTypeIndex(), {"std", "While"}},
      {stdir::BindExprObj::RuntimeTypeIndex(), {"std", "BindExpr"}},
      {stdir::VarDefObj::RuntimeTypeIndex(), {"std", "VarDef"}},
      {stdir::StoreObj::RuntimeTypeIndex(), {"std", "Store"}},
      {stdir::AssertObj::RuntimeTypeIndex(), {"std", "Assert"}},
      {stdir::ReturnObj::RuntimeTypeIndex(), {"std", "Return"}},
      {stdir::YieldObj::RuntimeTypeIndex(), {"std", "Yield"}},
      {stdir::BreakObj::RuntimeTypeIndex(), {"std", "Break"}},
      {stdir::ContinueObj::RuntimeTypeIndex(), {"std", "Continue"}},
  };
  std::set<std::string> seen_mnemonics;

  EXPECT_EQ(cases.size(), 54);
  for (const auto& [type_index, expected] : cases) {
    ffi::AnyView value = dialect_mnemonic_col[type_index];

    ASSERT_NE(value.type_index(), ffi::TypeIndex::kTVMFFINone);
    ffi::Array<ffi::String> actual = value.cast<ffi::Array<ffi::String>>();
    ASSERT_EQ(actual.size(), expected.size());
    for (size_t i = 0; i < expected.size(); ++i) {
      EXPECT_EQ(static_cast<std::string>(actual[i]), expected[i]);
    }
    EXPECT_TRUE(seen_mnemonics.insert(expected[0] + "$" + expected[1]).second);
  }
}

TEST(StdDialect, TextSugarPreservesTypedImmediateOperands) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Add add(i32, stdir::IntImm(i32, 1), stdir::IntImm(i32, 2));

  text::IRPrinter printer{text::PrinterConfig()};
  text::NodeAST ast = printer->operator()(add, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(ast->ToPython(text::PrinterConfig()), "std.i32(1) + std.i32(2)");
}

TEST(StdDialect, TextSugarUsesNoOperandStatements) {
  stdir::Break break_stmt;

  text::IRPrinter printer{text::PrinterConfig()};
  text::NodeAST ast =
      printer->operator()(break_stmt, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(ast->ToPython(text::PrinterConfig()), "break");
}

TEST(StdDialect, TextSugarUsesNativeReturnAndYield) {
  text::IRPrinter printer{text::PrinterConfig()};

  text::NodeAST ret =
      printer->operator()(stdir::Return(ffi::List<stdir::Var>{}), refl::AccessPath::Root())
          .cast<text::NodeAST>();
  EXPECT_EQ(ret->ToPython(text::PrinterConfig()), "return");

  text::NodeAST yield =
      printer->operator()(stdir::Yield_(ffi::List<stdir::Var>{}), refl::AccessPath::Root())
          .cast<text::NodeAST>();
  EXPECT_EQ(yield->ToPython(text::PrinterConfig()), "yield");
}

TEST(StdDialect, TextSugarPreservesBindAttrs) {
  ffi::Dict<ffi::String, ffi::Any> values;
  values.Set("tag", ffi::String("demo"));
  stdir::DictAttrs attrs(values);
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));

  text::IRPrinter printer{text::PrinterConfig()};

  text::NodeAST bind_expr = printer
                                ->operator()(stdir::BindExpr({}, ffi::Optional<stdir::Attrs>(attrs),
                                                             stdir::IntImm(i32, 1)),
                                             refl::AccessPath::Root())
                                .cast<text::NodeAST>();
  EXPECT_EQ(bind_expr->ToPython(text::PrinterConfig()), "std.BindExpr(std.i32(1), tag=\"demo\")");

  text::NodeAST bind_var_def =
      printer
          ->operator()(stdir::VarDef({}, ffi::Optional<stdir::Attrs>(attrs)),
                       refl::AccessPath::Root())
          .cast<text::NodeAST>();
  EXPECT_EQ(bind_var_def->ToPython(text::PrinterConfig()), "std.VarDef(tag=\"demo\")");
}

TEST(StdDialect, TextSugarUsesNamedOperands) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Var x(i32, "x");
  stdir::Add add(i32, x, stdir::IntImm(i32, 1));

  text::IRPrinter printer{text::PrinterConfig()};
  text::NodeAST ast = printer->operator()(add, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(ast->ToPython(text::PrinterConfig()), "x + std.i32(1)");
}

TEST(StdDialect, ExprOperatorHelpers) {
  stdir::PrimTy bool_ty(ffi::StringToDLDataType("bool"));
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Var cond(bool_ty, "cond");
  stdir::Var x(i32, "x");

  stdir::Expr add = x + 1;
  stdir::Expr radd = 1 + x;
  stdir::Expr div = x / 2;
  stdir::Expr mod = x % 2;
  stdir::Expr bitwise = ~x;
  stdir::Expr neg = -x;
  stdir::Expr cmp = x < 2;
  stdir::Expr eq = x == 2;
  stdir::Expr min_expr = stdir::min(x, 3);
  stdir::Expr select_expr = stdir::if_then_else(cond, x, stdir::IntImm(i32, 4));

  EXPECT_NE(add.as<stdir::AddObj>(), nullptr);
  EXPECT_NE(radd.as<stdir::AddObj>(), nullptr);
  EXPECT_NE(div.as<stdir::CDivObj>(), nullptr);
  EXPECT_NE(mod.as<stdir::FloorModObj>(), nullptr);
  EXPECT_NE(bitwise.as<stdir::BitwiseNotObj>(), nullptr);
  EXPECT_NE(neg.as<stdir::SubObj>(), nullptr);
  EXPECT_NE(cmp.as<stdir::LtObj>(), nullptr);
  EXPECT_NE(eq.as<stdir::EqObj>(), nullptr);
  EXPECT_NE(min_expr.as<stdir::MinObj>(), nullptr);
  EXPECT_NE(select_expr.as<stdir::IfExprObj>(), nullptr);
}

TEST(StdDialect, ExprOperatorHelpersAreExposedAsGlobalFuncs) {
  stdir::PrimTy bool_ty(ffi::StringToDLDataType("bool"));
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Var cond(bool_ty, "cond");
  stdir::Var x(i32, "x");

  ffi::Function add = ffi::Function::GetGlobalRequired("ffi.std.add");
  ffi::Function eq = ffi::Function::GetGlobalRequired("ffi.std.eq");
  ffi::Function select = ffi::Function::GetGlobalRequired("ffi.std.select");

  stdir::Expr add_expr = add(x, 1).cast<stdir::Expr>();
  stdir::Expr eq_expr = eq(x, 1).cast<stdir::Expr>();
  stdir::Expr select_expr = select(cond, x, 2).cast<stdir::Expr>();

  EXPECT_NE(add_expr.as<stdir::AddObj>(), nullptr);
  EXPECT_NE(eq_expr.as<stdir::EqObj>(), nullptr);
  EXPECT_NE(select_expr.as<stdir::IfExprObj>(), nullptr);
}

TEST(StdDialect, BinaryConstructorsRejectTypePromotionAndErasure) {
  stdir::AnyTy any;
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::PrimTy i64(ffi::StringToDLDataType("int64"));
  stdir::Var x_i32(i32, "x");
  stdir::Var y_i64(i64, "y");
  stdir::IntImm any_one(any, 1);
  stdir::IntImm one_i32(i32, 1);
  stdir::Var x_any(any, "x");

  EXPECT_NO_THROW({ stdir::Add(any, x_any, any_one); });
  EXPECT_NO_THROW({ stdir::Add(any, x_any, one_i32); });
  EXPECT_NO_THROW({ stdir::Add(i32, x_i32, any_one); });
  EXPECT_NO_THROW({ stdir::Add(any, x_i32, one_i32); });
  EXPECT_THROW({ stdir::Add(i32, x_i32, y_i64); }, ffi::Error);
  EXPECT_THROW({ stdir::Add(any, x_i32, y_i64); }, ffi::Error);
}

TEST(StdDialect, UnaryConstructorsRejectTypePromotionAndErasure) {
  stdir::AnyTy any;
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::PrimTy bool_ty(ffi::StringToDLDataType("bool"));
  stdir::Var x_i32(i32, "x");
  stdir::IntImm any_one(any, 1);
  stdir::BoolImm any_true(any, true);
  stdir::Var x_any(any, "x");

  EXPECT_NO_THROW({ stdir::Not(any, x_any); });
  EXPECT_NO_THROW({ stdir::Not(bool_ty, any_true); });
  EXPECT_NO_THROW({ stdir::Not(any, any_true); });
  EXPECT_THROW({ stdir::Not(i32, any_one); }, ffi::Error);
  EXPECT_THROW({ stdir::Not(any, x_i32); }, ffi::Error);
}

TEST(StdDialect, AbstractBasesDoNotHaveDialectMnemonics) {
  refl::TypeAttrColumn dialect_mnemonic_col(refl::type_attr::kDialectMnemonic);

  EXPECT_EQ(dialect_mnemonic_col[stdir::NodeObj::RuntimeTypeIndex()].type_index(),
            ffi::TypeIndex::kTVMFFINone);
  EXPECT_EQ(dialect_mnemonic_col[stdir::TyObj::RuntimeTypeIndex()].type_index(),
            ffi::TypeIndex::kTVMFFINone);
  EXPECT_EQ(dialect_mnemonic_col[stdir::StmtObj::RuntimeTypeIndex()].type_index(),
            ffi::TypeIndex::kTVMFFINone);
  EXPECT_EQ(dialect_mnemonic_col[stdir::AttrsObj::RuntimeTypeIndex()].type_index(),
            ffi::TypeIndex::kTVMFFINone);
  EXPECT_EQ(dialect_mnemonic_col[stdir::AggregateObj::RuntimeTypeIndex()].type_index(),
            ffi::TypeIndex::kTVMFFINone);
  EXPECT_EQ(dialect_mnemonic_col[stdir::ExprObj::RuntimeTypeIndex()].type_index(),
            ffi::TypeIndex::kTVMFFINone);
}

TEST(StdDialect, AbstractBaseTextPrintErrors) {
  stdir::Node node(ffi::make_object<stdir::NodeObj>());
  text::IRPrinter printer{text::PrinterConfig()};

  try {
    printer->operator()(node, refl::AccessPath::Root());
    FAIL() << "Expected base std.Node text printing to fail";
  } catch (const std::exception& error) {
    EXPECT_NE(std::string(error.what()).find("No ffi.std text printer registered for ffi.std.Node"),
              std::string::npos);
  }
}

}  // namespace
