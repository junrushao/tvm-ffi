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
  EXPECT_NE(rendered.find("x + 1"), std::string::npos);
  EXPECT_NE(rendered.find("return y"), std::string::npos);
}

TEST(StdDialect, TextPrintBindVarDef) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Var y(i32, "y");
  stdir::BindVarDef def({y}, ffi::Optional<stdir::Attrs>());

  text::IRPrinter printer{text::PrinterConfig()};
  text::NodeAST ast = printer->operator()(def, refl::AccessPath::Root()).cast<text::NodeAST>();

  EXPECT_EQ(ast->ToPython(text::PrinterConfig()), "y = std.BindVarDef(std.i32)");
}

TEST(StdDialect, TextPrintAssert) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Var x(i32, "x");
  stdir::Assert assert_stmt(stdir::Lt(i32, x, stdir::IntImm(i32, 2)));

  text::IRPrinter printer{text::PrinterConfig()};
  text::NodeAST ast =
      printer->operator()(assert_stmt, refl::AccessPath::Root()).cast<text::NodeAST>();

  EXPECT_EQ(ast->ToPython(text::PrinterConfig()), "assert x < 2");
}

TEST(StdDialect, TextPrintCallIncludesResultType) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Call call(i32, ffi::String("callee"), {stdir::IntImm(i32, 1)});

  text::IRPrinter printer{text::PrinterConfig()};
  text::NodeAST ast = printer->operator()(call, refl::AccessPath::Root()).cast<text::NodeAST>();

  EXPECT_EQ(ast->ToPython(text::PrinterConfig()), "std.Call(std.i32, callee, std.i32(1))");
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
      {stdir::TupleTypeObj::RuntimeTypeIndex(), {"std", "Tuple"}},
      {stdir::TensorTyObj::RuntimeTypeIndex(), {"std", "Tensor"}},
      {stdir::RangeObj::RuntimeTypeIndex(), {"std", "Range"}},
      {stdir::DictAttrsObj::RuntimeTypeIndex(), {"std", "DictAttrs"}},
      {stdir::VarObj::RuntimeTypeIndex(), {"std", "Var"}},
      {stdir::FuncObj::RuntimeTypeIndex(), {"std", "Func"}},
      {stdir::ModuleObj::RuntimeTypeIndex(), {"std", "Module"}},
      {stdir::IntImmObj::RuntimeTypeIndex(), {"std", "IntImm"}},
      {stdir::FloatImmObj::RuntimeTypeIndex(), {"std", "FloatImm"}},
      {stdir::StringImmObj::RuntimeTypeIndex(), {"std", "StringImm"}},
      {stdir::AddObj::RuntimeTypeIndex(), {"std", "Add", "__add__"}},
      {stdir::SubObj::RuntimeTypeIndex(), {"std", "Sub", "__sub__"}},
      {stdir::MulObj::RuntimeTypeIndex(), {"std", "Mul", "__mul__"}},
      {stdir::CDivObj::RuntimeTypeIndex(), {"std", "CDiv", "__truediv__"}},
      {stdir::FloorDivObj::RuntimeTypeIndex(), {"std", "FloorDiv", "__floordiv__"}},
      {stdir::FloorModObj::RuntimeTypeIndex(), {"std", "FloorMod", "__mod__"}},
      {stdir::CModObj::RuntimeTypeIndex(), {"std", "CMod"}},
      {stdir::PowObj::RuntimeTypeIndex(), {"std", "Pow", "__pow__"}},
      {stdir::LShiftObj::RuntimeTypeIndex(), {"std", "LShift", "__lshift__"}},
      {stdir::RShiftObj::RuntimeTypeIndex(), {"std", "RShift", "__rshift__"}},
      {stdir::XorObj::RuntimeTypeIndex(), {"std", "Xor", "__xor__"}},
      {stdir::MinObj::RuntimeTypeIndex(), {"std", "Min", "min"}},
      {stdir::MaxObj::RuntimeTypeIndex(), {"std", "Max", "max"}},
      {stdir::EqObj::RuntimeTypeIndex(), {"std", "Eq", "__eq__"}},
      {stdir::NeObj::RuntimeTypeIndex(), {"std", "Ne", "__ne__"}},
      {stdir::LeObj::RuntimeTypeIndex(), {"std", "Le", "__le__"}},
      {stdir::GeObj::RuntimeTypeIndex(), {"std", "Ge", "__ge__"}},
      {stdir::GtObj::RuntimeTypeIndex(), {"std", "Gt", "__gt__"}},
      {stdir::LtObj::RuntimeTypeIndex(), {"std", "Lt", "__lt__"}},
      {stdir::AndObj::RuntimeTypeIndex(), {"std", "And", "__and__"}},
      {stdir::OrObj::RuntimeTypeIndex(), {"std", "Or", "__or__"}},
      {stdir::NotObj::RuntimeTypeIndex(), {"std", "Not", "__invert__"}},
      {stdir::LoadObj::RuntimeTypeIndex(), {"std", "Load", "__load__"}},
      {stdir::CastObj::RuntimeTypeIndex(), {"std", "Cast", "__cast__"}},
      {stdir::CallObj::RuntimeTypeIndex(), {"std", "Call"}},
      {stdir::IfStmtObj::RuntimeTypeIndex(), {"std", "IfStmt", "__if__"}},
      {stdir::ScopeObj::RuntimeTypeIndex(), {"std", "Scope"}},
      {stdir::ForObj::RuntimeTypeIndex(), {"std", "For", "__for__"}},
      {stdir::WhileObj::RuntimeTypeIndex(), {"std", "While", "__while__"}},
      {stdir::BindExprObj::RuntimeTypeIndex(), {"std", "BindExpr", "__bind_expr__"}},
      {stdir::BindVarDefObj::RuntimeTypeIndex(), {"std", "BindVarDef", "__bind_var_def__"}},
      {stdir::StoreObj::RuntimeTypeIndex(), {"std", "Store", "__store__"}},
      {stdir::AssertObj::RuntimeTypeIndex(), {"std", "Assert", "__assert__"}},
      {stdir::ReturnObj::RuntimeTypeIndex(), {"std", "Return", "__return__"}},
      {stdir::YieldObj::RuntimeTypeIndex(), {"std", "Yield", "__yield__"}},
      {stdir::BreakObj::RuntimeTypeIndex(), {"std", "Break", "__break__"}},
      {stdir::ContinueObj::RuntimeTypeIndex(), {"std", "Continue", "__continue__"}},
  };
  std::set<std::string> seen_mnemonics;
  std::set<std::string> seen_generics;

  EXPECT_EQ(cases.size(), 49);
  for (const auto& [type_index, expected] : cases) {
    ffi::AnyView value = dialect_mnemonic_col[type_index];

    ASSERT_NE(value.type_index(), ffi::TypeIndex::kTVMFFINone);
    ffi::Array<ffi::String> actual = value.cast<ffi::Array<ffi::String>>();
    ASSERT_EQ(actual.size(), expected.size());
    for (size_t i = 0; i < expected.size(); ++i) {
      EXPECT_EQ(static_cast<std::string>(actual[i]), expected[i]);
    }
    EXPECT_TRUE(seen_mnemonics.insert(expected[0] + "$" + expected[1]).second);
    if (expected.size() == 3) {
      EXPECT_TRUE(seen_generics.insert(expected[0] + "$" + expected[2]).second);
    }
  }
}

TEST(StdDialect, TextGenericSugarUsesDialectStackForLiteralOnlyOperands) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Add add(i32, stdir::IntImm(i32, 1), stdir::IntImm(i32, 2));

  text::IRPrinter std_printer{text::PrinterConfig()};
  text::NodeAST std_ast =
      std_printer->operator()(add, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(std_ast->ToPython(text::PrinterConfig()), "1 + 2");

  text::IRPrinter tirx_printer{text::PrinterConfig()};
  tirx_printer->dialects.push_back("tirx");
  text::NodeAST explicit_ast =
      tirx_printer->operator()(add, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(explicit_ast->ToPython(text::PrinterConfig()), "std.Add(std.i32, 1, 2)");
}

TEST(StdDialect, TextGenericSugarUsesDialectStackForNoOperands) {
  stdir::Break break_stmt;

  text::IRPrinter std_printer{text::PrinterConfig()};
  text::NodeAST std_ast =
      std_printer->operator()(break_stmt, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(std_ast->ToPython(text::PrinterConfig()), "break");

  text::IRPrinter tirx_printer{text::PrinterConfig()};
  tirx_printer->dialects.push_back("tirx");
  text::NodeAST explicit_ast =
      tirx_printer->operator()(break_stmt, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(explicit_ast->ToPython(text::PrinterConfig()), "std.Break()");
}

TEST(StdDialect, TextGenericFallbackUsesPositionalMnemonicCall) {
  text::IRPrinter printer{text::PrinterConfig()};
  printer->dialects.push_back("tirx");

  text::NodeAST ret =
      printer->operator()(stdir::Return(ffi::List<stdir::Var>{}), refl::AccessPath::Root())
          .cast<text::NodeAST>();
  EXPECT_EQ(ret->ToPython(text::PrinterConfig()), "std.Return()");

  text::NodeAST yield =
      printer->operator()(stdir::Yield_(ffi::List<stdir::Var>{}), refl::AccessPath::Root())
          .cast<text::NodeAST>();
  EXPECT_EQ(yield->ToPython(text::PrinterConfig()), "std.Yield()");
}

TEST(StdDialect, TextGenericFallbackPreservesBindAttrs) {
  ffi::Dict<ffi::String, ffi::Any> values;
  values.Set("tag", ffi::String("demo"));
  stdir::DictAttrs attrs(values);
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));

  text::IRPrinter printer{text::PrinterConfig()};
  printer->dialects.push_back("tirx");

  text::NodeAST bind_expr = printer
                                ->operator()(stdir::BindExpr({}, ffi::Optional<stdir::Attrs>(attrs),
                                                             stdir::IntImm(i32, 1)),
                                             refl::AccessPath::Root())
                                .cast<text::NodeAST>();
  EXPECT_EQ(bind_expr->ToPython(text::PrinterConfig()), "std.BindExpr(std.i32(1), tag=\"demo\")");

  text::NodeAST bind_var_def =
      printer
          ->operator()(stdir::BindVarDef({}, ffi::Optional<stdir::Attrs>(attrs)),
                       refl::AccessPath::Root())
          .cast<text::NodeAST>();
  EXPECT_EQ(bind_var_def->ToPython(text::PrinterConfig()), "std.BindVarDef(tag=\"demo\")");
}

TEST(StdDialect, TextGenericSugarUsesNonLiteralOperandDialect) {
  stdir::PrimTy i32(ffi::StringToDLDataType("int32"));
  stdir::Var x(i32, "x");
  stdir::Add add(i32, x, stdir::IntImm(i32, 1));

  text::IRPrinter std_printer{text::PrinterConfig()};
  text::NodeAST std_ast =
      std_printer->operator()(add, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(std_ast->ToPython(text::PrinterConfig()), "x + 1");

  text::IRPrinter tirx_printer{text::PrinterConfig()};
  tirx_printer->dialects.push_back("tirx");
  text::NodeAST explicit_ast =
      tirx_printer->operator()(add, refl::AccessPath::Root()).cast<text::NodeAST>();
  EXPECT_EQ(explicit_ast->ToPython(text::PrinterConfig()), "x + 1");
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
  EXPECT_EQ(dialect_mnemonic_col[stdir::BindObj::RuntimeTypeIndex()].type_index(),
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
