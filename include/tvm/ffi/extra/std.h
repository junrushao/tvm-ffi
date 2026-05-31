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
 * \file tvm/ffi/extra/std.h
 * \brief Standard core dialect node definitions.
 */

/*
 * Node
 * |-- Ty
 * |   |-- AnyTy
 * |   |-- PrimTy
 * |   |-- TupleTy
 * |   `-- TensorTy
 * |-- Attrs
 * |   `-- DictAttrs
 * |-- FieldCollectionResult
 * |-- Aggregate
 * |   `-- Range
 * |-- Module
 * |-- Stmt
 * |   |-- Assert / Return / Yield_ / Break / Continue
 * |   |-- IfStmt
 * |   |-- BaseScope
 * |   |   `-- Scope
 * |   |-- BaseFunc
 * |   |   `-- Func
 * |   |-- BaseFor
 * |   |   `-- For
 * |   |-- BaseWhile
 * |   |   `-- While
 * |   |-- BaseBindExpr
 * |   |   `-- BindExpr
 * |   |-- BaseVarDef
 * |   |   `-- VarDef
 * |   `-- Store
 * `-- Expr
 *     |-- Var
 *     |-- Cast
 *     |-- Load
 *     |-- Call
 *     |-- BoolImm / IntImm / FloatImm / StringImm
 *     |-- Add/Sub/Mul/Pow, CDiv/CMod/FloorDiv/FloorMod, LShift/RShift, Min/Max
 *     |-- BitwiseAnd / BitwiseOr / BitwiseXor / BitwiseNot
 *     |-- IfExpr / Abs
 *     |-- Eq / Ne / Le / Ge / Gt / Lt
 *     `-- And / Or / Not
 */
#ifndef TVM_FFI_EXTRA_STD_H_
#define TVM_FFI_EXTRA_STD_H_

#include <tvm/ffi/any.h>
#include <tvm/ffi/container/dict.h>
#include <tvm/ffi/container/list.h>
#include <tvm/ffi/dtype.h>
#include <tvm/ffi/extra/base.h>
#include <tvm/ffi/extra/dataclass.h>
#include <tvm/ffi/object.h>
#include <tvm/ffi/optional.h>
#include <tvm/ffi/string.h>

#include <memory>
#include <optional>
#include <type_traits>
#include <utility>

namespace tvm {
namespace ffi {
namespace std_ {

/*! \brief Base object for all standard dialect nodes. */
struct NodeObj : public Object {
  /// \cond Doxygen_Suppress
  static constexpr bool _type_mutable = true;
  static constexpr TVMFFISEqHashKind _type_s_eq_hash_kind = kTVMFFISEqHashKindTreeNode;
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Node", NodeObj, Object);
  /// \endcond
};

/*! \brief Nullable reference to a standard dialect node. */
struct Node : public ObjectRef {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Node, ObjectRef, NodeObj);
  /// \endcond
};

/*! \brief Base object for standard dialect type nodes. */
struct TyObj : public NodeObj {
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Ty", TyObj, NodeObj);
  /// \endcond
};

/*! \brief Nullable reference to a standard dialect type node. */
struct Ty : public Node {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Ty, Node, TyObj);
  /// \endcond
};

/*! \brief Base object for attribute containers. */
struct AttrsObj : public NodeObj {
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Attrs", AttrsObj, NodeObj);
  /// \endcond
};

/*! \brief Nullable reference to an attribute container. */
struct Attrs : public Node {
  /*! \brief Convert a general FFI value into an attribute container. */
  static Attrs FromAny(AnyView src);

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Attrs, Node, AttrsObj);
  /// \endcond
};

/*! \brief Base object for standard dialect statement nodes. */
struct StmtObj : public NodeObj {
  /// \cond Doxygen_Suppress
  StmtObj() = default;

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Stmt", StmtObj, NodeObj);
  /// \endcond
};

/*! \brief Nullable reference to a standard dialect statement node. */
struct Stmt : public Node {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Stmt, Node, StmtObj);
  /// \endcond
};

}  // namespace std_

template <>
inline constexpr bool use_default_type_traits_v<std_::Attrs> = false;

template <>
struct TypeTraits<std_::Attrs>;

namespace std_ {

/*! \brief Base object for standard dialect aggregate helper nodes. */
struct AggregateObj : public NodeObj {
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Aggregate", AggregateObj, NodeObj);
  /// \endcond
};

/*! \brief Nullable reference to a standard dialect aggregate helper node. */
struct Aggregate : public Node {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Aggregate, Node, AggregateObj);
  /// \endcond
};

/*! \brief Base object for standard dialect expression nodes. */
struct ExprObj : public NodeObj {
  /*! \brief Static type of the expression. */
  Ty ty;

  /// \cond Doxygen_Suppress
  ExprObj() = default;
  explicit ExprObj(Ty ty) : ty(std::move(ty)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Expr", ExprObj, NodeObj);
  /// \endcond
};

/*! \brief Nullable reference to a standard dialect expression node. */
struct Expr : public Node {
  /*! \brief Construct an expression with a static type. */
  explicit Expr(Ty ty) : Expr(make_object<ExprObj>(std::move(ty))) {}
  /*! \brief Convert a general FFI value into an expression. */
  static Expr FromAny(AnyView src);

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Expr, Node, ExprObj);
  /// \endcond
};

}  // namespace std_

template <>
inline constexpr bool use_default_type_traits_v<std_::Expr> = false;

/// \cond Doxygen_Suppress
namespace details {
template <>
inline constexpr bool storage_enabled_v<std_::Expr> = true;
}  // namespace details

template <>
struct TypeTraits<std_::Expr>;
/// \endcond

namespace std_ {

/*! \brief Data object for a named SSA variable. */
struct VarObj : public ExprObj {
  /*! \brief Variable name. */
  String name;

  /// \cond Doxygen_Suppress
  VarObj() = default;
  VarObj(Ty ty, String name) : ExprObj(std::move(ty)), name(std::move(name)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Var", VarObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a named SSA variable. */
struct Var : public Expr {
  /*! \brief Construct a named SSA variable. */
  Var(Ty ty, String name) : Var(make_object<VarObj>(std::move(ty), std::move(name))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Var, Expr, VarObj);
  /// \endcond
};

/*! \brief Base object for scoped statements. */
struct BaseScopeObj : public StmtObj {
  /// \cond Doxygen_Suppress
  BaseScopeObj() = default;

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BaseScope", BaseScopeObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for scoped statements. */
struct BaseScope : public Stmt {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BaseScope, Stmt, BaseScopeObj);
  /// \endcond
};

/*! \brief Base object for standard dialect functions. */
struct BaseFuncObj : public StmtObj {
  /*! \brief Function symbol name. */
  String symbol;
  /*! \brief Function parameters. */
  List<Var> args;
  /*! \brief Optional return type. */
  Optional<Ty> ret_type;

  /// \cond Doxygen_Suppress
  BaseFuncObj() = default;
  BaseFuncObj(String symbol, List<Var> args, Optional<Ty> ret_type)
      : symbol(std::move(symbol)), args(std::move(args)), ret_type(std::move(ret_type)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BaseFunc", BaseFuncObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for standard dialect functions. */
struct BaseFunc : public Stmt {
  /*! \brief Construct a function-like statement base. */
  BaseFunc(String symbol, List<Var> args, Optional<Ty> ret_type)
      : BaseFunc(
            make_object<BaseFuncObj>(std::move(symbol), std::move(args), std::move(ret_type))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BaseFunc, Stmt, BaseFuncObj);
  /// \endcond
};

/*! \brief Data object for a standard dialect function. */
struct FuncObj : public BaseFuncObj {
  /*! \brief Function body statements. */
  List<Stmt> body;
  /*! \brief Optional function attributes. */
  Optional<Attrs> attrs;

  /// \cond Doxygen_Suppress
  FuncObj() = default;
  FuncObj(String symbol, List<Var> args, Optional<Ty> ret_type, List<Stmt> body,
          Optional<Attrs> attrs = {})
      : BaseFuncObj(std::move(symbol), std::move(args), std::move(ret_type)),
        body(std::move(body)),
        attrs(std::move(attrs)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Func", FuncObj, BaseFuncObj);
  /// \endcond
};

/*! \brief Reference wrapper for a standard dialect function. */
struct Func : public BaseFunc {
  /*! \brief Construct a standard dialect function. */
  Func(String symbol, List<Var> args, Optional<Ty> ret_type, List<Stmt> body,
       Optional<Attrs> attrs = {})
      : Func(make_object<FuncObj>(std::move(symbol), std::move(args), std::move(ret_type),
                                  std::move(body), std::move(attrs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Func, BaseFunc, FuncObj);
  /// \endcond
};

/*! \brief Data object for a module containing standard dialect functions. */
struct ModuleObj : public NodeObj {
  /*! \brief Functions contained by the module. */
  List<BaseFunc> funcs;

  /// \cond Doxygen_Suppress
  ModuleObj() = default;
  explicit ModuleObj(List<BaseFunc> funcs) : funcs(std::move(funcs)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Module", ModuleObj, NodeObj);
  /// \endcond
};

/*! \brief Reference wrapper for a module containing standard dialect functions. */
struct Module : public Node {
  /*! \brief Construct a module from its function list. */
  explicit Module(List<BaseFunc> funcs) : Module(make_object<ModuleObj>(std::move(funcs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Module, Node, ModuleObj);
  /// \endcond
};

/*! \brief Data object for a start/extent iteration or indexing range. */
struct RangeObj : public AggregateObj {
  /*! \brief Optional range start. */
  Optional<Expr> start;
  /*! \brief Range extent. */
  Expr extent;
  /*! \brief Optional range step. */
  Optional<Expr> step;

  /// \cond Doxygen_Suppress
  RangeObj() = default;
  explicit RangeObj(Optional<Expr> start, Expr extent, Optional<Expr> step = {});

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Range", RangeObj, AggregateObj);
  /// \endcond
};

/*! \brief Reference wrapper for a start/extent iteration or indexing range. */
struct Range : public Aggregate {
  /*! \brief Construct a start/extent range. */
  explicit Range(Optional<Expr> start, Expr extent, Optional<Expr> step = {})
      : Range(make_object<RangeObj>(std::move(start), std::move(extent), std::move(step))) {}
  /*! \brief Construct a range that starts at zero with the given extent. */
  explicit Range(Expr extent) : Range(Optional<Expr>(), std::move(extent), Optional<Expr>()) {}
  /*! \brief Convert a general FFI value into a range. */
  static Range FromAny(AnyView src);

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Range, Aggregate, RangeObj);
  /// \endcond
};

}  // namespace std_

template <>
inline constexpr bool use_default_type_traits_v<std_::Range> = false;

/// \cond Doxygen_Suppress
namespace details {
template <>
inline constexpr bool storage_enabled_v<std_::Range> = true;
}  // namespace details

template <>
struct TypeTraits<std_::Range>;
/// \endcond

namespace std_ {

/*! \brief Data object for the dynamically typed top type. */
struct AnyTyObj : public TyObj {
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.AnyTy", AnyTyObj, TyObj);
  /// \endcond
};

/*! \brief Reference wrapper for the dynamically typed top type. */
struct AnyTy : public Ty {
  /// \cond Doxygen_Suppress
  explicit AnyTy(ObjectPtr<AnyTyObj> ptr) : Ty(ObjectPtr<TyObj>(std::move(ptr))) {}
  /// \endcond
  /*! \brief Construct the dynamically typed top type. */
  AnyTy() : AnyTy(make_object<AnyTyObj>()) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(AnyTy, Ty, AnyTyObj);
  /// \endcond
};

/*! \brief Data object for a scalar primitive type. */
struct PrimTyObj : public TyObj {
  /*! \brief Primitive scalar data type. */
  DLDataType dtype;

  /// \cond Doxygen_Suppress
  PrimTyObj() = default;
  explicit PrimTyObj(DLDataType dtype) : dtype(dtype) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.PrimTy", PrimTyObj, TyObj);
  /// \endcond
};

/*! \brief Reference wrapper for a scalar primitive type. */
struct PrimTy : public Ty {
  /*! \brief Construct a scalar primitive type. */
  explicit PrimTy(DLDataType dtype) : PrimTy(make_object<PrimTyObj>(dtype)) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(PrimTy, Ty, PrimTyObj);
  /// \endcond
};

/*! \brief Data object for a tuple type. */
struct TupleTyObj : public TyObj {
  /*! \brief Tuple field types. */
  List<Ty> fields;

  /// \cond Doxygen_Suppress
  TupleTyObj() = default;
  explicit TupleTyObj(List<Ty> fields) : fields(std::move(fields)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.TupleTy", TupleTyObj, TyObj);
  /// \endcond
};

/*! \brief Reference wrapper for a tuple type. */
struct TupleTy : public Ty {
  /*! \brief Construct a tuple type from field types. */
  explicit TupleTy(List<Ty> fields) : TupleTy(make_object<TupleTyObj>(std::move(fields))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(TupleTy, Ty, TupleTyObj);
  /// \endcond
};

/*! \brief Data object for a tensor type. */
struct TensorTyObj : public TyObj {
  /*! \brief Tensor shape expressions. */
  List<Expr> shape;
  /*! \brief Tensor element data type. */
  DLDataType dtype;

  /// \cond Doxygen_Suppress
  TensorTyObj() = default;
  TensorTyObj(List<Expr> shape, DLDataType dtype) : shape(std::move(shape)), dtype(dtype) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.TensorTy", TensorTyObj, TyObj);
  /// \endcond
};

/*! \brief Reference wrapper for a tensor type. */
struct TensorTy : public Ty {
  /*! \brief Construct a tensor type from shape expressions and element type. */
  TensorTy(List<Expr> shape, DLDataType dtype)
      : TensorTy(make_object<TensorTyObj>(std::move(shape), dtype)) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(TensorTy, Ty, TensorTyObj);
  /// \endcond
};

/// \cond Doxygen_Suppress
namespace details {
TVM_FFI_EXTRA_CXX_API void CheckArithmeticTys(const char* node_name, const Ty& result_ty,
                                              const Expr& a, const Expr& b);
TVM_FFI_EXTRA_CXX_API void CheckComparisonTys(const char* node_name, const Ty& result_ty,
                                              const Expr& a, const Expr& b);
TVM_FFI_EXTRA_CXX_API void CheckBitwiseBinaryTys(const char* node_name, const Ty& result_ty,
                                                 const Expr& a, const Expr& b);
TVM_FFI_EXTRA_CXX_API void CheckLogicalBinaryTys(const char* node_name, const Ty& result_ty,
                                                 const Expr& a, const Expr& b);
TVM_FFI_EXTRA_CXX_API void CheckArithmeticUnaryTy(const char* node_name, const Ty& result_ty,
                                                  const Expr& operand);
TVM_FFI_EXTRA_CXX_API void CheckBitwiseUnaryTy(const char* node_name, const Ty& result_ty,
                                               const Expr& operand);
TVM_FFI_EXTRA_CXX_API void CheckLogicalUnaryTy(const char* node_name, const Ty& result_ty,
                                               const Expr& operand);
TVM_FFI_EXTRA_CXX_API void CheckIfExprTy(const Ty& result_ty, const Expr& cond,
                                         const Expr& then_expr, const Expr& else_expr);
TVM_FFI_EXTRA_CXX_API void CheckRangeDTypes(const char* node_name, const Optional<Expr>& start,
                                            const Expr& extent, const Optional<Expr>& step);
TVM_FFI_EXTRA_CXX_API void CheckLoadTy(const Ty& result_ty, const Expr& lhs,
                                       const List<Range>& indices);
TVM_FFI_EXTRA_CXX_API void CheckStoreTy(const Expr& lhs, const List<Range>& indices,
                                        const Expr& rhs);
TVM_FFI_EXTRA_CXX_API void CheckScalarBoolCond(const char* node_name, const Expr& cond);

inline void CheckLoopVarTy(const char* node_name, const Expr& extent, const Var& var) {
  TVM_FFI_CHECK(extent.defined(), TypeError) << node_name << " extent must be defined";
  TVM_FFI_CHECK(extent->ty.defined(), TypeError) << node_name << " extent type must be defined";
  TVM_FFI_CHECK(var.defined(), TypeError) << node_name << " loop variable must be defined";
  TVM_FFI_CHECK(var->ty.defined(), TypeError) << node_name << " loop variable type must be defined";
  if (extent->ty.as<AnyTyObj>() != nullptr) return;
  const PrimTyObj* extent_ty = extent->ty.as<PrimTyObj>();
  TVM_FFI_CHECK(extent_ty != nullptr, TypeError)
      << node_name << " extent type must be primitive or Any";
  TVM_FFI_CHECK(DTypeIsInt(extent_ty->dtype), TypeError)
      << node_name << " extent dtype must be integer, got " << DLDataTypeToString(extent_ty->dtype);
}

}  // namespace details
/// \endcond

/*! \brief Data object for a boolean literal. */
struct BoolImmObj : public ExprObj {
  /*! \brief Boolean literal value. */
  bool value = false;

  /// \cond Doxygen_Suppress
  BoolImmObj() = default;
  BoolImmObj(Ty ty, bool value) : ExprObj(std::move(ty)), value(value) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BoolImm", BoolImmObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a boolean literal. */
struct BoolImm : public Expr {
  /*! \brief Construct a boolean literal. */
  BoolImm(Ty ty, bool value) : BoolImm(make_object<BoolImmObj>(std::move(ty), value)) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BoolImm, Expr, BoolImmObj);
  /// \endcond
};

/*! \brief Data object for an integer literal. */
struct IntImmObj : public ExprObj {
  /*! \brief Integer literal value. */
  int64_t value = 0;

  /// \cond Doxygen_Suppress
  IntImmObj() = default;
  IntImmObj(Ty ty, int64_t value) : ExprObj(std::move(ty)), value(value) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.IntImm", IntImmObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for an integer literal. */
struct IntImm : public Expr {
  /*! \brief Construct an integer literal. */
  IntImm(Ty ty, int64_t value) : IntImm(make_object<IntImmObj>(std::move(ty), value)) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(IntImm, Expr, IntImmObj);
  /// \endcond
};

/*! \brief Data object for a floating-point literal. */
struct FloatImmObj : public ExprObj {
  /*! \brief Floating-point literal value. */
  double value = 0.0;

  /// \cond Doxygen_Suppress
  FloatImmObj() = default;
  FloatImmObj(Ty ty, double value) : ExprObj(std::move(ty)), value(value) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.FloatImm", FloatImmObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a floating-point literal. */
struct FloatImm : public Expr {
  /*! \brief Construct a floating-point literal. */
  FloatImm(Ty ty, double value) : FloatImm(make_object<FloatImmObj>(std::move(ty), value)) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(FloatImm, Expr, FloatImmObj);
  /// \endcond
};

/*! \brief Data object for a string literal. */
struct StringImmObj : public ExprObj {
  /*! \brief String literal value. */
  String value;

  /// \cond Doxygen_Suppress
  StringImmObj() = default;
  StringImmObj(Ty ty, String value) : ExprObj(std::move(ty)), value(std::move(value)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.StringImm", StringImmObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a string literal. */
struct StringImm : public Expr {
  /*! \brief Construct a string literal. */
  StringImm(Ty ty, String value)
      : StringImm(make_object<StringImmObj>(std::move(ty), std::move(value))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(StringImm, Expr, StringImmObj);
  /// \endcond
};

/*! \brief Define the object and reference wrapper for a standard binary expression node. */
#define TVM_FFI_STD_BINARY_EXPR(TypeName, CheckFunc)                                         \
  /*! \brief Data object for a binary expression. */                                         \
  struct TypeName##Obj : public ExprObj {                                                    \
    /*! \brief Left operand. */                                                              \
    Expr a;                                                                                  \
    /*! \brief Right operand. */                                                             \
    Expr b;                                                                                  \
                                                                                             \
    /** \cond Doxygen_Suppress */                                                            \
    TypeName##Obj() = default;                                                               \
    TypeName##Obj(Ty ty, Expr a, Expr b)                                                     \
        : ExprObj(std::move(ty)), a(std::move(a)), b(std::move(b)) {                         \
      details::CheckFunc(#TypeName, this->ty, this->a, this->b);                             \
    }                                                                                        \
                                                                                             \
    TVM_FFI_DECLARE_OBJECT_INFO("ffi.std." #TypeName, TypeName##Obj, ExprObj);               \
    /** \endcond */                                                                          \
  };                                                                                         \
                                                                                             \
  /*! \brief Reference wrapper for a binary expression. */                                   \
  struct TypeName : public Expr {                                                            \
    /*! \brief Construct a binary expression. */                                             \
    TypeName(Ty ty, Expr a, Expr b)                                                          \
        : TypeName(make_object<TypeName##Obj>(std::move(ty), std::move(a), std::move(b))) {} \
    /** \cond Doxygen_Suppress */                                                            \
    TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(TypeName, Expr, TypeName##Obj);               \
    /** \endcond */                                                                          \
  }

TVM_FFI_STD_BINARY_EXPR(Add, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(Sub, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(Mul, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(CDiv, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(FloorDiv, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(FloorMod, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(CMod, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(Pow, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(LShift, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(RShift, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(BitwiseAnd, CheckBitwiseBinaryTys);
TVM_FFI_STD_BINARY_EXPR(BitwiseOr, CheckBitwiseBinaryTys);
TVM_FFI_STD_BINARY_EXPR(BitwiseXor, CheckBitwiseBinaryTys);
TVM_FFI_STD_BINARY_EXPR(Min, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(Max, CheckArithmeticTys);
TVM_FFI_STD_BINARY_EXPR(Eq, CheckComparisonTys);
TVM_FFI_STD_BINARY_EXPR(Ne, CheckComparisonTys);
TVM_FFI_STD_BINARY_EXPR(Le, CheckComparisonTys);
TVM_FFI_STD_BINARY_EXPR(Ge, CheckComparisonTys);
TVM_FFI_STD_BINARY_EXPR(Gt, CheckComparisonTys);
TVM_FFI_STD_BINARY_EXPR(Lt, CheckComparisonTys);
TVM_FFI_STD_BINARY_EXPR(And, CheckLogicalBinaryTys);
TVM_FFI_STD_BINARY_EXPR(Or, CheckLogicalBinaryTys);

#undef TVM_FFI_STD_BINARY_EXPR

/*! \brief Data object for logical negation. */
struct NotObj : public ExprObj {
  /*! \brief Operand to negate. */
  Expr operand;

  /// \cond Doxygen_Suppress
  NotObj() = default;
  NotObj(Ty ty, Expr operand) : ExprObj(std::move(ty)), operand(std::move(operand)) {
    details::CheckLogicalUnaryTy("Not", this->ty, this->operand);
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Not", NotObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for logical negation. */
struct Not : public Expr {
  /*! \brief Construct a logical negation expression. */
  Not(Ty ty, Expr operand) : Not(make_object<NotObj>(std::move(ty), std::move(operand))) {}
  /*! \brief Convert a general FFI value into a logical negation expression. */
  static Not FromAny(AnyView src);

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Not, Expr, NotObj);
  /// \endcond
};

/*! \brief Data object for bitwise negation. */
struct BitwiseNotObj : public ExprObj {
  /*! \brief Operand to negate. */
  Expr operand;

  /// \cond Doxygen_Suppress
  BitwiseNotObj() = default;
  BitwiseNotObj(Ty ty, Expr operand) : ExprObj(std::move(ty)), operand(std::move(operand)) {
    details::CheckBitwiseUnaryTy("BitwiseNot", this->ty, this->operand);
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BitwiseNot", BitwiseNotObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for bitwise negation. */
struct BitwiseNot : public Expr {
  /*! \brief Construct a bitwise negation expression. */
  BitwiseNot(Ty ty, Expr operand)
      : BitwiseNot(make_object<BitwiseNotObj>(std::move(ty), std::move(operand))) {}

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BitwiseNot, Expr, BitwiseNotObj);
  /// \endcond
};

/*! \brief Data object for absolute value. */
struct AbsObj : public ExprObj {
  /*! \brief Operand. */
  Expr operand;

  /// \cond Doxygen_Suppress
  AbsObj() = default;
  AbsObj(Ty ty, Expr operand) : ExprObj(std::move(ty)), operand(std::move(operand)) {
    details::CheckArithmeticUnaryTy("Abs", this->ty, this->operand);
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Abs", AbsObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for absolute value. */
struct Abs : public Expr {
  /*! \brief Construct an absolute value expression. */
  Abs(Ty ty, Expr operand) : Abs(make_object<AbsObj>(std::move(ty), std::move(operand))) {}

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Abs, Expr, AbsObj);
  /// \endcond
};

/*! \brief Data object for a ternary expression. */
struct IfExprObj : public ExprObj {
  /*! \brief Condition expression. */
  Expr cond;
  /*! \brief Expression used when the condition is true. */
  Expr then_expr;
  /*! \brief Expression used when the condition is false. */
  Expr else_expr;

  /// \cond Doxygen_Suppress
  IfExprObj() = default;
  IfExprObj(Ty ty, Expr cond, Expr then_expr, Expr else_expr)
      : ExprObj(std::move(ty)),
        cond(std::move(cond)),
        then_expr(std::move(then_expr)),
        else_expr(std::move(else_expr)) {
    details::CheckIfExprTy(this->ty, this->cond, this->then_expr, this->else_expr);
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.IfExpr", IfExprObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a ternary expression. */
struct IfExpr : public Expr {
  /*! \brief Construct a ternary expression. */
  IfExpr(Ty ty, Expr cond, Expr then_expr, Expr else_expr)
      : IfExpr(make_object<IfExprObj>(std::move(ty), std::move(cond), std::move(then_expr),
                                      std::move(else_expr))) {}

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(IfExpr, Expr, IfExprObj);
  /// \endcond
};

}  // namespace std_

template <>
inline constexpr bool use_default_type_traits_v<std_::Not> = false;

template <>
struct TypeTraits<std_::Not>;

namespace std_ {

/*! \brief Data object for loading from an expression with indices. */
struct LoadObj : public ExprObj {
  /*! \brief Expression being loaded. */
  Expr lhs;
  /*! \brief Load indices or slices. */
  List<Range> indices;

  /// \cond Doxygen_Suppress
  LoadObj() = default;
  LoadObj(Ty ty, Expr lhs, List<Range> indices)
      : ExprObj(std::move(ty)), lhs(std::move(lhs)), indices(std::move(indices)) {
    details::CheckLoadTy(this->ty, this->lhs, this->indices);
  }
  LoadObj(Expr lhs, List<Range> indices, Ty ty)
      : LoadObj(std::move(ty), std::move(lhs), std::move(indices)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Load", LoadObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for loading from an expression with indices. */
struct Load : public Expr {
  /*! \brief Construct a load expression. */
  Load(Ty ty, Expr lhs, List<Range> indices)
      : Load(make_object<LoadObj>(std::move(ty), std::move(lhs), std::move(indices))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Load, Expr, LoadObj);
  /// \endcond
};

/*! \brief Data object for a cast expression. */
struct CastObj : public ExprObj {
  /*! \brief Var being cast. */
  Expr value;

  /// \cond Doxygen_Suppress
  CastObj() = default;
  CastObj(Ty ty, Expr value) : ExprObj(std::move(ty)), value(std::move(value)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Cast", CastObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a cast expression. */
struct Cast : public Expr {
  /*! \brief Construct a cast expression. */
  Cast(Ty ty, Expr value) : Cast(make_object<CastObj>(std::move(ty), std::move(value))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Cast, Expr, CastObj);
  /// \endcond
};

/*! \brief Symbolic analyzer object for ffi.std.Expr values. */
struct AnalyzerObj : public Object {
  /// \cond Doxygen_Suppress
  static constexpr bool _type_mutable = true;
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Analyzer", AnalyzerObj, Object);
  /// \endcond

  struct Impl;
  struct Testing;

  /*! \brief Proof strength used by boolean proof queries. */
  enum class ProofStrength : int {
    /*! \brief Default proof strength. */
    kDefault = 0,

    /*! \brief Enable symbolic-bound specific reasoning. */
    kSymbolicBound = 1,
  };

  /*! \brief Construct an empty symbolic analyzer. */
  TVM_FFI_EXTRA_CXX_API AnalyzerObj();

  /*! \brief Destroy the symbolic analyzer. */
  TVM_FFI_EXTRA_CXX_API ~AnalyzerObj();

  /*! \brief Mark a value as globally non-negative. */
  TVM_FFI_EXTRA_CXX_API void MarkGlobalNonNegValue(const Expr& value);

  /*! \brief Bind a variable to an expression in the analyzer state. */
  TVM_FFI_EXTRA_CXX_API void Bind(const Var& var, const Expr& expr, bool allow_override = false);

  /*! \brief Bind a variable to a range in the analyzer state. */
  TVM_FFI_EXTRA_CXX_API void Bind(const Var& var, const Range& range, bool allow_override = false);

  /*! \brief Bind multiple variables to ranges in the analyzer state. */
  TVM_FFI_EXTRA_CXX_API void Bind(const Dict<Var, Range>& variables, bool allow_override = false);

  /*! \brief Return whether expr can be proven greater than or equal to lower_bound. */
  TVM_FFI_EXTRA_CXX_API bool CanProveGreaterEqual(const Expr& expr, int64_t lower_bound);

  /*! \brief Return whether expr can be proven strictly less than upper_bound. */
  TVM_FFI_EXTRA_CXX_API bool CanProveLess(const Expr& expr, int64_t upper_bound);

  /*! \brief Return whether lhs and rhs can be proven equal. */
  TVM_FFI_EXTRA_CXX_API bool CanProveEqual(const Expr& lhs, const Expr& rhs);

  /*! \brief Return whether lhs can be proven less than or equal to a symbolic shape value. */
  TVM_FFI_EXTRA_CXX_API bool CanProveLessEqualThanSymbolicShapeValue(const Expr& lhs,
                                                                     const Expr& shape);

  /*! \brief Return whether cond can be proven true. */
  TVM_FFI_EXTRA_CXX_API bool CanProve(const Expr& cond,
                                      ProofStrength strength = ProofStrength::kDefault);

  /*! \brief Simplify an expression using the analyzer. */
  TVM_FFI_EXTRA_CXX_API Expr Simplify(const Expr& expr, int steps = 2);

 private:
  friend struct IRMutatorWithAnalyzer;
  std::unique_ptr<Impl> impl_;
};

/*! \brief Reference type for symbolic analyzer objects. */
struct Analyzer : public ObjectRef {
  /*! \brief Construct an analyzer reference. */
  Analyzer() : ObjectRef(make_object<AnalyzerObj>()) {}

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(Analyzer, ObjectRef, AnalyzerObj);
  /// \endcond
};

/*! \brief Data object for a call expression. */
struct CallObj : public ExprObj {
  /*! \brief Callee object. */
  Any callee;
  /*! \brief Positional call arguments. */
  List<Expr> args;
  /*! \brief Optional call attributes. */
  Optional<Attrs> attr;

  /// \cond Doxygen_Suppress
  CallObj() = default;
  CallObj(Ty ty, Any callee, List<Expr> args, Optional<Attrs> attr = {})
      : ExprObj(std::move(ty)),
        callee(std::move(callee)),
        args(std::move(args)),
        attr(std::move(attr)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Call", CallObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a call expression. */
struct Call : public Expr {
  /*! \brief Construct a call expression. */
  Call(Ty ty, Any callee, List<Expr> args, Optional<Attrs> attr = {})
      : Call(make_object<CallObj>(std::move(ty), std::move(callee), std::move(args),
                                  std::move(attr))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Call, Expr, CallObj);
  /// \endcond
};

/*! \brief Data object for an if statement. */
struct IfStmtObj : public StmtObj {
  /*! \brief Condition expression. */
  Expr cond;
  /*! \brief Statements executed when the condition is true. */
  List<Stmt> then_body;
  /*! \brief Statements executed when the condition is false. */
  List<Stmt> else_body;

  /// \cond Doxygen_Suppress
  IfStmtObj() = default;
  IfStmtObj(Expr cond, List<Stmt> then_body, List<Stmt> else_body)
      : cond(std::move(cond)), then_body(std::move(then_body)), else_body(std::move(else_body)) {
    details::CheckScalarBoolCond("IfStmt", this->cond);
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.IfStmt", IfStmtObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for an if statement. */
struct IfStmt : public Stmt {
  /*! \brief Construct an if statement. */
  IfStmt(Expr cond, List<Stmt> then_body, List<Stmt> else_body)
      : IfStmt(
            make_object<IfStmtObj>(std::move(cond), std::move(then_body), std::move(else_body))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(IfStmt, Stmt, IfStmtObj);
  /// \endcond
};

/*! \brief Base object for expression bindings. */
struct BaseBindExprObj : public StmtObj {
  /*! \brief Expression being bound. */
  Expr expr;

  /// \cond Doxygen_Suppress
  BaseBindExprObj() = default;
  explicit BaseBindExprObj(Expr expr) : expr(std::move(expr)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BaseBindExpr", BaseBindExprObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for expression bindings. */
struct BaseBindExpr : public Stmt {
  /*! \brief Construct an expression binding base. */
  explicit BaseBindExpr(Expr expr) : BaseBindExpr(make_object<BaseBindExprObj>(std::move(expr))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BaseBindExpr, Stmt, BaseBindExprObj);
  /// \endcond
};

/*! \brief Data object for binding an expression to variables. */
struct BindExprObj : public BaseBindExprObj {
  /*! \brief Variables bound by this statement. */
  List<Var> vars;

  /// \cond Doxygen_Suppress
  BindExprObj() = default;
  BindExprObj(List<Var> vars, Expr expr)
      : BaseBindExprObj(std::move(expr)), vars(std::move(vars)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BindExpr", BindExprObj, BaseBindExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for binding an expression to variables. */
struct BindExpr : public BaseBindExpr {
  /*! \brief Construct an expression binding. */
  BindExpr(List<Var> vars, Expr expr)
      : BindExpr(make_object<BindExprObj>(std::move(vars), std::move(expr))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BindExpr, BaseBindExpr, BindExprObj);
  /// \endcond
};

/*! \brief Base object for variable definitions. */
struct BaseVarDefObj : public StmtObj {
  /// \cond Doxygen_Suppress
  BaseVarDefObj() = default;

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BaseVarDef", BaseVarDefObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for variable definitions. */
struct BaseVarDef : public Stmt {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BaseVarDef, Stmt, BaseVarDefObj);
  /// \endcond
};

/*! \brief Data object for defining variables without a source expression. */
struct VarDefObj : public BaseVarDefObj {
  /*! \brief Variables defined by this statement. */
  List<Var> vars;

  /// \cond Doxygen_Suppress
  VarDefObj() = default;
  explicit VarDefObj(List<Var> vars) : vars(std::move(vars)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.VarDef", VarDefObj, BaseVarDefObj);
  /// \endcond
};

/*! \brief Reference wrapper for defining variables without a source expression. */
struct VarDef : public BaseVarDef {
  /*! \brief Construct a variable definition. */
  explicit VarDef(List<Var> vars) : VarDef(make_object<VarDefObj>(std::move(vars))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(VarDef, BaseVarDef, VarDefObj);
  /// \endcond
};

/*! \brief Data object for a lexical scope block. */
struct ScopeObj : public BaseScopeObj {
  /*! \brief Bindings introduced by the block. */
  List<Stmt> binds;
  /*! \brief Block body statements. */
  List<Stmt> body;
  /*! \brief Optional scope attributes. */
  Optional<Attrs> attrs;

  /// \cond Doxygen_Suppress
  ScopeObj() = default;
  ScopeObj(List<Stmt> binds, List<Stmt> body, Optional<Attrs> attrs = {})
      : binds(std::move(binds)), body(std::move(body)), attrs(std::move(attrs)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Scope", ScopeObj, BaseScopeObj);
  /// \endcond
};

/*! \brief Reference wrapper for a lexical scope block. */
struct Scope : public BaseScope {
  /*! \brief Construct a lexical scope block. */
  Scope(List<Stmt> binds, List<Stmt> body, Optional<Attrs> attrs = {})
      : Scope(make_object<ScopeObj>(std::move(binds), std::move(body), std::move(attrs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Scope, BaseScope, ScopeObj);
  /// \endcond
};

/*! \brief Base object for for loops. */
struct BaseForObj : public StmtObj {
  /*! \brief Loop range extent. */
  Expr extent;
  /*! \brief Loop variable introduced by the header. */
  Var var;

  /// \cond Doxygen_Suppress
  BaseForObj() = default;
  BaseForObj(Expr extent, Var var) : extent(std::move(extent)), var(std::move(var)) {
    details::CheckLoopVarTy("For", this->extent, this->var);
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BaseFor", BaseForObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for for loops. */
struct BaseFor : public Stmt {
  /*! \brief Construct a for-loop base. */
  BaseFor(Expr extent, Var var)
      : BaseFor(make_object<BaseForObj>(std::move(extent), std::move(var))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BaseFor, Stmt, BaseForObj);
  /// \endcond
};

/*! \brief Data object for a for loop. */
struct ForObj : public BaseForObj {
  /*! \brief Optional loop range start. */
  Optional<Expr> start;
  /*! \brief Optional loop range step. */
  Optional<Expr> step;
  /*! \brief Loop body statements. */
  List<Stmt> body;
  /*! \brief Optional loop attributes. */
  Optional<Attrs> attrs;

  /// \cond Doxygen_Suppress
  ForObj() = default;
  ForObj(Optional<Expr> start, Expr extent, Optional<Expr> step, Var var, List<Stmt> body,
         Optional<Attrs> attrs = {})
      : BaseForObj(std::move(extent), std::move(var)),
        start(std::move(start)),
        step(std::move(step)),
        body(std::move(body)),
        attrs(std::move(attrs)) {
    details::CheckRangeDTypes("For", this->start, this->extent, this->step);
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.For", ForObj, BaseForObj);
  /// \endcond
};

/*! \brief Reference wrapper for a for loop. */
struct For : public BaseFor {
  /*! \brief Construct a for loop. */
  For(Optional<Expr> start, Expr extent, Optional<Expr> step, Var var, List<Stmt> body,
      Optional<Attrs> attrs = {})
      : For(make_object<ForObj>(std::move(start), std::move(extent), std::move(step),
                                std::move(var), std::move(body), std::move(attrs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(For, BaseFor, ForObj);
  /// \endcond
};

/*! \brief Base object for while loops. */
struct BaseWhileObj : public StmtObj {
  /*! \brief Loop condition. */
  Expr cond;

  /// \cond Doxygen_Suppress
  BaseWhileObj() = default;
  explicit BaseWhileObj(Expr cond) : cond(std::move(cond)) {
    details::CheckScalarBoolCond("While", this->cond);
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BaseWhile", BaseWhileObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for while loops. */
struct BaseWhile : public Stmt {
  /*! \brief Construct a while-loop base. */
  explicit BaseWhile(Expr cond) : BaseWhile(make_object<BaseWhileObj>(std::move(cond))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BaseWhile, Stmt, BaseWhileObj);
  /// \endcond
};

/*! \brief Data object for a while loop. */
struct WhileObj : public BaseWhileObj {
  /*! \brief Loop body statements. */
  List<Stmt> body;
  /*! \brief Optional loop attributes. */
  Optional<Attrs> attrs;

  /// \cond Doxygen_Suppress
  WhileObj() = default;
  WhileObj(Expr cond, List<Stmt> body, Optional<Attrs> attrs = {})
      : BaseWhileObj(std::move(cond)), body(std::move(body)), attrs(std::move(attrs)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.While", WhileObj, BaseWhileObj);
  /// \endcond
};

/*! \brief Reference wrapper for a while loop. */
struct While : public BaseWhile {
  /*! \brief Construct a while loop. */
  While(Expr cond, List<Stmt> body, Optional<Attrs> attrs = {})
      : While(make_object<WhileObj>(std::move(cond), std::move(body), std::move(attrs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(While, BaseWhile, WhileObj);
  /// \endcond
};

/*! \brief Data object for storing into an expression with indices. */
struct StoreObj : public StmtObj {
  /*! \brief Expression being stored into. */
  Expr lhs;
  /*! \brief Store indices or slices. */
  List<Range> indices;
  /*! \brief Right-hand side value to store. */
  Expr rhs;

  /// \cond Doxygen_Suppress
  StoreObj() = default;
  StoreObj(Expr lhs, List<Range> indices, Expr rhs)
      : lhs(std::move(lhs)), indices(std::move(indices)), rhs(std::move(rhs)) {
    details::CheckStoreTy(this->lhs, this->indices, this->rhs);
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Store", StoreObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for storing into an expression with indices. */
struct Store : public Stmt {
  /*! \brief Construct a store statement. */
  Store(Expr lhs, List<Range> indices, Expr rhs)
      : Store(make_object<StoreObj>(std::move(lhs), std::move(indices), std::move(rhs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Store, Stmt, StoreObj);
  /// \endcond
};

/*! \brief Data object for an assertion statement. */
struct AssertObj : public StmtObj {
  /*! \brief Assertion condition. */
  Expr cond;

  /// \cond Doxygen_Suppress
  AssertObj() = default;
  explicit AssertObj(Expr cond) : cond(std::move(cond)) {
    details::CheckScalarBoolCond("Assert", this->cond);
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Assert", AssertObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for an assertion statement. */
struct Assert : public Stmt {
  /*! \brief Construct an assertion statement. */
  explicit Assert(Expr cond) : Assert(make_object<AssertObj>(std::move(cond))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Assert, Stmt, AssertObj);
  /// \endcond
};

/*! \brief Data object for returning variables from a function. */
struct ReturnObj : public StmtObj {
  /*! \brief Returned variables. */
  List<Var> vars;

  /// \cond Doxygen_Suppress
  ReturnObj() = default;
  explicit ReturnObj(List<Var> vars) : vars(std::move(vars)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Return", ReturnObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for returning variables from a function. */
struct Return : public Stmt {
  /*! \brief Construct a return statement. */
  explicit Return(List<Var> vars) : Return(make_object<ReturnObj>(std::move(vars))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Return, Stmt, ReturnObj);
  /// \endcond
};

/*! \brief Data object for yielding variables from a resumable scope. */
struct YieldObj : public StmtObj {
  /*! \brief Yielded variables. */
  List<Var> vars;

  /// \cond Doxygen_Suppress
  YieldObj() = default;
  explicit YieldObj(List<Var> vars) : vars(std::move(vars)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Yield", YieldObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for yielding variables from a resumable scope. */
struct Yield_ : public Stmt {
  /*! \brief Construct a yield statement. */
  explicit Yield_(List<Var> vars) : Yield_(make_object<YieldObj>(std::move(vars))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Yield_, Stmt, YieldObj);
  /// \endcond
};

/*! \brief Data object for a break statement. */
struct BreakObj : public StmtObj {
  /// \cond Doxygen_Suppress
  BreakObj() = default;

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Break", BreakObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for a break statement. */
struct Break : public Stmt {
  /// \cond Doxygen_Suppress
  explicit Break(ObjectPtr<BreakObj> ptr) : Stmt(ObjectPtr<StmtObj>(std::move(ptr))) {}
  /// \endcond
  /*! \brief Construct a break statement. */
  Break() : Break(make_object<BreakObj>()) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(Break, Stmt, BreakObj);
  /// \endcond
};

/*! \brief Data object for a continue statement. */
struct ContinueObj : public StmtObj {
  /// \cond Doxygen_Suppress
  ContinueObj() = default;

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Continue", ContinueObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for a continue statement. */
struct Continue : public Stmt {
  /// \cond Doxygen_Suppress
  explicit Continue(ObjectPtr<ContinueObj> ptr) : Stmt(ObjectPtr<StmtObj>(std::move(ptr))) {}
  /// \endcond
  /*! \brief Construct a continue statement. */
  Continue() : Continue(make_object<ContinueObj>()) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(Continue, Stmt, ContinueObj);
  /// \endcond
};

/*! \brief Data object for dictionary-backed attributes. */
struct DictAttrsObj : public AttrsObj {
  /*! \brief Attribute key-value pairs. */
  Dict<String, Any> values;

  /// \cond Doxygen_Suppress
  DictAttrsObj() = default;
  explicit DictAttrsObj(Dict<String, Any> values) : values(std::move(values)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.DictAttrs", DictAttrsObj, AttrsObj);
  /// \endcond
};

/*! \brief Reference wrapper for dictionary-backed attributes. */
struct DictAttrs : public Attrs {
  /*! \brief Construct dictionary-backed attributes. */
  explicit DictAttrs(Dict<String, Any> values)
      : DictAttrs(make_object<DictAttrsObj>(std::move(values))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(DictAttrs, Attrs, DictAttrsObj);
  /// \endcond
};

/*! \brief Collected language fields for std-derived dialect text printing. */
struct FieldCollectionResultObj : public NodeObj {
  /*! \brief Positional operands or header arguments. */
  List<Any> args;
  /*! \brief Compile-time attributes printed as keyword arguments. */
  DictAttrs attrs;
  /*! \brief Output variables introduced by this node. */
  List<Var> outs;
  /*! \brief Body nodes owned by this node. */
  List<Node> body;
  /*! \brief Optional type hint printed as a ``ty=`` keyword. */
  Optional<Ty> ty;

  /// \cond Doxygen_Suppress
  FieldCollectionResultObj() = default;
  FieldCollectionResultObj(List<Any> args, DictAttrs attrs, List<Var> outs, List<Node> body,
                           Optional<Ty> ty = std::nullopt)
      : args(std::move(args)),
        attrs(std::move(attrs)),
        outs(std::move(outs)),
        body(std::move(body)),
        ty(std::move(ty)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.FieldCollectionResult", FieldCollectionResultObj, NodeObj);
  /// \endcond
};

/*! \brief Reference wrapper for collected dialect text-format fields. */
struct FieldCollectionResult : public Node {
  /*! \brief Construct a field collection result. */
  FieldCollectionResult(List<Any> args, DictAttrs attrs, List<Var> outs, List<Node> body,
                        Optional<Ty> ty = std::nullopt)
      : FieldCollectionResult(make_object<FieldCollectionResultObj>(
            std::move(args), std::move(attrs), std::move(outs), std::move(body), std::move(ty))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(FieldCollectionResult, Node, FieldCollectionResultObj);
  /// \endcond
};

}  // namespace std_

template <>
struct TypeTraits<std_::Attrs> : public ObjectRefTypeTraitsBase<std_::Attrs> {
  using Base = ObjectRefTypeTraitsBase<std_::Attrs>;

  TVM_FFI_INLINE static std::optional<std_::Attrs> TryCastFromAnyView(const TVMFFIAny* src);
};

template <>
struct TypeTraits<std_::Expr> : public ObjectRefTypeTraitsBase<std_::Expr> {
  using Base = ObjectRefTypeTraitsBase<std_::Expr>;

  TVM_FFI_INLINE static std::optional<std_::Expr> TryCastFromAnyView(const TVMFFIAny* src);
};

template <>
struct TypeTraits<std_::Range> : public ObjectRefTypeTraitsBase<std_::Range> {
  using Base = ObjectRefTypeTraitsBase<std_::Range>;

  TVM_FFI_INLINE static std::optional<std_::Range> TryCastFromAnyView(const TVMFFIAny* src);
};

template <>
struct TypeTraits<std_::Not> : public ObjectRefTypeTraitsBase<std_::Not> {
  using Base = ObjectRefTypeTraitsBase<std_::Not>;

  TVM_FFI_INLINE static std::optional<std_::Not> TryCastFromAnyView(const TVMFFIAny* src);
};

inline std::optional<std_::Attrs> TypeTraits<std_::Attrs>::TryCastFromAnyView(
    const TVMFFIAny* src) {
  if (src->type_index == TypeIndex::kTVMFFINone) {
    return std_::DictAttrs(Dict<String, Any>{});
  }
  if (std::optional<std_::Attrs> attrs = Base::TryCastFromAnyView(src)) {
    return attrs;
  }
  if (std::optional<Dict<String, Any>> values =
          TypeTraits<Dict<String, Any>>::TryCastFromAnyView(src)) {
    return std_::DictAttrs(*std::move(values));
  }
  return std::nullopt;
}

inline std::optional<std_::Expr> TypeTraits<std_::Expr>::TryCastFromAnyView(const TVMFFIAny* src) {
  if (src->type_index == TypeIndex::kTVMFFINone) {
    return std::nullopt;
  }
  if (std::optional<std_::Expr> expr = Base::TryCastFromAnyView(src)) {
    return expr;
  }
  if (src->type_index == TypeIndex::kTVMFFIBool) {
    return std_::BoolImm(std_::AnyTy(), TypeTraits<bool>::CopyFromAnyViewAfterCheck(src));
  }
  if (std::optional<int64_t> value = TypeTraits<int64_t>::TryCastFromAnyView(src)) {
    return std_::IntImm(std_::AnyTy(), *value);
  }
  if (src->type_index == TypeIndex::kTVMFFIFloat) {
    return std_::FloatImm(std_::AnyTy(), TypeTraits<double>::CopyFromAnyViewAfterCheck(src));
  }
  if (std::optional<String> value = TypeTraits<String>::TryCastFromAnyView(src)) {
    return std_::StringImm(std_::AnyTy(), *std::move(value));
  }
  return std::nullopt;
}

inline std::optional<std_::Range> TypeTraits<std_::Range>::TryCastFromAnyView(
    const TVMFFIAny* src) {
  if (src->type_index == TypeIndex::kTVMFFINone) {
    return std::nullopt;
  }
  if (std::optional<std_::Range> range = Base::TryCastFromAnyView(src)) {
    return range;
  }
  if (std::optional<std_::Expr> expr =
          ObjectRefTypeTraitsBase<std_::Expr>::TryCastFromAnyView(src)) {
    return std_::Range(*std::move(expr), std_::IntImm(std_::AnyTy(), 1));
  }
  if (std::optional<int64_t> value = TypeTraits<int64_t>::TryCastFromAnyView(src)) {
    return std_::Range(std_::IntImm(std_::AnyTy(), *value), std_::IntImm(std_::AnyTy(), 1));
  }
  if (src->type_index == TypeIndex::kTVMFFIFloat) {
    return std_::Range(
        std_::FloatImm(std_::AnyTy(), TypeTraits<double>::CopyFromAnyViewAfterCheck(src)),
        std_::IntImm(std_::AnyTy(), 1));
  }
  return std::nullopt;
}

inline std::optional<std_::Not> TypeTraits<std_::Not>::TryCastFromAnyView(const TVMFFIAny* src) {
  if (src->type_index == TypeIndex::kTVMFFINone) {
    return std::nullopt;
  }
  if (std::optional<std_::Not> expr = Base::TryCastFromAnyView(src)) {
    return expr;
  }
  if (std::optional<std_::Expr> expr = TypeTraits<std_::Expr>::TryCastFromAnyView(src)) {
    return std_::Not(std_::AnyTy(), *std::move(expr));
  }
  return std::nullopt;
}

namespace std_ {

inline Attrs Attrs::FromAny(AnyView src) {
  TVMFFIAny src_any = src.CopyToTVMFFIAny();
  if (std::optional<Attrs> attrs = TypeTraits<Attrs>::TryCastFromAnyView(&src_any)) {
    return *std::move(attrs);
  }
  TVM_FFI_THROW(TypeError) << "Unsupported type for conversion to Attrs: " << src.GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

inline Expr Expr::FromAny(AnyView src) {
  TVMFFIAny src_any = src.CopyToTVMFFIAny();
  if (std::optional<Expr> expr = TypeTraits<Expr>::TryCastFromAnyView(&src_any)) {
    return *std::move(expr);
  }
  TVM_FFI_THROW(TypeError) << "Unsupported type for conversion to Expr: " << src.GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

inline Range Range::FromAny(AnyView src) {
  TVMFFIAny src_any = src.CopyToTVMFFIAny();
  if (std::optional<Range> range = TypeTraits<Range>::TryCastFromAnyView(&src_any)) {
    return *std::move(range);
  }
  TVM_FFI_THROW(TypeError) << "Unsupported type for conversion to Range: " << src.GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

inline Not Not::FromAny(AnyView src) {
  TVMFFIAny src_any = src.CopyToTVMFFIAny();
  if (std::optional<Not> expr = TypeTraits<Not>::TryCastFromAnyView(&src_any)) {
    return *std::move(expr);
  }
  TVM_FFI_THROW(TypeError) << "Unsupported type for conversion to Not: " << src.GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

/// \cond Doxygen_Suppress
inline RangeObj::RangeObj(Optional<Expr> start, Expr extent, Optional<Expr> step)
    : start(std::move(start)), extent(std::move(extent)), step(std::move(step)) {
  details::CheckRangeDTypes("Range", this->start, this->extent, this->step);
}
/// \endcond

/*! \brief Cast an expression to a standard dialect type. */
TVM_FFI_EXTRA_CXX_API Expr cast(Ty ty, Expr value);

/*! \brief Declare overloads for a standard dialect binary expression helper. */
#define TVM_FFI_STD_DECLARE_BINARY_OP(FuncName)                   \
  /*! \brief Construct a standard dialect binary expression. */   \
  TVM_FFI_EXTRA_CXX_API Expr FuncName(Expr a, Expr b);            \
  /*! \brief Construct a binary expression with a general rhs. */ \
  TVM_FFI_EXTRA_CXX_API Expr FuncName(Expr a, AnyView b);         \
  /*! \brief Construct a binary expression with a general lhs. */ \
  TVM_FFI_EXTRA_CXX_API Expr FuncName(AnyView a, Expr b)

TVM_FFI_STD_DECLARE_BINARY_OP(add);
TVM_FFI_STD_DECLARE_BINARY_OP(sub);
TVM_FFI_STD_DECLARE_BINARY_OP(mul);
TVM_FFI_STD_DECLARE_BINARY_OP(cdiv);
TVM_FFI_STD_DECLARE_BINARY_OP(cmod);
TVM_FFI_STD_DECLARE_BINARY_OP(truncdiv);
TVM_FFI_STD_DECLARE_BINARY_OP(truncmod);
TVM_FFI_STD_DECLARE_BINARY_OP(floordiv);
TVM_FFI_STD_DECLARE_BINARY_OP(floormod);
TVM_FFI_STD_DECLARE_BINARY_OP(pow);
TVM_FFI_STD_DECLARE_BINARY_OP(min);
TVM_FFI_STD_DECLARE_BINARY_OP(max);
TVM_FFI_STD_DECLARE_BINARY_OP(eq);
TVM_FFI_STD_DECLARE_BINARY_OP(ne);
TVM_FFI_STD_DECLARE_BINARY_OP(le);
TVM_FFI_STD_DECLARE_BINARY_OP(ge);
TVM_FFI_STD_DECLARE_BINARY_OP(gt);
TVM_FFI_STD_DECLARE_BINARY_OP(lt);
TVM_FFI_STD_DECLARE_BINARY_OP(equal);
TVM_FFI_STD_DECLARE_BINARY_OP(not_equal);
TVM_FFI_STD_DECLARE_BINARY_OP(less_equal);
TVM_FFI_STD_DECLARE_BINARY_OP(greater_equal);
TVM_FFI_STD_DECLARE_BINARY_OP(less);
TVM_FFI_STD_DECLARE_BINARY_OP(greater);
TVM_FFI_STD_DECLARE_BINARY_OP(logical_and);
TVM_FFI_STD_DECLARE_BINARY_OP(logical_or);
TVM_FFI_STD_DECLARE_BINARY_OP(left_shift);
TVM_FFI_STD_DECLARE_BINARY_OP(right_shift);
TVM_FFI_STD_DECLARE_BINARY_OP(bitwise_and);
TVM_FFI_STD_DECLARE_BINARY_OP(bitwise_or);
TVM_FFI_STD_DECLARE_BINARY_OP(bitwise_xor);

#undef TVM_FFI_STD_DECLARE_BINARY_OP

/*! \brief Construct unary negation as ``0 - operand``. */
TVM_FFI_EXTRA_CXX_API Expr neg(Expr operand);
/*! \brief Construct logical negation. */
TVM_FFI_EXTRA_CXX_API Expr logical_not(Expr operand);
/*! \brief Construct bitwise negation. */
TVM_FFI_EXTRA_CXX_API Expr bitwise_not(Expr operand);
/*! \brief Alias for bitwise negation. */
TVM_FFI_EXTRA_CXX_API Expr bitwise_neg(Expr operand);
/*! \brief Construct absolute value. */
TVM_FFI_EXTRA_CXX_API Expr abs(Expr operand);
/*! \brief Construct a ternary expression. */
TVM_FFI_EXTRA_CXX_API Expr if_then_else(Expr cond, Expr then_expr, Expr else_expr);
/*! \brief Alias for a ternary expression. */
TVM_FFI_EXTRA_CXX_API Expr select(Expr cond, Expr then_expr, Expr else_expr);

/// \cond Doxygen_Suppress
#define TVM_FFI_STD_BINARY_OPERATOR(Op, FuncName)                                          \
  inline Expr operator Op(Expr a, Expr b) { return FuncName(std::move(a), std::move(b)); } \
  template <typename T, std::enable_if_t<std::is_arithmetic_v<std::decay_t<T>>, int> = 0>  \
  inline Expr operator Op(Expr a, T b) {                                                   \
    return FuncName(std::move(a), AnyView(b));                                             \
  }                                                                                        \
  template <typename T, std::enable_if_t<std::is_arithmetic_v<std::decay_t<T>>, int> = 0>  \
  inline Expr operator Op(T a, Expr b) {                                                   \
    return FuncName(AnyView(a), std::move(b));                                             \
  }

TVM_FFI_STD_BINARY_OPERATOR(+, add)
TVM_FFI_STD_BINARY_OPERATOR(-, sub)
TVM_FFI_STD_BINARY_OPERATOR(*, mul)
TVM_FFI_STD_BINARY_OPERATOR(/, cdiv)
TVM_FFI_STD_BINARY_OPERATOR(%, floormod)
TVM_FFI_STD_BINARY_OPERATOR(<<, left_shift)
TVM_FFI_STD_BINARY_OPERATOR(>>, right_shift)
TVM_FFI_STD_BINARY_OPERATOR(&, bitwise_and)
TVM_FFI_STD_BINARY_OPERATOR(|, bitwise_or)
TVM_FFI_STD_BINARY_OPERATOR(^, bitwise_xor)
TVM_FFI_STD_BINARY_OPERATOR(<, lt)
TVM_FFI_STD_BINARY_OPERATOR(<=, le)
TVM_FFI_STD_BINARY_OPERATOR(>, gt)
TVM_FFI_STD_BINARY_OPERATOR(>=, ge)
TVM_FFI_STD_BINARY_OPERATOR(==, eq)
TVM_FFI_STD_BINARY_OPERATOR(!=, ne)
TVM_FFI_STD_BINARY_OPERATOR(&&, logical_and)
TVM_FFI_STD_BINARY_OPERATOR(||, logical_or)

#undef TVM_FFI_STD_BINARY_OPERATOR
/// \endcond

inline Expr operator-(Expr operand) { return neg(std::move(operand)); }
inline Expr operator+(Expr operand) { return operand; }
inline Expr operator!(Expr operand) { return logical_not(std::move(operand)); }
inline Expr operator~(Expr operand) { return bitwise_not(std::move(operand)); }

}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_STD_H_
